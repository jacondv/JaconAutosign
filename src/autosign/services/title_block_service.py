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
            fixed_fields = [f for f in template.title_block_fields if not f.field_type.is_revision_row]
            revision_fields = [f for f in template.title_block_fields if f.field_type.is_revision_row]
            for tb_field in fixed_fields:
                page_index = tb_field.page_ref.resolve_index(page_count)
                if page_index is None:
                    continue
                text = _extract_rect_text(doc, page_index, tb_field.rect)
                if text:
                    values[TitleBlockFieldType(tb_field.field_type)] = text
            if revision_fields:
                values.update(_extract_newest_revision_row(doc, page_count, revision_fields))
        finally:
            doc.close()
    return TitleBlockInfo(values=values)


def _extract_newest_revision_row(
    doc: "pdfium.PdfDocument", page_count: int, revision_fields: list[TitleBlockField]
) -> dict[TitleBlockFieldType, str]:
    """Each revision field's `rect` marks row slot #1 (the topmost slot of
    the table's fixed capacity) - which may be blank, since a new revision
    is inserted directly above the previously-newest one rather than always
    landing in slot #1 (see TitleBlockField's docstring). Reads every slot
    for every field, then picks whichever row is actually the newest -
    highest REV number if a REV_NUMBER field was drawn, otherwise the
    first (topmost) row with any non-blank text, which is where a new
    revision lands per that same insertion rule."""
    per_field_rows: dict[TitleBlockFieldType, list[str]] = {}
    max_rows_seen = 0
    for tb_field in revision_fields:
        page_index = tb_field.page_ref.resolve_index(page_count)
        if page_index is None:
            continue
        max_rows = max(1, tb_field.max_rows)
        row_height = tb_field.row_height_pt or 0.0
        rows_text = []
        for i in range(max_rows):
            row_rect = Rect(
                x=tb_field.rect.x,
                y=tb_field.rect.y - i * row_height,
                width=tb_field.rect.width,
                height=tb_field.rect.height,
            )
            rows_text.append(_extract_rect_text(doc, page_index, row_rect))
        per_field_rows[TitleBlockFieldType(tb_field.field_type)] = rows_text
        max_rows_seen = max(max_rows_seen, len(rows_text))

    newest_index = _pick_newest_row_index(per_field_rows, max_rows_seen)
    if newest_index is None:
        return {}
    return {
        field_type: rows[newest_index]
        for field_type, rows in per_field_rows.items()
        if newest_index < len(rows) and rows[newest_index]
    }


def _pick_newest_row_index(
    per_field_rows: dict[TitleBlockFieldType, list[str]], max_rows_seen: int
) -> Optional[int]:
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
    # No REV_NUMBER field, or none of its rows parsed as a number - fall
    # back to the topmost row with anything in it, which is where a new
    # revision lands (see _extract_newest_revision_row's docstring).
    for i in range(max_rows_seen):
        for rows in per_field_rows.values():
            if i < len(rows) and rows[i]:
                return i
    return None


def _extract_rect_text(doc: "pdfium.PdfDocument", page_index: int, rect: Rect) -> str:
    page = doc[page_index]
    try:
        textpage = page.get_textpage()
        try:
            text = textpage.get_text_bounded(
                left=rect.x, bottom=rect.y, right=rect.x + rect.width, top=rect.y + rect.height
            )
        finally:
            textpage.close()
    finally:
        page.close()
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

    return warnings
