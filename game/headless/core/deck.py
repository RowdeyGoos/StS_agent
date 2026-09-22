"""Deck and pile management for combat cards."""

from __future__ import annotations

from random import Random
from typing import Sequence

from game.headless.cards.base import Card
from game.headless.core.utils import shuffle_list

MAX_CARDS_IN_HAND = 10


class Deck:
    """Owns draw, discard, hand, and exhaust piles for a combat."""

    def __init__(self, cards: Sequence[Card], rng: Random, streams=None) -> None:
        if len({id(card) for card in cards}) != len(cards):
            raise ValueError("A deck cannot contain the same mutable card object twice.")
        self.rng = rng
        from copy import deepcopy
        for attribute, domain in (("niche_rng","niche"),("selection_rng","combat_card_selection"),("energy_rng","combat_energy_costs"),
                                  ("potion_rng","combat_potion_generation"),("generation_rng","combat_card_generation"),
                                  ("target_rng","combat_targets"),("orb_rng","combat_orb_generation")):
            setattr(self,attribute,streams[domain] if streams is not None else deepcopy(rng))
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
        self.in_play: list[Card] = []
        self.powers: list[Card] = []
        self.offered: list[Card] = []
        self.original_ids = {c.instance_id for c in cards}
        self.sequestered: list[Card] = []
        self.owner = None
        self.shuffle_draw_pile(initial=True)

    def all_cards(self):
        return [c for name in ("draw_pile", "discard_pile", "hand", "exhaust_pile", "in_play", "powers", "offered") for c in getattr(self, name)]

    def shuffle_draw_pile(self, *, initial=False) -> None:
        """Shuffle the draw pile in place."""
        from game.headless.core.native_rng import NativeRng
        native = isinstance(self.rng, NativeRng)
        if native and not initial:
            # Native refill StableShuffle orders by model ID, then upgrade level.
            from game.headless.core.native_shuffle import sort_cards
            sort_cards(self.draw_pile)
        shuffle_list(self.rng, self.draw_pile)
        if native:
            # Native pile index zero is top; this engine's stack pops from the end.
            self.draw_pile.reverse()

        if not initial:
            for card in self.all_cards():
                if card in self.draw_pile and card.enchantment and card.enchantment.definition_id == "perfect_fit":
                    self.draw_pile.remove(card)
                    self.draw_pile.append(card)

    def shuffle_piles(self, *, include_hand=False):
        """Native Shuffle starts with discard, then the current top-first draw pile."""
        from game.headless.core.native_rng import NativeRng
        hand = list(self.hand) if include_hand else []
        if isinstance(self.rng, NativeRng):
            self.draw_pile = self.discard_pile + list(reversed(self.draw_pile)) + hand
        else:
            self.draw_pile = self.draw_pile + hand + self.discard_pile
        self.discard_pile = []
        if include_hand:
            self.hand.clear()
        self.shuffle_draw_pile()

    def draw(self, count: int) -> list[Card]:
        """Draw up to `count` cards, stopping at the game's hand limit.

        Check capacity before refilling: a blocked draw must not shuffle or move
        cards. The limit is a game rule, independent of observation encoders.
        """
        if count < 0:
            raise ValueError("Draw count cannot be negative.")

        drawn_cards: list[Card] = []
        for _ in range(count):
            if len(self.hand) >= MAX_CARDS_IN_HAND:
                break
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
        if self.owner is not None:
            from game.headless.powers.ironclad import after_exhaust
            after_exhaust(self.owner, card)

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
