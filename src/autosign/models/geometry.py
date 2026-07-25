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
