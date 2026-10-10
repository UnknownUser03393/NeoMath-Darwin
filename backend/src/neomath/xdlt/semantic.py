from __future__ import annotations

from typing import Any

from neomath.xdlt.cards.binding import parse_use_card_body
from neomath.xdlt.cards.resolver import parse_card_arguments, resolve_use_card
from neomath.xdlt.context import parse_context_body
from neomath.xdlt.math import collect_math_diagnostics, lower_to_semantic, parse_math
from neomath.xdlt.math.nodes import MathNode
from neomath.xdlt.nodes import (
    Diagnostic,
    DisplayMathNode,
    HeadingNode,
    ParagraphNode,
    SemanticBlockNode,
    SourceRange,
    XdltDocument,
    XdltNode,
)
from neomath.xdlt.resolve import (
    Scope,
    SymbolDecl,
    resolve_sel_references,
    resolve_sel_symbols,
    resolve_symbols,
)
from neomath.xdlt.sel import lower_sel, parse_sel
from neomath.xdlt.sel.body import (
    parse_assert_body,
    parse_exec_arguments,
    parse_figure_arguments,
    parse_header_arguments,
)
from neomath.xdlt.sel.nodes import (
    SelDiagnostic,
    SelectorNode,
    SelNode,
    SemanticReferenceNode,
)

_SEMANTIC_TYPES = {
    "context": "Context",
    "thm": "Theorem",
    "lemma": "Lemma",
    "prop": "Proposition",
    "cor": "Corollary",
    "def": "Definition",
    "proof": "Proof",
    "example": "Example",
    "remark": "Remark",
    "derivation": "Derivation",
    "algorithm": "Algorithm",
    "assert": "Assertion",
    "exec": "Executable",
    "fig": "Figure",
    "table": "Table",
    "use-card": "CardReference",
    "raw": "RawBackendNode",
    "xdlt": "FileVersion",
}


def lower_to_semantic_ir(
    document: XdltDocument, card_registry: Any = None
) -> dict[str, Any]:
    return _SemanticBuilder(document, card_registry).build()


