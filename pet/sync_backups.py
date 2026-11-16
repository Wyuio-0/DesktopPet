"""Bounded, local study-data snapshots. Credentials and arbitrary paths are excluded."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import time
import uuid

from .settings import config_dir

KEEP = 10
MAX_BYTES = 16 * 1024 * 1024
ID = re.compile(r"b-[0-9]{13}-[a-f0-9]{32}\Z")
CATEGORIES = frozenset(("schedule", "exams", "notes"))


class BackupError(OSError):
    pass


def backup_directory():
    return Path(config_dir()) / "sync_backups"


class BackupStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else backup_directory()

    def _file(self, backup_id):
        if not isinstance(backup_id, str) or not ID.fullmatch(backup_id):
            raise BackupError("备份标识无效")
        path = self.directory / (backup_id + ".json")
        if path.is_symlink():
            raise BackupError("不能读取链接形式的备份")
        return path

    def _files(self):
        if not self.directory.exists(): return []
        return sorted((p for p in self.directory.glob("b-*.json") if ID.fullmatch(p.stem)), reverse=True)

    @staticmethod
    def _check_payload(payload):
        if (not isinstance(payload, dict) or set(payload) != {"data", "local"}
                or not isinstance(payload["data"], dict) or not payload["data"]
                or not set(payload["data"]).issubset(CATEGORIES | {"tombstones"})
                or not isinstance(payload["local"], dict)
                or set(payload["local"]) != (set(payload["data"]) - {"tombstones"})):
            raise BackupError("备份内容无效或不兼容")

    def create(self, payload, reason="before_replace"):
        self._check_payload(payload)
        if reason not in ("before_replace", "before_restore"):
            raise BackupError("备份原因无效")
        backup_id = f"b-{int(time.time() * 1000):013d}-{uuid.uuid4().hex}"
        target = self._file(backup_id)
        temporary = target.with_suffix(".tmp")
        try:
            # Refuse unbounded growth if a previous cleanup was blocked by the filesystem.
            if len(self._files()) > KEEP: raise BackupError("备份清理失败，请先检查备份目录")
            self.directory.mkdir(parents=True, exist_ok=True)
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            envelope = {"schema": 1, "platform": "pc", "id": backup_id,
                        "created_ms": int(time.time() * 1000), "reason": reason,
                        "payload": body, "sha256": hashlib.sha256(body.encode()).hexdigest()}
            encoded = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode()
            if len(encoded) > MAX_BYTES: raise BackupError("学业备份超过 16 MiB，覆盖已取消")
            with temporary.open("xb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            self.load(backup_id)  # Verify the committed bytes before allowing replacement.
            others = [p for p in self._files() if p != target]
            for old in others[KEEP - 1:]: old.unlink()
            return backup_id
        except BackupError:
            raise
        except (OSError, ValueError, TypeError, RecursionError) as error:
            raise BackupError("无法安全保存备份，覆盖已取消") from error
        finally:
            try: temporary.unlink(missing_ok=True)
            except OSError: pass

    def _read(self, backup_id):
        try:
            with self._file(backup_id).open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES: raise ValueError("size")
            entry = json.loads(raw)
            if (type(entry.get("schema")) is not int or entry["schema"] != 1
                    or entry.get("platform") != "pc" or entry.get("id") != backup_id
                    or entry.get("reason") not in ("before_replace", "before_restore")
                    or type(entry.get("created_ms")) is not int or not 0 < entry["created_ms"] < 253402300800000
                    or not isinstance(entry.get("payload"), str) or not isinstance(entry.get("sha256"), str)):
                raise ValueError("schema")
            digest = hashlib.sha256(entry["payload"].encode()).hexdigest()
            if not hmac.compare_digest(digest, entry["sha256"]): raise ValueError("digest")
            payload = json.loads(entry["payload"])
            self._check_payload(payload)
            return entry, payload
        except BackupError:
            raise
        except (OSError, ValueError, TypeError, AttributeError, UnicodeError, RecursionError) as error:
            raise BackupError("备份损坏、已丢失或不兼容，未恢复") from error

    def load(self, backup_id):
        return self._read(backup_id)[1]

    def list(self):
        entries = []
        for path in self._files():
            try:
                entry, payload = self._read(path.stem)
                entries.append({"id": path.stem, "created_ms": entry["created_ms"], "reason": entry["reason"],
                                "categories": [key for key in payload["data"] if key != "tombstones"], "valid": True})
            except BackupError:
                entries.append({"id": path.stem, "created_ms": 0, "reason": "corrupt", "categories": [], "valid": False})
        return entries
