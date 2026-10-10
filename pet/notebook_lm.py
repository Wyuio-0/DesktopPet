"""Google NotebookLM 风格的课件多模态知识工作台。

三栏式现代架构：
1. 来源 (Sources): 课件卡片、统一沉稳格式徽章、切片统计、提炼状态、拖拽上传。
2. 问答 (Chat): NotebookLM 快捷探针、课件上下文对话、流式回答、考点推演。
3. 工作室 (Studio): 核心考纲速览、18px 大字号排版、高对比无杂色渲染、实时进度条、Markdown 导出与复制。
"""

import os
import re
from PyQt5 import QtCore, QtGui, QtWidgets

from . import theme
from .chat import ReplyWorker
from .schedule_dialogs import DigestGenerateThread


# ── NotebookLM 专属 QSS 风格（大字号、低噪点、沉稳统一） ─────────────────────────

_NLM_QSS = f"""
QWidget#NLMRoot {{
    background: #0D0B14;
    color: #F1EFF7;
    font-family: {theme.FONT};
}}

/* 分割条设计 */
QSplitter::handle {{
    background: rgba(167, 139, 250, 0.15);
    border-radius: 1px;
}}
QSplitter::handle:hover {{
    background: {theme.ACCENT};
}}
QSplitter::handle:horizontal {{
    width: 6px;
}}

/* 滚动条 */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(167, 139, 250, 0.25);
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: {theme.ACCENT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* 下拉框 */
QComboBox {{
    background: #171422;
    color: #F1EFF7;
    border: 1px solid #2D273D;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 15px;
    min-width: 140px;
}}
QComboBox:hover {{
    border-color: {theme.BORDER_STRONG};
}}
QComboBox:focus {{
    border-color: {theme.ACCENT};
}}
QComboBox QAbstractItemView {{
    background: #1A1726;
    color: #F1EFF7;
    border: 1px solid #362F47;
    selection-background-color: rgba(167, 139, 250, 0.2);
    selection-color: #FFFFFF;
    font-size: 15px;
    padding: 6px;
}}

/* 输入框与文本阅览 */
QLineEdit, QPlainTextEdit, QTextBrowser {{
    background: #171422;
    color: #F1EFF7;
    border: 1px solid #2D273D;
    border-radius: 8px;
    font-size: 16px;
    font-family: {theme.FONT};
}}
QLineEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {theme.ACCENT};
    background: #1C182A;
}}

/* 按钮统一风格 */
QPushButton {{
    background: #1A1726;
    color: #E2DEEC;
    border: 1px solid #2D273D;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 14px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: rgba(167, 139, 250, 0.15);
    border-color: {theme.ACCENT};
    color: #FFFFFF;
}}
QPushButton:pressed {{
    background: {theme.ACCENT_DEEP};
    color: #FFFFFF;
}}
QPushButton:disabled {{
    color: #6B6278;
    border-color: rgba(255, 255, 255, 0.05);
}}

/* 核心行动主按钮 */
QPushButton#PrimaryBtn {{
    background: {theme.ACCENT};
    color: #120E1A;
    border: 1px solid {theme.ACCENT};
    font-weight: bold;
    font-size: 15px;
    border-radius: 8px;
}}
QPushButton#PrimaryBtn:hover {{
    background: {theme.ACCENT_BRIGHT};
    border-color: {theme.ACCENT_BRIGHT};
}}
QPushButton#PrimaryBtn:pressed {{
    background: {theme.ACCENT_DEEP};
    color: #FFFFFF;
}}
"""


