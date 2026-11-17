"""Synthetic alpha sprites exercise the illustrated pet playback contract."""

import cv2
import numpy as np
import pytest

from pet.sprite_animation import SpriteCapture, resize_sprite


@pytest.fixture
def sprite_sheet(tmp_path):
    # Each cell has real transparency, dark opaque artwork, and a unique tint.
    # Bright hidden RGB deliberately guards against halos during filtering.
    sheet = np.zeros((128, 192, 4), dtype=np.uint8)
    sheet[:, :, :3] = (255, 0, 255)
    colors = [(3 + cell, 5 + cell, 7 + cell, 255) for cell in range(6)]
    for cell, color in enumerate(colors):
        x, y = cell % 3 * 64, cell // 3 * 64
        sheet[y + 8:y + 56, x + 16:x + 48] = color
        sheet[y + 20, x + 30] = (0, 0, 0, 255)
    path = tmp_path / "透明精灵.png"
    success, encoded = cv2.imencode(".png", sheet)
    assert success
    path.write_bytes(encoded.tobytes())
    return path, colors


def config(path, **overrides):
    return {"sheet": path.name, "grid": [3, 2], "cells": [0, 5, 1],
            "motion": "none", **overrides}


def test_cells_decode_in_order_and_keep_dark_artwork_opaque(sprite_sheet):
    path, colors = sprite_sheet
    capture = SpriteCapture(config(path), path.parent)
    assert capture.isOpened()
    assert capture.get(cv2.CAP_PROP_FPS) == 20
    assert capture.get(cv2.CAP_PROP_FRAME_COUNT) == 3
    for index, cell in enumerate([0, 5, 1]):
        ok, frame = capture.read()
        assert ok
        assert frame.shape == (64, 64, 4)
        assert tuple(frame[25, 25]) == colors[cell]
        assert tuple(frame[20, 30]) == (0, 0, 0, 255)
        assert frame[0, 0, 3] == 0
        assert capture.get(cv2.CAP_PROP_POS_FRAMES) == index + 1
    assert capture.read() == (False, None)
    assert capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
    assert capture.read()[0]
    capture.release()
    assert not capture.isOpened()
    assert capture.read() == (False, None)
    assert not capture.set(cv2.CAP_PROP_POS_FRAMES, 0)


def test_decoded_frame_mutation_does_not_corrupt_cached_sheet(sprite_sheet):
    path, colors = sprite_sheet
    capture = SpriteCapture(config(path, cells=[0]), path.parent)
    _, first = capture.read()
    first[:] = 0
    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
    assert tuple(capture.read()[1][25, 25]) == colors[0]


@pytest.mark.parametrize("overrides", [
    {"grid": [0, 2]}, {"grid": [3]}, {"grid": [3, True]},
    {"grid": [5, 2]}, {"cells": []}, {"cells": [-1]},
    {"cells": [6]}, {"cells": [False]}, {"cells": [0] * 601},
    {"motion": "unknown"},
])
def test_invalid_sprite_layout_is_rejected(sprite_sheet, overrides):
    path, _ = sprite_sheet
    with pytest.raises(ValueError):
        SpriteCapture(config(path, **overrides), path.parent)


def test_sprite_path_cannot_escape_character_directory(sprite_sheet):
    path, _ = sprite_sheet
    character_dir = path.parent / "character"
    character_dir.mkdir()
    with pytest.raises(ValueError, match="目录"):
        SpriteCapture(config(path, sheet="../" + path.name), character_dir)


def test_opaque_image_without_alpha_is_rejected(tmp_path):
    path = tmp_path / "opaque.png"
    _, encoded = cv2.imencode(".png", np.full((16, 16, 3), 10, np.uint8))
    path.write_bytes(encoded.tobytes())
    with pytest.raises(ValueError, match="透明"):
        SpriteCapture({"sheet": path.name}, tmp_path)


def test_resize_ignores_hidden_rgb_and_preserves_edge_color():
    # Downscaling a black coat beside invisible magenta must not tint its edge.
    source = np.array([[[3, 5, 7, 255], [255, 0, 255, 0]],
                       [[3, 5, 7, 255], [255, 0, 255, 0]]], np.uint8)
    resized = resize_sprite(source, 0.5)
    assert resized.shape == (1, 1, 4)
    assert tuple(resized[0, 0, :3]) == (3, 5, 7)
    assert resized[0, 0, 3] == 128
    unchanged = resize_sprite(source, 1)
    np.testing.assert_array_equal(unchanged, source)


@pytest.mark.parametrize("motion", ["breathe", "sway", "bounce"])
def test_motion_is_bounded_and_keeps_transparent_corners(sprite_sheet, motion):
    path, _ = sprite_sheet
    capture = SpriteCapture(config(path, cells=[0] * 40, motion=motion), path.parent)
    boxes = []
    for _ in range(40):
        ok, frame = capture.read()
        assert ok and frame.shape == (64, 64, 4)
        assert frame[0, 0, 3] == frame[-1, -1, 3] == 0
        assert frame[30, 30, 3] == 255
        y, x = np.where(frame[:, :, 3] > 128)
        boxes.append((x.min(), y.min(), x.max(), y.max()))
    boxes = np.array(boxes)
    assert np.max(np.ptp(boxes, axis=0)) <= 5
