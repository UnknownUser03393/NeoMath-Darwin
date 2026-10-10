from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neomath.edlatex.backends.base import MathBackend
from neomath.edlatex.backends.sympy_backend import SymPyBackend


@dataclass
class BackendRegistry:
    """In-memory backend registry.

    This stays lightweight: availability is queried honestly from each backend,
    and no backend pretends to work when its executable / library is missing.
    """

    _backends: dict[str, MathBackend] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self._backends:
            self.register(SymPyBackend())

    def register(self, backend: MathBackend) -> None:
        self._backends[backend.name] = backend

    def names(self) -> list[str]:
        return sorted(self._backends)

    def get(self, name: str) -> MathBackend | None:
        return self._backends.get(name)

    def capabilities(self) -> dict[str, dict[str, Any]]:
        return {name: backend.capabilities() for name, backend in self._backends.items()}

    def availability(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for name, backend in self._backends.items():
            available, reason = backend.availability()
            out[name] = {"available": available, "reason": reason}
        return out


_DEFAULT_REGISTRY: BackendRegistry | None = None


def default_registry() -> BackendRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = BackendRegistry()
    return _DEFAULT_REGISTRY