class _SemanticBuilder:
    def __init__(self, document: XdltDocument, card_registry: Any = None) -> None:
        self.document = document
        self.card_registry = card_registry
        self.diagnostics: list[Diagnostic] = list(document.diagnostics)
        self.seen_ids: dict[str, SourceRange] = {}
        self._block_count = 0
        self._section_count = 0
        self._context_count = 0
        self._root_scope = Scope(None, "doc", "document")
        self._entity_registry: dict[str, dict[str, Any]] = {}
        self._assertions: list[tuple[dict[str, Any], SelNode | None, list[SelNode]]] = []
        self._figures: list[dict[str, Any]] = []

    def build(self) -> dict[str, Any]:
        children = self._walk(self.document.nodes, self._root_scope)
        self._finalize_assertions()
        self._finalize_figures()
        return {
            "type": "Document",
            "languageVersion": self.document.language_version,
            "children": children,
            "entities": self._entity_registry,
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }

    def _walk(self, nodes: list[XdltNode], base_scope: Scope) -> list[dict[str, Any]]:
        entities: list[dict[str, Any]] = []
        current_scope = base_scope
        for node in nodes:
            if isinstance(node, HeadingNode):
                self._section_count += 1
                current_scope = current_scope.child(f"section.{self._section_count}", "section")
                entities.append(
                    {
                        "type": "Section",
                        "level": node.level,
                        "title": node.title,
                        "sourceRange": node.source_range.to_dict(),
                    }
                )
            elif isinstance(node, SemanticBlockNode):
                if node.header.kind == "context":
                    # Context declarations are visible in the *enclosing* scope
                    # (document/section/block) so top-level ``#context:global``
                    # symbols resolve anywhere in the document.
                    entities.append(self._semantic_block(node, current_scope))
                elif node.header.kind == "assert":
                    entities.append(self._assert_block(node, current_scope))
                elif node.header.kind == "exec":
                    entities.append(self._exec_block(node, current_scope))
                elif node.header.kind == "fig":
                    entities.append(self._figure_block(node, current_scope))
                elif node.header.kind == "use-card":
                    entities.append(self._use_card_block(node, current_scope))
                else:
                    block_scope = self._scope_for_block(node, current_scope)
                    entity = self._semantic_block(node, block_scope)
                    if node.header.canonical_id:
                        self._register_entity(node.header.canonical_id, entity)
                    entities.append(entity)
            elif isinstance(node, DisplayMathNode):
                entity_type = "Equation" if node.id else "MathExpression"
                entity = self._math_entity(
                    node.body, node.source_range, current_scope, node.id, node.numbering
                )
                if node.id:
                    self._register_math_entity(node.id, node.body, entity)
                entities.append({**entity, "type": entity_type})
            elif isinstance(node, ParagraphNode):
                entities.append(self._paragraph(node, current_scope))
        return entities

    def _scope_for_block(self, node: SemanticBlockNode, parent: Scope) -> Scope:
        self._block_count += 1
        return parent.child(f"scope.{self._block_count}", "semantic_block")

    def _semantic_block(self, node: SemanticBlockNode, scope: Scope) -> dict[str, Any]:
        header = node.header
        if header.kind == "context":
            return self._context_block(node, scope)
        node_type = _SEMANTIC_TYPES.get(header.kind, "UnknownExtensionNode")
        if header.canonical_id:
            self._check_duplicate(header.canonical_id, node.source_range)
        entity: dict[str, Any] = {
            "type": node_type,
            "kind": header.kind,
            "id": header.canonical_id,
            "arguments": header.arguments,
            "bodyMode": header.body_mode,
            "sourceRange": node.source_range.to_dict(),
        }
        if header.body_mode == "RawBody":
            entity["source"] = node.deindented_body
        entity["children"] = self._walk(node.children, scope)
        return entity

    def _context_block(self, node: SemanticBlockNode, scope: Scope) -> dict[str, Any]:
        self._context_count += 1
        context_id = node.header.id or f"anon{self._context_count}"
        namespace = f"ctx.{context_id}"
        if node.header.canonical_id:
            self._check_duplicate(node.header.canonical_id, node.source_range)
        context = parse_context_body(node.body, node.source_range.start)
        for diagnostic in context.diagnostics:
            self.diagnostics.append(diagnostic)
        for declaration in context.declarations:
            for name in declaration.names:
                symbol_decl = SymbolDecl(
                    name=name,
                    symbol_id=f"sym:{namespace}/{name}",
                    type_expr=declaration.type_expression.name,
                    properties=[property.name for property in declaration.properties],
                    line=declaration.line,
                    value=declaration.value,
                    value_text=declaration.value_text,
                )
                status = scope.declare(symbol_decl)
                if status == "duplicate":
                    self.diagnostics.append(
                        Diagnostic(
                            severity="error",
                            code="DUPLICATE_SYMBOL",
                            message=f"Duplicate symbol '{name}'",
                            range=SourceRange(declaration.line, declaration.line + 1),
                        )
                    )
                elif status == "shadowed":
                    self.diagnostics.append(
                        Diagnostic(
                            severity="warning",
                            code="SHADOWED_SYMBOL",
                            message=f"Symbol '{name}' shadows an outer declaration",
                            range=SourceRange(declaration.line, declaration.line + 1),
                        )
                    )
        return {
            "type": "Context",
            "kind": node.header.kind,
            "id": node.header.canonical_id,
            "namespace": namespace,
            "declarations": [declaration.to_dict() for declaration in context.declarations],
            "contextDiagnostics": [diagnostic.to_dict() for diagnostic in context.diagnostics],
            "sourceRange": node.source_range.to_dict(),
            "children": self._walk(node.children, scope),
        }

    def _register_entity(self, canonical_id: str, entity: dict[str, Any]) -> None:
        self._entity_registry[canonical_id] = {
            "type": entity.get("type"),
            "id": canonical_id,
        }

    def _register_math_entity(self, math_id: str, raw_source: str, entity: dict[str, Any]) -> None:
        math_ir = entity["semanticMathIr"]
        if math_ir.get("kind") == "equation":
            entity_type = "Equation"
        elif math_ir.get("kind") == "relation":
            entity_type = "Relation"
        else:
            entity_type = "MathExpression"
        self._entity_registry[math_id] = {
            "type": entity_type,
            "id": math_id,
            "rawSource": raw_source,
            "mathIr": math_ir,
            "mathAst": entity["mathAst"],
        }

    def _assert_block(self, node: SemanticBlockNode, scope: Scope) -> dict[str, Any]:
        header = node.header
        if header.canonical_id:
            self._check_duplicate(header.canonical_id, node.source_range)
        arguments = parse_header_arguments(header.arguments)
        verifier = str(arguments.get("using", "sympy"))
        body = parse_assert_body(node.body, node.source_range.start)
        for body_diagnostic in body.diagnostics:
            self.diagnostics.append(body_diagnostic)

        symbol_diagnostics: list[SelDiagnostic] = []
        if body.claim is not None:
            resolve_sel_symbols(body.claim, scope, symbol_diagnostics)
        for requirement in body.requirements:
            resolve_sel_symbols(requirement, scope, symbol_diagnostics)
        for sel_diagnostic in symbol_diagnostics:
            self.diagnostics.append(self._sel_to_document_diagnostic(sel_diagnostic, node))

        entity: dict[str, Any] = {
            "type": "Assertion",
            "kind": header.kind,
            "id": header.canonical_id,
            "verifier": verifier,
            "claimSource": body.claim_source,
            "requirementSources": list(body.requirement_sources),
            "claim": None,
            "requirements": None,
            "symbols": {
                name: declaration.to_dict() for name, declaration in scope.visible_symbols().items()
            },
            "verification": {"status": "unverified", "verifier": verifier},
            "sourceRange": node.source_range.to_dict(),
            "children": [],
        }
        if header.canonical_id:
            self._register_entity(header.canonical_id, entity)
        self._assertions.append((entity, body.claim, body.requirements))
        return entity

    def _finalize_assertions(self) -> None:
        for entity, claim_ast, requirement_asts in self._assertions:
            reference_diagnostics: list[SelDiagnostic] = []
            if claim_ast is not None:
                resolve_sel_references(claim_ast, self._entity_registry, reference_diagnostics)
                entity["claim"] = lower_sel(claim_ast)
            requirements = []
            for requirement in requirement_asts:
                resolve_sel_references(requirement, self._entity_registry, reference_diagnostics)
                requirements.append(lower_sel(requirement))
            entity["requirements"] = requirements
            for sel_diagnostic in reference_diagnostics:
                self.diagnostics.append(self._sel_to_document_diagnostic(sel_diagnostic, None))

    def _exec_block(self, node: SemanticBlockNode, scope: Scope) -> dict[str, Any]:
        header = node.header
        if header.canonical_id:
            self._check_duplicate(header.canonical_id, node.source_range)
        arguments = parse_exec_arguments(header.arguments)
        language = str(arguments.get("language") or "python")
        input_names = arguments.get("inputs") or []
        assert isinstance(input_names, list)
        inputs: list[dict[str, Any]] = []
        for name in input_names:
            name = str(name)
            declaration = scope.lookup(name)
            if declaration is None:
                self.diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="UNRESOLVED_SYMBOL",
                        message=f"Unresolved symbol '{name}'",
                        range=node.source_range,
                    )
                )
                inputs.append({"name": name, "symbolId": None, "type": None, "properties": []})
            else:
                inputs.append(
                    {
                        "name": declaration.name,
                        "symbolId": declaration.symbol_id,
                        "type": declaration.type_expr,
                        "properties": list(declaration.properties),
                    }
                )
        entity: dict[str, Any] = {
            "type": "Executable",
            "kind": header.kind,
            "id": header.canonical_id,
            "language": language,
            "kernel": arguments.get("kernel"),
            "file": arguments.get("file"),
            "timeout": arguments.get("timeout"),
            "inputs": inputs,
            "source": node.deindented_body,
            "body": node.body,
            "sourceRange": node.source_range.to_dict(),
            "children": [],
        }
        if header.canonical_id:
            self._register_entity(header.canonical_id, entity)
        return entity

    def _figure_block(self, node: SemanticBlockNode, scope: Scope) -> dict[str, Any]:
        header = node.header
        if header.canonical_id:
            self._check_duplicate(header.canonical_id, node.source_range)
        arguments = parse_figure_arguments(header.arguments)
        entity: dict[str, Any] = {
            "type": "Figure",
            "kind": header.kind,
            "id": header.canonical_id,
            "body": node.body,
            "source": None,
            "sourceRaw": arguments.get("source"),
            "sourceRange": node.source_range.to_dict(),
            "children": self._walk(node.children, scope),
        }
        if header.canonical_id:
            self._register_entity(header.canonical_id, entity)
        self._figures.append(entity)
        return entity

    def _finalize_figures(self) -> None:
        for entity in self._figures:
            source_raw = entity.get("sourceRaw")
            if not source_raw:
                continue
            if not str(source_raw).lstrip().startswith("#"):
                continue
            source_sel = parse_sel(str(source_raw))
            reference_diagnostics: list[SelDiagnostic] = []
            resolve_sel_references(source_sel, self._entity_registry, reference_diagnostics)
            for sel_diagnostic in reference_diagnostics:
                self.diagnostics.append(self._sel_to_document_diagnostic(sel_diagnostic, None))
            entity["source"] = _figure_source_dict(source_sel)

    def _use_card_block(self, node: SemanticBlockNode, scope: Scope) -> dict[str, Any]:
        header = node.header
        if header.canonical_id:
            self._check_duplicate(header.canonical_id, node.source_range)
        arguments = parse_card_arguments(header.arguments)
        body = parse_use_card_body(node.body, node.source_range.start)
        for diagnostic in body.diagnostics:
            self.diagnostics.append(diagnostic)
        resolved, diagnostics = resolve_use_card(
            card_ref=arguments.get("cardRef"),
            mode=str(arguments.get("mode") or "reference"),
            version=arguments.get("version"),
            body=body.bindings,
            scope=scope,
            registry=self.card_registry,
        )
        for card_diagnostic in diagnostics:
            self.diagnostics.append(
                Diagnostic(
                    severity=str(card_diagnostic.get("severity", "error")),
                    code=str(card_diagnostic.get("code", "")),
                    message=str(card_diagnostic.get("message", "")),
                    range=node.source_range,
                )
            )
        entity: dict[str, Any] = {
            "type": "CardReference",
            "kind": header.kind,
            "id": header.canonical_id,
            **resolved,
            "requireSources": list(body.require_sources),
            "sourceRange": node.source_range.to_dict(),
            "children": [],
        }
        if header.canonical_id:
            self._register_entity(header.canonical_id, entity)
        return entity

    @staticmethod
    def _sel_to_document_diagnostic(
        diagnostic: SelDiagnostic, node: SemanticBlockNode | None
    ) -> Diagnostic:
        if node is not None:
            source_range = node.source_range
        else:
            source_range = SourceRange(0, 1)
        return Diagnostic(
            severity=diagnostic.severity,
            code=diagnostic.code,
            message=diagnostic.message,
            range=source_range,
        )

    def _paragraph(self, node: ParagraphNode, scope: Scope) -> dict[str, Any]:
        inline: list[dict[str, Any]] = []
        for math in node.inline_math:
            entity = self._math_entity(math.source, math.source_range, scope, None, "auto")
            entity["offset"] = math.offset
            entity["length"] = math.length
            inline.append(entity)
        return {
            "type": "Paragraph",
            "source": node.source,
            "sourceRange": node.source_range.to_dict(),
            "inlineMath": inline,
        }

    def _math_entity(
        self,
        math_source: str,
        source_range: SourceRange,
        scope: Scope,
        equation_id: str | None,
        numbering: str,
    ) -> dict[str, Any]:
        ast = parse_math(math_source)
        math_diagnostics = collect_math_diagnostics(ast)
        resolve_symbols(ast, scope, math_diagnostics)
        semantic_ir = lower_to_semantic(ast)
        entity: dict[str, Any] = {
            "rawSource": math_source,
            "mathAst": ast.to_dict(),
            "semanticMathIr": semantic_ir,
            "symbolReferences": _symbol_refs(ast),
            "mathDiagnostics": [diagnostic.to_dict() for diagnostic in math_diagnostics],
            "sourceRange": source_range.to_dict(),
        }
        if equation_id:
            self._check_duplicate(equation_id, source_range)
            entity["id"] = equation_id
            entity["numbering"] = numbering
        return entity

    def _check_duplicate(self, semantic_id: str, source_range: SourceRange) -> None:
        if semantic_id in self.seen_ids:
            self.diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="DUPLICATE_ID",
                    message=f"Duplicate stable semantic ID '{semantic_id}'",
                    range=source_range,
                )
            )
            return
        self.seen_ids[semantic_id] = source_range


def _symbol_refs(root: MathNode) -> list[str]:
    refs: list[str] = []
    _collect_refs(root, refs)
    return refs


def _collect_refs(node: MathNode, refs: list[str]) -> None:
    if node.kind == "symbol" and node.symbol_id and node.symbol_id not in refs:
        refs.append(node.symbol_id)
    for child in node.children():
        _collect_refs(child, refs)


def _figure_source_dict(sel: SelNode) -> dict[str, Any] | None:
    """``#exec:plot[0]`` -> ``{"targetId": "exec:plot", "index": "0"}``."""
    if isinstance(sel, SelectorNode):
        return {"targetId": sel.reference.target_id, "index": sel.index}
    if isinstance(sel, SemanticReferenceNode):
        return {"targetId": sel.target_id, "index": "0"}
    return None
