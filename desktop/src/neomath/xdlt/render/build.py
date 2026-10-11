"""RenderBuilder: resolved Semantic IR -> RenderDocument.

The builder consumes already-resolved state (values, verification results,
execution results, card registry) and never resolves, executes or verifies
anything itself. Numbering and reference resolution are separate passes; the
HTML backend never counts anything.
"""

from __future__ import annotations

from typing import Any

from neomath.xdlt.execution.result import ExecutionResult
from neomath.xdlt.render.diagnostics import RenderDiagnostic
from neomath.xdlt.render.nodes import (
    RenderAssertion,
    RenderCardReference,
    RenderCode,
    RenderDocument,
    RenderExecutable,
    RenderFigure,
    RenderHeading,
    RenderImage,
    RenderInlineMath,
    RenderMathBlock,
    RenderNode,
    RenderParagraph,
    RenderProof,
    RenderReference,
    RenderSection,
    RenderTable,
    RenderText,
    RenderThesis,
    anonymous_render_id,
    contains_opaque,
)
from neomath.xdlt.render.numbering import NumberingScheme
from neomath.xdlt.render.outputs import lower_execution_output
from neomath.xdlt.render.references import (
    reference_info,
    semantic_id_to_html_anchor,
    split_references,
)
from neomath.xdlt.verification.protocol import VerificationResult

_THESIS_KIND = {
    "Theorem": "theorem",
    "Lemma": "lemma",
    "Proposition": "proposition",
    "Corollary": "corollary",
    "Definition": "definition",
    "Example": "example",
    "Remark": "remark",
    "Algorithm": "algorithm",
}

_SUPPORTED_LAYOUT_KEYS = {"theme", "section", "numbering", "visibility", "metadata"}
_SUPPORTED_SECTION_STYLES = {"numbered"}