class SourceCard(QtWidgets.QFrame):
    """Google NotebookLM 风格的单份课件卡片（统一色调、大字号）。"""

    sig_selected = QtCore.pyqtSignal(dict)
    sig_digest = QtCore.pyqtSignal(dict)
    sig_ask = QtCore.pyqtSignal(dict)
    sig_delete = QtCore.pyqtSignal(dict)

    def __init__(self, file_info, is_active=False, parent=None):
        super().__init__(parent)
        self.file_info = file_info
        self.is_active = is_active
        self.setObjectName("SourceCard")
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self._build_ui()
        self._update_style()

    def _build_ui(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(9)

        # 顶行：统一格式微标 + 文件名 + 删除按钮
        top_row = QtWidgets.QHBoxLayout()
        top_row.setSpacing(8)

        ext = os.path.splitext(self.file_info.get("filename", ""))[1].upper().replace(".", "")
        if not ext:
            ext = "DOC"

        badge_lbl = QtWidgets.QLabel(ext, self)
        badge_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {theme.ACCENT_BRIGHT}; "
            f"background: rgba(167, 139, 250, 0.12); border: 1px solid rgba(167, 139, 250, 0.25); "
            f"border-radius: 4px; padding: 2px 7px;"
        )
        top_row.addWidget(badge_lbl)

        fn = self.file_info.get("filename", "")
        title_lbl = QtWidgets.QLabel(fn, self)
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF;")
        title_lbl.setToolTip(fn)
        title_lbl.setWordWrap(True)
        top_row.addWidget(title_lbl, 1)

        btn_del = QtWidgets.QPushButton("✕", self)
        btn_del.setFixedSize(24, 24)
        btn_del.setToolTip("从知识库移除此课件")
        btn_del.setStyleSheet(
            f"QPushButton {{ border: none; background: transparent; color: #7A7288; font-size: 14px; font-weight: bold; }} "
            f"QPushButton:hover {{ color: {theme.RED}; background: rgba(248, 113, 113, 0.15); border-radius: 4px; }}"
        )
        btn_del.clicked.connect(lambda: self.sig_delete.emit(self.file_info))
        top_row.addWidget(btn_del)
        lay.addLayout(top_row)

        # 中行：课程标签 · 大小 · 切片统计
        meta_row = QtWidgets.QHBoxLayout()
        meta_row.setSpacing(8)

        c_name = self.file_info.get("course") or "通用资料"
        course_badge = QtWidgets.QLabel(c_name, self)
        course_badge.setStyleSheet(
            "background: rgba(255, 255, 255, 0.06); color: #C5BFD2; border: 1px solid rgba(255, 255, 255, 0.1); "
            "padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500;"
        )
        meta_row.addWidget(course_badge)

        sz_str = self.file_info.get("size_str", "")
        chunks = self.file_info.get("chunks", 0)
        info_text = f"{sz_str} · {chunks} 切片" if sz_str else f"{chunks} 切片"
        info_lbl = QtWidgets.QLabel(info_text, self)
        info_lbl.setStyleSheet("color: #9A92A8; font-size: 13px;")
        meta_row.addWidget(info_lbl)
        meta_row.addStretch(1)
        lay.addLayout(meta_row)

        # 提炼进度条（仅提炼中可见）
        self.pbar = QtWidgets.QProgressBar(self)
        self.pbar.setFixedHeight(16)
        self.pbar.setRange(0, 100)
        self.pbar.setTextVisible(True)
        self.pbar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background: #231E31;
                text-align: center;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {theme.ACCENT}, stop:1 {theme.ACCENT_BRIGHT});
                border-radius: 4px;
            }}
        """)
        self.pbar.setVisible(False)
        lay.addWidget(self.pbar)

        # 底行：状态徽标 + 快速操作
        bottom_row = QtWidgets.QHBoxLayout()
        bottom_row.setSpacing(8)

        self.status_lbl = QtWidgets.QLabel(self)
        self._update_status_label()
        bottom_row.addWidget(self.status_lbl, 1)

        btn_digest = QtWidgets.QPushButton("⚡ 考纲", self)
        btn_digest.setToolTip("在右侧工作室查看或生成核心知识点大纲")
        btn_digest.setStyleSheet(
            f"QPushButton {{ background: rgba(167, 139, 250, 0.12); color: {theme.ACCENT_BRIGHT}; "
            f"border: 1px solid rgba(167, 139, 250, 0.3); padding: 4px 10px; font-size: 13px; border-radius: 6px; font-weight: 500; }} "
            f"QPushButton:hover {{ background: {theme.ACCENT}; color: #120E1A; font-weight: bold; border-color: {theme.ACCENT}; }}"
        )
        btn_digest.clicked.connect(lambda: self.sig_digest.emit(self.file_info))
        bottom_row.addWidget(btn_digest)

        btn_ask = QtWidgets.QPushButton("💬 提问", self)
        btn_ask.setToolTip("针对此课件在中间问答栏向阿米娅发起提问")
        btn_ask.setStyleSheet(
            f"QPushButton {{ background: #201B2E; color: #E2DEEC; "
            f"border: 1px solid #362F47; padding: 4px 10px; font-size: 13px; border-radius: 6px; font-weight: 500; }} "
            f"QPushButton:hover {{ background: rgba(167, 139, 250, 0.2); border-color: {theme.ACCENT}; color: #FFFFFF; }}"
        )
        btn_ask.clicked.connect(lambda: self.sig_ask.emit(self.file_info))
        bottom_row.addWidget(btn_ask)

        lay.addLayout(bottom_row)

    def _update_status_label(self):
        progress = self.file_info.get("progress")
        has_digest = self.file_info.get("has_digest", False)

        if progress is not None and 0 <= progress < 100:
            self.status_lbl.setText(f"⏳ 正在提炼 {progress}%")
            self.status_lbl.setStyleSheet(f"color: {theme.AMBER}; font-size: 13px; font-weight: 600;")
            self.pbar.setVisible(True)
            self.pbar.setValue(progress)
            self.pbar.setFormat(f"提炼 {progress}%")
        elif has_digest:
            self.status_lbl.setText("● 考纲已就绪")
            self.status_lbl.setStyleSheet(f"color: {theme.ACCENT_BRIGHT}; font-size: 13px; font-weight: 600;")
            self.pbar.setVisible(False)
        else:
            self.status_lbl.setText("○ 待提炼考纲")
            self.status_lbl.setStyleSheet("color: #8C849B; font-size: 13px;")
            self.pbar.setVisible(False)

    def set_active(self, active):
        self.is_active = active
        self._update_style()

    def update_progress(self, pct, msg=""):
        self.file_info["progress"] = pct
        self._update_status_label()

    def set_digest_ready(self, ready=True):
        self.file_info["has_digest"] = ready
        self.file_info.pop("progress", None)
        self._update_status_label()

    def _update_style(self):
        if self.is_active:
            self.setStyleSheet(f"""
                QFrame#SourceCard {{
                    background: #231C33;
                    border: 1.5px solid {theme.ACCENT};
                    border-radius: 10px;
                }}
            """)
        else:
            self.setStyleSheet("""
                QFrame#SourceCard {{
                    background: #171422;
                    border: 1px solid #2B253A;
                    border-radius: 10px;
                }}
                QFrame#SourceCard:hover {{
                    border: 1px solid #483E5E;
                    background: #1D182A;
                }}
            """)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self.sig_selected.emit(self.file_info)
        super().mousePressEvent(e)


class NotebookLMWorkspace(QtWidgets.QWidget):
    """Google NotebookLM 风格的全景知识工作台（嵌入式 / 独立对话框通用）。"""

    sig_upload_requested = QtCore.pyqtSignal()
    sig_open_folder_requested = QtCore.pyqtSignal()

    def __init__(self, owner=None, brain=None, kb=None, initial_course=None, initial_file=None, parent=None):
        super().__init__(parent or owner)
        self.owner = owner
        self.brain = brain or (getattr(owner, "brain", None) if owner else None)
        self.kb = kb or getattr(self.brain, "knowledge", None)
        self.initial_course = initial_course
        self.initial_file = initial_file
        self.active_file_info = None

        self._reply_worker = None
        self._digest_workers = {}
        self._cards = {}

        self.setObjectName("NLMRoot")
        self.setStyleSheet(_NLM_QSS)
        self.setAcceptDrops(True)

        self._build_ui()
        self.refresh_sources()

    def _build_ui(self):
        root_lay = QtWidgets.QVBoxLayout(self)
        root_lay.setContentsMargins(14, 12, 14, 14)
        root_lay.setSpacing(12)

        # 顶栏：标题 + 课程选择器 + 状态统计 + 操作按钮
        top_bar = QtWidgets.QHBoxLayout()
        top_bar.setSpacing(14)

        icon_lbl = QtWidgets.QLabel("📓", self)
        icon_lbl.setStyleSheet("font-size: 26px;")
        top_bar.addWidget(icon_lbl)

        title_lay = QtWidgets.QVBoxLayout()
        title_lay.setSpacing(3)
        self.title_lbl = QtWidgets.QLabel("课件学业研究台 · NotebookLM", self)
        self.title_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        self.stat_lbl = QtWidgets.QLabel("正在同步课程知识库...", self)
        self.stat_lbl.setStyleSheet("font-size: 14px; color: #9A92A8;")
        title_lay.addWidget(self.title_lbl)
        title_lay.addWidget(self.stat_lbl)
        top_bar.addLayout(title_lay)

        top_bar.addStretch(1)

        c_lbl = QtWidgets.QLabel("课程视图：", self)
        c_lbl.setStyleSheet("color: #B5ADBF; font-size: 15px; font-weight: 500;")
        top_bar.addWidget(c_lbl)

        self.course_combo = QtWidgets.QComboBox(self)
        self.course_combo.currentIndexChanged.connect(self._on_course_combo_changed)
        top_bar.addWidget(self.course_combo)

        self.btn_upload = QtWidgets.QPushButton("➕ 添加来源", self)
        self.btn_upload.setObjectName("PrimaryBtn")
        self.btn_upload.setToolTip("从本地电脑导入 PDF / PPT / Word 讲义或课件")
        self.btn_upload.clicked.connect(self._on_upload_clicked)
        top_bar.addWidget(self.btn_upload)

        self.btn_folder = QtWidgets.QPushButton("📁 课件库目录", self)
        self.btn_folder.setToolTip("在 Windows 文件资源管理器中打开知识库文件夹")
        self.btn_folder.clicked.connect(self._on_open_folder_clicked)
        top_bar.addWidget(self.btn_folder)

        root_lay.addLayout(top_bar)

        # 三栏分割器：来源 (左) | 问答 (中) | 考纲工作室 (右)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.splitter.setChildrenCollapsible(False)

        # ── 栏 1：来源 (Sources) ───────────────────────────────────
        sources_panel = QtWidgets.QWidget(self.splitter)
        sources_lay = QtWidgets.QVBoxLayout(sources_panel)
        sources_lay.setContentsMargins(0, 0, 10, 0)
        sources_lay.setSpacing(10)

        s_head = QtWidgets.QHBoxLayout()
        s_title = QtWidgets.QLabel("📚 来源资料", sources_panel)
        s_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        self.s_count_lbl = QtWidgets.QLabel("0 份文件", sources_panel)
        self.s_count_lbl.setStyleSheet(f"color: {theme.ACCENT_BRIGHT}; font-size: 14px; font-weight: bold;")
        s_head.addWidget(s_title)
        s_head.addWidget(self.s_count_lbl)
        s_head.addStretch(1)
        sources_lay.addLayout(s_head)

        # 拖拽提示卡片
        self.drop_card = QtWidgets.QFrame(sources_panel)
        self.drop_card.setStyleSheet("""
            QFrame {
                background: #15121F;
                border: 1.5px dashed #3D3551;
                border-radius: 8px;
                padding: 10px;
            }
            QFrame:hover {
                border-color: #A78BFA;
                background: rgba(167, 139, 250, 0.08);
            }
        """)
        drop_lay = QtWidgets.QVBoxLayout(self.drop_card)
        drop_lay.setContentsMargins(8, 8, 8, 8)
        drop_lay.setSpacing(4)
        drop_tip = QtWidgets.QLabel("📥 拖拽 PDF / PPT / Word 到此", self.drop_card)
        drop_tip.setAlignment(QtCore.Qt.AlignCenter)
        drop_tip.setStyleSheet(f"color: {theme.ACCENT_BRIGHT}; font-size: 14px; font-weight: 600;")
        drop_sub = QtWidgets.QLabel("阿米娅将自动关联课程并提炼考纲", self.drop_card)
        drop_sub.setAlignment(QtCore.Qt.AlignCenter)
        drop_sub.setStyleSheet("color: #8C849B; font-size: 12px;")
        drop_lay.addWidget(drop_tip)
        drop_lay.addWidget(drop_sub)
        sources_lay.addWidget(self.drop_card)

        # 课件卡片滚动列表
        self.cards_scroll = QtWidgets.QScrollArea(sources_panel)
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.cards_container = QtWidgets.QWidget()
        self.cards_lay = QtWidgets.QVBoxLayout(self.cards_container)
        self.cards_lay.setContentsMargins(0, 0, 0, 0)
        self.cards_lay.setSpacing(8)
        self.cards_lay.addStretch(1)
        self.cards_scroll.setWidget(self.cards_container)
        sources_lay.addWidget(self.cards_scroll, 1)

        self.splitter.addWidget(sources_panel)

        # ── 栏 2：问答交互 (Chat & Study Assistant) ────────────────
        chat_panel = QtWidgets.QWidget(self.splitter)
        chat_lay = QtWidgets.QVBoxLayout(chat_panel)
        chat_lay.setContentsMargins(8, 0, 8, 0)
        chat_lay.setSpacing(10)

        chat_head = QtWidgets.QHBoxLayout()
        chat_title = QtWidgets.QLabel("💬 智能学研助教", chat_panel)
        chat_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        chat_sub = QtWidgets.QLabel("基于选定课件解答与考点推演", chat_panel)
        chat_sub.setStyleSheet("color: #9A92A8; font-size: 13px;")
        chat_head.addWidget(chat_title)
        chat_head.addWidget(chat_sub)
        chat_head.addStretch(1)

        btn_clear_chat = QtWidgets.QPushButton("清空记录", chat_panel)
        btn_clear_chat.setStyleSheet("padding: 4px 10px; font-size: 13px; border-radius: 6px;")
        btn_clear_chat.clicked.connect(self._clear_chat)
        chat_head.addWidget(btn_clear_chat)
        chat_lay.addLayout(chat_head)

        # Google NotebookLM 快捷探针（Prompt Chips，沉稳药丸按键）
        chips_box = QtWidgets.QHBoxLayout()
        chips_box.setSpacing(8)
        chips = [
            ("🎯 划出期末重点", "请根据当前课件与教材内容，帮我划出期末考试的核心重点与必考考点。"),
            ("📝 5道期末模拟题", "请严格依据当前课件，为我出5道常考的期末模拟简答或分析题，并附带参考答案。"),
            ("💡 核心考点与公式", "请帮我梳理当前课件中的核心概念、定律、公式及解题步骤框架。"),
            ("⚡ 易错与对比辨析", "请帮我找出当前课件中最容易混淆的概念、常见错题陷阱与对比辨析表格。"),
        ]
        for label, prompt in chips:
            btn = QtWidgets.QPushButton(label, chat_panel)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #1A1726;
                    color: #EDE8F5;
                    border: 1px solid #362F47;
                    border-radius: 16px;
                    padding: 6px 14px;
                    font-size: 13px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {theme.ACCENT};
                    color: #120E1A;
                    border-color: {theme.ACCENT};
                    font-weight: bold;
                }}
            """)
            btn.clicked.connect(lambda _, p=prompt: self._ask_question(p))
            chips_box.addWidget(btn)
        chips_box.addStretch(1)
        chat_lay.addLayout(chips_box)

        # 问答展示框
        self.chat_browser = QtWidgets.QTextBrowser(chat_panel)
        self.chat_browser.setOpenExternalLinks(True)
        self.chat_browser.setStyleSheet("""
            QTextBrowser {{
                background: #14111E;
                border: 1px solid #282236;
                border-radius: 10px;
                padding: 14px;
                font-size: 16px;
                line-height: 1.6;
            }}
        """)
        self._init_chat_welcome()
        chat_lay.addWidget(self.chat_browser, 1)

        # 底部输入框条
        input_container = QtWidgets.QFrame(chat_panel)
        input_container.setStyleSheet(f"""
            QFrame {{
                background: #1C182A;
                border: 1px solid {theme.BORDER_STRONG};
                border-radius: 22px;
                padding: 4px 10px;
            }}
        """)
        input_lay = QtWidgets.QHBoxLayout(input_container)
        input_lay.setContentsMargins(8, 4, 8, 4)
        input_lay.setSpacing(8)

        self.chat_input = QtWidgets.QLineEdit(input_container)
        self.chat_input.setPlaceholderText("向选中的课件提问，或让阿米娅帮您梳理核心考点...")
        self.chat_input.setStyleSheet("border: none; background: transparent; font-size: 15px; color: #FFFFFF; padding: 4px;")
        self.chat_input.returnPressed.connect(self._on_input_submitted)
        input_lay.addWidget(self.chat_input, 1)

        self.btn_send = QtWidgets.QPushButton("➤", input_container)
        self.btn_send.setFixedSize(34, 34)
        self.btn_send.setToolTip("发送学术提问")
        self.btn_send.setStyleSheet(f"""
            QPushButton {{
                background: {theme.ACCENT};
                color: #120E1A;
                border: none;
                border-radius: 17px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {theme.ACCENT_BRIGHT};
            }}
        """)
        self.btn_send.clicked.connect(self._on_input_submitted)
        input_lay.addWidget(self.btn_send)
        chat_lay.addWidget(input_container)

        self.splitter.addWidget(chat_panel)

        # ── 栏 3：工作室 · 考纲速览 (Studio / Study Guide) ─────────
        studio_panel = QtWidgets.QWidget(self.splitter)
        studio_lay = QtWidgets.QVBoxLayout(studio_panel)
        studio_lay.setContentsMargins(10, 0, 0, 0)
        studio_lay.setSpacing(10)

        # 工作室顶栏
        studio_head = QtWidgets.QHBoxLayout()
        studio_head.setSpacing(10)

        st_title = QtWidgets.QLabel("⚡ 核心考纲工作室", studio_panel)
        st_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        studio_head.addWidget(st_title)

        self.active_file_badge = QtWidgets.QLabel("请在左侧选择课件", studio_panel)
        self.active_file_badge.setStyleSheet(
            f"background: rgba(167, 139, 250, 0.12); color: {theme.ACCENT_BRIGHT}; "
            f"border: 1px solid rgba(167, 139, 250, 0.25); padding: 3px 10px; border-radius: 5px; "
            f"font-size: 13px; font-weight: bold;"
        )
        studio_head.addWidget(self.active_file_badge)
        studio_head.addStretch(1)

        self.btn_copy_digest = QtWidgets.QPushButton("📋 复制考纲", studio_panel)
        self.btn_copy_digest.setToolTip("将提炼的考纲复制到系统剪贴板")
        self.btn_copy_digest.clicked.connect(self._copy_digest)
        studio_head.addWidget(self.btn_copy_digest)

        self.btn_export_md = QtWidgets.QPushButton("💾 导出", studio_panel)
        self.btn_export_md.setToolTip("将核心考纲导出为本地 Markdown 文档")
        self.btn_export_md.clicked.connect(self._export_markdown)
        studio_head.addWidget(self.btn_export_md)

        self.btn_regen_digest = QtWidgets.QPushButton("🔄 重新提炼", studio_panel)
        self.btn_regen_digest.setObjectName("PrimaryBtn")
        self.btn_regen_digest.setToolTip("调用 AI 重新对本课件提炼核心考点")
        self.btn_regen_digest.clicked.connect(self._start_active_digest)
        studio_head.addWidget(self.btn_regen_digest)

        studio_lay.addLayout(studio_head)

        # 工作室实时进度条
        self.studio_pbar = QtWidgets.QProgressBar(studio_panel)
        self.studio_pbar.setFixedHeight(24)
        self.studio_pbar.setRange(0, 100)
        self.studio_pbar.setTextVisible(True)
        self.studio_pbar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {theme.ACCENT};
                border-radius: 6px;
                background: #1B1728;
                text-align: center;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {theme.ACCENT}, stop:1 {theme.ACCENT_BRIGHT});
                border-radius: 5px;
            }}
        """)
        self.studio_pbar.setVisible(False)
        studio_lay.addWidget(self.studio_pbar)

        # 考纲大字号阅览框（18px 大字号、1.75 舒适行距、高对比）
        self.studio_browser = QtWidgets.QTextBrowser(studio_panel)
        self.studio_browser.setOpenExternalLinks(True)
        self.studio_browser.setStyleSheet(f"""
            QTextBrowser {{
                background: #14111E;
                color: #F1EFF7;
                border: 1px solid #282236;
                border-radius: 10px;
                padding: 22px;
                font-size: 18px;
                font-family: {theme.FONT};
                line-height: 1.75;
            }}
        """)
        studio_lay.addWidget(self.studio_browser, 1)

        self.splitter.addWidget(studio_panel)

        # 默认分栏比例：290px (来源) : 410px (问答) : 500px (工作室)
        self.splitter.setSizes([290, 410, 500])
        root_lay.addWidget(self.splitter, 1)

    def _init_chat_welcome(self):
        welcome_html = f"""
        <div style="padding: 12px; color: #F1EFF7; font-family: {theme.FONT};">
            <h3 style="color: #FFFFFF; margin-bottom: 10px; font-size: 18px;">✨ 阿米娅学术学研助教</h3>
            <p style="color: #A6A0B5; line-height: 1.7; font-size: 16px;">
                您可以点击上方的 <b>快捷探针</b>（如期末重点、模拟考题、公式定理梳理），或直接在下方针对当前课件提问。
            </p>
            <div style="background: #1A1726; border-left: 3px solid {theme.ACCENT}; padding: 12px; border-radius: 4px; margin-top: 14px; font-size: 15px; color: #C5BFD2;">
                💡 <b>贴士</b>：在左侧列表点击任意课件，中栏问答与右侧工作室将自动切换至该课件考纲。
            </div>
        </div>
        """
        self.chat_browser.setHtml(welcome_html)

    # ── 来源数据与列表刷新 ──────────────────────────────────────────

    def refresh_sources(self, select_course=None):
        """重新扫描知识库文件并刷新卡片列表。"""
        kb = self.kb or getattr(self.brain, "knowledge", None)
        if not kb:
            self.stat_lbl.setText("未检测到本地知识库组件")
            return

        stats = kb.get_stats()
        self.stat_lbl.setText(
            f"已收录 {stats['course_count']} 门课程 · {stats['file_count']} 份课件 · {stats['chunk_count']} 个知识切片"
        )
        self.s_count_lbl.setText(f"{stats['file_count']} 份文件")

        # 刷新课程下拉列表（保持当前选择）
        cur_data = select_course or self.course_combo.currentData()
        self.course_combo.blockSignals(True)
        self.course_combo.clear()
        self.course_combo.addItem("📚 全部课程资料", "__ALL__")
        self.course_combo.addItem("📂 通用讲义与笔记", "__GLOBAL__")
        for c in sorted(stats.get("courses", [])):
            if c:
                self.course_combo.addItem(f"📖 {c}", c)

        idx = 0
        if cur_data:
            found = self.course_combo.findData(cur_data)
            if found >= 0:
                idx = found
        self.course_combo.setCurrentIndex(idx)
        self.course_combo.blockSignals(False)

        # 获取课件列表
        selected_course = self.course_combo.currentData()
        course_filter = None if selected_course in ("__ALL__", None) else selected_course
        files = kb.get_course_files(course_filter)
        for f in files:
            sz = f.get("size", 0)
            sz_kb = sz / 1024
            f["size_str"] = f"{sz_kb/1024:.1f} MB" if sz_kb >= 1024 else f"{sz_kb:.0f} KB"

        # 清除旧卡片
        while self.cards_lay.count() > 1:
            item = self.cards_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._cards.clear()

        if not files:
            empty_lbl = QtWidgets.QLabel("暂无课件文件\n点击上方「➕ 添加来源」导入", self.cards_container)
            empty_lbl.setAlignment(QtCore.Qt.AlignCenter)
            empty_lbl.setStyleSheet("color: #7A7288; padding: 40px 10px; font-size: 15px;")
            self.cards_lay.insertWidget(0, empty_lbl)
            self._set_active_file(None)
            return

        active_to_pick = None
        target_fn = self.initial_file or (self.active_file_info.get("filename") if self.active_file_info else None)

        active_tasks = getattr(self.owner, "_active_digest_tasks", {}) if self.owner else {}

        for f in files:
            fn = f.get("filename")
            cn = f.get("course")
            task_key = (fn, cn or "")
            if task_key in active_tasks:
                f["progress"] = active_tasks[task_key].get("progress", 0)

            card = SourceCard(f, parent=self.cards_container)
            card.sig_selected.connect(self._set_active_file)
            card.sig_digest.connect(self._on_card_digest_clicked)
            card.sig_ask.connect(self._on_card_ask_clicked)
            card.sig_delete.connect(self._on_card_delete_clicked)

            self.cards_lay.insertWidget(self.cards_lay.count() - 1, card)
            self._cards[(fn, cn or "")] = card

            if target_fn and fn == target_fn:
                active_to_pick = f

        if not active_to_pick and files:
            active_to_pick = files[0]

        if active_to_pick:
            self._set_active_file(active_to_pick)

    def _set_active_file(self, file_info):
        """切换当前活动文件并刷新右侧工作室与问答上下文。"""
        self.active_file_info = file_info

        # 更新左侧卡片高亮
        for key, card in self._cards.items():
            if file_info and key == (file_info.get("filename"), file_info.get("course") or ""):
                card.set_active(True)
            else:
                card.set_active(False)

        if not file_info:
            self.active_file_badge.setText("未选择课件")
            self.studio_browser.setHtml("<div style='color:#7A7288; padding:50px; text-align:center; font-size:16px;'>请在左侧选择课件以查看考纲</div>")
            self.btn_copy_digest.setEnabled(False)
            self.btn_export_md.setEnabled(False)
            self.btn_regen_digest.setEnabled(False)
            return

        fn = file_info.get("filename", "")
        cn = file_info.get("course", "") or "通用讲义"
        self.active_file_badge.setText(f"《{fn}》· {cn}")
        self.btn_copy_digest.setEnabled(True)
        self.btn_export_md.setEnabled(True)
        self.btn_regen_digest.setEnabled(True)

        self._load_studio_digest()

    def _load_studio_digest(self):
        """载入当前活动文件的知识大纲至右侧工作室。"""
        if not self.active_file_info:
            return

        fn = self.active_file_info.get("filename", "")
        cn = self.active_file_info.get("course", "")

        # 检查是否正在提炼中
        active_tasks = getattr(self.owner, "_active_digest_tasks", {}) if self.owner else {}
        task_info = active_tasks.get((fn, cn or ""))
        if task_info:
            pct = task_info.get("progress", 0)
            status_msg = task_info.get("status", "提炼中...")
            self.studio_pbar.setVisible(True)
            self.studio_pbar.setValue(pct)
            self.studio_pbar.setFormat(f"正在提炼考纲: {pct}% · {status_msg}")
            self.btn_regen_digest.setEnabled(False)
            self.studio_browser.setHtml(f"""
                <div style="text-align: center; padding: 70px 20px; color: #FFFFFF;">
                    <h2 style="color: #FFFFFF; font-size: 22px;">⏳ 阿米娅正在深度梳理《{fn}》核心考点...</h2>
                    <p style="color: {theme.ACCENT_BRIGHT}; font-size: 16px; margin-top: 10px;">已完成 {pct}% · {status_msg}</p>
                    <p style="color: #8C849B; font-size: 14px; margin-top: 15px;">
                        正在提炼考纲大纲、公式推导、概念辨析与预测考题，请稍候。
                    </p>
                </div>
            """)
            return

        kb = self.kb or getattr(self.brain, "knowledge", None)
        if kb and kb.has_digest(fn, cn):
            digest_text = kb.get_digest(fn, cn)
            if digest_text and digest_text.strip():
                self.studio_pbar.setVisible(False)
                self.btn_regen_digest.setEnabled(True)
                self._render_markdown_in_studio(digest_text.strip())
                return

        # 尚未提炼考纲
        self.studio_pbar.setVisible(False)
        self.btn_regen_digest.setEnabled(True)
        empty_digest_html = f"""
        <div style="padding: 30px 15px; color: #F1EFF7; font-family: {theme.FONT};">
            <h2 style="color: #FFFFFF; margin-bottom: 14px; font-size: 22px;">⚡ 尚未为《{fn}》生成核心考纲</h2>
            <p style="color: #A6A0B5; font-size: 17px; line-height: 1.7;">
                点击右上角的 <b>「🔄 重新提炼」</b> 按钮，阿米娅将使用大模型深入解析课件全貌，自动生成：
            </p>
            <ul style="color: #EDE8F5; font-size: 16px; line-height: 1.8; margin-left: 20px;">
                <li>📚 <b>核心概念与关键术语速记表</b></li>
                <li>📐 <b>重点公式推导、定理法则与解题步骤</b></li>
                <li>🎯 <b>期末必考考点与预测大题 (⭐⭐⭐)</b></li>
                <li>💡 <b>核心易混淆概念对比与避坑指南</b></li>
                <li>📝 <b>考前自测模拟简答题 (Q&A)</b></li>
            </ul>
            <div style="margin-top: 30px; text-align: center;">
                <p style="color: #7A7288; font-size: 14px;">提炼完成后将永久缓存在本地知识库，随时支持检索与问答。</p>
            </div>
        </div>
        """
        self.studio_browser.setHtml(empty_digest_html)

    def _render_markdown_in_studio(self, md_text):
        """渲染高对比、无杂色、大字号 (18px) 的 Markdown 考纲内容。"""
        html = self._format_markdown_html(md_text)
        self.studio_browser.setHtml(html)

    def _format_markdown_html(self, text):
        """将 Markdown 转换为高对比、沉稳统一且字号舒适的 HTML。"""
        lines = text.split("\n")
        out = []
        in_code = False

        for line in lines:
            if line.strip().startswith("```"):
                if in_code:
                    out.append("</pre></div>")
                    in_code = False
                else:
                    out.append(
                        "<div style='background:#100E17; border:1px solid #282436; border-radius:6px; padding:12px; margin:12px 0;'>"
                        f"<pre style='font-family:{theme.MONO}; color:#EDE8F5; font-size:16px; margin:0; line-height:1.6;'>"
                    )
                    in_code = True
                continue

            if in_code:
                out.append(QtCore.Qt.escape(line) if hasattr(QtCore.Qt, "escape") else line)
                continue

            l = line.strip()
            if l.startswith("# "):
                out.append(f"<h1 style='color:#FFFFFF; border-bottom:1px solid rgba(167, 139, 250, 0.35); padding-bottom:8px; margin-top:24px; font-size:25px; font-weight:bold;'>{l[2:]}</h1>")
            elif l.startswith("## "):
                out.append(f"<h2 style='color:#FFFFFF; border-left:4px solid {theme.ACCENT}; padding-left:10px; margin-top:22px; font-size:21px; font-weight:bold;'>{l[3:]}</h2>")
            elif l.startswith("### "):
                out.append(f"<h3 style='color:#E6E1F2; margin-top:16px; font-size:18px; font-weight:bold;'>{l[4:]}</h3>")
            elif l.startswith("- ") or l.startswith("* "):
                content = l[2:]
                content = re.sub(r"\*\*(.+?)\*\*", r"<b style='color:#FFFFFF; font-weight:600;'>\1</b>", content)
                out.append(f"<div style='margin-left:14px; margin-bottom:5px; font-size:17px; line-height:1.75; color:#F0EFF5;'>• {content}</div>")
            elif re.match(r"^\d+\.\s", l):
                content = re.sub(r"^\d+\.\s", "", l)
                content = re.sub(r"\*\*(.+?)\*\*", r"<b style='color:#FFFFFF; font-weight:600;'>\1</b>", content)
                out.append(f"<div style='margin-left:14px; margin-bottom:5px; font-size:17px; line-height:1.75; color:#F0EFF5;'>① {content}</div>")
            elif l.startswith("> "):
                out.append(f"<div style='background:rgba(167, 139, 250, 0.08); border-left:3px solid {theme.ACCENT}; padding:10px 14px; border-radius:4px; margin:10px 0; color:#DDD8E8; font-size:16px; line-height:1.7;'>{l[2:]}</div>")
            elif not l:
                out.append("<div style='height:10px;'></div>")
            else:
                content = re.sub(r"\*\*(.+?)\*\*", r"<b style='color:#FFFFFF; font-weight:600;'>\1</b>", line)
                out.append(f"<p style='font-size:17px; line-height:1.75; margin:6px 0; color:#F0EFF5;'>{content}</p>")

        if in_code:
            out.append("</pre></div>")

        return f"<div style='font-family:{theme.FONT}; line-height:1.75;'>{''.join(out)}</div>"

    # ── 考纲生成与进度响应 ──────────────────────────────────────────

    def _start_active_digest(self):
        """开始为当前选中的课件生成考纲。"""
        if not self.active_file_info:
            return

        fn = self.active_file_info.get("filename", "")
        cn = self.active_file_info.get("course", "")
        fp = self.active_file_info.get("path", "")

        kb = self.kb or getattr(self.brain, "knowledge", None)
        if not fp or not os.path.isfile(fp):
            if kb:
                if cn and str(cn).strip():
                    fp = os.path.join(kb.courses_dir, str(cn).strip(), fn)
                else:
                    fp = os.path.join(kb.folder, fn)

        if not fp or not os.path.isfile(fp):
            QtWidgets.QMessageBox.warning(self, "未找到文件", f"课件源文件不存在：{fn}")
            return

        self.studio_pbar.setVisible(True)
        self.studio_pbar.setValue(0)
        self.studio_pbar.setFormat("正在启动分析提炼...")
        self.btn_regen_digest.setEnabled(False)

        worker = DigestGenerateThread(self.brain, fp, fn, cn, parent=self)
        task_key = (fn, cn or "")

        if self.owner and hasattr(self.owner, "_active_digest_tasks"):
            self.owner._active_digest_tasks[task_key] = {"progress": 0, "status": "启动中...", "worker": worker}

        worker.sig_progress.connect(self._on_worker_progress)
        worker.sig_done.connect(lambda txt, f_name=fn, c_name=cn: self._on_worker_done(f_name, c_name, txt))
        worker.sig_error.connect(lambda err, f_name=fn, c_name=cn: self._on_worker_error(f_name, c_name, err))

        self._digest_workers[task_key] = worker
        worker.start()

        # 更新左侧卡片进度
        card = self._cards.get(task_key)
        if card:
            card.update_progress(0, "正在启动...")

    def _on_worker_progress(self, pct, msg):
        self.studio_pbar.setVisible(True)
        self.studio_pbar.setValue(pct)
        self.studio_pbar.setFormat(f"提炼进度: {pct}% · {msg}")

        if self.active_file_info:
            task_key = (self.active_file_info.get("filename"), self.active_file_info.get("course") or "")
            card = self._cards.get(task_key)
            if card:
                card.update_progress(pct, msg)

    def _on_worker_done(self, filename, course, digest_text):
        task_key = (filename, course or "")
        self._digest_workers.pop(task_key, None)

        if self.owner and hasattr(self.owner, "_active_digest_tasks"):
            self.owner._active_digest_tasks.pop(task_key, None)

        kb = self.kb or getattr(self.brain, "knowledge", None)
        if kb:
            kb.save_digest(filename, course, digest_text)

        card = self._cards.get(task_key)
        if card:
            card.set_digest_ready(True)

        if self.active_file_info and (self.active_file_info.get("filename"), self.active_file_info.get("course") or "") == task_key:
            self.studio_pbar.setValue(100)
            self.studio_pbar.setFormat("✅ 提炼完成 100%")
            QtCore.QTimer.singleShot(1500, lambda: self.studio_pbar.setVisible(False))
            self.btn_regen_digest.setEnabled(True)
            self._render_markdown_in_studio(digest_text)

        if self.owner and hasattr(self.owner, "bubble") and hasattr(self.owner, "_body_rect"):
            self.owner.bubble.say(f"博士，《{filename}》的考纲与知识点提炼完成啦！随时可以查看～", self.owner._body_rect())

    def _on_worker_error(self, filename, course, err_msg):
        task_key = (filename, course or "")
        self._digest_workers.pop(task_key, None)

        if self.owner and hasattr(self.owner, "_active_digest_tasks"):
            self.owner._active_digest_tasks.pop(task_key, None)

        self.studio_pbar.setVisible(False)
        self.btn_regen_digest.setEnabled(True)

        if self.active_file_info and (self.active_file_info.get("filename"), self.active_file_info.get("course") or "") == task_key:
            self.studio_browser.setHtml(f"""
                <div style="padding: 24px; color: {theme.RED};">
                    <h3 style="font-size: 20px;">❌ 提炼失败</h3>
                    <p style="font-size: 16px; margin-top: 10px;">{err_msg}</p>
                </div>
            """)

    # ── 问答交互 (Chat) ─────────────────────────────────────────────

    def _on_input_submitted(self):
        txt = self.chat_input.text().strip()
        if not txt:
            return
        self.chat_input.clear()
        self._ask_question(txt)

    def _ask_question(self, question):
        """向学术助教提问并展示流式回答。"""
        if self._reply_worker and self._reply_worker.isRunning():
            return

        fn = self.active_file_info.get("filename", "") if self.active_file_info else ""
        cn = self.active_file_info.get("course", "") if self.active_file_info else ""

        # 构造 prompt 上下文
        scope_prefix = ""
        if fn:
            scope_prefix = f"【基于课件《{fn}》" + (f" (课程: {cn})】" if cn else "】")

        full_prompt = f"{scope_prefix}{question}"

        # 添加用户问题气泡（沉稳紫灰卡片，大字号）
        user_bubble = f"""
        <div style="margin: 14px 0; text-align: right;">
            <div style="display: inline-block; background: #2B243B; color: #FFFFFF; border: 1px solid #453A5E;
                        padding: 10px 16px; border-radius: 14px; font-size: 16px; line-height: 1.6; text-align: left; max-width: 85%;">
                <b>我：</b>{QtCore.Qt.escape(question) if hasattr(QtCore.Qt, "escape") else question}
            </div>
        </div>
        """
        self.chat_browser.append(user_bubble)

        # 启动 AI 回答流
        self.btn_send.setEnabled(False)
        self.chat_input.setEnabled(False)

        worker = ReplyWorker(self.brain, full_prompt, parent=self)
        self._reply_worker = worker

        placeholder = """
        <div style="margin: 14px 0;">
            <div style="background: #171322; border: 1px solid #2C263B; border-left: 4px solid #A78BFA;
                        border-radius: 8px; padding: 14px; font-size: 16px; color: #F1EFF7; line-height: 1.7;">
                <b style="color: #A78BFA;">🐰 阿米娅：</b>
                <div style="margin-top: 8px; color: #9A92A8;">正在分析课件考点并生成解答...</div>
            </div>
        </div>
        """
        self.chat_browser.append(placeholder)

        def on_delta(delta_text):
            formatted = self._format_markdown_html(delta_text)
            self.chat_browser.append(f"""
                <div style="background: #171322; border: 1px solid #2C263B; border-left: 4px solid #A78BFA;
                            border-radius: 8px; padding: 14px; font-size: 16px; color: #F1EFF7; line-height: 1.7; margin: 10px 0;">
                    <b style="color: #A78BFA;">🐰 阿米娅：</b>
                    <div style="margin-top: 8px;">{formatted}</div>
                </div>
            """)

        def on_done(final_text):
            self.btn_send.setEnabled(True)
            self.chat_input.setEnabled(True)
            self.chat_input.setFocus()
            sb = self.chat_browser.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())

        worker.done.connect(on_done)
        worker.start()

    def _clear_chat(self):
        self.chat_browser.clear()
        self._init_chat_welcome()

    # ── 工具栏操作 ──────────────────────────────────────────────────

    def _copy_digest(self):
        txt = self.studio_browser.toPlainText()
        if txt and txt.strip():
            QtWidgets.QApplication.clipboard().setText(txt.strip())
            self.btn_copy_digest.setText("✓ 已复制")
            QtCore.QTimer.singleShot(2000, lambda: self.btn_copy_digest.setText("📋 复制考纲"))

    def _export_markdown(self):
        txt = self.studio_browser.toPlainText()
        if not txt or not txt.strip():
            QtWidgets.QMessageBox.information(self, "提示", "当前尚无考纲内容可导出")
            return

        default_name = "核心考纲.md"
        if self.active_file_info:
            default_name = f"{os.path.splitext(self.active_file_info.get('filename', ''))[0]}_考纲.md"

        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出核心考纲", default_name, "Markdown 文档 (*.md);;所有文件 (*.*)"
        )
        if save_path:
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(txt.strip())
                QtWidgets.QMessageBox.information(self, "成功", f"考纲已成功导出至：\n{save_path}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "导出失败", f"无法写入文件：{e}")

    def _on_upload_clicked(self):
        self.sig_upload_requested.emit()

    def _on_open_folder_clicked(self):
        self.sig_open_folder_requested.emit()

    def _on_course_combo_changed(self):
        self.refresh_sources(select_course=self.course_combo.currentData())

    def _on_card_digest_clicked(self, file_info):
        self._set_active_file(file_info)

    def _on_card_ask_clicked(self, file_info):
        self._set_active_file(file_info)
        fn = file_info.get("filename", "")
        self.chat_input.setText(f"请帮我梳理《{fn}》的重点考题与易错题。")
        self.chat_input.setFocus()

    def _on_card_delete_clicked(self, file_info):
        fn = file_info.get("filename", "")
        cn = file_info.get("course", "")
        reply = QtWidgets.QMessageBox.question(
            self, "确认删除",
            f"确定要从知识库中移除《{fn}》吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            kb = self.kb or getattr(self.brain, "knowledge", None)
            if kb:
                kb.delete_file(fn, course=cn)
                self.refresh_sources()

    # ── 拖拽上传支持 ────────────────────────────────────────────────

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in e.mimeData().urls() if url.isLocalFile()]
            valid = [p for p in paths if os.path.exists(p)]
            if valid and self.owner:
                e.acceptProposedAction()
                c = self.course_combo.currentData()
                pref = c if c and c not in ("__ALL__", "__GLOBAL__") else ("__GLOBAL__" if c == "__GLOBAL__" else None)
                self.owner._handle_dropped_files(valid, preferred_course=pref)
                QtCore.QTimer.singleShot(800, self.refresh_sources)
                return
        super().dropEvent(e)
