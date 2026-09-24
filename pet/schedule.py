"""课程表：解析强智教务课表 JSON，提供查询与上课提醒。

数据链路
--------
用户从教务系统浏览器 Network 面板复制课表 JSON（xskbcx_cxXsksxxlist 响应），
本模块把它解析成内部 Course 列表并缓存，供菜单展示、上课提醒、AI 查询使用。

存储（均在用户数据目录，%APPDATA%\\AmiyaPet\\，不进仓库）：
  schedule_raw.json   强智原始 JSON（用户粘贴，留档便于每学期重新导入）
  schedule.json       解析后的内部格式（含 term_start / sections 等配置）

解析要点（强智字段 → 内部字段）：
  kcmc 课程名 | xqj 星期(1-7) | jc 节次("1-2") | zcd 周次("1-14周"/"8-12周(双)")
  cdmc 教室 | xm 教师 | xqmc 校区
特殊记录：pkbj=0 且 cdmc="未排地点" 的课（如实验课），教室从 xkbz 备注里捞。
sjkList 里的"无时间无地点"课（网课）不参与提醒，仅作展示。

节次时刻表（sections）与学期开始日期（term_start）都在 schedule.json 里，
可按本校作息修改。
"""

import json
import os
import re
import uuid
from datetime import date, datetime, timedelta

from .settings import config_dir

# 常见作息（仅作默认展示，具体以 schedule.json 的 sections 为准）。
DEFAULT_SECTIONS = {
    "1": "08:00", "2": "08:50", "3": "09:50", "4": "10:40", "5": "11:30",
    "6": "14:05", "7": "14:55", "8": "15:45", "9": "16:40",
    "10": "17:30", "11": "18:30", "12": "19:20", "13": "20:10",
}
WEEKDAY_NAMES = {1: "周一", 2: "周二", 3: "周三", 4: "周四",
                 5: "周五", 6: "周六", 7: "周日"}
_PARITY_LABEL = {"all": "", "odd": "单", "even": "双"}


def _raw_path():
    return os.path.join(config_dir(), "schedule_raw.json")


def _data_path():
    return os.path.join(config_dir(), "schedule.json")


def parse_weeks(zcd):
    """'1-14周' -> (1, 14, 'all'); '8-12周(双)' -> (8, 12, 'even'); '单' 同理。

    返回 (start, end, parity) 或 None（解析失败）。
    """
    m = re.search(r"(\d+)\s*-\s*(\d+)", zcd or "")
    if not m:
        return None
    start, end = int(m.group(1)), int(m.group(2))
    parity = "even" if "双" in zcd else ("odd" if "单" in zcd else "all")
    return (start, end, parity)


def parse_sections(jc):
    """'1-2节' 或 '1-2' -> (1, 2)，返回 (start, end) 或 None。"""
    m = re.search(r"(\d+)\s*-\s*(\d+)", jc or "")
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)))


def _room_of(rec):
    """教室：正常记录直接取 cdmc；'未排地点' 时从选课备注（xkbz）里捞，
    例如 '8,10,12周日2-5节A204' -> 'A204'。"""
    cdmc = (rec.get("cdmc") or "").strip()
    if cdmc and cdmc != "未排地点":
        return cdmc
    m = re.search(r"([A-Za-z]?\d{2,4}[A-Za-z]?\d*)$", (rec.get("xkbz") or "").strip())
    return m.group(1) if m else cdmc or "待定"


class Course:
    """一条上课安排。parity: 'all' / 'odd' / 'even'。"""

    __slots__ = ("name", "weekday", "sec_start", "sec_end",
                 "week_start", "week_end", "parity",
                 "room", "teacher", "campus", "note",
                 "custom_time", "id")

    def __init__(self, name, weekday, sec_start, sec_end,
                 week_start=1, week_end=20, parity="all", room="", teacher="",
                 campus="", note="", custom_time="", id=None):
        self.name = name
        self.weekday = int(weekday)          # 1=周一 ... 7=周日
        self.sec_start = int(sec_start)
        self.sec_end = int(sec_end)
        self.week_start = int(week_start)
        self.week_end = int(week_end)
        self.parity = parity or "all"        # 'all' / 'odd' / 'even'
        self.room = room
        self.teacher = teacher
        self.campus = campus
        self.note = note
        self.custom_time = str(custom_time or "").strip()
        self.id = str(id).strip() if id else uuid.uuid4().hex

    def active_on(self, week_no):
        """第 week_no 周是否上课（含单双周规则）。"""
        if not (self.week_start <= week_no <= self.week_end):
            return False
        if self.parity == "even":
            return week_no % 2 == 0
        if self.parity == "odd":
            return week_no % 2 == 1
        return True

    def start_time(self, week_no, sections):
        """第 week_no 周本节课的开始时刻 (hour, minute)，或 None（不在表内/本周不上）。

        对 sections 里手写的时刻或 custom_time 做范围校验（0<=h<24、0<=m<60）。
        """
        if not self.active_on(week_no):
            return None
        if self.custom_time and ":" in self.custom_time:
            try:
                start_part = re.split(r"[-~至到/]", self.custom_time)[0].strip()
                hh, mm = start_part.split(":")
                h, m = int(hh), int(mm)
                if 0 <= h < 24 and 0 <= m < 60:
                    return (h, m)
            except Exception:
                pass
        hhmm = sections.get(str(self.sec_start))
        if not hhmm:
            return None
        try:
            hh, mm = hhmm.split(":")
            h, m = int(hh), int(mm)
        except (ValueError, TypeError):
            return None
        if not (0 <= h < 24 and 0 <= m < 60):
            return None
        return (h, m)

    def display(self, sections=None, show_weeks=True):
        """一行展示文本，例如「1-2节 计算机组成与体系结构A @3区2-217」。
        节次区间换算时刻（若有 sections 且两端都在表内）。"""
        if self.custom_time:
            secs = "📌[%s] %d-%d节" % (self.custom_time, self.sec_start, self.sec_end)
        else:
            secs = "%d-%d节" % (self.sec_start, self.sec_end)
        when = ""
        if sections:
            a = sections.get(str(self.sec_start))
            b = sections.get(str(self.sec_end))
            if a and b:
                when = " (%s-%s)" % (a, b)
        weeks = ""
        if show_weeks:
            weeks = " %d-%d周%s" % (self.week_start, self.week_end,
                                    _PARITY_LABEL[self.parity])
        room = " @%s" % self.room if self.room else ""
        return "%s%s %s%s%s" % (secs, when, self.name, room, weeks)


