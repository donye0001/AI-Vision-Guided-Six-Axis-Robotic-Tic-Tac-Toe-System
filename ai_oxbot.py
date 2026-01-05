from pymycobot import MyCobot280
from img_recognition import OXDetector   
import time
import math

# === IO設定 ===
mc = MyCobot280('COM3',115200)
mcSpeep = 60
penLift = 30

# === 角度定義 ===
HOME = [0, 0, 0, 0, 0, -45]

# === 姿態定義 ===
DRAW_P = [0, 190, 50, -90, -45, 0]
Nine_Centers = [
    [[ 60, 170], [ 60, 200], [ 60, 230]],
    [[  0, 170], [  0, 200], [  0, 230]],
    [[-60, 170], [-60, 200], [-60, 230]]]
Board = [[0,0,0],[0,0,0],[0,0,0]]

# === 基本動作 ===
class Actions:
    def go_home(self):
        print("[INFO] Going home...")
        mc.send_angles(HOME, mcSpeep, 0)
        time.sleep(2)

    def draw_pose(self, pose):
        print("[INFO] Moving to draw pose...")
        mc.send_coords(pose, mcSpeep, 0)
        time.sleep(1)
        mc.send_coord(3, pose[2]+penLift, 30)
        time.sleep(0.5)
    
    def take_pin(self):
        print("[INFO] Taking pin...")
        mc.set_gripper_state(0, 50)
        time.sleep(2)
        mc.set_gripper_state(1, 50)
        time.sleep(0.5)
    
    def draw_O(self, pose):
        center = pose[0:2]
        height = pose[2]
        rx, ry, rz = pose[3:6]
        radius = 10
        print("[INFO] Drawing O...")
        olist = []
        
        for ang in range(0, 361, 20):
            rad = math.radians(ang)
            x = center[0] + radius * round(math.cos(rad), 2)
            y = center[1] + radius * round(math.sin(rad), 2)
            if ang == 0:
                olist.append([x, y, height+penLift , rx, ry, rz])
            olist.append([x, y, height, rx, ry, rz])
        olist.append([x, y, height+penLift , rx, ry, rz])
        for pose in olist:
            mc.send_coords(pose, 10, 1)
            # time.sleep(0.5)
    
    def draw_X(self, pose):
        def interpolate(p1, p2, steps):
            return [[p1[i] + (p2[i]-p1[i]) * t / (steps-1) for i in range(len(p1))] 
                    for t in range(steps)]
        
        x, y = pose[0:2]
        height = pose[2]
        rx, ry, rz = pose[3:6]
        offset = 10
        steps = 10
        print("[INFO] Drawing X...")

        # 原始角點
        xlist = [
            [x+offset, y+offset, height+penLift, rx, ry, rz],  # 抬筆到起點
            [x+offset, y+offset, height, rx, ry, rz],          # 落筆
            [x-offset, y-offset, height, rx, ry, rz],          # 畫線到對角
            [x-offset, y-offset, height+penLift, rx, ry, rz],  # 抬筆
            [x+offset, y-offset, height+penLift, rx, ry, rz],  # 移到另一筆起點
            [x+offset, y-offset, height, rx, ry, rz],          # 落筆
            [x-offset, y+offset, height, rx, ry, rz],          # 畫線到對角
            [x-offset, y+offset, height+penLift, rx, ry, rz]   # 抬筆完成
        ]

        smooth_path = []
        for i in range(len(xlist)-1):
            if i in [1, 5]:  # 抬筆段不插值
                smooth_path += interpolate(xlist[i], xlist[i+1], steps)
            else:
                smooth_path.append(xlist[i])
        for pose in smooth_path:
            mc.send_coords(pose, 10, 1)
            # print(pose)

    def draw_test(self):
        print("[INFO] Drawing test pattern...")
        safe_height = 120      # 安全高度 (提筆)
        tap_height = 70        # 點擊高度 (下壓)
        fixed_angles = [-90, -45, 0]  # 固定姿態 [rx, ry, rz]
        speed = 50             # 移動速度
        mode = 1               # 模式
    
        print("[INFO] 開始點擊九個格子...")

        for i in range(3):
            for j in range(3):
                x, y = Nine_Centers[i][j]
                print(f"[{i*3+j+1}/9] 點擊格子 ({i},{j}) at pixel ({x},{y})")
                # # 1-1. 使用排程執行畫 O 動作
                # manager.add_task(action.draw_O, [x, y, tap_height] + fixed_angles)
                
                # 2-1. 提筆，移到目標上方
                pose_safe = [x, y, safe_height] + fixed_angles
                mc.send_coords(pose_safe, speed, mode)
                time.sleep(2)
                
                # 2-2. 下壓點擊
                pose_tap = [x, y, tap_height] + fixed_angles
                mc.send_coords(pose_tap, 20, mode)  # 慢速下壓
                time.sleep(2)
                
                # 2-3. 提筆
                mc.send_coords(pose_safe, 30, mode)  # 快速提筆
                time.sleep(2)

                # 2-4. 回去
                mc.send_angles(HOME, 70, mode)
                time.sleep(2)

