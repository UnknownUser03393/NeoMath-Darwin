from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from time import perf_counter
from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    rationalize,
    standard_transformations,
)

from neomath.edlatex.backends.base import (
    STATUS_INVALID,
    STATUS_UNKNOWN,
    STATUS_VALID,
    STATUS_VALID_WITH_CONDITIONS,
    BackendContext,
    MathBackend,
    StepClaim,
    VerificationResult,
)
from neomath.edlatex.context.declarations import parse_declarations
from neomath.edlatex.derivation.rules import RULES, RuleSpec, rule_spec

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor, rationalize)


@dataclass
class ParsedEquation:
    lhs: sp.Expr
    rhs: sp.Expr


class SymPyBackend(MathBackend):
    name = "sympy"

    def capabilities(self) -> dict[str, Any]:
        return {
            "rules": list(RULES.keys()),
            "features": [
                "symbolic-equality",
                "solution-set-comparison",
                "differentiate",
                "integrate",
                "solve-equation",
                "context-aware-conditions",
            ],
        }

    def availability(self) -> tuple[bool, str]:
        try:
            _ = sp.__version__
            return True, ""
        except Exception as exc:  # pragma: no cover - import-level sanity
            return False, f"sympy unavailable: {exc}"

    def validate(
        self,
        claim: StepClaim,
        context: BackendContext | None = None,
        timeout: float = 5.0,
        cancel: Event | None = None,
    ) -> VerificationResult:
        context = _merge_claim_context(claim, context or BackendContext())
        spec = rule_spec(claim.rule)
        if spec is None:
            return VerificationResult(
                status=STATUS_UNKNOWN,
                rule=claim.rule,
                backend=self.name,
                message=f"Unknown rule: {claim.rule}",
                node_id=claim.node_id,
            )

        started = perf_counter()
        try:
            _check_abort(started, timeout, cancel)
            # Preserve original domain obligations before evaluate=True can erase them.
            for source in (claim.from_expr, claim.to_expr):
                for part in source.split("="):
                    if "{" in part or "}" in part:
                        continue
                    original = parse_expr(_normalize_text(part), transformations=_TRANSFORMS, evaluate=False)
                    if len(original.free_symbols) > 1:
                        return VerificationResult(status=STATUS_UNKNOWN, rule=claim.rule,
                            backend=self.name, method="capability-guard",
                            message="Multivariable verification is not fully supported")
                    for node in sp.preorder_traversal(original):
                        if isinstance(node, sp.Pow) and node.base.free_symbols and (
                            node.exp.is_integer is not True or node.exp.is_negative is True
                        ):
                            return VerificationResult(status=STATUS_UNKNOWN, rule=claim.rule,
                                backend=self.name, method="capability-guard",
                                message="Original domain/branch obligations are not fully verified")
            if claim.assumptions:
                # The existing context merger cannot represent general requirements.
                return VerificationResult(status=STATUS_UNKNOWN, rule=claim.rule,
                    backend=self.name, method="capability-guard",
                    message="Explicit assumptions require a complete assumption checker")
            result = _dispatch(self, claim, spec, context, started, timeout, cancel)
        except TimeoutError:
            return VerificationResult(
                status=STATUS_UNKNOWN,
                rule=claim.rule,
                backend=self.name,
                message="Timed out",
                node_id=claim.node_id,
                timed_out=True,
            )
        except Exception as exc:
            return VerificationResult(
                status=STATUS_UNKNOWN,
                rule=claim.rule,
                backend=self.name,
                message=f"sympy error: {exc}",
                node_id=claim.node_id,
            )
        if result.required_conditions:
            result.status = STATUS_UNKNOWN
            result.message = "Verification obligations have not been discharged: " + result.message
        result.node_id = claim.node_id
        return result


