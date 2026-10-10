from __future__ import annotations

from neomath.xdlt import (
    lower_to_semantic_ir,
    parse_assert_body,
    parse_sel,
    parse_xdlt,
)
from neomath.xdlt.sel import collect_sel_diagnostics
from neomath.xdlt.sel.nodes import (
    BinaryNode,
    CallNode,
    ComparisonNode,
    LiteralNode,
    LogicalNode,
    NamedArgumentNode,
    SemanticReferenceNode,
    SymbolNode,
    UnaryNode,
)

# --- SEL parser --------------------------------------------------------


def test_operator_precedence() -> None:
    ast = parse_sel("1 + 2 * 3")
    assert isinstance(ast, BinaryNode)
    assert ast.operator == "+"
    assert isinstance(ast.right, BinaryNode)
    assert ast.right.operator == "*"


def test_power_is_right_associative() -> None:
    ast = parse_sel("2^3^2")
    assert isinstance(ast, BinaryNode)
    assert ast.operator == "^"
    assert isinstance(ast.right, BinaryNode)
    assert ast.right.operator == "^"


def test_unary_minus_binds_tighter_than_power() -> None:
    ast = parse_sel("-2^2")
    assert isinstance(ast, BinaryNode)
    assert ast.operator == "^"
    assert isinstance(ast.left, UnaryNode)


def test_logical_precedence_or_over_and() -> None:
    ast = parse_sel("a and b or c")
    assert isinstance(ast, LogicalNode)
    assert ast.operator == "or"
    assert isinstance(ast.left, LogicalNode)
    assert ast.left.operator == "and"


def test_comparison_chain() -> None:
    ast = parse_sel("x >= 0")
    assert isinstance(ast, ComparisonNode)
    assert ast.operator == ">="
    assert isinstance(ast.left, SymbolNode)
    assert ast.left.name == "x"


def test_calls_and_named_arguments() -> None:
    ast = parse_sel("substitute(#eq:final, t=0)")
    assert isinstance(ast, CallNode)
    assert ast.name == "substitute"
    reference = ast.args[0]
    assert isinstance(reference, SemanticReferenceNode)
    assert reference.name == "eq:final"
    named = ast.args[1]
    assert isinstance(named, NamedArgumentNode)
    assert named.name == "t"
    assert isinstance(named.value, LiteralNode)
    assert named.value.value == "0"


def test_semantic_reference_and_selector() -> None:
    reference = parse_sel("#thm:foo")
    assert isinstance(reference, SemanticReferenceNode)
    assert reference.name == "thm:foo"

    selector = parse_sel("#exec:plot[0]")
    assert selector.kind == "selector"
    assert selector.index == "0"
    assert selector.reference.name == "exec:plot"


def test_implicit_multiplication() -> None:
    ast = parse_sel("2x")
    assert isinstance(ast, BinaryNode)
    assert ast.operator == "*"


def test_literals() -> None:
    assert parse_sel("1").value == "1"
    assert parse_sel("3.14").value_type == "real"
    assert parse_sel("true").value == "true"
    assert parse_sel('"abc"').value == "abc"
    assert parse_sel("null").value_type == "null"


def test_malformed_sel_is_recoverable() -> None:
    ast = parse_sel("substitute(#eq:final,")
    codes = [d.code for d in collect_sel_diagnostics(ast)]
    assert "SEL_PARSE_ERROR" in codes
    assert ast.kind == "call"


# --- assertion body parsing -------------------------------------------


def test_assert_body_claim_and_requirements() -> None:
    body = parse_assert_body(
        "claim substitute(#eq:final, t=0) == #eq:initial\nrequire L > 0\nrequire alpha > 0\n",
        10,
    )
    assert body.claim is not None
    assert body.claim_source == "substitute(#eq:final, t=0) == #eq:initial"
    assert len(body.requirements) == 2
    assert len(body.requirement_sources) == 2
    assert body.diagnostics == []


def test_assert_body_missing_claim() -> None:
    body = parse_assert_body("require L > 0\n", 0)
    codes = [d.code for d in body.diagnostics]
    assert "MISSING_CLAIM" in codes


def test_assert_body_duplicate_claim() -> None:
    body = parse_assert_body("claim x == 1\nclaim y == 2\n", 0)
    codes = [d.code for d in body.diagnostics]
    assert "DUPLICATE_CLAIM" in codes


def test_assert_body_unknown_statement() -> None:
    body = parse_assert_body("claim x == 1\nbanana foo\n", 0)
    codes = [d.code for d in body.diagnostics]
    assert "UNKNOWN_ASSERTION_STATEMENT" in codes


def test_assert_body_malformed_sel_diagnostic() -> None:
    body = parse_assert_body("claim substitute(#eq:final,\n", 0)
    codes = [d.code for d in body.diagnostics]
    assert "SEL_PARSE_ERROR" in codes


# --- reference resolution + document integration ----------------------


def test_assert_reference_resolves_through_document() -> None:
    ir = lower_to_semantic_ir(
        parse_xdlt(
            r"""$$ #eq:final
x + 1 = 2
$$

#assert:check(using=sympy) {
    claim substitute(#eq:final, x=0)
}
"""
        )
    )
    assertion = next(child for child in ir["children"] if child["type"] == "Assertion")
    assert assertion["id"] == "assert:check"
    assert assertion["verifier"] == "sympy"
    assert assertion["claim"]["kind"] == "call"
    reference = assertion["claim"]["arguments"][0]
    assert reference["targetId"] == "eq:final"
    assert reference["targetType"] == "Equation"
    assert assertion["verification"]["status"] == "unverified"


def test_unresolved_reference_diagnostic() -> None:
    ir = lower_to_semantic_ir(
        parse_xdlt(
            """#assert:check {
    claim #eq:missing == 1
}
"""
        )
    )
    codes = [d["code"] for d in ir["diagnostics"]]
    assert "UNRESOLVED_SEMANTIC_REFERENCE" in codes


def test_assert_symbols_resolve_against_context() -> None:
    ir = lower_to_semantic_ir(
        parse_xdlt(
            """#context:global {
    x: Real
}

#assert:check {
    claim x + 0 == x
}
"""
        )
    )
    assertion = next(child for child in ir["children"] if child["type"] == "Assertion")
    assert assertion["symbols"]["x"]["symbolId"] == "sym:ctx.global/x"
    assert assertion["symbols"]["x"]["type"] == "Real"
    claim_symbol = assertion["claim"]["left"]["left"]
    assert claim_symbol["symbolId"] == "sym:ctx.global/x"


def test_document_survives_assert_parsing_errors() -> None:
    doc = parse_xdlt(
        """#assert:broken {
    claim substitute(#eq:missing,
    banana
}
"""
    )
    ir = lower_to_semantic_ir(doc)
    codes = [d["code"] for d in ir["diagnostics"]]
    assert "SEL_PARSE_ERROR" in codes
    assert "UNKNOWN_ASSERTION_STATEMENT" in codes
