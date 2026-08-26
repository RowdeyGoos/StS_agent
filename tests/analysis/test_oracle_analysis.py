"""Tests for per-decision oracle regret analysis."""

from __future__ import annotations

from game.simulation.card import DefendCard, StrikeCard
from game.simulation.core import CombatEnv
from game.simulation.enemy import SimpleEnemy
from game.analysis.oracle import (
    analyze_episode_trace_with_oracle,
    analyze_oracle_decision,
)
from game.analysis.watch import trace_policy_episode


def _make_two_card_env(two_strikes: bool = False) -> CombatEnv:
    return CombatEnv(
        deck_factory=(
            (lambda: [StrikeCard(), StrikeCard()])
            if two_strikes
            else (lambda: [StrikeCard(), DefendCard()])
        ),
        enemy_factory=lambda: SimpleEnemy(max_hp=6),
        cards_per_turn=2,
        record_trajectory=False,
    )


def test_oracle_decision_reports_action_count_regret() -> None:
    env = _make_two_card_env()
    observation = env.reset(seed=0)
    defend_index = observation["hand"].index("Defend")
    selected_action_index = env.encode_action(("play", defend_index))

    analysis = analyze_oracle_decision(
        env,
        selected_action_index,
        max_steps=5,
        max_nodes_per_action=1_000,
    )

    strike_index = observation["hand"].index("Strike")
    strike_action_index = env.encode_action(("play", strike_index))
    assert analysis.comparison_proven is True
    assert analysis.selected_is_optimal is False
    assert analysis.decisive_dimension == "actions"
    assert analysis.action_count_regret == 1
    assert analysis.best_found_action_indices == (strike_action_index,)
    assert len(analysis.action_evaluations) == len(env.get_legal_actions())


def test_oracle_decision_recognizes_equally_optimal_actions() -> None:
    env = _make_two_card_env(two_strikes=True)
    env.reset(seed=0)
    selected_action_index = env.encode_action(("play", 0))

    analysis = analyze_oracle_decision(
        env,
        selected_action_index,
        max_steps=3,
        max_nodes_per_action=1_000,
    )

    assert analysis.comparison_proven is True
    assert analysis.selected_is_optimal is True
    assert analysis.decisive_dimension == "none"
    assert set(analysis.best_found_action_indices) == {
        env.encode_action(("play", 0)),
        env.encode_action(("play", 1)),
    }


def test_oracle_decision_does_not_overclaim_when_search_is_bounded() -> None:
    env = _make_two_card_env()
    observation = env.reset(seed=0)
    defend_index = observation["hand"].index("Defend")

    analysis = analyze_oracle_decision(
        env,
        env.encode_action(("play", defend_index)),
        max_steps=1,
        max_nodes_per_action=100,
    )

    assert analysis.comparison_proven is False
    assert analysis.selected_is_optimal is None
    assert analysis.selected_matches_best_found is False
    assert analysis.decisive_dimension == "unknown"


def test_episode_oracle_analysis_finds_first_divergence_and_ranks_it() -> None:
    policy_state = {"decision": 0}

    def defend_then_strike(env: CombatEnv, observation: dict, _mask: tuple[int, ...]) -> int:
        card_name = "Defend" if policy_state["decision"] == 0 else "Strike"
        policy_state["decision"] += 1
        hand_index = observation["hand"].index(card_name)
        return env.encode_action(("play", hand_index))

    trace = trace_policy_episode(
        env=_make_two_card_env(),
        policy=defend_then_strike,
        policy_name="test_policy",
        seed=0,
    )
    analysis = analyze_episode_trace_with_oracle(
        env=_make_two_card_env(),
        trace=trace,
        max_steps=5,
        max_nodes_per_action=1_000,
    )
    payload = analysis.as_dict()

    assert len(analysis.decisions) == 2
    assert len(analysis.proven_divergences) == 1
    assert analysis.proven_divergences[0].decision_index == 0
    assert analysis.ranked_weak_points[0].decision_index == 0
    assert payload["first_proven_divergence_index"] == 0
    assert payload["ranked_weak_point_indices"] == [0]


def test_oracle_analysis_rejects_nonpositive_worker_count() -> None:
    env = _make_two_card_env()
    env.reset(seed=0)

    try:
        analyze_oracle_decision(env, 0, search_workers=0)
    except ValueError as exc:
        assert "search_workers" in str(exc)
    else:
        raise AssertionError("Expected a nonpositive worker count to be rejected.")
