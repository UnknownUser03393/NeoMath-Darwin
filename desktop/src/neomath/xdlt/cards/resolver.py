"""Resolution of ``#use-card`` references: header args, bindings, requirements.

Bindings resolve card parameters to document symbols by identity
(``sym:ctx.global/L``), to literals, or to SEL expressions. Requirements are
checked by evaluating card SEL requirements against the bound values, reusing
the verification backend; ``unknown`` is never treated as ``unsatisfied``.
"""

from __future__ import annotations

from typing import Any

import sympy as sp

from neomath.xdlt.cards.binding import CardBinding
from neomath.xdlt.cards.model import Card
from neomath.xdlt.cards.registry import CardRegistry
from neomath.xdlt.nodes import Diagnostic, SourceRange
from neomath.xdlt.resolve import Scope
from neomath.xdlt.sel import lower_sel
from neomath.xdlt.sel.body import parse_argument_list
from neomath.xdlt.sel.nodes import SelNode
from neomath.xdlt.values import semantic_value_to_python
from neomath.xdlt.values.convert import assumptions_for
from neomath.xdlt.values.environment import ValueEnvironment
from neomath.xdlt.values.resolve import sel_value_to_semantic, semantic_from_dict
from neomath.xdlt.verification.sel_convert import sel_ir_to_value
from neomath.xdlt.verification.sympy_verifier import _check_value

_CARD_MODES = {"reference", "snapshot", "fork"}


def parse_card_arguments(arguments: str) -> dict[str, Any]:
    """Parse ``#card:fourier, mode=reference`` from a use-card header."""
    result: dict[str, Any] = {"cardRef": None, "mode": "reference", "version": None}
    for key, value in parse_argument_list(arguments):
        if key is None:
            result["cardRef"] = value
        elif key == "mode":
            result["mode"] = value
        elif key == "version":
            result["version"] = value
    return result


def parse_card_ref(text: str | None) -> tuple[str | None, str | None]:
    """``#card:fourier@1.2.0`` -> ``("fourier", "1.2.0")``."""
    if not text:
        return None, None
    ref = text.strip()
    if ref.startswith("#card:"):
        ref = ref[len("#card:") :]
    elif ref.startswith("card:"):
        ref = ref[len("card:") :]
    ref = ref.strip()
    if "@" in ref:
        card_id, version = ref.rsplit("@", 1)
        return card_id.strip() or None, (version.strip() or None)
    return ref or None, None


