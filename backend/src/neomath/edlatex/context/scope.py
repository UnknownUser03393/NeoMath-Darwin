from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import sympy

from neomath.edlatex.context.declarations import Declaration, Relation, parse_declarations
from neomath.edlatex.document import EdDocument
from neomath.edlatex.nodes import ContextNode, DerivationNode, SectionNode

ROOT_SCOPE_ID = "scope:document"


# ---------------------------------------------------------------------------
# Scope tree
# ---------------------------------------------------------------------------
@dataclass
class Scope:
    id: str
    kind: str  # document | section | derivation
    parent_id: str | None
    node_id: str | None = None
    level: int = 0
    child_ids: list[str] = field(default_factory=list)
    member_node_ids: list[str] = field(default_factory=list)
    declarations: list[Declaration] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "parentId": self.parent_id,
            "nodeId": self.node_id,
            "level": self.level,
            "childIds": list(self.child_ids),
            "memberNodeIds": list(self.member_node_ids),
            "declarations": [d.to_dict() for d in self.declarations],
        }


class ScopeTree:
    """Derives Document -> Section -> Derivation scopes from the flat node list.

    A ``ContextNode``'s declarations attach to the scope it sits in. A section
    heading opens a scope that stays active until a heading of equal or higher
    level. A derivation opens its own leaf scope so it can carry local
    assumptions without leaking them to siblings.
    """

    def __init__(self, document: EdDocument) -> None:
        self.scopes: dict[str, Scope] = {}
        self.node_to_scope: dict[str, str] = {}
        self._build(document)

    def _build(self, document: EdDocument) -> None:
        root = Scope(id=ROOT_SCOPE_ID, kind="document", parent_id=None, level=0)
        self.scopes[root.id] = root
        stack: list[Scope] = [root]

        for node in document.iter_nodes():
            if isinstance(node, SectionNode):
                while stack[-1].kind == "section" and stack[-1].level >= node.level:
                    stack.pop()
                parent = stack[-1]
                scope = Scope(
                    id=f"scope:{node.id}",
                    kind="section",
                    parent_id=parent.id,
                    node_id=node.id,
                    level=node.level,
                )
                parent.child_ids.append(scope.id)
                self.scopes[scope.id] = scope
                # The heading node itself belongs to the parent scope.
                self.node_to_scope[node.id] = parent.id
                parent.member_node_ids.append(node.id)
                stack.append(scope)
                continue

            current = stack[-1]

            if isinstance(node, DerivationNode):
                scope = Scope(
                    id=f"scope:{node.id}",
                    kind="derivation",
                    parent_id=current.id,
                    node_id=node.id,
                    level=current.level + 1,
                )
                current.child_ids.append(scope.id)
                self.scopes[scope.id] = scope
                self.node_to_scope[node.id] = scope.id
                scope.member_node_ids.append(node.id)
                for assumption in node.assumptions:
                    for decl in parse_declarations(assumption):
                        decl.source_scope_id = scope.id
                        decl.source_node_id = node.id
                        scope.declarations.append(decl)
                continue

            self.node_to_scope[node.id] = current.id
            current.member_node_ids.append(node.id)
            if isinstance(node, ContextNode):
                for raw in node.declarations:
                    for decl in parse_declarations(raw):
                        decl.source_scope_id = current.id
                        decl.source_node_id = node.id
                        current.declarations.append(decl)

    # --- navigation ---------------------------------------------------
    def chain(self, scope_id: str) -> list[Scope]:
        """Root -> ... -> scope."""
        result: list[Scope] = []
        current: str | None = scope_id
        while current is not None:
            scope = self.scopes.get(current)
            if scope is None:
                break
            result.append(scope)
            current = scope.parent_id
        result.reverse()
        return result

    def subtree_node_ids(self, scope_id: str) -> set[str]:
        """All node ids governed by ``scope_id`` or any descendant scope."""
        out: set[str] = set()
        stack = [scope_id]
        while stack:
            scope = self.scopes.get(stack.pop())
            if scope is None:
                continue
            out.update(scope.member_node_ids)
            stack.extend(scope.child_ids)
        return out


