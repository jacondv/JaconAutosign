"""Dialog to configure one signature box: label, signature image, and image
size - with a live preview so the effect is visible immediately, without
going through the Sign screen. Which page(s) get signed is no longer
decided here - it's chosen at sign time in the left panel (Page scope),
applying uniformly to every box."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
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
)

from ..models import Appearance, PageRef, PageRefType
from .appearance_preview import render_appearance_preview

_PREVIEW_SIGNER_NAME = "Signer Name"
_PREVIEW_MAX_WIDTH = 280


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
            "Scales the signature image within its box (1.0x = default fit).\n"
            "Larger values grow the image up to the box's edges."
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

        self._preview_label = QLabel("(no signature image yet)")
        self._preview_label.setWordWrap(True)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumHeight(120)
        self._preview_label.setFrameShape(QLabel.Shape.StyledPanel)
        preview_layout = QVBoxLayout()
        preview_layout.addWidget(self._preview_label, 1)
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

    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose signature image", "", "PNG image (*.png);;All files (*.*)"
        )
        if path:
            self._image_path = path
            self._image_path_label.setText(path)
            self._refresh_preview()

    def _refresh_preview(self) -> None:
        pixmap = render_appearance_preview(
            self._current_appearance(), self._box_width_pt, self._box_height_pt, _PREVIEW_SIGNER_NAME
        )
        if pixmap is None:
            self._preview_label.setPixmap(QPixmap())
            self._preview_label.setText("(no signature image yet)")
            return
        if pixmap.width() > _PREVIEW_MAX_WIDTH:
            pixmap = pixmap.scaledToWidth(_PREVIEW_MAX_WIDTH, Qt.TransformationMode.SmoothTransformation)
        self._preview_label.setText("")
        self._preview_label.setPixmap(pixmap)

    def _current_appearance(self) -> Appearance:
        return Appearance(
            image_path=self._image_path,
            show_text=self._show_text_check.isChecked(),
            text_template=self._text_template_edit.text() if self._show_text_check.isChecked() else None,
            image_scale=self._image_scale_spin.value(),
        )

    def result_label(self) -> str:
        return self._label_edit.text().strip() or "Signature"

    def result_page_ref(self) -> PageRef:
        # Which page(s) get signed is now chosen at sign time (Page scope in
        # the left panel), not per-box - every box just targets "all pages"
        # in the template's own coordinate space.
        return PageRef(type=PageRefType.ALL)

    def result_appearance(self) -> Appearance:
        return self._current_appearance()
