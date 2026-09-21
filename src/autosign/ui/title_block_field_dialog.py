"""Small dialog shown right after drawing a title-block field rectangle in
the Template Designer: pick which value it represents and which page it's
on. Unlike a signature box, a title-block field has no appearance to
configure - it's read-only extraction, not something drawn onto the PDF.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from ..models import DEFAULT_REVISION_MAX_ROWS, PageRef, PageRefType, TitleBlockFieldType

_FIELD_LABELS: dict[TitleBlockFieldType, str] = {
    TitleBlockFieldType.DRAWING_NO: "Drawing No.",
    TitleBlockFieldType.DRAWN_NAME: "DRAWN - name",
    TitleBlockFieldType.DRAWN_DATE: "DRAWN - date",
    TitleBlockFieldType.CHKD_NAME: "CHK'D - name",
    TitleBlockFieldType.CHKD_DATE: "CHK'D - date",
    TitleBlockFieldType.APPD_NAME: "APP'D - name",
    TitleBlockFieldType.APPD_DATE: "APP'D - date",
    TitleBlockFieldType.REV_NUMBER: "Revision table - newest REV No.",
    TitleBlockFieldType.REV_BY: "Revision table - newest BY",
    TitleBlockFieldType.REV_CKD: "Revision table - newest CKD",
    TitleBlockFieldType.REV_APP: "Revision table - newest APP",
    TitleBlockFieldType.REV_DATE: "Revision table - newest DATE",
}

_PAGE_THIS = ("this", None)
_PAGE_FIRST = ("first", None)
_PAGE_LAST = ("last", None)


class TitleBlockFieldDialog(QDialog):
    def __init__(
        self,
        current_page_number: int,
        field_type: TitleBlockFieldType | None = None,
        page_ref: PageRef | None = None,
        row_height_pt: float | None = None,
        max_rows: int = DEFAULT_REVISION_MAX_ROWS,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Title block field")
        self._current_page_number = current_page_number

        self._type_combo = QComboBox()
        for option, label in _FIELD_LABELS.items():
            self._type_combo.addItem(label, option.value)
        if field_type is not None:
            index = self._type_combo.findData(TitleBlockFieldType(field_type).value)
            if index >= 0:
                self._type_combo.setCurrentIndex(index)
        self._type_combo.currentIndexChanged.connect(self._update_row_fields_visibility)

        self._row_height_spin = QDoubleSpinBox()
        self._row_height_spin.setRange(1.0, 200.0)
        self._row_height_spin.setSuffix(" pt")
        self._row_height_spin.setValue(row_height_pt or 12.0)
        self._max_rows_spin = QSpinBox()
        self._max_rows_spin.setRange(1, 50)
        self._max_rows_spin.setValue(max_rows)
        self._row_hint = QLabel(
            "The rectangle you drew is row slot #1 (the topmost slot of the table's fixed "
            "capacity) - it may be blank on files with fewer revisions than that capacity. "
            "Row height is the vertical distance to the next slot down; the app scans every "
            "slot and picks the actual newest revision, wherever it lands."
        )
        self._row_hint.setWordWrap(True)

        self._page_combo = QComboBox()
        self._page_combo.addItem(f"This page (page {current_page_number}, fixed)", _PAGE_THIS)
        self._page_combo.addItem("First page", _PAGE_FIRST)
        self._page_combo.addItem("Last page", _PAGE_LAST)
        if page_ref is not None:
            ref_type = PageRefType(page_ref.type)
            if ref_type == PageRefType.FIRST:
                self._page_combo.setCurrentIndex(1)
            elif ref_type == PageRefType.LAST:
                self._page_combo.setCurrentIndex(2)
            else:
                self._page_combo.setCurrentIndex(0)

        self._row_height_label = QLabel("Row height:")
        self._max_rows_label = QLabel("Max rows in table:")

        form = QFormLayout()
        form.addRow("Field:", self._type_combo)
        form.addRow("Page:", self._page_combo)
        form.addRow(self._row_height_label, self._row_height_spin)
        form.addRow(self._max_rows_label, self._max_rows_spin)
        form.addRow("", self._row_hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Mark what this rectangle contains. For a \"Revision table\" field, draw the "
                "topmost row slot of the table."
            )
        )
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._update_row_fields_visibility()

    def _update_row_fields_visibility(self) -> None:
        is_row = self.result_field_type().is_revision_row
        for widget in (
            self._row_height_label,
            self._row_height_spin,
            self._max_rows_label,
            self._max_rows_spin,
            self._row_hint,
        ):
            widget.setVisible(is_row)

    def result_field_type(self) -> TitleBlockFieldType:
        return TitleBlockFieldType(self._type_combo.currentData())

    def result_label(self) -> str:
        return _FIELD_LABELS[self.result_field_type()]

    def result_page_ref(self) -> PageRef:
        kind, _ = self._page_combo.currentData()
        if kind == "first":
            return PageRef(type=PageRefType.FIRST)
        if kind == "last":
            return PageRef(type=PageRefType.LAST)
        return PageRef(type=PageRefType.ABSOLUTE, page_number=self._current_page_number)

    def result_row_height_pt(self) -> float | None:
        return self._row_height_spin.value() if self.result_field_type().is_revision_row else None

    def result_max_rows(self) -> int:
        return self._max_rows_spin.value()
