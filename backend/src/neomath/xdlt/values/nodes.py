"""Semantic value model.

A symbol has three separable aspects: identity (``sym:ctx.global/alpha``), type
and constraints (``Real & Positive``) and an optional runtime value. This module
defines the *value* half. ``SymbolicValue`` represents a symbol known by
identity/type but without a concrete value; it converts to a SymPy symbol at
execution time. Concrete values convert to native Python.
"""

from __future__ import annotations

from typing import Any


class SemanticValue:
    kind = "value"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind}


class IntegerValue(SemanticValue):
    kind = "integer"

    def __init__(self, value: int) -> None:
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value}


class RealValue(SemanticValue):
    kind = "real"

    def __init__(self, value: float) -> None:
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value}


class BooleanValue(SemanticValue):
    kind = "boolean"

    def __init__(self, value: bool) -> None:
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value}


class StringValue(SemanticValue):
    kind = "string"

    def __init__(self, value: str) -> None:
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value}


class ListValue(SemanticValue):
    kind = "list"

    def __init__(self, items: list[SemanticValue]) -> None:
        self.items = list(items)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "items": [item.to_dict() for item in self.items]}


class TupleValue(SemanticValue):
    kind = "tuple"

    def __init__(self, items: list[SemanticValue]) -> None:
        self.items = list(items)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "items": [item.to_dict() for item in self.items]}


class NullValue(SemanticValue):
    kind = "null"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind}


class SymbolicValue(SemanticValue):
    """A symbol known by identity/type but without a concrete value."""

    kind = "symbolic"

    def __init__(
        self,
        name: str,
        type_expr: str | None = None,
        properties: list[str] | None = None,
    ) -> None:
        self.name = name
        self.type_expr = type_expr
        self.properties = list(properties or [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "type": self.type_expr,
            "properties": list(self.properties),
        }


class MathValue(SemanticValue):
    """A symbolic expression value (SEL IR), kept unresolved."""

    kind = "math"

    def __init__(self, raw: str, sel_ir: dict[str, Any] | None = None) -> None:
        self.raw = raw
        self.sel_ir = sel_ir

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "raw": self.raw, "selIr": self.sel_ir}
