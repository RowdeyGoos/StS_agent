"""Ten concrete native death/cleanup probes, not a parameter cross-product."""
from copy import deepcopy
import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import PlayCard
from game.headless.core.combat import CombatEngine
from game.headless.core.osty import summon
from game.headless.monsters.catalog import DEFAULT_MONSTERS
from game.headless.monsters.underdocks_summons import append_child
from tests.headless.test_native_item_status import CURRENT_RECORD, prepare, expected, saved
from tests.headless.test_native_focused_behavior import state, execute

PREFIXES = ('focused_death_', 'focused_illusion_', 'focused_sicem_')
ROWS = [r for r in CURRENT_RECORD['result']['rows'] if r['scenario'].startswith(PREFIXES)]


def setup(row):
    scenario = row['scenario']
    pet = scenario.startswith('focused_sicem_')
    possession = scenario.startswith('focused_death_')
    kind = ('TheLost' if 'strength' in scenario else 'TheForgotten') if possession else scenario.removesuffix('_ending').rsplit('_', 1)[1]
    initial = row['before']['player'] if pet else row['before']
    cards = ['flatten' if pet else 'strike', 'strike', 'strike'] + ['defend'] * 11
    engine, identities = prepare(dict(row, before=initial), monster=DEFAULT_MONSTERS[kind], card_ids=cards)
    p, enemy = engine.player, engine.enemies[0]
    p.rules.potions = [None] * 3
    engine.done, engine.winner = False, None  # Authored survivor is added below.
    if not scenario.endswith('_ending'):
        ally = append_child(DEFAULT_MONSTERS['Chomper'], enemy, p)
        ally.hp = ally.max_hp = 1000
        ally.statuses._counts.clear()  # Native survivor omits AfterAddedToRoom.
    if possession:
        p.statuses.add('artifact', 1)
    if kind == 'Chomper':
        enemy.statuses.add('artifact', 2)
    if kind in ('EyeWithTeeth', 'Parafright'):
        enemy.statuses.add('illusion', 1)
        enemy.statuses.add('minion', 1)
    if scenario.startswith('focused_illusion_'):
        enemy.strength = 5  # Effective Strength 3 while the temporary loss exists.
        for name, value in [('enfeebling_touch', 2), ('poison', 7), ('doom', 1000), ('weak', 2), ('artifact', 1)]:
            enemy.statuses.add(name, value)
    if pet:
        if kind == 'TestSubject':
            enemy.max_hp = 100
        summon(p, 5)
        enemy.statuses.add('sic_em', 3)
        enemy.hp = 1
        if kind == 'SpinyToad':
            enemy.thorns = 5
    return engine, identities


def boundary(engine, identities, *, pet):
    # Generated Dazed keep their creation-order identity in the native fixture.
    for card in sorted(engine.player.deck.all_cards(), key=lambda c: int(c.instance_id.rsplit('.', 1)[1])):
        if card.instance_id not in identities:
            identities[card.instance_id] = f'card.{len(identities)}'
    result = state(engine, identities)
    enemy = engine.enemies[0]
    powers = result['enemy']['powers']
    effective = enemy.strength - enemy.statuses.get('enfeebling_touch')
    if effective:
        powers['STRENGTH_POWER'] = effective
    else:
        powers.pop('STRENGTH_POWER', None)
    if getattr(enemy, 'thorns', 0):
        powers['THORNS_POWER'] = enemy.thorns
    if type(enemy).__name__ == 'TestSubject':
        powers['ADAPTABLE_POWER'] = 1
        if enemy.is_alive:
            powers['ENRAGE_POWER'] = 2
    if type(enemy).__name__ in ('TheLost', 'TheForgotten', 'Chomper', 'SpinyToad') and not enemy.is_alive:
        # Native removed this creature. Preserve the stable slot, but compare
        # no active powers for its inert tombstone (unlike a reviving creature).
        powers.clear()
    if pet:
        osty = engine.player.rules.osty
        return dict(player=result, play=[identities[c.instance_id] for c in engine.player.deck.in_play], osty=dict(hp=osty['hp'], maxHp=osty['max_hp']))
    return result


def apply(engine, identities, step):
    if step['kind'] in ('dispatched_death', 'illusion_death'):
        target = engine.enemies[0]
        previous = target.hp
        target.hp = 0
        target._after_damage(previous, False)
        engine.resolve_external_effect()
    elif step['kind'] == 'pet_lethal':
        engine.apply(PlayCard(engine.player.hand[0].instance_id, 0))
    else:
        execute(engine, identities, step)


@pytest.mark.parametrize('row', ROWS, ids=lambda r: r['scenario'])
def test_native_death_dispatch_and_revival_continuation(row):
    engine, identities = setup(row)
    pet = row['scenario'].startswith('focused_sicem_')
    def native(value):
        return dict(player=expected(value['player']), play=value['play'], osty=value['osty']) if pet else expected(value)
    assert boundary(engine, identities, pet=pet) == native(row['before'])
    for step in row['steps']:
        restored = CombatEngine(cards=DEFAULT_CARDS)
        restored.restore(saved(engine))
        assert restored.legal_actions() == engine.legal_actions()
        apply(engine, identities, step)
        apply(restored, dict(identities), step)
        assert saved(restored) == saved(engine)
        actual, reference = boundary(engine, identities, pet=pet), native(step['state'])
        if pet and row['scenario'].endswith('_ending'):
            # Native suppresses result-pile Add at ending; headless canonically
            # finishes the outer card into discard (same as attack-hook probes).
            assert reference['play'] == actual['player']['discard'] == ['card.0']
            assert reference['player']['discard'] == actual['play'] == []
            actual['play'] = actual['player'].pop('discard')
            actual['player']['discard'] = []
        assert actual == reference, step['kind']
    restored.restore(saved(engine))
    assert saved(restored) == saved(engine)
    for key, native_key in (('shuffle', 'shuffle'), ('combat_targets', 'targets'), ('niche', 'niche'), ('monster_ai', 'ai')):
        stream = engine.native_streams[key]
        assert stream.counter == row[native_key]['counter']
        assert deepcopy(stream).next_double() == row[native_key]['suffix']


def test_lethal_sicem_settles_before_horn_selector_and_restores():
    from dataclasses import asdict
    from game.headless.relics.base import RelicInstance
    from game.headless.core.actions import ConfirmCombatSelection

    row = next(r for r in ROWS if r['scenario'] == 'focused_sicem_TestSubject')
    engine, _ = setup(row)
    p = engine.player
    p.rules.relics.append(asdict(RelicInstance('gremlin_horn', 'probe.horn')))
    p.rules.relic_data['probe.horn'] = {}
    p.rules.powers['stratagem'] = 1
    p.deck.discard_pile.extend(p.deck.draw_pile)
    p.deck.draw_pile.clear()
    engine.apply(PlayCard(p.hand[0].instance_id, 0))
    assert p.rules.selection is not None
    assert p.rules.osty == {'hp': 8, 'max_hp': 8}
    assert engine.enemies[0].statuses.get('sic_em') == 0
    restored = CombatEngine(cards=DEFAULT_CARDS)
    restored.restore(saved(engine))
    for _ in range(20):
        if p.rules.selection is None:
            break
        actions = engine.legal_actions()
        assert actions == restored.legal_actions()
        action = ConfirmCombatSelection() if ConfirmCombatSelection() in actions else actions[0]
        engine.apply(action)
        restored.apply(action)
        assert saved(engine) == saved(restored)
    assert p.rules.selection is None
    assert saved(engine) == saved(restored)
    assert p.rules.osty == {'hp': 8, 'max_hp': 8}
