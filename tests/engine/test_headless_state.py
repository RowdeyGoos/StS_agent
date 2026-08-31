"""Structural-fixture coverage for reduced private run state and combat seam."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from game.contracts.headless_v0 import CombatOutcome, DecisionPhase, NodeKind
from game.engine.headless_state import (
    COMBAT_HANDOFF_VERSION,
    COMBAT_LAUNCH_STREAM,
    EVENT_EFFECT_STREAM,
    REWARD_OFFER_STREAM,
    RNG_STREAM_MAP_VERSION,
    WORLD_RNG_STREAMS,
    WORLD_SEMANTIC_KEY_VERSION,
    WORLD_STATE_FINGERPRINT,
    WORLD_STATE_SCHEMA,
    WORLD_STATE_VERSION,
    AutomaticTransition,
    CombatLaunchSpec,
    CombatResolution,
    PendingDecision,
    StateValidationError,
    WorldState,
)


CONTENT_FINGERPRINT = "a" * 64
RULES_FINGERPRINT = "b" * 64


def _world(seed: int = 71) -> WorldState:
    return WorldState.create(
        seed=seed,
        current_hp=68,
        max_hp=80,
        gold=99,
        deck_definition_ids=("strike", "defend", "strike", "bash"),
        map_node_definitions=(
            ("floor_01_combat", NodeKind.COMBAT),
            ("floor_02_rest", NodeKind.REST),
            ("floor_03_event", NodeKind.EVENT),
        ),
        content_fingerprint=CONTENT_FINGERPRINT,
        rules_fingerprint=RULES_FINGERPRINT,
    )


def test_state_schema_stream_map_and_semantic_key_are_explicit() -> None:
    world = _world()

    assert world.schema == WORLD_STATE_SCHEMA == "reduced_world_state_v0"
    assert world.state_version == WORLD_STATE_VERSION == 1
    assert WORLD_SEMANTIC_KEY_VERSION == "reduced_world_state_v0.semantic_key.v1"
    assert COMBAT_HANDOFF_VERSION == "reduced_world_state_v0.combat_handoff.v1"
    assert RNG_STREAM_MAP_VERSION == "reduced_world_state_v0.rng_stream_map.v1"
    assert dict(WORLD_RNG_STREAMS) == {
        "combat_launch": COMBAT_LAUNCH_STREAM,
        "event_effect": EVENT_EFFECT_STREAM,
        "reward_offer": REWARD_OFFER_STREAM,
    }
    assert len(WORLD_STATE_FINGERPRINT) == 64
    assert len(world.semantic_key()) == 64
    assert world.rng_stream_counters() == {
        "combat_launch": 0,
        "event_effect": 0,
        "reward_offer": 0,
    }


def test_same_seed_and_inputs_allocate_identical_stable_run_card_and_map_ids() -> None:
    first = _world(seed=404)
    second = _world(seed=404)

    assert first.run_id == second.run_id
    assert first.master_deck == second.master_deck
    assert first.map_nodes == second.map_nodes
    assert first.identity_allocator.to_dict() == second.identity_allocator.to_dict()
    assert len({card.instance_id for card in first.master_deck}) == 4
    assert len({node.instance_id for node in first.map_nodes}) == 3
    assert [card.definition_id for card in first.master_deck] == [
        "strike",
        "defend",
        "strike",
        "bash",
    ]

    added_first = first.add_card("pommel_strike", upgraded=True)
    added_second = second.add_card("pommel_strike", upgraded=True)
    assert added_first == added_second
    assert added_first.instance_id.endswith("00000004")
    new_node_first = first.add_map_node("floor_04_combat", NodeKind.COMBAT)
    new_node_second = second.add_map_node("floor_04_combat", NodeKind.COMBAT)
    assert new_node_first == new_node_second
    assert new_node_first.instance_id.endswith("00000003")


def test_allocator_rejects_wrong_namespace_kind_and_unallocated_ids() -> None:
    world = _world(seed=19)
    other = _world(seed=20)

    with pytest.raises(StateValidationError, match="not allocated"):
        world.identity_allocator.validate_card_id(other.master_deck[0].instance_id)
    with pytest.raises(StateValidationError, match="not allocated"):
        world.identity_allocator.validate_card_id(world.map_nodes[0].instance_id)
    future = world.master_deck[0].instance_id[:-8] + "99999999"
    with pytest.raises(StateValidationError, match="not been allocated"):
        world.identity_allocator.validate_card_id(future)
    with pytest.raises(StateValidationError, match="already owns"):
        world.identity_allocator.allocate_run_id()


def test_world_tracks_private_pending_queue_node_history_and_terminal_result() -> None:
    world = _world()
    world.current_node_id = world.map_nodes[0].instance_id
    world.node_history = (world.map_nodes[0].instance_id,)
    world.pending_decision = PendingDecision(
        "reward_choice",
        8,
        {"hidden_offer_ids": ["offer.alpha", "offer.beta"]},
    )
    world.automatic_queue = (
        AutomaticTransition("advance_phase", {"destination": "reward"}),
    )

    world.validate()
    payload = world.to_private_dict()

    assert payload["pending_decision"]["private_context"] == {
        "hidden_offer_ids": ["offer.alpha", "offer.beta"]
    }
    assert payload["automatic_queue"] == [
        {
            "private_payload": {"destination": "reward"},
            "transition_kind": "advance_phase",
        }
    ]
    assert payload["node_history"] == [world.map_nodes[0].instance_id]


def test_combat_launch_advances_only_combat_stream_and_round_trips() -> None:
    world = _world(seed=902)
    world.rng.choice(REWARD_OFFER_STREAM, ("strike", "defend"))
    before = world.rng_stream_counters()

    launch = world.create_combat_launch(
        "jaw_worm_v0",
        combat_settings={"cards_per_turn": 5, "record_history": True},
    )

    assert CombatLaunchSpec.from_json(launch.to_json()) == launch
    assert launch.current_hp == world.current_hp
    assert launch.max_hp == world.max_hp
    assert launch.ordered_deck == world.master_deck
    assert 0 <= launch.combat_seed <= (1 << 63) - 1
    world.validate_combat_launch(launch)
    assert world.rng_stream_counters() == {
        "combat_launch": before["combat_launch"] + 1,
        "event_effect": before["event_effect"],
        "reward_offer": before["reward_offer"],
    }


def test_invalid_combat_launch_request_does_not_advance_rng() -> None:
    world = _world()
    before = world.rng.snapshot()

    with pytest.raises(StateValidationError, match="scenario_id"):
        world.create_combat_launch("Not A Semantic ID")
    with pytest.raises(StateValidationError, match="JSON-safe"):
        world.create_combat_launch("jaw_worm_v0", combat_settings={"scale": 1.5})

    assert world.rng.snapshot() == before


@pytest.mark.parametrize(
    "mutate,match",
    [
        (lambda launch: replace(launch, current_hp=launch.current_hp - 1), "HP"),
        (
            lambda launch: replace(launch, ordered_deck=tuple(reversed(launch.ordered_deck))),
            "deck",
        ),
        (lambda launch: replace(launch, run_id="run.wrong.00000000"), "another run"),
    ],
)
def test_combat_launch_rejects_persistent_state_mismatch(mutate, match: str) -> None:
    world = _world()
    launch = world.create_combat_launch("jaw_worm_v0")

    with pytest.raises(StateValidationError, match=match):
        world.validate_combat_launch(mutate(launch))


@pytest.mark.parametrize("bad_seed", [-1, 1 << 63, True])
def test_combat_launch_rejects_invalid_seed(bad_seed: int) -> None:
    world = _world()
    launch = world.create_combat_launch("jaw_worm_v0")

    with pytest.raises(StateValidationError, match="combat_seed"):
        replace(launch, combat_seed=bad_seed)


def test_combat_resolution_round_trip_applies_hp_as_only_persistent_delta() -> None:
    world = _world()
    launch = world.create_combat_launch("jaw_worm_v0")
    before = deepcopy(world.to_private_dict())
    resolution = CombatResolution(
        run_id=world.run_id,
        launch_key=launch.semantic_key(),
        outcome=CombatOutcome.VICTORY,
        final_hp=53,
        replay_reference="replay.combat.0001",
    )

    assert CombatResolution.from_json(resolution.to_json()) == resolution
    world.apply_combat_resolution(launch, resolution)
    after = world.to_private_dict()

    assert world.current_hp == 53
    assert before["current_hp"] == 68
    before["current_hp"] = 53
    assert after == before


def test_combat_resolution_rejects_wrong_launch_run_or_hp_atomically() -> None:
    world = _world()
    launch = world.create_combat_launch("jaw_worm_v0")
    valid = CombatResolution(
        run_id=world.run_id,
        launch_key=launch.semantic_key(),
        outcome=CombatOutcome.VICTORY,
        final_hp=60,
        replay_reference="replay.combat.0001",
    )
    before = world.to_private_dict()

    for invalid in (
        replace(valid, launch_key="0" * 64),
        replace(valid, run_id="run.wrong.00000000"),
        replace(valid, final_hp=world.max_hp + 1),
    ):
        with pytest.raises(StateValidationError):
            world.apply_combat_resolution(launch, invalid)
        assert world.to_private_dict() == before


def test_resolution_outcome_and_hp_must_be_consistent() -> None:
    world = _world()
    launch = world.create_combat_launch("jaw_worm_v0")

    with pytest.raises(StateValidationError, match="defeat"):
        CombatResolution(
            world.run_id,
            launch.semantic_key(),
            CombatOutcome.DEFEAT,
            1,
            "replay.combat.0001",
        )
    with pytest.raises(StateValidationError, match="victory"):
        CombatResolution(
            world.run_id,
            launch.semantic_key(),
            CombatOutcome.VICTORY,
            0,
            "replay.combat.0001",
        )
    with pytest.raises(StateValidationError, match="ongoing"):
        CombatResolution(
            world.run_id,
            launch.semantic_key(),
            CombatOutcome.ONGOING,
            1,
            "replay.combat.0001",
        )


def test_world_rejects_unknown_node_and_contract_fingerprint() -> None:
    world = _world()
    world.current_node_id = "map.0000000000000000.00000000"
    with pytest.raises(StateValidationError, match="known map node"):
        world.validate()

    payload = _world().to_private_dict()
    payload["contract_fingerprint"] = "0" * 64
    with pytest.raises(StateValidationError, match="contract fingerprint"):
        WorldState.from_private_dict(payload)
