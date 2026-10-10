"""Value assignment parsing, validation and environment building.

Values reuse the SEL front end (literals, lists) so no card-specific expression
language is invented. Type and constraint violations produce structured
diagnostics instead of being silently accepted.
"""

from __future__ import annotations

from typing import Any

from neomath.xdlt.sel import lower_sel, parse_sel
from neomath.xdlt.sel.nodes import SelNode
from neomath.xdlt.values.environment import ValueEnvironment
from neomath.xdlt.values.nodes import (
    BooleanValue,
    IntegerValue,
    ListValue,
    MathValue,
    NullValue,
    RealValue,
    SemanticValue,
    StringValue,
    SymbolicValue,
    TupleValue,
)

_NUMERIC_TYPES = {"Real", "Complex", "Integer", "Natural"}


def parse_value_expression(text: str) -> SemanticValue:
    """Parse ``= 0.01`` / ``= [0, 1]`` into a SemanticValue.

    Non-literal expressions (``= L``, ``= a + b``) become ``MathValue`` kept in
    SEL form rather than being guessed at.
    """
    node = parse_sel(text)
    value = sel_value_to_semantic(node)
    if value is not None:
        return value
    return MathValue(raw=text, sel_ir=lower_sel(node))


def sel_value_to_semantic(node: SelNode) -> SemanticValue | None:
    kind = node.kind
    if kind == "literal":
        value_type = node.value_type
        value = node.value
        if value_type == "integer":
            return IntegerValue(int(value))
        if value_type == "real":
            return RealValue(float(value))
        if value_type == "boolean":
            return BooleanValue(value == "true")
        if value_type == "string":
            return StringValue(value)
        if value_type == "null":
            return NullValue()
        return None
    if kind == "unary":
        inner = sel_value_to_semantic(node.operand)
        if isinstance(inner, IntegerValue):
            return IntegerValue(-inner.value if node.operator == "-" else inner.value)
        if isinstance(inner, RealValue):
            return RealValue(-inner.value if node.operator == "-" else inner.value)
        return inner
    if kind == "list":
        items: list[SemanticValue] = []
        for item in node.items:
            converted = sel_value_to_semantic(item)
            if converted is None:
                return None
            items.append(converted)
        return ListValue(items)
    return None


def validate_value(
    type_expr: str | None,
    properties: list[str] | None,
    value: SemanticValue,
) -> list[dict[str, Any]]:
    """Return VALUE_TYPE_MISMATCH / VALUE_CONSTRAINT_VIOLATION diagnostics."""
    diagnostics: list[dict[str, Any]] = []
    properties = list(properties or [])
    if isinstance(value, (SymbolicValue, MathValue, TupleValue)):
        return diagnostics  # no concrete number to prove anything about

    type_ok = _type_matches(type_expr, value)
    if not type_ok:
        diagnostics.append(
            {
                "severity": "error",
                "code": "VALUE_TYPE_MISMATCH",
                "message": f"value '{_value_repr(value)}' does not match type '{type_expr}'",
            }
        )
        return diagnostics

    numeric = _numeric_value(value)
    if numeric is not None:
        if "Positive" in properties and not numeric > 0:
            _constraint(diagnostics, f"value '{_value_repr(value)}' is not > 0")
        if "NonNegative" in properties and not numeric >= 0:
            _constraint(diagnostics, f"value '{_value_repr(value)}' is not >= 0")
        if "NonZero" in properties and numeric == 0:
            _constraint(diagnostics, f"value '{_value_repr(value)}' is zero")
        if type_expr == "Natural" and numeric < 0:
            _constraint(diagnostics, f"Natural value '{_value_repr(value)}' must be >= 0")
    return diagnostics


def override_to_value(value: Any) -> SemanticValue:
    if isinstance(value, bool):
        return BooleanValue(value)
    if isinstance(value, int):
        return IntegerValue(value)
    if isinstance(value, float):
        return RealValue(value)
    if isinstance(value, str):
        return StringValue(value)
    if isinstance(value, list):
        return ListValue([override_to_value(item) for item in value])
    if isinstance(value, tuple):
        return TupleValue([override_to_value(item) for item in value])
    if value is None:
        return NullValue()
    return StringValue(str(value))


def semantic_from_dict(data: dict[str, Any]) -> SemanticValue | None:
    kind = data.get("kind")
    if kind == "integer":
        return IntegerValue(int(data["value"]))
    if kind == "real":
        return RealValue(float(data["value"]))
    if kind == "boolean":
        return BooleanValue(bool(data["value"]))
    if kind == "string":
        return StringValue(str(data["value"]))
    if kind == "list":
        return ListValue(_items_from_dicts(data.get("items", [])))
    if kind == "tuple":
        return TupleValue(_items_from_dicts(data.get("items", [])))
    if kind == "null":
        return NullValue()
    if kind == "symbolic":
        return SymbolicValue(
            str(data.get("name", "")),
            data.get("type"),
            list(data.get("properties", [])),
        )
    if kind == "math":
        return MathValue(str(data.get("raw", "")), data.get("selIr"))
    return None


def build_value_environment(
    semantic_ir: dict[str, Any],
    overrides: dict[str, Any] | None = None,
) -> ValueEnvironment:
    environment = ValueEnvironment()
    _collect_values(semantic_ir.get("children", []), environment)
    for name, raw_value in (overrides or {}).items():
        environment.override(str(name), override_to_value(raw_value))
    return environment


def _collect_values(children: list[dict[str, Any]], environment: ValueEnvironment) -> None:
    for entity in children:
        if entity.get("type") == "Context":
            namespace = entity.get("namespace")
            for declaration in entity.get("declarations", []):
                type_name = declaration.get("type", {}).get("name")
                properties = [p.get("name") for p in declaration.get("properties", [])]
                value = (
                    semantic_from_dict(declaration["value"]) if declaration.get("value") else None
                )
                for name in declaration.get("names", []):
                    symbol_id = f"sym:{namespace}/{name}"
                    if value is None:
                        environment.declare(
                            name, symbol_id, SymbolicValue(name, type_name, properties)
                        )
                    else:
                        environment.declare(name, symbol_id, value)
        _collect_values(entity.get("children", []), environment)


def _items_from_dicts(data: list[dict[str, Any]]) -> list[SemanticValue]:
    items: list[SemanticValue] = []
    for item in data:
        converted = semantic_from_dict(item)
        if converted is not None:
            items.append(converted)
    return items


def _type_matches(type_expr: str | None, value: SemanticValue) -> bool:
    if type_expr in (None, ""):
        return True
    if isinstance(value, IntegerValue):
        return type_expr in _NUMERIC_TYPES
    if isinstance(value, RealValue):
        return type_expr in ("Real", "Complex")
    if isinstance(value, BooleanValue):
        return type_expr == "Boolean"
    if isinstance(value, StringValue):
        return type_expr == "String"
    if isinstance(value, NullValue):
        return True
    if isinstance(value, ListValue):
        return False
    return True


def _numeric_value(value: SemanticValue) -> float | None:
    if isinstance(value, IntegerValue):
        return float(value.value)
    if isinstance(value, RealValue):
        return value.value
    return None


def _value_repr(value: SemanticValue) -> str:
    if isinstance(value, RealValue):
        return repr(value.value)
    if isinstance(value, IntegerValue):
        return str(value.value)
    raw = value.to_dict().get("value")
    return str(raw) if raw is not None else "?"


def _constraint(diagnostics: list[dict[str, Any]], message: str) -> None:
    diagnostics.append(
        {"severity": "error", "code": "VALUE_CONSTRAINT_VIOLATION", "message": message}
    )
