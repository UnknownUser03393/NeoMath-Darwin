"""Standalone HTML document assembly.

The title comes from document metadata; the in-body title is never duplicated.
A minimal reference stylesheet is provided for tests / reference export only —
real themes belong to a later layout system, never inline styles here.
"""

from __future__ import annotations

from neomath.xdlt.render.html.escape import escape_html

_REFERENCE_CSS = """
.xdlt-document { max-width: 60rem; margin: 0 auto; padding: 1rem; line-height: 1.5; }
.xdlt-section { margin: 1rem 0; }
.xdlt-paragraph { margin: 0.6rem 0; }
.xdlt-equation { text-align: center; margin: 0.8rem 0; }
.xdlt-equation-number { margin-left: 0.5rem; }
.xdlt-theorem { border: 1px solid #ccc; border-radius: 4px;
 padding: 0.5rem 1rem; margin: 0.8rem 0; }
.xdlt-thesis-header { font-weight: 600; }
.xdlt-proof { padding-left: 1rem; border-left: 2px solid #ccc; margin: 0.8rem 0; }
.xdlt-card-reference { border: 1px solid var(--border-normal, #ccc); border-radius: 4px; padding: 0.5rem 1rem; margin: 0.8rem 0; }
.xdlt-card-header { display: flex; gap: 0.6rem; align-items: baseline; margin-bottom: 0.4rem; }
.xdlt-card-identity { font-weight: 600; }
.xdlt-card-mode { font-size: 0.85rem; color: var(--text-secondary, #666); }
.xdlt-card-empty { color: var(--text-muted, #666); font-style: italic; }
.xdlt-assertion { border-left: 3px solid #999; padding: 0.4rem 0.8rem; margin: 0.6rem 0; }
.xdlt-assertion-valid { border-left-color: #2e7d32; }
.xdlt-assertion-invalid { border-left-color: #c62828; }
.xdlt-assertion-unknown { border-left-color: #f9a825; }
.xdlt-code { background: var(--bg-elevated, #f5f5f5); color: var(--text-primary, inherit); padding: 0.5rem; overflow-x: auto; }
.xdlt-figure { margin: 1rem 0; text-align: center; }
.xdlt-table { border-collapse: collapse; }
.xdlt-table th, .xdlt-table td { border: 1px solid #ccc; padding: 0.3rem 0.6rem; }
.xdlt-exec-status { font-size: 0.85rem; color: #666; }
.xdlt-diagnostic-warning { color: #f9a825; }
.xdlt-diagnostic-error { color: #c62828; }
"""


def reference_css() -> str:
    return _REFERENCE_CSS


def html_document_shell(title: str, body: str, css: str | None = None) -> str:
    stylesheet = css if css is not None else _REFERENCE_CSS
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{escape_html(title)}</title>\n"
        f"<style>{stylesheet}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )
