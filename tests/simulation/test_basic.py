"""Basic mechanics tests for the minimal combat simulator."""

from __future__ import annotations

from math import isclose

from game.simulation.card import BashCard, DefendCard, StrikeCard
from game.simulation.core import CombatEnv
from game.simulation.deck import Deck
from game.simulation.enemy import SimpleEnemy
from game.simulation.player import Player
from game.simulation.status import VULNERABLE
from game.simulation.utils import make_rng


def test_strike_reduces_hp_correctly() -> None:
    deck = Deck([StrikeCard()], rng=make_rng(0))
    player = Player(deck=deck)
    enemy = SimpleEnemy(max_hp=20)

    player.start_turn(draw_count=1)
    player.play_card(0, enemy)

    assert enemy.hp == 14


def test_defend_grants_block() -> None:
    deck = Deck([DefendCard()], rng=make_rng(0))
    player = Player(deck=deck)
    enemy = SimpleEnemy()

    player.start_turn(draw_count=1)
    player.play_card(0, enemy)

    assert player.block == 5


def test_bash_applies_vulnerable() -> None:
    player = Player(deck=Deck([], rng=make_rng(0)))
    enemy = SimpleEnemy(max_hp=20)

    BashCard().play(player, enemy)

    assert enemy.hp == 12
    assert enemy.statuses.get(VULNERABLE) == 2


def test_vulnerable_increases_attack_damage_and_ticks_down_on_owner_turn_end() -> None:
    player = Player(deck=Deck([], rng=make_rng(0)))
    enemy = SimpleEnemy(max_hp=30)
    enemy.apply_status(VULNERABLE, 2)

    StrikeCard().play(player, enemy)

    assert enemy.hp == 21
    assert enemy.statuses.get(VULNERABLE) == 2

    enemy.execute_intent(player)

    assert enemy.statuses.get(VULNERABLE) == 1


def test_damage_interacts_with_block_correctly() -> None:
    deck = Deck([], rng=make_rng(0))
    player = Player(deck=deck)
    player.gain_block(5)

    damage_taken = player.take_damage(8)

    assert damage_taken == 3
    assert player.block == 0
    assert player.hp == 77


def test_reshuffling_works() -> None:
    deck = Deck([StrikeCard(), DefendCard()], rng=make_rng(123))

    first_draw = deck.draw(2)
    assert len(first_draw) == 2
    assert len(deck.draw_pile) == 0

    deck.discard_hand()
    second_draw = deck.draw(2)

    assert len(second_draw) == 2
    assert len(deck.hand) == 2
    assert len(deck.draw_pile) == 0
    assert len(deck.discard_pile) == 0


def test_combat_terminates_correctly() -> None:
    winning_env = CombatEnv(
        seed=0,
        deck_factory=lambda: [StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=6),
    )
    winning_env.reset()
    observation, reward, done, _ = winning_env.step(("play", 0))

    assert done is True
    assert reward == 1.0
    assert observation["enemy"]["hp"] == 0

    losing_env = CombatEnv(seed=0, player_max_hp=6)
    losing_env.reset()
    observation, reward, done, info = losing_env.step(("end_turn",))

    assert done is True
    assert reward == -2.0
    assert observation["player"]["hp"] == 0
    assert info["enemy_action"]["kind"] == "attack"
    assert info["enemy_action"]["value"] == 6
    assert info["enemy_action"]["attack_damage"] == 6
    assert info["player_hp_lost"] == 6
    assert info["hp_loss_penalty"] == -1.0


def test_losing_hp_yields_negative_reward() -> None:
    env = CombatEnv(seed=0)
    env.reset()

    observation, reward, done, info = env.step(("end_turn",))

    assert done is False
    assert observation["player"]["hp"] == 74
    assert isclose(reward, -0.075)
    assert info["player_hp_lost"] == 6
    assert isclose(info["hp_loss_penalty"], -0.075)


def test_defend_gets_positive_reward_for_reducing_projected_incoming_damage() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [DefendCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=20),
        cards_per_turn=1,
    )
    env.reset()

    observation, reward, done, info = env.step(("play", 0))

    assert done is False
    assert observation["player"]["block"] == 5
    assert isclose(reward, 0.03125)
    assert info["projected_incoming_hp_loss_before"] == 6
    assert info["projected_incoming_hp_loss_after"] == 1
    assert isclose(info["incoming_damage_reduction_bonus"], 0.03125)


def test_player_vulnerable_expires_before_enemy_attacks_if_it_reaches_zero() -> None:
    env = CombatEnv(seed=0)
    env.reset()
    assert env.player is not None

    env.player.apply_status(VULNERABLE, 1)
    observation, reward, done, info = env.step(("end_turn",))

    assert done is False
    assert observation["player"]["statuses"]["vulnerable"] == 0
    assert observation["player"]["hp"] == 74
    assert info["player_hp_lost"] == 6
    assert isclose(reward, -0.075)
    assert info["incoming_damage_reduction_bonus"] == 0.0


def test_training_env_can_skip_trajectory_recording_without_breaking_summary() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=6),
        cards_per_turn=1,
        record_trajectory=False,
    )
    env.reset()
    _observation, reward, done, _info = env.step(("play", 0))
    summary = env.get_episode_summary()

    assert done is True
    assert reward == 1.0
    assert summary.steps == 1
    assert summary.winner == "player"
    assert env.get_episode_history() == ()
