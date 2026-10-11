from __future__ import annotations

from typing import Any

import sympy as sp

X = sp.Symbol("x", real=True)


def _contains_square_root(expression: sp.Expr) -> bool:
    return any(
        node.func == sp.Pow and len(node.args) == 2 and node.args[1] == sp.Rational(1, 2)
        for node in sp.preorder_traversal(expression)
    )


def expression_from_ast(node: dict[str, Any]) -> sp.Expr:
    node_type = node["type"]
    if node_type == "integer":
        return sp.Integer(node["value"])
    if node_type == "rational":
        return sp.Rational(node["value"])
    if node_type == "symbol":
        if node["name"] != "x":
            raise ValueError("oracle only accepts x")
        return X
    if node_type == "negate":
        return -expression_from_ast(node["operand"])
    if node_type == "sqrt":
        return sp.sqrt(expression_from_ast(node["operand"]))
    left = expression_from_ast(node["left"])
    right = expression_from_ast(node["right"])
    operations = {
        "add": lambda: left + right,
        "subtract": lambda: left - right,
        "multiply": lambda: left * right,
        "divide": lambda: left / right,
        "power": lambda: left**right,
    }
    if node_type not in operations:
        raise ValueError(f"unsupported AST node: {node_type}")
    return operations[node_type]()


def solve_predicate_ast(predicate: dict[str, Any]) -> set[str] | str:
    solutions: set[sp.Expr] = set()
    all_reals = False
    exclusions: set[sp.Expr] = set()
    for equality in predicate["alternatives"]:
        left = expression_from_ast(equality["left"])
        right = expression_from_ast(equality["right"])
        equation = sp.together(left - right)
        denominator = sp.denom(equation)
        if denominator != 1:
            exclusions.update(sp.roots(sp.Poly(denominator, X)).keys())
        numerator = sp.numer(equation)
        if numerator == 0:
            all_reals = True
        elif _contains_square_root(left) or _contains_square_root(right):
            radical = left if _contains_square_root(left) else right
            other = right if _contains_square_root(left) else left
            if radical.func != sp.Pow or radical.exp != sp.Rational(1, 2):
                return "unverified"
            candidate_polynomial = sp.Poly(sp.expand(radical.base - other**2), X)
            candidates = sp.roots(candidate_polynomial).keys()
            for candidate in candidates:
                if candidate.is_real is False:
                    continue
                if sp.simplify(left.subs(X, candidate) - right.subs(X, candidate)) == 0:
                    solutions.add(candidate)
        else:
            try:
                polynomial = sp.Poly(numerator, X)
            except sp.PolynomialError:
                return "unverified"
            solutions.update(
                root
                for root in sp.roots(polynomial).keys()
                if root.is_real is not False and root not in exclusions
            )
    if all_reals:
        if exclusions:
            values = ",".join(sorted(str(value) for value in exclusions))
            return f"all_real_excluding:{values}"
        return "all_real"
    rational = {str(value) for value in solutions if value.is_Rational}
    if len(rational) != len(solutions):
        return "irrational"
    return rational
