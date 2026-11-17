"""Shared Qt theme for the desktop workspace and pet overlays.

The schedule, side panel, context menu, floating chat and action dialogs use
the same light surfaces, readable type and indigo-violet accent. Keep opaque
palette values usable in QSS and QPainter; PANEL is translucent for overlays.
"""

# ── Shared Apple-inspired light palette ──────────────────────────────────
from . import desktop_theme as apple

BG = apple.BG
PANEL_SOLID = apple.SURFACE
PANEL = "rgba(255, 255, 255, 246)"
FIELD = apple.FIELD
FIELD_DARK = apple.HOVER

GRID = apple.BORDER
BORDER_STRONG = apple.BORDER_STRONG

ACCENT = apple.ACCENT
ACCENT_BRIGHT = apple.ACCENT_HOVER
ACCENT_DEEP = apple.ACCENT_DEEP
ACCENT_SOFT = "#D8D7FF"
ON_ACCENT = apple.ON_ACCENT

TEXT = apple.TEXT
TEXT_DIM = apple.SECONDARY
TEXT_MUTE = apple.MUTED

GREEN = apple.GREEN
AMBER = apple.AMBER
RED = apple.RED

FONT = apple.FONT
MONO = "'Cascadia Mono', 'Consolas', 'Microsoft YaHei UI'"

FS_XS = 12
FS_SM = 14
FS_MD = 16
FS_LG = 18
FS_FLOAT = 17
FS_XL = 22
FS_2XL = 26
FS_HERO = 36

R_SM = 6
R_MD = 10
R_LG = 14

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
FLOAT_SELECT_BG = "rgba(94, 92, 230, 24)"
FLOAT_SELECT_TEXT = TEXT
DLG_BG = BG
DLG_FIELD = FIELD
DLG_FIELD_FOCUS = FIELD_DARK
DLG_TINT = "rgba(94, 92, 230, 14)"
DLG_HOVER = "rgba(94, 92, 230, 22)"
DLG_PRESSED = "rgba(94, 92, 230, 34)"

# Deprecated alias retained for older call sites. Prefer the neutral accent
# names in new code.
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
    font-family: %(font)s;
    font-size: %(fs_xl)dpx;
    font-weight: 700;
    padding: 0 0 2px 0;
}
QLabel#TerminalSubTitle {
    color: %(dim)s;
    font-family: %(font)s;
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
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox,
QDateEdit, QTimeEdit, QDateTimeEdit {
    background: %(field)s;
    color: %(text)s;
    border: 1px solid %(grid)s;
    border-radius: %(r_sm)dpx;
    padding: 6px %(sp_2)dpx;
    selection-background-color: %(accent_deep)s;
    selection-color: #FFFFFF;
    font-family: %(font)s;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus,
QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus {
    border: 1px solid %(accent)s;
    background: %(field_focus)s;
}
QComboBox::drop-down {
    width: 24px;
    border-left: 1px solid %(grid)s;
}
QComboBox QAbstractItemView {
    background: %(field)s;
    color: %(text)s;
    border: 1px solid %(border_strong)s;
    selection-background-color: %(tint)s;
    selection-color: %(text)s;
    padding: 4px;
}
QTextEdit, QPlainTextEdit, QTextBrowser, QListWidget, QTableWidget {
    background: %(field)s;
    color: %(text)s;
    border: 1px solid %(grid)s;
    border-radius: %(r_sm)dpx;
    selection-background-color: %(accent_deep)s;
    selection-color: #FFFFFF;
}
QHeaderView::section {
    background: %(field)s;
    color: %(dim)s;
    border: none;
    border-bottom: 1px solid %(grid)s;
    padding: 6px 8px;
}
QGroupBox {
    border: 1px solid %(grid)s;
    border-radius: %(r_md)dpx;
    margin-top: %(sp_3)dpx;
    padding: %(sp_3)dpx;
    color: %(text)s;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: %(sp_2)dpx;
    padding: 0 4px;
    background: %(bg)s;
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
QRadioButton {
    color: %(text)s;
    spacing: %(sp_2)dpx;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid %(border_strong)s;
    border-radius: 8px;
    background: %(field)s;
}
QRadioButton::indicator:checked {
    border: 5px solid %(accent)s;
    background: %(field)s;
}
QScrollBar:vertical {
    background: transparent;
    width: 9px;
    margin: 3px 2px;
}
QScrollBar::handle:vertical {
    background: %(border_strong)s;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: %(accent_bright)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
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
QToolTip {
    background: %(text)s;
    color: %(bg)s;
    border: none;
    padding: 5px 7px;
}
""" % {
    "bg": DLG_BG, "text": FLOAT_TEXT, "dim": FLOAT_TEXT_DIM,
    "mute": TEXT_MUTE, "font": FONT,
    "fs_sm": FS_SM, "fs_md": FS_MD, "fs_xl": FS_XL,
    "r_sm": R_SM, "r_md": R_MD, "sp_2": SP_2, "sp_3": SP_3, "sp_4": SP_4,
    "field": DLG_FIELD, "field_focus": DLG_FIELD_FOCUS, "grid": FLOAT_GRID,
    "tint": DLG_TINT, "hover": DLG_HOVER, "pressed": DLG_PRESSED,
    "accent": ACCENT, "accent_bright": ACCENT_BRIGHT,
    "accent_deep": ACCENT_DEEP, "on_accent": ON_ACCENT,
    "border_strong": BORDER_STRONG,
}
