"""Math Semantic IR -> MathML.

The browser never re-parses xdlt: the backend produces standards-compliant
MathML from the already-resolved Math IR. Output is deterministic. Opaque nodes
return ``None`` so the renderer can degrade to a safe fallback.
"""

from __future__ import annotations

from typing import Any

from neomath.xdlt.render.html.escape import escape_html


def math_ir_to_mathml(ir: dict[str, Any] | None) -> str | None:
    if ir is None:
        return None
    kind = ir.get("kind")
    if kind == "integer":
        return f"<mn>{escape_html(str(ir.get('value', '')))}</mn>"
    if kind == "real_literal":
        return f"<mn>{escape_html(str(ir.get('value', '')))}</mn>"
    if kind == "symbol_ref":
        return f"<mi>{escape_html(str(ir.get('name', '')))}</mi>"
    if kind == "text":
        return f"<mtext>{escape_html(str(ir.get('text', '')))}</mtext>"
    if kind == "group":
        return math_ir_to_mathml(ir.get("inner"))
    if kind == "add":
        return _op(ir.get("operands", []), "+")
    if kind == "subtract":
        return _binary(ir, "-")
    if kind == "negate":
        operand = math_ir_to_mathml(ir.get("operand"))
        if operand is None:
            return None
        return f"<mrow><mo>&#x2212;</mo>{operand}</mrow>"
    if kind == "multiply":
        return _op(ir.get("operands", []), "&#x2062;")
    if kind == "divide":
        return _binary(ir, "&#x2215;")
    if kind == "power":
        base = math_ir_to_mathml(ir.get("base"))
        exponent = math_ir_to_mathml(ir.get("exponent"))
        if base is None or exponent is None:
            return None
        return f"<msup>{base}{exponent}</msup>"
    if kind == "fraction":
        return _fraction(ir.get("numerator"), ir.get("denominator"))
    if kind == "root":
        return _root(ir)
    if kind == "function_call":
        return _function_call(ir)
    if kind == "equation":
        return _relation(ir, "=")
    if kind == "relation":
        return _relation(ir, str(ir.get("operator", "=")))
    if kind in ("sum", "product"):
        return _big_operator(ir, "&#x2211;" if kind == "sum" else "&#x220F;")
    if kind == "integral":
        return _integral(ir)
    if kind == "derivative":
        return _derivative(ir)
    if kind == "subscript":
        base = math_ir_to_mathml(ir.get("base"))
        subscript = math_ir_to_mathml(ir.get("subscript"))
        if base is None or subscript is None:
            return None
        return f"<msub>{base}{subscript}</msub>"
    if kind == "opaque":
        return None
    return None


def _op(operands: list[dict[str, Any]], operator: str) -> str | None:
    rendered: list[str] = []
    for operand in operands:
        part = math_ir_to_mathml(operand)
        if part is None:
            return None
        rendered.append(part)
    return f"<mrow>{f'<mo>{operator}</mo>'.join(rendered)}</mrow>"


def _binary(ir: dict[str, Any], operator: str) -> str | None:
    left = math_ir_to_mathml(ir.get("left"))
    right = math_ir_to_mathml(ir.get("right"))
    if left is None or right is None:
        return None
    return f"<mrow>{left}<mo>{operator}</mo>{right}</mrow>"


def _fraction(numerator: Any, denominator: Any) -> str | None:
    top = math_ir_to_mathml(numerator)
    bottom = math_ir_to_mathml(denominator)
    if top is None or bottom is None:
        return None
    return f"<mfrac>{top}{bottom}</mfrac>"


def _root(ir: dict[str, Any]) -> str | None:
    radicand = math_ir_to_mathml(ir.get("radicand"))
    if radicand is None:
        return None
    degree = ir.get("degree")
    if degree and degree.get("value") == "2":
        return f"<msqrt>{radicand}</msqrt>"
    if degree is None:
        return f"<msqrt>{radicand}</msqrt>"
    degree_ml = math_ir_to_mathml(degree)
    if degree_ml is None:
        return None
    return f"<mroot>{radicand}{degree_ml}</mroot>"


