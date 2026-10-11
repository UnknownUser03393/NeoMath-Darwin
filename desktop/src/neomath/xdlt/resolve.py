"""Lexical scopes and math-symbol resolution.

Symbols are declared by ``#context`` blocks. Math expressions resolve bare
symbols (single letters and Greek spellings) against the enclosing scope chain:
document -> section -> semantic block -> context. The author never annotates
variables by hand; an undeclared symbol yields ``UNRESOLVED_SYMBOL``.
"""

from __future__ import annotations

from typing import Any

from neomath.xdlt.math.nodes import (
    MathDiagnostic,
    MathNode,
    MathRange,
    MultiplyNode,
    SymbolNode,
)
from neomath.xdlt.sel.nodes import (
    SelDiagnostic,
    SelNode,
    SelRange,
    SemanticReferenceNode,
)
from neomath.xdlt.sel.nodes import (
    SymbolNode as SelSymbolNode,
)
from neomath.xdlt.values.nodes import SemanticValue

_BUILTIN_SYMBOLS = {"pi": "pi", "infty": "infty"}


class SymbolDecl:
    __slots__ = ("name", "symbol_id", "type_expr", "properties", "line", "value", "value_text")

    def __init__(
        self,
        name: str,
        symbol_id: str,
        type_expr: str | None,
        properties: list[str],
        line: int,
        value: SemanticValue | None = None,
        value_text: str | None = None,
    ) -> None:
        self.name = name
        self.symbol_id = symbol_id
        self.type_expr = type_expr
        self.properties = list(properties)
        self.line = line
        self.value = value
        self.value_text = value_text

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "symbolId": self.symbol_id,
            "type": self.type_expr,
            "properties": list(self.properties),
            "line": self.line,
            "value": self.value.to_dict() if self.value is not None else None,
            "valueText": self.value_text,
        }


class Scope:
    def __init__(self, parent: "Scope | None", scope_id: str, kind: str) -> None:
        self.parent = parent
        self.scope_id = scope_id
        self.kind = kind
        self.symbols: dict[str, SymbolDecl] = {}

    def child(self, scope_id: str, kind: str) -> "Scope":
        return Scope(self, scope_id, kind)

    def declare(self, declaration: SymbolDecl) -> str:
        """Return ``ok``, ``duplicate`` (same scope) or ``shadowed`` (outer scope)."""
        if declaration.name in self.symbols:
            return "duplicate"
        status = "ok"
        if self._inherited(declaration.name):
            status = "shadowed"
        self.symbols[declaration.name] = declaration
        return status

    def _inherited(self, name: str) -> bool:
        scope = self.parent
        while scope is not None:
            if name in scope.symbols:
                return True
            scope = scope.parent
        return False

    def lookup(self, name: str) -> SymbolDecl | None:
        scope: Scope | None = self
        while scope is not None:
            if name in scope.symbols:
                return scope.symbols[name]
            scope = scope.parent
        return None

    def visible_symbols(self) -> dict[str, SymbolDecl]:
        """All declarations reachable from this scope, innermost winning."""
        result: dict[str, SymbolDecl] = {}
        scope: Scope | None = self
        while scope is not None:
            for name, declaration in scope.symbols.items():
                result.setdefault(name, declaration)
            scope = scope.parent
        return result


def resolve_symbols(root: MathNode, scope: Scope, diagnostics: list[MathDiagnostic]) -> None:
    """Bind every bare symbol in ``root`` to a declaration and emit diagnostics.

    A run of adjacent single-letter symbols that spells a *declared* name is
    merged into one symbol first (``alpha`` -> the declared ``alpha``), so a
    multi-letter identifier never silently becomes a product. TeX semantics are
    preserved: an undeclared run (``xy``) stays ``x * y``.
    """
    _merge_word_symbols(root, scope)
    for node in _math_descendants(root):
        if not isinstance(node, SymbolNode):
            continue
        builtin = _BUILTIN_SYMBOLS.get(node.name)
        if builtin is not None:
            node.symbol_id = f"sym:builtin/{builtin}"
            continue
        declaration = scope.lookup(node.name)
        if declaration is not None:
            node.symbol_id = declaration.symbol_id
        else:
            diagnostics.append(
                MathDiagnostic(
                    severity="warning",
                    code="UNRESOLVED_SYMBOL",
                    message=f"Unresolved symbol '{node.name}'",
                    range=MathRange(node.range.start, node.range.end),
                )
            )


def _merge_word_symbols(root: MathNode, scope: Scope) -> None:
    """Replace ``a * l * p * h * a`` with a single symbol when ``alpha`` is declared."""
    for node in _math_descendants(root):
        if not isinstance(node, MultiplyNode) or not node.operands:
            continue
        if not all(
            isinstance(operand, SymbolNode) and len(operand.name) == 1
            for operand in node.operands
        ):
            continue
        word = "".join(operand.name for operand in node.operands)
        declaration = scope.lookup(word)
        if declaration is None:
            continue
        merged = SymbolNode(
            word, word, node.source, node.range.start, node.range.end
        )
        merged.symbol_id = declaration.symbol_id
        node.operands = [merged]


def collect_symbol_refs(root: MathNode) -> list[str]:
    """Resolved symbol ids used anywhere in a math tree, in order."""
    refs: list[str] = []
    for node in _math_descendants(root):
        if isinstance(node, SymbolNode) and node.symbol_id:
            refs.append(node.symbol_id)
    return refs


def _math_descendants(root: MathNode) -> list[MathNode]:
    result: list[MathNode] = [root]
    for node in root.children():
        result.extend(_math_descendants(node))
    return result


def resolve_sel_symbols(root: SelNode, scope: Scope, diagnostics: list[SelDiagnostic]) -> None:
    """Bind bare symbols inside a SEL tree to the enclosing math scope."""
    for node in _sel_descendants(root):
        if not isinstance(node, SelSymbolNode):
            continue
        declaration = scope.lookup(node.name)
        if declaration is not None:
            node.symbol_id = declaration.symbol_id
        else:
            diagnostics.append(
                SelDiagnostic(
                    severity="warning",
                    code="UNRESOLVED_SYMBOL",
                    message=f"Unresolved symbol '{node.name}'",
                    range=SelRange(node.range.start, node.range.end),
                )
            )


def resolve_sel_references(
    root: SelNode,
    registry: dict[str, dict[str, Any]],
    diagnostics: list[SelDiagnostic],
) -> None:
    """Resolve ``#namespace:id`` references against the document entity registry."""
    for node in _sel_descendants(root):
        if not isinstance(node, SemanticReferenceNode):
            continue
        target = registry.get(node.name)
        if target is None:
            node.target_id = None
            node.target_type = None
            diagnostics.append(
                SelDiagnostic(
                    severity="error",
                    code="UNRESOLVED_SEMANTIC_REFERENCE",
                    message=f"Unresolved semantic reference '#{node.name}'",
                    range=SelRange(node.range.start, node.range.end),
                )
            )
        else:
            node.target_id = node.name
            node.target_type = target.get("type")


def _sel_descendants(root: SelNode) -> list[SelNode]:
    result: list[SelNode] = [root]
    for node in root.children():
        result.extend(_sel_descendants(node))
    return result
