"""Stable anchors and semantic reference resolution.

``#eq:heat`` in prose becomes a ``RenderReference`` carrying the resolved target
kind, display text and anchor. Anchors are escaped deterministically; a raw
semantic ID is never dropped unescaped into an HTML ``id``.
"""

from __future__ import annotations

import re
from typing import Any

_REFERENCE = re.compile(r"#(?P<kind>[a-z][a-z0-9_-]*):(?P<id>[A-Za-z0-9_][A-Za-z0-9_.-]*)")

# kind -> human label used for deterministic default display text.
_LABELS = {
    "eq": "Equation",
    "thm": "Theorem",
    "lemma": "Lemma",
    "prop": "Proposition",
    "cor": "Corollary",
    "def": "Definition",
    "proof": "Proof",
    "example": "Example",
    "remark": "Remark",
    "fig": "Figure",
    "table": "Table",
    "algorithm": "Algorithm",
    "assert": "Assertion",
}


def semantic_id_to_html_anchor(semantic_id: str) -> str:
    """``eq:heat`` -> ``xdlt-eq-heat`` (collision/escaping safe)."""
    safe = "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in semantic_id)
    return f"xdlt-{safe}"


def split_references(text: str) -> list[str | tuple[str, str]]:
    """Split prose into text segments and ``(targetId, source)`` reference spans."""
    segments: list[str | tuple[str, str]] = []
    pos = 0
    for match in _REFERENCE.finditer(text):
        if match.start() > pos:
            segments.append(text[pos : match.start()])
        segments.append((f"{match.group('kind')}:{match.group('id')}", match.group(0)))
        pos = match.end()
    if pos < len(text):
        segments.append(text[pos:])
    return segments


def reference_info(
    target_id: str,
    registry: dict[str, dict[str, Any]],
    number_of: Any,
) -> tuple[str | None, str | None, str | None]:
    """(targetKind, displayText, anchor) for a resolved reference."""
    entity = registry.get(target_id)
    if entity is None:
        return None, None, None
    kind = _kind_from_entity(entity)
    number = number_of(target_id)
    if kind is None:
        label = "Item"
    else:
        label = _LABELS.get(kind, kind.capitalize())
    if number:
        display = f"{label} {number}"
    else:
        display = label
    return kind, display, semantic_id_to_html_anchor(target_id)


def _kind_from_entity(entity: dict[str, Any]) -> str | None:
    entity_type = entity.get("type")
    if not isinstance(entity_type, str):
        return None
    mapping = {
        "Equation": "eq",
        "Relation": "eq",
        "MathExpression": "eq",
        "Theorem": "thm",
        "Lemma": "lemma",
        "Proposition": "prop",
        "Corollary": "cor",
        "Definition": "def",
        "Proof": "proof",
        "Example": "example",
        "Remark": "remark",
        "Figure": "fig",
        "Table": "table",
        "Assertion": "assert",
        "Algorithm": "algorithm",
    }
    return mapping.get(entity_type)
