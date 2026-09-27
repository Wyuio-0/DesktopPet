"""Shared Qt theme — unified dark violet（黑 + 淡紫）.

One palette, deliberately NOT following the Windows light/dark setting: the
pet's panels and floating overlays keep the same identity on every desktop.
The old light-mode fork was dropped when the UI was unified — before that the
app carried two clashing languages (near-black grey/gold here, GitHub-slate
plus cyan in the ported schedule panels).

Every colour is a plain hex string so it can go straight into QtGui.QColor()
from the QPainter-based views (timetable.py, music.py, region_select.py).
PANEL is the sole exception: it is deliberately translucent for floating
overlays and must never reach QColor(), which cannot parse rgba() and fails
silently rather than raising.

Contrast was measured, not eyeballed; each ratio below is against the surface
that token is actually painted on. Two rules fall out and must hold for any
new UI:

  * A filled violet button needs ACCENT (light) + near-black text, or
    ACCENT_DEEP + white text. Mid-violet #8B5CF6 with white text is only
    4.23:1 and fails AA — that is the usual trap with purple.
  * TEXT_MUTE is 3.11:1. Large text and icons only, never body copy.
"""

# ── Structure: black-violet elevation ladder ─────────────────────────────
BG = "#0A0810"                     # deepest — dialog background
PANEL_SOLID = "#120E1A"            # panel / menu background (opaque)
PANEL = "rgba(18, 14, 26, 242)"    # translucent — floating overlays only
FIELD = "#1A1425"                  # card / input surface
FIELD_DARK = "#241C33"             # hover / raised surface

# ── Borders ──────────────────────────────────────────────────────────────
# No violet hairline reaches 3:1 on FIELD, so GRID is decorative only and
# real boundaries use BORDER_STRONG or a fill change.
GRID = "#2E2440"                   # decorative hairline (1.23:1)
BORDER_STRONG = "#7C66AD"          # meaningful boundary (3.73:1 on FIELD)

# ── Accent: light violet carries the identity ────────────────────────────
ACCENT = "#A78BFA"                 # accent text, active state, left bar (6.59:1)
ACCENT_BRIGHT = "#C4B5FD"          # small accent text, more headroom (9.72:1)
ACCENT_DEEP = "#7C3AED"            # pressed / filled with white text (5.70:1)
ACCENT_SOFT = "#5B4380"            # dividers, inactive edges
ON_ACCENT = "#120E1A"              # text on an ACCENT fill (7.31:1)

# ── Text ─────────────────────────────────────────────────────────────────
TEXT = "#EDE9F4"                   # body (15.00:1 on FIELD)
TEXT_DIM = "#9D93AE"               # secondary (6.17:1 on FIELD)
TEXT_MUTE = "#6B6278"              # 3.11:1 — large text / icons ONLY

# ── Semantic ─────────────────────────────────────────────────────────────
GREEN = "#34D399"                  # 9.33:1
AMBER = "#FBBF24"                  # 10.75:1
RED = "#F87171"                    # 6.48:1

FONT = "'Microsoft YaHei UI', 'Microsoft YaHei', 'Segoe UI'"
MONO = "'Cascadia Mono', 'Consolas', 'Microsoft YaHei UI'"

# ── Type scale — 14 ad-hoc sizes collapsed into 8 roles ──────────────────
# The old spread (11/12/13/14/15/16/18/20/21/22/24/26/36/40px) meant the chat
# bubble sat at 21px while panel body copy was 13px. Pick a role, not a number.
FS_XS = 12        # badges, timestamps, meta
FS_SM = 13        # secondary body, table cells
FS_MD = 15        # dialog body default
FS_LG = 17        # card titles, section heads
FS_FLOAT = 19     # overlays pinned to the pet (bubble / input / menu)
FS_XL = 20        # panel & dialog titles
FS_2XL = 24       # primary headings
FS_HERO = 34      # empty-state glyphs

# ── Radii — 9 values collapsed into 3 ────────────────────────────────────
R_SM = 4          # inputs, badges, small buttons
R_MD = 8          # cards
R_LG = 12         # dialogs, floating overlays

# ── Spacing, 4px base ────────────────────────────────────────────────────
SP_1, SP_2, SP_3, SP_4, SP_5, SP_6 = 4, 8, 12, 16, 20, 24


# ── Consumer-facing names ────────────────────────────────────────────────
# What the UI modules actually reference (~165 call sites). The FLOAT_*/DLG_*
# names are kept from the light/dark era on purpose: unifying the palette
# changed only their values, so no call site had to be touched.
FLOAT_PANEL = PANEL
FLOAT_TEXT = TEXT
FLOAT_TEXT_DIM = TEXT_DIM
FLOAT_ACCENT = ACCENT
FLOAT_ACCENT_SOFT = ACCENT_SOFT
FLOAT_ACCENT_BRIGHT = ACCENT_BRIGHT
FLOAT_GRID = GRID
FLOAT_FIELD = FIELD
FLOAT_SOLID = PANEL_SOLID
FLOAT_SELECT_BG = "rgba(167, 139, 250, 38)"
FLOAT_SELECT_TEXT = TEXT
DLG_BG = BG
DLG_FIELD = FIELD
DLG_FIELD_FOCUS = FIELD_DARK
DLG_TINT = "rgba(167, 139, 250, 20)"
DLG_HOVER = "rgba(167, 139, 250, 30)"
DLG_PRESSED = "rgba(167, 139, 250, 48)"

