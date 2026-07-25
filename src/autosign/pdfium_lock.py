"""PDFium (used via pypdfium2) is not thread-safe: calling it concurrently
from two threads (e.g. the background signing worker inspecting a PDF while
the main thread renders a preview) can crash the process with a native
access violation (WinError 0xc000001d). All PDFium calls - both in
PdfInspectService and in the preview renderer - must go through this single
lock so at most one thread touches the library at a time.
"""
from __future__ import annotations

import threading

PDFIUM_LOCK = threading.Lock()
