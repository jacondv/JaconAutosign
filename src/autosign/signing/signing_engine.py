"""Apply a Template to a specific PDF file and sign it with pyHanko (PAdES, PKCS#12).

Multiple signature boxes in the same file (including an "all pages" box
spread across several pages) are signed one at a time via incremental
update, so each later signature doesn't invalidate the ones already applied
to the same file (see docs/02-yeu-cau-phi-chuc-nang.md section 2).

Appearance: hand-signature image on the left, signer name + sign date on the
right - matching Acrobat's default layout when signing with a certificate
(see appearance_compose.py).
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pyhanko import stamp
from pyhanko.pdf_utils import images
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import fields, signers

from ..models import Rect, SignatureBox, SignPageScope, Template
from .appearance_compose import build_text_lines, compose_appearance_image
from .certificate_provider import CertificateProvider

if TYPE_CHECKING:
    # Type-only import to avoid a circular import at runtime:
    # services.batch_sign_service imports SigningEngine from this package,
    # while signing_engine needs PdfInfo from services just to annotate a
    # parameter type.
    from ..services.pdf_inspect_service import PdfInfo


class SigningError(Exception):
    """Error signing one specific file (missing page, unreadable signature
    image...). BatchSignService catches this per file so it doesn't abort
    the whole batch.
    """


class SigningEngine:
    def __init__(
        self,
        cert_provider: CertificateProvider,
        signer_display_name: str = "",
    ):
        self._cert_provider = cert_provider
        self._signer_display_name = signer_display_name

    def sign_file(
        self,
        pdf_info: PdfInfo,
        template: Template,
        output_path: Path,
        page_scope: SignPageScope = SignPageScope.ALL,
        current_page_index: int | None = None,
    ) -> None:
        boxes = template.signature_boxes
        if not boxes:
            raise SigningError("Template has no signature boxes.")

        page_indices = page_scope.resolve_indices(pdf_info.page_count, current_page_index)
        if not page_indices:
            raise SigningError(
                f"Missing page: '{page_scope.describe()}' does not resolve to a valid page "
                f"in this file ({pdf_info.page_count} page(s))."
            )

        # Local import to avoid a circular import (services imports this
        # module via BatchSignService -> SigningEngine, at package-init
        # time; this only needs to resolve once signing actually runs).
        from ..services.signature_status_service import get_signed_pages

        already_signed = get_signed_pages(pdf_info.path)
        pages_to_sign = [i for i in page_indices if i not in already_signed]
        sign_time = datetime.now().astimezone()

        try:
            pdf_bytes = pdf_info.path.read_bytes()
            for box_num, box in enumerate(boxes, start=1):
                for page_index in pages_to_sign:
                    field_name = f"Sig{box_num}_p{page_index + 1}"
                    pdf_bytes = self._apply_one_field(
                        pdf_bytes, pdf_info, box, page_index, field_name, sign_time
                    )
        except SigningError:
            raise
        except Exception as exc:  # pyHanko/PIL can raise several different error types
            raise SigningError(f"Signing error: {exc}") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file then atomically replace - this can be the
        # source file itself (overwrite-original output mode) or a
        # previously-signed output being extended with another page's
        # signature, so a plain truncate-write risks leaving a corrupt file
        # behind if interrupted midway.
        tmp_path = output_path.with_name(output_path.name + ".autosign-tmp")
        tmp_path.write_bytes(pdf_bytes)
        try:
            os.replace(tmp_path, output_path)
        except OSError as exc:
            tmp_path.unlink(missing_ok=True)
            raise SigningError(
                f"Could not write {output_path.name} - it may be open in another "
                f"program (e.g. a PDF viewer). Close it and try signing again. ({exc})"
            ) from exc

    def _apply_one_field(
        self,
        pdf_bytes: bytes,
        pdf_info: PdfInfo,
        box: SignatureBox,
        page_index: int,
        field_name: str,
        sign_time: datetime,
    ) -> bytes:
        actual_size = pdf_info.page_size(page_index)
        rect = box.rect
        if actual_size.differs_from(box.page_size_at_design_time):
            rect = rect.scaled_to(box.page_size_at_design_time, actual_size)

        pdf_box = (rect.x, rect.y, rect.x + rect.width, rect.y + rect.height)
        field_spec = fields.SigFieldSpec(field_name, box=pdf_box, on_page=page_index)

        pdf_signer = signers.PdfSigner(
            signers.PdfSignatureMetadata(field_name=field_name),
            signer=self._cert_provider.get_signer(),
            stamp_style=self._build_stamp_style(box, rect, sign_time),
            new_field_spec=field_spec,
        )

        # strict=False: some PDFs (e.g. exported from Word or older Foxit/
        # Acrobat versions) use hybrid cross-reference sections (both an
        # xref table and an xref stream). pyHanko's default strict reader
        # refuses to sign those ("hybrid cross-reference... while hybrid
        # xrefs are disabled") even though they're a legal, common PDF
        # structure - relax to non-strict so those files sign normally.
        writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes), strict=False)
        out_buffer = io.BytesIO()
        pdf_signer.sign_pdf(writer, output=out_buffer)
        return out_buffer.getvalue()

    def _build_stamp_style(
        self, box: SignatureBox, rect: Rect, sign_time: datetime
    ) -> stamp.BaseStampStyle:
        text_lines = build_text_lines(box.appearance, self._signer_display_name, sign_time)
        composed = compose_appearance_image(
            box.appearance.image_path,
            text_lines,
            rect.width,
            rect.height,
            box.appearance.font_size,
            box.appearance.image_scale,
            box.appearance.image_pos,
            box.appearance.text_pos,
            box.appearance.image_size,
            box.appearance.text_size,
        )
        return stamp.StaticStampStyle(
            background=images.PdfImage(composed), border_width=0, background_opacity=1.0
        )
