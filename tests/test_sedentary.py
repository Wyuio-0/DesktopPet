"""Tests for PetSedentaryCareCoordinator (Sedentary care & health reminder)."""

import sys
import time
from unittest.mock import MagicMock, patch

import pytest
from PyQt5 import QtCore, QtWidgets

# Ensure a single QApplication instance exists for tests
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

import pet.sedentary
from pet.sedentary import PetSedentaryCareCoordinator, get_idle_ms


@pytest.fixture
def mock_window():
    """Create a mock PetWindow for sedentary coordinator testing."""
    w = MagicMock()
    w.prefs = {
        "sedentary_enabled": True,
        "sedentary_interval_min": 60,
    }
    w.isVisible.return_value = True
    w._quitting = False
    w.focus_mgr = MagicMock()
    w.focus_mgr.is_focus_active.return_value = False
    return w


class TestPetSedentaryCareCoordinator:
    def test_init_and_getters(self, mock_window):
        coord = PetSedentaryCareCoordinator(mock_window)
        assert coord.window == mock_window
        assert coord.is_enabled() is True
        assert coord.get_interval_min() == 60
        coord.close()

    def test_format_reminder_text(self, mock_window):
        coord = PetSedentaryCareCoordinator(mock_window)
        assert "一小时" in coord._format_reminder_text(60)
        assert "一个半小时" in coord._format_reminder_text(90)
        assert "两小时" in coord._format_reminder_text(120)
        assert "45 分钟" in coord._format_reminder_text(45)
        coord.close()

    def test_trigger_reminder(self, mock_window):
        coord = PetSedentaryCareCoordinator(mock_window)
        coord.trigger_reminder(60)
        mock_window._announce.assert_called_once()
        args, kwargs = mock_window._announce.call_args
        assert "一小时" in args[0]
        assert kwargs.get("use_tts") is True
        coord.close()

    @patch.object(pet.sedentary, "get_idle_ms", return_value=5000)  # active (5s idle)
    def test_check_sedentary_triggers_when_duration_reached(self, mock_idle, mock_window):
        coord = PetSedentaryCareCoordinator(mock_window)
        # Simulate working for 61 minutes
        now = time.time()
        coord._session_start_time = now - 61 * 60

        coord._check_sedentary()
        mock_window._announce.assert_called_once()
        assert coord._last_remind_time > 0

        # Snooze test: checking again immediately should NOT re-trigger
        mock_window._announce.reset_mock()
        coord._check_sedentary()
        mock_window._announce.assert_not_called()

        coord.close()

    @patch.object(pet.sedentary, "get_idle_ms", return_value=5000)
    def test_snooze_triggers_after_30_minutes(self, mock_idle, mock_window):
        coord = PetSedentaryCareCoordinator(mock_window)
        now = time.time()
        coord._session_start_time = now - 95 * 60
        coord._last_remind_time = now - 31 * 60  # reminded 31 mins ago (> 30 min snooze)

        coord._check_sedentary()
        mock_window._announce.assert_called_once()
        coord.close()

    @patch.object(pet.sedentary, "get_idle_ms", return_value=700 * 1000)  # idle for 700s (> 10 mins)
    def test_resting_detection_and_reset(self, mock_idle, mock_window):
        coord = PetSedentaryCareCoordinator(mock_window)
        coord._session_start_time = time.time() - 80 * 60

        # 1. User is away resting
        coord._check_sedentary()
        assert coord._is_resting is True
        mock_window._announce.assert_not_called()

        # 2. User returns (active now)
        with patch.object(pet.sedentary, "get_idle_ms", return_value=2000):
            coord._check_sedentary()
            assert coord._is_resting is False
            # Session timer was reset to ~now
            assert time.time() - coord._session_start_time < 5
            mock_window._announce.assert_not_called()

        coord.close()

    def test_disabled_via_prefs(self, mock_window):
        mock_window.prefs["sedentary_enabled"] = False
        coord = PetSedentaryCareCoordinator(mock_window)
        coord._session_start_time = time.time() - 100 * 60
        with patch.object(pet.sedentary, "get_idle_ms", return_value=1000):
            coord._check_sedentary()
            mock_window._announce.assert_not_called()
        coord.close()
