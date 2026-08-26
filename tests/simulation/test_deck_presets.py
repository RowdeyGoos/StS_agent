"""Named deck registry and environment-selection coverage."""

from __future__ import annotations

from collections import Counter
import pickle

import pytest

import game
from game.simulation.card import create_starter_deck
from game.simulation.core import CombatEnv
from game.simulation.deck_presets import SUPPORTED_DECKS, resolve_deck_factory
from game.simulation.enemy import SimpleEnemy
from game.simulation.env_factory import CombatEnvFactory


def _all_deck_card_names(env: CombatEnv) -> list[str]:
    assert env.player is not None
    deck = env.player.deck
    return [
        card.name
        for pile in (
            deck.hand,
            deck.draw_pile,
            deck.discard_pile,
            deck.exhaust_pile,
        )
        for card in pile
    ]


def test_named_deck_registry_is_public_fresh_and_pickle_friendly() -> None:
    assert SUPPORTED_DECKS == ("starter", "ironclad_sequencing")
    assert game.SUPPORTED_DECKS is SUPPORTED_DECKS
    assert game.resolve_deck_factory is resolve_deck_factory

    for deck_name in SUPPORTED_DECKS:
        factory = resolve_deck_factory(deck_name)
        restored_factory = pickle.loads(pickle.dumps(factory))
        first = factory()
        second = restored_factory()

        assert [card.name for card in first] == [card.name for card in second]
        assert all(left is not right for left, right in zip(first, second))


def test_named_deck_registry_rejects_unknown_names_early() -> None:
    with pytest.raises(ValueError, match="Unsupported deck"):
        resolve_deck_factory("unknown")

    with pytest.raises(ValueError, match="Unsupported deck"):
        CombatEnvFactory(deck="unknown")


def test_explicit_starter_factory_preserves_seeded_simple_combat() -> None:
    selected_env = CombatEnvFactory(
        encounter_set="simple",
        deck="starter",
        enemy_hp=40,
        player_hp=73,
        cards_per_turn=4,
        hp_loss_penalty_scale=1.25,
        incoming_damage_shaping_scale=0.4,
        record_trajectory=False,
    )()
    legacy_env = CombatEnv(
        deck_factory=create_starter_deck,
        enemy_factory=lambda: SimpleEnemy(max_hp=40),
        player_max_hp=73,
        cards_per_turn=4,
        hp_loss_penalty_scale=1.25,
        incoming_damage_shaping_scale=0.4,
        record_trajectory=False,
    )

    selected_observation = selected_env.reset(seed=19)
    legacy_observation = legacy_env.reset(seed=19)

    assert selected_observation == legacy_observation
    assert selected_env.get_action_mask() == legacy_env.get_action_mask()
    assert selected_env.rng.getstate() == legacy_env.rng.getstate()


def test_named_decks_share_schemas_and_select_expected_contents() -> None:
    environments = {
        deck_name: CombatEnvFactory(encounter_set="simple", deck=deck_name)()
        for deck_name in SUPPORTED_DECKS
    }
    for env in environments.values():
        env.reset(seed=7)

    starter_env = environments["starter"]
    sequencing_env = environments["ironclad_sequencing"]
    assert (
        starter_env.observation_size,
        starter_env.action_space_size,
        starter_env.action_feature_size,
    ) == (
        sequencing_env.observation_size,
        sequencing_env.action_space_size,
        sequencing_env.action_feature_size,
    ) == (169, 11, 48)
    assert Counter(_all_deck_card_names(starter_env)) == Counter(
        {"Strike": 5, "Defend": 4, "Bash": 1}
    )
    assert Counter(_all_deck_card_names(sequencing_env)) == Counter(
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

    multi_enemy_environments = [
        CombatEnvFactory(encounter_set="overgrowth_easy", deck=deck_name)()
        for deck_name in SUPPORTED_DECKS
    ]
    assert {
        (
            env.observation_size,
            env.action_space_size,
            env.action_feature_size,
        )
        for env in multi_enemy_environments
    } == {(257, 31, 48)}


def test_combat_env_factory_with_named_deck_is_pickle_friendly() -> None:
    factory = CombatEnvFactory(
        encounter_set="overgrowth_easy",
        deck="ironclad_sequencing",
    )
    restored = pickle.loads(pickle.dumps(factory))

    expected = factory().reset(seed=23)
    actual = restored().reset(seed=23)

    assert actual == expected
