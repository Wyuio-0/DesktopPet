"""久坐关怀与健康提醒协调器。

职责：
1. 基于 Windows 原生 API (GetLastInputInfo) 无感获取键盘与鼠标活跃/空闲状态；
2. 持续监测博士的连续工作时间：当连续工作达到设定阈值（默认 60 分钟）且未离开休息时，
   桌宠主动播放提醒动作、弹出温馨关怀气泡并进行语音播报；
3. 离开电脑休息检测：若用户连续 10 分钟以上无任何键鼠输入，视为离开休息，
   重新返回操作时自动重置连续工作时长；
4. 防打扰缓冲保护：发出提醒后若用户未离开电脑，进入 30 分钟缓冲期，避免频繁弹窗打扰。
"""

import ctypes
import time
from ctypes import wintypes
from PyQt5 import QtCore


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


def get_idle_ms():
    """返回距离上一次系统键鼠操作的毫秒数；非 Windows 或调用失败时返回 0。"""
    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            if hasattr(ctypes.windll.kernel32, "GetTickCount64"):
                tick = ctypes.windll.kernel32.GetTickCount64() & 0xFFFFFFFF
            else:
                tick = ctypes.windll.kernel32.GetTickCount()
            return (tick - lii.dwTime) & 0xFFFFFFFF
    except Exception:
        pass
    return 0


class PetSedentaryCareCoordinator(QtCore.QObject):
    """协调桌面宠物的久坐健康关怀逻辑。"""

    # 判定离开电脑休息的闲置阈值（秒）：10 分钟
    REST_THRESHOLD_SEC = 10 * 60
    # 提醒后的防重复打扰缓冲时间（秒）：30 分钟
    REPEAT_SNOOZE_SEC = 30 * 60

    def __init__(self, window):
        parent = window if isinstance(window, QtCore.QObject) else None
        super().__init__(parent)
        self.window = window

        self._session_start_time = time.time()
        self._is_resting = False
        self._last_remind_time = 0

        # 定时轮询器：每 10 秒评估一次键鼠状态
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(10 * 1000)
        self._poll_timer.timeout.connect(self._check_sedentary)
        self._poll_timer.start()

    def reload_config(self):
        """配置项变更时被设置窗口调用。"""
        # 如果从关闭变为开启，刷新会话起始时间
        if self.is_enabled() and self._session_start_time == 0:
            self._session_start_time = time.time()

    def is_enabled(self):
        w = self.window
        if not hasattr(w, "prefs"):
            return True
        return bool(w.prefs.get("sedentary_enabled", True))

    def get_interval_min(self):
        w = self.window
        if not hasattr(w, "prefs"):
            return 60
        try:
            return int(w.prefs.get("sedentary_interval_min", 60))
        except (ValueError, TypeError):
            return 60

    def _format_reminder_text(self, interval_min):
        """生成温馨的久坐关怀文案。"""
        if interval_min == 60:
            time_desc = "一小时"
        elif interval_min == 90:
            time_desc = "一个半小时"
        elif interval_min == 120:
            time_desc = "两小时"
        else:
            time_desc = "%d 分钟" % interval_min
        return "博士，您已经连续工作%s了，请站起来活动一下关节、喝杯温水吧。" % time_desc

    def trigger_reminder(self, interval_min=None):
        """发出久坐提醒通知。"""
        w = self.window
        if getattr(w, "_quitting", False) or not w.isVisible():
            return
        if interval_min is None:
            interval_min = self.get_interval_min()
        text = self._format_reminder_text(interval_min)
        if hasattr(w, "_announce"):
            w._announce(text, use_tts=True)

    def _check_sedentary(self):
        """周期决策：检查是否达到久坐阈值或处于离开休息状态。"""
        w = self.window
        if not self.is_enabled():
            return
        if getattr(w, "_quitting", False) or not w.isVisible():
            return
        # 专注倒计时或番茄钟期间尊重专注模式，不打断
        if hasattr(w, "focus_mgr") and w.focus_mgr.is_focus_active():
            return

        now = time.time()
        idle_sec = get_idle_ms() / 1000.0

        # 1. 检测用户是否离开电脑去休息
        if idle_sec >= self.REST_THRESHOLD_SEC:
            if not self._is_resting:
                self._is_resting = True
            return

        # 2. 用户处于活跃使用状态（idle_sec < REST_THRESHOLD_SEC）
        if self._is_resting:
            # 刚从一次 >= 10 分钟的休息重新回来工作，重置会话计时器
            self._is_resting = False
            self._session_start_time = now
            self._last_remind_time = 0
            return

        # 3. 累积连续工作时长检测
        work_sec = max(0.0, now - self._session_start_time)
        target_sec = self.get_interval_min() * 60

        if work_sec >= target_sec:
            # 检查是否在防重复提醒缓冲期内
            if now - self._last_remind_time >= self.REPEAT_SNOOZE_SEC:
                self._last_remind_time = now
                self.trigger_reminder(self.get_interval_min())

    def close(self):
        """释放并停止定时器。"""
        self._poll_timer.stop()
