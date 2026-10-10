from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neomath.edlatex.document import EdDocument


@dataclass
class RenderDiagnostic:
    """A non-fatal issue raised while rendering (e.g. an unsupported node)."""

    severity: str  # info | warning | error
    code: str
    message: str
    node_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "nodeId": self.node_id,
        }


@dataclass
class RenderResult:
    format: str
    content: str
    diagnostics: list[RenderDiagnostic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "content": self.content,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }


class DocumentRenderer:
    """Base renderer. All renderers consume the SAME EdDocument model so there
    is a single source of truth for content; only presentation differs."""

    format = "abstract"

    def render(self, document: EdDocument) -> RenderResult:  # pragma: no cover - abstract
        raise NotImplementedError


def resolve_header_footer(document: EdDocument, value: str) -> str:
    """Resolve @meta.* references used in layout header/footer strings."""
    if value.startswith("@meta."):
        resolved = document.metadata.resolve(value)
        return "" if resolved is None else str(resolved)
    return value
