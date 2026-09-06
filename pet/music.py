"""桌面听歌感知与音乐律动模块（Music Visualizer & Beats Reaction）。

功能：
1. Windows WASAPI 音频瞬时峰值采样（纯 ctypes 零依赖，微秒级开销，CPU 占用趋近 0%）；
2. 常见音乐播放器曲目信息识别（网易云、QQ音乐、酷狗、Spotify、B站等）；
3. 悬浮音乐音符粒子视效（MusicNotesOverlay）：金色 ♪ ♫ ♩ 随音乐节拍浮动跳跃，完全穿透鼠标点击；
4. AI 工具 get_current_music() 支撑；
5. 偏好设置独立开关（music_visualizer_enabled）。
"""

import ctypes
import math
import os
import random
import sys
import time
from ctypes import wintypes, POINTER, c_float, c_void_p, Structure, byref, c_int, cast, c_long

from PyQt5 import QtCore, QtGui, QtWidgets

from . import theme

_IS_WIN = sys.platform.startswith("win")

# COM GUID 结构体与接口 IID
if _IS_WIN:
    class GUID(Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", wintypes.BYTE * 8)
        ]

        def __init__(self, d1, d2, d3, d4):
            super().__init__(d1, d2, d3, (wintypes.BYTE * 8)(*d4))

    CLSID_MMDeviceEnumerator = GUID(0xBCDE0395, 0xE52F, 0x467C, (0x8E, 0x3D, 0xC4, 0x57, 0x92, 0x91, 0x69, 0x2E))
    IID_IMMDeviceEnumerator = GUID(0xA95664D2, 0x9614, 0x4F35, (0xA7, 0x46, 0xDE, 0x8D, 0xB6, 0x36, 0x17, 0xE6))
    IID_IAudioMeterInformation = GUID(0xC02216F6, 0x8C67, 0x4B5B, (0x9D, 0x00, 0xD0, 0x08, 0xE7, 0x3E, 0x00, 0x64))


def _com_call(this_ptr, vtable_idx, restype, *argtypes):
    """辅助调用 COM 虚函数表中指定序号的函数指针。"""
    vtbl = cast(this_ptr, POINTER(POINTER(c_void_p))).contents
    fn_ptr = vtbl[vtable_idx]
    proto = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)
    return proto(fn_ptr)


