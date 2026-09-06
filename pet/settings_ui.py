"""统一设置对话框：语音 / 热键 / 通用。

语音：朗读回答（TTS）开关、静音、音量滑杆。
热键：聊天 / 翻译剪贴板 / OCR 截图 三个组合键的可视化改键（按当前角色保存，
     通过 owner.prefs["hotkeys_<角色>"] 覆盖 config.json 的默认值）。
通用：默认角色（下次启动生效）、考试倒计时徽章开关。

保存时复用 owner 上已有的 setter（_set_tts / _toggle_mute / _on_volume_slider /
_apply_hotkey_overrides / _refresh_exam_badge），保证与右键菜单行为一致。
"""

from PyQt5 import QtCore, QtGui, QtWidgets

from . import logging as petlog
from . import theme, tts, updater

# DIALOG_QSS 未覆盖的控件：页签、滑杆、组合键输入框——补上统一的 Terminal 风格。
_EXTRA_QSS = """
QTabWidget::pane { border: 1px solid %s; border-radius: 4px; background: %s; }
QTabBar::tab { background: transparent; color: %s; padding: 8px 18px;
               font-size: 18px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: %s; border-bottom: 2px solid %s; }
QTabBar::tab:hover { color: %s; }
QSlider::groove:horizontal { height: 4px; background: %s; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; margin: -5px 0; background: %s;
                             border-radius: 7px; }
QKeySequenceEdit { background: %s; color: %s; border: 1px solid %s;
                   border-radius: 4px; padding: 6px 8px;
                   selection-background-color: %s; font-family: %s; }
QKeySequenceEdit:focus { border: 1px solid %s; background: %s; }
""" % (
    theme.FLOAT_GRID, theme.DLG_BG,
    theme.FLOAT_TEXT_DIM, theme.FLOAT_ACCENT, theme.FLOAT_GOLD, theme.FLOAT_TEXT,
    theme.FLOAT_GRID, theme.FLOAT_GOLD,
    theme.DLG_FIELD, theme.FLOAT_TEXT, theme.FLOAT_GRID,
    theme.FLOAT_ACCENT, theme.MONO,
    theme.FLOAT_ACCENT, theme.DLG_FIELD_FOCUS,
)


def _spec_to_ks(spec):
    """'alt+a' -> QKeySequence('Alt+A')（无法识别的修饰键按普通键处理）。"""
    s = str(spec or "").strip()
    if not s:
        return QtGui.QKeySequence()
    mods, key = [], ""
    for p in s.split("+"):
        pl = p.strip().lower()
        if pl == "alt":
            mods.append("Alt")
        elif pl in ("ctrl", "control"):
            mods.append("Ctrl")
        elif pl == "shift":
            mods.append("Shift")
        elif pl in ("win", "super", "cmd", "meta"):
            mods.append("Meta")
        else:
            key = p.strip().upper()
    return QtGui.QKeySequence("+".join(mods + ([key] if key else [])))