# ---------------------------------------------------------------------------
# Effective context + conflicts
# ---------------------------------------------------------------------------
@dataclass
class SymbolContext:
    symbol: str
    domain: str | None = None
    sign: str | None = None
    value: str | None = None
    lower: str | None = None  # "a" with lower_strict
    lower_strict: bool = False
    upper: str | None = None
    upper_strict: bool = False
    nonzero: bool = False
    label: str | None = None

    def summary(self) -> str:
        parts: list[str] = []
        dom = {"real": "ℝ", "integer": "ℤ", "complex": "ℂ"}.get(self.domain or "", "")
        if dom:
            parts.append(f"{self.symbol} ∈ {dom}")
        if self.value is not None:
            parts.append(f"{self.symbol} = {self.value}")
        elif self.lower is not None or self.upper is not None:
            lo = self.lower if self.lower is not None else "-∞"
            hi = self.upper if self.upper is not None else "+∞"
            lb = "[" if (self.lower is not None and not self.lower_strict) else "("
            rb = "]" if (self.upper is not None and not self.upper_strict) else ")"
            parts.append(f"{self.symbol} ∈ {lb}{lo}, {hi}{rb}")
        elif self.sign:
            parts.append(f"{self.symbol} {self.sign}")
        if self.nonzero and self.value is None:
            parts.append(f"{self.symbol} ≠ 0")
        return " ∧ ".join(parts) if parts else self.symbol

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "domain": self.domain,
            "sign": self.sign,
            "value": self.value,
            "lower": self.lower,
            "lowerStrict": self.lower_strict,
            "upper": self.upper,
            "upperStrict": self.upper_strict,
            "nonzero": self.nonzero,
            "label": self.label,
            "summary": self.summary(),
        }


@dataclass
class Conflict:
    symbol: str
    code: str
    message: str
    conditions: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)  # scope ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "code": self.code,
            "message": self.message,
            "conditions": list(self.conditions),
            "sources": list(self.sources),
        }


def _num(text: str) -> sympy.Expr | None:
    try:
        expr = sympy.sympify(text, rational=True)
    except (sympy.SympifyError, TypeError, ValueError, SyntaxError):
        return None
    return expr if expr.is_number else None


