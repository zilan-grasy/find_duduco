import sys
import cv2
import numpy as np
from PIL import ImageGrab, Image, ImageTk
import tkinter as tk
from tkinter import messagebox, filedialog
from collections import defaultdict

# 设置DPI感知，让Windows不要自动缩放程序
try:
    import ctypes
    # Windows 10+ 的DPI感知设置
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except:
    try:
        # Windows 8.1 及更早版本
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

class ScreenshotSelector:
    """截图选择器 - 正确处理DPI缩放"""

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
        self.root.geometry("720x660")

        self.recognizer = GridImageRecognizer()
        self.current_image = None
        self.recognized_grid = None
        self.is_topmost = False

        # 工具栏
        toolbar = tk.Frame(root, bg='lightgray')
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)

        self.btn_open = tk.Button(toolbar, text="打开图像", command=self.open_image)
        self.btn_open.pack(side=tk.LEFT, padx=2)

        self.btn_capture = tk.Button(toolbar, text="截图识别", command=self.capture_screenshot)
        self.btn_capture.pack(side=tk.LEFT, padx=2)

        self.btn_save = tk.Button(toolbar, text="保存结果", command=self.save_result)
        self.btn_save.pack(side=tk.LEFT, padx=2)

        self.btn_topmost = tk.Button(toolbar, text="置顶", command=self.toggle_topmost)
        self.btn_topmost.pack(side=tk.RIGHT, padx=2)

        # 主内容区
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        
        # 使用grid布局：左侧上下结构，右侧识别结果
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

        # 右侧：详细结果（跨两行）
        right_frame = tk.Frame(main_frame, borderwidth=1, relief=tk.SUNKEN)
        right_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=2)

        result_label = tk.Label(right_frame, text="识别结果", bg='lightblue')
        result_label.pack(fill=tk.X)

        self.result_text = tk.Text(right_frame, font=('Courier', 11))
        self.result_text.pack(fill=tk.BOTH, expand=True)
        self.result_text.insert(tk.END, "识别结果将显示在这里\n")
        self.result_text.insert(tk.END, "请打开图像或截图识别网格")

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

    def open_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("图像文件", "*.jpg;*.jpeg;*.png;*.bmp")])
        if file_path:
            try:
                self.current_image = Image.open(file_path)
                self.display_image()
                self.recognize_and_display()
            except Exception as e:
                messagebox.showerror("错误", f"无法打开图像: {str(e)}")

    def capture_screenshot(self):
        self.root.iconify()
        selector = ScreenshotSelector(self.root)
        self.root.wait_window(selector.root)
        
        if selector.screenshot:
            self.current_image = selector.screenshot
            self.display_image()
            self.recognize_and_display()
        
        self.root.deiconify()

    def toggle_topmost(self):
        """切换窗口置顶状态"""
        self.is_topmost = not self.is_topmost
        self.root.attributes('-topmost', self.is_topmost)
        self.btn_topmost.config(text="取消置顶" if self.is_topmost else "置顶")

    def display_image(self):
        """触发图像显示/更新"""
        self._resize_image()

    def recognize_and_display(self):
        """自动识别网格并显示结果"""
        if self.current_image:
            try:
                # 清空之前的结果
                self.grid_text.delete(1.0, tk.END)
                self.result_text.delete(1.0, tk.END)
                
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
                    
                    # 显示详细结果
                    colors = set()
                    for row in self.recognized_grid:
                        colors.update(row)
                    
                    self.result_text.delete(1.0, tk.END)
                    self.result_text.insert(tk.END, f"网格大小: {len(self.recognized_grid)}x{len(self.recognized_grid[0])}\n")
                    self.result_text.insert(tk.END, f"颜色数量: {len(colors)}\n")
                    self.result_text.insert(tk.END, "\n识别的网格矩阵:\n")
                    self.result_text.insert(tk.END, "  " + " ".join(f"{i:2d}" for i in range(size)) + "\n")
                    self.result_text.insert(tk.END, "--" + "---" * size + "\n")
                    for i, row in enumerate(self.recognized_grid):
                        self.result_text.insert(tk.END, f"{i:2d}" + " " + " ".join(f"{c:2d}" for c in row) + "\n")
                else:
                    self.grid_text.delete(1.0, tk.END)
                    self.grid_text.insert(tk.END, "未能识别到网格")
                    self.result_text.delete(1.0, tk.END)
                    self.result_text.insert(tk.END, "未能识别到网格，请确保图像中包含清晰的网格线")
            except Exception as e:
                messagebox.showerror("错误", f"识别失败: {str(e)}")

    def save_result(self):
        if self.recognized_grid:
            file_path = "test.txt"
            with open(file_path, 'w', encoding='utf-8') as f:
                size = len(self.recognized_grid)
                f.write(f"{size}\n")
                for row in self.recognized_grid:
                    f.write(' '.join(map(str, row)) + '\n')
            messagebox.showinfo("成功", f"结果已保存到 {file_path}")
        else:
            messagebox.showwarning("警告", "没有可保存的识别结果")

if __name__ == "__main__":
    import sys
    
    # 检查是否有命令行参数（命令行模式）
    if len(sys.argv) >= 3:
        image_path = sys.argv[1]
        output_path = sys.argv[2]
        
        try:
            from PIL import Image
            recognizer = GridImageRecognizer()
            image = Image.open(image_path)
            grid = recognizer.recognize_from_image(image)
            
            if grid:
                size = len(grid)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(f"{size}\n")
                    for row in grid:
                        f.write(' '.join(map(str, row)) + '\n')
                print(f"识别成功！结果已保存到 {output_path}")
            else:
                print("未能识别到网格")
        except Exception as e:
            print(f"错误: {str(e)}")
    else:
        # 正常启动GUI
        root = tk.Tk()
        app = MainWindow(root)
        root.mainloop()