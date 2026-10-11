"""Project card registry: ``CardId -> versions``.

The registry is scanned from a ``cards/`` directory at build time. Identity and
version stay separate; ``reference`` mode may select the latest compatible
version while ``snapshot`` pins a specific version/content.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from neomath.xdlt.cards.loader import load_card_file
from neomath.xdlt.cards.model import Card


class CardRegistry:
    def __init__(self) -> None:
        self.cards: dict[str, dict[str, Card]] = {}
        self.diagnostics: list[dict[str, Any]] = []

    @classmethod
    def from_directory(cls, cards_dir: str | Path | None) -> "CardRegistry":
        registry = cls()
        if cards_dir is None:
            return registry
        directory = Path(cards_dir)
        if not directory.exists():
            return registry
        for path in sorted(directory.glob("*.card.json")):
            card = load_card_file(path)
            if card is not None:
                registry.register(card)
        return registry

    def register(self, card: Card) -> None:
        for diagnostic in card.diagnostics:
            self.diagnostics.append(dict(diagnostic))
        versions = self.cards.setdefault(card.card_id, {})
        if card.version and card.version in versions:
            self.diagnostics.append(
                {
                    "severity": "error",
                    "code": "DUPLICATE_CARD_VERSION",
                    "message": f"duplicate version '{card.version}' for card '{card.card_id}'",
                }
            )
        if card.version:
            versions[card.version] = card

    def has(self, card_id: str) -> bool:
        return card_id in self.cards

    def versions(self, card_id: str) -> list[str]:
        return sorted(self.cards.get(card_id, {}), key=_version_key)

    def resolve(self, card_id: str, version: str | None = None) -> Card | None:
        versions = self.cards.get(card_id)
        if not versions:
            return None
        if version:
            return versions.get(version)
        versions_list = self.versions(card_id)
        if not versions_list:
            return None
        return versions[versions_list[-1]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cards": [
                {
                    "id": card_id,
                    "versions": [
                        self.cards[card_id][version].to_dict()
                        for version in self.versions(card_id)
                    ],
                }
                for card_id in sorted(self.cards)
            ],
            "diagnostics": list(self.diagnostics),
        }


def _version_key(version: str) -> list[int]:
    def to_int(part: str) -> int:
        digits = "".join(ch for ch in part if ch.isdigit())
        try:
            return int(digits or 0)
        except ValueError:
            return 0

    parts = version.split(".")
    return [to_int(part) for part in parts[:3]]
