"""Status effect definitions and helpers for combat simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping
from types import MappingProxyType

SHRINK = "shrink"
VULNERABLE = "vulnerable"
WEAK = "weak"
TERRITORIAL = "territorial"
SLIPPERY = "slippery"
SUPPORTED_STATUS_NAMES: tuple[str, ...] = (SHRINK, VULNERABLE, WEAK, TERRITORIAL, SLIPPERY)
STATUS_STACK_SCALE = 5.0


@dataclass(frozen=True, slots=True)
class StatusDefinition:
    """Static behavior metadata for one status effect."""

    name: str
    duration_tick_side: str | None = "enemy"


STATUS_DEFINITIONS = MappingProxyType({
    SHRINK: StatusDefinition(name=SHRINK, duration_tick_side=None),
    VULNERABLE: StatusDefinition(name=VULNERABLE),
    WEAK: StatusDefinition(name=WEAK),
    TERRITORIAL: StatusDefinition(name=TERRITORIAL, duration_tick_side=None),
    SLIPPERY: StatusDefinition(name=SLIPPERY, duration_tick_side=None),
})


@dataclass(slots=True)
class StatusCollection:
    """Mutable status stack storage for a combatant."""

    _counts: dict[str, int] = field(default_factory=dict)
    _skip_next_tick: set[str] = field(default_factory=set)

    def add(self, status_name: str, stacks: int, *, skip_first_tick: bool = False) -> None:
        """Add stacks of a supported status effect."""
        _require_supported_status(status_name)
        if type(stacks) is not int or stacks < 0:
            raise ValueError("Status stacks cannot be negative.")
        if stacks == 0:
            return
        # Native stacking preserves the existing duration flag; only a new
        # player debuff skips its first enemy-side duration tick.
        if skip_first_tick and self.get(status_name) == 0 and status_name in (WEAK, VULNERABLE):
            self._skip_next_tick.add(status_name)
        self._counts[status_name] = self.get(status_name) + stacks

    def get(self, status_name: str) -> int:
        """Return the current stack count for a supported status."""
        _require_supported_status(status_name)
        return self._counts.get(status_name, 0)

    def decrement(self, status_name: str, amount: int = 1) -> None:
        """Remove status stacks, deleting the entry at zero."""
        _require_supported_status(status_name)
        if amount < 0:
            raise ValueError("Status decrement amount cannot be negative.")
        remaining = self.get(status_name) - amount
        if remaining > 0:
            self._counts[status_name] = remaining
            return
        self._counts.pop(status_name, None)
        self._skip_next_tick.discard(status_name)

    def on_turn_end(self) -> None:
        """Compatibility alias for an isolated enemy's end-of-turn tick."""
        self.after_enemy_side_turn_end()

    def after_enemy_side_turn_end(self) -> None:
        for name, definition in STATUS_DEFINITIONS.items():
            if definition.duration_tick_side != "enemy":
                continue
            if name in self._skip_next_tick:
                self._skip_next_tick.remove(name)
            elif self.get(name):
                self.decrement(name)

    def as_dict(self) -> dict[str, int]:
        """Keep legacy zero fields; include additional implemented active powers."""
        return {name: self.get(name) for name in SUPPORTED_STATUS_NAMES
                if name in (SHRINK, VULNERABLE) or self.get(name)}


def get_status_amount(
    statuses: StatusCollection | Mapping[str, int],
    status_name: str,
) -> int:
    """Read a status count from either a status collection or a plain mapping."""
    _require_supported_status(status_name)
    if isinstance(statuses, StatusCollection):
        return statuses.get(status_name)
    return int(statuses.get(status_name, 0))


def modify_attack_damage_for_statuses(
    base_damage: int,
    target_statuses: StatusCollection | Mapping[str, int],
    attacker_statuses: StatusCollection | Mapping[str, int] | None = None,
    attacker_strength: int = 0,
) -> int:
    """Apply attacker and defender combat modifiers to attack damage."""
    if base_damage < 0:
        raise ValueError("Damage cannot be negative.")

    modified_damage = max(0, base_damage + attacker_strength)
    if attacker_statuses is not None and get_status_amount(attacker_statuses, SHRINK) > 0:
        modified_damage = (modified_damage * 7) // 10
    # Keep fractions until all verified multipliers are combined. The earlier
    # Shrink approximation above remains a separate, reduced-content rule.
    numerator, denominator = 1, 1
    if attacker_statuses is not None and get_status_amount(attacker_statuses, WEAK) > 0:
        numerator *= 3
        denominator *= 4
    if get_status_amount(target_statuses, VULNERABLE) > 0:
        numerator *= 3
        denominator *= 2
    return modified_damage * numerator // denominator


def _require_supported_status(status_name: str) -> None:
    if status_name not in STATUS_DEFINITIONS:
        raise ValueError(f"Unsupported status effect: {status_name!r}")


# TODO: Add more status effects such as Frail and poison.
# TODO: Add richer status hooks for start-of-turn, card-play, and damage events.
