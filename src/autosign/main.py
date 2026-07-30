"""AutoSign application entry point."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from .config import settings_file
from .services import SettingsService
from .ui import theme
from .ui.main_window import MainWindow

_ICON_PATH = Path(__file__).parent / "ui" / "asset" / "AutoSign.ico"

# Explorer launches AutoSign once per selected file (Windows doesn't
# reliably honor a "run once with all files" registry hint for per-
# extension verbs - see register_context_menu.ps1), which used to open one
# window per file. A single-instance handoff over a local socket is what
# actually guarantees one window: every launch but the first hands its
# file paths to the first and exits instead of opening its own window.
_SINGLE_INSTANCE_SERVER = "AutoSign-SingleInstance"
_PATH_SEP = "\n"
_CONNECT_TIMEOUT_MS = 300
_RETRY_ATTEMPTS = 5
_RETRY_DELAY_S = 0.3


def _forward_to_running_instance(paths: list[Path]) -> bool:
    """True if another AutoSign was already running and got handed these
    paths (caller should exit without creating a window)."""
    socket = QLocalSocket()
    socket.connectToServer(_SINGLE_INSTANCE_SERVER)
    if not socket.waitForConnected(_CONNECT_TIMEOUT_MS):
        return False
    payload = _PATH_SEP.join(str(p) for p in paths).encode("utf-8")
    socket.write(payload)
    socket.waitForBytesWritten(500)
    socket.disconnectFromServer()
    return True


class _SingleInstanceServer:
    """Claims the local-socket name immediately (cheap) so a launch that
    starts moments later reliably finds it - before doing any of the slow
    work of building the main window. Handoffs that arrive before the
    window exists yet are queued and flushed once attach_window() runs."""

    def __init__(self) -> None:
        self._server = QLocalServer()
        QLocalServer.removeServer(_SINGLE_INSTANCE_SERVER)  # clears a stale handle from a crashed run
        self.is_listening = self._server.listen(_SINGLE_INSTANCE_SERVER)
        self._window: MainWindow | None = None
        self._pending: list[Path] = []
        self._server.newConnection.connect(self._on_new_connection)

    def attach_window(self, window: MainWindow) -> None:
        self._window = window
        if self._pending:
            window.open_startup_paths(self._pending)
            self._pending = []

    def _on_new_connection(self) -> None:
        conn = self._server.nextPendingConnection()
        if conn is None:
            return
        buffer = bytearray()
        conn.readyRead.connect(lambda: buffer.extend(bytes(conn.readAll())))

        def _on_disconnected() -> None:
            paths = [Path(p) for p in buffer.decode("utf-8").split(_PATH_SEP) if p]
            if self._window is not None:
                self._window.open_startup_paths(paths)
            else:
                self._pending.extend(paths)
            conn.deleteLater()

        conn.disconnected.connect(_on_disconnected)


def main() -> int:
    # Windows Explorer's "Open with AutoSign" passes the selected file(s) as
    # arguments (see register_context_menu.ps1).
    startup_paths = [Path(arg) for arg in sys.argv[1:]]

    app = QApplication(sys.argv)
    app.setApplicationName("AutoSign")
    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))
    # Fusion is a style Qt paints itself rather than delegating to the OS -
    # combined with the app-wide stylesheet below, this is what keeps every
    # color independent of the Windows light/dark theme (see ui/theme.py).
    app.setStyle("Fusion")

    if _forward_to_running_instance(startup_paths):
        return 0

    instance = _SingleInstanceServer()
    if not instance.is_listening:
        # Lost the race to claim the server name to another launch that's
        # still starting up - keep retrying the handoff briefly rather than
        # opening a second window.
        for _ in range(_RETRY_ATTEMPTS):
            time.sleep(_RETRY_DELAY_S)
            if _forward_to_running_instance(startup_paths):
                return 0
        # Gave up: fall through and open a normal (unlinked) window rather
        # than failing to start.

    initial_settings = SettingsService(settings_file()).load()
    app.setStyleSheet(theme.stylesheet(initial_settings.theme_mode))

    window = MainWindow(initial_theme=initial_settings.theme_mode, startup_paths=startup_paths)
    instance.attach_window(window)
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
