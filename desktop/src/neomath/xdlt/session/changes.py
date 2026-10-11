"""Source changes for incremental compilation.

A ``SourceChange(start, end, replacement)`` replaces ``old[start:end]`` with
``replacement`` in the previous source. Ranges must be valid, non-overlapping
and supplied in deterministic order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceChange:
    start: int
    end: int
    replacement: str

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start, "end": self.end, "replacement": self.replacement}


def validate_changes(changes: list[SourceChange], source_length: int) -> list[dict[str, Any]]:
    """Return INVALID_SOURCE_CHANGE diagnostics for malformed change sets."""
    diagnostics: list[dict[str, Any]] = []
    previous_end = -1
    for index, change in enumerate(changes):
        if change.start < 0 or change.end < change.start or change.end > source_length:
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "INVALID_SOURCE_CHANGE",
                    "message": f"change {index} has invalid range [{change.start}, {change.end})",
                }
            )
            continue
        if change.start < previous_end:
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "INVALID_SOURCE_CHANGE",
                    "message": f"change {index} overlaps an earlier change",
                }
            )
            continue
        previous_end = change.end
    return diagnostics


def apply_changes(source: str, changes: list[SourceChange]) -> str:
    """Apply changes to the previous source (they must be sorted, non-overlapping)."""
    if not changes:
        return source
    parts: list[str] = []
    cursor = 0
    for change in changes:
        parts.append(source[cursor : change.start])
        parts.append(change.replacement)
        cursor = change.end
    parts.append(source[cursor:])
    return "".join(parts)


def compute_source_change(old: str, new: str) -> SourceChange | None:
    """Conservative single-range diff via longest common prefix/suffix.

    This is not a Myers diff; it yields one minimal continuous changed range,
    which is correct for invalidation even if not minimal in edits.
    """
    if old == new:
        return None
    prefix = 0
    limit = min(len(old), len(new))
    while prefix < limit and old[prefix] == new[prefix]:
        prefix += 1
    suffix = 0
    while (
        suffix < len(old) - prefix
        and suffix < len(new) - prefix
        and old[len(old) - 1 - suffix] == new[len(new) - 1 - suffix]
    ):
        suffix += 1
    return SourceChange(
        start=prefix,
        end=len(old) - suffix,
        replacement=new[prefix : len(new) - suffix],
    )
