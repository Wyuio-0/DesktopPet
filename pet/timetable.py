"""课程表周视图：参考移动端架构的高级自适应周课表色块视图。

特性：
- 星期表头：自动换算当前周的公历日期（如 9.13），“今天”呈现罗德岛蓝胶囊高亮徽章与整列光晕；
- 节次时间轴：显示 1..13 节次徽章与上课时刻，当前正在进行的课程节次高亮提示；
- 现代课程卡片：Material/Arknights 色彩体系，6px 圆角卡片，彻底根治字体腰斩截断；
- 教室地点标签：@教室 标签自动换行居中，小卡片智能适配；
- 交互系统：悬浮高亮与手型光标、富文本 Tooltip、点击课程卡片触发详情弹窗、点击空白时段快捷添加课程。
"""

from datetime import date, datetime, timedelta
from PyQt5 import QtCore, QtGui, QtWidgets

from . import theme
from .schedule import _PARITY_LABEL, WEEKDAY_NAMES

RULER_W = 56         # 左侧节次/时间轴宽度
HEADER_H = 46        # 顶部星期/日期标题高度
MARGIN = 8
GAP = 4              # 课程块之间的垂直与水平微间隙
MAX_SECTIONS = 13    # 一天最多 13 节课

# 列序选项：周日开始 vs 周一开始
COL_WEEKDAYS_SUNDAY = [7, 1, 2, 3, 4, 5, 6]
COL_WEEKDAYS_MONDAY = [1, 2, 3, 4, 5, 6, 7]
_COL_WEEKDAYS = COL_WEEKDAYS_SUNDAY  # 兼容旧引用
_DAY_LABELS = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}

# 对齐移动端的 10 种 Material Design 护眼课程配色板
COURSE_COLORS = [
    QtGui.QColor(66, 133, 244),    # 蓝 #4285F4
    QtGui.QColor(52, 168, 83),     # 绿 #34A853
    QtGui.QColor(234, 67, 53),     # 红 #EA4335
    QtGui.QColor(245, 166, 35),    # 琥珀橙 #F5A623
    QtGui.QColor(171, 71, 188),    # 紫 #AB47BC
    QtGui.QColor(0, 172, 193),     # 青 #00ACC1
    QtGui.QColor(141, 110, 99),    # 棕 #8D6E63
    QtGui.QColor(255, 112, 67),    # 橙红 #FF7043
    QtGui.QColor(38, 166, 154),    # 薄荷青 #26A69A
    QtGui.QColor(126, 87, 194),    # 靛紫 #7E57C2
]


