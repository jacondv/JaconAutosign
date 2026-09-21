"""Template: signature box layout, reused across a batch of same-layout PDF files."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .geometry import PageSize, Rect


class PageRefType(str, Enum):
    ABSOLUTE = "absolute"
    FIRST = "first"
    LAST = "last"
    ALL = "all"


@dataclass(frozen=True)
class PageRef:
    type: PageRefType
    page_number: Optional[int] = None  # 1-based, only used when type == ABSOLUTE

    def resolve_indices(self, page_count: int) -> list[int]:
        """The 0-based page indices in the actual file that this signature
        box applies to (empty if not valid, e.g. the file is missing that page)."""
        if page_count <= 0:
            return []
        ref_type = PageRefType(self.type)
        if ref_type == PageRefType.FIRST:
            return [0]
        if ref_type == PageRefType.LAST:
            return [page_count - 1]
        if ref_type == PageRefType.ALL:
            return list(range(page_count))
        if ref_type == PageRefType.ABSOLUTE:
            if not self.page_number or self.page_number < 1 or self.page_number > page_count:
                return []
            return [self.page_number - 1]
        raise ValueError(f"Unsupported PageRefType: {ref_type}")

    def resolve_index(self, page_count: int) -> Optional[int]:
        """Convenience for the single-page cases (not usable for ALL)."""
        indices = self.resolve_indices(page_count)
        return indices[0] if len(indices) == 1 else None

    def describe(self) -> str:
        ref_type = PageRefType(self.type)
        if ref_type == PageRefType.ABSOLUTE:
            return f"Page {self.page_number}"
        if ref_type == PageRefType.FIRST:
            return "First page"
        if ref_type == PageRefType.ALL:
            return "All pages"
        return "Last page"

    def to_dict(self) -> dict:
        # self.type can arrive as a plain str (e.g. round-tripped through a
        # Qt QVariant, which drops the Enum subtype) - re-coerce to
        # PageRefType() so .value is always available.
        ref_type = PageRefType(self.type)
        data = {"type": ref_type.value}
        if ref_type == PageRefType.ABSOLUTE:
            data["page_number"] = self.page_number
        return data

    @staticmethod
    def from_dict(data: dict) -> "PageRef":
        return PageRef(type=PageRefType(data["type"]), page_number=data.get("page_number"))


@dataclass(frozen=True)
class Appearance:
    image_path: Optional[str] = None
    show_text: bool = False
    text_template: Optional[str] = None
    image_scale: float = 1.0
    # (x_frac, y_frac) within the box, 0..1 - image_pos is the image's
    # CENTER, text_pos is the text block's TOP-LEFT corner. None means "not
    # positioned independently yet": both default to the classic image-left
    # / text-right split (see appearance_compose.py), so existing templates
    # render exactly as before until someone drags either one.
    image_pos: Optional[tuple] = None
    text_pos: Optional[tuple] = None
    # (w_frac, h_frac) bounding box within the box, 0..1 - set by dragging a
    # resize handle in the box editor. The image fits (aspect-preserved)
    # within image_size; text_size is the wrap width/available height text
    # auto-shrinks to fit. None means "not resized independently yet",
    # falling back to image_scale / the classic split, same as image_pos.
    image_size: Optional[tuple] = None
    text_size: Optional[tuple] = None
    # Font size in pt for the text, set per-box in the box editor.
    # None/0 = auto (shrinks to fit the text's box).
    font_size: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "image_path": self.image_path,
            "show_text": self.show_text,
            "text_template": self.text_template,
            "image_scale": self.image_scale,
            "image_pos": list(self.image_pos) if self.image_pos else None,
            "text_pos": list(self.text_pos) if self.text_pos else None,
            "image_size": list(self.image_size) if self.image_size else None,
            "text_size": list(self.text_size) if self.text_size else None,
            "font_size": self.font_size,
        }

    @staticmethod
    def from_dict(data: dict) -> "Appearance":
        image_pos = data.get("image_pos")
        text_pos = data.get("text_pos")
        image_size = data.get("image_size")
        text_size = data.get("text_size")
        return Appearance(
            image_path=data.get("image_path"),
            show_text=data.get("show_text", False),
            text_template=data.get("text_template"),
            image_scale=data.get("image_scale", 1.0),
            image_pos=tuple(image_pos) if image_pos else None,
            text_pos=tuple(text_pos) if text_pos else None,
            image_size=tuple(image_size) if image_size else None,
            text_size=tuple(text_size) if text_size else None,
            font_size=data.get("font_size") or None,
        )


@dataclass
class SignatureBox:
    box_id: str
    label: str
    page_ref: PageRef
    rect: Rect
    page_size_at_design_time: PageSize
    appearance: Appearance = field(default_factory=Appearance)

    def to_dict(self) -> dict:
        return {
            "box_id": self.box_id,
            "label": self.label,
            "page_ref": self.page_ref.to_dict(),
            "rect": self.rect.to_dict(),
            "page_size_at_design_time": self.page_size_at_design_time.to_dict(),
            "appearance": self.appearance.to_dict(),
        }

    @staticmethod
    def from_dict(data: dict) -> "SignatureBox":
        return SignatureBox(
            box_id=data["box_id"],
            label=data["label"],
            page_ref=PageRef.from_dict(data["page_ref"]),
            rect=Rect.from_dict(data["rect"]),
            page_size_at_design_time=PageSize.from_dict(data["page_size_at_design_time"]),
            appearance=Appearance.from_dict(data.get("appearance", {})),
        )


class TitleBlockFieldType(str, Enum):
    """What a title-block field represents - drives how validate_title_block()
    cross-checks the extracted values (see services/title_block_service.py)."""

    DRAWING_NO = "drawing_no"
    DRAWN_NAME = "drawn_name"
    DRAWN_DATE = "drawn_date"
    CHKD_NAME = "chkd_name"
    CHKD_DATE = "chkd_date"
    APPD_NAME = "appd_name"
    APPD_DATE = "appd_date"
    REV_NUMBER = "rev_number"
    REV_BY = "rev_by"
    REV_CKD = "rev_ckd"
    REV_APP = "rev_app"
    REV_DATE = "rev_date"

    @property
    def is_revision_row(self) -> bool:
        """Revision-table fields sit in a fixed-capacity table (a bounded
        number of row slots) where a new revision is inserted directly above
        the previously-newest one, so the newest row's position SHIFTS as
        more revisions are added (unlike a fixed field) - see
        TitleBlockField.row_height_pt/max_rows and
        title_block_service._extract_newest_revision_row, which scans every
        slot and picks the actual newest one instead of assuming a fixed
        position."""
        return self in (
            TitleBlockFieldType.REV_NUMBER,
            TitleBlockFieldType.REV_BY,
            TitleBlockFieldType.REV_CKD,
            TitleBlockFieldType.REV_APP,
            TitleBlockFieldType.REV_DATE,
        )


DEFAULT_REVISION_MAX_ROWS = 10


@dataclass
class TitleBlockField:
    """A rectangle in the title block to read text from and validate - see
    docs on the title-block-check feature. `rect` is drawn once at template
    design time, same as a SignatureBox's rect.

    For a fixed field (Drawing No., DRAWN/CHK'D/APP'D) `rect` always points
    at the same spot. For a revision-row field (field_type.is_revision_row),
    `rect` points at row slot #1 - the TOPMOST slot of the table's fixed
    capacity (`max_rows` slots, `row_height_pt` apart) - which may well be
    blank on a file with fewer revisions than that capacity, since newer
    revisions get inserted directly above the older block rather than
    always landing in slot #1. Extraction scans all `max_rows` slots below
    `rect` and picks the actual newest row (see title_block_service.py)
    instead of assuming slot #1 is always the one that's filled.
    """

    field_id: str
    field_type: TitleBlockFieldType
    page_ref: PageRef
    rect: Rect
    page_size_at_design_time: PageSize
    row_height_pt: Optional[float] = None  # revision-row fields only
    max_rows: int = DEFAULT_REVISION_MAX_ROWS  # revision-row fields only

    def to_dict(self) -> dict:
        return {
            "field_id": self.field_id,
            "field_type": TitleBlockFieldType(self.field_type).value,
            "page_ref": self.page_ref.to_dict(),
            "rect": self.rect.to_dict(),
            "page_size_at_design_time": self.page_size_at_design_time.to_dict(),
            "row_height_pt": self.row_height_pt,
            "max_rows": self.max_rows,
        }

    @staticmethod
    def from_dict(data: dict) -> "TitleBlockField":
        return TitleBlockField(
            field_id=data["field_id"],
            field_type=TitleBlockFieldType(data["field_type"]),
            page_ref=PageRef.from_dict(data["page_ref"]),
            rect=Rect.from_dict(data["rect"]),
            page_size_at_design_time=PageSize.from_dict(data["page_size_at_design_time"]),
            row_height_pt=data.get("row_height_pt"),
            max_rows=data.get("max_rows", DEFAULT_REVISION_MAX_ROWS),
        )


@dataclass
class Template:
    template_id: str
    template_name: str
    created_at: str
    source_sample_file: Optional[str] = None
    signature_boxes: list[SignatureBox] = field(default_factory=list)
    title_block_fields: list[TitleBlockField] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "created_at": self.created_at,
            "source_sample_file": self.source_sample_file,
            "signature_boxes": [box.to_dict() for box in self.signature_boxes],
            "title_block_fields": [f.to_dict() for f in self.title_block_fields],
        }

    @staticmethod
    def from_dict(data: dict) -> "Template":
        return Template(
            template_id=data["template_id"],
            template_name=data["template_name"],
            created_at=data["created_at"],
            source_sample_file=data.get("source_sample_file"),
            signature_boxes=[
                SignatureBox.from_dict(b) for b in data.get("signature_boxes", [])
            ],
            title_block_fields=[
                TitleBlockField.from_dict(f) for f in data.get("title_block_fields", [])
            ],
        )
