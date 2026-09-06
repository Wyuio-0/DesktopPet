"""Tests for Rhodes Sticky Notes (桌面灵感便签)."""

import os
import sys
import tempfile
import pytest
from PyQt5 import QtCore, QtWidgets

# Ensure QApplication exists for UI tests
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

from pet.notes import Note, NotesManager, get_notes_manager, reload_notes_manager
from pet.notes_ui import StickyNoteWindow
from pet import actions


@pytest.fixture
def tmp_notes(monkeypatch):
    """Fixture providing an isolated NotesManager with a temporary file."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    monkeypatch.setenv("PET_NOTES_FILE", tmp_path)
    mgr = reload_notes_manager()
    yield mgr
    if os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except OSError:
            pass


class TestNoteModel:
    def test_auto_derive_title(self):
        n = Note(content="第一行是标题\n第二行是内容")
        assert n.auto_derive_title() == "第一行是标题"

        long_line = "这" * 30
        n2 = Note(content=long_line)
        derived = n2.auto_derive_title(max_len=16)
        assert len(derived) == 17  # 16 + "…"
        assert derived.endswith("…")

        empty_note = Note(content="")
        assert empty_note.auto_derive_title() == "空白便签"

    def test_dict_serialization(self):
        n = Note(id="test-id", title="测试便签", content="便签正文",
                 created_at="2026-09-06 12:00", updated_at="2026-09-06 12:01",
                 pinned=True)
        d = n.to_dict()
        assert d["id"] == "test-id"
        assert d["title"] == "测试便签"
        assert d["content"] == "便签正文"
        assert d["pinned"] is True

        n2 = Note.from_dict(d)
        assert n2.id == "test-id"
        assert n2.title == "测试便签"
        assert n2.content == "便签正文"
        assert n2.pinned is True


class TestNotesManager:
    def test_init_creates_default_note(self, tmp_notes):
        notes = tmp_notes.list_notes()
        assert len(notes) >= 1
        active = tmp_notes.get_active_note()
        assert active is not None

    def test_create_and_get_note(self, tmp_notes):
        note = tmp_notes.create_note(title="工作计划", content="今天完成便签功能")
        assert note.title == "工作计划"
        assert note.content == "今天完成便签功能"
        assert tmp_notes.get_note(note.id) == note
        assert tmp_notes.active_note_id == note.id

    def test_update_note(self, tmp_notes):
        note = tmp_notes.create_note(title="原标题", content="原始内容")
        updated = tmp_notes.update_note(note.id, title="新标题", content="更新后的内容")
        assert updated is not None
        assert updated.content == "更新后的内容"
        assert updated.title == "新标题"

    def test_toggle_pinned(self, tmp_notes):
        note = tmp_notes.create_note(content="重要便签")
        assert note.pinned is False
        pinned = tmp_notes.toggle_pinned(note.id)
        assert pinned is True
        assert note.pinned is True
        unpinned = tmp_notes.toggle_pinned(note.id)
        assert unpinned is False
        assert note.pinned is False

    def test_delete_note(self, tmp_notes):
        n1 = tmp_notes.create_note(content="便签1")
        n2 = tmp_notes.create_note(content="便签2")
        assert tmp_notes.delete_note(n2.id) is True
        assert tmp_notes.get_note(n2.id) is None
        # When all notes are deleted, manager guarantees at least one note
        tmp_notes.delete_note(n1.id)
        notes = tmp_notes.list_notes()
        assert len(notes) >= 1

    def test_persistence_and_reload(self, tmp_notes):
        tmp_notes.create_note(title="持久化测试", content="数据不会丢失")
        count_before = len(tmp_notes.list_notes())

        mgr2 = reload_notes_manager()
        notes2 = mgr2.list_notes()
        assert len(notes2) == count_before
        found = [n for n in notes2 if n.title == "持久化测试"]
        assert len(found) == 1
        assert found[0].content == "数据不会丢失"


class TestNotesActions:
    def test_create_sticky_note_action(self, tmp_notes):
        res = actions.create_sticky_note("复习高等数学", title="学业提醒")
        assert "已帮博士记入灵感便签「学业提醒」" in res
        assert "复习高等数学" in res

        empty_res = actions.create_sticky_note("")
        assert "不能为空" in empty_res

    def test_read_sticky_notes_action(self, tmp_notes):
        tmp_notes.create_note(title="考试复习", content="信号与系统期末考")
        res = actions.read_sticky_notes()
        assert "【博士的灵感便签】" in res
        assert "考试复习" in res

    def test_tools_schema_included(self):
        tool_names = [t["function"]["name"] for t in actions.TOOLS]
        assert "create_sticky_note" in tool_names
        assert "read_sticky_notes" in tool_names


class DummyWindow:
    def __init__(self):
        self.brain = None
        self.prefs = {}
        self.chat_opened = False

    def open_chat(self):
        self.chat_opened = True

    def x(self):
        return 100

    def y(self):
        return 100

    def width(self):
        return 120


class TestStickyNoteWindowUI:
    def test_window_lifecycle(self, tmp_notes):
        win = StickyNoteWindow(owner_window=None)
        assert win.isVisible() is False
        assert win.combo_notes.count() >= 1

        # Test note editing and word count
        win.editor.setPlainText("测试输入12345")
        assert "9 字" in win.lbl_char_count.text()

        # Test new note button
        initial_count = win.combo_notes.count()
        win.btn_new.click()
        assert win.combo_notes.count() == initial_count + 1

        # Test pin toggle
        assert win.is_pinned is True
        win.btn_pin.click()
        assert win.is_pinned is False
        win.btn_pin.click()
        assert win.is_pinned is True

        win.close()

    def test_screen_bounds_clamping(self, tmp_notes):
        dummy = DummyWindow()
        win = StickyNoteWindow(owner_window=dummy)
        screen = win._get_target_screen()
        avail = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1920, 1080)

        # Move far out to the right off-screen (like the bug where x was 2554)
        win.move(avail.right() + 500, 200)
        win.ensure_visible_on_screen()

        # Must be clamped inside the screen!
        assert win.x() + win.width() <= avail.right()
        assert win.x() >= avail.left()
        assert win.y() >= avail.top()
        assert win.y() + win.height() <= avail.bottom()

        # Center on screen test
        win.center_on_screen()
        assert abs(win.geometry().center().x() - avail.center().x()) <= 2
        assert abs(win.geometry().center().y() - avail.center().y()) <= 2

        win.close()

    def test_dock_near_pet_right_overflow_docks_left(self, tmp_notes):
        dummy = DummyWindow()
        screen = QtWidgets.QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1920, 1080)
        # Place dummy pet very close to right edge of screen
        dummy.x = lambda: avail.right() - 150
        dummy.y = lambda: 500
        dummy.width = lambda: 120

        win = StickyNoteWindow(owner_window=dummy)
        win.dock_near_pet()

        # Since right has only 30px, window must be placed to the left or clamped inside screen
        assert win.x() + win.width() <= avail.right()
        assert win.x() >= avail.left()
        win.close()

