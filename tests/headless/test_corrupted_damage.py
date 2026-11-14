"""Enchantment damage multipliers follow the native order and stay integral.

Native `Hook.ModifyDamage` multiplies the card's own damage by its enchantment
(Corrupted 1.5, Instinct 2) before additive hooks such as Strength, Calcify or
relic bonuses, then applies the other multipliers in decimal; HP and block loss
truncate the result once. Expected values are worked out by hand below.
"""
import json

import pytest

from game.headless.core.actions import EndTurn, PlayCard
from game.headless.enchantments.base import enchant
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.snapshots import restore_run


def fight(character, cards, enchanted, *, upgraded=(), relics=()):
    run = RunEngine(seed=11, card_ids=list(cards), config=RunConfig(character=character),
                    rng_profile="native", hp=80, max_hp=80)
    deck = list(run.state.deck)
    for index in upgraded:
        run.upgrade_card(deck[index].instance_id)
    for index, name in enchanted.items():
        enchant(deck[index], name)
    for name in relics:
        run.obtain_relic(name)
    run.start_combat(encounter_id="overgrowth_nibbit")
    enemy = run.combat.enemies[0]
    enemy.max_hp = enemy.hp = 300
    assert {card.instance_id for card in run.combat.player.hand} >= {deck[i].instance_id for i in enchanted}
    return run, deck


def play(run, card):
    enemy = run.combat.enemies[0]
    before = enemy.hp + enemy.block
    run.apply(PlayCard(instance_id=card.instance_id, target_slot=0 if card.spec.uses_target else None))
    return before - enemy.hp - enemy.block


def assert_integral_and_restorable(run):
    p, enemy = run.combat.player, run.combat.enemies[0]
    assert all(type(value) is int for value in (enemy.hp, enemy.block, p.hp, p.block))
    snapshot = run.snapshot()
    restored = restore_run(json.loads(json.dumps(snapshot)))
    assert restored.snapshot() == snapshot
    assert type(restored.combat.enemies[0].hp) is int
    run.apply(EndTurn())
    restored.apply(EndTurn())
    assert restored.snapshot() == run.snapshot()


IRONCLAD = ("strike", "twin_strike", "defend", "defend", "defend")


@pytest.mark.parametrize(
    "strength, weak, vulnerable, expected",
    [
        (0, False, False, 13),   # 9 * 1.5 = 13.5
        (3, False, False, 16),   # 13.5 + 3 = 16.5 (Strength is not multiplied: not 18)
        (-2, False, False, 11),  # 13.5 - 2 = 11.5 (not (9 - 2) * 1.5 = 10)
        (3, False, True, 24),    # 16.5 * 1.5 = 24.75
        (3, True, False, 12),    # 16.5 * 0.75 = 12.375
        (3, True, True, 18),     # 16.5 * 0.75 * 1.5 = 18.5625
    ],
)
def test_ironclad_corrupted_strike_follows_native_order(strength, weak, vulnerable, expected):
    run, deck = fight("ironclad", IRONCLAD, {0: "corrupted"}, upgraded=(0,))
    p, enemy = run.combat.player, run.combat.enemies[0]
    p.strength = strength
    if weak:
        p.statuses.add("weak", 2)
    if vulnerable:
        enemy.statuses.add("vulnerable", 2)
    hp = p.hp
    assert play(run, deck[0]) == expected
    assert p.hp == hp - 2
    assert_integral_and_restorable(run)


def test_ironclad_corrupted_multi_hit_floors_each_hit():
    run, deck = fight("ironclad", IRONCLAD, {1: "corrupted"})
    run.combat.player.strength = 1
    run.combat.enemies[0].statuses.add("vulnerable", 2)
    # Each hit: (5 * 1.5 + 1) * 1.5 = 12.75 -> 12; two hits 24, not floor(25.5).
    assert play(run, deck[1]) == 24
    assert_integral_and_restorable(run)


