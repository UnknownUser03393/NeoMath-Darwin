from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from neomath.edlatex.ids import new_id

# Verification states are shared across formula / derivation / assertion nodes.
# The UI must distinguish a genuine math error (invalid) from "not enough
# conditions" (valid-with-conditions) and "can't tell" (unknown).
VERIFICATION_STATES = {
    "unverified",
    "valid",
    "valid-with-conditions",
    "warning",
    "invalid",
    "unknown",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class SourceRange:
    start: int = 0
    end: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"start": self.start, "end": self.end}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SourceRange":
        data = data or {}
        return cls(start=int(data.get("start", 0)), end=int(data.get("end", 0)))


@dataclass
class Diagnostic:
    severity: str = "info"  # info | warning | error
    code: str = ""
    message: str = ""
    source_step_id: str | None = None
    related_expression: str | None = None
    required_condition: str | None = None
    possible_lost_solutions: list[str] = field(default_factory=list)
    possible_added_solutions: list[str] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "sourceStepId": self.source_step_id,
            "relatedExpression": self.related_expression,
            "requiredCondition": self.required_condition,
            "possibleLostSolutions": list(self.possible_lost_solutions),
            "possibleAddedSolutions": list(self.possible_added_solutions),
            "fixes": list(self.fixes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Diagnostic":
        return cls(
            severity=str(data.get("severity", "info")),
            code=str(data.get("code", "")),
            message=str(data.get("message", "")),
            source_step_id=data.get("sourceStepId"),
            related_expression=data.get("relatedExpression"),
            required_condition=data.get("requiredCondition"),
            possible_lost_solutions=[str(x) for x in data.get("possibleLostSolutions", [])],
            possible_added_solutions=[str(x) for x in data.get("possibleAddedSolutions", [])],
            fixes=[str(x) for x in data.get("fixes", [])],
        )


@dataclass
class DocumentNode:
    """Base for every semantic node.

    ``id`` is stable for the lifetime of the node. ``source`` always keeps the
    user's original input so editing is lossless even when parsing fails.
    """

    type: str = "node"
    id: str = ""
    source: str = ""
    source_range: SourceRange = field(default_factory=SourceRange)
    parent_id: str | None = None
    context_id: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = new_id(self.type)

    def touch(self) -> None:
        self.updated_at = _now()

    # --- serialization -------------------------------------------------
    def _base_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "source": self.source,
            "sourceRange": self.source_range.to_dict(),
            "parentId": self.parent_id,
            "contextId": self.context_id,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }

    def to_dict(self) -> dict[str, Any]:
        return self._base_dict()

    @staticmethod
    def _apply_base(node: "DocumentNode", data: dict[str, Any]) -> None:
        node.id = str(data.get("id") or node.id)
        node.source = str(data.get("source", ""))
        node.source_range = SourceRange.from_dict(data.get("sourceRange"))
        node.parent_id = data.get("parentId")
        node.context_id = data.get("contextId")
        node.created_at = str(data.get("createdAt", node.created_at))
        node.updated_at = str(data.get("updatedAt", node.updated_at))
        node.diagnostics = [Diagnostic.from_dict(d) for d in data.get("diagnostics", [])]


@dataclass
class SectionNode(DocumentNode):
    type: str = "section"
    level: int = 1
    title: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data["level"] = self.level
        data["title"] = self.title
        return data


@dataclass
class ParagraphNode(DocumentNode):
    type: str = "paragraph"
    # Text lives in ``source``.


