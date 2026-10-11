"""Project assembly: document + card registry + value environment + graph.

``XdltProject`` keeps the module boundaries: nothing is pushed into the bridge;
the bridge composes this project object.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from neomath.xdlt.cards.registry import CardRegistry
from neomath.xdlt.cards.resolver import resolve_project_cards
from neomath.xdlt.graph import build_dependency_graph
from neomath.xdlt.nodes import Diagnostic
from neomath.xdlt.parser import parse_xdlt
from neomath.xdlt.semantic import lower_to_semantic_ir
from neomath.xdlt.values import build_value_environment


class XdltProject:
    def __init__(
        self,
        document: Any,
        semantic_ir: dict[str, Any],
        card_registry: CardRegistry,
        value_environment: Any,
        graph: Any,
        diagnostics: list[Diagnostic],
    ) -> None:
        self.document = document
        self.semantic_ir = semantic_ir
        self.card_registry = card_registry
        self.value_environment = value_environment
        self.graph = graph
        self.diagnostics = diagnostics

    @classmethod
    def load(
        cls,
        content: str,
        cards_dir: str | Path | None = None,
        values: dict[str, Any] | None = None,
    ) -> "XdltProject":
        document = parse_xdlt(content)
        registry = CardRegistry.from_directory(cards_dir)
        semantic_ir = lower_to_semantic_ir(document, card_registry=registry)
        value_environment = build_value_environment(semantic_ir, overrides=values)
        graph = build_dependency_graph(
            semantic_ir,
            card_registry=registry,
            value_environment=value_environment,
        )
        card_diagnostics = resolve_project_cards(semantic_ir, registry, value_environment)
        diagnostics = list(document.diagnostics) + list(card_diagnostics)
        return cls(
            document=document,
            semantic_ir=semantic_ir,
            card_registry=registry,
            value_environment=value_environment,
            graph=graph,
            diagnostics=diagnostics,
        )
