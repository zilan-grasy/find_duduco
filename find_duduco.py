import time
import json
import os
import sys
import ctypes
from PIL import ImageGrab, Image, ImageTk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from duduco_solve import DuducoPuzzleSolver
from grid_recog import recognize_from_image as _grid_recognize, get_cell_center as _grid_get_cell_center

# 设置DPI感知，让Windows不要自动缩放程序
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass

class GridImageRecognizer:
    """图像网格识别器：委托 grid_recog 子模块执行实际工作。
    本类仅保存网格线坐标，供 MainWindow 查询。"""

    def __init__(self):
        self._last_h_peaks = None          # 最近一次识别的水平网格线 y 坐标列表
        self._last_v_peaks = None          # 最近一次识别的垂直网格线 x 坐标列表

    def recognize_from_image(self, image):
        """识别网格：委托 grid_recog.recognize_from_image，缓存网格线坐标"""
        result = _grid_recognize(image)
        if result is None:
            return None
        grid, (h_peaks, v_peaks) = result
        self._last_h_peaks = list(h_peaks)
        self._last_v_peaks = list(v_peaks)
        return grid

    def get_cell_center(self, row, col):
        """委托 grid_recog.get_cell_center 用缓存的网格线坐标计算"""
        return _grid_get_cell_center(self._last_h_peaks, self._last_v_peaks, row, col)

