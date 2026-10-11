from __future__ import annotations

from neomath.xdlt import (
    lower_to_semantic,
    lower_to_semantic_ir,
    parse_math,
    parse_xdlt,
    resolve_symbols,
)
from neomath.xdlt.math import collect_math_diagnostics
from neomath.xdlt.math.nodes import (
    AddNode,
    FractionNode,
    FunctionCallNode,
    IntegerNode,
    PowerNode,
    RelationNode,
    SubscriptNode,
    SymbolNode,
)
from neomath.xdlt.resolve import Scope, SymbolDecl


def _ir(source: str) -> dict:
    ast = parse_math(source)
    return lower_to_semantic(ast)


def test_arithmetic_precedence() -> None:
    ast = parse_math("1 + 2 * 3")
    assert isinstance(ast, AddNode)
    assert [operand.kind for operand in ast.operands] == ["integer", "multiply"]
    assert ast.operands[1].operands[0].value == "2"


def test_power_and_subscript() -> None:
    power = parse_math("x^2")
    assert isinstance(power, PowerNode)
    assert isinstance(power.base, SymbolNode) and power.base.name == "x"
    assert isinstance(power.exponent, IntegerNode) and power.exponent.value == "2"

    subscript = parse_math("x_n")
    assert isinstance(subscript, SubscriptNode)
    assert isinstance(subscript.subscript, SymbolNode) and subscript.subscript.name == "n"

    both = parse_math("x_n^2")
    assert both.kind == "power"
    assert both.base.kind == "subscript"


def test_fraction_is_structured() -> None:
    ast = parse_math(r"\frac{x^2 + 1}{L}")
    assert isinstance(ast, FractionNode)
    # The braced numerator is a group; lowering unwraps it.
    numerator = ast.numerator
    assert numerator.kind == "group"
    assert numerator.inner.kind == "add"
    assert ast.denominator.kind == "group"
    assert ast.denominator.inner.kind == "symbol"
    ir = _ir(r"\frac{x^2 + 1}{L}")
    assert ir["kind"] == "fraction"
    assert ir["numerator"]["kind"] == "add"
    assert ir["numerator"]["operands"][0]["kind"] == "power"


def test_function_calls() -> None:
    ast = parse_math(r"\sin x")
    assert isinstance(ast, FunctionCallNode)
    assert ast.name == "sin"
    assert ast.args[0].kind == "symbol"

    parenthesized = parse_math(r"\cos(x + 1)")
    assert isinstance(parenthesized, FunctionCallNode)
    assert parenthesized.name == "cos"
    assert _ir(r"\cos(x + 1)") == {
        "kind": "function_call",
        "name": "cos",
        "arguments": [
            {
                "kind": "add",
                "operands": [
                    {"kind": "symbol_ref", "name": "x", "symbolId": None},
                    {"kind": "integer", "value": "1"},
                ],
            }
        ],
    }


def test_greek_symbol_normalization() -> None:
    ast = parse_math(r"\alpha + 1")
    assert isinstance(ast, AddNode)
    symbol = ast.operands[0]
    assert isinstance(symbol, SymbolNode)
    assert symbol.name == "alpha"
    assert symbol.spelling == r"\alpha"


def test_relation_and_equation() -> None:
    relation = parse_math("x^2 + 1 = L")
    assert isinstance(relation, RelationNode)
    assert relation.operator == "="
    assert _ir("x^2 + 1 = L")["kind"] == "equation"

    less = parse_math("x < 1")
    assert isinstance(less, RelationNode)
    assert less.operator == "<"
    assert _ir("x < 1")["kind"] == "relation"


def test_implicit_multiplication_normalizes() -> None:
    implicit = _ir("2x")
    explicit = _ir(r"2 \cdot x")
    assert implicit == {
        "kind": "multiply",
        "operands": [
            {"kind": "integer", "value": "2"},
            {"kind": "symbol_ref", "name": "x", "symbolId": None},
        ],
    }
    assert implicit == explicit


