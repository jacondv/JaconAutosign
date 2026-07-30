"""Renders a preview of what a template's signature will look like once
applied - reuses the exact same compose_appearance_image()/build_text_lines()
functions the real signing pipeline uses, so the preview always matches
what actually gets stamped onto the PDF.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtGui import QImage, QPixmap

from ..models import Template
from ..signing.appearance_compose import build_text_lines, compose_appearance_image


def render_template_preview(
    template: Template, signer_name: str, font_size_pt: int | None = None
) -> QPixmap | None:
    """A pixmap of the first signature box's appearance, at its real
    proportions. None if the template has no signature boxes yet."""
    if not template.signature_boxes:
        return None
    box = template.signature_boxes[0]
    text_lines = build_text_lines(box.appearance, signer_name, datetime.now().astimezone())
    image = compose_appearance_image(
        box.appearance.image_path, text_lines, box.rect.width, box.rect.height, font_size_pt
    )
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimage = QImage(data, rgba.width, rgba.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())  # copy: detach from the bytes buffer above
