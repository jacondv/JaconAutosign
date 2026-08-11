"""Renders a preview of what a template's signature will look like once
applied - reuses the exact same compose_appearance_image()/build_text_lines()
functions the real signing pipeline uses, so the preview always matches
what actually gets stamped onto the PDF.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtGui import QImage, QPixmap

from ..models import Appearance, Template
from ..signing.appearance_compose import build_text_lines, compose_appearance_image


def render_appearance_preview(
    appearance: Appearance,
    width_pt: float,
    height_pt: float,
    signer_name: str,
    font_size_pt: int | None = None,
) -> QPixmap | None:
    """A pixmap of one appearance (image + text) at its real box
    proportions - the shared renderer behind both the Settings template
    preview and the box editor's live preview, so what you see while
    customizing always matches what actually gets stamped onto the PDF."""
    if not appearance.image_path and not appearance.show_text:
        return None
    text_lines = build_text_lines(appearance, signer_name, datetime.now().astimezone())
    image = compose_appearance_image(
        appearance.image_path,
        text_lines,
        width_pt,
        height_pt,
        font_size_pt,
        appearance.image_scale,
        appearance.image_pos,
        appearance.text_pos,
        appearance.image_size,
        appearance.text_size,
    )
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimage = QImage(data, rgba.width, rgba.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())  # copy: detach from the bytes buffer above


def render_template_preview(
    template: Template, signer_name: str, font_size_pt: int | None = None
) -> QPixmap | None:
    """A pixmap of the first signature box's appearance, at its real
    proportions. None if the template has no signature boxes yet."""
    if not template.signature_boxes:
        return None
    box = template.signature_boxes[0]
    return render_appearance_preview(
        box.appearance, box.rect.width, box.rect.height, signer_name, font_size_pt
    )
