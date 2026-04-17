"""Enemy state, encounter factories, and intent behavior."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from random import Random
from typing import TYPE_CHECKING, Callable, Sequence

from .status import StatusCollection, modify_attack_damage_for_statuses
from .utils import apply_damage_to_block_and_hp

if TYPE_CHECKING:
    from .player import Player

EncounterFactory = Callable[[Random], Sequence["Enemy"]]


@dataclass(frozen=True, slots=True)
class Intent:
    """Serializable description of an enemy's next planned action."""

    kind: str
    value: int
    move_name: str = ""
    attack_damage: int = 0
    block_gain: int = 0
    strength_gain: int = 0
    status_name: str | None = None
    status_stacks: int = 0
    slimed_added: int = 0

    def as_dict(self) -> dict[str, int | str | None]:
        """Return a plain dict representation for observations and logging."""
        return {
            "kind": self.kind,
            "value": self.value,
            "move_name": self.move_name,
            "attack_damage": self.attack_damage,
            "block_gain": self.block_gain,
            "strength_gain": self.strength_gain,
            "status_name": self.status_name,
            "status_stacks": self.status_stacks,
            "slimed_added": self.slimed_added,
        }


class Enemy(ABC):
    """Base class for an intent-driven enemy combatant."""

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
            "alive": self.is_alive,
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
        from .card import SlimedCard

        current_intent = self.intent

        if current_intent.attack_damage > 0:
            player.take_damage(
                current_intent.attack_damage,
                attacker_statuses=None,
                attacker_strength=0,
            )
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
            block_gain=template.block_gain,
            strength_gain=template.strength_gain,
            status_name=template.status_name,
            status_stacks=template.status_stacks,
            slimed_added=template.slimed_added,
        )


class SimpleEnemy(Enemy):
    """Single deterministic enemy used for early smoke tests."""

    INTENT_CYCLE: tuple[Intent, ...] = (
        Intent(kind="attack", value=6, move_name="Strike", attack_damage=6),
        Intent(kind="defend", value=6, move_name="Defend", block_gain=6),
        Intent(kind="attack", value=8, move_name="Heavy Strike", attack_damage=8),
    )

    def __init__(self, max_hp: int = 40, rng: Random | None = None) -> None:
        super().__init__(name="SimpleEnemy", max_hp=max_hp, rng=rng)
        self._intent_index = 0

    @property
    def intent(self) -> Intent:
        """Return the current deterministic intent."""
        return self._resolve_intent(self.INTENT_CYCLE[self._intent_index])

    def advance_intent(self) -> None:
        """Advance to the next intent in the repeating cycle."""
        self._intent_index = (self._intent_index + 1) % len(self.INTENT_CYCLE)


class Nibbit(Enemy):
    """Solo Nibbit from the Overgrowth easy encounter pool."""

    INTENT_CYCLE: tuple[Intent, ...] = (
        Intent(kind="attack", value=12, move_name="Butt", attack_damage=12),
        Intent(
            kind="attack_defend",
            value=6,
            move_name="Hesitant Slice",
            attack_damage=6,
            block_gain=5,
        ),
        Intent(kind="buff", value=2, move_name="Hiss", strength_gain=2),
    )

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Nibbit", max_hp=rng.randint(42, 46), rng=rng)
        self._intent_index = 0

    @property
    def intent(self) -> Intent:
        return self._resolve_intent(self.INTENT_CYCLE[self._intent_index])

    def advance_intent(self) -> None:
        self._intent_index = (self._intent_index + 1) % len(self.INTENT_CYCLE)


class ShrinkerBeetle(Enemy):
    """Shrinker Beetle from the Overgrowth easy encounter pool."""

    OPENING_INTENT = Intent(
        kind="debuff",
        value=1,
        move_name="Shrinker",
        status_name="shrink",
        status_stacks=1,
    )
    CHOMP = Intent(kind="attack", value=7, move_name="Chomp", attack_damage=7)
    STOMP = Intent(kind="attack", value=13, move_name="Stomp", attack_damage=13)

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Shrinker Beetle", max_hp=rng.randint(38, 40), rng=rng)
        self._used_opening = False
        self._post_opening_index = 0

    @property
    def intent(self) -> Intent:
        if not self._used_opening:
            return self._resolve_intent(self.OPENING_INTENT)
        return self._resolve_intent((self.CHOMP, self.STOMP)[self._post_opening_index])

    def advance_intent(self) -> None:
        if not self._used_opening:
            self._used_opening = True
            self._post_opening_index = 0
            return
        self._post_opening_index = 1 - self._post_opening_index


class FuzzyWurmCrawler(Enemy):
    """Fuzzy Wurm Crawler from the Overgrowth easy encounter pool."""

    INTENT_CYCLE: tuple[Intent, ...] = (
        Intent(kind="attack", value=4, move_name="Acid Goop", attack_damage=4),
        Intent(kind="buff", value=7, move_name="Inhale", strength_gain=7),
        Intent(kind="attack", value=4, move_name="Acid Goop", attack_damage=4),
    )

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Fuzzy Wurm Crawler", max_hp=rng.randint(55, 57), rng=rng)
        self._intent_index = 0

    @property
    def intent(self) -> Intent:
        return self._resolve_intent(self.INTENT_CYCLE[self._intent_index])

    def advance_intent(self) -> None:
        self._intent_index = (self._intent_index + 1) % len(self.INTENT_CYCLE)


