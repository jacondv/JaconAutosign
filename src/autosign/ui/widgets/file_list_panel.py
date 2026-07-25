"""The queued-files list: add/remove/clear controls plus inline status
coloring (signed / error / precheck warning). Knows nothing about signing or
templates - callers feed it warnings/statuses and react to its signals.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_ROLE_PATH = 1000


class FileListPanel(QWidget):
    selection_changed = Signal(object)  # Path | None
    file_activated = Signal(Path)  # double-click
    files_changed = Signal()  # files were added/removed/cleared - caller should refresh()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._files: list[Path] = []
        self._statuses: dict[Path, str] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Files"))

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._list.itemDoubleClicked.connect(self._on_item_activated)
        layout.addWidget(self._list, 1)

        buttons = QHBoxLayout()
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_selected)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear)
        buttons.addWidget(remove_btn)
        buttons.addWidget(clear_btn)
        layout.addLayout(buttons)

    # -------------------------------------------------------------- state
    @property
    def files(self) -> list[Path]:
        return list(self._files)

    @property
    def current_path(self) -> Path | None:
        item = self._list.currentItem()
        return item.data(_ROLE_PATH) if item else None

    def add_files(self, paths: Iterable[Path]) -> None:
        existing = set(self._files)
        added = False
        for path in paths:
            if path not in existing:
                self._files.append(path)
                existing.add(path)
                added = True
        if added:
            self.files_changed.emit()

    def remove_selected(self) -> None:
        selected = {item.data(_ROLE_PATH) for item in self._list.selectedItems()}
        if not selected:
            return
        self._files = [f for f in self._files if f not in selected]
        self.files_changed.emit()

    def clear(self) -> None:
        self._files.clear()
        self._statuses.clear()
        self.files_changed.emit()

    def set_status(self, path: Path, status: str) -> None:
        self._statuses[path] = status

    # ------------------------------------------------------------ render
    def refresh(self, warnings: dict[Path, str] | None = None) -> None:
        """Rebuild the list widget from current files/statuses. `warnings`
        (e.g. precheck results) are only shown for files with no status yet."""
        warnings = warnings or {}
        self._list.blockSignals(True)
        self._list.clear()
        for path in self._files:
            status = self._statuses.get(path)
            warning = warnings.get(path)
            text = path.name
            color = None
            if status == "success":
                text += "  -  Signed"
                color = Qt.GlobalColor.darkGreen
            elif status is not None:
                text += f"  -  Error: {status}"
                color = Qt.GlobalColor.red
            elif warning:
                text += f"  -  {warning}"
                color = Qt.GlobalColor.darkYellow
            item = QListWidgetItem(text)
            item.setData(_ROLE_PATH, path)
            item.setToolTip(str(path))
            if color is not None:
                item.setForeground(color)
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _on_selection_changed(self, current: QListWidgetItem | None, _previous) -> None:
        self.selection_changed.emit(current.data(_ROLE_PATH) if current else None)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        self.file_activated.emit(item.data(_ROLE_PATH))
