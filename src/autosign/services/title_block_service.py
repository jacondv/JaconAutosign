"""Reads the title-block fields configured on a Template out of an actual
PDF file, and cross-checks them: the values must be internally consistent
(CHK'D/APP'D on the main title block must match the newest revision row),
optionally match a fixed expected value from Settings, the Drawing No. must
appear in the file name, and none of the dates should be later than the
actual signing time. All checks are warnings only - see sign_screen.py,
which never blocks signing on these, only surfaces them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pypdfium2 as pdfium

from ..models import Rect, Template, TitleBlockField, TitleBlockFieldType
from ..pdfium_lock import PDFIUM_LOCK

_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%y", "%Y-%m-%d", "%d %b %Y", "%d-%b-%y")


@dataclass(frozen=True)
class TitleBlockInfo:
    """One extracted text value per field_type present on the template -
    None for any field_type the template doesn't define."""

    values: dict[TitleBlockFieldType, str]

    def get(self, field_type: TitleBlockFieldType) -> Optional[str]:
        return self.values.get(field_type) or None


@dataclass(frozen=True)
class TitleBlockWarning:
    message: str
    field_types: tuple[TitleBlockFieldType, ...]  # which extracted field(s) this concerns


def extract_title_block_info(pdf_path: Path, template: Template) -> Optional[TitleBlockInfo]:
    """None if the template has no title-block fields configured at all -
    callers use that to skip the whole feature for templates that don't use
    it, same as "no signature boxes" is a no-op elsewhere."""
    if not template.title_block_fields:
        return None
    values: dict[TitleBlockFieldType, str] = {}
    with PDFIUM_LOCK:
        try:
            doc = pdfium.PdfDocument(str(pdf_path))
        except Exception:
            return TitleBlockInfo(values={})
        try:
            page_count = len(doc)
            page_cache: dict[int, _PageContext] = {}
            fixed_fields = [f for f in template.title_block_fields if not f.field_type.is_revision_row]
            revision_fields = [f for f in template.title_block_fields if f.field_type.is_revision_row]
            for tb_field in fixed_fields:
                page_index = tb_field.page_ref.resolve_index(page_count)
                if page_index is None:
                    continue
                ctx = _get_page_context(doc, page_index, page_cache)
                text = _extract_rect_text(ctx, _design_rect_to_raw(tb_field, ctx))
                if text:
                    values[TitleBlockFieldType(tb_field.field_type)] = text
            if revision_fields:
                values.update(_extract_newest_revision_row(doc, page_count, revision_fields, page_cache))
        finally:
            for ctx in page_cache.values():
                ctx.close()
            doc.close()
    return TitleBlockInfo(values=values)


@dataclass
class _PageContext:
    """One page's textpage plus the geometry needed to map a field's
    design-time rect (in the ROTATED/visual coordinate space that
    render_page_to_qimage and the Template Designer canvas both use - see
    coordinates.py) into pdfium's text-extraction space, which is always
    the page's RAW, un-rotated mediabox - the two only coincide when the
    page has no /Rotate. Kept open across every field on the same page
    instead of re-opening per field/row (a revision-row field alone can
    scan up to _MAX_SCAN_ROWS rows)."""

    page: "pdfium.PdfPage"
    textpage: "pdfium.PdfTextPage"
    visual_width: float
    visual_height: float
    rotation: int

    def close(self) -> None:
        self.textpage.close()
        self.page.close()


def _get_page_context(
    doc: "pdfium.PdfDocument", page_index: int, cache: dict[int, _PageContext]
) -> _PageContext:
    ctx = cache.get(page_index)
    if ctx is not None:
        return ctx
    page = doc[page_index]
    visual_width, visual_height = page.get_size()
    ctx = _PageContext(
        page=page,
        textpage=page.get_textpage(),
        visual_width=visual_width,
        visual_height=visual_height,
        rotation=page.get_rotation(),
    )
    cache[page_index] = ctx
    return ctx


def _design_rect_to_raw(tb_field: TitleBlockField, ctx: _PageContext) -> Rect:
    """Rescales tb_field.rect from the page size it was drawn against to
    the file's actual current page size (same idea as SignatureBox/
    Rect.scaled_to elsewhere), then converts from visual/rotated space to
    pdfium's raw text-extraction space (see _visual_rect_to_raw)."""
    rect = tb_field.rect
    design_size = tb_field.page_size_at_design_time
    if (
        abs(design_size.width - ctx.visual_width) > 0.5
        or abs(design_size.height - ctx.visual_height) > 0.5
    ):
        rect = rect.scaled_to(design_size, type(design_size)(ctx.visual_width, ctx.visual_height))
    return _visual_rect_to_raw(rect, ctx.visual_width, ctx.visual_height, ctx.rotation)


