import cv2
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk
import ttkbootstrap as ttk

class OXDetector:
    """井字遊戲 O/X 辨識器 - 簡化版"""
    
    def __init__(self, camera_id=0, show_gui=True):
        self.cap = cv2.VideoCapture(camera_id)
        self.cap.set(3, 640)
        self.cap.set(4, 480)
        
        self.grid_rect = None
        self.board = [' ' for _ in range(9)]
        
        # 新增：控制更新循環的旗標
        self.running = False
        self.after_id = None
        
        # 可調參數
        self.threshold = 100
        self.min_area = 150          # 最小面積
        self.max_area = 3000         # 最大面積
        self.circle_tolerance = 50   # 圓形容差 (0-100)
        self.blur_size = 3           # 模糊程度
        
        if show_gui:
            self.window = ttk.Window(themename="darkly")
            self.window.title("OX Detector")
            self.window.geometry("1000x650")
            # 新增：綁定視窗關閉事件
            self.window.protocol("WM_DELETE_WINDOW", self._close)
            self._setup_gui()
        else:
            self.window = None
    
    def _setup_gui(self):
        """建立GUI"""
        # 控制面板
        ctrl = ttk.Frame(self.window, padding=10)
        ctrl.pack(fill=tk.X)
        
        # 按鈕區
        btn_frame = ttk.Frame(ctrl)
        btn_frame.pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="🔄 重置", 
                  command=self.reset, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="❌ 離開", 
                  command=self._close, width=10).pack(side=tk.LEFT, padx=3)
        
        # 參數調整區
        param_frame = ttk.Frame(self.window, padding=10)
        param_frame.pack(fill=tk.X, padx=10)
        
        def add_slider(parent, label, from_, to, default):
            frame = ttk.Frame(parent)
            frame.pack(fill=tk.X, pady=3)
            ttk.Label(frame, text=label, width=10).pack(side=tk.LEFT, padx=5)
            var = tk.IntVar(value=default)
            scale = ttk.Scale(frame, from_=from_, to=to, variable=var, length=200)
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            lbl = ttk.Label(frame, text=str(default), width=5)
            lbl.pack(side=tk.LEFT)
            scale.configure(command=lambda v: lbl.configure(text=f"{int(float(v))}"))
            return var
        
        self.var_thresh = add_slider(param_frame, "黑白門檻", 0, 255, 100)
        self.var_min = add_slider(param_frame, "最小面積", 50, 1000, 150)
        self.var_max = add_slider(param_frame, "最大面積", 500, 5000, 3000)
        self.var_circle = add_slider(param_frame, "圓形容差", 0, 100, 50)
        self.var_blur = add_slider(param_frame, "模糊程度", 1, 9, 3)
        
        # 顯示區
        self.canvas = tk.Canvas(self.window, bg='black', height=400)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 狀態列
        self.status_var = tk.StringVar(value="✅ 就緒 - 將紙張放入鏡頭前，自動偵測網格")
        ttk.Label(self.window, textvariable=self.status_var, 
                 relief=tk.SUNKEN, padding=5).pack(fill=tk.X, padx=5, pady=5)
    
    def _toggle_roi_selection(self):
        self.selecting_roi = not self.selecting_roi
        self.status_var.set("🖱️ 點擊拖曳選取區域" if self.selecting_roi else "✅ 已取消選取")
    
    def _on_mouse_down(self, event):
        if self.selecting_roi:
            self.roi_start = (event.x, event.y)
    
    def _on_mouse_drag(self, event):
        if self.selecting_roi and self.roi_start:
            self.roi_end = (event.x, event.y)
    
    def _on_mouse_up(self, event):
        if self.selecting_roi and self.roi_start:
            scale_x = 640 / max(self.canvas.winfo_width(), 1)
            scale_y = 480 / max(self.canvas.winfo_height(), 1)
            
            x1, y1 = self.roi_start
            x = int(min(x1, event.x) * scale_x)
            y = int(min(y1, event.y) * scale_y)
            w = int(abs(event.x - x1) * scale_x)
            h = int(abs(event.y - y1) * scale_y)
            
            if w > 50 and h > 50:
                self.grid_rect = (x, y, w, h)
                self.status_var.set(f"✅ 已選取 {w}x{h}")
            
            self.selecting_roi = False
    
    def _detect_shape(self, cell_roi):
        """簡化的形狀辨識"""
        contours, _ = cv2.findContours(cell_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (self.min_area < area < self.max_area):
                continue
            
            # 檢查圓形度
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue
            
            circularity = 4 * np.pi * area / (perimeter ** 2)
            threshold = 0.3 + (self.circle_tolerance / 100) * 0.5  # 0.3~0.8
            
            if circularity > threshold:
                return 'O'
            
            # 檢查X：用矩形長寬比
            x, y, w, h = cv2.boundingRect(cnt)
            aspect = max(w, h) / max(min(w, h), 1)
            if aspect < 2.5:  # 不要太細長
                hull = cv2.convexHull(cnt)
                hull_area = cv2.contourArea(hull)
                if hull_area > 0:
                    solidity = area / hull_area
                    if solidity < 0.85:  # X會比較不實心
                        return 'X'
        
        return ' '
    
    def get_board_state(self):
        """回傳 [' ', 'X', 'O', ...] 9個元素"""
        return self.board.copy()
    
    def get_board_2d(self):
        """回傳 3x3 二維陣列"""
        return [self.board[i:i+3] for i in range(0, 9, 3)]
    
    def reset(self):
        self.grid_rect = None
        self.board = [' '] * 9
        if self.window:
            self.status_var.set("🔄 已重置")
    
    def process_frame(self):
        """處理影像並更新棋盤"""
        ret, frame = self.cap.read()
        if not ret:
            return None
        
        frame = cv2.flip(frame, 1)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 更新參數
        if self.window and hasattr(self, 'var_thresh'):
            self.threshold = self.var_thresh.get()
            self.min_area = self.var_min.get()
            self.max_area = self.var_max.get()
            self.circle_tolerance = self.var_circle.get()
            blur = self.var_blur.get()
            if blur % 2 == 0:
                blur += 1
            gray = cv2.GaussianBlur(gray, (blur, blur), 0)
        
        _, thresh = cv2.threshold(gray, self.threshold, 255, cv2.THRESH_BINARY_INV)
        
        display = frame.copy()
        
        # 自動偵測網格
        if self.grid_rect is None:
            kernel = np.ones((7, 7), np.uint8)
            dilated = cv2.dilate(thresh, kernel)
            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > 5000:
                    x, y, w, h = cv2.boundingRect(cnt)
                    if 0.4 < w/max(h, 1) < 2.5:
                        self.grid_rect = (x, y, w, h)
                        break
        
        # 辨識棋盤
        if self.grid_rect:
            x, y, w, h = self.grid_rect
            cell_w, cell_h = w // 3, h // 3
            
            # 畫格線
            for i in range(4):
                cv2.line(display, (x+i*cell_w, y), (x+i*cell_w, y+h), (0,255,0), 2)
                cv2.line(display, (x, y+i*cell_h), (x+w, y+i*cell_h), (0,255,0), 2)
            
            # 檢測每格
            for i in range(9):
                r, c = i // 3, i % 3
                cx, cy = x + c*cell_w + cell_w//2, y + r*cell_h + cell_h//2
                
                rx, ry = x + c*cell_w + 5, y + r*cell_h + 5
                rw, rh = cell_w - 10, cell_h - 10
                
                if ry+rh <= thresh.shape[0] and rx+rw <= thresh.shape[1]:
                    cell_roi = thresh[ry:ry+rh, rx:rx+rw]
                    
                    if self.board[i] == ' ':
                        self.board[i] = self._detect_shape(cell_roi)
                    
                    # 顯示結果
                    if self.board[i] == 'O':
                        cv2.circle(display, (cx, cy), 20, (0,255,255), 3)
                    elif self.board[i] == 'X':
                        d = 18
                        cv2.line(display, (cx-d, cy-d), (cx+d, cy+d), (255,100,255), 3)
                        cv2.line(display, (cx+d, cy-d), (cx-d, cy+d), (255,100,255), 3)
        
        return display
    
    def run(self):
        """啟動GUI"""
        if not self.window:
            raise RuntimeError("需要 show_gui=True")
        
        self.running = True  # 啟動標記
        
        def update():
            if not self.running:  # 檢查是否應該繼續
                return
            
            try:
                frame = self.process_frame()
                if frame is not None:
                    h, w = frame.shape[:2]
                    canvas_w = max(self.canvas.winfo_width(), 100)
                    canvas_h = max(self.canvas.winfo_height(), 100)
                    
                    scale = min(canvas_w/w, canvas_h/h)
                    new_w = max(int(w*scale), 1)
                    new_h = max(int(h*scale), 1)
                    
                    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = cv2.resize(img, (new_w, new_h))
                    photo = ImageTk.PhotoImage(image=Image.fromarray(img))
                    
                    self.canvas.delete("all")
                    self.canvas.create_image(canvas_w//2, canvas_h//2, image=photo)
                    self.canvas.image = photo
                
                if self.running:  # 只在 running 時才排程下次更新
                    self.after_id = self.window.after(30, update)
            
            except tk.TclError:
                # 視窗已關閉，停止更新
                self.running = False
        
        self.window.update()
        update()
        self.window.mainloop()
    
    def _close(self):
        """安全地關閉應用程式"""
        self.running = False  # 停止更新循環
        
        # 取消所有待執行的 after 回調
        if self.after_id is not None:
            try:
                self.window.after_cancel(self.after_id)
            except:
                pass
        
        # 釋放攝影機
        if self.cap is not None:
            self.cap.release()
        
        # 銷毀視窗
        if self.window:
            try:
                self.window.quit()  # 先退出 mainloop
                self.window.destroy()
            except:
                pass


# 使用範例
if __name__ == "__main__":
    detector = OXDetector(camera_id=1, show_gui=True)
    detector.run()