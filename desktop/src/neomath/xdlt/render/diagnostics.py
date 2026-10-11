"""Render-phase diagnostics.

Parse / semantic / render diagnostics are separate stages: render problems must
never mutate the semantic IR.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RenderDiagnostic:
    severity: str
    code: str
    message: str
    render_id: str | None = None
    source_range: dict[str, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "renderId": self.render_id,
            "sourceRange": self.source_range,
        }
