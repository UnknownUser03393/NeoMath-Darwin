"""Math audit regressions: unsupported verification must fail closed.

Run with the original desktop/src on PYTHONPATH. Tests do not patch production code.
"""
from threading import Event
from time import perf_counter

import neomath_core
import pytest
import sympy as sp

from neomath.bridge import NeoMathBridge
from neomath.cas_worker import handle
from neomath.core_client import NeoMathCoreClient
from neomath.edlatex.backends.base import BackendContext, StepClaim
from neomath.edlatex.backends.sympy_backend import SymPyBackend, _sample_equivalence
from neomath.xdlt import lower_to_semantic_ir, parse_xdlt
from neomath.xdlt.verification import verify_document_assertions


def core(source):
    response = neomath_core.run_trace({"source": source})
    assert response["ok"], response
    return response["result"]


def cas(source):
    return handle("runTrace", {"document": {"source": source}})


def auto(source):
    # Math methods need only Core and cancellation, avoiding workspace/AI side effects.
    bridge = NeoMathBridge.__new__(NeoMathBridge)
    bridge.core = NeoMathCoreClient()
    bridge._cancel = Event()
    result = bridge.runTrace({"engine": "auto", "document": {"source": source}})
    assert result["ok"], result
    return result["result"]


def xdlt(claim, requirement=""):
    source = "#context {\nx: Real\n}\n#assert:a {\nclaim " + claim + "\n" + requirement + "\n}\n"
    results = verify_document_assertions(lower_to_semantic_ir(parse_xdlt(source)))
    assert len(results) == 1
    return results[0].to_dict()


@pytest.mark.parametrize("run", [core, cas, auto])
@pytest.mark.parametrize("source,values", [
    ("x^2=4", ["-2", "2"]), ("x^2=x", ["0", "1"]), ("x^2=0", ["0"]),
])
def test_complete_small_polynomial_sets(run, source, values):
    assert run(source)["states"][0]["solutionSet"]["values"] == values


@pytest.mark.parametrize("run", [core, cas, auto])
def test_positive_candidate_does_not_prove_completeness(run):
    trace = run("x^2=4\nx=2")
    assert trace["relations"][0]["lostSolutions"] == ["-2"]
    assert trace["diagnostics"][1]["status"] == "root_fault"
    probe = neomath_core.evaluate_probe({"source": "x^2=4"}, {"value": "2"})["result"]
    assert probe["steps"][0]["predicateResult"] is True
    assert "completeness" not in probe and "certificate" not in probe


@pytest.mark.parametrize("value,truth", [("2", True), ("-2", True), ("3", False)])
def test_candidate_membership_exact(value, truth):
    step = neomath_core.evaluate_probe({"source": "x^2=4"}, {"value": value})["result"]["steps"][0]
    assert step["defined"] and step["predicateResult"] is truth


@pytest.mark.parametrize("run", [core, cas, auto])
def test_complete_equivalent_result_has_no_counterexample(run):
    trace = run("x^2=4\nx=2 or x=-2")
    assert trace["relations"][0]["relation"] == "equivalent"
    assert not trace["relations"][0].get("probe")


@pytest.mark.parametrize("run", [core, cas, auto])
def test_division_by_variable_loses_zero(run):
    assert run("x^2=x\nx=1")["relations"][0]["lostSolutions"] == ["0"]


@pytest.mark.parametrize("source,value", [("x/x=1", "0"), ("(x^2-1)/(x-1)=x+1", "1")])
def test_basic_domain_exclusions(source, value):
    state = core(source)["states"][0]
    assert value in state["domain"]["excluded"]
    probe = neomath_core.evaluate_probe({"source": source}, {"value": value})["result"]["steps"][0]
    assert probe["defined"] is False and probe["predicateResult"] is None


@pytest.mark.parametrize("source,display", [
    ("sqrt(x^2)=x", "Interval(0, oo)"),
    ("sqrt(x)^2=x", "Interval(0, oo)"),
])
def test_square_root_real_solution_conditions(source, display):
    assert auto(source)["states"][0]["solutionSet"]["display"] == display


def test_absolute_value_identity_and_two_branches():
    assert auto("sqrt(x^2)=abs(x)")["states"][0]["solutionSet"]["kind"] == "all_real"
    assert auto("abs(x)=2")["states"][0]["solutionSet"]["values"] == ["-2", "2"]
    assert auto("1/x=0")["states"][0]["solutionSet"]["kind"] == "empty"


def test_unknown_cas_is_not_false():
    state = auto("sin(x)=x")["states"][0]
    assert state["trustLevel"] == "unverified" and state["solutionSet"]["kind"] == "unverified"
    assert xdlt("x > 0")["status"] == "unknown"


def test_all_sample_points_matching_is_not_proof():
    x = sp.Symbol("x")
    polynomial = (x-1)*(x-2)*(x-3)*(x+1)*(2*x-1)
    assert _sample_equivalence(polynomial, sp.Integer(0), perf_counter(), 5, None) is None
    result = SymPyBackend().validate(StepClaim(str(polynomial), "0", "simplify"))
    assert result.status == "unknown"


