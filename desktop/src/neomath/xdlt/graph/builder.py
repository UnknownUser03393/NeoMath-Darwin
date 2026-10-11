"""Build the dependency graph from Math Semantic IR.

The graph is a *semantic* view of the document: stable semantic IDs become
nodes (``eq:heat``, ``sym:ctx.global/alpha``), anonymous-but-needed entities get
deterministic internal IDs (``internal:doc/math.1``). Typed edges record
``uses-symbol`` / ``references`` / ``exec-input`` / ``produces`` / ``renders``
/ ``declares``. Everything is derived from document order, so the same IR
always produces the same graph.
"""

from __future__ import annotations

from typing import Any

from neomath.xdlt.graph.graph import DependencyGraph
from neomath.xdlt.graph.hash import (
    assertion_hash,
    collect_reference_ids,
    collect_symbol_ids,
    context_hash,
    executable_hash,
    figure_hash,
    math_entity_hash,
    stable_hash,
    symbol_node_hash,
)
from neomath.xdlt.graph.nodes import (
    ASSERTION,
    CARD,
    CARD_REFERENCE,
    CONTEXT,
    EQUATION,
    EXECUTABLE,
    EXECUTION_RESULT,
    FIGURE,
    MATH_EXPRESSION,
    SEMANTIC_BLOCK,
    SYMBOL,
    UNAVAILABLE,
)

_RESULT_SEP = "."


def result_node_id(exec_id: str, index: str | int = 0) -> str:
    """``exec:plot`` + index 0 -> ``result:exec.plot/0``."""
    return f"result:{exec_id.replace(':', _RESULT_SEP)}/{index}"


def build_dependency_graph(
    semantic_ir: dict[str, Any],
    card_registry: Any = None,
    value_environment: Any = None,
) -> DependencyGraph:
    return _GraphBuilder(semantic_ir, card_registry, value_environment).build()


