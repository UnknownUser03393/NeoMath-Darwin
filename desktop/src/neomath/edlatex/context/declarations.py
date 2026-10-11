from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Parses context declaration strings into structured facts. Grammar (flexible;
# multiple declarations may be separated by ';'):
#
#   reals x y            integers n           complex z         -> domain
#   positive a  negative a  nonnegative a  nonzero b            -> sign
#   x = -1        m = 1.0                                        -> value binding
#   with mass m = 1.0                                           -> parameter (labelled value)
#   x > 0   a >= 0   -1 <= x <= 1                               -> inequality / interval
#   contract -1 <= x <= 1                                       -> (contract prefix stripped)
#
# Anything unrecognised becomes an ``unknown`` declaration that is preserved so
# nothing is silently dropped.
# ---------------------------------------------------------------------------

_DOMAIN_WORDS = {
    "real": "real",
    "reals": "real",
    "integer": "integer",
    "integers": "integer",
    "complex": "complex",
    "complexes": "complex",
}
_SIGN_WORDS = {
    "positive": "positive",
    "negative": "negative",
    "nonnegative": "nonnegative",
    "nonneg": "nonnegative",
    "nonzero": "nonzero",
}
_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
_REL = re.compile(r"(<=|>=|<|>|=)")


@dataclass
class Relation:
    op: str  # one of = < > <= >=
    bound: str  # right-hand side literal / expression as text

    def to_dict(self) -> dict[str, str]:
        return {"op": self.op, "bound": self.bound}


@dataclass
class Declaration:
    raw: str
    kind: str  # domain | sign | value | inequality | param | unknown
    symbols: list[str] = field(default_factory=list)
    domain: str | None = None
    sign: str | None = None
    relations: list[Relation] = field(default_factory=list)
    label: str | None = None  # e.g. "mass" for `with mass m = 1.0`
    # Provenance (filled by the scope builder, not the parser).
    source_scope_id: str | None = None
    source_node_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "kind": self.kind,
            "symbols": list(self.symbols),
            "domain": self.domain,
            "sign": self.sign,
            "relations": [r.to_dict() for r in self.relations],
            "label": self.label,
            "sourceScopeId": self.source_scope_id,
            "sourceNodeId": self.source_node_id,
        }


def parse_declarations(raw: str) -> list[Declaration]:
    """Parse one raw declaration string (possibly ';'-separated) into facts."""
    results: list[Declaration] = []
    for chunk in raw.split(";"):
        text = chunk.strip()
        if not text:
            continue
        parsed = _parse_one(text)
        if parsed is not None:
            results.append(parsed)
    return results


def _parse_one(text: str) -> Declaration | None:
    original = text

    # `contract <...>` -> strip the keyword, keep the constraint.
    if text.lower().startswith("contract "):
        text = text[len("contract ") :].strip()

    # `with <label> <sym> = <value>` -> parameter binding.
    with_match = re.match(rf"^with\s+({_IDENT})\s+({_IDENT})\s*=\s*(.+)$", text)
    if with_match:
        label, sym, value = with_match.group(1), with_match.group(2), with_match.group(3).strip()
        return Declaration(
            raw=original,
            kind="param",
            symbols=[sym],
            label=label,
            relations=[Relation(op="=", bound=value)],
        )

    # Domain: `reals x y`
    parts = text.split()
    if parts and parts[0].lower() in _DOMAIN_WORDS and len(parts) >= 2:
        return Declaration(
            raw=original,
            kind="domain",
            symbols=parts[1:],
            domain=_DOMAIN_WORDS[parts[0].lower()],
        )

    # Sign: `positive a b`
    if parts and parts[0].lower() in _SIGN_WORDS and len(parts) >= 2:
        return Declaration(
            raw=original,
            kind="sign",
            symbols=parts[1:],
            sign=_SIGN_WORDS[parts[0].lower()],
        )

    # Relational: value / inequality / interval.
    tokens = _REL.split(text)
    # tokens alternates operand, op, operand, op, operand ...
    if len(tokens) >= 3:
        operands = [t.strip() for t in tokens[0::2]]
        ops = [t.strip() for t in tokens[1::2]]
        # Single relation:  lhs op rhs
        if len(ops) == 1:
            lhs, rhs = operands[0], operands[1]
            symbol, bound, op = _orient(lhs, ops[0], rhs)
            if symbol is not None:
                kind = "value" if op == "=" else "inequality"
                return Declaration(
                    raw=original,
                    kind=kind,
                    symbols=[symbol],
                    relations=[Relation(op=op, bound=bound)],
                )
        # Chained interval:  a <= x <= b  (middle operand is the symbol)
        elif len(ops) == 2 and re.fullmatch(_IDENT, operands[1]):
            symbol = operands[1]
            rels: list[Relation] = []
            # left:  a <= x   =>   x >= a
            rels.append(Relation(op=_flip(ops[0]), bound=operands[0]))
            # right: x <= b
            rels.append(Relation(op=ops[1], bound=operands[2]))
            return Declaration(
                raw=original, kind="inequality", symbols=[symbol], relations=rels
            )

    return Declaration(raw=original, kind="unknown")


def _orient(lhs: str, op: str, rhs: str) -> tuple[str | None, str, str]:
    """Return (symbol, bound, op) with the symbol on the left-hand side."""
    if re.fullmatch(_IDENT, lhs):
        return lhs, rhs, op
    if re.fullmatch(_IDENT, rhs):
        # Flip so the symbol leads:  0 < x  ->  x > 0
        return rhs, lhs, _flip(op)
    return None, rhs, op


def _flip(op: str) -> str:
    return {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "=": "="}[op]
