"""信息面板：课程表 / 待办与考试 / OCR 结果 的集中展示窗口。

把原来挤在气泡/浮窗里的长文本改为独立、可缩放、可滚动的置顶面板，
信息分层清晰，待办可直接在行内完成/删除。

入口：PetWindow 右键菜单（课程表/待办与考试/OCR 的查看类动作都指向本面板）。
"""

from datetime import datetime, timedelta

import html as _html

from PyQt5 import QtCore, QtGui, QtWidgets

from . import desktop_theme as apple, theme
from .schedule import _PARITY_LABEL
from .timetable import TimetableView

PAGE_SCHEDULE = "schedule"
PAGE_TASKS = "tasks"
PAGE_OCR = "ocr"
PAGE_KNOWLEDGE = "knowledge"


def _esc(t):
    return _html.escape(str(t))


def _day_head(name):
    """Markdown 风格的「标题行」（强调色加粗）。"""
    return ('<p style="margin:12px 0 2px 0;color:%s;font-size:%dpx;'
            'font-weight:700;">%s</p>'
            % (apple.ACCENT, theme.FS_XL, _esc(name)))


def _badge(text, color, *, tint="18", bold=False):
    """A pill badge tinted from `color`.

    The three course-status badges and the countdown badge all shared this
    markup with literal colours; `tint` is the fill alpha in hex-ish percent so
    the fill stays a wash of the border colour rather than a second palette.
    """
    return (
        '<span style="background:%s; color:%s; border:1px solid %s;'
        ' padding:3px %dpx; border-radius:%dpx; font-size:%dpx;%s">%s</span>'
        % (_tint(color, tint), color, color, theme.SP_2, theme.R_SM,
           theme.FS_XS, " font-weight:bold;" if bold else "", text)
    )


