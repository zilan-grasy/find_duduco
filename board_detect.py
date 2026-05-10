import cv2
import numpy as np
from PIL import Image


# BETA: 全屏截图自动定位棋盘区域，算法仍在优化中
def detect_board(image):
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
    return Image.fromarray(cropped[:, :, ::-1]), (vx1, hy1, vx2, hy2)