def _visual_rect_to_raw(rect: Rect, visual_width: float, visual_height: float, rotation: int) -> Rect:
    """Undoes the page's /Rotate so a rect drawn in visual/display space
    (what render_page_to_qimage renders and coordinates.py maps mouse
    clicks to/from - i.e. what every TitleBlockField.rect is stored in)
    lands on the right spot in pdfium's raw, un-rotated text-extraction
    space. `rotation` is the page's own /Rotate value (0/90/180/270,
    clockwise). Derived from first principles (rotate-then-normalize) and
    verified against a real rotation=270 drawing - see the title-block
    check docs for the reasoning."""
    rotation = rotation % 360
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    if rotation == 90:
        raw_w = visual_height
        return Rect(x=raw_w - y - h, y=x, width=h, height=w)
    if rotation == 180:
        return Rect(x=visual_width - x - w, y=visual_height - y - h, width=w, height=h)
    if rotation == 270:
        raw_h = visual_width
        return Rect(x=y, y=raw_h - x - w, width=h, height=w)
    return rect  # rotation == 0 (or an unsupported value - treat as none)


# Circuit breaker only - not a real-world limit, just a bound on how far
# _extract_newest_revision_row walks upward before giving up, in case a
# malformed/unusual PDF never produces a fully-blank row.
_MAX_SCAN_ROWS = 200


def _extract_newest_revision_row(
    doc: "pdfium.PdfDocument",
    page_count: int,
    revision_fields: list[TitleBlockField],
    page_cache: dict[int, _PageContext],
) -> dict[TitleBlockFieldType, str]:
    """Each revision field's `rect` is drawn tightly around REV 0 (the
    bottom row, which never moves - see TitleBlockField's docstring).
    Walks upward in rect.height steps (row index 0 = REV 0, 1 = the row
    above it, ...) until a row comes back completely blank across every
    revision field, then picks whichever row within that filled block is
    actually the newest: highest REV number if a REV_NUMBER field was
    drawn, otherwise simply the last (topmost) filled row."""
    per_field_rows: dict[TitleBlockFieldType, list[str]] = {
        TitleBlockFieldType(f.field_type): [] for f in revision_fields
    }
    last_filled_index = -1
    for i in range(_MAX_SCAN_ROWS):
        any_non_blank = False
        for tb_field in revision_fields:
            page_index = tb_field.page_ref.resolve_index(page_count)
            field_type = TitleBlockFieldType(tb_field.field_type)
            if page_index is None:
                per_field_rows[field_type].append("")
                continue
            ctx = _get_page_context(doc, page_index, page_cache)
            # Row-shifting happens in the SAME visual/design space the rect
            # was drawn in, before converting to raw space - shifting the
            # already-converted raw rect would walk the wrong axis once
            # rotation swaps x/y.
            design_size = tb_field.page_size_at_design_time
            shifted = Rect(
                x=tb_field.rect.x,
                y=tb_field.rect.y + i * tb_field.rect.height,
                width=tb_field.rect.width,
                height=tb_field.rect.height,
            )
            shifted_field = TitleBlockField(
                field_id=tb_field.field_id,
                field_type=tb_field.field_type,
                page_ref=tb_field.page_ref,
                rect=shifted,
                page_size_at_design_time=design_size,
            )
            text = _extract_rect_text(ctx, _design_rect_to_raw(shifted_field, ctx))
            per_field_rows[field_type].append(text)
            if text:
                any_non_blank = True
        if not any_non_blank:
            break
        last_filled_index = i
    if last_filled_index < 0:
        return {}

    newest_index = _pick_newest_row_index(per_field_rows, last_filled_index)
    return {
        field_type: rows[newest_index]
        for field_type, rows in per_field_rows.items()
        if newest_index < len(rows) and rows[newest_index]
    }


def _pick_newest_row_index(
    per_field_rows: dict[TitleBlockFieldType, list[str]], last_filled_index: int
) -> int:
    rev_number_rows = per_field_rows.get(TitleBlockFieldType.REV_NUMBER)
    if rev_number_rows:
        best_index: Optional[int] = None
        best_value: Optional[int] = None
        for i, text in enumerate(rev_number_rows):
            digits = re.sub(r"[^\d]", "", text)
            if not digits:
                continue
            value = int(digits)
            if best_value is None or value > best_value:
                best_value, best_index = value, i
        if best_index is not None:
            return best_index
    # No REV_NUMBER field, or none of its rows parsed as a number - the
    # last filled row (topmost of the used block) is the newest.
    return last_filled_index


def _extract_rect_text(ctx: _PageContext, raw_rect: Rect) -> str:
    text = ctx.textpage.get_text_bounded(
        left=raw_rect.x,
        bottom=raw_rect.y,
        right=raw_rect.x + raw_rect.width,
        top=raw_rect.y + raw_rect.height,
    )
    return " ".join(text.split())  # collapse embedded newlines/extra whitespace


