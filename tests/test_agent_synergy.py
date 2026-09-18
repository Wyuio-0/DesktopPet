import os
import sys
import pytest
from pet import actions
from pet.ai import AmiyaBrain
from pet.notes import get_notes_manager, reload_notes_manager

def test_pomodoro_action():
    started_args = []
    stopped = []

    actions.set_pomodoro_starter(lambda w, b, r: started_args.append((w, b, r)))
    actions.set_focus_stopper(lambda: stopped.append(True))

    res = actions.start_pomodoro(work_minutes=25, break_minutes=5, rounds=4)
    assert '开启番茄钟' in res
    assert started_args == [(25, 5, 4)]

    res_stop = actions.stop_focus()
    assert '停止了专注' in res_stop
    assert stopped == [True]


def test_sticky_note_action(tmp_path):
    os.environ['PET_NOTES_FILE'] = str(tmp_path / 'test_notes.json')
    reload_notes_manager()

    res = actions.create_sticky_note(content='买中性笔和草稿纸', title='买文具')
    assert '已帮博士记入灵感便签' in res
    assert '买文具' in res

    read_res = actions.read_sticky_notes()
    assert '【博士的灵感便签】' in read_res
    assert '买文具' in read_res


def test_agenda_summary():
    res_today = actions.agenda_summary('today')
    assert '日程综合看板' in res_today
    assert '今天' in res_today

    res_tmr = actions.agenda_summary('tomorrow')
    assert '日程综合看板' in res_tmr
    assert '明天' in res_tmr


def test_local_intent_routing(tmp_path):
    os.environ['PET_NOTES_FILE'] = str(tmp_path / 'test_notes2.json')
    reload_notes_manager()

    started_args = []
    actions.set_pomodoro_starter(lambda w, b, r: started_args.append((w, b, r)))

    brain = AmiyaBrain(char_dir=str(tmp_path))
    brain.cfg['api_key'] = ''
    brain.cfg['public_relay_url'] = ''

    # 1. 专注番茄钟
    reply_pomo = brain._try_local_intent('开启25分钟专注')
    assert reply_pomo and '开启番茄钟' in reply_pomo
    assert started_args == [(25, 5, 4)]

    # 2. 便签速记
    reply_note = brain._try_local_intent('记一下买笔')
    assert reply_note and '已帮博士记入灵感便签' in reply_note
    notes = get_notes_manager().list_notes()
    assert any('买笔' in n.content for n in notes)

    # 3. 明日日程总结
    reply_agenda = brain._try_local_intent('总结下我明天的所有待办和课程')
    assert reply_agenda and '日程综合看板' in reply_agenda
    assert '明天' in reply_agenda

    # 4. 离线 reply 闭环测试
    res_pomo_reply = brain.reply('开启45分钟自习')
    assert '开启番茄钟' in res_pomo_reply
    assert started_args[-1] == (45, 5, 4)

    res_note_reply = brain.reply('备忘录记一下明天带身份证')
    assert '已帮博士记入灵感便签' in res_note_reply

    res_tmr_reply = brain.reply('明天有什么安排')
    assert '日程综合看板' in res_tmr_reply
