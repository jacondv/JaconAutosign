"""Canvas that displays a rendered PDF page and lets the user draw/drag/resize
signature boxes with the mouse - the familiar "draw a rectangle" experience
from Acrobat. Can also run in read-only mode (see set_interactive), where it
instead behaves like a plain viewer page: click-drag pans (hand tool, like
Foxit Reader) and emits pan_requested for the surrounding scroll area to apply.

The read-only mode also supports hover-to-select text (see set_text_source):
holding the mouse still over text switches the cursor to an I-beam and
enables drag-to-select, like Foxit/Acrobat's "hand tool that turns into
select on hover" behavior - moving the mouse again without the button held
drops straight back to the hand cursor.

Coordinates used by this widget are preview-image PIXELS, not PDF points -
converting to PDF points (bottom-left origin) is the caller's job for
signature boxes (the template designer); text-selection coordinates are
converted internally since that interaction lives entirely in this widget.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QImage,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from ...models import PageSize, Rect
from ..coordinates import pdf_rect_to_pixel
from ..pdf_text import PageTextSource

_HANDLE_SIZE = 10
_MIN_BOX_SIZE = 10
_DEFAULT_BACKDROP = QColor(60, 60, 60)
_HOVER_DELAY_MS = 1000
_HOVER_TOLERANCE_PT = 3.0
_DRAG_TOLERANCE_PT = 6.0
_SELECTION_COLOR = QColor(60, 120, 255, 90)


class PageCanvas(QWidget):
    box_created = Signal(QRectF)
    box_changed = Signal(str, QRectF)
    box_selected = Signal(str)
    pan_requested = Signal(float, float)  # (dx, dy) mouse movement, screen pixels

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._pixmap: QPixmap | None = None
        self._boxes: dict[str, QRectF] = {}
        self._labels: dict[str, str] = {}
        self._selected_id: str | None = None
        self._interactive = True
        self._backdrop = _DEFAULT_BACKDROP
        self._mode: str = "idle"  # idle | draw | move | resize | pan
        self._drag_anchor: QPointF = QPointF()
        self._drag_orig_rect: QRectF = QRectF()
        self._draw_rect: QRectF | None = None
        self._pan_last_global: QPointF = QPointF()

        # ---- read-only mode: hover-to-select text ----
        self._text_source: PageTextSource | None = None
        self._page_size: PageSize | None = None
        self._dpi: float = 0.0
        self._cursor_mode: str = "pan"  # "pan" | "select"
        self._selecting = False
        self._text_selection: tuple[int, int] | None = None  # (anchor_char, end_char)
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._on_hover_timeout)
        self._hover_pos: QPointF | None = None

    def set_backdrop_color(self, color: QColor) -> None:
        """The neutral area behind the rendered page - themed to match the
        app's light/dark skin so it doesn't stand out as a leftover default."""
        self._backdrop = color
        self.update()

    def set_interactive(self, interactive: bool) -> None:
        """When False, the canvas is a read-only viewer page: no box
        drawing/dragging - instead the mouse pans the page (hand tool) or,
        while hovering text, selects it (see set_text_source)."""
        self._interactive = interactive
        if not interactive:
            self._selected_id = None
            self._mode = "idle"
            self._cursor_mode = "pan"
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()

    def set_page_image(self, image: QImage) -> None:
        self._pixmap = QPixmap.fromImage(image)
        # QPixmap.size() is the *physical* pixel size (device_pixel_ratio
        # already multiplied in, for HiDPI sharpness - see pdf_render.py);
        # the widget itself must be sized in logical/device-independent
        # pixels, or the canvas ends up bigger than the page actually
        # paints at, leaving a gray backdrop margin around it.
        self.setFixedSize(self._pixmap.deviceIndependentSize().toSize())
        self.update()

    def set_boxes(self, boxes: dict[str, QRectF], labels: dict[str, str] | None = None) -> None:
        self._boxes = dict(boxes)
        self._labels = dict(labels) if labels else {}
        if self._selected_id not in self._boxes:
            self._selected_id = None
        self.update()

    def select_box(self, box_id: str | None) -> None:
        self._selected_id = box_id
        self.update()

    # ------------------------------------------------------- text selection
    def set_text_source(self, pdf_path: str | None, page_index: int, page_size: PageSize, dpi: float) -> None:
        """Point hover-to-select at a new page - closes the previous page's
        text layer (if any) and clears any active selection."""
        self.close_text_source()
        self._text_source = PageTextSource(pdf_path, page_index) if pdf_path else None
        self._page_size = page_size
        self._dpi = dpi
        self._text_selection = None
        self._cursor_mode = "pan"
        if not self._interactive:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    def close_text_source(self) -> None:
        if self._text_source is not None:
            self._text_source.close()
            self._text_source = None
        self._text_selection = None

    def _pdf_point_at(self, pos: QPointF) -> tuple[float, float] | None:
        if self._page_size is None or self._dpi <= 0:
            return None
        scale = self._dpi / 72.0
        return pos.x() / scale, self._page_size.height - pos.y() / scale

    def _char_index_at(self, pos: QPointF, tol: float) -> int | None:
        if self._text_source is None:
            return None
        point = self._pdf_point_at(pos)
        if point is None:
            return None
        return self._text_source.char_index_at(*point, tol=tol)

    def _on_hover_timeout(self) -> None:
        if self._interactive or self._selecting or self._hover_pos is None:
            return
        if self._char_index_at(self._hover_pos, _HOVER_TOLERANCE_PT) is not None:
            self._cursor_mode = "select"
            self.setCursor(QCursor(Qt.CursorShape.IBeamCursor))

    def _copy_selection(self) -> None:
        if self._text_selection is None or self._text_source is None:
            return
        text = self._text_source.text_range(*self._text_selection)
        if text:
            QApplication.clipboard().setText(text)

    def contextMenuEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._interactive or self._text_selection is None:
            return
        menu = QMenu(self)
        copy_action = menu.addAction("Copy")
        if menu.exec(event.globalPos()) == copy_action:
            self._copy_selection()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if not self._interactive and self._text_selection is not None and event.matches(QKeySequence.StandardKey.Copy):
            self._copy_selection()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ paint
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._backdrop)
        if self._pixmap is not None:
            painter.drawPixmap(0, 0, self._pixmap)

        for box_id, rect in self._boxes.items():
            selected = self._interactive and box_id == self._selected_id
            self._paint_box(painter, rect, selected, self._labels.get(box_id, ""))

        if self._mode == "draw" and self._draw_rect is not None:
            pen = QPen(QColor(40, 170, 60), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(40, 170, 60, 40))
            painter.drawRect(self._draw_rect)

        self._paint_text_selection(painter)

    def _paint_text_selection(self, painter: QPainter) -> None:
        if self._interactive or self._text_selection is None:
            return
        if self._text_source is None or self._page_size is None:
            return
        rects = self._text_source.selection_rects(*self._text_selection)
        if not rects:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_SELECTION_COLOR)
        for left, bottom, right, top in rects:
            pdf_rect = Rect(x=left, y=bottom, width=right - left, height=top - bottom)
            painter.drawRect(pdf_rect_to_pixel(pdf_rect, self._page_size, self._dpi))

    def _paint_box(self, painter: QPainter, rect: QRectF, selected: bool, label: str) -> None:
        color = QColor(220, 40, 40) if selected else QColor(30, 120, 220)
        painter.setPen(QPen(color, 2))
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 45))
        painter.drawRect(rect)
        if label:
            painter.setPen(QPen(color, 1))
            painter.drawText(rect.adjusted(4, -18, 0, 0).topLeft(), label)
        if selected:
            handle = self._handle_rect(rect)
            painter.setBrush(color)
            painter.drawRect(handle)

    def _handle_rect(self, rect: QRectF) -> QRectF:
        return QRectF(
            rect.right() - _HANDLE_SIZE / 2,
            rect.bottom() - _HANDLE_SIZE / 2,
            _HANDLE_SIZE,
            _HANDLE_SIZE,
        )

    # -------------------------------------------------------------- mouse
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if not self._interactive:
            self._hover_timer.stop()
            if self._cursor_mode == "select":
                index = self._char_index_at(event.position(), _HOVER_TOLERANCE_PT)
                self._selecting = index is not None
                self._text_selection = (index, index) if index is not None else None
                self.update()
                return
            self._mode = "pan"
            self._pan_last_global = event.globalPosition()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return

        pos = event.position()
        if self._selected_id is not None:
            handle = self._handle_rect(self._boxes[self._selected_id])
            if handle.contains(pos):
                self._mode = "resize"
                self._drag_anchor = pos
                self._drag_orig_rect = QRectF(self._boxes[self._selected_id])
                return

        hit_id = self._box_at(pos)
        if hit_id is not None:
            self._selected_id = hit_id
            self.box_selected.emit(hit_id)
            self._mode = "move"
            self._drag_anchor = pos
            self._drag_orig_rect = QRectF(self._boxes[hit_id])
            self.update()
            return

        self._selected_id = None
        self.box_selected.emit("")
        self._mode = "draw"
        self._drag_anchor = pos
        self._draw_rect = QRectF(pos, pos)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._interactive:
            pos = event.position()
            if self._mode == "pan":
                global_pos = event.globalPosition()
                delta = global_pos - self._pan_last_global
                self._pan_last_global = global_pos
                self.pan_requested.emit(delta.x(), delta.y())
                return
            if self._selecting:
                index = self._char_index_at(pos, _DRAG_TOLERANCE_PT)
                if index is not None and self._text_selection is not None:
                    self._text_selection = (self._text_selection[0], index)
                    self.update()
                return
            # Hovering with no button held: any movement drops back to the
            # hand cursor immediately - only holding still near text (see
            # _on_hover_timeout) re-arms select mode.
            self._hover_pos = pos
            if self._cursor_mode == "select":
                self._cursor_mode = "pan"
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            self._hover_timer.start(_HOVER_DELAY_MS)
            return

        pos = event.position()
        if self._mode == "draw":
            self._draw_rect = QRectF(self._drag_anchor, pos).normalized()
            self.update()
        elif self._mode == "move" and self._selected_id is not None:
            delta = pos - self._drag_anchor
            new_rect = QRectF(self._drag_orig_rect)
            new_rect.translate(delta)
            self._boxes[self._selected_id] = self._clamp_to_canvas(new_rect)
            self.update()
        elif self._mode == "resize" and self._selected_id is not None:
            delta = pos - self._drag_anchor
            new_rect = QRectF(self._drag_orig_rect)
            new_rect.setWidth(max(_MIN_BOX_SIZE, self._drag_orig_rect.width() + delta.x()))
            new_rect.setHeight(max(_MIN_BOX_SIZE, self._drag_orig_rect.height() + delta.y()))
            self._boxes[self._selected_id] = self._clamp_to_canvas(new_rect)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._interactive:
            if self._mode == "pan":
                self._mode = "idle"
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
                return
            if self._selecting:
                self._selecting = False
                if self._text_selection is not None and self._text_selection[0] == self._text_selection[1]:
                    # A plain click, not a drag - no meaningful selection.
                    self._text_selection = None
                    self.update()
                return
            return

        if self._mode == "draw" and self._draw_rect is not None:
            rect = self._draw_rect.normalized()
            self._draw_rect = None
            self._mode = "idle"
            if rect.width() >= _MIN_BOX_SIZE and rect.height() >= _MIN_BOX_SIZE:
                self.box_created.emit(self._clamp_to_canvas(rect))
            self.update()
            return

        if self._mode in ("move", "resize") and self._selected_id is not None:
            self.box_changed.emit(self._selected_id, self._boxes[self._selected_id])

        self._mode = "idle"

    def _box_at(self, pos: QPointF) -> str | None:
        for box_id, rect in reversed(list(self._boxes.items())):
            if rect.contains(pos):
                return box_id
        return None

    def _clamp_to_canvas(self, rect: QRectF) -> QRectF:
        if self._pixmap is None:
            return rect
        # Mouse coordinates are in logical/device-independent pixels (like
        # the widget's own size) - bound against that, not the pixmap's
        # physical pixel size (see the comment in set_page_image).
        size = self._pixmap.deviceIndependentSize()
        bounds = QRectF(0, 0, size.width(), size.height())
        x = min(max(rect.x(), bounds.left()), bounds.right() - rect.width())
        y = min(max(rect.y(), bounds.top()), bounds.bottom() - rect.height())
        return QRectF(x, y, rect.width(), rect.height())