# === AI 決策 ===
class DecisionAI:
    EMPTY = 0
    HUMAN = 1
    AI = 2

    def __init__(self, board):
        self.board = board

    def check_winner(self, board):
        """回傳 1(HUMAN), 2(AI), 或 0(尚未分勝負)"""
        # rows
        for i in range(3):
            if board[i][0] == board[i][1] == board[i][2] != self.EMPTY:
                return board[i][0]

        # cols
        for j in range(3):
            if board[0][j] == board[1][j] == board[2][j] != self.EMPTY:
                return board[0][j]

        # diagonals
        if board[0][0] == board[1][1] == board[2][2] != self.EMPTY:
            return board[0][0]
        if board[0][2] == board[1][1] == board[2][0] != self.EMPTY:
            return board[0][2]

        return self.EMPTY

    def is_full(self, board):
        return all(cell != self.EMPTY for row in board for cell in row)

    def minimax(self, board, depth, is_ai_turn):
        winner = self.check_winner(board)
        if winner == self.AI:
            return 10 - depth
        if winner == self.HUMAN:
            return depth - 10
        if self.is_full(board):
            return 0
        if is_ai_turn:
            best = -float("inf")
            for i in range(3):
                for j in range(3):
                    if board[i][j] == self.EMPTY:
                        board[i][j] = self.AI
                        score = self.minimax(board, depth + 1, False)
                        board[i][j] = self.EMPTY
                        best = max(best, score)
            return best
        else:
            best = float("inf")
            for i in range(3):
                for j in range(3):
                    if board[i][j] == self.EMPTY:
                        board[i][j] = self.HUMAN
                        score = self.minimax(board, depth + 1, True)
                        board[i][j] = self.EMPTY
                        best = min(best, score)
            return best

    def get_best_move(self):
        """回傳 (row, col)"""
        best_score = -float("inf")
        best_move = None

        # 使用 board 副本，避免污染原始狀態
        board_copy = [row[:] for row in self.board]

        for i in range(3):
            for j in range(3):
                if board_copy[i][j] == self.EMPTY:
                    board_copy[i][j] = self.AI
                    score = self.minimax(board_copy, 0, False)
                    board_copy[i][j] = self.EMPTY

                    if score > best_score:
                        best_score = score
                        best_move = (i, j)
        return best_move

# === 任務封裝 ===
class Task:
    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __call__(self):
        return self.func(*self.args, **self.kwargs)

# === 中心處理 ===
class TaskManager:
    def __init__(self):
        self.tasks = []

    def add_task(self, func, *args, **kwargs):
        self.tasks.append(Task(func, *args, **kwargs))

    def get_next_task(self): #預送入執行
        if self.tasks:
            return self.tasks.pop(0)
        return None

    def run(self):
        time.sleep(2)
        while True:
            print("[INFO] Waiting task...")
            time.sleep(0.1)

            task = self.get_next_task()
            if task:
                task()  # 執行任務
                print("[INFO] Task finished\n")
            else:
                print("[INFO] No task")
                time.sleep(1)
                break

# === 主要 ===
if __name__ == "__main__":
    manager = TaskManager()
    action = Actions()
    decision = DecisionAI(Board)
    # ox = OXDetector(camera_id=1, show_gui=True)

    n = 0
    while True:
        if n == 0:
            print("[INFO] 請人類玩家下 O")
            ox = OXDetector(camera_id=1, show_gui=True)
            ox.run()
            board_state = ox.get_board_state()
            print(f"[INFO] 目前棋盤狀態: {board_state}")
            del ox
            n += 1
        elif n == 1:
            print("[INFO] 輪到 AI 玩家下 X")
            Board = [board_state[i*3:(i+1)*3] for i in range(3)].copy()
            decision.board = [[1 if cell=='O' else 2 if cell=='X' else 0 for cell in row] for row in Board]
            print(f"[DEBUG] 轉換後棋盤狀態: {decision.board}")
            move = decision.get_best_move()
            if move:
                row, col = move
                print(f"[INFO] AI 選擇下在格子 ({row}, {col})")
                x, y = Nine_Centers[row][col]
                manager.add_task(action.go_home)
                manager.add_task(action.draw_pose, [x, y, 70, -90, -45, 0])
                manager.add_task(action.draw_X, [x, y, 70, -90, -45, 0])
                manager.add_task(action.go_home)
                manager.run()
                print("[INFO] 等待系統整理...")
                time.sleep(20)  # 等待玩家看到結果
                n -= 1
            else:
                print("[INFO] 遊戲結束，無法下子")
                del ox
                break
            

    # 加入排程流程的任務
    # manager.add_task(action.go_home)
    # manager.add_task(action.draw_pose, Nine_Centers[0][1] + [50, -90, -45, 0])
    # # manager.add_task(action.take_pin)
    # manager.add_task(action.draw_X, Nine_Centers[0][1] + [50, -90, -45, 0])
    # # manager.add_task(action.draw_test)
    # manager.add_task(action.go_home)

    # 查詢座標
    # print(f"{mc.get_coords()}")

    # 啟動 TaskManager 主排程
    # manager.run()





    