def resolve_use_card(
    card_ref: str | None,
    mode: str,
    version: str | None,
    body: list[CardBinding],
    scope: Scope,
    registry: CardRegistry | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Resolve one use-card block. Returns (entity fragments, diagnostics)."""
    diagnostics: list[dict[str, Any]] = []
    card_id, ref_version = parse_card_ref(card_ref)
    selected_version = version or ref_version

    card: Card | None = None
    if card_id:
        if registry is None or not registry.has(card_id):
            diagnostics.append(_diag("error", "UNKNOWN_CARD", f"unknown card '{card_id}'"))
        else:
            card = registry.resolve(card_id, selected_version)
            if selected_version and card is None:
                diagnostics.append(
                    _diag(
                        "error",
                        "CARD_VERSION_NOT_FOUND",
                        f"card '{card_id}' version '{selected_version}' not found",
                    )
                )
            elif card is None:
                diagnostics.append(
                    _diag("error", "CARD_VERSION_NOT_FOUND", f"card '{card_id}' has no versions")
                )
    if mode not in _CARD_MODES:
        diagnostics.append(
            _diag("warning", "UNKNOWN_CARD_MODE", f"unknown card mode '{mode}', using reference")
        )
        mode = "reference"

    bindings = [_resolve_binding(binding, scope) for binding in body]
    entity: dict[str, Any] = {
        "cardId": card_id,
        "cardVersion": card.version if card else selected_version,
        "mode": mode,
        "bindings": bindings,
        "requirements": [],
        "cardSemanticHash": card.semantic_hash if card else None,
        "provenance": {
            "cardId": card_id,
            "cardVersion": card.version if card else selected_version,
            "mode": mode,
            "sourcePath": card.source_path if card else None,
            "cardSemanticHash": card.semantic_hash if card else None,
        },
    }
    if mode == "snapshot" and card is not None:
        entity["provenance"]["pinnedHash"] = card.semantic_hash
    if mode == "fork" and card is not None:
        entity["provenance"]["originCard"] = card.card_id
        entity["provenance"]["originVersion"] = card.version
    return entity, diagnostics


def check_card_requirements(
    entity: dict[str, Any],
    card: Card | None,
    value_environment: ValueEnvironment,
) -> list[dict[str, Any]]:
    """Evaluate a card's requirements against the resolved bindings."""
    if card is None:
        return []
    requirements: list[tuple[str, str | None]] = []
    for parameter in card.parameters.values():
        for source in parameter.requires:
            requirements.append((source, parameter.name))
    for source in card.requirements:
        requirements.append((source, None))

    bindings = entity.get("bindings") or []
    getter = _make_getter(bindings, card, value_environment)
    checked: list[dict[str, Any]] = []
    for source, parameter_name in requirements:
        status, message = _check_one(source, getter, parameter_name)
        checked.append({"source": source, "status": status, "message": message})
    entity["requirements"] = checked
    return checked


def _resolve_binding(binding: CardBinding, scope: Scope) -> dict[str, Any]:
    node = binding.value_node
    if node is None:
        return {"parameter": binding.parameter, "kind": "error", "valueRaw": binding.value_raw}
    if node.kind == "symbol":
        declaration = scope.lookup(node.name)
        return {
            "parameter": binding.parameter,
            "kind": "symbol",
            "name": node.name,
            "symbolId": declaration.symbol_id if declaration else None,
            "valueRaw": binding.value_raw,
        }
    if node.kind == "literal":
        value = sel_value_to_semantic(node)
        return {
            "parameter": binding.parameter,
            "kind": "literal",
            "literal": value.to_dict() if value else None,
            "valueRaw": binding.value_raw,
        }
    if node.kind == "list":
        items = [_resolve_binding_item(item, scope) for item in node.items]
        return {
            "parameter": binding.parameter,
            "kind": "list",
            "items": items,
            "valueRaw": binding.value_raw,
        }
    return {
        "parameter": binding.parameter,
        "kind": "expression",
        "selIr": lower_sel(node),
        "valueRaw": binding.value_raw,
    }


def _resolve_binding_item(node: SelNode, scope: Scope) -> dict[str, Any]:
    if node.kind == "symbol":
        declaration = scope.lookup(node.name)
        return {
            "kind": "symbol",
            "name": node.name,
            "symbolId": declaration.symbol_id if declaration else None,
        }
    value = sel_value_to_semantic(node)
    return {"kind": "literal", "literal": value.to_dict() if value else None}


def _make_getter(
    bindings: list[dict[str, Any]],
    card: Card,
    value_environment: ValueEnvironment,
) -> Any:
    def getter(name: str) -> Any:
        for binding in bindings:
            if binding.get("parameter") == name:
                return _binding_python(binding, value_environment, getter)
        if card is not None and name in card.parameters:
            parameter = card.parameters[name]
            return sp.Symbol(name, **assumptions_for(parameter.type_expr))
        return sp.Symbol(name)

    return getter


def _binding_python(
    binding: dict[str, Any], value_environment: ValueEnvironment, getter: Any
) -> Any:
    kind = binding.get("kind")
    if kind == "literal":
        value = semantic_from_dict(binding.get("literal") or {})
        return semantic_value_to_python(value, getter) if value is not None else sp.Symbol("?")
    if kind == "symbol":
        symbol_id = binding.get("symbolId")
        if symbol_id and value_environment.has_value(symbol_id):
            return semantic_value_to_python(value_environment.resolve(symbol_id), getter)
        return sp.Symbol(str(binding.get("name") or binding.get("parameter")))
    if kind == "list":
        return [
            _binding_python(item, value_environment, getter) for item in binding.get("items", [])
        ]
    if kind == "expression":
        return sp.sympify(binding.get("valueRaw") or "?")
    return sp.Symbol(str(binding.get("parameter")))


def _check_one(source: str, getter: Any, parameter: str | None) -> tuple[str, str]:
    try:
        ir = lower_sel(parse_sel_source(source))
        value = sel_ir_to_value(ir, {}, getter)
    except Exception:  # noqa: BLE001 - undecidable is unknown, never failed
        return "unknown", "could not evaluate requirement"
    status = _check_value(value)
    if status == "valid":
        return "valid", ""
    if status == "invalid":
        return "unsatisfied", f"requirement '{source}' is false"
    return "unknown", f"requirement '{source}' could not be decided"


def resolve_project_cards(
    semantic_ir: dict[str, Any],
    registry: CardRegistry,
    value_environment: ValueEnvironment,
) -> list[Diagnostic]:
    """Check every resolved card reference in a document's semantic IR.

    Mutates each CardReference entity in place (attaching requirement results)
    and returns document diagnostics.
    """
    diagnostics: list[Diagnostic] = []
    for entity in semantic_ir.get("children", []):
        if entity.get("type") != "CardReference":
            continue
        card_id = entity.get("cardId")
        if not card_id or not registry.has(str(card_id)):
            continue
        card = registry.resolve(str(card_id), entity.get("cardVersion"))
        if card is None:
            continue
        source_range = _source_range(entity)
        for requirement in check_card_requirements(entity, card, value_environment):
            if requirement["status"] == "unsatisfied":
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="CARD_REQUIREMENT_UNSATISFIED",
                        message=requirement["message"],
                        range=source_range,
                    )
                )
            elif requirement["status"] == "unknown":
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="CARD_REQUIREMENT_UNKNOWN",
                        message=requirement["message"],
                        range=source_range,
                    )
                )
    return diagnostics


def _source_range(entity: dict[str, Any]) -> SourceRange:
    data = entity.get("sourceRange") or {}
    return SourceRange(int(data.get("start", 0)), int(data.get("end", 1)))


def _diag(severity: str, code: str, message: str) -> dict[str, Any]:
    return {"severity": severity, "code": code, "message": message}


def parse_sel_source(source: str) -> SelNode:
    from neomath.xdlt.sel import parse_sel

    return parse_sel(source)