def _normalize(value: Optional[str]) -> str:
    return (value or "").strip().casefold()


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def validate_title_block(
    info: TitleBlockInfo,
    source_file: Path,
    sign_time: datetime,
    expected_ckd: Optional[str] = None,
    expected_app: Optional[str] = None,
) -> list[TitleBlockWarning]:
    warnings: list[TitleBlockWarning] = []

    drawing_no = info.get(TitleBlockFieldType.DRAWING_NO)
    if drawing_no and drawing_no not in source_file.stem:
        warnings.append(
            TitleBlockWarning(
                f"Drawing No. '{drawing_no}' does not appear in the file name.",
                (TitleBlockFieldType.DRAWING_NO,),
            )
        )

    title_rev = info.get(TitleBlockFieldType.TITLE_REV_NUMBER)
    rev_number = info.get(TitleBlockFieldType.REV_NUMBER)
    if title_rev and rev_number and _normalize(title_rev) != _normalize(rev_number):
        warnings.append(
            TitleBlockWarning(
                f"Title block REV ('{title_rev}') does not match the revision table's newest "
                f"REV ('{rev_number}').",
                (TitleBlockFieldType.TITLE_REV_NUMBER, TitleBlockFieldType.REV_NUMBER),
            )
        )

    chkd_name = info.get(TitleBlockFieldType.CHKD_NAME)
    rev_ckd = info.get(TitleBlockFieldType.REV_CKD)
    if chkd_name and rev_ckd and _normalize(chkd_name) != _normalize(rev_ckd):
        warnings.append(
            TitleBlockWarning(
                f"CHK'D ('{chkd_name}') does not match the latest revision's CKD ('{rev_ckd}').",
                (TitleBlockFieldType.CHKD_NAME, TitleBlockFieldType.REV_CKD),
            )
        )

    appd_name = info.get(TitleBlockFieldType.APPD_NAME)
    rev_app = info.get(TitleBlockFieldType.REV_APP)
    if appd_name and rev_app and _normalize(appd_name) != _normalize(rev_app):
        warnings.append(
            TitleBlockWarning(
                f"APP'D ('{appd_name}') does not match the latest revision's APP ('{rev_app}').",
                (TitleBlockFieldType.APPD_NAME, TitleBlockFieldType.REV_APP),
            )
        )

    drawn_name = info.get(TitleBlockFieldType.DRAWN_NAME)
    rev_by = info.get(TitleBlockFieldType.REV_BY)
    if drawn_name and rev_by and _normalize(drawn_name) != _normalize(rev_by):
        warnings.append(
            TitleBlockWarning(
                f"DRAWN ('{drawn_name}') does not match the latest revision's BY ('{rev_by}').",
                (TitleBlockFieldType.DRAWN_NAME, TitleBlockFieldType.REV_BY),
            )
        )

    if expected_ckd and chkd_name and _normalize(chkd_name) != _normalize(expected_ckd):
        warnings.append(
            TitleBlockWarning(
                f"CHK'D ('{chkd_name}') does not match the expected value ('{expected_ckd}').",
                (TitleBlockFieldType.CHKD_NAME,),
            )
        )
    if expected_app and appd_name and _normalize(appd_name) != _normalize(expected_app):
        warnings.append(
            TitleBlockWarning(
                f"APP'D ('{appd_name}') does not match the expected value ('{expected_app}').",
                (TitleBlockFieldType.APPD_NAME,),
            )
        )

    for field_type in (
        TitleBlockFieldType.DRAWN_DATE,
        TitleBlockFieldType.CHKD_DATE,
        TitleBlockFieldType.APPD_DATE,
        TitleBlockFieldType.REV_DATE,
    ):
        raw = info.get(field_type)
        parsed = _parse_date(raw)
        if parsed and parsed.date() > sign_time.date():
            warnings.append(
                TitleBlockWarning(
                    f"{field_type.value.replace('_', ' ').title()} ('{raw}') is later than the "
                    "signing date.",
                    (field_type,),
                )
            )

    warnings.extend(_check_date_order(info))
    return warnings


def _check_date_order(info: TitleBlockInfo) -> list[TitleBlockWarning]:
    """DRAWN date <= CHK'D date <= APP'D date - each pair checked
    independently (not chained) so a missing middle date (no CHK'D date
    drawn on the template) doesn't hide a DRAWN-after-APP'D mismatch."""
    warnings: list[TitleBlockWarning] = []
    drawn = _parse_date(info.get(TitleBlockFieldType.DRAWN_DATE))
    chkd = _parse_date(info.get(TitleBlockFieldType.CHKD_DATE))
    appd = _parse_date(info.get(TitleBlockFieldType.APPD_DATE))

    if drawn and chkd and drawn.date() > chkd.date():
        warnings.append(
            TitleBlockWarning(
                f"DRAWN date ({drawn.date()}) is later than CHK'D date ({chkd.date()}).",
                (TitleBlockFieldType.DRAWN_DATE, TitleBlockFieldType.CHKD_DATE),
            )
        )
    if chkd and appd and chkd.date() > appd.date():
        warnings.append(
            TitleBlockWarning(
                f"CHK'D date ({chkd.date()}) is later than APP'D date ({appd.date()}).",
                (TitleBlockFieldType.CHKD_DATE, TitleBlockFieldType.APPD_DATE),
            )
        )
    if drawn and appd and drawn.date() > appd.date():
        warnings.append(
            TitleBlockWarning(
                f"DRAWN date ({drawn.date()}) is later than APP'D date ({appd.date()}).",
                (TitleBlockFieldType.DRAWN_DATE, TitleBlockFieldType.APPD_DATE),
            )
        )
    return warnings
