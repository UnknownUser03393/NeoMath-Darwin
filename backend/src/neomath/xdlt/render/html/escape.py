"""HTML escaping.

All plain user text goes through ``escape_html``; raw HTML is never concatenated
into output. ``<script>alert(1)</script>`` in a document stays text.
"""

from __future__ import annotations

_ESCAPES = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
}


def escape_html(text: str) -> str:
    return "".join(_ESCAPES.get(ch, ch) for ch in text)


def escape_attr(value: str) -> str:
    return escape_html(value)
