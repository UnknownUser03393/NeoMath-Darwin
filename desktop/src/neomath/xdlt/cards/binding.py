"""Parsing of ``#use-card`` bodies into bindings and requirements.

Grammar::

    bind <parameter> = <SEL value>
    require <SEL expression>

Binding values are SEL, so a parameter can bind to a document symbol (``L``),
a literal (``2``) or a list (``[0, L]``) without inventing new syntax.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from neomath.xdlt.nodes import Diagnostic, SourceRange
from neomath.xdlt.sel import collect_sel_diagnostics, parse_sel
from neomath.xdlt.sel.nodes import SelNode

_BIND = re.compile(r"^bind\s+([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(.*)$")
_REQUIRE = re.compile(r"^require\s+(.*)$")


@dataclass
class CardBinding:
    parameter: str
    value_raw: str
    value_node: SelNode | None = None


@dataclass
class UseCardBody:
    bindings: list[CardBinding] = field(default_factory=list)
    requires: list[SelNode] = field(default_factory=list)
    require_sources: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)


def parse_use_card_body(body: str, start_line: int) -> UseCardBody:
    parsed = UseCardBody()
    for offset, line in enumerate(body.splitlines()):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        line_number = start_line + offset
        bind_match = _BIND.match(stripped)
        if bind_match:
            parameter = bind_match.group(1)
            source = bind_match.group(2).strip()
            value_node = parse_sel(source)
            parsed.bindings.append(
                CardBinding(parameter=parameter, value_raw=source, value_node=value_node)
            )
            _attach_diagnostics(parsed, value_node, line_number)
            continue
        require_match = _REQUIRE.match(stripped)
        if require_match:
            source = require_match.group(1).strip()
            requirement = parse_sel(source)
            parsed.requires.append(requirement)
            parsed.require_sources.append(source)
            _attach_diagnostics(parsed, requirement, line_number)
            continue
        parsed.diagnostics.append(
            Diagnostic(
                severity="error",
                code="UNKNOWN_CARD_BINDING_STATEMENT",
                message=f"Unknown use-card statement '{stripped}'",
                range=SourceRange(line_number, line_number + 1),
            )
        )
    return parsed


def _attach_diagnostics(parsed: UseCardBody, node: SelNode, line_number: int) -> None:
    for diagnostic in collect_sel_diagnostics(node):
        parsed.diagnostics.append(
            Diagnostic(
                severity=diagnostic.severity,
                code=diagnostic.code,
                message=diagnostic.message,
                range=SourceRange(line_number, line_number + 1),
            )
        )
