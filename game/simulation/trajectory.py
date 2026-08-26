"""Trajectory records and summary statistics for combat episodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .actions import CombatAction

Observation = dict[str, Any]


@dataclass(frozen=True, slots=True)
class TransitionRecord:
    """One environment transition recorded during an episode."""

    step_index: int
    turn: int
    action: CombatAction
    action_index: int
    reward: float
    done: bool
    observation: Observation
    next_observation: Observation
    info: dict[str, Any]


@dataclass(frozen=True, slots=True)
class EpisodeSummary:
    """Aggregate episode metrics useful for training logs."""

    total_reward: float
    steps: int
    final_turn: int
    winner: str | None
    player_hp: int
    enemy_hp: int

    def as_dict(self) -> dict[str, Any]:
        """Return a plain dict representation for loggers and wrappers."""
        return {
            "total_reward": self.total_reward,
            "steps": self.steps,
            "final_turn": self.final_turn,
            "winner": self.winner,
            "player_hp": self.player_hp,
            "enemy_hp": self.enemy_hp,
        }
