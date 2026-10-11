"""Render pipeline: resolved Semantic IR -> Render IR -> HTML.

The pipeline never resolves, executes or verifies anything itself; those states
are pre-computed and passed in. Render and HTML result objects carry
diagnostics, assets and source mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neomath.xdlt.execution.result import ExecutionResult
from neomath.xdlt.render.build import RenderBuilder
from neomath.xdlt.render.diagnostics import RenderDiagnostic
from neomath.xdlt.render.html.assets import GeneratedFileAsset, RenderAsset
from neomath.xdlt.render.html.renderer import HTMLRenderer
from neomath.xdlt.render.nodes import (
    RenderDocument,
    RenderImage,
    RenderNode,
)
from neomath.xdlt.verification.protocol import VerificationResult


@dataclass
class RenderResult:
    document: RenderDocument
    diagnostics: list[RenderDiagnostic] = field(default_factory=list)
    assets: list[RenderAsset] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document": self.document.to_dict(),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "assets": [a.to_dict() for a in self.assets],
            "metadata": dict(self.metadata),
        }


@dataclass
class HtmlRenderResult:
    html: str
    assets: list[RenderAsset] = field(default_factory=list)
    diagnostics: list[RenderDiagnostic] = field(default_factory=list)
    source_map: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "html": self.html,
            "assets": [a.to_dict() for a in self.assets],
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "sourceMap": self.source_map,
        }


def build_render_result(
    semantic_ir: dict[str, Any],
    card_registry: Any = None,
    verification: list[VerificationResult] | None = None,
    execution: list[ExecutionResult] | None = None,
    layout: dict[str, Any] | None = None,
) -> RenderResult:
    builder = RenderBuilder(
        semantic_ir,
        card_registry=card_registry,
        verification=verification,
        execution=execution,
        layout=layout,
    )
    document = builder.build()
    return RenderResult(
        document=document,
        diagnostics=builder.diagnostics,
        assets=_collect_assets(document),
        metadata=dict(document.metadata),
    )


def render_html_fragment(
    semantic_ir: dict[str, Any],
    card_registry: Any = None,
    verification: list[VerificationResult] | None = None,
    execution: list[ExecutionResult] | None = None,
    layout: dict[str, Any] | None = None,
    include_source_metadata: bool = True,
) -> HtmlRenderResult:
    render_result = build_render_result(
        semantic_ir,
        card_registry=card_registry,
        verification=verification,
        execution=execution,
        layout=layout,
    )
    renderer = HTMLRenderer(include_source_metadata=include_source_metadata)
    html = renderer.render_fragment(render_result.document)
    return HtmlRenderResult(
        html=html,
        assets=render_result.assets,
        diagnostics=render_result.diagnostics,
        source_map=_source_map(render_result.document),
    )


def render_html_document(
    semantic_ir: dict[str, Any],
    card_registry: Any = None,
    verification: list[VerificationResult] | None = None,
    execution: list[ExecutionResult] | None = None,
    layout: dict[str, Any] | None = None,
    include_source_metadata: bool = True,
) -> HtmlRenderResult:
    render_result = build_render_result(
        semantic_ir,
        card_registry=card_registry,
        verification=verification,
        execution=execution,
        layout=layout,
    )
    renderer = HTMLRenderer(include_source_metadata=include_source_metadata)
    html = renderer.render_standalone(render_result.document)
    return HtmlRenderResult(
        html=html,
        assets=render_result.assets,
        diagnostics=render_result.diagnostics,
        source_map=_source_map(render_result.document),
    )


def render_html_from_result(
    render_result: RenderResult,
    mode: str = "fragment",
    include_source_metadata: bool = True,
) -> HtmlRenderResult:
    renderer = HTMLRenderer(include_source_metadata=include_source_metadata)
    if mode == "document":
        html = renderer.render_standalone(render_result.document)
    else:
        html = renderer.render_fragment(render_result.document)
    return HtmlRenderResult(
        html=html,
        assets=render_result.assets,
        diagnostics=render_result.diagnostics,
        source_map=_source_map(render_result.document),
    )


def render_html(
    semantic_ir: dict[str, Any],
    mode: str = "fragment",
    card_registry: Any = None,
    verification: list[VerificationResult] | None = None,
    execution: list[ExecutionResult] | None = None,
    layout: dict[str, Any] | None = None,
    include_source_metadata: bool = True,
) -> HtmlRenderResult:
    if mode == "document":
        return render_html_document(
            semantic_ir,
            card_registry=card_registry,
            verification=verification,
            execution=execution,
            layout=layout,
            include_source_metadata=include_source_metadata,
        )
    return render_html_fragment(
        semantic_ir,
        card_registry=card_registry,
        verification=verification,
        execution=execution,
        layout=layout,
        include_source_metadata=include_source_metadata,
    )


def iter_render_nodes(node: RenderNode) -> Any:
    yield node
    for child in node.children():
        yield from iter_render_nodes(child)


def _collect_assets(document: RenderDocument) -> list[RenderAsset]:
    assets: list[RenderAsset] = []
    for node in iter_render_nodes(document):
        if not isinstance(node, RenderImage) or not node.src.startswith("data:"):
            continue
        mime, encoded = _parse_data_uri(node.src)
        assets.append(GeneratedFileAsset(node.src, encoded, mime))
    return assets


def _source_map(document: RenderDocument) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for node in iter_render_nodes(document):
        if not node.source_range:
            continue
        entries.append(
            {
                "renderId": node.render_id,
                "semanticId": node.semantic_id,
                "sourceRange": node.source_range,
            }
        )
    return entries


def _parse_data_uri(uri: str) -> tuple[str, str]:
    if ";" in uri and ",base64," in uri:
        header, encoded = uri.split(",base64,", 1)
        mime = header[len("data:"):]
        return mime, encoded
    return "image/png", ""
