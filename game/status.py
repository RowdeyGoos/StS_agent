"""Status effect definitions and helpers for combat simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

SHRINK = "shrink"
VULNERABLE = "vulnerable"
SUPPORTED_STATUS_NAMES: tuple[str, ...] = (SHRINK, VULNERABLE)
STATUS_STACK_SCALE = 5.0


@dataclass(frozen=True, slots=True)
class StatusDefinition:
    """Static behavior metadata for one status effect."""

    name: str
    decrements_at_end_of_owner_turn: bool = True


STATUS_DEFINITIONS: dict[str, StatusDefinition] = {
    SHRINK: StatusDefinition(name=SHRINK, decrements_at_end_of_owner_turn=False),
    VULNERABLE: StatusDefinition(name=VULNERABLE),
}


@dataclass(slots=True)
class StatusCollection:
    """Mutable status stack storage for a combatant."""

    _counts: dict[str, int] = field(default_factory=dict)

    def add(self, status_name: str, stacks: int) -> None:
        """Add stacks of a supported status effect."""
        _require_supported_status(status_name)
        if stacks < 0:
            raise ValueError("Status stacks cannot be negative.")
        if stacks == 0:
            return
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

    def on_turn_end(self) -> None:
        """Apply end-of-turn decay rules to the status set."""
        for status_name, definition in STATUS_DEFINITIONS.items():
            if definition.decrements_at_end_of_owner_turn and self.get(status_name) > 0:
                self.decrement(status_name)

    def as_dict(self) -> dict[str, int]:
        """Return a fixed-shape public dict for observations."""
        return {status_name: self.get(status_name) for status_name in SUPPORTED_STATUS_NAMES}


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
    if get_status_amount(target_statuses, VULNERABLE) > 0:
        modified_damage = (modified_damage * 3) // 2

    return modified_damage


def _require_supported_status(status_name: str) -> None:
    if status_name not in STATUS_DEFINITIONS:
        raise ValueError(f"Unsupported status effect: {status_name!r}")


# TODO: Add more status effects such as Weak, Frail, and poison.
# TODO: Add richer status hooks for start-of-turn, card-play, and damage events.
