"""Utility helpers for deterministic combat simulation."""

from __future__ import annotations

from random import Random
from typing import TypeVar

T = TypeVar("T")


def make_rng(seed: int | None = None) -> Random:
    """Create the dedicated random number generator used by the simulator."""
    return Random(seed)


def shuffle_list(rng: Random, items: list[T]) -> None:
    """Shuffle a list in place using the dedicated RNG."""
    rng.shuffle(items)


def apply_damage_to_block_and_hp(hp: int, block: int, damage: int) -> tuple[int, int]:
    """Apply damage to block first and then HP, clamping both at zero."""
    if damage < 0:
        raise ValueError("Damage cannot be negative.")

    blocked_damage = min(block, damage)
    remaining_damage = damage - blocked_damage
    new_block = block - blocked_damage
    new_hp = max(0, hp - remaining_damage)
    return new_hp, new_block
