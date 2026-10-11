"""Backend-neutral Render IR patches.

A patch describes a change to the Render IR tree, never to the DOM. HTML (and
anything DOM-shaped) appears only in the HTML lowering layer. ``apply_patches``
is the reference applier used to verify the invariant

    apply(oldRenderDocument, patches) == newRenderDocument
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from neomath.xdlt.render.nodes import RenderDocument, RenderNode


@dataclass(frozen=True)
class ReplaceNode:
    render_id: str
    node: RenderNode


@dataclass(frozen=True)
class RemoveNode:
    render_id: str


@dataclass(frozen=True)
class InsertNode:
    parent_render_id: str
    index: int
    node: RenderNode


@dataclass(frozen=True)
class ReplaceDocument:
    document: RenderDocument


RenderPatch = ReplaceNode | RemoveNode | InsertNode | ReplaceDocument


def apply_patches(document: RenderDocument, patches: list[RenderPatch]) -> RenderDocument:
    result = copy.deepcopy(document)
    for patch in patches:
        if isinstance(patch, ReplaceDocument):
            return copy.deepcopy(patch.document)
    for patch in patches:
        if isinstance(patch, ReplaceNode):
            _replace_node(result, patch.render_id, patch.node)
        elif isinstance(patch, RemoveNode):
            _remove_node(result, patch.render_id)
    # Insertions last, grouped per parent; ``index`` is the count of surviving
    # (common) children preceding the node, so a per-parent running count keeps
    # adjacent insertions in the right order.
    inserted: dict[str, int] = {}
    for patch in patches:
        if isinstance(patch, InsertNode):
            parent = _find_node(result, patch.parent_render_id)
            if parent is None:
                continue
            offset = inserted.get(patch.parent_render_id, 0)
            parent.child_nodes.insert(patch.index + offset, copy.deepcopy(patch.node))
            inserted[patch.parent_render_id] = offset + 1
    return result


def _find_node(root: RenderNode, render_id: str) -> RenderNode | None:
    if root.render_id == render_id:
        return root
    for child in root.children():
        found = _find_node(child, render_id)
        if found is not None:
            return found
    return None


def _replace_node(root: RenderNode, render_id: str, new_node: RenderNode) -> bool:
    for index, child in enumerate(root.children()):
        if child.render_id == render_id:
            root.child_nodes[index] = copy.deepcopy(new_node)
            return True
        if _replace_node(child, render_id, new_node):
            return True
    return False


def _remove_node(root: RenderNode, render_id: str) -> bool:
    for index, child in enumerate(root.children()):
        if child.render_id == render_id:
            del root.child_nodes[index]
            return True
        if _remove_node(child, render_id):
            return True
    return False


def serialize_patches(patches: list[RenderPatch]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for patch in patches:
        if isinstance(patch, ReplaceNode):
            result.append({"op": "replace", "renderId": patch.render_id})
        elif isinstance(patch, RemoveNode):
            result.append({"op": "remove", "renderId": patch.render_id})
        elif isinstance(patch, InsertNode):
            result.append(
                {
                    "op": "insert",
                    "parentRenderId": patch.parent_render_id,
                    "index": patch.index,
                }
            )
        elif isinstance(patch, ReplaceDocument):
            result.append({"op": "replace-document"})
    return result
