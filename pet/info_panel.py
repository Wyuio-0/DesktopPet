"""信息面板：课程表 / 待办与考试 / OCR 结果 的集中展示窗口。

把原来挤在气泡/浮窗里的长文本改为独立、可缩放、可滚动的置顶面板，
信息分层清晰，待办可直接在行内完成/删除。

入口：PetWindow 右键菜单（课程表/待办与考试/OCR 的查看类动作都指向本面板）。
"""

from datetime import datetime

import html as _html

from PyQt5 import QtCore, QtGui, QtWidgets

from . import theme
from .schedule import _PARITY_LABEL
from .timetable import TimetableView

PAGE_SCHEDULE = "schedule"
PAGE_TASKS = "tasks"
PAGE_OCR = "ocr"
PAGE_KNOWLEDGE = "knowledge"


def _esc(t):
    return _html.escape(str(t))


def _day_head(name):
    """Markdown 风格的「标题行」（金色加粗）。"""
    return ('<p style="margin:12px 0 2px 0;color:%s;font-size:20px;'
            'font-weight:700;">%s</p>' % (theme.FLOAT_GOLD, _esc(name)))


_DAY_LABELS = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "日"}


def _today_card_html(c, sched, now, week_no):
    """单节课的现代卡片 HTML，包含时段、状态徽章、教师与地点。"""
    secs = f"第 {c.sec_start}-{c.sec_end} 节"
    a = sched.sections.get(str(c.sec_start), "")
    b = sched.sections.get(str(c.sec_end), "")
    time_str = f"({a} - {b})" if a and b else (f"({a})" if a else "")

    # 判定课程状态 (进行中 / 即将开始 / 已结束)
    cur_mins = now.hour * 60 + now.minute
    status_badge = '<span style="background:#2D3748; color:#94A3B8; padding:3px 8px; border-radius:4px; font-size:12px;">已结束</span>'
    if a and ":" in a:
        try:
            parts = a.split(":")
            start_m = int(parts[0]) * 60 + int(parts[1])
            end_m = start_m + 45 * (c.sec_end - c.sec_start + 1)
            if b and ":" in b:
                eparts = b.split(":")
                end_m = int(eparts[0]) * 60 + int(eparts[1]) + 45
            if cur_mins < start_m:
                status_badge = '<span style="background:rgba(0,176,255,0.18); color:#00B0FF; border:1px solid #00B0FF; padding:3px 8px; border-radius:4px; font-size:12px;">待上课</span>'
            elif start_m <= cur_mins <= end_m:
                status_badge = '<span style="background:rgba(76,175,80,0.22); color:#4CAF50; border:1px solid #4CAF50; padding:3px 8px; border-radius:4px; font-size:12px; font-weight:bold;">● 正在进行中</span>'
        except Exception:
            pass

    room_str = f"📍 {_esc(c.room)}" if c.room else "📍 教室待定"
    teacher_str = f"👤 {_esc(c.teacher)}" if c.teacher else ""
    parity_str = {"all": "", "odd": " (仅单周)", "even": " (仅双周)"}.get(c.parity, "")
    weeks_str = f"📅 第 {c.week_start}-{c.week_end} 周{parity_str}"

    meta_parts = [room_str]
    if teacher_str:
        meta_parts.append(teacher_str)
    meta_parts.append(weeks_str)
    meta_line = " &nbsp;·&nbsp; ".join(meta_parts)

    return f"""
    <div style="background:#161B22; border:1px solid #30363D; border-radius:8px; padding:12px 16px; margin:8px 0;">
        <table width="100%" border="0" cellpadding="0" cellspacing="0">
            <tr>
                <td align="left"><span style="color:#00B0FF; font-weight:bold; font-size:13px;">{secs} {time_str}</span></td>
                <td align="right">{status_badge}</td>
            </tr>
        </table>
        <div style="color:#FFFFFF; font-size:16px; font-weight:bold; margin:6px 0;">{_esc(c.name)}</div>
        <div style="color:#8B949E; font-size:12px;">{meta_line}</div>
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
                <div style="font-size:36px; margin-bottom:12px;">☕</div>
                <div style="color:#FFFFFF; font-size:18px; font-weight:bold; margin-bottom:8px;">今日无课 · 自由自习</div>
                <div style="color:#8B949E; font-size:13px; line-height:1.6;">
                    今天 ({today_date_str}) 没有排课，博士可以好好休息或自习备考~<br/>
                    点击上方「<b>📅 本周课表</b>」可浏览全周日程，或点击「<b>+ 录入课程</b>」手动添加。
                </div>
            </div>
            """
        head = f"""
        <div style="margin-bottom:12px;">
            <span style="font-size:18px; font-weight:bold; color:#F8FAFC;">今日日程</span>
            <span style="font-size:13px; color:#00B0FF; margin-left:8px;">{today_date_str} · 共 {len(courses)} 门课程</span>
        </div>
        """
        cards = "".join(_today_card_html(c, sched, now, week_no) for c in courses)
        return head + cards

    # which == "next"
    nxt = sched.next_class()
    if not nxt:
        return """
        <div style="text-align:center; padding:50px 20px;">
            <div style="font-size:36px; margin-bottom:12px;">🎉</div>
            <div style="color:#FFFFFF; font-size:18px; font-weight:bold; margin-bottom:8px;">本周没有剩余课程了</div>
            <div style="color:#8B949E; font-size:13px;">博士可以好好享受空闲时光！</div>
        </div>
        """
    c, weekday, _, start = nxt
    mins = max(0, int((start - now).total_seconds() // 60))
    time_badge = f"{mins} 分钟后" if mins > 0 else "即将开始"
    where = f"📍 {_esc(c.room)}" if c.room else "📍 教室待定"
    teacher = f"👤 {_esc(c.teacher)}" if c.teacher else ""
    meta_line = " &nbsp;·&nbsp; ".join(x for x in [where, teacher, f"周{_DAY_LABELS.get(weekday, '')} 第 {c.sec_start}-{c.sec_end} 节"] if x)

    return f"""
    <div style="margin-bottom:16px;">
        <span style="font-size:18px; font-weight:bold; color:#F8FAFC;">下一节课安排</span>
    </div>
    <div style="background:#161B22; border:1px solid #00B0FF; border-radius:10px; padding:18px 20px;">
        <table width="100%" border="0" cellpadding="0" cellspacing="0">
            <tr>
                <td align="left"><span style="color:#00B0FF; font-size:13px; font-weight:bold;">🕒 开课时刻：{start.strftime('%H:%M')}</span></td>
                <td align="right"><span style="background:rgba(245,158,11,0.2); color:#FBBF24; border:1px solid #F59E0B; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:bold;">距离上课 {time_badge}</span></td>
            </tr>
        </table>
        <div style="color:#FFFFFF; font-size:22px; font-weight:bold; margin:10px 0;">{_esc(c.name)}</div>
        <div style="color:#94A3B8; font-size:13px;">{meta_line}</div>
    </div>
    """


_QSS = """
QWidget#PanelRoot { background:%s; color:%s; }
QWidget#TitleBar { background:%s; }
QLabel#TitleText { color:%s; font-size:20px; font-weight:700; }
QLabel#TitleSub { color:%s; font-size:13px; }
QPushButton#CloseBtn { color:%s; border:none; font-size:22px; }
QPushButton#CloseBtn:hover { color:%s; }
QListWidget#Nav { background:%s; border:none; font-size:18px; padding-top:10px; }
QListWidget#Nav::item { padding:16px 18px; border-radius:4px; margin:2px 8px; }
QListWidget#Nav::item:selected { background:%s; color:%s; }
QTextBrowser, QPlainTextEdit {
    background:%s; color:%s; border:1px solid %s; border-radius:4px;
    font-size:18px; padding:10px; line-height:1.5;
}
QTableWidget {
    background:%s; color:%s; border:1px solid %s; gridline-color:%s;
    font-size:16px; selection-background-color:%s;
}
QHeaderView::section { background:%s; color:%s; border:none; padding:8px; font-size:16px; }
QPushButton {
    background:%s; color:%s; border:1px solid %s; border-radius:4px;
    padding:6px 12px; font-size:13px;
}
QPushButton:hover { background:%s; }
QPushButton:disabled { color:%s; }
QPushButton#PrimaryBtn {
    background: #00B0FF; color: #FFFFFF; border: 1px solid #0091EA; font-weight: bold;
}
QPushButton#PrimaryBtn:hover { background: #40C4FF; }
QPushButton#ActionBtn {
    background: #1A2230; color: #00B0FF; border: 1px solid #00B0FF; font-weight: 500;
}
QPushButton#ActionBtn:hover { background: #00B0FF; color: #FFFFFF; }
""" % (
    theme.DLG_BG, theme.FLOAT_TEXT,
    theme.PANEL_SOLID,
    theme.FLOAT_GOLD, theme.FLOAT_TEXT_DIM,
    theme.FLOAT_TEXT_DIM, theme.FLOAT_ACCENT,
    theme.FLOAT_FIELD,
    theme.FLOAT_SELECT_BG, theme.FLOAT_SELECT_TEXT,
    theme.FLOAT_FIELD, theme.FLOAT_TEXT, theme.FLOAT_GRID,
    theme.FLOAT_FIELD, theme.FLOAT_TEXT, theme.FLOAT_GRID,
    theme.FLOAT_GRID, theme.FLOAT_SELECT_BG,
    theme.PANEL_SOLID, theme.FLOAT_TEXT_DIM,
    theme.FLOAT_FIELD, theme.FLOAT_TEXT, theme.FLOAT_GRID,
    theme.DLG_HOVER,
    theme.FLOAT_TEXT_DIM,
)


class InfoPanel(QtWidgets.QWidget):
    """课程表 / 待办与考试 / OCR 结果的集中面板（置顶、可缩放、可拖动）。"""

    def __init__(self, owner):
        super().__init__(None)
        self.owner = owner          # PetWindow（数据源：schedule / tasks）
        self._drag = None
        self.setWindowTitle("信息面板")
        self.setWindowFlags(
            QtCore.Qt.Window
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setMinimumSize(780, 580)
        self.resize(860, 680)
        self.setAcceptDrops(True)
        self.setStyleSheet(_QSS)
        self.setObjectName("PanelRoot")
        self._build()

    # ── UI ─────────────────────────────────────────────────────────

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 自定义标题栏（可拖动）
        bar = QtWidgets.QWidget(self)
        bar.setObjectName("TitleBar")
        bar.setFixedHeight(48)
        bar_layout = QtWidgets.QHBoxLayout(bar)
        bar_layout.setContentsMargins(16, 0, 8, 0)
        title = QtWidgets.QLabel("信息面板", bar)
        title.setObjectName("TitleText")
        sub = QtWidgets.QLabel("RHODES ISLAND · DESKTOP", bar)
        sub.setObjectName("TitleSub")
        close = QtWidgets.QPushButton("✕", bar)
        close.setObjectName("CloseBtn")
        close.setFixedSize(36, 36)
        close.setCursor(QtCore.Qt.PointingHandCursor)
        close.clicked.connect(self.hide)
        bar_layout.addWidget(title)
        bar_layout.addSpacing(10)
        bar_layout.addWidget(sub)
        bar_layout.addStretch(1)
        bar_layout.addWidget(close)
        root.addWidget(bar)

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(10, 10, 10, 10)
        body.setSpacing(10)
        root.addLayout(body, 1)

        # 左侧导航
        self.nav = QtWidgets.QListWidget(self)
        self.nav.setObjectName("Nav")
        self.nav.setFixedWidth(150)
        self.nav.addItem("课程表")
        self.nav.addItem("待办与考试")
        self.nav.addItem("OCR 结果")
        self.nav.addItem("课程知识库")
        self.nav.currentRowChanged.connect(self._switch_page)
        body.addWidget(self.nav)

        # 右侧页面
        self.stack = QtWidgets.QStackedWidget(self)
        self.stack.addWidget(self._build_schedule_page())
        self.stack.addWidget(self._build_tasks_page())
        self.stack.addWidget(self._build_ocr_page())
        self.stack.addWidget(self._build_knowledge_page())
        body.addWidget(self.stack, 1)

        self.nav.setCurrentRow(0)

    def _build_schedule_page(self):
        page = QtWidgets.QWidget(self)
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        btns = QtWidgets.QHBoxLayout()
        btns.setSpacing(6)
        self.btn_week = QtWidgets.QPushButton("本周课表", page)
        self.btn_today = QtWidgets.QPushButton("今日日程", page)
        self.btn_next = QtWidgets.QPushButton("下一节课", page)
        self.btn_week.clicked.connect(lambda: self.show_schedule("week"))
        self.btn_today.clicked.connect(lambda: self.show_schedule("today"))
        self.btn_next.clicked.connect(lambda: self.show_schedule("next"))
        for b in (self.btn_week, self.btn_today, self.btn_next):
            btns.addWidget(b)
        btns.addStretch(1)

        # 快捷功能按钮（右侧）
        self.btn_add_course = QtWidgets.QPushButton("+ 录入课程", page)
        self.btn_add_course.setObjectName("ActionBtn")
        self.btn_add_course.clicked.connect(lambda: self._on_empty_slot_clicked(1, 1))

        self.btn_import_schedule = QtWidgets.QPushButton("📥 导入", page)
        self.btn_import_schedule.setObjectName("ActionBtn")
        self.btn_import_schedule.clicked.connect(self._on_import_schedule)

        self.btn_ai_analysis = QtWidgets.QPushButton("✨ 学情分析", page)
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
        self.btn_prev_week = QtWidgets.QPushButton("◀ 上一周", page)
        self.week_label = QtWidgets.QLabel("第 1 周", page)
        self.week_label.setAlignment(QtCore.Qt.AlignCenter)
        self.week_label.setStyleSheet("color: #00B0FF; font-size: 15px; font-weight: bold;")
        self.btn_cur_week = QtWidgets.QPushButton("回到本周", page)
        self.btn_next_week = QtWidgets.QPushButton("下一周 ▶", page)
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
        self.sched_view.setStyleSheet("background: #101318; border: 1px solid #232A36; border-radius: 8px; padding: 12px;")

        # 周课表可视化色块视图（自适应填满，无滚动条）
        self.timetable = TimetableView(page)
        self.timetable.sig_course_clicked.connect(self._on_course_clicked)
        self.timetable.sig_empty_slot_clicked.connect(self._on_empty_slot_clicked)

        self.timetable_area = QtWidgets.QScrollArea(page)
        self.timetable_area.setWidget(self.timetable)
        self.timetable_area.setWidgetResizable(True)
        self.timetable_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.timetable_area.setStyleSheet(
            "QScrollArea{background:#101318;border:none;}"
            "QScrollArea>QWidget>QWidget{background:#101318;}")
        self.sched_stack = QtWidgets.QStackedWidget(page)
        self.sched_stack.addWidget(self.timetable_area)  # 0: 本周（色块）
        self.sched_stack.addWidget(self.sched_view)      # 1: 今天 / 下一节
        lay.addWidget(self.sched_stack, 1)
        return page

    def _build_tasks_page(self):
        page = QtWidgets.QWidget(self)
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        tip = QtWidgets.QLabel("双击任务可标记完成；选中后可用下方按钮操作。", page)
        tip.setStyleSheet("color:%s;font-size:15px;" % theme.FLOAT_TEXT_DIM)
        lay.addWidget(tip)

        self.task_table = QtWidgets.QTableWidget(0, 5, page)
        self.task_table.setHorizontalHeaderLabels(
            ["状态", "事项", "课程", "截止时间", "剩余"])
        self.task_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows)
        self.task_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection)
        self.task_table.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers)
        self.task_table.verticalHeader().setVisible(False)
        header = self.task_table.horizontalHeader()
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
        lay.setSpacing(8)

        self.ocr_status = QtWidgets.QLabel("暂无 OCR 结果。", page)
        self.ocr_status.setStyleSheet(
            "color:%s;font-size:16px;" % theme.FLOAT_TEXT_DIM)
        lay.addWidget(self.ocr_status)

        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal, page)
        self.ocr_source = QtWidgets.QPlainTextEdit(page)
        self.ocr_result = QtWidgets.QPlainTextEdit(page)
        for w in (self.ocr_source, self.ocr_result):
            w.setReadOnly(True)
            w.setPlaceholderText("")
        self.ocr_source.setPlaceholderText("原文（识别结果）")
        self.ocr_result.setPlaceholderText("译文 / 总结")
        split.addWidget(self.ocr_source)
        split.addWidget(self.ocr_result)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, 1)
        return page

    def _build_knowledge_page(self):
        page = QtWidgets.QWidget(self)
        page.setAcceptDrops(True)
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # 顶栏过滤与操作
        top_bar = QtWidgets.QHBoxLayout()
        top_bar.setSpacing(10)

        lbl = QtWidgets.QLabel("目标课程：", page)
        lbl.setStyleSheet("color: #94A3B8; font-size: 14px; font-weight: bold;")
        top_bar.addWidget(lbl)

        self.kw_course_combo = QtWidgets.QComboBox(page)
        self.kw_course_combo.setStyleSheet(
            "QComboBox{background:#1A1F29;color:#FFFFFF;border:1px solid #232A36;padding:5px 12px;border-radius:6px;font-size:13px;min-width:180px;}"
            "QComboBox:focus{border:1px solid #00B0FF;}"
        )
        self.kw_course_combo.currentIndexChanged.connect(self._on_kw_filter_changed)
        top_bar.addWidget(self.kw_course_combo)

        self.kw_stat_label = QtWidgets.QLabel("📚 正在加载知识库...", page)
        self.kw_stat_label.setStyleSheet("color: #00B0FF; font-size: 13px; font-weight: 500;")
        top_bar.addWidget(self.kw_stat_label, 1)

        self.btn_upload_doc = QtWidgets.QPushButton("➕ 上传课件", page)
        self.btn_upload_doc.setObjectName("PrimaryBtn")
        self.btn_upload_doc.setStyleSheet(
            "QPushButton{background:#00B0FF;color:#000000;font-weight:bold;padding:6px 14px;border-radius:6px;}"
            "QPushButton:hover{background:#40C4FF;}"
        )
        self.btn_upload_doc.clicked.connect(self._upload_courseware)
        top_bar.addWidget(self.btn_upload_doc)

        self.btn_open_folder = QtWidgets.QPushButton("📁 打开目录", page)
        self.btn_open_folder.setStyleSheet(
            "QPushButton{background:#1A1F29;color:#E2E8F0;border:1px solid #232A36;padding:6px 12px;border-radius:6px;}"
            "QPushButton:hover{background:#2D3748;}"
        )
        self.btn_open_folder.clicked.connect(self._open_knowledge_folder)
        top_bar.addWidget(self.btn_open_folder)

        lay.addLayout(top_bar)

        # 快捷 AI 问答推荐横栏 (Prompt Suggestions)
        ai_bar = QtWidgets.QHBoxLayout()
        ai_bar.setSpacing(8)
        ai_tip = QtWidgets.QLabel("✨ 快捷学业辅导：", page)
        ai_tip.setStyleSheet("color: #CBD5E1; font-size: 13px; font-weight: bold;")
        ai_bar.addWidget(ai_tip)

        self.btn_q_keypoints = QtWidgets.QPushButton("🎯 划出期末重点", page)
        self.btn_q_exam = QtWidgets.QPushButton("📝 生成5道期末模拟题", page)
        self.btn_q_summary = QtWidgets.QPushButton("💡 核心考点与公式梳理", page)

        for b in (self.btn_q_keypoints, self.btn_q_exam, self.btn_q_summary):
            b.setStyleSheet(
                "QPushButton{background:rgba(0,176,255,0.12);color:#00E5FF;border:1px solid rgba(0,176,255,0.35);padding:4px 10px;border-radius:14px;font-size:12px;}"
                "QPushButton:hover{background:rgba(0,176,255,0.25);border-color:#00E5FF;}"
            )
        self.btn_q_keypoints.clicked.connect(lambda: self._quick_ask_ai("请根据你掌握的本课程所有课件与考纲内容，帮我划出期末考试的核心重点与必考考点。"))
        self.btn_q_exam.clicked.connect(lambda: self._quick_ask_ai("请严格依据本课程的课件资料，为我出5道常考的期末模拟简答题或分析题，并附带参考解析答案。"))
        self.btn_q_summary.clicked.connect(lambda: self._quick_ask_ai("请帮我梳理本课程课件中的核心概念、定律、公式及解题步骤框架。"))

        ai_bar.addWidget(self.btn_q_keypoints)
        ai_bar.addWidget(self.btn_q_exam)
        ai_bar.addWidget(self.btn_q_summary)
        ai_bar.addStretch(1)
        lay.addLayout(ai_bar)

        # 课件列表表格
        self.kw_table = QtWidgets.QTableWidget(page)
        self.kw_table.setColumnCount(6)
        self.kw_table.setHorizontalHeaderLabels(["格式", "课件/讲义文件名", "关联课程", "大小", "知识切片", "操作"])
        self.kw_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.kw_table.setColumnWidth(0, 65)
        self.kw_table.setColumnWidth(2, 110)
        self.kw_table.setColumnWidth(3, 85)
        self.kw_table.setColumnWidth(4, 90)
        self.kw_table.setColumnWidth(5, 150)
        self.kw_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.kw_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.kw_table.setStyleSheet("QTableWidget{background:#101318;border:1px solid #232A36;border-radius:8px;}")
        lay.addWidget(self.kw_table, 1)

        # 底部提示
        bottom_tip = QtWidgets.QLabel("💡 提示：可直接将 PPT、PDF、Word 讲义从桌面拖拽到桌宠身上或此窗口，阿米娅会自动识别课程并建库！", page)
        bottom_tip.setStyleSheet("color: #64748B; font-size: 12px;")
        lay.addWidget(bottom_tip)

        return page

    # ── 行为 ───────────────────────────────────────────────────────

    def _switch_page(self, row):
        self.stack.setCurrentIndex(row)
        if row == 0:
            self.show_schedule("week")
        elif row == 1:
            self.refresh_tasks()
        elif row == 3:
            self.refresh_knowledge_page()

    def show_schedule(self, which):
        """展示课程表：'week' 用可视化色块表，'today'/'next' 用富文本列表。"""
        s = self.owner.schedule
        self.nav.setCurrentRow(0)
        self.stack.setCurrentIndex(0)

        # 选项卡高亮样式联动
        active_qss = "background: #00B0FF; color: #FFFFFF; font-weight: bold; border: 1px solid #0091EA;"
        self.btn_week.setStyleSheet(active_qss if which == "week" else "")
        self.btn_today.setStyleSheet(active_qss if which == "today" else "")
        self.btn_next.setStyleSheet(active_qss if which == "next" else "")

        if not s.courses:
            self.week_nav_widget.hide()
            self.sched_stack.setCurrentWidget(self.sched_view)
            self.sched_view.setHtml("""
            <div style="text-align:center; padding:60px 20px;">
                <div style="font-size:40px; margin-bottom:12px;">📅</div>
                <div style="color:#FFFFFF; font-size:18px; font-weight:bold; margin-bottom:8px;">暂无本科课表数据</div>
                <div style="color:#8B949E; font-size:13px; line-height:1.6;">
                    点击右上角「<b>+ 录入课程</b>」手动规划课程，或点击「<b>📥 导入课表</b>」导入教务 JSON。<br/>
                    阿米娅将根据您的课表作息提供提醒与学情分析！
                </div>
            </div>
            """)
            return

        if which == "week":
            # 色块视图：等宽列、高度∝节数、按课程配色；默认定位到当前周
            s_week = s.week_no() or 0
            self._display_week = s_week if s_week >= 1 else 1
            self._max_week = max((c.week_end for c in s.courses), default=20)
            self._render_week()
            return

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
        self.owner.schedule.delete_course(course)
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
        rows = sorted(tasks.items, key=lambda t: (t.done, t.due))
        self.task_table.setRowCount(len(rows))
        for i, t in enumerate(rows):
            tag = "考试" if t.kind == "exam" else "作业"
            title = "%s · %s" % (tag, t.title)
            if t.done:
                state, left = "✓ 完成", "—"
                color = theme.FLOAT_TEXT_DIM
            elif t.expired(now):
                state, left = "已过期", "—"
                color = theme.RED
            else:
                state = "待办"
                d = t.due - now
                if d.days >= 1:
                    left = "%d 天" % d.days
                elif d.seconds >= 3600:
                    left = "%d 小时" % (d.seconds // 3600)
                else:
                    left = "%d 分钟" % max(1, d.seconds // 60)
                color = theme.FLOAT_TEXT
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
        self.owner.tasks.remove(tid)
        self.refresh_tasks()

    def show_ocr(self, mode, text, result):
        """展示 OCR 结果（mode: 'translate' / 'summarize'）。"""
        self.nav.setCurrentRow(2)
        self.stack.setCurrentIndex(2)
        label = "截图翻译" if mode == "translate" else "截图总结"
        self.ocr_status.setText("%s · %s 字符" % (label, len(text)))
        self.ocr_source.setPlainText(text)
        self.ocr_result.setPlainText(result)

    def show_knowledge(self, course=None):
        """展示课程知识库管理页，可指定过滤课程。"""
        self.nav.setCurrentRow(3)
        self.stack.setCurrentIndex(3)
        self.refresh_knowledge_page(select_course=course)

    def refresh_knowledge_page(self, select_course=None):
        """刷新知识库页面列表与统计。"""
        kb = getattr(self.owner.brain, "knowledge", None)
        if not kb:
            return

        stats = kb.get_stats()
        self.kw_stat_label.setText(
            f"📚 已收录 {stats['course_count']} 门课程 · {stats['file_count']} 份课件 · {stats['chunk_count']} 个知识切片"
        )

        # 刷新下拉框
        cur_selection = select_course or self.kw_course_combo.currentData()
        self.kw_course_combo.blockSignals(True)
        self.kw_course_combo.clear()
        self.kw_course_combo.addItem(f"全部课程 ({stats['file_count']} 份课件)", "__ALL__")

        all_courses = list(stats['courses'])
        if hasattr(self.owner, "schedule") and self.owner.schedule:
            for c in self.owner.schedule.courses:
                if c.name and c.name not in all_courses:
                    all_courses.append(c.name)

        for cname in sorted(all_courses):
            cnt = len(kb.get_course_files(cname))
            self.kw_course_combo.addItem(f"📖 {cname} ({cnt} 份)", cname)

        if cur_selection:
            idx = self.kw_course_combo.findData(cur_selection)
            if idx >= 0:
                self.kw_course_combo.setCurrentIndex(idx)
        self.kw_course_combo.blockSignals(False)

        # 刷新表格
        target_course = self.kw_course_combo.currentData()
        if target_course == "__ALL__":
            files = kb.get_course_files(None)
        else:
            files = kb.get_course_files(target_course)

        self.kw_table.setRowCount(len(files))
        for row, f in enumerate(files):
            import os
            ext = os.path.splitext(f["filename"])[1].upper().replace(".", "")
            c_tag = f["course"] if f.get("course") else "通用讲义"
            size_kb = f["size"] / 1024
            size_str = f"{size_kb/1024:.1f} MB" if size_kb >= 1024 else f"{size_kb:.0f} KB"

            item_ext = QtWidgets.QTableWidgetItem(ext)
            item_ext.setTextAlignment(QtCore.Qt.AlignCenter)
            item_ext.setForeground(QtGui.QColor("#00B0FF"))

            item_name = QtWidgets.QTableWidgetItem(f["filename"])
            item_name.setToolTip(f["path"])
            item_name.setForeground(QtGui.QColor("#FFFFFF"))

            item_course = QtWidgets.QTableWidgetItem(c_tag)
            item_course.setTextAlignment(QtCore.Qt.AlignCenter)
            item_course.setForeground(QtGui.QColor("#A78BFA"))

            item_size = QtWidgets.QTableWidgetItem(size_str)
            item_size.setTextAlignment(QtCore.Qt.AlignCenter)
            item_size.setForeground(QtGui.QColor("#94A3B8"))

            item_chunks = QtWidgets.QTableWidgetItem(f"{f['chunks']} 切片")
            item_chunks.setTextAlignment(QtCore.Qt.AlignCenter)
            item_chunks.setForeground(QtGui.QColor("#34D399"))

            self.kw_table.setItem(row, 0, item_ext)
            self.kw_table.setItem(row, 1, item_name)
            self.kw_table.setItem(row, 2, item_course)
            self.kw_table.setItem(row, 3, item_size)
            self.kw_table.setItem(row, 4, item_chunks)

            # 操作按钮组
            act_widget = QtWidgets.QWidget()
            act_lay = QtWidgets.QHBoxLayout(act_widget)
            act_lay.setContentsMargins(4, 2, 4, 2)
            act_lay.setSpacing(6)

            btn_ask = QtWidgets.QPushButton("🔍 提问", act_widget)
            btn_ask.setStyleSheet("QPushButton{background:rgba(0,176,255,0.18);color:#00B0FF;border:1px solid #00B0FF;padding:2px 8px;border-radius:4px;font-size:11px;}"
                                  "QPushButton:hover{background:#00B0FF;color:#000;}")
            btn_ask.clicked.connect(lambda _, fn=f["filename"], cn=f["course"]: self._ask_file_ai(fn, cn))

            btn_del = QtWidgets.QPushButton("🗑", act_widget)
            btn_del.setToolTip("从知识库移除此文件")
            btn_del.setStyleSheet("QPushButton{background:rgba(255,82,82,0.15);color:#FF5252;border:1px solid #FF5252;padding:2px 6px;border-radius:4px;font-size:11px;}"
                                  "QPushButton:hover{background:#FF5252;color:#FFF;}")
            btn_del.clicked.connect(lambda _, fn=f["filename"], cn=f["course"]: self._delete_kw_file(fn, cn))

            act_lay.addWidget(btn_ask)
            act_lay.addWidget(btn_del)
            self.kw_table.setCellWidget(row, 5, act_widget)

    def _on_kw_filter_changed(self):
        self.refresh_knowledge_page()

    def _upload_courseware(self):
        """弹出文件选择框上传课件文件。"""
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "选择要导入的课件与讲义", "",
            "课件讲义文件 (*.pptx *.ppt *.pdf *.docx *.doc *.txt *.md *.png *.jpg);;所有文件 (*.*)"
        )
        if files:
            self.owner._handle_dropped_files(files)

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
        if e.button() == QtCore.Qt.LeftButton and e.y() <= 48:
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
