"""Dependency-graph node model for xdlt documents.

Graph nodes are NOT AST nodes. The AST describes *source structure*; the graph
describes *semantic dependencies*. A node carries its stable semantic identity
(``eq:heat``, ``sym:ctx.global/alpha``), a position-free semantic hash, and a
build state. Nodes never carry source positions, so a formatter pass cannot
invalidate the graph.
"""

from __future__ import annotations

from typing import Any

# Graph node kinds.
CONTEXT = "context"
SYMBOL = "symbol"
EQUATION = "equation"
MATH_EXPRESSION = "math_expression"
ASSERTION = "assertion"
EXECUTABLE = "executable"
EXECUTION_RESULT = "execution_result"
FIGURE = "figure"
SEMANTIC_BLOCK = "semantic_block"
CARD = "card"
CARD_REFERENCE = "card_reference"

NODE_KINDS = frozenset(
    {
        CONTEXT,
        SYMBOL,
        EQUATION,
        MATH_EXPRESSION,
        ASSERTION,
        EXECUTABLE,
        EXECUTION_RESULT,
        FIGURE,
        SEMANTIC_BLOCK,
        CARD,
        CARD_REFERENCE,
    }
)

# Document / node build states.
CLEAN = "clean"
DIRTY = "dirty"
RUNNING = "running"
FAILED = "failed"
BLOCKED = "blocked"
UNAVAILABLE = "unavailable"

BUILD_STATES = frozenset({CLEAN, DIRTY, RUNNING, FAILED, BLOCKED, UNAVAILABLE})


class GraphNode:
    __slots__ = ("node_id", "kind", "semantic_hash", "state", "data", "order")

    def __init__(
        self,
        node_id: str,
        kind: str,
        semantic_hash: str = "",
        data: dict[str, Any] | None = None,
        order: int = 0,
        state: str = DIRTY,
    ) -> None:
        self.node_id = node_id
        self.kind = kind
        self.semantic_hash = semantic_hash
        self.data = data or {}
        self.order = order
        self.state = state

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.node_id,
            "kind": self.kind,
            "semanticHash": self.semantic_hash,
            "state": self.state,
            "order": self.order,
        }
