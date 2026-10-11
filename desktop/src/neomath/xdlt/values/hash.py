"""Position-free hashes for semantic values.

The hash is derived from the parsed value, never the raw source text, so
``= 0.01`` and ``= 0.010`` hash identically while ``0.01`` and ``0.02`` do not.
"""

from __future__ import annotations

from neomath.xdlt.graph.hash import stable_hash
from neomath.xdlt.values.nodes import SemanticValue


def semantic_value_hash(value: SemanticValue | None) -> str:
    if value is None:
        return stable_hash({"value": None})
    return stable_hash({"value": value.to_dict()})
