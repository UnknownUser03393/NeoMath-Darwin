from __future__ import annotations

from typing import Any

from neomath.documents.model import NeoMathDocument
from neomath.edlatex.document import EdDocument, new_document
from neomath.edlatex.nodes import DerivationNode, DocumentNode, FormulaNode

# ---------------------------------------------------------------------------
# Bridges the legacy flat NeoMathDocument (source string + metadata, v1) and
# the structured EdDocument (v2). Two directions:
#   * from_legacy_document : v1 -> EdDocument (one formula node per source line)
#   * to_legacy_source     : EdDocument -> the flat `source` the C++ MathCore
#                            already consumes line-by-line (identity != rewrite)
# The v1 -> ed -> source round-trip is exact so existing runTrace / analyze /
# replay keep working unchanged.
# ---------------------------------------------------------------------------

# Legacy-only fields kept on the ed document so a v1 doc survives losslessly.
_LEGACY_KEYS = ("breakpoints", "recentProbe", "collapsedSteps")


def from_legacy_document(legacy: NeoMathDocument) -> EdDocument:
    """Convert a flat v1 document into a structured EdDocument."""
    doc = new_document(title=legacy.title)
    doc.document_id = legacy.document_id
    # Each source line becomes a formula node; blank lines are preserved as
    # empty formula nodes so projecting back reproduces the source exactly.
    for line in legacy.source.split("\n"):
        expr = line.strip()
        node = FormulaNode(source=line, parsed_expression=expr or None, display=True)
        doc.add_node(node)
    # Carry legacy interaction state on metadata.extra so nothing is dropped.
    legacy_state: dict[str, Any] = {
        "breakpoints": list(legacy.breakpoints),
        "collapsedSteps": list(legacy.collapsed_steps),
    }
    if legacy.recent_probe is not None:
        legacy_state["recentProbe"] = legacy.recent_probe
    doc.metadata.extra["legacyState"] = legacy_state
    return doc


def _math_nodes(doc: EdDocument) -> list[DocumentNode]:
    return [n for n in doc.iter_nodes() if isinstance(n, (FormulaNode, DerivationNode))]


def to_legacy_source(doc: EdDocument) -> str:
    """Project the document's math nodes to the flat source the core parses.

    * FormulaNode contributes its original source line (exact for v1 docs).
    * DerivationNode contributes its resulting expression (the step's state).
    """
    lines: list[str] = []
    for node in _math_nodes(doc):
        if isinstance(node, FormulaNode):
            lines.append(node.source if node.source else (node.parsed_expression or ""))
        elif isinstance(node, DerivationNode):
            lines.append(node.to_expr or node.from_expr)
    return "\n".join(lines)


def to_legacy_document(doc: EdDocument) -> NeoMathDocument:
    """Build a NeoMathDocument view so existing bridge methods can run."""
    legacy_state = doc.metadata.extra.get("legacyState", {}) if doc.metadata.extra else {}
    return NeoMathDocument(
        source=to_legacy_source(doc),
        title=doc.metadata.title,
        document_id=doc.document_id,
        breakpoints=[int(x) for x in legacy_state.get("breakpoints", [])],
        recent_probe=legacy_state.get("recentProbe"),
        collapsed_steps=[int(x) for x in legacy_state.get("collapsedSteps", [])],
    )


def looks_like_ed_document(data: dict[str, Any]) -> bool:
    """Heuristic: a v2 container has a node map / order or formatVersion >= 2."""
    if int(data.get("formatVersion", 1)) >= 2:
        return True
    return "nodes" in data or "order" in data


def ensure_ed_document(data: dict[str, Any]) -> EdDocument:
    """Load either format into an EdDocument."""
    if looks_like_ed_document(data):
        from neomath.edlatex.migration import migrate_ed_document

        return EdDocument.from_dict(migrate_ed_document(data))
    return from_legacy_document(NeoMathDocument.from_dict(data))
