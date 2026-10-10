from __future__ import annotations

from neomath.edlatex import (
    deserialize_ed_document,
    layout_from_template,
    new_document,
)
from neomath.edlatex.metadata import Author
from neomath.edlatex.nodes import (
    AssertionNode,
    DerivationNode,
    FormulaNode,
    ParagraphNode,
    SectionNode,
)
from neomath.edlatex.render import render_document


def _doc():
    doc = new_document("热传导方程作业")
    doc.metadata.authors = [Author(name="张三"), Author(name="李四")]
    doc.metadata.date = "2026-08-06"
    doc.add_node(SectionNode(level=1, title="第一题"))
    doc.add_node(ParagraphNode(source="设 $f(x)=x^2$，求定积分。"))
    doc.add_node(FormulaNode(parsed_expression=r"\int_0^1 x^2\,dx", display=True))
    doc.add_node(
        DerivationNode(name="d1", from_expr=r"\int_0^1 x^2 dx", to_expr="1/3", rule="integrate")
    )
    doc.add_node(AssertionNode(expression_ref="d1", equals="1/3"))
    return doc


# --- LaTeX -----------------------------------------------------------------
def test_latex_export_maps_metadata_and_structure() -> None:
    result = render_document(_doc(), "latex")
    tex = result.content
    # Content carries no \documentclass; the template/preamble provides it.
    assert tex.count("\\documentclass") == 1
    # Metadata mapped into preamble, not duplicated in content.
    assert "\\title{热传导方程作业}" in tex
    assert "张三 \\and 李四" in tex
    assert "\\date{2026-08-06}" in tex
    assert "\\maketitle" in tex
    # Structure.
    assert "\\section{第一题}" in tex
    assert "\\int_0^1 x^2\\,dx" in tex
    assert "\\begin{align}" in tex  # derivation
    # Node ids preserved as comments for round-trip / blame.
    assert "% node:" in tex
    assert tex.rstrip().endswith("\\end{document}")


def test_latex_export_reports_unsupported_nodes() -> None:
    from neomath.edlatex.nodes import AssetNode

    doc = new_document("x")
    doc.add_node(AssetNode(path="a.png", kind="image"))
    result = render_document(doc, "latex")
    assert any(d.code == "UNSUPPORTED_NODE" for d in result.diagnostics)


# --- HTML ------------------------------------------------------------------
def test_html_export_comes_from_same_model() -> None:
    result = render_document(_doc(), "html")
    html = result.content
    assert "<h1" in html and "第一题" in html
    assert "$$ \\int_0^1 x^2\\,dx $$" in html
    assert 'class="ed-derivation"' in html
    assert "热传导方程作业" in html  # header resolves @meta.title


# --- JSON round-trip -------------------------------------------------------
def test_json_export_round_trips_model() -> None:
    doc = _doc()
    ids = [n.id for n in doc.iter_nodes()]
    result = render_document(doc, "json")
    restored = deserialize_ed_document(result.content)
    assert [n.id for n in restored.iter_nodes()] == ids


# --- layout independence ---------------------------------------------------
def test_switching_layout_keeps_content_identical() -> None:
    doc = _doc()
    ids_before = [n.id for n in doc.iter_nodes()]
    sources_before = [n.source for n in doc.iter_nodes()]

    tex_article = render_document(doc, "latex").content
    doc.layout = layout_from_template("report")
    tex_report = render_document(doc, "latex").content

    # Content nodes untouched by the layout switch...
    assert [n.id for n in doc.iter_nodes()] == ids_before
    assert [n.source for n in doc.iter_nodes()] == sources_before
    # ...but the presentation (document class) differs.
    assert "{article}" in tex_article
    assert "{report}" in tex_report
    assert "\\section{第一题}" in tex_article and "\\section{第一题}" in tex_report


# --- pdf honesty -----------------------------------------------------------
def test_pdf_reports_unavailable_instead_of_faking() -> None:
    result = render_document(_doc(), "pdf")
    assert result.content == ""
    assert any(d.code == "PDF_UNAVAILABLE" for d in result.diagnostics)


def test_unknown_format_is_reported() -> None:
    result = render_document(_doc(), "docx")
    assert any(d.code == "UNKNOWN_FORMAT" for d in result.diagnostics)


# --- bridge export end-to-end ---------------------------------------------
def test_bridge_export_document_latex(tmp_path) -> None:
    from neomath.bridge import NeoMathBridge
    from neomath.config import AppConfig

    config = AppConfig(
        data_dir=tmp_path,
        dashscope_base_url="https://example.invalid/v1",
        qwen_model="qwen-plus",
        qwen_api_key=None,
    )
    bridge = NeoMathBridge(config)
    out = bridge.exportDocument({"document": _doc().to_dict(), "format": "latex"})
    assert out["ok"] is True
    assert out["result"]["format"] == "latex"
    assert r"\title{热传导方程作业}" in out["result"]["content"]

    # Legacy flat documents can be exported too (upconverted first).
    from neomath.documents.model import NeoMathDocument

    legacy = NeoMathDocument(source="x=1\ny=2", title="老文档").to_dict()
    out2 = bridge.exportDocument({"document": legacy, "format": "html"})
    assert out2["ok"] is True
    assert "老文档" in out2["result"]["content"]
