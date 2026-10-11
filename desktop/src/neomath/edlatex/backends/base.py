from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from threading import Event
from typing import Any

# The shared four+ verification states (kept aligned with node.VERIFICATION_STATES).
STATUS_UNVERIFIED = "unverified"
STATUS_VALID = "valid"
STATUS_VALID_WITH_CONDITIONS = "valid-with-conditions"
STATUS_WARNING = "warning"
STATUS_INVALID = "invalid"
STATUS_UNKNOWN = "unknown"


@dataclass
class StepClaim:
    """A single derivation step to verify: from_expr --rule--> to_expr."""

    from_expr: str
    to_expr: str
    rule: str
    node_id: str | None = None
    assumptions: list[str] = field(default_factory=list)

    @classmethod
    def from_node(cls, node: Any) -> "StepClaim":
        return cls(
            from_expr=getattr(node, "from_expr", ""),
            to_expr=getattr(node, "to_expr", ""),
            rule=getattr(node, "rule", ""),
            node_id=getattr(node, "id", None),
            assumptions=[str(x) for x in getattr(node, "assumptions", []) or []],
        )


@dataclass
class VerificationResult:
    status: str
    rule: str
    backend: str
    method: str = ""
    message: str = ""
    required_conditions: list[str] = field(default_factory=list)
    possible_lost_solutions: list[str] = field(default_factory=list)
    possible_added_solutions: list[str] = field(default_factory=list)
    node_id: str | None = None
    timed_out: bool = False
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "rule": self.rule,
            "backend": self.backend,
            "method": self.method,
            "message": self.message,
            "requiredConditions": list(self.required_conditions),
            "possibleLostSolutions": list(self.possible_lost_solutions),
            "possibleAddedSolutions": list(self.possible_added_solutions),
            "nodeId": self.node_id,
            "timedOut": self.timed_out,
            "detail": dict(self.detail),
        }


@dataclass
class BackendContext:
    """Facts a backend may use during validation (e.g. from the context system)."""

    nonzero_symbols: set[str] = field(default_factory=set)
    nonnegative_symbols: set[str] = field(default_factory=set)
    symbol_domains: dict[str, str] = field(default_factory=dict)


class MathBackend(ABC):
    """Abstract compute/proof backend.

    Concrete backends declare capabilities and availability honestly: an
    unavailable backend never fabricates a result.
    """

    name = "abstract"

    @abstractmethod
    def capabilities(self) -> dict[str, Any]:
        """Return {'rules': [...], 'features': [...]}."""

    @abstractmethod
    def availability(self) -> tuple[bool, str]:
        """Return (available, reason). reason is empty when available."""

    @abstractmethod
    def validate(
        self,
        claim: StepClaim,
        context: BackendContext | None = None,
        timeout: float = 5.0,
        cancel: Event | None = None,
    ) -> VerificationResult:
        """Verify a single step, respecting timeout and cooperative cancellation."""

    def _unavailable_result(self, claim: StepClaim) -> VerificationResult:
        available, reason = self.availability()
        return VerificationResult(
            status=STATUS_UNKNOWN,
            rule=claim.rule,
            backend=self.name,
            message=f"Unavailable: {reason}",
            node_id=claim.node_id,
        )
