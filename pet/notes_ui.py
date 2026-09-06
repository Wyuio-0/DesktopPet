"""桌面灵感便签图形界面（StickyNoteWindow）。

半透明极简黑金界面、无边框、支持任意拖拽移动与右下角缩放、
防抖毫秒级实时自动存盘、支持多便签快速切换，并集成了 AI 待办提取与笔记润色。
"""

from datetime import datetime

from PyQt5 import QtCore, QtGui, QtWidgets

from . import theme
from .notes import get_notes_manager


class _TitleBar(QtWidgets.QWidget):
    """自定义无边框窗口标题栏，支持鼠标拖拽窗口移动。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.window = parent
        self._drag_pos = None
        self.setFixedHeight(38)
        self.setStyleSheet(
            "background: %s; border-bottom: 1px solid %s;"
            % (theme.FLOAT_PANEL, theme.FLOAT_GRID)
        )

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.window.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and e.buttons() & QtCore.Qt.LeftButton:
            self.window.move(e.globalPos() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        if self.window and hasattr(self.window, "_save_geometry"):
            self.window._save_geometry()

    def mouseDoubleClickEvent(self, e):
        """双击标题栏居中重置便签位置。"""
        if e.button() == QtCore.Qt.LeftButton and self.window:
            self.window.center_on_screen()

    def contextMenuEvent(self, e):
        """标题栏右键菜单：方便用户随时居中或重新停靠。"""
        if not self.window:
            return
        m = QtWidgets.QMenu(self)
        m.setStyleSheet(theme.MENU_QSS)
        m.addAction("居中显示（屏幕中心）", self.window.center_on_screen)
        m.addAction("停靠至桌宠身旁", self.window.dock_near_pet)
        m.addSeparator()
        pin_txt = "取消置顶" if self.window.is_pinned else "置顶便签"
        m.addAction(pin_txt, self.window._toggle_pin)
        m.addAction("新建便签", self.window._on_new_note)
        m.addSeparator()
        m.addAction("关闭便签（Alt+N）", self.window.hide)
        m.exec_(e.globalPos())


class StickyNoteWindow(QtWidgets.QWidget):
    """悬浮便签窗口主类。"""

    def __init__(self, owner_window=None):
        super().__init__(None)  # Top-level window
        self.owner = owner_window
        self.mgr = get_notes_manager()
        self.is_pinned = True
        self._save_timer = QtCore.QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._do_auto_save)

        self._ai_worker = None

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, False)
        self.resize(360, 420)
        self.setMinimumSize(260, 240)

        self._build_ui()
        self._load_active_note()
        self._restore_geometry()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 外层容器卡片（半透明黑金风格）
        self.container = QtWidgets.QFrame(self)
        self.container.setObjectName("NoteContainer")
        self.container.setStyleSheet("""
            #NoteContainer {
                background: %s;
                border: 1px solid %s;
                border-left: 4px solid %s;
                border-radius: 6px;
            }
        """ % (theme.FLOAT_PANEL, theme.FLOAT_GRID, theme.FLOAT_GOLD))

        card_layout = QtWidgets.QVBoxLayout(self.container)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # ── 1. 标题栏 ─────────────────────────────────────────────
        self.title_bar = _TitleBar(self)
        tb_layout = QtWidgets.QHBoxLayout(self.title_bar)
        tb_layout.setContentsMargins(10, 4, 8, 4)
        tb_layout.setSpacing(6)

        icon_lbl = QtWidgets.QLabel("📝", self.title_bar)
        icon_lbl.setStyleSheet("font-size: 14px;")
        tb_layout.addWidget(icon_lbl)

        # 便签下拉切换器
        self.combo_notes = QtWidgets.QComboBox(self.title_bar)
        self.combo_notes.setFixedHeight(26)
        self.combo_notes.setStyleSheet("""
            QComboBox {
                background: %s;
                color: %s;
                border: 1px solid %s;
                border-radius: 4px;
                padding: 2px 8px;
                font-family: %s;
                font-size: 12px;
                font-weight: 600;
                min-width: 110px;
            }
            QComboBox::drop-down { border: none; width: 16px; }
            QComboBox QAbstractItemView {
                background: %s;
                color: %s;
                selection-background-color: %s;
                border: 1px solid %s;
            }
        """ % (
            theme.FLOAT_FIELD, theme.FLOAT_TEXT, theme.FLOAT_GRID, theme.FONT,
            theme.FLOAT_SOLID, theme.FLOAT_TEXT, theme.FLOAT_SELECT_BG, theme.FLOAT_GRID
        ))
        self.combo_notes.currentIndexChanged.connect(self._on_note_selected)
        tb_layout.addWidget(self.combo_notes, 1)

        btn_style = """
            QPushButton {
                background: transparent;
                color: %s;
                border: none;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 13px;
                font-family: %s;
            }
            QPushButton:hover {
                background: %s;
                color: %s;
            }
        """ % (theme.FLOAT_TEXT_DIM, theme.FONT, theme.FLOAT_SELECT_BG, theme.FLOAT_TEXT)

        # ➕ 新建
        self.btn_new = QtWidgets.QPushButton("➕", self.title_bar)
        self.btn_new.setToolTip("新建空白便签")
        self.btn_new.setStyleSheet(btn_style)
        self.btn_new.clicked.connect(self._on_new_note)
        tb_layout.addWidget(self.btn_new)

        # 🤖 AI 助手
        self.btn_ai = QtWidgets.QPushButton("🤖", self.title_bar)
        self.btn_ai.setToolTip("阿米娅便签助手（提取待办 / 润色整理）")
        self.btn_ai.setStyleSheet(btn_style)
        self.btn_ai.clicked.connect(self._show_ai_menu)
        tb_layout.addWidget(self.btn_ai)

        # 📌 置顶
        self.btn_pin = QtWidgets.QPushButton("📌", self.title_bar)
        self.btn_pin.setToolTip("切换置顶状态")
        self.btn_pin.setStyleSheet(
            btn_style + "QPushButton { color: %s; }" % theme.FLOAT_GOLD
        )
        self.btn_pin.clicked.connect(self._toggle_pin)
        tb_layout.addWidget(self.btn_pin)

        # 🗑️ 删除
        self.btn_del = QtWidgets.QPushButton("🗑️", self.title_bar)
        self.btn_del.setToolTip("删除当前便签")
        self.btn_del.setStyleSheet(btn_style)
        self.btn_del.clicked.connect(self._on_delete_note)
        tb_layout.addWidget(self.btn_del)

        # ✕ 关闭
        self.btn_close = QtWidgets.QPushButton("✕", self.title_bar)
        self.btn_close.setToolTip("关闭（Alt+N 可再次唤出）")
        self.btn_close.setStyleSheet(btn_style)
        self.btn_close.clicked.connect(self.hide)
        tb_layout.addWidget(self.btn_close)

        card_layout.addWidget(self.title_bar)

        # ── 2. 便签正文编辑区 ─────────────────────────────────────
        self.editor = QtWidgets.QTextEdit(self.container)
        self.editor.setPlaceholderText("随时在此记录灵感、待办清单或临时文本...\n（输入即自动保存）")
        self.editor.setStyleSheet("""
            QTextEdit {
                background: transparent;
                color: %s;
                border: none;
                padding: 10px 12px;
                font-family: %s;
                font-size: 14px;
                line-height: 1.5;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background: %s;
                border-radius: 3px;
                min-height: 20px;
            }
        """ % (theme.FLOAT_TEXT, theme.FONT, theme.FLOAT_GRID))
        self.editor.textChanged.connect(self._on_editor_changed)
        card_layout.addWidget(self.editor, 1)

        # ── 3. 底部状态栏 ─────────────────────────────────────────
        status_bar = QtWidgets.QWidget(self.container)
        status_bar.setFixedHeight(24)
        status_bar.setStyleSheet(
            "background: %s; border-top: 1px solid %s;"
            % (theme.FLOAT_FIELD, theme.FLOAT_GRID)
        )
        sb_layout = QtWidgets.QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(10, 0, 4, 0)
        sb_layout.setSpacing(6)

        self.lbl_char_count = QtWidgets.QLabel("0 字", status_bar)
        self.lbl_char_count.setStyleSheet(
            "color: %s; font-size: 11px; font-family: %s;"
            % (theme.FLOAT_TEXT_DIM, theme.FONT)
        )
        sb_layout.addWidget(self.lbl_char_count)

        sb_layout.addStretch(1)

        self.lbl_saved = QtWidgets.QLabel("已自动保存", status_bar)
        self.lbl_saved.setStyleSheet(
            "color: %s; font-size: 11px; font-family: %s;"
            % (theme.FLOAT_TEXT_DIM, theme.FONT)
        )
        sb_layout.addWidget(self.lbl_saved)

        # 右下角自由缩放手柄
        grip = QtWidgets.QSizeGrip(status_bar)
        grip.setFixedSize(14, 14)
        sb_layout.addWidget(grip)

        card_layout.addWidget(status_bar)
        root.addWidget(self.container)

    def _refresh_combo(self):
        """刷新便签下拉选择列表。"""
        self.combo_notes.blockSignals(True)
        self.combo_notes.clear()
        for n in self.mgr.list_notes():
            title_disp = ("📌 " if n.pinned else "") + (n.title or "空白便签")
            self.combo_notes.addItem(title_disp, n.id)
            if n.id == self.mgr.active_id:
                self.combo_notes.setCurrentIndex(self.combo_notes.count() - 1)
        self.combo_notes.blockSignals(False)

    def _load_active_note(self):
        """加载当前活跃便签内容到编辑器。"""
        note = self.mgr.get_active_note()
        self._refresh_combo()
        self.editor.blockSignals(True)
        self.editor.setPlainText(note.content)
        self.editor.blockSignals(False)
        self._update_status(saved=True)

    def _on_note_selected(self, index):
        if index < 0:
            return
        note_id = self.combo_notes.itemData(index)
        if note_id and note_id != self.mgr.active_id:
            # 切换前先确保当前便签已保存
            self._do_auto_save()
            self.mgr.set_active_id(note_id)
            self._load_active_note()

    def _on_editor_changed(self):
        """用户正在键入：防抖 400ms 自动存盘，并更新字数统计。"""
        self._update_status(saved=False)
        self._save_timer.start()

    def _do_auto_save(self):
        """执行自动持久化。"""
        content = self.editor.toPlainText()
        self.mgr.update_note(self.mgr.active_id, content=content)
        self._refresh_combo()
        self._update_status(saved=True)

    def _update_status(self, saved: bool):
        cnt = len(self.editor.toPlainText())
        self.lbl_char_count.setText(f"{cnt} 字")
        if saved:
            now_time = datetime.now().strftime("%H:%M")
            self.lbl_saved.setText(f"已保存 {now_time}")
            self.lbl_saved.setStyleSheet("color: %s; font-size: 11px;" % theme.FLOAT_TEXT_DIM)
        else:
            self.lbl_saved.setText("保存中…")
            self.lbl_saved.setStyleSheet("color: %s; font-size: 11px;" % theme.FLOAT_GOLD)

    def _on_new_note(self):
        self._do_auto_save()
        new_note = self.mgr.create_note(title="新建便签", content="")
        self._load_active_note()
        self.editor.setFocus()

    def _on_delete_note(self):
        cur_note = self.mgr.get_active_note()
        if len(self.mgr.list_notes()) <= 1 and not cur_note.content.strip():
            return
        reply = QtWidgets.QMessageBox.question(
            self,
            "删除便签",
            f"确定要删除便签「{cur_note.title}」吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.mgr.delete_note(cur_note.id)
            self._load_active_note()

    def _toggle_pin(self):
        self.is_pinned = not self.is_pinned
        note = self.mgr.get_active_note()
        self.mgr.update_note(note.id, pinned=self.is_pinned)
        self._refresh_combo()

        flags = self.windowFlags()
        if self.is_pinned:
            flags |= QtCore.Qt.WindowStaysOnTopHint
            self.btn_pin.setStyleSheet("QPushButton { color: %s; border: none; font-size: 13px; }" % theme.FLOAT_GOLD)
        else:
            flags &= ~QtCore.Qt.WindowStaysOnTopHint
            self.btn_pin.setStyleSheet("QPushButton { color: %s; border: none; font-size: 13px; }" % theme.FLOAT_TEXT_DIM)
        self.setWindowFlags(flags)
        self.show()

    def _show_ai_menu(self):
        """弹出阿米娅 AI 便签助手菜单。"""
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: %s;
                color: %s;
                border: 1px solid %s;
                border-radius: 6px;
                padding: 4px;
                font-family: %s;
            }
            QMenu::item:selected {
                background: %s;
                color: %s;
            }
        """ % (
            theme.FLOAT_SOLID, theme.FLOAT_TEXT, theme.FLOAT_GRID, theme.FONT,
            theme.FLOAT_SELECT_BG, theme.FLOAT_TEXT
        ))
        act_task = menu.addAction("⚡ 提取待办任务加入日程…")
        act_polish = menu.addAction("✍️ 让阿米娅润色整理笔记…")

        pt = self.btn_ai.mapToGlobal(QtCore.QPoint(0, self.btn_ai.height()))
        selected = menu.exec_(pt)
        if selected == act_task:
            self._ai_extract_task()
        elif selected == act_polish:
            self._ai_polish_note()

    def _ai_extract_task(self):
        """调用大模型将便签提取为待办任务并加入日程。"""
        content = self.editor.toPlainText().strip()
        if not content:
            QtWidgets.QMessageBox.information(self, "便签为空", "请先在便签中记录需要提取的内容哦~")
            return

        if not self.owner or not hasattr(self.owner, "brain") or not self.owner.brain.online:
            QtWidgets.QMessageBox.information(
                self, "模型未配置",
                "需要先配置大模型 API Key（右键菜单 → 模型配置…）才能使用 AI 智能提取待办哦。"
            )
            return

        prompt = (
            "请分析博士的这段便签内容，提取出需要完成的事项标题，如果提到了截止日期或时间（如明天、周三、今晚），"
            "请解析出具体内容并调用 add_task 工具添加到任务列表。"
            f"\n\n便签内容：\n{content}"
        )
        self.owner.open_chat()
        if hasattr(self.owner, "input_ctrl"):
            self.owner.input_ctrl.ask(prompt)

    def _ai_polish_note(self):
        """让阿米娅把便签内容整理润色为清晰的 Markdown。"""
        content = self.editor.toPlainText().strip()
        if not content:
            return

        if not self.owner or not hasattr(self.owner, "brain") or not self.owner.brain.online:
            QtWidgets.QMessageBox.information(
                self, "模型未配置",
                "需要先配置大模型 API Key（右键菜单 → 模型配置…）才能使用 AI 润色笔记哦。"
            )
            return

        prompt = f"请帮博士将以下便签笔记整理得条理分明、重点突出、格式清晰优雅：\n\n{content}"
        self.owner.open_chat()
        if hasattr(self.owner, "input_ctrl"):
            self.owner.input_ctrl.ask(prompt)

    def _get_target_screen(self):
        """获取便签窗口所在或就近的屏幕工作区。"""
        if self.owner and hasattr(self.owner, "screen"):
            s = self.owner.screen()
            if s:
                return s
        if self.owner and hasattr(self.owner, "x") and hasattr(self.owner, "y"):
            s = QtWidgets.QApplication.screenAt(QtCore.QPoint(self.owner.x(), self.owner.y()))
            if s:
                return s
        p = QtCore.QPoint(self.x(), self.y())
        s = QtWidgets.QApplication.screenAt(p)
        if s:
            return s
        return QtWidgets.QApplication.primaryScreen()

    def center_on_screen(self):
        """将便签窗口居中在当前屏幕工作区。"""
        screen = self._get_target_screen()
        avail = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1920, 1080)
        w = self.width()
        h = self.height()
        self.setGeometry(
            avail.center().x() - w // 2,
            avail.center().y() - h // 2,
            w,
            h,
        )
        self._save_geometry()

    def dock_near_pet(self):
        """将便签智能停靠在桌宠身旁（优先左侧或右侧可用空间更大的一侧）。"""
        screen = self._get_target_screen()
        avail = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1920, 1080)
        w = max(260, min(self.width(), avail.width() - 40))
        h = max(240, min(self.height(), avail.height() - 40))

        if self.owner and hasattr(self.owner, "x") and hasattr(self.owner, "y"):
            ow_x = self.owner.x()
            ow_y = self.owner.y()
            ow_w = getattr(self.owner, "width", lambda: 200)()

            # 计算右侧与左侧可用宽度
            space_right = avail.right() - (ow_x + ow_w + 20)
            space_left = ow_x - 20 - avail.left()

            if space_right >= w:
                px = ow_x + ow_w + 20
            elif space_left >= w:
                px = ow_x - w - 20
            elif space_right >= space_left:
                px = avail.right() - w - 12
            else:
                px = avail.left() + 12

            py = max(avail.top() + 12, min(ow_y - 40, avail.bottom() - h - 12))
            self.setGeometry(px, py, w, h)
        else:
            self.center_on_screen()
        self._save_geometry()

    def ensure_visible_on_screen(self):
        """确保便签窗口完整显示在屏幕可用工作区内，防止飘到屏幕外或只露出边缘。"""
        screen = self._get_target_screen()
        avail = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1920, 1080)
        r = self.geometry()
        w = max(260, min(r.width(), avail.width() - 40))
        h = max(240, min(r.height(), avail.height() - 40))
        x = r.x()
        y = r.y()

        # 严格检查是否出界，并留出 12px 屏幕边缘缓冲
        if x + w > avail.right():
            x = avail.right() - w - 12
        if x < avail.left():
            x = avail.left() + 12
        if y + h > avail.bottom():
            y = avail.bottom() - h - 12
        if y < avail.top():
            y = avail.top() + 12

        self.setGeometry(x, y, w, h)

    def _restore_geometry(self):
        """从用户偏好中恢复便签位置与尺寸，并严格校准防止溢出屏幕。"""
        screen = self._get_target_screen()
        avail = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1920, 1080)

        geo = None
        if self.owner and hasattr(self.owner, "prefs"):
            geo = self.owner.prefs.get("notes_geometry")

        if isinstance(geo, (list, tuple)) and len(geo) == 4:
            x, y, w, h = geo
            w = max(260, min(w, avail.width() - 40))
            h = max(240, min(h, avail.height() - 40))
            # 严格钳位在屏幕可用区内（彻底根治只露出几像素边框的情况）
            x = max(avail.left() + 12, min(x, avail.right() - w - 12))
            y = max(avail.top() + 12, min(y, avail.bottom() - h - 12))
            self.setGeometry(x, y, w, h)
        else:
            self.dock_near_pet()

    def _save_geometry(self):
        """将当前尺寸与位置持久化保存。"""
        if not self.owner or not hasattr(self.owner, "prefs"):
            return
        r = self.geometry()
        val = [r.x(), r.y(), r.width(), r.height()]
        prefs = self.owner.prefs
        if hasattr(prefs, "set"):
            prefs.set("notes_geometry", val)
        elif isinstance(prefs, dict):
            prefs["notes_geometry"] = val

    def showEvent(self, e):
        self.ensure_visible_on_screen()
        self._load_active_note()
        super().showEvent(e)

    def hideEvent(self, e):
        self._do_auto_save()
        self._save_geometry()
        super().hideEvent(e)

    def closeEvent(self, e):
        self._do_auto_save()
        self._save_geometry()
        super().closeEvent(e)
