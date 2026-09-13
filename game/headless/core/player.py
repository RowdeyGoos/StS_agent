"""Player state and combat logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from game.headless.core.deck import Deck
from game.headless.core.selection import PendingCardPlay
from game.headless.powers.status import StatusCollection, modify_attack_damage_for_statuses
from game.headless.core.utils import apply_damage_to_block_and_hp

if TYPE_CHECKING:
    from game.headless.cards.base import Card
    from game.headless.monsters.base import Enemy


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
        self.pending_play: PendingCardPlay | None = None
        self.cards_played_this_turn = 0
        self.power_sources: dict[str, int] = {}
        # Alias to the owning combat's enemy slots, rebound by reset/restore/clone.
        # Isolated Player rule fixtures can leave this unset.
        self.combat_enemies: list[Enemy] | None = None

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
        self.cards_played_this_turn = 0
        self.draw_cards(draw_count)

    def draw_cards(self, count: int) -> list[Card]:
        """Draw cards through the player's deck and return the cards drawn."""
        if count < 0:
            raise ValueError("Draw count cannot be negative.")
        if self.combat_is_ending:
            return []
        return self.deck.draw(count)

    @property
    def combat_is_ending(self) -> bool:
        return not self.is_alive or (self.combat_enemies is not None and
                                    not any(e.is_alive for e in self.combat_enemies))

    def end_turn(self) -> None:
        """End the player's turn by discarding the current hand."""
        if self.pending_play is not None:
            raise ValueError("Resolve the pending card choice first.")
        for card in tuple(self.hand):
            if card.spec.end_turn_damage:
                self.take_damage(card.spec.end_turn_damage, is_attack=False)
                if not self.is_alive:
                    return
            if card.spec.ethereal:
                self.hand.remove(card)
                self.deck.exhaust_card(card)
        self.deck.discard_hand()

    def gain_block(self, amount: int, *, powered: bool = False) -> None:
        """Increase player block."""
        if amount < 0:
            raise ValueError("Block gain cannot be negative.")
        self.block += amount * 3 // 4 if powered and self.statuses.get("frail") else amount

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
            incoming_damage, statuses=self.statuses,
        )
        return previous_hp - self.hp

    def apply_status(self, status_name: str, stacks: int, *, source=None) -> None:
        """Apply a status effect to the player."""
        self.statuses.add(status_name, stacks, skip_first_tick=True)
        if source is not None and self.combat_enemies is not None and status_name in ("shrink", "constrict"):
            self.power_sources.setdefault(status_name, self.combat_enemies.index(source))

    def gain_strength(self, amount: int) -> None:
        """Increase player strength."""
        if amount < 0:
            raise ValueError("Strength gain cannot be negative.")
        self.strength += amount

    def add_card_to_discard(self, card: Card) -> None:
        """Add a card directly to the discard pile."""
        self.deck.discard_card(card)

    def card_cost(self, card):
        return card.cost + (self.statuses.get("tangled") if card.spec.kind == "attack" and card.cost >= 0 else 0)

    def play_card(self, hand_index: int, enemy: Enemy) -> Card:
        """Play a card from the hand against the current enemy."""
        if self.pending_play is not None:
            raise ValueError("Resolve the pending card choice first.")
        try:
            card = self.hand[hand_index]
        except IndexError as exc:
            raise IndexError(f"Invalid hand index: {hand_index}.") from exc

        if card.cost < 0:
            raise ValueError(f"{card.name} is unplayable.")
        if self.card_cost(card) > self.energy:
            raise ValueError(f"Not enough energy to play {card.name}.")

        if self.statuses.get("ringing") and self.cards_played_this_turn:
            raise ValueError("Ringing permits only one card this turn.")
        self.energy -= self.card_cost(card)
        self.cards_played_this_turn += 1
        card = self.deck.pop_card_from_hand(hand_index)
        self.deck.in_play.append(card)
        result = card.play(self, enemy)
        if result is not None:
            index, _ = result
            slot = None if not card.spec.uses_target or enemy is None else self.combat_enemies.index(enemy)
            self.pending_play = PendingCardPlay(index, slot)
        else:
            self._finish_card_play()
        return card

    def pending_options(self) -> tuple[str, ...]:
        if self.pending_play is None:
            return ()
        card = self.deck.in_play[0]
        effect = card.definition.effects[self.pending_play.effect_index]
        return tuple(c.instance_id for c in effect.eligible(self))

    def choose_combat_card(self, instance_id: str) -> None:
        if instance_id not in self.pending_options():
            raise ValueError("Illegal combat card choice.")
        pending = self.pending_play
        card = self.deck.in_play[0]
        effect = card.definition.effects[pending.effect_index]
        selected = next(c for c in self.hand if c.instance_id == instance_id)
        effect.resolve(self, selected)
        target = None if pending.target_slot is None else self.combat_enemies[pending.target_slot]
        self.pending_play = None
        result = card.play(self, target, start_effect=pending.effect_index + 1)
        if result is not None:
            self.pending_play = PendingCardPlay(result[0], pending.target_slot)
        else:
            self._finish_card_play()

    def _finish_card_play(self) -> None:
        card = self.deck.in_play[0]
        if card.enchantment is not None:
            from game.headless.enchantments.base import ENCHANTMENTS
            ENCHANTMENTS[card.enchantment.definition_id].on_play(card.enchantment, self)
        if self.combat_enemies is not None:
            for enemy in tuple(self.combat_enemies):
                if enemy.is_alive:
                    enemy.after_player_card(self)
        card = self.deck.in_play.pop()
        if card.exhausts:
            self.deck.exhaust_card(card)
        else:
            self.deck.discard_card(card)
