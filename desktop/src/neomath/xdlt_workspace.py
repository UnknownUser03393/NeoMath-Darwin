"""File-system workspace for XDLT source documents.

Each document is one ``<name>.xdlt`` file holding the plain UTF-8 XDLT source
text (source is the file — no wrapper structure). The workspace lives under
``<data_dir>/xdlt/``. A ``.seeded`` marker records whether the built-in demo
document has been written once, mirroring ``NotebookWorkspace``.

Like ``NotebookWorkspace`` this is plain-file storage on purpose: a workspace
is a folder of text files the user can open and back up.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

SEED_MARKER = ".seeded"

XDLT_SUFFIX = ".xdlt"


class XdltDocumentWorkspace:
    def __init__(self, data_dir: Path) -> None:
        self.dir = data_dir / "xdlt"
        self.dir.mkdir(parents=True, exist_ok=True)

    def list(self) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        for path in sorted(self.dir.glob("*.xdlt")):
            try:
                stat = path.stat()
            except OSError as error:
                LOGGER.warning("Skipping unreadable xdlt file %s: %s", path.name, error)
                continue
            files.append(
                {
                    "name": path.stem,
                    "fileName": path.name,
                    "title": path.stem,
                    "updatedAt": stat.st_mtime,
                }
            )
        return {"files": files, "seeded": self._seeded()}

    def load(self, name: str) -> str | None:
        path = self._path(name)
        if not path.is_file():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def save(self, name: str, source: str) -> Path:
        path = self._path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(source, encoding="utf-8")
        temporary.replace(path)
        return path

    def rename(self, old: str, new: str) -> Path:
        old_path = self._path(old)
        new_path = self._path(new)
        if not old_path.is_file():
            raise FileNotFoundError(f"xdlt document not found: {old}")
        if new_path.exists():
            raise FileExistsError(f"xdlt document already exists: {new}")
        old_path.replace(new_path)
        return new_path

    def mark_seeded(self) -> None:
        (self.dir / SEED_MARKER).write_text("1", encoding="utf-8")

    def _seeded(self) -> bool:
        return (self.dir / SEED_MARKER).is_file()

    def _path(self, name: str) -> Path:
        # Never let a name escape the workspace: strip directories and
        # normalize ".xdlt" so callers may pass "X" or "X.xdlt" interchangeably.
        stem = Path(name).name
        if stem.endswith(XDLT_SUFFIX):
            stem = stem[: -len(XDLT_SUFFIX)]
        if not stem or stem in {".", ".."}:
            raise ValueError(f"invalid xdlt document name: {name!r}")
        return self.dir / f"{stem}{XDLT_SUFFIX}"
