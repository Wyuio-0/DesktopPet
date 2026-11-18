"""Alpha-preserving illustrated animation source with the VideoCapture interface."""

import math
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np


def _transform_alpha(frame, operation):
    """Filter premultiplied color so hidden background RGB cannot create halos."""
    pixels = frame.astype(np.float32)
    pixels[:, :, :3] *= pixels[:, :, 3:4] / 255
    filtered = operation(pixels)
    np.divide(filtered[:, :, :3] * 255, filtered[:, :, 3:4],
              out=filtered[:, :, :3], where=filtered[:, :, 3:4] > 0)
    return np.clip(np.rint(filtered), 0, 255).astype(np.uint8)


def blend_sprites(previous, current, weight):
    """Crossfade color and coverage together, without dark/transparent flashes."""
    if previous.shape != current.shape:
        return current.copy()
    weight = max(0.0, min(1.0, float(weight)))
    before = previous.astype(np.float32)
    after = current.astype(np.float32)
    before[:, :, :3] *= before[:, :, 3:4] / 255
    after[:, :, :3] *= after[:, :, 3:4] / 255
    result = before * (1 - weight) + after * weight
    np.divide(result[:, :, :3] * 255, result[:, :, 3:4],
              out=result[:, :, :3], where=result[:, :, 3:4] > 0)
    return np.clip(np.rint(result), 0, 255).astype(np.uint8)


@lru_cache(maxsize=2)
def _read_sheet(path, modified):
    sheet = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if sheet is None or sheet.ndim != 3 or sheet.shape[2] != 4:
        raise ValueError("插画动画需要含透明通道的 PNG 图片")
    return sheet