class WindowsAudioMeter:
    """基于 Windows Core Audio API (WASAPI) 的原生极轻量音频峰值采样器。

    使用纯 ctypes 直接获取默认音频播放设备的 Master Peak (0.0 ~ 1.0)。
    单次采样时间 < 0.1ms，零子进程，零外部依赖。
    """

    def __init__(self):
        self._initialized = False
        self._pEnum = None
        self._pDevice = None
        self._pMeter = None
        self._fnGetPeak = None
        self._ole32 = None
        if _IS_WIN:
            self._init_com()

    def _init_com(self):
        try:
            self._ole32 = ctypes.windll.ole32
            # 保证 COM 运行环境已初始化
            self._ole32.CoInitialize(None)

            pEnum = c_void_p()
            hr = self._ole32.CoCreateInstance(
                byref(CLSID_MMDeviceEnumerator),
                None,
                1,  # CLSCTX_INPROC_SERVER
                byref(IID_IMMDeviceEnumerator),
                byref(pEnum)
            )
            if hr != 0 or not pEnum.value:
                return

            # IMMDeviceEnumerator::GetDefaultAudioEndpoint(eRender=0, eMultimedia=1, &pDevice)
            pDevice = c_void_p()
            fnGetDef = _com_call(pEnum, 4, c_long, c_int, c_int, POINTER(c_void_p))
            hr = fnGetDef(pEnum, 0, 1, byref(pDevice))
            if hr != 0 or not pDevice.value:
                _com_call(pEnum, 2, wintypes.ULONG)(pEnum)
                return

            # IMMDevice::Activate(IID_IAudioMeterInformation, CLSCTX_ALL=23, NULL, &pMeter)
            pMeter = c_void_p()
            fnActivate = _com_call(pDevice, 3, c_long, POINTER(GUID), wintypes.DWORD, c_void_p, POINTER(c_void_p))
            hr = fnActivate(pDevice, byref(IID_IAudioMeterInformation), 1, None, byref(pMeter))
            if hr != 0 or not pMeter.value:
                _com_call(pDevice, 2, wintypes.ULONG)(pDevice)
                _com_call(pEnum, 2, wintypes.ULONG)(pEnum)
                return

            self._pEnum = pEnum
            self._pDevice = pDevice
            self._pMeter = pMeter
            self._fnGetPeak = _com_call(pMeter, 3, c_long, POINTER(c_float))
            self._initialized = True
        except Exception:
            self.release()

    def get_peak(self) -> float:
        """获取当前系统默认音频输出的即时峰值音量 (0.0 ~ 1.0)。"""
        if not self._initialized or not self._pMeter or not self._fnGetPeak:
            return 0.0
        try:
            peak = c_float()
            hr = self._fnGetPeak(self._pMeter, byref(peak))
            if hr == 0:
                val = float(peak.value)
                return max(0.0, min(1.0, val))
            else:
                # 设备可能发生插拔或改变，尝试重新连接
                self.release()
                self._init_com()
                return 0.0
        except Exception:
            return 0.0

    def release(self):
        """释放 COM 接口引用指针。"""
        if not _IS_WIN:
            return
        try:
            if self._pMeter:
                _com_call(self._pMeter, 2, wintypes.ULONG)(self._pMeter)
                self._pMeter = None
            if self._pDevice:
                _com_call(self._pDevice, 2, wintypes.ULONG)(self._pDevice)
                self._pDevice = None
            if self._pEnum:
                _com_call(self._pEnum, 2, wintypes.ULONG)(self._pEnum)
                self._pEnum = None
        except Exception:
            pass
        self._fnGetPeak = None
        self._initialized = False


