"""Position-free card semantic hashes.

The hash covers card identity, version, normalized parameters, the normalized
content Semantic IR, requirement SEL IR and dependencies. JSON whitespace,
formatter tweaks and source offsets never enter the hash.
"""

from __future__ import annotations

from typing import Any

from neomath.xdlt.cards.model import Card
from neomath.xdlt.graph.hash import stable_hash
from neomath.xdlt.sel import lower_sel, parse_sel

_POSITION_KEYS = {"sourceRange", "rawSource", "mathAst", "mathDiagnostics", "contextDiagnostics"}


def card_semantic_hash(card: Card) -> str:
    payload = {
        "card": {
            "id": card.card_id,
            "version": card.version,
            "type": card.card_type,
            "parameters": {
                name: {
                    "type": parameter.type_expr,
                    "requires": [_sel_ir(req) for req in parameter.requires],
                }
                for name, parameter in card.parameters.items()
            },
            "requirements": [_sel_ir(req) for req in card.requirements],
            "contentIr": _normalize(card.content_ir),
            "dependencies": sorted(card.dependencies),
        }
    }
    return stable_hash(payload)


def _sel_ir(source: str) -> dict[str, Any]:
    return lower_sel(parse_sel(source))


def _normalize(ir: Any) -> Any:
    if isinstance(ir, dict):
        return {
            key: _normalize(value)
            for key, value in ir.items()
            if key not in _POSITION_KEYS
        }
    if isinstance(ir, list):
        return [_normalize(item) for item in ir]
    return ir
