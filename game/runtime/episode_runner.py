"""Bounded public-policy episode execution for conforming headless backends."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from game.contracts.headless_v0 import (
    ActionRequest,
    DecisionState,
    DecisionStatus,
    HeadlessBinding,
    Transition,
    TransitionResult,
)
from game.runtime.decision_chooser import DecisionChooser


class EpisodeBackend(Protocol):
    """The small backend surface required by :func:`run_episode`."""

    def reset(self, configuration: Any) -> DecisionState:
        """Reset the backend and return its initial public decision boundary."""

    def observe(self) -> DecisionState:
        """Return the authoritative current public decision boundary."""

    def apply(self, action: ActionRequest) -> Transition:
        """Apply one decision-scoped action request."""


class EpisodeStopReason(str, Enum):
    """The finite terminal conditions of the generic episode loop."""

    TERMINAL = "terminal"
    UNSUPPORTED = "unsupported"
    WAITING = "waiting"
    TRANSITION_BUDGET_EXHAUSTED = "transition_budget_exhausted"
    UNADVERTISED_CANDIDATE = "unadvertised_candidate"
    REJECTED_TRANSITION = "rejected_transition"
    STALE_TRANSITION = "stale_transition"


class EpisodeRunnerContractError(RuntimeError):
    """Raised when a backend violates the runner's contract assumptions."""


@dataclass(frozen=True, slots=True)
class EpisodeResult:
    """A non-policy summary of one bounded backend execution."""

    stop_reason: EpisodeStopReason
    final_decision: DecisionState
    transition_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.stop_reason, EpisodeStopReason):
            raise TypeError("stop_reason must be an EpisodeStopReason.")
        if not isinstance(self.final_decision, DecisionState):
            raise TypeError("final_decision must be a DecisionState.")
        if (
            not isinstance(self.transition_count, int)
            or isinstance(self.transition_count, bool)
            or self.transition_count < 0
        ):
            raise ValueError("transition_count must be a nonnegative integer.")


def run_episode(
    backend: EpisodeBackend,
    configuration: Any,
    chooser: DecisionChooser,
    *,
    transition_budget: int,
) -> EpisodeResult:
    """Run one backend episode without exposing backend control state to a chooser.

    ``transition_budget`` caps calls to ``backend.apply``.  The runner does not
    sample randomness or touch a backend RNG; policy randomness, if wanted,
    belongs entirely to the supplied chooser.
    """

    _validate_transition_budget(transition_budget)
    reset_decision = _require_decision(backend.reset(configuration), "reset")
    current = _require_decision(backend.observe(), "observe after reset")
    _validate_monotonic(reset_decision, current)
    transition_count = 0

    while True:
        stop_reason = _non_actionable_stop_reason(current)
        if stop_reason is not None:
            return EpisodeResult(stop_reason, current, transition_count)
        if transition_count >= transition_budget:
            return EpisodeResult(
                EpisodeStopReason.TRANSITION_BUDGET_EXHAUSTED,
                current,
                transition_count,
            )

        chosen_candidate_id = chooser(current.policy_view())
        advertised_ids = {candidate.candidate_id for candidate in current.candidates}
        if (
            not isinstance(chosen_candidate_id, str)
            or chosen_candidate_id not in advertised_ids
        ):
            return EpisodeResult(
                EpisodeStopReason.UNADVERTISED_CANDIDATE,
                current,
                transition_count,
            )

        request = ActionRequest(
            HeadlessBinding.for_candidate(current, chosen_candidate_id)
        )
        transition = _require_transition(backend.apply(request))
        transition_count += 1
        next_decision = transition.next_decision
        _validate_transition_binding(request.binding, transition)

        if transition.result is TransitionResult.REJECTED:
            return EpisodeResult(
                EpisodeStopReason.REJECTED_TRANSITION,
                next_decision,
                transition_count,
            )
        if transition.result is TransitionResult.STALE:
            return EpisodeResult(
                EpisodeStopReason.STALE_TRANSITION,
                next_decision,
                transition_count,
            )

        observed = _require_decision(backend.observe(), "observe after apply")
        _validate_monotonic(current, next_decision)
        _validate_same_decision(next_decision, observed)
        current = observed


def _validate_transition_budget(transition_budget: int) -> None:
    if (
        not isinstance(transition_budget, int)
        or isinstance(transition_budget, bool)
        or transition_budget < 0
    ):
        raise ValueError("transition_budget must be a nonnegative integer.")


def _require_decision(value: object, operation: str) -> DecisionState:
    if not isinstance(value, DecisionState):
        raise EpisodeRunnerContractError(
            f"Backend {operation} must return a DecisionState."
        )
    return value


def _require_transition(value: object) -> Transition:
    if not isinstance(value, Transition):
        raise EpisodeRunnerContractError("Backend apply must return a Transition.")
    return value


def _non_actionable_stop_reason(
    decision: DecisionState,
) -> EpisodeStopReason | None:
    if decision.status is DecisionStatus.TERMINAL:
        return EpisodeStopReason.TERMINAL
    if decision.status is DecisionStatus.UNSUPPORTED:
        return EpisodeStopReason.UNSUPPORTED
    if decision.status is DecisionStatus.WAITING:
        return EpisodeStopReason.WAITING
    if decision.status is not DecisionStatus.ACTIONABLE:
        raise EpisodeRunnerContractError("Decision has an unknown status.")
    return None


def _validate_transition_binding(
    requested_binding: HeadlessBinding,
    transition: Transition,
) -> None:
    binding = transition.binding
    if binding != requested_binding:
        raise EpisodeRunnerContractError(
            "Backend apply returned a transition for a different action request."
        )


def _validate_monotonic(previous: DecisionState, current: DecisionState) -> None:
    if previous.run_id != current.run_id:
        raise EpisodeRunnerContractError("Backend changed run identity during an episode.")
    if current.decision_sequence < previous.decision_sequence:
        raise EpisodeRunnerContractError("Backend decision sequence regressed.")
    if (
        current.decision_sequence == previous.decision_sequence
        and current.decision_hash != previous.decision_hash
    ):
        raise EpisodeRunnerContractError(
            "Backend changed a decision without advancing its sequence."
        )


def _validate_same_decision(expected: DecisionState, observed: DecisionState) -> None:
    if (
        expected.run_id != observed.run_id
        or expected.decision_sequence != observed.decision_sequence
        or expected.decision_hash != observed.decision_hash
    ):
        raise EpisodeRunnerContractError(
            "Backend observe disagrees with the transition's next decision."
        )
