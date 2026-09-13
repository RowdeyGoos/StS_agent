"""Native Weak/Vulnerable timing and first targeted/area callers."""

import json
from copy import deepcopy

import pytest

from game.headless.core.actions import EndTurn, PlayCard
from game.headless.core.combat import CombatEngine
from game.headless.monsters.base import Intent
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.powers.status import StatusCollection, WEAK, VULNERABLE, modify_attack_damage_for_statuses
from game.headless.run.engine import RunEngine


def saved(engine):
    return json.loads(json.dumps(engine.snapshot()))


@pytest.mark.parametrize("base,strength,weak,vulnerable,expected", [
    (7, 0, 1, 1, 7), (7, 1, 1, 1, 9), (13, 0, 1, 0, 9),
    (13, 0, 5, 0, 9), (1, 0, 1, 1, 1), (0, 5, 1, 1, 5),
    (7, -10, 1, 1, 0), (7, 0, 0, 1, 10),
])
def test_modifiers_combine_before_rounding(base, strength, weak, vulnerable, expected):
    assert modify_attack_damage_for_statuses(base, {VULNERABLE: vulnerable},
                                            {WEAK: weak}, strength) == expected


@pytest.mark.parametrize("level,stacks", [(0, 1), (1, 2)])
def test_uppercut_damage_precedes_debuffs_then_weak_reduces_next_attack(level, stacks):
    run = RunEngine(card_ids=("uppercut",))
    if level:
        run.upgrade_card("run.card.0")
    combat = run.start_combat()
    run.apply(PlayCard("run.card.0", 0))
    enemy = combat.enemies[0]
    assert enemy.hp == 27  # Its new Vulnerable must not affect Uppercut itself.
    assert enemy.statuses.get(WEAK) == enemy.statuses.get(VULNERABLE) == stacks
    assert enemy.intent.attack_damage == 4  # floor(6 * .75).
    assert combat.player.energy == 1
    assert len(combat.player.deck.discard_pile) == 1
    run.apply(EndTurn())
    assert combat.player.hp == 76
    assert enemy.statuses.get(WEAK) == enemy.statuses.get(VULNERABLE) == stacks - 1
    assert enemy.intent.move_name == "Defend"


@pytest.mark.parametrize("level,stacks", [(0, 3), (1, 5)])
def test_shockwave_hits_every_living_slot_in_native_order_and_exhausts(level, stacks, monkeypatch):
    run = RunEngine(card_ids=("shockwave",))
    if level:
        run.upgrade_card("run.card.0")
    combat = run.start_combat(encounter_factory=lambda rng: [SimpleEnemy() for _ in range(3)])
    combat.enemies[1].hp = 0
    calls = []
    for slot, enemy in enumerate(combat.enemies):
        original = enemy.apply_status
        def record(name, amount, slot=slot, original=original):
            calls.append((slot, name, amount))
            original(name, amount)
        monkeypatch.setattr(enemy, "apply_status", record)
    assert PlayCard("run.card.0") in combat.legal_actions()
    assert PlayCard("run.card.0", 0) not in combat.legal_actions()
    run.apply(PlayCard("run.card.0"))
    assert calls == [(0, WEAK, stacks), (0, VULNERABLE, stacks),
                     (2, WEAK, stacks), (2, VULNERABLE, stacks)]
    assert combat.player.energy == 1
    assert [c.instance_id for c in combat.player.deck.exhaust_pile] == ["run.card.0"]
    run.apply(EndTurn())
    assert combat.player.hp == 72
    for slot in (0, 2):
        assert combat.enemies[slot].statuses.get(WEAK) == stacks - 1
    assert len(run.state.deck) == 1  # Exhaust never removes a master-deck card.


def test_uppercut_lethal_does_not_apply_debuffs_to_dead_target():
    run = RunEngine(card_ids=("uppercut",))
    combat = run.start_combat(encounter_factory=lambda rng: [SimpleEnemy(13), SimpleEnemy()])
    run.apply(PlayCard("run.card.0", 0))
    assert not combat.done
    assert combat.enemies[0].statuses.get(WEAK) == combat.enemies[0].statuses.get(VULNERABLE) == 0


@pytest.mark.parametrize("power", [WEAK, VULNERABLE])
def test_player_duration_skips_once_stacking_does_not_refresh_and_restore_preserves_flag(power):
    combat = CombatEngine(cards_per_turn=0)
    combat.reset()
    combat.player.apply_status(power, 2)
    clone = CombatEngine()
    clone.restore(saved(combat))
    for engine in (combat, clone):
        engine.apply(EndTurn())
        assert engine.player.statuses.get(power) == 2
        assert engine.player.statuses._skip_next_tick == set()
        engine.player.apply_status(power, 1)
        engine.apply(EndTurn())
        assert engine.player.statuses.get(power) == 2  # Reapplication did not reset skip.
        engine.apply(EndTurn())
        assert engine.player.statuses.get(power) == 1
        engine.apply(EndTurn())
        assert engine.player.statuses.get(power) == 0
        engine.player.apply_status(power, 1)
        assert engine.player.statuses._skip_next_tick == {power}
    assert saved(combat) == saved(clone)


