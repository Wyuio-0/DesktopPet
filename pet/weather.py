"""本地天气感知与昼夜环境联动协调器。

职责：
1. 异步获取实时天气：通过免 Key 的轻量开源接口 (wttr.in) 获取本地或指定城市的
   气温、天气状况（晴/阴/雨/雪等）、风速与湿度，全程工作在后台 QThread，零阻塞主界面；
2. 恶劣/特殊天气关怀提醒：当检测到下雨、下雪或气温骤降时，桌宠主动播放动作、
   弹出身旁对话气泡并语音提醒博士带伞或添衣（内置 4 小时防高频打扰机制）；
3. 昼夜环境调光（护眼模式）：夜间（23:00~06:00）自动对桌宠画面进行平滑亮度衰减
   （_dim_factor = 0.75），保持夜间屏幕舒适不刺眼，且透明度通道与穿透掩码完全无损；
4. 提供大模型天气查询接口 (get_weather)。
"""

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime
from PyQt5 import QtCore

# 常见天气英文与中文对照表（wttr.in 英文关键词 -> 中文描述）
_WEATHER_ZH_MAP = {
    "sunny": "晴朗",
    "clear": "晴",
    "partly cloudy": "多云",
    "cloudy": "阴天",
    "overcast": "阴天",
    "mist": "薄雾",
    "fog": "大雾",
    "patchy rain possible": "局部阵雨",
    "patchy light drizzle": "零星细雨",
    "light drizzle": "毛毛细雨",
    "freezing drizzle": "冻雨",
    "patchy light rain": "小阵雨",
    "light rain": "小雨",
    "moderate rain at times": "时有中雨",
    "moderate rain": "中雨",
    "heavy rain at times": "时有大雨",
    "heavy rain": "大雨",
    "torrential rain shower": "暴雨",
    "light shower": "小阵雨",
    "thundery outbreaks possible": "雷阵雨可能",
    "patchy light rain with thunder": "雷阵雨",
    "moderate or heavy rain with thunder": "雷暴大雨",
    "patchy light snow": "小阵雪",
    "light snow": "小雪",
    "moderate snow": "中雪",
    "heavy snow": "大雪",
    "blizzard": "暴风雪",
}


def parse_weather_desc(desc_raw: str, lang_zh: str = "") -> str:
    """根据 wttr.in 返回的描述转换或匹配中文天气。"""
    if lang_zh and lang_zh.strip():
        return lang_zh.strip()
    raw = (desc_raw or "").strip().lower()
    for k, v in _WEATHER_ZH_MAP.items():
        if k in raw:
            return v
    return desc_raw or "晴"


