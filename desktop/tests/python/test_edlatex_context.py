from __future__ import annotations

from neomath.edlatex.context import ContextResolver, parse_declarations
from neomath.edlatex.context.scope import ROOT_SCOPE_ID
from neomath.edlatex.document import new_document
from neomath.edlatex.nodes import ContextNode, DerivationNode, FormulaNode, SectionNode


# --- declaration parsing ---------------------------------------------------
def test_parse_declaration_kinds() -> None:
    assert parse_declarations("reals x y")[0].domain == "real"
    assert parse_declarations("integers n")[0].domain == "integer"
    assert parse_declarations("positive a")[0].sign == "positive"
    assert parse_declarations("nonzero b")[0].sign == "nonzero"
    val = parse_declarations("x = -1")[0]
    assert val.kind == "value" and val.relations[0].bound == "-1"
    interval = parse_declarations("-1 <= x <= 1")[0]
    assert {(r.op, r.bound) for r in interval.relations} == {(">=", "-1"), ("<=", "1")}
    assert parse_declarations("0 < x")[0].relations[0].op == ">"  # oriented to symbol
    param = parse_declarations("with mass m = 1.0")[0]
    assert param.kind == "param" and param.label == "mass"
    assert parse_declarations("contract -1 <= x <= 1")[0].kind == "inequality"


# --- scope tree ------------------------------------------------------------
def _acceptance_doc():
    doc = new_document("上下文")
    doc.add_node(ContextNode(declarations=["reals x"]))  # global x ∈ ℝ
    doc.add_node(SectionNode(level=1, title="第一节"))
    doc.add_node(ContextNode(declarations=["x > 0"]))  # section override/refine
    child = doc.add_node(FormulaNode(source="x^2+1", parsed_expression="x^2+1"))
    return doc, child


def test_scope_tree_document_section_derivation() -> None:
    doc = new_document("s")
    doc.add_node(SectionNode(level=1, title="A"))
    d = doc.add_node(DerivationNode(name="d", from_expr="a", to_expr="b", rule="factor"))
    resolver = ContextResolver(doc)
    chain = resolver.tree.chain(resolver.tree.node_to_scope[d.id])
    kinds = [s.kind for s in chain]
    assert kinds == ["document", "section", "derivation"]


# --- effective context (inheritance) --------------------------------------
def test_child_reads_inherited_effective_context() -> None:
    doc, child = _acceptance_doc()
    resolver = ContextResolver(doc)
    ctx = resolver.effective_context(child.id)
    assert ctx["x"].domain == "real"
    assert ctx["x"].lower == "0" and ctx["x"].lower_strict is True
    assert resolver.conflicts_for_node(child.id) == []


def test_inner_domain_overrides_outer() -> None:
    doc = new_document("override")
    doc.add_node(ContextNode(declarations=["reals x"]))
    doc.add_node(SectionNode(level=1, title="s"))
    doc.add_node(ContextNode(declarations=["integers x"]))
    child = doc.add_node(FormulaNode(source="x"))
    resolver = ContextResolver(doc)
    assert resolver.effective_context(child.id)["x"].domain == "integer"
    assert resolver.conflicts_for_node(child.id) == []  # override, not conflict


# --- conflict lifecycle (the headline acceptance) --------------------------
def test_conflict_appears_and_clears() -> None:
    doc, child = _acceptance_doc()

    # No conflict yet.
    assert ContextResolver(doc).conflicts_for_node(child.id) == []

    # Add x = -1 inside the section -> conflicts with inherited x > 0.
    bad = doc.add_node(ContextNode(declarations=["x = -1"]))
    conflicts = ContextResolver(doc).conflicts_for_node(child.id)
    assert len(conflicts) == 1
    assert conflicts[0].code == "VALUE_VIOLATES_BOUND"
    assert conflicts[0].symbol == "x"

    # Remove the offending declaration -> diagnostic disappears.
    doc.remove_node(bad.id)
    assert ContextResolver(doc).conflicts_for_node(child.id) == []


