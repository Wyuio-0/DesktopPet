"""Persistent sync tombstones prevent deleted study records from resurfacing."""
import json
import os
import threading
from pathlib import Path

from .settings import config_dir

CATEGORIES = ("schedule", "exams", "notes")
MAX_IDS = 10_000
MAX_ID_LENGTH = 128
_lock = threading.RLock()


def _path():
    return Path(config_dir()) / "sync_tombstones.json"


def _empty():
    return {category: set() for category in CATEGORIES}


def _valid_id(item):
    if not isinstance(item, str) or not item:
        return False
    try:
        return len(item.encode("utf-8")) <= MAX_ID_LENGTH
    except UnicodeEncodeError:
        return False


def validate(value):
    if value is None:
        return _empty()
    if not isinstance(value, dict) or set(value) - set(CATEGORIES):
        raise ValueError("无效的同步删除记录")
    result = _empty()
    for category, rows in value.items():
        if (not isinstance(rows, list) or len(rows) > MAX_IDS
                or any(not _valid_id(item) for item in rows)
                or len(set(rows)) != len(rows)):
            raise ValueError("无效的同步删除记录")
        result[category] = set(rows)
    return result


def _load():
    path = _path()
    if not path.exists():
        return _empty()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema") != 1:
        raise OSError("同步删除记录损坏")
    return validate({key: value for key, value in raw.items() if key != "schema"})


def _save(value):
    for category in CATEGORIES:
        if len(value[category]) > MAX_IDS:
            raise OSError("同步删除记录达到容量上限")
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as stream:
            json.dump({"schema": 1, **{key: sorted(value[key]) for key in CATEGORIES}},
                      stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def snapshot():
    with _lock:
        current = _load()
        return {key: sorted(current[key]) for key in CATEGORIES}


def record(category, item_id):
    return record_many(category, [item_id])


def record_many(category, item_ids):
    if (category not in CATEGORIES or not isinstance(item_ids, (list, tuple, set))
            or any(not _valid_id(item_id) for item_id in item_ids)):
        return False
    with _lock:
        try:
            current = _load()
            updated = current[category] | set(item_ids)
            if len(updated) > MAX_IDS:
                return False
            if updated == current[category]:
                return True
            current[category] = updated
            _save(current)
            return True
        except (OSError, ValueError, TypeError):
            return False


def forget(category, item_id):
    with _lock:
        try:
            current = _load()
            current[category].discard(item_id)
            _save(current)
        except (OSError, ValueError, TypeError):
            pass


def apply(incoming, mode, categories, local_ids, live_ids):
    """Merge peer tombstones; replacements clear tombstones for restored live IDs."""
    with _lock:
        current = _load()
        if not isinstance(incoming, dict):
            raise ValueError("无效的同步删除记录")
        remote_input = {category: sorted(rows) if isinstance(rows, set) else rows
                        for category, rows in incoming.items()}
        remote = validate(remote_input)
        for category in CATEGORIES:
            current[category].update(remote[category])
        if mode == "replace":
            for category in categories:
                current[category].update(set(local_ids.get(category, ())) - set(live_ids.get(category, ())))
                current[category].difference_update(set(live_ids.get(category, ())) - remote[category])
        _save(current)
        return {key: set(current[key]) for key in CATEGORIES}
