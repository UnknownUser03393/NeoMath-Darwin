"""Lower Math Surface AST to Math Semantic IR.

The semantic IR is backend-neutral and normalizes away purely surface
distinctions: ``2x`` and ``2 \\cdot x`` both become
``Multiply(Integer(2), SymbolRef(x))``. Parentheses (Group) are transparent.
The surface tree is never mutated.
"""

from __future__ import annotations

from typing import Any, cast

from neomath.xdlt.math.nodes import (
    FractionNode,
    IntegerNode,
    MathNode,
    PartialDerivativeNode,
    PowerNode,
    RelationNode,
    SymbolNode,
)

_ONE: dict[str, Any] = {"kind": "integer", "value": "1"}


def lower_to_semantic(node: MathNode, symbol_refs: list[str] | None = None) -> dict[str, Any]:
    """Normalize ``node`` into Semantic IR, appending resolved symbol ids to ``symbol_refs``."""
    refs = symbol_refs
    kind = node.kind

    if kind == "integer":
        return {"kind": "integer", "value": node.value}
    if kind == "real":
        return {"kind": "real_literal", "value": node.value}
    if kind == "text":
        return {"kind": "text", "text": node.text}
    if kind == "group":
        return lower_to_semantic(node.inner, refs)
    if kind == "tuple":
        return {"kind": "tuple", "parts": [lower_to_semantic(part, refs) for part in node.parts]}
    if kind == "empty":
        return {"kind": "opaque", "command": "", "raw": ""}
    if kind == "symbol":
        return _lower_symbol(cast("SymbolNode", node), refs)
    if kind == "add":
        return {"kind": "add", "operands": [lower_to_semantic(c, refs) for c in node.operands]}
    if kind == "subtract":
        return {
            "kind": "subtract",
            "left": lower_to_semantic(node.left, refs),
            "right": lower_to_semantic(node.right, refs),
        }
    if kind == "negate":
        return {"kind": "negate", "operand": lower_to_semantic(node.operand, refs)}
    if kind == "multiply":
        if len(node.operands) == 1:
            # A word-merge can collapse ``alpha`` to a single-factor product.
            return lower_to_semantic(node.operands[0], refs)
        return {"kind": "multiply", "operands": [lower_to_semantic(c, refs) for c in node.operands]}
    if kind == "divide":
        return {
            "kind": "divide",
            "left": lower_to_semantic(node.left, refs),
            "right": lower_to_semantic(node.right, refs),
        }
    if kind == "power":
        return {
            "kind": "power",
            "base": lower_to_semantic(node.base, refs),
            "exponent": lower_to_semantic(node.exponent, refs),
        }
    if kind == "fraction":
        return _lower_fraction(cast("FractionNode", node), refs)
    if kind == "root":
        degree = (
            lower_to_semantic(node.degree, refs)
            if node.degree
            else {"kind": "integer", "value": "2"}
        )
        return {
            "kind": "root",
            "radicand": lower_to_semantic(node.radicand, refs),
            "degree": degree,
        }
    if kind == "function_call":
        return {
            "kind": "function_call",
            "name": node.name,
            "arguments": [lower_to_semantic(arg, refs) for arg in node.args],
        }
    if kind == "sum":
        return _big_op("sum", node, refs)
    if kind == "product":
        return _big_op("product", node, refs)
    if kind == "integral":
        lower = lower_to_semantic(node.lower, refs) if node.lower else None
        upper = lower_to_semantic(node.upper, refs) if node.upper else None
        return {
            "kind": "integral",
            "body": lower_to_semantic(node.body, refs),
            "lower": lower,
            "upper": upper,
            "variable": node.variable,
        }
    if kind == "partial_derivative":
        return {
            "kind": "partial_derivative",
            "expression": lower_to_semantic(node.expression, refs),
            "order": lower_to_semantic(node.order, refs) if node.order else _ONE,
        }
    if kind == "subscript":
        return {
            "kind": "subscript",
            "base": lower_to_semantic(node.base, refs),
            "subscript": lower_to_semantic(node.subscript, refs),
        }
    if kind == "relation":
        if node.operator == "=":
            return {
                "kind": "equation",
                "lhs": lower_to_semantic(node.left, refs),
                "rhs": lower_to_semantic(node.right, refs),
            }
        return {
            "kind": "relation",
            "operator": node.operator,
            "left": lower_to_semantic(node.left, refs),
            "right": lower_to_semantic(node.right, refs),
        }
    if kind == "opaque":
        return {"kind": "opaque", "command": node.command, "raw": node.source}
    # Unknown/fallback node kinds stay opaque rather than guessing.
    return {"kind": "opaque", "command": "", "raw": node.source}


