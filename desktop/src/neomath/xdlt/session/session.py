"""Incremental compilation session.

``CompilationSession`` owns all cross-compilation reuse: verification and
execution results are cached by semantic hash + environment; source edits are
mapped to the dependency graph via ``SourceRangeIndex``; the render tree is
diffed into deterministic patches. The existing pure-function pipeline is never
modified — this layer composes it and keeps the caches explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neomath.xdlt.execution.environment import environment_hash
from neomath.xdlt.execution.protocol import ExecutionRequest
from neomath.xdlt.execution.python_runner import PythonRunner
from neomath.xdlt.graph import invalidate_nodes
from neomath.xdlt.graph.nodes import ASSERTION, EXECUTABLE
from neomath.xdlt.project import XdltProject
from neomath.xdlt.render import RenderResult, build_render_result, render_html_from_result
from neomath.xdlt.render.diff import (
    ReplaceDocument,
    apply_patches,
    diff_documents,
)
from neomath.xdlt.render.diff.patches import (
    InsertNode,
    RemoveNode,
    RenderPatch,
    ReplaceNode,
)
from neomath.xdlt.render.html.renderer import HTMLRenderer
from neomath.xdlt.render.nodes import RenderDocument
from neomath.xdlt.render.references import semantic_id_to_html_anchor
from neomath.xdlt.session.cache import (
    EnvironmentSnapshot,
    ExecutionCacheKey,
    SessionCache,
    SourceRangeIndex,
    VerificationCacheKey,
)
from neomath.xdlt.session.changes import (
    SourceChange,
    compute_source_change,
    validate_changes,
)
from neomath.xdlt.session.result import CompilationResult, IncrementalCompilationResult
from neomath.xdlt.values import semantic_value_to_python
from neomath.xdlt.values.nodes import SymbolicValue
from neomath.xdlt.verification import get_verifier, verify_assertion


@dataclass
class _SessionState:
    content: str
    project: XdltProject
    verification: list[Any] = field(default_factory=list)
    execution: list[Any] = field(default_factory=list)
    render: RenderResult | None = None
    html: str = ""
    values: dict[str, Any] | None = None
    execute: bool = True
    verify: bool = True
    layout: dict[str, Any] | None = None
    mode: str = "fragment"
    reused_verification: int = 0
    recomputed_verification: int = 0
    reused_execution: int = 0
    recomputed_execution: int = 0
    reused_parsing: bool = False
    environment: EnvironmentSnapshot | None = None


class CompilationSession:
    def __init__(
        self, session_id: str, cards_dir: str | None = None, mode: str = "fragment"
    ) -> None:
        self.session_id = session_id
        self.cards_dir = cards_dir
        self.mode = mode
        self._verification_cache: SessionCache = SessionCache()
        self._execution_cache: SessionCache = SessionCache()
        self._state: _SessionState | None = None

    # --- public ------------------------------------------------------------
    def compile(
        self,
        content: str,
        *,
        values: dict[str, Any] | None = None,
        execute: bool = True,
        verify: bool = True,
        layout: dict[str, Any] | None = None,
    ) -> CompilationResult:
        state = self._build(content, values=values, execute=execute, verify=verify, layout=layout)
        self._state = state
        return _to_compilation_result(state)

    def update(
        self,
        content: str,
        *,
        values: dict[str, Any] | None = None,
        changes: list[SourceChange] | None = None,
        execute: bool | None = None,
        verify: bool | None = None,
        layout: dict[str, Any] | None = None,
    ) -> IncrementalCompilationResult:
        previous = self._state
        if previous is None:
            result = self.compile(
                content,
                values=values,
                execute=execute if execute is not None else True,
                verify=verify if verify is not None else True,
                layout=layout,
            )
            return IncrementalCompilationResult(
                content=result.content,
                semantic_document=result.semantic_document,
                graph=result.graph,
                render_document=result.render_document,
                html=result.html,
                diagnostics=result.diagnostics,
                assets=result.assets,
                source_map=result.source_map,
                render_diagnostics=result.render_diagnostics,
                patches=[],
                html_patches=[],
                invalidated_semantic_ids=[],
                reused_parsing=False,
            )

        execute = previous.execute if execute is None else execute
        verify = previous.verify if verify is None else verify
        layout = previous.layout if layout is None else layout
        values = previous.values if values is None else values

        if changes is None:
            computed = compute_source_change(previous.content, content)
            changes = [computed] if computed is not None else []
        change_diagnostics = validate_changes(changes, len(previous.content))

        new_state = self._build(
            content,
            values=values,
            execute=execute,
            verify=verify,
            layout=layout,
            previous=previous,
        )

        # Invalidation: source-range direct hits -> dependency closure, plus any
        # node whose semantic hash actually changed. Environment changes map to
        # explicit invalidate reasons (values -> affected symbols; verify/execute
        # toggles -> all assertion/executable nodes).
        index = SourceRangeIndex(previous.project.graph)
        directly_affected = list(index.affected_semantic_ids(changes))
        if _snapshot_values(new_state) != _snapshot_values(previous):
            directly_affected.extend(_changed_value_symbols(previous, new_state))
        if new_state.verify != previous.verify:
            directly_affected.extend(
                nid
                for nid, node in previous.project.graph.nodes.items()
                if node.kind == ASSERTION
            )
        if new_state.execute != previous.execute:
            directly_affected.extend(
                nid
                for nid, node in previous.project.graph.nodes.items()
                if node.kind == EXECUTABLE
            )
        closure = invalidate_nodes(previous.project.graph, directly_affected)
        invalidated = _changed_semantic_ids(previous, new_state)
        invalidated_ids = _ordered_union(
            closure, invalidated, new_state.project.graph
        )

        old_render = previous.render.document if previous.render else None
        new_render = new_state.render.document if new_state.render else None
        patches: list[RenderPatch] = []
        fallback = False
        if old_render is not None and new_render is not None:
            patches, fallback = self._diff_safely(old_render, new_render)

        result = _to_incremental_result(
            new_state,
            patches,
            invalidated_ids,
            change_diagnostics,
            reused_parsing=new_state.reused_parsing,
            patch_fallback=fallback,
        )
        self._state = new_state
        return result

    def destroy(self) -> None:
        self._state = None
        self._verification_cache = SessionCache()
        self._execution_cache = SessionCache()

    def current_content(self) -> str | None:
        return self._state.content if self._state else None

    # --- build -------------------------------------------------------------
    def _build(
        self,
        content: str,
        *,
        values: dict[str, Any] | None,
        execute: bool,
        verify: bool,
        layout: dict[str, Any] | None,
        previous: _SessionState | None = None,
    ) -> _SessionState:
        reused_parsing = previous is not None and previous.content == content
        project = XdltProject.load(content, cards_dir=self.cards_dir, values=values)

        verification, reused_v, recomputed_v = self._verify_document(project, verify)
        execution, reused_e, recomputed_e = self._execute_document(project, execute)

        render = build_render_result(
            project.semantic_ir,
            card_registry=project.card_registry,
            verification=verification,
            execution=execution,
            layout=layout,
        )
        html = render_html_from_result(render, mode=self.mode).html

        snapshot = EnvironmentSnapshot(
            values=_normalized_values(project),
            execute=execute,
            verify=verify,
            layout=_normalized_layout(layout),
            cards_dir=self.cards_dir,
        )
        return _SessionState(
            content=content,
            project=project,
            verification=verification,
            execution=execution,
            render=render,
            html=html,
            values=values,
            execute=execute,
            verify=verify,
            layout=layout,
            mode=self.mode,
            reused_verification=reused_v,
            recomputed_verification=recomputed_v,
            reused_execution=reused_e,
            recomputed_execution=recomputed_e,
            reused_parsing=reused_parsing,
            environment=snapshot,
        )

    def _verify_document(
        self, project: XdltProject, verify: bool
    ) -> tuple[list[Any], int, int]:
        results: list[Any] = []
        if not verify:
            return results, 0, 0
        reused = 0
        recomputed = 0
        env_hash = environment_hash()
        values_hash = project.value_environment.values_hash()
        verifier = get_verifier("sympy")
        verifier_version = getattr(verifier, "version", "unknown") if verifier else "unknown"
        registry = project.semantic_ir.get("entities", {})
        for _node_id, node in project.graph.nodes.items():
            if node.kind != ASSERTION:
                continue
            key = VerificationCacheKey(
                semantic_hash=node.semantic_hash,
                values_hash=values_hash,
                environment_hash=env_hash,
                verifier="sympy",
                verifier_version=verifier_version,
            )
            cached = self._verification_cache.get(key)
            if cached is not None:
                results.append(cached)
                reused += 1
            else:
                result = verify_assertion(node.data or {}, registry)
                self._verification_cache.put(key, result)
                results.append(result)
                recomputed += 1
        return results, reused, recomputed

    def _execute_document(
        self, project: XdltProject, execute: bool
    ) -> tuple[list[Any], int, int]:
        results: list[Any] = []
        if not execute:
            return results, 0, 0
        reused = 0
        recomputed = 0
        env_hash = environment_hash()
        values_hash = project.value_environment.values_hash()
        runner = PythonRunner()
        for node_id in project.graph.topological_order():
            node = project.graph.nodes[node_id]
            if node.kind != EXECUTABLE:
                continue
            entity = node.data or {}
            key = ExecutionCacheKey(
                semantic_hash=node.semantic_hash,
                values_hash=values_hash,
                environment_hash=env_hash,
                runner="python",
                runner_version=runner.version,
            )
            cached = self._execution_cache.get(key)
            if cached is not None:
                results.append(cached)
                reused += 1
                continue
            inputs: dict[str, Any] = {}
            for input_decl in entity.get("inputs", []):
                name = str(input_decl.get("name"))
                symbol_id = input_decl.get("symbolId")
                if symbol_id and project.value_environment.has_value(symbol_id):
                    value = project.value_environment.resolve(symbol_id)
                else:
                    value = SymbolicValue(
                        name, input_decl.get("type"), input_decl.get("properties") or []
                    )
                inputs[name] = semantic_value_to_python(value)
            request = ExecutionRequest(
                exec_id=node_id,
                language=str(entity.get("language") or "python"),
                source=str(entity.get("source") or ""),
                file=entity.get("file"),
                inputs=inputs,
            )
            result = runner.execute(request)
            result.input_hash = node.semantic_hash
            result.environment_hash = env_hash
            self._execution_cache.put(key, result)
            results.append(result)
            recomputed += 1
        return results, reused, recomputed

    def _diff_safely(
        self, old_render: RenderDocument, new_render: RenderDocument
    ) -> tuple[list[RenderPatch], bool]:
        patches = diff_documents(old_render, new_render)
        fallback = any(isinstance(patch, ReplaceDocument) for patch in patches)
        return patches, fallback

    def apply_patches(self, patches: list[RenderPatch]) -> RenderDocument:
        """Reference applier over the session's current render document."""
        if self._state is None or self._state.render is None:
            raise ValueError("no compiled document in session")
        return apply_patches(self._state.render.document, patches)


