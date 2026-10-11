from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass
class NeoMathDocument:
    source: str = ""
    title: str = "未命名推导"
    document_id: str = field(default_factory=lambda: str(uuid4()))
    format_version: int = 1
    breakpoints: list[int] = field(default_factory=list)
    recent_probe: dict[str, Any] | None = None
    collapsed_steps: list[int] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        self.updated_at = datetime.now(UTC).isoformat()
        data = asdict(self)
        data["formatVersion"] = data.pop("format_version")
        data["documentId"] = data.pop("document_id")
        data["recentProbe"] = data.pop("recent_probe")
        data["collapsedSteps"] = data.pop("collapsed_steps")
        data["updatedAt"] = data.pop("updated_at")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NeoMathDocument":
        return cls(
            source=str(data.get("source", "")),
            title=str(data.get("title", "未命名推导")),
            document_id=str(data.get("documentId", uuid4())),
            format_version=int(data.get("formatVersion", 1)),
            breakpoints=[int(value) for value in data.get("breakpoints", [])],
            recent_probe=data.get("recentProbe"),
            collapsed_steps=[int(value) for value in data.get("collapsedSteps", [])],
            updated_at=str(data.get("updatedAt", datetime.now(UTC).isoformat())),
        )