def test_player_debuff_from_enemy_survives_application_turn_and_full_player_turn():
    class DebuffEnemy(SimpleEnemy):
        INTENT_CYCLE = (Intent("debuff", 1, "Weaken", status_name=WEAK, status_stacks=1),
                        Intent("attack", 7, "Hit", attack_damage=7, attack_count=1))
    combat = CombatEngine(enemy_factory=DebuffEnemy, cards_per_turn=0)
    combat.reset()
    combat.apply(EndTurn())
    assert combat.player.statuses.get(WEAK) == 1
    assert combat.player.statuses._skip_next_tick == set()
    combat.apply(EndTurn())
    assert combat.player.statuses.get(WEAK) == 0


def test_enemy_multihit_uses_raw_damage_and_combined_modifiers_before_each_hit():
    class MultiHit(SimpleEnemy):
        INTENT_CYCLE = (Intent("attack", 7, "Triple", attack_damage=7, attack_count=3),)
    combat = CombatEngine(enemy_factory=MultiHit, cards_per_turn=0)
    combat.reset()
    combat.enemies[0].apply_status(WEAK, 1)
    combat.player.apply_status(VULNERABLE, 1)
    combat.player.block = 5
    assert combat.enemies[0].intent.attack_damage == 5
    combat.apply(EndTurn())
    # Each actual hit is floor(7 * .75 * 1.5)=7, not floor(5 * 1.5)=7 by accident:
    # use Strength -2 on the second fixture below to expose double rounding.
    assert combat.player.hp == 64  # 21 total minus 5 block.
    other = CombatEngine(enemy_factory=MultiHit, cards_per_turn=0)
    other.reset()
    other.enemies[0].strength = -2
    other.enemies[0].apply_status(WEAK, 1)
    other.player.apply_status(VULNERABLE, 1)
    assert other.enemies[0].intent.attack_damage == 3
    other.apply(EndTurn())
    assert other.player.hp == 65  # floor(5 * .75 * 1.5)=5 per hit, not 4.


def test_non_attack_damage_ignores_weak_vulnerable_strength():
    enemy = SimpleEnemy()
    enemy.apply_status(VULNERABLE, 3)
    attacker = StatusCollection()
    attacker.add(WEAK, 2)
    assert enemy.take_damage(7, is_attack=False, attacker_statuses=attacker, attacker_strength=99) == 7


@pytest.mark.parametrize("flag", [["weak"], ["vulnerable", "vulnerable"], ["shrink"], ["unknown"], "vulnerable"])
def test_invalid_duration_snapshot_rejects_atomically(flag):
    combat = CombatEngine()
    combat.reset()
    combat.player.apply_status(VULNERABLE, 2)
    before = saved(combat)
    invalid = deepcopy(before)
    invalid["player"]["skip_status_tick"] = flag
    with pytest.raises(ValueError):
        combat.restore(invalid)
    assert saved(combat) == before


def test_search_clone_and_key_own_duration_flags():
    from game.analysis.bruteforce import clone_combat_env, _freeze
    from game.simulation.core import CombatEnv
    combat = CombatEnv()
    combat.reset()
    combat.player.apply_status(VULNERABLE, 2)
    clone = clone_combat_env(combat)
    assert _freeze(combat.player.statuses) == _freeze(clone.player.statuses)
    clone.player.statuses.after_enemy_side_turn_end()
    assert clone.player.statuses.get(VULNERABLE) == combat.player.statuses.get(VULNERABLE)
    assert _freeze(combat.player.statuses) != _freeze(clone.player.statuses)
    assert combat.player.statuses._skip_next_tick == {VULNERABLE}


def test_player_power_ticks_once_after_all_enemies_not_after_each_enemy():
    combat = CombatEngine(encounter_factory=lambda rng: [SimpleEnemy(), SimpleEnemy()], cards_per_turn=0)
    combat.reset()
    combat.player.apply_status(VULNERABLE, 2)
    combat.apply(EndTurn())
    assert combat.player.hp == 62  # Both attacks use Vulnerable.
    assert combat.player.statuses.get(VULNERABLE) == 2  # One skipped side tick.
    combat.apply(EndTurn())
    assert combat.player.statuses.get(VULNERABLE) == 1  # One tick, despite two enemies.


def test_shockwave_belongs_only_to_supported_colorless_content_pools():
    from game.headless.cards.colorless import DEFINITIONS as colorless
    from game.headless.cards.ironclad import DEFINITIONS as ironclad
    from game.headless.events.transformation import TRANSFORM_POOL, COLORLESS_POOL, replacement_pool
    from game.headless.run.config import RunConfig
    from game.headless.shops.catalog import SLOTS
    assert 'shockwave' in {c.definition_id for c in colorless}
    assert 'shockwave' not in {c.definition_id for c in ironclad}
    assert 'shockwave' not in RunConfig().reward_cards
    assert 'shockwave' not in TRANSFORM_POOL
    assert 'shockwave' in COLORLESS_POOL
    assert replacement_pool('shockwave', TRANSFORM_POOL) == COLORLESS_POOL
    assert all(name != 'shockwave' for slot in SLOTS for name, _ in slot.items)
