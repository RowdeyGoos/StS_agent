"""Tests for single-episode tracing and agent persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from game.cli import brute_force as brute_force_cli
from game import SUPPORTED_ENCOUNTERS
from game.agents.agent_io import load_agent, save_agent
from game.agents.baselines import QLearningAgent
from game.simulation.card import StrikeCard
from game.simulation.core import CombatEnv
from game.simulation.enemy import SimpleEnemy
from game.analysis.watch import (
    load_episode_trace,
    policy_from_agent,
    save_episode_trace,
    trace_policy_episode,
)
from game.cli import watch_policy


def test_q_learning_agent_can_be_saved_and_loaded() -> None:
    agent = QLearningAgent(
        action_space_size=3,
        learning_rate=0.5,
        discount=0.9,
        epsilon=0.1,
        epsilon_min=0.0,
        epsilon_decay=0.95,
        seed=0,
    )
    agent.q_table[(1, 2, 3)] = [0.0, 1.25, -0.5]

    with TemporaryDirectory() as temp_dir:
        checkpoint_path = Path(temp_dir) / "q_learning_agent.json"
        save_agent(agent, checkpoint_path)
        loaded_agent = load_agent(checkpoint_path)

        assert isinstance(loaded_agent, QLearningAgent)
        assert loaded_agent.action_space_size == 3
        assert loaded_agent.learning_rate == 0.5
        assert loaded_agent.q_table[(1, 2, 3)] == [0.0, 1.25, -0.5]


def test_trace_policy_episode_and_save_log() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=6),
        cards_per_turn=1,
    )
    agent = QLearningAgent(action_space_size=env.action_space_size, epsilon=0.0, seed=0)
    state = agent.encode_state(env, env.reset(seed=0))
    agent.q_table[state] = [0.0] * env.action_space_size
    agent.q_table[state][1] = 2.0

    trace = trace_policy_episode(
        env=env,
        policy=policy_from_agent(agent),
        policy_name="q_learning",
        seed=0,
        traced_agent=agent,
        encounter="simple",
        deck="ironclad_sequencing",
    )

    assert trace.summary["winner"] == "player"
    assert len(trace.steps) == 1
    assert trace.steps[0].action == ("play", 0)
    assert trace.steps[0].selected_action_score == 2.0
    assert trace.steps[0].action_mask[1] == 1
    assert trace.steps[0].legal_actions == (("end_turn",), ("play", 0))

    with TemporaryDirectory() as temp_dir:
        log_path = Path(temp_dir) / "trace.json"
        save_episode_trace(trace, log_path)
        payload = json.loads(log_path.read_text(encoding="utf-8"))
        loaded_trace = load_episode_trace(log_path)

        assert payload["policy_name"] == "q_learning"
        assert payload["encounter"] == "simple"
        assert payload["deck"] == "ironclad_sequencing"
        assert payload["summary"]["winner"] == "player"
        assert payload["steps"][0]["action"] == ["play", 0]
        assert payload["steps"][0]["legal_actions"] == [["end_turn"], ["play", 0]]
        assert loaded_trace.steps[0].legal_actions == (("end_turn",), ("play", 0))
        assert loaded_trace.encounter == "simple"
        assert loaded_trace.deck == "ironclad_sequencing"


def test_legacy_trace_without_deck_loads_as_unknown(tmp_path) -> None:
    trace_path = tmp_path / "legacy.json"
    trace_path.write_text(
        json.dumps(
            {
                "policy_name": "heuristic",
                "seed": 7,
                "encounter": "simple",
                "initial_observation": {},
                "steps": [],
                "summary": {},
            }
        ),
        encoding="utf-8",
    )

    assert load_episode_trace(trace_path).deck is None


def test_watch_and_brute_force_build_identical_seeded_encounters() -> None:
    for encounter in SUPPORTED_ENCOUNTERS:
        common_args = [
            "--encounter",
            encounter,
            "--deck",
            "ironclad_sequencing",
            "--seed",
            "19",
            "--player-hp",
            "73",
            "--cards-per-turn",
            "4",
            "--hp-loss-penalty-scale",
            "1.25",
            "--incoming-damage-shaping-scale",
            "0.4",
        ]
        brute_args = brute_force_cli.parse_args(common_args)
        watch_args = watch_policy.parse_args(["--policy", "heuristic", *common_args])
        brute_env = brute_force_cli.make_env(brute_args)
        watch_env = watch_policy.make_env(watch_args)

        brute_observation = brute_env.reset(seed=19)
        watch_observation = watch_env.reset(seed=19)

        assert watch_observation == brute_observation
        assert watch_env.get_action_mask() == brute_env.get_action_mask()
        assert watch_env.rng.getstate() == brute_env.rng.getstate()

        for _step_index in range(3):
            brute_transition = brute_env.step_discrete(0)
            watch_transition = watch_env.step_discrete(0)
            assert watch_transition == brute_transition
            if brute_transition[2]:
                break


def test_watch_retains_encounter_set_as_cli_alias() -> None:
    args = watch_policy.parse_args(
        ["--policy", "heuristic", "--encounter-set", "slimes"]
    )

    assert args.encounter == "slimes"


def test_watch_and_oracle_deck_defaults_and_choices_match() -> None:
    watch_default = watch_policy.parse_args(["--policy", "heuristic"])
    oracle_default = brute_force_cli.parse_args([])
    watch_named = watch_policy.parse_args(
        ["--policy", "heuristic", "--deck", "ironclad_sequencing"]
    )
    oracle_named = brute_force_cli.parse_args(
        ["--deck", "ironclad_sequencing"]
    )

    assert watch_default.deck == oracle_default.deck == "starter"
    assert watch_named.deck == oracle_named.deck == "ironclad_sequencing"


def test_oracle_json_records_deck(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / "oracle.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "sts-oracle",
            "--encounter",
            "simple",
            "--deck",
            "ironclad_sequencing",
            "--seed",
            "3",
            "--max-steps",
            "1",
            "--max-nodes",
            "1",
            "--json-out",
            str(output_path),
        ],
    )

    brute_force_cli.main()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["deck"] == "ironclad_sequencing"
