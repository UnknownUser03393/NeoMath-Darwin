from __future__ import annotations

from neomath.xdlt import lower_to_semantic_ir, parse_xdlt
from neomath.xdlt.nodes import DisplayMathNode, HeadingNode, SemanticBlockNode


def test_heading_and_semantic_header_are_distinguished() -> None:
    doc = parse_xdlt("""# Title
#thm:foo {
    body
}
""")

    assert [node.type for node in doc.nodes] == ["heading", "semantic_block"]
    assert isinstance(doc.nodes[0], HeadingNode)
    assert doc.nodes[0].title == "Title"
    assert isinstance(doc.nodes[1], SemanticBlockNode)
    assert doc.nodes[1].header.kind == "thm"
    assert doc.nodes[1].header.canonical_id == "thm:foo"


def test_document_body_recurses_into_nested_blocks() -> None:
    doc = parse_xdlt("""#thm:outer {
    intro
    #proof(#thm:outer) {
        text
    }
}
""")

    outer = doc.nodes[0]
    assert isinstance(outer, SemanticBlockNode)
    assert [node.type for node in outer.children] == ["paragraph", "semantic_block"]
    inner = outer.children[1]
    assert isinstance(inner, SemanticBlockNode)
    assert inner.header.kind == "proof"
    assert inner.header.arguments == "#thm:outer"


def test_raw_body_is_deindented_without_parsing_inner_braces() -> None:
    doc = parse_xdlt("""#exec:plot(javascript) {
    function f() {
        return {x: 1};
    }
}
""")

    node = doc.nodes[0]
    assert isinstance(node, SemanticBlockNode)
    assert node.header.body_mode == "RawBody"
    assert node.deindented_body == "function f() {\n    return {x: 1};\n}"
    assert node.children == []


def test_named_display_math_is_captured_with_numbering_hint() -> None:
    doc = parse_xdlt(r"""$$ #eq:a(numbered=true)
\frac{1}{3}
$$
""")

    node = doc.nodes[0]
    assert isinstance(node, DisplayMathNode)
    assert node.id == "eq:a"
    assert node.arguments == "numbered=true"
    assert node.numbering == "on"
    assert node.body == r"\frac{1}{3}"


def test_unknown_extension_survives_lowering() -> None:
    doc = parse_xdlt("""#vendor.magic:x {
    hello
}
""")

    ir = lower_to_semantic_ir(doc)
    assert ir["children"][0]["type"] == "UnknownExtensionNode"
    assert ir["children"][0]["kind"] == "vendor.magic"
    assert ir["children"][0]["id"] == "vendor.magic:x"


def test_duplicate_ids_report_semantic_diagnostic() -> None:
    doc = parse_xdlt("""#thm:foo {
}

#thm:foo {
}
""")

    ir = lower_to_semantic_ir(doc)
    codes = [diagnostic["code"] for diagnostic in ir["diagnostics"]]
    assert "DUPLICATE_ID" in codes


def test_unterminated_block_is_recoverable() -> None:
    doc = parse_xdlt("""#thm:broken {
    text
""")

    assert isinstance(doc.nodes[0], SemanticBlockNode)
    assert doc.nodes[0].diagnostics[0].code == "UNTERMINATED_BLOCK"
