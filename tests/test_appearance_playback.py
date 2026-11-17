"""Changing an appearance keeps active services and rolls back bad assets."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np
import pytest
from PyQt5 import QtCore

from pet.character import Character
from pet.window import PetWindow


@pytest.fixture
def appearance_window(tmp_path):
    directory = tmp_path / "amiya"
    directory.mkdir()
    png = directory / "sprite.png"
    pixels = np.zeros((64, 64, 4), np.uint8)
    pixels[8:56, 16:48] = (2, 3, 4, 255)
    _, encoded = cv2.imencode(".png", pixels)
    png.write_bytes(encoded.tobytes())
    (directory / "config.json").write_text(json.dumps({
        "name": "Amiya", "actions": {"idle": {"loop": True}},
        "appearances": {"illustrated": {"actions": {
            "idle": {"loop": True, "sprite": {"sheet": "sprite.png"}}
        }}}
    }), encoding="utf-8")
    char = Character(str(directory))
    window = SimpleNamespace(
        char=char, brain=object(), voice=object(), _tts_worker=object(),
        _trans_worker=object(), _ocr_worker=object(), input_ctrl=object(),
        focus_mgr=object(), _timer=Mock(), _rest_timer=Mock(),
        _compress_timer=Mock(), _cap=Mock(), _mem=Mock(),
        _cur_action=char.action("idle"), _frames=["old cached frame"],
        _last_bgra=np.ones((4, 4, 4), np.uint8), _replay=True,
        _replay_i=1, _cache_full=True, _skip_count=4,
        prefs=Mock(), wander_coord=SimpleNamespace(cancel_wandering=Mock()),
        x=lambda: 100, y=lambda: 200, width=lambda: 400, height=lambda: 500,
        _load_rest_config=Mock(), _schedule_rest=Mock(), _tick=Mock(),
        bubble=SimpleNamespace(say=Mock()), _body_rect=Mock(return_value=QtCore.QRect(100, 200, 400, 500)),
    )
    window.prefs.get.return_value = 1.0
    window._capture_action = PetWindow._capture_action
    window.play = lambda action: PetWindow.play(window, action)
    return window, png


def test_appearance_swap_preserves_live_services_and_clears_old_frames(appearance_window):
    window, _ = appearance_window
    service_names = ("brain", "voice", "_tts_worker", "_trans_worker",
                     "_ocr_worker", "input_ctrl", "focus_mgr")
    services = {name: getattr(window, name) for name in service_names}
    previous_capture = window._cap
    assert PetWindow._switch_appearance(window, "illustrated")
    assert window.char.appearance_key == "illustrated"
    assert all(getattr(window, name) is service for name, service in services.items())
    previous_capture.release.assert_called_once()
    assert window._frames == [] and window._last_bgra is None
    assert not window._replay and window._replay_i == 0
    assert window._appearance_anchor == (299, 700)
    window._compress_timer.stop.assert_called_once()
    window.wander_coord.cancel_wandering.assert_called_once()
    window.prefs.set.assert_called_once_with("appearance_amiya", "illustrated")
    window._tick.assert_called_once()
    window._cap.release()


def test_broken_appearance_keeps_live_model_and_animation(appearance_window):
    window, png = appearance_window
    png.unlink()
    previous = window.char
    previous_capture = window._cap
    previous_frames = window._frames
    assert not PetWindow._switch_appearance(window, "illustrated")
    assert window.char is previous and window._cap is previous_capture
    assert window._frames is previous_frames
    previous_capture.release.assert_not_called()
    window.prefs.set.assert_not_called()
    window.wander_coord.cancel_wandering.assert_not_called()
    window.bubble.say.assert_called_once()


def test_startup_restores_saved_appearance_and_falls_back_if_asset_missing(appearance_window):
    window, png = appearance_window
    window.prefs.get.return_value = "illustrated"
    restored = PetWindow._preferred_character(window.char, window.prefs)
    assert restored.appearance_key == "illustrated"
    png.unlink()
    restored = PetWindow._preferred_character(window.char, window.prefs)
    assert restored.appearance_key == "default"
    assert restored.key == window.char.key


def test_shipped_illustrated_actions_all_decode():
    from pathlib import Path
    from pet.sprite_animation import SpriteCapture, resize_sprite

    directory = Path(__file__).resolve().parents[1] / "characters" / "amiya"
    original = Character(str(directory))
    illustrated = Character(str(directory), "illustrated")
    assert all(action.pick_clip() for action in original.actions.values())
    for action in illustrated.actions.values():
        source = SpriteCapture(action.sprite, illustrated.dir)
        ok, frame = source.read()
        assert ok and frame.shape == (512, 512, 4)
        for density in (1, 2):
            scaled = resize_sprite(frame, illustrated.scale * density)
            assert scaled[:, :, 3].max() > 245
            assert (scaled[:, :, 3] == 0).any()
        source.release()