def _snapshot_values(state: _SessionState) -> dict[str, Any]:
    return state.project.value_environment.to_dict() if state.environment else {}


def _changed_value_symbols(previous: _SessionState, new: _SessionState) -> list[str]:
    old_env = previous.project.value_environment
    new_env = new.project.value_environment
    changed: list[str] = []
    for symbol_id, value in new_env.effective().items():
        if not old_env.has_value(symbol_id):
            changed.append(symbol_id)
        elif old_env.resolve(symbol_id).to_dict() != value.to_dict():
            changed.append(symbol_id)
    return changed


def _changed_semantic_ids(previous: _SessionState, new: _SessionState) -> list[str]:
    old_hashes = {nid: n.semantic_hash for nid, n in previous.project.graph.nodes.items()}
    changed: list[str] = []
    for nid, node in new.project.graph.nodes.items():
        if nid not in old_hashes or old_hashes[nid] != node.semantic_hash:
            changed.append(nid)
    return changed


def _ordered_union(closure: list[str], changed: list[str], graph: Any) -> list[str]:
    order = {nid: index for index, nid in enumerate(graph.nodes)}
    seen: set[str] = set()
    result: list[str] = []
    for node_id in list(closure) + list(changed):
        if node_id in seen:
            continue
        seen.add(node_id)
        result.append(node_id)
    result.sort(key=lambda nid: order.get(nid, 0))
    return result


