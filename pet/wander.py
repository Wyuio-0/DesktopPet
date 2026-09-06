"""屏幕边缘漫游与任务栏吸附协调器。

职责：
1. 漫游模式（Wandering）：在桌宠处于空闲状态时，定时/随机向左或向右慢速散步一段距离，
   遇到屏幕边缘自动折返并镜像朝向；遇交互（点击、拖拽、打开输入框等）立即无感打断。
2. 任务栏吸附（Taskbar Snapping）：检测屏幕可用工作区边缘，当桌宠被拖拽靠近任务栏边缘时
   （阈值内）自动吸附贴合并播放坐下（sit）动作，呈现坐在任务栏上荡腿的效果。
"""

import random
from PyQt5 import QtCore, QtWidgets


class PetWanderCoordinator(QtCore.QObject):
    """协调桌面宠物的自由漫游与任务栏吸附交互。"""

    def __init__(self, window):
        parent = window if isinstance(window, QtCore.QObject) else None
        super().__init__(parent)
        self.window = window

        self.is_wandering = False
        self.wander_target_x = 0
        self.wander_dir = 1
        self._wander_step_px = 2

        # 漫游决策定时器（空闲时周期性随机触发）
        self._wander_check_timer = QtCore.QTimer(self)
        self._wander_check_timer.setSingleShot(True)
        self._wander_check_timer.timeout.connect(self._on_check_wander)

        # 漫游步进定时器（驱动平滑移动）
        self._wander_step_timer = QtCore.QTimer(self)
        self._wander_step_timer.setInterval(30)
        self._wander_step_timer.timeout.connect(self._on_wander_step)

        # 初始延迟后启动漫游检测循环
        self._schedule_next_check(initial=True)

    # ------------------------------------------------------------------ #
    # 自由漫游机制 (Wandering)                                            #
    # ------------------------------------------------------------------ #

    def _schedule_next_check(self, initial=False):
        """设定下一次漫游尝试的时间间隔（15 ~ 35 秒随机）。"""
        self._wander_check_timer.stop()
        if not getattr(self.window, "_quitting", False):
            delay = random.randint(5000, 10000) if initial else random.randint(15000, 35000)
            self._wander_check_timer.start(delay)

    def _can_wander(self):
        """检查当前状态是否允许开始漫游。"""
        w = self.window
        # 1. 开关检测
        if not w.prefs.get("wandering_enabled", True):
            return False
        # 2. 窗口可见性与退出状态
        if not w.isVisible() or getattr(w, "_quitting", False):
            return False
        # 3. 正在拖拽、处于拖动状态或尚未完成首帧定位
        if getattr(w, "_moved", False) or getattr(w, "_drag_offset", None) is not None:
            return False
        if not getattr(w, "_first_frame_shown", True):
            return False
        # 4. 当前仅在 idle 动作下才允许发起散步
        if getattr(w, "_cur_action", None) is None or w._cur_action.name != "idle":
            return False
        # 5. 正在对话或输入框开启时禁止漫游
        if hasattr(w, "input") and w.input.isVisible():
            return False
        if hasattr(w, "input_ctrl") and w.input_ctrl.worker is not None and w.input_ctrl.worker.isRunning():
            return False
        # 6. 专注工具运行期间保持安静，不四处走动
        if hasattr(w, "focus_mgr") and w.focus_mgr.is_focus_active():
            return False
        return True

    def _on_check_wander(self):
        """周期决策：是否在空闲时开始漫步。"""
        if not self._can_wander():
            self._schedule_next_check()
            return

        w = self.window
        screen = w.screen() or QtWidgets.QApplication.primaryScreen()
        if not screen:
            self._schedule_next_check()
            return

        avail = screen.availableGeometry()
        pet_w = max(1, w.width())
        min_x = avail.left() + 20
        max_x = avail.right() - pet_w - 20
        cur_x = w.x()

        if max_x <= min_x:
            self._schedule_next_check()
            return

        # 漫步距离与方向决策
        distance = random.randint(90, 220)
        # 靠近屏幕左侧边界则强制向右；靠近右侧边界则强制向左
        if cur_x <= min_x + 60:
            direction = 1
        elif cur_x >= max_x - 60:
            direction = -1
        else:
            direction = random.choice([-1, 1])

        target_x = max(min_x, min(max_x, cur_x + direction * distance))
        if abs(target_x - cur_x) < 30:
            self._schedule_next_check()
            return

        # 启动漫游
        self.is_wandering = True
        self.wander_target_x = target_x
        self.wander_dir = 1 if target_x > cur_x else -1
        self._wander_step_px = 2

        # 角色水平镜像翻转：行走朝左时翻转，朝右时恢复正常
        w._facing_left = (self.wander_dir < 0)

        # 播放 move 动作
        w.play("move")
        self._wander_step_timer.start()

    def _on_wander_step(self):
        """步进定时器心跳：平滑推进 x 坐标。"""
        if not self.is_wandering:
            self._wander_step_timer.stop()
            return

        w = self.window
        # 若动作已被打断（非 move），退出漫游状态
        if w._cur_action is None or w._cur_action.name != "move":
            self.cancel_wandering()
            return

        cur_x = w.x()
        diff = self.wander_target_x - cur_x

        if abs(diff) <= self._wander_step_px:
            # 到达目标位置，正常结束漫游
            w.move(self.wander_target_x, w.y())
            w._reposition_popups()
            w._save_pet_position()
            self.cancel_wandering(finish_normally=True)
            return

        step = self._wander_step_px if self.wander_dir > 0 else -self._wander_step_px
        new_x = cur_x + step
        w.move(new_x, w.y())
        w._reposition_popups()

    def cancel_wandering(self, finish_normally=False):
        """打断或完成漫游状态。"""
        was_wandering = self.is_wandering
        self.is_wandering = False
        self._wander_step_timer.stop()

        w = self.window
        w._facing_left = False

        if was_wandering:
            if finish_normally or (w._cur_action and w._cur_action.name == "move"):
                w.play("idle")

        self._schedule_next_check()

    # ------------------------------------------------------------------ #
    # 任务栏吸附与坐下 (Taskbar Snapping & Docking)                         #
    # ------------------------------------------------------------------ #

    def check_taskbar_snap(self, moved=True):
        """检查并执行任务栏边缘吸附。

        检测角色脚底位置与 Windows 工作区底部（即底部任务栏上沿）的距离：
        若在阈值内，将角色脚底精准吸附贴合任务栏，并触发坐下（sit）动作。
        """
        w = self.window
        if not w.prefs.get("taskbar_dock_enabled", True):
            return False

        center = None
        if hasattr(w, "frameGeometry"):
            try:
                fg = w.frameGeometry()
                if hasattr(fg, "center"):
                    c = fg.center()
                    if isinstance(c, QtCore.QPoint):
                        center = c
            except Exception:
                pass

        screen = (QtWidgets.QApplication.screenAt(center) if center else None) or (
            w.screen() if hasattr(w, "screen") and callable(w.screen) else None
        ) or QtWidgets.QApplication.primaryScreen()
        if not screen:
            return False

        avail = screen.availableGeometry()
        body = w._body_rect()
        taskbar_top = avail.bottom()

        # gap > 0 表示在任务栏上方悬空，gap < 0 表示已超出任务栏下沿
        gap = taskbar_top - body.bottom()

        # 大幅放宽吸附识别区：
        # 上方识别区：脚底距离任务栏上沿 180px 内（从大半个身位外拖近即可轻松吸附）
        # 下方识别区：即使拖放到了任务栏内部甚至沉入底边（140px 内），也自动上浮吸附精准贴合任务栏
        if -140 <= gap <= 180:
            new_y = w.y() + gap
            w.move(w.x(), new_y)
            w._reposition_popups()
            w._save_pet_position()
            if moved:
                # 吸附成功：播放坐下（sit）动作，宛如坐在任务栏上
                if w.char.action("sit"):
                    w.play("sit")
            return True

        return False

    def close(self):
        """释放并停止所有定时器。"""
        self._wander_check_timer.stop()
        self._wander_step_timer.stop()
        self.is_wandering = False
