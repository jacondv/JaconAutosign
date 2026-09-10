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
    source_dir: str  # full path of the folder the original file was signed from
    destination: str  # full path of the folder the signed copy ended up in


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
        entries = []
        known_fields = HistoryEntry.__dataclass_fields__.keys()
        for item in data:
            if not isinstance(item, dict):
                continue
            # Older versions logged a single free-text "result" note instead
            # of source_dir/destination - drop those unknown rows rather
            # than letting one bad entry (a stale field name) blank out the
            # whole tab.
            try:
                entries.append(HistoryEntry(**{k: v for k, v in item.items() if k in known_fields}))
            except TypeError:
                continue
        return entries

    def _save(self, entries: list[HistoryEntry]) -> None:
        self._path.write_text(
            json.dumps([asdict(e) for e in entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def record_or_update(self, file_name: str, source_dir: str, destination: str) -> None:
        """Adds a new history row for a just-finished file, or - if a row
        for this file name is already there (e.g. it was auto-filed with
        "no matching folder" earlier and the user just moved it manually
        afterwards) - updates that row's destination in place instead of
        adding a duplicate. Keeps at most the most recent _MAX_ENTRIES rows."""
        entries = self.load()
        for entry in reversed(entries):
            if entry.file_name == file_name:
                entry.destination = destination
                self._save(entries)
                return
        entries.append(
            HistoryEntry(
                signed_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                file_name=file_name,
                source_dir=source_dir,
                destination=destination,
            )
        )
        self._save(entries[-_MAX_ENTRIES:])

    def clear(self) -> None:
        self._save([])
