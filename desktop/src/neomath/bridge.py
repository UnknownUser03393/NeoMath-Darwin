from __future__ import annotations

import logging
from pathlib import Path
from threading import Event
from typing import Any

from neomath.ai.openai_client import OpenAIClient
from neomath.config import DEFAULT_OPENAI_MODEL, AppConfig
from neomath.core_client import NeoMathCoreClient
from neomath.documents.autosave import AutosaveManager
from neomath.documents.model import NeoMathDocument
from neomath.documents.repository import DocumentRepository
from neomath.notebook_workspace import NotebookWorkspace
from neomath.settings_store import load_settings, save_settings
from neomath.xdlt_workspace import XdltDocumentWorkspace

LOGGER = logging.getLogger(__name__)


class NeoMathBridge:
    """Small, coarse-grained API exposed to JavaScript by pywebview."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.core = NeoMathCoreClient()
        self.repository = DocumentRepository(config.data_dir)
        self.autosave = AutosaveManager(config.data_dir)
        self.workspace = NotebookWorkspace(config.data_dir)
        self.xdlt_workspace = XdltDocumentWorkspace(config.data_dir)
        self.openai = OpenAIClient(config)
        self._cancel = Event()
        self._xdlt_sessions: dict[str, Any] = {}

    def analyzeDocument(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.core.analyze_document(self._document(payload))

    def runTrace(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._cancel.clear()
        result = self.core.run_trace(self._document(payload))
        return self._cancelled() if self._cancel.is_set() else result

    def replay(self, payload: dict[str, Any]) -> dict[str, Any]:
        changed_step = int(payload.get("changedStep", 0))
        return self.core.replay(self._document(payload), changed_step)

    def getCompletions(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.core.get_completions(
            self._document(payload),
            int(payload.get("step", 0)),
        )

    def executeTransformation(self, payload: dict[str, Any]) -> dict[str, Any]:
        intent = payload.get("intent", {})
        if isinstance(intent, str):
            intent = {"intent": intent}
        return self.core.execute_transformation(
            self._document(payload),
            int(payload.get("step", 0)),
            dict(intent),
        )

    def evaluateProbe(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.core.evaluate_probe(
            self._document(payload),
            dict(payload.get("probe", {})),
        )

    def requestAiExplanation(self, payload: dict[str, Any]) -> dict[str, Any]:
        trace = payload.get("trace")
        if not isinstance(trace, dict):
            trace = self.core.run_trace(self._document(payload))
        return self.openai.explain(trace)

    def compileAiIntent(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            intent = self.openai.compile_intent(str(payload.get("command", "")))
            return {"ok": True, "result": intent}
        except (ValueError, OSError) as error:
            return {
                "ok": False,
                "error": {
                    "type": "ai_schema_error",
                    "code": "AI_INTENT_REJECTED",
                    "message": str(error),
                },
            }

    def saveDocument(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            document = NeoMathDocument.from_dict(payload)
            path_value = payload.get("path")
            path = Path(str(path_value)) if path_value else self._choose_save_path()
            if path is None:
                return {"ok": False, "cancelled": True}
            saved = self.repository.save(document, path)
            self.autosave.discard(document.document_id)
            return {"ok": True, "result": {"path": str(saved), "document": document.to_dict()}}
        except (OSError, ValueError, TypeError) as error:
            LOGGER.exception("Unable to save document")
            return self._io_error("SAVE_FAILED", error)

    def autosaveDocument(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            document = NeoMathDocument.from_dict(payload)
            path = self.autosave.save(document)
            return {"ok": True, "result": {"path": str(path)}}
        except (OSError, ValueError, TypeError) as error:
            LOGGER.exception("Unable to autosave document")
            return self._io_error("AUTOSAVE_FAILED", error)

    def openDocument(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            payload = payload or {}
            path_value = payload.get("path")
            path = Path(str(path_value)) if path_value else self._choose_open_path()
            if path is None:
                return {"ok": False, "cancelled": True}
            document = self.repository.load(path)
            return {"ok": True, "result": {"path": str(path), "document": document.to_dict()}}
        except (OSError, ValueError, TypeError) as error:
            LOGGER.exception("Unable to open document")
            return self._io_error("OPEN_FAILED", error)

    # --- edLatex (v2) structured documents ----------------------------
    def saveEdDocument(self, payload: dict[str, Any]) -> dict[str, Any]:
        from neomath.edlatex.compat import ensure_ed_document

        try:
            document = ensure_ed_document(self._document(payload))
            path_value = payload.get("path")
            path = Path(str(path_value)) if path_value else self._choose_save_path(edlatex=True)
            if path is None:
                return {"ok": False, "cancelled": True}
            saved = self.repository.save_ed(document, path)
            self.autosave.discard(document.document_id)
            return {"ok": True, "result": {"path": str(saved), "document": document.to_dict()}}
        except (OSError, ValueError, TypeError) as error:
            LOGGER.exception("Unable to save edLatex document")
            return self._io_error("SAVE_FAILED", error)

    def autosaveEdDocument(self, payload: dict[str, Any]) -> dict[str, Any]:
        from neomath.edlatex.compat import ensure_ed_document

        try:
            document = ensure_ed_document(self._document(payload))
            path = self.autosave.save_ed(document)
            return {"ok": True, "result": {"path": str(path)}}
        except (OSError, ValueError, TypeError) as error:
            LOGGER.exception("Unable to autosave edLatex document")
            return self._io_error("AUTOSAVE_FAILED", error)

    def openEdDocument(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            payload = payload or {}
            path_value = payload.get("path")
            path = Path(str(path_value)) if path_value else self._choose_open_path()
            if path is None:
                return {"ok": False, "cancelled": True}
            document = self.repository.load_ed(path)
            return {"ok": True, "result": {"path": str(path), "document": document.to_dict()}}
        except (OSError, ValueError, TypeError) as error:
            LOGGER.exception("Unable to open edLatex document")
            return self._io_error("OPEN_FAILED", error)

    def parseContentEdl(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Parse a content.edl string into structured nodes (lossless)."""
        from neomath.edlatex.parser_edl import parse_content_edl

        try:
            text = str(payload.get("content", ""))
            nodes = parse_content_edl(text)
            return {"ok": True, "result": {"nodes": [n.to_dict() for n in nodes]}}
        except (ValueError, TypeError) as error:
            return self._io_error("PARSE_FAILED", error)

    def parseXdltDocument(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Parse a Draft 0.3 .hw document into lossless nodes and semantic IR."""
        from neomath.xdlt import lower_to_semantic_ir, parse_xdlt

        try:
            text = str(payload.get("content", ""))
            document = parse_xdlt(text)
            semantic_ir = lower_to_semantic_ir(document)
            return {
                "ok": True,
                "result": {
                    "document": document.to_dict(),
                    "nodes": [n.to_dict() for n in document.nodes],
                    "diagnostics": [d.to_dict() for d in document.diagnostics],
                    "semanticIr": semantic_ir,
                },
            }
        except (ValueError, TypeError) as error:
            return self._io_error("PARSE_FAILED", error)

    def parseXdltMath(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Parse a LaTeX-math fragment into Math Surface AST + Semantic IR."""
        from neomath.xdlt import collect_math_diagnostics, lower_to_semantic, parse_math

        try:
            source = str(payload.get("source", ""))
            ast = parse_math(source)
            return {
                "ok": True,
                "result": {
                    "ast": ast.to_dict(),
                    "semanticMathIr": lower_to_semantic(ast),
                    "diagnostics": [d.to_dict() for d in collect_math_diagnostics(ast)],
                },
            }
        except (ValueError, TypeError) as error:
            return self._io_error("PARSE_FAILED", error)

    def verifyXdltAssertions(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Lower a .hw document and verify its ``#assert`` blocks with a backend."""
        from neomath.xdlt import lower_to_semantic_ir, parse_xdlt
        from neomath.xdlt.verification import verify_document_assertions

        try:
            content = str(payload.get("content", ""))
            assertion_id = payload.get("assertionId")
            document = parse_xdlt(content)
            semantic_ir = lower_to_semantic_ir(document)
            results = verify_document_assertions(semantic_ir, assertion_id)
            return {
                "ok": True,
                "result": {
                    "semanticIr": semantic_ir,
                    "verificationResults": [result.to_dict() for result in results],
                },
            }
        except (ValueError, TypeError) as error:
            return self._io_error("PARSE_FAILED", error)

    def buildXdltDocument(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Build a .hw document: parse + semantic IR + value env + graph."""
        from neomath.xdlt.project import XdltProject

        try:
            content = str(payload.get("content", ""))
            cards_dir = payload.get("cardsDir")
            values = payload.get("values")
            project = XdltProject.load(content, cards_dir=cards_dir, values=values)
            return {
                "ok": True,
                "result": {
                    "document": project.document.to_dict(),
                    "semanticIr": project.semantic_ir,
                    "graph": project.graph.to_dict(),
                    "valueEnvironment": project.value_environment.to_dict(),
                    "cardRegistry": project.card_registry.to_dict(),
                    "diagnostics": [d.to_dict() for d in project.diagnostics]
                    + project.semantic_ir.get("diagnostics", []),
                },
            }
        except (ValueError, TypeError) as error:
            return self._io_error("PARSE_FAILED", error)

    def getXdltDependencyGraph(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Inspect the dependency graph: nodes, edges, cycles, topo order."""
        from neomath.xdlt.project import XdltProject

        try:
            content = str(payload.get("content", ""))
            cards_dir = payload.get("cardsDir")
            values = payload.get("values")
            project = XdltProject.load(content, cards_dir=cards_dir, values=values)
            return {
                "ok": True,
                "result": {
                    "graph": project.graph.to_dict(),
                    "diagnostics": [d.to_dict() for d in project.diagnostics]
                    + project.semantic_ir.get("diagnostics", []),
                },
            }
        except (ValueError, TypeError) as error:
            return self._io_error("PARSE_FAILED", error)

    def executeXdltDocument(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute dirty executable nodes (isolated, cached) and verify assertions."""
        from neomath.xdlt.execution import ExecutionEngine
        from neomath.xdlt.project import XdltProject

        try:
            content = str(payload.get("content", ""))
            cards_dir = payload.get("cardsDir")
            values = payload.get("values")
            exec_id = payload.get("execId")
            force = bool(payload.get("force", False))
            project = XdltProject.load(content, cards_dir=cards_dir, values=values)
            engine = ExecutionEngine(cache_dir=Path(self.config.data_dir) / ".xdlt-cache")
            outcome = engine.execute_document(
                project.semantic_ir,
                project.graph,
                project.value_environment,
                exec_id,
                force,
            )
            return {
                "ok": True,
                "result": {
                    "semanticIr": project.semantic_ir,
                    "graph": project.graph.to_dict(),
                    "valueEnvironment": project.value_environment.to_dict(),
                    "executionResults": [r.to_dict() for r in outcome["results"]],
                    "cacheHits": outcome["cacheHits"],
                    "nodeStates": outcome["nodeStates"],
                    "verificationResults": outcome["verificationResults"],
                    "diagnostics": [d.to_dict() for d in project.diagnostics]
                    + project.semantic_ir.get("diagnostics", []),
                },
            }
        except (ValueError, TypeError) as error:
            return self._io_error("PARSE_FAILED", error)

    def resolveXdltValues(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Resolve the value environment (document values + runtime overrides)."""
        from neomath.xdlt.project import XdltProject

        try:
            content = str(payload.get("content", ""))
            values = payload.get("values")
            project = XdltProject.load(content, cards_dir=payload.get("cardsDir"), values=values)
            return {
                "ok": True,
                "result": {
                    "valueEnvironment": project.value_environment.to_dict(),
                    "diagnostics": [d.to_dict() for d in project.diagnostics]
                    + project.semantic_ir.get("diagnostics", []),
                },
            }
        except (ValueError, TypeError) as error:
            return self._io_error("PARSE_FAILED", error)

    def getXdltReferenceCss(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Reference stylesheet used by the HTML reference backend (for preview)."""
        from neomath.xdlt.render.html.document import reference_css

        return {"ok": True, "result": {"css": reference_css()}}

    def createXdltSession(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create an incremental compilation session for a .hw document."""
        import uuid

        from neomath.xdlt.session import CompilationSession

        try:
            session_id = str(uuid.uuid4().hex[:16])
            cards_dir = payload.get("cardsDir")
            mode = str(payload.get("mode", "fragment"))
            session = CompilationSession(session_id, cards_dir=cards_dir, mode=mode)
            self._xdlt_sessions[session_id] = session
            result = session.compile(
                str(payload.get("content", "")),
                values=payload.get("values"),
                execute=bool(payload.get("execute", True)),
                verify=bool(payload.get("verify", True)),
                layout=payload.get("layout") if isinstance(payload.get("layout"), dict) else None,
            )
            return {"ok": True, "sessionId": session_id, "result": result.to_dict()}
        except (ValueError, TypeError) as error:
            return self._io_error("SESSION_FAILED", error)

    def updateXdltSession(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Incremental update of a session; returns render patches + stats."""
        from neomath.xdlt.session import SourceChange

        try:
            session_id = str(payload.get("sessionId", ""))
            session = self._xdlt_sessions.get(session_id)
            if session is None:
                return {
                    "ok": False,
                    "error": {
                        "type": "validation_error",
                        "code": "UNKNOWN_SESSION",
                        "message": f"unknown session '{session_id}'",
                    },
                }
            changes = None
            raw_changes = payload.get("changes")
            if raw_changes is not None:
                changes = [
                    SourceChange(
                        start=int(change["start"]),
                        end=int(change["end"]),
                        replacement=str(change["replacement"]),
                    )
                    for change in raw_changes
                ]
            result = session.update(
                str(payload.get("content", "")),
                values=payload.get("values"),
                changes=changes,
                execute=payload.get("execute"),
                verify=payload.get("verify"),
                layout=payload.get("layout") if isinstance(payload.get("layout"), dict) else None,
            )
            return {"ok": True, "sessionId": session_id, "result": result.to_dict()}
        except (ValueError, TypeError) as error:
            return self._io_error("SESSION_FAILED", error)

    def destroyXdltSession(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            session_id = str(payload.get("sessionId", ""))
            session = self._xdlt_sessions.pop(session_id, None)
            if session is not None:
                session.destroy()
            return {"ok": True, "result": {"destroyed": session is not None}}
        except (ValueError, TypeError) as error:
            return self._io_error("SESSION_FAILED", error)

    def renderXdltHtml(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Render a .hw document to HTML via the Render IR pipeline.

        ``execute`` / ``verify`` are opt-in: when off, executables render as
        ``unexecuted`` and assertions as their unverified state. Nothing is
        executed or verified implicitly.
        """
        from neomath.xdlt.execution import ExecutionEngine
        from neomath.xdlt.project import XdltProject
        from neomath.xdlt.render import build_render_result, render_html_from_result
        from neomath.xdlt.verification import verify_document_assertions

        try:
            content = str(payload.get("content", ""))
            cards_dir = payload.get("cardsDir")
            values = payload.get("values")
            mode = str(payload.get("mode", "fragment"))
            execute = bool(payload.get("execute", False))
            verify = bool(payload.get("verify", False))
            layout = payload.get("layout") if isinstance(payload.get("layout"), dict) else None
            project = XdltProject.load(content, cards_dir=cards_dir, values=values)

            verification = (
                verify_document_assertions(project.semantic_ir) if verify else []
            )
            execution = []
            if execute:
                engine = ExecutionEngine(cache_dir=Path(self.config.data_dir) / ".xdlt-cache")
                outcome = engine.execute_document(
                    project.semantic_ir, project.graph, project.value_environment
                )
                execution = outcome["results"]

            render_result = build_render_result(
                project.semantic_ir,
                card_registry=project.card_registry,
                verification=verification,
                execution=execution,
                layout=layout,
            )
            html_result = render_html_from_result(render_result, mode=mode)
            return {
                "ok": True,
                "result": {
                    "html": html_result.html,
                    "renderTree": render_result.to_dict(),
                    "diagnostics": [d.to_dict() for d in html_result.diagnostics],
                    "assets": [a.to_dict() for a in html_result.assets],
                    "sourceMap": html_result.source_map,
                },
            }
        except (ValueError, TypeError) as error:
            return self._io_error("RENDER_FAILED", error)

    def getXdltCards(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Scan a project card registry."""
        from neomath.xdlt.cards import CardRegistry

        try:
            registry = CardRegistry.from_directory(payload.get("cardsDir"))
            return {"ok": True, "result": registry.to_dict()}
        except (ValueError, TypeError) as error:
            return self._io_error("CARDS_FAILED", error)

    def resolveXdltCards(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Resolve ``#use-card`` references in a document."""
        from neomath.xdlt.project import XdltProject

        try:
            content = str(payload.get("content", ""))
            values = payload.get("values")
            project = XdltProject.load(
                content, cards_dir=payload.get("cardsDir"), values=values
            )
            references = [
                {key: value for key, value in child.items() if key != "children"}
                for child in project.semantic_ir.get("children", [])
                if child.get("type") == "CardReference"
            ]
            return {
                "ok": True,
                "result": {
                    "cardRegistry": project.card_registry.to_dict(),
                    "references": references,
                    "diagnostics": [d.to_dict() for d in project.diagnostics]
                    + project.semantic_ir.get("diagnostics", []),
                },
            }
        except (ValueError, TypeError) as error:
            return self._io_error("CARDS_FAILED", error)

    # --- context system (Phase 3) -------------------------------------
    def resolveContext(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return the effective context + conflicts for one node (real resolver)."""
        from neomath.edlatex.compat import ensure_ed_document
        from neomath.edlatex.context import ContextResolver

        try:
            document = ensure_ed_document(self._document(payload))
            resolver = ContextResolver(document)
            node_id = str(payload.get("nodeId", ""))
            if node_id not in document.nodes and node_id:
                return {
                    "ok": False,
                    "error": {
                        "type": "validation_error",
                        "code": "UNKNOWN_NODE",
                        "message": f"节点 {node_id} 不存在",
                    },
                }
            symbols = resolver.effective_context(node_id)
            conflicts = resolver.conflicts_for_node(node_id)
            return {
                "ok": True,
                "result": {
                    "nodeId": node_id,
                    "badge": resolver.badge(node_id),
                    "effectiveContext": {s: c.to_dict() for s, c in symbols.items()},
                    "conflicts": [c.to_dict() for c in conflicts],
                },
            }
        except (ValueError, TypeError) as error:
            return self._io_error("CONTEXT_FAILED", error)

    def inspectContext(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Full inspector payload: inheritance, overrides, conflicts, usedBy."""
        from neomath.edlatex.compat import ensure_ed_document
        from neomath.edlatex.context import ContextResolver

        try:
            document = ensure_ed_document(self._document(payload))
            resolver = ContextResolver(document)
            node_id = str(payload.get("nodeId", ""))
            return {"ok": True, "result": resolver.inspect(node_id)}
        except (ValueError, TypeError) as error:
            return self._io_error("CONTEXT_FAILED", error)

    def contextDiagnostics(self, payload: dict[str, Any]) -> dict[str, Any]:
        """All context conflicts across the document (Problems panel)."""
        from neomath.edlatex.compat import ensure_ed_document
        from neomath.edlatex.context import ContextResolver

        try:
            document = ensure_ed_document(self._document(payload))
            resolver = ContextResolver(document)
            return {
                "ok": True,
                "result": {"conflicts": [c.to_dict() for c in resolver.all_conflicts()]},
            }
        except (ValueError, TypeError) as error:
            return self._io_error("CONTEXT_FAILED", error)

    # --- derivation graph + SymPy validation (Phase 4) -----------------
    def getMathBackends(self) -> dict[str, Any]:
        from neomath.edlatex.backends.registry import default_registry

        registry = default_registry()
        return {
            "ok": True,
            "result": {
                "names": registry.names(),
                "capabilities": registry.capabilities(),
                "availability": registry.availability(),
            },
        }

    def validateStep(self, payload: dict[str, Any]) -> dict[str, Any]:
        from neomath.edlatex.backends.base import StepClaim
        from neomath.edlatex.backends.registry import default_registry
        from neomath.edlatex.compat import ensure_ed_document
        from neomath.edlatex.derivation.graph import DerivationGraph

        try:
            backend_name = str(payload.get("backend", "sympy"))
            node_id = str(payload.get("nodeId", ""))
            if node_id:
                document = ensure_ed_document(self._document(payload))
                result = DerivationGraph(document).validate_step(node_id, backend_name)
            else:
                backend = default_registry().get(backend_name)
                if backend is None:
                    raise ValueError(f"unknown backend: {backend_name}")
                claim = StepClaim(
                    from_expr=str(payload.get("from", "")),
                    to_expr=str(payload.get("to", "")),
                    rule=str(payload.get("rule", "")),
                    assumptions=[str(x) for x in payload.get("assumptions", [])],
                )
                result = backend.validate(claim)
            return {"ok": True, "result": result.to_dict()}
        except (ValueError, TypeError) as error:
            return self._io_error("VALIDATION_FAILED", error)

    def validateDerivations(self, payload: dict[str, Any]) -> dict[str, Any]:
        from neomath.edlatex.compat import ensure_ed_document
        from neomath.edlatex.derivation.graph import DerivationGraph

        try:
            document = ensure_ed_document(self._document(payload))
            backend_name = str(payload.get("backend", "sympy"))
            graph = DerivationGraph(document)
            results = graph.validate_all(backend_name)
            return {
                "ok": True,
                "result": {
                    "steps": {node_id: result.to_dict() for node_id, result in results.items()},
                    "earliestFault": graph.earliest_fault(),
                    "graph": [step.to_dict() for step in graph.steps.values()],
                },
            }
        except (ValueError, TypeError) as error:
            return self._io_error("VALIDATION_FAILED", error)

    def derivationBlame(self, payload: dict[str, Any]) -> dict[str, Any]:
        from neomath.edlatex.compat import ensure_ed_document
        from neomath.edlatex.derivation.graph import DerivationGraph

        try:
            document = ensure_ed_document(self._document(payload))
            node_id = str(payload.get("nodeId", ""))
            graph = DerivationGraph(document)
            return {"ok": True, "result": {"path": graph.blame_path(node_id)}}
        except (ValueError, TypeError) as error:
            return self._io_error("VALIDATION_FAILED", error)

    def exportDocument(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Render an edLatex document to json | html | latex (pdf reports N/A)."""
        from neomath.edlatex.compat import ensure_ed_document
        from neomath.edlatex.render import render_document

        try:
            document = ensure_ed_document(self._document(payload))
            fmt = str(payload.get("format", "latex"))
            result = render_document(document, fmt)
            return {"ok": True, "result": result.to_dict()}
        except (ValueError, TypeError) as error:
            return self._io_error("EXPORT_FAILED", error)

    def getRecentDocuments(self) -> dict[str, Any]:
        return {"ok": True, "result": self.repository.recent()}

    # --- Notebook workspace (React .nm documents) ------------------------

    def listNotebooks(self) -> dict[str, Any]:
        return {"ok": True, "result": self.workspace.list()}

    def loadNotebook(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name", "")).strip()
        try:
            document = self.workspace.load(name)
        except ValueError as error:
            return self._io_error("BAD_NAME", error)
        if document is None:
            return {
                "ok": False,
                "error": {
                    "type": "not_found",
                    "code": "NOT_FOUND",
                    "message": f"notebook not found: {name}",
                },
            }
        return {"ok": True, "result": {"document": document}}

    def saveNotebook(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name", "")).strip()
        document = payload.get("document")
        if not name or not isinstance(document, dict):
            return {
                "ok": False,
                "error": {
                    "type": "validation_error",
                    "code": "BAD_PAYLOAD",
                    "message": "name + document object required",
                },
            }
        try:
            path = self.workspace.save(name, document)
        except (OSError, ValueError) as error:
            return self._io_error("SAVE_FAILED", error)
        return {"ok": True, "result": {"name": path.stem, "fileName": path.name}}

    def renameNotebook(self, payload: dict[str, Any]) -> dict[str, Any]:
        old = str(payload.get("from", "")).strip()
        new = str(payload.get("to", "")).strip()
        if not old or not new:
            return {
                "ok": False,
                "error": {
                    "type": "validation_error",
                    "code": "BAD_PAYLOAD",
                    "message": "from + to required",
                },
            }
        try:
            path = self.workspace.rename(old, new)
        except (OSError, ValueError) as error:
            return self._io_error("RENAME_FAILED", error)
        return {"ok": True, "result": {"name": path.stem, "fileName": path.name}}

    def seedNotebooks(self) -> dict[str, Any]:
        try:
            self.workspace.mark_seeded()
        except OSError as error:
            return self._io_error("SEED_FAILED", error)
        return {"ok": True, "result": {}}

    # --- XDLT document workspace (React .xdlt source files) --------------
    def listXdltDocuments(self) -> dict[str, Any]:
        return {"ok": True, "result": self.xdlt_workspace.list()}

    def loadXdltDocument(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name", "")).strip()
        try:
            source = self.xdlt_workspace.load(name)
        except ValueError as error:
            return self._io_error("BAD_NAME", error)
        if source is None:
            return {
                "ok": False,
                "error": {
                    "type": "not_found",
                    "code": "NOT_FOUND",
                    "message": f"xdlt document not found: {name}",
                },
            }
        return {"ok": True, "result": {"source": source}}

    def saveXdltDocument(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name", "")).strip()
        source = payload.get("source")
        if not name or not isinstance(source, str):
            return {
                "ok": False,
                "error": {
                    "type": "validation_error",
                    "code": "BAD_PAYLOAD",
                    "message": "name + source string required",
                },
            }
        try:
            path = self.xdlt_workspace.save(name, source)
        except (OSError, ValueError) as error:
            return self._io_error("SAVE_FAILED", error)
        return {"ok": True, "result": {"name": path.stem, "fileName": path.name}}

    def renameXdltDocument(self, payload: dict[str, Any]) -> dict[str, Any]:
        old = str(payload.get("from", "")).strip()
        new = str(payload.get("to", "")).strip()
        if not old or not new:
            return {
                "ok": False,
                "error": {
                    "type": "validation_error",
                    "code": "BAD_PAYLOAD",
                    "message": "from + to required",
                },
            }
        try:
            path = self.xdlt_workspace.rename(old, new)
        except (OSError, ValueError) as error:
            return self._io_error("RENAME_FAILED", error)
        return {"ok": True, "result": {"name": path.stem, "fileName": path.name}}

    def seedXdltDocuments(self) -> dict[str, Any]:
        try:
            self.xdlt_workspace.mark_seeded()
        except OSError as error:
            return self._io_error("SEED_FAILED", error)
        return {"ok": True, "result": {}}

    def getCapabilities(self) -> dict[str, Any]:
        capabilities = self.core.get_capabilities()
        if capabilities.get("ok"):
            capabilities["result"]["openai"] = (
                "configured" if self.openai.available else "offline_fallback"
            )
            capabilities["result"]["uiTarget"] = "ui-mockups notebook"
        return capabilities

    def getSettings(self) -> dict[str, Any]:
        key = self.config.openai_api_key or ""
        masked = ""
        if key:
            masked = ("*" * max(0, len(key) - 4)) + key[-4:]
        return {
            "ok": True,
            "result": {
                "openaiConfigured": bool(key),
                "openaiApiKeyMasked": masked,
                "openaiModel": self.config.openai_model,
                "autosaveSeconds": self.config.autosave_seconds,
                "hasStoredKey": "openai_api_key" in load_settings(self.config.data_dir),
                "dataDir": str(self.config.data_dir),
            },
        }

    def saveSettings(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        updates: dict[str, Any] = {}
        if "openai_api_key" in payload:
            raw_key = payload.get("openai_api_key")
            updates["openai_api_key"] = (
                None if raw_key is None or str(raw_key).strip() == "" else str(raw_key).strip()
            )
        if "openai_model" in payload:
            model = str(payload.get("openai_model") or "").strip()
            updates["openai_model"] = model or DEFAULT_OPENAI_MODEL
        if "autosave_seconds" in payload:
            raw_seconds = payload.get("autosave_seconds")
            try:
                if raw_seconds is None or isinstance(raw_seconds, bool):
                    raise TypeError("autosave_seconds missing")
                seconds = int(raw_seconds)
            except (TypeError, ValueError):
                return {
                    "ok": False,
                    "error": {
                        "type": "validation_error",
                        "code": "INVALID_AUTOSAVE",
                        "message": "自动保存间隔必须是 5–600 秒的整数",
                    },
                }
            if seconds < 5 or seconds > 600:
                return {
                    "ok": False,
                    "error": {
                        "type": "validation_error",
                        "code": "INVALID_AUTOSAVE",
                        "message": "自动保存间隔必须是 5–600 秒的整数",
                    },
                }
            updates["autosave_seconds"] = seconds
        try:
            saved = save_settings(self.config.data_dir, updates)
        except OSError as error:
            return self._io_error("SETTINGS_SAVE_FAILED", error)

        config_updates: dict[str, Any] = {}
        if "openai_api_key" in updates:
            config_updates["openai_api_key"] = saved.get("openai_api_key")
        if "openai_model" in updates:
            config_updates["openai_model"] = str(saved.get("openai_model", DEFAULT_OPENAI_MODEL))
        if "autosave_seconds" in updates:
            raw_autosave = saved.get("autosave_seconds", self.config.autosave_seconds)
            config_updates["autosave_seconds"] = int(raw_autosave or self.config.autosave_seconds)
        if config_updates:
            self.config = self.config.with_updates(**config_updates)
            self.openai = OpenAIClient(self.config)
        return self.getSettings()

    def stop(self) -> dict[str, Any]:
        self._cancel.set()
        return {"ok": True, "result": {"cancelRequested": True}}

    @staticmethod
    def _document(payload: dict[str, Any]) -> dict[str, Any]:
        document = payload.get("document", payload)
        if not isinstance(document, dict):
            return {"source": ""}
        return document

    @staticmethod
    def _cancelled() -> dict[str, Any]:
        return {
            "ok": False,
            "error": {
                "type": "cancelled",
                "code": "OPERATION_CANCELLED",
                "message": "operation cancelled",
            },
        }

    @staticmethod
    def _io_error(code: str, error: Exception) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {"type": "io_error", "code": code, "message": str(error)},
        }

    @staticmethod
    def _choose_save_path(edlatex: bool = False) -> Path | None:
        import webview

        if edlatex:
            filename, file_types = "未命名.edlatex.json", ("edLatex 文档 (*.edlatex.json)",)
        else:
            filename, file_types = "未命名.neomath.json", ("NeoMath 文档 (*.neomath.json)",)
        values = webview.windows[0].create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=filename,
            file_types=file_types,
        )
        if not values:
            return None
        return Path(values if isinstance(values, str) else values[0])

    @staticmethod
    def _choose_open_path() -> Path | None:
        import webview

        values = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=(
                "NeoMath 文档 (*.neomath.json *.edlatex.json)",
                "所有文件 (*.*)",
            ),
        )
        if not values:
            return None
        return Path(values if isinstance(values, str) else values[0])
