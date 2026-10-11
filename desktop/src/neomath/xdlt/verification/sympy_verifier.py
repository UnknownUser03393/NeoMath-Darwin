"""SymPy-backed assertion verifier.

SEL semantic IR is translated to SymPy values and checked. Requirements become
SymPy symbol assumptions (``x >= 0`` -> ``nonnegative``). ``unknown`` is never
treated as ``invalid``.
"""

from __future__ import annotations

from typing import Any, Callable

import sympy as sp
from sympy.core.relational import Relational
from sympy.logic.boolalg import BooleanFunction

from neomath.xdlt.verification.errors import (
    CannotDecideError,
    InvalidReferenceTypeError,
    UnresolvedReferenceError,
    UnsupportedOperationError,
)
from neomath.xdlt.verification.protocol import VerificationContext, VerificationResult
from neomath.xdlt.verification.sel_convert import sel_ir_to_value

_TYPE_KWARGS: dict[str, dict[str, bool]] = {
    "Real": {"real": True},
    "Complex": {},
    "Integer": {"integer": True},
    "Natural": {"integer": True, "nonnegative": True},
}

_PROPERTY_KWARGS: dict[str, dict[str, bool]] = {
    "Positive": {"positive": True},
    "NonNegative": {"nonnegative": True},
    "NonZero": {"nonzero": True},
}

_REQUIREMENT_TO_ASSUMPTION: dict[str, dict[str, bool]] = {
    ">=": {"nonnegative": True},
    ">": {"positive": True},
    "<=": {"nonpositive": True},
    "<": {"negative": True},
    "!=": {"nonzero": True},
}

_STATUS_MESSAGES = {
    "valid": "claim holds",
    "valid-with-conditions": "claim holds under the stated requirements",
    "invalid": "claim is false",
    "unknown": "backend could not decide",
    "error": "verification failed",
    "unverified": "not verified",
}


class SymPyVerifier:
    name = "sympy"
    version = sp.__version__

    def verify(
        self,
        claim: dict[str, Any] | None,
        requirements: list[dict[str, Any]],
        context: VerificationContext,
    ) -> VerificationResult:
        diagnostics: list[dict[str, Any]] = []
        if claim is None:
            return VerificationResult(
                status="error",
                verifier=self.name,
                message="assertion has no claim",
                diagnostics=[
                    {
                        "severity": "error",
                        "code": "MISSING_CLAIM",
                        "message": "assertion has no claim",
                    }
                ],
                assertion_id=context.assertion_id,
            )

        context_assumptions = _context_assumptions(context)
        requirement_assumptions, requirement_sources, unsupported = _requirement_assumptions(
            requirements
        )
        for source in unsupported:
            diagnostics.append(
                {
                    "severity": "warning",
                    "code": "UNSUPPORTED_VERIFICATION_REQUIREMENT",
                    "message": f"requirement '{source}' could not be converted to assumptions",
                }
            )

        if requirement_sources:
            status, error_diagnostic = self._verify_with_assumptions(
                claim, context, context_assumptions, requirement_assumptions
            )
            if status == "valid":
                status = "valid-with-conditions"
            elif status == "unknown":
                # Maybe the requirements are unnecessary: try without them.
                without, _ = self._verify_with_assumptions(claim, context, context_assumptions, {})
                if without == "valid":
                    status = "valid"
        else:
            status, error_diagnostic = self._verify_with_assumptions(
                claim, context, context_assumptions, requirement_assumptions
            )
        if error_diagnostic is not None:
            diagnostics.append(error_diagnostic)

        return VerificationResult(
            status=status,
            verifier=self.name,
            message=_STATUS_MESSAGES.get(status, status),
            conditions=list(requirement_sources),
            diagnostics=diagnostics,
            evidence={"claimKind": claim.get("kind")},
            assertion_id=context.assertion_id,
        )

    def _verify_with_assumptions(
        self,
        claim: dict[str, Any],
        context: VerificationContext,
        context_assumptions: dict[str, dict[str, bool]],
        requirement_assumptions: dict[str, dict[str, bool]],
    ) -> tuple[str, dict[str, Any] | None]:
        symbol_getter = _make_symbol_getter(context_assumptions, requirement_assumptions)
        try:
            value = sel_ir_to_value(claim, context.referenced_entities, symbol_getter)
        except CannotDecideError:
            return "unknown", None
        except UnresolvedReferenceError as error:
            return "error", _error_diagnostic("UNRESOLVED_SEMANTIC_REFERENCE", str(error))
        except InvalidReferenceTypeError as error:
            return "error", _error_diagnostic("INVALID_SEMANTIC_REFERENCE_TYPE", str(error))
        except UnsupportedOperationError as error:
            return "error", _error_diagnostic("SEL_UNSUPPORTED_OPERATION", str(error))
        except Exception as error:  # noqa: BLE001 - backend failure is an error status
            return "error", _error_diagnostic("VERIFY_BACKEND_ERROR", f"sympy error: {error}")
        return _check_value(value), None


