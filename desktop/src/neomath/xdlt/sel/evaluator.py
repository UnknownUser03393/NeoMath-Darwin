"""Equation value semantics for SEL.

These helpers define how SEL operations behave on mathematical *values* rather
than raw AST nodes. The crucial rule is that an operation applied to an equation
distributes over both sides:

    substitute(#eq:final, t=0)   ->   Eq(substitute(lhs, t=0), substitute(rhs, t=0))

The helpers duck-type the value objects passed by a backend (e.g. SymPy ``Eq``
or ``Expr``) so this module stays backend-neutral.
"""

from __future__ import annotations

from typing import Any, Callable


def is_equation_value(value: Any) -> bool:
    return hasattr(value, "lhs") and hasattr(value, "rhs")


def map_equation(value: Any, fn: Callable[[Any], Any]) -> Any:
    """Apply ``fn`` to both sides of an equation value, or directly otherwise."""
    if is_equation_value(value):
        return _rebuild(value, fn(value.lhs), fn(value.rhs))
    return fn(value)


def substitute_value(value: Any, bindings: dict[Any, Any]) -> Any:
    """Apply substitutions to both sides of an equation value, or directly."""
    if is_equation_value(value):
        return _rebuild(value, value.lhs.subs(bindings), value.rhs.subs(bindings))
    return value.subs(bindings)


def _rebuild(value: Any, lhs: Any, rhs: Any) -> Any:
    constructor = type(value)
    try:
        return constructor(lhs, rhs)
    except TypeError:  # pragma: no cover - backend-specific fallback
        return lhs == rhs
