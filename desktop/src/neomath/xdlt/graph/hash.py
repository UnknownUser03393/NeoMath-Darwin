"""Position-free semantic hashes for graph nodes.

A node's hash depends only on meaning: normalized IR (math IR is already
normalized by ``math.lower``), resolved symbol identities, referenced-entity IR
and the verifier identity. Source ranges, formatting and whitespace never enter
the hash, so ``x+1`` and ``x + 1`` hash identically while ``x+2`` does not.
"""

from __future__ import annotations

from typing import Any

from neomath.xdlt.verification import get_verifier
from neomath.xdlt.verification.hash import assertion_semantic_hash


def stable_hash(payload: Any) -> str:
    import hashlib
    import json

    def default(value: Any) -> Any:
        if isinstance(value, set):
            return sorted(value, key=str)
        return str(value)

    encoded = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=default
    )
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# --- per-node-kind hashes -------------------------------------------------


def symbol_node_hash(declaration: dict[str, Any]) -> str:
    """Hash of a symbol declaration, excluding source position (line).

    The effective runtime value participates, so ``alpha = 0.01`` vs ``0.02``
    changes the hash (and dirties dependents) while whitespace-only edits do not.
    """
    return stable_hash(
        {
            "symbol": {
                "name": declaration.get("name"),
                "symbolId": declaration.get("symbolId"),
                "type": declaration.get("type"),
                "properties": sorted(declaration.get("properties") or []),
                "value": declaration.get("value"),
            }
        }
    )


def math_entity_hash(math_ir: dict[str, Any] | None) -> str:
    return stable_hash({"math": math_ir or {}})


def context_hash(entity: dict[str, Any]) -> str:
    declarations = []
    for declaration in entity.get("declarations", []):
        names = declaration.get("names", [])
        type_name = declaration.get("type", {}).get("name")
        properties = sorted(p.get("name") for p in declaration.get("properties", []))
        for name in names:
            declarations.append(
                {"name": name, "type": type_name, "properties": sorted(properties)}
            )
    return stable_hash({"context": declarations})


def executable_hash(entity: dict[str, Any], dependency_hashes: dict[str, str]) -> str:
    """Hash of an executable: source + runtime identity + declared inputs +
    the hashes of every input symbol it depends on."""
    payload = {
        "executable": {
            "source": entity.get("source"),
            "language": entity.get("language"),
            "kernel": entity.get("kernel"),
            "file": entity.get("file"),
            "timeout": entity.get("timeout"),
            "inputs": [inp.get("name") for inp in entity.get("inputs", [])],
            "dependencyHashes": dependency_hashes,
        }
    }
    return stable_hash(payload)


def figure_hash(entity: dict[str, Any], source: dict[str, Any] | None) -> str:
    return stable_hash({"figure": {"source": source or {}, "body": entity.get("body")}})


def assertion_hash(
    entity: dict[str, Any],
    registry: dict[str, dict[str, Any]],
    value_resolver: Any = None,
) -> str:
    """Reuse the verification semantic hash so graph hashes agree with
    ``VerificationResult.semantic_hash`` and verification can be reused when
    the referenced equation did not change. ``value_resolver(name)`` supplies
    effective (post-override) value dicts for the visible symbols."""
    claim = entity.get("claim")
    requirements = entity.get("requirements") or []
    referenced = referenced_entity_ir(claim, requirements, registry)
    # Only symbols actually referenced by the claim/requirements participate, so
    # changing an unrelated symbol's value does not invalidate this assertion.
    used_names = set(collect_sel_symbol_names(claim))
    for requirement in requirements:
        used_names.update(collect_sel_symbol_names(requirement))
    symbols: dict[str, dict[str, Any]] = {}
    for name, declaration in (entity.get("symbols") or {}).items():
        if name not in used_names:
            continue
        entry = {key: value for key, value in declaration.items() if key != "line"}
        if value_resolver is not None:
            effective = value_resolver(str(name))
            if effective is not None:
                entry["value"] = effective
        symbols[name] = entry
    verifier_name = entity.get("verifier") or "sympy"
    verifier = get_verifier(str(verifier_name))
    verifier_version = getattr(verifier, "version", "unknown") if verifier else "unknown"
    return assertion_semantic_hash(
        claim=claim,
        requirements=requirements,
        referenced_entities=referenced,
        symbol_declarations=symbols,
        verifier_name=str(verifier_name),
        verifier_version=str(verifier_version),
    )


def referenced_entity_ir(
    claim: dict[str, Any] | None,
    requirements: list[dict[str, Any]],
    registry: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    ids: list[str] = []
    if claim is not None:
        ids.extend(collect_reference_ids(claim))
    for requirement in requirements:
        ids.extend(collect_reference_ids(requirement))
    return {
        target_id: registry[target_id]
        for target_id in dict.fromkeys(ids)
        if target_id in registry
    }


# --- IR walkers ------------------------------------------------------------


def collect_reference_ids(ir: Any, result: list[str] | None = None) -> list[str]:
    result = [] if result is None else result
    if isinstance(ir, dict):
        if ir.get("kind") == "semantic_reference" and ir.get("targetId"):
            result.append(ir["targetId"])
        for value in ir.values():
            collect_reference_ids(value, result)
    elif isinstance(ir, list):
        for item in ir:
            collect_reference_ids(item, result)
    return result


def collect_sel_symbol_names(ir: Any, result: list[str] | None = None) -> list[str]:
    result = [] if result is None else result
    if isinstance(ir, dict):
        if ir.get("kind") == "symbol" and ir.get("name"):
            result.append(ir["name"])
        for value in ir.values():
            collect_sel_symbol_names(value, result)
    elif isinstance(ir, list):
        for item in ir:
            collect_sel_symbol_names(item, result)
    return result


def collect_symbol_ids(ir: Any, result: list[str] | None = None) -> list[str]:
    result = [] if result is None else result
    if isinstance(ir, dict):
        if ir.get("kind") == "symbol" and ir.get("symbolId"):
            result.append(ir["symbolId"])
        for value in ir.values():
            collect_symbol_ids(value, result)
    elif isinstance(ir, list):
        for item in ir:
            collect_symbol_ids(item, result)
    return result
