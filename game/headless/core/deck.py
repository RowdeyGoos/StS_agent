"""Deck and pile management for combat cards."""

from __future__ import annotations

from random import Random
from typing import Sequence

from game.headless.cards.base import Card
from game.headless.core.utils import shuffle_list


class Deck:
    """Owns draw, discard, hand, and exhaust piles for a combat."""

    def __init__(self, cards: Sequence[Card], rng: Random) -> None:
        if len({id(card) for card in cards}) != len(cards):
            raise ValueError("A deck cannot contain the same mutable card object twice.")
        self.rng = rng
        self._next_instance_id = 0
        self._allocated_ids = {card.instance_id for card in cards if card.instance_id is not None}
        if len(self._allocated_ids) != sum(card.instance_id is not None for card in cards):
            raise ValueError("Duplicate card instance ID in deck.")
        self.draw_pile: list[Card] = list(cards)
        for card in self.draw_pile:
            self._ensure_identity(card)
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
        self._ensure_identity(card)
        self.discard_pile.append(card)

    def exhaust_card(self, card: Card) -> None:
        """Move a single card into the exhaust pile."""
        self._ensure_identity(card)
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

    def _ensure_identity(self, card: Card) -> None:
        if card.instance_id is not None:
            self._allocated_ids.add(card.instance_id)
            return
        while f"combat.card.{self._next_instance_id}" in self._allocated_ids:
            self._next_instance_id += 1
        card.instance_id = f"combat.card.{self._next_instance_id}"
        self._next_instance_id += 1
        self._allocated_ids.add(card.instance_id)
