"""Deterministic Render IR diffing and patches.

Patches are backend-neutral (never DOM-shaped). ``apply_patches`` is the
reference applier; the invariant ``apply(old, diff(old, new)) == new`` is tested.
"""

from __future__ import annotations

from neomath.xdlt.render.diff.diff import diff_documents
from neomath.xdlt.render.diff.index import RenderIndex
from neomath.xdlt.render.diff.patches import (
    InsertNode,
    RemoveNode,
    RenderPatch,
    ReplaceDocument,
    ReplaceNode,
    apply_patches,
    serialize_patches,
)

__all__ = [
    "InsertNode",
    "RemoveNode",
    "RenderIndex",
    "RenderPatch",
    "ReplaceDocument",
    "ReplaceNode",
    "apply_patches",
    "diff_documents",
    "serialize_patches",
]
