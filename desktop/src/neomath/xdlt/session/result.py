"""Compilation results (full and incremental)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neomath.xdlt.render.diff.patches import RenderPatch, serialize_patches
from neomath.xdlt.render.nodes import RenderDocument


@dataclass
class CompilationResult:
    content: str
    semantic_document: dict[str, Any]
    graph: dict[str, Any]
    render_document: RenderDocument
    html: str
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    assets: list[dict[str, Any]] = field(default_factory=list)
    source_map: list[dict[str, Any]] = field(default_factory=list)
    render_diagnostics: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "semanticDocument": self.semantic_document,
            "graph": self.graph,
            "renderDocument": self.render_document.to_dict(),
            "html": self.html,
            "diagnostics": self.diagnostics,
            "assets": self.assets,
            "sourceMap": self.source_map,
            "renderDiagnostics": [d.to_dict() for d in self.render_diagnostics],
        }


@dataclass
class IncrementalCompilationResult(CompilationResult):
    patches: list[RenderPatch] = field(default_factory=list)
    html_patches: list[dict[str, Any]] = field(default_factory=list)
    invalidated_semantic_ids: list[str] = field(default_factory=list)
    reused_verification_count: int = 0
    recomputed_verification_count: int = 0
    reused_execution_count: int = 0
    recomputed_execution_count: int = 0
    reused_parsing: bool = False
    patch_fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "patches": serialize_patches(self.patches),
                "htmlPatches": self.html_patches,
                "invalidatedSemanticIds": self.invalidated_semantic_ids,
                "stats": {
                    "reusedVerification": self.reused_verification_count,
                    "recomputedVerification": self.recomputed_verification_count,
                    "reusedExecution": self.reused_execution_count,
                    "recomputedExecution": self.recomputed_execution_count,
                    "reusedParsing": self.reused_parsing,
                    "patchFallback": self.patch_fallback,
                },
            }
        )
        return data
