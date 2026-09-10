"""History tab: a read-only, sortable table of the last 100 signed files -
when each was signed, and its source/destination folders. Populated from
SigningHistoryService, written to by SignScreen's auto-move and manual-move
code paths.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import SigningHistoryService

_NO_MATCH_SUFFIX = " (no matching folder)"

_COL_INDEX = 0
_COL_TIME = 1
_COL_FILE = 2
_COL_SOURCE = 3
_COL_DESTINATION = 4


class HistoryScreen(QWidget):
    def __init__(self, history_service: SigningHistoryService, parent: QWidget | None = None):
        super().__init__(parent)
        self._history = history_service
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        title = QLabel("Signing history (last 100 files)")
        title.setObjectName("sectionTitle")
        header_row.addWidget(title)
        header_row.addStretch(1)
        clear_btn = QPushButton("Clear History")
        clear_btn.clicked.connect(self._on_clear_clicked)
        header_row.addWidget(clear_btn)
        layout.addLayout(header_row)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["#", "Signed at", "File name", "Source", "Destination"]
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        # Interactive (the default resize mode) lets the user drag every
        # column to whatever width they want, including these two.
        header.setSectionResizeMode(_COL_INDEX, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(_COL_INDEX, 40)
        header.setSectionResizeMode(_COL_TIME, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(_COL_TIME, 150)
        header.setSectionResizeMode(_COL_FILE, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(_COL_FILE, 220)
        header.setSectionResizeMode(_COL_SOURCE, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(_COL_SOURCE, 260)
        header.setSectionResizeMode(_COL_DESTINATION, QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        # Deferred: sortIndicatorChanged fires as the click starts the sort,
        # not after it - renumbering right away would read the pre-sort
        # row order.
        header.sortIndicatorChanged.connect(lambda *_: QTimer.singleShot(0, self._renumber_rows))
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self._table, 1)

    def refresh(self) -> None:
        entries = self._history.load()
        # Sorting is switched off while (re)filling the table so setItem()
        # doesn't fight the table re-sorting itself after every row.
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(entries))
        for row, entry in enumerate(reversed(entries)):  # newest first by default
            self._table.setItem(row, _COL_INDEX, QTableWidgetItem())
            self._table.setItem(row, _COL_TIME, QTableWidgetItem(entry.signed_at))
            self._table.setItem(row, _COL_FILE, QTableWidgetItem(entry.file_name))
            self._table.setItem(row, _COL_SOURCE, QTableWidgetItem(entry.source_dir))
            self._table.setItem(row, _COL_DESTINATION, QTableWidgetItem(entry.destination))
        self._table.setSortingEnabled(True)
        self._table.sortItems(_COL_TIME, Qt.SortOrder.DescendingOrder)
        self._renumber_rows()

    def _renumber_rows(self) -> None:
        # "#" reflects the row's current on-screen position, not a sortable
        # value of its own - recomputed after every (re)sort.
        for row in range(self._table.rowCount()):
            item = self._table.item(row, _COL_INDEX)
            if item is not None:
                item.setText(str(row + 1))

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        if column not in (_COL_SOURCE, _COL_DESTINATION):
            return
        item = self._table.item(row, column)
        if item is None:
            return
        text = item.text()
        if text.endswith(_NO_MATCH_SUFFIX):
            text = text[: -len(_NO_MATCH_SUFFIX)]
        folder = Path(text)
        if not folder.is_dir():
            QMessageBox.information(self, "Folder not found", f"'{folder}' no longer exists.")
            return
        self._open_in_os(folder)

    @staticmethod
    def _open_in_os(path: Path) -> None:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa: S606 (opens the folder with Explorer)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)

    def _on_clear_clicked(self) -> None:
        if self._table.rowCount() == 0:
            return
        confirm = QMessageBox.question(
            self,
            "Clear history",
            "Delete all signing history? This cannot be undone.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._history.clear()
        self.refresh()
