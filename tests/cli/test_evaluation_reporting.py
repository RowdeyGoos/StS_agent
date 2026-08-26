"""Tests for encounter-aware evaluation CLI output."""

from __future__ import annotations

from game.agents.baselines import EncounterEvaluationStats, EvaluationStats
from game.cli.train import comparison_evaluation_seed, parse_args, print_evaluation


def test_print_evaluation_includes_damage_and_encounter_rows(capsys) -> None:
    stats = EvaluationStats(
        episodes=2,
        mean_reward=0.25,
        win_rate=0.5,
        mean_steps=4.0,
        mean_player_hp=6.0,
        mean_damage_taken=2.0,
        by_encounter=(
            EncounterEvaluationStats(
                encounter="nibbit",
                episodes=2,
                mean_reward=0.25,
                win_rate=0.5,
                mean_steps=4.0,
                mean_player_hp=6.0,
                mean_damage_taken=2.0,
            ),
        ),
    )

    print_evaluation("Evaluation", stats)

    output_lines = capsys.readouterr().out.splitlines()
    assert output_lines[0].startswith("Evaluation: episodes=2")
    assert "mean_damage_taken=2.00" in output_lines[0]
    assert output_lines[1].startswith("  nibbit: episodes=2")
    assert "mean_damage_taken=2.00" in output_lines[1]


def test_compare_uses_documented_final_seed_offset() -> None:
    compare_args = parse_args(["--policy", "compare", "--seed", "11"])
    standalone_args = parse_args(["--policy", "q_learning", "--seed", "11"])

    assert comparison_evaluation_seed(compare_args) == 100_011
    assert comparison_evaluation_seed(standalone_args) is None
