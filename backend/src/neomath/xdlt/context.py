"""Structured parsing of ``#context`` symbol declarations.

Grammar per line::

    names ':' type [ '&' property ( '&' property )* ]
    names = name ( ',' name )*

Supported types and properties are intentionally small and validate against a
fixed vocabulary; anything else raises ``INVALID_SYMBOL_DECLARATION``.
"""

from __future__ import annotations

import re

from neomath.xdlt.nodes import Diagnostic, SourceRange
from neomath.xdlt.values import parse_value_expression, validate_value
from neomath.xdlt.values.nodes import SemanticValue

_TYPES = {"Real", "Complex", "Integer", "Natural"}
_PROPERTIES = {"Positive", "NonNegative", "NonZero"}

_DECLARATION = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)"
    r"\s*:\s*([A-Za-z]+)(.*)$"
)


class TypeExpression:
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name}


class Property:
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name}


class SymbolDeclaration:
    __slots__ = ("names", "type_expression", "properties", "line", "raw", "value", "value_text")

    def __init__(
        self,
        names: list[str],
        type_expression: TypeExpression,
        properties: list[Property],
        line: int,
        raw: str,
        value: SemanticValue | None = None,
        value_text: str | None = None,
    ) -> None:
        self.names = names
        self.type_expression = type_expression
        self.properties = properties
        self.line = line
        self.raw = raw
        self.value = value
        self.value_text = value_text

    def to_dict(self) -> dict[str, object]:
        return {
            "names": list(self.names),
            "type": self.type_expression.to_dict(),
            "properties": [property.to_dict() for property in self.properties],
            "line": self.line,
            "raw": self.raw,
            "value": self.value.to_dict() if self.value is not None else None,
            "valueText": self.value_text,
        }


class ContextDecl:
    __slots__ = ("declarations", "diagnostics")

    def __init__(
        self,
        declarations: list[SymbolDeclaration],
        diagnostics: list[Diagnostic],
    ) -> None:
        self.declarations = declarations
        self.diagnostics = diagnostics

    def to_dict(self) -> dict[str, object]:
        return {
            "declarations": [declaration.to_dict() for declaration in self.declarations],
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


def parse_context_body(body: str, start_line: int) -> ContextDecl:
    declarations: list[SymbolDeclaration] = []
    diagnostics: list[Diagnostic] = []
    for offset, line in enumerate(body.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        line_number = start_line + offset
        match = _DECLARATION.match(stripped)
        if not match:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="INVALID_SYMBOL_DECLARATION",
                    message=f"Invalid symbol declaration '{stripped}'",
                    range=SourceRange(line_number, line_number + 1),
                )
            )
            continue
        names = [part.strip() for part in match.group(1).split(",")]
        type_name = match.group(2)
        tail = match.group(3)
        value_text, property_tail = _split_value(tail)
        property_names = re.findall(r"&\s*([A-Za-z]+)", property_tail)
        if type_name not in _TYPES:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="INVALID_SYMBOL_DECLARATION",
                    message=f"Unknown type '{type_name}'",
                    range=SourceRange(line_number, line_number + 1),
                )
            )
        for property_name in property_names:
            if property_name not in _PROPERTIES:
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="INVALID_SYMBOL_DECLARATION",
                        message=f"Unknown property '{property_name}'",
                        range=SourceRange(line_number, line_number + 1),
                    )
                )
        value = parse_value_expression(value_text) if value_text else None
        if value is not None:
            for diagnostic in validate_value(type_name, property_names, value):
                diagnostics.append(
                    Diagnostic(
                        severity=str(diagnostic.get("severity", "error")),
                        code=str(diagnostic.get("code", "")),
                        message=str(diagnostic.get("message", "")),
                        range=SourceRange(line_number, line_number + 1),
                    )
                )
        declarations.append(
            SymbolDeclaration(
                names=names,
                type_expression=TypeExpression(type_name),
                properties=[Property(name) for name in property_names],
                line=line_number,
                raw=stripped,
                value=value,
                value_text=value_text,
            )
        )
    return ContextDecl(declarations, diagnostics)


def _split_value(tail: str) -> tuple[str | None, str]:
    """Split `` & Positive = 0.01`` into (``0.01``, `` & Positive``).

    The ``=`` is found at the top level, ignoring brackets and quotes, so a list
    value such as ``= [0, 1]`` is preserved whole.
    """
    depth = 0
    quote: str | None = None
    for index, ch in enumerate(tail):
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "[(":
            depth += 1
        elif ch in "])":
            depth = max(0, depth - 1)
        elif ch == "=" and depth == 0:
            return tail[index + 1 :].strip(), tail[:index].strip()
    return None, tail.strip()
