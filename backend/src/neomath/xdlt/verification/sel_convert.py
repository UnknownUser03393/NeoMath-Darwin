"""Evaluate SEL semantic IR against a SymPy backend.

The SEL IR is the verifier-independent form produced by ``sel.lower`` after
symbol and reference resolution. Evaluation yields a SymPy value (``Expr``,
``Eq``, a relational, or a boolean), which the verifier then checks.
"""

from __future__ import annotations

from typing import Any, Callable

import sympy as sp

from neomath.xdlt.sel.evaluator import map_equation, substitute_value
from neomath.xdlt.verification.errors import (
    CannotDecideError,
    InvalidReferenceTypeError,
    UnresolvedReferenceError,
    UnsupportedOperationError,
)
from neomath.xdlt.verification.math_convert import SymbolGetter, math_ir_to_sympy

_MATH_ENTITY_TYPES = ("Equation", "MathExpression", "Relation")

_SEL_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "log": sp.log,
    "ln": sp.log,
    "exp": sp.exp,
    "sqrt": sp.sqrt,
}


def sel_ir_to_value(
    ir: dict[str, Any],
    referenced_entities: dict[str, dict[str, Any]],
    symbol_getter: SymbolGetter,
) -> Any:
    kind = ir["kind"]
    if kind == "literal":
        return _literal(ir)
    if kind == "symbol":
        return symbol_getter(ir["name"])
    if kind == "semantic_reference":
        return _reference_value(ir, referenced_entities, symbol_getter)
    if kind == "selector":
        raise UnsupportedOperationError("execution selectors are not supported yet")
    if kind == "call":
        return _call_value(ir, referenced_entities, symbol_getter)
    if kind == "unary":
        operand = sel_ir_to_value(ir["operand"], referenced_entities, symbol_getter)
        if ir["operator"] == "not":
            return sp.Not(operand)
        if ir["operator"] == "-":
            return -operand
        return operand
    if kind == "binary":
        left = sel_ir_to_value(ir["left"], referenced_entities, symbol_getter)
        right = sel_ir_to_value(ir["right"], referenced_entities, symbol_getter)
        operator = ir["operator"]
        if operator == "+":
            return left + right
        if operator == "-":
            return left - right
        if operator == "*":
            return left * right
        if operator == "/":
            if right.is_zero is not False:
                raise CannotDecideError("Division requires a proven nonzero denominator")
            return left / right
        if operator == "^":
            if right.is_integer is not True or right.is_negative is True:
                if left.is_positive is not True:
                    raise CannotDecideError("Power domain/branch obligations are unresolved")
            return left**right
    if kind == "comparison":
        return _comparison(ir, referenced_entities, symbol_getter)
    if kind == "logical":
        left = sel_ir_to_value(ir["left"], referenced_entities, symbol_getter)
        right = sel_ir_to_value(ir["right"], referenced_entities, symbol_getter)
        if ir["operator"] == "and":
            return sp.And(left, right)
        if ir["operator"] == "or":
            return sp.Or(left, right)
    if kind == "list":
        return [sel_ir_to_value(item, referenced_entities, symbol_getter) for item in ir["items"]]
    if kind == "error":
        raise UnsupportedOperationError("claim could not be parsed")
    raise UnsupportedOperationError(f"unsupported SEL node kind '{kind}'")


def _literal(ir: dict[str, Any]) -> Any:
    value_type = ir["valueType"]
    value = ir["value"]
    if value_type == "integer":
        return sp.Integer(int(value))
    if value_type == "real":
        return sp.Rational(value)
    if value_type == "boolean":
        return sp.true if value == "true" else sp.false
    if value_type == "string":
        return value
    if value_type == "null":
        return None
    raise UnsupportedOperationError(f"unsupported literal type '{value_type}'")


def _reference_value(
    ir: dict[str, Any],
    referenced_entities: dict[str, dict[str, Any]],
    symbol_getter: SymbolGetter,
) -> Any:
    target_id = ir.get("targetId")
    if not target_id:
        raise UnresolvedReferenceError(f"unresolved semantic reference '#{ir['name']}'")
    entity = referenced_entities.get(target_id)
    if entity is None:
        raise UnresolvedReferenceError(f"unresolved semantic reference '#{ir['name']}'")
    entity_type = entity.get("type")
    if entity_type not in _MATH_ENTITY_TYPES:
        raise InvalidReferenceTypeError(
            f"reference '#{ir['name']}' targets a {entity_type}, not a math value"
        )
    math_ir = entity.get("mathIr")
    if math_ir is None:
        raise UnsupportedOperationError(f"entity '#{target_id}' has no math value")
    return math_ir_to_sympy(math_ir, symbol_getter)