def import_strongzhi(raw, term_start):
    """把强智课表 JSON（dict）解析成 Course 列表 + 无时间课列表。

    term_start: date，第 1 周周一。返回 (courses, note_courses)。
    解析失败的条目会被跳过并记录原因，不影响其余课程。
    """
    courses, notes, skipped = [], [], []
    for rec in raw.get("kbList", []):
        weeks = parse_weeks(rec.get("zcd"))
        secs = parse_sections(rec.get("jc"))
        name = (rec.get("kcmc") or "").strip()
        if not weeks or not secs or not name:
            skipped.append((name or "?", rec.get("zcd"), rec.get("jc")))
            continue
        try:
            weekday = int(rec.get("xqj", 0))
            if not 1 <= weekday <= 7:
                raise ValueError("xqj=%s" % rec.get("xqj"))
        except (TypeError, ValueError):
            skipped.append((name, rec.get("zcd"), "xqj=" + str(rec.get("xqj"))))
            continue
        w1, w2, parity = weeks
        courses.append(Course(
            name=name, weekday=weekday,
            sec_start=secs[0], sec_end=secs[1],
            week_start=w1, week_end=w2, parity=parity,
            room=_room_of(rec),
            teacher=(rec.get("xm") or "").strip(),
            campus=(rec.get("xqmc") or "").strip(),
            note="实验" if str(rec.get("pkbj")) == "0" else "",
        ))
    for rec in raw.get("sjkList", []):
        name = (rec.get("kcmc") or "").strip()
        if name:
            notes.append("%s / %s / %s" % (name, rec.get("jsxm", ""),
                                           rec.get("qsjsz", "")))
    return courses, notes, skipped