def _dispatch(
    backend: SymPyBackend,
    claim: StepClaim,
    spec: RuleSpec,
    context: BackendContext,
    started: float,
    timeout: float,
    cancel: Event | None,
) -> VerificationResult:
    if spec.category == "equivalence":
        if context.nonnegative_symbols or context.nonzero_symbols or context.symbol_domains:
            return VerificationResult(status=STATUS_UNKNOWN, rule=claim.rule,
                backend=backend.name, method="capability-guard",
                message="Context-aware equivalence is not fully supported")
        return _validate_equivalence(backend, claim, started, timeout, cancel)
    if spec.category == "equation_op":
        return _validate_equation_op(backend, claim, spec, context, started, timeout, cancel)
    if spec.category == "calculus":
        return _validate_calculus(backend, claim, started, timeout, cancel)
    if spec.category == "solve":
        return _validate_solve(backend, claim, context, started, timeout, cancel)
    return VerificationResult(
        status=STATUS_UNKNOWN,
        rule=claim.rule,
        backend=backend.name,
        message=f"Unsupported category {spec.category}",
    )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------
def _normalize_text(text: str) -> str:
    return (
        text.replace("\\left", "")
        .replace("\\right", "")
        .replace("\\,", "")
        .replace("\\cdot", "*")
        .replace("^", "**")
        .replace("\\", "")
        .strip()
    )


def _parse_expr(text: str) -> sp.Expr:
    return parse_expr(_normalize_text(text), transformations=_TRANSFORMS, evaluate=True)


def _parse_equation(text: str) -> ParsedEquation | None:
    if "=" not in text:
        return None
    lhs, rhs = text.split("=", 1)
    return ParsedEquation(lhs=_parse_expr(lhs), rhs=_parse_expr(rhs))


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------
def _merge_claim_context(claim: StepClaim, context: BackendContext) -> BackendContext:
    merged = BackendContext(
        nonzero_symbols=set(context.nonzero_symbols),
        nonnegative_symbols=set(context.nonnegative_symbols),
        symbol_domains=dict(context.symbol_domains),
    )
    for raw in claim.assumptions:
        for decl in parse_declarations(raw):
            for sym in decl.symbols:
                if decl.kind == "domain" and decl.domain:
                    merged.symbol_domains[sym] = decl.domain
                elif decl.kind == "sign":
                    if decl.sign in {"positive", "nonnegative"}:
                        merged.nonnegative_symbols.add(sym)
                    if decl.sign == "nonzero":
                        merged.nonzero_symbols.add(sym)
                    if decl.sign == "positive":
                        merged.nonzero_symbols.add(sym)
                elif decl.kind == "inequality" and _decl_nonzero_or_nonnegative(decl.raw):
                    merged.nonnegative_symbols.add(sym)
                elif decl.kind in {"value", "param"}:
                    for rel in decl.relations:
                        if rel.op == "=" and rel.bound.strip() != "0":
                            merged.nonzero_symbols.discard(sym)
    return merged


def _decl_nonzero_or_nonnegative(raw: str) -> bool:
    text = raw.replace(" ", "")
    return ">0" in text or ">=0" in text or "<0" in text or "<=0" in text


def _symbol_domain(symbol: sp.Symbol, context: BackendContext) -> sp.Set:
    domain = context.symbol_domains.get(symbol.name, "real")
    if domain == "integer":
        base: sp.Set = sp.S.Integers
    elif domain == "complex":
        base = sp.S.Complexes
    else:
        base = sp.S.Reals

    if symbol.name in context.nonzero_symbols:
        base = sp.Intersection(base, sp.Complement(sp.S.Reals, sp.FiniteSet(0)))
    if symbol.name in context.nonnegative_symbols:
        base = sp.Intersection(base, sp.Interval(0, sp.oo))
    return base


