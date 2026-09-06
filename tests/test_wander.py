"""Tests for PetWanderCoordinator (wandering & taskbar snapping)."""

import sys
from unittest.mock import MagicMock

import pytest
from PyQt5 import QtCore, QtWidgets

# Ensure a single QApplication instance exists for tests
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

from pet.wander import PetWanderCoordinator


@pytest.fixture
def mock_window():
    """Create a mock PetWindow suitable for testing PetWanderCoordinator."""
    w = MagicMock()
    w.prefs = {
        "wandering_enabled": True,
        "taskbar_dock_enabled": True,
    }
    w.isVisible.return_value = True
    w._quitting = False
    w._moved = False
    w._drag_offset = None
    w._first_frame_shown = True
    w._cur_action = MagicMock()
    w._cur_action.name = "idle"
    w._facing_left = False
    w.input = MagicMock()
    w.input.isVisible.return_value = False
    w.input_ctrl = MagicMock()
    w.input_ctrl.worker = None
    w.focus_mgr = MagicMock()
    w.focus_mgr.is_focus_active.return_value = False

    w.width.return_value = 100
    w.x.return_value = 500
    w.y.return_value = 600

    # Screen mock
    mock_screen = MagicMock()
    # Available geometry e.g. 0, 0 to 1920, 1040 (taskbar at bottom 40px)
    mock_screen.availableGeometry.return_value = QtCore.QRect(0, 0, 1920, 1040)
    w.screen.return_value = mock_screen

    # Body rect mock: at x=500, y=600, w=100, h=150 -> bottom = 750
    w._body_rect.return_value = QtCore.QRect(500, 600, 100, 150)

    # Character actions mock
    w.char = MagicMock()
    w.char.action.return_value = MagicMock()

    return w


class TestPetWanderCoordinator:
    def test_init(self, mock_window):
        coord = PetWanderCoordinator(mock_window)
        assert coord.window == mock_window
        assert not coord.is_wandering
        assert coord._wander_check_timer.isSingleShot()
        coord.close()

    def test_can_wander_conditions(self, mock_window):
        coord = PetWanderCoordinator(mock_window)
        assert coord._can_wander() is True

        # Disabled via prefs
        mock_window.prefs["wandering_enabled"] = False
        assert coord._can_wander() is False
        mock_window.prefs["wandering_enabled"] = True

        # Not visible or quitting
        mock_window.isVisible.return_value = False
        assert coord._can_wander() is False
        mock_window.isVisible.return_value = True

        mock_window._quitting = True
        assert coord._can_wander() is False
        mock_window._quitting = False

        # Dragging
        mock_window._drag_offset = QtCore.QPoint(10, 10)
        assert coord._can_wander() is False
        mock_window._drag_offset = None

        # Moved
        mock_window._moved = True
        assert coord._can_wander() is False
        mock_window._moved = False

        # Not first frame shown
        mock_window._first_frame_shown = False
        assert coord._can_wander() is False
        mock_window._first_frame_shown = True

        # Action is not idle
        mock_window._cur_action.name = "drag"
        assert coord._can_wander() is False
        mock_window._cur_action.name = "idle"

        # Chat input visible
        mock_window.input.isVisible.return_value = True
        assert coord._can_wander() is False
        mock_window.input.isVisible.return_value = False

        # AI worker running
        mock_window.input_ctrl.worker = MagicMock()
        mock_window.input_ctrl.worker.isRunning.return_value = True
        assert coord._can_wander() is False
        mock_window.input_ctrl.worker = None

        # Focus mode active
        mock_window.focus_mgr.is_focus_active.return_value = True
        assert coord._can_wander() is False
        mock_window.focus_mgr.is_focus_active.return_value = False

        # Restored
        assert coord._can_wander() is True
        coord.close()

    def test_on_check_wander_starts_wandering(self, mock_window):
        coord = PetWanderCoordinator(mock_window)
        coord._on_check_wander()

        assert coord.is_wandering is True
        mock_window.play.assert_called_with("move")
        if coord.wander_dir < 0:
            assert mock_window._facing_left is True
        else:
            assert mock_window._facing_left is False
        coord.close()

    def test_on_wander_step_advances_and_completes(self, mock_window):
        coord = PetWanderCoordinator(mock_window)
        coord.is_wandering = True
        coord.wander_dir = 1
        coord.wander_target_x = 510
        mock_window.x.return_value = 500
        mock_window.y.return_value = 600
        mock_window._cur_action.name = "move"

        # Step 1: moves towards target
        coord._on_wander_step()
        mock_window.move.assert_called_with(502, 600)
        mock_window._reposition_popups.assert_called()

        # Near target: completes wander
        mock_window.x.return_value = 509
        coord._on_wander_step()
        mock_window.move.assert_called_with(510, 600)
        mock_window.play.assert_called_with("idle")
        assert not coord.is_wandering
        assert mock_window._facing_left is False
        coord.close()

    def test_cancel_wandering(self, mock_window):
        coord = PetWanderCoordinator(mock_window)
        coord.is_wandering = True
        mock_window._cur_action.name = "move"
        mock_window._facing_left = True

        coord.cancel_wandering()
        assert not coord.is_wandering
        assert mock_window._facing_left is False
        mock_window.play.assert_called_with("idle")
        coord.close()

    def test_check_taskbar_snap_success(self, mock_window):
        coord = PetWanderCoordinator(mock_window)
        # Taskbar bottom at 1040, body bottom at 1020 -> gap = 20 (within -25..50)
        mock_window._body_rect.return_value = QtCore.QRect(500, 870, 100, 150)
        mock_window.y.return_value = 870

        res = coord.check_taskbar_snap(moved=True)
        assert res is True
        mock_window.move.assert_called_once()
        mock_window.play.assert_called_with("sit")
        mock_window._save_pet_position.assert_called_once()
        coord.close()

    def test_check_taskbar_snap_too_far(self, mock_window):
        coord = PetWanderCoordinator(mock_window)
        # Taskbar bottom at 1040, body bottom at 750 -> gap = 290 (far away)
        mock_window._body_rect.return_value = QtCore.QRect(500, 600, 100, 150)
        mock_window.y.return_value = 600

        res = coord.check_taskbar_snap(moved=True)
        assert res is False
        coord.close()

    def test_check_taskbar_snap_disabled_in_prefs(self, mock_window):
        coord = PetWanderCoordinator(mock_window)
        mock_window.prefs["taskbar_dock_enabled"] = False
        mock_window._body_rect.return_value = QtCore.QRect(500, 870, 100, 150)

        res = coord.check_taskbar_snap(moved=True)
        assert res is False
        coord.close()
