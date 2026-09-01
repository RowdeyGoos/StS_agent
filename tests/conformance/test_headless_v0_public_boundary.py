"""Actor-facing information-boundary conformance for headless_v0."""

from __future__ import annotations

from dataclasses import fields
import json
import re
from typing import Any, Mapping, Sequence

import pytest

from game.backends.headless.combat_v0_backend import CombatV0Backend
from game.backends.headless.fixture_backend import FixtureBackend
from game.backends.headless.reduced_run_backend import HeadlessRunConfig, ReducedRunBackend
from game.backends.headless.scenarios import scenario_from_id
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import (
    ActionRequest,
    CandidateKind,
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    HeadlessBinding,
    PolicyView,
    candidate_to_dict,
)
from game.data.headless_trajectory import (
    DecisionCorrelation,
    HindsightTargetRecord,
    PolicyReplayRecord,
    SyntheticAuditRecord,
    TrajectoryCompletion,
    policy_view_for,
)
from game.runtime.episode_runner import run_episode


_FORBIDDEN_PUBLIC_COMPONENTS = frozenset(
    {
        "audit",
        "commit",
        "control",
        "credential",
        "debug",
        "decision_hash",
        "diagnostic",
        "future",
        "hidden",
        "idempotency",
        "lease",
        "mask",
        "private",
        "receipt",
        "request",
        "rng",
        "seed",
        "shaped_reward",
        "snapshot",
        "token",
        "trace",
        "trajectory",
        "world_state",
    }
)
_PUBLIC_REFERENCE = re.compile(r"pub\.(card|enemy|reward|offer|node|option)\.[0-9a-f]{64}\Z")
_CANDIDATE_ID = re.compile(r"cand\.[0-9a-f]{64}\Z")
_ATTACKS = frozenset({"bash", "body_slam", "iron_wave", "pommel_strike", "strike"})


def _config(**settings: Any) -> HeadlessRunConfig:
    return HeadlessRunConfig(
        scenario_id="simple__starter",
        content_fingerprint=CONTENT_FINGERPRINT,
        game_seed=31,
        backend_settings=settings,
    )


def _request(decision: DecisionState, candidate_id: str) -> ActionRequest:
    return ActionRequest(HeadlessBinding.for_candidate(decision, candidate_id))


def _choose(view: PolicyView, *, room: str = "rest") -> str:
    if view.phase is DecisionPhase.COMBAT:
        cards = {
            card["card_ref"]: card["card_definition_id"]
            for card in view.observation.data["hand"]
        }
        attacks = [
            item
            for item in view.candidates
            if item.kind is CandidateKind.COMBAT_PLAY_CARD
            and cards[item.card_ref] in _ATTACKS
        ]
        if attacks:
            return attacks[0].candidate_id
        return next(
            item.candidate_id
            for item in view.candidates
            if item.kind is CandidateKind.COMBAT_END_TURN
        )
    if view.phase is DecisionPhase.REWARD:
        for kind in (
            CandidateKind.REWARD_CLAIM_GOLD,
            CandidateKind.REWARD_OPEN_CARD_REWARD,
            CandidateKind.REWARD_CHOOSE_CARD,
            CandidateKind.REWARD_SKIP_CARD,
            CandidateKind.REWARD_PROCEED,
        ):
            matching = [item for item in view.candidates if item.kind is kind]
            if matching:
                return matching[0].candidate_id
    if view.phase is DecisionPhase.MAP:
        kinds = {
            node["node_ref"]: node["kind"] for node in view.observation.data["nodes"]
        }
        preferred = [item for item in view.candidates if kinds[item.node_ref] == room]
        return (preferred[0] if preferred else view.candidates[0]).candidate_id
    for kind in (
        CandidateKind.ROOM_REST_HEAL,
        CandidateKind.ROOM_EVENT_OPTION,
        CandidateKind.ROOM_PROCEED,
    ):
        matching = [item for item in view.candidates if item.kind is kind]
        if matching:
            return matching[0].candidate_id
    raise AssertionError("unsupported actionable public boundary")


def _public_payload(decision: DecisionState) -> dict[str, Any]:
    view = decision.policy_view()
    return {
        "status": view.status.value,
        "phase": view.phase.value,
        "observation": view.observation.to_dict(),
        "candidates": [candidate_to_dict(item) for item in view.candidates],
        "public_events": [event.to_dict() for event in view.public_events],
    }


