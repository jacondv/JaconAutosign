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

    def to_dict(self) -> dict:
        return {
            "image_path": self.image_path,
            "show_text": self.show_text,
            "text_template": self.text_template,
        }

    @staticmethod
    def from_dict(data: dict) -> "Appearance":
        return Appearance(
            image_path=data.get("image_path"),
            show_text=data.get("show_text", False),
            text_template=data.get("text_template"),
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


@dataclass
class Template:
    template_id: str
    template_name: str
    created_at: str
    source_sample_file: Optional[str] = None
    signature_boxes: list[SignatureBox] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "created_at": self.created_at,
            "source_sample_file": self.source_sample_file,
            "signature_boxes": [box.to_dict() for box in self.signature_boxes],
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
        )
