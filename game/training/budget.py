"""Shared stopping controls for reproducible training-budget experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TrainingStopReason = Literal["episodes", "environment_steps", "training_time"]


@dataclass(frozen=True, slots=True)
class TrainingBudget:
    """Optional limits applied to the active training phase only."""

    max_environment_steps: int | None = None
    max_training_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.max_environment_steps is not None and self.max_environment_steps <= 0:
            raise ValueError("max_environment_steps must be positive when provided.")
        if self.max_training_seconds is not None and self.max_training_seconds <= 0.0:
            raise ValueError("max_training_seconds must be positive when provided.")

    def stop_reason(
        self,
        *,
        environment_steps: int,
        elapsed_seconds: float,
    ) -> TrainingStopReason | None:
        """Return the first exhausted limit using deterministic precedence."""
        if (
            self.max_environment_steps is not None
            and environment_steps >= self.max_environment_steps
        ):
            return "environment_steps"
        if (
            self.max_training_seconds is not None
            and elapsed_seconds >= self.max_training_seconds
        ):
            return "training_time"
        return None

    def remaining_environment_steps(self, environment_steps: int) -> int | None:
        """Return remaining transitions, or ``None`` when unbounded."""
        if self.max_environment_steps is None:
            return None
        return max(0, self.max_environment_steps - environment_steps)
