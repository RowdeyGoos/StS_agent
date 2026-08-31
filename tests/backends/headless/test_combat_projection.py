"""Public-information firewall tests for the combat_v0 projection."""

from __future__ import annotations

from copy import deepcopy

import pytest

from game.backends.headless.combat_projection import (
    CARD_DEFINITION_IDS,
    COMBAT_PROJECTION_EVIDENCE,
    ENEMY_DEFINITION_IDS,
    LEGACY_COMBAT_FIELD_ALLOWLIST,
    LEGACY_EXCLUDED_FIELD_PATHS,
    CombatProjectionError,
    project_combat_observation,
)
from game.backends.headless.scenarios import SUPPORTED_SCENARIOS, scenario_from_id
from game.contracts.headless_v0 import (
    DecisionPhase,
    EvidenceLabel,
    PublicObservation,
    PublicReferenceKind,
    PublicScope,
)
from game.simulation.card import CARD_SPECS
from game.simulation.core import CombatEnv
from game.simulation.enemy import SimpleEnemy


def _scope(
    *,
    history: int = 2,
    decision: int = 0,
    **reveal_overrides: int,
) -> PublicScope:
    reveals = {kind.value: 0 for kind in PublicReferenceKind}
    reveals.update(reveal_overrides)
    return PublicScope(history, decision, reveals)


def _simple_observation(*, seed: int = 17) -> dict[str, object]:
    env = CombatEnv(seed=seed, enemy_factory=lambda: SimpleEnemy(max_hp=20))
    return env.reset()


def test_projection_is_exact_stable_and_combat_v0_labelled() -> None:
    source = _simple_observation()
    scope = _scope(history=4, decision=9, card=3, enemy=2)

    first = project_combat_observation(source, scope)
    second = project_combat_observation(deepcopy(source), scope)

    assert first == second
    assert PublicObservation.from_dict(first.to_dict()) == first
    assert first.phase is DecisionPhase.COMBAT
    assert COMBAT_PROJECTION_EVIDENCE == EvidenceLabel.COMBAT_V0.value
    assert set(first.data) == {
        "discard_pile_size",
        "draw_pile_size",
        "enemies",
        "exhaust_pile_size",
        "hand",
        "outcome",
        "player",
        "terminal",
        "turn",
    }
    assert first.data["enemies"][0]["enemy_definition_id"] == "simple_enemy"
    assert [card["card_definition_id"] for card in first.data["hand"]] == [
        "defend",
        "defend",
        "strike",
        "strike",
        "bash",
    ]
    assert [card["cost"] for card in first.data["hand"]] == [1, 1, 1, 1, 2]
    assert all(card["upgraded"] is False for card in first.data["hand"])
    assert first.data["terminal"] is False
    assert first.data["outcome"] == "ongoing"


def test_projection_output_is_detached_and_deeply_immutable() -> None:
    source = _simple_observation()
    projected = project_combat_observation(source, _scope())

    source["player"]["hp"] = 1
    source["enemies"][0]["hp"] = 1
    source["enemies"][0]["intent"]["attack_damage"] = 999
    source["hand"].clear()

    assert projected.data["player"]["hp"] == 80
    assert projected.data["enemies"][0]["hp"] == 20
    assert projected.data["enemies"][0]["intent"]["attack_damage"] == 6
    assert len(projected.data["hand"]) == 5
    with pytest.raises(TypeError):
        projected.data["player"]["hp"] = 0
    with pytest.raises(TypeError):
        projected.data["enemies"][0]["intent"]["kind"] = "future"


def test_allowlist_excludes_legacy_and_adversarial_private_fields() -> None:
    source = _simple_observation()
    scope = _scope()
    baseline = project_combat_observation(source, scope)
    adversarial = deepcopy(source)

    adversarial.update(
        {
            "action_mask": (1, 0),
            "control_token": "private-control",
            "decision_hash": "private-binding",
            "future_outcome": "victory",
            "rng_state": {"next": 7},
            "seed": 123,
            "shaped_reward": 99.0,
            "snapshot_key": "private-snapshot",
        }
    )
    adversarial["enemy_count"] = 99
    adversarial["living_enemy_count"] = 0
    adversarial["card_counts"] = {"hand": {"Hidden Card": 999}}
    adversarial["enemy"] = {"hidden": "compatibility alias replaced"}
    adversarial["player"]["controller"] = "oracle"
    adversarial["player"]["hidden_hp"] = 999
    adversarial["player"]["statuses"]["future_status"] = 999
    enemy = adversarial["enemies"][0]
    enemy["behavior_state"] = {
        "phase_index": 999,
        "phase_count": 999,
        "possible_next_move_names": ["Lethal Future Move"],
        "rng_state": "private",
    }
    enemy["internal_id"] = "private-enemy"
    enemy["intent"]["move_name"] = "Future Move"
    enemy["intent"]["value"] = 999
    enemy["intent"]["future_damage"] = 999

    assert project_combat_observation(adversarial, scope) == baseline
    assert "behavior_state" not in LEGACY_COMBAT_FIELD_ALLOWLIST["enemy"]
    assert "move_name" not in LEGACY_COMBAT_FIELD_ALLOWLIST["intent"]
    assert {
        "card_counts",
        "enemy",
        "enemy_count",
        "enemies[].behavior_state",
        "enemies[].intent.move_name",
        "enemies[].intent.value",
        "living_enemy_count",
    } == LEGACY_EXCLUDED_FIELD_PATHS


