"""Encrypt/decrypt via Windows DPAPI (CryptProtectData/CryptUnprotectData),
tied to the currently logged-in Windows account - only that account, on that
same machine, can decrypt it again. Used for the opt-in "remember password"
feature without ever storing plaintext on disk, per docs/02-yeu-cau-phi-chuc-nang.md
section 1.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


class DpapiUnavailableError(Exception):
    """DPAPI is only available on Windows, or decryption failed (different machine/account)."""


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _require_windows() -> None:
    if not sys.platform.startswith("win"):
        raise DpapiUnavailableError("DPAPI is only available on Windows.")


def _to_blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buf = ctypes.create_string_buffer(data, len(data))
    blob = _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    return blob, buf  # also return buf so the caller keeps it alive, avoiding early GC


def _run(func_name: str, data: bytes) -> bytes:
    _require_windows()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_blob, _keep_alive = _to_blob(data)
    out_blob = _DataBlob()
    func = getattr(crypt32, func_name)
    ok = func(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    )
    if not ok:
        raise DpapiUnavailableError(f"{func_name} failed.")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def protect(data: bytes) -> bytes:
    return _run("CryptProtectData", data)


def unprotect(data: bytes) -> bytes:
    return _run("CryptUnprotectData", data)
