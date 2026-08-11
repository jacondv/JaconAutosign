"""Compose the signature image (left) + signer name/date (right) into a
single image, matching Adobe Acrobat's default layout when signing with a
certificate - or, once image_pos/text_pos are set on the Appearance, an
independently positioned/sized layout dragged out in the box editor.
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


def fit_image(image_path: str, max_w: int, max_h: int) -> Image.Image:
    """Loads image_path and resizes it (can enlarge past its native
    resolution, not just shrink) to fit within max_w x max_h while
    preserving aspect ratio. Shared by the real compose step and the box
    editor's draggable preview, so a dragged/resized preview matches what
    actually gets signed."""
    signature = Image.open(image_path).convert("RGBA")
    max_w, max_h = max(max_w, 1), max(max_h, 1)
    fit = min(max_w / signature.width, max_h / signature.height)
    new_size = (max(int(signature.width * fit), 1), max(int(signature.height * fit), 1))
    return signature.resize(new_size, Image.LANCZOS)


def layout_text(
    text_lines: list[str], available_w: int, available_h: int, font_size_pt: int | None
) -> tuple[list[str], ImageFont.ImageFont, int]:
    """Word-wraps text_lines to fit available_w, picking a font size - fixed
    (font_size_pt honored as-is) or auto-shrunk until the wrapped lines fit
    available_h. Returns (wrapped_lines, font, line_height). Shared by the
    real compose step and the box editor's draggable preview."""
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    if font_size_pt:
        font_size = max(_MIN_FONT_SIZE, font_size_pt * _PX_PER_POINT)
        font = _load_font(font_size)
        wrapped_lines = [w for line in text_lines for w in _wrap_line(line, font, available_w, probe)]
        return wrapped_lines, font, font_size + 4

    font_size = max(9, min(int(available_h * 0.16), available_h // max(len(text_lines), 1) - 2))
    while True:
        font = _load_font(font_size)
        wrapped_lines = [w for line in text_lines for w in _wrap_line(line, font, available_w, probe)]
        line_height = font_size + 4
        total_h = line_height * len(wrapped_lines)
        if total_h <= available_h or font_size <= _MIN_FONT_SIZE:
            return wrapped_lines, font, line_height
        font_size -= 1


def compose_appearance_image(
    image_path: str | None,
    text_lines: list[str],
    box_width_pt: float,
    box_height_pt: float,
    font_size_pt: int | None = None,
    image_scale: float = 1.0,
    image_pos: tuple[float, float] | None = None,
    text_pos: tuple[float, float] | None = None,
    image_size: tuple[float, float] | None = None,
    text_size: tuple[float, float] | None = None,
) -> Image.Image:
    """image_pos (image center) / text_pos (text block top-left), each a
    (x_frac, y_frac) of the box; image_size / text_size, each a (w_frac,
    h_frac) bounding box - None means "not positioned/resized independently
    yet", using image_scale and the classic image-left/text-right split
    instead (see the docstring on the Appearance model)."""
    width = max(int(box_width_pt * _PX_PER_POINT), 120)
    height = max(int(box_height_pt * _PX_PER_POINT), 60)
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 0))

    has_image = bool(image_path)
    has_text = bool(text_lines)
    # Reference split point for whichever element hasn't been customized
    # yet - independent of the OTHER element's customization state, so
    # e.g. dragging just the image doesn't disturb the text's default slot
    # (and vice versa) until that element is itself customized too.
    left_width = int(width * _LEFT_RATIO) if has_image and has_text else width

    if has_image:
        box_max_w = width - 2 * _PADDING
        box_max_h = height - 2 * _PADDING
        if image_size is not None:
            max_w = min(int(image_size[0] * width), box_max_w)
            max_h = min(int(image_size[1] * height), box_max_h)
        else:
            max_w = min(int((left_width - 2 * _PADDING) * image_scale), box_max_w)
            max_h = min(int(box_max_h * image_scale), box_max_h)
        signature = fit_image(image_path, max_w, max_h)
        if image_pos is not None:
            cx, cy = image_pos[0] * width, image_pos[1] * height
            x = int(min(max(cx - signature.width / 2, 0), width - signature.width))
            y = int(min(max(cy - signature.height / 2, 0), height - signature.height))
        else:
            x = (left_width - signature.width) // 2
            y = (height - signature.height) // 2
        canvas.paste(signature, (x, y), signature)

    if has_text:
        draw = ImageDraw.Draw(canvas)
        default_text_x = (left_width + _PADDING) if has_image else _PADDING
        if text_size is not None:
            available_w = max(int(text_size[0] * width), 10)
            available_h = max(int(text_size[1] * height), 10)
        else:
            available_w = (
                max(width - 2 * _PADDING, 10) if text_pos is not None
                else max(width - default_text_x - _PADDING, 10)
            )
            available_h = height - 2 * _PADDING
        wrapped_lines, font, line_height = layout_text(text_lines, available_w, available_h, font_size_pt)
        total_h = line_height * len(wrapped_lines)

        if text_pos is not None:
            x = int(min(max(text_pos[0] * width, 0), max(width - available_w - _PADDING, 0)))
            y = int(min(max(text_pos[1] * height, 0), max(height - total_h, 0)))
        else:
            x = default_text_x
            y = max(_PADDING, (height - total_h) // 2)

        for line in wrapped_lines:
            draw.text((x, y), line, fill=_TEXT_COLOR, font=font)
            y += line_height

    return canvas
