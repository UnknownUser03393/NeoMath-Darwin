"""Backend-neutral assertion verification protocol.

The core verification logic depends only on this interface, never on SymPy.
Concrete backends (``SymPyVerifier``) implement the protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

VERIFICATION_STATUSES = {
    "unverified",
    "valid",
    "valid-with-conditions",
    "invalid",
    "unknown",
    "error",
}


@dataclass
class VerificationResult:
    status: str = "unverified"
    verifier: str = ""
    message: str = ""
    conditions: list[str] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    assertion_id: str | None = None
    semantic_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "verifier": self.verifier,
            "message": self.message,
            "conditions": list(self.conditions),
            "diagnostics": list(self.diagnostics),
            "evidence": dict(self.evidence),
            "assertionId": self.assertion_id,
            "semanticHash": self.semantic_hash,
        }


@dataclass
class VerificationContext:
    """Everything a verifier needs about the enclosing document for one assertion."""

    symbol_declarations: dict[str, dict[str, Any]] = field(default_factory=dict)
    referenced_entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    assertion_id: str | None = None


@runtime_checkable
class AssertionVerifier(Protocol):
    name: str

    def verify(
        self,
        claim: dict[str, Any] | None,
        requirements: list[dict[str, Any]],
        context: VerificationContext,
    ) -> VerificationResult: ...
