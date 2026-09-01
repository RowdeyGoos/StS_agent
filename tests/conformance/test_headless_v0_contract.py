"""Independent black-box contract and candidate conformance for headless_v0."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Callable

import pytest

from game.backends.headless.combat_v0_backend import CombatV0Backend
from game.backends.headless.fixture_backend import FixtureBackend
from game.backends.headless.reduced_run_backend import HeadlessRunConfig, ReducedRunBackend
from game.backends.headless.scenarios import scenario_from_id
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import (
    ActionRequest,
    BackendManifest,
    CandidateKind,
    ContractValidationError,
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    DuplicateFieldError,
    HeadlessBinding,
    Transition,
    TransitionReason,
    TransitionResult,
)


_TARGETED_CARDS = frozenset(
    {"bash", "body_slam", "iron_wave", "pommel_strike", "strike"}
)


def _reduced_config(**settings: Any) -> HeadlessRunConfig:
    return HeadlessRunConfig(
        scenario_id="simple__starter",
        content_fingerprint=CONTENT_FINGERPRINT,
        game_seed=7,
        backend_settings=settings,
    )


def _request(decision: DecisionState, candidate_id: str) -> ActionRequest:
    return ActionRequest(HeadlessBinding.for_candidate(decision, candidate_id))


def _invalid_request(decision: DecisionState) -> ActionRequest:
    return ActionRequest(
        HeadlessBinding(
            run_id=decision.run_id,
            decision_sequence=decision.decision_sequence,
            decision_hash=decision.decision_hash,
            candidate_id="cand." + "0" * 64,
        )
    )


def _snapshot_json(backend: object) -> str:
    snapshot = backend.snapshot()  # type: ignore[attr-defined]
    if hasattr(snapshot, "__dataclass_fields__"):
        return repr(snapshot)
    return json.dumps(snapshot, sort_keys=True, separators=(",", ":"))


@pytest.mark.parametrize(
    ("factory", "configuration"),
    (
        (FixtureBackend, "combat"),
        (CombatV0Backend, scenario_from_id("simple__starter", seed=11)),
        (ReducedRunBackend, _reduced_config()),
    ),
    ids=("fixture", "combat_v0", "reduced"),
)
def test_stale_and_unadvertised_requests_are_atomic_across_backends(
    factory: Callable[[], object], configuration: object
) -> None:
    backend = factory()
    decision = backend.reset(configuration)  # type: ignore[attr-defined]
    before = _snapshot_json(backend)

    rejected = backend.apply(_invalid_request(decision))  # type: ignore[attr-defined]
    assert rejected.result is TransitionResult.REJECTED
    assert rejected.reason is TransitionReason.INVALID_CANDIDATE
    assert rejected.next_decision == decision
    assert _snapshot_json(backend) == before

    request = _request(decision, decision.candidates[0].candidate_id)
    accepted = backend.apply(request)  # type: ignore[attr-defined]
    assert accepted.result is TransitionResult.ACCEPTED
    after = _snapshot_json(backend)

    stale = backend.apply(request)  # type: ignore[attr-defined]
    assert stale.result is TransitionResult.STALE
    assert stale.reason is TransitionReason.STALE_BINDING
    assert stale.next_decision == accepted.next_decision
    assert _snapshot_json(backend) == after


@pytest.mark.parametrize(
    ("factory", "configuration"),
    (
        (FixtureBackend, "combat"),
        (CombatV0Backend, scenario_from_id("simple__starter", seed=13)),
        (ReducedRunBackend, _reduced_config()),
    ),
    ids=("fixture", "combat_v0", "reduced"),
)
@pytest.mark.parametrize("tampered_field", ("run_id", "decision_sequence", "decision_hash"))
def test_each_current_binding_identity_field_tamper_is_stale_and_atomic(
    factory: Callable[[], object], configuration: object, tampered_field: str
) -> None:
    backend = factory()
    decision = backend.reset(configuration)  # type: ignore[attr-defined]
    before = _snapshot_json(backend)
    values: dict[str, object] = {
        "run_id": decision.run_id,
        "decision_sequence": decision.decision_sequence,
        "decision_hash": decision.decision_hash,
        "candidate_id": decision.candidates[0].candidate_id,
    }
    if tampered_field == "run_id":
        values[tampered_field] = decision.run_id + ".tampered"
    elif tampered_field == "decision_sequence":
        values[tampered_field] = decision.decision_sequence + 1
    else:
        values[tampered_field] = "0" * 64
    request = ActionRequest(HeadlessBinding(**values))  # type: ignore[arg-type]

    transition = backend.apply(request)  # type: ignore[attr-defined]

    assert transition.result is TransitionResult.STALE
    assert transition.reason is TransitionReason.STALE_BINDING
    assert transition.binding == request.binding
    assert transition.next_decision == decision
    assert backend.observe() == decision  # type: ignore[attr-defined]
    assert _snapshot_json(backend) == before


def _strict_samples() -> tuple[tuple[type[Any], str], ...]:
    backend = FixtureBackend()
    decision = backend.reset("combat")
    request = _request(decision, decision.candidates[0].candidate_id)
    transition = backend.apply(request)
    return (
        (BackendManifest, backend.manifest().to_json()),
        (DecisionState, decision.to_json()),
        (ActionRequest, request.to_json()),
        (Transition, transition.to_json()),
    )


@pytest.mark.parametrize("codec,payload", _strict_samples())
def test_contract_codecs_reject_unknown_missing_and_duplicate_fields(
    codec: type[Any], payload: str
) -> None:
    value = json.loads(payload)
    value["unexpected"] = None
    with pytest.raises(ContractValidationError, match="unknown field"):
        codec.from_json(json.dumps(value))

    value = json.loads(payload)
    del value[next(iter(value))]
    with pytest.raises(ContractValidationError, match="missing field"):
        codec.from_json(json.dumps(value))

    first_key = next(iter(json.loads(payload)))
    duplicate = payload.replace(
        "{" + json.dumps(first_key) + ":",
        "{" + json.dumps(first_key) + ":null," + json.dumps(first_key) + ":",
        1,
    )
    with pytest.raises(DuplicateFieldError):
        codec.from_json(duplicate)


def test_nested_policy_fields_and_candidate_semantics_are_strict() -> None:
    decision = CombatV0Backend().reset(
        scenario_from_id("simple__starter", seed=3, enemy_max_hp=20)
    )

    observation_tamper = decision.to_dict()
    observation_tamper["observation"]["data"]["world_rng"] = 1
    with pytest.raises(ContractValidationError):
        DecisionState.from_dict(observation_tamper)

    candidate_tamper = decision.to_dict()
    candidate_tamper["candidates"][0]["slot"] = 0
    with pytest.raises(ContractValidationError):
        DecisionState.from_dict(candidate_tamper)

    hash_tamper = decision.to_dict()
    hash_tamper["decision_hash"] = "0" * 64
    with pytest.raises(ContractValidationError, match="Decision hash"):
        DecisionState.from_dict(hash_tamper)


def _assert_combat_candidates_complete(decision: DecisionState) -> None:
    assert decision.phase is DecisionPhase.COMBAT
    observation = decision.observation.data
    energy = observation["player"]["energy"]
    alive_enemies = {
        enemy["enemy_ref"] for enemy in observation["enemies"] if enemy["alive"]
    }
    expected: set[tuple[str, str | None, str | None]] = {
        (CandidateKind.COMBAT_END_TURN.value, None, None)
    }
    for card in observation["hand"]:
        if card["cost"] > energy:
            continue
        if card["card_definition_id"] in _TARGETED_CARDS:
            expected.update(
                (
                    CandidateKind.COMBAT_PLAY_CARD.value,
                    card["card_ref"],
                    enemy_ref,
                )
                for enemy_ref in alive_enemies
            )
        else:
            expected.add(
                (CandidateKind.COMBAT_PLAY_CARD.value, card["card_ref"], None)
            )
    actual = {
        (
            candidate.kind.value,
            getattr(candidate, "card_ref", None),
            getattr(candidate, "target_ref", None),
        )
        for candidate in decision.candidates
    }
    assert actual == expected


def test_combat_candidate_set_is_sound_and_complete_from_public_state() -> None:
    backend = CombatV0Backend()
    decision = backend.reset(
        scenario_from_id("simple__ironclad_sequencing", seed=19, enemy_max_hp=35)
    )

    for _ in range(24):
        if decision.status is not DecisionStatus.ACTIONABLE:
            break
        _assert_combat_candidates_complete(decision)
        snapshot = deepcopy(backend.snapshot())
        for candidate in decision.candidates:
            fork = CombatV0Backend()
            restored = fork.restore(deepcopy(snapshot))
            matching = next(
                item for item in restored.candidates if item.candidate_id == candidate.candidate_id
            )
            transition = fork.apply(_request(restored, matching.candidate_id))
            assert transition.result is TransitionResult.ACCEPTED
        end_turn = next(
            item
            for item in decision.candidates
            if item.kind is CandidateKind.COMBAT_END_TURN
        )
        decision = backend.apply(_request(decision, end_turn.candidate_id)).next_decision
    else:
        raise AssertionError("bounded combat characterization did not terminate")


def _assert_progression_candidates_complete(decision: DecisionState) -> None:
    observation = decision.observation.data
    if decision.phase is DecisionPhase.REWARD:
        expected: set[tuple[str, str | None, str | None]] = set()
        for reward in observation["rewards"]:
            if reward["kind"] == "gold" and not reward["claimed"]:
                expected.add(
                    (CandidateKind.REWARD_CLAIM_GOLD.value, reward["reward_ref"], None)
                )
            if reward["kind"] == "card" and not reward["opened"]:
                expected.add(
                    (
                        CandidateKind.REWARD_OPEN_CARD_REWARD.value,
                        reward["reward_ref"],
                        None,
                    )
                )
            if (
                reward["kind"] == "card"
                and reward["opened"]
                and not reward["claimed"]
            ):
                expected.update(
                    (
                        CandidateKind.REWARD_CHOOSE_CARD.value,
                        reward["reward_ref"],
                        offer["offer_ref"],
                    )
                    for offer in reward["offers"]
                )
                if reward["can_skip"]:
                    expected.add(
                        (CandidateKind.REWARD_SKIP_CARD.value, reward["reward_ref"], None)
                    )
        if observation["can_proceed"]:
            expected.add((CandidateKind.REWARD_PROCEED.value, None, None))
        actual = {
            (
                item.kind.value,
                getattr(item, "reward_ref", None),
                getattr(item, "offer_ref", None),
            )
            for item in decision.candidates
        }
        assert actual == expected
    elif decision.phase is DecisionPhase.MAP:
        assert {item.node_ref for item in decision.candidates} == {
            node["node_ref"] for node in observation["nodes"] if node["available"]
        }
    elif decision.phase is DecisionPhase.ROOM:
        enabled = {option["option_ref"]: option for option in observation["options"] if option["enabled"]}
        action_refs = {
            getattr(item, "option_ref", None)
            for item in decision.candidates
            if item.kind is not CandidateKind.ROOM_PROCEED
        }
        assert action_refs == set(enabled)
        assert any(item.kind is CandidateKind.ROOM_PROCEED for item in decision.candidates) == observation["can_proceed"]


def _choose_reduced_candidate(decision: DecisionState, *, room: str) -> str:
    if decision.phase is DecisionPhase.COMBAT:
        _assert_combat_candidates_complete(decision)
        hand = {
            card["card_ref"]: card["card_definition_id"]
            for card in decision.observation.data["hand"]
        }
        attacks = [
            item
            for item in decision.candidates
            if item.kind is CandidateKind.COMBAT_PLAY_CARD
            and hand[item.card_ref] in _TARGETED_CARDS
        ]
        chosen = attacks[0] if attacks else next(
            item for item in decision.candidates if item.kind is CandidateKind.COMBAT_END_TURN
        )
        return chosen.candidate_id
    _assert_progression_candidates_complete(decision)
    priorities = {
        DecisionPhase.REWARD: (
            CandidateKind.REWARD_CLAIM_GOLD,
            CandidateKind.REWARD_OPEN_CARD_REWARD,
            CandidateKind.REWARD_CHOOSE_CARD,
            CandidateKind.REWARD_SKIP_CARD,
            CandidateKind.REWARD_PROCEED,
        ),
        DecisionPhase.ROOM: (
            CandidateKind.ROOM_REST_HEAL,
            CandidateKind.ROOM_EVENT_OPTION,
            CandidateKind.ROOM_PROCEED,
        ),
    }
    if decision.phase is DecisionPhase.MAP:
        node_kinds = {
            node["node_ref"]: node["kind"] for node in decision.observation.data["nodes"]
        }
        preferred = [
            item for item in decision.candidates if node_kinds[item.node_ref] == room
        ]
        if preferred:
            return preferred[0].candidate_id
        return decision.candidates[0].candidate_id
    for kind in priorities[decision.phase]:
        matching = [item for item in decision.candidates if item.kind is kind]
        if matching:
            return matching[0].candidate_id
    raise AssertionError("no bounded candidate selection")


@pytest.mark.parametrize("room", ("rest", "event"))
def test_reduced_candidates_are_all_sound_and_progression_sets_are_complete(room: str) -> None:
    backend = ReducedRunBackend()
    decision = backend.reset(
        _reduced_config(initial_hp=60, combat_settings={"enemy_max_hp": 6})
    )
    seen: set[CandidateKind] = set()

    for _ in range(80):
        if decision.status is not DecisionStatus.ACTIONABLE:
            break
        if decision.phase is DecisionPhase.COMBAT:
            _assert_combat_candidates_complete(decision)
        else:
            _assert_progression_candidates_complete(decision)
        seen.update(item.kind for item in decision.candidates)
        snapshot = deepcopy(backend.snapshot())
        for candidate in decision.candidates:
            fork = ReducedRunBackend()
            restored = fork.restore(deepcopy(snapshot))
            matching = next(
                item for item in restored.candidates if item.candidate_id == candidate.candidate_id
            )
            assert fork.apply(_request(restored, matching.candidate_id)).result is TransitionResult.ACCEPTED
        chosen_id = _choose_reduced_candidate(decision, room=room)
        decision = backend.apply(_request(decision, chosen_id)).next_decision
    else:
        raise AssertionError("reduced route exceeded its bounded decision budget")

    assert decision.status is DecisionStatus.TERMINAL
    assert {
        CandidateKind.COMBAT_PLAY_CARD,
        CandidateKind.COMBAT_END_TURN,
        CandidateKind.REWARD_CLAIM_GOLD,
        CandidateKind.REWARD_OPEN_CARD_REWARD,
        CandidateKind.REWARD_CHOOSE_CARD,
        CandidateKind.REWARD_SKIP_CARD,
        CandidateKind.REWARD_PROCEED,
        CandidateKind.MAP_CHOOSE_NODE,
        CandidateKind.ROOM_PROCEED,
    } <= seen
    expected_room_kind = (
        CandidateKind.ROOM_REST_HEAL if room == "rest" else CandidateKind.ROOM_EVENT_OPTION
    )
    assert expected_room_kind in seen
