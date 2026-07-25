"""Batch-signing coordinator: iterates the file list, calls SigningEngine per
file, and never lets one failing file abort the whole batch (see docs/01 F4.6).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from ..models import Template
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


@dataclass
class PrecheckResult:
    file_path: Path
    page_count: Optional[int]
    warning: Optional[str]  # None = no warning


ProgressCallback = Callable[[int, int, FileSignResult], None]
CancelCheck = Callable[[], bool]


class BatchSignService:
    """signing_engine may be left unset when only a precheck (page-count
    validation, no certificate password needed yet) is required - it must be
    provided before calling run()."""

    def __init__(
        self,
        pdf_inspect_service: PdfInspectService,
        signing_engine: Optional[SigningEngine] = None,
    ):
        self._pdf_inspect = pdf_inspect_service
        self._engine = signing_engine

    def precheck(self, files: list[Path], template: Template) -> list[PrecheckResult]:
        """Check each file's page count against the template's requirements upfront (F3.4)."""
        results = []
        for file_path in files:
            try:
                info = self._pdf_inspect.get_info(file_path)
            except PdfInspectError as exc:
                results.append(PrecheckResult(file_path, None, str(exc)))
                continue

            missing = [
                box.page_ref.describe()
                for box in template.signature_boxes
                if not box.page_ref.resolve_indices(info.page_count)
            ]
            warning = (
                f"Missing required page(s): {', '.join(missing)} (file has {info.page_count} page(s))"
                if missing
                else None
            )
            results.append(PrecheckResult(file_path, info.page_count, warning))
        return results

    def run(
        self,
        files: list[Path],
        template: Template,
        output_dir: Path,
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
            result = self._sign_one(file_path, template, output_dir)
            results.append(result)
            if on_progress is not None:
                on_progress(i, total, result)
        return results

    def _sign_one(self, file_path: Path, template: Template, output_dir: Path) -> FileSignResult:
        try:
            info = self._pdf_inspect.get_info(file_path)
        except PdfInspectError as exc:
            return FileSignResult(file_path, status="failed", error_reason=str(exc))

        output_path = output_dir / file_path.name
        try:
            self._engine.sign_file(info, template, output_path)
        except SigningError as exc:
            return FileSignResult(file_path, status="failed", error_reason=str(exc))

        return FileSignResult(
            file_path,
            status="success",
            output_path=output_path,
            signed_at=datetime.now(timezone.utc).astimezone().isoformat(),
        )
