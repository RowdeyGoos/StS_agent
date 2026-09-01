"""Composition and recovery tests for the combat-only headless backend."""

from __future__ import annotations

from copy import deepcopy

import pytest

from game.backends.headless.combat_v0_backend import (
    BACKEND_FINGERPRINT,
    BACKEND_ID,
    BACKEND_VERSION,
    CombatV0Backend,
    CombatV0BackendError,
)
from game.backends.headless.scenarios import scenario_from_id
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import (
    ActionRequest,
    CombatEndTurnCandidate,
    CombatOutcome,
    CombatPlayCardCandidate,
    DecisionPhase,
    DecisionStatus,
    HeadlessBinding,
    NodeKind,
    PublicEventKind,
    TransitionReason,
    TransitionResult,
)
from game.engine.headless_state import (
    CombatLaunchSpec,
    CombatResolution,
    PersistentCardInstance,
    WorldState,
)


def _deck() -> tuple[PersistentCardInstance, ...]:
    definitions = ("strike", "strike", "defend", "defend", "bash")
    return tuple(
        PersistentCardInstance(f"card.test.{index:08d}", definition_id)
        for index, definition_id in enumerate(definitions)
    )


def _launch(
    *,
    current_hp: int = 80,
    max_hp: int = 80,
    seed: int = 3,
    scenario_id: str = "simple__starter",
    settings=None,
) -> CombatLaunchSpec:
    return CombatLaunchSpec(
        run_id="run.test.combat",
        scenario_id=scenario_id,
        combat_seed=seed,
        current_hp=current_hp,
        max_hp=max_hp,
        combat_settings={} if settings is None else settings,
        ordered_deck=_deck(),
    )


def _request(decision, candidate) -> ActionRequest:
    return ActionRequest(HeadlessBinding.for_candidate(decision, candidate.candidate_id))


def _end_turn(decision):
    return next(
        candidate
        for candidate in decision.candidates
        if isinstance(candidate, CombatEndTurnCandidate)
    )


def _attack(decision):
    card_definitions = {
        card["card_ref"]: card["card_definition_id"]
        for card in decision.observation.data["hand"]
    }
    return next(
        candidate
        for candidate in decision.candidates
        if isinstance(candidate, CombatPlayCardCandidate)
        and card_definitions[candidate.card_ref] in {"strike", "bash"}
    )


def test_standalone_seeded_victory_returns_valid_resolution_and_preserves_deck() -> None:
    backend = CombatV0Backend()
    scenario = scenario_from_id("simple__starter", seed=3, enemy_max_hp=6)
    decision = backend.reset(scenario)
    assert CombatV0Backend().reset(scenario) == decision
    launch = backend.launch_spec
    assert launch is not None
    expected_deck = launch.ordered_deck

    transition = backend.apply(_request(decision, _attack(decision)))

    assert transition.result is TransitionResult.ACCEPTED
    assert transition.next_decision.status is DecisionStatus.TERMINAL
    assert transition.next_decision.phase is DecisionPhase.TERMINAL
    assert [event.event_type for event in transition.public_events] == [
        PublicEventKind.COMBAT_CARD_PLAYED,
        PublicEventKind.COMBAT_RESOLVED,
    ]
    assert backend.resolution is not None
    assert backend.get_resolution() == backend.resolution
    assert backend.resolution.outcome is CombatOutcome.VICTORY
    assert backend.resolution.final_hp == 80
    assert backend.resolution.launch_key == launch.semantic_key()
    assert CombatResolution.from_json(backend.resolution.to_json()) == backend.resolution
    assert backend.launch_spec.ordered_deck == expected_deck
    restored = CombatV0Backend()
    assert restored.restore(backend.snapshot()) == transition.next_decision
    assert restored.resolution == backend.resolution


