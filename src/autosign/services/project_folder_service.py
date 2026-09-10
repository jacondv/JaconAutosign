"""Files a signed PDF away into a numbered project folder next to its
source file, e.g. "1304-XYZ.pdf" moves into a sibling "1304-Electrical\"
folder - and deletes the now-superseded, not-yet-signed source copy. See
find_matching_project_folder() for the exact matching rule.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

_LEADING_DIGITS = re.compile(r"^(\d+)")


def _leading_digits(name: str) -> str | None:
    match = _LEADING_DIGITS.match(name)
    return match.group(1) if match else None


def list_sibling_folders(parent: Path) -> list[Path]:
    """Subfolders directly under `parent`. Callers signing several files
    from the same folder should list this once and pass it to every
    find_matching_project_folder() call instead of letting each call
    re-scan the same directory."""
    try:
        return [p for p in parent.iterdir() if p.is_dir()]
    except OSError:
        return []


def find_matching_project_folder(
    source_file: Path, siblings: list[Path] | None = None
) -> Path | None:
    """Finds the sibling folder source_file belongs in, trying two rules
    in order:

    1. Leading-digit code (_match_by_leading_digits): a sibling folder
       whose name starts with as many leading digits as the FOLDER's own
       leading digits, e.g. a 2-digit folder "12. Chassis" matches
       "12-report.pdf" on "12"; a 4-digit folder "1304-Electrical" matches
       "1304-report.pdf" on "1304".
    2. Folder-name substring (_match_by_name_substring), for files that
       don't start with digits at all, e.g. "JSA-T43US-A.pdf" matches a
       sibling folder "T43US"; "JSV6-EMU-ABCD.pdf" prefers "JSV6-EMU" over
       a shorter "JSV6" also found among the siblings.

    Each rule returns None if it finds no match or more than one
    (ambiguous - left for the user to resolve with the manual move
    instead of guessing).

    `siblings` is the list of candidate folders (source_file.parent's
    subfolders) - pass it in when matching several files from the same
    folder to avoid re-scanning the directory for each one. Defaults to
    scanning source_file.parent when omitted."""
    if siblings is None:
        siblings = list_sibling_folders(source_file.parent)
    return _match_by_leading_digits(source_file, siblings) or _match_by_name_substring(
        source_file, siblings
    )


def _match_by_leading_digits(source_file: Path, siblings: list[Path]) -> Path | None:
    file_digits = _leading_digits(source_file.stem)
    if not file_digits:
        return None
    matches = []
    for folder in siblings:
        folder_digits = _leading_digits(folder.name)
        if not folder_digits:
            continue
        n = len(folder_digits)
        if len(file_digits) >= n and file_digits[:n] == folder_digits:
            matches.append(folder)
    return matches[0] if len(matches) == 1 else None


def _match_by_name_substring(source_file: Path, siblings: list[Path]) -> Path | None:
    stem = source_file.stem.lower()
    matches = [folder for folder in siblings if folder.name.lower() in stem]
    if not matches:
        return None
    longest = max(len(folder.name) for folder in matches)
    best = [folder for folder in matches if len(folder.name) == longest]
    return best[0] if len(best) == 1 else None


class MoveCollisionError(Exception):
    """The destination already has a file with this name - caller should
    ask the user to overwrite or cancel, then retry with overwrite=True.
    Nothing is touched on disk before this is raised."""

    def __init__(self, destination: Path):
        super().__init__(str(destination))
        self.destination = destination


def move_signed_file(
    signed_path: Path, source_file: Path, target_folder: Path, overwrite: bool = False
) -> Path:
    """Moves signed_path into target_folder (keeping its filename), then
    deletes source_file - the original, not-yet-signed copy this is
    replacing. Together that's what "move" means for this feature: the
    signed file gets filed away, and the stale draft next to it is gone."""
    destination = target_folder / signed_path.name
    if destination.exists():
        if not overwrite:
            raise MoveCollisionError(destination)
        destination.unlink()
    shutil.move(str(signed_path), str(destination))
    if source_file.exists() and source_file.resolve() != destination.resolve():
        source_file.unlink()
    return destination
