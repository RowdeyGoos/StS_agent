"""Ironclad card mechanics and sequencing-deck coverage."""

from __future__ import annotations

from collections import Counter

import game
from game.agents.baselines import choose_heuristic_action
from game.simulation.action_features import summarize_action
from game.simulation.card import (
    BashCard,
    BodySlamCard,
    Card,
    DefendCard,
    IronWaveCard,
    PommelStrikeCard,
    ShrugItOffCard,
    StrikeCard,
    create_ironclad_sequencing_deck,
    create_starter_deck,
    get_card_spec,
)
from game.simulation.core import CombatEnv
from game.simulation.deck import Deck
from game.simulation.encoding import ObservationEncoder
from game.simulation.enemy import SimpleEnemy
from game.simulation.player import Player
from game.simulation.status import SHRINK, VULNERABLE
from game.simulation.utils import make_rng


def _player_with_hand(*cards: Card) -> Player:
    deck = Deck([], rng=make_rng(0))
    deck.hand = list(cards)
    player = Player(deck=deck)
    player.energy = 3
    return player


def test_new_cards_and_deck_factory_are_public_symbols() -> None:
    assert game.PommelStrikeCard is PommelStrikeCard
    assert game.ShrugItOffCard is ShrugItOffCard
    assert game.IronWaveCard is IronWaveCard
    assert game.BodySlamCard is BodySlamCard
    assert game.create_ironclad_sequencing_deck is create_ironclad_sequencing_deck


def test_pommel_strike_deals_damage_then_draws_without_redrawing_itself() -> None:
    player = _player_with_hand(PommelStrikeCard())
    player.deck.draw_pile = [StrikeCard()]
    enemy = SimpleEnemy(max_hp=20)

    player.play_card(0, enemy)

    assert enemy.hp == 11
    assert [card.name for card in player.hand] == ["Strike"]
    assert [card.name for card in player.deck.discard_pile] == ["Pommel Strike"]
    assert player.energy == 2


def test_shrug_it_off_gains_block_and_draws_from_a_reshuffle() -> None:
    player = _player_with_hand(ShrugItOffCard())
    player.deck.discard_pile = [DefendCard()]
    enemy = SimpleEnemy()

    player.play_card(0, enemy)

    assert player.block == 8
    assert [card.name for card in player.hand] == ["Defend"]
    assert [card.name for card in player.deck.discard_pile] == ["Shrug It Off"]


def test_draw_card_does_not_draw_itself_when_other_piles_are_empty() -> None:
    player = _player_with_hand(PommelStrikeCard())

    player.play_card(0, SimpleEnemy())

    assert player.hand == []
    assert [card.name for card in player.deck.discard_pile] == ["Pommel Strike"]


def test_iron_wave_gains_block_before_dealing_damage() -> None:
    player = _player_with_hand(IronWaveCard())
    enemy = SimpleEnemy(max_hp=20)
    original_take_damage = enemy.take_damage
    block_when_damage_was_dealt: list[int] = []

    def record_block(amount: int, **kwargs: object) -> int:
        block_when_damage_was_dealt.append(player.block)
        return original_take_damage(amount, **kwargs)  # type: ignore[arg-type]

    enemy.take_damage = record_block  # type: ignore[method-assign]
    player.play_card(0, enemy)

    assert block_when_damage_was_dealt == [5]
    assert player.block == 5
    assert enemy.hp == 15


def test_body_slam_uses_current_block_without_consuming_it() -> None:
    player = _player_with_hand(BodySlamCard())
    player.block = 7
    enemy = SimpleEnemy(max_hp=20)

    player.play_card(0, enemy)

    assert enemy.hp == 13
    assert player.block == 7


def test_body_slam_deals_zero_damage_at_zero_block_without_strength() -> None:
    player = _player_with_hand(BodySlamCard())
    enemy = SimpleEnemy(max_hp=20)

    player.play_card(0, enemy)

    assert enemy.hp == 20
    assert player.block == 0


