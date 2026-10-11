"""Load ``.card.json`` files into Card models.

Card ``content`` is parsed by the real ``.hw`` parser into Semantic IR; there is
no second card-specific parser. Malformed JSON and missing identity fields
produce structured diagnostics rather than raising.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from neomath.xdlt.cards.hash import card_semantic_hash
from neomath.xdlt.cards.model import Card, CardParameter
from neomath.xdlt.parser import parse_xdlt

_VALID_TYPES = {
    "definition",
    "theorem",
    "lemma",
    "formula",
    "derivation",
    "proof",
    "example",
    "identity",
    "algorithm",
}


def load_card_file(path: str | Path) -> Card | None:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return Card(
            card_id=path.stem,
            version="",
            card_type="unknown",
            source_path=str(path),
            diagnostics=[
                _diagnostic("error", "INVALID_CARD", f"could not read card: {error}")
            ],
        )
    if not isinstance(data, dict):
        return Card(
            card_id=path.stem,
            version="",
            card_type="unknown",
            source_path=str(path),
            diagnostics=[_diagnostic("error", "INVALID_CARD", "card JSON must be an object")],
        )
    card = card_from_dict(data)
    card.source_path = str(path)
    return card


def card_from_dict(data: dict[str, Any]) -> Card:
    diagnostics: list[dict[str, Any]] = []
    card_id = str(data.get("id") or "").strip()
    version = str(data.get("version") or "").strip()
    card_type = str(data.get("type") or "").strip()
    if not card_id:
        diagnostics.append(_diagnostic("error", "INVALID_CARD", "card has no 'id'"))
    if not version:
        diagnostics.append(_diagnostic("error", "CARD_VERSION_MISSING", "card has no 'version'"))
    if card_type and card_type not in _VALID_TYPES:
        diagnostics.append(
            _diagnostic("warning", "INVALID_CARD", f"unknown card type '{card_type}'")
        )

    parameters: dict[str, CardParameter] = {}
    for name, spec in (data.get("parameters") or {}).items():
        if isinstance(spec, dict):
            requires = [str(req) for req in spec.get("requires", [])]
            parameters[str(name)] = CardParameter(
                name=str(name),
                type_expr=spec.get("type"),
                requires=requires,
            )

    content = str(data.get("content") or "")
    content_ir, content_diagnostics = _parse_content(content)
    diagnostics.extend(content_diagnostics)

    dependencies = [str(dep) for dep in data.get("dependencies", [])]

    card = Card(
        card_id=card_id or str(data.get("id") or ""),
        version=version,
        card_type=card_type or "unknown",
        title=str(data.get("title") or ""),
        parameters=parameters,
        requirements=[str(req) for req in data.get("requirements", [])],
        content=content,
        conclusion=data.get("conclusion"),
        dependencies=dependencies,
        provenance=dict(data.get("provenance") or {}),
        content_ir=content_ir,
        diagnostics=diagnostics,
    )
    card.semantic_hash = card_semantic_hash(card)
    return card


def _parse_content(content: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not content.strip():
        return None, []
    from neomath.xdlt.semantic import lower_to_semantic_ir

    document = parse_xdlt(content)
    diagnostics = [d.to_dict() for d in document.diagnostics]
    return lower_to_semantic_ir(document), diagnostics


def _diagnostic(severity: str, code: str, message: str) -> dict[str, Any]:
    return {"severity": severity, "code": code, "message": message}
