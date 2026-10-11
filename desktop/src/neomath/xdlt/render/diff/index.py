"""Render tree index: renderId -> node, with duplicate detection.

Used by the patch applier and by diagnostics. Duplicate renderIds indicate an
illegal render tree; the diff falls back to a full document replacement.
"""

from __future__ import annotations

from neomath.xdlt.render.nodes import RenderDocument, RenderNode


class RenderIndex:
    def __init__(self, document: RenderDocument) -> None:
        self.nodes: dict[str, RenderNode] = {}
        self.duplicates: list[str] = []
        self._walk(document)

    def _walk(self, node: RenderNode) -> None:
        if node.render_id in self.nodes:
            self.duplicates.append(node.render_id)
        self.nodes[node.render_id] = node
        for child in node.children():
            self._walk(child)

    def find(self, render_id: str) -> RenderNode | None:
        return self.nodes.get(render_id)

    def is_valid(self) -> bool:
        return not self.duplicates