class ContextResolver:
    """Resolves effective context per node and detects contradictions.

    Override rules: ``domain``, ``sign`` and ``value`` are overridden by the
    innermost scope; inequality bounds accumulate (intervals intersect) down the
    chain. Conflicts are detected on the merged result, so a local ``x = -1``
    still contradicts an inherited ``x > 0`` (a value never removes an inherited
    constraint).
    """

    def __init__(self, document: EdDocument) -> None:
        self.document = document
        self.tree = ScopeTree(document)

    # --- per-symbol merge --------------------------------------------
    def _merge(self, scope_id: str) -> tuple[dict[str, SymbolContext], dict[str, list[str]]]:
        symbols: dict[str, SymbolContext] = {}
        provenance: dict[str, list[str]] = {}

        def ctx(sym: str) -> SymbolContext:
            if sym not in symbols:
                symbols[sym] = SymbolContext(symbol=sym)
                provenance[sym] = []
            return symbols[sym]

        for scope in self.tree.chain(scope_id):
            for decl in scope.declarations:
                for sym in decl.symbols:
                    c = ctx(sym)
                    provenance[sym].append(scope.id)
                    _apply(c, decl)
        return symbols, provenance

    def _apply_to_ctx(self, scope_id: str) -> dict[str, SymbolContext]:
        return self._merge(scope_id)[0]

    # --- public API ---------------------------------------------------
    def effective_context(self, node_id: str) -> dict[str, SymbolContext]:
        scope_id = self.tree.node_to_scope.get(node_id, ROOT_SCOPE_ID)
        return self._apply_to_ctx(scope_id)

    def conflicts_for_scope(self, scope_id: str) -> list[Conflict]:
        symbols, provenance = self._merge(scope_id)
        out: list[Conflict] = []
        for sym, c in symbols.items():
            conflict = _detect_conflict(c)
            if conflict is not None:
                conflict.sources = sorted(set(provenance.get(sym, [])))
                out.append(conflict)
        return out

    def conflicts_for_node(self, node_id: str) -> list[Conflict]:
        scope_id = self.tree.node_to_scope.get(node_id, ROOT_SCOPE_ID)
        return self.conflicts_for_scope(scope_id)

    def badge(self, node_id: str) -> str:
        symbols = self.effective_context(node_id)
        segments = [c.summary() for c in symbols.values()]
        state = "冲突" if self.conflicts_for_node(node_id) else "一致"
        return " | ".join(segments + [state]) if segments else state

    def all_conflicts(self) -> list[Conflict]:
        """Conflicts across every scope that has declarations (Problems panel)."""
        seen: set[tuple[str, str, str]] = set()
        out: list[Conflict] = []
        for scope_id, scope in self.tree.scopes.items():
            if not scope.declarations and scope.kind != "derivation":
                continue
            for conflict in self.conflicts_for_scope(scope_id):
                key = (scope_id, conflict.symbol, conflict.code)
                if key not in seen:
                    seen.add(key)
                    out.append(conflict)
        return out

    def uses_of_symbol(self, symbol: str, scope_id: str) -> list[str]:
        """Node ids in the scope subtree whose math references ``symbol``."""
        result: list[str] = []
        for node_id in self.tree.subtree_node_ids(scope_id):
            node = self.document.get_node(node_id)
            if node is None:
                continue
            haystack = f"{node.source} {getattr(node, 'parsed_expression', '') or ''}"
            haystack += " ".join(getattr(node, "symbol_references", []) or [])
            if _mentions(symbol, haystack):
                result.append(node_id)
        return result

    def inspect(self, node_id: str) -> dict[str, Any]:
        scope_id = self.tree.node_to_scope.get(node_id, ROOT_SCOPE_ID)
        chain = self.tree.chain(scope_id)
        symbols, provenance = self._merge(scope_id)
        conflicts = self.conflicts_for_scope(scope_id)

        # Overrides: a symbol whose domain/sign/value was set in more than one
        # scope — the innermost wins, the outer ones are shown as overridden.
        overrides: list[dict[str, Any]] = []
        for scope in chain:
            for decl in scope.declarations:
                for sym in decl.symbols:
                    if decl.kind in {"domain", "sign", "value", "param"}:
                        inner = _innermost_scope_for(chain, sym, decl.kind)
                        if inner is not None and inner != scope.id:
                            overrides.append(
                                {
                                    "symbol": sym,
                                    "kind": decl.kind,
                                    "overriddenScope": scope.id,
                                    "byScope": inner,
                                }
                            )

        return {
            "nodeId": node_id,
            "scopeId": scope_id,
            "badge": self.badge(node_id),
            "inheritance": [
                {"scopeId": s.id, "kind": s.kind, "nodeId": s.node_id} for s in chain
            ],
            "declarations": [
                {**d.to_dict(), "scopeId": s.id}
                for s in chain
                for d in s.declarations
            ],
            "effectiveContext": {sym: c.to_dict() for sym, c in symbols.items()},
            "provenance": provenance,
            "overrides": overrides,
            "conflicts": [c.to_dict() for c in conflicts],
            "usedBy": {
                sym: self.uses_of_symbol(sym, self._declaring_scope(sym, chain))
                for sym in symbols
            },
        }

    def _declaring_scope(self, symbol: str, chain: list[Scope]) -> str:
        for scope in chain:  # outermost declaring scope governs the widest usage
            if any(symbol in d.symbols for d in scope.declarations):
                return scope.id
        return chain[0].id if chain else ROOT_SCOPE_ID

    # --- incremental --------------------------------------------------
    def affected_node_ids(self, scope_id: str) -> set[str]:
        """Nodes that must be re-validated when ``scope_id`` changes.

        Only the scope's own subtree is affected — ancestors and sibling
        subtrees are untouched, so callers never need to recompute everything.
        """
        return self.tree.subtree_node_ids(scope_id)

    def recompute(self, scope_id: str) -> dict[str, list[dict[str, Any]]]:
        """Re-resolve conflicts for exactly the affected nodes (no global sweep)."""
        result: dict[str, list[dict[str, Any]]] = {}
        for node_id in sorted(self.affected_node_ids(scope_id)):
            result[node_id] = [c.to_dict() for c in self.conflicts_for_node(node_id)]
        return result


def _innermost_scope_for(chain: list[Scope], symbol: str, kind: str) -> str | None:
    found: str | None = None
    for scope in chain:  # chain is root->leaf, so the last match is innermost
        for decl in scope.declarations:
            if symbol in decl.symbols and decl.kind == kind:
                found = scope.id
    return found


def _apply(c: SymbolContext, decl: Declaration) -> None:
    if decl.kind == "domain":
        c.domain = decl.domain  # innermost wins
    elif decl.kind == "sign":
        c.sign = decl.sign  # innermost wins
        if decl.sign == "nonzero":
            c.nonzero = True
    elif decl.kind in {"value", "param"}:
        for rel in decl.relations:
            if rel.op == "=":
                c.value = rel.bound  # innermost value wins
        if decl.label:
            c.label = decl.label
    elif decl.kind == "inequality":
        for rel in decl.relations:
            _tighten(c, rel)


def _tighten(c: SymbolContext, rel: Relation) -> None:
    val = _num(rel.bound)
    if val is None:
        return
    if rel.op in (">", ">="):
        strict = rel.op == ">"
        if c.lower is None or _num(c.lower) is None or val > _num(c.lower):  # type: ignore[operator]
            c.lower, c.lower_strict = rel.bound, strict
        elif val == _num(c.lower) and strict:
            c.lower_strict = True
    elif rel.op in ("<", "<="):
        strict = rel.op == "<"
        if c.upper is None or _num(c.upper) is None or val < _num(c.upper):  # type: ignore[operator]
            c.upper, c.upper_strict = rel.bound, strict
        elif val == _num(c.upper) and strict:
            c.upper_strict = True


