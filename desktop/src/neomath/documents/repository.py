from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from neomath.documents.model import NeoMathDocument
from neomath.documents.serializer import deserialize_document, serialize_document

if TYPE_CHECKING:
    from neomath.edlatex.document import EdDocument

EDLATEX_SUFFIX = ".edlatex.json"
LEGACY_SUFFIX = ".neomath.json"


class DocumentRepository:
    def __init__(self, data_dir: Path) -> None:
        self.documents_dir = data_dir / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.recent_path = data_dir / "recent.json"

    def save(self, document: NeoMathDocument, path: Path | None = None) -> Path:
        target = path or self.documents_dir / f"{document.document_id}.neomath.json"
        if not target.name.lower().endswith(".neomath.json"):
            target = target.with_name(target.name + ".neomath.json")
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(serialize_document(document), encoding="utf-8")
        temporary.replace(target)
        self._remember(target, document.title)
        return target

    def load(self, path: Path) -> NeoMathDocument:
        document = deserialize_document(path.read_text(encoding="utf-8"))
        self._remember(path, document.title)
        return document

    # --- edLatex (v2) documents ---------------------------------------
    def save_ed(self, document: "EdDocument", path: Path | None = None) -> Path:
        from neomath.edlatex.serialize import serialize_ed_document

        target = path or self.documents_dir / f"{document.document_id}{EDLATEX_SUFFIX}"
        if not target.name.lower().endswith(EDLATEX_SUFFIX):
            target = target.with_name(target.name + EDLATEX_SUFFIX)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(serialize_ed_document(document), encoding="utf-8")
        temporary.replace(target)
        self._remember(target, document.title)
        return target

    def load_ed(self, path: Path) -> "EdDocument":
        """Load any supported document as an EdDocument (legacy is upconverted)."""
        import json

        from neomath.edlatex.compat import ensure_ed_document

        raw = json.loads(path.read_text(encoding="utf-8"))
        document = ensure_ed_document(raw)
        self._remember(path, document.title)
        return document

    def recent(self, limit: int = 8) -> list[dict[str, str]]:
        if not self.recent_path.exists():
            return []
        try:
            import json

            values = json.loads(self.recent_path.read_text(encoding="utf-8"))
            return [value for value in values if Path(value["path"]).exists()][:limit]
        except (OSError, ValueError, KeyError, TypeError):
            return []

    def _remember(self, path: Path, title: str) -> None:
        import json

        values = [value for value in self.recent() if value["path"] != str(path)]
        values.insert(0, {"path": str(path), "title": title})
        self.recent_path.write_text(
            json.dumps(values[:8], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
