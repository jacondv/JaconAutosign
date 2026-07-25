"""Read PDF info (page count, size, rotation) via pypdfium2 - no Qt dependency."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium

from ..models import PageSize
from ..pdfium_lock import PDFIUM_LOCK


@dataclass(frozen=True)
class PdfInfo:
    path: Path
    page_count: int
    page_sizes: list[PageSize]

    def page_size(self, index: int) -> PageSize:
        return self.page_sizes[index]


class PdfInspectError(Exception):
    """PDF could not be read (corrupted, wrong format...)."""


class PdfInspectService:
    def get_info(self, path: Path) -> PdfInfo:
        with PDFIUM_LOCK:  # pdfium is not thread-safe - see pdfium_lock.py
            try:
                doc = pdfium.PdfDocument(str(path))
            except pdfium.PdfiumError as exc:
                raise PdfInspectError(f"Could not read PDF file: {exc}") from exc

            try:
                page_sizes = []
                for i in range(len(doc)):
                    page = doc[i]
                    width, height = page.get_size()
                    rotation = page.get_rotation()
                    page_sizes.append(PageSize(width=width, height=height, rotation=rotation))
                return PdfInfo(path=path, page_count=len(doc), page_sizes=page_sizes)
            finally:
                doc.close()
