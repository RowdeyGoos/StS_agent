"""Shared legal-action summaries and feature helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .actions import CombatAction, validate_action
from .card import CardSpec, get_card_spec
from .status import STATUS_STACK_SCALE, SUPPORTED_STATUS_NAMES, modify_attack_damage_for_statuses
from .utils import apply_damage_to_block_and_hp

ObservationLike = Mapping[str, Any]

# Keep card kind ordering stable: neural checkpoints depend on feature positions.
CARD_KIND_ORDER: tuple[str, ...] = ("attack", "block", "skill", "status")


@dataclass(frozen=True, slots=True)
class ActionSummary:
    """Structured tactical summary for one legal action in one observation."""

    action: CombatAction
    card_name: str | None
    card_kind: str | None
    target_index: int | None
    target_enemy_name: str | None
    cost: int
    exhausts: bool
    uses_target: bool
    is_dead_card: bool
    player_energy_after: int
    player_block_after: int
    damage_to_target: int
    block_gain: int
    applies_status_name: str | None
    applies_status_stacks: int
    target_hp_before: int | None
    target_hp_after: int | None
    target_block_before: int | None
    target_block_after: int | None
    target_intent_attack_damage: int
    projected_incoming_hp_loss_before: int
    projected_incoming_hp_loss_after: int
    incoming_hp_loss_reduction: int
    kills_target: bool
    wins_combat: bool
    living_enemy_count_after: int


def infer_legal_actions_from_observation(
    observation: ObservationLike,
) -> tuple[CombatAction, ...]:
    """Infer legal tuple actions directly from a structured observation."""
    player = _require_mapping(observation, "player")
    hand = observation.get("hand")
    enemies = _get_enemies(observation)
    if not isinstance(hand, list):
        raise ValueError("Observation field 'hand' must be a list.")

    energy = int(player["energy"])
    living_enemy_indices = [
        enemy_index
        for enemy_index, enemy in enumerate(enemies)
        if bool(enemy.get("alive", True))
    ]
    legal_actions: list[CombatAction] = [("end_turn",)]
    for hand_index, raw_card_name in enumerate(hand):
        card_name = str(raw_card_name)
        card_spec = get_card_spec(card_name)
        if card_spec.cost > energy:
            continue

        # Non-targeted cards should not be duplicated once per enemy. A Defend
        # is the same action no matter which enemy slot happens to exist.
        if not card_spec.uses_target:
            if len(enemies) == 1 and len(living_enemy_indices) == 1:
                legal_actions.append(("play", hand_index))
            elif living_enemy_indices:
                legal_actions.append(("play", hand_index, living_enemy_indices[0]))
            continue

        # Targeted cards expand into one legal action per living enemy so the
        # policy can learn target selection explicitly.
        if len(enemies) == 1 and len(living_enemy_indices) == 1:
            legal_actions.append(("play", hand_index))
            continue

        for enemy_index in living_enemy_indices:
            legal_actions.append(("play", hand_index, enemy_index))

    return tuple(legal_actions)


def summarize_action(
    observation: ObservationLike,
    action: CombatAction,
) -> ActionSummary:
    """Summarize the immediate tactical effect of one legal action."""
    validate_action(action)
    player = _require_mapping(observation, "player")
    hand = observation.get("hand")
    enemies = _get_enemies(observation)
    if not isinstance(hand, list):
        raise ValueError("Observation field 'hand' must be a list.")

    projected_before = project_incoming_hp_loss(observation)
    player_energy = int(player["energy"])
    player_block = int(player["block"])
    player_strength = int(player.get("strength", 0))
    player_statuses = dict(_require_mapping(player, "statuses"))

    if action[0] == "end_turn":
        return ActionSummary(
            action=action,
            card_name=None,
            card_kind=None,
            target_index=None,
            target_enemy_name=None,
            cost=0,
            exhausts=False,
            uses_target=False,
            is_dead_card=False,
            player_energy_after=player_energy,
            player_block_after=player_block,
            damage_to_target=0,
            block_gain=0,
            applies_status_name=None,
            applies_status_stacks=0,
            target_hp_before=None,
            target_hp_after=None,
            target_block_before=None,
            target_block_after=None,
            target_intent_attack_damage=0,
            projected_incoming_hp_loss_before=projected_before,
            projected_incoming_hp_loss_after=projected_before,
            incoming_hp_loss_reduction=0,
            kills_target=False,
            wins_combat=False,
            living_enemy_count_after=sum(
                1 for enemy in enemies if bool(enemy.get("alive", True))
            ),
        )

    hand_index = action[1]
    if hand_index < 0 or hand_index >= len(hand):
        raise ValueError(f"Hand index {hand_index} is out of range for observation hand.")

    card_name = str(hand[hand_index])
    card_spec = get_card_spec(card_name)
    target_index = None if not card_spec.uses_target else _resolve_target_index(action, enemies)
    target_enemy = enemies[target_index] if target_index is not None else None

    # Work on copies so feature construction never mutates the real observation.
    # We only simulate the immediate card effect, not the whole future turn.
    copied_enemies = [_copy_enemy(enemy) for enemy in enemies]
    copied_target = copied_enemies[target_index] if target_index is not None else None

    player_energy_after = max(0, player_energy - card_spec.cost)
    player_block_after = player_block + card_spec.block_gain

    damage_to_target = 0
    target_hp_before: int | None = None
    target_hp_after: int | None = None
    target_block_before: int | None = None
    target_block_after: int | None = None
    target_intent_attack_damage = 0

    if copied_target is not None:
        target_hp_before = int(copied_target["hp"])
        target_block_before = int(copied_target["block"])
        target_intent = _require_mapping(copied_target, "intent")
        target_intent_attack_damage = int(target_intent.get("attack_damage", 0))

        if card_spec.base_damage > 0:
            # Damage features use the same status/strength rules as combat.
            damage_to_target = modify_attack_damage_for_statuses(
                card_spec.base_damage,
                _require_mapping(copied_target, "statuses"),
                attacker_statuses=player_statuses,
                attacker_strength=player_strength,
            )
            copied_target["hp"], copied_target["block"] = apply_damage_to_block_and_hp(
                int(copied_target["hp"]),
                int(copied_target["block"]),
                damage_to_target,
            )
            copied_target["alive"] = int(copied_target["hp"]) > 0

        if (
            card_spec.applies_status_name is not None
            and bool(copied_target.get("alive", True))
        ):
            # Status application matters for action value even when it does not
            # immediately change HP, so include the post-action target state.
            target_statuses = _require_mapping(copied_target, "statuses")
            copied_target["statuses"] = dict(target_statuses)
            copied_target["statuses"][card_spec.applies_status_name] = (
                int(target_statuses.get(card_spec.applies_status_name, 0))
                + card_spec.applies_status_stacks
            )

        target_hp_after = int(copied_target["hp"])
        target_block_after = int(copied_target["block"])

    # This is the defensive signal used by reward shaping and action features:
    # how much visible incoming HP loss would remain after playing this card?
    projected_after = project_incoming_hp_loss_from_state(
        player_hp=int(player["hp"]),
        player_block=player_block_after,
        player_statuses=player_statuses,
        enemies=copied_enemies,
    )
    living_enemy_count_after = sum(
        1 for enemy in copied_enemies if bool(enemy.get("alive", True))
    )
    kills_target = (
        target_hp_before is not None
        and target_hp_after is not None
        and target_hp_before > 0
        and target_hp_after <= 0
    )

    return ActionSummary(
        action=action,
        card_name=card_name,
        card_kind=card_spec.kind,
        target_index=target_index,
        target_enemy_name=None if target_enemy is None else str(target_enemy["name"]),
        cost=card_spec.cost,
        exhausts=card_spec.exhausts,
        uses_target=card_spec.uses_target,
        is_dead_card=card_spec.is_dead_card,
        player_energy_after=player_energy_after,
        player_block_after=player_block_after,
        damage_to_target=damage_to_target,
        block_gain=card_spec.block_gain,
        applies_status_name=card_spec.applies_status_name,
        applies_status_stacks=card_spec.applies_status_stacks,
        target_hp_before=target_hp_before,
        target_hp_after=target_hp_after,
        target_block_before=target_block_before,
        target_block_after=target_block_after,
        target_intent_attack_damage=target_intent_attack_damage,
        projected_incoming_hp_loss_before=projected_before,
        projected_incoming_hp_loss_after=projected_after,
        incoming_hp_loss_reduction=max(0, projected_before - projected_after),
        kills_target=kills_target,
        wins_combat=living_enemy_count_after == 0,
        living_enemy_count_after=living_enemy_count_after,
    )


def project_incoming_hp_loss(observation: ObservationLike) -> int:
    """Estimate HP loss from currently telegraphed enemy attacks."""
    player = _require_mapping(observation, "player")
    return project_incoming_hp_loss_from_state(
        player_hp=int(player["hp"]),
        player_block=int(player["block"]),
        player_statuses=dict(_require_mapping(player, "statuses")),
        enemies=[_copy_enemy(enemy) for enemy in _get_enemies(observation)],
    )


def project_incoming_hp_loss_from_state(
    player_hp: int,
    player_block: int,
    player_statuses: Mapping[str, Any],
    enemies: list[dict[str, Any]],
) -> int:
    """Estimate projected HP loss from currently visible enemy intents."""
    original_hp = player_hp
    simulated_hp = player_hp
    simulated_block = player_block

    # Process living enemies in slot order, mirroring the enemy phase closely
    # enough for a one-turn tactical estimate.
    for enemy in enemies:
        if not bool(enemy.get("alive", True)):
            continue
        intent = _require_mapping(enemy, "intent")
        attack_damage = int(intent.get("attack_damage", 0))
        if attack_damage <= 0:
            continue

        resolved_damage = modify_attack_damage_for_statuses(
            attack_damage,
            player_statuses,
        )
        simulated_hp, simulated_block = apply_damage_to_block_and_hp(
            simulated_hp,
            simulated_block,
            resolved_damage,
        )
        if simulated_hp <= 0:
            return original_hp

    return max(0, original_hp - simulated_hp)


def encode_action_summary_features(
    summary: ActionSummary,
    *,
    supported_card_names: tuple[str, ...],
    supported_enemy_names: tuple[str, ...],
    supported_status_names: tuple[str, ...] = SUPPORTED_STATUS_NAMES,
    max_enemy_count: int,
    hp_scale: int,
    energy_per_turn: int,
) -> tuple[float, ...]:
    """Encode one structured action summary into a numeric feature vector."""
    # These features are consumed by action-conditioned neural policies. The
    # order must stay aligned with action_feature_names().
    action_type_features = (
        1.0 if summary.action[0] == "end_turn" else 0.0,
        1.0 if summary.action[0] == "play" else 0.0,
    )
    card_kind_features = tuple(
        1.0 if summary.card_kind == card_kind else 0.0
        for card_kind in CARD_KIND_ORDER
    )
    card_name_features = tuple(
        1.0 if summary.card_name == card_name else 0.0
        for card_name in supported_card_names
    )
    applies_status_features = tuple(
        (
            float(summary.applies_status_stacks) / STATUS_STACK_SCALE
            if summary.applies_status_name == status_name
            else 0.0
        )
        for status_name in supported_status_names
    )
    target_enemy_type_features = tuple(
        1.0 if summary.target_enemy_name == enemy_name else 0.0
        for enemy_name in supported_enemy_names
    )
    target_slot_fraction = 0.0
    if summary.target_index is not None and max_enemy_count > 1:
        # Slot position is useful, but normalized so the network does not see
        # raw integer IDs on a different scale from the rest of the features.
        target_slot_fraction = float(summary.target_index) / float(max_enemy_count - 1)

    return (
        1.0,
        *action_type_features,
        *card_kind_features,
        *card_name_features,
        float(summary.cost) / float(max(1, energy_per_turn)),
        float(summary.player_energy_after) / float(max(1, energy_per_turn)),
        1.0 if summary.exhausts else 0.0,
        1.0 if summary.uses_target else 0.0,
        1.0 if summary.is_dead_card else 0.0,
        float(summary.damage_to_target) / float(max(1, hp_scale)),
        float(summary.block_gain) / float(max(1, hp_scale)),
        *applies_status_features,
        1.0 if summary.target_index is not None else 0.0,
        target_slot_fraction,
        (
            0.0
            if summary.target_hp_before is None
            else float(summary.target_hp_before) / float(max(1, hp_scale))
        ),
        (
            0.0
            if summary.target_hp_after is None
            else float(max(0, summary.target_hp_after)) / float(max(1, hp_scale))
        ),
        (
            0.0
            if summary.target_block_before is None
            else float(summary.target_block_before) / float(max(1, hp_scale))
        ),
        (
            0.0
            if summary.target_block_after is None
            else float(summary.target_block_after) / float(max(1, hp_scale))
        ),
        float(summary.target_intent_attack_damage) / float(max(1, hp_scale)),
        1.0 if summary.kills_target else 0.0,
        1.0 if summary.wins_combat else 0.0,
        float(summary.player_block_after) / float(max(1, hp_scale)),
        float(summary.projected_incoming_hp_loss_before) / float(max(1, hp_scale)),
        float(summary.projected_incoming_hp_loss_after) / float(max(1, hp_scale)),
        float(summary.incoming_hp_loss_reduction) / float(max(1, hp_scale)),
        float(summary.living_enemy_count_after) / float(max(1, max_enemy_count)),
        *target_enemy_type_features,
    )


def action_feature_names(
    *,
    supported_card_names: tuple[str, ...],
    supported_enemy_names: tuple[str, ...],
    supported_status_names: tuple[str, ...] = SUPPORTED_STATUS_NAMES,
) -> tuple[str, ...]:
    """Return semantic names for encoded action features."""
    return (
        "is_legal",
        "is_end_turn",
        "is_play",
        *(f"card_kind_is_{card_kind}" for card_kind in CARD_KIND_ORDER),
        *(f"card_is_{card_name.lower()}" for card_name in supported_card_names),
        "cost_fraction",
        "energy_after_fraction",
        "exhausts",
        "uses_target",
        "is_dead_card",
        "damage_to_target_fraction",
        "block_gain_fraction",
        *(
            f"applies_status_{status_name}_fraction"
            for status_name in supported_status_names
        ),
        "target_exists",
        "target_slot_fraction",
        "target_hp_before_fraction",
        "target_hp_after_fraction",
        "target_block_before_fraction",
        "target_block_after_fraction",
        "target_intent_attack_fraction",
        "kills_target",
        "wins_combat",
        "player_block_after_fraction",
        "projected_incoming_hp_loss_before_fraction",
        "projected_incoming_hp_loss_after_fraction",
        "incoming_hp_loss_reduction_fraction",
        "living_enemy_count_after_fraction",
        *(f"target_is_{enemy_name.lower().replace(' ', '_').replace('(', '').replace(')', '')}" for enemy_name in supported_enemy_names),
    )


def _get_enemies(observation: ObservationLike) -> list[Mapping[str, Any]]:
    enemies = observation.get("enemies")
    if isinstance(enemies, list):
        return [enemy for enemy in enemies if isinstance(enemy, Mapping)]

    enemy = observation.get("enemy")
    if isinstance(enemy, Mapping):
        return [enemy]

    raise ValueError("Observation must contain 'enemies' or 'enemy'.")


def _require_mapping(container: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = container.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"Observation field {key!r} must be a mapping.")
    return value


def _resolve_target_index(
    action: CombatAction,
    enemies: list[Mapping[str, Any]],
) -> int | None:
    if action[0] != "play":
        return None
    if len(action) == 3:
        return action[2]

    # Two-part play actions are kept for single-enemy compatibility.
    living_enemy_indices = [
        enemy_index
        for enemy_index, enemy in enumerate(enemies)
        if bool(enemy.get("alive", True))
    ]
    if len(living_enemy_indices) == 1:
        return living_enemy_indices[0]
    return None


def _copy_enemy(enemy: Mapping[str, Any]) -> dict[str, Any]:
    copied_enemy = dict(enemy)
    copied_enemy["statuses"] = dict(_require_mapping(enemy, "statuses"))
    copied_enemy["intent"] = dict(_require_mapping(enemy, "intent"))
    copied_enemy["behavior_state"] = dict(_require_mapping(enemy, "behavior_state"))
    return copied_enemy
