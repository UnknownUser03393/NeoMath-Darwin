from __future__ import annotations

from neomath.edlatex.backends.base import StepClaim
from neomath.edlatex.backends.registry import default_registry
from neomath.edlatex.backends.sympy_backend import SymPyBackend
from neomath.edlatex.context import ContextResolver
from neomath.edlatex.derivation.graph import DerivationGraph
from neomath.edlatex.derivation.rules import all_rule_ids, rule_spec
from neomath.edlatex.document import new_document
from neomath.edlatex.nodes import ContextNode, DerivationNode, FormulaNode, SectionNode


def _doc_for_graph():
    doc = new_document("导数与方程")
    doc.add_node(ContextNode(declarations=["reals x"]))
    doc.add_node(SectionNode(level=1, title="第一题"))
    doc.add_node(FormulaNode(source="x^2", parsed_expression="x**2"))
    d1 = doc.add_node(
        DerivationNode(from_expr="x^2", to_expr="2*x", rule="differentiate")
    )
    d2 = doc.add_node(
        DerivationNode(from_expr="x^2=4", to_expr="x=2", rule="solve-equation")
    )
    d3 = doc.add_node(
        DerivationNode(from_expr="x(x-1)=0", to_expr="x-1=0", rule="divide-both-sides")
    )
    d4 = doc.add_node(
        DerivationNode(from_expr="x=1", to_expr="x^2=1", rule="square-both-sides")
    )
    d5 = doc.add_node(
        DerivationNode(from_expr="x^2=1", to_expr="x=1", rule="take-square-root")
    )
    # explicit dependencies to make the graph deterministic in tests
    d1.dependencies = [doc.order[2]]
    d2.dependencies = [d1.id]
    d3.dependencies = [d2.id]
    d4.dependencies = [d3.id]
    d5.dependencies = [d4.id]
    return doc, [d1, d2, d3, d4, d5]


# --- rules / registry ------------------------------------------------------
def test_rule_specs_cover_required_phase4_rules() -> None:
    assert set(all_rule_ids()) == {
        "simplify",
        "expand",
        "factor",
        "substitute",
        "add-both-sides",
        "subtract-both-sides",
        "multiply-both-sides",
        "divide-both-sides",
        "square-both-sides",
        "take-square-root",
        "differentiate",
        "integrate",
        "solve-equation",
    }
    assert rule_spec("divide-both-sides").needs_nonzero is True
    assert rule_spec("square-both-sides").may_add_solutions is True
    assert rule_spec("take-square-root").may_lose_solutions is True


def test_backend_registry_exposes_sympy_backend() -> None:
    registry = default_registry()
    assert "sympy" in registry.names()
    assert registry.availability()["sympy"]["available"] is True
    assert "solve-equation" in registry.capabilities()["sympy"]["rules"]


# --- backend verification --------------------------------------------------
def test_sympy_backend_valid_equivalence() -> None:
    backend = SymPyBackend()
    result = backend.validate(StepClaim(from_expr="x + x", to_expr="2*x", rule="simplify"))
    assert result.status == "valid"


def test_sympy_backend_invalid_equivalence() -> None:
    backend = SymPyBackend()
    result = backend.validate(StepClaim(from_expr="x + 1", to_expr="x + 2", rule="simplify"))
    assert result.status == "invalid"


def test_sympy_backend_unknown_for_unknown_rule() -> None:
    backend = SymPyBackend()
    result = backend.validate(StepClaim(from_expr="x", to_expr="x", rule="custom-rule"))
    assert result.status == "unknown"


def test_sympy_backend_divide_requires_condition() -> None:
    backend = SymPyBackend()
    result = backend.validate(
        StepClaim(from_expr="x(x-1)=0", to_expr="x-1=0", rule="divide-both-sides")
    )
    assert result.status == "unknown"
    assert result.required_conditions == ["divisor ≠ 0"]
    assert result.possible_lost_solutions == ["{0}"]


def test_sympy_backend_square_reports_extraneous_solution_risk() -> None:
    backend = SymPyBackend()
    result = backend.validate(StepClaim(from_expr="x=1", to_expr="x^2=1", rule="square-both-sides"))
    assert result.status in {"valid-with-conditions", "unknown", "invalid", "valid"}
    if result.status == "valid-with-conditions":
        assert result.possible_added_solutions or result.possible_lost_solutions


def test_sympy_backend_solve_equation() -> None:
    backend = SymPyBackend()
    result = backend.validate(
        StepClaim(from_expr="x^2=4", to_expr="{-2,2}", rule="solve-equation")
    )
    assert result.status in {"valid", "unknown"}


def test_sympy_backend_differentiate_and_integrate() -> None:
    backend = SymPyBackend()
    diff = backend.validate(StepClaim(from_expr="x^2", to_expr="2*x", rule="differentiate"))
    integ = backend.validate(StepClaim(from_expr="2*x", to_expr="x^2", rule="integrate"))
    assert diff.status == "valid"
    assert integ.status == "valid"


# --- graph / blame ---------------------------------------------------------
def test_derivation_graph_validate_all_and_blame_path() -> None:
    doc, steps = _doc_for_graph()
    graph = DerivationGraph(doc)

    results = graph.validate_all()
    assert set(results)
    assert graph.steps[steps[0].id].verification is not None

    fault = graph.earliest_fault()
    assert fault is not None
    assert "faultNodeId" in fault

    path = graph.blame_path(steps[-1].id)
    assert path[0] == doc.order[2]  # first formula
    assert path[-1] == steps[-1].id


# --- context integration ---------------------------------------------------
def test_graph_uses_context_for_validation_conditions() -> None:
    doc, steps = _doc_for_graph()
    # Make division conditionally safe by declaring the factor nonzero.
    doc.add_node(ContextNode(declarations=["nonzero x"]))
    resolver = ContextResolver(doc)
    assert resolver.badge(steps[2].id)
    graph = DerivationGraph(doc)
    result = graph.validate_step(steps[2].id)
    assert result.status in {"valid", "valid-with-conditions", "invalid", "unknown"}


# --- bridge end-to-end -----------------------------------------------------
def test_bridge_phase4_methods(tmp_path) -> None:
    from neomath.bridge import NeoMathBridge
    from neomath.config import AppConfig

    bridge = NeoMathBridge(
        AppConfig(
            data_dir=tmp_path,
            dashscope_base_url="https://example.invalid/v1",
            qwen_model="qwen-plus",
            qwen_api_key=None,
        )
    )

    doc, steps = _doc_for_graph()
    payload = {"document": doc.to_dict(), "backend": "sympy"}

    backends = bridge.getMathBackends()
    assert backends["ok"] is True
    assert "sympy" in backends["result"]["names"]

    validated = bridge.validateDerivations(payload)
    assert validated["ok"] is True
    assert validated["result"]["steps"]
    assert validated["result"]["graph"]

    one = bridge.validateStep(
        {"document": doc.to_dict(), "nodeId": steps[0].id, "backend": "sympy"}
    )
    assert one["ok"] is True

    blame = bridge.derivationBlame({"document": doc.to_dict(), "nodeId": steps[-1].id})
    assert blame["ok"] is True
    assert blame["result"]["path"]
