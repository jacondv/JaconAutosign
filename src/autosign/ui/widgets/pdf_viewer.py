"""A Foxit-Reader-like PDF viewer widget: toolbar (page navigation, zoom
in/out, fit width, fit page) plus a scrollable page view that supports
click-drag panning (hand tool) and Ctrl+wheel zooming, just like Foxit.

The toolbar can be hidden (show_toolbar=False) when the app provides its own
ribbon for these actions - all the same operations remain available as
public methods (prev_page, next_page, zoom_in, ...) for the ribbon to call.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ...models import PageSize
from ..pdf_render import DEFAULT_PREVIEW_DPI, render_page_to_qimage
from .page_canvas import PageCanvas

ZOOM_MIN = 0.25
ZOOM_MAX = 4.0
ZOOM_STEP = 1.25
_VIEWPORT_MARGIN = 20  # px, leaves a little breathing room for Fit Width/Page


class PdfViewerWidget(QWidget):
    page_changed = Signal(int)  # 0-based page index
    zoom_changed = Signal(str)  # display text, e.g. "125%"

    def __init__(self, parent: QWidget | None = None, show_toolbar: bool = True):
        super().__init__(parent)
        self._pdf_path: str | None = None
        self._page_sizes: list[PageSize] = []
        self._current_page = 0
        self._zoom = 1.0

        self._canvas = PageCanvas()
        self._canvas.set_interactive(False)
        self._canvas.pan_requested.connect(self._on_pan)
        self._canvas.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._canvas)
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.viewport().installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # The toolbar's labels/buttons are always built (show_page/set_zoom
        # update them internally regardless), but the bar itself is only
        # added to the visible layout when the app doesn't supply its own
        # ribbon for these actions.
        toolbar_container = QWidget(self)
        toolbar_container.setLayout(self._build_toolbar())
        if show_toolbar:
            layout.addWidget(toolbar_container)
        else:
            toolbar_container.hide()
        layout.addWidget(self._scroll, 1)

        # Left/Right navigate pages, but only while the viewer (not some
        # other field like the template combo) has focus.
        prev_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        prev_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        prev_shortcut.activated.connect(self.prev_page)
        next_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        next_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        next_shortcut.activated.connect(self.next_page)

    def _build_toolbar(self) -> QHBoxLayout:
        self._prev_btn = QPushButton("<")
        self._prev_btn.setFixedWidth(32)
        self._prev_btn.clicked.connect(self.prev_page)
        self._next_btn = QPushButton(">")
        self._next_btn.setFixedWidth(32)
        self._next_btn.clicked.connect(self.next_page)
        self._page_label = QLabel("No file")

        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setFixedWidth(28)
        zoom_out_btn.clicked.connect(self.zoom_out)
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedWidth(28)
        zoom_in_btn.clicked.connect(self.zoom_in)
        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(46)
        fit_width_btn = QPushButton("Fit Width")
        fit_width_btn.clicked.connect(self.fit_width)
        fit_page_btn = QPushButton("Fit Page")
        fit_page_btn.clicked.connect(self.fit_page)
        reset_btn = QPushButton("100%")
        reset_btn.clicked.connect(lambda: self.set_zoom(1.0))

        row = QHBoxLayout()
        row.addWidget(self._prev_btn)
        row.addWidget(self._page_label)
        row.addWidget(self._next_btn)
        row.addSpacing(16)
        row.addWidget(zoom_out_btn)
        row.addWidget(self._zoom_label)
        row.addWidget(zoom_in_btn)
        row.addWidget(fit_width_btn)
        row.addWidget(fit_page_btn)
        row.addWidget(reset_btn)
        row.addStretch(1)
        return row

    # ------------------------------------------------------------ document
    def load(self, pdf_path: str, page_sizes: list[PageSize]) -> None:
        self._pdf_path = pdf_path
        self._page_sizes = page_sizes
        self._current_page = 0
        self.show_page(0)

    def clear(self) -> None:
        self._pdf_path = None
        self._page_sizes = []
        self._current_page = 0
        self._canvas.set_boxes({})
        self._page_label.setText("No file")
        self._prev_btn.setEnabled(False)
        self._next_btn.setEnabled(False)

    def current_page(self) -> int:
        return self._current_page

    def page_count(self) -> int:
        return len(self._page_sizes)

    def zoom_label(self) -> str:
        return f"{round(self._zoom * 100)}%"

    def dpi(self) -> float:
        """Effective render DPI at the current zoom - use this (not the
        DEFAULT_PREVIEW_DPI constant) when converting overlay box coordinates."""
        return DEFAULT_PREVIEW_DPI * self._zoom

    def set_boxes(self, boxes: dict, labels: dict | None = None) -> None:
        self._canvas.set_boxes(boxes, labels)

    def set_backdrop_color(self, color) -> None:
        self._canvas.set_backdrop_color(color)

    # ---------------------------------------------------------------- nav
    def show_page(self, index: int) -> None:
        if not self._pdf_path or not (0 <= index < len(self._page_sizes)):
            return
        self._current_page = index
        image = render_page_to_qimage(self._pdf_path, index, dpi=round(self.dpi()))
        self._canvas.set_page_image(image)
        self._page_label.setText(f"Page {index + 1}/{len(self._page_sizes)}")
        self._prev_btn.setEnabled(index > 0)
        self._next_btn.setEnabled(index < len(self._page_sizes) - 1)
        self.page_changed.emit(index)

    def prev_page(self) -> None:
        if self._current_page > 0:
            self.show_page(self._current_page - 1)

    def next_page(self) -> None:
        if self._current_page < len(self._page_sizes) - 1:
            self.show_page(self._current_page + 1)

    # --------------------------------------------------------------- zoom
    def set_zoom(self, zoom: float) -> None:
        zoom = max(ZOOM_MIN, min(ZOOM_MAX, zoom))
        if abs(zoom - self._zoom) < 1e-6:
            return
        self._zoom = zoom
        label = f"{round(zoom * 100)}%"
        self._zoom_label.setText(label)
        self.zoom_changed.emit(label)
        if self._pdf_path:
            self.show_page(self._current_page)

    def zoom_in(self) -> None:
        self.set_zoom(self._zoom * ZOOM_STEP)

    def zoom_out(self) -> None:
        self.set_zoom(self._zoom / ZOOM_STEP)

    def fit_width(self) -> None:
        if not self._page_sizes:
            return
        page_width_pt = self._page_sizes[self._current_page].width
        viewport_width = self._scroll.viewport().width() - _VIEWPORT_MARGIN
        width_px_at_100 = page_width_pt * DEFAULT_PREVIEW_DPI / 72
        if width_px_at_100 > 0:
            self.set_zoom(viewport_width / width_px_at_100)

    def fit_page(self) -> None:
        if not self._page_sizes:
            return
        size = self._page_sizes[self._current_page]
        viewport = self._scroll.viewport().size()
        width_px_at_100 = size.width * DEFAULT_PREVIEW_DPI / 72
        height_px_at_100 = size.height * DEFAULT_PREVIEW_DPI / 72
        if width_px_at_100 <= 0 or height_px_at_100 <= 0:
            return
        zoom_w = (viewport.width() - _VIEWPORT_MARGIN) / width_px_at_100
        zoom_h = (viewport.height() - _VIEWPORT_MARGIN) / height_px_at_100
        self.set_zoom(min(zoom_w, zoom_h))

    # ------------------------------------------------------------ pan/wheel
    def _on_pan(self, dx: float, dy: float) -> None:
        hbar = self._scroll.horizontalScrollBar()
        vbar = self._scroll.verticalScrollBar()
        hbar.setValue(int(hbar.value() - dx))
        vbar.setValue(int(vbar.value() - dy))

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt override)
        if obj is self._scroll.viewport() and event.type() == QEvent.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if event.angleDelta().y() > 0:
                    self.zoom_in()
                else:
                    self.zoom_out()
                return True
        return super().eventFilter(obj, event)
