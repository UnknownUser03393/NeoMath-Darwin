from __future__ import annotations

import json

from neomath.edlatex.document import EdDocument
from neomath.edlatex.render.base import DocumentRenderer, RenderResult


class JsonRenderer(DocumentRenderer):
    """Serialize the full structured model. Round-trips via EdDocument.from_dict."""

    format = "json"

    def render(self, document: EdDocument) -> RenderResult:
        content = json.dumps(document.to_dict(), ensure_ascii=False, indent=2)
        return RenderResult(format=self.format, content=content)
