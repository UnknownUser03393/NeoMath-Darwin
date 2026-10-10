from __future__ import annotations

from neomath.xdlt import lower_to_semantic_ir, parse_xdlt
from neomath.xdlt.render import build_render_result, render_html_fragment
from neomath.xdlt.render.nodes import (
    RenderAssertion,
    RenderDocument,
    RenderExecutable,
    RenderMathBlock,
    RenderParagraph,
    RenderReference,
    RenderText,
    RenderThesis,
)
from neomath.xdlt.verification import verify_document_assertions


def _ir(hw: str, card_registry=None) -> dict:
    return lower_to_semantic_ir(parse_xdlt(hw), card_registry=card_registry)


def _render(hw: str, card_registry=None, **kwargs):
    ir = _ir(hw, card_registry)
    kwargs.setdefault("verification", verify_document_assertions(ir))
    return build_render_result(ir, card_registry=card_registry, **kwargs)


def _html(hw: str, card_registry=None, verification=None, **kwargs) -> str:
    ir = _ir(hw, card_registry)
    if verification is None:
        verification = verify_document_assertions(ir)
    return render_html_fragment(
        ir, card_registry=card_registry, verification=verification, **kwargs
    ).html


def _walk(node):
    yield node
    for child in node.children():
        yield from _walk(child)


def _find(document: RenderDocument, node_type):
    for node in _walk(document):
        if isinstance(node, node_type):
            return node
    return None


# --- Render IR -------------------------------------------------------------


def test_equation_node_identity_and_number() -> None:
    result = _render("$$ #eq:a(numbered=true)\nx + 1\n$$\n")
    equation = _find(result.document, RenderMathBlock)
    assert equation.semantic_id == "eq:a"
    assert equation.render_id == "eq:a"
    assert equation.number == "1"


def test_anonymous_nodes_get_stable_render_ids() -> None:
    result = _render("$$ #eq:a\nx\n$$\n\n$$ \ny\n$$\n")
    equations = [n for n in _walk(result.document) if isinstance(n, RenderMathBlock)]
    assert equations[0].render_id == "eq:a"
    assert equations[1].render_id.startswith("render:equation:")


def test_theorem_node() -> None:
    result = _render('#thm:t("Title") {\n    body\n}\n')
    thesis = _find(result.document, RenderThesis)
    assert thesis.kind == "theorem"
    assert thesis.title == "Title"
    assert thesis.number == "1"


def test_render_hash_is_stable_and_sensitive() -> None:
    base = "$$ #eq:a\nx + 1\n$$\n"
    first = _render(base)
    second = _render(base)
    equation_first = _find(first.document, RenderMathBlock)
    equation_second = _find(second.document, RenderMathBlock)
    assert equation_first.render_hash == equation_second.render_hash
    changed = _render("$$ #eq:a\nx + 2\n$$\n")
    assert equation_first.render_hash != _find(changed.document, RenderMathBlock).render_hash


def test_paragraph_text_and_inline_math() -> None:
    result = _render("解 $x + 1$ 问题\n")
    paragraph = _find(result.document, RenderParagraph)
    assert any(isinstance(c, RenderText) and "解" in c.text for c in paragraph.children())
    assert any(c.kind == "inline_math" for c in paragraph.children())


def test_reference_resolution() -> None:
    result = _render("$$ #eq:a\nx + 1\n$$\n\n见 #eq:a\n")
    reference = _find(result.document, RenderReference)
    assert reference.target_id == "eq:a"
    assert reference.target_kind == "eq"
    assert reference.display_text == "Equation 1"
    assert reference.anchor == "xdlt-eq-a"


def test_unresolved_reference_produces_diagnostic() -> None:
    result = _render("见 #eq:missing\n")
    codes = [d.code for d in result.diagnostics]
    assert "UNRESOLVED_RENDER_REFERENCE" in codes


