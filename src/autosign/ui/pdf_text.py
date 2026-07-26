"""Text-layer access for the read-only viewer's hover-to-select / copy
feature - hit-testing characters by position and building highlight rects
for a selection.

Kept separate from pdf_render.py (bitmap rendering): pdf_render.py opens and
closes a fresh document per call, but here the pdfium handles stay open for
as long as a page is on screen, since hover/drag interaction needs many
cheap lookups per second rather than one bitmap render.
"""
from __future__ import annotations

import pypdfium2 as pdfium

from ..pdfium_lock import PDFIUM_LOCK


class PageTextSource:
    """Lazily opens the text layer for one (pdf_path, page_index) pair.
    Must be closed explicitly, in the same spirit as the page/doc
    close-ordering note in pdf_render.py: never rely on the GC to release
    pdfium handles, since a GC-triggered close can fire from any thread at
    an arbitrary point and race with another pdfium call."""

    def __init__(self, pdf_path: str, page_index: int):
        self.pdf_path = pdf_path
        self.page_index = page_index
        self._doc = None
        self._page = None
        self._textpage = None
        self._open_failed = False

    def _ensure_open(self) -> bool:
        if self._textpage is not None:
            return True
        if self._open_failed:
            return False
        with PDFIUM_LOCK:
            try:
                self._doc = pdfium.PdfDocument(self.pdf_path)
                self._page = self._doc[self.page_index]
                self._textpage = self._page.get_textpage()
                # Required once with default params before subsequent
                # get_rect() calls work (see pypdfium2's own docstring).
                self._textpage.count_rects()
                return True
            except Exception:
                self._open_failed = True
                self._close_locked()
                return False

    def char_index_at(self, x: float, y: float, tol: float = 3.0) -> int | None:
        """Index of the character at/near PDF-point (x, y), or None."""
        if not self._ensure_open():
            return None
        with PDFIUM_LOCK:
            try:
                return self._textpage.get_index(x, y, tol, tol)
            except Exception:
                return None

    def selection_rects(self, start: int, end: int) -> list[tuple[float, float, float, float]]:
        """(left, bottom, right, top) rects in PDF points, one per line
        segment of the [start, end] character range (inclusive) - a
        selection spanning a line wrap needs more than one rect."""
        if not self._ensure_open():
            return []
        lo, hi = (start, end) if start <= end else (end, start)
        with PDFIUM_LOCK:
            try:
                n = self._textpage.count_rects(lo, hi - lo + 1)
                return [self._textpage.get_rect(i) for i in range(n)]
            except Exception:
                return []

    def text_range(self, start: int, end: int) -> str:
        if not self._ensure_open():
            return ""
        lo, hi = (start, end) if start <= end else (end, start)
        with PDFIUM_LOCK:
            try:
                return self._textpage.get_text_range(lo, hi - lo + 1)
            except Exception:
                return ""

    def close(self) -> None:
        with PDFIUM_LOCK:
            self._close_locked()

    def _close_locked(self) -> None:
        if self._textpage is not None:
            self._textpage.close()
            self._textpage = None
        if self._page is not None:
            self._page.close()
            self._page = None
        if self._doc is not None:
            self._doc.close()
            self._doc = None
