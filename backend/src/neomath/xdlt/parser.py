from __future__ import annotations

import re
from typing import Final

from neomath.xdlt.nodes import (
    BodyMode,
    CommentNode,
    Diagnostic,
    DisplayMathNode,
    ErrorNode,
    FencedCodeNode,
    HeadingNode,
    InlineMathNode,
    ParagraphNode,
    SemanticBlockNode,
    SemanticHeader,
    SourceRange,
    XdltDocument,
    XdltNode,
)

_CORE_BODY_MODES: Final[dict[str, BodyMode]] = {
    "context": "ContextBody",
    "thm": "DocumentBody",
    "lemma": "DocumentBody",
    "prop": "DocumentBody",
    "cor": "DocumentBody",
    "def": "DocumentBody",
    "proof": "DocumentBody",
    "example": "DocumentBody",
    "remark": "DocumentBody",
    "derivation": "DocumentBody",
    "algorithm": "DocumentBody",
    "assert": "ExpressionBody",
    "exec": "RawBody",
    "fig": "DocumentBody",
    "table": "TableBody",
    "use-card": "CardBindingBody",
    "raw": "RawBody",
    "xdlt": "ExpressionBody",
}

_INLINE_MATH = re.compile(r"\$([^$\n]+)\$")


def _extract_inline_math(source: str, source_range: SourceRange) -> list["InlineMathNode"]:
    """Split ``$...$`` spans out of paragraph text as inline math nodes."""
    inline: list[InlineMathNode] = []
    for match in _INLINE_MATH.finditer(source):
        content = match.group(1)
        inline.append(
            InlineMathNode(
                source=content,
                source_range=source_range,
                offset=match.start(1),
                length=len(content),
            )
        )
    return inline


_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_-]*"
_QUALIFIED_KIND = rf"{_IDENTIFIER}(?:\.{_IDENTIFIER})*"
_SEMANTIC_HEADER = re.compile(
    rf"^#(?P<kind>{_QUALIFIED_KIND})(?::(?P<id>{_IDENTIFIER}))?\s*"
    rf"(?P<args>\([^{{}}]*\))?\s*(?P<block>\{{)?\s*$"
)
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE = re.compile(r"^```([^`]*)\s*$")
_DISPLAY_HEADER = re.compile(
    rf"^\$\$\s*"
    rf"(?:#(?P<kind>{_QUALIFIED_KIND}):(?P<id>{_IDENTIFIER})"
    rf"(?P<args>\([^)]*\))?)?\s*$"
)


