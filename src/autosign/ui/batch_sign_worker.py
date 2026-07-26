"""Runs BatchSignService on its own QThread so the UI doesn't freeze (F4.4)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..models import SignPageScope, Template
from ..services.batch_sign_service import BatchSignService


class BatchSignWorker(QThread):
    progress = Signal(int, int, object)  # (done_count, total, FileSignResult)
    finished_all = Signal(list)  # list[FileSignResult]

    def __init__(
        self,
        service: BatchSignService,
        files: list[Path],
        template: Template,
        output_dir: Path,
        page_scope: SignPageScope = SignPageScope.ALL,
        current_page_index: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._service = service
        self._files = files
        self._template = template
        self._output_dir = output_dir
        self._page_scope = page_scope
        self._current_page_index = current_page_index
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:  # noqa: D102 (Qt override, runs on its own thread)
        results = self._service.run(
            self._files,
            self._template,
            self._output_dir,
            page_scope=self._page_scope,
            current_page_index=self._current_page_index,
            on_progress=lambda done, total, result: self.progress.emit(done, total, result),
            should_cancel=lambda: self._cancel_requested,
        )
        self.finished_all.emit(results)