def _ks_to_spec(ks):
    """QKeySequence -> 'alt+a'（可写回配置的小写格式）。"""
    s = ks.toString(QtGui.QKeySequence.PortableText)
    if not s:
        return ""
    mods = {"Alt": "alt", "Ctrl": "ctrl", "Shift": "shift", "Meta": "win"}
    parts = []
    for p in s.split("+"):
        pl = p.strip()
        parts.append(mods.get(pl, pl.lower()))
    return "+".join(parts)


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self.owner = owner
        self.setWindowTitle("设置")
        self.setModal(True)
        self.setMinimumWidth(540)
        self.setStyleSheet(theme.DIALOG_QSS + _EXTRA_QSS)
        self._orig_speed = float(self.owner.prefs.get("anim_speed", 1.0)) if hasattr(self.owner, "prefs") else 1.0
        self._build()
        self._load()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        head = QtWidgets.QLabel("SETTINGS", self)
        head.setObjectName("TerminalTitle")
        root.addWidget(head)
        sub = QtWidgets.QLabel("桌宠设置：语音 / 热键 / 通用。", self)
        sub.setObjectName("TerminalSubTitle")
        root.addWidget(sub)

        self.tabs = QtWidgets.QTabWidget(self)
        root.addWidget(self.tabs, 1)

        # ── 语音 ─────────────────────────────────────────────────────
        v = QtWidgets.QWidget(self)
        vl = QtWidgets.QVBoxLayout(v)
        vl.setSpacing(10)
        self.cb_tts = QtWidgets.QCheckBox("朗读回答（语音合成）", v)
        self.cb_mute = QtWidgets.QCheckBox("静音", v)
        self.cb_clone_autostop = QtWidgets.QCheckBox(
            "按钮启动的语音克隆 10 分钟未使用自动停止（默认关闭）", v)
        volrow = QtWidgets.QHBoxLayout()
        volrow.addWidget(QtWidgets.QLabel("音量", v))
        self.vol_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, v)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.valueChanged.connect(self._on_volume)
        self.vol_label = QtWidgets.QLabel("", v)
        volrow.addWidget(self.vol_slider, 1)
        volrow.addWidget(self.vol_label)
        vl.addWidget(self.cb_tts)
        vl.addWidget(self.cb_mute)
        vl.addWidget(self.cb_clone_autostop)
        vl.addLayout(volrow)
        vl.addStretch(1)
        self.tabs.addTab(v, "语音")

        # ── 热键 ─────────────────────────────────────────────────────
        h = QtWidgets.QWidget(self)
        hl = QtWidgets.QFormLayout(h)
        hl.setHorizontalSpacing(12)
        hl.setVerticalSpacing(12)
        self.hk_chat = QtWidgets.QKeySequenceEdit(h)
        self.hk_note = QtWidgets.QKeySequenceEdit(h)
        self.hk_translate = QtWidgets.QKeySequenceEdit(h)
        self.hk_ocr = QtWidgets.QKeySequenceEdit(h)
        hl.addRow("聊天", self.hk_chat)
        hl.addRow("灵感便签", self.hk_note)
        hl.addRow("翻译剪贴板", self.hk_translate)
        hl.addRow("OCR 截图", self.hk_ocr)
        note = QtWidgets.QLabel(
            "热键按当前角色保存；被其他程序占用的组合键会注册失败。", h)
        note.setStyleSheet("color:%s;font-size:13px;" % theme.FLOAT_TEXT_DIM)
        hl.addRow("", note)
        self.tabs.addTab(h, "热键")

        # ── 通用 ─────────────────────────────────────────────────────
        g = QtWidgets.QWidget(self)
        gl = QtWidgets.QFormLayout(g)
        gl.setHorizontalSpacing(12)
        gl.setVerticalSpacing(12)
        self.cb_char = QtWidgets.QComboBox(g)
        for c in self.owner._available_characters():
            self.cb_char.addItem(c.display_name, c.key)

        # 动作播放速度滑杆 (50% ~ 200%, 默认 100% / 1.0x)
        speed_row = QtWidgets.QHBoxLayout()
        self.speed_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, g)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setSingleStep(5)
        self.speed_slider.valueChanged.connect(self._on_speed_slider)
        self.speed_label = QtWidgets.QLabel("", g)
        self.speed_label.setFixedWidth(130)
        self.btn_reset_speed = QtWidgets.QPushButton("重置", g)
        self.btn_reset_speed.setFixedWidth(50)
        self.btn_reset_speed.clicked.connect(lambda: self.speed_slider.setValue(100))
        speed_row.addWidget(self.speed_slider, 1)
        speed_row.addWidget(self.speed_label)
        speed_row.addWidget(self.btn_reset_speed)

        self.cb_exam = QtWidgets.QCheckBox("显示考试倒计时常驻徽章", g)
        self.cb_wandering = QtWidgets.QCheckBox("允许空闲时在屏幕边缘漫游", g)
        self.cb_taskbar_dock = QtWidgets.QCheckBox("靠近任务栏时自动吸附并坐下", g)
        self.cb_sedentary = QtWidgets.QCheckBox("开启久坐关怀与健康提醒", g)
        self.combo_sedentary = QtWidgets.QComboBox(g)
        self.combo_sedentary.addItem("45 分钟", 45)
        self.combo_sedentary.addItem("60 分钟（推荐）", 60)
        self.combo_sedentary.addItem("90 分钟", 90)
        self.combo_sedentary.addItem("120 分钟", 120)
        sed_row = QtWidgets.QHBoxLayout()
        sed_row.addWidget(self.cb_sedentary)
        sed_row.addWidget(QtWidgets.QLabel("间隔", g))
        sed_row.addWidget(self.combo_sedentary)
        sed_row.addStretch(1)

        self.cb_check_updates = QtWidgets.QCheckBox("启动时检查更新", g)
        self.cb_knowledge_embed = QtWidgets.QCheckBox(
            "讲义检索：使用本地语义模型（需安装，未安装自动回退词频）", g)
        gl.addRow("默认角色", self.cb_char)
        gl.addRow("动作速度", speed_row)
        gl.addRow("", self.cb_exam)
        gl.addRow("", self.cb_wandering)
        gl.addRow("", self.cb_taskbar_dock)
        gl.addRow("", sed_row)

        profile_row = QtWidgets.QHBoxLayout()
        profile_lbl = QtWidgets.QLabel("记录专属称呼、偏好习惯与长程记忆", g)
        profile_lbl.setStyleSheet("color:%s;font-size:13px;" % theme.FLOAT_TEXT_DIM)
        self.btn_profile = QtWidgets.QPushButton("博士档案本…", g)
        self.btn_profile.clicked.connect(self._open_profile)
        profile_row.addWidget(profile_lbl)
        profile_row.addStretch(1)
        profile_row.addWidget(self.btn_profile)
        gl.addRow("长程记忆", profile_row)

        self.cb_weather_care = QtWidgets.QCheckBox("开启天气感知与雨雪关怀提醒", g)
        self.cb_night_dim = QtWidgets.QCheckBox("深夜自动护眼调光（23:00~06:00 调暗亮度）", g)
        self.edit_weather_city = QtWidgets.QLineEdit(g)
        self.edit_weather_city.setPlaceholderText("留空根据IP自动定位，或填城市如 北京/上海")
        weather_row = QtWidgets.QHBoxLayout()
        weather_row.addWidget(self.edit_weather_city)
        gl.addRow("", self.cb_weather_care)
        gl.addRow("", self.cb_night_dim)
        gl.addRow("天气城市", weather_row)

        self.cb_music_vis = QtWidgets.QCheckBox("开启听歌感知与音乐音符律动（随系统音乐跳动）", g)
        gl.addRow("", self.cb_music_vis)

        gl.addRow("", self.cb_check_updates)
        gl.addRow("", self.cb_knowledge_embed)
        self.ver_label = QtWidgets.QLabel(
            "当前版本 v%s" % updater.APP_VERSION, g)
        self.btn_check_updates = QtWidgets.QPushButton("检查更新…", g)
        self.btn_check_updates.clicked.connect(self._check_now)
        hrow = QtWidgets.QHBoxLayout()
        hrow.addWidget(self.ver_label)
        hrow.addStretch(1)
        hrow.addWidget(self.btn_check_updates)
        gl.addRow("版本", hrow)
        note2 = QtWidgets.QLabel("默认角色在下一次启动时生效。", g)
        note2.setStyleSheet("color:%s;font-size:13px;" % theme.FLOAT_TEXT_DIM)
        gl.addRow("", note2)
        self.tabs.addTab(g, "通用")

        # ── 按钮 ─────────────────────────────────────────────────────
        btns = QtWidgets.QHBoxLayout()
        btns.addStretch(1)
        self.btn_save = QtWidgets.QPushButton("保存", self)
        self.btn_cancel = QtWidgets.QPushButton("取消", self)
        self.btn_save.clicked.connect(self._save)
        self.btn_cancel.clicked.connect(self.reject)
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_cancel)
        root.addLayout(btns)

    def _load(self):
        o = self.owner
        self.cb_tts.setChecked(o._tts_on)
        self.cb_tts.setEnabled(o._tts_supported and tts.available())
        self.cb_mute.setChecked(not o.voice.enabled)
        self.cb_clone_autostop.setChecked(
            o.prefs.get("clone_manual_autostop", False))
        vol = int(round(o.voice.volume * 100))
        self.vol_slider.setValue(vol)
        self._on_volume(vol)
        ov = o.prefs.get("hotkeys_" + o.char.key, {}) or {}
        self.hk_chat.setKeySequence(_spec_to_ks(
            ov.get("chat") or o.char.cfg.get("hotkey", "alt+a")))
        self.hk_note.setKeySequence(_spec_to_ks(
            ov.get("note") or o.char.cfg.get("hotkey_note", "alt+n")))
        self.hk_translate.setKeySequence(_spec_to_ks(
            ov.get("translate") or o.char.cfg.get("hotkey_translate", "alt+t")))
        self.hk_ocr.setKeySequence(_spec_to_ks(
            ov.get("ocr") or o.char.cfg.get("hotkey_ocr", "alt+s")))
        idx = self.cb_char.findData(o.prefs.get("character", ""))
        if idx >= 0:
            self.cb_char.setCurrentIndex(idx)
        self.cb_exam.setChecked(o.prefs.get("exam_badge", True))
        self.cb_wandering.setChecked(o.prefs.get("wandering_enabled", True))
        self.cb_taskbar_dock.setChecked(o.prefs.get("taskbar_dock_enabled", True))
        self.cb_sedentary.setChecked(o.prefs.get("sedentary_enabled", True))
        sed_ival = int(o.prefs.get("sedentary_interval_min", 60))
        sed_idx = self.combo_sedentary.findData(sed_ival)
        if sed_idx >= 0:
            self.combo_sedentary.setCurrentIndex(sed_idx)
        self.cb_weather_care.setChecked(o.prefs.get("weather_care_enabled", True))
        self.cb_night_dim.setChecked(o.prefs.get("night_dim_enabled", True))
        self.edit_weather_city.setText(o.prefs.get("weather_city", ""))
        self.cb_music_vis.setChecked(o.prefs.get("music_visualizer_enabled", True))
        self.cb_check_updates.setChecked(o.prefs.get("check_updates", True))
        self.cb_knowledge_embed.setChecked(
            o.prefs.get("knowledge_embed", True))
        speed_pct = int(round(float(o.prefs.get("anim_speed", 1.0)) * 100))
        self.speed_slider.setValue(max(50, min(200, speed_pct)))
        self._on_speed_slider(self.speed_slider.value(), live_apply=False)

    def _check_now(self):
        """立即检查更新（结果以气泡/托盘提示显示）。"""
        self.owner._check_updates(silent=False)

    def _on_volume(self, value):
        self.vol_label.setText("%d%%" % value)

    def _on_speed_slider(self, value, live_apply=True):
        spd = value / 100.0
        text = "%.2fx" % spd
        if value == 100:
            text += "（原速）"
        elif value == 115:
            text += "（轻快·推荐）"
        elif value == 130:
            text += "（敏捷）"
        elif value == 150:
            text += "（极速）"
        elif value == 80:
            text += "（从容）"
        self.speed_label.setText(text)
        if live_apply and hasattr(self.owner, "set_anim_speed"):
            self.owner.set_anim_speed(spd)

    def reject(self):
        if hasattr(self.owner, "set_anim_speed") and hasattr(self, "_orig_speed"):
            self.owner.set_anim_speed(self._orig_speed)
        super().reject()

    def _save(self):
        from .hotkey import parse_hotkey
        o = self.owner
        try:
            # 校验热键格式（至少一个修饰键 + 一个键，否则全局注册会失败）
            specs = {"chat": _ks_to_spec(self.hk_chat.keySequence()),
                     "note": _ks_to_spec(self.hk_note.keySequence()),
                     "translate": _ks_to_spec(self.hk_translate.keySequence()),
                     "ocr": _ks_to_spec(self.hk_ocr.keySequence())}
            bad = [k for k, s in specs.items() if s and parse_hotkey(s) is None]
            if bad:
                QtWidgets.QMessageBox.warning(
                    self, "热键无效",
                    "以下热键格式无效（需要一个修饰键+一个按键）：\n%s"
                    % ", ".join(bad))
                return
            o._set_tts(self.cb_tts.isChecked())
            o._toggle_mute(self.cb_mute.isChecked())
            o._on_volume_slider(self.vol_slider.value())
            o.prefs.set("clone_manual_autostop",
                        self.cb_clone_autostop.isChecked())
            tts.set_manual_auto_stop(self.cb_clone_autostop.isChecked())
            # 热键只保存到 prefs；真正重注册由窗口在对话框关闭后执行
            # （见 PetWindow._open_settings），避免在模态事件循环里碰
            # RegisterHotKey/原生事件过滤器导致进程崩溃。
            o.prefs.set("hotkeys_" + o.char.key, specs)
            key = self.cb_char.currentData()
            if key:
                o.prefs.set("character", key)
            o.prefs.set("exam_badge", self.cb_exam.isChecked())
            o.prefs.set("wandering_enabled", self.cb_wandering.isChecked())
            o.prefs.set("taskbar_dock_enabled", self.cb_taskbar_dock.isChecked())
            if hasattr(o, "wander_coord") and not self.cb_wandering.isChecked():
                o.wander_coord.cancel_wandering()
            o.prefs.set("sedentary_enabled", self.cb_sedentary.isChecked())
            o.prefs.set("sedentary_interval_min", int(self.combo_sedentary.currentData()))
            if hasattr(o, "sedentary_coord"):
                o.sedentary_coord.reload_config()
            o.prefs.set("weather_care_enabled", self.cb_weather_care.isChecked())
            o.prefs.set("night_dim_enabled", self.cb_night_dim.isChecked())
            o.prefs.set("weather_city", self.edit_weather_city.text().strip())
            if hasattr(o, "weather_coord"):
                o.weather_coord.reload_config()
            o.prefs.set("music_visualizer_enabled", self.cb_music_vis.isChecked())
            if hasattr(o, "music_coord"):
                o.music_coord.reload_config()
            o.prefs.set("check_updates", self.cb_check_updates.isChecked())
            o.prefs.set("knowledge_embed", self.cb_knowledge_embed.isChecked())
            o._apply_knowledge_prefs()
            speed = self.speed_slider.value() / 100.0
            if hasattr(o, "set_anim_speed"):
                o.set_anim_speed(speed)
            o._refresh_exam_badge()
        except Exception:
            import traceback
            petlog.log("settings save 异常:\n%s" % traceback.format_exc())
            QtWidgets.QMessageBox.warning(
                self, "保存失败", "保存设置时出错，已记录到 pet.log。")
            return
        self.accept()

    def _open_profile(self):
        """打开博士档案本管理对话框。"""
        from .profile_ui import DoctorProfileDialog
        DoctorProfileDialog(self).exec_()
