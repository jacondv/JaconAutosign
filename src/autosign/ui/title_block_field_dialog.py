"""Small dialog shown right after drawing a title-block field rectangle in
the Template Designer: pick which value it represents and which page it's
on. Unlike a signature box, a title-block field has no appearance to
configure - it's read-only extraction, not something drawn onto the PDF.
"""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout

from ..models import PageRef, PageRefType, TitleBlockFieldType

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
        self._type_combo.currentIndexChanged.connect(self._update_row_hint_visibility)

        self._row_hint = QLabel(
            "Draw this box tightly around the BOTTOM row of the revision table (REV 0, the "
            "initial release) - it never moves as later revisions are added above it. The "
            "box's own height is used as the row spacing; the app scans upward until it hits "
            "a blank row to find the newest revision, so there's nothing else to configure."
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

        form = QFormLayout()
        form.addRow("Field:", self._type_combo)
        form.addRow("Page:", self._page_combo)
        form.addRow("", self._row_hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Mark what this rectangle contains."))
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._update_row_hint_visibility()

    def _update_row_hint_visibility(self) -> None:
        self._row_hint.setVisible(self.result_field_type().is_revision_row)

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