def _walk_keys(value: Any) -> tuple[str, ...]:
    keys: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            keys.append(key)
            keys.extend(_walk_keys(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            keys.extend(_walk_keys(item))
    return tuple(keys)


def _normalized_components(key: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
    components = set(filter(None, normalized.split("_")))
    components.add(normalized)
    return components


def _assert_public_boundary(decision: DecisionState) -> None:
    view = decision.policy_view()
    assert view.status is decision.status
    assert view.phase is decision.phase
    assert view.observation == decision.observation
    assert view.candidates == decision.candidates
    assert view.public_events == decision.public_events
    assert tuple(field.name for field in fields(view)) == (
        "status",
        "phase",
        "observation",
        "candidates",
        "public_events",
    )
    for attribute in (
        "run_id",
        "decision_sequence",
        "decision_hash",
        "backend_fingerprint",
        "content_fingerprint",
        "rules_fingerprint",
        "snapshot",
        "rng",
    ):
        assert not hasattr(view, attribute)

    public = _public_payload(decision)
    for key in _walk_keys(view.observation.data):
        assert not (_normalized_components(key) & _FORBIDDEN_PUBLIC_COMPONENTS), key
    for event in view.public_events:
        for key in _walk_keys(event.data):
            assert not (_normalized_components(key) & _FORBIDDEN_PUBLIC_COMPONENTS), key

    encoded = json.dumps(public, sort_keys=True, separators=(",", ":"))
    for private_marker in (
        decision.run_id,
        decision.decision_hash,
        decision.backend_fingerprint,
        decision.content_fingerprint,
        decision.rules_fingerprint,
    ):
        assert private_marker not in encoded


def _exercise_reduced_public_boundaries(*, room: str) -> tuple[DecisionState, ...]:
    backend = ReducedRunBackend()
    decision = backend.reset(
        _config(initial_hp=60, combat_settings={"enemy_max_hp": 6})
    )
    decisions = [decision]
    for _ in range(100):
        if decision.status is not DecisionStatus.ACTIONABLE:
            return tuple(decisions)
        candidate_id = _choose(decision.policy_view(), room=room)
        decision = backend.apply(_request(decision, candidate_id)).next_decision
        decisions.append(decision)
    raise AssertionError("public-boundary route exceeded bounded budget")


@pytest.mark.parametrize("room", ("rest", "event"))
def test_every_reduced_phase_exposes_only_the_policy_view(room: str) -> None:
    decisions = _exercise_reduced_public_boundaries(room=room)
    assert {item.phase for item in decisions} >= {
        DecisionPhase.COMBAT,
        DecisionPhase.REWARD,
        DecisionPhase.MAP,
        DecisionPhase.ROOM,
        DecisionPhase.TERMINAL,
    }
    for decision in decisions:
        _assert_public_boundary(decision)


def test_fixture_and_combat_policy_views_do_not_expose_control_identity() -> None:
    for fixture_id in ("combat", "reward", "map", "rest", "event", "unsupported"):
        backend = FixtureBackend()
        decision = backend.reset(fixture_id)
        while True:
            _assert_public_boundary(decision)
            if decision.status is not DecisionStatus.ACTIONABLE:
                break
            decision = backend.apply(
                _request(decision, decision.candidates[0].candidate_id)
            ).next_decision

    backend = CombatV0Backend()
    decision = backend.reset(
        scenario_from_id("simple__starter", seed=37, enemy_max_hp=12)
    )
    for _ in range(40):
        _assert_public_boundary(decision)
        if decision.status is not DecisionStatus.ACTIONABLE:
            break
        decision = backend.apply(
            _request(decision, _choose(decision.policy_view()))
        ).next_decision
    else:
        raise AssertionError("combat public-boundary run exceeded budget")


def test_public_references_and_candidate_ids_are_opaque_not_list_positions() -> None:
    decisions = _exercise_reduced_public_boundaries(room="event")
    for decision in decisions:
        payload = _public_payload(decision)
        references: list[str] = []

        def collect(value: Any) -> None:
            if isinstance(value, Mapping):
                for key, item in value.items():
                    if key.endswith("_ref") and isinstance(item, str):
                        references.append(item)
                    collect(item)
            elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                for item in value:
                    collect(item)

        collect(payload)
        assert all(_PUBLIC_REFERENCE.fullmatch(reference) for reference in references)
        for candidate in decision.candidates:
            assert _CANDIDATE_ID.fullmatch(candidate.candidate_id)
            assert not any(
                definition in candidate.candidate_id
                for definition in ("strike", "defend", "bash", "rest", "event")
            )


def test_runner_never_passes_backend_snapshot_or_control_envelope_to_chooser() -> None:
    backend = ReducedRunBackend()
    seen = 0

    def chooser(view: PolicyView) -> str:
        nonlocal seen
        seen += 1
        assert type(view) is PolicyView
        assert not isinstance(view, DecisionState)
        assert not hasattr(view, "__dict__")
        return _choose(view)

    result = run_episode(
        backend,
        _config(initial_hp=60, combat_settings={"enemy_max_hp": 6}),
        chooser,
        transition_budget=100,
    )
    assert result.final_decision.status is DecisionStatus.TERMINAL
    assert seen > 0


def test_runtime_unsupported_boundary_is_sanitized_and_fail_closed() -> None:
    backend = ReducedRunBackend()
    decision = backend.reset(
        _config(event_id="cool_spring", combat_settings={"enemy_max_hp": 1})
    )
    for _ in range(80):
        if decision.status is not DecisionStatus.ACTIONABLE:
            break
        decision = backend.apply(
            _request(decision, _choose(decision.policy_view(), room="event"))
        ).next_decision
    assert decision.status is DecisionStatus.UNSUPPORTED
    assert decision.phase is DecisionPhase.UNSUPPORTED
    assert dict(decision.observation.data) == {"reason_code": "unsupported_content"}
    assert "room_unavailable" not in json.dumps(_public_payload(decision))
    assert decision.candidates == ()


def test_hindsight_and_audit_sidecars_cannot_be_converted_to_policy_views() -> None:
    decision = FixtureBackend().reset("combat")
    policy = PolicyReplayRecord.from_decision(
        decision, decision.candidates[0].candidate_id
    )
    assert policy_view_for(policy) == decision.policy_view()

    target = HindsightTargetRecord(
        "trajectory.public.boundary",
        TrajectoryCompletion.INTERRUPTED,
        1,
        None,
        None,
        "before_choice",
    )
    with pytest.raises(TypeError):
        policy_view_for(target)  # type: ignore[arg-type]
    audit = SyntheticAuditRecord(
        "trajectory.public.boundary",
        0,
        0,
        DecisionCorrelation(
            decision.run_id,
            decision.decision_sequence,
            decision.decision_hash,
            decision.candidates[0].candidate_id,
        ),
        None,
        "a" * 64,
    )
    with pytest.raises(TypeError):
        policy_view_for(audit)  # type: ignore[arg-type]
