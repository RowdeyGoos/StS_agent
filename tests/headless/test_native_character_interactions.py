"""Four native mechanism probes, replayed through owned JSON continuations."""
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import PlayCard
from game.headless.core.combat import CombatEngine
from game.headless.core.native_service import COMBAT_STREAMS, NativeRandomService
from game.headless.core import orbs
from game.headless.core.resolution import drain
from game.headless.powers.ironclad import local_cost
from game.headless.relics.combat import owned
from tests.headless.test_native_item_status import saved, slug, power_map

ROOT = Path(__file__).parents[2]
PATH = ROOT / 'docs/evidence/native_character_interactions_2026_09_21.json.gz'
RECORD = json.loads(gzip.decompress(PATH.read_bytes()))
STREAMS = {'CombatCardSelection': 'combat_card_selection', 'CombatTargets': 'combat_targets',
           'CombatOrbGeneration': 'combat_orb_generation'}


def prepare(row):
    service = NativeRandomService(2)
    engine = CombatEngine(cards=DEFAULT_CARDS, deck_factory=lambda: [], cards_per_turn=0,
                          player_max_hp=80)
    engine.native_streams = {key: service.stream(key) for key in COMBAT_STREAMS}
    engine.reset(character=row['character'].lower())
    p = engine.player
    p.rules.relics = [dict(definition_id=slug(n), instance_id=f'relic.{i}', counter=0, data={})
                     for i, n in enumerate(row['relicNames'])]
    p.rules.relic_data = {r['instance_id']: {} for r in p.rules.relics}
    p.hp, p.energy = 80, row['before']['energy']
    engine.enemies[0].hp = engine.enemies[0].max_hp = 1000
    engine.enemies[0].statuses._counts.clear()
    for name in row['cardNames']:
        card = DEFAULT_CARDS.create(slug(name))
        p.deck._ensure_identity(card)
        p.hand.append(card)
    return engine, [c.instance_id for c in p.hand]


def state(engine, identities):
    from game.headless.core.resolution import find
    p = engine.player
    piles = [(name, cards) for name, cards in [('Hand', p.hand), ('DrawPile', p.deck.draw_pile),
             ('Discard', p.deck.discard_pile), ('Exhaust', p.deck.exhaust_pile), ('Play', p.deck.in_play)]]
    return dict(hp=p.hp, block=p.block, energy=p.energy, stars=p.rules.stars,
        enemyHp=engine.enemies[0].hp, powers=power_map(engine),
        cards=[dict(id=find(p, i).definition.definition_id.upper(), cost=local_cost(find(p, i)),
                    pile=next(n for n, cards in piles if find(p, i) in cards)) for i in identities],
        orbs=[dict(kind=p.rules.orbs[i]['kind'].title()+'Orb', passive=orbs.value(p,p.rules.orbs[i],'passive'),
                   evoke=orbs.value(p,p.rules.orbs[i],'evoke')) for i in p.rules.orb_order],
        counters={native: engine.native_streams[key].counter for native,key in STREAMS.items()},
        dust=owned(p,'galactic_dust')['counter'] if owned(p,'galactic_dust') else None)


def apply(engine, identities, step):
    from game.headless.core.resolution import find
    from game.headless.powers.ironclad import apply_power
    from game.headless.relics.character_hooks import hook, start
    p = engine.player
    kind, amount = step['kind'], step['amount']
    if kind == 'play':
        engine.apply(PlayCard(identities[amount], 0))
    elif kind == 'speed':
        from game.headless.potions.base import PotionInstance
        from game.headless.potions import use
        item = PotionInstance('speed_potion', 'potion.probe')
        p.rules.potion_capacity = p.rules.potion_slots = 1
        p.rules.potions = [dict(definition_id=item.definition_id, instance_id=item.instance_id)]
        owner = SimpleNamespace(state=SimpleNamespace(potions=[item]), combat=engine)
        use.use(owner, next(a for a in use.actions(owner) if a.instance_id == item.instance_id))
    elif kind == 'artifact':
        p.statuses.add('artifact', amount)
    elif kind == 'expire':
        from game.headless.potions.powers import after_end
        for key in tuple(p.rules.powers):
            after_end(p, key)
    elif kind == 'gain_stars':
        from game.headless.powers.regent import gain_stars
        gain_stars(p, amount)
    elif kind == 'spend':
        from game.headless.powers.regent import spend
        spend(p, 0, amount)
    elif kind == 'reset_mini':
        start(p, owned(p, 'mini_regent'), 5)
    elif kind == 'terminal_setup':
        apply_power(p, 'child_of_the_stars', 1)
        apply_power(p, 'juggernaut', 6)
        engine.enemies[0].hp = 6
        owned(p, 'galactic_dust')['counter'] = 9
        start(p, owned(p, 'mini_regent'), 5)
    elif kind == 'bookmark':
        hook(p, owned(p, 'bookmark'), 'after_flush', '')
    elif kind == 'turn_cost':
        from game.headless.core.card_costs import mark_setter
        card = find(p, identities[0])
        card.combat_state.turn_cost_override = amount
        mark_setter(card.combat_state, 'turn')
    elif kind == 'cost_cleanup':
        find(p, identities[0]).combat_state.turn_cost_override = None
    elif kind.startswith('channel_'):
        orbs.execute(p, 'orb_channel', ['random' if kind == 'channel_random' else kind[8:-3].lower()])
    elif kind == 'orb_end':
        orbs.phase(p, 'end')
    elif kind == 'loop_setup':
        apply_power(p, 'loop', 1)
    elif kind == 'loop':
        from game.headless.powers.defect import execute
        execute(p, 'def_start_power', ['loop'])
    elif kind == 'focus':
        apply_power(p, 'focus', amount)
    elif kind == 'evoke':
        orbs.execute(p, 'orb_evoke', [False, True])
    else:
        raise AssertionError(kind)
    drain(p)


