"""Tests for SoC coordinators (PetTrayCoordinator, PetContextMenuBuilder,
PetFocusToolsManager, PetInputController).
"""

import sys
from datetime import date
from unittest.mock import MagicMock

import pytest
from PyQt5 import QtCore, QtWidgets

# Ensure a single QApplication instance exists for tests
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

from pet.focus import PetFocusToolsManager
from pet.input_controller import PetInputController, TYPE_INTERVAL_MS, TYPE_STEP
from pet.menu import PetContextMenuBuilder
from pet.tray import PetTrayCoordinator


@pytest.fixture
def mock_window(tmp_path):
    """Create a lightweight mock of PetWindow with necessary properties."""
    w = MagicMock()
    w.char = MagicMock()
    w.char.display_name = "阿米娅"
    w.char.dir = str(tmp_path / "amiya")
    w.char.cfg = {"voice": {}, "greetings": {"enabled": False}}
    w.prefs = MagicMock()
    w.prefs.get.return_value = False
    w.brain = MagicMock()
    w.voice = MagicMock()
    w.voice.enabled = True
    w.voice.volume = 0.7
    w.isVisible.return_value = True
    w._tts_supported = True
    w._tts_on = True
    w._use_clone = False
    w._body_rect.return_value = QtCore.QRect(100, 100, 200, 300)
    return w


class TestPetTrayCoordinator:
    def test_init_and_tooltip(self, mock_window):
        tray = PetTrayCoordinator(mock_window)
        # Even in headless/mock environments, coordinator doesn't crash
        tray.update_tooltip()
        assert tray.window == mock_window

    def test_visibility_toggle(self, mock_window):
        tray = PetTrayCoordinator(mock_window)
        mock_window.isVisible.return_value = True
        tray.toggle_visible()
        mock_window.hide.assert_called_once()

        mock_window.isVisible.return_value = False
        tray.toggle_visible()
        mock_window.show.assert_called_once()


class TestPetContextMenuBuilder:
    def test_init_and_cache(self, mock_window):
        builder = PetContextMenuBuilder(mock_window)
        assert builder._chars_cache is None
        chars = builder.available_characters()
        assert isinstance(chars, list)
        assert builder._chars_cache is not None

        # Invalidate cache
        builder.invalidate_characters_cache()
        assert builder._chars_cache is None

    def test_menu_structure(self, mock_window):
        builder = PetContextMenuBuilder(mock_window)
        m = QtWidgets.QMenu()
        builder.add_action_menu(m)
        builder.add_schedule_menu(m)
        builder.add_tasks_menu(m)
        builder.add_focus_menu(m)
        builder.add_trans_ocr_menu(m)
        builder.add_ai_menu(m)
        builder.add_character_menu(m)
        builder.add_audio_menu(m)

        titles = [action.text() for action in m.actions()]
        assert "动作互动" in titles
        assert "课程表" in titles
        assert "待办与考试" in titles
        assert "专注小工具" in titles
        assert "翻译与识图" in titles
        assert "AI 与档案" in titles
        assert "切换人物" in titles
        assert "声音与克隆" in titles


class TestPetFocusToolsManager:
    def test_hhmm_parsing(self):
        assert PetFocusToolsManager._parse_hhmm("08:30") == 8 * 60 + 30
        assert PetFocusToolsManager._parse_hhmm("00:00") == 0
        assert PetFocusToolsManager._parse_hhmm("23:59") == 23 * 60 + 59
        assert PetFocusToolsManager._parse_hhmm("invalid") is None
        assert PetFocusToolsManager._parse_hhmm("25:00") is None

    def test_in_window(self):
        # Daytime window: 12:00 - 14:00 (720 to 840)
        assert PetFocusToolsManager._in_window(750, 720, 840) is True
        assert PetFocusToolsManager._in_window(700, 720, 840) is False
        assert PetFocusToolsManager._in_window(840, 720, 840) is False  # [start, end)

        # Midnight-wrapping window: 23:30 - 03:00 (1410 to 180)
        assert PetFocusToolsManager._in_window(1420, 1410, 180) is True   # 23:40
        assert PetFocusToolsManager._in_window(60, 1410, 180) is True     # 01:00
        assert PetFocusToolsManager._in_window(1200, 1410, 180) is False  # 20:00

    def test_countdown_state(self, mock_window):
        fm = PetFocusToolsManager(mock_window)
        assert fm.is_focus_active() is False
        assert fm.has_active_pomodoro() is False

        done_called = []
        fm.start_countdown(5, "⏳", lambda: done_called.append(True))
        # Initial tick decrements by 1 to paint immediately
        assert fm._cd_left == 4
        assert fm._cd_label == "⏳"
        assert fm.is_focus_active() is True

        fm.cancel_countdown()
        assert fm.is_focus_active() is False
        assert fm._cd_left == 0
        fm.close()


class TestPetInputController:
    def test_placeholder(self, mock_window):
        ctrl = PetInputController(mock_window)
        ctrl.update_placeholder()
        assert "阿米娅" in ctrl.input.placeholderText()

    def test_typewriter_step_catchup(self, mock_window):
        ctrl = PetInputController(mock_window)
        ctrl._chat_anchor = QtCore.QRect(0, 0, 100, 100)
        ctrl._type_target = "Hello World"
        ctrl._type_shown = 0
        ctrl._type_final = False

        # One tick reveals chars
        ctrl.type_tick()
        assert ctrl._type_shown >= TYPE_STEP
        ctrl.close()

    def test_open_chat_preserves_sitting(self, mock_window):
        ctrl = PetInputController(mock_window)
        mock_window._first_frame_shown = True
        mock_window._cur_action = MagicMock()
        mock_window._cur_action.name = "sit"
        mock_window._wake = MagicMock()

        ctrl.open_chat()
        # Should not wake/force to idle if sitting
        mock_window._wake.assert_not_called()
        ctrl.close()

    def test_open_chat_wakes_from_sleep(self, mock_window):
        ctrl = PetInputController(mock_window)
        mock_window._first_frame_shown = True
        mock_window._cur_action = MagicMock()
        mock_window._cur_action.name = "sleep"
        mock_window._wake = MagicMock()

        ctrl.open_chat()
        # Should wake if sleeping
        mock_window._wake.assert_called_once()
        ctrl.close()

    def test_on_reply_preserves_sitting(self, mock_window):
        ctrl = PetInputController(mock_window)
        ctrl._chat_anchor = QtCore.QRect(0, 0, 100, 100)
        mock_window._cur_action = MagicMock()
        mock_window._cur_action.name = "sit"
        mock_window.play = MagicMock()

        ctrl.on_reply("这是博士的回复")
        # Should NOT play standing greet if sitting
        mock_window.play.assert_not_called()
        ctrl.close()

    def test_on_reply_plays_greet_when_standing(self, mock_window):
        ctrl = PetInputController(mock_window)
        ctrl._chat_anchor = QtCore.QRect(0, 0, 100, 100)
        mock_window._cur_action = MagicMock()
        mock_window._cur_action.name = "idle"
        mock_window.char.interaction.return_value = "greet"
        mock_window.play = MagicMock()

        ctrl.on_reply("这是博士的回复")
        # Should play greet when standing
        mock_window.play.assert_called_with("greet")
        ctrl.close()