class _GraphBuilder:
    def __init__(
        self,
        semantic_ir: dict[str, Any],
        card_registry: Any = None,
        value_environment: Any = None,
    ) -> None:
        self.graph = DependencyGraph()
        self.registry: dict[str, dict[str, Any]] = semantic_ir.get("entities", {})
        self.children: list[dict[str, Any]] = semantic_ir.get("children", [])
        self.card_registry = card_registry
        self.value_env = value_environment
        self._symbols: dict[str, dict[str, Any]] = {}
        self._math_count = 0
        self._block_count = 0
        self._exec_count = 0
        self._assert_count = 0
        self._fig_count = 0
        self._card_count = 0
        self._collect_contexts(self.children)

    # --- pass 1: symbol declarations -------------------------------------
    def _collect_contexts(self, children: list[dict[str, Any]]) -> None:
        for entity in children:
            if entity.get("type") == "Context":
                namespace = entity.get("namespace")
                for declaration in entity.get("declarations", []):
                    type_name = declaration.get("type", {}).get("name")
                    properties = [p.get("name") for p in declaration.get("properties", [])]
                    value = declaration.get("value")
                    for name in declaration.get("names", []):
                        symbol_id = f"sym:{namespace}/{name}"
                        self._symbols[symbol_id] = {
                            "name": name,
                            "symbolId": symbol_id,
                            "type": type_name,
                            "properties": properties,
                            "value": value,
                        }
            self._collect_contexts(entity.get("children", []))

    # --- main build --------------------------------------------------------
    def build(self) -> DependencyGraph:
        for symbol_id, declaration in self._symbols.items():
            self._apply_effective_value(declaration, symbol_id)
            self.graph.add_node(symbol_id, SYMBOL, symbol_node_hash(declaration), declaration)
        self._walk(self.children)
        self._materialize_dangling()
        return self.graph

    def _apply_effective_value(self, declaration: dict[str, Any], symbol_id: str) -> None:
        if self.value_env is not None and self.value_env.has_value(symbol_id):
            declaration["value"] = self.value_env.resolve(symbol_id).to_dict()
        elif declaration.get("value") is None:
            declaration["value"] = None

    def _walk(self, children: list[dict[str, Any]]) -> None:
        for entity in children:
            entity_type = entity.get("type")
            if entity_type == "Context":
                self._context(entity)
            elif entity_type == "Equation":
                self._math(entity, is_equation=True)
            elif entity_type == "MathExpression":
                self._math(entity, is_equation=False)
            elif entity_type == "Assertion":
                self._assertion(entity)
            elif entity_type == "Executable":
                self._executable(entity)
            elif entity_type == "Figure":
                self._figure(entity)
            elif entity_type == "CardReference":
                self._use_card(entity)
            elif entity_type and entity_type not in ("Section", "Paragraph"):
                self._semantic_block(entity)
            self._walk(entity.get("children", []))

    # --- node handlers ------------------------------------------------------
    def _context(self, entity: dict[str, Any]) -> None:
        namespace = entity.get("namespace") or "doc"
        node_id = entity.get("id") or f"context:{namespace}"
        self.graph.add_node(node_id, CONTEXT, context_hash(entity), entity)
        for symbol_id, _declaration in self._symbols.items():
            if symbol_id.startswith(f"sym:{namespace}/"):
                self.graph.add_edge(node_id, symbol_id, "declares")

    def _math(self, entity: dict[str, Any], is_equation: bool) -> None:
        node_id = entity.get("id")
        if not node_id:
            self._math_count += 1
            node_id = f"internal:doc/math.{self._math_count}"
        kind = EQUATION if is_equation else MATH_EXPRESSION
        math_ir = entity.get("semanticMathIr") or {}
        self.graph.add_node(node_id, kind, math_entity_hash(math_ir), entity)
        for symbol_id in entity.get("symbolReferences", []):
            self._ensure_symbol_node(symbol_id)
            self.graph.add_edge(node_id, symbol_id, "uses-symbol")

    def _assertion(self, entity: dict[str, Any]) -> None:
        node_id = entity.get("id")
        if not node_id:
            self._assert_count += 1
            node_id = f"internal:doc/assert.{self._assert_count}"
        value_resolver = None
        if self.value_env is not None:
            value_resolver = self._effective_value_for_name
        self.graph.add_node(
            node_id, ASSERTION, assertion_hash(entity, self.registry, value_resolver), entity
        )
        claim = entity.get("claim")
        requirements = entity.get("requirements") or []
        for target_id in collect_reference_ids(claim) + collect_reference_ids(requirements):
            self.graph.add_edge(node_id, target_id, "references")
        for symbol_id in collect_symbol_ids(claim) + collect_symbol_ids(requirements):
            self._ensure_symbol_node(symbol_id)
            self.graph.add_edge(node_id, symbol_id, "uses-symbol")

    def _executable(self, entity: dict[str, Any]) -> None:
        node_id = entity.get("id")
        if not node_id:
            self._exec_count += 1
            node_id = f"internal:doc/exec.{self._exec_count}"
        dependency_hashes: dict[str, str] = {}
        for input_decl in entity.get("inputs", []):
            symbol_id = input_decl.get("symbolId")
            if not symbol_id:
                continue
            self._ensure_symbol_node(symbol_id)
            dependency_hashes[symbol_id] = symbol_node_hash(
                self._effective_input_decl(input_decl, symbol_id)
            )
            self.graph.add_edge(node_id, symbol_id, "exec-input")
        self.graph.add_node(
            node_id, EXECUTABLE, executable_hash(entity, dependency_hashes), entity
        )

    def _figure(self, entity: dict[str, Any]) -> None:
        node_id = entity.get("id")
        if not node_id:
            self._fig_count += 1
            node_id = f"internal:doc/fig.{self._fig_count}"
        source = entity.get("source") or {}
        self.graph.add_node(node_id, FIGURE, figure_hash(entity, source), entity)
        target_id = source.get("targetId")
        if not target_id:
            return
        index = source.get("index") or "0"
        result_id = result_node_id(target_id, index)
        self.graph.add_node(result_id, EXECUTION_RESULT, "", {}, state=UNAVAILABLE)
        self.graph.add_edge(node_id, result_id, "renders")
        target = self.registry.get(target_id)
        if (target and target.get("type") == "Executable") or target_id in self.graph.nodes:
            self.graph.add_edge(target_id, result_id, "produces")

    def _use_card(self, entity: dict[str, Any]) -> None:
        node_id = entity.get("id")
        if not node_id:
            self._card_count += 1
            node_id = f"internal:doc/use-card.{self._card_count}"
        provenance = entity.get("provenance") or {}
        bindings = _normalized_bindings(entity.get("bindings") or [])
        semantic_hash = stable_hash(
            {
                "card_reference": {
                    "cardId": provenance.get("cardId"),
                    "cardVersion": provenance.get("cardVersion"),
                    "mode": provenance.get("mode"),
                    "cardSemanticHash": provenance.get("cardSemanticHash"),
                    "bindings": bindings,
                }
            }
        )
        self.graph.add_node(node_id, CARD_REFERENCE, semantic_hash, entity)
        card_id = provenance.get("cardId")
        if card_id and self.card_registry is not None:
            card = self.card_registry.resolve(str(card_id), provenance.get("cardVersion"))
            if card is not None:
                self._collect_cards(card, set())
                self.graph.add_edge(node_id, card.identity, "references")
        for binding in entity.get("bindings", []):
            symbol_id = binding.get("symbolId")
            if symbol_id:
                self._ensure_symbol_node(symbol_id)
                self.graph.add_edge(node_id, symbol_id, "uses-symbol")

    def _collect_cards(self, card: Any, visited: set[str]) -> None:
        node_id = card.identity
        if node_id in visited:
            return
        visited.add(node_id)
        self.graph.add_node(node_id, CARD, card.semantic_hash, {"card": card.to_dict()})
        for dependency_id in card.dependencies:
            dependency = self.card_registry.resolve(str(dependency_id))
            if dependency is None:
                continue
            self._collect_cards(dependency, visited)
            self.graph.add_edge(node_id, dependency.identity, "depends-on")

    def _semantic_block(self, entity: dict[str, Any]) -> None:
        node_id = entity.get("id")
        if not node_id:
            return
        self.graph.add_node(
            node_id,
            SEMANTIC_BLOCK,
            _block_hash(entity, node_id),
            entity,
        )

    # --- helpers ------------------------------------------------------------
    def _ensure_symbol_node(self, symbol_id: str) -> None:
        if symbol_id in self.graph.nodes:
            return
        name = symbol_id.rsplit("/", 1)[-1]
        declaration: dict[str, Any] = {
            "name": name,
            "symbolId": symbol_id,
            "type": None,
            "properties": [],
            "value": None,
        }
        self.graph.add_node(symbol_id, SYMBOL, symbol_node_hash(declaration), declaration)

    def _effective_value_for_name(self, name: str) -> dict[str, Any]:
        return dict(self.value_env.resolve_name(name).to_dict())

    def _effective_input_decl(
        self, input_decl: dict[str, Any], symbol_id: str
    ) -> dict[str, Any]:
        effective = dict(input_decl)
        symbol_node = self.graph.nodes.get(symbol_id)
        document_value = symbol_node.data.get("value") if symbol_node else None
        if self.value_env is not None and self.value_env.has_value(symbol_id):
            effective["value"] = self.value_env.resolve(symbol_id).to_dict()
        else:
            effective["value"] = document_value
        return effective

    def _materialize_dangling(self) -> None:
        """Placeholder nodes for edge endpoints that were never materialized."""
        for source, target, _edge_type in self.graph.edges:
            for node_id in (source, target):
                if node_id in self.graph.nodes:
                    continue
                if node_id.startswith("result:"):
                    kind = EXECUTION_RESULT
                elif node_id.startswith("sym:"):
                    kind = SYMBOL
                else:
                    kind = SEMANTIC_BLOCK
                self.graph.add_node(node_id, kind, "", {})


def _block_hash(entity: dict[str, Any], node_id: str) -> str:
    return stable_hash(
        {"block": {"id": node_id, "kind": entity.get("kind"), "type": entity.get("type")}}
    )


def _normalized_bindings(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in binding.items() if key != "valueRaw"} for binding in bindings
    ]
