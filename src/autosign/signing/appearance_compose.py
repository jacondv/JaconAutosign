"""Compose the signature image (left) + signer name/date (right) into a
single image, matching Adobe Acrobat's default layout when signing with a
certificate.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from ..models import Appearance

_PX_PER_POINT = 4  # composed-image resolution; higher = sharper when the PDF is zoomed
_LEFT_RATIO = 0.42
_PADDING = 6
_TEXT_COLOR = (20, 20, 20, 255)
_MIN_FONT_SIZE = 7


def _load_font(size: int) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build_text_lines(
    appearance: "Appearance", signer_display_name: str, sign_time: datetime
) -> list[str]:
    """The text lines shown next to the signature image - shared by the real
    signing pipeline (signing_engine.py) and the Settings template preview,
    so the preview always matches what actually gets signed."""
    date_str = _format_signing_date(sign_time)
    if appearance.show_text and appearance.text_template:
        rendered = appearance.text_template.replace(
            "{{signer_name}}", signer_display_name or ""
        ).replace("{{sign_date}}", date_str)
        return [line for line in rendered.split("\n") if line.strip()]

    lines = []
    if signer_display_name:
        lines.append(f"Digitally signed by {signer_display_name}")
    lines.append(f"Date: {date_str}")
    return lines


def _format_signing_date(sign_time: datetime) -> str:
    """Adobe-style timestamp, e.g. "2026.07.27 09:40:08 +07'00'"."""
    offset = sign_time.strftime("%z") or "+0000"
    offset = f"{offset[:3]}'{offset[3:]}'"
    return sign_time.strftime("%Y.%m.%d %H:%M:%S ") + offset


def _wrap_line(line: str, font: ImageFont.ImageFont, max_width: float, draw: ImageDraw.ImageDraw) -> list[str]:
    """Break `line` at word boundaries so no piece exceeds max_width. Falls
    back to the whole word (no mid-word breaking) if a single word alone is
    already wider than max_width - better to overflow slightly than mangle it."""
    words = line.split(" ")
    if not words:
        return [line]
    wrapped = [words[0]]
    for word in words[1:]:
        candidate = f"{wrapped[-1]} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            wrapped[-1] = candidate
        else:
            wrapped.append(word)
    return wrapped


def compose_appearance_image(
    image_path: str | None,
    text_lines: list[str],
    box_width_pt: float,
    box_height_pt: float,
    font_size_pt: int | None = None,
) -> Image.Image:
    width = max(int(box_width_pt * _PX_PER_POINT), 120)
    height = max(int(box_height_pt * _PX_PER_POINT), 60)
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 0))

    has_image = bool(image_path)
    left_width = int(width * _LEFT_RATIO) if has_image and text_lines else width

    if has_image:
        signature = Image.open(image_path).convert("RGBA")
        max_w = left_width - 2 * _PADDING
        max_h = height - 2 * _PADDING
        signature.thumbnail((max(max_w, 1), max(max_h, 1)))
        x = (left_width - signature.width) // 2
        y = (height - signature.height) // 2
        canvas.paste(signature, (x, y), signature)

    if text_lines:
        draw = ImageDraw.Draw(canvas)
        text_x = (left_width + _PADDING) if has_image else _PADDING
        available_w = max(width - text_x - _PADDING, 10)
        available_h = height - 2 * _PADDING

        if font_size_pt:
            # User picked a fixed size (in pt, same unit as the box) -
            # honor it as-is, no shrink-to-fit.
            font_size = max(_MIN_FONT_SIZE, font_size_pt * _PX_PER_POINT)
            font = _load_font(font_size)
            wrapped_lines = [
                wrapped for line in text_lines for wrapped in _wrap_line(line, font, available_w, draw)
            ]
            line_height = font_size + 4
            total_h = line_height * len(wrapped_lines)
        else:
            font_size = max(9, min(int(height * 0.16), available_h // max(len(text_lines), 1) - 2))
            # Word-wrap at the current font size, then shrink and re-wrap until
            # the wrapped lines fit the box height (or we hit the size floor) -
            # a box too narrow for "Signed by: ..." wraps instead of overflowing.
            while True:
                font = _load_font(font_size)
                wrapped_lines = [
                    wrapped for line in text_lines for wrapped in _wrap_line(line, font, available_w, draw)
                ]
                line_height = font_size + 4
                total_h = line_height * len(wrapped_lines)
                if total_h <= available_h or font_size <= _MIN_FONT_SIZE:
                    break
                font_size -= 1

        y = max(_PADDING, (height - total_h) // 2)
        for line in wrapped_lines:
            draw.text((text_x, y), line, fill=_TEXT_COLOR, font=font)
            y += line_height

    return canvas