class LeafSlimeSmall(Enemy):
    """Small Leaf Slime from Overgrowth."""

    TACKLE = Intent(kind="attack", value=3, move_name="Tackle", attack_damage=3)
    GOOP = Intent(kind="shuffle", value=1, move_name="Goop", slimed_added=1)

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Leaf Slime (S)", max_hp=rng.randint(11, 15), rng=rng)
        self._last_move_name: str | None = None
        self._current_intent = self._choose_next_template()

    @property
    def intent(self) -> Intent:
        return self._resolve_intent(self._current_intent)

    def advance_intent(self) -> None:
        self._last_move_name = self._current_intent.move_name
        self._current_intent = self._choose_next_template()

    def _choose_next_template(self) -> Intent:
        if self._last_move_name is None:
            return self.rng.choice((self.TACKLE, self.GOOP))
        return self.GOOP if self._last_move_name == self.TACKLE.move_name else self.TACKLE


class LeafSlimeMedium(Enemy):
    """Medium Leaf Slime from Overgrowth."""

    INTENT_CYCLE: tuple[Intent, ...] = (
        Intent(kind="shuffle", value=2, move_name="Sticky Shot", slimed_added=2),
        Intent(kind="attack", value=8, move_name="Clump Shot", attack_damage=8),
    )

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Leaf Slime (M)", max_hp=rng.randint(32, 35), rng=rng)
        self._intent_index = 0

    @property
    def intent(self) -> Intent:
        return self._resolve_intent(self.INTENT_CYCLE[self._intent_index])

    def advance_intent(self) -> None:
        self._intent_index = (self._intent_index + 1) % len(self.INTENT_CYCLE)


class TwigSlimeSmall(Enemy):
    """Small Twig Slime from Overgrowth."""

    TACKLE = Intent(kind="attack", value=4, move_name="Tackle", attack_damage=4)

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Twig Slime (S)", max_hp=rng.randint(7, 11), rng=rng)

    @property
    def intent(self) -> Intent:
        return self._resolve_intent(self.TACKLE)

    def advance_intent(self) -> None:
        return


class TwigSlimeMedium(Enemy):
    """Medium Twig Slime from Overgrowth."""

    STICKY_SHOT = Intent(kind="shuffle", value=1, move_name="Sticky Shot", slimed_added=1)
    CHOMP = Intent(kind="attack", value=11, move_name="Chomp", attack_damage=11)

    def __init__(self, rng: Random) -> None:
        super().__init__(name="Twig Slime (M)", max_hp=rng.randint(26, 28), rng=rng)
        self._current_intent = self.STICKY_SHOT

    @property
    def intent(self) -> Intent:
        return self._resolve_intent(self._current_intent)

    def advance_intent(self) -> None:
        if self._current_intent.move_name == self.STICKY_SHOT.move_name:
            self._current_intent = self.CHOMP
            return

        self._current_intent = (
            self.CHOMP if self.rng.random() < (2.0 / 3.0) else self.STICKY_SHOT
        )


def build_overgrowth_easy_encounter(rng: Random) -> list[Enemy]:
    """Sample one encounter uniformly from the Overgrowth first-three-fight pool."""
    encounter_builders: tuple[EncounterFactory, ...] = (
        lambda inner_rng: [Nibbit(inner_rng)],
        _build_overgrowth_easy_slimes_encounter,
        lambda inner_rng: [ShrinkerBeetle(inner_rng)],
        lambda inner_rng: [FuzzyWurmCrawler(inner_rng)],
    )
    encounter_builder = rng.choice(encounter_builders)
    return list(encounter_builder(rng))


def sample_overgrowth_first_three_encounter_builders(
    rng: Random,
) -> tuple[EncounterFactory, ...]:
    """Sample three unique encounter builders from the Overgrowth easy pool."""
    encounter_builders: list[EncounterFactory] = [
        lambda inner_rng: [Nibbit(inner_rng)],
        _build_overgrowth_easy_slimes_encounter,
        lambda inner_rng: [ShrinkerBeetle(inner_rng)],
        lambda inner_rng: [FuzzyWurmCrawler(inner_rng)],
    ]
    rng.shuffle(encounter_builders)
    return tuple(encounter_builders[:3])


def _build_overgrowth_easy_slimes_encounter(rng: Random) -> list[Enemy]:
    """Build the Overgrowth easy Slimes encounter."""
    medium_enemy = rng.choice((LeafSlimeMedium, TwigSlimeMedium))(rng)
    small_enemies = [rng.choice((LeafSlimeSmall, TwigSlimeSmall))(rng) for _ in range(2)]
    return [medium_enemy, *small_enemies]
