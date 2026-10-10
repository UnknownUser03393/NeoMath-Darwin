"""Parsing of ``#assert`` bodies into structured claims and requirements.

Grammar::

    claim <SEL expression>
    require <SEL expression>

Exactly one ``claim`` is required; ``require`` may repeat. Unknown statements
and malformed SEL produce diagnostics without breaking the surrounding document.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from neomath.xdlt.nodes import Diagnostic, SourceRange
from neomath.xdlt.sel import collect_sel_diagnostics, parse_sel
from neomath.xdlt.sel.nodes import SelNode

_CLAIM = re.compile(r"^claim\s+(.*)$")
_REQUIRE = re.compile(r"^require\s+(.*)$")


@dataclass
class AssertionBody:
    claim: SelNode | None = None
    requirements: list[SelNode] = field(default_factory=list)
    claim_source: str | None = None
    requirement_sources: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)


def parse_assert_body(body: str, start_line: int) -> AssertionBody:
    parsed = AssertionBody()
    for offset, line in enumerate(body.splitlines()):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        line_number = start_line + offset
        claim_match = _CLAIM.match(stripped)
        if claim_match:
            if parsed.claim is not None:
                parsed.diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="DUPLICATE_CLAIM",
                        message="Assertion has more than one claim",
                        range=SourceRange(line_number, line_number + 1),
                    )
                )
            source = claim_match.group(1).strip()
            parsed.claim = parse_sel(source)
            parsed.claim_source = source
            _attach_sel_diagnostics(parsed, parsed.claim, line_number)
            continue
        require_match = _REQUIRE.match(stripped)
        if require_match:
            source = require_match.group(1).strip()
            requirement = parse_sel(source)
            parsed.requirements.append(requirement)
            parsed.requirement_sources.append(source)
            _attach_sel_diagnostics(parsed, requirement, line_number)
            continue
        parsed.diagnostics.append(
            Diagnostic(
                severity="error",
                code="UNKNOWN_ASSERTION_STATEMENT",
                message=f"Unknown assertion statement '{stripped}'",
                range=SourceRange(line_number, line_number + 1),
            )
        )
    if parsed.claim is None:
        parsed.diagnostics.append(
            Diagnostic(
                severity="error",
                code="MISSING_CLAIM",
                message="Assertion must have exactly one claim",
                range=SourceRange(start_line, start_line + 1),
            )
        )
    return parsed


def parse_header_arguments(arguments: str) -> dict[str, object]:
    """Parse ``using=sympy, foo=bar`` from a semantic header argument list."""
    result: dict[str, object] = {}
    for key, value in parse_argument_list(arguments):
        if key is None:
            result[value] = True
        else:
            result[key] = value.strip('"')
    return result


def split_argument_list(arguments: str) -> list[str]:
    """Split on top-level commas, ignoring those inside (), [], {}, and quotes.

    This lets ``inputs=[alpha, L]`` survive as one argument instead of being
    split into ``inputs=[alpha`` and ``L]``.
    """
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    for ch in arguments:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            current.append(ch)
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return [part for part in parts if part]


def parse_argument_list(arguments: str) -> list[tuple[str | None, str]]:
    """Ordered ``(key, value)`` pairs; positional parts carry ``key=None``."""
    result: list[tuple[str | None, str]] = []
    for part in split_argument_list(arguments):
        if "=" in part:
            key, value = part.split("=", 1)
            result.append((key.strip(), value.strip()))
        else:
            result.append((None, part.strip()))
    return result


def parse_exec_arguments(arguments: str) -> dict[str, object]:
    """Parse an ``#exec`` header argument list.

    ``(python, kernel="python3", inputs=[alpha, L])`` yields
    ``{"language": "python", "kernel": "python3", "inputs": ["alpha", "L"]}``.
    The first positional argument is the execution language.
    """
    result: dict[str, object] = {}
    inputs: list[str] = []
    for key, value in parse_argument_list(arguments):
        if key is None:
            if result.get("language") is None:
                result["language"] = value
            continue
        if key == "inputs":
            inputs = _parse_name_list(value)
        else:
            result[key] = value.strip('"')
    result["inputs"] = inputs
    return result


def parse_figure_arguments(arguments: str) -> dict[str, object]:
    """Parse an ``#fig`` header argument list (``source=#exec:plot[0]``)."""
    result: dict[str, object] = {}
    for key, value in parse_argument_list(arguments):
        if key is None:
            continue
        result[key] = value.strip('"')
    return result


def _parse_name_list(value: str) -> list[str]:
    stripped = value.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]
    names = [part.strip() for part in stripped.split(",")]
    return [name for name in names if name]


def _attach_sel_diagnostics(parsed: AssertionBody, node: SelNode, line_number: int) -> None:
    for diagnostic in collect_sel_diagnostics(node):
        parsed.diagnostics.append(
            Diagnostic(
                severity=diagnostic.severity,
                code=diagnostic.code,
                message=diagnostic.message,
                range=SourceRange(line_number, line_number + 1),
            )
        )
