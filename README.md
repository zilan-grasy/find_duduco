# 寻找嘟嘟可

用于《原神 · 千星奇域》中《嘟嘟可在哪里》游玩项目的自动识别与求解工具。

## 快速开始

### 环境要求

- Python 3.8+
- Windows

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
python find_duduco.py
```

### 打包为 exe（可选）

```bash
pyinstaller 寻找嘟嘟可.spec
```

打包后在 `dist/` 目录得到 `寻找嘟嘟可.exe`。首次运行时会在 exe 同级目录自动创建 `userdata/` 文件夹存放配置文件。

> **注意**：测试图片会随 exe 一起打包，可通过「打开图像」载入。

## 功能

- **打开图像**：载入本地截图，自动识别颜色矩阵并求解
- **截图识别**：全屏遮罩 + 鼠标框选棋盘区域 → 识别 → 求解
- **自动识别**：位置校准后一键全屏截图，自动匹配棋盘大小并求解
- **点击嘟嘟可**：解题后自动移动鼠标到每个嘟嘟可位置并双击（首位置可调双击/三击）
- **设置**：统一管理校准数据、点击速度（滑动条/手动输入）、截图后自动点击开关

## 测试

### 测试图片

文件夹内 `userdata/` 提供了 3 张测试截图，可直接用「打开图像」载入验证效果：

- `userdata/test1.png`
- `userdata/test2.png`
- `userdata/test3.png`

### 独立模块命令行用法

图像识别和求解器可脱离 GUI 独立运行，通过 JSON 文件桥接。

puzzle JSON 格式（`grid_recog.py` 输出 / `duduco_solve.py` 输入）：

```json
{
  "size": 8,
  "grid": [[8,8,2,...], [8,1,2,...], ...]
}
```

配置文件 `userdata/config.json`（程序自动生成）：

```json
{
  "calibrations": {"8": [100, 200, 500, 600]},
  "click_timings": {"init_delay": 100, "move_press": 20, "press_release": 10, "click_gap": 30, "duduco_gap": 50},
  "auto_click_capture": false,
  "auto_click_auto": false,
  "first_click_3": true,
  "puzzle": {"size": 8, "grid": [[8,8,2,...], ...]}
}
```

`duduco_solve.py` 兼容两种格式（含 `puzzle` 字段或裸 puzzle）。

```bash
# 图像 → JSON
python grid_recog.py userdata/test1.png output.json

# JSON → 解法
python duduco_solve.py output.json
```

## 项目结构

```
find_duduco/
├── find_duduco.py              # 主程序（GUI 界面，import 子模块完成识别和求解）
├── duduco_solve.py             # 约束传播求解器（可独立 CLI 运行）
├── grid_recog.py               # 图像网格识别（可独立 CLI 运行）
├── 寻找嘟嘟可.spec             # PyInstaller 打包配置
├── requirements.txt            # Python 依赖
├── userdata/                    # 用户数据目录
│   ├── test1.png / test2.png / test3.png   # 测试截图
│   └── config.json             # 校准 + 间隔 + 自动设置 + 谜题缓存（程序生成）
├── .gitignore
├── CHANGELOG.md
├── LICENSE
└── README.md
```

## 求解算法

采用**约束传播 + 回溯**策略：

1. **约束传播**（不动点迭代至收敛）：
   - 规则1 · 最后一格：某行/列只剩 1 个合法位置 → 确定放置
   - 规则2 · 双向鸽巢原理：N 种颜色横跨 N 行/列 → 双向排除（占位：该 N 行/列上其他色排除；定域：该 N 色在其他行/列也排除）
   - 规则3 · 包围排除：某格子 8 邻域包含某颜色的全部剩余候选 → 该格排除

2. **双色迷你回溯**：约束卡住时穷举候选最少的 2 色，交叉验证提取公共推理

3. **主递归回溯**：剩余颜色逐一尝试合法位置，找第一个完整解

## 图像识别管线

Canny 边缘检测 → 投影峰值提取网格线 → 聚类去重 → 切割格子 → HSV 取中心区域主色 → K-means 聚类 → Union-Find 合并近色 → 输出颜色编号矩阵

## 常见问题

### DPI 缩放导致截图或点击偏移

程序启动时已设置 DPI 感知（`SetProcessDpiAwareness`）。如果你的系统显示缩放不是 100%，且出现截图区域或点击位置偏差，请尝试：

1. 右键 `python.exe` / 打包后的 `.exe` → **属性** → **兼容性** → **更改高 DPI 设置**
2. 勾选「替代高 DPI 缩放行为」，下拉选择「应用程序」
3. 或者在 Windows 显示设置中将缩放临时调为 100%

### 杀毒软件 / 安全软件拦截

程序的「点击嘟嘟可」功能会调用 Windows API 模拟鼠标移动和点击（`SetCursorPos` + `mouse_event`），以及「截图识别」会调用全屏截图。这些行为可能被安全软件（Windows Defender、360、火绒等）标记为可疑。

如果遇到拦截：

- 将程序目录或 `.exe` 加入安全软件的白名单 / 排除列表
- 如不放心，可仅使用「打开图像」载入截图手动查看解法，不使用自动点击功能

### 游戏窗口不要被遮挡

截图识别和自动识别均依赖屏幕画面，请确保游戏棋盘完整显示在屏幕上，不被其他窗口遮挡。

## 免责声明

本工具仅供个人学习与辅助参考。使用者应自行判断使用场景，遵守游戏相关条款。

- 本工具不修改游戏客户端、不读写游戏内存、不拦截网络通信，仅为图像识别与鼠标模拟。
- 使用本工具产生的任何后果（包括但不限于账号警告、封禁、误操作等），由使用者自行承担。
- 开发者不鼓励任何违反游戏规则的行为，不对使用本工具造成的任何损失负责。

## 许可

基于 MIT 许可证开源。详见 [LICENSE](LICENSE)。