class Schedule:
    """加载/保存内部格式，提供按天/按周查询与"下一节课"。

    内部格式（schedule.json）：
    {
      "term": "2026-2027-1",
      "term_start": "2026-09-07",        # 第 1 周周一
      "sections": {"1": "08:00", ...},   # 节次时刻表，可按校作息修改
      "courses": [ {...}, ... ]
    }
    """

    def __init__(self, path=None):
        self.path = path or _data_path()
        self.term = ""
        self.term_start = None            # date
        self.sections = dict(DEFAULT_SECTIONS)
        self.remind_minutes = 10          # 上课前多少分钟提醒
        self.week_start_day = "sunday"    # 周课表起始日: "sunday" / "monday"
        self.courses = []
        self.notes = []                   # 无时间课说明文本
        self.adjustments = []             # 教学安排调整（调课/停课）
        self._listeners = []              # 数据变更监听器回调列表
        self.load()

    # ── 监听机制 ───────────────────────────────────────────────────

    def register_listener(self, fn):
        """注册课表数据变更监听器（在新增/修改/删除后触发）。"""
        if fn not in self._listeners:
            self._listeners.append(fn)

    def unregister_listener(self, fn):
        """注销监听器。"""
        if fn in self._listeners:
            self._listeners.remove(fn)

    def _notify_listeners(self):
        for fn in list(self._listeners):
            try:
                fn()
            except Exception:
                pass

    # ── 持久化 ─────────────────────────────────────────────────────

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        self.term = str(data.get("term", ""))
        self.adjustments = list(data.get("adjustments", []))
        try:
            self.term_start = date.fromisoformat(str(data["term_start"]))
        except Exception:
            self.term_start = None
        sections = data.get("sections") or {}
        sec_map = dict(DEFAULT_SECTIONS)
        sec_map.update({str(k): str(v) for k, v in sections.items()})
        if sec_map.get("9") in ("16:30", "16:35"):
            sec_map["9"] = "16:40"
        if sec_map.get("10") == "18:30":
            sec_map["10"] = "17:30"
        if sec_map.get("11") == "19:20":
            sec_map["11"] = "18:30"
        if sec_map.get("12") == "20:10":
            sec_map["12"] = "19:20"
        if sec_map.get("13") == "21:00":
            sec_map["13"] = "20:10"
        self.sections = sec_map
        self.remind_minutes = max(1, int(data.get("remind_minutes", 10) or 10))
        self.week_start_day = str(data.get("week_start_day", "sunday")).lower()
        if self.week_start_day not in ("monday", "sunday"):
            self.week_start_day = "sunday"
        self.courses = []
        for c in data.get("courses", []):
            try:
                self.courses.append(Course(
                    name=c["name"], weekday=c["weekday"],
                    sec_start=c["sec_start"], sec_end=c["sec_end"],
                    week_start=c["week_start"], week_end=c["week_end"],
                    parity=c.get("parity", "all"),
                    room=c.get("room", ""), teacher=c.get("teacher", ""),
                    campus=c.get("campus", ""), note=c.get("note", ""),
                    custom_time=c.get("custom_time", ""),
                    id=c.get("id")))
            except (KeyError, TypeError, ValueError):
                continue
        self.notes = list(data.get("notes", []))

    def save(self, term="", term_start=None, courses=None, notes=None,
             sections=None, week_start_day=None):
        if courses is not None:
            self.courses = courses
        if notes is not None:
            self.notes = notes
        if term:
            self.term = term
        if term_start:
            self.term_start = term_start
        if sections:
            self.sections = sections
        if week_start_day is not None:
            start_day = str(week_start_day).lower()
            if start_day in ("monday", "sunday"):
                self.week_start_day = start_day
        payload = {
            "term": self.term,
            "term_start": self.term_start.isoformat() if self.term_start else "",
            "sections": self.sections,
            "remind_minutes": self.remind_minutes,
            "week_start_day": self.week_start_day,
            "courses": [self._course_dict(c) for c in self.courses],
            "notes": self.notes,
            "adjustments": self.adjustments,
        }
        try:
            d = os.path.dirname(self.path)
            if d:
                os.makedirs(d, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            self._notify_listeners()
            return True
        except Exception:
            return False

    def set_week_start_day(self, start_day):
        """设置周课表起始日 ('sunday' 或 'monday') 并保存。"""
        start_day = str(start_day).lower()
        if start_day not in ("monday", "sunday"):
            start_day = "sunday"
        self.week_start_day = start_day
        return self.save()

    @staticmethod
    def _course_dict(c):
        return {"name": c.name, "weekday": c.weekday,
                "sec_start": c.sec_start, "sec_end": c.sec_end,
                "week_start": c.week_start, "week_end": c.week_end,
                "parity": c.parity, "room": c.room, "teacher": c.teacher,
                "campus": c.campus, "note": c.note,
                "custom_time": getattr(c, "custom_time", ""),
                "id": getattr(c, "id", "")}

    # ── 查询 ───────────────────────────────────────────────────────

    def week_no(self, day=None):
        """今天（或给定日期）是第几周（1 起）。term_start 未配置时返回 None。"""
        day = day or date.today()
        if not self.term_start:
            return None
        delta = day - self.term_start
        if delta.days < 0:
            return 0
        return delta.days // 7 + 1

    def courses_on(self, weekday, week_no=None):
        """某天（weekday 1-7）的课程；week_no 为 None 时不做周次过滤。"""
        out = [c for c in self.courses if c.weekday == weekday]
        if week_no is not None:
            out = [c for c in out if c.active_on(week_no)]
        return sorted(out, key=lambda c: c.sec_start)

    def courses_for_day(self, day=None):
        """获取指定公历日期的课程（感知教学安排调课与放假停课）。"""
        day = day or date.today()
        day_str = day.isoformat()
        adj = next((a for a in self.adjustments if a.get("date") == day_str), None)
        if adj:
            if adj.get("type") == "suspend":
                return []
            if adj.get("type") == "substitute":
                target_wd = adj.get("target_weekday") or day.isoweekday()
                target_wk = adj.get("target_week") or self.week_no(day) or 1
                return self.courses_on(target_wd, target_wk)
        week_no = self.week_no(day) or 1
        return self.courses_on(day.isoweekday(), week_no)

    def courses_for_grid(self, cur_date, default_weekday, default_week_no):
        """为周视图网格某一列返回课程列表与生效的调整规则 (courses, adj)。"""
        day_str = cur_date.isoformat()
        adj = next((a for a in self.adjustments if a.get("date") == day_str), None)
        if adj:
            if adj.get("type") == "suspend":
                return [], adj
            if adj.get("type") == "substitute":
                target_wd = adj.get("target_weekday") or default_weekday
                target_wk = adj.get("target_week") or default_week_no
                return self.courses_on(target_wd, target_wk), adj
        return self.courses_on(default_weekday, default_week_no), None

    def add_adjustments(self, new_adjustments):
        """添加或更新教学安排调整。"""
        dates_to_add = {a.get("date") for a in new_adjustments if a.get("date")}
        self.adjustments = [a for a in self.adjustments if a.get("date") not in dates_to_add] + new_adjustments
        return self.save()

    def clear_adjustments(self):
        """清空所有教学安排调整。"""
        self.adjustments = []
        return self.save()

    def today(self, week_no=None):
        if week_no is None:
            return self.courses_for_day(date.today())
        return self.courses_on(date.today().isoweekday(), week_no)

    def next_class(self, now=None, week_no=None):
        """从 now 起最近的下一节课（若本周无后续课，自动跨周推算下一周首节课），返回 (course, weekday, week_no,
        start_datetime) 或 None（整学期已无后续课）。"""
        now = now or datetime.now()
        if week_no is None:
            week_no = self.week_no(now.date())
        if not week_no or week_no <= 0:
            return None
        today_idx = now.isoweekday()
        # 1. 优先查本周剩余天
        for offset in range(0, 7 - today_idx + 1):
            weekday = today_idx + offset
            if weekday > 7:
                continue
            day = now.date() + timedelta(days=offset)
            for c in self.courses_on(weekday, week_no):
                hm = c.start_time(week_no, self.sections)
                if hm is None:
                    continue
                target = datetime.combine(day, datetime.min.time()) \
                    .replace(hour=hm[0], minute=hm[1])
                if target > now:
                    return (c, weekday, week_no, target)

        # 2. 本周已无后续课，跨周推算下一周 (week_no + 1)
        next_week = week_no + 1
        days_until_next_monday = 8 - today_idx
        for offset in range(days_until_next_monday, days_until_next_monday + 7):
            day = now.date() + timedelta(days=offset)
            weekday = day.isoweekday()
            for c in self.courses_on(weekday, next_week):
                hm = c.start_time(next_week, self.sections)
                if hm is None:
                    continue
                target = datetime.combine(day, datetime.min.time()) \
                    .replace(hour=hm[0], minute=hm[1])
                if target > now:
                    return (c, weekday, next_week, target)
        return None

    def dump_text(self, week_no=None):
        """整张课表文本（按星期排），week_no 用于标注单双周实际是否上课。"""
        lines = []
        for wd in range(1, 8):
            courses = self.courses_on(wd, None)   # 不过滤周次，才能标出"本周不上"
            if not courses:
                continue
            lines.append(WEEKDAY_NAMES[wd])
            for c in courses:
                mark = ""
                if week_no and not c.active_on(week_no):
                    mark = "  [本周不上]"
                lines.append("  " + c.display(self.sections) + mark)
        if self.notes:
            lines.append("无时间课程（网课）：")
            lines.extend("  - " + n for n in self.notes)
        return "\n".join(lines)

    # ── 增删改 ─────────────────────────────────────────────────────

    @staticmethod
    def _course_matches(c, target):
        if c is target:
            return True
        c_id = getattr(c, "id", None)
        t_id = getattr(target, "id", None)
        if c_id and t_id and c_id == t_id:
            return True
        return (c.name == target.name and
                c.weekday == target.weekday and
                c.sec_start == target.sec_start and
                c.sec_end == target.sec_end and
                c.week_start == target.week_start and
                c.week_end == target.week_end and
                c.parity == target.parity and
                c.room == target.room and
                getattr(c, "custom_time", "") == getattr(target, "custom_time", ""))

    def add_course(self, course):
        """新增一门课程并保存。"""
        self.courses.append(course)
        return self.save()

    def update_course(self, old_course, new_course):
        """修改指定课程并保存。"""
        for i, c in enumerate(self.courses):
            if self._course_matches(c, old_course):
                self.courses[i] = new_course
                return self.save()
        return False

    def delete_course(self, target_course):
        """删除指定课程并保存。"""
        for i, c in enumerate(self.courses):
            if self._course_matches(c, target_course):
                del self.courses[i]
                return self.save()
        return False

    def snap_time_to_sections(self, start_time_str, end_time_str):
        """将任意时间范围（如 '14:15', '15:30'）智能吸附到课表 13 节体系中的最近节次区间。"""
        return snap_time_to_sections_standalone(start_time_str, end_time_str, self.sections)

    def find_target_course(self, name, weekday=None, sec_start=None, target_week=None, room=None):
        """智能定位与打分匹配课表已有日程/课程（对齐移动端算法）。"""
        if not self.courses:
            return None
        clean_query = re.sub(r"^(?:一门|一节|个|场|次)?(?:课程|日程|活动|课)?", "", (name or "").strip())
        clean_query = re.sub(r"(?:课|课程)$", "", clean_query).strip()

        best_match = None
        best_score = -1

        for c in self.courses:
            score = 0
            c_name = c.name.strip()
            clean_c_name = re.sub(r"(?:课|课程)$", "", c_name).strip()

            # 1. 名称匹配与评分 (0 ~ 100)
            if clean_query:
                if c_name.lower() == (name or "").strip().lower() or clean_c_name.lower() == clean_query.lower():
                    score += 100
                elif clean_query.lower() in clean_c_name.lower() or clean_c_name.lower() in clean_query.lower():
                    score += 70
                elif len(clean_query) >= 2 and (clean_query[:2].lower() in clean_c_name.lower() or clean_c_name[:2].lower() in clean_query.lower()):
                    score += 40
                else:
                    continue
            else:
                score += 20

            # 2. 星期打分 (40)
            if weekday is not None:
                if c.weekday == int(weekday):
                    score += 40
                else:
                    continue

            # 3. 节次打分 (30)
            if sec_start is not None:
                sec_val = int(sec_start)
                if c.sec_start == sec_val or (c.sec_start <= sec_val <= c.sec_end):
                    score += 30
                elif abs(c.sec_start - sec_val) <= 2:
                    score += 10

            # 4. 周次打分 (25)
            if target_week is not None:
                tw = int(target_week)
                if c.active_on(tw):
                    score += 25
                    if c.week_start == c.week_end == tw:
                        score += 10

            # 5. 地点打分 (15)
            if room and c.room:
                if room.lower() in c.room.lower() or c.room.lower() in room.lower():
                    score += 15

            if score > best_score:
                best_score = score
                best_match = c

        return best_match

    def delete_course_matching(self, name, weekday=None, sec_start=None, target_week=None, room=None, delete_all_weeks=True):
        """根据删除请求智能匹配并删除课程（支持单周删除与整门删除）。"""
        target = self.find_target_course(name=name, weekday=weekday, sec_start=sec_start, target_week=target_week, room=room)
        if not target:
            return None

        if delete_all_weeks or target.week_start == target.week_end or target_week is None:
            self.delete_course(target)
            return target

        t_week = int(target_week)
        if t_week < target.week_start or t_week > target.week_end:
            self.delete_course(target)
            return target

        # 单周豁免：若删除的是首周或末周，缩窄周次；否则拆分为前后两段
        if t_week == target.week_start:
            target.week_start += 1
            self.save()
        elif t_week == target.week_end:
            target.week_end -= 1
            self.save()
        else:
            part1 = Course(
                name=target.name, weekday=target.weekday,
                sec_start=target.sec_start, sec_end=target.sec_end,
                week_start=target.week_start, week_end=t_week - 1,
                parity=target.parity, room=target.room, teacher=target.teacher,
                campus=target.campus, note=target.note, custom_time=target.custom_time
            )
            part2 = Course(
                name=target.name, weekday=target.weekday,
                sec_start=target.sec_start, sec_end=target.sec_end,
                week_start=t_week + 1, week_end=target.week_end,
                parity=target.parity, room=target.room, teacher=target.teacher,
                campus=target.campus, note=target.note, custom_time=target.custom_time
            )
            self.courses = [c for c in self.courses if not self._course_matches(c, target)] + [part1, part2]
            self.save()
        return target

    def modify_course_matching(self, target_name, target_weekday=None, target_sec_start=None, target_week=None,
                               new_name=None, new_weekday=None, new_sec_start=None, new_sec_end=None,
                               new_room=None, new_teacher=None, new_custom_time=None, new_week_start=None, new_week_end=None):
        """根据修改请求智能匹配并修改课程/日程。返回 (old_course, new_course) 或 (None, None)。"""
        target = self.find_target_course(name=target_name, weekday=target_weekday, sec_start=target_sec_start, target_week=target_week)
        if not target:
            return None, None

        name = str(new_name).strip() if new_name and str(new_name).strip() else target.name
        weekday = int(new_weekday) if new_weekday and 1 <= int(new_weekday) <= 7 else target.weekday
        sec_start = target.sec_start
        sec_end = target.sec_end
        if new_sec_start is not None:
            sec_start = max(1, min(int(new_sec_start), 13))
            sec_end = max(sec_start, min(int(new_sec_end) if new_sec_end is not None else sec_start, 13))

        custom_time = ""
        if new_custom_time is not None and str(new_custom_time).strip():
            custom_time = str(new_custom_time).strip()
            if "-" in custom_time:
                parts = custom_time.split("-", 1)
                snapped = self.snap_time_to_sections(parts[0].strip(), parts[1].strip())
                sec_start, sec_end = snapped
        elif new_sec_start is None:
            custom_time = getattr(target, "custom_time", "")

        room = str(new_room).strip() if new_room is not None else target.room
        teacher = str(new_teacher).strip() if new_teacher is not None else target.teacher
        week_start = max(1, int(new_week_start)) if new_week_start is not None else target.week_start
        week_end = max(week_start, int(new_week_end)) if new_week_end is not None else target.week_end

        updated = Course(
            name=name, weekday=weekday, sec_start=sec_start, sec_end=sec_end,
            week_start=week_start, week_end=week_end, parity=target.parity,
            room=room, teacher=teacher, campus=target.campus, note=target.note,
            custom_time=custom_time, id=target.id
        )
        self.update_course(target, updated)
        return target, updated

    def parse_delete_from_natural_language(self, text):
        """本地 NLP 解析自然语言删除与取消日程请求。"""
        trimmed = (text or "").strip()
        del_keywords = ("删除", "删掉", "删了", "退课", "取消", "移除", "去掉", "不开", "不上了")
        if not any(k in trimmed for k in del_keywords):
            return None

        raw = re.sub(r"^(?:阿米娅|请问|请|麻烦您|麻烦你|麻烦帮我|请帮我|麻烦|帮我|可以帮我|帮|给我)+[,，\s]*", "", trimmed)
        target_str = ""
        m1 = re.search(r"(?:把|将)\s*([^,，。!！?？]+?)\s*(?:从课表|从日程)?\s*(?:取消|删除|删掉|删了|退课|移除|去掉|不开)", raw)
        if m1:
            target_str = m1.group(1).strip()
        else:
            m2 = re.search(r"(?:取消|删除|删掉|删了|退课|移除|去掉)\s*(?:一门|一节|个|场|次)?\s*(?:从课表|从日程)?\s*([^,，。!！?？]+)", raw)
            if m2:
                cand = re.sub(r"^(?:掉|了|吧|一下)+", "", m2.group(1).strip()).strip()
                if len(cand) >= 2 and cand not in ("一下", "这个", "上面", "课表", "日程"):
                    target_str = cand
            if not target_str:
                m3 = re.search(r"([^,，。!！?？]+?)\s*(?:退课|不开了|不开|取消|删除|删了|删掉)", raw)
                if m3:
                    target_str = m3.group(1).strip()

        subject = target_str if target_str else raw
        weekday = parse_weekday_from_text(subject) or parse_weekday_from_text(raw)
        cur_week = self.week_no() or 1
        target_week = parse_week_from_text(subject, cur_week) or parse_week_from_text(raw, cur_week)
        sec_start, _, _ = parse_sections_or_time_from_text(subject, self.sections)
        room = parse_room_from_text(subject)

        matched_c = next((c for c in self.courses if c.name in subject or c.name in raw or (len(c.name) >= 2 and c.name[:2] in subject)), None)
        if matched_c:
            cand_name = matched_c.name
        else:
            cand_name = re.sub(r"^(?:周[一二三四五六日天七]|星期[一二三四五六日天七]|明天|后天|今天|下周[一二三四五六日天七]?|第[0-9一二两三四五六七八九十]+周|下午|上午|晚上|中午|[0-9]{1,2}点|[0-9]{1,2}节|第[0-9]{1,2}(?:-[0-9]{1,2})?节)+", "", subject)
            cand_name = re.sub(r"^(?:在|@|的|一门|一节|个|场|次|课)+", "", cand_name)
            if room:
                cand_name = cand_name.replace(room, "")
            cand_name = re.sub(r"(?:课|课程|教室|地点)$", "", cand_name).strip()

        delete_all = ("退课" in trimmed or "整门" in trimmed or target_week is None or
                      any(c.name == cand_name and c.week_start == c.week_end for c in self.courses))

        return self.delete_course_matching(
            name=cand_name,
            weekday=weekday,
            sec_start=sec_start,
            target_week=target_week,
            room=room,
            delete_all_weeks=delete_all
        )

    def parse_modify_from_natural_language(self, text):
        """本地 NLP 解析自然语言修改与调整日程请求。"""
        trimmed = (text or "").strip()
        mod_keywords = ("改到", "改成", "改在", "改至", "推迟到", "推迟至", "提前到", "提前至", "调整到", "调整为", "换到", "换成")
        kw_found = next((k for k in mod_keywords if k in trimmed), None)
        if not kw_found:
            return None, None

        raw = re.sub(r"^(?:阿米娅|请问|请|麻烦您|麻烦你|麻烦帮我|请帮我|麻烦|帮我|可以帮我|帮|给我)+[,，\s]*", "", trimmed)
        parts = raw.split(kw_found, 1)
        if len(parts) < 2:
            return None, None

        target_raw = re.sub(r"^(?:把|将)\s*", "", parts[0].strip()).strip()
        target_raw = re.sub(r"(?:的时间|地点|教室)$", "", target_raw).strip()
        new_raw = parts[1].strip()

        cur_week = self.week_no() or 1
        target_weekday = parse_weekday_from_text(target_raw)
        target_week = parse_week_from_text(target_raw, cur_week)
        target_sec, _, _ = parse_sections_or_time_from_text(target_raw, self.sections)

        matched_c = next((c for c in self.courses if c.name in target_raw or (len(c.name) >= 2 and c.name[:2] in target_raw)), None)
        if matched_c:
            target_name = matched_c.name
        else:
            target_name = re.sub(r"^(?:周[一二三四五六日天七]|星期[一二三四五六日天七]|明天|后天|今天|下周[一二三四五六日天七]?|第[0-9一二两三四五六七八九十]+周|下午|上午|晚上|中午|[0-9]{1,2}点|[0-9]{1,2}节|第[0-9]{1,2}(?:-[0-9]{1,2})?节)+", "", target_raw)
            target_name = re.sub(r"^(?:在|@|的|一门|一节|个|场|次|课)+", "", target_name)
            target_name = re.sub(r"(?:课|课程|教室|地点)$", "", target_name).strip()

        new_weekday = parse_weekday_from_text(new_raw)
        new_sec_start, new_sec_end, new_custom_time = parse_sections_or_time_from_text(new_raw, self.sections)
        new_room = parse_room_from_text(new_raw)
        new_week = parse_week_from_text(new_raw, cur_week)

        new_name = None
        if kw_found in ("改成", "换成") and not new_room and new_sec_start is None and new_weekday is None:
            new_name = re.sub(r"^(?:一门|一节|个|场|次)?", "", new_raw)
            new_name = re.sub(r"(?:课|课程)$", "", new_name).strip()

        return self.modify_course_matching(
            target_name=target_name,
            target_weekday=target_weekday,
            target_sec_start=target_sec,
            target_week=target_week,
            new_name=new_name,
            new_weekday=new_weekday,
            new_sec_start=new_sec_start,
            new_sec_end=new_sec_end,
            new_room=new_room if new_room else None,
            new_custom_time=new_custom_time if new_custom_time else None,
            new_week_start=new_week,
            new_week_end=new_week
        )

    def parse_course_from_natural_language(self, text):
        """本地规则解析自然语言添加课程与活动。"""
        trimmed = (text or "").strip()
        if not trimmed:
            return None
        negative_words = ("删除", "删掉", "删了", "退课", "取消", "移除", "不要这", "不要", "修改", "改一下", "改成", "改到", "不是这", "查一下", "看下课表", "今天有什么课", "有什么课", "不对")
        if any(w in trimmed for w in negative_words):
            return None

        room = parse_room_from_text(trimmed)
        name = ""
        m_book = re.search(r"[《“「]([^》”」]+)[》”」]", trimmed)
        if m_book:
            name = m_book.group(1).strip()
        if not name:
            m_label = re.search(r"(?:课程|日程|活动|主题)(?:名|名称)?\s*[:：]\s*([a-zA-Z0-9\u4e00-\u9fa5]{2,15}?)(?=[,，。、\s在从第周]|$)", trimmed)
            if m_label:
                cand = m_label.group(1).strip()
                time_words = ("上午", "下午", "晚上", "中午", "今天", "明天", "后天", "这周", "下周", "周一", "周二", "周三", "周四", "周五", "周六", "周日")
                if cand not in ("课程", "日程", "活动", "这个", "上面", "时间", "安排") and not any(t in cand for t in time_words):
                    name = cand

        raw = trimmed
        while True:
            cleaned = re.sub(r"^(?:阿米娅|请问|请|麻烦您|麻烦你|麻烦帮我|请帮我|麻烦|帮我|可以帮我|帮|给我)+[,，\s]*", "", raw)
            cleaned = re.sub(r"^(?:添加|录入|加上?|补上?|有一门|有一节|加一门|加一节|加个|新加|新建|安排|记一下|记录)+[,，\s]*", "", cleaned)
            cleaned = re.sub(r"^(?:一门|一节|个|场|次)?(?:课程|日程|活动|事项)?[:：\s]*", "", cleaned)
            if cleaned == raw:
                break
            raw = cleaned

        if not name and room:
            m_c = re.search(r"(?:[，,、\s:：]|^)(?:开|上|听|做|学|有|加|录入)?\s*(?:一门|一节|门)?\s*([a-zA-Z0-9\u4e00-\u9fa5]{2,15}?)(?:课|课程)?\s*(?:在|@)\s*" + re.escape(room), raw)
            if m_c:
                cand = m_c.group(1).strip()
                time_words = ("上午", "下午", "晚上", "中午", "今天", "明天", "后天", "这周", "下周", "周一", "周二", "周三", "周四", "周五", "周六", "周日")
                if not any(t in cand for t in time_words) and not re.search(r"[0-9]+[点节分]", cand):
                    name = cand

        if not name:
            m_verb = re.search(r"(?<![早中晚])(?:有|上|加|补|去上)(?![午海])\s*(?:一门|一节|个|场)?\s*([a-zA-Z0-9\u4e00-\u9fa5]{2,12}?)(?:课|课程)?(?=[,，。、\s在@从第周点]|$)", raw)
            if m_verb:
                cand = m_verb.group(1).strip()
                time_words = ("上午", "下午", "晚上", "中午", "今天", "明天", "后天", "这周", "下周", "周一", "周二", "周三", "周四", "周五", "周六", "周日")
                if cand not in ("课程", "日程", "活动", "这个", "上面", "时间", "安排") and not any(t in cand for t in time_words):
                    name = cand

        if not name:
            m_sec = re.search(r"(?:[0-9]{1,2}\s*[~至到与和/\-]?\s*[0-9]{1,2}?\s*节)\s*(?:加|上|有)?\s*(?:一门|一节)?\s*([a-zA-Z0-9\u4e00-\u9fa5]{2,12}?)(?:课|课程)?(?=[,，。、\s在@从第周点]|$)", raw)
            if m_sec:
                cand = m_sec.group(1).strip()
                if cand not in ("课程", "日程", "活动", "这个", "上面", "时间", "安排"):
                    name = cand

        if not name:
            m_start = re.search(r"^([a-zA-Z0-9\u4e00-\u9fa5]{2,12}?)(?:课|课程)?(?=[,，。、\s在@从第周点]|$)", raw)
            if m_start:
                cand = m_start.group(1).strip()
                time_words = ("上午", "下午", "晚上", "中午", "今天", "明天", "后天", "这周", "下周", "周一", "周二", "周三", "周四", "周五", "周六", "周日")
                if cand not in ("课程", "日程", "活动", "这个", "上面", "时间", "安排") and not any(t in cand for t in time_words):
                    name = cand

        if name:
            name = re.sub(r"^(?:在|@|个|次|场|开|去|参加|有|门|一门|一节|一个|这门|这节|加|加上|考|点)+", "", name).strip()
            name = re.sub(r"(?:持续[0-9一两二三四五六七八九十]+周.*|[，,。、].*)$", "", name).strip()
            name = re.sub(r"^(?:周[一二三四五六日天七]|星期[一二三四五六日天七]|上午|下午|晚上|中午|[0-9]{1,2}点)+", "", name).strip()
            name = re.sub(r"(?:[0-9]{1,2}[:点][0-9]{2}|[0-9]{1,2}点)+.*$", "", name).strip()
            if name.endswith("课") and len(name) >= 3 and not name.endswith("网球课"):
                name = name[:-1]

        invalid_names = {"课表", "课", "这节课", "我的课", "一节", "一门", "活动", "这个活动", "日程", "安排", "这个", "上面", "新日程", ""}
        if not name or name in invalid_names or name.isdigit():
            return None

        weekday = parse_weekday_from_text(trimmed) or date.today().isoweekday()
        sec_start, sec_end, custom_time = parse_sections_or_time_from_text(trimmed, self.sections)
        sec_start = sec_start or 1
        sec_end = sec_end or max(sec_start, min(sec_start + 1, 13))

        teacher = ""
        m_t = re.search(r"([\u4e00-\u9fa5]{2,4})(?:老师|教授|学长|学姐|主持)", trimmed)
        if m_t:
            teacher = m_t.group(1)

        max_week = max((c.week_end for c in self.courses), default=16)
        cur_week = self.week_no() or 1
        week_start, week_end = resolve_week_range(trimmed, name, custom_time, 1, max_week, cur_week, max_week)

        course = Course(
            name=name, weekday=weekday, sec_start=sec_start, sec_end=sec_end,
            week_start=week_start, week_end=week_end, parity="all",
            room=room, teacher=teacher, custom_time=custom_time,
            note="AI活动录入" if custom_time else "AI智能录入"
        )
        self.add_course(course)
        return course

    def parse_adjustments_from_notice(self, text, base_year=None):
        """解析通知文本中的教学调整并存入课表。"""
        adjs = parse_adjustments_from_notice(text, base_year=base_year)
        if adjs:
            self.add_adjustments(adjs)
        return adjs

    def build_schedule_analysis_context(self):
        """生成供大模型对话注入的真实排课全景学情数据库。"""
        if not self.courses:
            return ""
        now = datetime.now()
        cur_date = now.date()
        week_no = self.week_no(cur_date) or 1
        today_wd = cur_date.isoweekday()
        wd_names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        lines = []
        lines.append("【博士当前真实课表学情全景数据库】：")
        lines.append(f"- 当前学期进度：第 {week_no} 周（今日是 {wd_names[today_wd]}）")

        distinct_names = sorted(list({c.name for c in self.courses}))
        lines.append(f"- 修读科目清单（共 {len(distinct_names)} 门）：{'、'.join(distinct_names)}")

        lines.append(f"- 本周（第 {week_no} 周）各日排课与课时负荷：")
        total_sessions = 0
        busy_days = []
        free_days = []
        for wd in range(1, 8):
            day_courses = self.courses_on(wd, week_no)
            day_sessions = sum(c.sec_end - c.sec_start + 1 for c in day_courses)
            total_sessions += day_sessions
            w_name = wd_names[wd]
            if not day_courses:
                free_days.append(w_name)
                lines.append(f"  * {w_name}：无课（全天空闲，建议规划自主复习、大作业攻坚或整理作息）")
            else:
                if day_sessions >= 6:
                    busy_days.append(f"{w_name}({day_sessions}节)")
                details = []
                for c in day_courses:
                    room_str = f" @{c.room}" if c.room and c.room != "待定" else ""
                    teacher_str = f"({c.teacher})" if c.teacher else ""
                    time_desc = f"📌[{c.custom_time}] " if getattr(c, "custom_time", "") else ""
                    details.append(f"{time_desc}{c.sec_start}-{c.sec_end}节《{c.name}》{teacher_str}{room_str}")
                lines.append(f"  * {w_name}：共 {day_sessions} 节课 [ {'；'.join(details)} ]")

        lines.append(f"- 本周总课时：共 {total_sessions} 节课。")
        if busy_days:
            lines.append(f"- 高负荷繁忙日：{'、'.join(busy_days)}（课时密集，需注意提前预习与课间精力恢复）")
        if free_days:
            lines.append(f"- 较空闲日：{'、'.join(free_days)}（拥有整块自主掌控时间，适合用于深入钻研核心科目或休整放松）")

        today_courses = self.courses_for_day(cur_date)
        if today_courses:
            c_lines = []
            for c in today_courses:
                time_str = f" ({self.sections.get(str(c.sec_start), '')})" if self.sections.get(str(c.sec_start)) else ""
                room_str = f" @{c.room}" if c.room else ""
                c_lines.append(f"{c.sec_start}-{c.sec_end}节{time_str}《{c.name}》{room_str}")
            lines.append(f"- 今日（{wd_names[today_wd]}）课程安排：{'；'.join(c_lines)}")
        else:
            today_str = cur_date.isoformat()
            adj = next((a for a in self.adjustments if a.get("date") == today_str), None)
            if adj and adj.get("type") == "suspend":
                lines.append(f"- 今日（{wd_names[today_wd]}）课程安排：今日因【{adj.get('reason', '法定节假日')}】停课放假，无排课。")
            else:
                lines.append(f"- 今日（{wd_names[today_wd]}）课程安排：今天没有排课，可自由安排学习或休息。")

        if self.adjustments:
            lines.append("\n【教学安排与调课/停课备忘（已生效）】：")
            for a in sorted(self.adjustments, key=lambda x: x.get("date", "")):
                desc = "停课放假" if a.get("type") == "suspend" else f"调课（按第{a.get('target_week', '')}周周{a.get('target_weekday', '')}课表）"
                reason_str = f"【{a.get('reason')}】" if a.get("reason") else ""
                lines.append(f"- {a.get('date')}{reason_str}：{desc}")

        return "\n".join(lines)


# ── 辅助函数（算法与规则解析）──────────────────────────────────────

def snap_time_to_sections_standalone(start_time_str, end_time_str, sections=None):
    """将时间范围吸附到 13 节体系中的最近节次区间。"""
    sections = sections or DEFAULT_SECTIONS

    def parse_to_mins(t):
        parts = re.split(r"[:：]", str(t).strip())
        if len(parts) >= 2:
            try:
                return int(parts[0]) * 60 + int(parts[1])
            except ValueError:
                return 0
        return 0

    start_mins = parse_to_mins(start_time_str)
    end_mins = parse_to_mins(end_time_str)
    if end_mins <= start_mins:
        end_mins = start_mins + 45

    sec_times = []
    for sec in range(1, 14):
        time_str = sections.get(str(sec)) or DEFAULT_SECTIONS.get(str(sec), "08:00")
        sm = parse_to_mins(time_str)
        em = sm + 45
        sec_times.append((sec, sm, em))

    best_start = 1
    min_diff = float("inf")
    for sec, sm, em in sec_times:
        if sm <= start_mins <= em:
            best_start = sec
            break
        diff = min(abs(start_mins - sm), abs(start_mins - em))
        if diff < min_diff:
            min_diff = diff
            best_start = sec

    best_end = best_start
    min_end_diff = float("inf")
    for sec, sm, em in sec_times:
        if sec < best_start:
            continue
        if sm <= end_mins <= em:
            best_end = sec
            break
        diff = min(abs(end_mins - sm), abs(end_mins - em))
        if diff < min_end_diff:
            min_end_diff = diff
            best_end = sec

    return (best_start, best_end)


def is_activity(name, custom_time="", user_text=""):
    """判断是否为日程活动（非固定全学期常规课程）。"""
    if custom_time:
        return True
    act_keywords = (
        "组会", "会议", "例会", "研讨会", "讲座", "报告", "实验", "答疑", "班会",
        "活动", "自习", "培训", "体测", "体检", "竞赛", "比赛", "面试", "聚餐",
        "值日", "值班", "彩排", "宣讲会", "日程", "聚会"
    )
    return any(k in (name or "") or k in (user_text or "") for k in act_keywords)


def parse_chinese_or_arabic_number(str_val):
    """解析中文或阿拉伯数字（支持 1~99，如 '三'、'十二'、'25'）。"""
    trimmed = str(str_val or "").strip()
    if trimmed.isdigit():
        return int(trimmed)
    if trimmed == "两":
        return 2
    cn_units = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "零": 0}
    if trimmed.startswith("十"):
        rem = trimmed[1:]
        return 10 + cn_units.get(rem, 0)
    if "十" in trimmed:
        parts = trimmed.split("十", 1)
        tens = cn_units.get(parts[0], 1)
        ones = cn_units.get(parts[1], 0) if parts[1] else 0
        return tens * 10 + ones
    return cn_units.get(trimmed, 1)