# ---------------------------------------------------------------------------
# Validation dispatch
# ---------------------------------------------------------------------------
def _validate_equivalence(
    backend: SymPyBackend,
    claim: StepClaim,
    started: float,
    timeout: float,
    cancel: Event | None,
) -> VerificationResult:
    left = _parse_expr(claim.from_expr)
    _check_abort(started, timeout, cancel)
    right = _parse_expr(claim.to_expr)
    _check_abort(started, timeout, cancel)

    if sp.simplify(left - right) == 0:
        return VerificationResult(
            status=STATUS_VALID,
            rule=claim.rule,
            backend=backend.name,
            method="simplify-diff",
            message="Expressions are equivalent",
        )

    verdict = _sample_equivalence(left, right, started, timeout, cancel)
    if verdict is False:
        return VerificationResult(
            status=STATUS_INVALID,
            rule=claim.rule,
            backend=backend.name,
            method="numeric-sampling",
            message="Expressions differ on sample points",
        )
    return VerificationResult(
        status=STATUS_UNKNOWN,
        rule=claim.rule,
        backend=backend.name,
        method="simplify-diff",
        message="sympy could not prove equivalence",
    )


def _validate_equation_op(
    backend: SymPyBackend,
    claim: StepClaim,
    spec: RuleSpec,
    context: BackendContext,
    started: float,
    timeout: float,
    cancel: Event | None,
) -> VerificationResult:
    before = _parse_equation(claim.from_expr)
    after = _parse_equation(claim.to_expr)
    if before is None or after is None:
        return VerificationResult(
            status=STATUS_UNKNOWN,
            rule=claim.rule,
            backend=backend.name,
            message="Expected equation forms",
        )

    before_set = _equation_solution_set(before, context, started, timeout, cancel)
    after_set = _equation_solution_set(after, context, started, timeout, cancel)
    if before_set is None or after_set is None:
        return VerificationResult(
            status=STATUS_UNKNOWN,
            rule=claim.rule,
            backend=backend.name,
            message="sympy could not compute equation solution sets",
        )

    if spec.id in {"add-both-sides", "subtract-both-sides"}:
        if before_set == after_set:
            return VerificationResult(
                status=STATUS_VALID,
                rule=claim.rule,
                backend=backend.name,
                method="solveset-compare",
                message="Both sides changed equivalently",
            )
        return VerificationResult(
            status=STATUS_INVALID,
            rule=claim.rule,
            backend=backend.name,
            method="solveset-compare",
            message="Addition/subtraction did not preserve the solution set",
        )

    if spec.id == "multiply-both-sides":
        if before_set == after_set:
            if _all_nonzero_in_context(before, context):
                return VerificationResult(
                    status=STATUS_VALID,
                    rule=claim.rule,
                    backend=backend.name,
                    method="solveset-compare",
                    message="Both sides were multiplied by a non-zero factor",
                )
            return VerificationResult(
                status=STATUS_VALID_WITH_CONDITIONS,
                rule=claim.rule,
                backend=backend.name,
                method="solveset-compare",
                required_conditions=["multiplier ≠ 0"],
                message="Multiplication is only conditionally valid",
            )
        if after_set.is_subset(before_set) is True:
            return VerificationResult(
                status=STATUS_VALID_WITH_CONDITIONS,
                rule=claim.rule,
                backend=backend.name,
                method="solveset-compare",
                required_conditions=["multiplier ≠ 0"],
                possible_lost_solutions=[_missing_solutions(before_set, after_set)],
                message="Multiplication lost solutions under a zero factor",
            )
        if after_set.is_superset(before_set) is True:
            return VerificationResult(
                status=STATUS_VALID_WITH_CONDITIONS,
                rule=claim.rule,
                backend=backend.name,
                method="solveset-compare",
                required_conditions=["multiplier ≠ 0"],
                possible_added_solutions=[_added_solutions(before_set, after_set)],
                message="Multiplication may have added solutions",
            )
        return VerificationResult(
            status=STATUS_INVALID,
            rule=claim.rule,
            backend=backend.name,
            method="solveset-compare",
            message="Multiplication changed the solution set in an unsupported way",
        )

    if spec.id == "divide-both-sides":
        if before_set == after_set:
            if _all_nonzero_in_context(before, context):
                return VerificationResult(
                    status=STATUS_VALID,
                    rule=claim.rule,
                    backend=backend.name,
                    method="solveset-compare",
                    message="Both sides were divided by a non-zero divisor",
                )
            return VerificationResult(
                status=STATUS_VALID_WITH_CONDITIONS,
                rule=claim.rule,
                backend=backend.name,
                method="solveset-compare",
                required_conditions=["divisor ≠ 0"],
                message="Division is only conditionally valid",
            )
        if after_set.is_subset(before_set) is True:
            return VerificationResult(
                status=STATUS_VALID_WITH_CONDITIONS,
                rule=claim.rule,
                backend=backend.name,
                method="solveset-compare",
                required_conditions=["divisor ≠ 0"],
                possible_lost_solutions=[_missing_solutions(before_set, after_set)],
                message="Division may have dropped solutions",
            )
        if after_set.is_superset(before_set) is True:
            return VerificationResult(
                status=STATUS_VALID_WITH_CONDITIONS,
                rule=claim.rule,
                backend=backend.name,
                method="solveset-compare",
                required_conditions=["divisor ≠ 0"],
                possible_added_solutions=[_added_solutions(before_set, after_set)],
                message="Division changed the solution set in a non-equivalent way",
            )
        return VerificationResult(
            status=STATUS_INVALID,
            rule=claim.rule,
            backend=backend.name,
            method="solveset-compare",
            message="Division changed the solution set in an unsupported way",
        )

    if spec.id == "square-both-sides":
        if before_set == after_set:
            return VerificationResult(
                status=STATUS_VALID,
                rule=claim.rule,
                backend=backend.name,
                method="solveset-compare",
                message="Squaring happened to preserve the solution set",
            )
        if after_set.is_superset(before_set) is True:
            return VerificationResult(
                status=STATUS_VALID_WITH_CONDITIONS,
                rule=claim.rule,
                backend=backend.name,
                method="solveset-compare",
                possible_added_solutions=[_added_solutions(before_set, after_set)],
                message="Squaring may introduce extraneous solutions",
            )
        if after_set.is_subset(before_set) is True:
            return VerificationResult(
                status=STATUS_VALID_WITH_CONDITIONS,
                rule=claim.rule,
                backend=backend.name,
                method="solveset-compare",
                possible_lost_solutions=[_missing_solutions(before_set, after_set)],
                message="Squaring lost solutions under the chosen domain",
            )
        return VerificationResult(
            status=STATUS_INVALID,
            rule=claim.rule,
            backend=backend.name,
            method="solveset-compare",
            message="Squaring changed the solution set inconsistently",
        )

    if spec.id == "take-square-root":
        if before_set == after_set:
            return VerificationResult(
                status=STATUS_VALID,
                rule=claim.rule,
                backend=backend.name,
                method="solveset-compare",
                message="Square-root step preserved the solution set",
            )
        if after_set.is_subset(before_set) is True:
            return VerificationResult(
                status=STATUS_VALID_WITH_CONDITIONS,
                rule=claim.rule,
                backend=backend.name,
                method="solveset-compare",
                possible_lost_solutions=[_missing_solutions(before_set, after_set)],
                message="Taking square roots may lose solutions",
            )
        if after_set.is_superset(before_set) is True:
            return VerificationResult(
                status=STATUS_VALID_WITH_CONDITIONS,
                rule=claim.rule,
                backend=backend.name,
                method="solveset-compare",
                possible_added_solutions=[_added_solutions(before_set, after_set)],
                message="Square-root step introduced extra solutions",
            )
        return VerificationResult(
            status=STATUS_INVALID,
            rule=claim.rule,
            backend=backend.name,
            method="solveset-compare",
            message="Square-root step changed the solution set inconsistently",
        )

    return VerificationResult(
        status=STATUS_UNKNOWN,
        rule=claim.rule,
        backend=backend.name,
        message="Rule not handled",
    )


