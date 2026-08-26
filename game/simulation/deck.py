"""Deck and pile management for combat cards."""

from __future__ import annotations

from random import Random
from typing import Sequence

from .card import Card
from .utils import shuffle_list


class Deck:
    """Owns draw, discard, hand, and exhaust piles for a combat."""

    def __init__(self, cards: Sequence[Card], rng: Random) -> None:
        self.rng = rng
        self.draw_pile: list[Card] = list(cards)
        self.discard_pile: list[Card] = []
        self.exhaust_pile: list[Card] = []
        self.hand: list[Card] = []
        self.shuffle_draw_pile()

    def shuffle_draw_pile(self) -> None:
        """Shuffle the draw pile in place."""
        shuffle_list(self.rng, self.draw_pile)

    def draw(self, count: int) -> list[Card]:
        """Draw up to `count` cards into the hand."""
        if count < 0:
            raise ValueError("Draw count cannot be negative.")

        drawn_cards: list[Card] = []
        for _ in range(count):
            if not self.draw_pile:
                self._refill_draw_pile()
            if not self.draw_pile:
                break

            card = self.draw_pile.pop()
            self.hand.append(card)
            drawn_cards.append(card)

        return drawn_cards

    def pop_card_from_hand(self, hand_index: int) -> Card:
        """Remove and return a card from the hand."""
        try:
            return self.hand.pop(hand_index)
        except IndexError as exc:
            raise IndexError(f"Invalid hand index: {hand_index}.") from exc

    def discard_card(self, card: Card) -> None:
        """Move a single card into the discard pile."""
        self.discard_pile.append(card)

    def exhaust_card(self, card: Card) -> None:
        """Move a single card into the exhaust pile."""
        self.exhaust_pile.append(card)

    def discard_hand(self) -> None:
        """Discard the entire current hand."""
        self.discard_pile.extend(self.hand)
        self.hand.clear()

    def _refill_draw_pile(self) -> None:
        """Reshuffle the discard pile into the draw pile when needed."""
        if not self.discard_pile:
            return

        self.draw_pile.extend(self.discard_pile)
        self.discard_pile.clear()
        self.shuffle_draw_pile()
