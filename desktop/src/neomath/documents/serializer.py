from __future__ import annotations

import json
from typing import Any

from neomath.documents.migration import migrate_document
from neomath.documents.model import NeoMathDocument

SECRET_FIELDS = {"OPENAI_API_KEY", "openai_api_key", "apiKey"}


def serialize_document(document: NeoMathDocument) -> str:
    data = document.to_dict()
    if SECRET_FIELDS.intersection(data):
        raise ValueError("document contains a forbidden secret field")
    return json.dumps(data, ensure_ascii=False, indent=2)


def deserialize_document(text: str) -> NeoMathDocument:
    raw: Any = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("NeoMath document root must be an object")
    if SECRET_FIELDS.intersection(raw):
        raise ValueError("NeoMath documents may not contain API credentials")
    return NeoMathDocument.from_dict(migrate_document(raw))
