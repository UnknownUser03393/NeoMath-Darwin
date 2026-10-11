from __future__ import annotations

from neomath.xdlt import build_dependency_graph, lower_to_semantic_ir, parse_xdlt
from neomath.xdlt.graph import invalidate
from neomath.xdlt.values import (
    build_value_environment,
    parse_value_expression,
    semantic_value_to_python,
)
from neomath.xdlt.values.nodes import (
    IntegerValue,
    ListValue,
    RealValue,
    SymbolicValue,
)


def _env(hw: str, overrides: dict | None = None):
    return build_value_environment(lower_to_semantic_ir(parse_xdlt(hw)), overrides)


def _codes(hw: str) -> list[str]:
    ir = lower_to_semantic_ir(parse_xdlt(hw))
    return [d["code"] for d in ir["diagnostics"]]


# --- value assignment -------------------------------------------------------


def test_typed_value_declaration() -> None:
    env = _env("#context {\n    alpha: Real & Positive = 0.01\n}")
    value = env.resolve("sym:ctx.anon1/alpha")
    assert isinstance(value, RealValue)
    assert value.value == 0.01


def test_integer_and_real_conversion() -> None:
    env = _env("#context {\n    L: Real & Positive = 1\n    n: Integer & Positive\n}")
    assert isinstance(env.resolve("sym:ctx.anon1/L"), IntegerValue)
    assert env.resolve("sym:ctx.anon1/L").value == 1
    symbolic = env.resolve("sym:ctx.anon1/n")
    assert isinstance(symbolic, SymbolicValue)
    assert symbolic.name == "n"
    assert symbolic.type_expr == "Integer"
    assert symbolic.properties == ["Positive"]


def test_constraint_violation() -> None:
    codes = _codes("#context {\n    alpha: Real & Positive = -1\n}")
    assert "VALUE_CONSTRAINT_VIOLATION" in codes


def test_type_mismatch() -> None:
    codes = _codes("#context {\n    n: Integer = 3.14\n}")
    assert "VALUE_TYPE_MISMATCH" in codes


def test_natural_negative_is_violation() -> None:
    codes = _codes("#context {\n    n: Natural = -1\n}")
    assert "VALUE_CONSTRAINT_VIOLATION" in codes


def test_valid_value_has_no_diagnostics() -> None:
    assert _codes("#context {\n    alpha: Real & Positive = 0.01\n}") == []


def test_list_value() -> None:
    value = parse_value_expression("[0, 1, 2]")
    assert isinstance(value, ListValue)
    assert [item.value for item in value.items] == [0, 1, 2]


def test_symbolic_fallback_is_sympy_symbol() -> None:
    env = _env("#context {\n    n: Integer\n}")
    value = env.resolve("sym:ctx.anon1/n")
    python_value = semantic_value_to_python(value)
    assert str(python_value) == "n"
    assert python_value.is_integer


# --- runtime override -------------------------------------------------------


def test_runtime_override() -> None:
    hw = "#context {\n    alpha: Real = 0.01\n}"
    base = _env(hw)
    overridden = _env(hw, {"alpha": 0.02})
    assert base.resolve("sym:ctx.anon1/alpha").value == 0.01
    assert overridden.resolve("sym:ctx.anon1/alpha").value == 0.02


def test_override_does_not_mutate_source() -> None:
    hw = "#context {\n    alpha: Real = 0.01\n}"
    overridden = _env(hw, {"alpha": 0.02})
    document_value = overridden.resolve("sym:ctx.anon1/alpha")
    assert document_value.value == 0.02
    # A fresh environment without the override still sees the document value.
    assert _env(hw).resolve("sym:ctx.anon1/alpha").value == 0.01


def test_concrete_values_reach_execution() -> None:
    from neomath.xdlt.execution import ExecutionEngine

    ir = lower_to_semantic_ir(
        parse_xdlt(
            """#context {
    alpha: Real & Positive = 0.01
    L: Real & Positive = 1
}

#exec:test(python, inputs=[alpha, L]) {
from xdlt_runtime import output
output.json({"alpha": alpha, "L": L})
}
"""
        )
    )
    env = build_value_environment(ir)
    graph = build_dependency_graph(ir, value_environment=env)
    engine = ExecutionEngine()
    outcome = engine.execute_document(ir, graph, env)
    assert outcome["results"][0].outputs[0].to_dict()["value"] == {"alpha": 0.01, "L": 1}


# --- value hash / DAG -------------------------------------------------------


def test_value_change_changes_symbol_hash() -> None:
    hw = (
        "#context {\n    alpha: Real & Positive = 0.01\n}\n"
        "\n#exec:plot(python, inputs=[alpha]) {\nprint(alpha)\n}"
    )
    ir1 = lower_to_semantic_ir(parse_xdlt(hw))
    ir2 = lower_to_semantic_ir(parse_xdlt(hw.replace("0.01", "0.02")))
    g1 = build_dependency_graph(ir1)
    g2 = build_dependency_graph(ir2)
    alpha1 = g1.nodes["sym:ctx.anon1/alpha"].semantic_hash
    alpha2 = g2.nodes["sym:ctx.anon1/alpha"].semantic_hash
    assert alpha1 != alpha2
    assert g1.nodes["exec:plot"].semantic_hash != g2.nodes["exec:plot"].semantic_hash


def test_formatting_only_edit_keeps_hash() -> None:
    hw1 = "#context {\n    alpha: Real & Positive = 0.01\n}"
    hw2 = "#context {\n    alpha:Real&Positive=0.01\n}"
    g1 = build_dependency_graph(lower_to_semantic_ir(parse_xdlt(hw1)))
    g2 = build_dependency_graph(lower_to_semantic_ir(parse_xdlt(hw2)))
    alpha1 = g1.nodes["sym:ctx.anon1/alpha"].semantic_hash
    alpha2 = g2.nodes["sym:ctx.anon1/alpha"].semantic_hash
    assert alpha1 == alpha2


def test_override_dirties_dependents() -> None:
    hw = """#context {
    alpha: Real & Positive = 0.01
}

#exec:plot(python, inputs=[alpha]) {
print(alpha)
}

#fig:data(source=#exec:plot[0]) {
    Generated.
}
"""
    ir = lower_to_semantic_ir(parse_xdlt(hw))
    env = build_value_environment(ir)
    graph = build_dependency_graph(ir, value_environment=env)
    affected = set(invalidate(graph, "sym:ctx.anon1/alpha"))
    assert {"exec:plot", "result:exec.plot/0", "fig:data"} <= affected
