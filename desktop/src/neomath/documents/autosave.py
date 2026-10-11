from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from neomath.documents.model import NeoMathDocument
from neomath.documents.serializer import serialize_document

if TYPE_CHECKING:
    from neomath.edlatex.document import EdDocument


class AutosaveManager:
    """Atomic crash-recovery snapshots kept outside user-selected documents."""

    def __init__(self, data_dir: Path) -> None:
        self.directory = data_dir / "autosave"
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, document: NeoMathDocument) -> Path:
        target = self.directory / f"{document.document_id}.neomath.json"
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(serialize_document(document), encoding="utf-8")
        temporary.replace(target)
        return target

    def save_ed(self, document: "EdDocument") -> Path:
        from neomath.edlatex.serialize import serialize_ed_document

        target = self.directory / f"{document.document_id}.edlatex.json"
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(serialize_ed_document(document), encoding="utf-8")
        temporary.replace(target)
        return target

    def discard(self, document_id: str) -> None:
        for suffix in (".neomath.json", ".edlatex.json"):
            (self.directory / f"{document_id}{suffix}").unlink(missing_ok=True)
