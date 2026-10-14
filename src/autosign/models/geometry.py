"""PDF coordinates (points, bottom-left origin) - not pixels."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}

    @staticmethod
    def from_dict(data: dict) -> "Rect":
        return Rect(x=data["x"], y=data["y"], width=data["width"], height=data["height"])

    def scaled_to(self, from_size: "PageSize", to_size: "PageSize") -> "Rect":
        """Rescale coordinates when the actual page size differs from the size at template design time."""
        if from_size.width <= 0 or from_size.height <= 0:
            return self
        scale_x = to_size.width / from_size.width
        scale_y = to_size.height / from_size.height
        return Rect(
            x=self.x * scale_x,
            y=self.y * scale_y,
            width=self.width * scale_x,
            height=self.height * scale_y,
        )

    def to_raw_page_space(self, visual_width: float, visual_height: float, rotation: int) -> "Rect":
        """Undoes the page's /Rotate so a rect drawn in visual/display space
        (what render_page_to_qimage renders and ui/coordinates.py maps mouse
        clicks to/from) lands on the right spot in the PDF's raw, un-rotated
        default user space - the space both pdfium's get_text_bounded() and
        a PDF annotation's /Rect are defined in. A viewer rotates the whole
        page (content + annotations) by /Rotate for display, so any rect
        meant to land at the on-screen position the user drew/clicked must
        first be converted back through the inverse of that rotation.
        `rotation` is the page's own /Rotate value (0/90/180/270, clockwise).
        Derived from first principles (rotate-then-normalize) and verified
        against a real rotation=270 drawing - see the title-block check
        docs for the reasoning (first used there, now shared with signing)."""
        rotation = rotation % 360
        x, y, w, h = self.x, self.y, self.width, self.height
        if rotation == 90:
            raw_w = visual_height
            return Rect(x=raw_w - y - h, y=x, width=h, height=w)
        if rotation == 180:
            return Rect(x=visual_width - x - w, y=visual_height - y - h, width=w, height=h)
        if rotation == 270:
            raw_h = visual_width
            return Rect(x=y, y=raw_h - x - w, width=h, height=w)
        return self  # rotation == 0 (or an unsupported value - treat as none)


@dataclass(frozen=True)
class PageSize:
    width: float
    height: float
    rotation: int = 0

    def to_dict(self) -> dict:
        return {"width": self.width, "height": self.height, "rotation": self.rotation}

    @staticmethod
    def from_dict(data: dict) -> "PageSize":
        return PageSize(
            width=data["width"], height=data["height"], rotation=data.get("rotation", 0)
        )

    def differs_from(self, other: "PageSize", tolerance: float = 0.5) -> bool:
        return (
            abs(self.width - other.width) > tolerance
            or abs(self.height - other.height) > tolerance
        )
