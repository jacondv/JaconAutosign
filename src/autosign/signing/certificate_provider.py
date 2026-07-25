"""Source of the Digital ID used for signing. MVP only supports PKCS#12
(.p12/.pfx); the interface allows adding more sources later (Windows
Certificate Store, PKCS#11) without changing the Signing Engine/UI.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pyhanko.sign import signers


@dataclass(frozen=True)
class CertificateInfo:
    subject: str
    issuer: str
    not_valid_after: datetime
    common_name: str | None = None

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.not_valid_after

    def days_until_expiry(self) -> int:
        return (self.not_valid_after - datetime.now(timezone.utc)).days


class CertificateLoadError(Exception):
    """Wrong password, or the certificate file is corrupted/invalid."""


class CertificateProvider(ABC):
    @abstractmethod
    def get_signer(self) -> signers.SimpleSigner:
        """Return a signer ready to hand to pyHanko's PdfSigner."""

    @abstractmethod
    def get_info(self) -> CertificateInfo:
        """Info shown to the user to confirm before running a batch."""


class Pkcs12CertificateProvider(CertificateProvider):
    """Reads a Digital ID from a PKCS#12 file (.p12 or .pfx - same format)."""

    def __init__(self, pfx_path: Path, passphrase: str):
        try:
            signer = signers.SimpleSigner.load_pkcs12(
                pfx_file=str(pfx_path), passphrase=passphrase.encode("utf-8")
            )
        except Exception as exc:  # pyHanko can raise ValueError/OSError depending on the failure
            raise CertificateLoadError(f"Could not read certificate file: {exc}") from exc

        if signer is None:
            raise CertificateLoadError("Wrong password, or an invalid certificate file.")
        self._signer = signer

    def get_signer(self) -> signers.SimpleSigner:
        return self._signer

    def get_info(self) -> CertificateInfo:
        cert = self._signer.signing_cert
        return CertificateInfo(
            subject=cert.subject.human_friendly,
            issuer=cert.issuer.human_friendly,
            not_valid_after=cert.not_valid_after,
            common_name=cert.subject.native.get("common_name"),
        )
