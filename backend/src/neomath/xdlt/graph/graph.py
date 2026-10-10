"""Directed dependency graph with typed edges, cycle detection and scheduling.

Edge direction is uniform: ``A --type--> B`` means *A's result depends on B*
(for the default ``reverse`` edges such as ``uses-symbol``/``references``).
Invalidation therefore propagates from the dependency toward the dependent
(``B`` changing dirties ``A``).

Two edge kinds are *forward* feeding relations instead: ``produces``
(executable -> result) and ``declares`` (context -> symbol). There the source
feeds the target, so invalidation propagates source -> target and the target
depends on the source for scheduling.

Everything here is deterministic: node insertion order is document order and
every traversal is seeded from insertion order, so equal input produces equal
output.
"""

from __future__ import annotations

from typing import Any

from neomath.xdlt.graph.nodes import DIRTY, GraphNode

# Forward edges: source feeds target (target depends on source).
_FORWARD_EDGE_TYPES = frozenset({"produces", "declares"})

EDGE_TYPES = frozenset(
    {
        "references",
        "uses-symbol",
        "depends-on",
        "verifies",
        "exec-input",
        "produces",
        "renders",
        "condition",
        "declares",
    }
)


class DependencyGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[tuple[str, str, str]] = []
        self._order = 0

    # --- construction ----------------------------------------------------
    def add_node(
        self,
        node_id: str,
        kind: str,
        semantic_hash: str = "",
        data: dict[str, Any] | None = None,
        state: str | None = None,
    ) -> GraphNode:
        existing = self.nodes.get(node_id)
        if existing is not None:
            # A later pass may enrich a placeholder created earlier (e.g. a
            # symbol node first seen through an edge, later declared).
            if data and not existing.data:
                existing.data = data
            if semantic_hash and not existing.semantic_hash:
                existing.semantic_hash = semantic_hash
            if state is not None:
                existing.state = state
            return existing
        node = GraphNode(node_id, kind, semantic_hash, data, self._order, state or DIRTY)
        self.nodes[node_id] = node
        self._order += 1
        return node

    def add_edge(self, source: str, target: str, edge_type: str) -> None:
        edge = (source, target, edge_type)
        if edge not in self.edges:
            self.edges.append(edge)

    # --- dependency semantics --------------------------------------------
    def dependents(self, node_id: str) -> list[str]:
        """Nodes whose result is invalidated when ``node_id`` changes."""
        result: list[str] = []
        for source, target, edge_type in self.edges:
            if edge_type in _FORWARD_EDGE_TYPES:
                if source == node_id:
                    result.append(target)
            else:
                if target == node_id:
                    result.append(source)
        return result

    def dependencies(self, node_id: str) -> list[str]:
        """Nodes whose change invalidates ``node_id`` (must run before it)."""
        result: list[str] = []
        for source, target, edge_type in self.edges:
            if edge_type in _FORWARD_EDGE_TYPES:
                if target == node_id:
                    result.append(source)
            else:
                if source == node_id:
                    result.append(target)
        return result

    # --- traversal -------------------------------------------------------
    def find_cycles(self) -> list[list[str]]:
        """Return dependency cycles as node-id paths (deterministic)."""
        # Iterative DFS with three-state colouring; back edge -> cycle path.
        nodes = sorted(self.nodes, key=lambda nid: self.nodes[nid].order)
        color: dict[str, int] = {nid: 0 for nid in nodes}
        stack: list[str] = []

        def neighbors(node_id: str) -> list[str]:
            deps = self.dependencies(node_id)
            return sorted(deps, key=lambda nid: self.nodes[nid].order)

        for start in nodes:
            if color[start] != 0:
                continue
            frame: list[tuple[str, int]] = [(start, 0)]
            color[start] = 1
            stack.append(start)
            while frame:
                node_id, child_index = frame[-1]
                children = neighbors(node_id)
                if child_index < len(children):
                    child = children[child_index]
                    frame[-1] = (node_id, child_index + 1)
                    if color[child] == 1:
                        # child is on the current stack -> cycle.
                        start_index = stack.index(child)
                        return [stack[start_index:] + [child]]
                    if color[child] == 0:
                        color[child] = 1
                        stack.append(child)
                        frame.append((child, 0))
                else:
                    color[node_id] = 2
                    stack.pop()
                    frame.pop()
        return []

    def topological_order(self) -> list[str]:
        """Deterministic Kahn ordering; nodes in a cycle are omitted."""
        indegree: dict[str, int] = {nid: 0 for nid in self.nodes}
        for nid in self.nodes:
            indegree[nid] = len(self.dependencies(nid))
        # Initial frontier in insertion order keeps the result deterministic.
        ready = [nid for nid in self.nodes if indegree[nid] == 0]
        result: list[str] = []
        while ready:
            node_id = ready.pop(0)
            result.append(node_id)
            for dependent in self.dependents(node_id):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
        return result

    # --- serialization ---------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [
                {"source": source, "target": target, "type": edge_type}
                for source, target, edge_type in self.edges
            ],
            "cycles": self.find_cycles(),
            "topologicalOrder": self.topological_order(),
        }
