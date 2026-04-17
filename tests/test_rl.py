"""RL-focused tests for encodings, masks, and episode bookkeeping."""

from __future__ import annotations

from game.card import BashCard, DefendCard, StrikeCard
from game.core import CombatEnv
from game.enemy import SimpleEnemy, build_overgrowth_easy_encounter
from game.gym_env import GymCombatEnv
from game.utils import make_rng


def test_fixed_width_observation_encoding() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=12),
        cards_per_turn=1,
    )
    observation = env.reset()
    encoded = env.encode_observation(observation)
    feature_map = dict(zip(env.encoder.feature_names, encoded, strict=True))

    assert len(encoded) == env.observation_size
    assert observation["card_counts"]["hand"] == {"Strike": 1}
    assert feature_map["player_hp_fraction"] == 1.0
    assert feature_map["enemy_0_hp_fraction"] == 1.0
    assert feature_map["hand_size_fraction"] == 0.1
    assert feature_map["hand_count_strike_fraction"] == 1.0
    assert feature_map["draw_pile_count_strike_fraction"] == 0.0
    assert feature_map["hand_slot_0_is_strike"] == 1.0
    assert feature_map["hand_slot_0_is_defend"] == 0.0
    assert feature_map["hand_slot_1_is_strike"] == 0.0
    assert feature_map["player_status_vulnerable_fraction"] == 0.0
    assert feature_map["enemy_0_status_vulnerable_fraction"] == 0.0
    assert feature_map["enemy_0_name_is_simpleenemy"] == 1.0


def test_status_features_are_encoded() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [BashCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=20),
        cards_per_turn=1,
    )
    env.reset()
    assert env.enemy is not None
    env.enemy.apply_status("vulnerable", 2)

    encoded = env.encode_observation()
    feature_map = dict(zip(env.encoder.feature_names, encoded, strict=True))

    assert feature_map["enemy_0_status_vulnerable_fraction"] == 0.4


def test_action_mask_and_discrete_action_roundtrip() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [StrikeCard(), DefendCard(), StrikeCard()],
        cards_per_turn=3,
    )
    env.reset()

    mask = env.get_action_mask()

    assert mask[:4] == (1, 1, 1, 1)
    assert all(value == 0 for value in mask[4:])
    assert env.encode_action(("end_turn",)) == 0
    assert env.encode_action(("play", 2)) == 3
    assert env.decode_action(0) == ("end_turn",)
    assert env.decode_action(3) == ("play", 2)


def test_multi_enemy_targeted_actions_are_encoded() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [StrikeCard()],
        encounter_factory=lambda _rng: [SimpleEnemy(max_hp=6), SimpleEnemy(max_hp=8)],
        cards_per_turn=1,
        max_enemy_count=3,
    )
    env.reset()

    mask = env.get_action_mask()

    assert mask[0] == 1
    assert mask[1] == 1
    assert mask[2] == 1
    assert env.encode_action(("play", 0, 1)) == 2
    assert env.decode_action(2) == ("play", 0, 1)


def test_overgrowth_easy_encounter_builder_uses_supported_pool() -> None:
    encounter = build_overgrowth_easy_encounter(make_rng(0))
    enemy_names = {enemy.name for enemy in encounter}

    assert len(encounter) in {1, 3}
    assert enemy_names <= {
        "Nibbit",
        "Leaf Slime (S)",
        "Leaf Slime (M)",
        "Twig Slime (S)",
        "Twig Slime (M)",
        "Shrinker Beetle",
        "Fuzzy Wurm Crawler",
    }


def test_episode_history_and_summary_are_recorded() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [StrikeCard()],
        enemy_factory=lambda: SimpleEnemy(max_hp=6),
        cards_per_turn=1,
    )
    env.reset()
    observation, reward, done, info = env.step_discrete(1)

    history = env.get_episode_history()
    summary = env.get_episode_summary()

    assert done is True
    assert reward == 1.0
    assert observation["enemy"]["hp"] == 0
    assert len(history) == 1
    assert history[0].action == ("play", 0)
    assert history[0].action_index == 1
    assert summary.total_reward == 1.0
    assert summary.winner == "player"
    assert info["episode_summary"]["winner"] == "player"


def test_gym_wrapper_if_gymnasium_available() -> None:
    try:
        gym_env = GymCombatEnv(
            seed=0,
            deck_factory=lambda: [StrikeCard()],
            enemy_factory=lambda: SimpleEnemy(max_hp=6),
            cards_per_turn=1,
        )
    except ModuleNotFoundError:
        return

    observation, info = gym_env.reset(seed=0)
    next_observation, reward, terminated, truncated, step_info = gym_env.step(1)

    assert observation.shape[0] == gym_env.combat_env.observation_size
    assert info["action_mask"][1] == 1
    assert terminated is True
    assert truncated is False
    assert reward == 1.0
    assert next_observation.shape[0] == gym_env.combat_env.observation_size
    assert step_info["episode"]["winner"] == "player"
