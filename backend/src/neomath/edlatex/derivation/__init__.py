from __future__ import annotations

from typing import Any

from neomath.edlatex.derivation.rules import (
    CALCULUS,
    EQUATION_OP,
    EQUIVALENCE,
    RULES,
    SOLVE,
    RuleSpec,
    all_rule_ids,
    rule_spec,
)

__all__ = [
    "DerivationGraph",
    "GraphStep",
    "RuleSpec",
    "RULES",
    "all_rule_ids",
    "rule_spec",
    "EQUIVALENCE",
    "EQUATION_OP",
    "CALCULUS",
    "SOLVE",
]


def __getattr__(name: str) -> Any:
    if name in {"DerivationGraph", "GraphStep"}:
        from neomath.edlatex.derivation.graph import DerivationGraph, GraphStep

        return {"DerivationGraph": DerivationGraph, "GraphStep": GraphStep}[name]
    raise AttributeError(name)