def _validate_calculus(
    backend: SymPyBackend,
    claim: StepClaim,
    started: float,
    timeout: float,
    cancel: Event | None,
) -> VerificationResult:
    src = _parse_expr(claim.from_expr)
    _check_abort(started, timeout, cancel)
    dst = _parse_expr(claim.to_expr)
    _check_abort(started, timeout, cancel)
    x = _free_symbol(src, dst)
    if x is None:
        return VerificationResult(
            status=STATUS_UNKNOWN,
            rule=claim.rule,
            backend=backend.name,
            message="No free symbol found",
        )

    if claim.rule == "differentiate":
        if sp.simplify(sp.diff(src, x) - dst) == 0:
            return VerificationResult(
                status=STATUS_VALID,
                rule=claim.rule,
                backend=backend.name,
                method="sympy.diff",
                message="Derivative matches sympy",
            )
        verdict = _sample_equivalence(sp.diff(src, x), dst, started, timeout, cancel)
        if verdict is False:
            return VerificationResult(
                status=STATUS_INVALID,
                rule=claim.rule,
                backend=backend.name,
                message="Derivative mismatch",
            )
        return VerificationResult(
            status=STATUS_UNKNOWN,
            rule=claim.rule,
            backend=backend.name,
            message="sympy could not prove the derivative step",
        )

    if claim.rule == "integrate":
        if sp.simplify(sp.diff(dst, x) - src) == 0:
            return VerificationResult(
                status=STATUS_VALID,
                rule=claim.rule,
                backend=backend.name,
                method="antiderivative-check",
                message="Antiderivative differentiates back to the integrand",
            )
        verdict = _sample_equivalence(sp.diff(dst, x), src, started, timeout, cancel)
        if verdict is False:
            return VerificationResult(
                status=STATUS_INVALID,
                rule=claim.rule,
                backend=backend.name,
                message="Integral mismatch",
            )
        return VerificationResult(
            status=STATUS_UNKNOWN,
            rule=claim.rule,
            backend=backend.name,
            message="sympy could not prove the integral step",
        )

    return VerificationResult(
        status=STATUS_UNKNOWN,
        rule=claim.rule,
        backend=backend.name,
        message="Calculus rule not handled",
    )