def test_positive_with_negative_value_conflicts() -> None:
    doc = new_document("c")
    doc.add_node(ContextNode(declarations=["positive a", "a = -3"]))
    node = doc.add_node(FormulaNode(source="a"))
    conflicts = ContextResolver(doc).conflicts_for_node(node.id)
    assert any(c.symbol == "a" for c in conflicts)


def test_non_integer_value_vs_integer_domain_conflicts() -> None:
    doc = new_document("c")
    doc.add_node(ContextNode(declarations=["integers n", "n = 3/2"]))
    node = doc.add_node(FormulaNode(source="n"))
    codes = {c.code for c in ContextResolver(doc).conflicts_for_node(node.id)}
    assert "VALUE_NOT_IN_DOMAIN" in codes


def test_empty_interval_conflicts() -> None:
    doc = new_document("c")
    doc.add_node(ContextNode(declarations=["x > 5", "x < 1"]))
    node = doc.add_node(FormulaNode(source="x"))
    codes = {c.code for c in ContextResolver(doc).conflicts_for_node(node.id)}
    assert "EMPTY_INTERVAL" in codes


def test_x_ge_zero_disables_false_positive_for_negative_root() -> None:
    # Under x >= 0, x = 2 is fine; there must be no spurious conflict.
    doc = new_document("c")
    doc.add_node(ContextNode(declarations=["x >= 0", "x = 2"]))
    node = doc.add_node(FormulaNode(source="x"))
    assert ContextResolver(doc).conflicts_for_node(node.id) == []


# --- incremental recompute -------------------------------------------------
def test_scope_change_only_affects_subtree() -> None:
    doc = new_document("incr")
    doc.add_node(ContextNode(declarations=["reals x"]))
    doc.add_node(SectionNode(level=1, title="A"))
    in_a = doc.add_node(FormulaNode(source="x_a"))
    doc.add_node(SectionNode(level=1, title="B"))
    in_b = doc.add_node(FormulaNode(source="x_b"))

    resolver = ContextResolver(doc)
    section_a_scope = resolver.tree.node_to_scope[in_a.id]
    affected = resolver.affected_node_ids(section_a_scope)

    assert in_a.id in affected
    assert in_b.id not in affected  # sibling section untouched
    # Document root change would affect everything, a leaf section only its own.
    assert resolver.affected_node_ids(ROOT_SCOPE_ID) >= affected


# --- inspector -------------------------------------------------------------
def test_inspect_reports_inheritance_overrides_and_usedby() -> None:
    doc = new_document("inspect")
    doc.add_node(ContextNode(declarations=["reals x"]))
    doc.add_node(SectionNode(level=1, title="s"))
    doc.add_node(ContextNode(declarations=["integers x"]))  # overrides domain
    child = doc.add_node(FormulaNode(source="x + 1", parsed_expression="x+1"))

    report = ContextResolver(doc).inspect(child.id)
    assert [s["kind"] for s in report["inheritance"]] == ["document", "section"]
    assert any(o["symbol"] == "x" and o["kind"] == "domain" for o in report["overrides"])
    assert child.id in report["usedBy"]["x"]  # the formula references x
    assert "x" in report["effectiveContext"]


# --- bridge end-to-end -----------------------------------------------------
def test_bridge_context_methods(tmp_path) -> None:
    from neomath.bridge import NeoMathBridge
    from neomath.config import AppConfig

    config = AppConfig(
        data_dir=tmp_path,
        openai_base_url="https://example.invalid/v1",
        openai_model="qwen-plus",
        openai_api_key=None,
    )
    bridge = NeoMathBridge(config)
    doc, child = _acceptance_doc()
    doc.add_node(ContextNode(declarations=["x = -1"]))
    payload = {"document": doc.to_dict(), "nodeId": child.id}

    resolved = bridge.resolveContext(payload)
    assert resolved["ok"] is True
    assert resolved["result"]["conflicts"]

    inspected = bridge.inspectContext(payload)
    assert inspected["ok"] is True
    assert inspected["result"]["scopeId"]

    diagnostics = bridge.contextDiagnostics({"document": doc.to_dict()})
    assert diagnostics["ok"] is True
    assert diagnostics["result"]["conflicts"]