# Deprecated alias: FLOAT_GOLD predates the violet palette, where "gold" is a
# misleading name for what is really the bright-accent role. Kept pointing at
# the new value so nothing breaks; prefer FLOAT_ACCENT_BRIGHT in new code.
GOLD = ACCENT_BRIGHT
FLOAT_GOLD = FLOAT_ACCENT_BRIGHT


# Both sheets below are formatted at import time, so a placeholder that does
# not resolve takes the whole app down rather than degrading one widget. They
# use %(name)s rather than positional %s precisely so the substitutions cannot
# silently shift when a rule is added — QSS braces are untouched by % mapping.
MENU_QSS = """
QMenu {
    background: %(solid)s;
    color: %(text)s;
    border: 1px solid %(grid)s;
    border-radius: %(r_md)dpx;
    padding: %(sp_2)dpx;
    font-family: %(font)s;
    font-size: %(fs_float)dpx;
}
QMenu::item {
    padding: 10px 32px 10px 20px;
    border-radius: %(r_sm)dpx;
}
QMenu::item:selected {
    background: %(select_bg)s;
    color: %(select_text)s;
}
QMenu::item:disabled {
    color: %(mute)s;
}
QMenu::separator {
    height: 1px;
    background: %(grid)s;
    margin: %(sp_1)dpx %(sp_1)dpx;
}
""" % {
    "solid": FLOAT_SOLID, "text": FLOAT_TEXT, "grid": FLOAT_GRID,
    "font": FONT, "fs_float": FS_FLOAT, "r_md": R_MD, "r_sm": R_SM,
    "sp_1": SP_1, "sp_2": SP_2,
    "select_bg": FLOAT_SELECT_BG, "select_text": FLOAT_SELECT_TEXT,
    "mute": TEXT_MUTE,
}


DIALOG_QSS = """
QDialog {
    background: %(bg)s;
    color: %(text)s;
    font-family: %(font)s;
    font-size: %(fs_md)dpx;
}
QLabel {
    color: %(text)s;
}
QLabel#TerminalTitle {
    color: %(text)s;
    font-family: %(mono)s;
    font-size: %(fs_xl)dpx;
    font-weight: 700;
    padding: 0 0 2px 0;
}
QLabel#TerminalSubTitle {
    color: %(dim)s;
    font-family: %(mono)s;
    font-size: %(fs_sm)dpx;
    padding: 0 0 %(sp_2)dpx 0;
}
QLabel#TerminalNote {
    color: %(dim)s;
    background: %(tint)s;
    border-left: 3px solid %(accent)s;
    border-radius: %(r_sm)dpx;
    padding: 7px 9px;
}
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
    background: %(field)s;
    color: %(text)s;
    border: 1px solid %(grid)s;
    border-radius: %(r_sm)dpx;
    padding: 6px %(sp_2)dpx;
    selection-background-color: %(accent_deep)s;
    selection-color: #FFFFFF;
    font-family: %(mono)s;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {
    border: 1px solid %(accent)s;
    background: %(field_focus)s;
}
QComboBox::drop-down {
    width: 24px;
    border-left: 1px solid %(grid)s;
}
QCheckBox {
    color: %(text)s;
    spacing: %(sp_2)dpx;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid %(border_strong)s;
    border-radius: 3px;   /* 15px box: R_SM would look almost circular */
    background: %(field)s;
}
QCheckBox::indicator:checked {
    background: %(accent)s;
    border: 1px solid %(accent)s;
}
QPushButton {
    background: %(field)s;
    color: %(text)s;
    border: 1px solid %(grid)s;
    border-radius: %(r_sm)dpx;
    padding: 6px %(sp_4)dpx;
    min-width: 62px;
}
QPushButton:hover {
    background: %(hover)s;
    border-color: %(accent)s;
}
QPushButton:pressed {
    background: %(pressed)s;
}
QPushButton:disabled {
    color: %(mute)s;
    border-color: %(grid)s;
}
QPushButton#PrimaryBtn {
    background: %(accent)s;
    color: %(on_accent)s;
    border: 1px solid %(accent)s;
    font-weight: 700;
}
QPushButton#PrimaryBtn:hover {
    background: %(accent_bright)s;
    border-color: %(accent_bright)s;
}
QPushButton#PrimaryBtn:pressed {
    background: %(accent_deep)s;
    color: #FFFFFF;
}
""" % {
    "bg": DLG_BG, "text": FLOAT_TEXT, "dim": FLOAT_TEXT_DIM,
    "mute": TEXT_MUTE, "font": FONT, "mono": MONO,
    "fs_sm": FS_SM, "fs_md": FS_MD, "fs_xl": FS_XL,
    "r_sm": R_SM, "sp_2": SP_2, "sp_4": SP_4,
    "field": DLG_FIELD, "field_focus": DLG_FIELD_FOCUS, "grid": FLOAT_GRID,
    "tint": DLG_TINT, "hover": DLG_HOVER, "pressed": DLG_PRESSED,
    "accent": ACCENT, "accent_bright": ACCENT_BRIGHT,
    "accent_deep": ACCENT_DEEP, "on_accent": ON_ACCENT,
    "border_strong": BORDER_STRONG,
}
