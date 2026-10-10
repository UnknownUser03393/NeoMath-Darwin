"""Sidecar result cache on disk.

Layout::

    .xdlt-cache/
    └── results/
        └── exec-plot/
            └── <semantic-hash>/
                ├── manifest.json
                ├── stdout.txt
                ├── stderr.txt
                └── output-0.*
        └── assertions/
            └── assert-test/
                └── <semantic-hash>/
                    └── result.json

Generated results are never written back into the ``.hw`` document. A cache hit
requires the semantic hash, environment hash and runner version to all match.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from neomath.xdlt.execution.result import (
    ExecutionResult,
    ImageOutput,
    JsonOutput,
    MathOutput,
    Output,
    TableOutput,
    TextOutput,
)


def _slug(value: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in value)


class ResultCache:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _result_dir(self, exec_id: str, semantic_hash: str) -> Path:
        return self.root / "results" / _slug(exec_id) / _slug(semantic_hash)

    def _assertion_dir(self, assertion_id: str, semantic_hash: str) -> Path:
        return self.root / "assertions" / _slug(assertion_id) / _slug(semantic_hash)

    # --- execution results ------------------------------------------------
    def load(
        self,
        exec_id: str,
        semantic_hash: str,
        environment_hash: str,
        runner_version: str,
    ) -> ExecutionResult | None:
        directory = self._result_dir(exec_id, semantic_hash)
        manifest_path = directory / "manifest.json"
        if not manifest_path.exists():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if manifest.get("semanticHash") != semantic_hash:
            return None
        if manifest.get("environmentHash") != environment_hash:
            return None
        if manifest.get("runnerVersion") != runner_version:
            return None
        return ExecutionResult(
            exec_id=exec_id,
            status=manifest.get("status", "unavailable"),
            stdout=_read_text(directory / "stdout.txt"),
            stderr=_read_text(directory / "stderr.txt"),
            outputs=_load_outputs(manifest, directory),
            input_hash=semantic_hash,
            environment_hash=environment_hash,
            runner_version=runner_version,
            message=manifest.get("message", ""),
        )

    def store(
        self,
        result: ExecutionResult,
        semantic_hash: str,
        environment_hash: str,
        runner_version: str,
    ) -> None:
        directory = self._result_dir(result.exec_id, semantic_hash)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "stdout.txt").write_text(result.stdout or "", encoding="utf-8")
        (directory / "stderr.txt").write_text(result.stderr or "", encoding="utf-8")
        output_files: list[dict[str, Any]] = []
        for index, output in enumerate(result.outputs):
            output_files.append(_write_output(directory, index, output))
        manifest = {
            "execId": result.exec_id,
            "semanticHash": semantic_hash,
            "environmentHash": environment_hash,
            "runnerVersion": runner_version,
            "status": result.status,
            "message": result.message,
            "outputs": output_files,
        }
        (directory / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # --- verification results --------------------------------------------
    def load_verification(self, assertion_id: str, semantic_hash: str) -> dict[str, Any] | None:
        path = self._assertion_dir(assertion_id, semantic_hash) / "result.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def store_verification(
        self, assertion_id: str, semantic_hash: str, result: dict[str, Any]
    ) -> None:
        directory = self._assertion_dir(assertion_id, semantic_hash)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _write_output(directory: Path, index: int, output: Output) -> dict[str, Any]:
    stem = f"output-{index}"
    if isinstance(output, TextOutput):
        path = directory / f"{stem}.txt"
        path.write_text(output.text, encoding="utf-8")
        return {"kind": "text", "file": path.name}
    if isinstance(output, ImageOutput):
        path = directory / f"{stem}.png"
        try:
            path.write_bytes(base64.b64decode(output.data_base64))
        except (ValueError, OSError):
            path.write_text(output.data_base64, encoding="utf-8")
        return {
            "kind": "image",
            "file": path.name,
            "mime": output.mime,
            "name": output.name,
        }
    if isinstance(output, MathOutput):
        path = directory / f"{stem}.json"
        path.write_text(
            json.dumps(
                {"kind": "math", "expression": output.expression, "format": output.format},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {"kind": "math", "file": path.name, "format": output.format}
    # JSON / table share a JSON file.
    path = directory / f"{stem}.json"
    path.write_text(
        json.dumps(_output_payload(output), ensure_ascii=False), encoding="utf-8"
    )
    return {"kind": output.kind, "file": path.name}


def _output_payload(output: Output) -> dict[str, Any]:
    if isinstance(output, TableOutput):
        return {"headers": list(output.headers), "rows": output.rows}
    if isinstance(output, JsonOutput):
        return {"value": output.value}
    return {"value": str(output)}


def _load_outputs(manifest: dict[str, Any], directory: Path) -> list[Output]:
    outputs: list[Output] = []
    for entry in manifest.get("outputs", []):
        kind = entry.get("kind")
        path = directory / str(entry.get("file", ""))
        if not path.exists():
            continue
        try:
            if kind == "text":
                outputs.append(TextOutput(_read_text(path)))
            elif kind == "image":
                outputs.append(
                    ImageOutput(
                        base64.b64encode(path.read_bytes()).decode(),
                        mime=str(entry.get("mime", "image/png")),
                        name=entry.get("name"),
                    )
                )
            elif kind == "math":
                data = json.loads(path.read_text(encoding="utf-8"))
                outputs.append(
                    MathOutput(data.get("expression", ""), str(data.get("format", "latex")))
                )
            elif kind == "table":
                data = json.loads(path.read_text(encoding="utf-8"))
                outputs.append(TableOutput(list(data.get("headers", [])), data.get("rows", [])))
            else:  # json
                data = json.loads(path.read_text(encoding="utf-8"))
                outputs.append(JsonOutput(data.get("value")))
        except (OSError, ValueError):
            continue
    return outputs
