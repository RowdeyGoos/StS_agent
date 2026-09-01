"""Structural-fixture coverage for deterministic, snapshot-safe map traversal."""

from copy import deepcopy
from dataclasses import replace

import pytest

from game.content.reduced_v0 import (
    CONTENT_FINGERPRINT,
    MapNodeTemplate,
    MapTemplate,
)
from game.contracts.headless_v0 import (
    ActionRequest,
    DecisionPhase,
    HeadlessBinding,
    MAX_PUBLIC_COUNTER,
    NodeKind,
    PublicEvent,
    PublicEventKind,
    RunOutcome,
    TransitionResult,
)
from game.engine.headless_state import PendingDecision, TerminalResult, WorldState
from game.engine.map_rules import (
    RULES_FINGERPRINT,
    MapRuleError,
    MapRules,
    _validate_closed_template,
)


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


def _request(decision, index: int = 0) -> ActionRequest:
    return ActionRequest(
        HeadlessBinding.for_candidate(decision, decision.candidates[index].candidate_id)
    )


def test_reset_exposes_exactly_reachable_candidates_and_preserves_rng() -> None:
    world = _world()
    decision = MapRules().reset(world)
    graph = decision.observation.data

    assert decision.phase is DecisionPhase.MAP
    assert len(graph["nodes"]) == 5
    assert {
        node["node_ref"] for node in graph["nodes"] if node["available"]
    } == {candidate.node_ref for candidate in decision.candidates}
    assert world.rng_stream_counters() == {
        "combat_launch": 0,
        "event_effect": 0,
        "reward_offer": 0,
    }


def test_full_bound_route_replays_every_transition_boundary() -> None:
    rules = MapRules("two_combat_rest")
    world = _world(22)
    decision = rules.reset(world)
    event_kinds = []

    while decision.candidates:
        transition = rules.choose_node(world, _request(decision))
        assert transition.result is TransitionResult.ACCEPTED
        assert rules.decision(world).to_json() == transition.next_decision.to_json()
        assert transition.public_events == transition.next_decision.public_events
        event_kinds.append(transition.public_events[0].data["node_kind"])
        decision = transition.next_decision

    assert decision.phase is DecisionPhase.TERMINAL
    assert event_kinds == ["combat", "event", "combat", "terminal"]


def test_raw_candidate_cross_run_and_tampered_bindings_are_atomic() -> None:
    rules = MapRules()
    first, second = _world(31), _world(32)
    first_decision, second_decision = rules.reset(first), rules.reset(second)
    before = deepcopy(first.to_private_dict())

    with pytest.raises(TypeError):
        rules.choose_node(first, first_decision.candidates[0])
    assert first.to_private_dict() == before

    cross_run = _request(second_decision)
    assert rules.choose_node(first, cross_run).result is TransitionResult.STALE
    assert first.to_private_dict() == before

    current = _request(first_decision).binding
    for binding in (
        HeadlessBinding("run." + "0" * 16 + ".00000000", current.decision_sequence, current.decision_hash, current.candidate_id),
        HeadlessBinding(current.run_id, current.decision_sequence + 1, current.decision_hash, current.candidate_id),
        HeadlessBinding(current.run_id, current.decision_sequence, "0" * 64, current.candidate_id),
    ):
        assert rules.choose_node(first, binding).result is TransitionResult.STALE
        assert first.to_private_dict() == before

    unadvertised = HeadlessBinding(
        current.run_id,
        current.decision_sequence,
        current.decision_hash,
        "cand." + "0" * 64,
    )
    assert rules.choose_node(first, unadvertised).result is TransitionResult.REJECTED
    assert first.to_private_dict() == before


def test_repeated_reset_makes_old_full_binding_stale() -> None:
    rules = MapRules()
    world = _world()
    first = rules.reset(world)
    old_request = _request(first)
    second = rules.reset(world)

    assert second.decision_sequence > first.decision_sequence
    assert rules.choose_node(world, old_request).result is TransitionResult.STALE


@pytest.mark.parametrize(
    "template",
    (
        MapTemplate(
            "cycle",
            (
                MapNodeTemplate("start", "combat", ("loop",)),
                MapNodeTemplate("loop", "rest", ("start",)),
                MapNodeTemplate("finish", "terminal", ()),
            ),
        ),
        MapTemplate(
            "self_cycle",
            (
                MapNodeTemplate("start", "combat", ("start",)),
                MapNodeTemplate("finish", "terminal", ()),
            ),
        ),
        MapTemplate(
            "nonterminal_leaf",
            (
                MapNodeTemplate("start", "combat", ("leaf",)),
                MapNodeTemplate("leaf", "rest", ()),
                MapNodeTemplate("finish", "terminal", ()),
            ),
        ),
    ),
)
def test_arbitrary_invalid_templates_reject_before_mutation(template: MapTemplate) -> None:
    world = _world()
    before = deepcopy(world.to_private_dict())

    with pytest.raises(MapRuleError):
        _validate_closed_template(template)
    with pytest.raises(MapRuleError, match="exact registered"):
        MapRules(template).reset(world)
    assert world.to_private_dict() == before