def _context_assumptions(context: VerificationContext) -> dict[str, dict[str, bool]]:
    result: dict[str, dict[str, bool]] = {}
    for name, declaration in context.symbol_declarations.items():
        kwargs: dict[str, bool] = {}
        type_expr = declaration.get("type")
        if type_expr in _TYPE_KWARGS:
            kwargs.update(_TYPE_KWARGS[type_expr])
        for property_name in declaration.get("properties", []):
            if property_name in _PROPERTY_KWARGS:
                kwargs.update(_PROPERTY_KWARGS[property_name])
        result[name] = kwargs
    return result


def _requirement_assumptions(
    requirements: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, bool]], list[str], list[str]]:
    assumptions: dict[str, dict[str, bool]] = {}
    sources: list[str] = []
    unsupported: list[str] = []
    for requirement in requirements:
        if requirement["kind"] != "comparison":
            unsupported.append(requirement.get("raw", requirement["kind"]))
            continue
        operator = requirement["operator"]
        left = requirement["left"]
        right = requirement["right"]
        if left["kind"] == "symbol" and _is_zero_literal(right):
            name = left["name"]
        elif right["kind"] == "symbol" and _is_zero_literal(left):
            name = right["name"]
            operator = _flip_operator(operator)
        else:
            unsupported.append(requirement.get("raw", "requirement"))
            continue
        if operator in _REQUIREMENT_TO_ASSUMPTION:
            assumptions.setdefault(name, {}).update(_REQUIREMENT_TO_ASSUMPTION[operator])
            sources.append(requirement.get("raw", f"{name} {operator} 0"))
        else:
            unsupported.append(requirement.get("raw", f"{name} {operator} 0"))
    return assumptions, sources, unsupported


def _is_zero_literal(ir: dict[str, Any]) -> bool:
    return (
        ir["kind"] == "literal"
        and ir["valueType"] in ("integer", "real")
        and float(ir["value"]) == 0.0
    )


def _flip_operator(operator: str) -> str:
    return {"<": ">", "<=": ">=", ">": "<", ">=": "<="}.get(operator, operator)


def _make_symbol_getter(
    context_assumptions: dict[str, dict[str, bool]],
    requirement_assumptions: dict[str, dict[str, bool]],
) -> Callable[[str], sp.Symbol]:
    cache: dict[str, sp.Symbol] = {}

    def getter(name: str) -> sp.Symbol:
        if name in cache:
            return cache[name]
        kwargs: dict[str, bool] = {}
        kwargs.update(context_assumptions.get(name, {}))
        kwargs.update(requirement_assumptions.get(name, {}))
        symbol = sp.Symbol(name, **kwargs)
        cache[name] = symbol
        return symbol

    return getter


def _check_value(value: Any) -> str:
    if value == sp.true:
        return "valid"
    if value == sp.false:
        return "invalid"
    if isinstance(value, Relational):
        if getattr(value, "rel_op", None) == "==":
            try:
                diff = sp.simplify(value.lhs - value.rhs)
            except Exception:  # noqa: BLE001 - fall back to equals()
                diff = None
            if diff is not None and diff == 0:
                return "valid"
            if diff is not None and diff.is_number:  # a non-zero constant is a counterexample
                return "invalid"
            equality = value.lhs.equals(value.rhs)
            if equality is True:
                return "valid"
            if equality is False:
                return "invalid"
            return "unknown"
        # Strict/weak inequalities are only decidable when the backend already
        # evaluated them to a concrete boolean (``1 > 0`` -> True); an open
        # inequality (``L > 0``) is unknown, never false.
        return "unknown"
    if isinstance(value, BooleanFunction):
        simplified = value.simplify()
        if simplified == sp.true:
            return "valid"
        if simplified == sp.false:
            return "invalid"
        return "unknown"
    # A non-boolean expression as a claim has no truth value.
    return "unknown"


def _error_diagnostic(code: str, message: str) -> dict[str, Any]:
    return {"severity": "error", "code": code, "message": message}
