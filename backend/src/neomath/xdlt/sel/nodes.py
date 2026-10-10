"""SEL (Semantic Expression Language) AST nodes.

SEL is xdlt's own backend-neutral expression language for machine-checkable
semantic claims. Nodes keep the raw source slice and character offsets so
diagnostics and the formatter can round-trip; symbol and reference resolution
mutate ``symbol_id`` / ``target_*`` fields in place.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class SelRange:
    __slots__ = ("start", "end")

    def __init__(self, start: int, end: int) -> None:
        self.start = start
        self.end = end

    def to_dict(self) -> dict[str, int]:
        return {"start": self.start, "end": self.end}


class SelDiagnostic:
    __slots__ = ("severity", "code", "message", "range")

    def __init__(self, severity: str, code: str, message: str, range: SelRange) -> None:
        self.severity = severity
        self.code = code
        self.message = message
        self.range = range

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "range": self.range.to_dict(),
        }


class SelNode:
    kind: str
    source: str
    range: SelRange
    diagnostics: list[SelDiagnostic]

    def __init__(
        self,
        kind: str,
        source: str = "",
        start: int = 0,
        end: int = 0,
        diagnostics: list[SelDiagnostic] | None = None,
    ) -> None:
        self.kind = kind
        self.source = source
        self.range = SelRange(start, end)
        self.diagnostics = diagnostics or []

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(f"{type(self).__name__!r} has no attribute {name!r}")

    def children(self) -> list["SelNode"]:
        result: list[SelNode] = []
        for value in self.__dict__.values():
            if isinstance(value, SelNode):
                result.append(value)
            elif isinstance(value, list):
                result.extend(item for item in value if isinstance(item, SelNode))
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "source": self.source,
            "range": self.range.to_dict(),
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


def iter_sel(node: SelNode) -> Iterable[SelNode]:
    yield node
    for child in node.children():
        yield from iter_sel(child)


class LiteralNode(SelNode):
    def __init__(
        self,
        value_type: str,
        value: str,
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("literal", source, start, end)
        self.value_type = value_type
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["valueType"] = self.value_type
        data["value"] = self.value
        return data


class SymbolNode(SelNode):
    def __init__(self, name: str, source: str = "", start: int = 0, end: int = 0) -> None:
        super().__init__("symbol", source, start, end)
        self.name = name
        self.symbol_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["name"] = self.name
        data["symbolId"] = self.symbol_id
        return data


class SemanticReferenceNode(SelNode):
    def __init__(self, name: str, source: str = "", start: int = 0, end: int = 0) -> None:
        super().__init__("semantic_reference", source, start, end)
        self.name = name
        self.target_id: str | None = None
        self.target_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["name"] = self.name
        data["targetId"] = self.target_id
        data["targetType"] = self.target_type
        return data


class SelectorNode(SelNode):
    def __init__(
        self,
        reference: SemanticReferenceNode,
        index: str,
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("selector", source, start, end)
        self.reference = reference
        self.index = index

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["reference"] = self.reference.to_dict()
        data["index"] = self.index
        return data


class CallNode(SelNode):
    def __init__(
        self, name: str, args: list[SelNode], source: str = "", start: int = 0, end: int = 0
    ) -> None:
        super().__init__("call", source, start, end)
        self.name = name
        self.args = args

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["name"] = self.name
        return data


class NamedArgumentNode(SelNode):
    def __init__(
        self, name: str, value: SelNode, source: str = "", start: int = 0, end: int = 0
    ) -> None:
        super().__init__("named_argument", source, start, end)
        self.name = name
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["name"] = self.name
        return data


class UnaryNode(SelNode):
    def __init__(
        self, operator: str, operand: SelNode, source: str = "", start: int = 0, end: int = 0
    ) -> None:
        super().__init__("unary", source, start, end)
        self.operator = operator
        self.operand = operand

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["operator"] = self.operator
        return data


class BinaryNode(SelNode):
    def __init__(
        self,
        operator: str,
        left: SelNode,
        right: SelNode,
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("binary", source, start, end)
        self.operator = operator
        self.left = left
        self.right = right

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["operator"] = self.operator
        return data


class ComparisonNode(SelNode):
    def __init__(
        self,
        operator: str,
        left: SelNode,
        right: SelNode,
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("comparison", source, start, end)
        self.operator = operator
        self.left = left
        self.right = right

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["operator"] = self.operator
        return data


class LogicalNode(SelNode):
    def __init__(
        self,
        operator: str,
        left: SelNode,
        right: SelNode,
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("logical", source, start, end)
        self.operator = operator
        self.left = left
        self.right = right

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["operator"] = self.operator
        return data


class ListNode(SelNode):
    def __init__(
        self, items: list[SelNode], source: str = "", start: int = 0, end: int = 0
    ) -> None:
        super().__init__("list", source, start, end)
        self.items = items


class ErrorNode(SelNode):
    def __init__(self, raw: str, source: str = "", start: int = 0, end: int = 0) -> None:
        super().__init__("error", source, start, end)
        self.raw = raw
