"""Frame decoding + chroma-key: turn an opaque webm frame into BGRA.

The webm clips render the character on a solid black background.  Because the
character contains genuinely dark pixels (outlines, dark clothing), a plain
threshold would punch holes in her.  The old approach flood-filled dark pixels
from the four corners, which left two classes of artifacts:

* **Enclosed background pockets** — gaps between moving body parts (arm vs
  waist, skirt vs legs, hair vs head) that are not connected to the border in
  the current frame.  They stayed fully opaque and flickered as black blobs
  whenever the character animated.
* **Noise-broken connectivity** — anything that broke the dark pixel path
  (compression noise, a slightly bright pixel) stranded background regions
  behind it.

This version works on a *background-like* mask — near-black **and** low-chroma,
so dark *coloured* artwork (a navy dress, purple shading, outlines with hue) is
never misclassified:

1. a single flood-fill over a 1 px border padding marks every background-like
   component that touches the frame border -> transparent,
2. the remaining background-like components are fully enclosed by the
   character: background pockets between body parts -> also transparent
   (size-guarded so tiny dark features such as eyes/pupils are never eaten),
3. the character's interior stays fully opaque and only the thin edge fringe
   is feathered with a brightness ramp — anti-aliased edges, solid core.
"""

import cv2
import numpy as np

# Max channel brightness below which a pixel *may* be background.  The real
# background is essentially 0 (border stats <= 4) while the character's dark
# line art sits around 19-45, so 18 separates them cleanly.
_BG_MAX = 18
# Max channel spread (crude chroma).  Guards dark coloured artwork (dress
# folds, shading, outlines with hue) from ever being treated as background.
_BG_CHROMA = 12
# Enclosed background-like regions smaller than this fraction of the frame are
# kept (eyes, pupils, tiny specks).  1000x1000 -> 40 px; 765x765 -> ~23 px.
_MIN_HOLE_RATIO = 4e-5
# Brightness at which a pixel is fully opaque; below it alpha ramps down so
# anti-aliased edges fade smoothly instead of showing a hard black fringe.
_SOLID = 40


def _bg_mask(frame):
    """Near-black AND low-chroma mask (uint8, 255 = background-like)."""
    b, g, r = cv2.split(frame)
    maxc = cv2.max(cv2.max(b, g), r)
    chroma = cv2.subtract(maxc, cv2.min(cv2.min(b, g), r))
    dark = cv2.threshold(maxc, _BG_MAX, 255, cv2.THRESH_BINARY_INV)[1]
    grey = cv2.threshold(chroma, _BG_CHROMA, 255, cv2.THRESH_BINARY_INV)[1]
    return cv2.bitwise_and(dark, grey), maxc


def key_frame(frame, scale):
    """frame: HxWx3 BGR uint8 -> HxWx4 BGRA uint8, resized by `scale`."""
    h, w = frame.shape[:2]
    if scale != 1.0:
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)),
                           interpolation=cv2.INTER_AREA)
        h, w = frame.shape[:2]

    bg, maxc = _bg_mask(frame)

    # 1) Background connected to the border.  Pad with one border ring of
    # background so a single flood-fill from (0,0) marks *all* border-touching
    # background components, not just the four corners.
    padded = np.zeros((h + 2, w + 2), np.uint8)
    padded[1:-1, 1:-1] = bg
    padded[0, :] = padded[-1, :] = padded[:, 0] = padded[:, -1] = 255
    ffmask = np.zeros((h + 4, w + 4), np.uint8)
    cv2.floodFill(padded, ffmask, (0, 0), 128)
    outside = padded[1:-1, 1:-1] == 128

    # 2) Enclosed pockets: background-like regions surrounded by the character.
    holes = (bg > 0) & ~outside
    if holes.any():
        # Drop tiny holes (eyes, specks); keep real pockets.
        n, labels, stats, _ = cv2.connectedComponentsWithStats(
            holes.astype(np.uint8), connectivity=4)
        min_hole = max(12, int(h * w * _MIN_HOLE_RATIO))
        drop = np.zeros(n, bool)
        drop[1:] = stats[1:, cv2.CC_STAT_AREA] < min_hole
        holes[drop[labels]] = False
    transparent = outside | holes

    # Keep the character's interior fully opaque (so dark outlines/clothing
    # stay crisp), and feather only the thin edge fringe against the black
    # background using a brightness ramp — anti-aliased edges, solid core.
    opaque = (~transparent).astype(np.uint8) * 255
    core = cv2.erode(opaque, np.ones((3, 3), np.uint8), iterations=1)
    soft = np.clip(maxc.astype(np.int32) * 255 // _SOLID, 0, 255).astype(np.uint8)
    alpha = np.where(core > 0, 255,
                     np.where(transparent, 0, soft)).astype(np.uint8)

    bgra = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = alpha
    return bgra


def calc_action_interval(action_interval, fps=0.0, speed_mult=1.0):
    """计算动作播放的真实帧间隔（毫秒）。

    - 优先使用 action_interval（各角色 config.json 中为各动作精确校准的原生真实毫秒间隔）。
    - 若未配置或为 0，且视频容器提供了合理帧率 (1 < fps <= 120)，按 round(1000 / fps) 计算。
    - 若两者皆无或 fps 异常（如 WebM 容器缺省时间基返回 1000.0），兜底为 25ms (~40fps)。
    - 若指定了速度倍率 speed_mult (> 0)，则按 interval / speed_mult 换算。
    - 最终 clamp 在 [10, 1000] ms，保证 QTimer 安全且不吃满 CPU。
    """
    if action_interval and action_interval > 0:
        interval = int(action_interval)
    elif fps and 1 < fps <= 120:
        interval = round(1000 / fps)
    else:
        interval = 25
    if speed_mult and speed_mult > 0 and speed_mult != 1.0:
        interval = round(interval / speed_mult)
    return max(10, min(1000, interval))
