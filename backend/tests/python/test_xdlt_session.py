from __future__ import annotations

from neomath.xdlt import lower_to_semantic_ir, parse_xdlt
from neomath.xdlt.render import build_render_result
from neomath.xdlt.render.diff import (
    InsertNode,
    RemoveNode,
    ReplaceDocument,
    ReplaceNode,
    apply_patches,
    diff_documents,
    serialize_patches,
)
from neomath.xdlt.session import CompilationSession

DOC = """# 标题

#context {
    alpha: Real & Positive = 0.01
    T: Real & Positive = 300
}

$$ #eq:heat(numbered=true)
x + alpha
$$

#thm:solution("Sol") {
    定理内容
}

#assert:energy(using=sympy) {
    claim substitute(#eq:heat, x=0) == alpha
}

#exec:data(
    python,
    inputs=[alpha]
) {
from xdlt_runtime import output
output.json({"alpha": alpha})
}
"""


def _structure(node) -> dict:
    def clean(n) -> dict:
        data = n.to_dict()
        data.pop("renderHash", None)
        data.pop("sourceRange", None)
        if "children" in data:
            data["children"] = [clean(c) for c in n.children()]
        return data

    return clean(node)


def _doc(hw: str):
    return build_render_result(lower_to_semantic_ir(parse_xdlt(hw))).document


def _patch_names(patches) -> list[str]:
    return [type(patch).__name__ for patch in patches]


def _patch_ids(patches) -> list[str]:
    result = []
    for patch in patches:
        if isinstance(patch, (ReplaceNode, RemoveNode)):
            result.append(patch.render_id)
    return result


# --- 1. identical content --------------------------------------------------


def test_identical_update_is_noop() -> None:
    session = CompilationSession("s1")
    session.compile(DOC)
    result = session.update(DOC)
    assert result.invalidated_semantic_ids == []
    assert result.patches == []
    assert result.reused_verification_count >= 1
    assert result.recomputed_verification_count == 0
    assert result.recomputed_execution_count == 0


# --- 2. paragraph text edit ------------------------------------------------


def test_paragraph_edit_patches_paragraph_only() -> None:
    session = CompilationSession("s2")
    session.compile(DOC)
    edited = DOC.replace("定理内容", "改过的定理内容")
    result = session.update(edited)
    # A pure paragraph edit touches no assertion / executable.
    assert result.recomputed_verification_count == 0
    assert result.recomputed_execution_count == 0
    assert ReplaceDocument not in [type(p) for p in result.patches]
    assert "render:paragraph:" in "".join(_patch_ids(result.patches))


# --- 3. equation edit ------------------------------------------------------


def test_equation_edit_invalidates_dependents_and_patches_subtree() -> None:
    session = CompilationSession("s3")
    session.compile(DOC)
    edited = DOC.replace("x + alpha", "x + 2\\alpha")
    result = session.update(edited)
    assert "eq:heat" in result.invalidated_semantic_ids
    assert "assert:energy" in result.invalidated_semantic_ids
    # The theorem is unrelated and untouched.
    assert "thm:solution" not in result.invalidated_semantic_ids
    ids = _patch_ids(result.patches)
    assert "eq:heat" in ids
    assert ReplaceDocument not in [type(p) for p in result.patches]


# --- 4. assertion dependency -----------------------------------------------


def test_assertion_dependency_recomputes_only_affected() -> None:
    doc = """#context {
    x: Real
}

#assert:a {
    claim x + 0 == x
}

#assert:b {
    claim x + 0 == x
}
"""
    session = CompilationSession("s4")
    session.compile(doc)
    edited = doc.replace("#assert:b", "#assert:changed").replace(
        "claim x + 0 == x", "claim x + 1 == x", 1
    )
    result = session.update(edited)
    # One assertion changed (recomputed), the other unchanged (reused).
    assert result.recomputed_verification_count == 1
    assert result.reused_verification_count == 1


# --- 5. execution dependency -----------------------------------------------


