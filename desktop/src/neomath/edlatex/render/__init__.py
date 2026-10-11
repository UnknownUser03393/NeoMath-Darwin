from __future__ import annotations

from neomath.edlatex.document import EdDocument
from neomath.edlatex.render.base import (
    DocumentRenderer,
    RenderDiagnostic,
    RenderResult,
)
from neomath.edlatex.render.html_renderer import HtmlRenderer
from neomath.edlatex.render.json_renderer import JsonRenderer
from neomath.edlatex.render.latex_renderer import LatexRenderer

_RENDERERS: dict[str, type[DocumentRenderer]] = {
    "json": JsonRenderer,
    "html": HtmlRenderer,
    "latex": LatexRenderer,
    "tex": LatexRenderer,
}


def render_document(document: EdDocument, fmt: str) -> RenderResult:
    """Render ``document`` to ``fmt`` (json | html | latex).

    PDF is intentionally not implemented here: it must be produced from the
    LaTeX (or a controlled HTML) pipeline and honestly reports when the
    toolchain is unavailable rather than faking a result.
    """
    key = fmt.lower()
    if key == "pdf":
        return RenderResult(
            format="pdf",
            content="",
            diagnostics=[
                RenderDiagnostic(
                    severity="error",
                    code="PDF_UNAVAILABLE",
                    message="PDF 需从 LaTeX 工具链生成；请先导出 .tex 再用已配置的 LaTeX 编译。",
                )
            ],
        )
    renderer_cls = _RENDERERS.get(key)
    if renderer_cls is None:
        return RenderResult(
            format=key,
            content="",
            diagnostics=[
                RenderDiagnostic(
                    severity="error",
                    code="UNKNOWN_FORMAT",
                    message=f"不支持的导出格式: {fmt}",
                )
            ],
        )
    return renderer_cls().render(document)


__all__ = [
    "DocumentRenderer",
    "RenderResult",
    "RenderDiagnostic",
    "HtmlRenderer",
    "JsonRenderer",
    "LatexRenderer",
    "render_document",
]
