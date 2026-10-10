from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BodyMode = Literal[
    "DocumentBody",
    "ExpressionBody",
    "ContextBody",
    "RawBody",
    "TableBody",
    "CardBindingBody",
]


@dataclass
class SourceRange:
    start: int
    end: int

    def to_dict(self) -> dict[str, int]:
        return {"start": self.start, "end": self.end}


@dataclass
class Diagnostic:
    severity: str
    code: str
    message: str
    range: SourceRange
    fixes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "range": self.range.to_dict(),
            "fixes": list(self.fixes),
        }


@dataclass
class SemanticHeader:
    kind: str
    id: str | None = None
    arguments: str = ""
    body_mode: BodyMode = "DocumentBody"
    known: bool = True

    @property
    def canonical_id(self) -> str | None:
        if not self.id:
            return None
        return f"{self.kind}:{self.id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "canonicalId": self.canonical_id,
            "arguments": self.arguments,
            "bodyMode": self.body_mode,
            "known": self.known,
        }


@dataclass
class XdltNode:
    type: str
    source: str
    source_range: SourceRange
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "source": self.source,
            "sourceRange": self.source_range.to_dict(),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }


@dataclass
class HeadingNode(XdltNode):
    level: int = 1
    title: str = ""

    def __init__(
        self,
        source: str,
        source_range: SourceRange,
        level: int,
        title: str,
        diagnostics: list[Diagnostic] | None = None,
    ) -> None:
        super().__init__("heading", source, source_range, diagnostics or [])
        self.level = level
        self.title = title

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update({"level": self.level, "title": self.title})
        return data


@dataclass
class ParagraphNode(XdltNode):
    def __init__(
        self,
        source: str,
        source_range: SourceRange,
        diagnostics: list[Diagnostic] | None = None,
    ) -> None:
        super().__init__("paragraph", source, source_range, diagnostics or [])
        self.inline_math: list["InlineMathNode"] = []

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["inlineMath"] = [child.to_dict() for child in self.inline_math]
        return data


@dataclass
class InlineMathNode(XdltNode):
    """A ``$...$`` span inside a paragraph.

    ``offset``/``length`` locate the math content within the paragraph's
    ``source`` (the ``$`` delimiters are excluded from ``source``).
    """

    offset: int = 0
    length: int = 0

    def __init__(
        self,
        source: str,
        source_range: SourceRange,
        offset: int,
        length: int,
    ) -> None:
        super().__init__("inline_math", source, source_range)
        self.offset = offset
        self.length = length

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["offset"] = self.offset
        data["length"] = self.length
        return data


@dataclass
class CommentNode(XdltNode):
    def __init__(self, source: str, source_range: SourceRange) -> None:
        super().__init__("comment", source, source_range)


@dataclass
class FencedCodeNode(XdltNode):
    language: str = ""
    body: str = ""

    def __init__(
        self,
        source: str,
        source_range: SourceRange,
        language: str,
        body: str,
        diagnostics: list[Diagnostic] | None = None,
    ) -> None:
        super().__init__("fenced_code", source, source_range, diagnostics or [])
        self.language = language
        self.body = body

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update({"language": self.language, "body": self.body})
        return data


@dataclass
class DisplayMathNode(XdltNode):
    id: str | None = None
    arguments: str = ""
    body: str = ""
    numbering: str = "auto"

    def __init__(
        self,
        source: str,
        source_range: SourceRange,
        body: str,
        id: str | None = None,
        arguments: str = "",
        numbering: str = "auto",
        diagnostics: list[Diagnostic] | None = None,
    ) -> None:
        super().__init__("display_math", source, source_range, diagnostics or [])
        self.id = id
        self.arguments = arguments
        self.body = body
        self.numbering = numbering

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "id": self.id,
                "arguments": self.arguments,
                "body": self.body,
                "numbering": self.numbering,
            }
        )
        return data


@dataclass
class SemanticBlockNode(XdltNode):
    header: SemanticHeader = field(default_factory=lambda: SemanticHeader(kind="unknown"))
    body: str = ""
    deindented_body: str = ""
    children: list[XdltNode] = field(default_factory=list)

    def __init__(
        self,
        source: str,
        source_range: SourceRange,
        header: SemanticHeader,
        body: str,
        children: list[XdltNode] | None = None,
        deindented_body: str = "",
        diagnostics: list[Diagnostic] | None = None,
    ) -> None:
        super().__init__("semantic_block", source, source_range, diagnostics or [])
        self.header = header
        self.body = body
        self.children = children or []
        self.deindented_body = deindented_body

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "header": self.header.to_dict(),
                "body": self.body,
                "deindentedBody": self.deindented_body,
                "children": [child.to_dict() for child in self.children],
            }
        )
        return data


@dataclass
class ErrorNode(XdltNode):
    expected: list[str] = field(default_factory=list)

    def __init__(
        self,
        source: str,
        source_range: SourceRange,
        diagnostics: list[Diagnostic],
        expected: list[str] | None = None,
    ) -> None:
        super().__init__("error", source, source_range, diagnostics)
        self.expected = expected or []

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["expected"] = list(self.expected)
        return data


@dataclass
class XdltDocument:
    language_version: str = "0.3"
    nodes: list[XdltNode] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "Document",
            "languageVersion": self.language_version,
            "nodes": [node.to_dict() for node in self.nodes],
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }
