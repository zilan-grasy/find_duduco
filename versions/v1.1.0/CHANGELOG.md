# v1.1.0 (2026-05-10)

## 新增
- **自动识别(beta)**按钮：全屏截图 → Sobel方向梯度 → 投影包络 → 方形配对 → 自动裁剪棋盘
- **点击嘟嘟可**按钮：解出后自动移动鼠标到屏幕对应位置并双击
- **15×15 网格上限**守卫（识别阶段 16 条线以上返回 None，Solver 初始化抛 ValueError）
- **独立模块文件**：
  - `duduco_solve.py` — 纯求解算法（可从命令行独立调用）
  - `grid_recog.py` — 图像识别（可从命令行独立调用）
  - `board_detect.py` — 棋盘定位（beta，可从命令行独立调用）
- **版本文件夹管理**：构建产物按版本号存放在 `versions/vx.x.x/`

## 改动
- 合并 `_find_grid_lines_contour` 和 `_find_grid_lines_hough` 为统一的 `_find_grid_lines`
- 移除调试 print 语句
- `ScreenshotsSelector` 记录框选 bbox
- `recognize_from_image` 输出网格线坐标供 `get_cell_center` 使用
- `.gitignore` 新增 `venv/`、`test.txt`

## 删除
- `grid_recognizer_gui.py`（旧版独立识别 GUI）
- `solve_puzzle.py`（旧版命令行求解器）