def test_verification_result_lowering() -> None:
    hw = """#context {
    x: Real
}

#assert:a {
    claim x + 0 == x
}
"""
    result = _render(hw, verification=verify_document_assertions(_ir(hw)))
    assertion = _find(result.document, RenderAssertion)
    assert assertion.verification_status == "valid"


def test_execution_result_lowering() -> None:
    from neomath.xdlt.execution import ExecutionRequest, PythonRunner

    hw = "#exec:data(python) {\nprint('hi')\n}\n"
    runner = PythonRunner()
    request = ExecutionRequest(exec_id="exec:data", language="python", source="print('hi')")
    result = build_render_result(
        _ir(hw), execution=[runner.execute(request)]
    )
    executable = _find(result.document, RenderExecutable)
    assert executable.status == "success"
    assert executable.stdout == "hi\n"


def test_card_reference_provenance(tmp_path) -> None:
    import json

    from neomath.xdlt.cards import CardRegistry

    (tmp_path / "heat.card.json").write_text(
        json.dumps(
            {
                "id": "heat",
                "version": "1.0.0",
                "type": "derivation",
                "parameters": {"L": {"type": "Real", "requires": ["L > 0"]}},
                "content": "$$ #eq:inside\nx + 1\n$$",
                "dependencies": [],
            }
        ),
        encoding="utf-8",
    )
    registry = CardRegistry.from_directory(tmp_path)
    hw = "#use-card:h(#card:heat, mode=reference) {\nbind L = 1\n}\n"
    result = _render(hw, card_registry=registry)
    from neomath.xdlt.render.nodes import RenderCardReference

    card = _find(result.document, RenderCardReference)
    assert card.card_id == "heat"
    assert card.version == "1.0.0"
    assert card.mode == "reference"
    assert card.provenance.get("cardId") == "heat"


# --- HTML backend ----------------------------------------------------------


def test_html_heading_and_section() -> None:
    html = _html("# 标题\n\n正文\n")
    assert 'class="xdlt-section"' in html
    assert "<h1>标题</h1>" in html


def test_html_paragraph_and_escaping() -> None:
    html = _html('<script>alert(1)</script>\n')
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html


def test_html_inline_math_mathml() -> None:
    html = _html("解 $x + 1$ 问题\n")
    assert '<span class="xdlt-inline-math">' in html
    assert "<math " in html
    assert "<mo>+</mo>" in html


def test_html_equation_with_number_and_source_map() -> None:
    html = _html("$$ #eq:a(numbered=true)\nx + 1\n$$\n")
    assert '<div class="xdlt-equation"' in html
    assert 'data-xdlt-id="eq:a"' in html
    assert 'data-xdlt-source-start=' in html
    assert "(1)" in html


def test_html_reference_anchor() -> None:
    html = _html("$$ #eq:a\nx\n$$\n\n见 #eq:a\n")
    assert '<a class="xdlt-reference" href="#xdlt-eq-a">Equation 1</a>' in html


def test_html_theorem_and_proof() -> None:
    html = _html('#thm:t("Title") {\n    body\n}\n\n#proof(#thm:t) {\n    proof body\n}\n')
    assert '<section class="xdlt-thesis xdlt-theorem"' in html
    assert "Theorem 1" in html
    assert "<title>Title</title>" in html or "Title" in html
    assert '<section class="xdlt-proof"' in html
    assert "Proof." in html


def test_html_assertion_statuses_are_distinct() -> None:
    valid = "#context {\n    x: Real\n}\n\n#assert:a {\n    claim x + 0 == x\n}\n"
    invalid = "#assert:b {\n    claim x + 1 == x\n}\n"
    unknown = "#assert:c {\n    claim f(x) == 1\n}\n"
    assert 'class="xdlt-assertion xdlt-assertion-valid"' in _html(valid)
    assert 'class="xdlt-assertion xdlt-assertion-invalid"' in _html(invalid)
    assert 'class="xdlt-assertion xdlt-assertion-unknown"' in _html(unknown)


