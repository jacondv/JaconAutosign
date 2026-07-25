"""Dialog to configure one signature box: label, page reference, signature image."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ..models import Appearance, PageRef, PageRefType

_PAGE_REF_LABELS = {
    PageRefType.FIRST: "First page",
    PageRefType.LAST: "Last page",
    PageRefType.ALL: "All pages",
    PageRefType.ABSOLUTE: "Specific page...",
}


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

        self._page_ref_combo = QComboBox()
        for ref_type, text in _PAGE_REF_LABELS.items():
            self._page_ref_combo.addItem(text, ref_type)

        self._page_number_spin = QSpinBox()
        self._page_number_spin.setRange(1, max(page_count, 1))
        self._page_number_spin.setValue(current_page_number)

        initial_type = page_ref.type if page_ref else PageRefType.ABSOLUTE
        index = self._page_ref_combo.findData(initial_type)
        self._page_ref_combo.setCurrentIndex(max(index, 0))
        if page_ref and page_ref.type == PageRefType.ABSOLUTE and page_ref.page_number:
            self._page_number_spin.setValue(page_ref.page_number)
        self._page_ref_combo.currentIndexChanged.connect(self._update_page_number_visibility)

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
        form.addRow("Applies to:", self._page_ref_combo)
        form.addRow("Page number:", self._page_number_spin)

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

        self._update_page_number_visibility()

    def _update_page_number_visibility(self) -> None:
        is_absolute = self._page_ref_combo.currentData() == PageRefType.ABSOLUTE
        self._page_number_spin.setEnabled(is_absolute)

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
        # QComboBox/QVariant loses the Enum subtype when round-tripping through
        # currentData(), returning a plain str - must coerce back explicitly.
        ref_type = PageRefType(self._page_ref_combo.currentData())
        if ref_type == PageRefType.ABSOLUTE:
            return PageRef(type=ref_type, page_number=self._page_number_spin.value())
        return PageRef(type=ref_type)

    def result_appearance(self) -> Appearance:
        return Appearance(
            image_path=self._image_path,
            show_text=self._show_text_check.isChecked(),
            text_template=self._text_template_edit.text() if self._show_text_check.isChecked() else None,
        )
