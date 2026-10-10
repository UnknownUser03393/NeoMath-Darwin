from __future__ import annotations

import neomath_core

from neomath.core_client import NeoMathCoreClient

DEMOS = {
    "lost": "x(x - 1) = 0\nx - 1 = 0\nx = 1",
    "extra": ("sqrt(x) = x - 2\nx = (x - 2)^2\nx^2 - 5x + 4 = 0\nx = 1 or x = 4"),
    "domain": "(x - 1) / (x - 1) = 1\n1 = 1",
}


def run(source: str) -> dict:
    response = NeoMathCoreClient().run_trace({"source": source})
    assert response["ok"], response
    return response["result"]


def test_extension_is_cpp_and_coarse_grained() -> None:
    assert neomath_core.__file__.endswith(".pyd")
    public = {name for name in dir(neomath_core) if not name.startswith("_")}
    assert public == {
        "analyze_document",
        "evaluate_probe",
        "execute_transformation",
        "get_capabilities",
        "get_completions",
        "parse_document",
        "replay",
        "run_trace",
    }
    capabilities = neomath_core.get_capabilities()
    assert capabilities["result"]["core"] == "C++20"


def test_lost_root_demo() -> None:
    result = run(DEMOS["lost"])
    assert result["states"][0]["solutionSet"]["values"] == ["0", "1"]
    assert result["relations"][0]["lostSolutions"] == ["0"]
    assert result["activeProbe"]["value"] == "0"
    assert [item["status"] for item in result["diagnostics"]] == [
        "valid",
        "root_fault",
        "tainted",
    ]


def test_extraneous_root_demo() -> None:
    result = run(DEMOS["extra"])
    assert result["states"][0]["solutionSet"]["values"] == ["4"]
    assert result["states"][1]["solutionSet"]["values"] == ["1", "4"]
    assert result["relations"][0]["gainedSolutions"] == ["1"]
    assert result["activeProbe"]["value"] == "1"


def test_domain_expansion_demo() -> None:
    result = run(DEMOS["domain"])
    assert result["states"][0]["domain"]["excluded"] == ["1"]
    assert result["states"][0]["solutionSet"]["kind"] == "all_real_excluding_finite"
    assert result["relations"][0]["domainExpanded"]
    assert not result["activeProbe"]["previousDefined"]
    assert result["activeProbe"]["currentDefined"]


def test_semantic_completion_certificate() -> None:
    document = {"source": "x^2 - 4 = 0"}
    completions = NeoMathCoreClient().get_completions(document, 0)
    factor = next(item for item in completions["result"] if item["id"] == "factor")
    assert factor["available"]
    assert factor["preview"] == "(x - 2)(x + 2) = 0"
    transformed = NeoMathCoreClient().execute_transformation(
        document,
        0,
        {"intent": "factor"},
    )
    assert transformed["result"]["applied"]
    assert transformed["result"]["certificate"]["status"] == "verified"
    assert transformed["result"]["certificate"]["solutionInvariant"] == (
        "exact_solution_set_preserved"
    )


def test_parse_errors_are_structured() -> None:
    result = NeoMathCoreClient().parse_document("sin(x) = 0")
    assert result["ok"]
    error = result["result"]["steps"][0]["error"]
    assert error["type"] == "parse_error"
    assert error["code"] == "UNKNOWN_IDENTIFIER"
    assert isinstance(error["start"], int)


def test_integer_overflow_is_structured_with_user_message() -> None:
    """Overflowing exact rational work must not be silent.

    Uses a product that exceeds checked int64 during analysis. The API keeps
    INTEGER_OVERFLOW on MathState.reason and a non-empty Chinese/user message
    on the diagnostic that still names the code.
    """
    response = NeoMathCoreClient().run_trace({"source": "9223372036854775807 * 2 = x"})
    assert response["ok"], response
    result = response["result"]
    state = result["states"][0]
    assert state["reason"] == "INTEGER_OVERFLOW"
    assert state["verificationStatus"] == "unverified"
    diagnostic = result["diagnostics"][0]
    assert diagnostic["status"] == "unverified"
    message = diagnostic["message"]
    assert isinstance(message, str) and message
    assert "INTEGER_OVERFLOW" in message
    assert len(message) > len("INTEGER_OVERFLOW")
    # Student-facing path must not be the bare machine code alone.
    assert "64" in message or "有理" in message or "范围" in message


def test_replay_reuses_only_the_unchanged_prefix() -> None:
    client = NeoMathCoreClient()
    original = "x = 1\nx + 1 = 2\nx = 1"
    client.run_trace({"source": original})

    changed = "x = 1\nx + 1 = 2\nx = 2"
    result = client.replay({"source": changed}, 2)
    assert result["ok"]
    assert result["metrics"]["cacheHits"] == 2
    assert result["result"]["states"][2]["solutionSet"]["values"] == ["2"]
    assert result["result"]["diagnostics"][2]["status"] == "root_fault"


def test_replay_validates_the_prefix_instead_of_trusting_changed_step() -> None:
    client = NeoMathCoreClient()
    client.run_trace({"source": DEMOS["lost"]})
    result = client.replay({"source": "x = 2\nx - 1 = 1"}, 2)
    assert result["ok"]
    assert result["metrics"]["cacheHits"] == 0


def test_probe_runs_through_the_whole_derivation() -> None:
    result = NeoMathCoreClient().evaluate_probe(
        {"source": DEMOS["lost"]},
        {"value": "0"},
    )
    assert result["ok"], result
    steps = result["result"]["steps"]
    assert [item["predicateResult"] for item in steps] == [True, False, False]
    assert steps[0]["leftValue"] == "0"
    assert steps[0]["residual"] == "0"


def test_all_v1_transformations_return_verified_certificates() -> None:
    client = NeoMathCoreClient()
    cases = [
        ("(x - 1)(x + 1) = 0", {"intent": "expand"}, "expand"),
        ("2x + 3 = 7", {"intent": "move_terms"}, "move_terms"),
        ("x = 1", {"intent": "multiply", "arguments": {"expression": "x"}}, "multiply"),
        ("x(x - 1) = 0", {"intent": "divide", "arguments": {"expression": "x"}}, "divide"),
        ("sqrt(x) = x - 2", {"intent": "square_both_sides"}, "square_both_sides"),
        ("2x = 2", {"intent": "solve"}, "solve"),
        ("x = 1", {"intent": "verify"}, "verify"),
    ]
    for source, intent, kind in cases:
        result = client.execute_transformation({"source": source}, 0, intent)
        assert result["ok"], result
        assert result["result"]["applied"], result
        certificate = result["result"]["certificate"]
        assert certificate["kind"] == kind
        assert certificate["status"] == "verified"
        assert certificate["verificationMethod"] != "unverified"

    conditional = client.execute_transformation(
        {"source": "x(x - 1) = 0"},
        0,
        {"intent": "divide", "arguments": {"expression": "x"}},
    )
    assert conditional["result"]["certificate"]["requiredAssumptions"][0]["code"] == "NONZERO"


def test_integer_limit_is_a_structured_parse_error() -> None:
    response = NeoMathCoreClient().parse_document(f"{'9' * 200}x = 1")
    assert response["ok"], response
    error = response["result"]["steps"][0]["error"]
    assert error["type"] == "parse_error"
    assert error["code"] == "INTEGER_LIMIT"