def _validate_solve(
    backend: SymPyBackend,
    claim: StepClaim,
    context: BackendContext,
    started: float,
    timeout: float,
    cancel: Event | None,
) -> VerificationResult:
    eq = _parse_equation(claim.from_expr)
    if eq is None:
        return VerificationResult(
            status=STATUS_UNKNOWN,
            rule=claim.rule,
            backend=backend.name,
            message="Expected equation",
        )
    symbol = _free_symbol(eq.lhs, eq.rhs)
    if symbol is None:
        return VerificationResult(
            status=STATUS_UNKNOWN,
            rule=claim.rule,
            backend=backend.name,
            message="No symbol to solve",
        )

    target = _parse_solution_set(claim.to_expr)
    if target is None:
        return VerificationResult(
            status=STATUS_UNKNOWN,
            rule=claim.rule,
            backend=backend.name,
            message="Could not parse solution set",
        )
    solved = _equation_solution_set(eq, context, started, timeout, cancel)
    if solved is None:
        return VerificationResult(
            status=STATUS_UNKNOWN,
            rule=claim.rule,
            backend=backend.name,
            message="sympy could not compute the solution set",
        )

    if solved == target:
        return VerificationResult(
            status=STATUS_VALID,
            rule=claim.rule,
            backend=backend.name,
            method="solveset-compare",
            message="Solution sets match",
        )
    if solved.is_subset(target) is True and solved != target:
        return VerificationResult(
            status=STATUS_INVALID,
            rule=claim.rule,
            backend=backend.name,
            method="solveset-compare",
            possible_added_solutions=[_added_solutions(solved, target)],
            message="Solution set adds extra solutions",
        )
    if solved.is_superset(target) is True and solved != target:
        return VerificationResult(
            status=STATUS_INVALID,
            rule=claim.rule,
            backend=backend.name,
            method="solveset-compare",
            possible_lost_solutions=[_missing_solutions(solved, target)],
            message="Solution set is missing one or more solutions",
        )
    return VerificationResult(
        status=STATUS_UNKNOWN,
        rule=claim.rule,
        backend=backend.name,
        method="solveset-compare",
        message="Solution sets do not match",
    )


