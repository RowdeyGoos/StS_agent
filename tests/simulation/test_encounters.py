"""Encounter fidelity and enemy-intent regression tests."""

from __future__ import annotations

from collections import Counter
from random import Random

from game.simulation.card import DefendCard
from game.simulation.core import CombatEnv
from game.simulation.deck import Deck
from game.simulation.enemy import (
    Mawler,
    build_overgrowth_hard_v1_encounter,
    build_overgrowth_slimes_encounter,
)
from game.simulation.env_factory import (
    CombatEnvFactory,
    SUPPORTED_ENCOUNTERS,
    SUPPORTED_FIXED_ENCOUNTERS,
    SUPPORTED_TRAINING_ENCOUNTER_SETS,
)
from game.simulation.player import Player
from game.simulation.status import SHRINK, VULNERABLE
from game.simulation.utils import make_rng


class _MawlerBoundaryRandom(Random):
    def __init__(self, seed):
        super().__init__(seed)
        self.rolls = iter((0.9, 0.1, 0.5))

    def random(self):
        return next(self.rolls)


def test_overgrowth_slimes_encounter_has_canonical_composition() -> None:
    for seed in range(64):
        encounter = build_overgrowth_slimes_encounter(make_rng(seed))
        counts = Counter(enemy.name for enemy in encounter)

        assert len(encounter) == 3
        assert encounter[1].name in {"Leaf Slime (M)", "Twig Slime (M)"}
        assert {encounter[0].name, encounter[2].name} == {"Leaf Slime (S)", "Twig Slime (S)"}
        assert counts["Leaf Slime (M)"] + counts["Twig Slime (M)"] == 1
        assert counts["Leaf Slime (S)"] == 1
        assert counts["Twig Slime (S)"] == 1
        assert sum(counts.values()) == 3


def test_overgrowth_slimes_encounter_is_seed_reproducible() -> None:
    first = build_overgrowth_slimes_encounter(make_rng(19))
    second = build_overgrowth_slimes_encounter(make_rng(19))

    assert [enemy.to_observation() for enemy in first] == [
        enemy.to_observation() for enemy in second
    ]


def test_mawler_opens_with_two_hit_claw_and_exposes_future_candidates() -> None:
    mawler = Mawler(make_rng(0))
    observation = mawler.to_observation()

    assert observation["hp"] == observation["max_hp"] == 72
    assert observation["intent"]["move_name"] == "Claw"
    assert observation["intent"]["attack_damage"] == 4
    assert observation["intent"]["attack_count"] == 2
    assert observation["behavior_state"] == {
        "phase_index": 0,
        "phase_count": 5,
        "possible_next_move_names": ["Rip and Tear", "Roar"],
    }


def test_mawler_applies_attack_modifiers_per_hit() -> None:
    player = Player(deck=Deck([], rng=make_rng(0)))
    mawler = Mawler(make_rng(0))
    mawler.apply_status(SHRINK, 1)

    executed = mawler.execute_intent(player)

    assert executed.attack_damage == 2
    assert executed.attack_count == 2
    assert player.hp == 76


def test_mawler_roar_is_single_use_and_moves_do_not_repeat() -> None:
    rng = _MawlerBoundaryRandom(0)
    player = Player(deck=Deck([], rng=make_rng(0)))
    mawler = Mawler(rng)

    mawler.execute_intent(player)
    roar_observation = mawler.to_observation()
    assert roar_observation["intent"]["move_name"] == "Roar"
    # Native branch order is Rip and Tear, Roar, Claw; illegal entries filter out.
    assert roar_observation["behavior_state"]["possible_next_move_names"] == [
        "Rip and Tear",
        "Claw",
    ]

    mawler.execute_intent(player)
    assert player.statuses.get(VULNERABLE) == 3
    after_roar = mawler.to_observation()
    assert after_roar["intent"]["move_name"] == "Rip and Tear"
    assert after_roar["behavior_state"]["possible_next_move_names"] == ["Claw"]

    mawler.execute_intent(player)
    after_rip = mawler.to_observation()
    assert after_rip["intent"]["move_name"] == "Claw"
    assert after_rip["behavior_state"]["possible_next_move_names"] == [
        "Rip and Tear"
    ]


def test_mawler_multi_hit_projection_matches_execution() -> None:
    env = CombatEnv(
        seed=0,
        deck_factory=lambda: [DefendCard()],
        encounter_factory=lambda rng: [Mawler(rng)],
        cards_per_turn=1,
        incoming_damage_shaping_scale=0.5,
    )
    observation = env.reset()
    defend_index = observation["hand"].index("Defend")

    _observation, reward, done, info = env.step(("play", defend_index))

    assert done is False
    assert info["projected_incoming_hp_loss_before"] == 8
    assert info["projected_incoming_hp_loss_after"] == 3
    assert reward == 0.03125

    observation, reward, done, info = env.step(("end_turn",))

    assert done is False
    assert observation["player"]["hp"] == 77
    assert info["player_hp_lost"] == 3
    assert reward == -0.0375


def test_hard_v1_fixed_encounters_and_exported_registries() -> None:
    expected_fixed = {
        "mawler": ["Mawler"],
        "nibbits": ["Nibbit", "Nibbit"],
        "shrinker_fuzzy": ["Shrinker Beetle", "Fuzzy Wurm Crawler"],
    }
    for encounter_name, expected_names in expected_fixed.items():
        env = CombatEnvFactory(encounter_set=encounter_name)()
        observation = env.reset(seed=7)
        assert [enemy["name"] for enemy in observation["enemies"]] == expected_names
        assert env.encoder.max_enemy_count == 3

    assert "overgrowth_hard_v1" in SUPPORTED_TRAINING_ENCOUNTER_SETS
    assert "simple" in SUPPORTED_FIXED_ENCOUNTERS
    assert set(expected_fixed) <= set(SUPPORTED_FIXED_ENCOUNTERS)
    assert set(SUPPORTED_TRAINING_ENCOUNTER_SETS) <= set(SUPPORTED_ENCOUNTERS)
    assert set(SUPPORTED_FIXED_ENCOUNTERS) <= set(SUPPORTED_ENCOUNTERS)
    assert len(SUPPORTED_ENCOUNTERS) == len(set(SUPPORTED_ENCOUNTERS))


def test_overgrowth_hard_v1_samples_only_declared_encounters_reproducibly() -> None:
    expected_compositions = {
        ("Mawler",),
        ("Nibbit", "Nibbit"),
        ("Shrinker Beetle", "Fuzzy Wurm Crawler"),
    }
    sampled_compositions = set()
    for seed in range(64):
        first = build_overgrowth_hard_v1_encounter(make_rng(seed))
        second = build_overgrowth_hard_v1_encounter(make_rng(seed))
        first_observations = [enemy.to_observation() for enemy in first]
        second_observations = [enemy.to_observation() for enemy in second]

        composition = tuple(enemy.name for enemy in first)
        sampled_compositions.add(composition)
        assert composition in expected_compositions
        assert first_observations == second_observations

    assert sampled_compositions == expected_compositions