def resolve_week_range(user_text, name, custom_time="", suggested_start=1, suggested_end=16, current_week=1, max_week=16):
    """智能计算与校验课程/活动的起止周次。"""
    trimmed = (user_text or "").strip()
    is_act = is_activity(name, custom_time, trimmed)

    # 1. 检查明确范围
    m_range = re.search(r"(?:从|自|第)?\s*([0-9一二两三四五六七八九十]+)\s*周?\s*[~至到与和\-]\s*(?:从|自|第)?\s*([0-9一二两三四五六七八九十]+)\s*周", trimmed)
    if m_range:
        s = parse_chinese_or_arabic_number(m_range.group(1))
        e = parse_chinese_or_arabic_number(m_range.group(2))
        start = max(1, s)
        end = max(start, e)
        return (start, end)

    # 2. 检查持续周数
    m_dur = re.search(r"(?:持续|连开|一共|共|连续|连着)\s*([0-9一二两三四五六七八九十]+)\s*周", trimmed)
    if m_dur:
        dur = max(1, parse_chinese_or_arabic_number(m_dur.group(1)))
        if "下下周" in trimmed or "下下星期" in trimmed:
            start_week = current_week + 2
        elif "下周" in trimmed or "下星期" in trimmed or "下礼拜" in trimmed:
            start_week = current_week + 1
        else:
            m_single = re.search(r"第\s*([0-9一二两三四五六七八九十]+)\s*周", trimmed)
            start_week = parse_chinese_or_arabic_number(m_single.group(1)) if m_single else current_week
        start_week = max(1, start_week)
        return (start_week, start_week + dur - 1)

    # 3. 检查每周/全学期
    is_weekly = any(k in trimmed for k in ("每周", "每星期", "每个礼拜", "整学期", "整个学期", "全学期"))
    if is_weekly:
        start_week = max(1, current_week) if is_act else 1
        return (start_week, max(start_week, max_week))

    # 4. 单次活动默认单周
    if is_act:
        if "下下周" in trimmed or "下下星期" in trimmed:
            target_week = current_week + 2
        elif "下周" in trimmed or "下星期" in trimmed or "下礼拜" in trimmed:
            target_week = current_week + 1
        else:
            m_single = re.search(r"第\s*([0-9一二两三四五六七八九十]+)\s*周", trimmed)
            if m_single:
                target_week = parse_chinese_or_arabic_number(m_single.group(1))
            else:
                target_week = suggested_start if suggested_start > 0 else current_week
        target_week = max(1, target_week)
        return (target_week, target_week)

    s = suggested_start if (1 <= suggested_start <= max_week) else 1
    e = suggested_end if (s <= suggested_end <= max_week) else max_week
    return (s, e)


