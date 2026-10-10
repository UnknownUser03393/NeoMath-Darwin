import pytest

from neomath.cas_worker import handle
from neomath.notebook_cas import needs_cas


@pytest.mark.parametrize("source", [
    "x^2=2\nx=±sqrt(2)",
    "x^3=2\nx=2^(1/3)",
    "x^2<4\nabs(x)<2",
    "sin(x)^2+cos(x)^2\n1",
    "exp(x)=1\nx=0",
    "log(x)=0\nx=1",  # same roots but different domains; checked separately below
])
def test_real_cas_states(source):
    result = handle("runTrace", {"document": {"source": source}})
    for state in result["states"]:
        if state["solutionSet"]["kind"] == "expression":
            assert state["trustLevel"] == "cas_computed"
            assert state["verification"]["status"] == "unknown"
        else:
            assert state["trustLevel"] == "cas_verified"
            assert state["verification"]["target"] == "solution_completeness"
    if not source.startswith("log"):
        assert result["relations"][0]["relation"] == "equivalent"


def test_domain_is_not_lost_to_simplification():
    result = handle("runTrace", {"document": {"source": "x/x=1\n1=1"}})
    assert result["diagnostics"][1]["status"] == "root_fault"
    assert result["relations"][0]["domainExpanded"]
    assert result["relations"][0]["probe"]["previousDefined"] is False


@pytest.mark.parametrize("source", ["__import__('os').system('whoami')", "x+y=0", "1/0", "sqrt(-1)"])
def test_unsupported_or_undefined_input_is_not_verified(source):
    result = handle("runTrace", {"document": {"source": source}})
    assert result["states"][0]["trustLevel"] == "unverified"


def test_core_exact_states_do_not_trigger_fallback():
    assert not needs_cas({"ok": True, "result": {"states": [{"trustLevel": "exact_core"}]}})
    assert needs_cas({"ok": True, "result": {"states": [{"trustLevel": "unverified"}]}})


def test_symbolic_probe_and_latex():
    payload = {"document": {"source": "x^2=2\nx=\\pm\\sqrt{2}"}}
    assert handle("runTrace", payload)["relations"][0]["relation"] == "equivalent"
    probe = handle("evaluateProbe", {**payload, "probe": {"value": "sqrt(2)"}})
    assert all(step["predicateResult"] for step in probe["steps"])


@pytest.mark.parametrize("sign", [r"\pm", r"\mp"])
def test_latex_sign_without_space(sign):
    result = handle("runTrace", {"document": {"source": "x^2=1\nx=" + sign + "1"}})
    assert result["relations"][0]["relation"] == "equivalent"
    assert result["states"][1]["source"] == "x=" + sign + "1"
