"""HTML reference backend.

Renders a RenderDocument into deterministic HTML with semantic classes only
(``xdlt-theorem``, ``xdlt-assertion-valid``, ...). No inline styles, no
hard-coded colors: visual design belongs to CSS. Math is rendered as MathML from
the Math IR; opaque math degrades to a safe ``data-latex`` span.
"""

from __future__ import annotations

from typing import Any

from neomath.xdlt.render.html.document import html_document_shell
from neomath.xdlt.render.html.escape import escape_attr, escape_html
from neomath.xdlt.render.html.math import math_ir_to_mathml
from neomath.xdlt.render.nodes import (
    RenderAssertion,
    RenderCardReference,
    RenderCitation,
    RenderCode,
    RenderDiagnostic,
    RenderDocument,
    RenderExecutable,
    RenderFigure,
    RenderHeading,
    RenderImage,
    RenderInlineMath,
    RenderMathBlock,
    RenderNode,
    RenderParagraph,
    RenderProof,
    RenderReference,
    RenderSection,
    RenderTable,
    RenderText,
    RenderThesis,
    contains_opaque,
)

_MATHML_NAMESPACE = 'xmlns="http://www.w3.org/1998/Math/MathML"'

_LABELS = {
    "theorem": "Theorem",
    "lemma": "Lemma",
    "proposition": "Proposition",
    "corollary": "Corollary",
    "definition": "Definition",
    "example": "Example",
    "remark": "Remark",
    "algorithm": "Algorithm",
}