def _tint(hex_color, pct):
    """`hex_color` at `pct`% opacity as an rgba() string for inline HTML."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "rgba(%d,%d,%d,%.2f)" % (r, g, b, int(pct) / 100.0)


_DAY_LABELS = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "日"}


def _today_card_html(c, sched, now, week_no):
    """单节课的现代卡片 HTML，包含时段、状态徽章、教师与地点。"""
    secs = f"第 {c.sec_start}-{c.sec_end} 节"
    a = sched.sections.get(str(c.sec_start), "")
    b = sched.sections.get(str(c.sec_end), "")
    time_str = f"({a} - {b})" if a and b else (f"({a})" if a else "")

    # 判定课程状态 (进行中 / 即将开始 / 已结束)
    cur_mins = now.hour * 60 + now.minute
    status_badge = _badge("已结束", apple.SECONDARY)
    if a and ":" in a:
        try:
            parts = a.split(":")
            start_m = int(parts[0]) * 60 + int(parts[1])
            end_m = start_m + 45 * (c.sec_end - c.sec_start + 1)
            if b and ":" in b:
                eparts = b.split(":")
                end_m = int(eparts[0]) * 60 + int(eparts[1]) + 45
            if cur_mins < start_m:
                status_badge = _badge("待上课", apple.ACCENT)
            elif start_m <= cur_mins <= end_m:
                status_badge = _badge("● 正在进行中", apple.GREEN, tint="12",
                                      bold=True)
        except Exception:
            pass

    room_str = f"地点：{_esc(c.room)}" if c.room else "地点待定"
    teacher_str = f"教师：{_esc(c.teacher)}" if c.teacher else ""
    parity_str = {"all": "", "odd": " (仅单周)", "even": " (仅双周)"}.get(c.parity, "")
    weeks_str = f"第 {c.week_start}-{c.week_end} 周{parity_str}"

    meta_parts = [room_str]
    if teacher_str:
        meta_parts.append(teacher_str)
    meta_parts.append(weeks_str)
    meta_line = " &nbsp;·&nbsp; ".join(meta_parts)

    return f"""
        <div style="background:{apple.SURFACE}; border:1px solid {apple.BORDER};
                border-radius:12px; padding:{theme.SP_4}px {theme.SP_5}px;
                margin:{theme.SP_2}px 0;">
        <table width="100%" border="0" cellpadding="0" cellspacing="0">
            <tr>
                <td align="left"><span style="color:{apple.ACCENT}; font-weight:600; font-size:{theme.FS_SM}px;">{secs} {time_str}</span></td>
                <td align="right">{status_badge}</td>
            </tr>
        </table>
        <div style="color:{apple.TEXT}; font-size:{theme.FS_LG}px; font-weight:600; margin:8px 0;">{_esc(c.name)}</div>
        <div style="color:{apple.SECONDARY}; font-size:{theme.FS_XS}px;">{meta_line}</div>
    </div>
    """


def _schedule_html(which, sched, week_no):
    """今天/下一节课的富文本卡片流展示。"""
    now = datetime.now()
    if which == "today":
        courses = sched.today(week_no)
        today_date_str = f"{now.month}月{now.day}日 周{_DAY_LABELS.get(now.isoweekday(), '')}"
        if not courses:
            return f"""
            <div style="text-align:center; padding:50px 20px;">
            <div style="color:{apple.ACCENT}; font-size:{theme.FS_2XL}px; font-weight:600; margin-bottom:{theme.SP_3}px;">今天</div>
            <div style="color:{apple.TEXT}; font-size:{theme.FS_LG}px; font-weight:600; margin-bottom:{theme.SP_2}px;">今日无课 · 自由自习</div>
            <div style="color:{apple.SECONDARY}; font-size:{theme.FS_SM}px; line-height:1.6;">
                    今天 ({today_date_str}) 没有排课，博士可以好好休息或自习备考~<br/>
                    点击上方「<b>本周课表</b>」可浏览全周日程，或点击「<b>+ 录入课程</b>」手动添加。
                </div>
            </div>
            """
        head = f"""
        <div style="margin-bottom:{theme.SP_3}px;">
            <span style="font-size:{theme.FS_LG}px; font-weight:600; color:{apple.TEXT};">今日日程</span>
            <span style="font-size:{theme.FS_SM}px; color:{apple.SECONDARY}; margin-left:{theme.SP_2}px;">{today_date_str} · 共 {len(courses)} 门课程</span>
        </div>
        """
        cards = "".join(_today_card_html(c, sched, now, week_no) for c in courses)
        return head + cards

    # which == "next"
    nxt = sched.next_class()
    if not nxt:
        return f"""
        <div style="text-align:center; padding:50px 20px;">
            <div style="color:{apple.GREEN}; font-size:{theme.FS_2XL}px; font-weight:600; margin-bottom:{theme.SP_3}px;">轻松一点</div>
            <div style="color:{apple.TEXT}; font-size:{theme.FS_LG}px; font-weight:600; margin-bottom:{theme.SP_2}px;">本周没有剩余课程</div>
            <div style="color:{apple.SECONDARY}; font-size:{theme.FS_SM}px;">博士可以好好享受空闲时光！</div>
        </div>
        """
    c, weekday, _, start = nxt
    mins = max(0, int((start - now).total_seconds() // 60))
    time_badge = f"{mins} 分钟后" if mins > 0 else "即将开始"
    where = f"地点：{_esc(c.room)}" if c.room else "地点待定"
    teacher = f"教师：{_esc(c.teacher)}" if c.teacher else ""
    meta_line = " &nbsp;·&nbsp; ".join(x for x in [where, teacher, f"周{_DAY_LABELS.get(weekday, '')} 第 {c.sec_start}-{c.sec_end} 节"] if x)

    return f"""
    <div style="margin-bottom:{theme.SP_4}px;">
        <span style="font-size:{theme.FS_LG}px; font-weight:600; color:{apple.TEXT};">下一节课安排</span>
    </div>
    <div style="background:{apple.SURFACE}; border:1px solid {apple.BORDER};
                border-radius:12px; padding:{theme.SP_5}px {theme.SP_5}px;">
        <table width="100%" border="0" cellpadding="0" cellspacing="0">
            <tr>
                <td align="left"><span style="color:{apple.ACCENT}; font-size:{theme.FS_SM}px; font-weight:600;">开课时刻：{start.strftime('%H:%M')}</span></td>
                <td align="right">{_badge("距离上课 " + time_badge, apple.AMBER, tint="12", bold=True)}</td>
            </tr>
        </table>
        <div style="color:{apple.TEXT}; font-size:{theme.FS_XL}px; font-weight:600; margin:10px 0;">{_esc(c.name)}</div>
        <div style="color:{apple.SECONDARY}; font-size:{theme.FS_SM}px;">{meta_line}</div>
    </div>
    """


_QSS = """
QWidget#PanelRoot {
    background:%(bg)s; color:%(text)s; font-family:%(font)s; font-size:%(fs_sm)dpx;
}
QWidget#TitleBar { background:%(surface)s; border-bottom:1px solid %(border)s; }
QLabel#BrandMark {
    background:%(accent)s; color:%(on_accent)s; border-radius:10px;
    font-size:14px; font-weight:700;
}
QLabel#TitleText { color:%(text)s; font-size:16px; font-weight:600; }
QLabel#TitleSub { color:%(dim)s; font-size:%(fs_xs)dpx; }
QPushButton#CloseBtn, QPushButton#MaxBtn {
    background:transparent; color:%(dim)s; border:none; border-radius:9px;
    font-size:18px; min-width:34px; min-height:34px; padding:0;
}
QPushButton#CloseBtn:hover, QPushButton#MaxBtn:hover {
    background:%(hover)s; color:%(text)s;
}
QFrame#Sidebar { background:%(sidebar)s; border:none; border-radius:14px; }
QLabel#SidebarHeading { color:%(dim)s; font-size:%(fs_xs)dpx; font-weight:600; padding:4px 8px; }
QLabel#SidebarFooter { color:%(mute)s; font-size:%(fs_xs)dpx; padding:10px 8px 4px 8px; }
QFrame#ContentSurface {
    background:%(surface)s; border:1px solid %(border)s; border-radius:16px;
}
QLabel#PageTitle { color:%(text)s; font-size:%(fs_2xl)dpx; font-weight:600; }
QLabel#PageSubtitle { color:%(dim)s; font-size:%(fs_sm)dpx; }
QFrame#PageDivider { background:%(border)s; border:none; max-height:1px; }
QFrame#StatCard, QFrame#OcrCard, QFrame#KnowledgeFileCard {
    background:%(surface)s; border:1px solid %(border)s; border-radius:12px;
}
QFrame#KnowledgeFileCard { padding:4px; }
QLabel#StatLabel { color:%(dim)s; font-size:%(fs_sm)dpx; }
QLabel#StatValue { color:%(text)s; font-size:%(fs_2xl)dpx; font-weight:700; }
QLabel#CardTitle { color:%(text)s; font-size:%(fs_md)dpx; font-weight:600; }
QLabel#OcrStatus {
    color:%(accent)s; background:%(select_bg)s; border:1px solid %(border)s;
    border-radius:10px; padding:7px 12px; font-size:%(fs_sm)dpx; font-weight:600;
}
QLabel#FileBadge {
    color:%(accent)s; background:%(select_bg)s; border:1px solid %(border)s;
    border-radius:8px; padding:5px 8px; font-size:%(fs_xs)dpx; font-weight:700;
}
QListWidget#Nav {
    background:transparent; border:none; font-size:%(fs_sm)dpx; padding-top:4px;
}
QListWidget#Nav::item {
    min-height:22px; padding:9px 10px; border-radius:9px; margin:2px 0;
}
QListWidget#Nav::item:selected {
    background:%(select_bg)s; color:%(accent)s; font-weight:600;
}
QListWidget#Nav::item:hover:!selected {
    background:%(hover)s;
}
QTextBrowser, QPlainTextEdit {
    background:%(surface)s; color:%(text)s; border:1px solid %(border)s;
    border-radius:10px; font-size:%(fs_md)dpx; padding:12px;
}
QPlainTextEdit:focus { border:1px solid %(accent)s; }
QTableWidget {
    background:%(surface)s; alternate-background-color:%(field)s;
    color:%(text)s; border:none; gridline-color:%(border)s;
    font-size:%(fs_sm)dpx; selection-background-color:%(select_bg)s;
    selection-color:%(text)s; outline:0; border-radius:10px;
}
QTableWidget::item { padding:10px 10px; border-bottom:1px solid %(border)s; }
QHeaderView { background:%(field)s; border:none; }
QHeaderView::section {
    background:%(field)s; color:%(dim)s; border:none;
    border-bottom:1px solid %(border)s; padding:10px 8px;
    font-size:%(fs_xs)dpx; font-weight:600;
}
QSplitter::handle { background:%(border)s; }
QSplitter::handle:hover { background:%(accent)s; }
QScrollArea { background:transparent; border:none; }
QScrollBar:vertical { background:transparent; width:9px; margin:3px 2px; }
QScrollBar::handle:vertical { background:%(scroll)s; border-radius:4px; min-height:28px; }
QScrollBar::handle:vertical:hover { background:%(dim)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }
QPushButton {
    background:%(field)s; color:%(text)s; border:1px solid %(border)s;
    border-radius:9px; padding:0 13px; min-height:34px; font-size:%(fs_sm)dpx;
}
QPushButton:hover { background:%(hover)s; border-color:%(border_strong)s; }
QPushButton:pressed { background:%(pressed)s; }
QPushButton:disabled { color:%(mute)s; background:%(field)s; border-color:%(border)s; }
QPushButton#PrimaryBtn {
    background:%(accent)s; color:%(on_accent)s;
    border:1px solid %(accent)s; font-weight:600;
}
QPushButton#PrimaryBtn:hover { background:%(accent_hover)s; border-color:%(accent_hover)s; }
QPushButton#PrimaryBtn:pressed { background:%(accent_deep)s; }
QPushButton#ActionBtn {
    background:%(select_bg)s; color:%(accent)s;
    border:1px solid transparent; font-weight:600;
}
QPushButton#ActionBtn:hover { background:%(hover)s; border-color:%(border_strong)s; }
QPushButton#WeekStartBtn { background:%(field)s; color:%(dim)s; }
QToolTip { background:%(text)s; color:%(surface)s; border:none; padding:6px 8px; }
""" % {
    "bg": apple.BG, "surface": apple.SURFACE, "sidebar": apple.SIDEBAR,
    "field": apple.FIELD, "border": apple.BORDER,
    "border_strong": apple.BORDER_STRONG, "scroll": apple.BORDER_STRONG,
    "text": apple.TEXT, "dim": apple.SECONDARY, "mute": apple.MUTED,
    "accent": apple.ACCENT, "accent_hover": apple.ACCENT_HOVER,
    "accent_deep": apple.ACCENT_DEEP, "on_accent": apple.ON_ACCENT,
    "select_bg": apple.SELECT_BG, "hover": apple.HOVER,
    "pressed": apple.PRESSED, "font": apple.FONT,
    "fs_xs": theme.FS_XS,
    "fs_sm": theme.FS_SM, "fs_md": theme.FS_MD,
    "fs_2xl": theme.FS_2XL,
}


# ── Fragments for widgets styled outside _QSS ────────────────────────────
# The knowledge-base tab styles most of its widgets individually; these were
# all literal cyan/slate before.
_S_SUNK = ("background: %s; border: 1px solid %s; border-radius: 10px;"
           % (apple.FIELD, apple.BORDER))
_S_ACCENT_LABEL = ("color: %s; font-size: %dpx; font-weight: bold;"
                   % (apple.ACCENT, theme.FS_MD))
_S_DIM_LABEL = ("color: %s; font-size: %dpx; font-weight: bold;"
                % (apple.SECONDARY, theme.FS_SM))
_S_MUTE_TIP = "color: %s; font-size: %dpx;" % (apple.MUTED, theme.FS_XS)
_S_BTN_PRIMARY = (
    "QPushButton{background:%s;color:%s;font-weight:600;padding:0 %dpx;"
    "min-height:36px;border-radius:9px;border:1px solid %s;}"
    "QPushButton:hover{background:%s;}"
    "QPushButton:pressed{background:%s;color:#FFFFFF;}"
    % (apple.ACCENT, apple.ON_ACCENT, theme.SP_4, apple.ACCENT,
       apple.ACCENT_HOVER, apple.ACCENT_DEEP))
_S_BTN_SECONDARY = (
    "QPushButton{background:%s;color:%s;border:1px solid %s;padding:0 %dpx;"
    "min-height:34px;border-radius:9px;}"
    "QPushButton:hover{background:%s;border-color:%s;}"
    % (apple.FIELD, apple.TEXT, apple.BORDER, theme.SP_3,
       apple.HOVER, apple.BORDER_STRONG))
_S_COMBO = (
    "QComboBox{background:%s;color:%s;border:1px solid %s;padding:5px %dpx;"
    "border-radius:8px;font-size:%dpx;min-width:180px;}"
    "QComboBox:focus{border:1px solid %s;}"
    % (apple.FIELD, apple.TEXT, apple.BORDER, theme.SP_3,
       theme.FS_SM, apple.ACCENT))


def _s_pill(color):
    """Small tinted pill button (ask / delete / suggestion chips)."""
    return ("QPushButton{background:%s;color:%s;border:1px solid %s;"
            "padding:3px %dpx;border-radius:%dpx;font-size:%dpx;}"
            "QPushButton:hover{background:%s;color:%s;}"
            % (_tint(color, "16"), color, color, theme.SP_2, theme.R_SM,
               theme.FS_XS, color, apple.ON_ACCENT))


class InfoPanel(QtWidgets.QWidget):
    """课程表 / 待办与考试 / OCR 结果的集中面板（置顶、可缩放、可拖动）。"""

    def __init__(self, owner):
        super().__init__(None)
        self.owner = owner          # PetWindow（数据源：schedule / tasks）
        self._drag = None
        self.setWindowTitle("阿米娅桌面助手")
        self.setWindowFlags(
            QtCore.Qt.Window
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        screen = QtWidgets.QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        width = min(1480, int(available.width() * 0.94)) if available else 1360
        height = min(1020, int(available.height() * 0.94)) if available else 900
        width = max(960, width)
        height = max(640, height)
        self.setMinimumSize(min(1120, width), min(720, height))
        self.resize(width, height)
        self.setAcceptDrops(True)
        self.setStyleSheet(_QSS)
        self.setObjectName("PanelRoot")
        self._build()
        if hasattr(self.owner, "sig_digest_progress"):
            self.owner.sig_digest_progress.connect(self._on_digest_progress)
        if hasattr(self.owner, "sig_digest_finished"):
            self.owner.sig_digest_finished.connect(self._on_digest_finished)

    # ── UI ─────────────────────────────────────────────────────────

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 简洁标题栏：品牌标识、窗口名称与系统式窗口操作。
        bar = QtWidgets.QWidget(self)
        bar.setObjectName("TitleBar")
        bar.setFixedHeight(62)
        bar_layout = QtWidgets.QHBoxLayout(bar)
        bar_layout.setContentsMargins(22, 0, 16, 0)
        bar_layout.setSpacing(10)

        brand = QtWidgets.QLabel("A", bar)
        brand.setObjectName("BrandMark")
        brand.setAlignment(QtCore.Qt.AlignCenter)
        brand.setFixedSize(34, 34)
        bar_layout.addWidget(brand)

        title_group = QtWidgets.QWidget(bar)
        title_group_layout = QtWidgets.QVBoxLayout(title_group)
        title_group_layout.setContentsMargins(0, 0, 0, 0)
        title_group_layout.setSpacing(1)
        title = QtWidgets.QLabel("阿米娅桌面助手", title_group)
        title.setObjectName("TitleText")
        sub = QtWidgets.QLabel("学习与日常安排", title_group)
        sub.setObjectName("TitleSub")
        title_group_layout.addWidget(title)
        title_group_layout.addWidget(sub)
        bar_layout.addWidget(title_group)
        bar_layout.addStretch(1)

        self.btn_max = QtWidgets.QPushButton("□", bar)
        self.btn_max.setObjectName("MaxBtn")
        self.btn_max.setFixedSize(34, 34)
        self.btn_max.setToolTip("最大化")
        self.btn_max.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_max.clicked.connect(self._toggle_maximize)

        close = QtWidgets.QPushButton("×", bar)
        close.setObjectName("CloseBtn")
        close.setFixedSize(34, 34)
        close.setToolTip("关闭")
        close.setCursor(QtCore.Qt.PointingHandCursor)
        close.clicked.connect(self.hide)

        bar_layout.addWidget(self.btn_max)
        bar_layout.addWidget(close)
        root.addWidget(bar)

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(18, 16, 18, 18)
        body.setSpacing(16)
        root.addLayout(body, 1)

        # 轻量侧边栏，导航项保留原有页面顺序与信号行为。
        sidebar = QtWidgets.QFrame(self)
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(194)
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 14, 12, 12)
        sidebar_layout.setSpacing(6)
        sidebar_heading = QtWidgets.QLabel("工作区", sidebar)
        sidebar_heading.setObjectName("SidebarHeading")
        sidebar_layout.addWidget(sidebar_heading)

        self.nav = QtWidgets.QListWidget(sidebar)
        self.nav.setObjectName("Nav")
        self.nav.setSpacing(3)
        self.nav.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.nav.addItems(("▦   课程表", "✓   待办与考试", "⌕   OCR 结果", "▤   课程知识库"))
        self.nav.currentRowChanged.connect(self._switch_page)
        sidebar_layout.addWidget(self.nav, 1)

        sidebar_footer = QtWidgets.QLabel("罗德岛 · 学习空间", sidebar)
        sidebar_footer.setObjectName("SidebarFooter")
        sidebar_layout.addWidget(sidebar_footer)
        body.addWidget(sidebar)

        # 页面置于白色内容面板内，标题、副标题在切换时保持一致。
        content = QtWidgets.QFrame(self)
        content.setObjectName("ContentSurface")
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 22)
        content_layout.setSpacing(12)

        page_heading = QtWidgets.QVBoxLayout()
        page_heading.setContentsMargins(0, 0, 0, 0)
        page_heading.setSpacing(4)
        self.page_title = QtWidgets.QLabel("课程表", content)
        self.page_title.setObjectName("PageTitle")
        self.page_subtitle = QtWidgets.QLabel("查看每周安排，轻松规划学习节奏。", content)
        self.page_subtitle.setObjectName("PageSubtitle")
        page_heading.addWidget(self.page_title)
        page_heading.addWidget(self.page_subtitle)
        content_layout.addLayout(page_heading)

        divider = QtWidgets.QFrame(content)
        divider.setObjectName("PageDivider")
        divider.setFrameShape(QtWidgets.QFrame.HLine)
        content_layout.addWidget(divider)

        self.stack = QtWidgets.QStackedWidget(content)
        self.stack.setObjectName("PageStack")
        self.stack.addWidget(self._build_schedule_page())
        self.stack.addWidget(self._build_tasks_page())
        self.stack.addWidget(self._build_ocr_page())
        self.stack.addWidget(self._build_knowledge_page())
        content_layout.addWidget(self.stack, 1)
        body.addWidget(content, 1)

        self.nav.setCurrentRow(0)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.btn_max.setText("□")
            self.btn_max.setToolTip("最大化")
        else:
            self.showMaximized()
            self.btn_max.setText("❐")
            self.btn_max.setToolTip("还原")

    def _build_schedule_page(self):
        page = QtWidgets.QWidget(self)
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        btns = QtWidgets.QHBoxLayout()
        btns.setSpacing(6)
        self.btn_week = QtWidgets.QPushButton("周视图", page)
        self.btn_week_list = QtWidgets.QPushButton("详细周表", page)
        self.btn_today = QtWidgets.QPushButton("今日日程", page)
        self.btn_next = QtWidgets.QPushButton("下一节课", page)
        self.btn_week.clicked.connect(lambda: self.show_schedule("week"))
        self.btn_week_list.clicked.connect(lambda: self.show_schedule("list"))
        self.btn_today.clicked.connect(lambda: self.show_schedule("today"))
        self.btn_next.clicked.connect(lambda: self.show_schedule("next"))
        for b in (self.btn_week, self.btn_week_list, self.btn_today, self.btn_next):
            btns.addWidget(b)
        btns.addStretch(1)

        # 快捷功能按钮（右侧）
        self.btn_add_course = QtWidgets.QPushButton("+ 录入课程", page)
        self.btn_add_course.setObjectName("ActionBtn")
        self.btn_add_course.clicked.connect(lambda: self._on_empty_slot_clicked(1, 1))

        self.btn_import_schedule = QtWidgets.QPushButton("导入课表", page)
        self.btn_import_schedule.setObjectName("ActionBtn")
        self.btn_import_schedule.clicked.connect(self._on_import_schedule)

        self.btn_ai_analysis = QtWidgets.QPushButton("学情分析", page)
        self.btn_ai_analysis.setObjectName("PrimaryBtn")
        self.btn_ai_analysis.clicked.connect(self._on_ai_schedule_analysis)

        for b in (self.btn_add_course, self.btn_import_schedule, self.btn_ai_analysis):
            btns.addWidget(b)

        lay.addLayout(btns)

        # 周导航：上一周 / 第 N 周 / 回到本周 / 下一周（仅本周视图显示）
        self._display_week = 1
        self._max_week = 20
        nav = QtWidgets.QHBoxLayout()
        nav.setSpacing(10)
        self.btn_prev_week = QtWidgets.QPushButton("‹ 上一周", page)
        self.week_label = QtWidgets.QLabel("第 1 周", page)
        self.week_label.setAlignment(QtCore.Qt.AlignCenter)
        self.week_label.setStyleSheet(_S_ACCENT_LABEL)
        self.btn_cur_week = QtWidgets.QPushButton("回到本周", page)
        self.btn_next_week = QtWidgets.QPushButton("下一周 ›", page)
        self.btn_week_start = QtWidgets.QPushButton(page)
        self.btn_week_start.setObjectName("WeekStartBtn")
        self.btn_week_start.setToolTip("切换周课表起始日：周日 / 周一")

        self.btn_prev_week.clicked.connect(self._prev_week)
        self.btn_cur_week.clicked.connect(self._go_current_week)
        self.btn_next_week.clicked.connect(self._next_week)
        self.btn_week_start.clicked.connect(self._toggle_week_start_day)

        nav.addWidget(self.btn_prev_week)
        nav.addWidget(self.week_label, 1)
        nav.addWidget(self.btn_cur_week)
        nav.addWidget(self.btn_next_week)
        nav.addWidget(self.btn_week_start)
        self.week_nav_widget = QtWidgets.QWidget(page)
        self.week_nav_widget.setLayout(nav)
        lay.addWidget(self.week_nav_widget)

        self.sched_view = QtWidgets.QTextBrowser(page)
        self.sched_view.setOpenExternalLinks(False)
        self.sched_view.setStyleSheet(_S_SUNK + " padding: %dpx;" % theme.SP_3)

        # 周课表可视化色块视图
        self.timetable = TimetableView(page)
        self.timetable.sig_course_clicked.connect(self._on_course_clicked)
        self.timetable.sig_empty_slot_clicked.connect(self._on_empty_slot_clicked)

        self.timetable_area = QtWidgets.QScrollArea(page)
        self.timetable_area.setWidget(self.timetable)
        self.timetable_area.setWidgetResizable(True)
        self.timetable_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.timetable_area.setStyleSheet(
            "QScrollArea{background:%s;border:none;}"
            "QScrollArea>QWidget>QWidget{background:%s;}"
            % (apple.SURFACE, apple.SURFACE))
        self.sched_stack = QtWidgets.QStackedWidget(page)
        self.sched_stack.addWidget(self.timetable_area)  # 0: 本周（色块）
        self.sched_stack.addWidget(self.sched_view)      # 1: 今天 / 下一节
        self.week_list_area = QtWidgets.QScrollArea(page)
        self.week_list_area.setWidgetResizable(True)
        self.week_list_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.week_list_area.setObjectName("WeekListArea")
        self.week_list_area.setStyleSheet(
            f"QScrollArea{{background:{apple.SURFACE};border:none;}}"
            f"QScrollArea>QWidget>QWidget{{background:{apple.SURFACE};}}")
        self.week_list_content = QtWidgets.QWidget(self.week_list_area)
        self.week_list_content.setObjectName("WeekListContent")
        self.week_list_content.setAutoFillBackground(True)
        self.week_list_content.setStyleSheet(f"background:{apple.SURFACE};")
        self.week_list_layout = QtWidgets.QVBoxLayout(self.week_list_content)
        self.week_list_layout.setContentsMargins(4, 4, 10, 12)
        self.week_list_layout.setSpacing(14)
        self.week_list_area.setWidget(self.week_list_content)
        self.sched_stack.addWidget(self.week_list_area)  # 2: 完整信息列表
        lay.addWidget(self.sched_stack, 1)
        return page

    def _build_tasks_page(self):
        page = QtWidgets.QWidget(self)
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        stats_row = QtWidgets.QHBoxLayout()
        stats_row.setSpacing(12)
        self.task_stat_values = {}
        for key, label in (("pending", "待完成"),
                           ("exams", "近期考试"),
                           ("week", "本周安排")):
            card = QtWidgets.QFrame(page)
            card.setObjectName("StatCard")
            card_layout = QtWidgets.QVBoxLayout(card)
            card_layout.setContentsMargins(16, 12, 16, 12)
            card_layout.setSpacing(3)
            title = QtWidgets.QLabel(label, card)
            title.setObjectName("StatLabel")
            value = QtWidgets.QLabel("0", card)
            value.setObjectName("StatValue")
            card_layout.addWidget(title)
            card_layout.addWidget(value)
            stats_row.addWidget(card, 1)
            self.task_stat_values[key] = value
        lay.addLayout(stats_row)

        self.task_table = QtWidgets.QTableWidget(0, 5, page)
        self.task_table.setHorizontalHeaderLabels(
            ["状态", "事项", "课程", "截止时间", "剩余"])
        self.task_table.setAlternatingRowColors(True)
        self.task_table.setShowGrid(False)
        self.task_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows)
        self.task_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection)
        self.task_table.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers)
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.verticalHeader().setDefaultSectionSize(54)
        header = self.task_table.horizontalHeader()
        header.setMinimumHeight(42)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        for col in (0, 2, 3, 4):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
        self.task_table.itemDoubleClicked.connect(lambda *_: self._toggle_done())
        lay.addWidget(self.task_table, 1)

        btns = QtWidgets.QHBoxLayout()
        self.btn_done = QtWidgets.QPushButton("标记完成", page)
        self.btn_del = QtWidgets.QPushButton("删除", page)
        self.btn_refresh = QtWidgets.QPushButton("刷新", page)
        self.btn_done.clicked.connect(self._toggle_done)
        self.btn_del.clicked.connect(self._remove_task)
        self.btn_refresh.clicked.connect(self.refresh_tasks)
        for b in (self.btn_done, self.btn_del):
            btns.addWidget(b)
        btns.addStretch(1)
        btns.addWidget(self.btn_refresh)
        lay.addLayout(btns)
        return page

    def _build_ocr_page(self):
        page = QtWidgets.QWidget(self)
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        status_row = QtWidgets.QHBoxLayout()
        self.ocr_status = QtWidgets.QLabel("暂无 OCR 结果。", page)
        self.ocr_status.setObjectName("OcrStatus")
        self.ocr_status.setStyleSheet(
            "color:%s;font-size:%dpx;" % (apple.ACCENT, theme.FS_SM))
        status_row.addWidget(self.ocr_status)
        status_row.addStretch(1)
        lay.addLayout(status_row)

        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal, page)
        split.setHandleWidth(10)
        self.ocr_source_card = QtWidgets.QFrame(split)
        self.ocr_source_card.setObjectName("OcrCard")
        source_layout = QtWidgets.QVBoxLayout(self.ocr_source_card)
        source_layout.setContentsMargins(16, 14, 16, 14)
        source_layout.setSpacing(10)
        source_title = QtWidgets.QLabel("原文（识别结果）", self.ocr_source_card)
        source_title.setObjectName("CardTitle")
        source_layout.addWidget(source_title)
        self.ocr_source = QtWidgets.QPlainTextEdit(self.ocr_source_card)
        self.ocr_source.setObjectName("OcrText")

        self.ocr_result_card = QtWidgets.QFrame(split)
        self.ocr_result_card.setObjectName("OcrCard")
        result_layout = QtWidgets.QVBoxLayout(self.ocr_result_card)
        result_layout.setContentsMargins(16, 14, 16, 14)
        result_layout.setSpacing(10)
        result_title = QtWidgets.QLabel("译文 / 总结", self.ocr_result_card)
        result_title.setObjectName("CardTitle")
        result_layout.addWidget(result_title)
        self.ocr_result = QtWidgets.QPlainTextEdit(self.ocr_result_card)
        self.ocr_result.setObjectName("OcrText")

        for w in (self.ocr_source, self.ocr_result):
            w.setReadOnly(True)
            w.setPlaceholderText("")
            w.setStyleSheet(
                "background:transparent;border:none;padding:2px;"
                "font-size:%dpx;color:%s;" % (theme.FS_MD, apple.TEXT))
        self.ocr_source.setPlaceholderText("原文（识别结果）")
        self.ocr_result.setPlaceholderText("译文 / 总结")
        source_layout.addWidget(self.ocr_source, 1)
        result_layout.addWidget(self.ocr_result, 1)
        split.addWidget(self.ocr_source_card)
        split.addWidget(self.ocr_result_card)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, 1)
        return page

    def _build_knowledge_page(self):
        page = QtWidgets.QWidget(self)
        page.setAcceptDrops(True)
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(4, 4, 8, 8)
        lay.setSpacing(14)

        heading = QtWidgets.QHBoxLayout()
        heading.setSpacing(14)
        icon_lbl = QtWidgets.QLabel("▤", page)
        icon_lbl.setAlignment(QtCore.Qt.AlignCenter)
        icon_lbl.setFixedSize(48, 48)
        icon_lbl.setStyleSheet(
            "background:%s;color:%s;border-radius:14px;font-size:23px;font-weight:700;"
            % (apple.SELECT_BG, apple.ACCENT))
        heading.addWidget(icon_lbl)

        title_stack = QtWidgets.QVBoxLayout()
        title_stack.setSpacing(4)
        title = QtWidgets.QLabel("课程知识库", page)
        title.setStyleSheet(
            f"font-size:{theme.FS_XL}px;font-weight:700;color:{apple.TEXT};")
        desc = QtWidgets.QLabel(
            "整理讲义资料，在网页工作台中阅读、提炼与复习。", page)
        desc.setStyleSheet(
            f"font-size:{theme.FS_SM}px;color:{apple.SECONDARY};")
        title_stack.addWidget(title)
        title_stack.addWidget(desc)
        heading.addLayout(title_stack, 1)

        self._btn_open_web = QtWidgets.QPushButton("打开课程知识库", page)
        self._btn_open_web.setObjectName("PrimaryBtn")
        self._btn_open_web.setMinimumHeight(42)
        self._btn_open_web.clicked.connect(lambda: self._launch_web_workspace())
        heading.addWidget(self._btn_open_web)
        lay.addLayout(heading)

        stats_row = QtWidgets.QHBoxLayout()
        stats_row.setSpacing(12)
        self.kw_stat_values = {}
        for key, label in (("courses", "覆盖课程"),
                           ("files", "已收录课件"),
                           ("chunks", "知识片段")):
            card = QtWidgets.QFrame(page)
            card.setObjectName("StatCard")
            card_layout = QtWidgets.QVBoxLayout(card)
            card_layout.setContentsMargins(16, 12, 16, 12)
            card_layout.setSpacing(3)
            caption = QtWidgets.QLabel(label, card)
            caption.setObjectName("StatLabel")
            value = QtWidgets.QLabel("0", card)
            value.setObjectName("StatValue")
            card_layout.addWidget(caption)
            card_layout.addWidget(value)
            stats_row.addWidget(card, 1)
            self.kw_stat_values[key] = value
        lay.addLayout(stats_row)

        self.kw_stat_card = QtWidgets.QFrame(page)
        self.kw_stat_card.setObjectName("KnowledgeStatus")
        self.kw_stat_card.setStyleSheet(
            f"background:{apple.FIELD};border:1px solid {apple.BORDER};"
            f"border-radius:{theme.R_MD}px;")
        status_layout = QtWidgets.QHBoxLayout(self.kw_stat_card)
        status_layout.setContentsMargins(14, 8, 14, 8)
        self.kw_stat_lbl = QtWidgets.QLabel("正在同步本地知识库数据…", self.kw_stat_card)
        self.kw_stat_lbl.setWordWrap(True)
        self.kw_stat_lbl.setStyleSheet(
            f"font-size:{theme.FS_SM}px;color:{apple.SECONDARY};")
        status_layout.addWidget(self.kw_stat_lbl, 1)
        self.kw_btn_folder = QtWidgets.QPushButton("本地课件文件夹", self.kw_stat_card)
        self.kw_btn_folder.clicked.connect(self._open_knowledge_folder)
        status_layout.addWidget(self.kw_btn_folder)
        self.kw_btn_refresh = QtWidgets.QPushButton("刷新统计", self.kw_stat_card)
        self.kw_btn_refresh.clicked.connect(lambda: self.refresh_knowledge_page())
        status_layout.addWidget(self.kw_btn_refresh)
        lay.addWidget(self.kw_stat_card)

        files_heading = QtWidgets.QHBoxLayout()
        self.kw_recent_title = QtWidgets.QLabel("最近添加的课件", page)
        self.kw_recent_title.setObjectName("CardTitle")
        files_heading.addWidget(self.kw_recent_title)
        files_heading.addStretch(1)
        lay.addLayout(files_heading)

        self.kw_files_scroll = QtWidgets.QScrollArea(page)
        self.kw_files_scroll.setWidgetResizable(True)
        self.kw_files_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.kw_files_container = QtWidgets.QWidget(self.kw_files_scroll)
        self.kw_files_layout = QtWidgets.QVBoxLayout(self.kw_files_container)
        self.kw_files_layout.setContentsMargins(2, 2, 8, 8)
        self.kw_files_layout.setSpacing(9)
        self.kw_files_layout.addStretch(1)
        self.kw_files_scroll.setWidget(self.kw_files_container)
        lay.addWidget(self.kw_files_scroll, 1)

        self._render_knowledge_files([])
        return page

    # ── 行为 ───────────────────────────────────────────────────────

    def _switch_page(self, row):
        self.stack.setCurrentIndex(row)
        titles = (
            ("课程表", "查看每周安排，轻松规划学习节奏。"),
            ("待办与考试", "把重要事项排清楚，留出专注时间。"),
            ("OCR 结果", "查看截图识别、翻译与总结内容。"),
            ("课程知识库", "整理讲义资料，随时回顾课程重点。"),
        )
        if 0 <= row < len(titles):
            self.page_title.setText(titles[row][0])
            self.page_subtitle.setText(titles[row][1])
        if row == 0:
            self.show_schedule("list")
        elif row == 1:
            self.refresh_tasks()
        elif row == 3:
            self.refresh_knowledge_page()

    def show_schedule(self, which):
        """展示课程表：周列表展示完整信息，周视图显示时间网格。"""
        s = self.owner.schedule
        self.nav.setCurrentRow(0)
        self.stack.setCurrentIndex(0)

        # 选项卡高亮样式联动
        active_qss = ("background: %s; color: %s; font-weight: 600;"
                      " border: 1px solid %s;" % (apple.ACCENT, apple.ON_ACCENT, apple.ACCENT))
        self.btn_week.setStyleSheet(active_qss if which == "week" else "")
        self.btn_week_list.setStyleSheet(active_qss if which == "list" else "")
        self.btn_today.setStyleSheet(active_qss if which == "today" else "")
        self.btn_next.setStyleSheet(active_qss if which == "next" else "")

        if not s.courses:
            self._schedule_mode = which
            self.week_nav_widget.hide()
            self.sched_stack.setCurrentWidget(self.sched_view)
            self.sched_view.setHtml(f"""
            <div style="text-align:center; padding:60px 20px;">
                <div style="color:{apple.ACCENT}; font-size:{theme.FS_2XL}px; font-weight:600; margin-bottom:{theme.SP_3}px;">开始规划</div>
                <div style="color:{apple.TEXT}; font-size:{theme.FS_LG}px; font-weight:600; margin-bottom:{theme.SP_2}px;">暂无课程安排</div>
                <div style="color:{apple.SECONDARY}; font-size:{theme.FS_SM}px; line-height:1.6;">
                    点击右上角「<b>+ 录入课程</b>」手动规划课程，或点击「<b>导入课表</b>」导入教务 JSON。<br/>
                    阿米娅将根据您的课表作息提供提醒与学情分析！
                </div>
            </div>
            """)
            return

        if which in ("week", "list"):
            # 两种周视图共用周导航；切换表现形式时保留当前浏览周。
            if getattr(self, "_schedule_mode", None) not in ("week", "list"):
                s_week = s.week_no() or 0
                self._display_week = s_week if s_week >= 1 else 1
            self._schedule_mode = which
            self._max_week = max((c.week_end for c in s.courses), default=20)
            self._render_week()
            return

        self._schedule_mode = which
        self.week_nav_widget.hide()
        week_no = s.week_no()
        html = _schedule_html(which, s, week_no)
        self.sched_stack.setCurrentWidget(self.sched_view)
        self.sched_view.setHtml(html)
        self.sched_view.moveCursor(QtGui.QTextCursor.Start)

    # ── 周导航与课程交互 ─────────────────────────────────────────────

    def _render_week(self):
        s = self.owner.schedule
        self.timetable.set_data(s, self._display_week)
        if self._schedule_mode == "list":
            self._render_week_list()
            self.sched_stack.setCurrentWidget(self.week_list_area)
        else:
            self.sched_stack.setCurrentWidget(self.timetable_area)
        self.week_nav_widget.show()
        real_week = s.week_no() or 0
        tag = " (本周)" if self._display_week == real_week else ""
        self.week_label.setText(f"第 {self._display_week} 周{tag}")
        self.btn_prev_week.setEnabled(self._display_week > 1)
        self.btn_next_week.setEnabled(self._display_week < self._max_week)
        self.btn_cur_week.setEnabled(self._display_week != real_week and real_week >= 1)
        is_sun = getattr(s, "week_start_day", "sunday") == "sunday"
        self.btn_week_start.setText("起始: 周日" if is_sun else "起始: 周一")

    def _render_week_list(self):
        """按日期分组展示本周课程的完整信息，避免七列网格压缩长文本。"""
        while self.week_list_layout.count():
            item = self.week_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        sched = self.owner.schedule
        visible_days = 0
        weekdays = self.timetable.col_weekdays
        dates = self.timetable._date_objs
        for index, weekday in enumerate(weekdays):
            course_date = dates[index] if index < len(dates) else None
            if course_date and hasattr(sched, "courses_for_grid"):
                courses, adjustment = sched.courses_for_grid(
                    course_date, weekday, self._display_week)
            else:
                courses = list(sched.courses_on(weekday, self._display_week))
                adjustment = None

            if adjustment and adjustment.get("type") == "suspend":
                day_courses = []
            else:
                day_courses = sorted(courses, key=lambda c: (c.sec_start, c.sec_end, c.name))
            if not day_courses and not (adjustment and adjustment.get("type") == "suspend"):
                continue

            visible_days += 1
            day_group = QtWidgets.QWidget(self.week_list_content)
            day_layout = QtWidgets.QVBoxLayout(day_group)
            day_layout.setContentsMargins(0, 0, 0, 0)
            day_layout.setSpacing(8)

            day_heading = QtWidgets.QHBoxLayout()
            date_label = ""
            if course_date:
                date_label = f" · {course_date.month}月{course_date.day}日"
            day_title = QtWidgets.QLabel(
                f"周{_DAY_LABELS.get(weekday, str(weekday))}{date_label}", day_group)
            day_title.setStyleSheet(
                f"color:{apple.TEXT};font-size:16px;font-weight:700;padding:2px 0;")
            day_heading.addWidget(day_title)
            day_heading.addStretch(1)
            count_label = QtWidgets.QLabel(
                "停课" if adjustment and adjustment.get("type") == "suspend"
                else f"{len(day_courses)} 门课程", day_group)
            count_label.setStyleSheet(
                f"color:{apple.SECONDARY};font-size:13px;padding:2px 8px;")
            day_heading.addWidget(count_label)
            day_layout.addLayout(day_heading)

            if adjustment and adjustment.get("type") == "suspend":
                reason = adjustment.get("reason") or "本日停课"
                suspension = QtWidgets.QLabel(f"{reason} · 全天停课", day_group)
                suspension.setWordWrap(True)
                suspension.setStyleSheet(
                    f"background:#FFF8E8;color:{apple.AMBER};border:1px solid #F0D9A8;"
                    "border-radius:10px;padding:14px 16px;font-size:14px;")
                day_layout.addWidget(suspension)
            else:
                for course in day_courses:
                    card = self._make_week_course_card(
                        course, weekday, adjustment=adjustment)
                    day_layout.addWidget(card)
            self.week_list_layout.addWidget(day_group)

        if visible_days == 0:
            empty = QtWidgets.QLabel("本周暂无课程安排", self.week_list_content)
            empty.setAlignment(QtCore.Qt.AlignCenter)
            empty.setMinimumHeight(180)
            empty.setStyleSheet(
                f"color:{apple.SECONDARY};font-size:18px;padding:24px;")
            self.week_list_layout.addWidget(empty)

        if sched.notes:
            note = QtWidgets.QLabel("课表说明：" + "；".join(str(n) for n in sched.notes),
                                    self.week_list_content)
            note.setWordWrap(True)
            note.setStyleSheet(
                f"background:{apple.FIELD};color:{apple.SECONDARY};border:1px solid {apple.BORDER};"
                "border-radius:10px;padding:12px 14px;font-size:13px;")
            self.week_list_layout.addWidget(note)
        self.week_list_layout.addStretch(1)

    def _make_week_course_card(self, course, display_weekday, adjustment=None):
        """创建可读的课程卡片，显式呈现所有已录入字段。"""
        card = QtWidgets.QFrame(self.week_list_content)
        card.setObjectName("WeekCourseCard")
        card.setStyleSheet(
            f"QFrame#WeekCourseCard{{background:{apple.SURFACE};border:1px solid {apple.BORDER};"
            "border-radius:12px;}"
            f"QLabel{{border:none;background:transparent;color:{apple.TEXT};}}")
        outer = QtWidgets.QHBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        color = self.timetable._color_of.get(course.name)
        color_name = color.name() if color else apple.ACCENT
        accent = QtWidgets.QFrame(card)
        accent.setFixedWidth(5)
        accent.setStyleSheet(f"background:{color_name};border-top-left-radius:12px;border-bottom-left-radius:12px;")
        outer.addWidget(accent)

        body = QtWidgets.QVBoxLayout()
        body.setContentsMargins(16, 12, 14, 12)
        body.setSpacing(8)
        outer.addLayout(body, 1)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(12)
        name = QtWidgets.QLabel(course.name, card)
        name.setWordWrap(True)
        name.setStyleSheet(f"font-size:18px;font-weight:700;color:{apple.TEXT};")
        header.addWidget(name, 1)

        start = (self.owner.schedule.sections or {}).get(str(course.sec_start), "")
        end = (self.owner.schedule.sections or {}).get(str(course.sec_end), "")
        section_text = f"第 {course.sec_start}-{course.sec_end} 节"
        custom_time = getattr(course, "custom_time", "")
        if custom_time:
            section_text += f"  ·  自定义 {custom_time}"
        elif start and end:
            section_text += f"  ·  {start}–{end}"
        time_label = QtWidgets.QLabel(section_text, card)
        time_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        time_label.setStyleSheet(
            f"color:{apple.ACCENT};background:{apple.SELECT_BG};border-radius:8px;"
            "padding:6px 10px;font-size:13px;font-weight:600;")
        header.addWidget(time_label, 0)

        detail_btn = QtWidgets.QPushButton("课程详情", card)
        detail_btn.setFixedHeight(32)
        detail_btn.setStyleSheet(
            f"QPushButton{{background:{apple.FIELD};color:{apple.ACCENT};border:1px solid {apple.BORDER};"
            "border-radius:8px;padding:0 12px;font-size:13px;}"
            f"QPushButton:hover{{background:{apple.SELECT_BG};border-color:{apple.ACCENT};}}")
        detail_btn.clicked.connect(lambda _checked=False, c=course: self._on_course_clicked(c))
        header.addWidget(detail_btn, 0)
        body.addLayout(header)

        parity = {"all": "每周", "odd": "单周", "even": "双周"}.get(course.parity, "每周")
        week_text = f"第 {course.week_start}-{course.week_end} 周 · {parity}"
        display_day = f"周{_DAY_LABELS.get(display_weekday, str(display_weekday))}"
        if adjustment and adjustment.get("type") == "substitute":
            source_day = f"周{_DAY_LABELS.get(course.weekday, str(course.weekday))}"
            display_day += f" · 调课自{source_day}"
        meta_values = (
            ("上课日", display_day),
            ("教学周", week_text),
            ("教室", course.room or "未指定"),
            ("教师", course.teacher or "未指定"),
            ("校区", course.campus or "未指定"),
        )
        meta_row = QtWidgets.QHBoxLayout()
        meta_row.setSpacing(22)
        for label_text, value_text in meta_values:
            item = QtWidgets.QLabel(
                f"<span style='color:{apple.MUTED};'>{label_text}</span>　{_esc(value_text)}", card)
            item.setTextFormat(QtCore.Qt.RichText)
            item.setWordWrap(True)
            item.setStyleSheet(f"font-size:13px;color:{apple.SECONDARY};")
            meta_row.addWidget(item, 1)
        body.addLayout(meta_row)

        if course.note:
            note = QtWidgets.QLabel(f"备注：{_esc(course.note)}", card)
            note.setTextFormat(QtCore.Qt.RichText)
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{apple.SECONDARY};font-size:13px;")
            body.addWidget(note)
        return card

    def _toggle_week_start_day(self):
        s = self.owner.schedule
        new_day = "monday" if getattr(s, "week_start_day", "sunday") == "sunday" else "sunday"
        s.set_week_start_day(new_day)
        self._render_week()

    def _prev_week(self):
        if self._display_week > 1:
            self._display_week -= 1
            self._render_week()

    def _next_week(self):
        if self._display_week < self._max_week:
            self._display_week += 1
            self._render_week()

    def _go_current_week(self):
        s = self.owner.schedule
        real_week = s.week_no() or 1
        self._display_week = max(1, real_week)
        self._render_week()

    def _on_course_clicked(self, course):
        """点击课程色块弹窗展示详情。"""
        from .schedule_dialogs import CourseDetailDialog
        color = self.timetable._color_of.get(course.name, None)
        dlg = CourseDetailDialog(
            course,
            color=color,
            sections=self.owner.schedule.sections,
            parent=self
        )
        dlg.sig_edit_requested.connect(self._on_edit_course)
        dlg.sig_delete_requested.connect(self._on_delete_course)
        dlg.sig_ask_ai.connect(self._on_ask_ai)
        dlg.sig_open_knowledge.connect(self.show_knowledge)
        dlg.exec_()

    def _on_empty_slot_clicked(self, weekday, section):
        """点击空白格快捷录入课程。"""
        from .schedule_dialogs import CourseEditDialog
        dlg = CourseEditDialog(default_weekday=weekday, default_sec=section, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted and dlg.result_course:
            self.owner.schedule.add_course(dlg.result_course)
            self._render_week()
            if hasattr(self.owner, "bubble"):
                self.owner.bubble.say(f"已为博士添加课程《{dlg.result_course.name}》！", self.owner._body_rect())

    def _on_edit_course(self, course):
        """编辑指定课程。"""
        from .schedule_dialogs import CourseEditDialog
        dlg = CourseEditDialog(course=course, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted and dlg.result_course:
            self.owner.schedule.update_course(course, dlg.result_course)
            self._render_week()
            if hasattr(self.owner, "bubble"):
                self.owner.bubble.say(f"已更新课程《{dlg.result_course.name}》信息！", self.owner._body_rect())

    def _on_delete_course(self, course):
        """删除指定课程。"""
        if not self.owner.schedule.delete_course(course):
            QtWidgets.QMessageBox.warning(self, "删除失败", "课程已保留。请检查存储空间后重试。")
            return
        self._render_week()
        if hasattr(self.owner, "bubble"):
            self.owner.bubble.say(f"已删除课程《{course.name}》。", self.owner._body_rect())

    def _on_ask_ai(self, prompt):
        """向阿米娅发起提问。"""
        if hasattr(self.owner, "_ask"):
            self.owner._ask(prompt)
        elif hasattr(self.owner, "open_chat"):
            self.owner.open_chat()
        elif hasattr(self.owner, "bubble"):
            self.owner.bubble.say(prompt, self.owner._body_rect())

    def _on_import_schedule(self):
        """导入强智教务课表。"""
        if hasattr(self.owner, "import_schedule"):
            self.owner.import_schedule()
        elif hasattr(self.owner, "focus") and hasattr(self.owner.focus, "import_schedule"):
            self.owner.focus.import_schedule()
        self._render_week()

    def _on_ai_schedule_analysis(self):
        """一键让阿米娅分析课表。"""
        prompt = "阿米娅，请结合我当前学期的本科课表为我做一次全面的学情分析：包括课程负荷评估、每周节奏分析与自习备考建议！"
        self._on_ask_ai(prompt)


    def refresh_tasks(self):
        """从 owner.tasks 重建待办表格。"""
        self.nav.setCurrentRow(1)
        self.stack.setCurrentIndex(1)
        tasks = self.owner.tasks
        now = datetime.now()
        all_tasks = list(tasks.items)
        rows = sorted(all_tasks, key=lambda t: (t.done, t.due))
        soon = now + timedelta(days=30)
        week_end = now + timedelta(days=7)
        if hasattr(self, "task_stat_values"):
            self.task_stat_values["pending"].setText(
                str(sum(1 for task in all_tasks if not task.done)))
            self.task_stat_values["exams"].setText(
                str(sum(1 for task in all_tasks
                        if not task.done and task.kind == "exam"
                        and now <= task.due <= soon)))
            self.task_stat_values["week"].setText(
                str(sum(1 for task in all_tasks
                        if not task.done and now <= task.due <= week_end)))
        self.task_table.setRowCount(len(rows))
        for i, t in enumerate(rows):
            self.task_table.setRowHeight(i, 54)
            tag = "考试" if t.kind == "exam" else "作业"
            title = "%s · %s" % (tag, t.title)
            if t.done:
                state, left = "✓ 完成", "—"
                color = apple.SECONDARY
            elif t.expired(now):
                state, left = "已过期", "—"
                color = apple.RED
            else:
                state = "待办"
                d = t.due - now
                if d.days >= 1:
                    left = "%d 天" % d.days
                elif d.seconds >= 3600:
                    left = "%d 小时" % (d.seconds // 3600)
                else:
                    left = "%d 分钟" % max(1, d.seconds // 60)
                color = apple.TEXT
            items = [QtWidgets.QTableWidgetItem(state),
                     QtWidgets.QTableWidgetItem(title),
                     QtWidgets.QTableWidgetItem(t.course),
                     QtWidgets.QTableWidgetItem(
                         t.due.strftime("%m-%d %H:%M")),
                     QtWidgets.QTableWidgetItem(left)]
            for it in items:
                it.setForeground(QtGui.QColor(color))
                it.setTextAlignment(QtCore.Qt.AlignCenter)
            items[1].setTextAlignment(QtCore.Qt.AlignLeft
                                      | QtCore.Qt.AlignVCenter)
            self.task_table.setItem(i, 0, items[0])
            self.task_table.setItem(i, 1, items[1])
            self.task_table.setItem(i, 2, items[2])
            self.task_table.setItem(i, 3, items[3])
            self.task_table.setItem(i, 4, items[4])
            self.task_table.item(i, 0).setData(QtCore.Qt.UserRole, t.id)

    def _selected_task_id(self):
        row = self.task_table.currentRow()
        if row < 0:
            return None
        return self.task_table.item(row, 0).data(QtCore.Qt.UserRole)

    def _toggle_done(self):
        tid = self._selected_task_id()
        if not tid:
            return
        for t in self.owner.tasks.items:
            if t.id == tid:
                self.owner.tasks.set_done(tid, not t.done)
                break
        self.refresh_tasks()

    def _remove_task(self):
        tid = self._selected_task_id()
        if not tid:
            return
        if not self.owner.tasks.remove(tid):
            QtWidgets.QMessageBox.warning(self, "删除失败", "任务已保留。请检查存储空间后重试。")
            return
        self.refresh_tasks()

    def show_ocr(self, mode, text, result):
        """展示 OCR 结果（mode: 'translate' / 'summarize'）。"""
        self.nav.setCurrentRow(2)
        self.stack.setCurrentIndex(2)
        label = "截图翻译" if mode == "translate" else "截图总结"
        self.ocr_status.setText("%s · %s 字符" % (label, len(text)))
        self.ocr_source.setPlainText(text)
        self.ocr_result.setPlainText(result)

    def _launch_web_workspace(self, course=None, filename=None):
        """调起 NotebookLM 网页版工作台。"""
        from .web_launcher import open_notebook_lm
        brain = getattr(self.owner, "brain", None)
        kb = getattr(brain, "knowledge", None)
        open_notebook_lm(course=course, filename=filename, brain=brain, kb=kb)

    def show_knowledge(self, course=None):
        """展示课程知识库管理页，并直接打开 NotebookLM 网页端。"""
        self.nav.setCurrentRow(3)
        self.stack.setCurrentIndex(3)
        self.refresh_knowledge_page(select_course=course)
        self._launch_web_workspace(course=course)

    def _render_knowledge_files(self, files):
        """Render a small preview from the real local knowledge-base index."""
        while self.kw_files_layout.count():
            item = self.kw_files_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not files:
            empty = QtWidgets.QLabel(
                "暂无课件资料。打开课程知识库可导入并整理讲义。",
                self.kw_files_container)
            empty.setAlignment(QtCore.Qt.AlignCenter)
            empty.setMinimumHeight(150)
            empty.setStyleSheet(
                f"color:{apple.SECONDARY};font-size:{theme.FS_MD}px;padding:20px;")
            self.kw_files_layout.addWidget(empty)
            self.kw_files_layout.addStretch(1)
            return

        for info in files[:8]:
            filename = str(info.get("filename") or "未命名课件")
            course = str(info.get("course") or "通用讲义")
            extension = filename.rsplit(".", 1)[-1].upper() if "." in filename else "DOC"
            size = max(0, int(info.get("size") or 0))
            size_text = f"{size / (1024 * 1024):.1f} MB" if size >= 1024 * 1024 else f"{size / 1024:.0f} KB"
            chunks = max(0, int(info.get("chunks") or 0))

            card = QtWidgets.QFrame(self.kw_files_container)
            card.setObjectName("KnowledgeFileCard")
            card.setMinimumHeight(74)
            row = QtWidgets.QHBoxLayout(card)
            row.setContentsMargins(14, 10, 16, 10)
            row.setSpacing(14)

            badge = QtWidgets.QLabel(extension, card)
            badge.setObjectName("FileBadge")
            badge.setAlignment(QtCore.Qt.AlignCenter)
            badge.setMinimumWidth(54)
            row.addWidget(badge)

            details = QtWidgets.QVBoxLayout()
            details.setSpacing(4)
            name = QtWidgets.QLabel(filename, card)
            name.setStyleSheet(
                f"font-size:{theme.FS_MD}px;font-weight:600;color:{apple.TEXT};")
            name.setWordWrap(True)
            meta = QtWidgets.QLabel(course, card)
            meta.setStyleSheet(
                f"font-size:{theme.FS_SM}px;color:{apple.SECONDARY};")
            details.addWidget(name)
            details.addWidget(meta)
            row.addLayout(details, 1)

            count = QtWidgets.QLabel(f"{chunks} 段内容  ·  {size_text}", card)
            count.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            count.setStyleSheet(
                f"font-size:{theme.FS_SM}px;color:{apple.SECONDARY};")
            row.addWidget(count)
            self.kw_files_layout.addWidget(card)

        self.kw_files_layout.addStretch(1)

    def refresh_knowledge_page(self, select_course=None):
        """刷新知识库页面列表与统计。"""
        brain = getattr(self.owner, "brain", None)
        kb = getattr(brain, "knowledge", None)
        if kb:
            stats = kb.get_stats()
            f_count = stats.get("file_count", 0)
            c_count = stats.get("chunk_count", 0)
            courses = stats.get("courses", [])
            course_count = stats.get("course_count", len(courses))
            if hasattr(self, "kw_stat_values"):
                self.kw_stat_values["courses"].setText(str(course_count))
                self.kw_stat_values["files"].setText(str(f_count))
                self.kw_stat_values["chunks"].setText(str(c_count))
            text = f"本地已收录 {f_count} 份课件 · {c_count} 段内容 · 覆盖 {course_count} 门课程"
            if hasattr(self, "kw_stat_lbl"):
                self.kw_stat_lbl.setText(text)
            file_course = select_course if select_course else "__ALL__"
            files = list(kb.get_course_files(file_course))
            def recency(item):
                try:
                    return float(item.get("mtime") or 0)
                except (TypeError, ValueError):
                    return 0.0
            files.sort(key=recency, reverse=True)
            if hasattr(self, "kw_files_layout"):
                self._render_knowledge_files(files)
            if hasattr(self, "kw_recent_title"):
                self.kw_recent_title.setText(
                    f"《{select_course}》的课件" if select_course else "最近添加的课件")
        else:
            if hasattr(self, "kw_stat_lbl"):
                self.kw_stat_lbl.setText("本地知识库暂不可用。")
            if hasattr(self, "kw_files_layout"):
                self._render_knowledge_files([])

    def _on_digest_progress(self, filename, course, pct, status_msg):
        """当课件知识点提炼进度更新时，更新知识库提示。"""
        if hasattr(self, "kw_stat_lbl") and pct < 100:
            self.kw_stat_lbl.setText(f"正在整理《{filename}》的学习要点（{pct}% · {status_msg}）")

    def _on_digest_finished(self, filename, course, ok, msg):
        """提炼完成或出错时，刷新知识库状态。"""
        self.refresh_knowledge_page()

    def _show_courseware_digest(self, filename, course, file_path):
        """在系统浏览器中打开 NotebookLM 网页版并聚焦该课件。"""
        self._launch_web_workspace(course=course, filename=filename)

    def _upload_courseware(self):
        """弹出文件选择框上传课件文件。"""
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "选择要导入的课件与讲义", "",
            "课件讲义文件 (*.pptx *.ppt *.pdf *.docx *.doc *.txt *.md *.png *.jpg);;所有文件 (*.*)"
        )
        if files:
            self.owner._handle_dropped_files(files)
            QtCore.QTimer.singleShot(800, self.refresh_knowledge_page)

    def _open_knowledge_folder(self):
        """在系统资源管理器中打开知识库目录。"""
        import os
        from .settings import config_dir
        kb = getattr(self.owner.brain, "knowledge", None)
        path = kb.folder if kb else os.path.join(config_dir(), "knowledge")
        os.makedirs(path, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))

    def _quick_ask_ai(self, prompt_prefix):
        """针对当前选中的课程向阿米娅发起学术提问。"""
        selected_course = self.kw_course_combo.currentData()
        if selected_course and selected_course != "__ALL__":
            prompt = f"针对《{selected_course}》这门课程：{prompt_prefix}"
        else:
            prompt = prompt_prefix
        self.owner.open_chat()
        if hasattr(self.owner, "_chat_widget") and self.owner._chat_widget:
            self.owner._chat_widget.input.setPlainText(prompt)

    def _ask_file_ai(self, filename, course_name):
        c_desc = f"关于《{course_name}》的课件《{filename}》：" if course_name else f"关于课件《{filename}》："
        self.owner.open_chat()
        if hasattr(self.owner, "_chat_widget") and self.owner._chat_widget:
            self.owner._chat_widget.input.setPlainText(f"{c_desc}请帮我总结其中的核心要点与可能考题。")

    def _delete_kw_file(self, filename, course_name):
        reply = QtWidgets.QMessageBox.question(
            self, "确认删除",
            f"确定要从知识库中移除课件《{filename}》吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            kb = getattr(self.owner.brain, "knowledge", None)
            if kb:
                kb.delete_file(filename, course=course_name)
                self.refresh_knowledge_page()

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
            import os
            valid = [p for p in paths if os.path.exists(p)]
            if valid:
                e.acceptProposedAction()
                self.owner._handle_dropped_files(valid)
                return
        super().dropEvent(e)

    # ── 窗口行为（拖动 / Esc 关闭）─────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton and e.y() <= 62:
            self._drag = e.globalPos() - self.frameGeometry().topLeft()
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPos() - self._drag)
            e.accept()
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag = None
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)

    def present(self):
        """显示并置前面板（页面切换由各 show_* / refresh_* 方法负责）。"""
        if not self.isVisible():
            self._center()
        self.show()
        self.raise_()
        self.activateWindow()

    def _center(self):
        screen = self.screen() or QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.center() - self.rect().center())