def test_html_executable_and_outputs() -> None:
    from neomath.xdlt.execution import ExecutionRequest, PythonRunner

    hw = """#exec:data(python) {
from xdlt_runtime import output
print("out")
output.json({"a": 1})
output.table([["x", 1], ["y", 2]])
}
"""
    runner = PythonRunner()
    source = hw.split("{", 1)[1].rsplit("}", 1)[0]
    request = ExecutionRequest(
        exec_id="exec:data", language="python", source=source
    )
    html = render_html_fragment(_ir(hw), execution=[runner.execute(request)]).html
    assert 'class="xdlt-exec xdlt-exec-success"' in html
    assert 'class="xdlt-exec-stdout"' in html and "out" in html
    assert '<pre class="xdlt-code"' in html  # JSON + text outputs
    assert '<table class="xdlt-table"' in html  # table output


def test_html_opaque_math_fallback() -> None:
    html = _html(r"$ \unknown{x} $\n")
    assert 'class="xdlt-math-opaque"' in html
    assert "data-latex=" in html


def test_html_figure_unavailable() -> None:
    hw = "#fig:f(source=#exec:data[0]) {\n    Caption.\n}\n"
    html = _html(hw)
    assert '<figure class="xdlt-figure"' in html
    assert "xdlt-figure-unavailable" in html


def test_html_card_reference_renders(tmp_path) -> None:
    import json

    from neomath.xdlt.cards import CardRegistry

    (tmp_path / "heat.card.json").write_text(
        json.dumps(
            {
                "id": "heat",
                "version": "1.0.0",
                "type": "derivation",
                "parameters": {"L": {"type": "Real", "requires": ["L > 0"]}},
                "content": "卡内容\n",
                "dependencies": [],
            }
        ),
        encoding="utf-8",
    )
    registry = CardRegistry.from_directory(tmp_path)
    hw = "#use-card:h(#card:heat, mode=reference) {\nbind L = 1\n}\n"
    html = _html(hw, card_registry=registry)
    assert 'class="xdlt-card-reference"' in html
    assert "heat@1.0.0" in html
    assert "reference" in html


def test_html_fragment_vs_standalone() -> None:
    from neomath.xdlt.render import render_html_document

    fragment = _html("# 标题\n")
    standalone = render_html_document(_ir("# 标题\n"), layout={"metadata": {"title": "文档"}}).html
    assert "<!doctype html>" in standalone
    assert "<html" in standalone and "</html>" in standalone
    assert "<title>文档</title>" in standalone
    assert "<!doctype html>" not in fragment


def test_html_is_byte_stable() -> None:
    hw = """# 标题

$$ #eq:a(numbered=true)
x + 1
$$

#thm:t("T") {
    内容 #eq:a
}

#assert:a {
    claim x + 0 == x
}
"""
    assert _html(hw) == _html(hw)


def test_figure_resolves_execution_image(tmp_path) -> None:
    from neomath.xdlt.execution import ExecutionRequest, PythonRunner

    hw = """#exec:data(python) {
from xdlt_runtime import output
output.image(b"\\x89PNG\\r\\n")
}

#fig:f(source=#exec:data[0]) {
    Generated plot.
}
"""
    runner = PythonRunner()
    source = 'from xdlt_runtime import output\noutput.image(b"\\x89PNG\\r\\n")'
    request = ExecutionRequest(exec_id="exec:data", language="python", source=source)
    html = render_html_fragment(
        _ir(hw), execution=[runner.execute(request)]
    ).html
    assert '<figure class="xdlt-figure"' in html
    assert "xdlt-figure-unavailable" not in html
    assert 'class="xdlt-image"' in html
    assert "data:image/png;base64," in html


def test_unsupported_layout_option_diagnostic() -> None:
    result = build_render_result(_ir("正文\n"), layout={"fancyThing": True})
    codes = [d.code for d in result.diagnostics]
    assert "UNSUPPORTED_LAYOUT_OPTION" in codes
