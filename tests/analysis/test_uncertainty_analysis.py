"""Tests for sampled information-aware oracle analysis."""

from __future__ import annotations

from game.cli.brute_force import parse_args
from game.simulation.card import BashCard, DefendCard, SlimedCard, StrikeCard
from game.simulation.core import CombatEnv
from game.simulation.enemy import SimpleEnemy
from game.analysis.uncertainty import (
    analyze_information_aware_decision,
    sample_hidden_combat_states,
)


def test_hidden_state_samples_preserve_observation_and_randomize_draw_order() -> None:
    env = CombatEnv(
        deck_factory=lambda: [
            StrikeCard(),
            DefendCard(),
            BashCard(),
            SlimedCard(),
        ],
        enemy_factory=lambda: SimpleEnemy(max_hp=20),
        cards_per_turn=1,
        record_trajectory=False,
    )
    observation = env.reset(seed=7)

    samples = sample_hidden_combat_states(
        env,
        sample_count=12,
        sampling_seed=99,
    )
    draw_orders = {
        tuple(card.name for card in sample.player.deck.draw_pile)
        for sample in samples
        if sample.player is not None
    }

    assert all(sample.get_observation() == observation for sample in samples)
    assert len(draw_orders) > 1
    assert all(
        sample.player is not None and sample.rng is sample.player.deck.rng
        for sample in samples
    )


def test_information_aware_decision_aggregates_shared_samples() -> None:
    env = CombatEnv(
        deck_factory=lambda: [StrikeCard(), DefendCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=6),
        cards_per_turn=2,
        record_trajectory=False,
    )
    observation = env.reset(seed=0)
    defend_hand_index = observation["hand"].index("Defend")
    strike_hand_index = observation["hand"].index("Strike")
    defend_action_index = env.encode_action(("play", defend_hand_index))
    strike_action_index = env.encode_action(("play", strike_hand_index))

    analysis = analyze_information_aware_decision(
        env,
        defend_action_index,
        sample_count=4,
        sampling_seed=123,
        max_steps=5,
        max_nodes_per_action=1_000,
    )
    payload = analysis.as_dict()

    assert analysis.all_actions_resolved is True
    assert analysis.all_sample_searches_proven is True
    assert analysis.selected_matches_best is False
    assert analysis.best_action_indices == (strike_action_index,)
    assert analysis.decisive_dimension == "mean_actions"
    assert analysis.mean_action_count_regret == 1.0
    assert all(
        evaluation.terminal_sample_count == 4
        for evaluation in analysis.action_evaluations
    )
    assert payload["sample_count"] == 4


def test_information_aware_cli_is_opt_in() -> None:
    default_args = parse_args([])
    enabled_args = parse_args(
        [
            "--information-aware-regret",
            "--information-samples",
            "12",
            "--information-max-nodes-per-action",
            "500",
            "--search-workers",
            "4",
        ]
    )

    assert default_args.information_aware_regret is False
    assert enabled_args.information_aware_regret is True
    assert enabled_args.information_samples == 12
    assert enabled_args.information_max_nodes_per_action == 500
    assert enabled_args.search_workers == 4
