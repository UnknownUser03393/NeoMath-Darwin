from __future__ import annotations

from neomath.xdlt import lower_to_semantic_ir, parse_xdlt
from neomath.xdlt.graph import (
    build_dependency_graph,
    invalidate,
    result_node_id,
)


def _graph(hw: str):
    return build_dependency_graph(lower_to_semantic_ir(parse_xdlt(hw)))


def _edges(graph) -> set[tuple[str, str, str]]:
    return {(s, t, e) for s, t, e in graph.edges}


# --- DAG edges --------------------------------------------------------------


def test_symbol_to_equation_edge() -> None:
    graph = _graph(
        """#context {
    alpha: Real
}

$$ #eq:a
x + alpha
$$
"""
    )
    assert ("eq:a", "sym:ctx.anon1/alpha", "uses-symbol") in _edges(graph)


def test_equation_to_assertion_edge() -> None:
    graph = _graph(
        """$$ #eq:a
x + 1 = 2
$$

#assert:test {
    claim substitute(#eq:a, x=0)
}
"""
    )
    assert ("assert:test", "eq:a", "references") in _edges(graph)


def test_symbol_to_executable_edge() -> None:
    graph = _graph(
        """#context {
    alpha: Real
}

#exec:plot(python, inputs=[alpha]) {
print("hi")
}
"""
    )
    assert ("exec:plot", "sym:ctx.anon1/alpha", "exec-input") in _edges(graph)


def test_result_to_figure_edge_and_selector_identity() -> None:
    graph = _graph(
        """#exec:plot(python) {
print("hi")
}

#fig:data(source=#exec:plot[0]) {
    Generated.
}
"""
    )
    assert result_node_id("exec:plot", 0) == "result:exec.plot/0"
    assert ("fig:data", "result:exec.plot/0", "renders") in _edges(graph)
    assert ("exec:plot", "result:exec.plot/0", "produces") in _edges(graph)
    assert graph.nodes["result:exec.plot/0"].kind == "execution_result"


def test_context_declares_edge() -> None:
    graph = _graph(
        """#context {
    alpha: Real
}
"""
    )
    assert ("context:ctx.anon1", "sym:ctx.anon1/alpha", "declares") in _edges(graph)


def test_acceptance_document_dag() -> None:
    graph = _graph(
        """#context {
    alpha: Real & Positive
}

$$ #eq:a
x + alpha
$$

#assert:test(using=sympy) {
    claim substitute(#eq:a, x=0) == alpha
}

#exec:plot(
    python,
    inputs=[alpha]
) {
from xdlt_runtime import output

output.json({
    "alpha": alpha
})
}

#fig:data(
    source=#exec:plot[0]
) {
    Generated result.
}
"""
    )
    edges = _edges(graph)
    assert ("eq:a", "sym:ctx.anon1/alpha", "uses-symbol") in edges
    assert ("assert:test", "eq:a", "references") in edges
    assert ("assert:test", "sym:ctx.anon1/alpha", "uses-symbol") in edges
    assert ("exec:plot", "sym:ctx.anon1/alpha", "exec-input") in edges
    assert ("exec:plot", "result:exec.plot/0", "produces") in edges
    assert ("fig:data", "result:exec.plot/0", "renders") in edges
    assert graph.find_cycles() == []


def test_builder_is_deterministic() -> None:
    hw = """#context {
    alpha: Real
}

$$ #eq:a
x + alpha
$$

#assert:test {
    claim substitute(#eq:a, x=0) == alpha
}
"""
    first = _graph(hw)
    second = _graph(hw)
    assert [n.node_id for n in first.nodes.values()] == [n.node_id for n in second.nodes.values()]
    assert first.edges == second.edges
    assert first.topological_order() == second.topological_order()
    for node_id, node in first.nodes.items():
        assert node.semantic_hash == second.nodes[node_id].semantic_hash


def test_multi_line_exec_header_parses() -> None:
    ir = lower_to_semantic_ir(
        parse_xdlt(
            """#exec:plot(
    python,
    kernel="python3",
    inputs=[alpha, L]
) {
print("hi")
}
"""
        )
    )
    exec_entity = next(child for child in ir["children"] if child["type"] == "Executable")
    assert exec_entity["language"] == "python"
    assert exec_entity["kernel"] == "python3"
    assert [i["name"] for i in exec_entity["inputs"]] == ["alpha", "L"]


