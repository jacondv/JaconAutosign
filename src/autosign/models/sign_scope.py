"""Which page(s) of a file get signed - chosen at sign time (the left
panel), not baked into the template. Applies uniformly to every signature
box in the template for that run.
"""
from __future__ import annotations

from enum import Enum


class SignPageScope(str, Enum):
    CURRENT = "current"
    FIRST = "first"
    LAST = "last"
    ALL = "all"

    def resolve_indices(
        self, page_count: int, current_page_index: int | None = None
    ) -> list[int]:
        """0-based page indices this scope targets in a file with
        `page_count` pages (empty if not applicable, e.g. CURRENT with no
        known page index, or a page index out of range)."""
        if page_count <= 0:
            return []
        if self == SignPageScope.FIRST:
            return [0]
        if self == SignPageScope.LAST:
            return [page_count - 1]
        if self == SignPageScope.ALL:
            return list(range(page_count))
        if self == SignPageScope.CURRENT:
            if current_page_index is None or not (0 <= current_page_index < page_count):
                return []
            return [current_page_index]
        raise ValueError(f"Unsupported SignPageScope: {self}")

    def describe(self) -> str:
        return _DESCRIPTIONS[self]


_DESCRIPTIONS = {
    SignPageScope.CURRENT: "Current page",
    SignPageScope.FIRST: "First page",
    SignPageScope.LAST: "Last page",
    SignPageScope.ALL: "All pages",
}
