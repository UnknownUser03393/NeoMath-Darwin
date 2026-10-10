"""Document-symbol to Python value conversion.

Bare symbols declared in ``#context`` have no concrete numeric value, so v1 maps
them to SymPy symbols carrying their declared assumptions (``alpha: Real &
Positive`` -> ``Symbol('alpha', real=True, positive=True)``). A declared value
set (integer/real/boolean/string/list) plugs in directly. The conversion is an
adapter: the runner and the engine never guess each other's value format.
"""

from __future__ import annotations

from typing import Any

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


def document_symbol_to_python(
    name: str, type_expr: str | None, properties: list[str] | None = None
) -> Any:
    import sympy as sp

    kwargs: dict[str, bool] = {}
    kwargs.update(_TYPE_ASSUMPTIONS.get(type_expr or "", {}))
    for property_name in properties or []:
        if property_name in _PROPERTY_ASSUMPTIONS:
            kwargs.update(_PROPERTY_ASSUMPTIONS[property_name])
    return sp.Symbol(name, **kwargs)


def encode_input_value(value: Any) -> Any:
    """Serialize a Python value for transport to an isolated runner process."""
    import sympy as sp

    if isinstance(value, sp.Symbol):
        return {
            "__xdlt__": "sympy_symbol",
            "name": str(value.name),
            "assumptions": {key: bool(val) for key, val in value.assumptions0.items()},
        }
    if isinstance(value, sp.Basic):
        return {"__xdlt__": "sympy_expr", "repr": sp.srepr(value)}
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=str)
    return value


def json_default(value: Any) -> Any:
    """JSON fallback for structured outputs containing SymPy objects."""
    import sympy as sp

    if isinstance(value, sp.Basic):
        return str(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=str)
    return str(value)