@dataclass
class _MathNode(DocumentNode):
    """Shared math payload for formula and derivation nodes."""

    parsed_expression: str | None = None
    symbol_references: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    verification_status: str = "unverified"
    normalized_expression: str | None = None

    def _math_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(
            {
                "parsedExpression": self.parsed_expression,
                "symbolReferences": list(self.symbol_references),
                "assumptions": list(self.assumptions),
                "dependencies": list(self.dependencies),
                "verificationStatus": self.verification_status,
                "normalizedExpression": self.normalized_expression,
            }
        )
        return data

    @staticmethod
    def _apply_math(node: "_MathNode", data: dict[str, Any]) -> None:
        node.parsed_expression = data.get("parsedExpression")
        node.symbol_references = [str(x) for x in data.get("symbolReferences", [])]
        node.assumptions = [str(x) for x in data.get("assumptions", [])]
        node.dependencies = [str(x) for x in data.get("dependencies", [])]
        node.verification_status = str(data.get("verificationStatus", "unverified"))
        node.normalized_expression = data.get("normalizedExpression")


@dataclass
class FormulaNode(_MathNode):
    type: str = "formula"
    display: bool = True  # display ($$) vs inline ($) math

    def to_dict(self) -> dict[str, Any]:
        data = self._math_dict()
        data["display"] = self.display
        return data


@dataclass
class DerivationNode(_MathNode):
    type: str = "derivation"
    name: str = ""
    from_expr: str = ""
    to_expr: str = ""
    rule: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = self._math_dict()
        data.update(
            {"name": self.name, "from": self.from_expr, "to": self.to_expr, "rule": self.rule}
        )
        return data


@dataclass
class AssertionNode(DocumentNode):
    type: str = "assertion"
    expression_ref: str = ""  # id of node / derivation whose result is checked
    equals: str = ""
    verification_status: str = "unverified"

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data.update(
            {
                "expression": self.expression_ref,
                "equals": self.equals,
                "verificationStatus": self.verification_status,
            }
        )
        return data


@dataclass
class CodeNode(DocumentNode):
    type: str = "code"
    language: str = "python"
    outputs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data["language"] = self.language
        data["outputs"] = list(self.outputs)
        return data


@dataclass
class ContextNode(DocumentNode):
    type: str = "context"
    declarations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data["declarations"] = list(self.declarations)
        return data


@dataclass
class AssetNode(DocumentNode):
    type: str = "asset"
    path: str = ""
    kind: str = "image"

    def to_dict(self) -> dict[str, Any]:
        data = self._base_dict()
        data["path"] = self.path
        data["kind"] = self.kind
        return data


_NODE_CLASSES: dict[str, type[DocumentNode]] = {
    "section": SectionNode,
    "paragraph": ParagraphNode,
    "formula": FormulaNode,
    "derivation": DerivationNode,
    "assertion": AssertionNode,
    "code": CodeNode,
    "context": ContextNode,
    "asset": AssetNode,
}


def node_from_dict(data: dict[str, Any]) -> DocumentNode:
    """Reconstruct the correct node subclass from its serialized ``type``."""
    node_type = str(data.get("type", "paragraph"))
    cls = _NODE_CLASSES.get(node_type, ParagraphNode)
    node = cls()
    DocumentNode._apply_base(node, data)
    if isinstance(node, _MathNode):
        _MathNode._apply_math(node, data)
    if isinstance(node, SectionNode):
        node.level = int(data.get("level", 1))
        node.title = str(data.get("title", ""))
    elif isinstance(node, FormulaNode):
        node.display = bool(data.get("display", True))
    elif isinstance(node, DerivationNode):
        node.name = str(data.get("name", ""))
        node.from_expr = str(data.get("from", ""))
        node.to_expr = str(data.get("to", ""))
        node.rule = str(data.get("rule", ""))
    elif isinstance(node, AssertionNode):
        node.expression_ref = str(data.get("expression", ""))
        node.equals = str(data.get("equals", ""))
        node.verification_status = str(data.get("verificationStatus", "unverified"))
    elif isinstance(node, CodeNode):
        node.language = str(data.get("language", "python"))
        node.outputs = list(data.get("outputs", []))
    elif isinstance(node, ContextNode):
        node.declarations = [str(x) for x in data.get("declarations", [])]
    elif isinstance(node, AssetNode):
        node.path = str(data.get("path", ""))
        node.kind = str(data.get("kind", "image"))
    return node
