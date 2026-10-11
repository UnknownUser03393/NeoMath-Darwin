from __future__ import annotations

import json
from pathlib import Path

from neomath.xdlt.cards import CardRegistry
from neomath.xdlt.graph import invalidate
from neomath.xdlt.project import XdltProject


def _write_card(
    cards_dir: Path, card_id: str, version: str, filename: str | None = None, **overrides
) -> None:
    data = {
        "id": card_id,
        "version": version,
        "type": "derivation",
        "title": card_id,
        "parameters": {"L": {"type": "Real", "requires": ["L > 0"]}},
        "content": "$$ #eq:main\n\\theta = L\n$$",
        "dependencies": [],
    }
    data.update(overrides)
    (cards_dir / (filename or f"{card_id}.card.json")).write_text(
        json.dumps(data), encoding="utf-8"
    )


def _load(cards_dir: Path) -> CardRegistry:
    return CardRegistry.from_directory(cards_dir)


def _refs(semantic_ir) -> list[dict]:
    return [c for c in semantic_ir["children"] if c["type"] == "CardReference"]


def _codes(project: XdltProject) -> list[str]:
    codes = [d.code for d in project.diagnostics]
    codes += [d.get("code") for d in project.semantic_ir.get("diagnostics", [])]
    return codes


# --- registry ---------------------------------------------------------------


def test_load_valid_card(tmp_path) -> None:
    _write_card(tmp_path, "heat", "1.0.0")
    registry = _load(tmp_path)
    card = registry.resolve("heat")
    assert card is not None
    assert card.version == "1.0.0"
    assert card.parameters["L"].requires == ["L > 0"]
    assert card.content_ir is not None  # content parsed by the real .hw parser


def test_invalid_card(tmp_path) -> None:
    (tmp_path / "broken.card.json").write_text('{"version": "1.0"}', encoding="utf-8")
    registry = _load(tmp_path)
    codes = [d["code"] for d in registry.diagnostics]
    assert "INVALID_CARD" in codes


def test_duplicate_card_version(tmp_path) -> None:
    _write_card(tmp_path, "heat", "1.0.0", title="first")
    _write_card(tmp_path, "heat2", "1.0.0", title="second")
    # Same id + version across files is a duplicate.
    (tmp_path / "heat-dup.card.json").write_text(
        json.dumps(
            {"id": "heat", "version": "1.0.0", "type": "derivation", "title": "dup"}
        ),
        encoding="utf-8",
    )
    registry = _load(tmp_path)
    codes = [d["code"] for d in registry.diagnostics]
    assert "DUPLICATE_CARD_VERSION" in codes


def test_version_selection_picks_latest(tmp_path) -> None:
    _write_card(tmp_path, "heat", "1.0.0", filename="heat-v1.card.json", title="old")
    _write_card(tmp_path, "heat", "1.2.0", filename="heat-v2.card.json", title="new")
    registry = _load(tmp_path)
    assert registry.versions("heat") == ["1.0.0", "1.2.0"]
    assert registry.resolve("heat").version == "1.2.0"
    assert registry.resolve("heat", "1.0.0").version == "1.0.0"
    assert registry.resolve("heat", "9.9.9") is None


def test_unknown_card_diagnostic(tmp_path) -> None:
    _write_card(tmp_path, "heat", "1.0.0")
    project = XdltProject.load(
        "#use-card:x(#card:missing, mode=reference) {\nbind L = L\n}",
        cards_dir=tmp_path,
    )
    assert "UNKNOWN_CARD" in _codes(project)


def test_card_version_not_found(tmp_path) -> None:
    _write_card(tmp_path, "heat", "1.0.0")
    project = XdltProject.load(
        "#use-card:x(#card:heat@2.0.0, mode=reference) {\nbind L = L\n}",
        cards_dir=tmp_path,
    )
    assert "CARD_VERSION_NOT_FOUND" in _codes(project)


