"""Small backend-neutral policies for the ``headless_v0`` runner.

These policies are smoke-test consumers, not gameplay solvers.  They operate
on the contract's :class:`PolicyView` only; in particular, they never receive
or reconstruct a backend, control binding, game RNG, or private world state.
"""

from __future__ import annotations

from random import Random
from typing import Callable

from game.contracts.headless_v0 import (
    CandidateKind,
    DecisionPhase,
    PolicyView,
    TypedCandidate,
)


def _candidate_ids(view: PolicyView) -> tuple[str, ...]:
    if not isinstance(view, PolicyView):
        raise TypeError("chooser input must be a PolicyView")
    if not view.candidates:
        raise ValueError("cannot choose from a policy view without candidates")
    return tuple(candidate.candidate_id for candidate in view.candidates)


class FirstLegalChooser:
    """Choose the first candidate in the contract's canonical ordering."""

    def __call__(self, view: PolicyView) -> str:
        return _candidate_ids(view)[0]


class SeededRandomChooser:
    """Choose uniformly from advertised candidates using a private policy RNG."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = Random(seed)

    def __call__(self, view: PolicyView) -> str:
        return self._rng.choice(_candidate_ids(view))


def choose_first_legal(view: PolicyView) -> str:
    """Functional form of :class:`FirstLegalChooser`."""

    return FirstLegalChooser()(view)


def choose_seeded_random(view: PolicyView, *, seed: int | None = None) -> str:
    """Choose one candidate with a fresh, explicitly configured policy seed.

    Repeated calls with this function and the same seed are deterministic.  A
    caller that wants one progressing random stream should use
    :class:`SeededRandomChooser` instead.
    """

    return SeededRandomChooser(seed)(view)


def _structural_score(view: PolicyView, candidate: TypedCandidate) -> tuple[int, str]:
    """Return a deliberately coarse, public-only preference score."""

    kind = candidate.kind
    if view.phase is DecisionPhase.COMBAT:
        if kind is CandidateKind.COMBAT_PLAY_CARD:
            card_id = getattr(candidate, "card_ref", "")
            # References are opaque, so use the public hand record to locate
            # the matching definition.  The fallback remains deterministic.
            hand = view.observation.data.get("hand", ())
            definition = next(
                (
                    item.get("card_definition_id", "")
                    for item in hand
                    if item.get("card_ref") == card_id
                ),
                "",
            )
            preference = {
                "bash": 40,
                "body_slam": 35,
                "strike": 30,
                "iron_wave": 25,
                "pommel_strike": 20,
                "shrug_it_off": 15,
                "defend": 10,
            }.get(definition, 5)
            return (preference, candidate.candidate_id)
        if kind is CandidateKind.COMBAT_END_TURN:
            return (0, candidate.candidate_id)

    # Progression choices are intentionally simple and deterministic.  Gold
    # and healing are useful smoke-route defaults; otherwise choose the first
    # advertised option without pretending to evaluate long-term value.
    preference = {
        CandidateKind.REWARD_CLAIM_GOLD: 30,
        CandidateKind.REWARD_OPEN_CARD_REWARD: 20,
        CandidateKind.REWARD_CHOOSE_CARD: 15,
        CandidateKind.REWARD_SKIP_CARD: 10,
        CandidateKind.ROOM_REST_HEAL: 30,
        CandidateKind.ROOM_EVENT_OPTION: 20,
        CandidateKind.MAP_CHOOSE_NODE: 10,
        CandidateKind.REWARD_PROCEED: 5,
        CandidateKind.ROOM_PROCEED: 5,
    }.get(kind, 0)
    return (preference, candidate.candidate_id)


def choose_structural_heuristic(view: PolicyView) -> str:
    """Choose a stable public-only action for reduced smoke episodes.

    This is structural plumbing, not an optimal policy: it has no learned
    value estimate, search, counterfactual reasoning, or target-game claim.
    """

    _candidate_ids(view)
    candidates = view.candidates
    return max(candidates, key=lambda candidate: _structural_score(view, candidate)).candidate_id


def make_first_legal_chooser() -> Callable[[PolicyView], str]:
    return FirstLegalChooser()


def make_seeded_random_chooser(seed: int | None = None) -> Callable[[PolicyView], str]:
    return SeededRandomChooser(seed)


def make_structural_heuristic() -> Callable[[PolicyView], str]:
    return choose_structural_heuristic
