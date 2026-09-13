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
        deck.owner = self
        from game.headless.core.card_state import CombatRules

        self.rules = CombatRules()
        self._resolving = False
        self.catalog = None
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
        from game.headless.powers.ironclad import start_turn

        start_turn(self, draw_count)

    def draw_cards(self, count: int) -> list[Card]:
        from game.headless.core.resolution import push, drain

        if count < 0:
            raise ValueError("Draw count cannot be negative.")
        if self.combat_is_ending or self.rules.powers.get("no_draw"):
            return []
        if self._resolving:
            push(self, ["draw", count, False])
            return []
        before = {c.instance_id for c in self.hand}
        push(self, ["draw", count, False])
        drain(self)
        return [c for c in self.hand if c.instance_id not in before]

    @property
    def combat_is_ending(self) -> bool:
        return not self.is_alive or (
            self.combat_enemies is not None and not any(e.is_alive for e in self.combat_enemies)
        )

    def end_turn(self) -> None:
        """End the player's turn by discarding the current hand."""
        if self.pending_play is not None or self.rules.selection is not None:
            raise ValueError("Resolve the pending card choice first.")
        from game.headless.powers.ironclad import end_turn

        end_turn(self)

    def gain_block(self, amount: int, *, powered: bool = False) -> None:
        """Increase player block."""
        if amount < 0:
            raise ValueError("Block gain cannot be negative.")
        from game.headless.powers.ironclad import block_multiplier, record_block, after_block

        if not amount and not powered:
            return
        if powered:
            if self.rules.powers.get("no_block") and self.deck.in_play:
                return
            amount += self.rules.powers.get("dexterity", 0)
            if self.deck.in_play and self.deck.in_play[-1].definition.defend:
                amount += self.rules.powers.get("fasten", 0)
        gain = max(0, amount) * block_multiplier(self, powered)
        if powered and self.statuses.get("frail"):
            gain = gain * 3 // 4
        self.block += gain
        if gain:
            record_block(self, powered)
            after_block(self)

    def take_damage(
        self,
        amount: int,
        is_attack: bool = True,
        attacker_statuses: StatusCollection | None = None,
        attacker_strength: int = 0,
        source=None,
    ) -> int:
        """Apply incoming damage and return the HP damage taken."""
        incoming_damage = (
            modify_attack_damage_for_statuses(
                amount,
                self.statuses,
                attacker_statuses=attacker_statuses,
                attacker_strength=attacker_strength,
                extra_multiplier=(
                    (1, 2)
                    if self.rules.powers.get("colossus")
                    and attacker_statuses is not None
                    and attacker_statuses.get("vulnerable")
                    else (1, 1)
                ),
            )
            if is_attack
            else amount
        )
        previous_hp = self.hp
        self.hp, self.block = apply_damage_to_block_and_hp(
            self.hp,
            self.block,
            incoming_damage,
            statuses=self.statuses,
        )
        damage = previous_hp - self.hp
        from game.headless.powers.ironclad import after_hp_loss

        if damage and is_attack and self.rules.powers.pop("the_gambit", 0):
            self.hp = 0
        if damage:
            after_hp_loss(self, damage)
        if (
            is_attack
            and self.is_alive
            and source is not None
            and source.is_alive
            and self.rules.powers.get("flame_barrier")
        ):
            source.take_damage(self.rules.powers["flame_barrier"], is_attack=False)
        return damage

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

    def gain_energy(self, amount):
        if not self.combat_is_ending and not self.rules.powers.get("no_energy_gain"):
            self.energy += amount

    def card_cost(self, card):
        from game.headless.powers.ironclad import card_cost

        return card_cost(self, card)

    def play_card(self, hand_index: int, enemy) -> Card:
        from game.headless.core.resolution import start_play, drain

        if self.pending_play is not None or self.rules.selection is not None:
            raise ValueError("Resolve the pending card choice first.")
        card = self.hand[hand_index]
        if (card.cost < 0 and not card.spec.x_cost) or self.card_cost(card) > self.energy:
            raise ValueError("Card is unplayable or unaffordable.")
        if self.statuses.get("ringing") and self.cards_played_this_turn:
            raise ValueError("Ringing permits only one card this turn.")
        start_play(self, card, enemy)
        drain(self)
        return card

    def pending_options(self) -> tuple[str, ...]:
        if self.pending_play is None:
            return ()
        card = self.deck.in_play[-1]
        effect = card.definition.effects[self.pending_play.effect_index]
        return tuple(c.instance_id for c in effect.eligible(self))

    def choose_combat_card(self, instance_id: str) -> None:
        if instance_id not in self.pending_options():
            raise ValueError("Illegal combat card choice.")
        from game.headless.core.resolution import drain

        card = self.deck.in_play[-1]
        effect = card.definition.effects[self.pending_play.effect_index]
        selected = next(c for c in effect.eligible(self) if c.instance_id == instance_id)
        self.pending_play = None
        self._resolving = True
        try:
            effect.resolve(self, selected)
        finally:
            self._resolving = False
        drain(self)
