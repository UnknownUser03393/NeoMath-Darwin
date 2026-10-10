"""Dependency DAG + incremental invalidation for xdlt documents.

The graph is a *semantic* view derived from Math Semantic IR: stable semantic
IDs become typed nodes, anonymous-but-needed entities get deterministic
internal IDs, and typed edges record how results depend on each other.
"""

from __future__ import annotations

from neomath.xdlt.graph.builder import build_dependency_graph, result_node_id
from neomath.xdlt.graph.graph import EDGE_TYPES, DependencyGraph
from neomath.xdlt.graph.hash import (
    assertion_hash,
    context_hash,
    executable_hash,
    figure_hash,
    math_entity_hash,
    stable_hash,
    symbol_node_hash,
)
from neomath.xdlt.graph.invalidate import invalidate, invalidate_nodes
from neomath.xdlt.graph.nodes import (
    ASSERTION,
    BLOCKED,
    BUILD_STATES,
    CARD,
    CARD_REFERENCE,
    CLEAN,
    CONTEXT,
    DIRTY,
    EQUATION,
    EXECUTABLE,
    EXECUTION_RESULT,
    FAILED,
    FIGURE,
    MATH_EXPRESSION,
    NODE_KINDS,
    RUNNING,
    SEMANTIC_BLOCK,
    SYMBOL,
    UNAVAILABLE,
    GraphNode,
)

__all__ = [
    "ASSERTION",
    "BLOCKED",
    "BUILD_STATES",
    "CARD",
    "CARD_REFERENCE",
    "CLEAN",
    "CONTEXT",
    "DIRTY",
    "EQUATION",
    "EXECUTABLE",
    "EXECUTION_RESULT",
    "FAILED",
    "FIGURE",
    "MATH_EXPRESSION",
    "NODE_KINDS",
    "RUNNING",
    "SEMANTIC_BLOCK",
    "SYMBOL",
    "UNAVAILABLE",
    "DependencyGraph",
    "EDGE_TYPES",
    "GraphNode",
    "assertion_hash",
    "build_dependency_graph",
    "context_hash",
    "executable_hash",
    "figure_hash",
    "invalidate",
    "invalidate_nodes",
    "math_entity_hash",
    "result_node_id",
    "stable_hash",
    "symbol_node_hash",
]
