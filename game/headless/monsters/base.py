"""Enemy state, encounter factories, and intent behavior."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from random import Random
from types import MappingProxyType
from typing import TYPE_CHECKING, Callable, Sequence

from game.headless.powers.status import StatusCollection, modify_attack_damage_for_statuses
from game.headless.core.utils import apply_damage_to_block_and_hp

if TYPE_CHECKING:
    from game.headless.core.player import Player

EncounterFactory = Callable[[Random], Sequence["Enemy"]]


@dataclass(frozen=True, slots=True)
class Intent:
    """Serializable description of an enemy's next planned action."""

    kind: str
    value: int
    move_name: str = ""
    attack_damage: int = 0
    attack_count: int = 0
    block_gain: int = 0
    strength_gain: int = 0
    status_name: str | None = None
    status_stacks: int = 0
    slimed_added: int = 0

    def __post_init__(self) -> None:
        if self.attack_damage < 0:
            raise ValueError("Intent attack damage cannot be negative.")
        if self.attack_count < 0:
            raise ValueError("Intent attack count cannot be negative.")
        is_attack_intent = self.kind in {"attack", "attack_defend"}
        if is_attack_intent and self.attack_count <= 0:
            raise ValueError(
                "Attack intents must define a positive attack count."
            )
        if not is_attack_intent and self.attack_count > 0:
            raise ValueError("Non-attack intents cannot define an attack count.")

    def as_dict(self) -> dict[str, int | str | None]:
        """Return a plain dict representation for observations and logging."""
        return {
            "kind": self.kind,
            "value": self.value,
            "move_name": self.move_name,
            "attack_damage": self.attack_damage,
            "attack_count": self.attack_count,
            "block_gain": self.block_gain,
            "strength_gain": self.strength_gain,
            "status_name": self.status_name,
            "status_stacks": self.status_stacks,
            "slimed_added": self.slimed_added,
        }


class Enemy(ABC):
    """Base class for an intent-driven enemy combatant."""

    # Content-owned exceptions for fields whose type changes during play.
    SNAPSHOT_FIELD_TYPES = MappingProxyType({})

    def __init__(self, name: str, max_hp: int, rng: Random | None = None) -> None:
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.block = 0
        self.strength = 0
        self.statuses = StatusCollection()
        self.rng = rng or Random(0)

    @property
    def is_alive(self) -> bool:
        """Return whether the enemy is still alive."""
        return self.hp > 0

    def start_turn(self) -> None:
        """Clear block at the start of the enemy turn."""
        self.block = 0

    def gain_block(self, amount: int) -> None:
        """Increase enemy block."""
        if amount < 0:
            raise ValueError("Block gain cannot be negative.")
        self.block += amount

    def gain_strength(self, amount: int) -> None:
        """Increase enemy strength."""
        if amount < 0:
            raise ValueError("Strength gain cannot be negative.")
        self.strength += amount

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
        """Apply a status effect to the enemy."""
        self.statuses.add(status_name, stacks)

    def to_observation(self) -> dict[str, int | str | bool | dict[str, int] | dict[str, int | str | None]]:
        """Return a plain dict snapshot used by observations and renderers."""
        return {
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "block": self.block,
            "strength": self.strength,
            "statuses": self.statuses.as_dict(),
            "intent": self.intent.as_dict(),
            "behavior_state": self.behavior_state,
            "alive": self.is_alive,
        }

    @property
    def behavior_state(self) -> dict[str, int | str | list[str]]:
        """Return enemy-internal script state needed to reason about future moves.

        This exposes the state that determines future move probabilities without
        revealing any unresolved random outcomes.
        """
        return {
            "phase_index": self._behavior_phase_index(),
            "phase_count": self._behavior_phase_count(),
            "possible_next_move_names": self._possible_next_move_names(),
        }

    @property
    @abstractmethod
    def intent(self) -> Intent:
        """Return the currently telegraphed intent."""

    @abstractmethod
    def advance_intent(self) -> None:
        """Advance to the next intent in the enemy's cycle."""

    def execute_intent(self, player: Player) -> Intent:
        """Execute the current intent and advance to the next one."""
        from game.headless.cards.status import SlimedCard

        current_intent = self.intent

        for _hit_index in range(current_intent.attack_count):
            player.take_damage(
                current_intent.attack_damage,
                attacker_statuses=None,
                attacker_strength=0,
            )
            if not player.is_alive:
                break
        if current_intent.block_gain > 0:
            self.gain_block(current_intent.block_gain)
        if current_intent.strength_gain > 0:
            self.gain_strength(current_intent.strength_gain)
        if current_intent.status_name is not None and current_intent.status_stacks > 0:
            player.apply_status(current_intent.status_name, current_intent.status_stacks)
        for _ in range(current_intent.slimed_added):
            player.add_card_to_discard(SlimedCard())

        self.statuses.on_turn_end()
        self.advance_intent()
        return current_intent

    def _resolve_intent(self, template: Intent) -> Intent:
        """Convert a base intent template into its current combat values."""
        resolved_attack_damage = 0
        if template.attack_damage > 0:
            resolved_attack_damage = modify_attack_damage_for_statuses(
                template.attack_damage,
                {},
                attacker_statuses=self.statuses,
                attacker_strength=self.strength,
            )

        resolved_value = template.value
        if template.kind in {"attack", "attack_defend"}:
            resolved_value = resolved_attack_damage
        elif template.kind == "buff":
            resolved_value = template.strength_gain
        elif template.kind == "defend":
            resolved_value = template.block_gain
        elif template.kind in {"debuff", "shuffle"}:
            resolved_value = template.status_stacks or template.slimed_added

        return Intent(
            kind=template.kind,
            value=resolved_value,
            move_name=template.move_name,
            attack_damage=resolved_attack_damage,
            attack_count=template.attack_count,
            block_gain=template.block_gain,
            strength_gain=template.strength_gain,
            status_name=template.status_name,
            status_stacks=template.status_stacks,
            slimed_added=template.slimed_added,
        )

    def _behavior_phase_index(self) -> int:
        """Return the current position in the enemy's move script."""
        return 0

    def _behavior_phase_count(self) -> int:
        """Return the number of distinct script positions for this enemy."""
        return 1

    def _possible_next_templates(self) -> tuple[Intent, ...]:
        """Return the set of possible next move templates after the current intent."""
        return (self.intent,)

    def _possible_next_move_names(self) -> list[str]:
        """Return unique possible next move names in deterministic order."""
        seen_move_names: set[str] = set()
        move_names: list[str] = []
        for template in self._possible_next_templates():
            move_name = template.move_name
            if move_name in seen_move_names:
                continue
            seen_move_names.add(move_name)
            move_names.append(move_name)
        return move_names
