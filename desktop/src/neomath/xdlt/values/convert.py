"""SemanticValue -> Python / SymPy conversion.

Concrete values become native Python; ``SymbolicValue`` becomes a SymPy symbol
carrying the declared assumptions; ``MathValue`` evaluates through the SEL
backend. The runner and the engine never guess each other's value format.
"""

from __future__ import annotations

from typing import Any, Callable

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

_TYPE_ASSUMPTIONS: dict[str, dict[str, bool]] = {
    "Real": {"real": True},
    "Complex": {},
    "Integer": {"integer": True},
    "Natural": {"integer": True, "nonnegative": True},
}

_PROPERTY_ASSUMPTIONS: dict[str, dict[str, bool]] = {
    "Positive": {"positive": True},
    "NonNegative": {"nonnegative": True},
    "NonZero": {"nonzero": True},
}

SymbolGetter = Callable[[str], Any]


def assumptions_for(type_expr: str | None, properties: list[str] | None = None) -> dict[str, bool]:
    kwargs: dict[str, bool] = {}
    kwargs.update(_TYPE_ASSUMPTIONS.get(type_expr or "", {}))
    for property_name in properties or []:
        if property_name in _PROPERTY_ASSUMPTIONS:
            kwargs.update(_PROPERTY_ASSUMPTIONS[property_name])
    return kwargs


def semantic_value_to_python(
    value: SemanticValue, symbol_getter: SymbolGetter | None = None
) -> Any:
    import sympy as sp

    if isinstance(value, IntegerValue):
        return value.value
    if isinstance(value, RealValue):
        return value.value
    if isinstance(value, BooleanValue):
        return value.value
    if isinstance(value, StringValue):
        return value.value
    if isinstance(value, NullValue):
        return None
    if isinstance(value, ListValue):
        return [semantic_value_to_python(item, symbol_getter) for item in value.items]
    if isinstance(value, TupleValue):
        return tuple(semantic_value_to_python(item, symbol_getter) for item in value.items)
    if isinstance(value, SymbolicValue):
        return sp.Symbol(value.name, **assumptions_for(value.type_expr, value.properties))
    if isinstance(value, MathValue):
        if value.sel_ir is not None and symbol_getter is not None:
            from neomath.xdlt.verification.sel_convert import sel_ir_to_value

            try:
                return sel_ir_to_value(value.sel_ir, {}, symbol_getter)
            except Exception:  # noqa: BLE001 - fall back to a plain symbol
                pass
        return sp.Symbol(value.raw or "?")
    return None