def test_unknown_command_is_loss_tolerant() -> None:
    ast = parse_math(r"\unknowncommand{x} + 1")
    codes = [diagnostic.code for diagnostic in collect_math_diagnostics(ast)]
    assert "UNSUPPORTED_MATH_COMMAND" in codes
    assert ast.kind == "add"
    assert ast.operands[0].kind == "opaque"


def test_malformed_math_is_recoverable() -> None:
    ast = parse_math(r"\frac{x}{")
    codes = [diagnostic.code for diagnostic in collect_math_diagnostics(ast)]
    assert "MATH_PARSE_ERROR" in codes
    assert ast.kind == "fraction"


def test_source_is_preserved_on_nodes() -> None:
    ast = parse_math(r"x^2")
    assert ast.source == "x^2"
    assert ast.range.start == 0
    assert ast.range.end == 3


def test_integral_with_differential() -> None:
    ir = _ir(r"\int_0^1 f(x)\,dx")
    assert ir["kind"] == "integral"
    assert ir["variable"] == "x"
    assert ir["body"]["kind"] == "function_call"


def test_partial_derivative_fraction() -> None:
    ir = _ir(r"\frac{\partial u}{\partial t}")
    assert ir["kind"] == "derivative"
    assert ir["expression"]["name"] == "u"
    assert ir["variable"]["name"] == "t"


def test_sum_bounds_variable_extraction() -> None:
    ir = _ir(r"\sum_{n=1}^N x_n")
    assert ir["kind"] == "sum"
    assert ir["variable"] == "n"
    assert ir["lower"] == {"kind": "integer", "value": "1"}


# --- symbol resolution ------------------------------------------------


def _scope_with(names: dict[str, str]) -> Scope:
    scope = Scope(None, "doc", "document")
    for name, symbol_id in names.items():
        scope.declare(SymbolDecl(name, symbol_id, "Real", [], 0))
    return scope


def test_symbol_binding() -> None:
    scope = _scope_with({"alpha": "sym:ctx.global/alpha"})
    ast = parse_math(r"\alpha + 1")
    diagnostics = collect_math_diagnostics(ast)
    resolve_symbols(ast, scope, diagnostics)
    assert ast.operands[0].symbol_id == "sym:ctx.global/alpha"
    assert [d.code for d in diagnostics] == []


def test_unresolved_symbol() -> None:
    scope = _scope_with({})
    ast = parse_math(r"\beta")
    diagnostics = collect_math_diagnostics(ast)
    resolve_symbols(ast, scope, diagnostics)
    assert [d.code for d in diagnostics] == ["UNRESOLVED_SYMBOL"]


def test_builtin_pi_resolves_without_declaration() -> None:
    scope = _scope_with({})
    ast = parse_math(r"\pi")
    diagnostics = collect_math_diagnostics(ast)
    resolve_symbols(ast, scope, diagnostics)
    assert ast.symbol_id == "sym:builtin/pi"
    assert diagnostics == []


# --- context parsing + integration -----------------------------------


def test_context_declarations_are_structured() -> None:
    ir = lower_to_semantic_ir(
        parse_xdlt(
            """#context:global {
    x, t: Real
    L, alpha: Real & Positive
    n: Integer & Positive
}
"""
        )
    )
    context = ir["children"][0]
    assert context["type"] == "Context"
    assert context["namespace"] == "ctx.global"
    declarations = context["declarations"]
    assert declarations[0]["names"] == ["x", "t"]
    assert declarations[1]["type"] == {"name": "Real"}
    assert declarations[1]["properties"] == [{"name": "Positive"}]
    assert declarations[2]["properties"] == [{"name": "Positive"}]


