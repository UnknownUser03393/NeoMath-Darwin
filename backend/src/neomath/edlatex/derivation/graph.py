from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neomath.edlatex.backends.base import BackendContext, StepClaim, VerificationResult
from neomath.edlatex.backends.registry import default_registry
from neomath.edlatex.context import ContextResolver
from neomath.edlatex.document import EdDocument
from neomath.edlatex.nodes import DerivationNode, FormulaNode


@dataclass
class GraphStep:
    node_id: str
    from_expr: str
    to_expr: str
    rule: str
    dependencies: list[str] = field(default_factory=list)
    verification: VerificationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodeId": self.node_id,
            "from": self.from_expr,
            "to": self.to_expr,
            "rule": self.rule,
            "dependencies": list(self.dependencies),
            "verification": self.verification.to_dict() if self.verification else None,
        }


@dataclass
class DerivationGraph:
    document: EdDocument
    steps: dict[str, GraphStep] = field(default_factory=dict)
    outgoing: dict[str, list[str]] = field(default_factory=dict)
    incoming: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._build()

    def _build(self) -> None:
        for node in self.document.iter_nodes():
            if isinstance(node, DerivationNode):
                deps = list(node.dependencies)
                if not deps and node.from_expr:
                    # Simple heuristic: if from_expr exactly matches a previous
                    # formula source, link to it. This keeps the graph useful for
                    # the linear notebook style without requiring explicit refs.
                    deps = self._infer_dependencies(node)
                step = GraphStep(
                    node_id=node.id,
                    from_expr=node.from_expr,
                    to_expr=node.to_expr,
                    rule=node.rule,
                    dependencies=deps,
                )
                self.steps[node.id] = step
                self.incoming.setdefault(node.id, [])
                for dep in deps:
                    self.outgoing.setdefault(dep, []).append(node.id)
                    self.incoming.setdefault(node.id, []).append(dep)

    def _infer_dependencies(self, node: DerivationNode) -> list[str]:
        matches: list[str] = []
        for prev in self.document.iter_nodes():
            if prev.id == node.id:
                break
            if isinstance(prev, FormulaNode) and (
                prev.source == node.from_expr or prev.parsed_expression == node.from_expr
            ):
                matches.append(prev.id)
        return matches[-1:]  # last matching formula is the immediate predecessor

    def topological_order(self) -> list[str]:
        # Graph is intentionally simple: use document order for the reachable subset.
        order: list[str] = []
        seen: set[str] = set()
        for node in self.document.iter_nodes():
            if node.id in self.steps and node.id not in seen:
                order.append(node.id)
                seen.add(node.id)
        return order

    def validate_all(self, backend_name: str = "sympy") -> dict[str, VerificationResult]:
        registry = default_registry()
        backend = registry.get(backend_name)
        if backend is None:
            raise ValueError(f"unknown backend: {backend_name}")
        resolver = ContextResolver(self.document)
        results: dict[str, VerificationResult] = {}
        for node_id in self.topological_order():
            step = self.steps[node_id]
            ctx = self._backend_context(resolver, node_id)
            claim = StepClaim(
                from_expr=step.from_expr,
                to_expr=step.to_expr,
                rule=step.rule,
                node_id=node_id,
                assumptions=self._assumptions_for_node(resolver, node_id),
            )
            verification = backend.validate(claim, ctx)
            step.verification = verification
            results[node_id] = verification
        return results

    def validate_step(self, node_id: str, backend_name: str = "sympy") -> VerificationResult:
        registry = default_registry()
        backend = registry.get(backend_name)
        if backend is None:
            raise ValueError(f"unknown backend: {backend_name}")
        step = self.steps[node_id]
        resolver = ContextResolver(self.document)
        claim = StepClaim(
            from_expr=step.from_expr,
            to_expr=step.to_expr,
            rule=step.rule,
            node_id=node_id,
            assumptions=self._assumptions_for_node(resolver, node_id),
        )
        verification = backend.validate(claim, self._backend_context(resolver, node_id))
        step.verification = verification
        return verification

    def earliest_fault(self) -> dict[str, Any] | None:
        results = self.validate_all()
        for node_id in self.topological_order():
            result = results.get(node_id)
            if result is None:
                continue
            if result.status in {"invalid", "unknown", "unverified"}:
                return {
                    "faultNodeId": node_id,
                    "status": result.status,
                    "message": result.message,
                    "rule": result.rule,
                }
        return None

    def blame_path(self, node_id: str) -> list[str]:
        path: list[str] = []
        current = node_id
        seen: set[str] = set()
        while current and current not in seen:
            seen.add(current)
            path.append(current)
            deps = self.incoming.get(current, [])
            current = deps[-1] if deps else ""
        path.reverse()
        return path

    def _backend_context(self, resolver: ContextResolver, node_id: str) -> BackendContext:
        ctx = BackendContext()
        effective = resolver.effective_context(node_id)
        for symbol, sc in effective.items():
            if sc.nonzero:
                ctx.nonzero_symbols.add(symbol)
            if sc.sign in {"positive", "nonnegative"}:
                ctx.nonnegative_symbols.add(symbol)
            if sc.domain:
                ctx.symbol_domains[symbol] = sc.domain
        return ctx

    def _assumptions_for_node(self, resolver: ContextResolver, node_id: str) -> list[str]:
        scope_id = resolver.tree.node_to_scope.get(node_id, "scope:document")
        chain = resolver.tree.chain(scope_id)
        assumptions: list[str] = []
        for scope in chain:
            for decl in scope.declarations:
                assumptions.append(decl.raw)
        return assumptions
