from __future__ import annotations

from neomath.xdlt import lower_to_semantic_ir, parse_xdlt
from neomath.xdlt.math import lower_to_semantic, parse_math
from neomath.xdlt.verification import verify_document_assertions


def _results(hw: str) -> list[dict]:
    ir = lower_to_semantic_ir(parse_xdlt(hw))
    return [result.to_dict() for result in verify_document_assertions(ir)]


def _single_result(hw: str) -> dict:
    results = _results(hw)
    assert len(results) == 1
    return results[0]


# --- verification states ----------------------------------------------


def test_valid_identity() -> None:
    result = _single_result(
        """#context {
    x: Real
}

#assert:identity {
    claim x + 0 == x
}
"""
    )
    assert result["status"] == "valid"
    assert result["assertionId"] == "assert:identity"


def test_invalid_equation() -> None:
    result = _single_result(
        """#context {
    x: Real
}

#assert:false {
    claim x + 1 == x
}
"""
    )
    assert result["status"] == "invalid"


def test_expanded_square_valid() -> None:
    result = _single_result(
        """#context {
    x: Real
}

#assert:expand {
    claim (x + 1)^2 == x^2 + 2x + 1
}
"""
    )
    assert result["status"] == "valid"


def test_differentiate_valid() -> None:
    result = _single_result(
        """#context {
    x: Real
}

#assert:deriv {
    claim differentiate(x^2, x) == 2x
}
"""
    )
    assert result["status"] == "valid"


def test_substitute_reference_valid() -> None:
    result = _single_result(
        r"""$$ #eq:foo
x + 1 = 2
$$

#assert:subst {
    claim substitute(#eq:foo, x=1)
}
"""
    )
    assert result["status"] == "valid"


def test_claim_equation_reference_valid() -> None:
    result = _single_result(
        r"""#context {
    x: Real
}

$$ #eq:identity
(x + 1)^2 = x^2 + 2x + 1
$$

#assert:claim-eq {
    claim #eq:identity
}
"""
    )
    assert result["status"] == "valid"


def test_unknown_is_not_invalid() -> None:
    # f is an undefined function, so the equation cannot be decided
    # -> unknown, never invalid.
    result = _single_result(
        """#assert:unknown-check {
    claim f(x) == 1
}
"""
    )
    assert result["status"] == "unknown"


def test_wrong_reference_type_is_error() -> None:
    result = _single_result(
        """#thm:foo {
    body
}

#assert:bad-type {
    claim substitute(#thm:foo, x=0)
}
"""
    )
    assert result["status"] == "error"
    codes = [d["code"] for d in result["diagnostics"]]
    assert "INVALID_SEMANTIC_REFERENCE_TYPE" in codes


def test_unresolved_reference_is_error() -> None:
    result = _single_result(
        """#assert:bad-ref {
    claim substitute(#eq:missing, x=0)
}
"""
    )
    assert result["status"] == "error"
    codes = [d["code"] for d in result["diagnostics"]]
    assert "UNRESOLVED_SEMANTIC_REFERENCE" in codes


# --- requirements / assumptions ---------------------------------------


def test_requirements_produce_valid_with_conditions() -> None:
    result = _single_result(
        """#context {
    x: Real
}

#assert:sqrt-req {
    claim sqrt(x^2) == x
    require x >= 0
}
"""
    )
    assert result["status"] == "valid-with-conditions"
    assert result["conditions"] == ["x >= 0"]


def test_context_type_assumption_is_used() -> None:
    # x: Real is enough for x + 0 == x without any requirement.
    result = _single_result(
        """#context {
    x: Real
}

#assert:real-assumption {
    claim x + 0 == x
}
"""
    )
    assert result["status"] == "valid"


def test_unsupported_requirement_is_flagged() -> None:
    result = _single_result(
        """#context {
    x: Real
}

#assert:weird-req {
    claim x + 0 == x
    require x >= 5
}
"""
    )
    # x >= 5 cannot become a basic sympy assumption -> warning; the claim
    # itself is unconditionally true, so the status stays valid.
    codes = [d["code"] for d in result["diagnostics"]]
    assert "UNSUPPORTED_VERIFICATION_REQUIREMENT" in codes
    assert result["status"] == "valid"


# --- cache boundary / semantic hash -----------------------------------


def test_semantic_hash_is_stable_and_sensitive() -> None:
    hw = """#context {
    x: Real
}

#assert:stable {
    claim x + 0 == x
}
"""
    first = _single_result(hw)
    second = _single_result(hw)
    assert first["semanticHash"] == second["semanticHash"]

    changed = _single_result(
        """#context {
    x: Real
}

#assert:stable {
    claim x + 1 == x
}
"""
    )
    assert changed["semanticHash"] != first["semanticHash"]


# --- acceptance document ----------------------------------------------


def test_acceptance_document_runs_end_to_end() -> None:
    hw = r"""#context {
    x: Real
}

$$ #eq:identity
(x + 1)^2 = x^2 + 2x + 1
$$

#assert:expand(using=sympy) {
    claim #eq:identity
}

#assert:derivative(using=sympy) {
    claim differentiate(x^2, x) == 2x
}

#assert:substitution(using=sympy) {
    claim substitute(#eq:identity, x=0)
}
"""
    results = _results(hw)
    assert [r["status"] for r in results] == ["valid", "valid", "valid"]
    assert all(r["semanticHash"] for r in results)


def test_verify_single_assertion_by_id() -> None:
    ir = lower_to_semantic_ir(
        parse_xdlt(
            """#assert:a {
    claim x + 0 == x
}

#assert:b {
    claim x + 1 == x
}
"""
        )
    )
    results = verify_document_assertions(ir, assertion_id="assert:b")
    assert len(results) == 1
    assert results[0].assertion_id == "assert:b"
    assert results[0].status == "invalid"


# --- derivative normalization -----------------------------------------


def test_partial_derivative_first_order() -> None:
    ir = lower_to_semantic(parse_math(r"\frac{\partial u}{\partial t}"))
    assert ir["kind"] == "derivative"
    assert ir["expression"]["name"] == "u"
    assert ir["variable"]["name"] == "t"
    assert ir["order"] == {"kind": "integer", "value": "1"}
    assert ir["partial"] is True


def test_partial_derivative_second_order() -> None:
    ir = lower_to_semantic(parse_math(r"\frac{\partial^2 u}{\partial t^2}"))
    assert ir["kind"] == "derivative"
    assert ir["order"] == {"kind": "integer", "value": "2"}
    assert ir["partial"] is True


def test_partial_derivative_symbolic_order() -> None:
    ir = lower_to_semantic(parse_math(r"\frac{\partial^n f}{\partial x^n}"))
    assert ir["kind"] == "derivative"
    assert ir["order"]["kind"] == "symbol_ref"
    assert ir["order"]["name"] == "n"


def test_mixed_partial_derivative() -> None:
    ir = lower_to_semantic(parse_math(r"\frac{\partial^2 u}{\partial x \partial y}"))
    assert ir["kind"] == "derivative"
    assert len(ir["variables"]) == 2
    assert ir["variables"][0]["variable"]["name"] == "x"
    assert ir["variables"][1]["variable"]["name"] == "y"
    assert ir["partial"] is True
