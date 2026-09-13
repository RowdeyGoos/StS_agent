"""Plain continuation data for an authored card effect waiting for input."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HandChoice:
    instance_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PendingCardPlay:
    effect_index: int
    target_slot: int | None