def _domain_set(domain: str | None) -> Any:
    """Base solution set for the declared number domain."""
    if domain == "integer":
        return sympy.S.Integers
    if domain == "complex":
        return sympy.S.Complexes
    return sympy.S.Reals


def _solution_set(c: SymbolContext) -> tuple[Any, bool]:
    """Build the symbol's solution set as a sympy Set (the real satisfiability
    model). Returns (set, has_numeric_value); set is None when a symbolic value
    makes the question undecidable."""
    sets: list[Any] = [_domain_set(c.domain)]

    if c.sign == "positive":
        sets.append(sympy.Interval.open(0, sympy.oo))
    elif c.sign == "negative":
        sets.append(sympy.Interval.open(-sympy.oo, 0))
    elif c.sign == "nonnegative":
        sets.append(sympy.Interval(0, sympy.oo))
    if c.nonzero or c.sign == "nonzero":
        sets.append(sympy.Complement(sympy.S.Reals, sympy.FiniteSet(0)))

    lo = _num(c.lower) if c.lower is not None else None
    hi = _num(c.upper) if c.upper is not None else None
    if lo is not None or hi is not None:
        left = lo if lo is not None else -sympy.oo
        right = hi if hi is not None else sympy.oo
        left_open = c.lower_strict if lo is not None else True
        right_open = c.upper_strict if hi is not None else True
        sets.append(sympy.Interval(left, right, left_open, right_open))

    has_value = False
    if c.value is not None:
        val = _num(c.value)
        if val is None:
            return None, False  # symbolic value -> undecidable
        sets.append(sympy.FiniteSet(val))
        has_value = True

    return sympy.Intersection(*sets), has_value


def _detect_conflict(c: SymbolContext) -> Conflict | None:
    """A conflict exists iff sympy proves the solution set empty.

    sympy is the decider: an unproven / undecidable set (``is_empty`` None) is
    reported as no-conflict, never as an error.
    """
    solution, has_value = _solution_set(c)
    if solution is None or solution.is_empty is not True:
        return None

    if has_value and c.value is not None:
        value = _num(c.value)
        # Which constraint emptied the set? (messaging only; the decision above
        # was sympy's.)
        if sympy.Intersection(sympy.FiniteSet(value), _domain_set(c.domain)).is_empty is True:
            dom = {"integer": "ℤ", "real": "ℝ", "complex": "ℂ"}.get(c.domain or "", "该数域")
            return Conflict(
                symbol=c.symbol,
                code="VALUE_NOT_IN_DOMAIN",
                message=f"{c.symbol} = {c.value} 不在声明数域 {dom} 内",
                conditions=[f"{c.symbol} ∈ {dom}", f"{c.symbol} = {c.value}"],
            )
        if (c.nonzero or c.sign == "nonzero") and value == 0:
            return Conflict(
                symbol=c.symbol,
                code="VALUE_VIOLATES_SIGN",
                message=f"{c.symbol} = 0 与 {c.symbol} ≠ 0 矛盾",
                conditions=[f"{c.symbol} ≠ 0", f"{c.symbol} = {c.value}"],
            )
        bound = _describe_bounds(c)
        return Conflict(
            symbol=c.symbol,
            code="VALUE_VIOLATES_BOUND",
            message=f"{c.symbol} = {c.value} 不满足约束 {bound}",
            conditions=[bound, f"{c.symbol} = {c.value}"],
        )

    return Conflict(
        symbol=c.symbol,
        code="EMPTY_INTERVAL",
        message=f"{c.symbol} 的约束相互矛盾，解集为空（{c.summary()}）",
        conditions=[c.summary()],
    )


def _describe_bounds(c: SymbolContext) -> str:
    """Human-readable description of just the numeric bounds/sign on a symbol."""
    parts: list[str] = []
    if c.lower is not None:
        parts.append(f"{c.symbol} {'>' if c.lower_strict else '≥'} {c.lower}")
    if c.upper is not None:
        parts.append(f"{c.symbol} {'<' if c.upper_strict else '≤'} {c.upper}")
    if c.sign and not parts:
        parts.append(f"{c.symbol} {c.sign}")
    return " ∧ ".join(parts) if parts else c.symbol


def _mentions(symbol: str, text: str) -> bool:
    import re

    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(symbol)}(?![A-Za-z0-9_])", text) is not None