def parse_sections_or_time_from_text(text, sections=None):
    """解析自然语言中的节次/时段信息。返回 (sec_start, sec_end, custom_time)。"""
    trimmed = str(text or "").strip()
    m_dig = re.search(r"([0-9]{1,2})[:点：]([0-9]{2})\s*[~至到与和/\-]\s*([0-9]{1,2})[:点：]([0-9]{2})", trimmed)
    if m_dig:
        sh = int(m_dig.group(1))
        sm = int(m_dig.group(2))
        eh = int(m_dig.group(3))
        em = int(m_dig.group(4))
        st_str = f"{sh:02d}:{sm:02d}"
        et_str = f"{eh:02d}:{em:02d}"
        s_start, s_end = snap_time_to_sections_standalone(st_str, et_str, sections)
        return (s_start, s_end, f"{st_str}-{et_str}")

    m_range = re.search(r"(?:第)?([0-9]{1,2})\s*[~至到与和\-]\s*([0-9]{1,2})\s*节", trimmed)
    if m_range:
        s = int(m_range.group(1))
        e = int(m_range.group(2))
        return (s, e, "")

    m_single = re.search(r"(?:第)?([0-9]{1,2})\s*节", trimmed)
    if m_single:
        s = int(m_single.group(1))
        return (s, s, "")

    if "下午两点" in trimmed or "14:00" in trimmed or "14点" in trimmed:
        return (6, 7, "14:00-15:30")
    if "下午三点" in trimmed or "15:00" in trimmed or "15点" in trimmed:
        return (7, 8, "15:00-16:30")
    if "下午四点" in trimmed or "16:00" in trimmed or "16点" in trimmed:
        return (8, 9, "16:00-17:30")
    if "晚上七点" in trimmed or "19:00" in trimmed or "19点" in trimmed:
        return (11, 12, "19:00-20:30")
    if "上午八点" in trimmed or "8:00" in trimmed or "8点" in trimmed:
        return (1, 2, "08:00-09:35")
    if "上午十点" in trimmed or "10:00" in trimmed or "10点" in trimmed:
        return (3, 4, "10:00-11:35")
    if "下午" in trimmed:
        return (6, 7, "")
    if "上午" in trimmed:
        return (1, 2, "")
    if "晚上" in trimmed:
        return (11, 12, "")
    return (None, None, "")