def test_corrupted_fraction_truncates_once_against_block():
    run, deck = fight("ironclad", IRONCLAD, {0: "corrupted"}, upgraded=(0,))
    enemy = run.combat.enemies[0]
    enemy.block = 5
    # Native removes int(min(5, 13.5)) block and int(8.5) HP.
    assert play(run, deck[0]) == 13
    assert (enemy.block, enemy.hp) == (0, 292)
    assert_integral_and_restorable(run)


def test_instinct_doubles_card_damage_before_strength():
    run, deck = fight("ironclad", IRONCLAD, {0: "instinct"})
    run.combat.player.strength = 3
    assert play(run, deck[0]) == 15  # 6 * 2 + 3, not (6 + 3) * 2
    assert_integral_and_restorable(run)


NECROBINDER = ("strike_necrobinder", "poke", "defend_necrobinder", "defend_necrobinder", "defend_necrobinder")


def test_necrobinder_corrupted_strike_with_strength_and_vulnerable():
    run, deck = fight("necrobinder", NECROBINDER, {0: "corrupted"}, upgraded=(0,))
    run.combat.player.strength = 1
    run.combat.enemies[0].statuses.add("vulnerable", 2)
    assert play(run, deck[0]) == 21  # (13.5 + 1) * 1.5 = 21.75
    assert_integral_and_restorable(run)


def test_necrobinder_corrupted_osty_attack_with_calcify_and_vulnerable():
    run, deck = fight("necrobinder", NECROBINDER, {1: "corrupted"}, upgraded=(1,), relics=("bound_phylactery",))
    p = run.combat.player
    p.rules.powers["calcify"] = 2
    run.combat.enemies[0].statuses.add("vulnerable", 2)
    assert play(run, deck[1]) == 23  # Poke+: (9 * 1.5 + 2) * 1.5 = 23.25
    assert_integral_and_restorable(run)


# Vigor is a native ModifyDamageAdditive hook like Strength, so the enchantment
# does not multiply it. One case per call site that consumes Vigor: the attack
# task (single and multi-hit), random hits through hit(), The Hunt and Knockout Blow.
@pytest.mark.parametrize(
    "character, cards, enchantment, upgraded, vigor, expected",
    [
        ("ironclad", IRONCLAD, "corrupted", (0,), 3, 16),  # Strike+: 13.5 + 3, not (9 + 3) * 1.5 = 18
        ("ironclad", IRONCLAD, "instinct", (), 3, 15),  # Strike: 6 * 2 + 3, not (6 + 3) * 2 = 18
        ("ironclad", ("twin_strike",) + IRONCLAD[2:], "corrupted", (), 3, 20),  # 2 x (7.5 + 3), not 2 x 12
        ("ironclad", ("sword_boomerang",) + IRONCLAD[2:], "corrupted", (), 3, 21),  # 3 x (4.5 + 3), not 3 x 9
        ("silent", ("the_hunt", "strike_silent", "defend_silent", "defend_silent"), "corrupted", (), 4, 19),  # 15 + 4, not 21
        ("regent", ("knockout_blow", "strike_regent", "defend_regent", "defend_regent"), "corrupted", (), 4, 49),  # 45 + 4, not 51
    ],
)
def test_vigor_is_added_after_the_enchantment_multiplier(character, cards, enchantment, upgraded, vigor, expected):
    run, deck = fight(character, cards, {0: enchantment}, upgraded=upgraded)
    p = run.combat.player
    p.rules.powers["vigor"] = vigor
    assert play(run, deck[0]) == expected
    assert "vigor" not in p.rules.powers
    assert_integral_and_restorable(run)


def test_vigor_without_enchantment_is_unchanged():
    run, deck = fight("ironclad", ("twin_strike",) + IRONCLAD[2:], {})
    run.combat.player.rules.powers["vigor"] = 3
    assert play(run, deck[0]) == 16  # 2 x (5 + 3)
    assert_integral_and_restorable(run)
