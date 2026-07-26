"""Two-tier ribbon in the light/dark Foxit-Reader-like skin: a text-tab strip
(Home, Settings) - active tab in the accent color with an underline - on top
of an icon strip. Each icon button has a small caption underneath, and
groups of related buttons are separated by a thin vertical divider.

Colors themselves come entirely from the app-wide stylesheet in theme.py
(applied once, at the QApplication level in main.py) - this widget only sets
objectNames for that stylesheet to target. The one thing that *can't* be
themed via QSS is the hand-drawn icon pixmaps (ribbon_icons.py bakes a
stroke color into the pixmap), so set_theme() regenerates those explicitly
when the user switches theme.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import ribbon_icons as icons
from .. import theme

_TAB_BAR_HEIGHT = 28
_STRIP_HEIGHT = 74
_SMALL_ICON = QSize(20, 20)
_ICON_SIZE = QSize(26, 26)
_BIG_ICON_SIZE = QSize(32, 32)

IconFactory = Callable[..., QIcon]


class RibbonBar(QWidget):
    home_activated = Signal()
    settings_activated = Signal()

    open_files_requested = Signal()
    open_folder_requested = Signal()
    prev_page_requested = Signal()
    next_page_requested = Signal()
    zoom_in_requested = Signal()
    zoom_out_requested = Signal()
    fit_width_requested = Signal()
    fit_page_requested = Signal()
    reset_zoom_requested = Signal()
    toggle_panel_requested = Signal()
    sign_requested = Signal()
    export_report_requested = Signal()
    wheel_page_turn_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None, theme_mode: str = theme.THEME_LIGHT):
        super().__init__(parent)
        self._icon_color = theme.palette_for(theme_mode).text
        self._icon_buttons: list[tuple[QToolButton, IconFactory, QSize]] = []
        self.setFixedHeight(_TAB_BAR_HEIGHT + _STRIP_HEIGHT)
        self._build_ui()

    def set_theme(self, mode: str) -> None:
        """Regenerate every hand-drawn icon in the new theme's text color -
        call after applying the new app-wide stylesheet."""
        self._icon_color = theme.palette_for(mode).text
        for btn, factory, size in self._icon_buttons:
            btn.setIcon(factory(size.width(), self._icon_color))

    # ------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        tab_bar = QWidget()
        tab_bar.setObjectName("ribbonTabBar")
        tab_bar.setFixedHeight(_TAB_BAR_HEIGHT)
        tab_row = QHBoxLayout(tab_bar)
        tab_row.setContentsMargins(6, 0, 6, 0)
        tab_row.setSpacing(0)
        self._home_tab_btn = self._tab_button("Home")
        self._settings_tab_btn = self._tab_button("Settings")
        self._home_tab_btn.setChecked(True)
        self._home_tab_btn.clicked.connect(lambda: self.setCurrentIndex(0))
        self._settings_tab_btn.clicked.connect(lambda: self.setCurrentIndex(1))
        tab_row.addWidget(self._home_tab_btn)
        tab_row.addWidget(self._settings_tab_btn)
        tab_row.addStretch(1)

        self._content_stack = QStackedWidget()
        self._content_stack.setObjectName("ribbonContent")
        self._content_stack.setFixedHeight(_STRIP_HEIGHT)
        self._content_stack.addWidget(self._build_home_strip())
        self._content_stack.addWidget(self._build_settings_strip())

        root.addWidget(tab_bar)
        root.addWidget(self._content_stack)

    @staticmethod
    def _tab_button(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("ribbonTabButton")
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFlat(True)
        return btn

    # -------------------------------------------------------------- tabs
    def setCurrentIndex(self, index: int) -> None:
        (self._home_tab_btn if index == 0 else self._settings_tab_btn).setChecked(True)
        self._content_stack.setCurrentIndex(index)
        (self.home_activated if index == 0 else self.settings_activated).emit()

    def currentIndex(self) -> int:
        return self._content_stack.currentIndex()

    def select_home_tab(self) -> None:
        self.setCurrentIndex(0)

    # ------------------------------------------------------------------- Home
    def _build_home_strip(self) -> QWidget:
        strip = QWidget()
        row = QHBoxLayout(strip)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(2)

        row.addWidget(
            self._group(
                self._icon_button("Open Files", icons.open_files_icon, self.open_files_requested),
                self._icon_button("Open Folder", icons.open_folder_icon, self.open_folder_requested),
            )
        )
        row.addWidget(self._divider())
        row.addWidget(self._build_navigate_cluster())
        self._wheel_page_turn_btn = self._toggle_icon_button(
            "Wheel Turn",
            "Wheel Page Turn: scrolling past the top/bottom edge of a page "
            "moves to the previous/next page. Off by default (wheel only "
            "scrolls within the current page).",
            icons.wheel_page_turn_icon,
            self.wheel_page_turn_toggled,
        )
        row.addWidget(self._group(self._wheel_page_turn_btn))
        row.addWidget(self._divider())
        row.addWidget(self._build_zoom_cluster())
        row.addWidget(self._divider())
        self._sign_btn = self._icon_button("Sign", icons.sign_icon, self.sign_requested, big=True)
        row.addWidget(
            self._group(
                self._sign_btn,
                self._icon_button("Export Report", icons.export_icon, self.export_report_requested),
            )
        )
        row.addWidget(self._divider())
        self._toggle_panel_btn = self._icon_button("Hide Panel", icons.panel_icon, self.toggle_panel_requested)
        row.addWidget(self._group(self._toggle_panel_btn))

        row.addStretch(1)
        return strip

    def _build_navigate_cluster(self) -> QWidget:
        self._prev_btn = self._icon_button("Previous", icons.prev_icon, self.prev_page_requested)
        self._next_btn = self._icon_button("Next", icons.next_icon, self.next_page_requested)
        self._page_label = QLabel("No file")
        self._page_label.setObjectName("ribbonStatusLabel")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._signed_badge = QLabel("")
        self._signed_badge.setObjectName("ribbonSignedBadge")
        self._signed_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        status_col = QVBoxLayout()
        status_col.setSpacing(0)
        status_col.addStretch(1)
        status_col.addWidget(self._page_label)
        status_col.addWidget(self._signed_badge)
        status_col.addStretch(1)

        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._prev_btn)
        layout.addLayout(status_col)
        layout.addWidget(self._next_btn)
        return wrap

    def _build_zoom_cluster(self) -> QWidget:
        zoom_out_btn = self._icon_button("", icons.zoom_out_icon, self.zoom_out_requested, small=True)
        zoom_in_btn = self._icon_button("", icons.zoom_in_icon, self.zoom_in_requested, small=True)
        self._zoom_label = QLabel("100%")
        self._zoom_label.setObjectName("ribbonZoomLabel")
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        stepper = QHBoxLayout()
        stepper.setContentsMargins(0, 0, 0, 0)
        stepper.setSpacing(0)
        stepper.addWidget(zoom_out_btn)
        stepper.addWidget(self._zoom_label)
        stepper.addWidget(zoom_in_btn)
        stepper_wrap = QWidget()
        stepper_wrap.setLayout(stepper)

        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        row.addWidget(stepper_wrap)
        row.addWidget(self._icon_button("Fit Width", icons.fit_width_icon, self.fit_width_requested))
        row.addWidget(self._icon_button("Fit Page", icons.fit_page_icon, self.fit_page_requested))
        row.addWidget(self._icon_button("100%", icons.reset_zoom_icon, self.reset_zoom_requested))
        return wrap

    # --------------------------------------------------------------- Settings
    def _build_settings_strip(self) -> QWidget:
        strip = QWidget()
        row = QHBoxLayout(strip)
        row.setContentsMargins(8, 4, 8, 4)
        hint = QLabel("Configure the signing certificate, signer name, output folder, and templates below.")
        hint.setObjectName("ribbonStatusLabel")
        hint.setWordWrap(True)
        row.addWidget(hint, 1)
        return strip

    # ------------------------------------------------------------------ state
    def set_page_label(self, text: str) -> None:
        self._page_label.setText(text)

    def set_page_signed(self, signed: bool | None) -> None:
        """None = no file loaded / unknown, otherwise show or clear the badge."""
        self._signed_badge.setText("Signed" if signed else "")

    def set_nav_enabled(self, has_prev: bool, has_next: bool) -> None:
        self._prev_btn.setEnabled(has_prev)
        self._next_btn.setEnabled(has_next)

    def set_zoom_label(self, text: str) -> None:
        self._zoom_label.setText(text)

    def set_sign_enabled(self, enabled: bool) -> None:
        self._sign_btn.setEnabled(enabled)

    def set_panel_toggle_text(self, text: str) -> None:
        self._toggle_panel_btn.setText(text.replace(">>", "").replace("<<", "").strip())

    def set_wheel_page_turn_enabled(self, enabled: bool) -> None:
        """Restore a saved preference - does not emit wheel_page_turn_toggled
        (mirrors the other set_*() restore methods across the app)."""
        self._wheel_page_turn_btn.blockSignals(True)
        self._wheel_page_turn_btn.setChecked(enabled)
        self._wheel_page_turn_btn.blockSignals(False)

    # ----------------------------------------------------------------- helpers
    def _icon_button(
        self, caption: str, icon_factory: IconFactory, signal: Signal, big: bool = False, small: bool = False
    ) -> QToolButton:
        size = _BIG_ICON_SIZE if big else (_SMALL_ICON if small else _ICON_SIZE)
        btn = QToolButton()
        btn.setIcon(icon_factory(size.width(), self._icon_color))
        btn.setIconSize(size)
        btn.setAutoRaise(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if caption:
            btn.setText(caption)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setFixedWidth(78 if big else 62)
        else:
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            btn.setFixedWidth(_SMALL_ICON.width() + 10)
        btn.clicked.connect(signal.emit)
        self._icon_buttons.append((btn, icon_factory, size))
        return btn

    def _toggle_icon_button(
        self, caption: str, tooltip: str, icon_factory: IconFactory, signal: Signal
    ) -> QToolButton:
        size = _ICON_SIZE
        btn = QToolButton()
        btn.setIcon(icon_factory(size.width(), self._icon_color))
        btn.setIconSize(size)
        btn.setAutoRaise(True)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setText(caption)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn.setFixedWidth(62)
        btn.toggled.connect(signal.emit)
        self._icon_buttons.append((btn, icon_factory, size))
        return btn

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setObjectName("ribbonDivider")
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        return line

    @staticmethod
    def _group(*widgets: QWidget) -> QWidget:
        box = QWidget()
        box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(box)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(2)
        for widget in widgets:
            layout.addWidget(widget)
        return box