def test_card_version_missing(tmp_path) -> None:
    (tmp_path / "nover.card.json").write_text(
        json.dumps({"id": "nover", "type": "theorem"}), encoding="utf-8"
    )
    registry = _load(tmp_path)
    assert registry.resolve("nover") is None  # no usable version to select
    assert "CARD_VERSION_MISSING" in [d["code"] for d in registry.diagnostics]


# --- binding ----------------------------------------------------------------


def test_symbol_binding_resolves_by_identity(tmp_path) -> None:
    _write_card(tmp_path, "heat", "1.0.0")
    project = XdltProject.load(
        """#context {
    L: Real & Positive = 1
}

#use-card:h(#card:heat, mode=reference) {
    bind L = L
}
""",
        cards_dir=tmp_path,
    )
    ref = _refs(project.semantic_ir)[0]
    binding = ref["bindings"][0]
    assert binding["parameter"] == "L"
    assert binding["kind"] == "symbol"
    assert binding["symbolId"] == "sym:ctx.anon1/L"


def test_literal_binding(tmp_path) -> None:
    _write_card(tmp_path, "heat", "1.0.0")
    project = XdltProject.load(
        "#use-card:h(#card:heat, mode=reference) {\nbind L = 2\n}",
        cards_dir=tmp_path,
    )
    binding = _refs(project.semantic_ir)[0]["bindings"][0]
    assert binding["kind"] == "literal"
    assert binding["literal"] == {"kind": "integer", "value": 2}


# --- requirements -----------------------------------------------------------


def test_requirement_valid(tmp_path) -> None:
    _write_card(tmp_path, "heat", "1.0.0")
    project = XdltProject.load(
        """#context {
    L: Real & Positive = 1
}

#use-card:h(#card:heat, mode=reference) {
    bind L = L
}
""",
        cards_dir=tmp_path,
    )
    ref = _refs(project.semantic_ir)[0]
    assert ref["requirements"] == [{"source": "L > 0", "status": "valid", "message": ""}]
    assert "CARD_REQUIREMENT_UNSATISFIED" not in _codes(project)


def test_requirement_failed(tmp_path) -> None:
    _write_card(tmp_path, "heat", "1.0.0")
    project = XdltProject.load(
        """#context {
    L: Real & Positive = -1
}

#use-card:h(#card:heat, mode=reference) {
    bind L = L
}
""",
        cards_dir=tmp_path,
    )
    ref = _refs(project.semantic_ir)[0]
    assert ref["requirements"][0]["status"] == "unsatisfied"
    assert "CARD_REQUIREMENT_UNSATISFIED" in _codes(project)


def test_requirement_unknown_is_not_failed(tmp_path) -> None:
    _write_card(tmp_path, "heat", "1.0.0")
    project = XdltProject.load(
        """#context {
    L: Real
}

#use-card:h(#card:heat, mode=reference) {
    bind L = L
}
""",
        cards_dir=tmp_path,
    )
    ref = _refs(project.semantic_ir)[0]
    assert ref["requirements"][0]["status"] == "unknown"
    codes = _codes(project)
    assert "CARD_REQUIREMENT_UNKNOWN" in codes
    assert "CARD_REQUIREMENT_UNSATISFIED" not in codes


# --- modes / provenance -----------------------------------------------------


def test_reference_mode_provenance(tmp_path) -> None:
    _write_card(tmp_path, "heat", "1.0.0")
    project = XdltProject.load(
        "#use-card:h(#card:heat, mode=reference) {\nbind L = 2\n}",
        cards_dir=tmp_path,
    )
    ref = _refs(project.semantic_ir)[0]
    assert ref["mode"] == "reference"
    assert ref["provenance"]["cardId"] == "heat"
    assert ref["provenance"]["cardVersion"] == "1.0.0"
    assert ref["provenance"]["cardSemanticHash"]
    assert ref["provenance"]["sourcePath"]


