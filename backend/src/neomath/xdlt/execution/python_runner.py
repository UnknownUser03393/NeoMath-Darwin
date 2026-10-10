"""Isolated Python execution runner.

Runs each executable block in a *child process* so that ``sys.exit()``,
infinite loops and interpreter corruption cannot take down NeoMath. This is
``trusted-local`` execution, not a security sandbox. Inputs are injected as an
explicit environment (never by string-substituting the source), and structured
outputs are collected through a minimal ``xdlt_runtime`` API.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Any

from neomath.xdlt.execution.protocol import ExecutionRequest
from neomath.xdlt.execution.result import (
    ExecutionResult,
    ImageOutput,
    JsonOutput,
    MathOutput,
    TableOutput,
    TextOutput,
)
from neomath.xdlt.execution.values import encode_input_value

_VERSION = "1.0"

_WORKER = r'''
import json, sys, types, io, base64, traceback, time

job_path, result_path = sys.argv[1], sys.argv[2]
with open(job_path, encoding="utf-8") as _f:
    job = json.load(_f)

def _decode(value):
    if isinstance(value, dict) and value.get("__xdlt__") == "sympy_symbol":
        import sympy as _sp
        assumptions = {k: bool(v) for k, v in value.get("assumptions", {}).items()}
        return _sp.Symbol(value["name"], **assumptions)
    if isinstance(value, dict) and value.get("__xdlt__") == "sympy_expr":
        import sympy as _sp
        return _sp.sympify(value["repr"])
    return value

inputs = {k: _decode(v) for k, v in job.get("inputs", {}).items()}
outputs = []

class _Output:
    def text(self, value):
        outputs.append({"kind": "text", "text": str(value)})
    def json(self, value):
        outputs.append({"kind": "json", "value": value})
    def math(self, value, format="latex"):
        outputs.append({"kind": "math", "expression": str(value), "format": str(format)})
    def image(self, value, mime="image/png", name=None):
        if hasattr(value, "savefig"):
            import io as _io
            _buf = _io.BytesIO()
            value.savefig(_buf, format="png")
            data = _buf.getvalue()
        elif isinstance(value, bytes):
            data = value
        else:
            data = str(value).encode()
        outputs.append({"kind": "image", "mime": mime, "name": name,
                        "dataBase64": base64.b64encode(data).decode()})
    def table(self, value, headers=None):
        rows = [[str(cell) for cell in row] for row in value]
        outputs.append({"kind": "table", "headers": list(headers or []), "rows": rows})

sys.modules["xdlt_runtime"] = types.SimpleNamespace(output=_Output())

def _json_default(obj):
    import sympy as _sp
    if isinstance(obj, _sp.Basic):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return sorted(obj, key=str)
    return str(obj)

stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
status, error, duration = "success", None, 0.0
_start = time.time()
try:
    sys.stdout, sys.stderr = stdout_buf, stderr_buf
    env = dict(globals())
    env.update(inputs)
    exec(compile(job.get("source", ""), job.get("file") or "<xdlt-exec>", "exec"), env)
except Exception as _exc:  # noqa: BLE001 - report any runtime failure
    status = "failed"
    error = "".join(traceback.format_exception(type(_exc), _exc, _exc.__traceback__))
finally:
    sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
    duration = time.time() - _start

with open(result_path, "w", encoding="utf-8") as _f:
    json.dump({
        "status": status,
        "stdout": stdout_buf.getvalue(),
        "stderr": stderr_buf.getvalue(),
        "outputs": outputs,
        "error": error,
        "duration": duration,
    }, _f, ensure_ascii=False, default=_json_default)
'''


class PythonRunner:
    language = "python"
    version = _VERSION

    def __init__(self, timeout: float = 15.0, python: str | None = None) -> None:
        self.timeout = timeout
        self.python = python or sys.executable

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        started_at = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()
        timeout = request.timeout if request.timeout else self.timeout
        encoded_inputs = {name: encode_input_value(value) for name, value in request.inputs.items()}

        with tempfile.TemporaryDirectory(prefix="xdlt-run-") as tmp:
            job_path = os.path.join(tmp, "job.json")
            result_path = os.path.join(tmp, "result.json")
            with open(job_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {"source": request.source, "file": request.file, "inputs": encoded_inputs},
                    handle,
                    ensure_ascii=False,
                )
            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "utf-8"
            command = [self.python, "-c", _WORKER, job_path, result_path]
            stdout_data = b""
            stderr_data = b""
            timed_out = False
            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=request.working_directory or None,
                    env=env,
                )
                try:
                    stdout_data, stderr_data = process.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    process.kill()
                    stdout_data, stderr_data = process.communicate()
            except FileNotFoundError:
                return self._result(
                    request,
                    started_at,
                    0.0,
                    status="unavailable",
                    message=f"python interpreter not found: {self.python}",
                )

            duration = time.monotonic() - start
            if timed_out:
                return self._result(
                    request,
                    started_at,
                    duration,
                    status="timeout",
                    stdout=stdout_data.decode(errors="replace"),
                    stderr=stderr_data.decode(errors="replace"),
                    message=f"timed out after {timeout:g}s",
                )
            if not os.path.exists(result_path):
                return self._result(
                    request,
                    started_at,
                    duration,
                    status="failed",
                    stdout=stdout_data.decode(errors="replace"),
                    stderr=stderr_data.decode(errors="replace"),
                    message="worker exited without producing a result (sys.exit / os._exit?)",
                )
            try:
                with open(result_path, encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, ValueError):
                return self._result(
                    request, started_at, duration, status="failed", message="result unreadable"
                )
            return self._result(
                request,
                started_at,
                float(data.get("duration", duration)),
                status=str(data.get("status", "failed")),
                stdout=str(data.get("stdout", "")),
                stderr=str(data.get("stderr", "")),
                outputs=_outputs_from_dicts(data.get("outputs", [])),
                message=str(data.get("error") or ""),
            )

    @staticmethod
    def _result(
        request: ExecutionRequest,
        started_at: str,
        duration: float,
        status: str,
        stdout: str = "",
        stderr: str = "",
        outputs: list[Any] | None = None,
        message: str = "",
    ) -> ExecutionResult:
        finished_at = datetime.now(timezone.utc).isoformat()
        return ExecutionResult(
            exec_id=request.exec_id,
            status=status,
            stdout=stdout,
            stderr=stderr,
            outputs=outputs or [],
            started_at=started_at,
            finished_at=finished_at,
            duration=duration,
            message=message,
            runner_version=_VERSION,
        )


def _outputs_from_dicts(entries: list[dict[str, Any]]) -> list[Any]:
    outputs: list[Any] = []
    for entry in entries:
        kind = entry.get("kind")
        if kind == "text":
            outputs.append(TextOutput(str(entry.get("text", ""))))
        elif kind == "json":
            outputs.append(JsonOutput(entry.get("value")))
        elif kind == "math":
            expression = str(entry.get("expression", ""))
            outputs.append(MathOutput(expression, str(entry.get("format", "latex"))))
        elif kind == "image":
            outputs.append(
                ImageOutput(
                    str(entry.get("dataBase64", "")),
                    mime=str(entry.get("mime", "image/png")),
                    name=entry.get("name"),
                )
            )
        elif kind == "table":
            outputs.append(
                TableOutput(
                    [str(item) for item in entry.get("headers", [])],
                    [[str(cell) for cell in row] for row in entry.get("rows", [])],
                )
            )
    return outputs
