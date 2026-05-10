import sys
import cv2
import numpy as np
from PIL import ImageGrab, Image, ImageTk
import tkinter as tk
from tkinter import messagebox, filedialog
from collections import defaultdict
from typing import List, Tuple, Set, Dict

# 设置DPI感知，让Windows不要自动缩放程序
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass

class GridImageRecognizer:
    """图像网格识别器"""

    def __init__(self):
        self.grid = []
        self._board_crop_bbox = None
        self._last_h_peaks = None
        self._last_v_peaks = None

    def _cluster_lines(self, lines, threshold=10):
        if not lines:
            return []
        lines = sorted(lines)
        clusters = []
        current_cluster = [lines[0]]
        for line in lines[1:]:
            if line - current_cluster[-1] < threshold:
                current_cluster.append(line)
            else:
                clusters.append(current_cluster)
                current_cluster = [line]
        clusters.append(current_cluster)
        return [sum(c) / len(c) for c in clusters]

    def _find_grid_lines(self, edges, height, width):
        horizontal_projection = np.sum(edges, axis=0)
        vertical_projection = np.sum(edges, axis=1)

        def find_peaks(projection, threshold_ratio=0.1):
            threshold = np.max(projection) * threshold_ratio
            peaks, in_peak, peak_start = [], False, 0
            for i, val in enumerate(projection):
                if val > threshold:
                    if not in_peak:
                        in_peak, peak_start = True, i
                else:
                    if in_peak:
                        in_peak = False
                        peaks.append((peak_start + i) // 2)
            if in_peak:
                peaks.append((peak_start + len(projection)) // 2)
            return peaks

        h_lines = find_peaks(vertical_projection, 0.15)
        v_lines = find_peaks(horizontal_projection, 0.15)

        if len(h_lines) < 3 or len(v_lines) < 3:
            min_line_length = min(width, height) // 5
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40,
                                    minLineLength=min_line_length, maxLineGap=15)
            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    if abs(x2 - x1) > abs(y2 - y1):
                        h_lines.append((y1 + y2) / 2)
                    else:
                        v_lines.append((x1 + x2) / 2)

        return h_lines, v_lines

    def recognize_from_image(self, image):
        open_cv_image = np.array(image)
        if len(open_cv_image.shape) == 3 and open_cv_image.shape[2] == 4:
            open_cv_image = open_cv_image[:, :, :3]
        open_cv_image = open_cv_image[:, :, ::-1].copy()
        
        height, width = open_cv_image.shape[:2]
        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100, apertureSize=3)
        
        h_lines, v_lines = self._find_grid_lines(edges, height, width)

        if len(h_lines) < 2 or len(v_lines) < 2:
            return None

        h_lines = self._cluster_lines(h_lines, threshold=height // 25)
        v_lines = self._cluster_lines(v_lines, threshold=width // 25)

        if len(h_lines) < 2 or len(v_lines) < 2:
            return None

        if len(h_lines) > 16 or len(v_lines) > 16:
            return None

        h_lines, v_lines = sorted(h_lines), sorted(v_lines)
        self._last_h_peaks = list(h_lines)
        self._last_v_peaks = list(v_lines)
        cells = []
        for i in range(len(h_lines) - 1):
            row = []
            for j in range(len(v_lines) - 1):
                x1, y1, x2, y2 = int(v_lines[j]), int(h_lines[i]), int(v_lines[j+1]), int(h_lines[i+1])
                row.append(open_cv_image[y1:y2, x1:x2])
            cells.append(row)
        
        if not cells or not cells[0]:
            return None
        
        color_list = []
        for row in cells:
            color_row = []
            for cell in row:
                color_row.append(self._get_dominant_color(cell, use_center=True))
            color_list.append(color_row)
        
        all_colors = [c for row in color_list for c in row if c is not None]
        if not all_colors:
            return None
        
        grid_rows, grid_cols = len(color_list), len(color_list[0])
        target_colors = max(grid_rows, grid_cols)
        
        if len(all_colors) < target_colors:
            target_colors = len(all_colors)
        
        color_array = np.array(all_colors, dtype=np.float32)
        normalized = np.zeros_like(color_array)
        normalized[:, 0] = color_array[:, 0] / 180.0
        normalized[:, 1] = color_array[:, 1] / 255.0
        normalized[:, 2] = color_array[:, 2] / 255.0
        
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 300, 0.0001)
        try:
            compactness, labels, centers = cv2.kmeans(
                normalized.reshape((-1, 3)), target_colors, None, criteria, 30, cv2.KMEANS_PP_CENTERS)
            best_labels, best_centers = labels.flatten(), centers
        except:
            return [[1 if c else 0 for c in row] for row in color_list]

        merge_map = {}
        n_clusters = len(best_centers)
        for i in range(n_clusters):
            merge_map[i] = i
        for i in range(n_clusters):
            for j in range(i + 1, n_clusters):
                dist = np.linalg.norm(best_centers[i] - best_centers[j])
                if dist < 0.08:
                    root_i = i
                    while merge_map[root_i] != root_i:
                        root_i = merge_map[root_i]
                    root_j = j
                    while merge_map[root_j] != root_j:
                        root_j = merge_map[root_j]
                    if root_i != root_j:
                        merge_map[max(root_i, root_j)] = min(root_i, root_j)
        
        remap = {}
        new_id = 0
        for i in range(n_clusters):
            root = i
            while merge_map[root] != root:
                root = merge_map[root]
            if root not in remap:
                remap[root] = new_id
                new_id += 1
            remap[i] = remap[root]

        merged_centers = {}
        for i in range(n_clusters):
            mroot = remap[i]
            if mroot not in merged_centers:
                merged_centers[mroot] = []
            merged_centers[mroot].append(best_centers[i])
        for mroot in merged_centers:
            merged_centers[mroot] = np.mean(merged_centers[mroot], axis=0)

        label_idx, result = 0, []
        for row in color_list:
            row_result = []
            for color in row:
                if color is None:
                    row_result.append(0)
                else:
                    raw_hash = (color[0] / 180.0, color[1] / 255.0, color[2] / 255.0)
                    best_cluster = min(merged_centers.items(), key=lambda x: np.linalg.norm(raw_hash - x[1]))
                    row_result.append(best_cluster[0] + 1)
                    label_idx += 1
            result.append(row_result)
        return result

    def _get_dominant_color(self, cell, use_center=False):
        if cell.size == 0:
            return None
        if use_center:
            h, w = cell.shape[:2]
            margin_h, margin_w = int(h * 0.2), int(w * 0.2)
            if margin_h > 0 and margin_w > 0:
                cell = cell[margin_h:h-margin_h, margin_w:w-margin_w]
                if cell.size == 0:
                    return None
        hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)
        avg_h, avg_s, avg_v = np.mean(hsv[:, :, 0]), np.mean(hsv[:, :, 1]), np.mean(hsv[:, :, 2])
        if avg_s < 10 or (avg_v > 245 and avg_s < 25):
            return None
        return (avg_h, avg_s, avg_v)

    def get_cell_center(self, row, col):
        if self._last_h_peaks is None or self._last_v_peaks is None:
            return None
        if row < 0 or row >= len(self._last_h_peaks) - 1:
            return None
        if col < 0 or col >= len(self._last_v_peaks) - 1:
            return None
        cx = (self._last_v_peaks[col] + self._last_v_peaks[col + 1]) / 2
        cy = (self._last_h_peaks[row] + self._last_h_peaks[row + 1]) / 2
        return (cx, cy)

    # BETA: 全屏截图自动定位棋盘区域，算法仍在优化中
    def auto_detect_board(self, image):
        self._board_crop_bbox = None
        open_cv_image = np.array(image)
        if len(open_cv_image.shape) == 3 and open_cv_image.shape[2] == 4:
            open_cv_image = open_cv_image[:, :, :3]
        open_cv_image_bgr = open_cv_image[:, :, ::-1].copy()

        orig_h, orig_w = open_cv_image_bgr.shape[:2]

        target = 400
        scale = min(1.0, target / max(orig_h, orig_w))
        if scale < 1.0:
            small = cv2.resize(open_cv_image_bgr, (int(orig_w * scale), int(orig_h * scale)))
        else:
            small = open_cv_image_bgr
        small_h, small_w = small.shape[:2]

        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        gx = np.abs(cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3))
        gy = np.abs(cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3))
        edge = np.clip(gx + gy, 0, 255).astype(np.uint8)

        _, binary = cv2.threshold(edge, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        h_proj = np.sum(binary > 0, axis=1).astype(np.float64)
        v_proj = np.sum(binary > 0, axis=0).astype(np.float64)

        radius = max(5, min(small_w, small_h) // 6)
        kernel = np.ones(radius * 2 + 1) / (radius * 2 + 1)
        h_env = np.convolve(h_proj, kernel, mode='same')
        v_env = np.convolve(v_proj, kernel, mode='same')

        if h_env.max() <= 0 or v_env.max() <= 0:
            return None

        h_thresh = h_env.max() * 0.3
        v_thresh = v_env.max() * 0.3

        def find_regions(signal, thresh):
            regions = []
            in_region = False
            start = 0
            for i in range(len(signal)):
                if signal[i] >= thresh and not in_region:
                    in_region = True
                    start = i
                elif signal[i] < thresh and in_region:
                    in_region = False
                    if i - start >= 3:
                        regions.append((start, i - 1))
            if in_region and len(signal) - start >= 3:
                regions.append((start, len(signal) - 1))
            return regions

        h_regions = find_regions(h_env, h_thresh)
        v_regions = find_regions(v_env, v_thresh)

        if not h_regions or not v_regions:
            return None

        best = None
        best_score = 0
        for hy1, hy2 in h_regions:
            for vx1, vx2 in v_regions:
                rw = vx2 - vx1
                rh = hy2 - hy1
                if rw < 10 or rh < 10:
                    continue
                aspect = max(rw, rh) / max(min(rw, rh), 1)
                if aspect > 1.8:
                    continue
                score = min(rw, rh) * (2.0 - aspect)
                if score > best_score:
                    best_score = score
                    best = (vx1, hy1, vx2, hy2)

        if best is None:
            return None

        vx1, hy1, vx2, hy2 = best
        if scale < 1.0:
            inv = 1.0 / scale
            vx1, hy1 = int(vx1 * inv), int(hy1 * inv)
            vx2, hy2 = int(vx2 * inv), int(hy2 * inv)

        margin = 15
        vx1 = max(0, vx1 - margin)
        hy1 = max(0, hy1 - margin)
        vx2 = min(orig_w, vx2 + margin)
        hy2 = min(orig_h, hy2 + margin)

        cropped = open_cv_image_bgr[hy1:hy2, vx1:vx2]
        self._board_crop_bbox = (vx1, hy1, vx2, hy2)
        return Image.fromarray(cropped[:, :, ::-1])


class DuducoPuzzleSolver:
    """嘟嘟可谜题求解器"""
    
    def __init__(self, grid: List[List[int]], num_colors: int):
        self.grid = grid
        self.size = len(grid)
        if self.size > 15:
            raise ValueError(f"网格大小 {self.size} 超过上限 15")
        self.num_colors = num_colors
        self.regions = self._find_regions()
        self.solutions = []
        self.current_placement = {}
        self.duducos = {}
        self.no_duduco_rows = set()
        self.no_duduco_cols = set()
        self.no_duduco_positions = set()
    
    def solve(self):
        self._detection_loop()
        while self._mini_backtrack_two_colors():
            self._detection_loop()
        self._solve_region(len(self.duducos))
        return self.solutions

    def format_solution(self, solution: Dict[int, Tuple[int, int]]) -> str:
        result = []
        result.append(f"网格大小: {self.size}x{self.size}")
        result.append(f"嘟嘟可数量: {len(solution)}")
        result.append("")
        
        result.append("解法结果（*表示嘟嘟可位置）：")
        header = "   | " + " ".join(f"{i+1:2d}" for i in range(self.size))
        result.append(header)
        result.append("---+-" + "--" * self.size)
        
        for r in range(self.size):
            row_str = f"{r+1:2d} | "
            for c in range(self.size):
                pos = (r, c)
                if pos in solution.values():
                    row_str += " * "
                else:
                    row_str += f"{self.grid[r][c]:2d} "
            result.append(row_str)
        
        result.append("")
        result.append("嘟嘟可位置详情：")
        for color, (r, c) in sorted(solution.items(), key=lambda x: x[1][0]):
            result.append(f"  颜色{color}: ({r+1}, {c+1})")
        
        return "\n".join(result)

    def _find_regions(self) -> Dict[int, List[Tuple[int, int]]]:
        visited, regions = set(), defaultdict(list)
        for r in range(self.size):
            for c in range(self.size):
                if (r, c) not in visited:
                    color = self.grid[r][c]
                    regions[color].append(self._bfs_region(r, c, color, visited))
        return regions

    def _bfs_region(self, start_r: int, start_c: int, color: int, visited: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
        region, queue, directions = [], [(start_r, start_c)], [(-1, 0), (1, 0), (0, -1), (0, 1)]
        while queue:
            r, c = queue.pop(0)
            if (r, c) in visited or self.grid[r][c] != color:
                continue
            visited.add((r, c))
            region.append((r, c))
            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.size and 0 <= nc < self.size and (nr, nc) not in visited:
                    if self.grid[nr][nc] == color:
                        queue.append((nr, nc))
        return region

    def _is_valid_position(self, r: int, c: int) -> bool:
        return (r not in self.no_duduco_rows and 
                c not in self.no_duduco_cols and 
                (r, c) not in self.no_duduco_positions)

    def _mark_placement(self, color: int, pos: Tuple[int, int]):
        r, c = pos
        self.duducos[color] = pos
        self.no_duduco_rows.add(r)
        self.no_duduco_cols.add(c)
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.size and 0 <= nc < self.size:
                    self.no_duduco_positions.add((nr, nc))

    def _detect_last_cell(self) -> bool:
        for r in range(self.size):
            if r in self.no_duduco_rows:
                continue
            candidates = [(r, c) for c in range(self.size) if c not in self.no_duduco_cols and (r, c) not in self.no_duduco_positions]
            if len(candidates) == 1:
                r, c = candidates[0]
                color = self.grid[r][c]
                if color not in self.duducos and color not in self.current_placement:
                    self._mark_placement(color, candidates[0])
                    return True
        
        for c in range(self.size):
            if c in self.no_duduco_cols:
                continue
            candidates = [(r, c) for r in range(self.size) if self._is_valid_position(r, c)]
            if len(candidates) == 1:
                r, c = candidates[0]
                color = self.grid[r][c]
                if color not in self.duducos and color not in self.current_placement:
                    self._mark_placement(color, candidates[0])
                    return True
        return False

    def _detect_n_color_shared_rows(self, n: int) -> bool:
        updated = False
        colors = list(self.regions.keys())
        if len(colors) < n:
            return updated
        
        from itertools import combinations
        
        for color_combination in combinations(colors, n):
            if any(c in self.duducos or c in self.current_placement for c in color_combination):
                continue
            
            all_rows = set()
            for color in color_combination:
                region = self.regions[color][0]
                for pos in region:
                    r, c = pos
                    if self._is_valid_position(r, c):
                        all_rows.add(r)
            
            if len(all_rows) == n:
                for r in all_rows:
                    for c in range(self.size):
                        color_at_pos = self.grid[r][c]
                        if color_at_pos not in color_combination:
                            pos = (r, c)
                            if pos not in self.no_duduco_positions:
                                self.no_duduco_positions.add(pos)
                                updated = True
        
        for color_combination in combinations(colors, n):
            if any(c in self.duducos or c in self.current_placement for c in color_combination):
                continue
            
            all_cols = set()
            for color in color_combination:
                region = self.regions[color][0]
                for pos in region:
                    r, c = pos
                    if self._is_valid_position(r, c):
                        all_cols.add(c)
            
            if len(all_cols) == n:
                for c in all_cols:
                    for r in range(self.size):
                        color_at_pos = self.grid[r][c]
                        if color_at_pos not in color_combination:
                            pos = (r, c)
                            if pos not in self.no_duduco_positions:
                                self.no_duduco_positions.add(pos)
                                updated = True
        return updated

    def _detect_surrounded_exclusion(self) -> bool:
        updated = False
        for r in range(self.size):
            for c in range(self.size):
                if not self._is_valid_position(r, c):
                    continue
                neighbors = set()
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.size and 0 <= nc < self.size:
                            neighbors.add((nr, nc))

                for color, regions_list in self.regions.items():
                    if color in self.duducos or color in self.current_placement:
                        continue
                    region = regions_list[0]
                    unmarked = [p for p in region if self._is_valid_position(p[0], p[1])]
                    if not unmarked:
                        continue
                    if all(p in neighbors for p in unmarked):
                        self.no_duduco_positions.add((r, c))
                        updated = True
                        break
        return updated

    def _detection_loop(self):
        max_iterations = 100
        for iteration in range(max_iterations):
            changed = False
            
            if self._detect_last_cell():
                changed = True
            for n in range(1, self.size + 1):
                if self._detect_n_color_shared_rows(n):
                    changed = True
            if self._detect_surrounded_exclusion():
                changed = True
            
            if not changed:
                break

    def _mini_backtrack_two_colors(self) -> bool:
        color_candidates = {}
        for color in self.regions:
            if color in self.duducos or color in self.current_placement:
                continue
            region = self.regions[color][0]
            valid = [pos for pos in region if self._is_valid_position(pos[0], pos[1])]
            if valid:
                color_candidates[color] = valid

        if len(color_candidates) < 2:
            return False

        sorted_colors = sorted(color_candidates.items(), key=lambda x: len(x[1]))
        (color1, positions1), (color2, positions2) = sorted_colors[0], sorted_colors[1]

        valid_combinations = []
        for pos1 in positions1:
            for pos2 in positions2:
                if pos1 == pos2:
                    continue
                r1, c1 = pos1
                r2, c2 = pos2
                if r1 == r2 or c1 == c2:
                    continue
                if abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1:
                    continue
                valid_combinations.append((pos1, pos2))

        if not valid_combinations:
            return False

        branch_new_duducos = {}
        branch_new_no_pos = []

        for pos1, pos2 in valid_combinations:
            old_duducos = self.duducos.copy()
            old_no_rows = self.no_duduco_rows.copy()
            old_no_cols = self.no_duduco_cols.copy()
            old_no_pos = self.no_duduco_positions.copy()

            self.duducos[color1] = pos1
            self.duducos[color2] = pos2
            r1, c1 = pos1
            r2, c2 = pos2
            self.no_duduco_rows.add(r1)
            self.no_duduco_rows.add(r2)
            self.no_duduco_cols.add(c1)
            self.no_duduco_cols.add(c2)
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    nr1, nc1 = r1 + dr, c1 + dc
                    nr2, nc2 = r2 + dr, c2 + dc
                    if 0 <= nr1 < self.size and 0 <= nc1 < self.size:
                        self.no_duduco_positions.add((nr1, nc1))
                    if 0 <= nr2 < self.size and 0 <= nc2 < self.size:
                        self.no_duduco_positions.add((nr2, nc2))

            self._detection_loop()

            new_duducos = {c: p for c, p in self.duducos.items()
                           if c not in old_duducos and c != color1 and c != color2}
            branch_new_duducos[(pos1, pos2)] = new_duducos
            branch_new_no_pos.append(self.no_duduco_positions - old_no_pos)

            self.duducos = old_duducos
            self.no_duduco_rows = old_no_rows
            self.no_duduco_cols = old_no_cols
            self.no_duduco_positions = old_no_pos

        if not branch_new_duducos:
            return False

        found = False

        branch_sets = [set(d.keys()) for d in branch_new_duducos.values()]
        common_colors = branch_sets[0]
        for s in branch_sets[1:]:
            common_colors &= s

        if common_colors:
            for color in common_colors:
                if color in self.duducos:
                    continue
                positions = [branch[color] for branch in branch_new_duducos.values()]
                if len(set(positions)) == 1:
                    self._mark_placement(color, positions[0])
                    found = True

        if branch_new_no_pos:
            common_no = branch_new_no_pos[0].copy()
            for s in branch_new_no_pos[1:]:
                common_no &= s
            for pos in common_no:
                if pos not in self.no_duduco_positions:
                    self.no_duduco_positions.add(pos)
                    found = True

        return found

    def _solve_region(self, placed_count: int) -> bool:
        if placed_count >= len(self.regions):
            solution = {**self.duducos, **self.current_placement}
            self.solutions.append(solution)
            return True

        for color in sorted(self.regions.keys()):
            if color in self.duducos or color in self.current_placement:
                continue
                
            region = self.regions[color][0]
            valid_positions = [pos for pos in region if self._is_valid_position(pos[0], pos[1])]
            
            if not valid_positions:
                return False
            
            for pos in valid_positions:
                self.current_placement[color] = pos
                r, c = pos
                
                old_no_duduco_rows = self.no_duduco_rows.copy()
                old_no_duduco_cols = self.no_duduco_cols.copy()
                old_no_duduco_positions = self.no_duduco_positions.copy()
                
                self.no_duduco_rows.add(r)
                self.no_duduco_cols.add(c)
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.size and 0 <= nc < self.size:
                            self.no_duduco_positions.add((nr, nc))
                
                if self._solve_region(placed_count + 1):
                    return True
                
                self.no_duduco_rows = old_no_duduco_rows
                self.no_duduco_cols = old_no_duduco_cols
                self.no_duduco_positions = old_no_duduco_positions
                del self.current_placement[color]
        return False

class ScreenshotSelector:
    """截图选择器"""

    def __init__(self, parent):
        self.parent = parent
        self.start_x = self.start_y = self.current_x = self.current_y = 0
        self.rect = None
        self.screenshot = None
        self.bbox = None

        import ctypes
        user32 = ctypes.windll.user32
        self.screen_width = user32.GetSystemMetrics(0)
        self.screen_height = user32.GetSystemMetrics(1)

        self.root = tk.Toplevel(parent)
        self.root.overrideredirect(True)
        self.root.attributes('-alpha', 0.3)
        self.root.attributes('-topmost', True)
        self.root.geometry(f'{self.screen_width}x{self.screen_height}+0+0')

        self.canvas = tk.Canvas(self.root, cursor='cross', bg='gray', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind('<ButtonPress-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.root.bind('<Escape>', self.on_escape)

    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.rect = None

    def on_drag(self, event):
        self.current_x, self.current_y = event.x, event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.current_x, self.current_y,
            outline='red', width=2)

    def on_release(self, event):
        x1, y1 = min(self.start_x, self.current_x), min(self.start_y, self.current_y)
        x2, y2 = max(self.start_x, self.current_x), max(self.start_y, self.current_y)
        if x2 - x1 > 10 and y2 - y1 > 10:
            self.screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            self.bbox = (x1, y1, x2, y2)
        self.root.destroy()

    def on_escape(self, event):
        self.root.destroy()

class MainWindow:
    """主窗口 - 整合图像识别和解题器，自动显示结果"""

    def __init__(self, root):
        self.root = root
        self.root.title("寻找嘟嘟可")
        self.root.geometry("720x660")

        self.recognizer = GridImageRecognizer()
        self.current_image = None
        self.recognized_grid = None
        self.solution = None
        self.board_screen_bbox = None

        # 工具栏
        toolbar = tk.Frame(root, bg='lightgray')
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)

        self.btn_open = tk.Button(toolbar, text="打开图像", command=self.open_image)
        self.btn_open.pack(side=tk.LEFT, padx=2)

        self.btn_capture = tk.Button(toolbar, text="截图识别", command=self.capture_screenshot)
        self.btn_capture.pack(side=tk.LEFT, padx=2)

        self.btn_auto = tk.Button(toolbar, text="自动识别(beta)", command=self.auto_capture_and_recognize)
        self.btn_auto.pack(side=tk.LEFT, padx=2)

        self.btn_click = tk.Button(toolbar, text="点击嘟嘟可", command=self.click_duducos)
        self.btn_click.pack(side=tk.LEFT, padx=2)

        self.btn_topmost = tk.Button(toolbar, text="置顶", command=self.toggle_topmost)
        self.btn_topmost.pack(side=tk.RIGHT, padx=2)
        self.is_topmost = False

        # 主内容区
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        
        # 使用grid布局：左侧上下结构，右侧解题结果
        main_frame.grid_columnconfigure(0, weight=0)  # 左侧固定宽度
        main_frame.grid_columnconfigure(1, weight=1)  # 右侧自动扩展
        main_frame.grid_rowconfigure(0, weight=0)     # 原图行固定高度
        main_frame.grid_rowconfigure(1, weight=1)     # 识别网格行自动扩展

        # 左上：图像显示（固定大小正方形）
        left_frame = tk.Frame(main_frame, borderwidth=1, relief=tk.SUNKEN, width=265, height=265)
        left_frame.grid(row=0, column=0, sticky="nw", padx=2, pady=2)
        left_frame.pack_propagate(False)  # 禁止自动调整大小

        image_label = tk.Label(left_frame, text="原图", bg='lightblue')
        image_label.pack(fill=tk.X)

        # 创建固定大小正方形画布用于显示图像
        self.image_canvas = tk.Canvas(left_frame, bg='white', width=240, height=240)
        self.image_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.image_canvas.bind('<Configure>', self._resize_image)
        self.current_photo = None

        # 左下：识别结果
        middle_frame = tk.Frame(main_frame, borderwidth=1, relief=tk.SUNKEN, width=265)
        middle_frame.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        middle_frame.pack_propagate(False)

        grid_label = tk.Label(middle_frame, text="识别的网格", bg='lightblue')
        grid_label.pack(fill=tk.X)

        self.grid_text = tk.Text(middle_frame, font=('Courier', 11))
        self.grid_text.pack(fill=tk.BOTH, expand=True)

        # 右侧：解题结果（跨两行）
        right_frame = tk.Frame(main_frame, borderwidth=1, relief=tk.SUNKEN)
        right_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=2)

        solution_label = tk.Label(right_frame, text="解题结果", bg='lightblue')
        solution_label.pack(fill=tk.X)

        self.solution_text = tk.Text(right_frame, font=('SimHei', 11))
        self.solution_text.pack(fill=tk.BOTH, expand=True)
        self.solution_text.tag_configure("gray_text", foreground="gray")
        self.solution_text.insert(tk.END, "解题结果将显示在这里\n请打开图像或截图识别谜题", "gray_text")

    def open_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("图像文件", "*.jpg;*.jpeg;*.png;*.bmp")])
        if file_path:
            try:
                self.current_image = Image.open(file_path)
                self.board_screen_bbox = None
                self.display_image()
                self.recognize_and_solve()
            except Exception as e:
                messagebox.showerror("错误", f"无法打开图像: {str(e)}")

    def capture_screenshot(self):
        self.root.iconify()
        selector = ScreenshotSelector(self.root)
        self.root.wait_window(selector.root)
        
        if selector.screenshot:
            self.current_image = selector.screenshot
            self.board_screen_bbox = selector.bbox
            self.display_image()
            self.recognize_and_solve()
        
        self.root.deiconify()

    def auto_capture_and_recognize(self):
        self.root.iconify()
        self.root.update()
        import time
        time.sleep(0.3)
        
        try:
            full_screenshot = ImageGrab.grab()
        except Exception as e:
            self.root.deiconify()
            messagebox.showerror("错误", f"截图失败: {str(e)}")
            return
        
        self.root.deiconify()
        self.root.update()
        
        self.grid_text.delete(1.0, tk.END)
        self.solution_text.delete(1.0, tk.END)
        self.grid_text.insert(tk.END, "正在自动检测棋盘区域...\n")
        self.root.update()
        
        board_image = self.recognizer.auto_detect_board(full_screenshot)
        
        if board_image is None:
            self.board_screen_bbox = None
            self.grid_text.delete(1.0, tk.END)
            self.grid_text.insert(tk.END, "未检测到棋盘区域\n")
            self.grid_text.insert(tk.END, "请使用「截图识别」手动框选\n")
            self.solution_text.delete(1.0, tk.END)
            self.solution_text.insert(tk.END, "自动检测失败，未能找到棋盘区域。\n请确保游戏窗口完整显示在屏幕上。", "gray_text")
            return
        
        self.current_image = board_image
        self.board_screen_bbox = self.recognizer._board_crop_bbox
        self.display_image()
        self.root.update_idletasks()
        
        self.grid_text.delete(1.0, tk.END)
        self.grid_text.insert(tk.END, "检测到棋盘，开始识别...\n")
        self.root.update()
        
        self.recognize_and_solve()

    def click_duducos(self):
        if self.solution is None:
            messagebox.showwarning("提示", "请先识别并解题")
            return
        if self.board_screen_bbox is None:
            messagebox.showwarning("提示", "缺少棋盘屏幕坐标，请使用截图识别或自动识别")
            return

        bbox = self.board_screen_bbox
        bx, by = bbox[0], bbox[1]

        self.root.iconify()
        self.root.update()
        import time
        time.sleep(0.3)

        user32 = ctypes.windll.user32

        for color, (row, col) in sorted(self.solution.items()):
            center = self.recognizer.get_cell_center(row, col)
            if center is None:
                continue
            sx = int(bx + center[0])
            sy = int(by + center[1])
            user32.SetCursorPos(sx, sy)
            time.sleep(0.05)
            for _ in range(2):
                user32.mouse_event(0x0002, 0, 0, 0, 0)
                time.sleep(0.01)
                user32.mouse_event(0x0004, 0, 0, 0, 0)
                time.sleep(0.01)
            time.sleep(0.08)

        self.root.deiconify()

    def toggle_topmost(self):
        """切换窗口置顶状态"""
        self.is_topmost = not self.is_topmost
        self.root.attributes('-topmost', self.is_topmost)
        self.btn_topmost.config(text="取消置顶" if self.is_topmost else "置顶")

    def _resize_image(self, event=None):
        """根据画布大小缩放图像，保持比例"""
        if self.current_image:
            canvas_width = self.image_canvas.winfo_width()
            canvas_height = self.image_canvas.winfo_height()
            
            if canvas_width > 0 and canvas_height > 0:
                # 保持图像比例，不拉伸
                width, height = self.current_image.size
                scale = min(canvas_width / width, canvas_height / height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                
                # 居中显示
                x = (canvas_width - new_width) // 2
                y = (canvas_height - new_height) // 2
                
                resized = self.current_image.resize((new_width, new_height), Image.LANCZOS)
                self.current_photo = ImageTk.PhotoImage(resized)
                
                # 清除画布并显示新图像
                self.image_canvas.delete("all")
                self.image_canvas.create_image(x, y, anchor=tk.NW, image=self.current_photo)
        else:
            self.image_canvas.delete("all")
            self.image_canvas.create_text(
                self.image_canvas.winfo_width()//2, 
                self.image_canvas.winfo_height()//2,
                text="请打开图像或截图",
                fill="gray"
            )

    def display_image(self):
        """触发图像显示/更新"""
        self._resize_image()

    def recognize_and_solve(self):
        if self.current_image:
            try:
                # 清空之前的结果
                self.grid_text.delete(1.0, tk.END)
                self.solution_text.delete(1.0, tk.END)
                
                # 识别网格
                self.grid_text.insert(tk.END, "正在识别网格...\n")
                self.root.update()
                
                self.recognized_grid = self.recognizer.recognize_from_image(self.current_image)
                
                if self.recognized_grid:
                    size = len(self.recognized_grid)
                    self.grid_text.delete(1.0, tk.END)
                    self.grid_text.insert(tk.END, f"识别结果 ({size}x{size})\n")
                    self.grid_text.insert(tk.END, "-" * 30 + "\n")
                    for row in self.recognized_grid:
                        self.grid_text.insert(tk.END, ' '.join(map(str, row)) + '\n')
                    
                    # 自动解题
                    self.solution_text.insert(tk.END, "正在解题...\n")
                    self.root.update()
                    
                    try:
                        grid = self.recognized_grid
                        colors = set()
                        for row in grid:
                            colors.update(row)
                        
                        self.solution_text.delete(1.0, tk.END)
                        self.solution_text.insert(tk.END, f"网格大小: {len(grid)}x{len(grid[0])}\n")
                        self.solution_text.insert(tk.END, f"颜色数量: {len(colors)}\n")
                        self.solution_text.insert(tk.END, "正在求解...\n")
                        self.root.update()
                        
                        solver = DuducoPuzzleSolver(grid, len(colors))
                        solutions = solver.solve()
                        
                        self.solution_text.delete(1.0, tk.END)
                        if solutions:
                            self.solution = solutions[0]
                            result_text = solver.format_solution(self.solution)
                            self.solution_text.insert(tk.END, result_text)
                        else:
                            self.solution_text.insert(tk.END, "未找到解！\n")
                            self.solution_text.insert(tk.END, "可能的原因：\n")
                            self.solution_text.insert(tk.END, "- 识别的网格数据有误\n")
                            self.solution_text.insert(tk.END, "- 谜题本身无解\n")
                            self.solution_text.insert(tk.END, "- 颜色分类不正确\n")
                    except Exception as e:
                        self.solution_text.delete(1.0, tk.END)
                        self.solution_text.insert(tk.END, f"解题出错: {str(e)}")
                else:
                    self.grid_text.delete(1.0, tk.END)
                    self.grid_text.insert(tk.END, "未能识别到网格，请确保图像中包含清晰的网格线")
                    self.solution_text.delete(1.0, tk.END)
            except Exception as e:
                messagebox.showerror("错误", f"处理失败: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()