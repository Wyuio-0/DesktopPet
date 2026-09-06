"""右键上下文菜单构建器：主菜单组装、子菜单懒加载与角色发现。"""

import glob
import os
import traceback

from PyQt5 import QtCore, QtWidgets

from . import theme, tts, logging as petlog
from .ai_settings import AiSettingsDialog
from .apps_ui import AppWhitelistDialog
from .character import Character
from .settings import characters_dirs


class PetContextMenuBuilder(QtCore.QObject):
    """负责桌面宠物右键菜单的构建、子菜单懒加载与相关弹窗触发。"""

    def __init__(self, window):
        parent = window if isinstance(window, QtCore.QObject) else None
        super().__init__(parent)
        self.window = window
        self._chars_cache = None
        self._chars_mtime = None

    def invalidate_characters_cache(self):
        """清除角色目录扫描缓存。"""
        self._chars_cache = None
        self._chars_mtime = None

    def available_characters(self):
        """获取所有可用角色列表（按目录 mtime 缓存，避免每次右键全量扫描磁盘）。"""
        dirs = characters_dirs()
        try:
            key = tuple(
                (d, os.path.getmtime(d)) if os.path.isdir(d) else (d, None)
                for d in dirs)
        except OSError:
            key = None
        if self._chars_cache is not None and self._chars_mtime == key:
            return self._chars_cache

        chars = []
        seen = set()
        for base in dirs:
            for cfg_path in sorted(
                    glob.glob(os.path.join(base, "*", "config.json"))):
                try:
                    ch = Character(os.path.dirname(cfg_path))
                except Exception:
                    continue
                k = os.path.normcase(ch.key)
                if k in seen:
                    continue
                seen.add(k)
                chars.append(ch)
        self._chars_cache = chars
        self._chars_mtime = key
        return chars

    def show_menu(self, pos):
        """构建并在指定物理位置弹出清晰优雅的右键主菜单。"""
        w = self.window
        m = QtWidgets.QMenu(w)
        m.setStyleSheet(theme.MENU_QSS)

        # 快捷键提示（仅当真实注册成功时展示）
        hint = ""
        hk = getattr(w, "hotkey", None)
        if hk and hk.active and hasattr(w, "_hotkey_spec"):
            hint = "（%s）" % w._hotkey_spec.title()

        note_hint = ""
        nhk = getattr(w, "_note_hotkey", None)
        if nhk and nhk.active and hasattr(w, "_note_hotkey_spec"):
            note_hint = "（%s）" % w._note_hotkey_spec.title()

        # ── 1. 日常互动 ──────────────────────────────────────────────
        m.addAction("和%s聊天…" % w.char.display_name + hint, w.open_chat)
        m.addAction("灵感便签…" + note_hint, w.toggle_notes)
        self.add_action_menu(m)
        m.addSeparator()

        # ── 2. 学业与效率工具 ────────────────────────────────────────
        self.add_schedule_menu(m)
        self.add_tasks_menu(m)
        self.add_focus_menu(m)
        self.add_trans_ocr_menu(m)
        m.addSeparator()

        # ── 3. 智能与角色 ────────────────────────────────────────────
        self.add_ai_menu(m)
        self.add_character_menu(m)
        self.add_audio_menu(m)
        m.addSeparator()

        # ── 4. 系统 ──────────────────────────────────────────────────
        m.addAction("设置…", self.open_settings)
        m.addAction("退出", w._quit)

        m.exec_(w.mapToGlobal(pos))

    # ── 子菜单装配 ───────────────────────────────────────────────────

    def add_action_menu(self, parent):
        """动作互动子菜单（打招呼、施放技能、坐下休息/站起身来、动作速度调节）。"""
        w = self.window
        sub = parent.addMenu("动作互动")
        sub.addAction("打招呼", lambda: w._act_voice("greet", "greet"))
        sub.addAction("施放技能", lambda: w._act_voice("skill_begin", "skill"))
        is_sitting = (
            getattr(w, "_cur_action", None) is not None
            and getattr(w._cur_action, "name", "") == "sit"
        )
        if is_sitting:
            sub.addAction("站起身来", lambda: w.play("idle"))
        else:
            sub.addAction("坐下休息", lambda: w._act_voice("sit", "sit"))

        sub.addSeparator()
        speed_sub = sub.addMenu("动作速度")
        cur_speed = float(w.prefs.get("anim_speed", 1.0)) if hasattr(w, "prefs") else 1.0
        speeds = [
            ("0.8x（从容慢速）", 0.8),
            ("1.0x（原速标准）", 1.0),
            ("1.15x（轻快流畅 · 推荐）", 1.15),
            ("1.3x（敏捷快速）", 1.3),
            ("1.5x（极速）", 1.5),
        ]
        for label, val in speeds:
            act = speed_sub.addAction(label, lambda v=val: w.set_anim_speed(v))
            act.setCheckable(True)
            if abs(cur_speed - val) < 0.05:
                act.setChecked(True)
        speed_sub.addSeparator()
        speed_sub.addAction("自定义速度…", self.open_settings)

    def add_character_menu(self, parent):
        """切换人物子菜单（aboutToShow 懒加载，防磁盘卡顿）。"""
        sub = parent.addMenu("切换人物")
        placeholder = sub.addAction("加载中…")
        placeholder.setEnabled(False)
        sub.aboutToShow.connect(lambda s=sub: self._populate_character_menu(s))

    def _populate_character_menu(self, sub):
        sub.clear()
        current = os.path.normcase(self.window.char.dir)
        chars = self.available_characters()
        if not chars:
            act = sub.addAction("未找到其他人物")
            act.setEnabled(False)
        for char in chars:
            act = sub.addAction(char.display_name)
            act.setCheckable(True)
            act.setChecked(os.path.normcase(char.dir) == current)
            act.triggered.connect(
                lambda checked=False, path=char.dir: self.window._switch_character(path))
        if chars:
            sub.addSeparator()
        sub.addAction("添加新角色…", self.add_character_entry)

    def add_character_entry(self):
        """GUI 入口：选素材文件夹 → 自动生成新角色。"""
        w = self.window
        src = QtWidgets.QFileDialog.getExistingDirectory(
            w, "选择角色素材文件夹（内含动画 webm）", os.path.expanduser("~"))
        if not src:
            return
        key, ok = QtWidgets.QInputDialog.getText(
            w, "角色标识", "角色 key（英文小写，如 amiya2）：")
        if not ok or not key.strip():
            return
        name, ok = QtWidgets.QInputDialog.getText(
            w, "显示名称", "显示名称（如 能天使）：", text=key.strip())
        if not ok:
            return
        try:
            from .add_character import add_character
            result = add_character(key.strip(), name.strip(), src)
        except ValueError as e:
            w.raise_()
            w.bubble.say(str(e), w._body_rect())
            return
        except Exception as e:
            w.raise_()
            w.bubble.say("添加失败：%s" % type(e).__name__, w._body_rect())
            return

        self.invalidate_characters_cache()
        voice = "，语音 %d 条" % result["voice_count"] if result["voice_count"] else ""
        w._announce("已添加角色「%s」，动作：%s%s。右键菜单即可切换。"
                    % (result["display_name"], "/".join(result["actions"]),
                       voice), use_tts=False)

    def add_schedule_menu(self, parent):
        """课程表子菜单：今日课程 / 下一节课 / 本周课表 / 导入。"""
        fm = getattr(self.window, "focus_mgr", None)
        sub = parent.addMenu("课程表")
        if fm:
            sub.addAction("今天课程", fm.show_today)
            sub.addAction("下一节课", fm.show_next)
            sub.addAction("本周课表", fm.show_week)
            sub.addSeparator()
            sub.addAction("导入课表…", fm.import_schedule)
        else:
            sub.addAction("今天课程", self.window._show_today)
            sub.addAction("下一节课", self.window._show_next)
            sub.addAction("本周课表", self.window._show_week)
            sub.addSeparator()
            sub.addAction("导入课表…", self.window._import_schedule)

    def add_tasks_menu(self, parent):
        """待办与考试子菜单。"""
        fm = getattr(self.window, "focus_mgr", None)
        sub = parent.addMenu("待办与考试")
        if fm:
            sub.addAction("添加作业 DDL…", lambda: fm.add_task("homework"))
            sub.addAction("添加考试…", lambda: fm.add_task("exam"))
            sub.addSeparator()
            sub.addAction("即将到期", fm.show_tasks)
            sub.addAction("考试倒计时", fm.show_exam_countdown)
            sub.addAction("管理待办…", fm.manage_tasks)
            badge_act = sub.addAction("考试倒计时徽章")
            badge_act.setCheckable(True)
            badge_act.setChecked(self.window.prefs.get("exam_badge", True))
            badge_act.toggled.connect(fm.toggle_exam_badge)
        else:
            sub.addAction("添加作业 DDL…", lambda: self.window._add_task("homework"))
            sub.addAction("添加考试…", lambda: self.window._add_task("exam"))
            sub.addSeparator()
            sub.addAction("即将到期", self.window._show_tasks)
            sub.addAction("考试倒计时", self.window._show_exam_countdown)
            sub.addAction("管理待办…", self.window._manage_tasks)
            badge_act = sub.addAction("考试倒计时徽章")
            badge_act.setCheckable(True)
            badge_act.setChecked(self.window.prefs.get("exam_badge", True))
            badge_act.toggled.connect(self.window._toggle_exam_badge)

    def add_trans_ocr_menu(self, parent):
        """翻译与识图子菜单（截图翻译、剪贴板翻译、截图总结、知识库）。"""
        w = self.window
        sub = parent.addMenu("翻译与识图")

        ocr_hint = ""
        ohk = getattr(w, "_ocr_hotkey", None)
        if ohk and ohk.active and hasattr(w, "_ocr_hotkey_spec"):
            ocr_hint = "（%s）" % w._ocr_hotkey_spec.title()
        else:
            ocr_hint = "（Alt+S）"
        sub.addAction("截图翻译" + ocr_hint, lambda: w._ocr_flow("translate"))

        trans_hint = ""
        thk = getattr(w, "_translate_hotkey", None)
        if thk and thk.active and hasattr(w, "_translate_hotkey_spec"):
            trans_hint = "（%s）" % w._translate_hotkey_spec.title()
        else:
            trans_hint = "（Alt+T）"
        sub.addAction("翻译剪贴板" + trans_hint, w._translate_clipboard)
        sub.addAction("截图总结", lambda: w._ocr_flow("summarize"))
        sub.addSeparator()
        sub.addAction("重新加载讲义知识库", self.reload_knowledge)

    add_ocr_menu = add_trans_ocr_menu

    def add_focus_menu(self, parent):
        """专注小工具子菜单。"""
        fm = getattr(self.window, "focus_mgr", None)
        sub = parent.addMenu("专注小工具")
        if fm:
            sub.addAction("提醒事项…", fm.reminder_dialog)
            sub.addAction("倒计时…", fm.countdown_dialog)
            sub.addAction("番茄钟…", fm.pomodoro_dialog)
            if fm.is_focus_active():
                sub.addSeparator()
                running = "番茄钟" if fm.has_active_pomodoro() else "倒计时"
                sub.addAction("停止%s" % running, fm.stop_focus)
        else:
            sub.addAction("提醒事项…", self.window._reminder_dialog)
            sub.addAction("倒计时…", self.window._countdown_dialog)
            sub.addAction("番茄钟…", self.window._pomodoro_dialog)
            if getattr(self.window, "_pomo", None) or (
                    hasattr(self.window, "_cd_timer") and self.window._cd_timer.isActive()):
                sub.addSeparator()
                running = "番茄钟" if getattr(self.window, "_pomo", None) else "倒计时"
                sub.addAction("停止%s" % running, self.window._stop_focus)

    def add_ai_menu(self, parent):
        """AI 与档案子菜单（博士档案本、模型配置、应用白名单、会话重置、在线状态）。"""
        w = self.window
        sub = parent.addMenu("AI 与档案")
        sub.addAction("博士档案本…", self.open_doctor_profile)
        sub.addAction("忘记当前对话", self.forget_chat)
        sub.addSeparator()
        sub.addAction("模型配置…", self.open_ai_settings)
        sub.addAction("应用白名单…", self.open_app_whitelist)
        sub.addSeparator()
        if not w.brain.online:
            status = "AI 离线（用内置台词）"
        elif w.brain.cfg.get("allow_actions", True):
            status = "AI 在线 · 可操作电脑"
        else:
            status = "AI 在线"
        act = sub.addAction(status)
        act.setEnabled(False)

    def add_audio_menu(self, parent):
        """声音与克隆子菜单：静音复选框、音量滑动条、TTS 开关、语音克隆。"""
        w = self.window
        sub = parent.addMenu("声音与克隆")
        mute = sub.addAction("静音")
        mute.setCheckable(True)
        mute.setChecked(not w.voice.enabled)
        mute.toggled.connect(w._toggle_mute)
        sub.addSeparator()

        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, sub)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(int(round(w.voice.volume * 100)))
        slider.setFixedWidth(240)
        slider.valueChanged.connect(w._on_volume_slider)
        wa = QtWidgets.QWidgetAction(sub)
        wa.setDefaultWidget(slider)
        sub.addAction(wa)

        sub.addSeparator()
        tts_act = sub.addAction("朗读回答（语音合成）")
        tts_act.setCheckable(True)
        tts_supported = getattr(w, "_tts_supported", True)
        tts_on = getattr(w, "_tts_on", False)
        tts_act.setEnabled(tts_supported and tts.available())
        tts_act.setChecked(tts_on)
        tts_act.toggled.connect(w._set_tts)

        if getattr(w, "_use_clone", False):
            sub.addSeparator()
            state = tts.clone_state()
            if state == "running":
                sub.addAction("停止语音克隆服务（释放显存）", w._stop_clone)
            elif state == "starting":
                loading = sub.addAction("语音克隆服务加载中…")
                loading.setEnabled(False)
            else:
                sub.addAction("启动语音克隆服务（AI 声线）", w._start_clone)

    add_volume_menu = add_audio_menu

    def add_clone_menu(self, parent):
        pass

    # ── 对话框与业务动作 ─────────────────────────────────────────────

    def open_ai_settings(self):
        """打开模型配置对话框。"""
        w = self.window
        dlg = AiSettingsDialog(w.char.dir, w.brain.cfg, w, w.char.display_name)
        dlg.saved.connect(self.apply_ai_settings)
        dlg.exec_()

    def open_app_whitelist(self):
        """打开应用白名单管理对话框。"""
        AppWhitelistDialog(self.window).exec_()

    def open_settings(self):
        """打开统一设置对话框（语音 / 热键 / 通用）。"""
        from .settings_ui import SettingsDialog
        SettingsDialog(self.window).exec_()
        QtCore.QTimer.singleShot(0, self.window._apply_hotkey_overrides)

    def open_doctor_profile(self):
        """打开博士档案本与长程记忆管理对话框。"""
        from .profile_ui import DoctorProfileDialog
        DoctorProfileDialog(self.window).exec_()

    def apply_ai_settings(self, cfg):
        """应用新保存的模型配置。"""
        w = self.window
        w._apply_ai_settings(cfg)

    def forget_chat(self):
        """清除当前对话记忆。"""
        w = self.window
        w.brain.clear_history()
        w.trans_popup.hide()
        w.bubble.say("好的博士，我们重新开始吧。", w._body_rect())

    def reload_knowledge(self):
        """重新扫描并加载讲义知识库目录。"""
        w = self.window
        kb = getattr(w.brain, "knowledge", None)
        if kb is None:
            w._attach_brain_services()
            kb = w.brain.knowledge
        kb.reload()
        if len(kb):
            w.bubble.say("知识库已重新加载：%d 个片段。" % len(kb), w._body_rect())
        else:
            w.bubble.say("知识库为空。请把讲义 .txt / .md 放进\n%s"
                        % kb.folder, w._body_rect())
