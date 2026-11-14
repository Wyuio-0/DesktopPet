"""Regressions found by native Android sync acceptance; all files are temporary."""
import copy
from datetime import datetime

import pytest

from pet import sync_service as sync
from pet.tasks import Task, Tasks
from tools.run_android_sync_acceptance import fixture


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr("pet.schedule._data_path", lambda: str(tmp_path / "schedule.json"))
    monkeypatch.setattr("pet.tasks._data_path", lambda: str(tmp_path / "tasks.json"))
    monkeypatch.setattr("pet.notes.notes_path", lambda: str(tmp_path / "notes.json"))


def test_wire_fields_survive_disk_roundtrip():
    wanted = fixture()
    sync.DataSyncEngine.apply_data(wanted, "replace")
    actual = sync.DataSyncEngine.pack_all_data()
    assert all(actual["schedule"]["sections"][k] == v for k, v in wanted["schedule"]["sections"].items())
    assert actual["schedule"]["courses"] == wanted["schedule"]["courses"]
    assert actual["exams"] == wanted["exams"]


def test_merge_preserves_distinct_arrangements_and_applies_edits():
    initial = fixture()
    later = copy.deepcopy(initial)
    later["schedule"]["courses"][0].update(id="even-course", parity="even")
    later["exams"][0].update(id="later-exam", examTimeMillis=1800086401234)
    sync.DataSyncEngine.apply_data(initial)
    sync.DataSyncEngine.apply_data(later)
    # Repeat and then edit the original records using their stable IDs.
    sync.DataSyncEngine.apply_data(later)
    initial["schedule"]["courses"][0].update(room="改教室", sec_start=3)
    initial["exams"][0].update(seatNumber="9", examTimeMillis=1800000061234)
    sync.DataSyncEngine.apply_data(initial)
    actual = sync.DataSyncEngine.pack_all_data()
    courses = {c["id"]: c for c in actual["schedule"]["courses"]}
    exams = {e["id"]: e for e in actual["exams"]}
    assert len(courses) == len(exams) == 2
    assert courses["accept-course"]["room"] == "改教室"
    assert courses["accept-course"]["sec_start"] == 3
    assert courses["even-course"]["parity"] == "even"
    assert exams["accept-exam"] == initial["exams"][0]
    assert exams["later-exam"] == later["exams"][0]


def test_legacy_task_format_and_local_reminders_survive_merge():
    task = Task.from_dict({"id": "accept-exam", "title": "旧考试", "kind": "exam",
                          "due": "2026-12-01 09:30", "done": True, "remind_min": 60})
    assert task.due == datetime(2026, 12, 1, 9, 30)
    manager = Tasks()
    manager.items.append(task)
    manager.save()
    sync.DataSyncEngine.apply_data(fixture())
    restored = Tasks().items[0]
    assert restored.done and restored.remind_min == 60
    assert restored.id == "accept-exam"
    assert restored.exam_details["durationMinutes"] == 75
