"""Tests for single-episode tracing and agent persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from game.agent_io import load_agent, save_agent
from game.baselines import QLearningAgent
from game.card import StrikeCard
from game.core import CombatEnv
from game.enemy import SimpleEnemy
from game.watch import (
    load_episode_trace,
    policy_from_agent,
    save_episode_trace,
    trace_policy_episode,
)


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
        assert payload["summary"]["winner"] == "player"
        assert payload["steps"][0]["action"] == ["play", 0]
        assert payload["steps"][0]["legal_actions"] == [["end_turn"], ["play", 0]]
        assert loaded_trace.steps[0].legal_actions == (("end_turn",), ("play", 0))
