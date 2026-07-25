"""Render a PDF page to a QImage for display on a canvas / preview pane.

Kept separate from PdfInspectService: this is a UI concern (depends on Qt),
while PdfInspectService (services/) only reads metadata and has no Qt dependency.
"""
from __future__ import annotations

import pypdfium2 as pdfium
from PySide6.QtGui import QImage

from ..pdfium_lock import PDFIUM_LOCK

DEFAULT_PREVIEW_DPI = 150


def render_page_to_qimage(pdf_path: str, page_index: int, dpi: int = DEFAULT_PREVIEW_DPI) -> QImage:
    with PDFIUM_LOCK:  # pdfium is not thread-safe - see pdfium_lock.py
        doc = pdfium.PdfDocument(pdf_path)
        try:
            page = doc[page_index]
            bitmap = page.render(scale=dpi / 72)
            raw = bytes(bitmap.buffer)
            image = QImage(
                raw, bitmap.width, bitmap.height, bitmap.stride, QImage.Format.Format_BGR888
            )
            return image.copy()  # copy() because the source buffer is freed once the doc closes
        finally:
            doc.close()