def test_composer_launch_initializes_current_hp_and_seeded_defeat_preserves_deck() -> None:
    launch = _launch(
        current_hp=1,
        max_hp=80,
        settings={"cards_per_turn": 2, "energy_per_turn": 2},
    )
    backend = CombatV0Backend()
    decision = backend.reset(launch)

    assert decision.observation.data["player"]["hp"] == 1
    assert decision.observation.data["player"]["energy_per_turn"] == 2
    assert len(decision.observation.data["hand"]) == 2
    transition = backend.apply(_request(decision, _end_turn(decision)))

    assert transition.next_decision.status is DecisionStatus.TERMINAL
    assert backend.resolution is not None
    assert backend.resolution.outcome is CombatOutcome.DEFEAT
    assert backend.resolution.final_hp == 0
    assert backend.launch_spec is launch
    assert backend.launch_spec.ordered_deck == launch.ordered_deck


def test_combat_piles_and_generated_cards_never_change_persistent_launch_deck() -> None:
    launch = _launch(scenario_id="slimes__starter", seed=17)
    backend = CombatV0Backend()
    decision = backend.reset(launch)
    original = launch.to_dict()

    transition = backend.apply(_request(decision, _end_turn(decision)))
    observation = transition.next_decision.observation.data
    combat_card_count = (
        len(observation["hand"])
        + observation["draw_pile_size"]
        + observation["discard_pile_size"]
        + observation["exhaust_pile_size"]
    )

    # Sticky Shot adds a combat-only Slimed on this frozen encounter seed.
    assert combat_card_count > len(launch.ordered_deck)
    assert backend.launch_spec.to_dict() == original
    assert all(card.definition_id != "slimed" for card in backend.launch_spec.ordered_deck)


def test_every_advertised_candidate_is_sound_from_the_same_snapshot() -> None:
    backend = CombatV0Backend()
    decision = backend.reset(_launch(seed=19))
    snapshot = backend.snapshot()

    for candidate in decision.candidates:
        fork = CombatV0Backend()
        restored = fork.restore(snapshot)
        transition = fork.apply(_request(restored, candidate))
        assert transition.result is TransitionResult.ACCEPTED
        assert transition.reason is TransitionReason.ACCEPTED


def test_stale_and_tampered_requests_reject_without_mutation() -> None:
    backend = CombatV0Backend()
    initial = backend.reset(_launch(seed=11))
    snapshot = backend.snapshot()
    valid = _request(initial, _end_turn(initial))
    tampered = ActionRequest(
        HeadlessBinding(
            run_id=initial.run_id,
            decision_sequence=initial.decision_sequence,
            decision_hash=initial.decision_hash,
            candidate_id="cand." + "0" * 64,
        )
    )

    rejected = backend.apply(tampered)
    assert rejected.result is TransitionResult.REJECTED
    assert rejected.reason is TransitionReason.INVALID_CANDIDATE
    assert backend.snapshot() == snapshot

    accepted = backend.apply(valid)
    assert accepted.result is TransitionResult.ACCEPTED
    after = backend.snapshot()
    stale = backend.apply(valid)
    assert stale.result is TransitionResult.STALE
    assert stale.reason is TransitionReason.STALE_BINDING
    assert backend.snapshot() == after


def test_snapshot_restore_replays_multiple_decisions_and_exact_continuation() -> None:
    backend = CombatV0Backend()
    decision0 = backend.reset(_launch(seed=23))
    snapshot0 = backend.snapshot()
    transition1 = backend.apply(_request(decision0, _end_turn(decision0)))
    decision1 = transition1.next_decision
    snapshot1 = backend.snapshot()
    transition2 = backend.apply(_request(decision1, _end_turn(decision1)))
    snapshot2 = backend.snapshot()

    restored0 = CombatV0Backend()
    assert restored0.restore(snapshot0) == decision0
    restored1 = CombatV0Backend()
    assert restored1.restore(snapshot1) == decision1
    restored2 = CombatV0Backend()
    assert restored2.restore(snapshot2) == transition2.next_decision

    fork_a = CombatV0Backend()
    fork_b = CombatV0Backend()
    fork_decision_a = fork_a.restore(snapshot1)
    fork_decision_b = fork_b.restore(snapshot1)
    candidate_a = _end_turn(fork_decision_a)
    candidate_b = next(
        candidate
        for candidate in fork_decision_b.candidates
        if candidate.candidate_id == candidate_a.candidate_id
    )
    assert fork_a.apply(_request(fork_decision_a, candidate_a)) == fork_b.apply(
        _request(fork_decision_b, candidate_b)
    )