def parse_xdlt(text: str) -> XdltDocument:
    parser = _Parser(text)
    nodes = parser.parse_nodes(0, len(parser.lines), None)
    return XdltDocument(nodes=nodes, diagnostics=_collect_diagnostics(nodes))


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.lines = text.split("\n")

    def parse_nodes(self, start: int, end: int, close_indent: int | None) -> list[XdltNode]:
        nodes: list[XdltNode] = []
        i = start
        while i < end:
            line = self.lines[i]
            stripped = line.strip()
            if stripped == "":
                i += 1
                continue
            if close_indent is not None and _indent(line) == close_indent and stripped == "}":
                break
            node: XdltNode
            if _is_comment(line):
                nodes.append(CommentNode(line, SourceRange(i, i + 1)))
                i += 1
                continue
            fence = _FENCE.match(stripped)
            if fence:
                node, i = self._parse_fenced_code(i, end, fence.group(1).strip())
                nodes.append(node)
                continue
            if stripped.startswith("$$"):
                node, i = self._parse_display_math(i, end)
                nodes.append(node)
                continue
            if _is_heading(line):
                match = _HEADING.match(line)
                if match:
                    nodes.append(
                        HeadingNode(
                            source=line,
                            source_range=SourceRange(i, i + 1),
                            level=len(match.group(1)),
                            title=match.group(2).strip(),
                        )
                    )
                    i += 1
                    continue
            if _is_semantic_candidate(line):
                node, next_i = self._parse_semantic_block(i, end)
                nodes.append(node)
                i = next_i
                continue
            node, i = self._parse_paragraph(i, end, close_indent)
            nodes.append(node)
        return nodes

    def _parse_paragraph(
        self, start: int, end: int, close_indent: int | None
    ) -> tuple[ParagraphNode, int]:
        i = start
        while i < end:
            line = self.lines[i]
            stripped = line.strip()
            if stripped == "":
                break
            if close_indent is not None and _indent(line) == close_indent and stripped == "}":
                break
            if i != start and _starts_block(line):
                break
            i += 1
        source = "\n".join(self.lines[start:i])
        node = ParagraphNode(source, SourceRange(start, i))
        node.inline_math = _extract_inline_math(source, node.source_range)
        return node, i

    def _parse_fenced_code(self, start: int, end: int, language: str) -> tuple[FencedCodeNode, int]:
        i = start + 1
        while i < end and not _FENCE.match(self.lines[i].strip()):
            i += 1
        closed = i < end
        next_i = i + 1 if closed else end
        source = "\n".join(self.lines[start:next_i])
        body = "\n".join(self.lines[start + 1 : i])
        diagnostics: list[Diagnostic] = []
        if not closed:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="UNTERMINATED_CODE_FENCE",
                    message="Fenced code block has no closing fence",
                    range=SourceRange(start, next_i),
                    fixes=["Insert closing ```"],
                )
            )
        return (
            FencedCodeNode(source, SourceRange(start, next_i), language, body, diagnostics),
            next_i,
        )

    def _scan_header(self, start: int, end: int) -> tuple[str, int]:
        """Collect a semantic header that may span lines.

        ``#exec:plot(`` arguments can be formatted across several lines::

            #exec:plot(
                python,
                inputs=[alpha]
            ) {

        The header is complete once its parens balance and it ends with a block
        opener (``{``) or the argument list close (``)``).
        """
        parts = [self.lines[start].strip()]
        consumed = 1
        while consumed < end - start and consumed < 50:
            text = " ".join(parts).strip()
            if _parens_balanced(text) and (
                text.endswith("{") or text.endswith("}") or text.endswith(")") or "(" not in text
            ):
                break
            next_line = self.lines[start + consumed]
            stripped_next = next_line.strip()
            if not stripped_next:
                break
            parts.append(stripped_next)
            consumed += 1
        if consumed < end - start and "{" not in "".join(parts):
            next_line = self.lines[start + consumed].strip()
            if next_line == "{":
                parts.append("{")
                consumed += 1
        return " ".join(parts).strip(), consumed

    def _parse_display_math(self, start: int, end: int) -> tuple[DisplayMathNode, int]:
        header_line = self.lines[start].strip()
        header_match = _DISPLAY_HEADER.match(header_line)
        i = start + 1
        while i < end and self.lines[i].strip() != "$$":
            if i != start + 1 and _starts_outer_sync(self.lines[i]):
                break
            i += 1
        closed = i < end and self.lines[i].strip() == "$$"
        next_i = i + 1 if closed else i
        source = "\n".join(self.lines[start:next_i])
        body = "\n".join(self.lines[start + 1 : i]).strip()
        diagnostics: list[Diagnostic] = []
        math_id = None
        args = ""
        if header_match:
            kind = header_match.group("kind")
            item_id = header_match.group("id")
            if kind and item_id:
                math_id = f"{kind}:{item_id}"
                args = _strip_arg_parens(header_match.group("args") or "")
        else:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="INVALID_DISPLAY_MATH_HEADER",
                    message="Display math header is malformed",
                    range=SourceRange(start, start + 1),
                )
            )
        if not closed:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="UNTERMINATED_DISPLAY_MATH",
                    message="Display math block has no closing $$",
                    range=SourceRange(start, next_i),
                    fixes=["Insert closing $$"],
                )
            )
        numbering = "on" if "numbered=true" in args.replace(" ", "") else "auto"
        return (
            DisplayMathNode(
                source,
                SourceRange(start, next_i),
                body,
                math_id,
                args,
                numbering,
                diagnostics,
            ),
            next_i,
        )

    def _parse_semantic_block(self, start: int, end: int) -> tuple[XdltNode, int]:
        stripped, consumed = self._scan_header(start, end)
        header_span = SourceRange(start, start + consumed)
        match = _SEMANTIC_HEADER.match(stripped)
        if not match:
            diagnostic = Diagnostic(
                severity="error",
                code="INVALID_BLOCK_HEADER",
                message="Semantic header is malformed",
                range=header_span,
            )
            return (
                ErrorNode(
                    "\n".join(self.lines[start : start + consumed]),
                    header_span,
                    [diagnostic],
                    ["semantic header"],
                ),
                start + consumed,
            )

        header = _header_from_match(match)
        if not match.group("block"):
            source = "\n".join(self.lines[start : start + consumed])
            body = ""
            return SemanticBlockNode(source, header_span, header, body), start + consumed

        opener_indent = _indent(self.lines[start])
        body_start = start + consumed
        close = body_start
        while close < end:
            candidate = self.lines[close]
            if _indent(candidate) == opener_indent and candidate.strip() == "}":
                break
            close += 1
        closed = close < end
        next_i = close + 1 if closed else end
        source = "\n".join(self.lines[start:next_i])
        body_lines = self.lines[body_start:close]
        body = "\n".join(body_lines)
        diagnostics: list[Diagnostic] = []
        if not closed:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="UNTERMINATED_BLOCK",
                    message=f"Semantic block '#{header.kind}' has no closing '}}'",
                    range=SourceRange(start, next_i),
                    fixes=["Insert closing }"],
                )
            )
        children: list[XdltNode] = []
        deindented = ""
        if header.body_mode == "DocumentBody":
            children = self.parse_nodes(body_start, close, opener_indent)
        elif header.body_mode == "RawBody":
            deindented = _deindent(body_lines)
        return (
            SemanticBlockNode(
                source=source,
                source_range=SourceRange(start, next_i),
                header=header,
                body=body,
                children=children,
                deindented_body=deindented,
                diagnostics=diagnostics,
            ),
            next_i,
        )


