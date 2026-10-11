from __future__ import annotations

import pytest

from neomath.core_client import NeoMathCoreClient


@pytest.mark.parametrize(
    ("source", "kind", "values", "excluded"),
    [
        ("x(x-1)=0", "finite", ["0", "1"], []),
        ("x^2=x", "finite", ["0", "1"], []),
        ("(x-1)/(x-1)=1", "all_real_excluding_finite", [], ["1"]),
        ("x/x=1", "all_real_excluding_finite", [], ["0"]),
        ("sqrt(x)=x-2", "finite", ["4"], []),
        ("x^2=4", "finite", ["-2", "2"], []),
        ("(x^2-1)/(x-1)=x+1", "all_real_excluding_finite", [], ["1"]),
        ("1/(x-1)=0", "empty", [], []),
        ("2x=2", "finite", ["1"], []),
        ("0x=0", "all_real", [], []),
        ("x^2+1=0", "empty", [], []),
        ("(x-2)^2=0", "finite", ["2"], []),
        ("(x^2-4)/(x-2)=0", "finite", ["-2"], []),
        ("sqrt(x+1)=x-1", "finite", ["3"], []),
    ],
)
def test_golden_solution_sets(
    source: str,
    kind: str,
    values: list[str],
    excluded: list[str],
) -> None:
    response = NeoMathCoreClient().run_trace({"source": source})
    assert response["ok"], response
    solution = response["result"]["states"][0]["solutionSet"]
    assert solution["kind"] == kind
    assert solution["values"] == values
    assert solution["excluded"] == excluded


def test_nonlinear_radical_is_explicitly_unverified() -> None:
    response = NeoMathCoreClient().run_trace({"source": "sqrt(x^2)=x"})
    state = response["result"]["states"][0]
    assert state["verificationStatus"] == "unverified"
    assert state["reason"] == "square_root_form_not_supported"