def _to_compilation_result(state: _SessionState) -> CompilationResult:
    return CompilationResult(
        content=state.content,
        semantic_document=state.project.semantic_ir,
        graph=state.project.graph.to_dict(),
        render_document=state.render.document if state.render else RenderDocument(),
        html=state.html,
        diagnostics=_combined_diagnostics(state),
        assets=[a.to_dict() for a in state.render.assets] if state.render else [],
        source_map=_source_map(state.render) if state.render else [],
        render_diagnostics=state.render.diagnostics if state.render else [],
    )


def _to_incremental_result(
    state: _SessionState,
    patches: list[RenderPatch],
    invalidated_ids: list[str],
    change_diagnostics: list[dict[str, Any]],
    reused_parsing: bool,
    patch_fallback: bool = False,
) -> IncrementalCompilationResult:
    base = _to_compilation_result(state)
    renderer = HTMLRenderer()
    html_patches = [_lower_html(patch, renderer) for patch in patches]
    return IncrementalCompilationResult(
        content=base.content,
        semantic_document=base.semantic_document,
        graph=base.graph,
        render_document=base.render_document,
        html=base.html,
        diagnostics=base.diagnostics + change_diagnostics,
        assets=base.assets,
        source_map=base.source_map,
        render_diagnostics=base.render_diagnostics,
        patches=patches,
        html_patches=html_patches,
        invalidated_semantic_ids=invalidated_ids,
        reused_verification_count=state.reused_verification,
        recomputed_verification_count=state.recomputed_verification,
        reused_execution_count=state.reused_execution,
        recomputed_execution_count=state.recomputed_execution,
        reused_parsing=reused_parsing,
        patch_fallback=patch_fallback,
    )


