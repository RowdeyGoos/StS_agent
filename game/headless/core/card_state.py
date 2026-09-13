"""Owned transient card values and plain, resumable combat rule state."""

from dataclasses import dataclass, field


@dataclass
class CardState:
    extra_damage: int = 0
    cost_change: int = 0
    free_this_turn: bool = False


@dataclass
class CombatRules:
    powers: dict[str, int] = field(default_factory=dict)
    auxiliaries: dict[str, int] = field(default_factory=dict)
    tasks: list[list] = field(default_factory=list)
    plays: dict[str, dict] = field(default_factory=dict)
    attacks_started: int = 0
    attacks_finished: int = 0
    hp_loss_events: int = 0
    hp_lost_this_turn: int = 0
    exhausted_this_turn: int = 0
    player_side: bool = True
    turn_ending: bool = False
    max_hp_gained: int = 0
    ethereal_draws: int = 0
