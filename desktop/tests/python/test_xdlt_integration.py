from __future__ import annotations

import json
from pathlib import Path

from neomath.xdlt.execution import ExecutionEngine
from neomath.xdlt.project import XdltProject

_DOC = """#context {
    alpha: Real & Positive = 0.01
    L: Real & Positive = 1
}

#use-card:heat(
    #card:heat-solution,
    mode=reference
) {
    bind alpha = alpha
    bind L = L
}

#exec:test(
    python,
    inputs=[alpha, L]
) {
from xdlt_runtime import output

output.json({
    "alpha": alpha,
    "L": L
})
}
"""


def _make_project(tmp_path: Path, values: dict | None = None) -> XdltProject:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(exist_ok=True)
    (cards_dir / "heat-solution.card.json").write_text(
        json.dumps(
            {
                "id": "heat-solution",
                "version": "1.0.0",
                "type": "derivation",
                "title": "Heat solution",
                "parameters": {
                    "alpha": {"type": "Real", "requires": ["alpha > 0"]},
                    "L": {"type": "Real", "requires": ["L > 0"]},
                },
                "content": "$$ #eq:heat-sol\n\\theta = \\alpha x^2 + L\n$$",
                "dependencies": [],
            }
        ),
        encoding="utf-8",
    )
    return XdltProject.load(_DOC, cards_dir=cards_dir, values=values)


def test_full_acceptance_closed_loop(tmp_path) -> None:
    project = _make_project(tmp_path)
    assert project.diagnostics == []  # no errors anywhere

    # 1. bindings resolve by identity
    reference = next(
        c for c in project.semantic_ir["children"] if c["type"] == "CardReference"
    )
    bound = {b["parameter"]: b["symbolId"] for b in reference["bindings"]}
    assert bound["alpha"] == "sym:ctx.anon1/alpha"
    assert bound["L"] == "sym:ctx.anon1/L"

    # 2. requirements verify
    statuses = {r["source"]: r["status"] for r in reference["requirements"]}
    assert statuses == {"alpha > 0": "valid", "L > 0": "valid"}

    # 3. value environment resolves
    env = project.value_environment
    assert env.resolve("sym:ctx.anon1/alpha").to_dict() == {
        "kind": "real",
        "value": 0.01,
    }
    assert env.resolve("sym:ctx.anon1/L").to_dict() == {"kind": "integer", "value": 1}

    # 4. graph builds with cards
    nodes = {n.node_id: n.kind for n in project.graph.nodes.values()}
    assert nodes["use-card:heat"] == "card_reference"
    assert nodes["card:heat-solution@1.0.0"] == "card"
    assert nodes["exec:test"] == "executable"

    # 5. exec receives concrete values
    engine = ExecutionEngine(cache_dir=tmp_path / ".xdlt-cache")
    outcome = engine.execute_document(
        project.semantic_ir, project.graph, project.value_environment
    )
    result = outcome["results"][0]
    assert result.status == "success"
    assert result.outputs[0].to_dict()["value"] == {"alpha": 0.01, "L": 1}

    # 6. cache works
    second_project = _make_project(tmp_path)
    second_outcome = engine.execute_document(
        second_project.semantic_ir, second_project.graph, second_project.value_environment
    )
    assert second_outcome["cacheHits"] == ["exec:test"]


def test_runtime_override_reruns_with_new_value(tmp_path) -> None:
    project = _make_project(tmp_path)
    engine = ExecutionEngine(cache_dir=tmp_path / ".xdlt-cache")
    first = engine.execute_document(
        project.semantic_ir, project.graph, project.value_environment
    )
    assert first["results"][0].outputs[0].to_dict()["value"] == {"alpha": 0.01, "L": 1}

    # Override alpha -> 0.02 without touching source.
    overridden = _make_project(tmp_path, values={"alpha": 0.02})
    assert overridden.value_environment.resolve("sym:ctx.anon1/alpha").to_dict() == {
        "kind": "real",
        "value": 0.02,
    }
    # The source declaration is untouched.
    assert "0.01" in _DOC

    # Value change dirties the executable hash -> rerun, new cache entry.
    assert project.graph.nodes["exec:test"].semantic_hash != overridden.graph.nodes[
        "exec:test"
    ].semantic_hash
    second = engine.execute_document(
        overridden.semantic_ir, overridden.graph, overridden.value_environment
    )
    assert second["results"][0].cached is False
    assert second["results"][0].outputs[0].to_dict()["value"] == {"alpha": 0.02, "L": 1}
