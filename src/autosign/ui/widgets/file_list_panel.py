"""The queued-files list: add/remove/clear controls plus an inline
"[x/y Signed]" page count. Knows nothing about signing or templates -
callers feed it page counts and react to its signals. Signing errors are
reported via a popup by the caller, not shown inline here.
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
    reset_requested = Signal(list)  # list[Path] - the selected files

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._files: list[Path] = []
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
        reset_btn = QPushButton("Reset")
        reset_btn.setToolTip("Discard the signed output for the selected file(s) so the next Sign starts over from the original.")
        reset_btn.clicked.connect(lambda: self.reset_requested.emit(self.selected_files()))
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear)
        buttons.addWidget(remove_btn)
        buttons.addWidget(reset_btn)
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

    def selected_files(self) -> list[Path]:
        return [item.data(_ROLE_PATH) for item in self._list.selectedItems()]

    def add_files(self, paths: Iterable[Path]) -> list[Path]:
        """Returns the subset of `paths` that were actually newly added
        (i.e. not already in the list), in order - callers use this to
        auto-select/preview the first newly opened file."""
        existing = set(self._files)
        added: list[Path] = []
        for path in paths:
            if path not in existing:
                self._files.append(path)
                existing.add(path)
                added.append(path)
        if added:
            self.files_changed.emit()
        return added

    def select_path(self, path: Path | None) -> None:
        """Programmatically select `path` in the list, the same as a user
        click - fires selection_changed so the preview follows."""
        if path is None:
            self._list.setCurrentItem(None)
            return
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(_ROLE_PATH) == path:
                self._list.setCurrentItem(item)
                return

    def remove_selected(self) -> None:
        selected = {item.data(_ROLE_PATH) for item in self._list.selectedItems()}
        if not selected:
            return
        self._files = [f for f in self._files if f not in selected]
        self.files_changed.emit()

    def clear(self) -> None:
        self._files.clear()
        self.files_changed.emit()

    # ------------------------------------------------------------ render
    def refresh(self, page_counts: dict[Path, tuple[int, int]] | None = None) -> None:
        """Rebuild the list widget from current files. `page_counts` maps a
        file to (signed_pages, total_pages), shown as "[x/y Signed]"."""
        page_counts = page_counts or {}
        current_path = self.current_path
        self._list.blockSignals(True)
        self._list.clear()
        current_item = None
        for path in self._files:
            text = path.name
            color = None
            counts = page_counts.get(path)
            if counts is not None:
                signed, total = counts
                text += f"  [{signed}/{total} Signed]"
                if signed > 0:
                    color = Qt.GlobalColor.darkGreen
            item = QListWidgetItem(text)
            item.setData(_ROLE_PATH, path)
            item.setToolTip(str(path))
            if color is not None:
                item.setForeground(color)
            self._list.addItem(item)
            if path == current_path:
                current_item = item
        if current_item is not None:
            self._list.setCurrentItem(current_item)
        self._list.blockSignals(False)

    def _on_selection_changed(self, current: QListWidgetItem | None, _previous) -> None:
        self.selection_changed.emit(current.data(_ROLE_PATH) if current else None)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        self.file_activated.emit(item.data(_ROLE_PATH))
