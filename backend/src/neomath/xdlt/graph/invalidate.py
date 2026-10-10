"""Incremental invalidation over the dependency graph.

``invalidate_nodes`` returns the exact closure of nodes that must be re-run when
a given set of nodes changes. Only true dependents are returned; unrelated
nodes are never touched.
"""

from __future__ import annotations

from neomath.xdlt.graph.graph import DependencyGraph


def invalidate_nodes(graph: DependencyGraph, changed_ids: list[str]) -> list[str]:
    """Nodes that become dirty when ``changed_ids`` change, in document order."""
    affected: set[str] = set()
    frontier = list(changed_ids)
    while frontier:
        current = frontier.pop(0)
        if current in affected:
            continue
        affected.add(current)
        for dependent in graph.dependents(current):
            if dependent not in affected:
                frontier.append(dependent)
    return sorted(affected, key=lambda nid: graph.nodes[nid].order)


def invalidate(graph: DependencyGraph, node_id: str) -> list[str]:
    """Convenience wrapper: invalidate from a single node."""
    return invalidate_nodes(graph, [node_id])
