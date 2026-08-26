"""Tests for deterministic fixed-seed benchmark reporting."""

from __future__ import annotations

import json

from game.agents.baselines import QLearningAgent
from game.analysis import benchmark as benchmark_module
from game.analysis.benchmark import (
    BENCHMARK_FORMAT_VERSION,
    BenchmarkEnvironmentConfig,
    BenchmarkPolicyMetadata,
    ResolvedBenchmarkPolicy,
    format_benchmark_table,
    run_fixed_seed_benchmark,
)
from game.analysis.watch import policy_from_agent, policy_from_named_policy
from game.simulation.card import StrikeCard
from game.simulation.core import CombatEnv
from game.simulation.enemy import SimpleEnemy


def _tiny_env_factory(enemy_hp: int = 6):
    return lambda: CombatEnv(
        deck_factory=lambda: [StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=enemy_hp),
        cards_per_turn=1,
        max_hand_size=1,
        record_trajectory=False,
    )


def _built_in_policy(name: str) -> ResolvedBenchmarkPolicy:
    return ResolvedBenchmarkPolicy(
        metadata=BenchmarkPolicyMetadata(
            label=name,
            source_kind="built_in",
            policy_type=name,
        ),
        policy=policy_from_named_policy(name),
    )


def test_benchmark_uses_identical_seed_range_for_every_cell(monkeypatch) -> None:
    calls: list[tuple[int, int]] = []

    class FutureStats:
        def as_dict(self):
            return {
                "episodes": 3,
                "mean_reward": 0.5,
                "win_rate": 0.75,
                "mean_steps": 4.0,
                "mean_player_hp": 60.0,
                "mean_damage_taken": 20.0,
            }

    def fake_evaluate_policy(*, env_factory, policy, episodes, seed):
        del env_factory, policy
        calls.append((episodes, seed))
        return FutureStats()

    monkeypatch.setattr(benchmark_module, "evaluate_policy", fake_evaluate_policy)
    report = run_fixed_seed_benchmark(
        environment_factories=(
            ("first", _tiny_env_factory()),
            ("second", _tiny_env_factory()),
        ),
        policies=(_built_in_policy("random"), _built_in_policy("heuristic")),
        episodes=3,
        base_seed=41,
        environment=BenchmarkEnvironmentConfig(),
    )

    assert calls == [(3, 41)] * 4
    assert report.episode_seeds == (41, 42, 43)
    assert report.results[0].metrics["mean_damage_taken"] == 20.0
    table = format_benchmark_table(report)
    table_heading = table.splitlines()[0]
    assert table_heading.index("Mean HP") < table_heading.index(
        "Mean damage"
    ) < table_heading.index("Mean reward")
    assert "20.00" in table.splitlines()[1]
    assert [
        (result.encounter, result.policy_label) for result in report.results
    ] == [
        ("first", "random"),
        ("first", "heuristic"),
        ("second", "random"),
        ("second", "heuristic"),
    ]


def test_real_built_in_benchmark_is_repeatable() -> None:
    kwargs = {
        "environment_factories": (("tiny", _tiny_env_factory()),),
        "policies": (_built_in_policy("random"), _built_in_policy("heuristic")),
        "episodes": 4,
        "base_seed": 9,
        "environment": BenchmarkEnvironmentConfig(
            enemy_hp=6,
            cards_per_turn=1,
        ),
    }

    first = run_fixed_seed_benchmark(**kwargs)
    second = run_fixed_seed_benchmark(**kwargs)

    assert first.as_dict() == second.as_dict()


def test_saved_agent_tie_breaking_is_encounter_order_independent() -> None:
    template_env = _tiny_env_factory()()
    agent = QLearningAgent(
        action_space_size=template_env.action_space_size,
        epsilon=0.0,
    )
    policy = ResolvedBenchmarkPolicy(
        metadata=BenchmarkPolicyMetadata(
            label="tabular",
            source_kind="checkpoint",
            policy_type="q_learning",
            agent_path="checkpoint.json",
        ),
        policy=policy_from_agent(agent),
        agent=agent,
    )
    environment = BenchmarkEnvironmentConfig(cards_per_turn=1)
    forward = run_fixed_seed_benchmark(
        environment_factories=(
            ("six", _tiny_env_factory(6)),
            ("twelve", _tiny_env_factory(12)),
        ),
        policies=(policy,),
        episodes=4,
        base_seed=17,
        environment=environment,
    )
    reverse = run_fixed_seed_benchmark(
        environment_factories=(
            ("twelve", _tiny_env_factory(12)),
            ("six", _tiny_env_factory(6)),
        ),
        policies=(policy,),
        episodes=4,
        base_seed=17,
        environment=environment,
    )

    forward_metrics = {
        result.encounter: dict(result.metrics) for result in forward.results
    }
    reverse_metrics = {
        result.encounter: dict(result.metrics) for result in reverse.results
    }
    assert forward_metrics == reverse_metrics


def test_report_json_and_table_are_stable(tmp_path) -> None:
    monkey_report = run_fixed_seed_benchmark(
        environment_factories=(("tiny", _tiny_env_factory()),),
        policies=(_built_in_policy("heuristic"),),
        episodes=2,
        base_seed=3,
        environment=BenchmarkEnvironmentConfig(enemy_hp=6, cards_per_turn=1),
        device="cpu",
    )
    output_path = monkey_report.write_json(tmp_path / "nested" / "benchmark.json")
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    table = format_benchmark_table(monkey_report)

    assert payload["benchmark_format_version"] == BENCHMARK_FORMAT_VERSION
    assert payload["config"]["episode_seeds"] == [3, 4]
    assert payload["config"]["device"] == "cpu"
    assert payload["config"]["environment"]["deck"] == "starter"
    assert payload["policies"][0]["source_kind"] == "built_in"
    assert payload["results"][0]["metrics"] == dict(
        monkey_report.results[0].metrics
    )
    assert table.splitlines()[0].startswith("Encounter")
    assert "Mean damage" in table.splitlines()[0]
    assert "0.00" in table.splitlines()[1]
    assert "tiny" in table
    assert "heuristic" in table
