from __future__ import annotations

from pathlib import Path

from neomath.documents.model import NeoMathDocument
from neomath.documents.repository import DocumentRepository
from neomath.edlatex import (
    EdDocument,
    deserialize_ed_document,
    from_legacy_document,
    layout_from_template,
    new_document,
    parse_content_edl,
    render_content_edl,
    serialize_ed_document,
    to_legacy_source,
)
from neomath.edlatex.metadata import Author
from neomath.edlatex.migration import migrate_ed_document
from neomath.edlatex.nodes import (
    AssertionNode,
    DerivationNode,
    FormulaNode,
    ParagraphNode,
    SectionNode,
)

SAMPLE_EDL = """# 第一题

设 $f(x)=x^2$，求：

$$
\\int_0^1 f(x)\\,dx
$$

@derive integral-1 {
    from: \\int_0^1 x^2 dx
    to: \\left[\\frac{x^3}{3}\\right]_0^1
    rule: integrate
}

@assert {
    expression: integral-2
    equals: \\frac{1}{3}
}"""


def _build_doc() -> EdDocument:
    doc = new_document("偏微分方程作业 3")
    doc.metadata.authors = [Author(name="张三")]
    doc.metadata.course = "偏微分方程"
    doc.add_node(SectionNode(level=1, title="第一题"))
    doc.add_node(ParagraphNode(source="设 f(x)=x^2"))
    doc.add_node(FormulaNode(source=r"\int_0^1 f(x)dx", parsed_expression=r"\int_0^1 f(x)dx"))
    doc.add_node(DerivationNode(name="d1", from_expr="a", to_expr="b", rule="integrate"))
    doc.add_node(AssertionNode(expression_ref="d1", equals="1/3"))
    return doc


# --- serialization round-trip ---------------------------------------------
def test_ed_document_json_round_trip_preserves_ids_order_and_sources() -> None:
    doc = _build_doc()
    ids = [n.id for n in doc.iter_nodes()]
    sources = [n.source for n in doc.iter_nodes()]

    restored = deserialize_ed_document(serialize_ed_document(doc))

    assert [n.id for n in restored.iter_nodes()] == ids
    assert [n.source for n in restored.iter_nodes()] == sources
    assert restored.metadata.title == "偏微分方程作业 3"
    assert restored.metadata.authors[0].name == "张三"
    assert restored.metadata.course == "偏微分方程"
    assert restored.format_version == 2
    # Node subtypes survive.
    types = [n.type for n in restored.iter_nodes()]
    assert types == ["section", "paragraph", "formula", "derivation", "assertion"]


def test_content_edl_parse_is_lossless() -> None:
    nodes = parse_content_edl(SAMPLE_EDL)
    kinds = [n.type for n in nodes]
    assert kinds == ["section", "paragraph", "formula", "derivation", "assertion"]
    derivation = nodes[3]
    assert isinstance(derivation, DerivationNode)
    assert derivation.rule == "integrate"
    assert derivation.from_expr == r"\int_0^1 x^2 dx"
    assertion = nodes[4]
    assert isinstance(assertion, AssertionNode)
    assert assertion.equals == r"\frac{1}{3}"
    # Round-trip reproduces the original text.
    assert render_content_edl(nodes).strip() == SAMPLE_EDL.strip()


def test_malformed_edl_degrades_without_data_loss() -> None:
    text = "@derive broken {\n    from: a\n"  # unterminated brace
    nodes = parse_content_edl(text)
    # The raw text is still captured; nothing is dropped.
    assert render_content_edl(nodes).strip() == text.strip()


# --- stable ids ------------------------------------------------------------
def test_node_ids_stay_stable_across_insert_and_remove() -> None:
    doc = _build_doc()
    original = {n.id for n in doc.iter_nodes()}

    inserted = doc.add_node(ParagraphNode(source="新段落"), index=1)
    assert original.issubset({n.id for n in doc.iter_nodes()})  # nothing renumbered
    assert inserted.id not in original

    first_id = doc.order[0]
    doc.remove_node(first_id)
    remaining = {n.id for n in doc.iter_nodes()}
    # Every surviving id is unchanged.
    assert remaining == (original | {inserted.id}) - {first_id}


# --- metadata / layout independence ---------------------------------------
def test_layout_switch_does_not_touch_content_ids_or_order() -> None:
    doc = _build_doc()
    ids_before = [n.id for n in doc.iter_nodes()]
    sources_before = [n.source for n in doc.iter_nodes()]

    doc.layout = layout_from_template("neurips")
    assert doc.layout.template == "neurips"

    assert [n.id for n in doc.iter_nodes()] == ids_before
    assert [n.source for n in doc.iter_nodes()] == sources_before


