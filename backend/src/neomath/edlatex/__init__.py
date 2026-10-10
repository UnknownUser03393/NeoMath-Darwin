"""edLatex structured math document model.

Public surface for the rest of the app. Core logic here is DOM-free and unit
testable; cross-language transport uses the ``to_dict`` / ``from_dict`` pairs.
"""

from __future__ import annotations

from neomath.edlatex.compat import (
    ensure_ed_document,
    from_legacy_document,
    to_legacy_document,
    to_legacy_source,
)
from neomath.edlatex.document import EdDocument, new_document
from neomath.edlatex.layout import Layout, layout_from_template
from neomath.edlatex.metadata import Author, Metadata
from neomath.edlatex.parser_edl import parse_content_edl, render_content_edl
from neomath.edlatex.serialize import deserialize_ed_document, serialize_ed_document

__all__ = [
    "EdDocument",
    "new_document",
    "Metadata",
    "Author",
    "Layout",
    "layout_from_template",
    "parse_content_edl",
    "render_content_edl",
    "serialize_ed_document",
    "deserialize_ed_document",
    "from_legacy_document",
    "to_legacy_document",
    "to_legacy_source",
    "ensure_ed_document",
]
