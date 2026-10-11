"""Render IR: *what* to render, decoupled from HTML / MathML / LaTeX.

Render nodes never carry presentation vocabulary (``div``, ``span``, ``class``).
They carry meaning plus stable identity, source mapping and a deterministic
render hash. Each entity-backed node keeps its ``semanticId``; anonymous nodes
get a stable ``render:<kind>.<ordinal>`` derived from document order.
"""

from __future__ import annotations

from typing import Any

from neomath.xdlt.graph.hash import stable_hash


def identity_payload(node: "RenderNode") -> dict[str, Any]:
    """Position-independent semantic identity for anonymous render nodes.

    This is *identity*, not version: it must be stable across unrelated edits
    (prepending a paragraph must not shift later anonymous IDs), so it never
    contains source offsets, document order, numbering, or resolved display
    state. Editing a node's own content changes its identity by design.
    """
    kind = node.kind
    if kind == "document":
        return {"k": "document"}
    if kind == "heading":
        return {"k": "heading", "level": node.level, "text": node.text}
    if kind == "section":
        return {"k": "section", "title": node.title, "level": node.level}
    if kind == "paragraph":
        return {"k": "paragraph", "c": [identity_payload(child) for child in node.child_nodes]}
    if kind == "text":
        return {"k": "text", "t": node.text}
    if kind == "inline_math":
        return {"k": "math", "m": node.math_ir}
    if kind == "equation":
        return {"k": "equation", "m": node.math_ir}
    if kind in ("reference", "citation"):
        return {"k": kind, "t": node.target_id}
    if kind == "code":
        return {"k": "code", "s": node.source, "l": node.language}
    if kind == "executable":
        return {"k": "executable", "s": node.source, "l": node.language}
    if kind == "image":
        return {"k": "image", "s": node.src}
    if kind == "figure":
        return {
            "k": "figure",
            "c": node.caption,
            "s": getattr(node, "source_target", None),
        }
    if kind == "table":
        return {"k": "table", "h": node.headers, "r": node.rows}
    if kind == "assertion":
        return {"k": "assertion", "c": node.claim, "r": node.requirements}
    if kind == "card_reference":
        return {"k": "card", "i": node.card_id, "v": node.version, "m": node.mode}
    if kind == "diagnostic":
        return {"k": "diagnostic", "c": node.code, "m": node.message}
    if kind in (
        "theorem",
        "lemma",
        "proposition",
        "corollary",
        "definition",
        "example",
        "remark",
        "algorithm",
    ):
        return {"k": kind, "t": node.title}
    if kind == "proof":
        return {"k": "proof", "p": node.proves}
    return {"k": kind, "semanticId": node.semantic_id}


def anonymous_render_id(node: "RenderNode") -> str:
    """Deterministic, position-independent identity for anonymous nodes."""
    digest = stable_hash(identity_payload(node))
    return f"render:{node.kind}:{digest[len('sha256:'):][:12]}"


def contains_opaque(ir: Any | None) -> bool:
    """True when a Math IR subtree contains an unsupported opaque node."""
    if ir is None:
        return False
    if ir.get("kind") == "opaque":
        return True
    for value in ir.values():
        if isinstance(value, dict) and contains_opaque(value):
            return True
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and contains_opaque(item):
                    return True
    return False


class RenderNode:
    kind = "node"

    def __init__(
        self,
        kind: str,
        render_id: str = "",
        semantic_id: str | None = None,
        source_range: dict[str, int] | None = None,
    ) -> None:
        self.kind = kind
        self.render_id = render_id
        self.semantic_id = semantic_id
        self.source_range = source_range
        self.render_hash = ""

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(f"{type(self).__name__!r} has no attribute {name!r}")

    def children(self) -> list["RenderNode"]:
        """All child render nodes (child_nodes, outputs, image, content, ...)."""
        result: list[RenderNode] = []
        for value in self.__dict__.values():
            if isinstance(value, RenderNode):
                result.append(value)
            elif isinstance(value, list):
                result.extend(item for item in value if isinstance(item, RenderNode))
        return result

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "kind": self.kind,
            "renderId": self.render_id,
            "semanticId": self.semantic_id,
            "sourceRange": self.source_range,
            "renderHash": self.render_hash,
        }
        children = self.children()
        if children:
            data["children"] = [child.to_dict() for child in children]
        return data

    def hash_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"kind": self.kind, "semanticId": self.semantic_id}
        for key, value in self.__dict__.items():
            if key in ("render_id", "render_hash", "diagnostics", "source_range"):
                continue
            if isinstance(value, RenderNode):
                payload[key] = value.render_hash
            elif isinstance(value, list):
                payload[key] = [
                    item.render_hash if isinstance(item, RenderNode) else item for item in value
                ]
            else:
                payload[key] = value
        return payload

    def finalize_hash(self, layout_hash: str = "") -> None:
        """Compute the deterministic render hash bottom-up.

        The layout projection participates, so a layout-only change repatches the
        render tree without touching verification or execution.
        """
        for child in self.children():
            child.finalize_hash(layout_hash)
        self.render_hash = stable_hash({"node": self.hash_payload(), "layout": layout_hash})


class RenderDocument(RenderNode):
    def __init__(self, metadata: dict[str, Any] | None = None) -> None:
        super().__init__("document", render_id="render:document")
        self.metadata = metadata or {}
        self.layout: dict[str, Any] = {}
        self.child_nodes: list[RenderNode] = []


class RenderSection(RenderNode):
    def __init__(
        self, level: int, title: str, source_range: dict[str, int] | None = None
    ) -> None:
        super().__init__("section", semantic_id=None, source_range=source_range)
        self.level = level
        self.title = title
        self.child_nodes: list[RenderNode] = []


