import cv2
import numpy as np
from PIL import Image


def _cluster_lines(lines, threshold=10):
    """将靠近的直线合并聚类，返回每簇的平均值"""
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


def _find_grid_lines(edges, height, width):
    """从边缘图中检测网格线：先投影峰值法，不足时回退 Hough 直线检测"""
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


def _get_dominant_color(cell, use_center=False):
    """提取格子主色：转HSV后取均值，白色/低饱和视为空白(返回None)"""
    if cell.size == 0:
        return None
    if use_center:
        h, w = cell.shape[:2]
        margin_h, margin_w = int(h * 0.2), int(w * 0.2)
        if margin_h > 0 and margin_w > 0:
            cell = cell[margin_h:h - margin_h, margin_w:w - margin_w]
            if cell.size == 0:
                return None
    hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)
    avg_h, avg_s, avg_v = np.mean(hsv[:, :, 0]), np.mean(hsv[:, :, 1]), np.mean(hsv[:, :, 2])
    if avg_s < 10 or (avg_v > 245 and avg_s < 25):
        return None
    return (avg_h, avg_s, avg_v)


def get_cell_center(h_lines, v_lines, row, col):
    """根据网格线坐标计算指定格子(row,col)的中心点屏幕坐标"""
    if h_lines is None or v_lines is None:
        return None
    if row < 0 or row >= len(h_lines) - 1:
        return None
    if col < 0 or col >= len(v_lines) - 1:
        return None
    cx = (v_lines[col] + v_lines[col + 1]) / 2
    cy = (h_lines[row] + h_lines[row + 1]) / 2
    return (cx, cy)


def recognize_from_image(image):
    """完整的网格识别流程：
    1. 边缘检测(Canny) → 网格线提取 → 切分格子
    2. 每格取中心区域 HSV 均值 → 过滤白色/空白
    3. K-means 聚类 + Union-Find 合并近色簇 → 输出颜色编号矩阵"""
    open_cv_image = np.array(image)
    if len(open_cv_image.shape) == 3 and open_cv_image.shape[2] == 4:
        open_cv_image = open_cv_image[:, :, :3]
    open_cv_image = open_cv_image[:, :, ::-1].copy()

    height, width = open_cv_image.shape[:2]
    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100, apertureSize=3)

    h_peaks, v_peaks = _find_grid_lines(edges, height, width)

    if len(h_peaks) < 2 or len(v_peaks) < 2:
        return None

    h_peaks = _cluster_lines(h_peaks, threshold=height // 25)
    v_peaks = _cluster_lines(v_peaks, threshold=width // 25)

    if len(h_peaks) < 2 or len(v_peaks) < 2:
        return None

    if len(h_peaks) > 16 or len(v_peaks) > 16:
        return None

    h_peaks, v_peaks = sorted(h_peaks), sorted(v_peaks)

    cells = []
    for i in range(len(h_peaks) - 1):
        row = []
        for j in range(len(v_peaks) - 1):
            x1, y1, x2, y2 = int(v_peaks[j]), int(h_peaks[i]), int(v_peaks[j + 1]), int(h_peaks[i + 1])
            if x2 <= x1 or y2 <= y1:
                continue
            row.append(open_cv_image[y1:y2, x1:x2])
        if row:
            cells.append(row)

    if not cells or not cells[0]:
        return None

    color_list = []
    for row in cells:
        color_row = []
        for cell in row:
            color_row.append(_get_dominant_color(cell, use_center=True))
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
        _, _, centers = cv2.kmeans(
            normalized.reshape((-1, 3)), target_colors, None, criteria, 30, cv2.KMEANS_PP_CENTERS)
        best_centers = centers
    except:
        return [[1 if c else 0 for c in row] for row in color_list]

    # Union-Find 合并距离过近的聚类中心，避免同一颜色被拆成多个编号
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

    result = []
    for row in color_list:
        row_result = []
        for color in row:
            if color is None:
                row_result.append(0)
            else:
                raw_hash = (color[0] / 180.0, color[1] / 255.0, color[2] / 255.0)
                best_cluster = min(merged_centers.items(), key=lambda x: np.linalg.norm(raw_hash - x[1]))
                row_result.append(best_cluster[0] + 1)
        result.append(row_result)
    return result, (h_peaks, v_peaks)


def recognize_and_format(image):
    r = recognize_from_image(image)
    if r is None:
        return None
    grid, lines = r
    size = len(grid)
    return {"size": size, "grid": grid}, lines


if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) < 2:
        print("用法: python grid_recog.py <图像路径> [输出文件]")
        print("  将识别结果输出为 JSON，格式：{\"size\": N, \"grid\": [[...], ...]}")
        sys.exit(1)
    img = Image.open(sys.argv[1])
    result = recognize_and_format(img)
    if result is None:
        print("识别失败")
        sys.exit(1)
    puzzle, _ = result
    text = json.dumps(puzzle, indent=2, ensure_ascii=False)
    if len(sys.argv) >= 3:
        with open(sys.argv[2], 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"已保存到 {sys.argv[2]}")
    else:
        print(text)