def test_availability_bijection_wrong_phase_and_nondefault_snapshot_restore() -> None:
    rules = MapRules("short_rest_path")
    world = _world(51)
    first = rules.reset(world)
    start = rules.choose_node(world, _request(first))
    graph = start.next_decision.observation.data

    assert {
        node["node_ref"] for node in graph["nodes"] if node["available"]
    } == {candidate.node_ref for candidate in start.next_decision.candidates}
    assert not next(
        node["available"] for node in graph["nodes"] if node["node_ref"] == first.candidates[0].node_ref
    )

    restored = WorldState.from_private_dict(world.to_private_dict())
    fresh = MapRules()
    assert fresh.decision(restored).to_json() == start.next_decision.to_json()
    assert fresh.choose_node(restored, _request(fresh.decision(restored))).result is TransitionResult.ACCEPTED

    wrong_phase = _world()
    with pytest.raises(MapRuleError, match="map phase"):
        MapRules().decision(wrong_phase)


def test_post_mutation_projection_failure_rolls_back_exact_private_state(monkeypatch) -> None:
    rules = MapRules()
    world = _world()
    decision = rules.reset(world)
    before = deepcopy(world.to_private_dict())
    original_decision = MapRules.decision
    calls = 0

    def fail_after_mutation(self, state):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("forced projection failure")
        return original_decision(self, state)

    monkeypatch.setattr(MapRules, "decision", fail_after_mutation)
    with pytest.raises(RuntimeError, match="forced projection"):
        rules.choose_node(world, _request(decision))
    assert world.to_private_dict() == before
    assert world.rng_stream_counters() == {
        "combat_launch": 0,
        "event_effect": 0,
        "reward_offer": 0,
    }


def test_stale_and_rejected_after_choice_replay_current_events_from_snapshot() -> None:
    rules = MapRules()
    world = _world(61)
    initial = rules.reset(world)
    old_request = _request(initial)
    accepted = rules.choose_node(world, old_request)
    restored = WorldState.from_private_dict(world.to_private_dict())
    before = deepcopy(restored.to_private_dict())
    fresh = MapRules()

    stale = fresh.choose_node(restored, old_request)
    assert stale.result is TransitionResult.STALE
    assert stale.public_events == stale.next_decision.public_events
    assert stale.public_events == accepted.public_events
    assert restored.to_private_dict() == before

    current = fresh.decision(restored)
    invalid = HeadlessBinding(
        current.run_id,
        current.decision_sequence,
        current.decision_hash,
        "cand." + "0" * 64,
    )
    rejected = fresh.choose_node(restored, invalid)
    assert rejected.result is TransitionResult.REJECTED
    assert rejected.public_events == rejected.next_decision.public_events
    assert rejected.public_events == current.public_events
    assert restored.to_private_dict() == before


@pytest.mark.parametrize("tamper", ("duplicate", "kind"))
def test_installed_nodes_require_exact_definition_and_kind_bijection(tamper: str) -> None:
    world = _world()
    rules = MapRules()
    rules.reset(world)
    nodes = list(world.map_nodes)
    if tamper == "duplicate":
        nodes[1] = replace(
            nodes[1],
            definition_id=nodes[0].definition_id,
            node_kind=nodes[0].node_kind,
        )
    else:
        replacement = NodeKind.REST if nodes[0].node_kind is not NodeKind.REST else NodeKind.EVENT
        nodes[0] = replace(nodes[0], node_kind=replacement)
    world.map_nodes = tuple(nodes)

    with pytest.raises(MapRuleError, match="map node"):
        rules.decision(world)


def test_session_rejects_pending_context_and_content_identity_forgery() -> None:
    rules = MapRules()

    wrong_kind = _world(71)
    rules.reset(wrong_kind)
    pending = wrong_kind.pending_decision
    assert pending is not None
    wrong_kind.pending_decision = PendingDecision(
        "reward_choice", pending.sequence, pending.private_context
    )
    with pytest.raises(MapRuleError, match="pending decision kind"):
        rules.decision(wrong_kind)

    missing_template = _world(72)
    rules.reset(missing_template)
    pending = missing_template.pending_decision
    assert pending is not None
    missing_template.pending_decision = PendingDecision(
        pending.decision_kind, pending.sequence, {"public_events": []}
    )
    with pytest.raises(MapRuleError, match="context fields"):
        rules.decision(missing_template)

    conflicting_template = _world(73)
    MapRules("short_rest_path").reset(conflicting_template)
    with pytest.raises(MapRuleError, match="conflicts"):
        MapRules("two_combat_rest").decision(conflicting_template)

    bad_content = _world(74)
    bad_content.content_fingerprint = "a" * 64
    with pytest.raises(MapRuleError, match="content fingerprint"):
        rules.reset(bad_content)

    bad_rules = _world(75)
    bad_rules.rules_fingerprint = "b" * 64
    with pytest.raises(MapRuleError, match="rules fingerprint"):
        rules.reset(bad_rules)