class HTMLRenderer:
    def __init__(self, include_source_metadata: bool = True) -> None:
        self.include_source_metadata = include_source_metadata

    def render_fragment(self, document: RenderDocument) -> str:
        body = self._render_children(document.child_nodes)
        # The document node carries a stable anchor so document-level patches
        # (insert into "render:document") can find their parent.
        anchor = ' data-xdlt-render-id="render:document"' if self.include_source_metadata else ""
        return f'<article class="xdlt-document"{anchor}>{body}</article>'

    def render_node(self, node: RenderNode) -> str:
        """Render one render node to HTML (used for patch payloads)."""
        return self._render_node(node)

    def render_standalone(self, document: RenderDocument) -> str:
        body = self._render_children(document.child_nodes)
        title = str(document.metadata.get("title") or "")
        return html_document_shell(title=title, body=body)

    # --- node dispatch -----------------------------------------------------
    def _render_children(self, nodes: list[RenderNode]) -> str:
        return "".join(self._render_node(node) for node in nodes)

    def _render_node(self, node: RenderNode) -> str:
        if isinstance(node, RenderText):
            return escape_html(node.text)
        if isinstance(node, RenderInlineMath):
            return self._render_math(node.math_ir, node.raw, inline=True)
        if isinstance(node, RenderMathBlock):
            return self._render_math(node.math_ir, node.raw, inline=False, node=node)
        if isinstance(node, RenderSection):
            return self._render_section(node)
        if isinstance(node, RenderHeading):
            return self._render_heading(node)
        if isinstance(node, RenderParagraph):
            body = self._render_children(node.children())
            return f'<p class="xdlt-paragraph"{self._attrs(node)}>{body}</p>'
        if isinstance(node, RenderThesis):
            return self._render_thesis(node)
        if isinstance(node, RenderProof):
            return self._render_proof(node)
        if isinstance(node, (RenderReference, RenderCitation)):
            return self._render_reference(node)
        if isinstance(node, RenderAssertion):
            return self._render_assertion(node)
        if isinstance(node, RenderCode):
            return (
                f'<pre class="xdlt-code"{self._attrs(node)}><code>'
                f"{escape_html(node.source)}</code></pre>"
            )
        if isinstance(node, RenderExecutable):
            return self._render_executable(node)
        if isinstance(node, RenderFigure):
            return self._render_figure(node)
        if isinstance(node, RenderImage):
            alt = escape_attr(node.alt)
            src = escape_attr(node.src)
            return f'<img class="xdlt-image" src="{src}" alt="{alt}" />'
        if isinstance(node, RenderTable):
            return self._render_table(node)
        if isinstance(node, RenderCardReference):
            return self._render_card(node)
        if isinstance(node, RenderDiagnostic):
            return self._render_diagnostic(node)
        body = self._render_children(node.children())
        klass = f"xdlt-{node.kind}"
        return f'<div class="{klass}"{self._attrs(node)}>{body}</div>'

    # --- blocks ------------------------------------------------------------
    def _render_section(self, node: RenderSection) -> str:
        attrs = self._attrs(node)
        body = self._render_children(node.children())
        return f'<section class="xdlt-section"{attrs}>{body}</section>'

    def _render_heading(self, node: RenderHeading) -> str:
        level = min(max(node.level, 1), 6)
        return f"<h{level}>{escape_html(node.text)}</h{level}>"

    def _render_thesis(self, node: RenderThesis) -> str:
        label = _LABELS.get(node.kind, node.kind.capitalize())
        number_text = f"{label} {node.number}" if node.number else label
        title = (
            f'<span class="xdlt-thesis-title">{escape_html(node.title)}</span>'
            if node.title
            else ""
        )
        header = (
            f'<header class="xdlt-thesis-header">'
            f'<span class="xdlt-thesis-label">{escape_html(number_text)}</span>{title}'
            f"</header>"
        )
        body = self._render_children(node.children())
        klass = f"xdlt-{node.kind}"
        return (
            f'<section class="xdlt-thesis {klass}"{self._attrs(node)}>'
            f"{header}{body}</section>"
        )

    def _render_proof(self, node: RenderProof) -> str:
        header = '<header class="xdlt-proof-header">Proof.</header>'
        body = self._render_children(node.children())
        return (
            f'<section class="xdlt-proof"{self._attrs(node)}>'
            f"{header}{body}<span class=\"xdlt-qed\">Q.E.D.</span></section>"
        )

    def _render_reference(self, node: RenderNode) -> str:
        text = getattr(node, "display_text", None) or escape_html(
            getattr(node, "target_id", "") or ""
        )
        anchor = getattr(node, "anchor", None)
        if anchor:
            href = f"#{escape_attr(anchor)}"
            return f'<a class="xdlt-reference" href="{href}">{escape_html(text)}</a>'
        return f'<span class="xdlt-reference-unresolved">{escape_html(text)}</span>'

    def _render_assertion(self, node: RenderAssertion) -> str:
        status = escape_attr(node.verification_status or "unverified")
        claim_source = escape_html(node.claim_source or "")
        status_text = escape_html(node.verification_status or "unverified")
        header = (
            f'<header class="xdlt-assertion-header">'
            f'<span class="xdlt-assertion-status">status: {status_text}</span>'
            f"</header>"
        )
        claim = f'<div class="xdlt-assertion-claim">{claim_source}</div>' if claim_source else ""
        return (
            f'<section class="xdlt-assertion xdlt-assertion-{status}"{self._attrs(node)}>'
            f"{header}{claim}</section>"
        )

    def _render_executable(self, node: RenderExecutable) -> str:
        status = escape_attr(node.status or "unexecuted")
        source = (
            f'<pre class="xdlt-exec-source"><code>{escape_html(node.source)}</code></pre>'
            if node.source
            else ""
        )
        cached = ' data-cached="true"' if node.cached else ""
        stdout = (
            f'<pre class="xdlt-exec-stdout">{escape_html(node.stdout)}</pre>'
            if node.stdout
            else ""
        )
        stderr = (
            f'<pre class="xdlt-exec-stderr">{escape_html(node.stderr)}</pre>'
            if node.stderr
            else ""
        )
        outputs = "".join(self._render_node(output) for output in node.outputs)
        return (
            f'<section class="xdlt-exec xdlt-exec-{status}"{self._attrs(node)}{cached}>'
            f'<span class="xdlt-exec-status">{escape_html(node.status)}</span>{source}'
            f"{stdout}{stderr}{outputs}</section>"
        )

    def _render_figure(self, node: RenderFigure) -> str:
        content = ""
        if node.image is not None and node.available:
            content = self._render_node(node.image)
        else:
            content = (
                '<div class="xdlt-figure-unavailable">figure unavailable</div>'
            )
        caption_parts = []
        if node.number:
            caption_parts.append(f"Figure {node.number}")
        if node.caption:
            caption_parts.append(escape_html(node.caption))
        caption = (
            f"<figcaption>{'. '.join(caption_parts)}</figcaption>" if caption_parts else ""
        )
        return (
            f'<figure class="xdlt-figure"{self._attrs(node)}>{content}{caption}</figure>'
        )

    def _render_table(self, node: RenderTable) -> str:
        header = ""
        if node.headers:
            cells = "".join(f"<th>{escape_html(str(cell))}</th>" for cell in node.headers)
            header = f"<thead><tr>{cells}</tr></thead>"
        rows = ""
        for row in node.rows:
            cells = "".join(f"<td>{escape_html(str(cell))}</td>" for cell in row)
            rows += f"<tr>{cells}</tr>"
        caption = (
            f"<caption>Table {node.number}</caption>"
            if node.number
            else ""
        )
        return (
            f'<table class="xdlt-table"{self._attrs(node)}>{caption}{header}'
            f"<tbody>{rows}</tbody></table>"
        )

    def _render_card(self, node: RenderCardReference) -> str:
        identity = node.card_id or ""
        if identity and node.version:
            identity = f"{identity}@{node.version}"
        header = (
            f'<header class="xdlt-card-header">'
            f'<span class="xdlt-card-identity">{escape_html(identity)}</span>'
            f'<span class="xdlt-card-mode">{escape_html(node.mode)}</span>'
            f"</header>"
        )
        content = self._render_children(node.content)
        if not content:
            content = '<div class="xdlt-card-empty">卡片内容不可用</div>'
        return (
            f'<section class="xdlt-card-reference"{self._attrs(node)}>'
            f"{header}{content}</section>"
        )

    def _render_diagnostic(self, node: RenderDiagnostic) -> str:
        severity = escape_attr(node.severity)
        message = escape_html(f"{node.code}: {node.message}")
        return (
            f'<div class="xdlt-diagnostic xdlt-diagnostic-{severity}">{message}</div>'
        )

    # --- math --------------------------------------------------------------
    def _render_math(
        self, math_ir: dict[str, Any], raw: str, inline: bool, node: RenderNode | None = None
    ) -> str:
        if contains_opaque(math_ir) or math_ir_to_mathml(math_ir) is None:
            fallback = (
                f'<span class="xdlt-math-opaque" data-latex="{escape_attr(raw)}">'
                f"{escape_html(raw)}</span>"
            )
            return fallback
        mathml = math_ir_to_mathml(math_ir)
        wrapper = "span" if inline else "div"
        klass = "xdlt-inline-math" if inline else "xdlt-equation"
        attrs = self._attrs(node) if node is not None else ""
        number = ""
        if not inline and node is not None and getattr(node, "number", None):
            number = (
                f'<span class="xdlt-equation-number">'
                f"({escape_html(node.number)})</span>"
            )
        return (
            f'<{wrapper} class="{klass}"{attrs}>'
            f"<math {_MATHML_NAMESPACE}>{mathml}</math>{number}"
            f"</{wrapper}>"
        )

    # --- source metadata -----------------------------------------------------
    def _attrs(self, node: RenderNode) -> str:
        parts: list[str] = []
        if node.semantic_id:
            parts.append(f'data-xdlt-id="{escape_attr(node.semantic_id)}"')
        elif node.render_id:
            parts.append(f'data-xdlt-render-id="{escape_attr(node.render_id)}"')
        if self.include_source_metadata and node.source_range:
            parts.append(f'data-xdlt-source-start="{node.source_range.get("start", 0)}"')
            parts.append(f'data-xdlt-source-end="{node.source_range.get("end", 0)}"')
        return f" {' '.join(parts)}" if parts else ""