class ScreenshotSelector:
    """截图选择器：全屏半透明遮罩，鼠标拖动框选区域，Esc取消"""

    def __init__(self, parent):
        """创建全屏半透明遮罩窗口，绑定鼠标事件"""
        self.start_x = self.start_y = self.current_x = self.current_y = 0
        self.rect = None
        self.screenshot = None
        self.bbox = None

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
        self._config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "userdata", "config.json")
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            self._config_path = os.path.join(exe_dir, "userdata", "config.json")
        self.calibrations = {int(k): tuple(v) for k, v in self._load_settings("calibrations", {}).items()}  # {size(int): bbox(x1,y1,x2,y2)}
        self.click_timings = self._load_settings("click_timings", {
            "init_delay": 100, "move_press": 20, "press_release": 10,
            "click_gap": 30, "duduco_gap": 50
        })  # 单位毫秒
        self.auto_click_capture_var = tk.BooleanVar(value=self._load_settings("auto_click_capture", False))
        self.auto_click_auto_var = tk.BooleanVar(value=self._load_settings("auto_click_auto", False))
        self.first_click_3_var = tk.BooleanVar(value=self._load_settings("first_click_3", True))
        self._click_mode = None  # 'capture' 或 'auto'，标记当前识别来源

        style = ttk.Style()
        style.theme_use('classic')
        style.configure('Gray.Horizontal.TScale', troughcolor='#d0d0d0')

        # 工具栏
        toolbar = tk.Frame(root, bg='lightgray')
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)

        self.btn_open = tk.Button(toolbar, text="打开图像", command=self.open_image)
        self.btn_open.pack(side=tk.LEFT, padx=2)

        self.btn_capture = tk.Button(toolbar, text="截图识别", command=self.capture_screenshot)
        self.btn_capture.pack(side=tk.LEFT, padx=2)

        self.btn_auto = tk.Button(toolbar, text="自动识别", command=self.auto_capture_and_recognize)
        self.btn_auto.pack(side=tk.LEFT, padx=2)

        self.btn_click = tk.Button(toolbar, text="点击嘟嘟可", command=self.click_duducos)
        self.btn_click.pack(side=tk.LEFT, padx=2)

        self.btn_settings = tk.Button(toolbar, text="设置", command=self._show_settings)
        self.btn_settings.pack(side=tk.LEFT, padx=2)

        self.btn_topmost = tk.Button(toolbar, text="置顶", command=self.toggle_topmost)
        self.btn_topmost.pack(side=tk.RIGHT, padx=2)
        self.is_topmost = False

        # 主内容区
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        self._main_widgets = []  # 记录主界面子控件，切换设置时隐藏
        
        # 使用grid布局：左侧上下结构，右侧解题结果
        self.main_frame.grid_columnconfigure(0, weight=0)  # 左侧固定宽度
        self.main_frame.grid_columnconfigure(1, weight=1)  # 右侧自动扩展
        self.main_frame.grid_rowconfigure(0, weight=0)     # 原图行固定高度
        self.main_frame.grid_rowconfigure(1, weight=1)     # 识别网格行自动扩展

        # 左上：图像显示（固定大小正方形）
        left_frame = tk.Frame(self.main_frame, borderwidth=1, relief=tk.SUNKEN, width=265, height=265)
        left_frame.grid(row=0, column=0, sticky="nw", padx=2, pady=2)
        left_frame.pack_propagate(False)  # 禁止自动调整大小

        image_label = tk.Label(left_frame, text="原图", bg='lightgray')
        image_label.pack(fill=tk.X)

        # 创建固定大小正方形画布用于显示图像
        self.image_canvas = tk.Canvas(left_frame, bg='white', width=240, height=240)
        self.image_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.image_canvas.bind('<Configure>', self._resize_image)
        self.current_photo = None

        # 左下：识别结果
        middle_frame = tk.Frame(self.main_frame, borderwidth=1, relief=tk.SUNKEN, width=265)
        middle_frame.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        middle_frame.pack_propagate(False)

        grid_label = tk.Label(middle_frame, text="识别的网格", bg='lightgray')
        grid_label.pack(fill=tk.X)

        self.grid_text = tk.Text(middle_frame)
        self.grid_text.pack(fill=tk.BOTH, expand=True)

        # 右侧：解题结果（跨两行）
        right_frame = tk.Frame(self.main_frame, borderwidth=1, relief=tk.SUNKEN)
        right_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=2)

        solution_label = tk.Label(right_frame, text="解题结果", bg='lightgray')
        solution_label.pack(fill=tk.X)

        self.solution_text = tk.Text(right_frame)
        self.solution_text.pack(fill=tk.BOTH, expand=True)
        self.solution_text.tag_configure("gray_text", foreground="gray")
        self._main_widgets = [left_frame, middle_frame, right_frame]

    def _load_settings(self, key, default):
        """从 config.json 读取指定 key 的配置"""
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get(key, default)
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    def _save_settings(self, **kwargs):
        """将 key=value 写入 config.json（保留已有字段，固定顺序：校准→间隔→自动→谜题）"""
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        for k, v in kwargs.items():
            data[k] = v

        lines = ['{']
        keys = ['calibrations', 'click_timings', 'auto_click_capture', 'auto_click_auto', 'first_click_3', 'puzzle']
        present = [k for k in keys if k in data]
        for i, key in enumerate(present):
            comma = ',' if i < len(present) - 1 else ''
            val = data[key]
            if key == 'calibrations' and isinstance(val, dict):
                lines.append(f'  "{key}": {{')
                entries = sorted(val.items(), key=lambda x: int(x[0]))
                for j, (size, bbox) in enumerate(entries):
                    c = ',' if j < len(entries) - 1 else ''
                    lines.append(f'    "{size}": {json.dumps(bbox)}{c}')
                lines.append(f'  }}{comma}')
            elif key == 'puzzle' and isinstance(val, dict) and 'grid' in val:
                lines.append(f'  "{key}": {{')
                lines.append(f'    "size": {val["size"]},')
                lines.append(f'    "grid": [')
                grid = val['grid']
                for j, row in enumerate(grid):
                    row_json = json.dumps(row)
                    c = ',' if j < len(grid) - 1 else ''
                    lines.append(f'      {row_json}{c}')
                lines.append(f'    ]')
                lines.append(f'  }}{comma}')
            else:
                val_json = json.dumps(val, ensure_ascii=False, indent=2)
                indented = '\n'.join('  ' + line for line in val_json.split('\n'))
                lines.append(f'  "{key}": {indented}{comma}')
        lines.append('}')

        with open(self._config_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')

    def open_image(self):
        """打开本地图像文件：弹出文件对话框，载入后自动识别+解题"""
        file_path = filedialog.askopenfilename(filetypes=[("图像文件", "*.jpg;*.jpeg;*.png;*.bmp")])
        if file_path:
            try:
                self.current_image = Image.open(file_path)
                self.board_screen_bbox = None
                self.display_image()
                self._click_mode = None
                self.recognize_and_solve()
            except Exception as e:
                messagebox.showerror("错误", f"无法打开图像: {str(e)}")

    def capture_screenshot(self):
        """截图识别：最小化窗口 → 弹出全屏遮罩框选棋盘 → 截取后自动识别+解题"""
        self.root.iconify()
        selector = ScreenshotSelector(self.root)
        self.root.wait_window(selector.root)
        
        if selector.screenshot:
            self.current_image = selector.screenshot
            self.board_screen_bbox = selector.bbox
            self._click_mode = 'capture'
            self.display_image()
            self.recognize_and_solve()
        
        self.root.deiconify()

    def auto_capture_and_recognize(self):
        """自动识别：全屏截图 → 逐校准位置尝试 → 取最高网格数 → 求解失败则回退下一尺寸"""
        if not self.calibrations:
            messagebox.showwarning("提示", "请先在「位置校准」中框选至少一个尺寸的棋盘位置")
            return

        self.root.iconify()
        self.root.update()
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
        self.grid_text.insert(tk.END, "正在校准匹配...\n")
        self.root.update()

        all_results = self._try_calibrations(full_screenshot)
        if not all_results:
            self.grid_text.delete(1.0, tk.END)
            self.grid_text.insert(tk.END, "所有校准位置均识别失败\n")
            self.grid_text.insert(tk.END, "请重新校准或使用「截图识别」手动框选\n")
            self.solution_text.delete(1.0, tk.END)
            self.solution_text.insert(tk.END, "校准匹配失败", "gray_text")
            return

        self._click_mode = 'auto'
        for idx, candidate in enumerate(all_results):
            self.board_screen_bbox = candidate['bbox']
            self.current_image = full_screenshot.crop(candidate['bbox'])
            self.display_image()
            self.root.update_idletasks()

            self.grid_text.delete(1.0, tk.END)
            suffix = f" (回退 {idx+1}/{len(all_results)})" if idx > 0 else ""
            self.grid_text.insert(tk.END, f"校准匹配: {candidate['size']}×{candidate['size']}{suffix}\n")
            self.root.update()
            
            if self.recognize_and_solve():
                return

        self.grid_text.delete(1.0, tk.END)
        self.grid_text.insert(tk.END, "所有校准尺寸均未找到解\n")
        self.solution_text.delete(1.0, tk.END)
        self.solution_text.insert(tk.END, "所有校准尺寸均未找到解", "gray_text")

    def _try_calibrations(self, full_screenshot):
        """用所有校准位置截图并识别，返回按网格数降序排列的结果列表"""
        results = []
        for size in sorted(self.calibrations.keys(), reverse=True):
            bbox = self.calibrations[size]
            grid = self.recognizer.recognize_from_image(full_screenshot.crop(bbox))
            if grid is not None and len(grid) > 0:
                results.append({'size': size, 'bbox': bbox, 'grid_size': len(grid)})
        results.sort(key=lambda x: x['grid_size'], reverse=True)
        return results

    def click_duducos(self):
        """自动点击：按解题结果依次将鼠标移动到每个嘟嘟可格子中心点并双击（首个位置点3下）"""
        if self.solution is None:
            messagebox.showwarning("提示", "请先识别并解题")
            return
        if self.board_screen_bbox is None:
            messagebox.showwarning("提示", "缺少棋盘屏幕坐标，请使用截图识别或自动识别")
            return

        bbox = self.board_screen_bbox
        bx, by = bbox[0], bbox[1]
        t = self.click_timings

        self.root.iconify()
        self.root.update()
        time.sleep(t["init_delay"] / 1000.0)

        user32 = ctypes.windll.user32

        def do_click(sx, sy):
            user32.SetCursorPos(sx, sy)
            time.sleep(t["move_press"] / 1000.0)
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(t["press_release"] / 1000.0)
            user32.mouse_event(0x0004, 0, 0, 0, 0)

        sorted_solution = sorted(self.solution.items())
        for i, (color, (row, col)) in enumerate(sorted_solution):
            center = self.recognizer.get_cell_center(row, col)
            if center is None:
                continue
            sx = int(bx + center[0])
            sy = int(by + center[1])

            clicks = 3 if (i == 0 and self.first_click_3_var.get()) else 2
            for _ in range(clicks):
                do_click(sx, sy)
                time.sleep(t["click_gap"] / 1000.0)
            if i < len(sorted_solution) - 1:
                time.sleep(t["duduco_gap"] / 1000.0)

        self.root.deiconify()

    def toggle_topmost(self):
        """切换窗口置顶状态"""
        self.is_topmost = not self.is_topmost
        self.root.attributes('-topmost', self.is_topmost)
        self.btn_topmost.config(text="取消置顶" if self.is_topmost else "置顶")

    def _show_settings(self):
        """切换到设置界面"""
        if hasattr(self, '_settings_frame') and self._settings_frame:
            return  # 已在设置界面
        for w in self._main_widgets:
            w.pack_forget()
            w.grid_forget()
        self._settings_frame = tk.Frame(self.main_frame)
        self._settings_frame.pack(fill=tk.BOTH, expand=True)
        self._build_sidebar()
        self._show_calibration_tab()

    def _hide_settings(self):
        """返回主界面"""
        if hasattr(self, '_settings_frame') and self._settings_frame:
            self._settings_frame.destroy()
            self._settings_frame = None
        for i, w in enumerate(self._main_widgets):
            if i == 0:
                w.grid(row=0, column=0, sticky="nw", padx=2, pady=2)
            elif i == 1:
                w.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
            else:
                w.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=2)
        self._resize_image()

    def _build_sidebar(self):
        """设置页左侧竖直标签栏"""
        sidebar = tk.Frame(self._settings_frame, width=80)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0), pady=4)
        sidebar.pack_propagate(False)

        tk.Button(sidebar, text="← 返回", command=self._hide_settings, width=6).pack(pady=(0, 6))

        tabs = [("校准", self._show_calibration_tab), ("间隔", self._show_interval_tab), ("自动", self._show_auto_tab)]
        self._tab_btns = {}
        for text, cmd in tabs:
            btn = tk.Label(sidebar, text=text, width=6, padx=6, pady=4, relief=tk.GROOVE, cursor='hand2')
            btn.pack(pady=2)
            btn.bind('<Button-1>', lambda e, c=cmd: c())
            self._tab_btns[text] = btn

        self._tab_content = tk.Frame(self._settings_frame)
        self._tab_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=4)

    def _switch_tab(self, active):
        for text, btn in self._tab_btns.items():
            if text == active:
                btn.config(bg='#d0d0ff', fg='black')
            else:
                btn.config(bg='SystemButtonFace', fg='black')
        for w in self._tab_content.winfo_children():
            w.destroy()

    def _show_calibration_tab(self):
        self._switch_tab("校准")
        f = self._tab_content

        tk.Label(f, text="为每种网格尺寸框选棋盘位置", font=('', 10)).pack(pady=4)

        list_frame = tk.Frame(f)
        list_frame.pack(fill=tk.BOTH, padx=4)

        for size in range(6, 16):
            row_frame = tk.Frame(list_frame)
            row_frame.pack(fill=tk.X, pady=1)

            tk.Label(row_frame, text=f"{size}×{size}", width=5, anchor='w').pack(side=tk.LEFT, padx=2)

            bbox_str = "未校准" if size not in self.calibrations else f"({self.calibrations[size][0]},{self.calibrations[size][1]})→({self.calibrations[size][2]},{self.calibrations[size][3]})"
            tk.Label(row_frame, text=bbox_str, width=26, anchor='w', fg='gray').pack(side=tk.LEFT)

            def make_calibrate(sz=size):
                def cal():
                    self.root.iconify()
                    s = ScreenshotSelector(self.root)
                    self.root.wait_window(s.root)
                    self.root.deiconify()
                    if s.bbox:
                        self.calibrations[sz] = s.bbox
                        self._save_settings(calibrations={str(k): list(v) for k, v in self.calibrations.items()})
                        self._switch_tab("校准")
                        self._show_calibration_tab()
                return cal

            tk.Button(row_frame, text="校准", command=make_calibrate(), width=6).pack(side=tk.RIGHT, padx=2)

        def clear_all():
            self.calibrations.clear()
            self._save_settings(calibrations={})
            self._switch_tab("校准")
            self._show_calibration_tab()

        tk.Button(f, text="清除全部", command=clear_all).pack(pady=(12, 8))

        tk.Frame(f).pack(fill=tk.BOTH, expand=True)

    def _show_interval_tab(self):
        self._switch_tab("间隔")
        f = self._tab_content

        tk.Label(f, text="点击间隔设置", font=('', 10)).pack(pady=(4, 8))

        labels = [
            ("init_delay", "截图→首点"),
            ("move_press", "移动→按下"),
            ("press_release", "按下→抬起"),
            ("click_gap", "双击间隔"),
            ("duduco_gap", "位点间隔"),
        ]

        defaults = {"init_delay": 100, "move_press": 20, "press_release": 10, "click_gap": 30, "duduco_gap": 50}

        for key, desc in labels:
            row = tk.Frame(f)
            row.pack(fill=tk.X, padx=10, pady=4)

            tk.Label(row, text=desc, width=18, anchor='w').pack(side=tk.LEFT)

            if not hasattr(self, '_timing_scales'):
                self._timing_scales = {}
                self._timing_entries = {}

            f2 = tk.Frame(row)
            f2.pack(side=tk.RIGHT)

            entry = tk.Entry(f2, width=5, justify='center')
            entry.insert(0, str(self.click_timings[key]))
            entry.pack(side=tk.LEFT)
            self._timing_entries[key] = entry

            def make_slider_cb(k):
                def cb(v):
                    val = int(float(v))
                    self.click_timings[k] = val
                    e = self._timing_entries[k]
                    e.delete(0, tk.END)
                    e.insert(0, str(val))
                    self._save_settings(click_timings=self.click_timings)
                return cb

            scale = ttk.Scale(row, from_=1, to=200, orient=tk.HORIZONTAL, length=260,
                             command=make_slider_cb(key), style='Gray.Horizontal.TScale')
            scale.set(self.click_timings[key])
            scale.pack(side=tk.LEFT, padx=4)
            self._timing_scales[key] = scale

            def make_entry_cb(k, s):
                def cb():
                    ent = self._timing_entries[k]
                    val = ent.get()
                    try:
                        v = int(val)
                        v = max(1, min(300, v))
                        self.click_timings[k] = v
                        s.set(v)
                        self._save_settings(click_timings=self.click_timings)
                    except ValueError:
                        pass
                return cb

            entry.bind('<FocusOut>', make_entry_cb(key, scale))
            entry.bind('<Return>', make_entry_cb(key, scale))

            tk.Label(f2, text=" ms", fg='gray').pack(side=tk.LEFT)

        def restore_defaults():
            for k, dv in defaults.items():
                self.click_timings[k] = dv
                self._timing_scales[k].set(dv)
                self._timing_entries[k].delete(0, tk.END)
                self._timing_entries[k].insert(0, str(dv))
            self._save_settings(click_timings=self.click_timings)

        tk.Button(f, text="恢复默认", command=restore_defaults).pack(pady=(12, 4))

        tk.Frame(f).pack(fill=tk.BOTH, expand=True)

    def _show_auto_tab(self):
        self._switch_tab("自动")
        f = self._tab_content

        tk.Label(f, text="自动点击设置", font=('', 10)).pack(pady=8)

        def on_toggle_capture():
            self._save_settings(auto_click_capture=self.auto_click_capture_var.get())

        cb1 = tk.Checkbutton(f, text="截图识别后立即点击嘟嘟可", variable=self.auto_click_capture_var, command=on_toggle_capture)
        cb1.pack(pady=4, anchor='w', padx=20)

        def on_toggle_auto():
            self._save_settings(auto_click_auto=self.auto_click_auto_var.get())

        cb2 = tk.Checkbutton(f, text="自动识别后立即点击嘟嘟可", variable=self.auto_click_auto_var, command=on_toggle_auto)
        cb2.pack(pady=4, anchor='w', padx=20)

        def on_toggle_first():
            self._save_settings(first_click_3=self.first_click_3_var.get())

        cb3 = tk.Checkbutton(f, text="首次点击点 3 下", variable=self.first_click_3_var, command=on_toggle_first)
        cb3.pack(pady=4, anchor='w', padx=20)

        tk.Frame(f).pack(fill=tk.BOTH, expand=True)

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
        """核心管线：网格识别 → 颜色聚类 → 构建求解器 → 约束传播 → 回溯求解 → 显示结果
        返回 True 表示找到解"""
        if not self.current_image:
            return False
        try:
            self.grid_text.delete(1.0, tk.END)
            self.solution_text.delete(1.0, tk.END)
            
            self.grid_text.insert(tk.END, "正在识别网格...\n")
            self.root.update()
            
            self.recognized_grid = self.recognizer.recognize_from_image(self.current_image)
            
            if not self.recognized_grid:
                self.grid_text.delete(1.0, tk.END)
                self.grid_text.insert(tk.END, "未能识别到网格，请确保图像中包含清晰的网格线")
                self.solution_text.delete(1.0, tk.END)
                return False

            size = len(self.recognized_grid)
            self.grid_text.delete(1.0, tk.END)
            self.grid_text.insert(tk.END, f"识别结果 ({size}x{size})\n")
            self.grid_text.insert(tk.END, "-" * 30 + "\n")
            for row in self.recognized_grid:
                self.grid_text.insert(tk.END, ' '.join(map(str, row)) + '\n')
            
            self._save_settings(puzzle={"size": size, "grid": self.recognized_grid})
            
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
                    if self.board_screen_bbox:
                        should_click = (self._click_mode == 'capture' and self.auto_click_capture_var.get()) or \
                                       (self._click_mode == 'auto' and self.auto_click_auto_var.get())
                        if should_click:
                            self.root.after(200, self.click_duducos)
                    return True
                else:
                    self.solution_text.insert(tk.END, "未找到解！\n")
                    self.solution_text.insert(tk.END, "可能的原因：\n")
                    self.solution_text.insert(tk.END, "- 识别的网格数据有误\n")
                    self.solution_text.insert(tk.END, "- 谜题本身无解\n")
                    self.solution_text.insert(tk.END, "- 颜色分类不正确\n")
                    return False
            except Exception as e:
                self.solution_text.delete(1.0, tk.END)
                self.solution_text.insert(tk.END, f"解题出错: {str(e)}")
                return False
        except Exception as e:
            messagebox.showerror("错误", f"处理失败: {str(e)}")
            return False

if __name__ == "__main__":
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()