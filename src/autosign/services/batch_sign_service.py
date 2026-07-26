"""Batch-signing coordinator: iterates the file list, calls SigningEngine per
file, and never lets one failing file abort the whole batch (see docs/01 F4.6).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from ..models import SignPageScope, Template
from ..signing.signing_engine import SigningEngine, SigningError
from .pdf_inspect_service import PdfInspectError, PdfInspectService


@dataclass
class FileSignResult:
    file_path: Path
    status: str  # "success" | "failed"
    error_reason: Optional[str] = None
    output_path: Optional[Path] = None
    signed_at: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.status == "success"


ProgressCallback = Callable[[int, int, FileSignResult], None]
CancelCheck = Callable[[], bool]


class BatchSignService:
    def __init__(
        self,
        pdf_inspect_service: PdfInspectService,
        signing_engine: Optional[SigningEngine] = None,
    ):
        self._pdf_inspect = pdf_inspect_service
        self._engine = signing_engine

    def run(
        self,
        files: list[Path],
        template: Template,
        output_dir: Path,
        page_scope: SignPageScope = SignPageScope.ALL,
        current_page_index: Optional[int] = None,
        on_progress: Optional[ProgressCallback] = None,
        should_cancel: Optional[CancelCheck] = None,
    ) -> list[FileSignResult]:
        if self._engine is None:
            raise SigningError("BatchSignService has no SigningEngine assigned.")
        results: list[FileSignResult] = []
        total = len(files)
        for i, file_path in enumerate(files, start=1):
            if should_cancel is not None and should_cancel():
                break
            result = self._sign_one(file_path, template, output_dir, page_scope, current_page_index)
            results.append(result)
            if on_progress is not None:
                on_progress(i, total, result)
        return results

    def _sign_one(
        self,
        file_path: Path,
        template: Template,
        output_dir: Path,
        page_scope: SignPageScope,
        current_page_index: Optional[int],
    ) -> FileSignResult:
        output_path = output_dir / file_path.name
        # If this file was already (partially) signed in an earlier run,
        # build on that output instead of the pristine source - otherwise
        # e.g. signing "current page" twice for different pages would each
        # start over from scratch and only the second signature would
        # survive. Overwrite-original output mode already has output_path
        # == file_path, so this is a no-op there.
        basis_path = output_path if output_path.exists() else file_path
        try:
            info = self._pdf_inspect.get_info(basis_path)
        except PdfInspectError as exc:
            return FileSignResult(file_path, status="failed", error_reason=str(exc))

        try:
            self._engine.sign_file(info, template, output_path, page_scope, current_page_index)
        except SigningError as exc:
            return FileSignResult(file_path, status="failed", error_reason=str(exc))

        return FileSignResult(
            file_path,
            status="success",
            output_path=output_path,
            signed_at=datetime.now(timezone.utc).astimezone().isoformat(),
        )
