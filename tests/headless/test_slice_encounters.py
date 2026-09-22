"""Source-anchored A0 HP, move-cycle, composition and continuation cases."""

import json
from copy import deepcopy
from random import Random

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import EndTurn, PlayCard
from game.headless.core.combat import CombatEngine
from game.headless.core.deck import Deck
from game.headless.core.player import Player
from game.headless.encounters.overgrowth import build_overgrowth_slimes_encounter
from game.headless.monsters.overgrowth import (
    Nibbit, LeafSlimeSmall, LeafSlimeMedium, TwigSlimeSmall, TwigSlimeMedium, SimpleEnemy,
)


def snapshot(combat):
    return json.loads(json.dumps(combat.snapshot()))


def durable_player():
    return Player(Deck([], Random(0)), max_hp=1000)


class MoveRolls:
    """Synthetic boundary rolls, independent of Python/native RNG algorithms."""
    def __init__(self, values):
        self.values = iter(values)
        self.calls = 0

    def randint(self, lower, upper):
        return lower

    def random(self):
        self.calls += 1
        return next(self.values)


@pytest.mark.parametrize("kind,low,high", [
    (Nibbit, 42, 46), (LeafSlimeSmall, 11, 15), (LeafSlimeMedium, 32, 35),
    (TwigSlimeSmall, 7, 11), (TwigSlimeMedium, 26, 28),
])
def test_verified_a0_hp_ranges(kind, low, high):
    values = {kind(Random(seed)).hp for seed in range(100)}
    assert values == set(range(low, high + 1))


def test_solo_nibbit_full_cycles_attack_block_strength_and_vulnerable():
    enemy, player = Nibbit(Random(0)), durable_player()
    initial_rng = enemy.rng.getstate()
    moves = []
    for expected_damage, expected_block, expected_strength in [
        (12, 0, 0), (6, 5, 0), (0, 0, 2),
        (14, 0, 2), (8, 5, 2), (0, 0, 4),
        (16, 0, 4), (10, 5, 4), (0, 0, 6),
    ]:
        enemy.start_turn()
        hp = player.hp
        move = enemy.execute_intent(player)
        moves.append(move.move_name)
        assert hp - player.hp == expected_damage
        assert (enemy.block, enemy.strength) == (expected_block, expected_strength)
    assert moves == ["Butt", "Hesitant Slice", "Hiss"] * 3
    assert enemy.rng.getstate() == initial_rng
    enemy.apply_status("vulnerable", 2)
    enemy.take_damage(7, attacker_strength=2)
    assert enemy.hp == enemy.max_hp - 13  # floor((7 + 2) * 1.5)
    enemy.execute_intent(player)
    assert enemy.statuses.get("vulnerable") == 1
    enemy.execute_intent(player)
    assert enemy.statuses.get("vulnerable") == 0


@pytest.mark.parametrize("opening,expected", [(0.4999, "Tackle"), (0.5, "Goop")])
def test_small_leaf_has_equal_opening_and_cannot_repeat(opening, expected):
    rng = MoveRolls([opening, 0, 0.99, 0.5, 0.1])
    enemy, player = LeafSlimeSmall(rng), durable_player()
    moves = []
    for _ in range(4):
        moves.append(enemy.intent.move_name)
        enemy.execute_intent(player)
    other = "Goop" if expected == "Tackle" else "Tackle"
    assert moves == [expected, other, expected, other]
    assert rng.calls == 5  # Opening plus every random-branch transition.
    assert player.hp == 994
    assert len(player.deck.discard_pile) == 2
    assert all(c.definition.definition_id == "slimed" for c in player.deck.discard_pile)


def test_medium_leaf_alternates_two_slimed_with_eight_damage():
    enemy, player = LeafSlimeMedium(Random(0)), durable_player()
    moves = [enemy.execute_intent(player).move_name for _ in range(6)]
    assert moves == ["Sticky Shot", "Clump Shot"] * 3
    assert player.hp == 976
    cards = player.deck.discard_pile
    assert len(cards) == 6 and len({c.instance_id for c in cards}) == 6
    assert all(c.spec.draw_count == 1 and c.exhausts for c in cards)


def test_small_twig_always_tackles_for_four():
    enemy, player = TwigSlimeSmall(Random(0)), durable_player()
    assert [enemy.execute_intent(player).attack_damage for _ in range(5)] == [4] * 5
    assert player.hp == 980 and not player.deck.discard_pile


