"""Rolling log of the last N signed files: when each was signed and where
the signed copy ended up. Written from sign_screen.py's _auto_move_if_matched
/ _discard_source_without_move / _perform_move - the places that decide a
file is done and settle where its signed copy lives - and read by
history_screen.py to fill the History tab.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

_MAX_ENTRIES = 100


@dataclass
class HistoryEntry:
    signed_at: str  # ISO 8601, local time - also sorts correctly as plain text
    file_name: str
    result: str  # destination folder name, or a fixed note if nothing matched


class SigningHistoryService:
    def __init__(self, history_path: Path):
        self._path = history_path

    def load(self) -> list[HistoryEntry]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return [HistoryEntry(**item) for item in data if isinstance(item, dict)]

    def _save(self, entries: list[HistoryEntry]) -> None:
        self._path.write_text(
            json.dumps([asdict(e) for e in entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def record_or_update(self, file_name: str, result: str) -> None:
        """Adds a new history row for a just-finished file, or - if a row
        for this file name is already there (e.g. it was auto-filed with
        "no matching folder" earlier and the user just moved it manually
        afterwards) - updates that row's result in place instead of adding
        a duplicate. Keeps at most the most recent _MAX_ENTRIES rows."""
        entries = self.load()
        for entry in reversed(entries):
            if entry.file_name == file_name:
                entry.result = result
                self._save(entries)
                return
        entries.append(
            HistoryEntry(
                signed_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                file_name=file_name,
                result=result,
            )
        )
        self._save(entries[-_MAX_ENTRIES:])
