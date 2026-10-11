from __future__ import annotations

from typing import Any

from neomath.edlatex.document import EDLATEX_FORMAT_VERSION

# edLatex containers are format version 2. Version 1 is the legacy flat
# NeoMathDocument, handled by the compat layer, not here.


def migrate_ed_document(data: dict[str, Any]) -> dict[str, Any]:
    """Return a current-format edLatex dict, rejecting unknown future formats."""
    migrated = dict(data)
    version = int(migrated.get("formatVersion", EDLATEX_FORMAT_VERSION))

    if version < 2:
        # A v1 flat document reached the ed loader directly. Convert it.
        from neomath.documents.model import NeoMathDocument
        from neomath.edlatex.compat import from_legacy_document

        ed = from_legacy_document(NeoMathDocument.from_dict(migrated))
        return ed.to_dict()

    if version > EDLATEX_FORMAT_VERSION:
        raise ValueError(
            f"edLatex format {version} is newer than supported {EDLATEX_FORMAT_VERSION}"
        )

    migrated["formatVersion"] = EDLATEX_FORMAT_VERSION
    return migrated
