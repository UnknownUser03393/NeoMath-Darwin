from __future__ import annotations

import re
from typing import Any

from neomath.edlatex.nodes import (
    AssertionNode,
    CodeNode,
    ContextNode,
    DerivationNode,
    DocumentNode,
    FormulaNode,
    ParagraphNode,
    SectionNode,
    SourceRange,
)

# ---------------------------------------------------------------------------
# content.edl is a light structured text format. The parser is block-oriented
# and ALWAYS stores each node's exact original text in ``node.source`` so an
# edit round-trips losslessly even for constructs it does not fully understand.
# A malformed block degrades to a paragraph rather than corrupting the input.
# ---------------------------------------------------------------------------

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_DERIVE = re.compile(r"^@derive\b\s*([\w-]*)\s*\{")
_ASSERT = re.compile(r"^@assert\b\s*\{")
_CONTEXT_INLINE = re.compile(r"^#\{(.*)\}\s*$")
_CONTEXT_BLOCK = re.compile(r"^#field\b\s*\{")
_FENCE = re.compile(r"^```(\w*)\s*$")
_FIELD = re.compile(r"^\s*([\w-]+)\s*:\s*(.*?)\s*$")


def _parse_braced_fields(body: str) -> dict[str, str]:
    """Extract ``key: value`` pairs from a brace block body."""
    fields: dict[str, str] = {}
    for line in body.splitlines():
        match = _FIELD.match(line)
        if match:
            fields[match.group(1)] = match.group(2)
    return fields


def parse_content_edl(text: str) -> list[DocumentNode]:
    lines = text.split("\n")
    nodes: list[DocumentNode] = []
    i = 0
    n = len(lines)

    def emit(node: DocumentNode, start: int, end: int) -> None:
        node.source = "\n".join(lines[start:end])
        node.source_range = SourceRange(start=start, end=end)
        nodes.append(node)

    node: DocumentNode
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped == "":
            i += 1
            continue

        # Fenced code block.
        fence = _FENCE.match(stripped)
        if fence:
            lang = fence.group(1) or "python"
            j = i + 1
            while j < n and not _FENCE.match(lines[j].strip()):
                j += 1
            end = min(j + 1, n)  # include closing fence
            code_src = "\n".join(lines[i + 1 : j])
            node = CodeNode(language=lang)
            node.source = code_src
            node.source_range = SourceRange(start=i, end=end)
            nodes.append(node)
            i = end
            continue

        # Display math block.
        if stripped == "$$":
            j = i + 1
            while j < n and lines[j].strip() != "$$":
                j += 1
            end = min(j + 1, n)
            expr = "\n".join(lines[i + 1 : j]).strip()
            node = FormulaNode(display=True, parsed_expression=expr)
            emit(node, i, end)
            i = end
            continue

        # @derive block (brace-delimited, may span lines).
        derive = _DERIVE.match(stripped)
        if derive:
            j, body = _consume_braces(lines, i)
            fields = _parse_braced_fields(body)
            node = DerivationNode(
                name=derive.group(1),
                from_expr=fields.get("from", ""),
                to_expr=fields.get("to", ""),
                rule=fields.get("rule", ""),
            )
            emit(node, i, j)
            i = j
            continue

        # @assert block.
        if _ASSERT.match(stripped):
            j, body = _consume_braces(lines, i)
            fields = _parse_braced_fields(body)
            node = AssertionNode(
                expression_ref=fields.get("expression", ""),
                equals=fields.get("equals", ""),
            )
            emit(node, i, j)
            i = j
            continue

        # Context: inline #{ ... } or #field { ... } block.
        ctx_inline = _CONTEXT_INLINE.match(stripped)
        if ctx_inline:
            node = ContextNode(declarations=[ctx_inline.group(1).strip()])
            emit(node, i, i + 1)
            i += 1
            continue
        if _CONTEXT_BLOCK.match(stripped):
            j, body = _consume_braces(lines, i)
            decls = [ln.strip() for ln in body.splitlines() if ln.strip()]
            node = ContextNode(declarations=decls)
            emit(node, i, j)
            i = j
            continue

        # Heading.
        heading = _HEADING.match(line)
        if heading:
            node = SectionNode(level=len(heading.group(1)), title=heading.group(2).strip())
            emit(node, i, i + 1)
            i += 1
            continue

        # Paragraph: accumulate until a blank line or the next block starter.
        j = i
        while j < n and lines[j].strip() != "" and not _is_block_start(lines[j]):
            j += 1
        node = ParagraphNode()
        emit(node, i, j)
        i = j

    return nodes


def _is_block_start(line: str) -> bool:
    stripped = line.strip()
    if stripped in ("$$",):
        return True
    return bool(
        _FENCE.match(stripped)
        or _DERIVE.match(stripped)
        or _ASSERT.match(stripped)
        or _CONTEXT_INLINE.match(stripped)
        or _CONTEXT_BLOCK.match(stripped)
        or _HEADING.match(line)
    )


def _consume_braces(lines: list[str], start: int) -> tuple[int, str]:
    """Consume from ``start`` until braces balance. Returns (end_index, body).

    ``body`` is the text strictly inside the outermost ``{ }``. If braces never
    balance the block runs to EOF, keeping the raw text intact.
    """
    depth = 0
    body_parts: list[str] = []
    i = start
    seen_open = False
    while i < len(lines):
        line = lines[i]
        for ch in line:
            if ch == "{":
                depth += 1
                seen_open = True
                if depth == 1:
                    continue  # don't include the outermost opener
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i + 1, "\n".join(body_parts)
        if seen_open:
            # Capture inner lines (skip the opener line's leading "...{").
            if i == start:
                brace_pos = line.find("{")
                body_parts.append(line[brace_pos + 1 :])
            else:
                body_parts.append(line)
        i += 1
    return len(lines), "\n".join(body_parts)


def render_content_edl(nodes: list[DocumentNode]) -> str:
    """Render nodes back to content.edl using each node's preserved source.

    Because every node retains its original text, this is lossless for parsed
    documents and stable for programmatically built ones.
    """
    blocks: list[str] = []
    for node in nodes:
        if node.source:
            blocks.append(node.source)
        else:
            blocks.append(_synthesize(node))
    return "\n\n".join(blocks) + "\n"


def _synthesize(node: DocumentNode) -> str:
    """Produce text for a node that was built in code with no source set."""
    if isinstance(node, SectionNode):
        return f"{'#' * node.level} {node.title}"
    if isinstance(node, FormulaNode):
        expr = node.parsed_expression or ""
        return f"$$\n{expr}\n$$" if node.display else f"${expr}$"
    if isinstance(node, DerivationNode):
        return (
            f"@derive {node.name} {{\n"
            f"    from: {node.from_expr}\n"
            f"    to: {node.to_expr}\n"
            f"    rule: {node.rule}\n"
            f"}}"
        )
    if isinstance(node, AssertionNode):
        return f"@assert {{\n    expression: {node.expression_ref}\n    equals: {node.equals}\n}}"
    if isinstance(node, ContextNode):
        return "#{ " + "; ".join(node.declarations) + " }"
    if isinstance(node, CodeNode):
        return f"```{node.language}\n\n```"
    return ""


def parse_document_json(nodes: list[DocumentNode]) -> list[dict[str, Any]]:
    return [n.to_dict() for n in nodes]
