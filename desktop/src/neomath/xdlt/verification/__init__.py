"""Assertion verification: backend-neutral protocol + SymPy adapter."""

from __future__ import annotations

from typing import Any

from neomath.xdlt.verification.errors import (
    CannotDecideError,
    InvalidReferenceTypeError,
    UnresolvedReferenceError,
    UnsupportedOperationError,
    UnsupportedRequirementError,
    VerificationError,
)
from neomath.xdlt.verification.hash import assertion_semantic_hash
from neomath.xdlt.verification.protocol import (
    VERIFICATION_STATUSES,
    AssertionVerifier,
    VerificationContext,
    VerificationResult,
)
from neomath.xdlt.verification.sympy_verifier import SymPyVerifier

_VERIFIERS: dict[str, AssertionVerifier] = {"sympy": SymPyVerifier()}


def get_verifier(name: str) -> AssertionVerifier | None:
    return _VERIFIERS.get(name)


def available_verifiers() -> list[str]:
    return sorted(_VERIFIERS)


def verify_assertion(
    assertion: dict[str, Any],
    entity_registry: dict[str, dict[str, Any]],
) -> VerificationResult:
    """Run the configured verifier for one lowered assertion entity."""
    verifier_name = str(assertion.get("verifier") or "sympy")
    verifier = get_verifier(verifier_name)
    symbol_declarations = assertion.get("symbols", {})
    context = VerificationContext(
        symbol_declarations=symbol_declarations,
        referenced_entities=entity_registry,
        assertion_id=assertion.get("id"),
    )
    if verifier is None:
        result = VerificationResult(
            status="error",
            verifier=verifier_name,
            message=f"verifier '{verifier_name}' is unavailable",
            diagnostics=[
                {
                    "severity": "error",
                    "code": "VERIFY_BACKEND_UNAVAILABLE",
                    "message": f"verifier '{verifier_name}' is unavailable",
                }
            ],
            assertion_id=assertion.get("id"),
        )
        return result

    claim = assertion.get("claim")
    requirements = assertion.get("requirements", [])
    result = verifier.verify(claim, requirements, context)
    referenced = _referenced_entity_ir(claim, requirements, entity_registry)
    result.semantic_hash = assertion_semantic_hash(
        claim=claim,
        requirements=requirements,
        referenced_entities=referenced,
        symbol_declarations=symbol_declarations,
        verifier_name=verifier.name,
        verifier_version=getattr(verifier, "version", "unknown"),
    )
    return result


def verify_document_assertions(
    semantic_ir: dict[str, Any],
    assertion_id: str | None = None,
) -> list[VerificationResult]:
    """Verify every assertion in a lowered document (optionally one by id)."""
    registry = semantic_ir.get("entities", {})
    results: list[VerificationResult] = []
    for child in semantic_ir.get("children", []):
        if child.get("type") != "Assertion":
            continue
        if assertion_id is not None and child.get("id") != assertion_id:
            continue
        results.append(verify_assertion(child, registry))
    return results


def _referenced_entity_ir(
    claim: dict[str, Any] | None,
    requirements: list[dict[str, Any]],
    entity_registry: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    ids: list[str] = []
    if claim is not None:
        ids.extend(_collect_reference_ids(claim))
    for requirement in requirements:
        ids.extend(_collect_reference_ids(requirement))
    return {
        target_id: entity_registry[target_id]
        for target_id in dict.fromkeys(ids)
        if target_id in entity_registry
    }


def _collect_reference_ids(ir: dict[str, Any], result: list[str] | None = None) -> list[str]:
    result = [] if result is None else result
    if ir.get("kind") == "semantic_reference" and ir.get("targetId"):
        result.append(ir["targetId"])
    for value in ir.values():
        if isinstance(value, dict):
            _collect_reference_ids(value, result)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _collect_reference_ids(item, result)
    return result


__all__ = [
    "AssertionVerifier",
    "VerificationContext",
    "VerificationResult",
    "VERIFICATION_STATUSES",
    "VerificationError",
    "CannotDecideError",
    "UnresolvedReferenceError",
    "InvalidReferenceTypeError",
    "UnsupportedOperationError",
    "UnsupportedRequirementError",
    "get_verifier",
    "available_verifiers",
    "verify_assertion",
    "verify_document_assertions",
    "assertion_semantic_hash",
]
