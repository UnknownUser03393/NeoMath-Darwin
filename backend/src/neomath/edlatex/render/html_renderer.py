from __future__ import annotations

from html import escape

from neomath.edlatex.document import EdDocument
from neomath.edlatex.nodes import (
    AssertionNode,
    CodeNode,
    ContextNode,
    DerivationNode,
    DocumentNode,
    FormulaNode,
    ParagraphNode,
    SectionNode,
)
from neomath.edlatex.render.base import (
    DocumentRenderer,
    RenderDiagnostic,
    RenderResult,
    resolve_header_footer,
)


class HtmlRenderer(DocumentRenderer):
    """HTML preview from the same model the editor and LaTeX export use.

    Math is emitted as raw ``$...$`` / ``$$...$$`` so the existing KaTeX pass in
    the UI renders it; this renderer does not maintain a separate content copy.
    """

    format = "html"

    def render(self, document: EdDocument) -> RenderResult:
        diagnostics: list[RenderDiagnostic] = []
        layout = document.layout
        header = resolve_header_footer(document, layout.header)

        parts: list[str] = []
        parts.append(f'<article class="edlatex theme-{escape(layout.theme)}" '
                     f'data-template="{escape(layout.template)}">')
        if header:
            parts.append(f'<header class="ed-header">{escape(header)}</header>')

        for node in document.iter_nodes():
            parts.append(self._render_node(node, diagnostics))

        parts.append("</article>")
        return RenderResult(format=self.format, content="\n".join(parts), diagnostics=diagnostics)

    def _render_node(
        self, node: DocumentNode, diagnostics: list[RenderDiagnostic]
    ) -> str:
        attr = f'id="{escape(node.id)}" data-type="{escape(node.type)}"'
        if isinstance(node, SectionNode):
            level = min(max(node.level, 1), 6)
            return f'<h{level} {attr}>{escape(node.title)}</h{level}>'
        if isinstance(node, ParagraphNode):
            # Keep inline $..$ verbatim for KaTeX; escape only HTML-unsafe chars
            # that are not part of math delimiters.
            return f'<p {attr}>{_escape_prose(node.source)}</p>'
        if isinstance(node, FormulaNode):
            expr = node.parsed_expression or node.source
            if node.display:
                return f'<div class="ed-formula" {attr}>$$ {expr} $$</div>'
            return f'<span class="ed-formula-inline" {attr}>${expr}$</span>'
        if isinstance(node, DerivationNode):
            return (
                f'<div class="ed-derivation" {attr} data-rule="{escape(node.rule)}">'
                f'<span class="ed-from">${node.from_expr}$</span>'
                f'<span class="ed-arrow">→</span>'
                f'<span class="ed-to">${node.to_expr}$</span>'
                f'<span class="ed-rule">{escape(node.rule)}</span>'
                f'</div>'
            )
        if isinstance(node, AssertionNode):
            status = escape(node.verification_status)
            return (
                f'<div class="ed-assertion" {attr} data-status="{status}">'
                f'${node.expression_ref} = {node.equals}$</div>'
            )
        if isinstance(node, ContextNode):
            decls = "; ".join(escape(d) for d in node.declarations)
            return f'<div class="ed-context" {attr}>{decls}</div>'
        if isinstance(node, CodeNode):
            return (
                f'<pre class="ed-code" {attr} data-language="{escape(node.language)}">'
                f'<code>{escape(node.source)}</code></pre>'
            )
        diagnostics.append(
            RenderDiagnostic(
                severity="warning",
                code="UNSUPPORTED_NODE",
                message=f"节点类型 {node.type} 暂无 HTML 导出实现",
                node_id=node.id,
            )
        )
        return f'<!-- unsupported node {escape(node.id)} ({escape(node.type)}) -->'


def _escape_prose(text: str) -> str:
    """Escape HTML angle brackets/ampersands but leave $ math delimiters intact."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
