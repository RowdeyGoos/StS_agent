"""Tests for public-only headless smoke choosers."""

from __future__ import annotations

import pytest

from game.agents.headless_baselines import (
    FirstLegalChooser,
    SeededRandomChooser,
    choose_structural_heuristic,
)
from game.backends.headless.reduced_run_backend import HeadlessRunConfig, ReducedRunBackend
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import PolicyView
from game.runtime.episode_runner import EpisodeStopReason, run_episode
from tests.runtime.test_episode_runner import _decision


def _view(sequence: int = 0) -> PolicyView:
    return _decision(sequence).policy_view()


def test_first_legal_is_deterministic_and_advertised() -> None:
    view = _view()
    chooser = FirstLegalChooser()
    chosen = chooser(view)
    assert chosen == view.candidates[0].candidate_id
    assert chosen in {candidate.candidate_id for candidate in view.candidates}


def test_seeded_random_stream_is_reproducible_and_uses_only_candidates() -> None:
    view = _view()
    left = SeededRandomChooser(17)
    right = SeededRandomChooser(17)
    left_choices = [left(view) for _ in range(12)]
    right_choices = [right(view) for _ in range(12)]
    assert left_choices == right_choices
    assert set(left_choices) <= {candidate.candidate_id for candidate in view.candidates}


def test_seeded_random_chooser_configuration_is_separate_from_view() -> None:
    first = SeededRandomChooser(1)
    second = SeededRandomChooser(2)
    view = _view()
    assert all(first(view) == view.candidates[0].candidate_id for _ in range(8))
    assert all(second(view) == view.candidates[0].candidate_id for _ in range(8))
    assert not hasattr(view, "run_id")
    assert not hasattr(view, "decision_hash")


def test_structural_heuristic_is_deterministic_and_advertised() -> None:
    view = _view()
    chosen = choose_structural_heuristic(view)
    assert chosen == choose_structural_heuristic(view)
    assert chosen in {candidate.candidate_id for candidate in view.candidates}


def test_structural_heuristic_completes_reduced_smoke_route() -> None:
    configuration = HeadlessRunConfig(
        scenario_id="simple__starter",
        content_fingerprint=CONTENT_FINGERPRINT,
        game_seed=7,
        backend_settings={},
    )
    result = run_episode(
        ReducedRunBackend(),
        configuration,
        choose_structural_heuristic,
        transition_budget=300,
    )
    assert result.stop_reason is EpisodeStopReason.TERMINAL


@pytest.mark.parametrize(
    "chooser", (FirstLegalChooser(), SeededRandomChooser(3), choose_structural_heuristic)
)
def test_choosers_reject_empty_or_non_policy_inputs(chooser) -> None:
    with pytest.raises(ValueError, match="without candidates"):
        chooser(
            PolicyView(
                status="terminal",
                phase="terminal",
                observation=_view().observation.__class__(
                    "terminal",
                    {
                        "outcome": "victory",
                        "player": {"deck_size": 10, "gold": 0, "hp": 80, "max_hp": 80},
                    },
                    _view().observation.public_scope,
                ),
                candidates=(),
                public_events=(),
            )
        )
    with pytest.raises(TypeError):
        chooser(object())
