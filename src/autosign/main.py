"""Autosign application entry point."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .config import settings_file
from .services import SettingsService
from .ui import theme
from .ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Autosign")
    # Fusion is a style Qt paints itself rather than delegating to the OS -
    # combined with the app-wide stylesheet below, this is what keeps every
    # color independent of the Windows light/dark theme (see ui/theme.py).
    app.setStyle("Fusion")

    initial_settings = SettingsService(settings_file()).load()
    app.setStyleSheet(theme.stylesheet(initial_settings.theme_mode))

    window = MainWindow(initial_theme=initial_settings.theme_mode)
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
