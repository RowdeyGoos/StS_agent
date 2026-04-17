"""Action types for the combat environment."""

from __future__ import annotations

from typing import Literal, TypeAlias

PlayAction: TypeAlias = tuple[Literal["play"], int]
TargetedPlayAction: TypeAlias = tuple[Literal["play"], int, int]
EndTurnAction: TypeAlias = tuple[Literal["end_turn"]]
CombatAction: TypeAlias = PlayAction | TargetedPlayAction | EndTurnAction


def validate_action(action: tuple[object, ...]) -> None:
    """Validate that an action matches the supported tuple-based API."""
    if not action:
        raise ValueError("Action cannot be empty.")

    action_type = action[0]
    if action_type == "play":
        if len(action) == 2 and isinstance(action[1], int):
            return
        if len(action) == 3 and isinstance(action[1], int) and isinstance(action[2], int):
            return
        raise ValueError(
            "Play actions must have the form ('play', hand_index) or "
            "('play', hand_index, target_index)."
        )

    if action_type == "end_turn":
        if len(action) != 1:
            raise ValueError("End-turn actions must have the form ('end_turn',).")
        return

    raise ValueError(f"Unsupported action type: {action_type!r}")
