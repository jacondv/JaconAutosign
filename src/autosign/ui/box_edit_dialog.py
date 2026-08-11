"""Dialog to configure one signature box: label, signature image, and -
directly in the live preview - independent position AND size for both the
image and the text info, decoupled from the classic image-left/text-right
split. Drag a box's body to move it, drag the little square at its
bottom-right corner to resize it - no need to go through the Sign screen
to see the effect. Which page(s) get signed is no longer decided here -
it's chosen at sign time in the left panel (Page scope), applying
uniformly to every box."""
from __future__ import annotations

from datetime import datetime

from PIL import Image, ImageDraw
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import Appearance, PageRef, PageRefType
from ..signing.appearance_compose import (
    _LEFT_RATIO,
    _PADDING,
    build_text_lines,
    fit_image,
    layout_text,
)

_PREVIEW_SIGNER_NAME = "Signer Name"
_PREVIEW_WIDTH = 280
_TEXT_COLOR = (20, 20, 20, 255)
_MIN_BOX_PX = 20
_HANDLE_SIZE = 10


def _pil_to_qpixmap(image: Image.Image) -> QPixmap:
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimage = QImage(data, rgba.width, rgba.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())  # copy: detach from the bytes buffer above


class _ResizeHandle(QLabel):
    """Small square at a draggable box's bottom-right corner - drag it to
    resize that box directly, live."""

    resized = Signal(int, int)  # new box width/height, in canvas pixels

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(_HANDLE_SIZE, _HANDLE_SIZE)
        self.setStyleSheet("background-color: #2f7de1; border: 1px solid white;")
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self._dragging = False

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if not self._dragging:
            return
        # event.pos() is relative to this handle; self.pos() is the handle's
        # own top-left within its parent box - summing gives the mouse
        # position relative to the box's top-left, i.e. the new box size
        # (the box's top-left is the resize anchor).
        pos_in_box = self.pos() + event.pos()
        self.resized.emit(pos_in_box.x(), pos_in_box.y())

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._dragging = False


