"""Knowledge card resolution: semantic resources, not JSON blobs."""

from __future__ import annotations

from neomath.xdlt.cards.binding import (
    CardBinding,
    UseCardBody,
    parse_use_card_body,
)
from neomath.xdlt.cards.hash import card_semantic_hash
from neomath.xdlt.cards.loader import card_from_dict, load_card_file
from neomath.xdlt.cards.model import Card, CardParameter
from neomath.xdlt.cards.registry import CardRegistry
from neomath.xdlt.cards.resolver import (
    check_card_requirements,
    parse_card_arguments,
    parse_card_ref,
    resolve_use_card,
)

__all__ = [
    "Card",
    "CardBinding",
    "CardParameter",
    "CardRegistry",
    "UseCardBody",
    "card_from_dict",
    "card_semantic_hash",
    "check_card_requirements",
    "load_card_file",
    "parse_card_arguments",
    "parse_card_ref",
    "parse_use_card_body",
    "resolve_use_card",
]
