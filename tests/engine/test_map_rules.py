"""Structural-fixture tests for the deterministic reduced map DAG."""

from copy import deepcopy

import pytest

from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import DecisionPhase, TransitionResult
from game.engine.headless_state import WorldState
from game.engine.map_rules import MapRules, RULES_FINGERPRINT


def _world(seed: int = 7) -> WorldState:
    return WorldState.create(
        seed=seed,
        current_hp=70,
        max_hp=80,
        gold=10,
        deck_definition_ids=("strike", "defend"),
        map_node_definitions=(),
        content_fingerprint=CONTENT_FINGERPRINT,
        rules_fingerprint=RULES_FINGERPRINT,
    )


def test_reset_exposes_only_reachable_graph_and_deterministic_candidates() -> None:
    world = _world()
    decision = MapRules().reset(world)

    assert decision.phase is DecisionPhase.MAP
    assert {node["kind"] for node in decision.observation.data["nodes"]} == {
        "combat", "rest", "event", "terminal"
    }
    assert len(decision.observation.data["nodes"]) == 5
    assert len(decision.candidates) == 1
    assert decision.observation.data["nodes"] == sorted(
        decision.observation.data["nodes"], key=lambda node: node["node_ref"]
    )
    assert world.rng_stream_counters() == {
        "combat_launch": 0,
        "event_effect": 0,
        "reward_offer": 0,
    }


def test_route_is_deterministic_and_choice_emits_map_event() -> None:
    first, second = _world(22), _world(22)
    rules = MapRules("two_combat_rest")
    left, right = rules.reset(first), rules.reset(second)
    assert left.to_json() == right.to_json()

    transition = rules.choose_node(first, left.candidates[0])
    assert transition.result is TransitionResult.ACCEPTED
    assert transition.public_events[0].data == {"node_kind": "combat"}
    assert first.node_history == (first.current_node_id,)
    assert tuple(c.node_ref for c in transition.next_decision.candidates) == tuple(
        c.node_ref for c in rules.decision(first).candidates
    )


def test_invalid_and_stale_choices_are_mutation_atomic() -> None:
    rules = MapRules()
    world = _world()
    decision = rules.reset(world)
    before = deepcopy(world.to_private_dict())

    with pytest.raises(ValueError):
        rules.choose_node(world, "cand." + "0" * 64)
    assert world.to_private_dict() == before

    rules.choose_node(world, decision.candidates[0])
    after = deepcopy(world.to_private_dict())
    stale = rules.choose_node(world, decision.candidates[0])
    assert stale.result is TransitionResult.STALE
    assert world.to_private_dict() == after


def test_snapshot_round_trip_replays_same_next_map_choice() -> None:
    rules = MapRules()
    world = _world(44)
    decision = rules.reset(world)
    rules.choose_node(world, decision.candidates[0])
    payload = world.to_private_dict()
    restored = WorldState.from_private_dict(payload)
    current = rules.decision(world)
    replay = rules.decision(restored)
    assert replay.to_json() == current.to_json()
    assert rules.choose_node(restored, replay.candidates[0]).next_decision.to_json() == rules.choose_node(world, current.candidates[0]).next_decision.to_json()
