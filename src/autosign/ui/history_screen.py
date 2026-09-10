"""History tab: a read-only, sortable table of the last 100 signed files -
when each was signed and where the signed copy ended up (moved to which
project folder, or left in the output folder because no folder matched).
Populated from SigningHistoryService, written to by SignScreen's auto-move
and manual-move code paths.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from ..services import SigningHistoryService

_COL_TIME = 0
_COL_FILE = 1
_COL_RESULT = 2


class HistoryScreen(QWidget):
    def __init__(self, history_service: SigningHistoryService, parent: QWidget | None = None):
        super().__init__(parent)
        self._history = history_service
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel("Signing history (last 100 files)")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Signed at", "File name", "Result"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(_COL_TIME, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_COL_FILE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_RESULT, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table, 1)

    def refresh(self) -> None:
        entries = self._history.load()
        # Sorting is switched off while (re)filling the table so setItem()
        # doesn't fight the table re-sorting itself after every row.
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(entries))
        for row, entry in enumerate(reversed(entries)):  # newest first by default
            self._table.setItem(row, _COL_TIME, QTableWidgetItem(entry.signed_at))
            self._table.setItem(row, _COL_FILE, QTableWidgetItem(entry.file_name))
            self._table.setItem(row, _COL_RESULT, QTableWidgetItem(entry.result))
        self._table.setSortingEnabled(True)
        self._table.sortItems(_COL_TIME, Qt.SortOrder.DescendingOrder)