def test_snapshot_tampering_is_fail_closed_and_restore_is_atomic() -> None:
    backend = CombatV0Backend()
    original = backend.reset(_launch(seed=29))
    snapshot = backend.snapshot()
    tampered = deepcopy(snapshot)
    tampered["accepted_candidate_ids"].append("cand." + "0" * 64)

    with pytest.raises(CombatV0BackendError, match="hash"):
        backend.restore(tampered)
    assert backend.observe() == original
    assert backend.snapshot() == snapshot


def test_backend_never_depends_on_or_advances_world_rng() -> None:
    world = WorldState.create(
        seed=101,
        current_hp=80,
        max_hp=80,
        gold=7,
        deck_definition_ids=("strike", "strike", "defend", "defend", "bash"),
        map_node_definitions=(("start", NodeKind.COMBAT),),
        content_fingerprint=CONTENT_FINGERPRINT,
        rules_fingerprint="a" * 64,
    )
    launch = world.create_combat_launch("simple__starter")
    before = world.rng.snapshot()
    backend = CombatV0Backend()
    decision = backend.reset(launch)
    backend.apply(_request(decision, _end_turn(decision)))

    assert world.rng.snapshot() == before
    assert world.rng_stream_counters() == {
        "combat_launch": 1,
        "event_effect": 0,
        "reward_offer": 0,
    }


def test_manifest_is_honest_combat_only_and_close_releases_episode() -> None:
    backend = CombatV0Backend()
    manifest = backend.manifest()

    assert manifest.backend_id == BACKEND_ID
    assert manifest.backend_version == BACKEND_VERSION
    assert manifest.backend_fingerprint == BACKEND_FINGERPRINT
    assert manifest.supported_phases == (DecisionPhase.COMBAT,)
    assert manifest.unsupported_phases == (
        DecisionPhase.MAP,
        DecisionPhase.REWARD,
        DecisionPhase.ROOM,
    )
    assert manifest.capabilities.deterministic_reset is True
    assert manifest.capabilities.counterfactual_stepping is True
    assert manifest.capabilities.snapshot_restore is True
    assert manifest.capabilities.live_truth is False
    assert {item.label.value for item in manifest.evidence} == {
        "combat_v0",
        "structural_fixture",
    }

    backend.reset(_launch())
    backend.close()
    with pytest.raises(RuntimeError, match="not initialized"):
        backend.observe()


def test_unsupported_settings_upgrades_and_persistent_slimed_fail_closed() -> None:
    with pytest.raises(CombatV0BackendError, match="Unsupported combat settings"):
        CombatV0Backend().reset(_launch(settings={"world_rng": 1}))

    upgraded = list(_deck())
    upgraded[0] = PersistentCardInstance(
        upgraded[0].instance_id, upgraded[0].definition_id, upgraded=True
    )
    with pytest.raises(CombatV0BackendError, match="upgraded"):
        CombatV0Backend().reset(
            CombatLaunchSpec(
                run_id="run.test.combat",
                scenario_id="simple__starter",
                combat_seed=3,
                current_hp=80,
                max_hp=80,
                combat_settings={},
                ordered_deck=tuple(upgraded),
            )
        )

    slimed = list(_deck())
    slimed[0] = PersistentCardInstance(slimed[0].instance_id, "slimed")
    with pytest.raises(CombatV0BackendError, match="persistent card"):
        CombatV0Backend().reset(
            CombatLaunchSpec(
                run_id="run.test.combat",
                scenario_id="simple__starter",
                combat_seed=3,
                current_hp=80,
                max_hp=80,
                combat_settings={},
                ordered_deck=tuple(slimed),
            )
        )
