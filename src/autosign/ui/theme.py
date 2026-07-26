"""Centralized theming: two complete palettes (light/dark), applied as a
single app-wide stylesheet via QApplication.setStyleSheet() in main.py.

Windows' native widget style pulls some colors (checkboxes, scrollbars,
combo-box popups...) straight from the OS theme even when a stylesheet is
layered on top of it, which is why colors used to "leak" the Windows theme
into the app. main.py forces QApplication.setStyle("Fusion") - a style Qt
renders itself, not the OS - so this stylesheet is the only source of color,
regardless of whether Windows is in light or dark mode.
"""
from __future__ import annotations

from dataclasses import dataclass

THEME_LIGHT = "light"
THEME_DARK = "dark"


@dataclass(frozen=True)
class Palette:
    accent: str
    accent_hover: str
    accent_text: str
    text: str
    text_muted: str
    border: str
    bg_window: str
    bg_panel: str
    bg_input: str
    bg_hover: str
    bg_pressed: str
    bg_disabled: str
    text_disabled: str
    canvas_backdrop: str  # the neutral area behind the rendered PDF page
    success: str


LIGHT = Palette(
    accent="#e07b1a",
    accent_hover="#c96c14",
    accent_text="#ffffff",
    text="#2b2b2b",
    text_muted="#6a6a6a",
    border="#d9d9d9",
    bg_window="#ffffff",
    bg_panel="#f7f7f7",
    bg_input="#ffffff",
    bg_hover="#eeeeee",
    bg_pressed="#e2e2e2",
    bg_disabled="#f0f0f0",
    text_disabled="#a8a8a8",
    canvas_backdrop="#c8c8c8",
    success="#1a7a1a",
)

DARK = Palette(
    accent="#e0821f",
    accent_hover="#f0954a",
    accent_text="#1c1c1c",
    text="#e6e6e6",
    text_muted="#a0a0a0",
    border="#4a4a4a",
    bg_window="#2b2b2b",
    bg_panel="#333333",
    bg_input="#3a3a3a",
    bg_hover="#454545",
    bg_pressed="#505050",
    bg_disabled="#333333",
    text_disabled="#787878",
    canvas_backdrop="#1e1e1e",
    success="#4fc24f",
)


def palette_for(mode: str) -> Palette:
    return DARK if mode == THEME_DARK else LIGHT


def stylesheet(mode: str) -> str:
    p = palette_for(mode)
    return f"""
QWidget {{
    background: {p.bg_window};
    color: {p.text};
    selection-background-color: {p.accent};
    selection-color: {p.accent_text};
}}
QMainWindow, QDialog {{
    background: {p.bg_window};
}}
QToolTip {{
    background: {p.bg_panel};
    color: {p.text};
    border: 1px solid {p.border};
    padding: 4px;
}}
QGroupBox {{
    background: {p.bg_panel};
    border: 1px solid {p.border};
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {p.text};
}}
QLineEdit, QComboBox, QListWidget, QKeySequenceEdit, QAbstractSpinBox {{
    background: {p.bg_input};
    border: 1px solid {p.border};
    border-radius: 3px;
    padding: 3px;
    color: {p.text};
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background: {p.bg_input};
    color: {p.text};
    selection-background-color: {p.accent};
    selection-color: {p.accent_text};
    border: 1px solid {p.border};
    outline: none;
}}
QListWidget::item:selected {{
    background: {p.accent};
    color: {p.accent_text};
}}
QPushButton {{
    background: {p.bg_input};
    border: 1px solid {p.border};
    border-radius: 3px;
    padding: 5px 12px;
    color: {p.text};
}}
QPushButton:hover {{
    background: {p.bg_hover};
}}
QPushButton:pressed {{
    background: {p.bg_pressed};
}}
QPushButton:disabled {{
    background: {p.bg_disabled};
    color: {p.text_disabled};
    border-color: {p.border};
}}
QPushButton#primaryButton {{
    background: {p.accent};
    border: 1px solid {p.accent};
    color: {p.accent_text};
    font-weight: 600;
}}
QPushButton#primaryButton:hover {{
    background: {p.accent_hover};
}}
QPushButton#primaryButton:disabled {{
    background: {p.bg_disabled};
    border-color: {p.border};
    color: {p.text_disabled};
}}
QLabel {{
    color: {p.text};
    background: transparent;
}}
QRadioButton, QCheckBox {{
    color: {p.text};
    spacing: 6px;
    background: transparent;
}}
QRadioButton::indicator, QCheckBox::indicator {{
    width: 13px;
    height: 13px;
    border: 1px solid {p.text_muted};
    background: {p.bg_input};
}}
QRadioButton::indicator {{
    border-radius: 7px;
}}
QCheckBox::indicator {{
    border-radius: 3px;
}}
QRadioButton::indicator:hover, QCheckBox::indicator:hover {{
    border: 1px solid {p.accent};
}}
QRadioButton::indicator:checked {{
    border: 1px solid {p.accent};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {p.accent}, stop:0.45 {p.accent}, stop:0.55 {p.bg_input}, stop:1 {p.bg_input});
}}
QCheckBox::indicator:checked {{
    border: 1px solid {p.accent};
    background: {p.accent};
}}
QProgressBar {{
    background: {p.bg_input};
    border: 1px solid {p.border};
    border-radius: 3px;
    text-align: center;
    color: {p.text};
}}
QProgressBar::chunk {{
    background: {p.accent};
    border-radius: 3px;
}}
QSplitter::handle {{
    background: {p.border};
}}
QScrollBar:vertical, QScrollBar:horizontal {{
    background: {p.bg_panel};
    border: none;
}}
QScrollBar::handle {{
    background: {p.border};
    border-radius: 3px;
}}
QScrollBar::handle:hover {{
    background: {p.text_muted};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0px;
    width: 0px;
}}

/* Ribbon */
#ribbonTabBar {{
    background: {p.bg_window};
    border-bottom: 1px solid {p.border};
}}
#ribbonTabButton {{
    background: transparent;
    color: {p.text};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 5px 16px 3px 16px;
    font-size: 9pt;
}}
#ribbonTabButton:hover {{
    color: {p.accent};
}}
#ribbonTabButton:checked {{
    color: {p.accent};
    border-bottom: 2px solid {p.accent};
    font-weight: 600;
}}
#ribbonContent {{
    background: {p.bg_panel};
    border-bottom: 1px solid {p.border};
}}
QFrame#ribbonDivider {{
    color: {p.border};
}}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    color: {p.text};
    font-size: 7.8pt;
    padding: 2px;
}}
QToolButton:hover {{
    background: {p.bg_hover};
    border: 1px solid {p.border};
}}
QToolButton:pressed {{
    background: {p.bg_pressed};
}}
QToolButton:checked {{
    background: {p.accent};
    border: 1px solid {p.accent};
    color: {p.accent_text};
}}
QToolButton:disabled {{
    color: {p.text_disabled};
}}
QLabel#ribbonStatusLabel {{
    color: {p.text};
    font-size: 8pt;
}}
QLabel#ribbonSignedBadge {{
    color: {p.success};
    font-weight: bold;
    font-size: 8pt;
}}
QLabel#ribbonZoomLabel {{
    color: {p.text};
    font-size: 8pt;
    min-width: 34px;
}}
"""
