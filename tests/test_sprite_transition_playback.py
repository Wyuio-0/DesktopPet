"""Display transitions must not reintroduce an old action on cached loops."""

from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np
import pytest
from PyQt5 import QtWidgets

from pet.window import PetWindow


@pytest.fixture
def qt_app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_display_fade_preserves_cached_frames_and_finishes(qt_app):
    pet = PetWindow.__new__(PetWindow)
    QtWidgets.QWidget.__init__(pet)
    pet.label = QtWidgets.QLabel(pet)
    pet._dpr = 1
    pet._first_frame_shown = True
    previous = np.full((16, 16, 4), (20, 40, 60, 255), np.uint8)
    current = np.full((16, 16, 4), (100, 120, 140, 255), np.uint8)
    pet._sprite_transition_from = previous
    pet._sprite_transition_step = 0
    pet._frames = [current]
    pet._show(current)
    np.testing.assert_array_equal(pet._last_bgra[0, 0], [60, 80, 100, 255])
    np.testing.assert_array_equal(pet._frames[0][0, 0], [100, 120, 140, 255])
    pet._show(current)
    np.testing.assert_array_equal(pet._last_bgra, current)
    assert pet._sprite_transition_from is None
    assert pet._last_facing_left is False
    # Cache replay must remain the new pose, without the previous action ghost.
    pet._show(pet._frames[0])
    np.testing.assert_array_equal(pet._last_bgra, current)
    pet.deleteLater()


@pytest.mark.parametrize("was_sprite", [True, False])
def test_new_action_uses_latest_sprite_pose_for_display_transition(was_sprite):
    latest = np.full((16, 16, 4), 255, np.uint8)
    action = SimpleNamespace(sprite={}, loop=True, loop_count=0, interval=50)
    capture = Mock()
    capture.get.return_value = 20
    pet = SimpleNamespace(
        _facing_left=False, _cur_action=SimpleNamespace(sprite={} if was_sprite else None),
        _last_bgra=latest, char=SimpleNamespace(action=lambda name: action),
        _capture_action=lambda character, selected: capture, _cap=Mock(),
        _mem=Mock(), _compress_timer=Mock(), _timer=Mock(),
        prefs=SimpleNamespace(get=lambda key, default: default), _schedule_rest=Mock(),
    )
    assert PetWindow.play(pet, "greet")
    assert (pet._sprite_transition_from is latest) is was_sprite
    assert pet._last_bgra is None
    assert pet._frames == []
    capture.get.assert_called_once_with(cv2.CAP_PROP_FPS)


def test_turn_uses_displayed_direction_before_wander_sets_next_direction():
    latest = np.zeros((8, 8, 4), np.uint8)
    latest[:, :3] = (20, 40, 60, 255)
    action = SimpleNamespace(sprite={}, loop=True, loop_count=0, interval=50)
    capture = Mock()
    capture.get.return_value = 20
    pet = SimpleNamespace(
        _facing_left=True, _last_facing_left=False,
        _cur_action=SimpleNamespace(sprite={}), _last_bgra=latest,
        char=SimpleNamespace(action=lambda name: action),
        _capture_action=lambda character, selected: capture, _cap=Mock(),
        _mem=Mock(), _compress_timer=Mock(), _timer=Mock(),
        prefs=SimpleNamespace(get=lambda key, default: default), _schedule_rest=Mock(),
    )
    assert PetWindow.play(pet, "move")
    np.testing.assert_array_equal(pet._sprite_transition_from, cv2.flip(latest, 1))