def _comparison(
    ir: dict[str, Any],
    referenced_entities: dict[str, dict[str, Any]],
    symbol_getter: SymbolGetter,
) -> Any:
    left = sel_ir_to_value(ir["left"], referenced_entities, symbol_getter)
    right = sel_ir_to_value(ir["right"], referenced_entities, symbol_getter)
    operator = ir["operator"]
    if operator == "==":
        return sp.Eq(left, right)
    if operator == "!=":
        return sp.Ne(left, right)
    if operator == "<":
        return sp.Lt(left, right)
    if operator == "<=":
        return sp.Le(left, right)
    if operator == ">":
        return sp.Gt(left, right)
    if operator == ">=":
        return sp.Ge(left, right)
    raise UnsupportedOperationError(f"unsupported comparison '{operator}'")


def _call_value(
    ir: dict[str, Any],
    referenced_entities: dict[str, dict[str, Any]],
    symbol_getter: SymbolGetter,
) -> Any:
    name = ir["name"]
    args = ir["arguments"]

    def evaluate(argument: dict[str, Any]) -> Any:
        return sel_ir_to_value(argument, referenced_entities, symbol_getter)

    if name in _SEL_FUNCTIONS:
        values = [evaluate(argument) for argument in args]
        if name == "sqrt" and values[0].is_nonnegative is not True:
            raise CannotDecideError("Square-root real domain is unresolved")
        if name in ("log", "ln") and values[0].is_positive is not True:
            raise CannotDecideError("Logarithm real domain is unresolved")
        if name == "tan" and values[0].free_symbols:
            raise CannotDecideError("Tangent domain exclusions are unresolved")
        return _SEL_FUNCTIONS[name](*values)
    if name == "substitute":
        target = evaluate(args[0])
        bindings = {}
        for argument in args[1:]:
            if argument["kind"] != "named_argument":
                raise UnsupportedOperationError("substitute requires named bindings (x=0)")
            bindings[symbol_getter(argument["name"])] = evaluate(argument["value"])
        return substitute_value(target, bindings)
    if name == "simplify":
        return map_equation(evaluate(args[0]), sp.simplify)
    if name == "expand":
        return map_equation(evaluate(args[0]), sp.expand)
    if name == "factor":
        return map_equation(evaluate(args[0]), sp.factor)
    if name == "differentiate":
        expression = evaluate(args[0])
        variable = symbol_getter(_symbol_name(args[1]))
        order = 1
        if len(args) >= 3:
            order = int(evaluate(args[2]))
        return sp.diff(expression, variable, order)
    if name == "integrate":
        expression = evaluate(args[0])
        variable = symbol_getter(_symbol_name(args[1]))
        if len(args) >= 4:
            lower = evaluate(args[2])
            upper = evaluate(args[3])
            return sp.integrate(expression, (variable, lower, upper))
        return sp.integrate(expression, variable)
    if name == "lhs":
        return _side(evaluate(args[0]), "lhs")
    if name == "rhs":
        return _side(evaluate(args[0]), "rhs")
    if name == "equals":
        left = evaluate(args[0])
        right = evaluate(args[1])
        difference = sp.simplify(left - right)
        if difference == 0:
            return sp.true
        if not difference.free_symbols and difference.is_zero is False:
            return sp.false
        raise CannotDecideError("equals(): no proof or exact counterexample")
    if name == "equivalent":
        left = evaluate(args[0])
        right = evaluate(args[1])
        difference = sp.simplify(left - right)
        if difference == 0:
            return sp.true
        if not difference.free_symbols and difference.is_zero is False:
            return sp.false
        raise CannotDecideError("equivalent(): cannot decide")
    if name == "value":
        return sp.nsimplify(evaluate(args[0]))
    if name == "output":
        raise UnsupportedOperationError("output() is not supported yet")
    # Undefined functions act as placeholder atoms (f(x), g(x, y), ...).
    return sp.Function(name)(*[evaluate(argument) for argument in args])


def _symbol_name(ir: dict[str, Any]) -> str:
    if ir["kind"] != "symbol":
        raise UnsupportedOperationError("expected a symbol argument")
    return str(ir["name"])


def _side(value: Any, side: str) -> Any:
    if hasattr(value, "lhs") and hasattr(value, "rhs"):
        return value.lhs if side == "lhs" else value.rhs
    raise UnsupportedOperationError(f"{side}() requires an equation argument")
