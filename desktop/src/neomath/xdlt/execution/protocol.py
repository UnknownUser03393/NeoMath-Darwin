"""Backend-neutral execution protocol.

The engine depends only on this interface. Concrete runners (``PythonRunner``)
implement it; the runner never receives the whole AST, only a structured
request. Execution is *trusted local execution*: no sandbox is claimed.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from neomath.xdlt.execution.result import ExecutionResult


class ExecutionRequest:
    """Everything a runner needs to run one block, with no AST attached."""

    __slots__ = (
        "exec_id",
        "language",
        "source",
        "file",
        "working_directory",
        "inputs",
        "dependency_hashes",
        "environment",
        "timeout",
    )

    def __init__(
        self,
        exec_id: str,
        language: str,
        source: str,
        file: str | None = None,
        working_directory: str | None = None,
        inputs: dict[str, Any] | None = None,
        dependency_hashes: dict[str, str] | None = None,
        environment: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> None:
        self.exec_id = exec_id
        self.language = language
        self.source = source
        self.file = file
        self.working_directory = working_directory
        self.inputs = inputs or {}
        self.dependency_hashes = dependency_hashes or {}
        self.environment = environment or {}
        self.timeout = timeout


@runtime_checkable
class ExecutionRunner(Protocol):
    language: str

    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...
