"""Pose changes keep the illustrated pet registered and visually continuous."""

import copy
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from pet.sprite_animation import SpriteCapture, blend_sprites


@pytest.fixture
def shipped_sprite():
    directory = Path(__file__).resolve().parents[1] / "characters" / "amiya"
    config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    return directory, config["appearances"]["illustrated"]["actions"]["idle"]["sprite"]


def frames_from(directory, config):
    capture = SpriteCapture(config, directory)
    frames = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frames.append(frame)
    finally:
        capture.release()
    return frames


def opaque_box(frame):
    y, x = np.where(frame[:, :, 3] > 128)
    assert len(x), "A pose transition emitted a blank frame"
    return x.min(), y.min(), x.max(), y.max()


def boot_center(frame):
    # Ignore changed ears, head tilts and raised hands: the bottom 35 pixels
    # describe the shared seated footprint instead of the changing expression.
    baseline = opaque_box(frame)[3]
    y, x = np.where((frame[:, :, 3] > 128)
                    & (np.indices(frame.shape[:2])[0] > baseline - 35))
    return x.mean(), y.max()


def test_shipped_blink_keeps_the_same_foot_position(shipped_sprite):
    directory, config = shipped_sprite
    cfg = dict(config, cells=[0, 1, 0], motion="none", transition_frames=0)
    centers = np.array([boot_center(frame) for frame in frames_from(directory, cfg)])
    assert np.ptp(centers[:, 0]) < 2
    assert np.ptp(centers[:, 1]) <= 1


def test_shipped_poses_share_scale_and_ground_baseline(shipped_sprite):
    directory, config = shipped_sprite
    cfg = dict(config, cells=list(range(6)), motion="none", transition_frames=0)
    boxes = np.array([opaque_box(frame) for frame in frames_from(directory, cfg)])
    heights = boxes[:, 3] - boxes[:, 1] + 1
    assert np.ptp(heights) <= 2
    assert np.ptp(boxes[:, 3]) <= 1


def test_shipped_idle_contains_no_blank_or_truncated_transition(shipped_sprite):
    directory, config = shipped_sprite
    frames = frames_from(directory, config)
    assert len(frames) == len(config["cells"])
    assert all(frame.shape == (512, 512, 4) for frame in frames)
    assert all(np.count_nonzero(frame[:, :, 3] > 128) > 50000 for frame in frames)


@pytest.fixture
def unequal_pose_sheet(tmp_path):
    sheet = np.zeros((64, 128, 4), np.uint8)
    sheet[:, :, :3] = (255, 0, 255)  # hidden RGB must not bleed into art
    sheet[20:44, 14:26] = (3, 5, 7, 255)
    sheet[22:52, 64 + 32:64 + 48] = (3, 5, 7, 255)
    path = tmp_path / "different-poses.png"
    ok, encoded = cv2.imencode(".png", sheet)
    assert ok
    path.write_bytes(encoded.tobytes())
    cfg = {"sheet": path.name, "grid": [2, 1], "cells": [0, 1],
           "motion": "none", "transition_frames": 0,
           "alignment": {"anchors": [[20, 44], [40, 52]],
                         "heights": [24, 30], "reference": 0}}
    return path.parent, cfg


def test_explicit_pose_anchors_align_without_changing_canvas(unequal_pose_sheet):
    directory, config = unequal_pose_sheet
    frames = frames_from(directory, config)
    boxes = np.array([opaque_box(frame) for frame in frames])
    assert all(frame.shape == (64, 64, 4) for frame in frames)
    assert abs(boxes[0, 3] - boxes[1, 3]) <= 1
    assert abs((boxes[0, 0] + boxes[0, 2]) / 2
               - (boxes[1, 0] + boxes[1, 2]) / 2) <= 1
    assert abs((boxes[0, 3] - boxes[0, 1])
               - (boxes[1, 3] - boxes[1, 1])) <= 1
    assert tuple(frames[1][30, 20]) == (3, 5, 7, 255)


@pytest.mark.parametrize("patch", [
    {"anchors": [[20, 44]]},
    {"anchors": [[20, 44], [float("nan"), 52]]},
    {"heights": [24]},
    {"heights": [24, 0]},
    {"heights": [24, float("inf")]},
    {"reference": 2},
    {"reference": -1},
])
def test_invalid_alignment_metadata_is_rejected(unequal_pose_sheet, patch):
    directory, config = unequal_pose_sheet
    cfg = copy.deepcopy(config)
    cfg["alignment"].update(patch)
    with pytest.raises(ValueError):
        SpriteCapture(cfg, directory)


def test_negative_pose_transition_length_is_rejected(unequal_pose_sheet):
    directory, config = unequal_pose_sheet
    with pytest.raises(ValueError):
        SpriteCapture(dict(config, transition_frames=-1), directory)


def test_pose_transition_mixes_color_without_pulsing_alpha(tmp_path):
    sheet = np.zeros((32, 64, 4), np.uint8)
    sheet[4:28, 8:24] = (0, 0, 0, 255)
    sheet[4:28, 32 + 8:32 + 24] = (200, 160, 80, 255)
    path = tmp_path / "expressions.png"
    ok, encoded = cv2.imencode(".png", sheet)
    assert ok
    path.write_bytes(encoded.tobytes())
    config = {"sheet": path.name, "grid": [2, 1], "cells": [0, 1, 1],
              "motion": "none", "transition_frames": 2}
    first, middle, last = frames_from(tmp_path, config)
    assert tuple(first[16, 16]) == (0, 0, 0, 255)
    assert tuple(middle[16, 16]) == (100, 80, 40, 255)
    assert tuple(last[16, 16]) == (200, 160, 80, 255)
    assert first[0, 0, 3] == middle[0, 0, 3] == last[0, 0, 3] == 0


def test_pose_blending_does_not_reveal_invisible_background_color():
    previous = np.array([[[3, 5, 7, 255], [0, 0, 0, 0]]], np.uint8)
    current = np.array([[[255, 0, 255, 0], [255, 0, 255, 0]]], np.uint8)
    blended = blend_sprites(previous, current, 0.5)
    assert tuple(blended[0, 0]) == (3, 5, 7, 128)
    assert blended[0, 1, 3] == 0