def parse_room_from_text(text):
    """解析自然语言中的地点/教室。"""
    trimmed = str(text or "").strip()
    room = ""
    m1 = re.search(r"(?:在|@|教室(?:在|是)?|地点(?:在|是)?)\s*([a-zA-Z0-9\u4e00-\u9fa5\-]{2,12}?)(?=[的开上听做学有搞举行举办参加跑打，,。、\s]|$)", trimmed)
    if m1:
        room = m1.group(1).strip()
    else:
        m2 = re.search(r"(?:在|@|教室(?:在|是)?|地点(?:在|是)?)\s*([a-zA-Z0-9\u4e00-\u9fa5\-]{1,12}?(?:楼[0-9A-Za-z\-]*|室|教室|馆|栋|区[0-9A-Za-z\-]*|操场|球场|[0-9]{3,4}|[教综信文生化美图东西南][一二三四五六七八九十0-9]+))", trimmed)
        if m2:
            room = m2.group(1).strip()
        else:
            m3 = re.search(r"\b([教综信文生化美图东西南][一二三四五六七八九十0-9]+(?:-[0-9A-Za-z]+)?)\b", trimmed)
            if m3:
                room = m3.group(1).strip()
    if room:
        for sfx in ("开", "去", "上", "参加", "有", "搞", "进行", "听"):
            if room.endswith(sfx):
                room = room[:-len(sfx)].strip()
        if room in ("学校", "这里", "那里", "上面", "这个", "课表", "日程"):
            room = ""
    return room


