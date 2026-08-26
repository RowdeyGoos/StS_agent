"""Tests for the tactical trace analyzer."""

from __future__ import annotations

from game.analysis.trace import analyze_episode_trace
from game.analysis.watch import EpisodeTrace, StepTrace


def _make_enemy_observation(hp: int, attack_damage: int) -> dict[str, object]:
    return {
        "name": "SimpleEnemy",
        "hp": hp,
        "max_hp": 12,
        "block": 0,
        "strength": 0,
        "statuses": {"vulnerable": 0, "shrink": 0},
        "intent": {
            "move_name": "Strike",
            "kind": "attack",
            "value": attack_damage,
            "attack_damage": attack_damage,
            "block_gain": 0,
            "strength_gain": 0,
            "status_name": None,
            "status_stacks": 0,
            "slimed_added": 0,
        },
        "behavior_state": {
            "phase_index": 0,
            "phase_count": 3,
            "possible_next_move_names": ["Defend"],
        },
        "alive": True,
    }


def _make_observation(hand: list[str], enemy_hp: int, attack_damage: int) -> dict[str, object]:
    enemy = _make_enemy_observation(enemy_hp, attack_damage)
    hand_counts = {card_name: hand.count(card_name) for card_name in set(hand)}
    return {
        "turn": 1,
        "player": {
            "hp": 20,
            "max_hp": 20,
            "block": 0,
            "energy": 1,
            "energy_per_turn": 3,
            "strength": 0,
            "statuses": {"vulnerable": 0, "shrink": 0},
        },
        "enemy": enemy,
        "enemies": [enemy],
        "enemy_count": 1,
        "living_enemy_count": 1,
        "hand": hand,
        "draw_pile_size": 0,
        "discard_pile_size": 0,
        "exhaust_pile_size": 0,
        "card_counts": {
            "hand": hand_counts,
            "draw_pile": {},
            "discard_pile": {},
            "exhaust_pile": {},
        },
    }


def test_trace_analyzer_flags_missed_lethal() -> None:
    observation = _make_observation(["Strike", "Defend"], enemy_hp=6, attack_damage=6)
    trace = EpisodeTrace(
        policy_name="test",
        seed=0,
        initial_observation=observation,
        steps=(
            StepTrace(
                step_index=0,
                turn=1,
                action_index=2,
                action=("play", 1),
                reward=0.0,
                done=False,
                observation=observation,
                next_observation=observation,
                info={},
                action_mask=(1, 1, 1),
                legal_actions=(("end_turn",), ("play", 0), ("play", 1)),
            ),
        ),
        summary={"winner": "enemy", "steps": 1, "player_hp": 20, "enemy_hp": 6, "total_reward": 0.0},
    )

    report = analyze_episode_trace(trace)

    assert any(finding.category == "missed_lethal" for finding in report.findings)


def test_trace_analyzer_flags_dead_card_and_missing_block() -> None:
    observation = _make_observation(["Defend", "Slimed"], enemy_hp=9, attack_damage=8)
    trace = EpisodeTrace(
        policy_name="test",
        seed=0,
        initial_observation=observation,
        steps=(
            StepTrace(
                step_index=0,
                turn=1,
                action_index=2,
                action=("play", 1),
                reward=0.0,
                done=False,
                observation=observation,
                next_observation=observation,
                info={},
                action_mask=(1, 1, 1),
                legal_actions=(("end_turn",), ("play", 0), ("play", 1)),
            ),
        ),
        summary={"winner": "enemy", "steps": 1, "player_hp": 20, "enemy_hp": 9, "total_reward": 0.0},
    )

    report = analyze_episode_trace(trace)
    categories = {finding.category for finding in report.findings}

    assert "ignored_damage_prevention" in categories
    assert "wasted_dead_card" in categories