def test_session_rejects_impossible_history_current_and_terminal_state() -> None:
    rules = MapRules()

    impossible = _world(81)
    rules.reset(impossible)
    by_definition = {node.definition_id: node for node in impossible.map_nodes}
    start = by_definition["start"]
    skipped = by_definition["combat_2"]
    event = PublicEvent(
        0,
        PublicEventKind.MAP_NODE_CHOSEN,
        DecisionPhase.MAP,
        {"node_kind": skipped.node_kind.value},
    )
    pending = impossible.pending_decision
    assert pending is not None
    impossible.node_history = (start.instance_id, skipped.instance_id)
    impossible.current_node_id = skipped.instance_id
    impossible.pending_decision = PendingDecision(
        pending.decision_kind,
        pending.sequence,
        {"public_events": [event.to_dict()], "template_id": "two_combat_rest"},
    )
    with pytest.raises(MapRuleError, match="impossible edge"):
        rules.decision(impossible)

    duplicate = _world(82)
    first = rules.reset(duplicate)
    rules.choose_node(duplicate, _request(first))
    duplicate.node_history = (*duplicate.node_history, duplicate.node_history[-1])
    with pytest.raises(MapRuleError, match="more than once"):
        rules.decision(duplicate)

    incoherent = _world(83)
    first = rules.reset(incoherent)
    rules.choose_node(incoherent, _request(first))
    incoherent.current_node_id = None
    with pytest.raises(MapRuleError, match="history tail"):
        rules.decision(incoherent)

    forged_terminal = _world(84)
    rules.reset(forged_terminal)
    forged_terminal.phase = DecisionPhase.TERMINAL
    forged_terminal.terminal_result = TerminalResult(RunOutcome.VICTORY, "map_complete")
    with pytest.raises(MapRuleError, match="requires visiting"):
        rules.decision(forged_terminal)


@pytest.mark.parametrize("event_case", ("combat", "multiple", "wrong_kind"))
def test_session_rejects_forged_or_noncanonical_current_events(event_case: str) -> None:
    world = _world(90)
    rules = MapRules()
    first = rules.reset(world)
    rules.choose_node(world, _request(first))
    pending = world.pending_decision
    assert pending is not None
    current = next(node for node in world.map_nodes if node.instance_id == world.current_node_id)
    map_event = PublicEvent(
        0,
        PublicEventKind.MAP_NODE_CHOSEN,
        DecisionPhase.MAP,
        {"node_kind": current.node_kind.value},
    )
    if event_case == "combat":
        events = [
            PublicEvent(
                0, PublicEventKind.COMBAT_TURN_ENDED, DecisionPhase.COMBAT, {}
            ).to_dict()
        ]
    elif event_case == "multiple":
        events = [map_event.to_dict(), replace(map_event, sequence=1).to_dict()]
    else:
        wrong_kind = NodeKind.REST if current.node_kind is not NodeKind.REST else NodeKind.EVENT
        events = [
            PublicEvent(
                0,
                PublicEventKind.MAP_NODE_CHOSEN,
                DecisionPhase.MAP,
                {"node_kind": wrong_kind.value},
            ).to_dict()
        ]
    world.pending_decision = PendingDecision(
        pending.decision_kind,
        pending.sequence,
        {"public_events": events, "template_id": "two_combat_rest"},
    )

    with pytest.raises(MapRuleError, match="map event|exactly one"):
        rules.decision(world)


def test_sequence_capacity_rejects_before_advertising_and_exact_limit_completes() -> None:
    rules = MapRules()
    exhausted = _world(101)
    rules.reset(exhausted)
    pending = exhausted.pending_decision
    assert pending is not None
    exhausted.pending_decision = PendingDecision(
        pending.decision_kind,
        MAX_PUBLIC_COUNTER - 3,
        pending.private_context,
    )
    before = deepcopy(exhausted.to_private_dict())
    with pytest.raises(MapRuleError, match="cannot complete"):
        rules.decision(exhausted)
    assert exhausted.to_private_dict() == before

    exact = _world(102)
    decision = rules.reset(exact)
    pending = exact.pending_decision
    assert pending is not None
    exact.pending_decision = PendingDecision(
        pending.decision_kind,
        MAX_PUBLIC_COUNTER - 4,
        pending.private_context,
    )
    decision = rules.decision(exact)
    while decision.candidates:
        transition = rules.choose_node(exact, _request(decision))
        assert transition.result is TransitionResult.ACCEPTED
        decision = transition.next_decision
    assert decision.phase is DecisionPhase.TERMINAL
    assert decision.decision_sequence == MAX_PUBLIC_COUNTER
