from __future__ import annotations

from typing import Any

CURRENT_FORMAT_VERSION = 1


def migrate_document(data: dict[str, Any]) -> dict[str, Any]:
    """Return a current-format copy without accepting unknown future formats."""
    migrated = dict(data)
    version = int(migrated.get("formatVersion", 1))
    if version < 1:
        # Early development files used `steps` as a list of source strings.
        steps = migrated.pop("steps", [])
        if "source" not in migrated and isinstance(steps, list):
            migrated["source"] = "\n".join(str(step) for step in steps)
        version = 1
    if version > CURRENT_FORMAT_VERSION:
        raise ValueError(
            f"document format {version} is newer than supported version {CURRENT_FORMAT_VERSION}"
        )
    migrated["formatVersion"] = CURRENT_FORMAT_VERSION
    return migrated
