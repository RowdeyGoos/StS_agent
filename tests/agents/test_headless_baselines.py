"""Tests for public-only headless smoke choosers."""

from __future__ import annotations

import random

import pytest

from game.agents.headless_baselines import (
    FirstLegalChooser,
    SeededChooserConfig,
    SeededRandomChooser,
    choose_first_legal,
    choose_seeded_random,
    choose_structural_heuristic,
    make_first_legal_chooser,
    make_seeded_random_chooser,
    make_structural_heuristic,
)
from game.backends.headless.combat_v0_backend import CombatV0Backend
from game.backends.headless.fixture_backend import FixtureBackend
from game.backends.headless.reduced_run_backend import HeadlessRunConfig, ReducedRunBackend
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.contracts.headless_v0 import PolicyView
from game.backends.headless.scenarios import scenario_from_id
from game.runtime.episode_runner import EpisodeStopReason, run_episode
from tests.runtime.test_episode_runner import _decision


def _view(sequence: int = 0) -> PolicyView:
    return _decision(sequence).policy_view()


def _multi_candidate_view() -> PolicyView:
    return CombatV0Backend().reset(
        scenario_from_id("simple__starter", seed=1)
    ).policy_view()


def test_first_legal_is_deterministic_and_advertised() -> None:
    view = _view()
    chooser = FirstLegalChooser()
    chosen = chooser(view)
    assert chosen == view.candidates[0].candidate_id
    assert chosen in {candidate.candidate_id for candidate in view.candidates}


def test_seeded_random_stream_is_reproducible_and_uses_only_candidates() -> None:
    view = _multi_candidate_view()
    left = SeededRandomChooser(SeededChooserConfig(17))
    right = SeededRandomChooser(SeededChooserConfig(17))
    left_choices = [left(view) for _ in range(12)]
    right_choices = [right(view) for _ in range(12)]
    assert left_choices == right_choices
    assert len(set(left_choices)) > 1
    assert set(left_choices) <= {candidate.candidate_id for candidate in view.candidates}


def test_seeded_random_configuration_is_strict_and_seed_changes_stream() -> None:
    with pytest.raises(TypeError):
        SeededChooserConfig(True)
    with pytest.raises(TypeError):
        SeededRandomChooser(1)  # type: ignore[arg-type]
    view = _multi_candidate_view()
    first = SeededRandomChooser(SeededChooserConfig(1))
    second = SeededRandomChooser(SeededChooserConfig(2))
    assert [first(view) for _ in range(12)] != [second(view) for _ in range(12)]
    assert not hasattr(view, "run_id")
    assert not hasattr(view, "decision_hash")


def test_seeded_random_does_not_mutate_global_rng_or_policy_view() -> None:
    view = _multi_candidate_view()
    before_view = view
    random.seed(991)
    before_rng = random.getstate()
    chooser = SeededRandomChooser(SeededChooserConfig(3))
    chooser(view)
    assert random.getstate() == before_rng
    assert view == before_view


def test_structural_heuristic_is_deterministic_and_advertised() -> None:
    view = _view()
    chosen = choose_structural_heuristic(view)
    assert chosen == choose_structural_heuristic(view)
    assert chosen in {candidate.candidate_id for candidate in view.candidates}


def test_functional_and_factory_forms_match_contract_boundary() -> None:
    view = _multi_candidate_view()
    assert choose_first_legal(view) == make_first_legal_chooser()(view)
    config = SeededChooserConfig(11)
    expected = SeededRandomChooser(config)
    actual = make_seeded_random_chooser(config)
    assert choose_seeded_random(view, config=config) == expected(view)
    assert actual(view) in {candidate.candidate_id for candidate in view.candidates}
    assert make_structural_heuristic()(view) == choose_structural_heuristic(view)


def test_structural_heuristic_completes_reduced_smoke_route() -> None:
    backend = ReducedRunBackend()
    phases = []

    def chooser(view: PolicyView) -> str:
        phases.append(view.phase.value)
        chosen = choose_structural_heuristic(view)
        assert chosen in {candidate.candidate_id for candidate in view.candidates}
        return chosen

    configuration = HeadlessRunConfig(
        scenario_id="simple__starter",
        content_fingerprint=CONTENT_FINGERPRINT,
        game_seed=7,
        backend_settings={},
    )
    result = run_episode(
        backend,
        configuration,
        chooser,
        transition_budget=300,
    )
    assert result.stop_reason is EpisodeStopReason.TERMINAL
    assert backend.terminal_reason == "route_complete"
    assert {"combat", "reward", "map", "room"} <= set(phases)


def test_first_legal_accepts_the_recorded_fixture_branch_only() -> None:
    backend = FixtureBackend()
    result = run_episode(backend, "combat", FirstLegalChooser(), transition_budget=10)
    assert result.stop_reason is EpisodeStopReason.TERMINAL


@pytest.mark.parametrize(
    "chooser",
    (
        FirstLegalChooser(),
        SeededRandomChooser(SeededChooserConfig(3)),
        choose_structural_heuristic,
    ),
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
