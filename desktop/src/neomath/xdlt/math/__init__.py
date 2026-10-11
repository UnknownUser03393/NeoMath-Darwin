"""xdlt math subsystem: LaTeX-math subset parser and Math Semantic IR."""

from __future__ import annotations

from neomath.xdlt.math.lexer import Token, tokenize
from neomath.xdlt.math.lower import lower_to_semantic
from neomath.xdlt.math.nodes import (
    MathDiagnostic,
    MathNode,
    MathRange,
    iter_math,
)
from neomath.xdlt.math.parser import parse_math


def collect_math_diagnostics(root: MathNode) -> list[MathDiagnostic]:
    """All diagnostics attached anywhere in a math tree."""
    result: list[MathDiagnostic] = []
    for node in iter_math(root):
        result.extend(node.diagnostics)
    return result


__all__ = [
    "Token",
    "tokenize",
    "parse_math",
    "lower_to_semantic",
    "MathDiagnostic",
    "MathNode",
    "MathRange",
    "iter_math",
    "collect_math_diagnostics",
]
