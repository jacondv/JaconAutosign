"""Detect which pages of a PDF already carry a filled-in digital signature
field - used to show a "Signed" badge for the page currently on screen. Pure
pyHanko structural parsing; this has nothing to do with whether Autosign
itself produced the signature.
"""
from __future__ import annotations

from pathlib import Path

from pyhanko.pdf_utils.generic import IndirectObject, Reference
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.fields import enumerate_sig_fields


def get_signed_pages(path: Path) -> set[int]:
    """0-based indices of pages that contain at least one signed field.
    Best-effort: any file that can't be parsed just reports no signed pages
    rather than raising, since this is only used for a UI badge."""
    try:
        with open(path, "rb") as f:
            reader = PdfFileReader(f)
            page_index_by_ref = _page_index_by_ref(reader)
            signed_pages: set[int] = set()
            for _name, _value, field_ref in enumerate_sig_fields(reader, filled_status=True):
                page_ref = field_ref.get_object().get("/P")
                if isinstance(page_ref, IndirectObject):
                    index = page_index_by_ref.get(page_ref.reference)
                    if index is not None:
                        signed_pages.add(index)
            return signed_pages
    except Exception:
        return set()


def _page_index_by_ref(reader: PdfFileReader) -> dict[Reference, int]:
    refs: list[Reference] = []
    _flatten_page_tree(reader.root["/Pages"], refs)
    return {ref: i for i, ref in enumerate(refs)}


def _flatten_page_tree(node: IndirectObject, refs: list[Reference]) -> None:
    obj = node.get_object()
    if obj.get("/Type") == "/Pages":
        for kid in obj["/Kids"]:
            _flatten_page_tree(kid, refs)
    else:
        refs.append(node.reference)
