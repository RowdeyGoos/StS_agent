"""One native trace per distinct hook/branch, without seed/ascension products."""
from copy import deepcopy
import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.combat import CombatEngine
from game.headless.core.resolution import drain
from game.headless.monsters.catalog import DEFAULT_MONSTERS
from tests.headless.test_native_item_status import (
    FOCUSED_RECORD, prepare, boundary, expected, apply, saved,
)

ROWS = [r for r in FOCUSED_RECORD['result']['rows'] if r['scenario'].startswith('focused_')]


def setup(row):
    roster = row['scenario'].startswith('focused_roster_')
    possess = row['scenario'].startswith('focused_possess_')
    if possess:
        kind = 'TheLost' if 'strength' in row['scenario'] else 'TheForgotten'
    elif roster:
        kind = 'Ovicopter' if row['scenario'].endswith('ovicopter') else 'LivingShield'
    else:
        kind = row['scenario'].removeprefix('focused_monster_') if row['scenario'].startswith('focused_monster_') else 'Chomper'
    initial = row['before']['player'] if roster else row['before']
    engine, identities = prepare(dict(row, before=initial), monster=DEFAULT_MONSTERS[kind])
    p = engine.player
    p.rules.potions = [None] * 3
    for power in initial['powers']:
        key = power['id'].removesuffix('_POWER').lower()
        if key == 'artifact':
            p.statuses._counts[key] = power['amount']
        else:
            p.rules.powers[key] = power['amount']
            if key == 'tender':
                p.rules.auxiliaries[key] = 0
    if roster:
        from game.headless.monsters.underdocks_summons import append_child
        boss = engine.enemies[0]
        for i, native in enumerate(row['before']['enemies'][1:]):
            kwargs = {'position': i + 1} if kind == 'Ovicopter' else {}
            ally = append_child(DEFAULT_MONSTERS[native['type']], boss, p, **kwargs)
            ally.hp = ally.max_hp = native['hp']
            if kind == 'Ovicopter':
                ally._intent_index = 1
        engine.enemies[-1].statuses.add('doom', 1000)
        if kind == 'Ovicopter':
            boss._intent_index = 2
    if possess and not row['scenario'].endswith('_ending'):
        from game.headless.monsters.underdocks_summons import append_child
        append_child(DEFAULT_MONSTERS['Chomper'], engine.enemies[0], p)
    return engine, identities


def move_name(enemy):
    name = enemy.intent.move_name.upper().replace(' ', '_')
    return {'DIZZY': 'STUNNED', 'WAR_CHANT': 'WAR_CHANT', 'UNLOAD_2': 'UNLOAD_MOVE', **{k: k for k in ('DEBILITATING_SMOG', 'EYE_LASERS', 'MIASMA', 'DREAD')}}.get(name, name + '_MOVE')


def enemy_powers(engine, enemy):
    result = {k.upper() + '_POWER': v for k, v in enemy.statuses._counts.items() if v}
    if enemy.strength:
        result['STRENGTH_POWER'] = enemy.strength
    intrinsic = {'Exoskeleton': ('HARD_TO_KILL_POWER', 9), 'BowlbugRock': ('IMBALANCED_POWER', 1), 'LivingShield': ('RAMPART_POWER', 25), 'TheLost': ('POSSESS_STRENGTH_POWER', 1), 'TheForgotten': ('POSSESS_SPEED_POWER', 1)}
    if type(enemy).__name__ in intrinsic:
        key, value = intrinsic[type(enemy).__name__]
        result[key] = value
    if getattr(enemy, 'dexterity', 0):
        result['DEXTERITY_POWER'] = enemy.dexterity
    return result


def state(engine, identities, *, roster=False):
    result = boundary(engine, identities, move=move_name(engine.enemies[0]))
    result['enemy']['powers'] = enemy_powers(engine, engine.enemies[0])
    from game.headless.relics.combat import memory
    for relic, owned in zip(result['relics'], engine.player.rules.relics):
        if relic['id'] == 'RUINED_HELMET':
            relic['state'] = bool(memory(engine.player, owned).get('used'))
    if roster:
        return dict(player=result, enemies=[dict(type=type(e).__name__, hp=e.hp, block=e.block,
            powers=enemy_powers(engine, e) if e.is_alive else None, move=move_name(e)) for e in engine.enemies])
    return result