# --- cycle detection --------------------------------------------------------


def test_cycle_detection_returns_path() -> None:
    graph = _graph(
        """#assert:a {
    claim #assert:b
}

#assert:b {
    claim #assert:a
}

#assert:independent {
    claim 1 == 1
}
"""
    )
    cycles = graph.find_cycles()
    assert len(cycles) == 1
    assert cycles[0][0] == cycles[0][-1]
    assert "assert:a" in cycles[0] and "assert:b" in cycles[0]
    order = graph.topological_order()
    assert "assert:independent" in order  # acyclic nodes still schedule
    assert "assert:a" not in order and "assert:b" not in order  # cycle omitted


def test_graph_module_cycle_path_explicit() -> None:
    from neomath.xdlt.graph import DependencyGraph

    graph = DependencyGraph()
    graph.add_node("exec:a", "executable")
    graph.add_node("exec:b", "executable")
    graph.add_edge("exec:a", "exec:b", "references")
    graph.add_edge("exec:b", "exec:a", "references")
    cycles = graph.find_cycles()
    assert cycles == [["exec:a", "exec:b", "exec:a"]]


# --- invalidation -----------------------------------------------------------


def test_invalidation_only_touches_dependents() -> None:
    graph = _graph(
        """#context {
    alpha: Real
    beta: Real
}

$$ #eq:a
x + alpha
$$

$$ #eq:unrelated
y + beta
$$

#assert:test {
    claim substitute(#eq:a, x=0) == alpha
}

#assert:other {
    claim substitute(#eq:unrelated, y=0) == beta
}
"""
    )
    affected = set(invalidate(graph, "sym:ctx.anon1/alpha"))
    assert "eq:a" in affected
    assert "assert:test" in affected
    assert "eq:unrelated" not in affected
    assert "assert:other" not in affected
    assert "sym:ctx.anon1/beta" not in affected


def test_invalidation_follows_result_to_figure() -> None:
    graph = _graph(
        """#context {
    alpha: Real
}

#exec:plot(python, inputs=[alpha]) {
print(alpha)
}

#fig:data(source=#exec:plot[0]) {
    Generated.
}
"""
    )
    affected = set(invalidate(graph, "sym:ctx.anon1/alpha"))
    assert affected == {
        "sym:ctx.anon1/alpha",
        "exec:plot",
        "result:exec.plot/0",
        "fig:data",
    }


# --- semantic hashes --------------------------------------------------------


def test_math_formatting_does_not_change_hash() -> None:
    first = _graph("$$ #eq:a\nx+1\n$$")
    second = _graph("$$ #eq:a\nx + 1\n$$")
    changed = _graph("$$ #eq:a\nx + 2\n$$")
    assert first.nodes["eq:a"].semantic_hash == second.nodes["eq:a"].semantic_hash
    assert first.nodes["eq:a"].semantic_hash != changed.nodes["eq:a"].semantic_hash


def test_assertion_hash_changes_when_referenced_equation_changes() -> None:
    base = """$$ #eq:a
x + 1 = 2
$$

#assert:test {
    claim substitute(#eq:a, x=0)
}
"""
    changed = base.replace("x + 1 = 2", "x + 2 = 2")
    first = _graph(base)
    second = _graph(changed)
    assert first.nodes["assert:test"].semantic_hash != second.nodes["assert:test"].semantic_hash


def test_symbol_hash_is_position_free() -> None:
    first = _graph(
        """#context {
    alpha: Real
}

$$ #eq:a
x + alpha
$$
"""
    )
    second = _graph(
        """#context {
    alpha: Real
}


$$ #eq:a
x + alpha
$$
"""
    )
    first_hash = first.nodes["sym:ctx.anon1/alpha"].semantic_hash
    second_hash = second.nodes["sym:ctx.anon1/alpha"].semantic_hash
    assert first_hash == second_hash


# --- figure source resolution -----------------------------------------------


def test_figure_source_resolves_to_exec_target() -> None:
    ir = lower_to_semantic_ir(
        parse_xdlt(
            """#exec:plot(python) {
print("hi")
}

#fig:data(source=#exec:plot[0]) {
    Generated.
}
"""
        )
    )
    fig = next(child for child in ir["children"] if child["type"] == "Figure")
    assert fig["source"] == {"targetId": "exec:plot", "index": "0"}
