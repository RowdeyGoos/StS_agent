"""Cross-workstream regressions for the integrated combat representation."""

from __future__ import annotations

import pytest

from game.agents.baselines import choose_heuristic_action, evaluate_policy
from game.cli.benchmark import parse_args as parse_benchmark_args
from game.simulation.action_features import summarize_action
from game.simulation.card import BodySlamCard, StrikeCard
from game.simulation.core import CombatEnv
from game.simulation.encoding import (
    DEFAULT_CARD_NAME_TO_ID,
    DEFAULT_ENEMY_NAME_TO_ID,
    DEFAULT_MOVE_NAME_TO_ID,
)
from game.simulation.enemy import FuzzyWurmCrawler, Mawler
from game.simulation.env_factory import CombatEnvFactory


def test_combined_encoder_appends_enemy_and_card_schemas() -> None:
    simple_env = CombatEnv()
    hard_env = CombatEnvFactory(encounter_set="overgrowth_hard_v1")()

    assert (simple_env.observation_size, simple_env.action_feature_size) == (169, 48)
    assert (hard_env.observation_size, hard_env.action_feature_size) == (257, 48)
    assert (simple_env.action_space_size, hard_env.action_space_size) == (11, 31)
    assert DEFAULT_CARD_NAME_TO_ID["Slimed"] == 4
    assert DEFAULT_CARD_NAME_TO_ID["Pommel Strike"] == 5
    assert DEFAULT_ENEMY_NAME_TO_ID["Fuzzy Wurm Crawler"] == 8
    assert DEFAULT_ENEMY_NAME_TO_ID["Mawler"] == 9
    assert DEFAULT_MOVE_NAME_TO_ID["Clump Shot"] == 15
    assert DEFAULT_MOVE_NAME_TO_ID["Claw"] == 16


def test_summary_driven_heuristic_uses_total_multi_hit_target_threat() -> None:
    env = CombatEnv(
        deck_factory=lambda: [StrikeCard()],
        encounter_factory=lambda rng: [Mawler(rng), FuzzyWurmCrawler(rng)],
        cards_per_turn=1,
        max_enemy_count=3,
    )
    observation = env.reset(seed=0)

    action = env.decode_action(
        choose_heuristic_action(env, observation, env.get_action_mask())
    )

    assert action == ("play", 0, 0)
    mawler_summary = summarize_action(observation, action)
    assert mawler_summary.target_intent_attack_damage == 8


def test_body_slam_summary_preserves_per_hit_incoming_projection() -> None:
    env = CombatEnv(
        deck_factory=lambda: [BodySlamCard()],
        encounter_factory=lambda rng: [Mawler(rng)],
        cards_per_turn=1,
    )
    env.reset(seed=0)
    assert env.player is not None
    env.player.block = 5
    observation = env.get_observation()

    summary = summarize_action(observation, ("play", 0))

    assert summary.damage_to_target == 5
    assert summary.target_intent_attack_damage == 8
    assert summary.projected_incoming_hp_loss_before == 3
    assert summary.projected_incoming_hp_loss_after == 3


def test_hard_pool_evaluation_uses_canonical_encounter_rows() -> None:
    stats = evaluate_policy(
        env_factory=CombatEnvFactory(encounter_set="overgrowth_hard_v1"),
        policy=lambda _env, _observation, _mask: 0,
        episodes=12,
        seed=0,
    )

    assert {row.encounter for row in stats.by_encounter} == {
        "mawler",
        "nibbits",
        "shrinker_fuzzy",
    }
    assert stats.mean_damage_taken > 0.0


def test_benchmark_accepts_new_fixed_encounters_but_rejects_sampled_hard_pool() -> None:
    args = parse_benchmark_args(
        [
            "--encounter",
            "mawler",
            "--encounter",
            "nibbits",
            "--episodes",
            "1",
        ]
    )
    assert args.encounter == ["mawler", "nibbits"]

    with pytest.raises(SystemExit):
        parse_benchmark_args(["--encounter", "overgrowth_hard_v1"])