class RenderHeading(RenderNode):
    def __init__(
        self,
        level: int,
        text: str,
        semantic_id: str | None = None,
        source_range: dict[str, int] | None = None,
    ) -> None:
        super().__init__("heading", semantic_id=semantic_id, source_range=source_range)
        self.level = level
        self.text = text


class RenderParagraph(RenderNode):
    def __init__(self, source_range: dict[str, int] | None = None) -> None:
        super().__init__("paragraph", source_range=source_range)
        self.child_nodes: list[RenderNode] = []


class RenderText(RenderNode):
    def __init__(self, text: str) -> None:
        super().__init__("text")
        self.text = text


class RenderInlineMath(RenderNode):
    def __init__(self, math_ir: dict[str, Any], raw: str = "") -> None:
        super().__init__("inline_math")
        self.math_ir = math_ir
        self.raw = raw


class RenderMathBlock(RenderNode):
    """A display equation; ``semantic_id`` set when it carries a ``#eq:`` id."""

    def __init__(
        self,
        math_ir: dict[str, Any],
        raw: str = "",
        number: str | None = None,
        semantic_id: str | None = None,
        source_range: dict[str, int] | None = None,
    ) -> None:
        super().__init__("equation", semantic_id=semantic_id, source_range=source_range)
        self.math_ir = math_ir
        self.raw = raw
        self.number = number


class RenderThesis(RenderNode):
    """Theorem-like block: theorem/lemma/proposition/corollary/definition/
    example/remark/algorithm share one structure and one HTML framework."""

    def __init__(
        self,
        kind: str,
        semantic_id: str | None,
        number: str | None,
        title: str | None,
        source_range: dict[str, int] | None = None,
    ) -> None:
        super().__init__(kind, semantic_id=semantic_id, source_range=source_range)
        self.number = number
        self.title = title
        self.child_nodes: list[RenderNode] = []


class RenderProof(RenderNode):
    def __init__(
        self,
        proves: str | None,
        source_range: dict[str, int] | None = None,
    ) -> None:
        super().__init__("proof", source_range=source_range)
        self.proves = proves
        self.child_nodes: list[RenderNode] = []


class RenderReference(RenderNode):
    def __init__(self, target_id: str | None, source_range: dict[str, int] | None = None) -> None:
        super().__init__("reference", source_range=source_range)
        self.target_id = target_id
        self.target_kind: str | None = None
        self.display_text: str | None = None
        self.anchor: str | None = None


class RenderCitation(RenderNode):
    def __init__(self, target_id: str | None) -> None:
        super().__init__("citation")
        self.target_id = target_id


class RenderAssertion(RenderNode):
    def __init__(
        self,
        semantic_id: str | None,
        claim: dict[str, Any] | None,
        claim_source: str | None,
        source_range: dict[str, int] | None = None,
    ) -> None:
        super().__init__("assertion", semantic_id=semantic_id, source_range=source_range)
        self.claim = claim
        self.claim_source = claim_source
        self.requirements: list[dict[str, Any]] = []
        self.verification_status: str = "unverified"
        self.verifier: str = ""
        self.message: str = ""
        self.evidence: dict[str, Any] = {}


class RenderCode(RenderNode):
    def __init__(self, source: str, language: str = "") -> None:
        super().__init__("code")
        self.source = source
        self.language = language


class RenderExecutable(RenderNode):
    def __init__(
        self,
        semantic_id: str | None,
        language: str,
        source: str,
        source_range: dict[str, int] | None = None,
    ) -> None:
        super().__init__("executable", semantic_id=semantic_id, source_range=source_range)
        self.language = language
        self.source = source
        self.status: str = "unexecuted"
        self.cached: bool = False
        self.stdout: str = ""
        self.stderr: str = ""
        self.outputs: list[RenderNode] = []


class RenderImage(RenderNode):
    def __init__(self, src: str, mime: str = "image/png", alt: str = "") -> None:
        super().__init__("image")
        self.src = src
        self.mime = mime
        self.alt = alt


class RenderFigure(RenderNode):
    def __init__(
        self,
        semantic_id: str | None,
        number: str | None,
        caption: str,
        source_range: dict[str, int] | None = None,
    ) -> None:
        super().__init__("figure", semantic_id=semantic_id, source_range=source_range)
        self.number = number
        self.caption = caption
        self.image: RenderImage | None = None
        self.available: bool = False
        self.source_target: str | None = None
        self.source_index: str | None = None


class RenderTable(RenderNode):
    def __init__(
        self,
        semantic_id: str | None,
        number: str | None,
        headers: list[str],
        rows: list[list[str]],
        source_range: dict[str, int] | None = None,
    ) -> None:
        super().__init__("table", semantic_id=semantic_id, source_range=source_range)
        self.number = number
        self.headers = headers
        self.rows = rows


class RenderCardReference(RenderNode):
    def __init__(
        self,
        semantic_id: str | None,
        card_id: str | None,
        version: str | None,
        mode: str,
        source_range: dict[str, int] | None = None,
    ) -> None:
        super().__init__("card_reference", semantic_id=semantic_id, source_range=source_range)
        self.card_id = card_id
        self.version = version
        self.mode = mode
        self.provenance: dict[str, Any] = {}
        self.bindings: list[dict[str, Any]] = []
        self.content: list[RenderNode] = []


class RenderDiagnostic(RenderNode):
    def __init__(self, code: str, message: str, severity: str = "warning") -> None:
        super().__init__("diagnostic")
        self.code = code
        self.message = message
        self.severity = severity
