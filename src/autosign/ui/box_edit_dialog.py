"""Dialog to configure one signature box: label and signature image. Which
page(s) get signed is no longer decided here - it's chosen at sign time in
the left panel (Page scope), applying uniformly to every box."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..models import Appearance, PageRef, PageRefType


class BoxEditDialog(QDialog):
    def __init__(
        self,
        page_count: int,
        current_page_number: int,
        label: str = "",
        page_ref: PageRef | None = None,
        appearance: Appearance | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Signature box settings")
        self._page_count = page_count
        self._image_path = appearance.image_path if appearance else None

        self._label_edit = QLineEdit(label or "Signature")

        self._image_path_label = QLabel(self._image_path or "(no image selected)")
        browse_btn = QPushButton("Choose signature image (.png)...")
        browse_btn.clicked.connect(self._browse_image)

        # Default appearance: signature image on the left, "Signed by: <name>
        # / Date: <date>" on the right (Acrobat's default layout) - no extra
        # options needed. This checkbox only swaps in a CUSTOM text template.
        self._show_text_check = QCheckBox("Use custom text template (instead of default)")
        self._show_text_check.setChecked(appearance.show_text if appearance else False)
        self._text_template_edit = QLineEdit(
            (appearance.text_template if appearance and appearance.text_template else
             "{{signer_name}}\n{{sign_date}}")
        )

        form = QFormLayout()
        form.addRow("Label:", self._label_edit)

        image_row = QHBoxLayout()
        image_row.addWidget(self._image_path_label, 1)
        image_row.addWidget(browse_btn)
        form.addRow("Signature image:", image_row)
        form.addRow(
            "", QLabel("Default appearance: signature image (left) + Signed by/Date (right)")
        )
        form.addRow("", self._show_text_check)
        form.addRow("Custom text template:", self._text_template_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose signature image", "", "PNG image (*.png);;All files (*.*)"
        )
        if path:
            self._image_path = path
            self._image_path_label.setText(path)

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
        )
