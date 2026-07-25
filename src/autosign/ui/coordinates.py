"""Shared conversion between PDF points (bottom-left origin) and preview-image
pixels (top-left origin) - used by both the template designer canvas and the
read-only PDF preview pane."""
from __future__ import annotations

from PySide6.QtCore import QRectF

from ..models import PageSize, Rect


def pdf_rect_to_pixel(rect: Rect, page_size: PageSize, dpi: float) -> QRectF:
    scale = dpi / 72.0
    x = rect.x * scale
    width = rect.width * scale
    height = rect.height * scale
    y = (page_size.height - rect.y - rect.height) * scale
    return QRectF(x, y, width, height)


def pixel_rect_to_pdf(rect: QRectF, page_size: PageSize, dpi: int) -> Rect:
    scale = dpi / 72.0
    x = rect.x() / scale
    width = rect.width() / scale
    height = rect.height() / scale
    y = page_size.height - (rect.y() + rect.height()) / scale
    return Rect(x=x, y=y, width=width, height=height)