def parse_weekday_from_text(text, current_weekday=None):
    """解析自然语言中的星期指示词。返回 1~7（1=周一，7=周日）或 None。"""
    trimmed = str(text or "").strip()
    if current_weekday is None:
        current_weekday = date.today().isoweekday()
    if "大后天" in trimmed:
        return (current_weekday + 2) % 7 + 1
    if "后天" in trimmed:
        return (current_weekday + 1) % 7 + 1
    if "明天" in trimmed:
        return current_weekday % 7 + 1
    if "今天" in trimmed:
        return current_weekday
    if any(k in trimmed for k in ("周一", "星期一", "礼拜一")):
        return 1
    if any(k in trimmed for k in ("周二", "星期二", "礼拜二")):
        return 2
    if any(k in trimmed for k in ("周三", "星期三", "礼拜三")):
        return 3
    if any(k in trimmed for k in ("周四", "星期四", "礼拜四")):
        return 4
    if any(k in trimmed for k in ("周五", "星期五", "礼拜五")):
        return 5
    if any(k in trimmed for k in ("周六", "星期六", "礼拜六")):
        return 6
    if any(k in trimmed for k in ("周日", "周天", "星期日", "星期天", "礼拜日", "礼拜天")):
        return 7
    return None


def parse_week_from_text(text, current_week=1):
    """解析自然语言中的周次指示词。"""
    trimmed = str(text or "").strip()
    if "下下周" in trimmed or "下下星期" in trimmed:
        return current_week + 2
    if "下周" in trimmed or "下星期" in trimmed or "下礼拜" in trimmed:
        return current_week + 1
    if any(k in trimmed for k in ("这周", "本周", "这星期", "本星期")):
        return current_week
    m = re.search(r"第\s*([0-9一二两三四五六七八九十]+)\s*周", trimmed)
    if m:
        return parse_chinese_or_arabic_number(m.group(1))
    return None