@pytest.mark.parametrize('row', RECORD['result']['rows'], ids=lambda r:r['character'])
def test_native_character_interactions(row):
    engine, identities = prepare(row)
    assert state(engine, identities) == row['before']
    for step in row['steps']:
        other = CombatEngine(cards=DEFAULT_CARDS)
        other.restore(saved(engine))
        assert other.legal_actions() == engine.legal_actions()
        apply(engine, identities, step)
        apply(other, identities, step)
        assert saved(other) == saved(engine)
        assert state(engine, identities) == step['state'], step['kind']
    for name, key in STREAMS.items():
        rng = engine.native_streams[key]
        assert dict(counter=rng.counter, suffix=rng.next_double()) == row['tails'][name]


def test_native_character_interaction_capture_identity():
    import hashlib
    assert RECORD['userDirectoryRemoved']
    assert RECORD['pins']['sts2.dll'] == 'e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18'
    assert {r['character'] for r in RECORD['result']['rows']} == {'Silent', 'Regent', 'Necrobinder', 'Defect'}
    assert len(RECORD['result']['rows']) == 4
    for name, digest in RECORD['fixtureSources'].items():
        assert hashlib.sha256((ROOT / 'tools/native_combat_oracle/queue_runtime' / name).read_bytes()).hexdigest() == digest


def test_cables_excludes_all_direct_passive_callers():
    from tests.headless.test_defect_cards import fight, play, channel
    from game.headless.relics.character_hooks import hook
    from game.headless.relics.combat import memory
    from game.headless.powers.defect import execute
    for caller in ('loop', 'emotion_chip', 'darkness', 'tesla_coil'):
        engine = fight(*([caller] if caller in ('darkness', 'tesla_coil') else []))
        p = engine.player
        p.rules.relics = [dict(definition_id=n, instance_id=f'relic.{i}', counter=0, data={})
                         for i,n in enumerate(('gold_plated_cables', 'emotion_chip'))]
        p.rules.relic_data = {r['instance_id']: {} for r in p.rules.relics}
        channel(engine, 'lightning' if caller == 'tesla_coil' else 'dark')
        if caller == 'loop':
            p.rules.powers['loop'] = 1
            execute(p, 'def_start_power', ['loop'])
        elif caller == 'emotion_chip':
            relic = owned(p, 'emotion_chip')
            memory(p, relic)['previous_damage'] = True
            hook(p, relic, 'after_draw', '')
        else:
            play(engine, caller)
        drain(p)
        if caller == 'tesla_coil':
            assert engine.enemies[0].hp == 994  # 3 attack damage plus one 3-damage passive.
        else:
            assert p.rules.orbs[p.rules.orb_order[0]]['value'] == 12, caller
        other = CombatEngine(cards=DEFAULT_CARDS)
        other.restore(saved(engine))
        assert saved(other) == saved(engine)


def test_natural_orb_phase_restores_after_a_deferred_death_choice():
    from copy import deepcopy
    from tests.headless.test_defect_cards import fight, channel
    from game.headless.core.actions import EndTurn, ChooseCombatCard, ConfirmCombatSelection
    engine = fight(discard=('strike', 'defend'), enemies=2)
    p = engine.player
    p.rules.relics = [dict(definition_id=n, instance_id=f'relic.{i}', counter=0, data={})
                     for i,n in enumerate(('gold_plated_cables', 'gremlin_horn'))]
    p.rules.relic_data = {r['instance_id']: {} for r in p.rules.relics}
    p.rules.powers['stratagem'] = 1
    p.deck.target_rng.seed(1)
    p.rules.orb_slots = 3
    engine.enemies[0].hp = 1
    channel(engine, 'lightning', 'frost')
    engine.apply(EndTurn())
    assert p.rules.selection
    # Native detached death hooks let the natural phase finish before its choice.
    assert p.block == 2 and engine.enemies[1].hp == 997
    snapshot = saved(engine)
    other = CombatEngine(cards=DEFAULT_CARDS)
    other.restore(snapshot)
    for target in (engine, other):
        target.apply(next(a for a in target.legal_actions() if isinstance(a, ChooseCombatCard)))
        target.apply(ConfirmCombatSelection())
    assert saved(other) == saved(engine)
    for damage in ('phase', 'receipt', 'schema'):
        bad = deepcopy(snapshot)
        if damage == 'phase':
            rules = bad['player']['rules']
            task = ['orb_phase_trigger', 'orb.0', 'passive', None]
            rules['tasks'].insert(0, task)
            rules['pending_events'].append(dict(context=rules['active_hook'], task=task))
            rules['turn_ending'] = False
        elif damage == 'receipt':
            bad['player']['rules']['tasks'].insert(0, ['orb_phase_trigger', 'orb.0', 'passive', None])
        else:
            bad['schema'] = 'headless_combat_state_v46'
        with pytest.raises(ValueError):
            CombatEngine(cards=DEFAULT_CARDS).restore(bad)