def _header_from_match(match: re.Match[str]) -> SemanticHeader:
    kind = match.group("kind")
    body_mode = _CORE_BODY_MODES.get(kind, "DocumentBody")
    return SemanticHeader(
        kind=kind,
        id=match.group("id"),
        arguments=_strip_arg_parens(match.group("args") or ""),
        body_mode=body_mode,
        known=kind in _CORE_BODY_MODES,
    )


def _strip_arg_parens(value: str) -> str:
    if value.startswith("(") and value.endswith(")"):
        return value[1:-1].strip()
    return value.strip()


def _parens_balanced(text: str) -> bool:
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
    return depth == 0


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith("//")


def _is_heading(line: str) -> bool:
    return bool(_HEADING.match(line))


def _is_semantic_candidate(line: str) -> bool:
    stripped = line.lstrip()
    return len(stripped) > 1 and stripped[0] == "#" and _is_identifier_start(stripped[1])


def _is_identifier_start(value: str) -> bool:
    return value.isalpha() or value == "_"


def _starts_block(line: str) -> bool:
    stripped = line.strip()
    return (
        _is_comment(line)
        or bool(_FENCE.match(stripped))
        or stripped.startswith("$$")
        or _is_heading(line)
        or _is_semantic_candidate(line)
    )


def _starts_outer_sync(line: str) -> bool:
    return bool(
        _indent(line) == 0
        and (_is_heading(line) or _is_semantic_candidate(line) or _FENCE.match(line.strip()))
    )


def _deindent(lines: list[str]) -> str:
    nonblank = [line for line in lines if line.strip()]
    if not nonblank:
        return ""
    width = min(_indent(line) for line in nonblank)
    return "\n".join(line[width:] if len(line) >= width else line for line in lines)


def _collect_diagnostics(nodes: list[XdltNode]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for node in nodes:
        diagnostics.extend(node.diagnostics)
        if isinstance(node, SemanticBlockNode):
            diagnostics.extend(_collect_diagnostics(node.children))
    return diagnostics
