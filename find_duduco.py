import time
from PIL import ImageGrab, Image, ImageTk
import tkinter as tk
from tkinter import messagebox, filedialog

from duduco_solve import DuducoPuzzleSolver
from grid_recog import recognize_from_image as _grid_recognize, get_cell_center as _grid_get_cell_center
from board_detect import detect_board as _detect_board

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
    """图像网格识别器：委托 grid_recog / board_detect 子模块执行实际工作。
    本类仅保存状态（网格线坐标、裁剪bbox），供 MainWindow 查询。"""

    def __init__(self):
        self._board_crop_bbox = None       # 自动检测时棋盘在屏幕上的裁剪坐标 (x1,y1,x2,y2)
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

    # BETA: 全屏截图自动定位棋盘区域，算法仍在优化中
    def auto_detect_board(self, image):
        """自动定位棋盘：委托 board_detect.detect_board，缓存裁剪坐标"""
        self._board_crop_bbox = None
        result = _detect_board(image)
        if result is None:
            return None
        cropped, bbox = result
        self._board_crop_bbox = bbox
        return cropped

class ScreenshotSelector:
    """截图选择器：全屏半透明遮罩，鼠标拖动框选区域，Esc取消"""

    def __init__(self, parent):
        """创建全屏半透明遮罩窗口，绑定鼠标事件"""
        self.parent = parent
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
        """打开本地图像文件：弹出文件对话框，载入后自动识别+解题"""
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
        """截图识别：最小化窗口 → 弹出全屏遮罩框选棋盘 → 截取后自动识别+解题"""
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
        """自动识别：最小化窗口 → 全屏截图 → 自动检测棋盘 → 识别+解题"""
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
        """自动点击：按解题结果依次将鼠标移动到每个嘟嘟可格子中心点并双击"""
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
        time.sleep(0.3)

        user32 = ctypes.windll.user32

        for color, (row, col) in sorted(self.solution.items()):
            center = self.recognizer.get_cell_center(row, col)
            if center is None:
                continue
            sx = int(bx + center[0])
            sy = int(by + center[1])
            user32.SetCursorPos(sx, sy)
            time.sleep(0.08)
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.05)
            user32.mouse_event(0x0004, 0, 0, 0, 0)
            time.sleep(0.12)
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.05)
            user32.mouse_event(0x0004, 0, 0, 0, 0)
            time.sleep(0.15)

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
        """核心管线：网格识别 → 颜色聚类 → 构建求解器 → 约束传播 → 回溯求解 → 显示结果"""
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