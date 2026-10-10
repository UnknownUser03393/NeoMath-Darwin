from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Iterable, Iterator
from uuid import uuid4

from neomath.edlatex.layout import Layout
from neomath.edlatex.metadata import Metadata
from neomath.edlatex.nodes import DocumentNode

EDLATEX_FORMAT_VERSION = 2


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class EdDocument:
    """Structured edLatex document.

    Node *identity* and node *order* are stored separately: ``nodes`` maps a
    stable id to its node, and ``order`` is the sequence of ids. Inserting or
    removing a node never rewrites other nodes' ids.
    """

    document_id: str = field(default_factory=lambda: str(uuid4()))
    format_version: int = EDLATEX_FORMAT_VERSION
    metadata: Metadata = field(default_factory=Metadata)
    layout: Layout = field(default_factory=Layout)
    nodes: dict[str, DocumentNode] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    # --- node operations ----------------------------------------------
    def add_node(self, node: DocumentNode, index: int | None = None) -> DocumentNode:
        if node.id in self.nodes:
            raise ValueError(f"duplicate node id: {node.id}")
        self.nodes[node.id] = node
        if index is None or index >= len(self.order):
            self.order.append(node.id)
        else:
            self.order.insert(max(index, 0), node.id)
        self.touch()
        return node

    def remove_node(self, node_id: str) -> DocumentNode | None:
        node = self.nodes.pop(node_id, None)
        if node is not None and node_id in self.order:
            self.order.remove(node_id)
            # Detach any children so they don't dangle onto a dead parent.
            for child in self.nodes.values():
                if child.parent_id == node_id:
                    child.parent_id = None
            self.touch()
        return node

    def move_node(self, node_id: str, index: int) -> None:
        if node_id not in self.order:
            return
        self.order.remove(node_id)
        self.order.insert(max(0, min(index, len(self.order))), node_id)
        self.touch()

    def get_node(self, node_id: str) -> DocumentNode | None:
        return self.nodes.get(node_id)

    def iter_nodes(self) -> Iterator[DocumentNode]:
        for node_id in self.order:
            node = self.nodes.get(node_id)
            if node is not None:
                yield node

    def nodes_in_order(self) -> list[DocumentNode]:
        return list(self.iter_nodes())

    def children_of(self, parent_id: str | None) -> list[DocumentNode]:
        return [n for n in self.iter_nodes() if n.parent_id == parent_id]

    def touch(self) -> None:
        self.updated_at = _now()

    @property
    def title(self) -> str:
        return self.metadata.title

    # --- serialization -------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "documentId": self.document_id,
            "formatVersion": self.format_version,
            "metadata": self.metadata.to_dict(),
            "layout": self.layout.to_dict(),
            # order first so a human reading the JSON sees the document shape,
            # then the id-keyed node bodies.
            "order": list(self.order),
            "nodes": {nid: self.nodes[nid].to_dict() for nid in self.order if nid in self.nodes},
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EdDocument":
        from neomath.edlatex.nodes import node_from_dict

        doc = cls(
            document_id=str(data.get("documentId") or uuid4()),
            format_version=int(data.get("formatVersion", EDLATEX_FORMAT_VERSION)),
            metadata=Metadata.from_dict(data.get("metadata")),
            layout=Layout.from_dict(data.get("layout")),
            created_at=str(data.get("createdAt", _now())),
            updated_at=str(data.get("updatedAt", _now())),
        )
        raw_nodes = data.get("nodes", {}) or {}
        order = [str(x) for x in data.get("order", [])]
        # Rebuild nodes; tolerate an order list that references missing ids and
        # append any nodes present in the map but absent from order.
        for nid, node_data in raw_nodes.items():
            node = node_from_dict(node_data)
            node.id = str(nid)
            doc.nodes[node.id] = node
        doc.order = [nid for nid in order if nid in doc.nodes]
        for nid in raw_nodes:
            if nid not in doc.order:
                doc.order.append(str(nid))
        return doc


def new_document(
    title: str = "未命名文档", nodes: Iterable[DocumentNode] | None = None
) -> EdDocument:
    doc = EdDocument(metadata=Metadata(title=title))
    for node in nodes or []:
        doc.add_node(node)
    return doc
