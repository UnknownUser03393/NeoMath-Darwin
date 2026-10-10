"""Stable semantic-input hashes for assertion verification.

A hash is derived from meaning-relevant inputs only: the normalized claim and
requirement IR, the referenced equation/entity IR, the active symbol
declarations, and the verifier identity. Formatting/whitespace never changes the
hash, so future caching can skip re-verification when nothing semantic changed.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def assertion_semantic_hash(
    claim: dict[str, Any] | None,
    requirements: list[dict[str, Any]],
    referenced_entities: dict[str, dict[str, Any]],
    symbol_declarations: dict[str, dict[str, Any]],
    verifier_name: str,
    verifier_version: str,
) -> str:
    payload = {
        "claim": claim,
        "requirements": requirements,
        "entities": referenced_entities,
        "symbols": symbol_declarations,
        "verifier": verifier_name,
        "verifierVersion": verifier_version,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
