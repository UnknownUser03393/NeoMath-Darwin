from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Known metadata fields have sensible defaults; anything else is preserved
# verbatim in ``extra`` so third-party / future fields survive a round-trip.
_KNOWN = {
    "title",
    "authors",
    "date",
    "course",
    "institution",
    "version",
    "keywords",
    "language",
}


@dataclass
class Author:
    name: str
    affiliation: str | None = None
    email: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"name": self.name}
        if self.affiliation is not None:
            data["affiliation"] = self.affiliation
        if self.email is not None:
            data["email"] = self.email
        return data

    @classmethod
    def from_value(cls, value: Any) -> "Author":
        if isinstance(value, str):
            return cls(name=value)
        if isinstance(value, dict):
            return cls(
                name=str(value.get("name", "")),
                affiliation=value.get("affiliation"),
                email=value.get("email"),
            )
        return cls(name=str(value))


@dataclass
class Metadata:
    title: str = "未命名文档"
    authors: list[Author] = field(default_factory=list)
    date: str | None = None
    course: str | None = None
    institution: str | None = None
    version: str | None = None
    keywords: list[str] = field(default_factory=list)
    language: str = "zh-CN"
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "title": self.title,
            "authors": [a.to_dict() for a in self.authors],
            "language": self.language,
        }
        for key in ("date", "course", "institution", "version"):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        if self.keywords:
            data["keywords"] = list(self.keywords)
        # Unknown fields are round-tripped without interpretation.
        for key, value in self.extra.items():
            data.setdefault(key, value)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Metadata":
        data = data or {}
        authors_raw = data.get("authors", [])
        if isinstance(authors_raw, (str, dict)):
            authors_raw = [authors_raw]
        extra = {k: v for k, v in data.items() if k not in _KNOWN}
        return cls(
            title=str(data.get("title", "未命名文档")),
            authors=[Author.from_value(a) for a in authors_raw],
            date=data.get("date"),
            course=data.get("course"),
            institution=data.get("institution"),
            version=(str(data["version"]) if data.get("version") is not None else None),
            keywords=[str(k) for k in data.get("keywords", [])],
            language=str(data.get("language", "zh-CN")),
            extra=extra,
        )

    def resolve(self, path: str) -> Any:
        """Resolve a ``@meta.<field>`` reference used from Content.

        Returns ``None`` when the field is absent so callers can decide how to
        render a missing value instead of crashing.
        """
        key = path.split(".", 1)[1] if path.startswith("@meta.") else path
        if key == "title":
            return self.title
        if key in {"author", "authors"}:
            return ", ".join(a.name for a in self.authors)
        if key == "date":
            return self.date
        if hasattr(self, key):
            return getattr(self, key)
        return self.extra.get(key)
