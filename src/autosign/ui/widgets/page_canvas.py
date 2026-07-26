"""Canvas that displays a rendered PDF page and lets the user draw/drag/resize
signature boxes with the mouse - the familiar "draw a rectangle" experience
from Acrobat. Can also run in read-only mode (see set_interactive), where it
instead behaves like a plain viewer page: click-drag pans (hand tool, like
Foxit Reader) and emits pan_requested for the surrounding scroll area to apply.

Coordinates used by this widget are preview-image PIXELS, not PDF points -
converting to PDF points (bottom-left origin) is the caller's job (the
template designer), since that requires knowing the render DPI and page size.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

_HANDLE_SIZE = 10
_MIN_BOX_SIZE = 10
_DEFAULT_BACKDROP = QColor(60, 60, 60)


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

    def set_backdrop_color(self, color: QColor) -> None:
        """The neutral area behind the rendered page - themed to match the
        app's light/dark skin so it doesn't stand out as a leftover default."""
        self._backdrop = color
        self.update()

    def set_interactive(self, interactive: bool) -> None:
        """When False, the canvas is a read-only viewer page: no box
        drawing/dragging - instead the mouse pans the page (hand tool)."""
        self._interactive = interactive
        if not interactive:
            self._selected_id = None
            self._mode = "idle"
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
            if self._mode == "pan":
                global_pos = event.globalPosition()
                delta = global_pos - self._pan_last_global
                self._pan_last_global = global_pos
                self.pan_requested.emit(delta.x(), delta.y())
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
