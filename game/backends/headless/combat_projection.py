"""Public-information projection for legacy ``combat_v0`` observations.

The legacy structured observation is useful simulator diagnostic data, but it
is not itself a policy contract.  This module copies only the accepted combat
subset into :class:`~game.contracts.headless_v0.PublicObservation` and derives
public references exclusively through the caller-provided ``PublicScope``.

Evidence for this adapter is limited to ``combat_v0`` behavior.  In particular,
the projection makes no target-game parity claim and emits no legacy behavior,
RNG, reward-shaping, control, or future-state fields.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping, Sequence

from game.content.card_upgrades import (
    BASE_CARD_PROFILE,
    projected_card_name,
    validate_card_profile,
)
from game.contracts.headless_v0 import (
    CombatOutcome,
    DecisionPhase,
    EvidenceLabel,
    PublicObservation,
    PublicScope,
    StatusKind,
    combat_card_reference,
    combat_enemy_reference,
)
from game.simulation.card import get_card_spec


COMBAT_PROJECTION_VERSION = "combat_v0_public_projection_v1"
COMBAT_PROJECTION_EVIDENCE = EvidenceLabel.COMBAT_V0.value

# These are intentionally closed adapter definitions.  Adding simulator
# content requires an explicit projection review rather than silently exposing
# a newly added legacy name to policy consumers.
CARD_DEFINITION_IDS: Mapping[str, str] = MappingProxyType(
    {
        "Bash": "bash",
        "Body Slam": "body_slam",
        "Defend": "defend",
        "Iron Wave": "iron_wave",
        "Pommel Strike": "pommel_strike",
        "Shrug It Off": "shrug_it_off",
        "Slimed": "slimed",
        "Strike": "strike",
    }
)

ENEMY_DEFINITION_IDS: Mapping[str, str] = MappingProxyType(
    {
        "Fuzzy Wurm Crawler": "fuzzy_wurm_crawler",
        "Leaf Slime (M)": "leaf_slime_m",
        "Leaf Slime (S)": "leaf_slime_s",
        "Mawler": "mawler",
        "Nibbit": "nibbit",
        "Shrinker Beetle": "shrinker_beetle",
        "SimpleEnemy": "simple_enemy",
        "Twig Slime (M)": "twig_slime_m",
        "Twig Slime (S)": "twig_slime_s",
    }
)

# The projector reads only these fields.  The constants make the information
# firewall reviewable without treating legacy observations as a wire schema.
LEGACY_COMBAT_FIELD_ALLOWLIST: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "top": frozenset(
            {
                "discard_pile_size",
                "draw_pile_size",
                "enemies",
                "exhaust_pile_size",
                "hand",
                "player",
                "turn",
            }
        ),
        "player": frozenset(
            {
                "block",
                "energy",
                "energy_per_turn",
                "hp",
                "max_hp",
                "statuses",
                "strength",
            }
        ),
        "statuses": frozenset({"shrink", "vulnerable"}),
        "enemy": frozenset(
            {
                "alive",
                "block",
                "hp",
                "intent",
                "max_hp",
                "name",
                "statuses",
                "strength",
            }
        ),
        "intent": frozenset(
            {
                "attack_count",
                "attack_damage",
                "block_gain",
                "kind",
                "slimed_added",
                "status_name",
                "status_stacks",
                "strength_gain",
            }
        ),
    }
)

# These known legacy diagnostics are explicitly excluded from the public
# projection.  Arbitrary unknown fields are excluded by the same allowlist.
LEGACY_EXCLUDED_FIELD_PATHS = frozenset(
    {
        "card_counts",
        "enemy",
        "enemy_count",
        "enemies[].behavior_state",
        "enemies[].intent.move_name",
        "enemies[].intent.value",
        "living_enemy_count",
    }
)


class CombatProjectionError(ValueError):
    """Raised when a legacy observation cannot be safely projected."""


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CombatProjectionError(f"{path} must be an object.")
    return value


def _require_sequence(value: Any, path: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise CombatProjectionError(f"{path} must be an array.")
    return value


def _required(source: Mapping[str, Any], field: str, path: str) -> Any:
    try:
        return source[field]
    except KeyError as exc:
        raise CombatProjectionError(f"{path}.{field} is required.") from exc


def _definition(
    definitions: Mapping[str, Any],
    legacy_name: Any,
    path: str,
) -> Any:
    if not isinstance(legacy_name, str):
        raise CombatProjectionError(f"{path} must be a string.")
    try:
        return definitions[legacy_name]
    except KeyError as exc:
        raise CombatProjectionError(
            f"{path} names unsupported combat_v0 content: {legacy_name!r}."
        ) from exc


def _project_statuses(value: Any, path: str) -> dict[str, Any]:
    statuses = _require_mapping(value, path)
    return {
        "shrink": _required(statuses, "shrink", path),
        "vulnerable": _required(statuses, "vulnerable", path),
    }


def _project_player(value: Any) -> dict[str, Any]:
    path = "observation.player"
    player = _require_mapping(value, path)
    return {
        "hp": _required(player, "hp", path),
        "max_hp": _required(player, "max_hp", path),
        "block": _required(player, "block", path),
        "energy": _required(player, "energy", path),
        "energy_per_turn": _required(player, "energy_per_turn", path),
        "strength": _required(player, "strength", path),
        "statuses": _project_statuses(
            _required(player, "statuses", path),
            f"{path}.statuses",
        ),
    }


def _project_intent(value: Any, path: str) -> dict[str, Any]:
    intent = _require_mapping(value, path)
    status_name = _required(intent, "status_name", path)
    if status_name is None:
        status_kind = StatusKind.NONE.value
    elif status_name in (StatusKind.SHRINK.value, StatusKind.VULNERABLE.value):
        status_kind = status_name
    else:
        raise CombatProjectionError(
            f"{path}.status_name names an unsupported public status: {status_name!r}."
        )
    return {
        "kind": _required(intent, "kind", path),
        "attack_damage": _required(intent, "attack_damage", path),
        "attack_count": _required(intent, "attack_count", path),
        "block_gain": _required(intent, "block_gain", path),
        "strength_gain": _required(intent, "strength_gain", path),
        "status_kind": status_kind,
        "status_stacks": _required(intent, "status_stacks", path),
        "slimed_added": _required(intent, "slimed_added", path),
    }


def _project_enemies(value: Any, scope: PublicScope) -> list[dict[str, Any]]:
    enemies = _require_sequence(value, "observation.enemies")
    result: list[dict[str, Any]] = []
    for index, raw_enemy in enumerate(enemies):
        path = f"observation.enemies[{index}]"
        enemy = _require_mapping(raw_enemy, path)
        definition_id = _definition(
            ENEMY_DEFINITION_IDS,
            _required(enemy, "name", path),
            f"{path}.name",
        )
        result.append(
            {
                "enemy_ref": combat_enemy_reference(scope, definition_id, index),
                "enemy_definition_id": definition_id,
                "hp": _required(enemy, "hp", path),
                "max_hp": _required(enemy, "max_hp", path),
                "block": _required(enemy, "block", path),
                "strength": _required(enemy, "strength", path),
                "statuses": _project_statuses(
                    _required(enemy, "statuses", path),
                    f"{path}.statuses",
                ),
                "intent": _project_intent(
                    _required(enemy, "intent", path),
                    f"{path}.intent",
                ),
                "alive": _required(enemy, "alive", path),
            }
        )
    return result


def _project_hand(value: Any, scope: PublicScope, card_profile: str) -> list[dict[str, Any]]:
    hand = _require_sequence(value, "observation.hand")
    result: list[dict[str, Any]] = []
    for index, legacy_name in enumerate(hand):
        base_name, upgraded = projected_card_name(legacy_name, card_profile)
        definition_id = _definition(
            CARD_DEFINITION_IDS,
            base_name,
            f"observation.hand[{index}]",
        )
        result.append(
            {
                "card_ref": combat_card_reference(scope, definition_id, index),
                "card_definition_id": definition_id,
                "cost": get_card_spec(legacy_name).cost,
                "upgraded": upgraded,
            }
        )
    return result


def _public_outcome(
    player: Mapping[str, Any],
    enemies: Sequence[Mapping[str, Any]],
) -> CombatOutcome:
    player_defeated = player["hp"] == 0
    enemies_defeated = not any(enemy["alive"] is True for enemy in enemies)
    # CombatEnv cannot produce simultaneous defeat in the current rules.  Do
    # not silently assign an outcome to an externally constructed state.
    if player_defeated and enemies_defeated:
        raise CombatProjectionError(
            "observation has simultaneously defeated player and enemies."
        )
    if player_defeated:
        return CombatOutcome.DEFEAT
    if enemies_defeated:
        return CombatOutcome.VICTORY
    return CombatOutcome.ONGOING


def project_combat_observation(
    observation: Mapping[str, Any],
    public_scope: PublicScope,
    *,
    card_profile: str = BASE_CARD_PROFILE,
) -> PublicObservation:
    """Copy one structured ``CombatEnv`` observation into ``headless_v0``.

    ``public_scope`` is explicit because reference lifetimes are owned by the
    public-history state machine, not recoverable from private environment
    counters.  Enemy aliases use the encounter-reveal ordinal and card aliases
    use the hand-reveal ordinal already declared by that scope.
    """

    validate_card_profile(card_profile)
    if not isinstance(public_scope, PublicScope):
        raise CombatProjectionError("public_scope must be a PublicScope.")
    source = _require_mapping(observation, "observation")
    player = _project_player(_required(source, "player", "observation"))
    enemies = _project_enemies(
        _required(source, "enemies", "observation"),
        public_scope,
    )
    hand = _project_hand(_required(source, "hand", "observation"), public_scope, card_profile)
    outcome = _public_outcome(player, enemies)
    data = {
        "turn": _required(source, "turn", "observation"),
        "player": player,
        "enemies": enemies,
        "hand": hand,
        "draw_pile_size": _required(source, "draw_pile_size", "observation"),
        "discard_pile_size": _required(
            source,
            "discard_pile_size",
            "observation",
        ),
        "exhaust_pile_size": _required(
            source,
            "exhaust_pile_size",
            "observation",
        ),
        "terminal": outcome is not CombatOutcome.ONGOING,
        "outcome": outcome.value,
    }
    return PublicObservation(
        phase=DecisionPhase.COMBAT,
        data=data,
        public_scope=public_scope,
    )
