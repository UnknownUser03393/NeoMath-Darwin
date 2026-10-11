"""Structured execution results and rich output values.

Outputs are typed, never flattened to strings: text, JSON, image, math and
table each carry their own payload. ``outputs[0]`` corresponds to the selector
``#exec:foo[0]`` -> ``result:exec.foo/0``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

EXECUTION_STATUSES = {"success", "failed", "timeout", "cancelled", "unavailable"}


class Output:
    kind = "output"

    def __init__(self, kind: str) -> None:
        self.kind = kind

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind}


class TextOutput(Output):
    def __init__(self, text: str) -> None:
        super().__init__("text")
        self.text = text

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["text"] = self.text
        return data


class JsonOutput(Output):
    def __init__(self, value: Any) -> None:
        super().__init__("json")
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["value"] = self.value
        return data


class ImageOutput(Output):
    def __init__(self, data_base64: str, mime: str = "image/png", name: str | None = None) -> None:
        super().__init__("image")
        self.data_base64 = data_base64
        self.mime = mime
        self.name = name

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["mime"] = self.mime
        data["name"] = self.name
        data["dataBase64"] = self.data_base64
        return data


class MathOutput(Output):
    def __init__(self, expression: str, format: str = "latex") -> None:
        super().__init__("math")
        self.expression = expression
        self.format = format

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["expression"] = self.expression
        data["format"] = self.format
        return data


class TableOutput(Output):
    def __init__(self, headers: list[str], rows: list[list[Any]]) -> None:
        super().__init__("table")
        self.headers = headers
        self.rows = rows

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["headers"] = list(self.headers)
        data["rows"] = [[cell for cell in row] for row in self.rows]
        return data


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class ExecutionResult:
    exec_id: str = ""
    run_id: str = field(default_factory=new_run_id)
    status: str = "unavailable"
    stdout: str = ""
    stderr: str = ""
    outputs: list[Output] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration: float = 0.0
    input_hash: str = ""
    environment_hash: str = ""
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    cached: bool = False
    message: str = ""
    runner_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "execId": self.exec_id,
            "runId": self.run_id,
            "status": self.status,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "outputs": [output.to_dict() for output in self.outputs],
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "duration": round(self.duration, 4),
            "inputHash": self.input_hash,
            "environmentHash": self.environment_hash,
            "diagnostics": list(self.diagnostics),
            "cached": self.cached,
            "message": self.message,
            "runnerVersion": self.runner_version,
        }
