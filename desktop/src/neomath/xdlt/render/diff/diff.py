"""Deterministic render tree diff.

Matching is keyed by ``renderId`` (semantic nodes keep their semanticId; the
content-fingerprint identity for anonymous nodes is stable across unrelated
insertions). The most important fast path: ``old.renderHash == new.renderHash``
skips the whole subtree.

Patch ordering is fixed: recursions for matched children (old document order),
then removals (old order), then insertions (new order).
"""

from __future__ import annotations

from typing import Any

from neomath.xdlt.render.diff.patches import (
    InsertNode,
    RemoveNode,
    RenderPatch,
    ReplaceDocument,
    ReplaceNode,
)
from neomath.xdlt.render.nodes import RenderDocument, RenderNode

_ATOMIC_KINDS = {
    "paragraph",
    "heading",
    "equation",
    "inline_math",
    "text",
    "reference",
    "citation",
    "code",
    "executable",
    "image",
    "figure",
    "table",
    "assertion",
    "diagnostic",
    "card_reference",
}


def diff_documents(
    old: RenderDocument, new: RenderDocument, stats: dict[str, int] | None = None
) -> list[RenderPatch]:
    """Diff two render documents; empty list when they are identical.

    A renderId mapping to multiple nodes with *different* content is a corrupt
    tree: matching would be ambiguous, so we fall back to a full replacement.
    Identical-content duplicates (e.g. two equal equations) are legal and are
    handled by occurrence pairing. ``stats`` (optional) records how many subtrees
    were actually examined (for subtree-skip profiling).
    """
    if stats is None:
        stats = {}
    stats["visited"] = 0
    if old.render_hash == new.render_hash:
        stats["visited"] = 1
        return []
    if _has_ambiguous_duplicates(old) or _has_ambiguous_duplicates(new):
        return [ReplaceDocument(new)]
    return _diff_children(old, new, is_root=True, stats=stats)


def _has_ambiguous_duplicates(document: RenderNode) -> bool:
    by_id: dict[str, str] = {}
    for node in _walk(document):
        previous = by_id.get(node.render_id)
        if previous is not None and previous != node.render_hash:
            return True
        by_id[node.render_id] = node.render_hash
    return False


def _walk(node: RenderNode) -> Any:
    yield node
    for child in node.children():
        yield from _walk(child)


def _diff_node(old: RenderNode, new: RenderNode, stats: dict[str, int]) -> list[RenderPatch]:
    stats["visited"] = stats.get("visited", 0) + 1
    if old.render_hash == new.render_hash:
        return []
    if old.kind in _ATOMIC_KINDS:
        return [ReplaceNode(old.render_id, new)]
    if old.render_id != new.render_id:
        return [ReplaceDocument(_as_document(new))]
    return _diff_children(old, new, is_root=False, stats=stats)


def _diff_children(
    old_parent: RenderNode,
    new_parent: RenderNode,
    is_root: bool,
    stats: dict[str, int],
) -> list[RenderPatch]:
    old_children = old_parent.child_nodes
    new_children = new_parent.child_nodes
    old_keys = _occurrence_keys(old_children)
    new_keys = _occurrence_keys(new_children)
    old_map = dict(zip(old_keys, old_children, strict=False))
    new_map = dict(zip(new_keys, new_children, strict=False))

    common = [key for key in old_keys if key in new_map]
    new_common = [key for key in new_keys if key in old_map]
    if common != new_common:
        # Reorder / ambiguous: replace this parent (never guess patch order).
        if is_root:
            return [ReplaceDocument(_as_document(new_parent))]
        return [ReplaceNode(old_parent.render_id, new_parent)]

    patches: list[RenderPatch] = []
    for key in common:
        patches.extend(_diff_node(old_map[key], new_map[key], stats))
    for node in old_children:
        if _key(node, old_children) not in new_map:
            patches.append(RemoveNode(node.render_id))
    common_before = 0
    for node in new_children:
        if _key(node, new_children) in old_map:
            common_before += 1
        else:
            patches.append(InsertNode(old_parent.render_id, common_before, node))
    return patches


def _key(node: RenderNode, siblings: list[RenderNode]) -> tuple[str, int]:
    occurrence = 0
    for sibling in siblings:
        if sibling is node:
            break
        if sibling.render_id == node.render_id:
            occurrence += 1
    return (node.render_id, occurrence)


def _occurrence_keys(nodes: list[RenderNode]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    result: list[tuple[str, int]] = []
    for node in nodes:
        occurrence = counts.get(node.render_id, 0)
        counts[node.render_id] = occurrence + 1
        result.append((node.render_id, occurrence))
    return result


def _as_document(node: RenderNode) -> RenderDocument:
    if isinstance(node, RenderDocument):
        return node
    document = RenderDocument()
    document.child_nodes = list(node.child_nodes)
    return document
