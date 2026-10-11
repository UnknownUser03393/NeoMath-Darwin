from __future__ import annotations

from uuid import uuid4

# Short type prefixes keep ids human-readable in JSON and content.edl while
# staying globally unique. An id is assigned once at node creation and is never
# regenerated when siblings are inserted or removed (identity != order).
TYPE_PREFIXES = {
    "document": "doc",
    "section": "sec",
    "paragraph": "par",
    "formula": "fml",
    "derivation": "der",
    "assertion": "asr",
    "code": "cod",
    "context": "ctx",
    "asset": "ast",
}


def new_id(node_type: str) -> str:
    """Return a fresh stable id for a node of ``node_type``."""
    prefix = TYPE_PREFIXES.get(node_type, node_type[:3] or "nod")
    return f"{prefix}-{uuid4().hex[:8]}"