def _function_call(ir: dict[str, Any]) -> str | None:
    name = escape_html(str(ir.get("name", "")))
    args: list[str] = []
    for argument in ir.get("arguments", []):
        part = math_ir_to_mathml(argument)
        if part is None:
            return None
        args.append(part)
    inner = f"<mrow>{','.join(args)}</mrow>" if args else "<mrow></mrow>"
    return f"<mrow><mi>{name}</mi><mfenced open='(' close=')'>{inner}</mfenced></mrow>"


def _relation(ir: dict[str, Any], operator: str) -> str | None:
    left = math_ir_to_mathml(ir.get("lhs") if "lhs" in ir else ir.get("left"))
    right = math_ir_to_mathml(ir.get("rhs") if "rhs" in ir else ir.get("right"))
    if left is None or right is None:
        return None
    op_symbol = {
        "=": "=",
        "!=": "&#x2260;",
        "<": "&lt;",
        "<=": "&#x2264;",
        ">": "&gt;",
        ">=": "&#x2265;",
    }.get(operator, operator)
    return f"<mrow>{left}<mo>{op_symbol}</mo>{right}</mrow>"


def _big_operator(ir: dict[str, Any], symbol: str) -> str | None:
    body = math_ir_to_mathml(ir.get("body"))
    lower = math_ir_to_mathml(ir.get("lower")) if ir.get("lower") else None
    upper = math_ir_to_mathml(ir.get("upper")) if ir.get("upper") else None
    if body is None:
        return None
    bounds = ""
    if lower is not None and upper is not None:
        bounds = f"<munderover><mo>{symbol}</mo>{lower}{upper}</munderover>"
    elif lower is not None:
        bounds = f"<munder><mo>{symbol}</mo>{lower}</munder>"
    else:
        bounds = f"<mo>{symbol}</mo>"
    return f"<mrow>{bounds}{body}</mrow>"


def _integral(ir: dict[str, Any]) -> str | None:
    body = math_ir_to_mathml(ir.get("body"))
    if body is None:
        return None
    lower = math_ir_to_mathml(ir.get("lower")) if ir.get("lower") else None
    upper = math_ir_to_mathml(ir.get("upper")) if ir.get("upper") else None
    integral = "<mo>&#x222B;</mo>"
    if lower is not None and upper is not None:
        integral = f"<msubsup><mo>&#x222B;</mo>{lower}{upper}</msubsup>"
    variable = ir.get("variable")
    differential = f"<mi>d</mi><mi>{escape_html(str(variable))}</mi>" if variable else ""
    return f"<mrow>{integral}{body}{differential}</mrow>"


def _derivative(ir: dict[str, Any]) -> str | None:
    expression = math_ir_to_mathml(ir.get("expression"))
    if expression is None:
        return None
    partial = bool(ir.get("partial"))
    symbol = "&#x2202;" if partial else "d"
    variables = ir.get("variables")
    if variables:
        numerator = f"<mrow><mo>{symbol}</mo></mrow>"
        denominator_parts: list[str] = []
        for item in variables:
            variable = math_ir_to_mathml(item.get("variable"))
            if variable is None:
                return None
            order = item.get("order") or {}
            exponent = (
                f"<msup>{variable}{math_ir_to_mathml(order)}</msup>"
                if order.get("value") not in (None, "1")
                else variable
            )
            denominator_parts.append(exponent)
        denominator = f"<mrow><mo>{symbol}</mo>{''.join(denominator_parts)}</mrow>"
        return f"<mrow><mfrac>{numerator}{denominator}</mfrac>{expression}</mrow>"
    variable = math_ir_to_mathml(ir.get("variable"))
    if variable is None:
        return None
    order = ir.get("order") or {}
    exponent = (
        f"<msup>{symbol}{math_ir_to_mathml(order)}</msup>"
        if order.get("value") not in (None, "1")
        else symbol
    )
    numerator = f"<mrow><mo>{exponent}</mo></mrow>"
    denominator = f"<mrow><mo>{symbol}</mo>{variable}</mrow>"
    return f"<mrow><mfrac>{numerator}{denominator}</mfrac>{expression}</mrow>"