def test_snapshot_mode_pins_hash(tmp_path) -> None:
    _write_card(tmp_path, "heat", "1.0.0")
    project = XdltProject.load(
        "#use-card:h(#card:heat, mode=snapshot) {\nbind L = 2\n}",
        cards_dir=tmp_path,
    )
    ref = _refs(project.semantic_ir)[0]
    assert ref["mode"] == "snapshot"
    assert ref["provenance"]["pinnedHash"] == ref["provenance"]["cardSemanticHash"]


def test_fork_mode_records_origin(tmp_path) -> None:
    _write_card(tmp_path, "heat", "1.0.0")
    project = XdltProject.load(
        "#use-card:h(#card:heat, mode=fork) {\nbind L = 2\n}",
        cards_dir=tmp_path,
    )
    ref = _refs(project.semantic_ir)[0]
    assert ref["mode"] == "fork"
    assert ref["provenance"]["originCard"] == "heat"
    assert ref["provenance"]["originVersion"] == "1.0.0"


# --- card semantic hash -----------------------------------------------------


def test_card_hash_is_position_free() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        _write_card(Path(tmp), "heat", "1.0.0", content="$$ #eq:main\n\\theta = L\n$$")
        first = _load(Path(tmp)).resolve("heat")
        (Path(tmp) / "heat.card.json").write_text(
            json.dumps(
                {
                    "id": "heat",
                    "version": "1.0.0",
                    "type": "derivation",
                    "content": "$$ #eq:main\n\\theta   =   L\n$$",
                    "parameters": {"L": {"type": "Real", "requires": ["L > 0"]}},
                }
            ),
            encoding="utf-8",
        )
        second = _load(Path(tmp)).resolve("heat")
    assert first.semantic_hash == second.semantic_hash


def test_card_hash_changes_on_semantic_change() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        _write_card(Path(tmp), "heat", "1.0.0", content="$$ #eq:main\n\\theta = L\n$$")
        first = _load(Path(tmp)).resolve("heat")
        (Path(tmp) / "heat.card.json").write_text(
            json.dumps(
                {
                    "id": "heat",
                    "version": "1.0.0",
                    "type": "derivation",
                    "content": "$$ #eq:main\n\\theta = L + 1\n$$",
                    "parameters": {"L": {"type": "Real", "requires": ["L > 0"]}},
                }
            ),
            encoding="utf-8",
        )
        second = _load(Path(tmp)).resolve("heat")
    assert first.semantic_hash != second.semantic_hash


# --- cross-card dependencies + DAG ------------------------------------------


def test_cross_card_dependency_enters_dag(tmp_path) -> None:
    _write_card(tmp_path, "base", "1.0.0", title="base")
    _write_card(
        tmp_path,
        "heat",
        "1.0.0",
        title="heat",
        dependencies=["base"],
    )
    project = XdltProject.load(
        "#use-card:h(#card:heat, mode=reference) {\nbind L = 2\n}",
        cards_dir=tmp_path,
    )
    edges = {(s, t) for s, t, _e in project.graph.edges}
    assert ("card:heat@1.0.0", "card:base@1.0.0") in edges
    assert ("use-card:h", "card:heat@1.0.0") in edges


def test_card_dependency_cycle_detected(tmp_path) -> None:
    _write_card(tmp_path, "a", "1.0.0", title="a", dependencies=["b"])
    _write_card(tmp_path, "b", "1.0.0", title="b", dependencies=["a"])
    project = XdltProject.load(
        "#use-card:h(#card:a, mode=reference) {\nbind L = 2\n}",
        cards_dir=tmp_path,
    )
    cycles = project.graph.find_cycles()
    assert cycles
    path = cycles[0]
    assert path[0] == path[-1]
    assert "card:a@1.0.0" in path and "card:b@1.0.0" in path


def test_dag_invalidation_reaches_card_dependent(tmp_path) -> None:
    _write_card(tmp_path, "heat", "1.0.0")
    project = XdltProject.load(
        """#context {
    L: Real & Positive = 1
}

#use-card:h(#card:heat, mode=reference) {
    bind L = L
}
""",
        cards_dir=tmp_path,
    )
    affected = set(invalidate(project.graph, "sym:ctx.anon1/L"))
    assert "use-card:h" in affected
