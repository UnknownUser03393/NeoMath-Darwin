from __future__ import annotations

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
from neomath.edlatex.render.base import DocumentRenderer, RenderDiagnostic, RenderResult

# Template -> LaTeX document class. First iteration maps the arXiv / NeurIPS-like
# templates onto `article`; the architecture already routes every template here
# so a precise style package can be swapped in later without touching Content.
_DOCUMENT_CLASS = {
    "article": "article",
    "homework": "article",
    "report": "report",
    "arxiv": "article",
    "neurips": "article",
}

_SECTION_COMMANDS = {1: "section", 2: "subsection", 3: "subsubsection"}


class LatexRenderer(DocumentRenderer):
    format = "latex"

    def render(self, document: EdDocument) -> RenderResult:
        diagnostics: list[RenderDiagnostic] = []
        meta = document.metadata
        layout = document.layout
        doc_class = _DOCUMENT_CLASS.get(layout.template, "article")

        lines: list[str] = []
        # --- preamble (template owns it; Content never carries \documentclass)
        lines.append(f"\\documentclass[{layout.font.size}pt]{{{doc_class}}}")
        lines.append("\\usepackage{amsmath,amssymb}")
        lines.append("\\usepackage[utf8]{inputenc}")
        if meta.language.startswith("zh"):
            lines.append("\\usepackage{ctex}")
        if layout.template in {"arxiv", "neurips"}:
            lines.append(f"% template:{layout.template} (article base; style pkg TBD)")
        # Metadata is mapped automatically — never duplicated inside Content.
        lines.append(f"\\title{{{_escape(meta.title)}}}")
        if meta.authors:
            authors = " \\and ".join(_escape(a.name) for a in meta.authors)
            lines.append(f"\\author{{{authors}}}")
        if meta.date:
            lines.append(f"\\date{{{_escape(meta.date)}}}")
        lines.append("\\begin{document}")
        lines.append("\\maketitle")

        for node in document.iter_nodes():
            # Preserve node identity in the output for round-trip / blame.
            lines.append(f"% node:{node.id} type:{node.type}")
            rendered = self._render_node(node, diagnostics)
            if rendered:
                lines.append(rendered)
            lines.append("")

        lines.append("\\end{document}")
        return RenderResult(format=self.format, content="\n".join(lines), diagnostics=diagnostics)

    def _render_node(
        self, node: DocumentNode, diagnostics: list[RenderDiagnostic]
    ) -> str:
        if isinstance(node, SectionNode):
            command = _SECTION_COMMANDS.get(node.level, "paragraph")
            return f"\\{command}{{{_escape(node.title)}}}"
        if isinstance(node, ParagraphNode):
            # Prose may contain inline $..$; pass math through untouched.
            return node.source
        if isinstance(node, FormulaNode):
            expr = node.parsed_expression or node.source
            return f"\\[\n{expr}\n\\]" if node.display else f"${expr}$"
        if isinstance(node, DerivationNode):
            # from -> to as an aligned step; rule shown as an annotation.
            return (
                "\\begin{align}\n"
                f"{node.from_expr} &\\;\\longrightarrow\\; {node.to_expr}"
                f" && \\text{{({_escape(node.rule)})}}\n"
                "\\end{align}"
            )
        if isinstance(node, AssertionNode):
            return f"\\[\n{node.expression_ref} = {node.equals}\n\\]"
        if isinstance(node, ContextNode):
            decls = "; ".join(_escape(d) for d in node.declarations)
            return f"\\noindent\\textit{{context: {decls}}}"
        if isinstance(node, CodeNode):
            return f"\\begin{{verbatim}}\n{node.source}\n\\end{{verbatim}}"
        # Unknown / unsupported node -> explicit diagnostic, not silent drop.
        diagnostics.append(
            RenderDiagnostic(
                severity="warning",
                code="UNSUPPORTED_NODE",
                message=f"节点类型 {node.type} 暂无 LaTeX 导出实现",
                node_id=node.id,
            )
        )
        return f"% unsupported node {node.id} ({node.type})"


# Escape LaTeX specials in plain text (NOT applied to math expressions).
_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _escape(text: str) -> str:
    out: list[str] = []
    for ch in text:
        out.append(_SPECIALS.get(ch, ch))
    return "".join(out)