class RenderBuilder:
    def __init__(
        self,
        semantic_ir: dict[str, Any],
        card_registry: Any = None,
        verification: list[VerificationResult] | None = None,
        execution: list[ExecutionResult] | None = None,
        layout: dict[str, Any] | None = None,
    ) -> None:
        self.semantic_ir = semantic_ir
        self.registry: dict[str, dict[str, Any]] = semantic_ir.get("entities", {})
        self.card_registry = card_registry
        self.verification: dict[str, VerificationResult] = {
            result.assertion_id: result
            for result in (verification or [])
            if result.assertion_id is not None
        }
        self.execution: dict[str, ExecutionResult] = {
            result.exec_id: result for result in (execution or [])
        }
        self.layout = layout or {}
        self.numbering = NumberingScheme().new_context()
        self.diagnostics: list[RenderDiagnostic] = []
        # references are resolved in a post-pass over the tree

    def build(self) -> RenderDocument:
        document = RenderDocument(self._metadata())
        document.layout = self._layout_projection()
        document.child_nodes = self._build_tree(self.semantic_ir.get("children", []))
        self._assign_render_ids(document.child_nodes)
        self._resolve_references(document.child_nodes)
        self._detect_opaque_math(document.child_nodes)
        from neomath.xdlt.graph.hash import stable_hash

        layout_hash = stable_hash({"layout": document.layout})
        document.finalize_hash(layout_hash)
        return document

    # --- tree building ----------------------------------------------------
    def _build_tree(self, entities: list[Any]) -> list[RenderNode]:
        # ``entities`` is either a flat semantic-entity list (group sections
        # here) or the mixed dict/tuple output of a parent ``_group_sections``
        # call (already grouped). Re-grouping the latter would crash on tuples.
        if not any(isinstance(item, tuple) for item in entities):
            grouped = self._group_sections(entities)
        else:
            grouped = entities
        nodes: list[RenderNode] = []
        for item in grouped:
            if isinstance(item, dict):
                node = self._render_entity(item)
                if node is not None:
                    nodes.append(node)
            else:
                section, section_children = item
                heading = RenderHeading(section.level, section.title)
                section.child_nodes = [heading] + self._build_tree(section_children)
                nodes.append(section)
        return nodes

    def _group_sections(self, entities: list[dict[str, Any]]) -> list[Any]:
        top: list[Any] = []
        stack: list[tuple[int, list[Any]]] = []
        for entity in entities:
            if entity.get("type") == "Section":
                level = int(entity.get("level", 1))
                while stack and stack[-1][0] >= level:
                    stack.pop()
                node = RenderSection(
                    level, str(entity.get("title") or ""), entity.get("sourceRange")
                )
                children: list[Any] = []
                if stack:
                    stack[-1][1].append((node, children))
                else:
                    top.append((node, children))
                stack.append((level, children))
            else:
                if stack:
                    stack[-1][1].append(entity)
                else:
                    top.append(entity)
        return top

    def _render_entity(self, entity: dict[str, Any]) -> RenderNode | None:
        entity_type = entity.get("type")
        if entity_type == "Paragraph":
            return self._render_paragraph(entity)
        if entity_type in ("Equation", "Relation"):
            return self._render_math(entity, is_equation=True)
        if entity_type == "MathExpression":
            return self._render_math(entity, is_equation=False)
        if entity_type in _THESIS_KIND:
            return self._render_thesis(entity, entity_type)
        if entity_type == "Proof":
            return self._render_proof(entity)
        if entity_type == "Assertion":
            return self._render_assertion(entity)
        if entity_type == "Executable":
            return self._render_executable(entity)
        if entity_type == "Figure":
            return self._render_figure(entity)
        if entity_type == "Table":
            return self._render_table_block(entity)
        if entity_type == "CardReference":
            return self._render_card(entity)
        if entity_type == "RawBackendNode":
            return RenderCode(str(entity.get("source") or ""))
        return None  # Context/Section/unknown are not content

    def _render_paragraph(self, entity: dict[str, Any]) -> RenderParagraph:
        node = RenderParagraph(entity.get("sourceRange"))
        node.child_nodes = self._inline_children(
            str(entity.get("source") or ""), entity.get("inlineMath") or []
        )
        self._set_id(node, entity.get("id"), "paragraph")
        return node

    def _inline_children(self, source: str, inline_math: list[dict[str, Any]]) -> list[RenderNode]:
        segments: list[RenderNode] = []
        cursor = 0
        for span in sorted(inline_math, key=lambda m: int(m.get("offset") or 0)):
            offset = int(span.get("offset") or 0)
            length = int(span.get("length") or 0)
            open_dollar = max(0, offset - 1)
            if open_dollar > cursor:
                segments.extend(self._prose_segments(source[cursor:open_dollar]))
            segments.append(
                RenderInlineMath(span.get("semanticMathIr") or {}, str(span.get("rawSource") or ""))
            )
            cursor = offset + length + 1
        if cursor < len(source):
            segments.extend(self._prose_segments(source[cursor:]))
        return segments

    def _prose_segments(self, text: str) -> list[RenderNode]:
        segments: list[RenderNode] = []
        for segment in split_references(text):
            if isinstance(segment, str):
                if segment:
                    segments.append(RenderText(segment))
            else:
                target_id, _source = segment
                reference = RenderReference(target_id)
                pass  # references resolved by _resolve_references pass
                segments.append(reference)
        return segments

    def _render_math(self, entity: dict[str, Any], is_equation: bool) -> RenderMathBlock:
        semantic_id = entity.get("id")
        number = self.numbering.assign(semantic_id, "equation") if semantic_id else None
        node = RenderMathBlock(
            entity.get("semanticMathIr") or {},
            str(entity.get("rawSource") or ""),
            number,
            semantic_id,
            entity.get("sourceRange"),
        )
        self._set_id(node, semantic_id, "equation")
        return node

    def _render_thesis(self, entity: dict[str, Any], entity_type: str) -> RenderThesis:
        semantic_id = entity.get("id")
        kind = _THESIS_KIND[entity_type]
        number = self.numbering.assign(semantic_id, kind) if semantic_id else None
        title = _parse_title(str(entity.get("arguments") or ""))
        node = RenderThesis(
            kind, semantic_id, number, title, entity.get("sourceRange")
        )
        node.child_nodes = self._build_tree(entity.get("children", []))
        self._set_id(node, semantic_id, kind)
        return node

    def _render_proof(self, entity: dict[str, Any]) -> RenderProof:
        node = RenderProof(
            _parse_proves(str(entity.get("arguments") or "")), entity.get("sourceRange")
        )
        node.child_nodes = self._build_tree(entity.get("children", []))
        self._set_id(node, entity.get("id"), "proof")
        return node

    def _render_assertion(self, entity: dict[str, Any]) -> RenderAssertion:
        semantic_id = entity.get("id")
        node = RenderAssertion(
            semantic_id, entity.get("claim"), entity.get("claimSource"), entity.get("sourceRange")
        )
        node.requirements = entity.get("requirements") or []
        node.verifier = str(entity.get("verifier") or "sympy")
        result = self.verification.get(semantic_id) if semantic_id else None
        if result is not None:
            node.verification_status = result.status
            node.message = result.message
            node.evidence = result.evidence
        else:
            node.verification_status = str(
                (entity.get("verification") or {}).get("status", "unverified")
            )
        self._set_id(node, semantic_id, "assertion")
        return node

    def _render_executable(self, entity: dict[str, Any]) -> RenderExecutable:
        semantic_id = entity.get("id")
        node = RenderExecutable(
            semantic_id,
            str(entity.get("language") or "python"),
            str(entity.get("source") or ""),
            entity.get("sourceRange"),
        )
        result = self.execution.get(semantic_id) if semantic_id else None
        if result is not None:
            node.status = result.status
            node.cached = result.cached
            node.stdout = result.stdout
            node.stderr = result.stderr
            node.outputs = [lower_execution_output(output) for output in result.outputs]
        else:
            node.status = "unexecuted"
        self._set_id(node, semantic_id, "executable")
        return node

    def _render_figure(self, entity: dict[str, Any]) -> RenderFigure:
        semantic_id = entity.get("id")
        number = self.numbering.assign(semantic_id, "figure") if semantic_id else None
        node = RenderFigure(
            semantic_id, number, str(entity.get("body") or ""), entity.get("sourceRange")
        )
        source = entity.get("source") or {}
        node.source_target = source.get("targetId")
        node.source_index = source.get("index")
        self._set_id(node, semantic_id, "figure")
        self._resolve_figure_source(node, source)
        return node

    def _resolve_figure_source(self, node: RenderFigure, source: dict[str, Any]) -> None:
        target_id = source.get("targetId")
        if not target_id:
            return
        index = str(source.get("index") or "0")
        result = self.execution.get(str(target_id))
        if result is None or result.status != "success":
            self.diagnostics.append(
                RenderDiagnostic(
                    "warning",
                    "UNAVAILABLE_EXECUTION_OUTPUT",
                    f"figure '{node.semantic_id}' references unexecuted/failed '{target_id}'",
                    render_id=node.render_id,
                    source_range=node.source_range,
                )
            )
            return
        outputs = result.outputs
        if not outputs:
            self.diagnostics.append(
                RenderDiagnostic(
                    "warning",
                    "UNAVAILABLE_EXECUTION_OUTPUT",
                    f"figure '{node.semantic_id}' references output [{index}] which does not exist",
                    render_id=node.render_id,
                    source_range=node.source_range,
                )
            )
            return
        index_int = _parse_index(index)
        if index_int is None or index_int >= len(outputs):
            self.diagnostics.append(
                RenderDiagnostic(
                    "warning",
                    "UNAVAILABLE_EXECUTION_OUTPUT",
                    f"figure '{node.semantic_id}' references output [{index}] which does not exist",
                    render_id=node.render_id,
                    source_range=node.source_range,
                )
            )
            return
        lowered = lower_execution_output(outputs[index_int])
        if isinstance(lowered, RenderImage):
            node.image = lowered
            node.available = True

    def _render_table_block(self, entity: dict[str, Any]) -> RenderNode:
        semantic_id = entity.get("id")
        number = self.numbering.assign(semantic_id, "table") if semantic_id else None
        node = RenderTable(
            semantic_id, number, [], [], entity.get("sourceRange")
        )
        self._set_id(node, semantic_id, "table")
        body = str(entity.get("body") or "")
        if body:
            node.rows = [[line] for line in body.splitlines()]
        return node

    def _render_card(self, entity: dict[str, Any]) -> RenderCardReference:
        semantic_id = entity.get("id")
        card_id = entity.get("cardId")
        node = RenderCardReference(
            semantic_id,
            card_id,
            entity.get("cardVersion"),
            str(entity.get("mode") or "reference"),
            entity.get("sourceRange"),
        )
        node.provenance = entity.get("provenance") or {}
        node.bindings = entity.get("bindings") or []
        self._set_id(node, semantic_id, "card_reference")
        card = None
        if card_id and self.card_registry is not None:
            card = self.card_registry.resolve(str(card_id), entity.get("cardVersion"))
        if card is not None and card.content_ir:
            node.content = self._build_tree(card.content_ir.get("children", []))
        return node

    # --- identity / numbering / references --------------------------------
    def _set_id(self, node: RenderNode, semantic_id: Any, kind: str) -> None:
        if semantic_id:
            node.render_id = str(semantic_id)
        else:
            node.render_id = anonymous_render_id(node)

    def _assign_render_ids(self, nodes: list[RenderNode]) -> None:
        for node in self._iter_nodes(nodes):
            if not node.render_id:
                node.render_id = anonymous_render_id(node)

    def _resolve_references(self, nodes: list[RenderNode]) -> None:
        for node in self._iter_nodes(nodes):
            if not isinstance(node, RenderReference) or not node.target_id:
                continue
            kind, display, anchor = reference_info(
                node.target_id, self.registry, self.numbering.number_of
            )
            if kind is None:
                self.diagnostics.append(
                    RenderDiagnostic(
                        "warning",
                        "UNRESOLVED_RENDER_REFERENCE",
                        f"reference '#{node.target_id}' has no renderable target",
                        render_id=node.render_id,
                        source_range=node.source_range,
                    )
                )
                node.display_text = node.target_id
                node.anchor = semantic_id_to_html_anchor(node.target_id)
            else:
                node.target_kind = kind
                node.display_text = display
                node.anchor = anchor

    # --- layout / metadata --------------------------------------------------
    def _layout_projection(self) -> dict[str, Any]:
        projection: dict[str, Any] = {
            "theme": self.layout.get("theme"),
            "numbering": (self.layout.get("numbering") or {}).get("equations", "auto"),
            "visibility": dict(self.layout.get("visibility") or {}),
        }
        for key in self.layout:
            if key not in _SUPPORTED_LAYOUT_KEYS:
                self.diagnostics.append(
                    RenderDiagnostic(
                        "warning",
                        "UNSUPPORTED_LAYOUT_OPTION",
                        f"layout option '{key}' is not supported and was ignored",
                    )
                )
        section_style = (self.layout.get("section") or {}).get("style")
        if section_style is not None and section_style not in _SUPPORTED_SECTION_STYLES:
            self.diagnostics.append(
                RenderDiagnostic(
                    "warning",
                    "UNSUPPORTED_LAYOUT_OPTION",
                    f"section style '{section_style}' is not supported; using numbered",
                )
            )
        return projection

    def _metadata(self) -> dict[str, Any]:
        meta = dict(self.layout.get("metadata") or {})
        return {
            "title": meta.get("title"),
            "author": meta.get("author"),
            "date": meta.get("date"),
            "abstract": meta.get("abstract"),
        }

    @staticmethod
    def _iter_nodes(nodes: list[RenderNode]) -> Any:
        for node in nodes:
            yield node
            yield from RenderBuilder._iter_nodes(node.children())

    def _detect_opaque_math(self, nodes: list[RenderNode]) -> None:
        for node in self._iter_nodes(nodes):
            if isinstance(node, (RenderInlineMath, RenderMathBlock)) and contains_opaque(
                node.math_ir
            ):
                self.diagnostics.append(
                    RenderDiagnostic(
                        "warning",
                        "OPAQUE_MATH_RENDERED",
                        f"opaque math rendered as fallback in '{node.render_id}'",
                        render_id=node.render_id,
                        source_range=node.source_range,
                    )
                )


def _parse_title(arguments: str) -> str | None:
    value = arguments.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value or None


def _parse_proves(arguments: str) -> str | None:
    value = arguments.strip().lstrip("#")
    return value or None


def _parse_index(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None