def _combined_diagnostics(state: _SessionState) -> list[dict[str, Any]]:
    result = [d.to_dict() for d in state.project.diagnostics]
    result += state.project.semantic_ir.get("diagnostics", [])
    return result


def _source_map(render: RenderResult) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for node in _iter(render.document):
        if not node.source_range:
            continue
        entries.append(
            {
                "renderId": node.render_id,
                "semanticId": node.semantic_id,
                "sourceRange": node.source_range,
            }
        )
    return entries


def _iter(node: Any) -> Any:
    yield node
    for child in node.children():
        yield from _iter(child)


def _lower_html(patch: RenderPatch, renderer: HTMLRenderer) -> dict[str, Any]:
    if isinstance(patch, ReplaceNode):
        return {
            "op": "replace",
            "renderId": patch.render_id,
            "anchor": semantic_id_to_html_anchor(patch.render_id),
            "html": renderer.render_node(patch.node),
        }
    if isinstance(patch, RemoveNode):
        return {
            "op": "remove",
            "renderId": patch.render_id,
            "anchor": semantic_id_to_html_anchor(patch.render_id),
        }
    if isinstance(patch, InsertNode):
        return {
            "op": "insert",
            "parentRenderId": patch.parent_render_id,
            "parentAnchor": semantic_id_to_html_anchor(patch.parent_render_id),
            "index": patch.index,
            "html": renderer.render_node(patch.node),
        }
    if isinstance(patch, ReplaceDocument):
        return {
            "op": "replace-document",
            "html": renderer.render_fragment(patch.document),
        }
    return {"op": "unknown"}


def _normalized_values(project: XdltProject) -> dict[str, Any]:
    return dict(project.value_environment.to_dict())


def _normalized_layout(layout: dict[str, Any] | None) -> dict[str, Any]:
    return layout or {}
