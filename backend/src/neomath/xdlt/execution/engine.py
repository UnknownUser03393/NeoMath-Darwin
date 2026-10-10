"""Incremental execution scheduler.

Given a dependency graph it schedules *dirty* executable nodes in topological
order, runs them through isolated runners, stores results in the sidecar cache,
updates build states, propagates failures to dependents (figure -> blocked) and
reuses assertion verification when the semantic hash is unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from neomath.xdlt.execution.cache import ResultCache
from neomath.xdlt.execution.environment import environment_hash
from neomath.xdlt.execution.protocol import ExecutionRequest, ExecutionRunner
from neomath.xdlt.execution.python_runner import PythonRunner
from neomath.xdlt.execution.result import ExecutionResult
from neomath.xdlt.graph.builder import result_node_id
from neomath.xdlt.graph.nodes import (
    ASSERTION,
    BLOCKED,
    CLEAN,
    EXECUTABLE,
    EXECUTION_RESULT,
    FAILED,
    FIGURE,
    RUNNING,
    UNAVAILABLE,
    GraphNode,
)
from neomath.xdlt.values import build_value_environment, semantic_value_to_python
from neomath.xdlt.values.nodes import SymbolicValue
from neomath.xdlt.verification import verify_assertion

_DEFAULT_CACHE_DIR = Path(".xdlt-cache")


class ExecutionEngine:
    def __init__(
        self,
        cache_dir: str | Path | None = None,
        timeout: float = 15.0,
        runners: dict[str, ExecutionRunner] | None = None,
    ) -> None:
        self.cache = ResultCache(cache_dir) if cache_dir else None
        default_runners: dict[str, ExecutionRunner] = {"python": PythonRunner(timeout=timeout)}
        self.runners: dict[str, ExecutionRunner] = runners or default_runners
        self.timeout = timeout
        self._env_hash: str | None = None

    @property
    def environment(self) -> str:
        if self._env_hash is None:
            self._env_hash = environment_hash()
        return self._env_hash

    def execute_document(
        self,
        semantic_ir: dict[str, Any],
        graph: Any,
        value_environment: Any = None,
        exec_id: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        env_hash = self.environment
        if value_environment is None:
            value_environment = build_value_environment(semantic_ir)
        results: list[ExecutionResult] = []
        cache_hits: list[str] = []
        dirty: list[GraphNode] = []

        for node_id in graph.topological_order():
            node = graph.nodes[node_id]
            if node.kind != EXECUTABLE:
                continue
            if exec_id is not None and node_id != exec_id:
                continue
            runner = self.runners.get(str((node.data or {}).get("language") or "python"))
            runner_version = getattr(runner, "version", "0") if runner else "0"
            cached: ExecutionResult | None = None
            if self.cache is not None and not force:
                cached = self.cache.load(node_id, node.semantic_hash, env_hash, runner_version)
            if cached is not None:
                cached.cached = True
                node.state = CLEAN
                self._apply_result(graph, node, cached)
                results.append(cached)
                cache_hits.append(node_id)
            else:
                dirty.append(node)

        for node in dirty:  # already in topological order
            results.append(self._run_node(graph, node, env_hash, value_environment))

        self._update_figure_states(graph)
        verification = self._run_assertions(semantic_ir, graph, force)
        node_states = {node_id: node.state for node_id, node in graph.nodes.items()}
        return {
            "results": results,
            "cacheHits": cache_hits,
            "nodeStates": node_states,
            "verificationResults": verification,
        }

    # --- execution ---------------------------------------------------------
    def _run_node(
        self, graph: Any, node: GraphNode, env_hash: str, value_environment: Any
    ) -> ExecutionResult:
        entity = node.data or {}
        language = str(entity.get("language") or "python")
        runner = self.runners.get(language)
        node.state = RUNNING
        if runner is None:
            result = ExecutionResult(
                exec_id=node.node_id,
                status="unavailable",
                message=f"no runner for language '{language}'",
            )
            node.state = FAILED
        else:
            inputs: dict[str, Any] = {}
            for input_decl in entity.get("inputs", []):
                name = str(input_decl.get("name"))
                symbol_id = input_decl.get("symbolId")
                if symbol_id and value_environment.has_value(symbol_id):
                    value = value_environment.resolve(symbol_id)
                else:
                    value = SymbolicValue(
                        name, input_decl.get("type"), input_decl.get("properties") or []
                    )
                inputs[name] = semantic_value_to_python(value)
            request = ExecutionRequest(
                exec_id=node.node_id,
                language=language,
                source=str(entity.get("source") or ""),
                file=entity.get("file"),
                inputs=inputs,
                dependency_hashes=_dependency_hashes(graph, entity),
                environment={"python": "trusted-local"},
                timeout=_as_float(entity.get("timeout")) or self.timeout,
            )
            result = runner.execute(request)
            result.input_hash = node.semantic_hash
            result.environment_hash = env_hash
            if self.cache is not None:
                self.cache.store(
                    result,
                    node.semantic_hash,
                    env_hash,
                    getattr(runner, "version", "0"),
                )
            node.state = CLEAN if result.status == "success" else FAILED
        self._apply_result(graph, node, result)
        return result

    @staticmethod
    def _apply_result(graph: Any, node: GraphNode, result: ExecutionResult) -> None:
        state = CLEAN if result.status == "success" else UNAVAILABLE
        # The run itself is result index 0 even when it produced no rich outputs.
        count = max(1, len(result.outputs))
        for index in range(count):
            result_id = result_node_id(node.node_id, index)
            result_node = graph.add_node(result_id, EXECUTION_RESULT, "", {}, state=state)
            graph.add_edge(node.node_id, result_id, "produces")
            result_node.data["outputIndex"] = index

    @staticmethod
    def _update_figure_states(graph: Any) -> None:
        for node in graph.nodes.values():
            if node.kind != FIGURE:
                continue
            source = (node.data or {}).get("source") or {}
            target_id = source.get("targetId")
            if not target_id:
                node.state = BLOCKED
                continue
            result_id = result_node_id(target_id, source.get("index") or "0")
            result_node = graph.nodes.get(result_id)
            node.state = CLEAN if (result_node and result_node.state == CLEAN) else BLOCKED

    # --- assertions ---------------------------------------------------------
    def _run_assertions(
        self, semantic_ir: dict[str, Any], graph: Any, force: bool
    ) -> list[dict[str, Any]]:
        registry = semantic_ir.get("entities", {})
        verification: list[dict[str, Any]] = []
        for node_id, node in graph.nodes.items():
            if node.kind != ASSERTION:
                continue
            entity = node.data or {}
            cached = None
            if self.cache is not None and not force:
                cached = self.cache.load_verification(node_id, node.semantic_hash)
            if cached is not None:
                verified = dict(cached)
                verified["cached"] = True
            else:
                verified = verify_assertion(entity, registry).to_dict()
                verified["cached"] = False
                if self.cache is not None:
                    self.cache.store_verification(node_id, node.semantic_hash, verified)
            node.state = FAILED if verified.get("status") == "error" else CLEAN
            node.data = {**(node.data or {}), "verification": verified.get("status")}
            verification.append(verified)
        return verification


def _dependency_hashes(graph: Any, entity: dict[str, Any]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for input_decl in entity.get("inputs", []):
        symbol_id = input_decl.get("symbolId")
        if symbol_id and symbol_id in graph.nodes:
            hashes[str(symbol_id)] = graph.nodes[symbol_id].semantic_hash
    return hashes


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
