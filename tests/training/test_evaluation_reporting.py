"""Tests for encounter-aware evaluation reporting."""

from __future__ import annotations

from game.agents import baselines
from game.agents.baselines import (
    EpisodeMetrics,
    choose_heuristic_action,
    evaluate_policy,
    rollout_episode,
)
from game.simulation.card import StrikeCard
from game.simulation.core import CombatEnv
from game.simulation.env_factory import CombatEnvFactory
from game.simulation.enemy import SimpleEnemy


def test_episode_metrics_keeps_legacy_constructor_compatible() -> None:
    metrics = EpisodeMetrics(
        total_reward=1.0,
        steps=2,
        win=True,
        player_hp=7,
        enemy_hp=0,
    )

    assert metrics.damage_taken == 0
    assert metrics.encounter == "unknown"


def test_rollout_captures_fixed_encounter_and_damage_taken() -> None:
    env = CombatEnv(
        deck_factory=lambda: [StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=100),
        player_max_hp=5,
        cards_per_turn=1,
    )

    metrics = rollout_episode(env, lambda _env, _obs, _mask: 0, seed=3)

    assert metrics.encounter == "simple"
    assert metrics.win is False
    assert metrics.player_hp == 0
    assert metrics.damage_taken == 5


def test_evaluation_groups_weighted_metrics_in_sorted_order(monkeypatch) -> None:
    rollout_metrics = iter(
        (
            EpisodeMetrics(1.0, 2, True, 8, 0, 2, "zeta"),
            EpisodeMetrics(-1.0, 6, False, 0, 7, 10, "alpha"),
            EpisodeMetrics(0.5, 4, True, 4, 0, 6, "zeta"),
        )
    )
    monkeypatch.setattr(
        baselines,
        "rollout_episode",
        lambda _env, _policy, seed=None: next(rollout_metrics),
    )

    stats = evaluate_policy(
        env_factory=object,
        policy=lambda _env, _observation, _mask: 0,
        episodes=3,
        seed=20,
    )

    assert stats.episodes == 3
    assert stats.mean_reward == 0.5 / 3.0
    assert stats.win_rate == 2.0 / 3.0
    assert stats.mean_steps == 4.0
    assert stats.mean_player_hp == 4.0
    assert stats.mean_damage_taken == 6.0
    assert tuple(row.encounter for row in stats.by_encounter) == ("alpha", "zeta")
    assert stats.by_encounter[0].episodes == 1
    assert stats.by_encounter[1].episodes == 2
    assert stats.by_encounter[1].mean_reward == 0.75

    payload = stats.as_dict()
    assert tuple(payload)[:5] == (
        "episodes",
        "mean_reward",
        "win_rate",
        "mean_steps",
        "mean_player_hp",
    )
    assert payload["mean_damage_taken"] == 6.0
    assert [row["encounter"] for row in payload["by_encounter"]] == [
        "alpha",
        "zeta",
    ]


def test_sampled_pool_reports_multiple_deterministic_encounter_rows() -> None:
    stats = evaluate_policy(
        env_factory=CombatEnvFactory(encounter_set="overgrowth_easy"),
        policy=lambda _env, _observation, _mask: 0,
        episodes=8,
        seed=0,
    )

    labels = tuple(row.encounter for row in stats.by_encounter)
    assert len(labels) >= 2
    assert labels == tuple(sorted(labels))
    assert sum(row.episodes for row in stats.by_encounter) == stats.episodes


def test_encounter_labels_cover_canonical_and_fallback_compositions() -> None:
    slimes_observation = {
        "player": {"hp": 80},
        "enemies": [
            {"name": "Twig Slime (M)"},
            {"name": "Twig Slime (S)"},
            {"name": "Leaf Slime (S)"},
        ],
    }
    fallback_observation = {
        "player": {"hp": 80},
        "enemies": [
            {"name": "Odd Enemy!"},
            {"name": "Another/Odd Enemy"},
        ],
    }

    assert baselines._encounter_label_from_observation(slimes_observation) == "slimes"
    assert (
        baselines._encounter_label_from_observation(fallback_observation)
        == "odd_enemy__another_odd_enemy"
    )


def test_easy_fixed_evaluation_preserves_existing_reward_metrics() -> None:
    stats = evaluate_policy(
        env_factory=lambda: CombatEnv(
            deck_factory=lambda: [StrikeCard()],
            enemy_factory=lambda: SimpleEnemy(max_hp=6),
            cards_per_turn=1,
        ),
        policy=choose_heuristic_action,
        episodes=3,
        seed=0,
    )

    assert stats.win_rate == 1.0
    assert stats.mean_reward == 1.0
    assert stats.mean_damage_taken == 0.0
    assert tuple(row.encounter for row in stats.by_encounter) == ("simple",)
