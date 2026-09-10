"""Unit tests for schedule AI analysis (query_schedule scope=analyze/all)."""
from datetime import date
import pytest

from pet import actions
from pet.schedule import Course, Schedule


@pytest.fixture
def mock_schedule():
    sched = Schedule()
    sched.term_start = date(2026, 9, 7)
    sched.courses = [
        Course(name="高等数学", weekday=1, sec_start=1, sec_end=2,
               week_start=1, week_end=16, parity="all", room="教1-101", teacher="张教授"),
        Course(name="大学物理", weekday=1, sec_start=3, sec_end=4,
               week_start=1, week_end=16, parity="all", room="教2-202", teacher="李教授"),
        Course(name="物理实验", weekday=1, sec_start=6, sec_end=8,
               week_start=1, week_end=16, parity="all", room="物理楼", teacher="王老师"),
        Course(name="大学英语", weekday=2, sec_start=1, sec_end=2,
               week_start=1, week_end=16, parity="all", room="外语楼", teacher="Smith"),
    ]
    sched.notes = ["形式与政策 / 线上网课"]
    return sched


def test_query_schedule_no_schedule():
    actions.set_schedule_provider(lambda: None)
    res = actions.query_schedule("analyze")
    assert "还没有导入课表" in res


def test_query_schedule_analyze(mock_schedule):
    actions.set_schedule_provider(lambda: mock_schedule)
    res = actions.query_schedule("analyze")

    assert "【博士课表全量与学情数据】" in res
    assert "高等数学" in res
    assert "大学物理" in res
    assert "大学英语" in res
    assert "高负荷密集日" in res or "周一" in res
    assert "本周总课时" in res
    assert "空闲整块自习日" in res
    assert "形式与政策" in res


def test_query_schedule_all_scope_alias(mock_schedule):
    actions.set_schedule_provider(lambda: mock_schedule)
    res_all = actions.query_schedule("all")
    assert "【博士课表全量与学情数据】" in res_all