def test_execution_dependency_reruns_only_affected() -> None:
    doc = """#exec:a(python, inputs=[x]) {
from xdlt_runtime import output
output.json({"x": x})
}

#exec:b(python) {
print("b")
}
"""
    session = CompilationSession("s5")
    session.compile(doc)
    # Add a new executable -> one rerun, the other reused.
    extended = doc + '\n#exec:c(python) {\nprint("c")\n}\n'
    result = session.update(extended)
    assert result.recomputed_execution_count == 1
    assert result.reused_execution_count == 2


# --- 6. execute=false ------------------------------------------------------


def test_execute_false_does_not_run_code() -> None:
    session = CompilationSession("s6")
    session.compile(DOC, execute=False)
    assert len(session._state.execution) == 0
    edited = DOC.replace("x + alpha", "x + 2\\alpha")
    result = session.update(edited, execute=False)
    assert result.recomputed_execution_count == 0
    # Render shows unexecuted, never a real run.
    assert "unexecuted" in result.html


# --- 7. values change with identical source --------------------------------


def test_values_change_invalidates_dependents_only() -> None:
    session = CompilationSession("s7")
    session.compile(DOC)
    result = session.update(DOC, values={"alpha": 0.02})
    assert "sym:ctx.anon1/alpha" in result.invalidated_semantic_ids
    assert "eq:heat" in result.invalidated_semantic_ids
    assert "exec:data" in result.invalidated_semantic_ids
    assert result.recomputed_verification_count == 1
    assert result.recomputed_execution_count == 1
    assert result.reused_parsing is True  # parser/semantic reusable


# --- 8. layout-only change -------------------------------------------------


def test_layout_only_change_reuses_verification_and_execution() -> None:
    session = CompilationSession("s8")
    session.compile(DOC)
    result = session.update(DOC, layout={"theme": "dark"})
    assert result.recomputed_verification_count == 0
    assert result.recomputed_execution_count == 0
    assert result.reused_parsing is True
    assert result.patches  # render patches change with layout


# --- 9. insertion before anonymous nodes (no ID avalanche) -----------------


def test_prepend_does_not_avalanche_anonymous_ids() -> None:
    base = "一段\n\n二段\n\n三段\n"
    old = _doc(base)
    new = _doc("插入\n\n一段\n\n二段\n\n三段\n")
    patches = diff_documents(old, new)
    assert len(patches) == 1 and isinstance(patches[0], InsertNode)
    # No anonymous paragraph was removed or replaced.
    assert not any(isinstance(p, (RemoveNode, ReplaceNode)) for p in patches)


# --- 10. subtree hash skip -------------------------------------------------


def test_unchanged_subtrees_are_skipped() -> None:
    # Each paragraph carries inline math so it has several children; a big tree
    # where only the equation leaf changes must not recurse into paragraphs.
    paragraphs = "\n\n".join(f"段落 {i} $x + {i}$" for i in range(30))
    old_hw = f"{paragraphs}\n\n$$ #eq:one\nx + 1\n$$\n"
    new_hw = f"{paragraphs}\n\n$$ #eq:one\nx + 2\n$$\n"
    old, new = _doc(old_hw), _doc(new_hw)
    total = len(list(_walk_nodes(new)))
    stats: dict = {}
    diff_documents(old, new, stats=stats)
    # The diff examines paragraph *roots* but never descends into them; the
    # visited count stays far below the total node count.
    assert stats["visited"] < total // 2
    assert stats["visited"] < 40


def _walk_nodes(node):
    yield node
    for child in node.children():
        yield from _walk_nodes(child)


# --- 11. reorder -----------------------------------------------------------


def test_reorder_falls_back_to_parent_replace() -> None:
    base = """# 节

AAA

BBB

CCC
"""
    old = _doc(base)
    new = _doc("""# 节

BBB

AAA

CCC
""")
    patches = diff_documents(old, new)
    assert patches  # deterministic non-empty
    # Never a full document fallback.
    assert not any(isinstance(p, ReplaceDocument) for p in patches)
    assert all(isinstance(p, ReplaceNode) for p in patches)


# --- 12. duplicate renderId -------------------------------------------------


