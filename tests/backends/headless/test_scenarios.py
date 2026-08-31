"""Tests for the closed combat-v0 scenario adapter."""

import json

import pytest

from game.backends.headless.scenarios import (
    SCENARIO_EVIDENCE,
    SCENARIO_SCHEMA,
    SUPPORTED_SCENARIOS,
    CombatScenario,
    scenario_from_id,
)


def test_named_scenarios_round_trip_and_build() -> None:
    assert SUPPORTED_SCENARIOS
    for scenario_id in SUPPORTED_SCENARIOS:
        scenario = scenario_from_id(scenario_id, seed=17)
        encoded = scenario.to_dict()
        assert json.loads(json.dumps(encoded)) == encoded
        assert CombatScenario.from_dict(encoded) == scenario
        assert scenario.build().get_observation() == scenario.build().get_observation()


def test_descriptor_seed_and_settings_are_deterministic() -> None:
    scenario = scenario_from_id(
        "simple__ironclad_sequencing",
        seed=123,
        player_max_hp=77,
        enemy_max_hp=31,
        cards_per_turn=4,
        hp_loss_penalty_scale=0.25,
        incoming_damage_shaping_scale=0.75,
        record_trajectory=True,
    )
    first = scenario.build()
    second = scenario.build()
    assert first.get_observation() == second.get_observation()
    assert first.get_legal_actions() == second.get_legal_actions()


@pytest.mark.parametrize(
    "payload",
    [
        {"scenario_id": "missing__starter", "encounter": "simple", "deck": "starter"},
        {"scenario_id": "simple__starter", "encounter": "simple", "deck": "starter", "extra": 1},
    ],
)
def test_bad_descriptor_shape_rejected(payload) -> None:
    with pytest.raises(ValueError):
        CombatScenario.from_dict(payload)


@pytest.mark.parametrize("missing_field", ["schema", "evidence"])
def test_missing_wire_metadata_rejected(missing_field) -> None:
    payload = scenario_from_id("simple__starter").to_dict()
    del payload[missing_field]
    with pytest.raises(ValueError, match="Missing scenario fields"):
        CombatScenario.from_dict(payload)


@pytest.mark.parametrize(
    "scenario_id, overrides",
    [
        ("unknown__starter", {}),
        ("simple__starter", {"player_max_hp": 0}),
        ("simple__starter", {"cards_per_turn": True}),
        ("simple__starter", {"record_trajectory": 1}),
        ("simple__starter", {"enemy_max_hp": -1}),
        ("nibbit__starter", {"enemy_max_hp": 41}),
        ("simple__starter", {"seed": None}),
    ],
)
def test_invalid_ids_and_settings_rejected(scenario_id, overrides) -> None:
    with pytest.raises(ValueError):
        scenario_from_id(scenario_id, **overrides)


def test_wire_metadata_is_fixed() -> None:
    scenario = scenario_from_id("simple__starter")
    assert scenario.to_dict()["schema"] == SCENARIO_SCHEMA
    assert scenario.to_dict()["evidence"] == SCENARIO_EVIDENCE
