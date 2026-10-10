from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Margin:
    top: str = "25mm"
    bottom: str = "25mm"
    left: str = "25mm"
    right: str = "25mm"

    def to_dict(self) -> dict[str, str]:
        return {"top": self.top, "bottom": self.bottom, "left": self.left, "right": self.right}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Margin":
        data = data or {}
        base = cls()
        return cls(
            top=str(data.get("top", base.top)),
            bottom=str(data.get("bottom", base.bottom)),
            left=str(data.get("left", base.left)),
            right=str(data.get("right", base.right)),
        )


@dataclass
class Font:
    size: int = 11
    family: str = "lmodern"

    def to_dict(self) -> dict[str, Any]:
        return {"size": self.size, "family": self.family}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Font":
        data = data or {}
        return cls(size=int(data.get("size", 11)), family=str(data.get("family", "lmodern")))


@dataclass
class Layout:
    """Presentation-only settings.

    Layout never carries content semantics: switching layouts must not change
    any node id or node ordering. Only rendering is affected.
    """

    template: str = "article"
    paper_size: str = "a4"
    columns: int = 1
    margin: Margin = field(default_factory=Margin)
    font: Font = field(default_factory=Font)
    section_style: str = "numbered"
    header: str = "@meta.title"
    footer: str = "page-number"
    theme: str = "light"
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "template": self.template,
            "paperSize": self.paper_size,
            "columns": self.columns,
            "margin": self.margin.to_dict(),
            "font": self.font.to_dict(),
            "sectionStyle": self.section_style,
            "headerFooter": {"header": self.header, "footer": self.footer},
            "theme": self.theme,
        }
        for key, value in self.extra.items():
            data.setdefault(key, value)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Layout":
        data = data or {}
        header_footer = data.get("headerFooter", {}) or {}
        known = {
            "template",
            "paperSize",
            "columns",
            "margin",
            "font",
            "sectionStyle",
            "headerFooter",
            "theme",
        }
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(
            template=str(data.get("template", "article")),
            paper_size=str(data.get("paperSize", "a4")),
            columns=int(data.get("columns", 1)),
            margin=Margin.from_dict(data.get("margin")),
            font=Font.from_dict(data.get("font")),
            section_style=str(data.get("sectionStyle", "numbered")),
            header=str(header_footer.get("header", "@meta.title")),
            footer=str(header_footer.get("footer", "page-number")),
            theme=str(data.get("theme", "light")),
            extra=extra,
        )


# Built-in templates. First iteration only fixes structural defaults; precise
# visual parity with the real journal styles is a later concern, but the
# architecture already routes every template through the same Layout model.
BUILTIN_TEMPLATES: dict[str, dict[str, Any]] = {
    "article": {"template": "article", "columns": 1, "sectionStyle": "numbered"},
    "homework": {
        "template": "homework",
        "columns": 1,
        "sectionStyle": "numbered",
        "font": {"size": 12, "family": "lmodern"},
    },
    "report": {"template": "report", "columns": 1, "sectionStyle": "numbered"},
    "arxiv": {
        "template": "arxiv",
        "columns": 1,
        "sectionStyle": "numbered",
        "margin": {"top": "30mm", "bottom": "30mm", "left": "25mm", "right": "25mm"},
    },
    "neurips": {
        "template": "neurips",
        "columns": 1,
        "sectionStyle": "numbered",
        "font": {"size": 10, "family": "times"},
    },
}


def layout_from_template(name: str) -> Layout:
    """Return a Layout for a built-in template name (falls back to article)."""
    return Layout.from_dict(BUILTIN_TEMPLATES.get(name, BUILTIN_TEMPLATES["article"]))