def native_state(native, *, roster=False):
    if not roster:
        return expected(native)
    result = deepcopy(native)
    result['player'] = expected(result['player'])
    for enemy in result['enemies']:
        # Dead stable slots are tombstones; native removes their powers. This
        # comparison covers living powers and the death/next-intent boundary.
        enemy['powers'] = {p['id']: p['amount'] for p in enemy['powers']} if enemy['hp'] else None
    return result


def execute(engine, identities, step):
    if step['kind'] == 'steal':
        engine.enemies[0]._intent_index = 0
        engine.enemies[0].execute_intent(engine.player, tick_statuses=False)
    elif step['kind'] == 'possess_death':
        enemy = engine.enemies[0]
        enemy.hp = 0
        enemy.on_combat_state_changed(engine.player)
        engine._check_terminal()
    elif step['kind'] == 'block':
        engine.player.block = step['index']
    elif step['kind'] == 'monster_move':
        engine.enemies[0].execute_intent(engine.player, tick_statuses=False)
        drain(engine.player)
    elif step['kind'] == 'end_player':
        engine.player.end_turn()
    else:
        apply(engine, identities, step)


@pytest.mark.parametrize('row', ROWS, ids=lambda r: r['scenario'])
def test_native_focused_behavior_and_restore(row):
    engine, identities = setup(row)
    roster = row['scenario'].startswith('focused_roster_')
    assert state(engine, identities, roster=roster) == native_state(row['before'], roster=roster)
    for step in row['steps']:
        snapshot = saved(engine)
        restored = CombatEngine(cards=DEFAULT_CARDS)
        restored.restore(snapshot)
        assert saved(restored) == snapshot
        execute(engine, identities, step)
        execute(restored, identities, step)
        assert saved(restored) == saved(engine)
        assert state(engine, identities, roster=roster) == native_state(step['state'], roster=roster), step
    restored.restore(saved(engine))
    assert saved(restored) == saved(engine)
    for key, native in (('shuffle', 'shuffle'), ('combat_targets', 'targets'), ('niche', 'niche'), ('monster_ai', 'ai')):
        stream = engine.native_streams[key]
        assert stream.counter == row[native]['counter']
        assert deepcopy(stream).next_double() == row[native]['suffix']


@pytest.mark.parametrize('shield_dies', [False, True], ids=['later-ally-dies', 'actor-dies-to-thorns'])
def test_living_shield_pending_roll_survives_later_selector_and_rejects_corruption(shield_dies):
    from game.headless.core.actions import EndTurn
    from tests.headless.test_glory import clone, saved as run_saved, step, settle
    from game.headless.run.engine import RunEngine
    from game.headless.run.inventory import add_relic

    run = RunEngine(seed=2, max_hp=1000, card_ids=('strike', 'defend'))
    add_relic(run.state, 'centennial_puzzle')
    run.start_combat(encounter_id='glory_turret_operator', cards_per_turn=0)
    p, shield, turret = run.combat.player, *run.combat.enemies
    p.rules.powers['stratagem'] = 1
    if shield_dies:
        shield.hp = 1
        p.rules.powers['thorns'] = 1
    p.block = 6  # Shield is blocked; the later Turret opens the draw selector.
    p.deck.discard_pile.extend(p.deck.draw_pile)
    p.deck.draw_pile.clear()
    if not shield_dies:
        turret.statuses.add('doom', turret.hp)
    step(run, EndTurn())
    assert p.rules.selection and shield.move_roll_pending is (not shield_dies)
    before = run_saved(run)
    bad = deepcopy(before)
    bad['combat']['enemies'][0]['state']['move_roll_pending'] = shield_dies
    with pytest.raises(ValueError, match='move roll'):
        run.restore(bad)
    assert run_saved(run) == before
    settle(run)
    if not shield_dies:
        assert not turret.is_alive and shield.intent.move_name == 'Smash'
    else:
        assert turret.is_alive and not shield.is_alive
    assert not shield.move_roll_pending
    clone(run)


def test_deferred_roster_snapshots_reject_old_schema_and_unowned_roll():
    for row in (r for r in ROWS if r['scenario'].startswith('focused_roster_')):
        engine, _ = setup(row)
        before = saved(engine)
        for bad in (dict(before, schema='headless_combat_state_v43'), deepcopy(before)):
            if bad['schema'] == before['schema']:
                bad['enemies'][0]['state']['move_roll_pending'] = True
            with pytest.raises(ValueError):
                engine.restore(bad)
            assert saved(engine) == before
