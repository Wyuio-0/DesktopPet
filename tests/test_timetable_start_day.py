"""Unit tests for timetable week start day (Sunday vs Monday) and dynamic dates."""

from datetime import date, timedelta
import json
import pytest
from PyQt5 import QtWidgets

from pet.schedule import Schedule, Course
from pet.timetable import (
    TimetableView,
    COL_WEEKDAYS_SUNDAY,
    COL_WEEKDAYS_MONDAY,
)


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication([])
    return app


class TestScheduleWeekStartDay:
    def test_default_is_sunday(self, tmp_path):
        p = tmp_path / "schedule.json"
        s = Schedule(str(p))
        assert s.week_start_day == "sunday"

    def test_set_week_start_day_persists(self, tmp_path):
        p = tmp_path / "schedule.json"
        s = Schedule(str(p))
        s.set_week_start_day("monday")
        assert s.week_start_day == "monday"

        # Reload from file
        s2 = Schedule(str(p))
        assert s2.week_start_day == "monday"

        # Toggle back to sunday
        s2.set_week_start_day("sunday")
        assert s2.week_start_day == "sunday"
        s3 = Schedule(str(p))
        assert s3.week_start_day == "sunday"

    def test_invalid_start_day_defaults_to_sunday(self, tmp_path):
        p = tmp_path / "schedule.json"
        s = Schedule(str(p))
        s.set_week_start_day("friday")
        assert s.week_start_day == "sunday"


class TestTimetableDynamicColumns:
    def test_columns_order(self, qapp, tmp_path):
        tv = TimetableView()
        tv._week_start_day = "sunday"
        assert tv.col_weekdays == [7, 1, 2, 3, 4, 5, 6]

        tv._week_start_day = "monday"
        assert tv.col_weekdays == [1, 2, 3, 4, 5, 6, 7]

    def test_calculate_dates_sunday_vs_monday(self, qapp, tmp_path):
        p = tmp_path / "schedule.json"
        today = date.today()
        # Assume term start is 2 weeks ago monday
        term_start = today - timedelta(days=today.isoweekday() - 1 + 14)
        s = Schedule(str(p))
        s.save(term="2026-1", term_start=term_start)

        tv = TimetableView()

        # 1. Test Sunday start
        s.set_week_start_day("sunday")
        tv.set_data(s, s.week_no())

        assert tv._week_start_day == "sunday"
        assert tv.col_weekdays == COL_WEEKDAYS_SUNDAY
        assert len(tv._dates) == 7
        assert tv._today_col_idx >= 0
        # The column corresponding to today in tv.col_weekdays must match today's isoweekday
        today_iso = today.isoweekday()
        assert tv.col_weekdays[tv._today_col_idx] == today_iso
        # Date string must match today's month.day
        assert tv._dates[tv._today_col_idx] == f"{today.month}.{today.day}"

        # 2. Test Monday start
        s.set_week_start_day("monday")
        tv.set_data(s, s.week_no())

        assert tv._week_start_day == "monday"
        assert tv.col_weekdays == COL_WEEKDAYS_MONDAY
        assert len(tv._dates) == 7
        assert tv._today_col_idx >= 0
        assert tv.col_weekdays[tv._today_col_idx] == today_iso
        assert tv._dates[tv._today_col_idx] == f"{today.month}.{today.day}"
