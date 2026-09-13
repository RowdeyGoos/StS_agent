"""Trace and oracle coverage for sequencing cards."""

from __future__ import annotations

from game.analysis.bruteforce import (
    _minimum_actions_to_win_lower_bound,
    brute_force_combat,
    clone_combat_env,
)
from game.analysis.trace import analyze_episode_trace
from game.analysis.watch import EpisodeTrace, StepTrace
from game.simulation.card import BodySlamCard, DefendCard, StrikeCard
from game.simulation.core import CombatEnv
from game.simulation.enemy import SimpleEnemy


def test_trace_analyzer_recognizes_body_slam_lethal() -> None:
    env = CombatEnv(
        deck_factory=lambda: [BodySlamCard(), DefendCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=7),
        cards_per_turn=2,
    )
    observation = env.reset(seed=0)
    assert env.player is not None
    env.player.block = 7
    observation = env.get_observation()
    body_index = observation["hand"].index("Body Slam")
    defend_index = observation["hand"].index("Defend")
    legal_actions = tuple(env.get_legal_actions())
    trace = EpisodeTrace(
        policy_name="test",
        seed=0,
        initial_observation=observation,
        steps=(
            StepTrace(
                step_index=0,
                turn=1,
                action_index=env.encode_action(("play", defend_index)),
                action=("play", defend_index),
                reward=0.0,
                done=False,
                observation=observation,
                next_observation=observation,
                info={},
                action_mask=env.get_action_mask(),
                legal_actions=legal_actions,
            ),
        ),
        summary={
            "winner": "enemy",
            "steps": 1,
            "player_hp": 80,
            "enemy_hp": 7,
            "total_reward": 0.0,
        },
    )

    report = analyze_episode_trace(trace)

    missed_lethal = next(
        finding for finding in report.findings if finding.category == "missed_lethal"
    )
    assert missed_lethal.recommended_action == ("play", body_index)


def test_oracle_clone_owns_mutable_card_instances() -> None:
    env = CombatEnv(
        deck_factory=lambda: [BodySlamCard(), StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=7),
        cards_per_turn=2,
    )
    env.reset(seed=0)

    cloned = clone_combat_env(env)

    assert cloned.player is not None
    assert env.player is not None
    assert [type(card) for card in cloned.player.hand] == [
        type(card) for card in env.player.hand
    ]
    assert all(
        cloned_card is not original_card
        and cloned_card.definition is original_card.definition
        and cloned_card.instance_id == original_card.instance_id
        for cloned_card, original_card in zip(cloned.player.hand, env.player.hand)
    )

    cloned_strike = next(card for card in cloned.player.hand if card.name == "Strike")
    original_strike = next(card for card in env.player.hand if card.name == "Strike")
    cloned_strike.upgrade()
    assert original_strike.upgrade_level == 0
    assert cloned_strike.upgrade_level == 1
    cloned.player.deck.discard_card(StrikeCard())
    assert cloned.player.deck._allocated_ids != env.player.deck._allocated_ids


def test_oracle_bound_falls_back_for_dynamic_body_slam_damage() -> None:
    env = CombatEnv(
        deck_factory=lambda: [BodySlamCard(), StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=20),
        cards_per_turn=2,
    )
    env.reset(seed=0)
    assert env.player is not None
    env.player.block = 20
    env.last_observation = env.get_observation()

    assert _minimum_actions_to_win_lower_bound(env) == 1

    result = brute_force_combat(env, max_steps=2, max_nodes=50)
    assert result.found_win is True
    assert result.proven_optimal is True
    assert result.steps[0].action[0] == "play"
    assert result.steps[0].observation["hand"][result.steps[0].action[1]] == "Body Slam"