def test_public_reference_lifetimes_depend_only_on_public_scope() -> None:
    source = _simple_observation()
    initial = project_combat_observation(
        source,
        _scope(history=5, decision=1, card=3, enemy=7),
    )
    next_decision = project_combat_observation(
        source,
        _scope(history=5, decision=2, card=3, enemy=7),
    )
    next_hand_reveal = project_combat_observation(
        source,
        _scope(history=5, decision=2, card=4, enemy=7),
    )
    next_encounter_reveal = project_combat_observation(
        source,
        _scope(history=5, decision=2, card=3, enemy=8),
    )
    next_public_history = project_combat_observation(
        source,
        _scope(history=6, decision=0, card=3, enemy=7),
    )

    initial_cards = tuple(card["card_ref"] for card in initial.data["hand"])
    initial_enemies = tuple(enemy["enemy_ref"] for enemy in initial.data["enemies"])
    assert tuple(card["card_ref"] for card in next_decision.data["hand"]) == initial_cards
    assert tuple(enemy["enemy_ref"] for enemy in next_decision.data["enemies"]) == initial_enemies
    assert (
        tuple(card["card_ref"] for card in next_hand_reveal.data["hand"])
        != initial_cards
    )
    assert (
        tuple(enemy["enemy_ref"] for enemy in next_hand_reveal.data["enemies"])
        == initial_enemies
    )
    assert (
        tuple(card["card_ref"] for card in next_encounter_reveal.data["hand"])
        == initial_cards
    )
    assert (
        tuple(enemy["enemy_ref"] for enemy in next_encounter_reveal.data["enemies"])
        != initial_enemies
    )
    assert (
        tuple(card["card_ref"] for card in next_public_history.data["hand"])
        != initial_cards
    )
    assert (
        tuple(enemy["enemy_ref"] for enemy in next_public_history.data["enemies"])
        != initial_enemies
    )


def test_closed_card_allowlist_tracks_combat_v0_registry() -> None:
    assert set(CARD_DEFINITION_IDS) == set(CARD_SPECS)


@pytest.mark.parametrize("scenario_id", SUPPORTED_SCENARIOS)
def test_every_closed_scenario_projects_without_unreviewed_content(
    scenario_id: str,
) -> None:
    source = scenario_from_id(scenario_id, seed=17).build().get_observation()
    projected = project_combat_observation(source, _scope())

    assert all(
        card["card_definition_id"] in set(CARD_DEFINITION_IDS.values())
        for card in projected.data["hand"]
    )
    assert all(
        enemy["enemy_definition_id"] in set(ENEMY_DEFINITION_IDS.values())
        for enemy in projected.data["enemies"]
    )


def test_visible_actor_state_derives_terminal_victory_and_defeat() -> None:
    victory_env = CombatEnv(seed=3, enemy_factory=lambda: SimpleEnemy(max_hp=6))
    victory_env.reset()
    victory_source, _reward, victory_done, _info = victory_env.step(("play", 0))
    assert victory_done
    victory = project_combat_observation(victory_source, _scope())
    assert victory.data["terminal"] is True
    assert victory.data["outcome"] == "victory"

    defeat_env = CombatEnv(
        seed=3,
        player_max_hp=6,
        enemy_factory=lambda: SimpleEnemy(max_hp=20),
    )
    defeat_env.reset()
    defeat_source, _reward, defeat_done, _info = defeat_env.step(("end_turn",))
    assert defeat_done
    defeat = project_combat_observation(defeat_source, _scope())
    assert defeat.data["terminal"] is True
    assert defeat.data["outcome"] == "defeat"


def test_unreachable_simultaneous_defeat_fails_closed() -> None:
    source = _simple_observation()
    source["player"]["hp"] = 0
    source["enemies"][0]["hp"] = 0
    source["enemies"][0]["alive"] = False

    with pytest.raises(CombatProjectionError, match="simultaneously defeated"):
        project_combat_observation(source, _scope())


@pytest.mark.parametrize(
    "mutation, match",
    [
        (lambda observation: observation.pop("hand"), "observation.hand is required"),
        (
            lambda observation: observation["hand"].__setitem__(0, "Unknown Card"),
            "unsupported combat_v0 content",
        ),
        (
            lambda observation: observation["enemies"][0].__setitem__(
                "name", "Unknown Enemy"
            ),
            "unsupported combat_v0 content",
        ),
        (
            lambda observation: observation["enemies"][0]["intent"].__setitem__(
                "status_name", "private_status"
            ),
            "unsupported public status",
        ),
    ],
)
def test_projection_fails_closed_for_missing_or_unreviewed_public_content(
    mutation,
    match: str,
) -> None:
    source = _simple_observation()
    mutation(source)
    with pytest.raises(CombatProjectionError, match=match):
        project_combat_observation(source, _scope())


def test_projection_requires_public_scope_not_private_identity() -> None:
    with pytest.raises(CombatProjectionError, match="PublicScope"):
        project_combat_observation(
            _simple_observation(),
            {"run_id": "private", "rng_state": "private"},
        )
