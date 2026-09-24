import os
import json
import pytest
from datetime import date
from pet import actions
from pet.schedule import Schedule, Course
from pet.ai import AmiyaBrain, _clean_stream_display_text, _execute_embedded_schedule_commands


@pytest.fixture
def temp_schedule(tmp_path):
    path = str(tmp_path / "test_schedule.json")
    sched = Schedule(path=path)
    sched.term = "2026-2027-1"
    sched.term_start = date(2026, 9, 7)
    # Add initial course
    sched.courses = [
        Course(
            name="高等数学", weekday=1, sec_start=1, sec_end=2,
            week_start=1, week_end=16, parity="all",
            room="教一101", teacher="张教授"
        ),
        Course(
            name="实验室组会", weekday=4, sec_start=6, sec_end=7,
            week_start=3, week_end=3, parity="all",
            room="综合楼402", teacher="李老师", custom_time="14:15-15:30"
        ),
    ]
    sched.save()
    actions.set_schedule_provider(lambda: sched)
    return sched


def test_actions_add_course(temp_schedule):
    res = actions.add_course(
        name="大学英语", weekday=2, sec_start=3, sec_end=4,
        room="教二202", teacher="王老师"
    )
    assert "大学英语" in res
    assert any(c.name == "大学英语" and c.weekday == 2 and c.sec_start == 3 for c in temp_schedule.courses)


def test_actions_add_course_with_custom_time(temp_schedule):
    res = actions.add_course(
        name="读书会", weekday=5, custom_time="16:40-18:00",
        room="图书馆B101"
    )
    assert "读书会" in res
    c = next((c for c in temp_schedule.courses if c.name == "读书会"), None)
    assert c is not None
    assert c.weekday == 5
    assert c.custom_time == "16:40-18:00"
    assert c.sec_start == 9  # 16:40 maps to period 9


def test_actions_modify_course(temp_schedule):
    res = actions.modify_course(
        target_name="组会",
        new_weekday=5,
        new_sec_start=8,
        new_sec_end=9,
        new_room="科研楼301"
    )
    assert "已成功" in res
    c = next((c for c in temp_schedule.courses if "组会" in c.name), None)
    assert c is not None
    assert c.weekday == 5
    assert c.sec_start == 8
    assert c.sec_end == 9
    assert c.room == "科研楼301"


def test_actions_delete_course(temp_schedule):
    res = actions.delete_course(name="高等数学")
    assert "已成功" in res
    assert not any(c.name == "高等数学" for c in temp_schedule.courses)


def test_actions_adjust_schedule_notice(temp_schedule):
    notice = "9月20日（周日），教学安排按第5周周二课表执行。10月1日-7日，所有课程停上。"
    res = actions.adjust_schedule(notice_text=notice)
    assert "已成功解析" in res
    assert len(temp_schedule.adjustments) >= 2
    # Verify clear
    clear_res = actions.adjust_schedule(clear_all=True)
    assert "已为博士清空" in clear_res
    assert len(temp_schedule.adjustments) == 0


def test_execute_embedded_schedule_commands_add(temp_schedule):
    model_output = """好的博士，我已经为您在课表中记录了毛概课：
```json:add_course
{
  "name": "毛概",
  "weekday": 3,
  "sec_start": 3,
  "sec_end": 4,
  "week_start": 1,
  "week_end": 16,
  "room": "教三201"
}
```
请博士准时上课哦。"""
    cleaned = _execute_embedded_schedule_commands(model_output, "周三3-4节加一门毛概在教三201")
    assert "```json" not in cleaned
    assert "毛概课" in cleaned
    assert any(c.name == "毛概" and c.weekday == 3 for c in temp_schedule.courses)


def test_execute_embedded_schedule_commands_modify(temp_schedule):
    model_output = """好的博士，已经帮您把组会调整到周五下午了：
```json:modify_course
{
  "target_name": "组会",
  "target_weekday": 4,
  "new_weekday": 5,
  "new_sec_start": 8,
  "new_sec_end": 9,
  "new_room": "新楼501"
}
```
"""
    cleaned = _execute_embedded_schedule_commands(model_output, "把组会改到周五8-9节新楼501")
    assert "```json" not in cleaned
    c = next((c for c in temp_schedule.courses if "组会" in c.name), None)
    assert c is not None
    assert c.weekday == 5
    assert c.sec_start == 8
    assert c.room == "新楼501"


def test_execute_embedded_schedule_commands_delete(temp_schedule):
    model_output = """博士，已经为您取消了周四的组会安排：
```json:delete_course
{
  "name": "组会",
  "weekday": 4,
  "sec_start": 6
}
```
"""
    cleaned = _execute_embedded_schedule_commands(model_output, "把周四下午的组会取消")
    assert "```json" not in cleaned
    assert not any("组会" in c.name for c in temp_schedule.courses)


def test_clean_stream_display_text():
    partial = "好的博士，已经为您记录了行程```json:add_course\n{\n  \"name\": \"测试\""
    cleaned = _clean_stream_display_text(partial)
    assert cleaned == "好的博士，已经为您记录了行程"
    assert "```json" not in cleaned


def test_local_intent_offline_schedule(tmp_path, temp_schedule):
    char_dir = str(tmp_path / "char")
    os.makedirs(char_dir, exist_ok=True)
    brain = AmiyaBrain(char_dir)

    # 1. 离线删除
    reply_del = brain._try_local_intent("帮我把高等数学退课了")
    assert reply_del is not None
    assert "高等数学" in reply_del
    assert not any(c.name == "高等数学" for c in temp_schedule.courses)

    # 2. 离线修改
    reply_mod = brain._try_local_intent("把组会改到周五第8-9节")
    assert reply_mod is not None
    assert "调整为" in reply_mod
    c = next((c for c in temp_schedule.courses if "组会" in c.name), None)
    assert c is not None
    assert c.weekday == 5

    # 3. 离线添加
    reply_add = brain._try_local_intent("周二第1-2节加一门计算机网络在科技楼102")
    assert reply_add is not None
    assert "计算机网络" in reply_add
    assert any(c.name == "计算机网络" and c.weekday == 2 for c in temp_schedule.courses)

    # 4. 离线调课通知
    reply_adj = brain._try_local_intent("学校教学安排：9月20日按第5周周二课表执行，9月25日停课")
    assert reply_adj is not None
    assert "教学安排调整" in reply_adj
    assert len(temp_schedule.adjustments) >= 2


def test_schedule_listener_notified(temp_schedule):
    notified = []
    temp_schedule.register_listener(lambda: notified.append(True))
    actions.add_course(name="听力课", weekday=3, sec_start=1, sec_end=2)
    assert len(notified) == 1
    actions.delete_course(name="听力课")
    assert len(notified) == 2
