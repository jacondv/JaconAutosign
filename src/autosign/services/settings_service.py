"""Persisted app settings: certificate path, signer name, last-used template,
output folder defaults. The password is NEVER stored in plaintext - it is
only stored encrypted via Windows DPAPI (tied to the current Windows user
account), and only when the user explicitly opts in to "remember password".
"""
from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from ..security import DpapiUnavailableError, protect, unprotect

OUTPUT_MODE_SUBFOLDER = "subfolder"  # "signed/" next to the source file
OUTPUT_MODE_CUSTOM = "custom"  # a fixed folder chosen by the user

THEME_LIGHT = "light"
THEME_DARK = "dark"

DEFAULT_SHORTCUT_OPEN_FILES = "Ctrl+O"
DEFAULT_SHORTCUT_OPEN_FOLDER = "Ctrl+Shift+O"
DEFAULT_SHORTCUT_SIGN = "Ctrl+S"

DEFAULT_PAGE_SCOPE = "all"  # SignPageScope.ALL.value


@dataclass
class AppSettings:
    last_pfx_path: Optional[str] = None
    signer_name: Optional[str] = None
    last_template_id: Optional[str] = None
    output_mode: str = OUTPUT_MODE_SUBFOLDER
    custom_output_dir: Optional[str] = None
    remember_password: bool = False
    protected_password_b64: Optional[str] = None
    theme_mode: str = THEME_LIGHT
    shortcut_open_files: str = DEFAULT_SHORTCUT_OPEN_FILES
    shortcut_open_folder: str = DEFAULT_SHORTCUT_OPEN_FOLDER
    shortcut_sign: str = DEFAULT_SHORTCUT_SIGN
    last_file_scope_current_only: bool = False
    last_page_scope: str = DEFAULT_PAGE_SCOPE


class SettingsService:
    def __init__(self, settings_path: Path):
        self._path = settings_path

    def load(self) -> AppSettings:
        if not self._path.exists():
            return AppSettings()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return AppSettings()
        known_fields = AppSettings.__dataclass_fields__.keys()
        return AppSettings(**{k: v for k, v in data.items() if k in known_fields})

    def save(self, settings: AppSettings) -> None:
        self._path.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get_remembered_password(self, settings: AppSettings) -> Optional[str]:
        if not settings.remember_password or not settings.protected_password_b64:
            return None
        try:
            encrypted = base64.b64decode(settings.protected_password_b64)
            return unprotect(encrypted).decode("utf-8")
        except (DpapiUnavailableError, ValueError, UnicodeDecodeError):
            return None  # could not decrypt (e.g. different machine/account) - treat as unset

    def set_remembered_password(self, settings: AppSettings, password: str) -> None:
        try:
            encrypted = protect(password.encode("utf-8"))
            settings.protected_password_b64 = base64.b64encode(encrypted).decode("ascii")
            settings.remember_password = True
        except DpapiUnavailableError:
            self.clear_remembered_password(settings)

    def clear_remembered_password(self, settings: AppSettings) -> None:
        settings.protected_password_b64 = None
        settings.remember_password = False

    def resolve_output_dir(self, settings: AppSettings, source_file: Optional[Path]) -> Path:
        if settings.output_mode == OUTPUT_MODE_CUSTOM and settings.custom_output_dir:
            return Path(settings.custom_output_dir)
        if source_file is not None:
            return source_file.parent / "signed"
        return Path("signed")