class TimetableView(QtWidgets.QWidget):
    """自适应填满窗口的高级周课表色块视图。"""

    sig_course_clicked = QtCore.pyqtSignal(object)              # 点击课程卡片
    sig_empty_slot_clicked = QtCore.pyqtSignal(int, int)        # 点击空白格 (weekday, section)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._schedule = None
        self._eff_week = 1
        self._preview_note = False
        self._week_start_day = "sunday"
        self._courses = {wd: [] for wd in range(1, 8)}
        self._notes = []
        self._color_of = {}
        self._dates = [""] * 7       # 7 列对应的 M.d 日期
        self._date_objs = []         # 7 列对应的 date 对象
        self._today_col_idx = -1     # 今天的列索引 (0..6)
        self._current_sec = -1       # 当前时间落入的节次 (1..13)
        self._max_sections = MAX_SECTIONS

        # 鼠标交互跟踪
        self._card_rects = []        # [(QRect, Course)]
        self._slot_rects = []        # [(QRect, weekday, sec)]
        self._hovered_course = None
        self._hovered_slot = None

        self.setMouseTracking(True)
        self.setAutoFillBackground(True)
        self.setMinimumSize(600, 480)

    @property
    def col_weekdays(self):
        """当前视图生效的星期列序列。"""
        return COL_WEEKDAYS_MONDAY if self._week_start_day == "monday" else COL_WEEKDAYS_SUNDAY

    # ── 数据绑定 ──────────────────────────────────────────────────────

    def set_data(self, sched, display_week):
        """填充课表数据并重绘，计算当前周对应的实际公历日期与今天高亮。"""
        self._schedule = sched
        self._eff_week = max(1, int(display_week or 1))
        self._week_start_day = getattr(sched, "week_start_day", "sunday")
        current_week_no = sched.week_no() or 0
        self._preview_note = current_week_no < 1
        self._notes = list(sched.notes)
        self._courses = {wd: sched.courses_on(wd, None) for wd in range(1, 8)}

        # 动态自适应本周课表最大节数 (8..13)
        max_sec = 0
        for wd in range(1, 8):
            for c in sched.courses_on(wd, self._eff_week):
                if c.sec_end > max_sec:
                    max_sec = c.sec_end
        for adj in getattr(sched, "adjustments", []):
            if adj.get("type") == "substitute" and adj.get("target_week") == self._eff_week:
                t_wd = adj.get("target_weekday")
                if t_wd:
                    for c in sched.courses_on(t_wd, self._eff_week):
                        if c.sec_end > max_sec:
                            max_sec = c.sec_end
        if max_sec <= 8:
            self._max_sections = 8
        elif max_sec <= 10:
            self._max_sections = 10
        elif max_sec <= 12:
            self._max_sections = 12
        else:
            self._max_sections = 13

        # 配色映射
        self._color_of = {}
        idx = 0
        for wd in range(1, 8):
            for c in self._courses[wd]:
                if c.name not in self._color_of:
                    self._color_of[c.name] = COURSE_COLORS[idx % len(COURSE_COLORS)]
                    idx += 1

        # 计算日期与今天标记
        self._calculate_dates(sched, current_week_no)
        # 计算当前正在进行的节次
        self._calculate_current_section(sched)

        self.update()

    def _calculate_dates(self, sched, current_week_no):
        """换算本周 7 天的公历月日 (M.d)。
        支持周日开始 (7, 1..6) 或周一开始 (1..7)。
        严格以今日真实星期与自然周为锚点对齐。
        """
        self._dates = [""] * 7
        self._date_objs = []
        self._today_col_idx = -1
        today = date.today()
        today_iso = today.isoweekday()  # 1=Mon .. 7=Sun

        if self._week_start_day == "monday":
            offset_to_start = today_iso - 1
        else:
            offset_to_start = 0 if today_iso == 7 else today_iso

        cur_week_start = today - timedelta(days=offset_to_start)

        # 依据 eff_week 与 current_week_no 的周差推算目标周的起始日
        week_diff = self._eff_week - max(1, current_week_no)
        target_start = cur_week_start + timedelta(weeks=week_diff)

        for i in range(7):
            cur_day = target_start + timedelta(days=i)
            self._dates[i] = f"{cur_day.month}.{cur_day.day}"
            self._date_objs.append(cur_day)
            if cur_day == today:
                self._today_col_idx = i


    def _calculate_current_section(self, sched):
        """检测当前时间是否落在某一节课的时刻范围内。"""
        self._current_sec = -1
        if self._today_col_idx < 0:
            return
        now = datetime.now()
        cur_mins = now.hour * 60 + now.minute
        secs = getattr(sched, "sections", {}) or {}
        for r in range(1, self._max_sections + 1):
            t_str = secs.get(str(r), "")
            if ":" in t_str:
                try:
                    parts = t_str.split(":")
                    sm = int(parts[0]) * 60 + int(parts[1])
                    if sm <= cur_mins <= sm + 45:
                        self._current_sec = r
                        break
                except Exception:
                    pass

    # ── 布局尺寸计算 ──────────────────────────────────────────────────

    def _grid_rect(self):
        """网格主体矩形。"""
        x = MARGIN + RULER_W
        y = MARGIN + HEADER_H
        w = max(100, self.width() - x - MARGIN)
        h = max(100, self.height() - y - MARGIN - (24 if (self._preview_note or self._notes) else 0))
        return QtCore.QRect(x, y, w, h)

    def _col_w(self):
        return self._grid_rect().width() / len(self.col_weekdays)

    def _row_h(self):
        return self._grid_rect().height() / self._max_sections

    # ── 绘制主入口 ────────────────────────────────────────────────────

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setRenderHint(QtGui.QPainter.TextAntialiasing)

        # 整体背景（深色极客风）
        p.fillRect(self.rect(), QtGui.QColor("#101318"))

        self._paint_today_column_glow(p)
        self._paint_grid(p)
        self._paint_header(p)
        self._paint_ruler(p)
        self._paint_courses(p)
        self._paint_notes(p)
        p.end()

    def _paint_today_column_glow(self, p):
        """在今天所在列绘制非常柔和的纵向光晕引导背景。"""
        if self._today_col_idx < 0:
            return
        g = self._grid_rect()
        col_w = self._col_w()
        x = round(g.left() + self._today_col_idx * col_w)
        today_rect = QtCore.QRect(x, g.top(), round(col_w), g.height())
        p.fillRect(today_rect, QtGui.QColor(0, 176, 255, 12))

    def _paint_grid(self, p):
        """绘制网格基准线。"""
        g = self._grid_rect()
        row_h = self._row_h()
        col_w = self._col_w()

        # 横向分隔线
        pen_line = QtGui.QPen(QtGui.QColor("#1E2532"), 1)
        p.setPen(pen_line)
        for r in range(self._max_sections + 1):
            y = round(g.top() + r * row_h)
            p.drawLine(g.left(), y, g.right(), y)

        # 纵向分隔线
        for c in range(len(self.col_weekdays) + 1):
            x = round(g.left() + c * col_w)
            p.drawLine(x, g.top(), x, g.bottom())

        # 当前进行中节次横向高亮线
        if self._current_sec > 0:
            y1 = round(g.top() + (self._current_sec - 1) * row_h)
            y2 = round(g.top() + self._current_sec * row_h)
            cur_slot_rect = QtCore.QRect(g.left(), y1, g.width(), y2 - y1)
            p.fillRect(cur_slot_rect, QtGui.QColor(0, 176, 255, 18))

    def _paint_header(self, p):
        """顶部星期表头，包含星期、公历日期以及今天胶囊高亮。"""
        col_w = self._col_w()
        g = self._grid_rect()

        for i, wd in enumerate(self.col_weekdays):
            col_x = round(g.left() + i * col_w)
            is_today = (i == self._today_col_idx)
            header_rect = QtCore.QRect(col_x + 2, MARGIN + 2, round(col_w) - 4, HEADER_H - 4)

            # 今天高亮胶囊背景
            if is_today:
                p.setBrush(QtGui.QBrush(QtGui.QColor(0, 176, 255, 45)))
                p.setPen(QtGui.QPen(QtGui.QColor(0, 176, 255, 180), 1))
                p.drawRoundedRect(header_rect, 6, 6)

            # 星期文字
            day_name = _DAY_LABELS[wd]
            p.setFont(QtGui.QFont(theme.FONT, 11, QtGui.QFont.Bold if is_today else QtGui.QFont.DemiBold))
            p.setPen(QtGui.QColor("#00B0FF" if is_today else "#E2E8F0"))
            w_rect = QtCore.QRect(col_x, MARGIN + 4, round(col_w), 16)
            p.drawText(w_rect, QtCore.Qt.AlignCenter, day_name)

            # 公历日期 (例如 9.13)
            date_str = self._dates[i] if i < len(self._dates) and self._dates[i] else ""
            if date_str:
                p.setFont(QtGui.QFont(theme.FONT, 9, QtGui.QFont.Bold if is_today else QtGui.QFont.Normal))
                p.setPen(QtGui.QColor("#00B0FF" if is_today else "#64748B"))
                d_rect = QtCore.QRect(col_x, MARGIN + 22, round(col_w), 16)
                p.drawText(d_rect, QtCore.Qt.AlignCenter, date_str)

            # 调课/停课徽章 (感知教学安排调整)
            if i < len(self._date_objs) and self._schedule:
                col_d = self._date_objs[i]
                d_str = col_d.isoformat()
                adj = next((a for a in getattr(self._schedule, "adjustments", []) if a.get("date") == d_str), None)
                if adj and adj.get("type") in ("suspend", "substitute"):
                    badge_text = "停课" if adj.get("type") == "suspend" else "调"
                    badge_bg = QtGui.QColor(251, 140, 0, 180) if adj.get("type") == "suspend" else QtGui.QColor(0, 229, 255, 180)
                    b_rect = QtCore.QRect(col_x + round(col_w) - 24, MARGIN + 4, 20, 12)
                    p.setBrush(QtGui.QBrush(badge_bg))
                    p.setPen(QtCore.Qt.NoPen)
                    p.drawRoundedRect(b_rect, 3, 3)
                    p.setFont(QtGui.QFont(theme.FONT, 7, QtGui.QFont.Bold))
                    p.setPen(QtGui.QColor("#000000" if adj.get("type") == "substitute" else "#FFFFFF"))
                    p.drawText(b_rect, QtCore.Qt.AlignCenter, badge_text)

    def _paint_ruler(self, p):
        """左侧时间轴：节次编号与开始时刻，高亮当前节次。"""
        g = self._grid_rect()
        row_h = self._row_h()
        secs = getattr(self._schedule, "sections", {}) or {}

        for r in range(self._max_sections):
            sec = r + 1
            is_cur = (sec == self._current_sec)
            y = round(g.top() + r * row_h)
            slot_h = round(row_h)

            ruler_rect = QtCore.QRect(MARGIN, y + 2, RULER_W - 6, slot_h - 4)

            # 正在上课节次背景标记
            if is_cur:
                p.setBrush(QtGui.QBrush(QtGui.QColor(0, 176, 255, 60)))
                p.setPen(QtGui.QPen(QtGui.QColor(0, 176, 255), 1))
                p.drawRoundedRect(ruler_rect, 4, 4)

            # 节次编号 (上)
            p.setFont(QtGui.QFont(theme.FONT, 9, QtGui.QFont.Bold if is_cur else QtGui.QFont.DemiBold))
            p.setPen(QtGui.QColor("#00B0FF" if is_cur else "#94A3B8"))
            sec_rect = QtCore.QRect(MARGIN, y + 2, RULER_W - 6, 14)
            p.drawText(sec_rect, QtCore.Qt.AlignCenter, str(sec))

            # 开始时刻 (下)
            t = secs.get(str(sec), "")
            if t:
                p.setFont(QtGui.QFont(theme.FONT, 8))
                p.setPen(QtGui.QColor("#00B0FF" if is_cur else "#64748B"))
                time_rect = QtCore.QRect(MARGIN, y + 17, RULER_W - 6, 13)
                p.drawText(time_rect, QtCore.Qt.AlignCenter, t)

    def _paint_courses(self, p):
        """绘制所有有效课程卡片，记录命中区域供点击交互。"""
        self._card_rects = []
        self._slot_rects = []

        if self._schedule is None:
            return

        g = self._grid_rect()
        col_w = self._col_w()
        row_h = self._row_h()

        # 遍历每一列（周日 ~ 周六 或 周一 ~ 周日）
        for i, wd in enumerate(self.col_weekdays):
            col_x = round(g.left() + i * col_w)
            col_date = self._date_objs[i] if i < len(self._date_objs) else None
            adj = None
            if col_date and hasattr(self._schedule, "courses_for_grid"):
                active_courses, adj = self._schedule.courses_for_grid(col_date, wd, self._eff_week)
            else:
                active_courses = [c for c in self._courses[wd] if c.active_on(self._eff_week)]

            is_substitute = bool(adj and adj.get("type") == "substitute")
            if adj and adj.get("type") == "suspend":
                # 绘制整列停课放假卡片
                hol_rect = QtCore.QRect(col_x + 2, round(g.top() + 2), round(col_w) - 4, round(g.height() - 4))
                p.setBrush(QtGui.QBrush(QtGui.QColor(251, 140, 0, 18)))
                p.setPen(QtGui.QPen(QtGui.QColor(251, 140, 0, 90), 1, QtCore.Qt.DashLine))
                p.drawRoundedRect(hol_rect, 6, 6)
                p.setFont(QtGui.QFont(theme.FONT, 10, QtGui.QFont.Bold))
                p.setPen(QtGui.QColor("#FFA726"))
                reason = adj.get("reason") or "停课"
                p.drawText(hol_rect, QtCore.Qt.AlignCenter, f"🏖️\n\n{reason}\n全天停课")
                continue

            # 记录空白可点击格
            for sec in range(1, self._max_sections + 1):
                occupied = any(c.sec_start <= sec <= c.sec_end for c in active_courses)
                if not occupied:
                    slot_y = round(g.top() + (sec - 1) * row_h)
                    slot_rect = QtCore.QRect(col_x + 2, slot_y + 1, round(col_w) - 4, round(row_h) - 2)
                    self._slot_rects.append((slot_rect, wd, sec))

                    # 空白格悬浮加号微光
                    if self._hovered_slot == (wd, sec):
                        p.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 10)))
                        p.setPen(QtGui.QPen(QtGui.QColor("#00B0FF"), 1, QtCore.Qt.DashLine))
                        p.drawRoundedRect(slot_rect, 4, 4)

            # 绘制课程卡片（支持重叠课程水平等分并列排布，彻底杜绝互相遮挡）
            sorted_courses = sorted(active_courses, key=lambda c: (c.sec_start, -(c.sec_end - c.sec_start)))
            clusters = []
            for c in sorted_courses:
                placed = False
                for cl in clusters:
                    if any(max(c.sec_start, x.sec_start) <= min(c.sec_end, x.sec_end) for x in cl):
                        cl.append(c)
                        placed = True
                        break
                if not placed:
                    clusters.append([c])

            for cl in clusters:
                slots = []
                c_slots = {}
                for c in cl:
                    assigned = False
                    for s_idx, end_sec in enumerate(slots):
                        if end_sec < c.sec_start:
                            slots[s_idx] = c.sec_end
                            c_slots[c] = s_idx
                            assigned = True
                            break
                    if not assigned:
                        c_slots[c] = len(slots)
                        slots.append(c.sec_end)
                total_slots = len(slots)

                for c in cl:
                    slot_idx = c_slots[c]
                    sub_w = (col_w - 4) / total_slots
                    x = col_x + 2 + slot_idx * sub_w
                    y = round(g.top() + (c.sec_start - 1) * row_h + 1)
                    h = round((c.sec_end - c.sec_start + 1) * row_h - GAP)
                    w = round(sub_w - (1 if total_slots > 1 else 0))
                    rect = QtCore.QRect(round(x), y, max(4, w), max(4, h))
                    self._card_rects.append((rect, c))

                    base_color = self._color_of.get(c.name, COURSE_COLORS[0])
                    is_hovered = (self._hovered_course == c)

                    # 卡片背景绘制：微渐变或悬浮增亮
                    card_color = QtGui.QColor(base_color)
                    if is_hovered:
                        card_color = card_color.lighter(115)

                    p.setBrush(QtGui.QBrush(card_color))
                    border_color = QtGui.QColor(card_color).lighter(130) if is_hovered else QtGui.QColor(card_color).darker(110)
                    p.setPen(QtGui.QPen(border_color, 1))
                    p.drawRoundedRect(rect, 6, 6)

                    # 绘制卡片内排版文字（彻底修复文字截断与重叠）
                    self._paint_course_card_content(p, rect, c, is_substitute)

    def _paint_course_card_content(self, p, rect, c, is_substitute=False):
        """精准排版课程名称与地点，自适应高度与宽度，绝不腰斩截断文字。"""
        inner = rect.adjusted(5, 5, -5, -4)
        if inner.height() < 16 or inner.width() < 14:
            return

        total_h = inner.height()

        # 调课徽章
        if is_substitute and total_h >= 24:
            p.setBrush(QtGui.QBrush(QtGui.QColor(0, 229, 255, 230)))
            p.setPen(QtCore.Qt.NoPen)
            tag_rect = QtCore.QRect(inner.right() - 16, inner.top(), 16, 11)
            p.drawRoundedRect(tag_rect, 2, 2)
            p.setFont(QtGui.QFont(theme.FONT, 7, QtGui.QFont.Bold))
            p.setPen(QtGui.QColor("#000000"))
            p.drawText(tag_rect, QtCore.Qt.AlignCenter, "调")

        # 自定义时间标记 (如 📌15:00-17:00)
        custom_time = getattr(c, "custom_time", "")
        top_offset = 0
        if custom_time and total_h >= 45:
            p.setFont(QtGui.QFont(theme.FONT, 7, QtGui.QFont.Bold))
            p.setPen(QtGui.QColor("#FFE082"))
            rfm = QtGui.QFontMetrics(p.font())
            time_text = rfm.elidedText("📌" + custom_time, QtCore.Qt.ElideRight, inner.width())
            time_rect = QtCore.QRect(inner.left(), inner.top(), inner.width(), 13)
            p.drawText(time_rect, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop, time_text)
            top_offset = 14

        # 单节短卡片（高度很小）：居中显示一行课程名
        if total_h < 40:
            p.setFont(QtGui.QFont(theme.FONT, 9, QtGui.QFont.Bold))
            p.setPen(QtGui.QColor(255, 255, 255))
            fm = QtGui.QFontMetrics(p.font())
            elided = fm.elidedText(c.name, QtCore.Qt.ElideRight, inner.width())
            p.drawText(inner, QtCore.Qt.AlignCenter, elided)
            return

        # 常规 2 节及以上课程卡片：上部课程名称，下部教室地点
        # 1. 课程名：根据可用高度分配行数（最多 2 或 3 行）
        name_font = QtGui.QFont(theme.FONT, 10 if inner.width() >= 50 else 8, QtGui.QFont.Bold)
        p.setFont(name_font)
        fm = QtGui.QFontMetrics(name_font)
        line_h = fm.lineSpacing()

        has_room = bool(c.room)
        reserved_bottom = 20 if has_room else 0
        avail_name_h = max(line_h, total_h - reserved_bottom - top_offset)
        max_lines = max(1, avail_name_h // line_h)

        name_rect = QtCore.QRect(inner.left(), inner.top() + top_offset, inner.width(), max_lines * line_h)
        p.setPen(QtGui.QColor(255, 255, 255))
        p.drawText(name_rect, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop | QtCore.Qt.TextWordWrap, c.name)

        # 2. 教室与地点（@理学楼-401）
        if has_room and total_h >= 45:
            room_text = f"@{c.room}"
            p.setFont(QtGui.QFont(theme.FONT, 8 if inner.width() >= 50 else 7, QtGui.QFont.Normal))
            p.setPen(QtGui.QColor(240, 245, 255, 220))
            rfm = QtGui.QFontMetrics(p.font())
            elided_room = rfm.elidedText(room_text, QtCore.Qt.ElideRight, inner.width())

            room_y = min(inner.bottom() - 14, name_rect.bottom() + 2)
            room_rect = QtCore.QRect(inner.left(), room_y, inner.width(), 16)
            p.drawText(room_rect, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter, elided_room)

    def _paint_notes(self, p):
        """学期预览与网课说明。"""
        g = self._grid_rect()
        y = g.bottom() + 6
        if self._preview_note and self._schedule is not None:
            ts = getattr(self._schedule, "term_start", None)
            head = "学期尚未开始" + (f"（{ts.isoformat()} 开学）" if ts else "")
            p.setFont(QtGui.QFont(theme.FONT, 10, QtGui.QFont.Bold))
            p.setPen(QtGui.QColor(theme.FLOAT_GOLD))
            p.drawText(QtCore.QRect(MARGIN, y, self.width() - 2 * MARGIN, 20),
                       QtCore.Qt.AlignLeft,
                       f"⚠ {head} —— 以下为第 {self._eff_week} 周课表预览")
            y += 20
        if self._notes:
            p.setFont(QtGui.QFont(theme.FONT, 9))
            p.setPen(QtGui.QColor(theme.FLOAT_TEXT_DIM))
            p.drawText(QtCore.QRect(MARGIN, y, self.width() - 2 * MARGIN, 20),
                       QtCore.Qt.AlignLeft,
                       "网课说明：" + "；".join(self._notes))

    # ── 鼠标与交互事件 ────────────────────────────────────────────────

    def mouseMoveEvent(self, event):
        pos = event.pos()
        new_hovered_course = None
        new_hovered_slot = None

        # 检查是否命中课程卡片
        for rect, c in self._card_rects:
            if rect.contains(pos):
                new_hovered_course = c
                break

        # 检查是否命中空白格
        if not new_hovered_course:
            for rect, wd, sec in self._slot_rects:
                if rect.contains(pos):
                    new_hovered_slot = (wd, sec)
                    break

        need_repaint = False
        if new_hovered_course != self._hovered_course:
            self._hovered_course = new_hovered_course
            need_repaint = True
            if self._hovered_course:
                self.setCursor(QtCore.Qt.PointingHandCursor)
                self._show_course_tooltip(self._hovered_course)
            else:
                QtWidgets.QToolTip.hideText()

        if new_hovered_slot != self._hovered_slot:
            self._hovered_slot = new_hovered_slot
            need_repaint = True
            if self._hovered_slot and not self._hovered_course:
                self.setCursor(QtCore.Qt.PointingHandCursor)
                wd, sec = self._hovered_slot
                QtWidgets.QToolTip.showText(
                    self.mapToGlobal(pos),
                    f"点击在此录入新课程：{_DAY_LABELS[wd]} 第 {sec} 节",
                    self
                )
            elif not self._hovered_course:
                self.unsetCursor()
                QtWidgets.QToolTip.hideText()

        if need_repaint:
            self.update()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hovered_course = None
        self._hovered_slot = None
        self.unsetCursor()
        QtWidgets.QToolTip.hideText()
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            pos = event.pos()
            # 1. 点击课程卡片
            for rect, c in self._card_rects:
                if rect.contains(pos):
                    self.sig_course_clicked.emit(c)
                    return

            # 2. 点击空白格子
            for rect, wd, sec in self._slot_rects:
                if rect.contains(pos):
                    self.sig_empty_slot_clicked.emit(wd, sec)
                    return

        super().mousePressEvent(event)

    def _show_course_tooltip(self, c):
        """展示课程悬浮详细气泡。"""
        wd_str = _DAY_LABELS.get(c.weekday, f"周{c.weekday}")
        secs = getattr(self._schedule, "sections", {}) or {}
        t1 = secs.get(str(c.sec_start), "")
        t2 = secs.get(str(c.sec_end), "")
        time_str = f" ({t1}-{t2})" if t1 and t2 else ""
        parity_str = {"all": "全部周", "odd": "单周", "even": "双周"}.get(c.parity, "")

        tip_html = f"""
        <div style="font-family:'Microsoft YaHei UI'; padding:4px;">
            <b style="font-size:13px; color:#00B0FF;">{c.name}</b><br/>
            <span>⏰ 时间：{wd_str} 第 {c.sec_start}-{c.sec_end} 节{time_str}</span><br/>
            <span>📅 周次：第 {c.week_start}-{c.week_end} 周 ({parity_str})</span><br/>
            <span>📍 教室：{c.room or '未指定'}</span><br/>
            <span>👤 教师：{c.teacher or '未指定'}</span>
        </div>
        """
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), tip_html, self)