def _lower_symbol(node: SymbolNode, refs: list[str] | None) -> dict[str, Any]:
    result: dict[str, Any] = {"kind": "symbol_ref", "name": node.name, "symbolId": node.symbol_id}
    if node.symbol_id and refs is not None and node.symbol_id not in refs:
        refs.append(node.symbol_id)
    return result


def _lower_fraction(node: FractionNode, refs: list[str] | None) -> dict[str, Any]:
    numerator = _unwrap_group(node.numerator)
    denominator = _unwrap_group(node.denominator)
    partial_numerator = _partial_numerator(numerator)
    partial_variables = _partial_denominator_variables(denominator)
    if partial_numerator is not None and partial_variables:
        # \frac{\partial^n u}{\partial x^n} and mixed partials -> Derivative
        return _lower_derivative(
            partial_numerator[0], partial_numerator[1], partial_variables, refs
        )
    return {
        "kind": "fraction",
        "numerator": lower_to_semantic(numerator, refs),
        "denominator": lower_to_semantic(denominator, refs),
    }


def _partial_numerator(node: MathNode) -> tuple[MathNode, MathNode | None] | None:
    if isinstance(node, PartialDerivativeNode):
        return (node.expression, node.order)
    return None


def _partial_denominator_variables(node: MathNode) -> list[tuple[MathNode, MathNode | None]] | None:
    """Extract (variable, order) pairs from a ``\\partial`` denominator.

    Handles ``\\partial x``, ``(\\partial x)^n`` and mixed ``\\partial x \\partial y``.
    The order may be an integer or a symbol (``\\partial^n``).
    """
    if isinstance(node, PartialDerivativeNode):
        return [(node.expression, node.order)]
    if isinstance(node, PowerNode):
        base = _unwrap_group(node.base)
        if isinstance(base, PartialDerivativeNode):
            return [(base.expression, node.exponent)]
        return None
    if node.kind == "multiply":
        variables: list[tuple[MathNode, MathNode | None]] = []
        for part in node.operands:
            part = _unwrap_group(part)
            if not isinstance(part, PartialDerivativeNode):
                return None
            variables.append((part.expression, part.order))
        return variables
    return None


def _lower_derivative(
    expression: MathNode,
    numerator_order: MathNode | None,
    variables: list[tuple[MathNode, MathNode | None]],
    refs: list[str] | None,
) -> dict[str, Any]:
    if len(variables) == 1:
        variable, variable_order = variables[0]
        order_node = _choose_order(numerator_order, variable_order)
        order = lower_to_semantic(order_node, refs) if order_node is not None else _ONE
        return {
            "kind": "derivative",
            "expression": lower_to_semantic(expression, refs),
            "variable": lower_to_semantic(variable, refs),
            "order": order,
            "partial": True,
        }
    return {
        "kind": "derivative",
        "expression": lower_to_semantic(expression, refs),
        "variables": [
            {
                "variable": lower_to_semantic(var, refs),
                "order": lower_to_semantic(order_node, refs) if order_node is not None else _ONE,
            }
            for var, order_node in variables
        ],
        "partial": True,
    }


def _choose_order(numerator: MathNode | None, denominator: MathNode | None) -> MathNode | None:
    """Pick the derivative order; when both are integers, use the larger."""
    if numerator is None and denominator is None:
        return None
    if numerator is None:
        return denominator
    if denominator is None:
        return numerator
    if isinstance(numerator, IntegerNode) and isinstance(denominator, IntegerNode):
        try:
            return IntegerNode(str(max(int(numerator.value), int(denominator.value))))
        except ValueError:
            return numerator
    return numerator


def _unwrap_group(node: MathNode) -> MathNode:
    while node.kind == "group":
        node = node.inner
    return node


def _extract_limit(
    limit: MathNode | None, refs: list[str] | None
) -> tuple[str | None, dict[str, Any] | None]:
    """From ``\\sum_{n=1}`` lower, recover the index variable and the bound value."""
    if limit is not None:
        limit = _unwrap_group(limit)
    if (
        isinstance(limit, RelationNode)
        and limit.operator == "="
        and isinstance(limit.left, SymbolNode)
    ):
        return limit.left.name, lower_to_semantic(limit.right, refs)
    if limit is not None:
        return None, lower_to_semantic(limit, refs)
    return None, None


def _big_op(kind: str, node: MathNode, refs: list[str] | None) -> dict[str, Any]:
    variable, lower = _extract_limit(node.lower, refs)
    upper = lower_to_semantic(node.upper, refs) if node.upper else None
    return {
        "kind": kind,
        "body": lower_to_semantic(node.body, refs),
        "lower": lower,
        "upper": upper,
        "variable": variable,
    }
