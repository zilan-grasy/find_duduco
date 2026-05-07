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

    def _find_grid_lines_contour(self, edges):
        height, width = edges.shape
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        dilated = cv2.dilate(closed, kernel, iterations=2)
        contours, hierarchy = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return [], []
        
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
        
        return find_peaks(vertical_projection, 0.15), find_peaks(horizontal_projection, 0.15)

    def _find_grid_lines_hough(self, edges, height, width):
        min_line_length = min(width, height) // 5
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=40,
                                minLineLength=min_line_length, maxLineGap=15)
        if lines is None:
            return [], []
        
        horizontal_lines, vertical_lines = [], []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if abs(x2 - x1) > abs(y2 - y1):
                horizontal_lines.append((y1 + y2) / 2)
            else:
                vertical_lines.append((x1 + x2) / 2)
        return horizontal_lines, vertical_lines

    def recognize_from_image(self, image):
        open_cv_image = np.array(image)
        if len(open_cv_image.shape) == 3 and open_cv_image.shape[2] == 4:
            open_cv_image = open_cv_image[:, :, :3]
        open_cv_image = open_cv_image[:, :, ::-1].copy()
        
        height, width = open_cv_image.shape[:2]
        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100, apertureSize=3)
        
        h_lines, v_lines = self._find_grid_lines_contour(edges)
        if len(h_lines) < 3 or len(v_lines) < 3:
            h_lines2, v_lines2 = self._find_grid_lines_hough(edges, height, width)
            h_lines += h_lines2
            v_lines += v_lines2
        
        if len(h_lines) < 2 or len(v_lines) < 2:
            return None
        
        h_lines = self._cluster_lines(h_lines, threshold=height//25)
        v_lines = self._cluster_lines(v_lines, threshold=width//25)
        
        if len(h_lines) < 2 or len(v_lines) < 2:
            return None
        
        h_lines, v_lines = sorted(h_lines), sorted(v_lines)
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
        
        best_labels, best_score = None, float('inf')
        for _ in range(10):
            try:
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 300, 0.0001)
                compactness, labels, centers = cv2.kmeans(
                    normalized.reshape((-1, 3)), target_colors, None, criteria, 30, cv2.KMEANS_PP_CENTERS)
                if compactness < best_score:
                    best_score, best_labels = compactness, labels.flatten()
            except:
                continue
        
        if best_labels is None:
            return [[1 if c else 0 for c in row] for row in color_list]
        
        label_idx, result = 0, []
        for row in color_list:
            row_result = []
            for color in row:
                if color is None:
                    row_result.append(0)
                else:
                    row_result.append(best_labels[label_idx] + 1)
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
        if avg_s < 10 or avg_v > 250:
            return None
        return (avg_h, avg_s, avg_v)

class DuducoPuzzleSolver:
    """嘟嘟可谜题求解器"""
    
    def __init__(self, grid: List[List[int]], num_colors: int):
        self.grid = grid
        self.size = len(grid)
        self.num_colors = num_colors
        self.regions = self._find_regions()
        self.solutions = []
        self.current_placement = {}
        self.duducos = {}
        self.no_duduco_rows = set()
        self.no_duduco_cols = set()
        self.no_duduco_positions = set()
        self.detected_colors = set()
    
    def _is_valid_position(self, r: int, c: int) -> bool:
        return (r not in self.no_duduco_rows and 
                c not in self.no_duduco_cols and 
                (r, c) not in self.no_duduco_positions)

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

    def _detect_single_cell(self) -> bool:
        for color, regions_list in self.regions.items():
            if color in self.duducos or color in self.current_placement:
                continue
            region = regions_list[0]
            if len(region) == 1:
                r, c = region[0]
                if self._is_valid_position(r, c):
                    self._mark_placement(color, region[0])
                    return True
        return False

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

    def _detect_two_cell_patterns(self) -> bool:
        updated = False
        for color, regions_list in self.regions.items():
            if color in self.duducos or color in self.current_placement or color in self.detected_colors:
                continue
            
            region = regions_list[0]
            unmarked = [pos for pos in region if self._is_valid_position(pos[0], pos[1])]
            
            if len(unmarked) == 2:
                (r1, c1), (r2, c2) = unmarked
                if r1 == r2:
                    row, col1, col2 = r1, sorted([c1, c2])[0], sorted([c1, c2])[1]
                    if row > 0:
                        self.no_duduco_positions.add((row - 1, col1))
                        self.no_duduco_positions.add((row - 1, col2))
                    if row < self.size - 1:
                        self.no_duduco_positions.add((row + 1, col1))
                        self.no_duduco_positions.add((row + 1, col2))
                    updated = True
                elif c1 == c2:
                    col, row1, row2 = c1, sorted([r1, r2])[0], sorted([r1, r2])[1]
                    if col > 0:
                        self.no_duduco_positions.add((row1, col - 1))
                        self.no_duduco_positions.add((row2, col - 1))
                    if col < self.size - 1:
                        self.no_duduco_positions.add((row1, col + 1))
                        self.no_duduco_positions.add((row2, col + 1))
                    updated = True
            self.detected_colors.add(color)
        return updated

    def _detect_three_cell_patterns(self) -> bool:
        updated = False
        for color, regions_list in self.regions.items():
            if color in self.duducos or color in self.current_placement or color in self.detected_colors:
                continue
            
            region = regions_list[0]
            unmarked = [pos for pos in region if self._is_valid_position(pos[0], pos[1])]
            
            if len(unmarked) == 3:
                rows, cols = [p[0] for p in unmarked], [p[1] for p in unmarked]
                
                if len(set(rows)) == 1:
                    row, sorted_cols = rows[0], sorted(cols)
                    if sorted_cols[2] - sorted_cols[0] == 2:
                        mid_col = sorted_cols[1]
                        if row > 0 and (row - 1, mid_col) not in self.no_duduco_positions:
                            self.no_duduco_positions.add((row - 1, mid_col))
                        if row < self.size - 1 and (row + 1, mid_col) not in self.no_duduco_positions:
                            self.no_duduco_positions.add((row + 1, mid_col))
                        updated = True
                elif len(set(cols)) == 1:
                    col, sorted_rows = cols[0], sorted(rows)
                    if sorted_rows[2] - sorted_rows[0] == 2:
                        mid_row = sorted_rows[1]
                        if col > 0 and (mid_row, col - 1) not in self.no_duduco_positions:
                            self.no_duduco_positions.add((mid_row, col - 1))
                        if col < self.size - 1 and (mid_row, col + 1) not in self.no_duduco_positions:
                            self.no_duduco_positions.add((mid_row, col + 1))
                        updated = True
                else:
                    for pos in unmarked:
                        r, c = pos
                        has_above, has_below = (r - 1, c) in unmarked, (r + 1, c) in unmarked
                        has_left, has_right = (r, c - 1) in unmarked, (r, c + 1) in unmarked
                        
                        if (has_above + has_below + has_left + has_right) == 2:
                            if has_above and has_left and r + 1 < self.size and c + 1 < self.size:
                                self.no_duduco_positions.add((r + 1, c + 1))
                                updated = True
                            elif has_above and has_right and r + 1 < self.size and c - 1 >= 0:
                                self.no_duduco_positions.add((r + 1, c - 1))
                                updated = True
                            elif has_below and has_left and r - 1 >= 0 and c + 1 < self.size:
                                self.no_duduco_positions.add((r - 1, c + 1))
                                updated = True
                            elif has_below and has_right and r - 1 >= 0 and c - 1 >= 0:
                                self.no_duduco_positions.add((r - 1, c - 1))
                                updated = True
                            break
            self.detected_colors.add(color)
        return updated

    def _detection_loop(self):
        max_iterations = 100
        for iteration in range(max_iterations):
            changed = False
            self.detected_colors.clear()
            
            for n in range(1, self.size + 1):
                if self._detect_n_color_shared_rows(n):
                    changed = True
            if self._detect_three_cell_patterns():
                changed = True
            if self._detect_two_cell_patterns():
                changed = True
            if self._detect_last_cell():
                changed = True
            if self._detect_single_cell():
                changed = True
            
            if not changed:
                break

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

    def solve(self):
        self._detection_loop()
        self._solve_region(len(self.duducos))
        return self.solutions

    def format_solution(self, solution: Dict[int, Tuple[int, int]]) -> str:
        result = []
        result.append(f"网格大小: {self.size}x{self.size}")
        result.append(f"嘟嘟可数量: {len(solution)}")
        result.append("")
        
        result.append("解法结果（*表示嘟嘟可位置）：")
        header = "   | " + " ".join(f"{i:2d}" for i in range(self.size))
        result.append(header)
        result.append("---+-" + "--" * self.size)
        
        for r in range(self.size):
            row_str = f"{r:2d} | "
            for c in range(self.size):
                pos = (r, c)
                if pos in solution.values():
                    row_str += " * "
                else:
                    row_str += f"{self.grid[r][c]:2d} "
            result.append(row_str)
        
        result.append("")
        result.append("嘟嘟可位置详情：")
        for color in sorted(solution.keys()):
            r, c = solution[color]
            result.append(f"  颜色{color}: ({r}, {c})")
        
        return "\n".join(result)

class ScreenshotSelector:
    """截图选择器"""

    def __init__(self, parent):
        self.parent = parent
        self.start_x = self.start_y = self.current_x = self.current_y = 0
        self.rect = None
        self.screenshot = None

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
        self.root.destroy()

    def on_escape(self, event):
        self.root.destroy()

class MainWindow:
    """主窗口 - 整合图像识别和解题器，自动显示结果"""

    def __init__(self, root):
        self.root = root
        self.root.title("寻找嘟嘟可")
        self.root.geometry("600x550")

        self.recognizer = GridImageRecognizer()
        self.current_image = None
        self.recognized_grid = None
        self.solution = None

        # 工具栏
        toolbar = tk.Frame(root, bg='lightgray')
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)

        self.btn_open = tk.Button(toolbar, text="打开图像", command=self.open_image)
        self.btn_open.pack(side=tk.LEFT, padx=2)

        self.btn_capture = tk.Button(toolbar, text="截图识别", command=self.capture_screenshot)
        self.btn_capture.pack(side=tk.LEFT, padx=2)

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
        left_frame = tk.Frame(main_frame, borderwidth=1, relief=tk.SUNKEN, width=220, height=220)
        left_frame.grid(row=0, column=0, sticky="nw", padx=2, pady=2)
        left_frame.pack_propagate(False)  # 禁止自动调整大小

        image_label = tk.Label(left_frame, text="原图", bg='lightblue')
        image_label.pack(fill=tk.X)

        # 创建固定大小正方形画布用于显示图像
        self.image_canvas = tk.Canvas(left_frame, bg='white', width=200, height=200)
        self.image_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.image_canvas.bind('<Configure>', self._resize_image)
        self.current_photo = None

        # 左下：识别结果
        middle_frame = tk.Frame(main_frame, borderwidth=1, relief=tk.SUNKEN, width=220)
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
            self.display_image()
            self.recognize_and_solve()
        
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
        """自动识别网格并解题，直接显示结果"""
        print("DEBUG: recognize_and_solve called")
        if self.current_image:
            try:
                # 清空之前的结果
                self.grid_text.delete(1.0, tk.END)
                self.solution_text.delete(1.0, tk.END)
                
                # 识别网格
                self.grid_text.insert(tk.END, "正在识别网格...\n")
                self.root.update()
                
                print("DEBUG: calling recognize_from_image")
                self.recognized_grid = self.recognizer.recognize_from_image(self.current_image)
                print(f"DEBUG: recognized_grid = {self.recognized_grid}")
                
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