# ---------------------------------------------------------------------------
# Set helpers
# ---------------------------------------------------------------------------
def _equation_solution_set(
    eq: ParsedEquation,
    context: BackendContext,
    started: float,
    timeout: float,
    cancel: Event | None,
) -> sp.Set | None:
    symbol = _free_symbol(eq.lhs, eq.rhs)
    if symbol is None:
        return None
    domain = _symbol_domain(symbol, context)
    _check_abort(started, timeout, cancel)
    solved = sp.solveset(sp.Eq(eq.lhs, eq.rhs), symbol, domain=domain)
    if solved.has(sp.ConditionSet):
        return None
    return solved


def _parse_solution_set(text: str) -> sp.Set | None:
    text = text.strip().replace(" ", "")
    result: sp.Set | None
    if text in {"∅", "empty", "EmptySet"}:
        result = sp.EmptySet
    elif text in {"R", "ℝ", "Reals"}:
        result = sp.S.Reals
    elif text in {"Z", "ℤ", "Integers"}:
        result = sp.S.Integers
    elif text.startswith("{") and text.endswith("}"):
        inner = text[1:-1].strip()
        if not inner:
            result = sp.EmptySet
        else:
            items = [
                parse_expr(part, transformations=_TRANSFORMS, evaluate=True)
                for part in inner.split(",")
            ]
            result = sp.FiniteSet(*items)
    else:
        result = None
    return result


# ---------------------------------------------------------------------------
# Symbol / relation helpers
# ---------------------------------------------------------------------------
def _free_symbol(*exprs: sp.Expr) -> sp.Symbol | None:
    symbols_seen: list[sp.Symbol] = []
    for expr in exprs:
        symbols_seen.extend(sorted(expr.free_symbols, key=lambda s: s.name))
    if not symbols_seen:
        return None
    return symbols_seen[0]


def _known_zero(expr: sp.Expr) -> bool:
    simplified = sp.simplify(expr)
    eq_zero = simplified.equals(0)
    return bool(expr == 0 or expr.is_zero is True or bool(eq_zero))


def _known_nonzero(expr: sp.Expr, context: BackendContext) -> bool:
    if expr.is_number:
        return bool(expr != 0)
    if expr.is_Symbol and expr.name in context.nonzero_symbols:
        return True
    if expr.is_Mul:
        return bool(all(_known_nonzero(arg, context) for arg in expr.args))
    if expr.is_Pow and expr.exp.is_Integer and expr.exp > 0:
        return _known_nonzero(expr.base, context)
    return bool(expr.is_zero is False or expr.is_nonzero is True)




def _missing_solutions(before: Any, after: Any) -> str:
    diff = before - after
    return str(diff)


def _added_solutions(before: Any, after: Any) -> str:
    diff = after - before
    return str(diff)


# ---------------------------------------------------------------------------
# Equivalence sampling and abort handling
# ---------------------------------------------------------------------------
def _all_nonzero_in_context(eq: ParsedEquation, context: BackendContext) -> bool:
    symbols = sorted(eq.lhs.free_symbols | eq.rhs.free_symbols, key=lambda s: s.name)
    return bool(symbols) and all(
        sym.name in context.nonzero_symbols
        for sym in symbols
    )


def _sample_equivalence(
    left: sp.Expr,
    right: sp.Expr,
    started: float,
    timeout: float,
    cancel: Event | None,
) -> bool | None:
    symbols_seen = sorted((left.free_symbols | right.free_symbols), key=lambda s: s.name)
    if not symbols_seen:
        return bool(sp.simplify(left - right) == 0)
    samples = [1, 2, 3, -1, sp.Rational(1, 2)]
    for sample in samples:
        _check_abort(started, timeout, cancel)
        subs = {s: sample for s in symbols_seen}
        try:
            lv = sp.simplify(left.subs(subs))
            rv = sp.simplify(right.subs(subs))
            if (lv.is_number and rv.is_number and lv.is_finite is True and rv.is_finite is True
                    and sp.simplify(lv - rv).is_zero is False):
                return False
        except Exception:
            continue
    return None


def _check_abort(started: float, timeout: float, cancel: Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise TimeoutError("cancelled")
    if timeout > 0 and perf_counter() - started > timeout:
        raise TimeoutError("timeout")
