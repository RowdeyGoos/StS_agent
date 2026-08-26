"""Tests for the fixed-seed benchmark command."""

from __future__ import annotations

import json

import pytest

from game.agents.agent_io import save_agent
from game.agents.baselines import QLearningAgent
from game.agents.dqn import DQNAgent
from game.analysis import benchmark as benchmark_module
from game.cli import benchmark
from game.simulation.env_factory import CombatEnvFactory


def test_cli_parses_ordered_fixed_encounters_and_labeled_agents() -> None:
    args = benchmark.parse_args(
        [
            "--encounter",
            "nibbit",
            "--encounter",
            "slimes",
            "--episodes",
            "12",
            "--seed",
            "31",
            "--agent",
            "ddqn=runs/model=one",
        ]
    )

    assert args.encounter == ["nibbit", "slimes"]
    assert args.episodes == 12
    assert args.seed == 31
    assert args.agent == [benchmark.AgentSpec("ddqn", "runs/model=one")]


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--encounter", "overgrowth_easy"],
        ["--encounter", "simple", "--episodes", "0"],
        ["--encounter", "simple", "--encounter", "simple"],
        ["--encounter", "simple", "--agent", "missing-separator"],
        ["--encounter", "simple", "--agent", "random=checkpoint.json"],
        ["--encounter", "simple", "--agent", "bad label=checkpoint.json"],
        [
            "--encounter",
            "simple",
            "--agent",
            "model=one.json",
            "--agent",
            "model=two.json",
        ],
    ],
)
def test_cli_rejects_invalid_benchmark_shapes(argv) -> None:
    with pytest.raises(SystemExit) as exc_info:
        benchmark.parse_args(argv)

    assert exc_info.value.code == 2


def test_fixed_encounter_seam_prefers_shared_registry(monkeypatch) -> None:
    monkeypatch.setattr(
        benchmark.env_factory_module,
        "SUPPORTED_FIXED_ENCOUNTERS",
        ("simple", "future_enemy"),
        raising=False,
    )

    assert benchmark.supported_fixed_encounters() == ("simple", "future_enemy")


def test_labeled_q_learning_checkpoint_runs_and_records_provenance(tmp_path) -> None:
    checkpoint_path = tmp_path / "tabular.json"
    save_agent(QLearningAgent(action_space_size=11, epsilon=0.0), checkpoint_path)
    args = benchmark.parse_args(
        [
            "--encounter",
            "simple",
            "--episodes",
            "1",
            "--seed",
            "5",
            "--enemy-hp",
            "6",
            "--agent",
            f"tabular={checkpoint_path}",
        ]
    )

    report = benchmark.run_benchmark_command(args)

    assert [policy.label for policy in report.policies] == [
        "random",
        "heuristic",
        "tabular",
    ]
    assert report.policies[-1].policy_type == "q_learning"
    assert report.policies[-1].agent_path == str(checkpoint_path)
    assert len(report.results) == 3


def test_incompatible_checkpoint_fails_before_any_evaluation(
    tmp_path, monkeypatch
) -> None:
    checkpoint_path = tmp_path / "wrong-layout.json"
    save_agent(QLearningAgent(action_space_size=31), checkpoint_path)
    args = benchmark.parse_args(
        [
            "--encounter",
            "simple",
            "--episodes",
            "1",
            "--agent",
            f"wrong={checkpoint_path}",
        ]
    )
    calls = 0

    def fail_if_called(**_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("evaluation should not start")

    monkeypatch.setattr(benchmark_module, "evaluate_policy", fail_if_called)
    with pytest.raises(ValueError, match="action_space_size"):
        benchmark.run_benchmark_command(args)

    assert calls == 0


def test_main_does_not_create_partial_json_for_incompatible_checkpoint(
    tmp_path,
) -> None:
    checkpoint_path = tmp_path / "wrong-layout.json"
    output_path = tmp_path / "reports" / "benchmark.json"
    save_agent(QLearningAgent(action_space_size=31), checkpoint_path)

    with pytest.raises(SystemExit, match="Incompatible checkpoint"):
        benchmark.main(
            [
                "--encounter",
                "simple",
                "--episodes",
                "1",
                "--agent",
                f"wrong={checkpoint_path}",
                "--json-out",
                str(output_path),
            ]
        )

    assert not output_path.exists()


def test_main_writes_versioned_json_after_success(tmp_path, capsys) -> None:
    output_path = tmp_path / "reports" / "benchmark.json"
    benchmark.main(
        [
            "--encounter",
            "simple",
            "--episodes",
            "1",
            "--seed",
            "2",
            "--enemy-hp",
            "6",
            "--json-out",
            str(output_path),
        ]
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    output = capsys.readouterr().out

    assert payload["benchmark_format_version"] == 1
    assert payload["config"]["episode_seeds"] == [2]
    assert [policy["label"] for policy in payload["policies"]] == [
        "random",
        "heuristic",
    ]
    assert "Encounter" in output
    assert "Saved benchmark report" in output


def test_shared_enemy_layout_is_checked_during_benchmark_preflight() -> None:
    env_factory = CombatEnvFactory(encounter_set="slimes", record_trajectory=False)
    env = env_factory()
    encoder = env.encoder
    agent = DQNAgent(
        observation_size=env.observation_size,
        action_space_size=env.action_space_size,
        hidden_sizes=(16,),
        architecture="shared_enemy",
        action_feature_size=env.action_feature_size,
        max_enemy_count=encoder.max_enemy_count,
        enemy_feature_start=(
            encoder.scalar_feature_count + encoder.pile_count_feature_count
        ),
        enemy_slot_feature_size=encoder.enemy_slot_feature_count,
        uses_target_feature_index=encoder.action_feature_names.index("uses_target"),
        target_slot_feature_index=encoder.action_feature_names.index(
            "target_slot_fraction"
        ),
        device="cpu",
        seed=0,
    )
    policies = (
        benchmark.ResolvedBenchmarkPolicy(
            metadata=benchmark.BenchmarkPolicyMetadata(
                label="shared",
                source_kind="checkpoint",
                policy_type="dqn",
            ),
            policy=lambda _env, _observation, _mask: 0,
            agent=agent,
        ),
    )
    environments = (("slimes", env_factory),)

    benchmark.validate_agent_compatibility(policies, environments)
    agent.enemy_slot_feature_size = encoder.enemy_slot_feature_count + 1

    with pytest.raises(ValueError, match="enemy_slot_feature_size"):
        benchmark.validate_agent_compatibility(policies, environments)
