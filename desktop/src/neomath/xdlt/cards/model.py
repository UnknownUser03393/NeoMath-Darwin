"""Card model: a semantic resource, not a JSON blob of Markdown.

``content`` is a ``.hw`` fragment parsed by the real xdlt parser into Semantic
IR. Parameters are typed and constrained with the same TypeExpression / SEL
vocabulary as the document, never a card-specific expression language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CardParameter:
    name: str
    type_expr: str | None = None
    requires: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type_expr,
            "requires": list(self.requires),
        }


@dataclass
class Card:
    card_id: str
    version: str
    card_type: str
    title: str = ""
    parameters: dict[str, CardParameter] = field(default_factory=dict)
    requirements: list[str] = field(default_factory=list)
    content: str = ""
    conclusion: str | None = None
    dependencies: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    source_path: str | None = None
    content_ir: dict[str, Any] | None = None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    semantic_hash: str = ""

    @property
    def identity(self) -> str:
        return f"card:{self.card_id}@{self.version}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.card_id,
            "version": self.version,
            "type": self.card_type,
            "title": self.title,
            "parameters": {
                name: parameter.to_dict() for name, parameter in self.parameters.items()
            },
            "requirements": list(self.requirements),
            "content": self.content,
            "conclusion": self.conclusion,
            "dependencies": list(self.dependencies),
            "provenance": dict(self.provenance),
            "sourcePath": self.source_path,
            "semanticHash": self.semantic_hash,
            "diagnostics": list(self.diagnostics),
        }