def parse_adjustments_from_notice(text, base_year=None):
    """从教务处通知文本中提取调课/停课教学安排调整。"""
    year = base_year or date.today().year
    m_y = re.search(r"(20\d{2})年", text or "")
    if m_y:
        year = int(m_y.group(1))

    cn_num_map = {
        "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7,
        "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7
    }
    result = []

    # 1. 调课: "9月20日（周日），教学安排按第5周周二课表执行"
    p1 = re.compile(r"(\d{1,2})月(\d{1,2})日(?:[（(][^）)]*[）)])?[，, ]*(?:教学安排)?(?:均|都|各单位)?按(?:第(\d+)周)?(?:的)?周([一二三四五六日天1-7])(?:课表)?执行")
    for m in p1.finditer(text):
        month = int(m.group(1))
        day = int(m.group(2))
        tw = int(m.group(3)) if m.group(3) else None
        wd_str = m.group(4)
        twd = cn_num_map.get(wd_str, 1)
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        reason = f"按第{tw}周周{wd_str}" if tw else f"按周{wd_str}"
        result.append({
            "id": uuid.uuid4().hex,
            "date": date_str,
            "type": "substitute",
            "target_week": tw,
            "target_weekday": twd,
            "reason": reason
        })

    # 2. 连续多天停课: "10月1日-7日，所有课程停上"
    p2 = re.compile(r"(\d{1,2})月(\d{1,2})日\s*[-~至到]\s*(?:(\d{1,2})月)?(\d{1,2})日(?:[（(][^）)]*[）)])?(?:(?!\d{1,2}月)[^。；;\n])*?停[上课]")
    for m in p2.finditer(text):
        m_start = int(m.group(1))
        d_start = int(m.group(2))
        m_end = int(m.group(3)) if m.group(3) else m_start
        d_end = int(m.group(4))
        match_full = m.group(0)
        prefix = text[:m.start()][-30:] if m.start() > 0 else ""
        if "中秋" in match_full or "中秋" in prefix:
            holiday = "中秋节停课"
        elif "国庆" in match_full or "国庆" in prefix:
            holiday = "国庆节停课"
        elif "元旦" in match_full or "元旦" in prefix:
            holiday = "元旦停课"
        elif "五一" in match_full or "五一" in prefix:
            holiday = "五一停课"
        elif "端午" in match_full or "端午" in prefix:
            holiday = "端午节停课"
        elif "清明" in match_full or "清明" in prefix:
            holiday = "清明节停课"
        else:
            holiday = "停课"

        cur = date(year, m_start, d_start)
        end_d = date(year, m_end, d_end)
        while cur <= end_d:
            d_str = cur.isoformat()
            if not any(r["date"] == d_str for r in result):
                result.append({
                    "id": uuid.uuid4().hex,
                    "date": d_str,
                    "type": "suspend",
                    "reason": holiday
                })
            cur += timedelta(days=1)

    # 3. 单日停课: "9月25日，所有课程停上"
    p3 = re.compile(r"(\d{1,2})月(\d{1,2})日(?:[（(][^）)]*[）)])?(?!\s*[-~至到])(?:(?!\d{1,2}月)[^。；;\n])*?停[上课]")
    for m in p3.finditer(text):
        month = int(m.group(1))
        day = int(m.group(2))
        d_str = f"{year:04d}-{month:02d}-{day:02d}"
        if any(r["date"] == d_str for r in result):
            continue
        match_full = m.group(0)
        prefix = text[:m.start()][-30:] if m.start() > 0 else ""
        if "中秋" in match_full or "中秋" in prefix:
            holiday = "中秋节停课"
        elif "国庆" in match_full or "国庆" in prefix:
            holiday = "国庆节停课"
        elif "元旦" in match_full or "元旦" in prefix:
            holiday = "元旦停课"
        elif "五一" in match_full or "五一" in prefix:
            holiday = "五一停课"
        else:
            holiday = "停课"
        result.append({
            "id": uuid.uuid4().hex,
            "date": d_str,
            "type": "suspend",
            "reason": holiday
        })

    return result

