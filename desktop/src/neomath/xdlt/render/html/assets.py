"""Render asset model and materialization.

Generated assets (execution images) are represented here; HTML output uses
self-contained data URIs by default and can copy assets to an output directory.
Absolute local paths never leak into exported HTML.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any


class RenderAsset:
    kind = "asset"

    def __init__(self, url: str) -> None:
        self.url = url

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "url": self.url}


class InlineTextAsset(RenderAsset):
    kind = "inline_text"

    def __init__(self, url: str, content: str) -> None:
        super().__init__(url)
        self.content = content


class GeneratedFileAsset(RenderAsset):
    kind = "generated_file"

    def __init__(self, url: str, data_base64: str, mime: str = "image/png") -> None:
        super().__init__(url)
        self.data_base64 = data_base64
        self.mime = mime


class LocalFileAsset(RenderAsset):
    kind = "local_file"

    def __init__(self, url: str, path: str) -> None:
        super().__init__(url)
        self.path = path


def materialize_assets(assets: list[RenderAsset], output_dir: str | Path) -> list[dict[str, Any]]:
    """Write generated assets under ``output_dir/assets/``; return records."""
    directory = Path(output_dir)
    assets_dir = directory / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for index, asset in enumerate(assets):
        if isinstance(asset, GeneratedFileAsset):
            data = base64.b64decode(asset.data_base64)
            filename = f"asset-{index}.{_extension(asset.mime)}"
            (assets_dir / filename).write_bytes(data)
            records.append(
                {"url": f"assets/{filename}", "mime": asset.mime, "written": True}
            )
        else:
            records.append({"url": asset.url, "written": False})
    return records


def _extension(mime: str) -> str:
    return {"image/png": "png", "image/jpeg": "jpg", "image/svg+xml": "svg"}.get(
        mime, "bin"
    )