def test_metadata_edit_does_not_change_content() -> None:
    doc = _build_doc()
    sources_before = [n.source for n in doc.iter_nodes()]
    doc.metadata.title = "改了标题"
    doc.metadata.keywords = ["热传导方程"]
    assert [n.source for n in doc.iter_nodes()] == sources_before


def test_unknown_metadata_fields_round_trip() -> None:
    doc = new_document("x")
    doc.metadata.extra["supervisor"] = "李四"
    restored = deserialize_ed_document(serialize_ed_document(doc))
    assert restored.metadata.extra.get("supervisor") == "李四"


# --- legacy migration ------------------------------------------------------
def test_v1_document_migrates_and_projects_back_exactly() -> None:
    v1 = NeoMathDocument(source="x(x-1)=0\nx-1=0\nx=1", title="丢根", breakpoints=[1])
    ed = from_legacy_document(v1)
    assert ed.format_version == 2
    assert len(ed.order) == 3
    # Projection back to the flat source the C++ core consumes is exact.
    assert to_legacy_source(ed) == v1.source
    # And survives a JSON round-trip.
    restored = deserialize_ed_document(serialize_ed_document(ed))
    assert to_legacy_source(restored) == v1.source
    assert restored.metadata.extra["legacyState"]["breakpoints"] == [1]


def test_migrate_ed_document_upconverts_flat_dict() -> None:
    flat = NeoMathDocument(source="a=b", title="t").to_dict()
    migrated = migrate_ed_document(flat)
    assert migrated["formatVersion"] == 2
    assert "nodes" in migrated and "order" in migrated


def test_migrate_ed_document_rejects_future_format() -> None:
    try:
        migrate_ed_document({"formatVersion": 99, "nodes": {}, "order": []})
    except ValueError:
        return
    raise AssertionError("future edLatex format must be rejected")


# --- persistence (save -> reload) -----------------------------------------
def test_repository_saves_and_reloads_ed_document(tmp_path: Path) -> None:
    repo = DocumentRepository(tmp_path)
    doc = _build_doc()
    doc.layout = layout_from_template("homework")
    ids = [n.id for n in doc.iter_nodes()]

    path = repo.save_ed(doc)
    assert path.name.endswith(".edlatex.json")

    reloaded = repo.load_ed(path)
    assert [n.id for n in reloaded.iter_nodes()] == ids
    assert reloaded.layout.template == "homework"
    assert reloaded.metadata.title == "偏微分方程作业 3"
    # No credentials ever land on disk.
    text = path.read_text(encoding="utf-8")
    assert "API_KEY" not in text and "DASHSCOPE" not in text


def test_repository_loads_legacy_file_as_ed_document(tmp_path: Path) -> None:
    repo = DocumentRepository(tmp_path)
    legacy = NeoMathDocument(source="x=1\ny=2", title="老文档")
    legacy_path = repo.save(legacy)  # writes a v1 .neomath.json

    ed = repo.load_ed(legacy_path)
    assert ed.format_version == 2
    assert to_legacy_source(ed) == "x=1\ny=2"
    assert ed.metadata.title == "老文档"


# --- bridge end-to-end (real data flow, no UI shell) -----------------------
def test_bridge_ed_document_save_open_and_parse(tmp_path: Path) -> None:
    from neomath.bridge import NeoMathBridge
    from neomath.config import AppConfig

    config = AppConfig(
        data_dir=tmp_path,
        dashscope_base_url="https://example.invalid/v1",
        qwen_model="qwen-plus",
        qwen_api_key=None,
    )
    bridge = NeoMathBridge(config)
    doc = _build_doc()
    target = tmp_path / "hw.edlatex.json"

    saved = bridge.saveEdDocument({"document": doc.to_dict(), "path": str(target)})
    assert saved["ok"] is True
    assert Path(saved["result"]["path"]).exists()

    opened = bridge.openEdDocument({"path": saved["result"]["path"]})
    assert opened["ok"] is True
    assert opened["result"]["document"]["formatVersion"] == 2

    parsed = bridge.parseContentEdl({"content": SAMPLE_EDL})
    assert parsed["ok"] is True
    assert [n["type"] for n in parsed["result"]["nodes"]] == [
        "section",
        "paragraph",
        "formula",
        "derivation",
        "assertion",
    ]
