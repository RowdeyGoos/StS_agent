"""Player state and combat logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .deck import Deck
from .status import StatusCollection, modify_attack_damage_for_statuses
from .utils import apply_damage_to_block_and_hp

if TYPE_CHECKING:
    from .card import Card
    from .enemy import Enemy


class Player:
    """Represents the player's combat state and card-playing behavior."""

    def __init__(
        self,
        deck: Deck,
        max_hp: int = 80,
        energy_per_turn: int = 3,
    ) -> None:
        self.deck = deck
        self.max_hp = max_hp
        self.hp = max_hp
        self.block = 0
        self.energy_per_turn = energy_per_turn
        self.energy = 0
        self.strength = 0
        self.statuses = StatusCollection()

    @property
    def hand(self) -> list[Card]:
        """Return the current hand."""
        return self.deck.hand

    @property
    def is_alive(self) -> bool:
        """Return whether the player is still alive."""
        return self.hp > 0

    def start_turn(self, draw_count: int = 5) -> None:
        """Start the player's turn by clearing block, resetting energy, and drawing."""
        self.block = 0
        self.energy = self.energy_per_turn
        self.draw_cards(draw_count)

    def draw_cards(self, count: int) -> list[Card]:
        """Draw cards through the player's deck and return the cards drawn."""
        return self.deck.draw(count)

    def end_turn(self) -> None:
        """End the player's turn by discarding the current hand."""
        self.deck.discard_hand()
        self.statuses.on_turn_end()

    def gain_block(self, amount: int) -> None:
        """Increase player block."""
        if amount < 0:
            raise ValueError("Block gain cannot be negative.")
        self.block += amount

    def take_damage(
        self,
        amount: int,
        is_attack: bool = True,
        attacker_statuses: StatusCollection | None = None,
        attacker_strength: int = 0,
    ) -> int:
        """Apply incoming damage and return the HP damage taken."""
        incoming_damage = (
            modify_attack_damage_for_statuses(
                amount,
                self.statuses,
                attacker_statuses=attacker_statuses,
                attacker_strength=attacker_strength,
            )
            if is_attack
            else amount
        )
        previous_hp = self.hp
        self.hp, self.block = apply_damage_to_block_and_hp(
            self.hp,
            self.block,
            incoming_damage,
        )
        return previous_hp - self.hp

    def apply_status(self, status_name: str, stacks: int) -> None:
        """Apply a status effect to the player."""
        self.statuses.add(status_name, stacks)

    def gain_strength(self, amount: int) -> None:
        """Increase player strength."""
        if amount < 0:
            raise ValueError("Strength gain cannot be negative.")
        self.strength += amount

    def add_card_to_discard(self, card: Card) -> None:
        """Add a card directly to the discard pile."""
        self.deck.discard_card(card)

    def play_card(self, hand_index: int, enemy: Enemy) -> Card:
        """Play a card from the hand against the current enemy."""
        try:
            card = self.hand[hand_index]
        except IndexError as exc:
            raise IndexError(f"Invalid hand index: {hand_index}.") from exc

        if card.cost > self.energy:
            raise ValueError(f"Not enough energy to play {card.name}.")

        self.energy -= card.cost
        card = self.deck.pop_card_from_hand(hand_index)
        card.play(self, enemy)

        if card.exhausts:
            self.deck.exhaust_card(card)
        else:
            self.deck.discard_card(card)

        return card
