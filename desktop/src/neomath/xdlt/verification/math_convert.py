"""Convert Math Semantic IR to SymPy expressions.

The input is the normalized dict tree produced by ``neomath.xdlt.math.lower``.
``symbol_getter`` is a callable ``(name: str) -> sympy.Symbol`` supplied by the
verifier so symbol assumptions stay consistent with the active context.
"""

from __future__ import annotations

from typing import Any, Callable

import sympy as sp

from neomath.xdlt.verification.errors import UnsupportedOperationError

_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "log": sp.log,
    "ln": sp.log,
    "exp": sp.exp,
}

_RELATIONS: dict[str, Callable[..., Any]] = {
    "!=": sp.Ne,
    "<": sp.Lt,
    "<=": sp.Le,
    ">": sp.Gt,
    ">=": sp.Ge,
}

SymbolGetter = Callable[[str], sp.Symbol]


def math_ir_to_sympy(ir: dict[str, Any], symbol_getter: SymbolGetter) -> Any:
    kind = ir["kind"]
    if kind == "integer":
        return sp.Integer(int(ir["value"]))
    if kind == "real_literal":
        return sp.Float(ir["value"])
    if kind == "symbol_ref":
        return _symbol_ref(ir, symbol_getter)
    if kind == "add":
        return sum(math_ir_to_sympy(operand, symbol_getter) for operand in ir["operands"])
    if kind == "subtract":
        return math_ir_to_sympy(ir["left"], symbol_getter) - math_ir_to_sympy(
            ir["right"], symbol_getter
        )
    if kind == "negate":
        return -math_ir_to_sympy(ir["operand"], symbol_getter)
    if kind == "multiply":
        result = sp.Integer(1)
        for operand in ir["operands"]:
            result *= math_ir_to_sympy(operand, symbol_getter)
        return result
    if kind == "divide":
        return math_ir_to_sympy(ir["left"], symbol_getter) / math_ir_to_sympy(
            ir["right"], symbol_getter
        )
    if kind == "power":
        return math_ir_to_sympy(ir["base"], symbol_getter) ** math_ir_to_sympy(
            ir["exponent"], symbol_getter
        )
    if kind == "fraction":
        return math_ir_to_sympy(ir["numerator"], symbol_getter) / math_ir_to_sympy(
            ir["denominator"], symbol_getter
        )
    if kind == "root":
        radicand = math_ir_to_sympy(ir["radicand"], symbol_getter)
        degree = math_ir_to_sympy(ir["degree"], symbol_getter)
        return sp.root(radicand, degree) if degree != sp.Integer(2) else sp.sqrt(radicand)
    if kind == "function_call":
        return _function_call(ir, symbol_getter)
    if kind == "sum":
        body = math_ir_to_sympy(ir["body"], symbol_getter)
        variable = symbol_getter(ir["variable"])
        lower = math_ir_to_sympy(ir["lower"], symbol_getter)
        upper = math_ir_to_sympy(ir["upper"], symbol_getter)
        return sp.Sum(body, (variable, lower, upper))
    if kind == "product":
        body = math_ir_to_sympy(ir["body"], symbol_getter)
        variable = symbol_getter(ir["variable"])
        lower = math_ir_to_sympy(ir["lower"], symbol_getter)
        upper = math_ir_to_sympy(ir["upper"], symbol_getter)
        return sp.Product(body, (variable, lower, upper))
    if kind == "integral":
        body = math_ir_to_sympy(ir["body"], symbol_getter)
        variable = symbol_getter(ir["variable"])
        if ir.get("lower") is not None and ir.get("upper") is not None:
            lower = math_ir_to_sympy(ir["lower"], symbol_getter)
            upper = math_ir_to_sympy(ir["upper"], symbol_getter)
            return sp.Integral(body, (variable, lower, upper))
        return sp.Integral(body, variable)
    if kind == "derivative":
        expression = math_ir_to_sympy(ir["expression"], symbol_getter)
        if "variables" in ir:
            variables = [
                (math_ir_to_sympy(item["variable"], symbol_getter), int(item["order"]["value"]))
                for item in ir["variables"]
            ]
            return sp.Derivative(expression, *variables)
        variable = math_ir_to_sympy(ir["variable"], symbol_getter)
        order = int(ir["order"]["value"])
        return sp.Derivative(expression, variable, order)
    if kind == "partial_derivative":
        raise UnsupportedOperationError("bare \\partial without a variable is unsupported")
    if kind == "subscript":
        return _subscript(ir, symbol_getter)
    if kind == "equation":
        lhs = math_ir_to_sympy(ir["lhs"], symbol_getter)
        rhs = math_ir_to_sympy(ir["rhs"], symbol_getter)
        return sp.Eq(lhs, rhs)
    if kind == "relation":
        operator = ir["operator"]
        if operator not in _RELATIONS:
            raise UnsupportedOperationError(f"unsupported relation '{operator}'")
        lhs = math_ir_to_sympy(ir["left"], symbol_getter)
        rhs = math_ir_to_sympy(ir["right"], symbol_getter)
        return _RELATIONS[operator](lhs, rhs)
    if kind in ("opaque", "text", "tuple"):
        raise UnsupportedOperationError(f"cannot convert '{kind}' math to a verifier expression")
    raise UnsupportedOperationError(f"unsupported math IR kind '{kind}'")


def _symbol_ref(ir: dict[str, Any], symbol_getter: SymbolGetter) -> Any:
    name = ir["name"]
    if name == "pi":
        return sp.pi
    if name == "infty":
        return sp.oo
    if name == "e":
        return sp.E
    return symbol_getter(name)


def _function_call(ir: dict[str, Any], symbol_getter: SymbolGetter) -> Any:
    name = ir["name"]
    args = [math_ir_to_sympy(argument, symbol_getter) for argument in ir["arguments"]]
    if name in _FUNCTIONS:
        return _FUNCTIONS[name](*args)
    # Undefined functions act as placeholder atoms (f(x), g(x, y), ...).
    return sp.Function(name)(*args)


def _subscript(ir: dict[str, Any], symbol_getter: SymbolGetter) -> Any:
    base = ir["base"]
    sub = ir["subscript"]
    if base["kind"] == "symbol_ref" and sub["kind"] in ("integer", "symbol"):
        if sub["kind"] == "symbol":
            sub_name = sub["name"]
        else:
            sub_name = sub["value"]
        return sp.Symbol(f"{base['name']}_{sub_name}")
    raise UnsupportedOperationError("subscript on a non-symbol base is unsupported")