def test_body_slam_uses_block_gained_by_iron_wave_in_the_same_turn() -> None:
    player = _player_with_hand(IronWaveCard(), BodySlamCard())
    enemy = SimpleEnemy(max_hp=20)

    player.play_card(0, enemy)
    player.play_card(0, enemy)

    assert player.block == 5
    assert enemy.hp == 10
    assert player.energy == 1


def test_new_attacks_use_strength_shrink_vulnerable_and_enemy_block_rules() -> None:
    attack_cases = (
        (PommelStrikeCard(), 9),
        (IronWaveCard(), 5),
        (BodySlamCard(), 6),
    )
    for card, base_damage in attack_cases:
        player = _player_with_hand(card)
        player.strength = 2
        player.statuses.add(SHRINK, 1)
        if isinstance(card, BodySlamCard):
            player.block = base_damage
        enemy = SimpleEnemy(max_hp=30)
        enemy.block = 2
        enemy.apply_status(VULNERABLE, 1)

        player.play_card(0, enemy)

        expected_attack_damage = (((base_damage + 2) * 7) // 10 * 3) // 2
        assert enemy.hp == 30 - max(0, expected_attack_damage - 2)


def test_card_specs_capture_draw_mixed_effect_and_dynamic_damage_semantics() -> None:
    pommel = get_card_spec("Pommel Strike")
    shrug = get_card_spec("Shrug It Off")
    iron_wave = get_card_spec("Iron Wave")
    body_slam = get_card_spec("Body Slam")

    assert (pommel.cost, pommel.kind, pommel.base_damage, pommel.draw_count) == (
        1,
        "attack",
        9,
        1,
    )
    assert (shrug.cost, shrug.kind, shrug.block_gain, shrug.draw_count) == (
        1,
        "block",
        8,
        1,
    )
    assert shrug.uses_target is False
    assert (iron_wave.base_damage, iron_wave.block_gain) == (5, 5)
    assert body_slam.damage_equals_player_block is True
    assert body_slam.is_dead_card is False


def test_sequencing_deck_has_exact_fresh_contents_and_starter_is_unchanged() -> None:
    first = create_ironclad_sequencing_deck()
    second = create_ironclad_sequencing_deck()

    assert Counter(card.name for card in first) == Counter(
        {
            "Strike": 2,
            "Defend": 3,
            "Bash": 1,
            "Pommel Strike": 1,
            "Shrug It Off": 1,
            "Iron Wave": 1,
            "Body Slam": 1,
        }
    )
    assert [card.name for card in first] == [
        "Strike",
        "Strike",
        "Defend",
        "Defend",
        "Defend",
        "Bash",
        "Pommel Strike",
        "Shrug It Off",
        "Iron Wave",
        "Body Slam",
    ]
    assert len(first) == 10
    assert all(
        first_card is not second_card
        for first_card, second_card in zip(first, second)
    )
    assert Counter(card.name for card in create_starter_deck()) == Counter(
        {"Strike": 5, "Defend": 4, "Bash": 1}
    )


def test_shrug_it_off_has_one_canonical_action_against_multiple_enemies() -> None:
    env = CombatEnv(
        deck_factory=lambda: [ShrugItOffCard()],
        encounter_factory=lambda _rng: [SimpleEnemy(), SimpleEnemy()],
        cards_per_turn=1,
        max_enemy_count=3,
    )
    env.reset(seed=0)

    assert env.get_legal_actions() == [("end_turn",), ("play", 0, 0)]


def test_new_card_observation_and_action_features_are_encoded() -> None:
    env = CombatEnv(
        deck_factory=create_ironclad_sequencing_deck,
        cards_per_turn=10,
    )
    observation = env.reset(seed=7)
    observation_features = dict(
        zip(env.encoder.feature_names, env.encode_observation(observation), strict=True)
    )
    action_features = env.encode_action_features(observation)
    pommel_index = observation["hand"].index("Pommel Strike")
    pommel_features = dict(
        zip(
            env.encoder.action_feature_names,
            action_features[env.encode_action(("play", pommel_index))],
            strict=True,
        )
    )

    assert observation_features[
        f"hand_slot_{pommel_index}_is_pommel_strike"
    ] == 1.0
    assert pommel_features["card_is_pommel_strike"] == 1.0
    assert pommel_features["cards_drawn_fraction"] == 0.0


def test_action_summaries_cover_draw_mixed_effects_and_body_slam_state() -> None:
    env = CombatEnv(
        deck_factory=lambda: [
            PommelStrikeCard(),
            ShrugItOffCard(),
            IronWaveCard(),
            BodySlamCard(),
            StrikeCard(),
        ],
        cards_per_turn=4,
    )
    env.reset(seed=0)
    assert env.player is not None
    env.player.deck.hand = [
        PommelStrikeCard(),
        ShrugItOffCard(),
        IronWaveCard(),
        BodySlamCard(),
    ]
    env.player.deck.draw_pile = [StrikeCard()]
    env.player.deck.discard_pile = []
    env.player.block = 0
    observation = env.get_observation()

    pommel = summarize_action(observation, ("play", 0))
    shrug = summarize_action(observation, ("play", 1))
    iron_wave = summarize_action(observation, ("play", 2))
    zero_body_slam = summarize_action(observation, ("play", 3))
    action_features = env.encode_action_features(observation)
    pommel_action_features = dict(
        zip(
            env.encoder.action_feature_names,
            action_features[env.encode_action(("play", 0))],
            strict=True,
        )
    )

    assert (pommel.damage_to_target, pommel.cards_drawn) == (9, 1)
    assert (shrug.block_gain, shrug.cards_drawn, shrug.target_index) == (8, 1, None)
    assert (iron_wave.damage_to_target, iron_wave.block_gain) == (5, 5)
    assert zero_body_slam.damage_to_target == 0
    assert zero_body_slam.is_dead_card is True
    assert pommel_action_features["cards_drawn_fraction"] == 0.1

    observation["player"]["block"] = 7
    body_slam = summarize_action(observation, ("play", 3))
    assert body_slam.damage_to_target == 7
    assert body_slam.is_dead_card is False


def test_card_schema_expands_without_changing_action_space() -> None:
    legacy_encoder = ObservationEncoder(
        card_name_to_id={
            "<PAD>": 0,
            "Strike": 1,
            "Defend": 2,
            "Bash": 3,
            "Slimed": 4,
        }
    )
    expanded_encoder = ObservationEncoder()

    assert expanded_encoder.vector_size - legacy_encoder.vector_size == 56
    assert expanded_encoder.action_feature_count - legacy_encoder.action_feature_count == 4
    assert "cards_drawn_fraction" in expanded_encoder.action_feature_names
    assert expanded_encoder.action_space_size == legacy_encoder.action_space_size == 11


def test_heuristic_uses_body_slam_lethal_and_avoids_it_at_zero_block() -> None:
    env = CombatEnv(
        deck_factory=lambda: [BodySlamCard(), StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=7),
        cards_per_turn=2,
    )
    observation = env.reset(seed=0)
    assert env.player is not None
    env.player.block = 7
    observation = env.get_observation()

    lethal_action = env.decode_action(
        choose_heuristic_action(env, observation, env.get_action_mask())
    )
    assert observation["hand"][lethal_action[1]] == "Body Slam"

    env.player.block = 0
    observation = env.get_observation()
    productive_action = env.decode_action(
        choose_heuristic_action(env, observation, env.get_action_mask())
    )
    assert observation["hand"][productive_action[1]] == "Strike"


def test_new_game_catalog_content_does_not_expand_legacy_card_vocabulary():
    """A game-only card must not invalidate the frozen research representation."""
    import subprocess
    import sys

    result = subprocess.run([sys.executable, "-c", '''
from game.headless.cards import ironclad
from game.headless.cards.base import CardDefinition, CardSpec
ironclad.DEFINITIONS += (CardDefinition("new", (CardSpec("New card", 1, "skill"),), ()),)
from game.headless.cards.catalog import DEFAULT_CARDS
assert DEFAULT_CARDS.create("new").name == "New card"
from game.simulation.card import CARD_SPECS
from game.simulation import card_records
assert tuple(CARD_SPECS) == ("Strike", "Defend", "Bash", "Pommel Strike", "Shrug It Off", "Iron Wave", "Body Slam", "Slimed")
'''], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
