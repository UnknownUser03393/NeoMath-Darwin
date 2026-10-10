"""xdlt Semantic Expression Language (SEL)."""

from __future__ import annotations

from neomath.xdlt.sel.evaluator import is_equation_value, map_equation, substitute_value
from neomath.xdlt.sel.lexer import SelToken, tokenize_sel
from neomath.xdlt.sel.lower import lower_sel
from neomath.xdlt.sel.nodes import (
    SelDiagnostic,
    SelNode,
    SelRange,
    iter_sel,
)
from neomath.xdlt.sel.parser import parse_sel


def collect_sel_diagnostics(root: SelNode) -> list[SelDiagnostic]:
    result: list[SelDiagnostic] = []
    for node in iter_sel(root):
        result.extend(node.diagnostics)
    return result


__all__ = [
    "SelToken",
    "SelDiagnostic",
    "SelNode",
    "SelRange",
    "iter_sel",
    "tokenize_sel",
    "parse_sel",
    "lower_sel",
    "collect_sel_diagnostics",
    "is_equation_value",
    "map_equation",
    "substitute_value",
]