def test_ambiguous_duplicate_render_id_falls_back() -> None:
    import copy

    old = _doc("一段\n\n二段\n")
    # A different document, then corrupted: two nodes share a renderId but not
    # content, so the diff must fall back to a full replacement.
    corrupt = copy.deepcopy(_doc("三\n\n四\n"))
    text_nodes = [n for n in _walk_nodes(corrupt) if n.kind == "text" and n.text]
    assert len(text_nodes) >= 2
    text_nodes[1].render_id = text_nodes[0].render_id
    patches = diff_documents(old, corrupt)
    assert any(isinstance(p, ReplaceDocument) for p in patches)


# --- 13. byte stability ----------------------------------------------------


def test_diff_is_byte_stable() -> None:
    old = _doc("A\n\nB\n\nC\n")
    new = _doc("A\n\nB2\n\nC\n\nD\n")
    first = serialize_patches(diff_documents(old, new))
    for _ in range(50):
        assert serialize_patches(diff_documents(old, new)) == first


# --- 14. patch application equivalence -------------------------------------


def test_apply_patches_equals_full_rebuild() -> None:
    old = _doc("""# 节

AAA

$$ #eq:a
x + 1
$$

BBB
""")
    new = _doc("""# 节

AAA 改

$$ #eq:a
x + 2
$$

BBB

CCC
""")
    patches = diff_documents(old, new)
    applied = apply_patches(old, patches)
    assert _structure(applied) == _structure(new)


def test_html_patch_payload_matches_new_render() -> None:
    from neomath.xdlt.render import render_html_fragment
    from neomath.xdlt.render.html.renderer import HTMLRenderer

    old_hw = "$$ #eq:a\nx + 1\n$$\n"
    new_hw = "$$ #eq:a\nx + 2\n$$\n"
    old, new = _doc(old_hw), _doc(new_hw)
    patches = diff_documents(old, new)
    renderer = HTMLRenderer()
    new_html = render_html_fragment(lower_to_semantic_ir(parse_xdlt(new_hw))).html
    for patch in patches:
        if isinstance(patch, ReplaceNode):
            assert renderer.render_node(patch.node) in new_html


# --- session invalidation precision ----------------------------------------


def test_edit_one_equation_does_not_touch_unrelated_nodes() -> None:
    doc = """$$ #eq:heat
x + 1
$$

$$ #eq:other
y + 1
$$

#assert:heat(using=sympy) {
    claim substitute(#eq:heat, x=0)
}

#assert:other(using=sympy) {
    claim substitute(#eq:other, y=0)
}
"""
    session = CompilationSession("s-precise")
    session.compile(doc)
    edited = doc.replace("x + 1", "x + 2")
    result = session.update(edited)
    assert "eq:heat" in result.invalidated_semantic_ids
    assert "assert:heat" in result.invalidated_semantic_ids
    assert "eq:other" not in result.invalidated_semantic_ids
    assert "assert:other" not in result.invalidated_semantic_ids
    assert result.reused_verification_count == 1  # assert:other reused
    assert result.recomputed_verification_count == 1


# --- perf / reuse ratio ----------------------------------------------------


def test_large_document_incremental_reuse() -> None:
    paragraphs = "\n\n".join(f"段落 {i}" for i in range(60))
    equations = "\n\n".join(
        f"$$ #eq:e{i}\nx + {i}\n$$" for i in range(20)
    )
    assertions = "\n\n".join(
        f"#assert:q{i}(using=sympy) {{\n    claim substitute(#eq:e{i}, x=0) == {i}\n}}"
        for i in range(20)
    )
    doc = f"{paragraphs}\n\n{equations}\n\n{assertions}\n"
    session = CompilationSession("s-perf")
    session.compile(doc, execute=False)
    total_nodes = len(list(_walk_nodes(session._state.render.document)))
    edited = doc.replace("x + 7", "x + 70")
    result = session.update(edited, execute=False)
    assert len(result.invalidated_semantic_ids) < 10  # far below document size
    assert result.recomputed_verification_count == 1  # only assert:q7
    assert result.reused_verification_count >= 19
    assert total_nodes > 100
    assert len(result.patches) <= 4  # subtree-granular, not whole document
