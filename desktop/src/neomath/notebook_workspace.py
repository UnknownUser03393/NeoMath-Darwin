"""File-system workspace for React Notebook documents.

Each notebook is one ``<name>.nm`` file holding the React ``NotebookDocument``
JSON (the same shape the SPA produces). The workspace lives under
``<data_dir>/notebooks/``. A ``.seeded`` marker records whether the built-in
demo notebooks have been written once, so they never resurrect after the user
deletes them.

This is plain-file storage on purpose: no DB, no migrations — a workspace is
a folder of JSON files the user can open and back up.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

SEED_MARKER = ".seeded"


class NotebookWorkspace:
    def __init__(self, data_dir: Path) -> None:
        self.dir = data_dir / "notebooks"
        self.dir.mkdir(parents=True, exist_ok=True)

    def list(self) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        for path in sorted(self.dir.glob("*.nm")):
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                LOGGER.warning("Skipping unreadable notebook %s: %s", path.name, error)
                continue
            if not isinstance(document, dict):
                continue
            files.append(
                {
                    "name": path.stem,
                    "fileName": path.name,
                    "title": document.get("title") or path.stem,
                    "updatedAt": document.get("updatedAt"),
                }
            )
        return {"files": files, "seeded": self._seeded()}

    def load(self, name: str) -> dict[str, Any] | None:
        path = self._path(name)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def save(self, name: str, document: dict[str, Any]) -> Path:
        path = self._path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
        return path

    def rename(self, old: str, new: str) -> Path:
        old_path = self._path(old)
        new_path = self._path(new)
        if not old_path.is_file():
            raise FileNotFoundError(f"notebook not found: {old}")
        if new_path.exists():
            raise FileExistsError(f"notebook already exists: {new}")
        old_path.replace(new_path)
        return new_path

    def mark_seeded(self) -> None:
        (self.dir / SEED_MARKER).write_text("1", encoding="utf-8")

    def _seeded(self) -> bool:
        return (self.dir / SEED_MARKER).is_file()

    def _path(self, name: str) -> Path:
        # Never let a name escape the workspace: strip directories and
        # normalize ".nm" so callers may pass "X" or "X.nm" interchangeably.
        stem = Path(name).name
        if stem.endswith(".nm"):
            stem = stem[: -len(".nm")]
        if not stem or stem in {".", ".."}:
            raise ValueError(f"invalid notebook name: {name!r}")
        return self.dir / f"{stem}.nm"
