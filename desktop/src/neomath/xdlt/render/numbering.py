"""Document numbering pass.

Numbering is a separate pass: the renderer never counts equations or theorems
on the fly. Semantic IDs (``eq:heat``) stay strictly separate from display
numbers (``(1)``).
"""

from __future__ import annotations

from typing import Any

_NUMBERED_KINDS = (
    "equation",
    "theorem",
    "lemma",
    "proposition",
    "corollary",
    "definition",
    "example",
    "remark",
    "algorithm",
    "figure",
    "table",
)


class NumberingScheme:
    """Policy for which kinds get numbered (default: all supported kinds)."""

    def __init__(self, numbered: set[str] | None = None) -> None:
        self.numbered = set(numbered) if numbered is not None else set(_NUMBERED_KINDS)

    def new_context(self) -> "NumberingContext":
        return NumberingContext(self)


class NumberingContext:
    def __init__(self, scheme: NumberingScheme) -> None:
        self.scheme = scheme
        self._counters: dict[str, int] = {}
        self._assigned: dict[str, str] = {}

    def is_numbered(self, kind: str) -> bool:
        return kind in self.scheme.numbered

    def next(self, kind: str) -> str:
        self._counters[kind] = self._counters.get(kind, 0) + 1
        return str(self._counters[kind])

    def assign(self, semantic_id: str, kind: str) -> str | None:
        """Assign and record a display number for a semantic entity."""
        if not self.is_numbered(kind):
            return None
        number = self.next(kind)
        self._assigned[semantic_id] = number
        return number

    def number_of(self, semantic_id: str) -> str | None:
        return self._assigned.get(semantic_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scheme": sorted(self.scheme.numbered),
            "counters": dict(sorted(self._counters.items())),
            "assigned": dict(sorted(self._assigned.items())),
        }