def fetch_weather_sync(city: str = "", timeout: int = 6) -> dict:
    """同步从 wttr.in 拉取天气数据（请在子线程调用），返回标准字典或 None。"""
    city_param = urllib.parse.quote(city.strip()) if city and city.strip() else ""
    url = f"https://wttr.in/{city_param}?format=j1"
    req = urllib.request.Request(url, headers={
        "User-Agent": "curl/7.68.0",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        curr = data.get("current_condition", [{}])[0]
        nearest = data.get("nearest_area", [{}])[0]
        area_name = nearest.get("areaName", [{}])[0].get("value", "") or city or "本地"

        temp_c = int(curr.get("temp_C", 20))
        humidity = int(curr.get("humidity", 50))
        wind_kmph = int(curr.get("windspeedKmph", 10))

        raw_desc = curr.get("weatherDesc", [{}])[0].get("value", "Clear")
        lang_zh = ""
        zh_list = curr.get("lang_zh")
        if isinstance(zh_list, list) and zh_list:
            lang_zh = zh_list[0].get("value", "")

        desc = parse_weather_desc(raw_desc, lang_zh)
        return {
            "city": area_name,
            "temp_c": temp_c,
            "desc": desc,
            "raw_desc": raw_desc,
            "humidity": humidity,
            "wind_kmph": wind_kmph,
            "time": time.time(),
        }
    except Exception:
        return None


class WeatherWorker(QtCore.QThread):
    """后台异步拉取天气工作线程。"""

    weather_ready = QtCore.pyqtSignal(object)  # 发送 dict 或 None

    def __init__(self, city="", parent=None):
        super().__init__(parent)
        self.city = city

    def run(self):
        result = fetch_weather_sync(self.city)
        self.weather_ready.emit(result)


class PetWeatherCoordinator(QtCore.QObject):
    """桌面宠物天气感知与昼夜联动协调器。"""

    # 相同天气关怀提醒的最短间隔：4 小时（防打扰缓冲）
    CARE_SNOOZE_SEC = 4 * 3600

    def __init__(self, window):
        parent = window if isinstance(window, QtCore.QObject) else None
        super().__init__(parent)
        self.window = window

        self._current_weather = None  # 最近一次成功拉取的天气信息
        self._last_care_time = 0      # 上次触发关怀提醒的时刻
        self._last_care_kind = ""     # 上次提醒类型：rain / snow / cold
        self._worker = None

        # 1. 周期天气更新定时器（每 1 小时检查一次）
        self._weather_timer = QtCore.QTimer(self)
        self._weather_timer.setInterval(3600 * 1000)
        self._weather_timer.timeout.connect(self._on_check_weather)

        # 2. 昼夜检测定时器（每 30 秒检查一次本地时间，调整降光系数）
        self._daynight_timer = QtCore.QTimer(self)
        self._daynight_timer.setInterval(30 * 1000)
        self._daynight_timer.timeout.connect(self._check_day_night)

        # 启动定时器：昼夜检测立即触发一次，天气首查延时 8 秒执行（避免挤占冷启动）
        self._daynight_timer.start()
        self._check_day_night()
        QtCore.QTimer.singleShot(8000, self._on_check_weather)
        self._weather_timer.start()

    def close(self):
        """释放协调器定时器与正在执行的后台线程。"""
        self._weather_timer.stop()
        self._daynight_timer.stop()
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(1000)

    def reload_config(self):
        """配置更新时刷新设置。"""
        self._check_day_night()
        self._on_check_weather()

    # ------------------------------------------------------------------ #
    # 昼夜环境调光 (Nighttime Dimming)                                    #
    # ------------------------------------------------------------------ #

    def _check_day_night(self):
        """检查当前时间，在 23:00~06:00 期间平滑微降桌宠亮度。"""
        w = self.window
        if not hasattr(w, "prefs"):
            return
        enabled = w.prefs.get("night_dim_enabled", True)
        now_hour = datetime.now().hour
        is_night = (now_hour >= 23 or now_hour < 6)

        new_factor = 0.75 if (enabled and is_night) else 1.0
        if getattr(w, "_dim_factor", 1.0) != new_factor:
            w._dim_factor = new_factor

    # ------------------------------------------------------------------ #
    # 天气感知与关怀逻辑                                                  #
    # ------------------------------------------------------------------ #

    def _on_check_weather(self):
        """发起后台天气更新请求。"""
        w = self.window
        if not hasattr(w, "prefs") or getattr(w, "_quitting", False):
            return
        if not w.prefs.get("weather_care_enabled", True):
            return
        if self._worker and self._worker.isRunning():
            return

        city = w.prefs.get("weather_city", "") or ""
        self._worker = WeatherWorker(city, self)
        self._worker.weather_ready.connect(self._on_weather_received)
        self._worker.start()

    def _on_weather_received(self, info):
        """后台天气更新完成回调。"""
        if not info or not isinstance(info, dict):
            return
        self._current_weather = info
        self._evaluate_ambient_care(info)

    def _evaluate_ambient_care(self, info):
        """根据天气状况判断是否需要主动弹出关怀提示。"""
        w = self.window
        if not hasattr(w, "prefs") or not w.prefs.get("weather_care_enabled", True):
            return
        if getattr(w, "_quitting", False) or not w.isVisible():
            return

        desc = info.get("desc", "")
        temp_c = info.get("temp_c", 20)
        now = time.time()

        care_kind = ""
        msg = ""

        # 判定优先级：雨天 > 雪天 > 低温
        if "雨" in desc or "雷" in desc:
            care_kind = "rain"
            msg = "博士，外面正在下雨，出门记得带好雨伞，注意脚下安全哦。"
        elif "雪" in desc:
            care_kind = "snow"
            msg = "博士，外面下雪了，天气寒冷，出门一定要多穿一件厚外套。"
        elif temp_c <= 5:
            care_kind = "cold"
            msg = f"博士，今天气温比较低（当前 {temp_c}°C），请注意保暖，别着凉了。"

        if not care_kind or not msg:
            return

        # 4 小时冷却保护：同一类型关怀在 4 小时内不重复骚扰
        if care_kind == self._last_care_kind and (now - self._last_care_time < self.CARE_SNOOZE_SEC):
            return

        self._last_care_time = now
        self._last_care_kind = care_kind

        # 触发桌宠关怀
        if hasattr(w, "_announce"):
            w._announce(msg, use_tts=True)

    def get_weather_summary(self, city=None) -> str:
        """供 actions.get_weather 调用：获取格式化的天气摘要。"""
        # 若指定了外部城市，或者尚未获取过天气数据，则现场同步请求（短超时）
        specified_city = (city or "").strip()
        if specified_city or self._current_weather is None:
            res = fetch_weather_sync(specified_city, timeout=4)
            if res:
                self._current_weather = res
            elif self._current_weather is None:
                return "抱歉博士，暂时没能获取到当前天气信息，请稍后再试。"

        info = self._current_weather
        city_name = specified_city or info.get("city", "本地")
        desc = info.get("desc", "晴")
        temp = info.get("temp_c", "--")
        humidity = info.get("humidity", "--")
        wind = info.get("wind_kmph", "--")

        tip = "天气晴朗，适宜出行。"
        if "雨" in desc or "雷" in desc:
            tip = "外面有雨，出门记得带伞。"
        elif "雪" in desc:
            tip = "外面有雪，注意保暖防滑。"
        elif isinstance(temp, int) and temp <= 5:
            tip = "天气寒冷，多加件衣服。"
        elif isinstance(temp, int) and temp >= 32:
            tip = "天气炎热，注意防暑防晒与补水。"

        return f"【{city_name}天气】状况：{desc}，气温：{temp}°C，湿度：{humidity}%，风速：{wind}km/h。{tip}"
