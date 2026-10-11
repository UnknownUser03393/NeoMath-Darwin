"""Session-scoped caches, environment snapshots and source-range indexing.

Cache keys are frozen dataclasses hashing the *semantic* identity plus the
relevant environment — never the bare semanticId alone, never object ids.
All cross-compilation reuse flows explicitly through ``CompilationSession``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neomath.xdlt.graph.hash import stable_hash


@dataclass(frozen=True)
class VerificationCacheKey:
    semantic_hash: str
    values_hash: str
    environment_hash: str
    verifier: str
    verifier_version: str


@dataclass(frozen=True)
class ExecutionCacheKey:
    semantic_hash: str
    values_hash: str
    environment_hash: str
    runner: str
    runner_version: str


class SessionCache:
    """Small typed dict; correctness never depends on its size."""

    def __init__(self) -> None:
        self._store: dict[Any, Any] = {}

    def get(self, key: Any) -> Any:
        return self._store.get(key)

    def put(self, key: Any, value: Any) -> None:
        self._store[key] = value

    def __len__(self) -> int:
        return len(self._store)


@dataclass(frozen=True)
class EnvironmentSnapshot:
    values: dict[str, Any]
    execute: bool
    verify: bool
    layout: dict[str, Any]
    cards_dir: str | None

    def values_hash(self) -> str:
        return stable_hash({"values": self.values})

    def layout_hash(self) -> str:
        return stable_hash({"layout": self.layout})

    def cards_hash(self) -> str:
        return stable_hash({"cards": self.cards_dir})

    def hash(self) -> str:
        return stable_hash(
            {
                "values": self.values,
                "execute": self.execute,
                "verify": self.verify,
                "layout": self.layout,
                "cards": self.cards_dir,
            }
        )


class SourceRangeIndex:
    """Maps source ranges to graph node ids for direct source-edit hits."""

    def __init__(self, graph: Any) -> None:
        self._entries: list[tuple[int, int, str]] = []
        self._order: dict[str, int] = {}
        for index, (node_id, node) in enumerate(graph.nodes.items()):
            self._order[node_id] = index
            source_range = (node.data or {}).get("sourceRange")
            if source_range and "start" in source_range and "end" in source_range:
                self._entries.append(
                    (int(source_range["start"]), int(source_range["end"]), node_id)
                )

    def affected_semantic_ids(self, changes: list[Any]) -> list[str]:
        affected: set[str] = set()
        for change in changes:
            start, end = change.start, change.end
            for node_start, node_end, node_id in self._entries:
                if _intersects(node_start, node_end, start, end):
                    affected.add(node_id)
        return sorted(affected, key=lambda node_id: self._order.get(node_id, 0))


def _intersects(node_start: int, node_end: int, change_start: int, change_end: int) -> bool:
    if change_start == change_end:
        # Insertion point: hits a node whose range contains the point.
        return node_start <= change_start < node_end
    return change_start < node_end and node_start < change_end