def test_context_symbols_resolve_in_equation() -> None:
    ir = lower_to_semantic_ir(
        parse_xdlt(
            r"""#context:global {
    x, t, alpha: Real
}

$$ #eq:heat
\alpha x + t = 0
$$
"""
        )
    )
    equation = next(child for child in ir["children"] if child["type"] == "Equation")
    assert equation["id"] == "eq:heat"
    assert equation["symbolReferences"] == [
        "sym:ctx.global/alpha",
        "sym:ctx.global/x",
        "sym:ctx.global/t",
    ]
    assert equation["mathDiagnostics"] == []
    # Semantic IR carries resolved symbol ids.
    lhs = equation["semanticMathIr"]["lhs"]
    assert lhs["operands"][0]["kind"] == "multiply"
    assert lhs["operands"][0]["operands"][1]["symbolId"] == "sym:ctx.global/x"


def test_duplicate_symbol_declaration() -> None:
    ir = lower_to_semantic_ir(
        parse_xdlt(
            """#context:global {
    x: Real
    x: Integer
}
"""
        )
    )
    codes = [diagnostic["code"] for diagnostic in ir["diagnostics"]]
    assert "DUPLICATE_SYMBOL" in codes


def test_shadowed_symbol_is_warning() -> None:
    ir = lower_to_semantic_ir(
        parse_xdlt(
            """#context:global {
    x: Real
}

#thm:t {
    #context:inner {
        x: Integer
    }

    $x > 0$
}
"""
        )
    )
    codes = [diagnostic["code"] for diagnostic in ir["diagnostics"]]
    assert "SHADOWED_SYMBOL" in codes


def test_nested_context_shadows_outer() -> None:
    ir = lower_to_semantic_ir(
        parse_xdlt(
            """#context:global {
    x: Real
}

#thm:t {
    #context:inner {
        x: Integer
    }

    $x > 0$
}
"""
        )
    )
    theorem = next(child for child in ir["children"] if child["type"] == "Theorem")
    paragraph = next(child for child in theorem["children"] if child["type"] == "Paragraph")
    inline = paragraph["inlineMath"][0]
    # The inner `x` shadows the outer one inside the theorem.
    assert inline["symbolReferences"] == ["sym:ctx.inner/x"]
    assert inline["mathDiagnostics"] == []


def test_invalid_symbol_declaration() -> None:
    ir = lower_to_semantic_ir(
        parse_xdlt(
            """#context:global {
    x: Frobnicate
}
"""
        )
    )
    codes = [diagnostic["code"] for diagnostic in ir["diagnostics"]]
    assert "INVALID_SYMBOL_DECLARATION" in codes


def test_inline_math_resolves_in_paragraph() -> None:
    ir = lower_to_semantic_ir(
        parse_xdlt(
            """#context:global {
    x, t: Real
}

设 $u(x,t)$ 满足。
"""
        )
    )
    paragraph = next(child for child in ir["children"] if child["type"] == "Paragraph")
    inline = paragraph["inlineMath"][0]
    assert inline["rawSource"] == "u(x,t)"
    assert inline["semanticMathIr"]["kind"] == "function_call"
    assert inline["symbolReferences"] == ["sym:ctx.global/x", "sym:ctx.global/t"]


def test_document_survives_unknown_math_command() -> None:
    ir = lower_to_semantic_ir(
        parse_xdlt(
            r"""$$ #eq:a
\unknowncommand{x} + 1
$$
"""
        )
    )
    equation = next(child for child in ir["children"] if child["type"] == "Equation")
    assert equation["id"] == "eq:a"
    codes = [diagnostic["code"] for diagnostic in equation["mathDiagnostics"]]
    assert "UNSUPPORTED_MATH_COMMAND" in codes
    # The document-level diagnostics are empty; the math degraded locally.
    assert all(
        diagnostic["code"] not in ("UNSUPPORTED_MATH_COMMAND", "MATH_PARSE_ERROR")
        for diagnostic in ir["diagnostics"]
    )