class MusicTrackDetector:
    """常见音乐播放客户端与网页媒体标题探测器。"""

    # 常见音乐播放器特征定义：(关键词, 播放器名称, 标题清洗模式)
    PLAYER_PATTERNS = [
        ("网易云音乐", "网易云音乐"),
        ("qq音乐", "QQ音乐"),
        ("酷狗音乐", "酷狗音乐"),
        ("酷我音乐", "酷我音乐"),
        ("spotify", "Spotify"),
        ("foobar2000", "foobar2000"),
        ("哔哩哔哩", "Bilibili"),
        ("bilibili", "Bilibili"),
        ("youtube", "YouTube"),
        ("apple music", "Apple Music"),
    ]

    @staticmethod
    def get_active_media_track() -> dict:
        """探测当前正在播放的媒体标题与播放器名。

        返回格式：
        {
            "playing": bool,
            "title": str,
            "artist": str,
            "player": str,
            "raw_title": str,
        }
        """
        if not _IS_WIN:
            return {"playing": False, "title": "", "artist": "", "player": "", "raw_title": ""}

        user32 = ctypes.windll.user32
        titles = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_cb(hwnd, _lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    t = buf.value.strip()
                    if t:
                        titles.append(t)
            return 1

        try:
            user32.EnumWindows(enum_cb, 0)
        except Exception:
            pass

        for raw in titles:
            lower = raw.lower()
            for kw, player_name in MusicTrackDetector.PLAYER_PATTERNS:
                if kw in lower:
                    title, artist = MusicTrackDetector._parse_track(raw, player_name)
                    if title:
                        return {
                            "playing": True,
                            "title": title,
                            "artist": artist,
                            "player": player_name,
                            "raw_title": raw,
                        }

        return {"playing": False, "title": "", "artist": "", "player": "", "raw_title": ""}

    @staticmethod
    def _parse_track(raw: str, player: str) -> tuple:
        """从播放器窗口标题中解析出 (歌名, 歌手)。"""
        clean = raw
        # 移除播放器常见后缀与标缀
        for tag in ["- 网易云音乐", "网易云音乐 -", "网易云音乐",
                    "- QQ音乐", "QQ音乐 -", "QQ音乐",
                    "- 酷狗音乐", "酷狗音乐",
                    "- 酷我音乐", "酷我音乐",
                    "_哔哩哔哩_bilibili", "_哔哩哔哩", "- YouTube"]:
            clean = clean.replace(tag, "").strip()

        # 常见格式："歌名 - 歌手" 或 "歌手 - 歌名"
        if " - " in clean:
            parts = [p.strip() for p in clean.split(" - ") if p.strip()]
            if len(parts) >= 2:
                if player in ("Spotify", "foobar2000"):
                    # 欧美常见：Artist - Title
                    return parts[1], parts[0]
                else:
                    # 中文常见：Title - Artist
                    return parts[0], parts[1]
        return clean, ""


class _FloatingNote:
    """单个悬浮跳动音符粒子。"""

    SYMBOLS = ["♪", "♫", "♩", "♬"]

    def __init__(self, index: int):
        self.symbol = self.SYMBOLS[index % len(self.SYMBOLS)]
        self.base_x = 15 + index * 26
        self.x = float(self.base_x)
        self.base_y = 65.0
        self.y = self.base_y
        self.velocity_y = 0.0
        self.opacity = 0.0
        self.phase = index * 1.5
        self.size = 18 + (index % 3) * 3

    def tick(self, peak: float, is_playing: bool, delta_time: float = 0.04):
        """根据音频峰值更新音符物理位置与透明度。"""
        self.phase += delta_time * 4.0

        if is_playing and peak > 0.015:
            # 音乐播放中：透明度渐升，随节拍上下跃动
            target_opacity = min(1.0, 0.4 + peak * 1.2)
            self.opacity += (target_opacity - self.opacity) * 0.25

            # 随峰值冲击产生向上的升力，带柔和的浮动正弦波
            impulse = peak * 45.0
            float_wave = math.sin(self.phase) * 12.0
            target_y = self.base_y - impulse - float_wave
            self.y += (target_y - self.y) * 0.3
            self.x = self.base_x + math.cos(self.phase * 0.8) * 6.0
        else:
            # 静音或停止：缓缓下沉并平滑淡出
            self.opacity = max(0.0, self.opacity - delta_time * 0.8)
            self.y += (self.base_y - self.y) * 0.15


class MusicNotesOverlay(QtWidgets.QWidget):
    """悬浮音符特效图层：微型、透明、无边框、完全穿透鼠标点击。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.SubWindow
            | QtCore.Qt.WindowTransparentForInput
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

        self.resize(130, 90)
        self.notes = [_FloatingNote(i) for i in range(4)]
        self._visible_energy = 0.0

    def update_energy(self, peak: float, is_playing: bool):
        """传入即时音频峰值并重绘。"""
        for n in self.notes:
            n.tick(peak, is_playing)

        # 检查是否全部已完全透明
        max_op = max(n.opacity for n in self.notes)
        self._visible_energy = max_op
        if max_op > 0.02:
            if not self.isVisible():
                self.show()
            self.update()
        else:
            if self.isVisible():
                self.hide()

    def paintEvent(self, event):
        if self._visible_energy <= 0.01:
            return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)

        for n in self.notes:
            if n.opacity <= 0.02:
                continue

            alpha = int(n.opacity * 220)
            # 罗德岛金色主题音符 (#F5C842)
            color = QtGui.QColor(245, 200, 66, alpha)
            glow = QtGui.QColor(255, 240, 150, int(alpha * 0.45))

            font = QtGui.QFont("Segoe UI Symbol", n.size, QtGui.QFont.Bold)
            painter.setFont(font)

            # 微发光轮廓
            painter.setPen(glow)
            painter.drawText(QtCore.QPointF(n.x - 1, n.y - 1), n.symbol)
            painter.drawText(QtCore.QPointF(n.x + 1, n.y + 1), n.symbol)

            # 主音符主体
            painter.setPen(color)
            painter.drawText(QtCore.QPointF(n.x, n.y), n.symbol)

        painter.end()


class PetMusicCoordinator(QtCore.QObject):
    """听歌感知与音乐律动总协调器。"""

    _active_instance = None

    def __init__(self, window):
        super().__init__(window if isinstance(window, QtCore.QObject) else None)
        PetMusicCoordinator._active_instance = self
        self.window = window

        self.meter = WindowsAudioMeter()
        self.overlay = MusicNotesOverlay(window if isinstance(window, QtWidgets.QWidget) else None)

        # 状态统计
        self._last_peak = 0.0
        self._playing_streak = 0
        self._silence_streak = 0
        self._is_music_active = False

        # 缓存当前检测到的歌曲
        self._cached_track = {"playing": False, "title": "", "artist": "", "player": ""}
        self._last_track_check = 0.0

        # 音频高频采样与动效定时器（通常 35ms / ~28 FPS）
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        self.reload_config()

    @classmethod
    def get_active_instance(cls):
        return cls._active_instance

    def reload_config(self):
        """重新加载开关与设置配置。"""
        prefs = getattr(self.window, "prefs", {})
        enabled = prefs.get("music_visualizer_enabled", True) if hasattr(prefs, "get") else True
        if enabled:
            if not self._timer.isActive():
                # 初始休眠采样 250ms，检测到音频播放后加速至 35ms
                self._timer.start(250)
        else:
            self._timer.stop()
            self._is_music_active = False
            self.overlay.hide()

    def reposition(self):
        """将音符悬浮窗定位在桌宠身旁/头顶侧上方。"""
        w = self.window
        if not hasattr(w, "x") or not hasattr(w, "y"):
            return

        # 若角色朝左，音符呈现在右肩上方；若朝右，呈现在左肩上方
        facing_left = getattr(w, "_facing_left", False)
        if facing_left:
            target_x = w.x() + int(w.width() * 0.55)
        else:
            target_x = w.x() + int(w.width() * 0.15)

        target_y = w.y() - 45
        self.overlay.move(target_x, target_y)

    def _on_tick(self):
        """定时采样音频峰值并驱动粒子动效。"""
        w = self.window
        if hasattr(w, "isVisible") and not w.isVisible():
            self.overlay.hide()
            return
        if getattr(w, "_quitting", False):
            self.overlay.hide()
            return

        peak = self.meter.get_peak()
        self._last_peak = peak

        # 峰值过滤与防抖状态机
        if peak > 0.015:
            self._playing_streak += 1
            self._silence_streak = 0
            if self._playing_streak >= 2 and not self._is_music_active:
                self._is_music_active = True
                # 加速采样以呈现丝滑律动
                self._timer.setInterval(35)
        else:
            self._silence_streak += 1
            if self._silence_streak >= 25:  # 连续约 1 秒静音
                self._playing_streak = 0
                if self._is_music_active:
                    self._is_music_active = False
                    # 静音降频节能
                    self._timer.setInterval(250)

        # 只有在显示或有残留粒子能量时才同步位置并重绘
        if self._is_music_active or self.overlay.isVisible():
            self.reposition()
            self.overlay.update_energy(peak, self._is_music_active)

    def get_current_music_info(self) -> dict:
        """获取当前正在播放的曲目及音量状态（供 AI 工具与气泡查询）。"""
        now = time.time()
        # 缓存 3 秒，避免高频 EnumWindows 扫描
        if now - self._last_track_check > 3.0:
            self._last_track_check = now
            self._cached_track = MusicTrackDetector.get_active_media_track()

        peak = self.meter.get_peak()
        has_audio = peak > 0.015 or self._is_music_active

        track = dict(self._cached_track)
        track["has_audio"] = has_audio
        track["peak_volume"] = round(peak, 2)
        return track

    def close(self):
        """安全释放定时器、图层与 COM 接口。"""
        self._timer.stop()
        if self.overlay:
            self.overlay.close()
        if self.meter:
            self.meter.release()
        PetMusicCoordinator._active_instance = None
