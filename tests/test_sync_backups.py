import json
from datetime import datetime

import pytest

from pet import sync_service as sync
from pet import sync_backups as backups
from pet.notes import NotesManager
from pet.schedule import Schedule
from pet.tasks import Tasks
from tools.run_android_sync_acceptance import fixture


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr("pet.schedule._data_path", lambda: str(tmp_path / "schedule.json"))
    monkeypatch.setattr("pet.tasks._data_path", lambda: str(tmp_path / "tasks.json"))
    monkeypatch.setattr("pet.notes.notes_path", lambda: str(tmp_path / "notes.json"))
    monkeypatch.setattr(backups, "backup_directory", lambda: tmp_path / "backups")


def seed():
    sync.DataSyncEngine.apply_data(fixture(), "replace", _backup=False)


def contents():
    data = sync.DataSyncEngine.pack_all_data()
    return {key: data[key] for key in ("schedule", "exams", "notes")}


def test_backup_before_replace_and_restore_preserves_local_metadata_and_homework():
    seed()
    schedule = Schedule()
    schedule.remind_minutes = 25
    schedule.adjustments = [{"date": "2026-12-01", "type": "suspend", "reason": "停课"}]
    schedule.save(week_start_day="monday")
    tasks = Tasks()
    tasks.items[0].done = True
    tasks.items[0].remind_min = 99
    tasks.items[0].created = datetime(2020, 1, 1)
    tasks.save()
    original = contents()
    sync.DataSyncEngine.apply_data({"schedule": {"courses": []}, "exams": [], "notes": []}, "replace")
    entry = sync.DataSyncEngine.list_backups()[0]
    assert entry["valid"] and set(entry["categories"]) == {"schedule", "exams", "notes"}
    homework = Tasks().add("备份后新建作业", "homework", datetime(2027, 1, 1))
    sync.DataSyncEngine.restore_backup(entry["id"])
    assert contents() == original
    assert Schedule().adjustments == schedule.adjustments
    assert Schedule().week_start_day == "monday"
    restored = next(t for t in Tasks().items if t.kind == "exam")
    assert restored.done and restored.remind_min == 99 and restored.created == datetime(2020, 1, 1)
    assert any(t.id == homework.id for t in Tasks().items)
    assert sync.DataSyncEngine.list_backups()[0]["reason"] == "before_restore"


def test_partial_restore_does_not_change_other_categories():
    seed()
    before = contents()
    sync.DataSyncEngine.apply_data({"notes": []}, "replace")
    backup_id = sync.DataSyncEngine.list_backups()[0]["id"]
    sync.DataSyncEngine.apply_data({"exams": []}, "replace")
    sync.DataSyncEngine.restore_backup(backup_id)
    assert contents()["notes"] == before["notes"]
    assert contents()["exams"] == []


def test_backup_failure_blocks_replacement(monkeypatch):
    seed()
    before = contents()
    def fail(*args, **kwargs): raise backups.BackupError("备份失败")
    monkeypatch.setattr(backups.BackupStore, "create", fail)
    with pytest.raises(backups.BackupError): sync.DataSyncEngine.apply_data({"notes": []}, "replace")
    assert contents() == before


def test_bad_request_and_merge_do_not_create_backups():
    seed()
    sync.DataSyncEngine.apply_data({"notes": []}, "merge")
    with pytest.raises(ValueError): sync.DataSyncEngine.apply_data({"notes": None}, "replace")
    assert not sync.DataSyncEngine.list_backups()


@pytest.mark.parametrize("field,value", [("payload", None), ("platform", "android"), ("created_ms", 10**30)])
def test_corrupt_or_wrong_platform_backup_does_not_change_data(field, value):
    seed()
    sync.DataSyncEngine.apply_data({"notes": []}, "replace")
    entry = sync.DataSyncEngine.list_backups()[0]
    path = backups.backup_directory() / (entry["id"] + ".json")
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope[field] = envelope["payload"] + " " if field == "payload" else value
    path.write_text(json.dumps(envelope), encoding="utf-8")
    before = contents()
    with pytest.raises(backups.BackupError): sync.DataSyncEngine.restore_backup(entry["id"])
    assert contents() == before
    assert not sync.DataSyncEngine.list_backups()[0]["valid"]


def test_retention_and_allowlisted_snapshot(tmp_path):
    seed()
    marker = "example_private_configuration"
    (tmp_path / "paired_devices.json").write_text(json.dumps({"token": marker}))
    for _ in range(13): sync.DataSyncEngine.apply_data({"notes": []}, "replace")
    entries = sync.DataSyncEngine.list_backups()
    assert len(entries) == backups.KEEP
    assert all(e["valid"] for e in entries)
    for path in backups.backup_directory().glob("*.json"):
        assert marker not in path.read_text(encoding="utf-8")
    assert not list(backups.backup_directory().glob("*.tmp"))


@pytest.mark.parametrize("backup_id", ["../notes", "C:/notes.json", "", "b-fake"])
def test_arbitrary_path_restore_rejected(backup_id):
    with pytest.raises(backups.BackupError): backups.BackupStore().load(backup_id)


def test_restore_cancellation_when_safety_backup_fails(monkeypatch):
    seed()
    sync.DataSyncEngine.apply_data({"notes": []}, "replace")
    backup_id = sync.DataSyncEngine.list_backups()[0]["id"]
    before = contents()
    def fail(*args, **kwargs): raise backups.BackupError("备份失败")
    monkeypatch.setattr(backups.BackupStore, "create", fail)
    with pytest.raises(backups.BackupError): sync.DataSyncEngine.restore_backup(backup_id)
    assert contents() == before


def test_size_limit_blocks_replacement(monkeypatch):
    seed()
    before = contents()
    monkeypatch.setattr(backups, "MAX_BYTES", 64)
    with pytest.raises(backups.BackupError): sync.DataSyncEngine.apply_data({"notes": []}, "replace")
    assert contents() == before
