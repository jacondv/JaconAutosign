"""Paths for user data (templates, settings) - kept separate from the install directory."""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "Autosign"


def app_data_dir() -> Path:
    """Per-user data directory: %APPDATA%\\Autosign on Windows."""
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".autosign"
    path = root / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def templates_dir() -> Path:
    path = app_data_dir() / "templates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return app_data_dir() / "settings.json"
