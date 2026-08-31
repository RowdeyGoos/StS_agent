"""Tests for the contract-only generic headless episode runner."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from game.contracts.headless_v0 import (
    CombatEndTurnCandidate,
    DecisionPhase,
    DecisionState,
    DecisionStatus,
    HeadlessBinding,
    PublicObservation,
    PublicScope,
    Transition,
    TransitionReason,
    TransitionResult,
    combat_card_reference,
    combat_enemy_reference,
)
from game.runtime.episode_runner import (
    EpisodeRunnerContractError,
    EpisodeStopReason,
    run_episode,
)


_FINGERPRINT = "a" * 64


def _scope(ordinal: int) -> PublicScope:
    return PublicScope(
        history_ordinal=0,
        decision_ordinal=ordinal,
        reveal_ordinals={
            "card": 0,
            "enemy": 0,
            "node": 0,
            "offer": 0,
            "option": 0,
            "reward": 0,
        },
    )


def _decision(sequence: int, status: DecisionStatus = DecisionStatus.ACTIONABLE) -> DecisionState:
    phase = DecisionPhase.COMBAT if status is DecisionStatus.ACTIONABLE else {
        DecisionStatus.TERMINAL: DecisionPhase.TERMINAL,
        DecisionStatus.UNSUPPORTED: DecisionPhase.UNSUPPORTED,
        DecisionStatus.WAITING: DecisionPhase.COMBAT,
    }[status]
    if phase is DecisionPhase.COMBAT:
        enemy_ref = combat_enemy_reference(_scope(sequence), "jaw_worm", 0)
        card_ref = combat_card_reference(_scope(sequence), "strike", 0)
        data = {
            "discard_pile_size": 0,
            "draw_pile_size": 0,
            "enemies": [
                {
                    "alive": True,
                    "block": 0,
                    "enemy_definition_id": "jaw_worm",
                    "enemy_ref": enemy_ref,
                    "hp": 40,
                    "intent": {
                        "attack_count": 1,
                        "attack_damage": 10,
                        "block_gain": 0,
                        "kind": "attack",
                        "slimed_added": 0,
                        "status_kind": "none",
                        "status_stacks": 0,
                        "strength_gain": 0,
                    },
                    "max_hp": 40,
                    "statuses": {"shrink": 0, "vulnerable": 0},
                    "strength": 0,
                }
            ],
            "exhaust_pile_size": 0,
            "hand": [
                {
                    "card_definition_id": "strike",
                    "card_ref": card_ref,
                    "cost": 1,
                    "upgraded": False,
                }
            ],
            "outcome": "ongoing",
            "player": {
                "block": 0,
                "energy": 3,
                "energy_per_turn": 3,
                "hp": 80,
                "max_hp": 80,
                "statuses": {"shrink": 0, "vulnerable": 0},
                "strength": 0,
            },
            "terminal": False,
            "turn": sequence + 1,
        }
    elif phase is DecisionPhase.TERMINAL:
        data = {"outcome": "victory", "player": {"deck_size": 10, "gold": 0, "hp": 80, "max_hp": 80}}
    else:
        data = {"reason_code": "unsupported_phase"}
    observation = PublicObservation(phase, data, _scope(sequence))
    candidates = () if status is not DecisionStatus.ACTIONABLE else (CombatEndTurnCandidate(observation.public_scope.decision_scope),)
    return DecisionState.create(
        backend_id="fake",
        backend_version="v1",
        backend_fingerprint=_FINGERPRINT,
        content_version="v1",
        content_fingerprint=_FINGERPRINT,
        rules_version="v1",
        rules_fingerprint=_FINGERPRINT,
        run_id="run",
        decision_sequence=sequence,
        status=status,
        phase=phase,
        observation=observation,
        candidates=candidates,
    )


@dataclass
class _FakeBackend:
    decisions: list[DecisionState]
    apply_calls: int = 0
    received_requests: list[object] | None = None

    def __post_init__(self) -> None:
        self.index = 0
        self.received_requests = []

    def reset(self, configuration: object) -> DecisionState:
        assert configuration == {"fixture": True}
        self.index = 0
        return self.decisions[0]

    def observe(self) -> DecisionState:
        return self.decisions[self.index]

    def apply(self, action: object) -> Transition:
        self.apply_calls += 1
        self.received_requests.append(action)
        current = self.decisions[self.index]
        self.index += 1
        next_decision = self.decisions[self.index]
        return Transition(
            TransitionResult.ACCEPTED,
            TransitionReason.ACCEPTED,
            HeadlessBinding.for_candidate(current, current.candidates[0].candidate_id),
            next_decision.public_events,
            next_decision,
        )


def test_runner_executes_deterministic_episode_with_public_view_only() -> None:
    backend = _FakeBackend([_decision(0), _decision(1), _decision(2, DecisionStatus.TERMINAL)])
    seen = []

    def chooser(view):
        seen.append(view)
        assert not hasattr(view, "decision_hash")
        assert not hasattr(view, "run_id")
        return view.candidates[0].candidate_id

    result = run_episode(backend, {"fixture": True}, chooser, transition_budget=4)

    assert result.stop_reason is EpisodeStopReason.TERMINAL
    assert result.transition_count == 2
    assert len(seen) == 2
    assert backend.apply_calls == 2


def test_runner_rejects_an_unadvertised_choice_without_applying() -> None:
    backend = _FakeBackend([_decision(0), _decision(1, DecisionStatus.TERMINAL)])

    result = run_episode(backend, {"fixture": True}, lambda view: "cand." + "0" * 64, transition_budget=1)

    assert result.stop_reason is EpisodeStopReason.UNADVERTISED_CANDIDATE
    assert result.transition_count == 0
    assert backend.apply_calls == 0


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (DecisionStatus.TERMINAL, EpisodeStopReason.TERMINAL),
        (DecisionStatus.UNSUPPORTED, EpisodeStopReason.UNSUPPORTED),
    ],
)
def test_runner_stops_at_non_actionable_boundary(status, reason) -> None:
    backend = _FakeBackend([_decision(0, status)])

    result = run_episode(backend, {"fixture": True}, lambda view: view.candidates[0].candidate_id, transition_budget=1)

    assert result.stop_reason is reason
    assert result.transition_count == 0
    assert backend.apply_calls == 0


def test_runner_stops_before_exceeding_transition_budget() -> None:
    backend = _FakeBackend([_decision(0), _decision(1), _decision(2, DecisionStatus.TERMINAL)])

    result = run_episode(backend, {"fixture": True}, lambda view: view.candidates[0].candidate_id, transition_budget=1)

    assert result.stop_reason is EpisodeStopReason.TRANSITION_BUDGET_EXHAUSTED
    assert result.transition_count == 1
    assert backend.apply_calls == 1


def test_runner_rejects_regressing_observed_decision_sequence() -> None:
    reset = _decision(1)
    observed = _decision(0)

    class RegressingBackend:
        def reset(self, configuration):
            return reset

        def observe(self):
            return observed

        def apply(self, action):
            raise AssertionError("apply should not run")

    with pytest.raises(EpisodeRunnerContractError, match="regressed"):
        run_episode(RegressingBackend(), None, lambda view: view.candidates[0].candidate_id, transition_budget=1)
