"""AutoSign application entry point."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .config import settings_file
from .services import SettingsService
from .ui import theme
from .ui.main_window import MainWindow

_ICON_PATH = Path(__file__).parent / "ui" / "asset" / "AutoSign.ico"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AutoSign")
    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))
    # Fusion is a style Qt paints itself rather than delegating to the OS -
    # combined with the app-wide stylesheet below, this is what keeps every
    # color independent of the Windows light/dark theme (see ui/theme.py).
    app.setStyle("Fusion")

    initial_settings = SettingsService(settings_file()).load()
    app.setStyleSheet(theme.stylesheet(initial_settings.theme_mode))

    # Windows Explorer's "Open with AutoSign" passes every selected file as
    # its own argument (see register_context_menu.ps1's MultiSelectModel).
    startup_paths = [Path(arg) for arg in sys.argv[1:]]

    window = MainWindow(initial_theme=initial_settings.theme_mode, startup_paths=startup_paths)
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
