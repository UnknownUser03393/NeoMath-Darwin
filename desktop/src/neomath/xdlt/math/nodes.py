"""Math Surface AST nodes.

These mirror the author's LaTeX-math input as closely as possible. A separate
``lower`` pass normalizes them into the Math Semantic IR. Every node retains the
raw source slice and character offsets so formatters and diagnostics can
round-trip the original math.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class MathRange:
    __slots__ = ("start", "end")

    def __init__(self, start: int, end: int) -> None:
        self.start = start
        self.end = end

    def to_dict(self) -> dict[str, int]:
        return {"start": self.start, "end": self.end}


class MathDiagnostic:
    __slots__ = ("severity", "code", "message", "range")

    def __init__(
        self,
        severity: str,
        code: str,
        message: str,
        range: MathRange,
    ) -> None:
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


class MathNode:
    kind: str
    source: str
    range: MathRange
    diagnostics: list[MathDiagnostic]

    def __init__(
        self,
        kind: str,
        source: str = "",
        start: int = 0,
        end: int = 0,
        diagnostics: list[MathDiagnostic] | None = None,
    ) -> None:
        self.kind = kind
        self.source = source
        self.range = MathRange(start, end)
        self.diagnostics = diagnostics or []

    def __getattr__(self, name: str) -> Any:
        # Subclass-specific fields (operands, left, right, ...) are resolved as
        # ``Any`` so the dynamic dispatch in parser/lower stays type-checkable.
        raise AttributeError(f"{type(self).__name__!r} has no attribute {name!r}")

    def children(self) -> list["MathNode"]:
        """Direct child math nodes (used by resolver/lower walks)."""
        result: list[MathNode] = []
        for value in self.__dict__.values():
            if isinstance(value, MathNode):
                result.append(value)
            elif isinstance(value, list):
                result.extend(item for item in value if isinstance(item, MathNode))
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "source": self.source,
            "range": self.range.to_dict(),
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


def iter_math(node: MathNode) -> Iterable[MathNode]:
    """Depth-first walk over a math tree (node itself first)."""
    yield node
    for child in node.children():
        yield from iter_math(child)


class EmptyNode(MathNode):
    def __init__(self, source: str = "") -> None:
        super().__init__("empty", source, 0, len(source))


class IntegerNode(MathNode):
    def __init__(self, value: str, source: str = "", start: int = 0, end: int = 0) -> None:
        super().__init__("integer", source, start, end)
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["value"] = self.value
        return data


class RealNode(MathNode):
    def __init__(self, value: str, source: str = "", start: int = 0, end: int = 0) -> None:
        super().__init__("real", source, start, end)
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["value"] = self.value
        return data


class TextNode(MathNode):
    def __init__(self, text: str, source: str = "", start: int = 0, end: int = 0) -> None:
        super().__init__("text", source, start, end)
        self.text = text

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["text"] = self.text
        return data


class SymbolNode(MathNode):
    """A bare symbol: a single letter or a Greek command.

    ``name`` is the canonical spelling (``alpha`` for ``\\alpha``); ``spelling``
    keeps the surface form (``\\alpha``). ``symbol_id`` is assigned by name
    resolution.
    """

    def __init__(
        self,
        name: str,
        spelling: str,
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("symbol", source, start, end)
        self.name = name
        self.spelling = spelling
        self.symbol_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["name"] = self.name
        data["spelling"] = self.spelling
        data["symbolId"] = self.symbol_id
        return data


class AddNode(MathNode):
    def __init__(
        self, operands: list[MathNode], source: str = "", start: int = 0, end: int = 0
    ) -> None:
        super().__init__("add", source, start, end)
        self.operands = operands


class SubtractNode(MathNode):
    def __init__(
        self, left: MathNode, right: MathNode, source: str = "", start: int = 0, end: int = 0
    ) -> None:
        super().__init__("subtract", source, start, end)
        self.left = left
        self.right = right


class NegateNode(MathNode):
    def __init__(self, operand: MathNode, source: str = "", start: int = 0, end: int = 0) -> None:
        super().__init__("negate", source, start, end)
        self.operand = operand


class MultiplyNode(MathNode):
    def __init__(
        self, operands: list[MathNode], source: str = "", start: int = 0, end: int = 0
    ) -> None:
        super().__init__("multiply", source, start, end)
        self.operands = operands


class DivideNode(MathNode):
    def __init__(
        self, left: MathNode, right: MathNode, source: str = "", start: int = 0, end: int = 0
    ) -> None:
        super().__init__("divide", source, start, end)
        self.left = left
        self.right = right


class PowerNode(MathNode):
    def __init__(
        self, base: MathNode, exponent: MathNode, source: str = "", start: int = 0, end: int = 0
    ) -> None:
        super().__init__("power", source, start, end)
        self.base = base
        self.exponent = exponent


class FractionNode(MathNode):
    def __init__(
        self,
        numerator: MathNode,
        denominator: MathNode,
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("fraction", source, start, end)
        self.numerator = numerator
        self.denominator = denominator


class RootNode(MathNode):
    def __init__(
        self,
        radicand: MathNode,
        degree: MathNode | None,
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("root", source, start, end)
        self.radicand = radicand
        self.degree = degree


class GroupNode(MathNode):
    def __init__(self, inner: MathNode, source: str = "", start: int = 0, end: int = 0) -> None:
        super().__init__("group", source, start, end)
        self.inner = inner


class TupleNode(MathNode):
    """Comma-separated group, e.g. the ``x, t`` in ``u(x, t)``."""

    def __init__(
        self, parts: list[MathNode], source: str = "", start: int = 0, end: int = 0
    ) -> None:
        super().__init__("tuple", source, start, end)
        self.parts = parts


class FunctionCallNode(MathNode):
    def __init__(
        self,
        name: str,
        args: list[MathNode],
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("function_call", source, start, end)
        self.name = name
        self.args = args

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["name"] = self.name
        return data


class SumNode(MathNode):
    def __init__(
        self,
        body: MathNode,
        lower: MathNode | None,
        upper: MathNode | None,
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("sum", source, start, end)
        self.body = body
        self.lower = lower
        self.upper = upper


class ProductNode(MathNode):
    def __init__(
        self,
        body: MathNode,
        lower: MathNode | None,
        upper: MathNode | None,
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("product", source, start, end)
        self.body = body
        self.lower = lower
        self.upper = upper


class IntegralNode(MathNode):
    def __init__(
        self,
        body: MathNode,
        lower: MathNode | None,
        upper: MathNode | None,
        variable: str | None,
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("integral", source, start, end)
        self.body = body
        self.lower = lower
        self.upper = upper
        self.variable = variable

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["variable"] = self.variable
        return data


class PartialDerivativeNode(MathNode):
    def __init__(
        self,
        expression: MathNode,
        order: MathNode | None,
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("partial_derivative", source, start, end)
        self.expression = expression
        self.order = order


class SubscriptNode(MathNode):
    def __init__(
        self, base: MathNode, subscript: MathNode, source: str = "", start: int = 0, end: int = 0
    ) -> None:
        super().__init__("subscript", source, start, end)
        self.base = base
        self.subscript = subscript


class RelationNode(MathNode):
    def __init__(
        self,
        operator: str,
        left: MathNode,
        right: MathNode,
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("relation", source, start, end)
        self.operator = operator
        self.left = left
        self.right = right

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["operator"] = self.operator
        return data


class OpaqueNode(MathNode):
    def __init__(
        self,
        command: str,
        args_raw: str,
        source: str = "",
        start: int = 0,
        end: int = 0,
    ) -> None:
        super().__init__("opaque", source, start, end)
        self.command = command
        self.args_raw = args_raw

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["command"] = self.command
        data["argsRaw"] = self.args_raw
        return data
