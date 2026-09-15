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
    # Execution keeps the authored amount; the displayed amount is rounded.
    # Excluded from public as_dict, included in private dataclass continuation.
    base_attack_damage: int | None = None
    discard_cards: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "discard_cards", tuple(self.discard_cards))
        if any(not isinstance(c, str) or not c for c in self.discard_cards):
            raise ValueError("Generated cards require definition IDs.")
        if self.base_attack_damage is not None and (type(self.base_attack_damage) is not int or self.base_attack_damage < 0):
            raise ValueError("Authored intent damage must be nonnegative or absent.")
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
            **({"discard_cards": list(self.discard_cards)} if self.discard_cards else {}),
        }


class Enemy(ABC):
    """Base class for an intent-driven enemy combatant."""

    # Content-owned exceptions for fields whose type changes during play.
    SNAPSHOT_FIELD_TYPES = MappingProxyType({})
    APPLIED_PLAYER_POWERS = ()

    def __init__(self, name: str, max_hp: int, rng: Random | None = None, *, min_hp: int | None = None) -> None:
        from game.headless.encounters.randomness import MonsterConstruction
        if isinstance(rng, MonsterConstruction):
            max_hp = rng.initial_hp(max_hp if min_hp is None else min_hp, max_hp)
            rng = rng.ai
        elif min_hp is not None:
            max_hp = rng.randint(min_hp, max_hp)
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.block = 0
        self.strength = 0
        self.statuses = StatusCollection()
        self.rng = rng or Random(0)
        self.combat_player = None

    @property
    def is_alive(self) -> bool:
        """Return whether the enemy is still alive."""
        return self.hp > 0

    @property
    def prevents_combat_end(self):
        return False

    @property
    def can_take_turn(self):
        return self.is_alive

    def incoming_attack_multiplier(self):
        return (1, 1)

    def _attack_multiplier(self, attacker_statuses):
        n, d = self.incoming_attack_multiplier()
        player = self.combat_player
        if player is not None and attacker_statuses is player.statuses and self.statuses.get('vulnerable'):
            from game.headless.relics.combat import has
            n *= 150 + player.rules.powers.get('cruelty', 0) + (25 if has(player, 'paper_phrog') else 0)
            d *= 150
        if player is not None and attacker_statuses is player.statuses:
            from game.headless.relics.damage import attack_multiplier
            n *= attack_multiplier(player, player.current_card)
            from game.headless.potions.powers import attack_multiplier as potion_multiplier
            n *= potion_multiplier(player, player.current_card)
            from game.headless.powers.silent import damage_multiplier
            n *= damage_multiplier(player, self)
            if self.statuses.get("conqueror") and player.current_card is not None and player.current_card.definition.definition_id == "sovereign_blade":
                n *= 2
        return n, d

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
        powered: bool = True,
    ) -> int:
        """Apply incoming damage and return the HP damage taken."""
        player = self.combat_player
        if is_attack and powered and player is not None and attacker_statuses is player.statuses:
            from game.headless.relics.damage import attack_bonus
            amount += attack_bonus(player, player.current_card)
            from game.headless.powers.silent import damage_bonus
            amount += damage_bonus(player, player.current_card)
        incoming_damage = (
            modify_attack_damage_for_statuses(
                amount,
                self.statuses,
                attacker_statuses=attacker_statuses,
                attacker_strength=attacker_strength,
                extra_multiplier=self._attack_multiplier(attacker_statuses),
            )
            if is_attack and powered
            else amount
        )
        previous_hp = self.hp
        self.hp, self.block = apply_damage_to_block_and_hp(
            self.hp,
            self.block,
            incoming_damage, statuses=self.statuses,
        )
        if is_attack and powered and player is not None and attacker_statuses is player.statuses:
            slot = str(player.combat_enemies.index(self))
            player.rules.regent_hits[slot] = player.rules.regent_hits.get(slot, 0) + 1
        damage = self._after_damage(previous_hp, is_attack)
        if is_attack and powered and player is not None and attacker_statuses is player.statuses and self.is_alive:
            from game.headless.core.resolution import push
            callbacks = []
            for key, amount in player.rules.powers.items():
                if key == "monarchs_gaze":
                    callbacks.append(["status", player.combat_enemies.index(self), "monarchs_gaze_strength_down", amount])
                elif key == "envenom" and damage:
                    callbacks.append(["status", player.combat_enemies.index(self), "poison", amount])
            push(player, *callbacks)
        return damage

    def take_unblockable_damage(self, amount):
        from game.headless.powers.damage import resolve_unblocked_damage
        previous_hp = self.hp
        self.hp = max(0, self.hp - resolve_unblocked_damage(self.statuses, amount))
        return self._after_damage(previous_hp, False)

    def _after_damage(self, previous_hp, is_attack):
        damage = previous_hp - self.hp
        self.on_damage_taken(damage, is_attack)
        if self.combat_player is not None:
            from game.headless.core.enemy_lifecycle import settle_enemies
            settle_enemies(self.combat_player)
            if previous_hp > 0 and self.hp <= 0 and not self.combat_player.combat_is_ending:
                from game.headless.relics.combat import has
                from game.headless.core.resolution import push
                if has(self.combat_player, "gremlin_horn"):
                    push(self.combat_player, ["death_hook", self.combat_player.combat_enemies.index(self)])
            if previous_hp > 0 and self.hp <= 0 and not self.combat_player._resolving:
                from game.headless.core.resolution import drain
                drain(self.combat_player)
        return damage

    def apply_status(self, status_name: str, stacks: int, *, source=None) -> None:
        """Apply a status effect to the enemy."""
        if source is not None and status_name in ("weak", "vulnerable", "frail", "slow", "constrict", "tangled", "ringing", "shrink", "mangle", "dark_shackles", "demise", "poison", "strangle", "conqueror", "crush_under", "dying_star", "monarchs_gaze_strength_down"):
            from game.headless.relics.damage import debuff_amount
            stacks = debuff_amount(source, source.current_card, stacks)
        if stacks and status_name in ("weak", "vulnerable", "frail", "slow", "constrict", "tangled", "ringing", "shrink", "mangle", "dark_shackles", "demise", "poison", "strangle", "conqueror", "crush_under", "dying_star", "monarchs_gaze_strength_down") and self.statuses.get("artifact"):
            self.statuses.decrement("artifact")
            return
        self.statuses.add(status_name, stacks)
        if status_name == "poison" and stacks and source is not None:
            from game.headless.powers.silent import after_poison
            after_poison(source)
        if status_name == 'vulnerable' and stacks and source is not None:
            source.draw_cards(source.rules.powers.get('vicious', 0))

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

    def execute_intent(self, player: Player, *, tick_statuses: bool = True) -> Intent:
        """Execute the current intent and advance to the next one."""
        from game.headless.cards.status import SlimedCard

        current_intent = self.intent

        for _hit_index in range(current_intent.attack_count):
            self.execute_hit(player, current_intent)
            from game.headless.core.resolution import drain
            drain(player)
            if not player.is_alive or not self.is_alive:
                return current_intent
        self.execute_after_hits(player, current_intent)

        if tick_statuses:
            from game.headless.powers.lifecycle import after_owner_side_turn_end
            self.statuses.on_turn_end()
            after_owner_side_turn_end(self)
        self.advance_intent()
        return current_intent

    def execute_hit(self, player, current_intent):
        player.take_damage(
            current_intent.attack_damage if current_intent.base_attack_damage is None else current_intent.base_attack_damage,
            attacker_statuses=None if current_intent.base_attack_damage is None else self.statuses,
            attacker_strength=-(sum(self.statuses.get(k) for k in ("mangle", "dark_shackles", "crush_under", "dying_star", "monarchs_gaze_strength_down"))) if current_intent.base_attack_damage is None else self.strength - (sum(self.statuses.get(k) for k in ("mangle", "dark_shackles", "crush_under", "dying_star", "monarchs_gaze_strength_down"))),
            source=self,
        )

    def execute_after_hits(self, player, current_intent):
        from game.headless.cards.status import SlimedCard
        if current_intent.block_gain > 0:
            self.gain_block(current_intent.block_gain)
        if current_intent.strength_gain > 0:
            self.gain_strength(current_intent.strength_gain)
        if current_intent.status_name is not None and current_intent.status_stacks > 0:
            player.apply_status(current_intent.status_name, current_intent.status_stacks, source=self)
        for _ in range(current_intent.slimed_added):
            player.add_card_to_discard(SlimedCard())

        if current_intent.discard_cards:
            from game.headless.cards.catalog import DEFAULT_CARDS
            for definition_id in current_intent.discard_cards:
                player.add_card_to_discard(DEFAULT_CARDS.create(definition_id))

        self.after_move(player, current_intent)


    def after_move(self, player, intent):
        """Content-owned effects after the shared ordered move operations."""

    def on_damage_taken(self, damage, is_attack):
        """Content-owned phase/death reactions, resolved between individual hits."""

    def after_player_card(self, player):
        """Content-owned response after a complete card, including its choices."""

    def validate_combat_context(self, player):
        """Validate saved relationships after all owned creature slots exist."""

    def on_combat_state_changed(self, player):
        """Resolve source-owned effects after external combat mutations."""

    def _resolve_intent(self, template: Intent) -> Intent:
        """Convert a base intent template into its current combat values."""
        resolved_attack_damage = 0
        if template.attack_damage > 0:
            resolved_attack_damage = modify_attack_damage_for_statuses(
                template.attack_damage,
                {},
                attacker_statuses=self.statuses,
                attacker_strength=self.strength - (sum(self.statuses.get(k) for k in ("mangle", "dark_shackles", "crush_under", "dying_star", "monarchs_gaze_strength_down"))),
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
            base_attack_damage=template.attack_damage,
            attack_count=template.attack_count,
            block_gain=template.block_gain,
            strength_gain=template.strength_gain,
            status_name=template.status_name,
            status_stacks=template.status_stacks,
            slimed_added=template.slimed_added,
            discard_cards=template.discard_cards,
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