def test_numeric_probe_false_is_not_universal_false():
    result = neomath_core.evaluate_probe({"source": "x^2=4"}, {"value": "0"})["result"]
    assert result["steps"][0]["predicateResult"] is False
    assert core("x^2=4")["states"][0]["solutionSet"]["values"] == ["-2", "2"]


@pytest.mark.parametrize("run", [core, auto])
def test_radical_cannot_claim_empty_without_completeness(run):
    state = run("sqrt(x)=x-1")["states"][0]
    assert state["solutionSet"]["kind"] != "empty" or state["trustLevel"] == "unverified"


def test_radical_solve_must_not_certify_contradiction():
    result = neomath_core.execute_transformation({"source": "sqrt(x)=x-1"}, 0, {"intent": "solve"})["result"]
    assert not (result["applied"] and result["source"] == "0 = 1" and result["certificate"]["status"] == "verified")


@pytest.mark.parametrize("source", ["1/(1/x)=x", "(1/x)^0=1", "1/(x^2-2)=1/(x^2-2)"])
def test_nontrivial_domain_must_not_be_all_real(source):
    state = core(source)["states"][0]
    assert state["domain"]["kind"] != "all_real" or state["trustLevel"] == "unverified"


def test_disjunction_order_must_not_change_solution_union():
    for source in ("x=0 or x/x=1", "x/x=1 or x=0"):
        state = core(source)["states"][0]
        assert state["trustLevel"] == "unverified"
        assert state["solutionSet"]["kind"] == "unverified"


def test_forward_implication_points_from_source_to_target():
    assert core("x=2\nx^2=4")["relations"][0]["relation"] == "forward_implication"


def test_real_defined_irrational_probe_not_undefined():
    step = neomath_core.evaluate_probe({"source": "sqrt(x)=1"}, {"value": "2"})["result"]["steps"][0]
    assert step["defined"] is True


@pytest.mark.parametrize("target,key,missing", [("{2}", "possibleLostSolutions", "{-2}"), ("{-2,2,3}", "possibleAddedSolutions", "{3}")])
def test_edlatex_completeness_difference_direction(target, key, missing):
    result = SymPyBackend().validate(StepClaim("x^2=4", target, "solve-equation"))
    assert missing in getattr(result, "possible_lost_solutions" if key == "possibleLostSolutions" else "possible_added_solutions")


def test_edlatex_domain_change_is_not_unconditionally_valid():
    result = SymPyBackend().validate(StepClaim("x/x", "1", "simplify"))
    assert result.status != "valid" or result.required_conditions


def test_edlatex_equivalence_respects_nonnegative_context():
    result = SymPyBackend().validate(StepClaim("sqrt(x^2)", "x", "simplify"), BackendContext(nonnegative_symbols={"x"}))
    assert result.status in ("valid", "valid-with-conditions", "unknown")


def test_xdlt_decimal_identity_must_not_be_refuted_by_roundoff():
    assert xdlt("0.1+0.2 == 0.3")["status"] != "invalid"


def test_xdlt_cannot_refute_claim_that_is_its_own_requirement():
    assert xdlt("x == 2", "require x == 2")["status"] != "invalid"


def test_xdlt_division_identity_has_nonzero_obligation():
    result = xdlt("x/x == 1")
    assert result["status"] != "valid" or result["conditions"]


def test_timeout_and_cancel_are_unknown():
    cancelled = Event()
    cancelled.set()
    result = SymPyBackend().validate(StepClaim("x+1", "x+1", "simplify"), cancel=cancelled)
    assert result.status == "unknown" and result.timed_out


def test_unknown_core_cannot_issue_certificate_even_for_same_expression():
    result = neomath_core.execute_transformation({"source": "1/(x^2-2)=1/(x^2-2)"}, 0, {"intent": "verify"})["result"]
    assert not result["applied"]


def test_cas_inline_calculus_does_not_erase_domain():
    assert cas("diff(x/x,x)=0")["states"][0]["trustLevel"] == "unverified"


def test_xdlt_nonzero_assumption_discharges_division_obligation():
    assert xdlt("x/x == 1", "require x != 0")["status"] == "valid-with-conditions"


def test_unknown_results_name_their_verification_target():
    state = core("sqrt(x)=x-1")["states"][0]
    assert state["verification"]["status"] == "unknown"
    assert state["verification"]["target"] == "solution_completeness"
    assert state["verification"]["limitations"]
    assert cas("x+1")["states"][0]["verification"]["status"] == "unknown"


def test_probe_unknown_is_not_false_and_false_is_scoped():
    uncertain = neomath_core.evaluate_probe({"source": "sqrt(x)=1"}, {"value": "2"})["result"]["steps"][0]
    assert uncertain["predicateResult"] is None
    assert uncertain["verificationStatus"] == "unknown"
    rejected = neomath_core.evaluate_probe({"source": "x^2=4"}, {"value": "3"})["result"]["steps"][0]
    assert rejected["verificationStatus"] == "refuted"
    assert rejected["verificationTarget"] == "predicate_at_assignment"
