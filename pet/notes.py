"""桌面灵感便签数据管理模块（Rhodes Sticky Note & Scratchpad）。

持久化保存在用户配置目录（%APPDATA%\\AmiyaPet\\notes.json），
支持环境变量 PET_NOTES_FILE 覆盖（单测与环境隔离）。
支持多便签、自动标题提炼、置顶标记与原子存盘。
"""

import json
import os
import uuid
from datetime import datetime

from .settings import config_dir

_CURRENT_MANAGER = None


def notes_path():
    """获取 notes.json 路径，支持 PET_NOTES_FILE 覆盖。"""
    return os.environ.get("PET_NOTES_FILE") or os.path.join(
        config_dir(), "notes.json"
    )


class Note:
    """单个便签实体。"""

    def __init__(self, note_id=None, title="灵感随记", content="", created_at=None, updated_at=None, pinned=False, id=None):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.id = note_id or id or ("note_" + uuid.uuid4().hex[:8])
        self.title = str(title or "灵感随记").strip()
        self.content = str(content or "")
        self.created_at = str(created_at or now_str)
        self.updated_at = str(updated_at or now_str)
        self.pinned = bool(pinned)

    def auto_derive_title(self, max_len: int = 16) -> str:
        """从第一行内容中自动提炼标题（最长 max_len 个字符）。"""
        lines = [line.strip() for line in self.content.splitlines() if line.strip()]
        if not lines:
            return "空白便签"
        first = lines[0].lstrip("#-•* ")
        return (first[:max_len] + "…") if len(first) > max_len else first

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pinned": self.pinned,
        }

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            return cls()
        return cls(
            note_id=data.get("id"),
            title=data.get("title", "灵感随记"),
            content=data.get("content", ""),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            pinned=data.get("pinned", False),
        )


class NotesManager:
    """管理便签列表、活跃便签与持久化存储。"""

    def __init__(self, filepath=None):
        self.filepath = filepath or notes_path()
        self.notes = []
        self.active_id = ""
        self.load()

    def load(self):
        """从 JSON 加载便签列表，自动容错。"""
        if not os.path.isfile(self.filepath):
            self._init_default()
            return
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                raw_notes = data.get("notes") or []
                self.notes = [Note.from_dict(d) for d in raw_notes if isinstance(d, dict)]
                self.active_id = str(data.get("active_id") or "")
            elif isinstance(data, list):
                self.notes = [Note.from_dict(d) for d in data if isinstance(d, dict)]
        except Exception:
            self.notes = []

        if not self.notes:
            self._init_default()
        elif not any(n.id == self.active_id for n in self.notes):
            self.active_id = self.notes[0].id

    def _init_default(self):
        """初始化一个包含简短使用介绍的默认便签。"""
        default_note = Note(
            title="罗德岛灵感随记",
            content="欢迎使用罗德岛灵感便签！\n\n- 随手记录想法、代码片段或临时待办\n- 输入即自动保存，不丢任何字句\n- 点击顶部 🤖 按钮，让阿米娅帮您提取待办或整理笔记\n- 按 Alt+N 即可随时唤出或隐藏",
            pinned=True,
        )
        self.notes = [default_note]
        self.active_id = default_note.id
        self.save()

    def save(self) -> bool:
        """原子写入 JSON 持久化存储。"""
        data = {
            "active_id": self.active_id,
            "notes": [n.to_dict() for n in self.notes],
        }
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            tmp = self.filepath + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.filepath)
            return True
        except Exception:
            return False

    def list_notes(self) -> list:
        return list(self.notes)

    def get_note(self, note_id: str):
        for n in self.notes:
            if n.id == note_id:
                return n
        return None

    def get_active_note(self) -> Note:
        for n in self.notes:
            if n.id == self.active_id:
                return n
        if self.notes:
            self.active_id = self.notes[0].id
            return self.notes[0]
        self._init_default()
        return self.notes[0]

    def set_active_id(self, note_id: str) -> bool:
        if any(n.id == note_id for n in self.notes):
            self.active_id = note_id
            self.save()
            return True
        return False

    def create_note(self, title="", content="", pinned=False) -> Note:
        new_note = Note(title=title or "未命名便签", content=content, pinned=pinned)
        if not title and content:
            new_note.title = new_note.auto_derive_title()
        self.notes.insert(0, new_note)
        self.active_id = new_note.id
        self.save()
        return new_note

    @property
    def active_note_id(self) -> str:
        return self.active_id

    def toggle_pinned(self, note_id: str) -> bool:
        target = self.get_note(note_id)
        if not target:
            return False
        target.pinned = not target.pinned
        self.save()
        return target.pinned

    def update_note(self, note_id: str, content=None, title=None, pinned=None):
        target = self.get_note(note_id)
        if not target:
            return None
        changed = False
        if content is not None and content != target.content:
            target.content = str(content)
            target.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            if (not title and target.title in ("未命名便签", "空白便签", "灵感随记")) or not target.title:
                target.title = target.auto_derive_title()
            changed = True
        if title is not None and title.strip():
            target.title = title.strip()
            changed = True
        if pinned is not None and pinned != target.pinned:
            target.pinned = bool(pinned)
            changed = True
        if changed:
            self.save()
        return target

    def delete_note(self, note_id: str) -> bool:
        idx = -1
        for i, n in enumerate(self.notes):
            if n.id == note_id:
                idx = i
                break
        if idx < 0:
            return False

        self.notes.pop(idx)
        if not self.notes:
            self._init_default()
        elif self.active_id == note_id:
            self.active_id = self.notes[min(idx, len(self.notes) - 1)].id
        self.save()
        return True


def get_notes_manager() -> NotesManager:
    """获取单例 NotesManager。"""
    global _CURRENT_MANAGER
    if _CURRENT_MANAGER is None:
        _CURRENT_MANAGER = NotesManager()
    return _CURRENT_MANAGER


def reload_notes_manager() -> NotesManager:
    """强制重新加载 NotesManager（单测与配置重载用）。"""
    global _CURRENT_MANAGER
    _CURRENT_MANAGER = NotesManager()
    return _CURRENT_MANAGER