class _DraggableBox(QLabel):
    """A box (sized to fit the pixmap set on it) that can be dragged
    anywhere within its parent widget - the box editor's preview canvas -
    and resized via its corner _ResizeHandle."""

    moved = Signal()
    resized = Signal(int, int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_offset: QPoint | None = None
        self.handle = _ResizeHandle(self)
        self.handle.resized.connect(self.resized)

    def reposition_handle(self) -> None:
        self.handle.move(self.width() - _HANDLE_SIZE, self.height() - _HANDLE_SIZE)
        self.handle.raise_()

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._drag_offset is None:
            return
        parent = self.parentWidget()
        target = self.mapToParent(event.pos() - self._drag_offset)
        x = max(0, min(target.x(), parent.width() - self.width()))
        y = max(0, min(target.y(), parent.height() - self.height()))
        self.move(x, y)
        self.moved.emit()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._drag_offset = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class BoxEditDialog(QDialog):
    def __init__(
        self,
        page_count: int,
        current_page_number: int,
        box_width_pt: float,
        box_height_pt: float,
        label: str = "",
        page_ref: PageRef | None = None,
        appearance: Appearance | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Signature box settings")
        self._page_count = page_count
        self._box_width_pt = box_width_pt
        self._box_height_pt = box_height_pt
        self._image_path = appearance.image_path if appearance else None
        self._image_pos = appearance.image_pos if appearance else None
        self._text_pos = appearance.text_pos if appearance else None
        self._image_size = appearance.image_size if appearance else None
        self._text_size = appearance.text_size if appearance else None

        self._label_edit = QLineEdit(label or "Signature")
        self._label_edit.textChanged.connect(self._refresh_preview)

        self._image_path_label = QLabel(self._image_path or "(no image selected)")
        browse_btn = QPushButton("Choose signature image (.png)...")
        browse_btn.clicked.connect(self._browse_image)

        self._image_scale_spin = QDoubleSpinBox()
        self._image_scale_spin.setRange(0.2, 3.0)
        self._image_scale_spin.setSingleStep(0.1)
        self._image_scale_spin.setSuffix("x")
        self._image_scale_spin.setValue(appearance.image_scale if appearance else 1.0)
        self._image_scale_spin.setToolTip(
            "Used until the image is resized by dragging its corner handle\n"
            "in the preview - after that, the dragged size takes over."
        )
        self._image_scale_spin.valueChanged.connect(self._refresh_preview)

        # Default appearance: signature image on the left, "Signed by: <name>
        # / Date: <date>" on the right (Acrobat's default layout) - no extra
        # options needed. This checkbox only swaps in a CUSTOM text template.
        self._show_text_check = QCheckBox("Use custom text template (instead of default)")
        self._show_text_check.setChecked(appearance.show_text if appearance else False)
        self._show_text_check.toggled.connect(self._refresh_preview)
        self._text_template_edit = QLineEdit(
            (appearance.text_template if appearance and appearance.text_template else
             "{{signer_name}}\n{{sign_date}}")
        )
        self._text_template_edit.textChanged.connect(self._refresh_preview)

        reset_position_btn = QPushButton("Reset position && size (image left / text right)")
        reset_position_btn.clicked.connect(self._reset_position)

        form = QFormLayout()
        form.addRow("Label:", self._label_edit)

        image_row = QHBoxLayout()
        image_row.addWidget(self._image_path_label, 1)
        image_row.addWidget(browse_btn)
        form.addRow("Signature image:", image_row)
        form.addRow("Image size:", self._image_scale_spin)
        form.addRow(
            "", QLabel("Default appearance: signature image (left) + Signed by/Date (right)")
        )
        form.addRow("", self._show_text_check)
        form.addRow("Custom text template:", self._text_template_edit)
        form.addRow("", reset_position_btn)

        canvas_w, canvas_h = self._preview_canvas_size()
        self._preview_canvas = QWidget()
        self._preview_canvas.setFixedSize(canvas_w, canvas_h)
        self._preview_canvas.setStyleSheet(
            "background-color: white; border: 1px solid palette(mid);"
        )
        self._preview_empty_label = QLabel("(no signature image yet)", self._preview_canvas)
        self._preview_empty_label.setGeometry(0, 0, canvas_w, canvas_h)
        self._preview_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_empty_label.setWordWrap(True)

        self._image_box = _DraggableBox(self._preview_canvas)
        self._image_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_box.moved.connect(self._on_image_moved)
        self._image_box.resized.connect(self._on_image_resized)
        self._image_box.hide()

        self._text_box = _DraggableBox(self._preview_canvas)
        self._text_box.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._text_box.moved.connect(self._on_text_moved)
        self._text_box.resized.connect(self._on_text_resized)
        self._text_box.hide()

        preview_layout = QVBoxLayout()
        preview_layout.addWidget(
            QLabel("Drag a box to move it, drag its corner handle to resize it:")
        )
        preview_layout.addWidget(self._preview_canvas, 0, Qt.AlignmentFlag.AlignHCenter)
        preview_layout.addStretch(1)
        preview_group = QGroupBox("Preview")
        preview_group.setLayout(preview_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        content_row = QHBoxLayout()
        content_row.addLayout(form, 1)
        content_row.addWidget(preview_group, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(content_row)
        layout.addWidget(buttons)

        self._refresh_preview()

    # ----------------------------------------------------------------- data
    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose signature image", "", "PNG image (*.png);;All files (*.*)"
        )
        if path:
            self._image_path = path
            self._image_path_label.setText(path)
            self._refresh_preview()

    def _reset_position(self) -> None:
        self._image_pos = None
        self._text_pos = None
        self._image_size = None
        self._text_size = None
        self._refresh_preview()

    def result_label(self) -> str:
        return self._label_edit.text().strip() or "Signature"

    def result_page_ref(self) -> PageRef:
        # Which page(s) get signed is now chosen at sign time (Page scope in
        # the left panel), not per-box - every box just targets "all pages"
        # in the template's own coordinate space.
        return PageRef(type=PageRefType.ALL)

    def result_appearance(self) -> Appearance:
        return Appearance(
            image_path=self._image_path,
            show_text=self._show_text_check.isChecked(),
            text_template=self._text_template_edit.text() if self._show_text_check.isChecked() else None,
            image_scale=self._image_scale_spin.value(),
            image_pos=self._image_pos,
            text_pos=self._text_pos,
            image_size=self._image_size,
            text_size=self._text_size,
        )

    # -------------------------------------------------------------- preview
    def _preview_canvas_size(self) -> tuple[int, int]:
        ratio = self._box_height_pt / self._box_width_pt if self._box_width_pt else 0.4
        return _PREVIEW_WIDTH, max(int(_PREVIEW_WIDTH * ratio), 60)

    def _on_image_moved(self) -> None:
        cw, ch = self._preview_canvas.width(), self._preview_canvas.height()
        box = self._image_box
        cx, cy = box.x() + box.width() / 2, box.y() + box.height() / 2
        self._image_pos = (cx / cw, cy / ch)

    def _on_text_moved(self) -> None:
        cw, ch = self._preview_canvas.width(), self._preview_canvas.height()
        box = self._text_box
        self._text_pos = (box.x() / cw, box.y() / ch)

    def _on_image_resized(self, new_w: int, new_h: int) -> None:
        cw, ch = self._preview_canvas.width(), self._preview_canvas.height()
        box = self._image_box
        box_x, box_y = box.x(), box.y()  # top-left is the resize anchor
        new_w = max(_MIN_BOX_PX, min(new_w, cw - box_x))
        new_h = max(_MIN_BOX_PX, min(new_h, ch - box_y))
        self._image_size = (new_w / cw, new_h / ch)
        # Re-derive the center-based image_pos so the anchored top-left
        # doesn't jump once _refresh_preview() re-centers on it.
        self._image_pos = ((box_x + new_w / 2) / cw, (box_y + new_h / 2) / ch)
        self._refresh_preview()

    def _on_text_resized(self, new_w: int, new_h: int) -> None:
        cw, ch = self._preview_canvas.width(), self._preview_canvas.height()
        box = self._text_box
        box_x, box_y = box.x(), box.y()
        new_w = max(_MIN_BOX_PX, min(new_w, cw - box_x))
        new_h = max(_MIN_BOX_PX, min(new_h, ch - box_y))
        self._text_size = (new_w / cw, new_h / ch)
        self._text_pos = (box_x / cw, box_y / ch)
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        appearance = self.result_appearance()
        has_image = bool(appearance.image_path)
        text_lines = build_text_lines(appearance, _PREVIEW_SIGNER_NAME, datetime.now().astimezone())
        has_text = bool(text_lines)

        if not has_image and not has_text:
            self._image_box.hide()
            self._text_box.hide()
            self._preview_empty_label.setText("(no signature image yet)")
            self._preview_empty_label.show()
            return
        self._preview_empty_label.hide()

        cw, ch = self._preview_canvas.width(), self._preview_canvas.height()
        # Reference split point for whichever element hasn't been
        # customized yet - independent of the OTHER element's customization
        # state, so dragging just one doesn't disturb the other's default
        # slot until it's customized too.
        left_width = int(cw * _LEFT_RATIO) if has_image and has_text else cw

        if has_image:
            box_max_w, box_max_h = cw - 2 * _PADDING, ch - 2 * _PADDING
            if self._image_size is not None:
                box_w = min(int(self._image_size[0] * cw), box_max_w)
                box_h = min(int(self._image_size[1] * ch), box_max_h)
            else:
                box_w = min(int((left_width - 2 * _PADDING) * appearance.image_scale), box_max_w)
                box_h = min(int(box_max_h * appearance.image_scale), box_max_h)
            try:
                pixmap = _pil_to_qpixmap(fit_image(appearance.image_path, box_w, box_h))
            except (OSError, ValueError):
                pixmap = None
            if pixmap is not None:
                self._image_box.setPixmap(pixmap)
                self._image_box.resize(max(box_w, 1), max(box_h, 1))
                self._image_box.reposition_handle()
                if self._image_pos is not None:
                    cx, cy = self._image_pos[0] * cw, self._image_pos[1] * ch
                    x = int(min(max(cx - box_w / 2, 0), cw - box_w))
                    y = int(min(max(cy - box_h / 2, 0), ch - box_h))
                else:
                    x = (left_width - box_w) // 2
                    y = (ch - box_h) // 2
                self._image_box.move(max(x, 0), max(y, 0))
                self._image_box.show()
            else:
                self._image_box.hide()
        else:
            self._image_box.hide()

        if has_text:
            default_text_x = (left_width + _PADDING) if has_image else _PADDING
            if self._text_size is not None:
                avail_w = max(int(self._text_size[0] * cw), _MIN_BOX_PX)
                avail_h = max(int(self._text_size[1] * ch), _MIN_BOX_PX)
            elif self._text_pos is not None:
                avail_w = max(cw - 2 * _PADDING, 10)
                avail_h = ch - 2 * _PADDING
            else:
                avail_w = max(cw - default_text_x - _PADDING, 10)
                avail_h = ch - 2 * _PADDING
            wrapped_lines, font, line_height = layout_text(text_lines, avail_w, avail_h, None)
            total_h = line_height * len(wrapped_lines)
            # Once resized, the box IS the dragged bounding rect (so the
            # handle stays where it was left); otherwise it hugs the actual
            # content height, same as the classic vertically-centered
            # layout - matches compose_appearance_image's own positioning,
            # which is never wider/taller than what's actually drawn either.
            box_w, box_h = avail_w, (avail_h if self._text_size is not None else total_h)

            text_image = Image.new("RGBA", (max(box_w, 1), max(box_h, 1)), (255, 255, 255, 0))
            draw = ImageDraw.Draw(text_image)
            y = 0
            for line in wrapped_lines:
                draw.text((0, y), line, fill=_TEXT_COLOR, font=font)
                y += line_height
            pixmap = _pil_to_qpixmap(text_image)
            self._text_box.setPixmap(pixmap)
            self._text_box.resize(max(box_w, 1), max(box_h, 1))
            self._text_box.reposition_handle()
            if self._text_pos is not None:
                x = int(min(max(self._text_pos[0] * cw, 0), max(cw - box_w, 0)))
                y = int(min(max(self._text_pos[1] * ch, 0), max(ch - box_h, 0)))
            else:
                x = default_text_x
                y = max(_PADDING, (ch - box_h) // 2)
            self._text_box.move(max(x, 0), max(y, 0))
            self._text_box.show()
        else:
            self._text_box.hide()
