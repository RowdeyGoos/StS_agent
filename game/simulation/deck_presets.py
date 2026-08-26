"""Named, pickle-friendly deck presets shared by training and inspection tools."""

from __future__ import annotations

from collections.abc import Callable

from .card import Card, create_ironclad_sequencing_deck, create_starter_deck

DeckFactory = Callable[[], list[Card]]

_DECK_FACTORIES: dict[str, DeckFactory] = {
    "starter": create_starter_deck,
    "ironclad_sequencing": create_ironclad_sequencing_deck,
}
SUPPORTED_DECKS: tuple[str, ...] = tuple(_DECK_FACTORIES)


def resolve_deck_factory(deck: str) -> DeckFactory:
    """Return the top-level factory registered for one named deck preset."""
    try:
        return _DECK_FACTORIES[deck]
    except KeyError as exc:
        choices = ", ".join(SUPPORTED_DECKS)
        raise ValueError(
            f"Unsupported deck: {deck!r}. Supported decks: {choices}."
        ) from exc
