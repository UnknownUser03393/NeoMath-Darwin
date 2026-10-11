"""Lower a resolved SEL AST into a verifier-independent semantic representation.

The input AST is expected to already have symbol references and semantic
references resolved (see ``neomath.xdlt.resolve``). The output is a plain dict
tree that any backend can consume without touching SEL source syntax.
"""

from __future__ import annotations

from typing import Any

from neomath.xdlt.sel.nodes import SelNode


def lower_sel(node: SelNode) -> dict[str, Any]:
    kind = node.kind
    if kind == "literal":
        return {"kind": "literal", "valueType": node.value_type, "value": node.value}
    if kind == "symbol":
        return {"kind": "symbol", "name": node.name, "symbolId": node.symbol_id}
    if kind == "semantic_reference":
        return {
            "kind": "semantic_reference",
            "name": node.name,
            "targetId": node.target_id,
            "targetType": node.target_type,
        }
    if kind == "selector":
        return {"kind": "selector", "reference": lower_sel(node.reference), "index": node.index}
    if kind == "call":
        return {
            "kind": "call",
            "name": node.name,
            "arguments": [lower_sel(arg) for arg in node.args],
        }
    if kind == "named_argument":
        return {"kind": "named_argument", "name": node.name, "value": lower_sel(node.value)}
    if kind == "unary":
        return {"kind": "unary", "operator": node.operator, "operand": lower_sel(node.operand)}
    if kind == "binary":
        return {
            "kind": "binary",
            "operator": node.operator,
            "left": lower_sel(node.left),
            "right": lower_sel(node.right),
        }
    if kind == "comparison":
        return {
            "kind": "comparison",
            "operator": node.operator,
            "left": lower_sel(node.left),
            "right": lower_sel(node.right),
        }
    if kind == "logical":
        return {
            "kind": "logical",
            "operator": node.operator,
            "left": lower_sel(node.left),
            "right": lower_sel(node.right),
        }
    if kind == "list":
        return {"kind": "list", "items": [lower_sel(item) for item in node.items]}
    if kind == "error":
        return {"kind": "error", "raw": node.raw}
    return {"kind": "error", "raw": node.source}
