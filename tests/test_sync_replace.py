"""Replacement is explicit, category-scoped and validated before changing data."""
import copy
from datetime import datetime

import pytest
from unittest.mock import Mock
import threading

from pet import sync_service as sync
from pet.notes import NotesManager
from pet.tasks import Tasks
from tools.run_android_sync_acceptance import fixture


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr("pet.schedule._data_path", lambda: str(tmp_path / "schedule.json"))
    monkeypatch.setattr("pet.tasks._data_path", lambda: str(tmp_path / "tasks.json"))
    monkeypatch.setattr("pet.notes.notes_path", lambda: str(tmp_path / "notes.json"))


def lists():
    data = sync.DataSyncEngine.pack_all_data()
    return data["schedule"]["courses"], data["exams"], data["notes"]


def test_replace_removes_old_records_and_preserves_homework():
    sync.DataSyncEngine.apply_data(fixture(), "replace")
    homework = Tasks().add("本地作业", "homework", datetime(2027, 1, 1))
    incoming = fixture()
    incoming["schedule"]["courses"][0]["id"] = "new-course"
    incoming["exams"][0]["id"] = "new-exam"
    incoming["notes"][0]["id"] = "new-note"
    sync.DataSyncEngine.apply_data(incoming, "replace")
    courses, exams, notes = lists()
    assert [c["id"] for c in courses] == ["new-course"]
    assert [e["id"] for e in exams] == ["new-exam"]
    assert [n["id"] for n in notes] == ["new-note"]
    assert any(t.id == homework.id for t in Tasks().items)


def test_empty_replace_survives_reload_and_leaves_no_welcome_note():
    sync.DataSyncEngine.apply_data(fixture(), "replace")
    sync.DataSyncEngine.apply_data({"schedule": {"courses": []}, "exams": [], "notes": []}, "replace")
    assert lists() == ([], [], [])
    assert NotesManager().notes == []
    assert lists() == ([], [], [])


def test_missing_categories_and_missing_course_list_are_unchanged():
    sync.DataSyncEngine.apply_data(fixture(), "replace")
    before = lists()
    sync.DataSyncEngine.apply_data({"schedule": {"term": "新学期"}}, "replace")
    assert lists() == before
    sync.DataSyncEngine.apply_data({"notes": []}, "replace")
    assert lists() == (before[0], before[1], [])


def test_replace_uses_incoming_note_even_if_older_but_merge_keeps_newer():
    incoming = fixture()
    sync.DataSyncEngine.apply_data(incoming, "replace")
    older = copy.deepcopy(incoming["notes"][0])
    older.update(content="旧版本内容", updated_at="2020-01-01 00:00")
    sync.DataSyncEngine.apply_data({"notes": [older]}, "merge")
    assert lists()[2][0]["content"] != "旧版本内容"
    sync.DataSyncEngine.apply_data({"notes": [older]}, "replace")
    assert lists()[2] == [older]


@pytest.mark.parametrize("bad", [
    {"exams": None}, {"notes": {}}, {"schedule": []}, {"schedule": {"courses": None}},
    {"exams": [{}]}, {"notes": [{}]}, {"schedule": {"courses": [{}]}},
    {"exams": [{"title": "错时间", "examTimeMillis": "tomorrow"}]},
    {"notes": [fixture()["notes"][0], fixture()["notes"][0]]},
])
def test_bad_payload_rejected_before_any_category_changes(bad):
    sync.DataSyncEngine.apply_data(fixture(), "replace")
    before = lists()
    payload = {"schedule": {"courses": []}, "exams": [], "notes": []}
    payload.update(bad)
    with pytest.raises(ValueError):
        sync.DataSyncEngine.apply_data(payload, "replace")
    assert lists() == before


@pytest.mark.parametrize("mode", ["unknown", "", None, 1])
def test_invalid_mode_does_not_clear_data(mode):
    sync.DataSyncEngine.apply_data(fixture(), "replace")
    before = lists()
    with pytest.raises(ValueError):
        sync.DataSyncEngine.apply_data({"exams": [], "notes": []}, mode)
    assert lists() == before


def test_empty_merge_is_noop():
    sync.DataSyncEngine.apply_data(fixture(), "replace")
    before = lists()
    sync.DataSyncEngine.apply_data({"schedule": {"courses": []}, "exams": [], "notes": []}, "merge")
    assert lists() == before


def test_replace_keeps_distinct_exam_ids_with_same_title_and_time():
    first = fixture()["exams"][0]
    second = dict(first, id="second-exam", location="第二考场")
    sync.DataSyncEngine.apply_data({"exams": [first, second]}, "replace")
    assert {e["id"] for e in lists()[1]} == {"accept-exam", "second-exam"}


def test_bidirectional_sync_stops_after_failed_pull_and_pushes_merge_only():
    service = object.__new__(sync.RhodesSyncService)
    service.sync_pull = Mock(return_value=(False, "拉取失败"))
    service.sync_push = Mock(return_value=(True, {}))
    assert service.sync_merge("127.0.0.1", 23334, "test-token") == (False, "拉取失败")
    service.sync_push.assert_not_called()
    service.sync_pull.return_value = True, {}
    assert service.sync_merge("127.0.0.1", 23334, "test-token")[0]
    service.sync_push.assert_called_once_with("127.0.0.1", 23334, "test-token", mode="merge")


def test_snapshot_waits_until_all_replaced_categories_are_applied(monkeypatch):
    sync.DataSyncEngine.apply_data(fixture(), "replace")
    replacement = fixture()
    replacement["schedule"]["courses"][0]["id"] = "new-course"
    replacement["exams"][0]["id"] = "new-exam"
    replacement["notes"][0]["id"] = "new-note"
    schedule_written, release, packed = threading.Event(), threading.Event(), threading.Event()
    original = sync.Schedule.save
    def paused_save(manager, *args, **kwargs):
        result = original(manager, *args, **kwargs)
        schedule_written.set()
        assert release.wait(5)
        return result
    monkeypatch.setattr(sync.Schedule, "save", paused_save)
    result = []
    def read():
        result.append(lists())
        packed.set()
    writer = threading.Thread(target=sync.DataSyncEngine.apply_data, args=(replacement, "replace"))
    reader = threading.Thread(target=read)
    writer.start()
    try:
        assert schedule_written.wait(3)
        reader.start()
        assert not packed.wait(0.1)
    finally:
        release.set()
        writer.join(5)
        if reader.ident is not None: reader.join(5)
    assert packed.is_set()
    courses, exams, notes = result[0]
    assert [c["id"] for c in courses] == ["new-course"]
    assert [e["id"] for e in exams] == ["new-exam"]
    assert [n["id"] for n in notes] == ["new-note"]