class SpriteCapture:
    """Play sprite cells with gentle breathing or swaying, retaining real alpha."""

    def __init__(self, cfg, base_dir):
        path = (Path(base_dir) / cfg["sheet"]).resolve()
        if not path.is_relative_to(Path(base_dir).resolve()):
            raise ValueError("插画文件必须位于当前角色目录内")
        self._sheet = _read_sheet(str(path), path.stat().st_mtime_ns)
        grid = cfg.get("grid", [1, 1])
        if (len(grid) != 2 or any(type(n) is not int or n < 1 for n in grid)):
            raise ValueError("插画网格尺寸无效")
        self._cols, self._rows = grid
        height, width = self._sheet.shape[:2]
        if width % self._cols or height % self._rows:
            raise ValueError("插画尺寸必须能被网格整除")
        self._width, self._height = width // self._cols, height // self._rows
        self._cells = tuple(cfg.get("cells", [0]))
        if not self._cells or len(self._cells) > 600:
            raise ValueError("插画动画帧序列无效")
        if any(type(n) is not int or not 0 <= n < self._cols * self._rows for n in self._cells):
            raise ValueError("插画动画包含越界帧")
        self._motion = cfg.get("motion", "none")
        if self._motion not in ("none", "breathe", "sway", "bounce"):
            raise ValueError("未知插画动画效果")
        self._transition_frames = cfg.get("transition_frames", 0)
        if type(self._transition_frames) is not int or not 0 <= self._transition_frames <= 8:
            raise ValueError("插画过渡帧数无效")
        self._alignment = self._validate_alignment(cfg.get("alignment"))
        self._poses = {cell: self._aligned_pose(cell) for cell in set(self._cells)}
        self._index = 0
        self._closed = False
        self._previous_cell = None
        self._last_pose = None
        self._transition_from = None
        self._transition_step = 0

    def _validate_alignment(self, alignment):
        if alignment is None:
            return None
        try:
            count = self._cols * self._rows
            anchors = np.asarray(alignment["anchors"], dtype=np.float32)
            heights = np.asarray(alignment["heights"], dtype=np.float32)
            reference = alignment.get("reference", 0)
            valid = (anchors.shape == (count, 2) and heights.shape == (count,)
                     and type(reference) is int and 0 <= reference < count
                     and np.isfinite(anchors).all() and np.isfinite(heights).all()
                     and (anchors >= 0).all() and (heights > 0).all()
                     and (anchors[:, 0] <= self._width).all()
                     and (anchors[:, 1] <= self._height).all()
                     and (heights <= self._height).all())
            if valid:
                return anchors, heights, reference
        except (KeyError, TypeError, ValueError):
            pass
        raise ValueError("插画对齐配置无效")

    def _aligned_pose(self, cell):
        left = (cell % self._cols) * self._width
        top = (cell // self._cols) * self._height
        pose = self._sheet[top:top + self._height, left:left + self._width].copy()
        if self._alignment is not None:
            anchors, heights, reference = self._alignment
            scale = float(heights[reference] / heights[cell])
            offset = anchors[reference] - scale * anchors[cell]
            matrix = np.float32([[scale, 0, offset[0]], [0, scale, offset[1]]])
            pose = _transform_alpha(pose, lambda pixels: cv2.warpAffine(
                pixels, matrix, (self._width, self._height), flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0)))
        return pose

    def isOpened(self):
        return not self._closed

    def get(self, prop):
        if prop == cv2.CAP_PROP_FPS:
            return 20.0
        if prop == cv2.CAP_PROP_FRAME_COUNT:
            return len(self._cells)
        if prop == cv2.CAP_PROP_POS_FRAMES:
            return self._index
        return 0.0

    def set(self, prop, value):
        if prop != cv2.CAP_PROP_POS_FRAMES or self._closed:
            return False
        self._index = max(0, min(len(self._cells), int(value)))
        self._previous_cell = self._last_pose = self._transition_from = None
        self._transition_step = 0
        return True

    def read(self):
        if self._closed or self._index >= len(self._cells):
            return False, None
        index = self._index
        cell = self._cells[index]
        self._index += 1
        pose = self._poses[cell]
        if cell != self._previous_cell and self._last_pose is not None and self._transition_frames:
            self._transition_from = self._last_pose
            self._transition_step = 0
        self._previous_cell = cell
        if self._transition_from is not None:
            self._transition_step += 1
            pose = blend_sprites(self._transition_from, pose,
                                 self._transition_step / self._transition_frames)
            if self._transition_step >= self._transition_frames:
                self._transition_from = None
        self._last_pose = pose.copy()
        frame = pose.copy()
        # Keep feet at a stable baseline; a tiny squash/sway gives the drawing
        # movement without inventing a walking or fully rigged skeleton.
        phase = math.tau * index / len(self._cells)
        matrix = None
        if self._motion == "breathe":
            scale_y = 1 - 0.008 * (1 - math.cos(phase))
            matrix = np.float32([[1, 0, 0], [0, scale_y, self._height * (1 - scale_y)]])
        elif self._motion == "sway":
            matrix = cv2.getRotationMatrix2D(
                (self._width / 2, self._height * 0.94), 1.1 * math.sin(phase), 1)
        elif self._motion == "bounce":
            matrix = np.float32([[1, 0, 0], [0, 1, -2 * (1 - math.cos(phase))]])
        if matrix is not None:
            frame = _transform_alpha(frame, lambda pixels: cv2.warpAffine(
                                   pixels, matrix, (self._width, self._height),
                                   flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                                   borderValue=(0, 0, 0, 0)))
        return True, frame

    def release(self):
        self._closed = True
        self._sheet = None
        self._poses.clear()
        self._last_pose = self._transition_from = None


def resize_sprite(frame, scale):
    """Resize existing BGRA; dark hair and clothing must never be chroma keyed."""
    height, width = frame.shape[:2]
    if scale == 1:
        return np.ascontiguousarray(frame)
    size = max(1, round(width * scale)), max(1, round(height * scale))
    return _transform_alpha(frame, lambda pixels: cv2.resize(
        pixels, size, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR))