def test_medium_twig_equal_branch_max_two_attacks_and_no_repeated_sticky():
    rng = MoveRolls([0.99, 0.4999, 0, 0.1, 0.5])
    enemy, player = TwigSlimeMedium(rng), durable_player()
    moves, phases = [], []
    for _ in range(5):
        moves.append(enemy.intent.move_name)
        phases.append(enemy.behavior_state["phase_index"])
        if enemy._consecutive_attacks == 2:
            assert enemy.behavior_state["possible_next_move_names"] == ["Sticky Shot"]
        enemy.execute_intent(player)
    assert moves == ["Sticky Shot", "Chomp", "Chomp", "Sticky Shot", "Chomp"]
    assert phases == [0, 1, 2, 0, 1]
    assert enemy.intent.move_name == "Sticky Shot"
    assert player.hp == 967 and len(player.deck.discard_pile) == 2
    assert rng.calls == 5


def test_slime_composition_and_native_slot_order_across_authored_seeds():
    seen = set()
    for seed in range(64):
        enemies = build_overgrowth_slimes_encounter(Random(seed))
        assert type(enemies[1]) in (LeafSlimeMedium, TwigSlimeMedium)
        assert {type(enemies[0]), type(enemies[2])} == {LeafSlimeSmall, TwigSlimeSmall}
        seen.add(tuple(type(e) for e in enemies))
    assert len(seen) == 4


@pytest.mark.parametrize("kind", [Nibbit, LeafSlimeSmall, LeafSlimeMedium, TwigSlimeSmall, TwigSlimeMedium])
def test_each_enemy_full_cycle_restores_every_boundary_without_state_or_rng_alias_leaks(kind):
    combat = CombatEngine(seed=9, deck_factory=lambda: [], encounter_factory=lambda rng: [kind(rng)], player_max_hp=1000)
    combat.reset()
    for _ in range(12):
        restored = CombatEngine()
        restored.restore(snapshot(combat))
        assert restored.player.combat_enemies is restored.enemies
        assert restored.enemies is not combat.enemies
        before = snapshot(combat)
        combat.legal_actions()
        combat.enemies[0].to_observation()
        assert snapshot(combat) == before
        assert combat.apply(EndTurn()) == restored.apply(EndTurn())
        assert snapshot(combat) == snapshot(restored)


@pytest.mark.parametrize("invalid_count", [-1, 0, 3])
def test_invalid_twig_repeat_counter_restore_is_atomic(invalid_count):
    combat = CombatEngine(seed=0, deck_factory=lambda: [], encounter_factory=lambda rng: [TwigSlimeMedium(rng)])
    combat.reset()
    combat.apply(EndTurn())
    before = snapshot(combat)
    malformed = deepcopy(before)
    malformed["enemies"][0]["state"]["_consecutive_attacks"] = invalid_count
    with pytest.raises(ValueError, match="Twig Slime"):
        combat.restore(malformed)
    assert snapshot(combat) == before


def test_lethal_nibbit_slice_stops_block_gain_and_later_enemy_actions():
    combat = CombatEngine(seed=0, player_max_hp=1, deck_factory=lambda: [],
                          encounter_factory=lambda rng: [Nibbit(rng), TwigSlimeMedium(rng)])
    combat.reset()
    nibbit = combat.enemies[0]
    nibbit._intent_index = 1  # Synthetic lethal Hesitant Slice boundary.
    second_before = deepcopy(vars(combat.enemies[1]))
    rng_before = combat.rng.getstate()
    result = combat.apply(EndTurn())
    assert result.winner == "enemy"
    assert nibbit.block == 0 and nibbit._intent_index == 1
    assert combat.enemies[1]._current_intent == second_before["_current_intent"]
    assert combat.rng.getstate() == rng_before
    assert not combat.player.deck.discard_pile


def test_restore_rebinds_draw_liveness_to_its_own_enemy_graph():
    env = CombatEngine(seed=0, deck_factory=lambda: [DEFAULT_CARDS.create("pommel_strike"), DEFAULT_CARDS.create("strike")],
                    enemy_factory=lambda: SimpleEnemy(max_hp=9), cards_per_turn=2)
    env.reset()
    cloned = CombatEngine()
    cloned.restore(snapshot(env))
    assert cloned.player.combat_enemies is cloned.enemies
    assert cloned.player.combat_enemies is not env.enemies
    # Change only the clone's HP to make its Pommel nonlethal, then draw.
    cloned.enemies[0].hp = 20
    for engine in (env, cloned):
        player = engine.player
        strike = next(c for c in player.hand if c.name == "Strike")
        player.hand.remove(strike)
        player.deck.discard_pile.append(strike)
    card = next(c for c in env.player.hand if c.name == "Pommel Strike")
    env.apply(PlayCard(card.instance_id, 0))
    cloned.apply(PlayCard(card.instance_id, 0))
    assert env.player.hand == []
    assert [c.name for c in cloned.player.hand] == ["Strike"]
