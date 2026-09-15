"""Owned transient card values and plain, resumable combat rule state."""

from dataclasses import dataclass, field


@dataclass
class CardState:
    extra_damage: int = 0
    cost_change: int = 0
    turn_cost_change: int = 0
    combat_cost_change: int = 0
    free_this_turn: bool = False
    free_this_combat: bool = False
    turn_cost_override: int | None = None
    combat_cost_override: int | None = None
    combat_override_baseline: int = 0
    override_turn_baseline: int = 0
    override_combat_baseline: int = 0
    replay_count: int = 0
    return_next_turn: bool = False
    free_until_played: bool = False
    sly_this_turn: bool = False
    sly_this_combat: bool = False
    retain_this_turn: bool = False
    retain_this_combat: bool = False
    all_enemies: bool = False


@dataclass
class CombatRules:
    powers: dict[str, int] = field(default_factory=dict)
    auxiliaries: dict[str, int] = field(default_factory=dict)
    tasks: list[list] = field(default_factory=list)
    plays: dict[str, dict] = field(default_factory=dict)
    hook_sequence: int = 0
    active_hook: int = 0
    deferred_hooks: list[dict] = field(default_factory=list)
    attacks_started: int = 0
    attacks_finished: int = 0
    hp_loss_events: int = 0
    hp_lost_this_turn: int = 0
    exhausted_this_turn: int = 0
    player_side: bool = True
    turn_ending: bool = False
    max_hp_gained: int = 0
    ethereal_draws: int = 0
    selection: dict | None = None
    power_sequence: int = 0
    skills_started: int = 0
    plays_finished: int = 0
    gold_gained: int = 0
    gold_available: int = 0
    gold_lost: int = 0
    end_turn_hand_size: int = 0
    end_hand_remaining: list[str] = field(default_factory=list)
    potion_slots: int = 3
    potion_pool: list[str] = field(default_factory=lambda: ["fire_potion", "block_potion"])
    potions_generated: list[str] = field(default_factory=list)
    potions: list[dict | None] = field(default_factory=list)
    potion_uses: dict[str, dict] = field(default_factory=dict)

    relics: list[dict] = field(default_factory=list)
    relic_data: dict[str, dict] = field(default_factory=dict)
    round_number: int = 0
    room_kind: str = "combat"
    potion_capacity: int = 3
    enemy_turn: dict | None = None
    discarded_turn: int = 0
    drawn_combat: int = 0
    skills_finished: int = 0
    shivs_finished: int = 0
    extra_card_rewards: int = 0
    nightmares: dict[str, dict] = field(default_factory=dict)
