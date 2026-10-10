from __future__ import annotations

import json
from typing import Any

from neomath.edlatex.document import EdDocument

# Same guard as the legacy serializer: an edLatex container must never persist
# API credentials.
SECRET_FIELDS = {"DASHSCOPE_API_KEY", "qwen_api_key", "apiKey"}


def _assert_no_secrets(data: dict[str, Any]) -> None:
    if SECRET_FIELDS.intersection(data):
        raise ValueError("edLatex document may not contain API credentials")


def serialize_ed_document(document: EdDocument) -> str:
    data = document.to_dict()
    _assert_no_secrets(data)
    _assert_no_secrets(data.get("metadata", {}))
    return json.dumps(data, ensure_ascii=False, indent=2)


def deserialize_ed_document(text: str) -> EdDocument:
    raw: Any = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("edLatex document root must be an object")
    _assert_no_secrets(raw)
    from neomath.edlatex.migration import migrate_ed_document

    return EdDocument.from_dict(migrate_ed_document(raw))
