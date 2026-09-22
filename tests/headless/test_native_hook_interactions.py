"""Native shared draw, discard, Sly, exhaust and replay interactions."""
from copy import deepcopy
from dataclasses import asdict
import json
import re
from pathlib import Path

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.combat import CombatEngine
from game.headless.core.native_service import NativeRandomService, COMBAT_STREAMS
from game.headless.core.resolution import find, move_out, push, drain
from game.headless.encounters.randomness import MonsterConstruction
from game.headless.monsters.hive_normal import Chomper
from game.headless.monsters.glory_bosses import Queen
from game.headless.relics.base import RelicInstance

RECORD = json.loads((Path(__file__).parents[2] / 'docs/evidence/native_interactions_2026_09_20.json').read_text())


def saved(combat):
    return json.loads(json.dumps(combat.snapshot()))


def prepare(row):
    service = NativeRandomService(int(row['seed']))
    streams = {name: service.stream(name) for name in COMBAT_STREAMS}
    shuffle_start = streams['shuffle'].getstate()
    definitions = [{'StrikeIronclad':'strike','DefendIronclad':'defend'}.get(n,re.sub(r'(?<!^)(?=[A-Z])', '_', n).lower()) for n in row['definitions']]
    def deck():
        cards = [DEFAULT_CARDS.create(n) for n in definitions]
        if row['subject'] in ('Scrape','DrumOfBattle') and row['variant']:
            cards[-1].upgrade()
        return cards
    combat = CombatEngine(cards=DEFAULT_CARDS, cards_per_turn=0, deck_factory=deck,
        encounter_factory=lambda _: [(Queen if row['scenario']=='binding' else Chomper)(MonsterConstruction(streams['monster_ai'], streams['niche']))])
    combat.native_streams, combat.rng = streams, streams['monster_ai']
    combat.reset(relics=[RelicInstance('the_abacus', 'relic.0')])
    p = combat.player
    cards = {c.instance_id.removeprefix('combat.'):c for c in p.deck.all_cards()}
    for field, name in [('hand','hand'),('draw','draw_pile'),('discard','discard_pile'),('play','in_play'),('exhaust','exhaust_pile')]:
        pile = [cards[i] for i in row['before'][field]]
        setattr(p.deck, name, list(reversed(pile)) if field == 'draw' else pile)
    p.deck.rng.setstate(shuffle_start)
    p.energy = 3
    p.rules.drawn_combat = p.rules.drawn_turn = 0
    p.rules.powers['stratagem'] = 1
    from game.headless.powers.ironclad import apply_power
    extras=[]
    if row['subject']=='Scrape':
        apply_power(p,'hellraiser',1)
    elif row['subject']=='DrumOfBattle':
        for name in (['feel_no_pain','dark_embrace'] if row['variant'] else ['dark_embrace','feel_no_pain']):
            apply_power(p,name,3 if name=='feel_no_pain' else 1)
        if row['scenario'] in ('duplication','burst'):
            apply_power(p,row['scenario'],1)
        extras={'axe':['throwing_axe'],'ashes':['charons_ashes']}.get(row['scenario'],[])
    else:
        powers={'iteration':['pagestorm','defect_iteration'],'automation':['pagestorm','automation'],
                'removed':['pagestorm','corrosive_wave'],'slither':['confused'],'binding':['chains_of_binding','pagestorm'],'confused':['pagestorm','confused','speedster','corrosive_wave']}[row['scenario']]
        for name in reversed(powers) if row['variant'] else powers:
            if name=='chains_of_binding':
                combat.enemies[0].after_move(p, Queen.MOVES[0])
            else:
                apply_power(p,name,3 if row['scenario']=='binding' else 1)
    for name in extras:
        relic=RelicInstance(name,f'relic.{len(p.rules.relics)}')
        p.rules.relics.append(asdict(relic))
        p.rules.relic_data[relic.instance_id]={}
    if row['scenario']=='slither':
        from game.headless.enchantments.base import enchant
        for identity in ('card.0','card.1'):
            enchant(cards[identity],'slither')
    combat.enemies[0].statuses._counts.clear()  # Native omits AfterAddedToRoom.
    combat.enemies[0].hp=combat.enemies[0].max_hp=500
    return combat


def begin(combat, row):
    if row['subject'] == 'Scrape':
        combat.apply(PlayCard(combat.player.hand[-1].instance_id, 0))
    else:
        task=['exhaust',combat.player.hand[-1].instance_id] if row['subject']=='DrumOfBattle' else ['draw',3,False]
        push(combat.player,task)
        drain(combat.player)


def label(card):
    return card.instance_id.removeprefix('combat.')


def state(combat):
    p = combat.player
    from game.headless.powers.ironclad import local_cost
    return dict(hand=[label(c) for c in p.hand], draw=[label(c) for c in reversed(p.deck.draw_pile)],
                discard=[label(c) for c in p.deck.discard_pile], play=[label(c) for c in p.deck.in_play],
                exhaust=[label(c) for c in p.deck.exhaust_pile], energy=p.energy, block=p.block,
                enemyHp=combat.enemies[0].hp, poison=combat.enemies[0].statuses.get('poison'), duplication=p.rules.powers.get('duplication',0), burst=p.rules.powers.get('burst',0),
                automation=next((p.rules.auxiliaries[k] for k in p.rules.powers if k.startswith('automation:')),None),
                bound=[c.combat_state.bound for c in sorted(p.deck.all_cards(),key=lambda c:int(c.instance_id.rsplit('.',1)[1]))],
                costs=[0 if c.spec.x_cost else local_cost(c) for c in sorted(p.deck.all_cards(),key=lambda c:int(c.instance_id.rsplit('.',1)[1]))])


@pytest.mark.parametrize('row', RECORD['result']['rows'], ids=lambda r:f"{r['subject']}-{r['scenario']}-{r['seed']}-{r['variant']}")
def test_native_interactions_callbacks_and_restore(row, monkeypatch):
    combat = prepare(row)
    p = combat.player
    assert state(combat) == row['before']
    from game.headless.powers import defect
    original = defect.draw_record
    drawn = []
    def record(player, card):
        if player is p:
            drawn.append(label(card))
        return original(player, card)
    monkeypatch.setattr(defect, 'draw_record', record)
    begin(combat, row)
    assert state(combat) == row['checkpoint']
    other = CombatEngine(cards=DEFAULT_CARDS)
    other.restore(saved(combat))
    assert saved(other) == saved(combat)
    for index,answer in enumerate(row['answers']):
        if row['scenario']=='removed' and index==0:
            from game.headless.core.draw_hooks import remove_power
            for engine in (combat,other):
                remove_power(engine.player,'corrosive_wave')
                restored=CombatEngine(cards=DEFAULT_CARDS)
                restored.restore(saved(engine))
                assert saved(restored)==saved(engine)
        assert state(combat) == answer['state']
        assert {label(c) for c in p.deck.draw_pile} == set(answer['options'])
        for action in [*[ChooseCombatCard('combat.'+i) for i in answer['selected']],ConfirmCombatSelection()]:
            combat.apply(action)
            other.apply(action)
        assert saved(other) == saved(combat)
        other.restore(saved(combat))
    assert state(combat) == row['after']
    assert drawn == row['draws']
    assert p.rules.drawn_turn == p.rules.drawn_combat == len(drawn)
    assert p.rules.plays_finished == len(row['plays'])
    assert p.rules.discarded_turn == len(row['discards'])
    assert not p.rules.tasks and not p.rules.selection and not p.deck.in_play
    for engine in (combat,other):
        deck = engine.player.deck
        for rng,native in [(deck.rng,'shuffle'),(deck.target_rng,'targets'),(deck.energy_rng,'energyCosts'),(deck.selection_rng,'selection'),(deck.niche_rng,'niche'),(engine.rng,'ai')]:
            assert rng.counter == row[native]['counter'], native
            assert deepcopy(rng).next_double() == row[native]['suffix']



@pytest.mark.parametrize('subject,scenario', [('DrumOfBattle','duplication'),('Draw','automation'),('Draw','iteration')])
@pytest.mark.parametrize('mutation', ['shape','owner','old_schema'])
def test_paused_interaction_rejects_malformed_save_atomically(subject, scenario, mutation):
    row=next(r for r in RECORD['result']['rows'] if r['subject']==subject and r['scenario']==scenario and not r['variant'])
    combat=prepare(row)
    begin(combat,row)
    before=saved(combat)
    bad=deepcopy(before)
    rules=bad['player']['rules']
    task=next(t for t in rules['tasks'] if t[0]==('drum_exhaust' if subject=='DrumOfBattle' else 'draw_power'))
    receipt=next((r for r in rules['pending_events'] if r['task']==task),None)
    if mutation=='shape':
        task.append(0)
    elif mutation=='owner':
        task[1]='not-owned'
    else:
        bad['schema']='headless_combat_state_v34'
    if receipt:
        receipt['task']=list(task)
    with pytest.raises(ValueError):
        combat.restore(bad)
    assert saved(combat)==before


def test_drum_exhaust_requires_emitted_receipt():
    row=next(r for r in RECORD['result']['rows'] if r['subject']=='DrumOfBattle')
    combat=prepare(row)
    begin(combat,row)
    before=saved(combat)
    bad=deepcopy(before)
    rules=bad['player']['rules']
    rules['pending_events']=[r for r in rules['pending_events'] if r['task'][0]!='drum_exhaust']
    with pytest.raises(ValueError):
        combat.restore(bad)
    assert saved(combat)==before


def test_previous_run_draw_semantics_reject_atomically():
    from game.headless.run.engine import RunEngine
    run=RunEngine.ironclad_slice(seed=2)
    before=json.loads(json.dumps(run.snapshot()))
    bad=deepcopy(before)
    bad['schema']='headless_run_state_v50'
    with pytest.raises(ValueError):
        run.restore(bad)
    assert json.loads(json.dumps(run.snapshot()))==before


@pytest.mark.parametrize('seed', [1,2,3,4])
def test_expired_corrosive_wave_continues_detached_death_draw(seed):
    # Source-backed full-turn regression, complementing the native controlled
    # removal cases. Expiry happens naturally while the death hook is parked.
    from game.headless.core.actions import EndTurn
    from game.headless.powers.ironclad import apply_power
    combat=CombatEngine(cards=DEFAULT_CARDS,cards_per_turn=0,
        deck_factory=lambda:[DEFAULT_CARDS.create(n) for n in ('dazed','defend','strike','anger')],
        encounter_factory=lambda rng:[Chomper(rng),Chomper(rng)])
    combat.reset(seed=seed,relics=[RelicInstance('gremlin_horn','relic.0')])
    p=combat.player
    cards=sorted(p.deck.all_cards(),key=lambda c:c.instance_id)
    p.deck.draw_pile,p.deck.discard_pile=[cards[0]],cards[1:]
    for key,amount in [('plating',2),('juggernaut',6),('pagestorm',1),('corrosive_wave',1),('stratagem',1)]:
        apply_power(p,key,amount)
    combat.enemies[0].hp=1
    for enemy in combat.enemies:
        enemy.statuses._counts.clear()
    combat.apply(EndTurn())
    assert p.rules.selection and 'corrosive_wave' not in p.rules.powers
    assert any(t[0]=='draw_power_removed' for t in p.rules.tasks)
    other=CombatEngine(cards=DEFAULT_CARDS)
    other.restore(saved(combat))
    # A newly applied instance must not replace the captured expired amount.
    for engine in (combat,other):
        apply_power(engine.player,'corrosive_wave',7)
    while p.rules.selection:
        selected=p.rules.selection['candidates'][0]
        for action in (ChooseCombatCard(selected),ConfirmCombatSelection()):
            combat.apply(action)
            other.apply(action)
            assert saved(combat)==saved(other)
    # Nested draw uses the new 7; captured original uses 1; enemy-side tick removes 1.
    assert combat.enemies[1].statuses.get('poison')==7


@pytest.mark.parametrize('mutation', ['receipt','power','amount'])
def test_removed_listener_save_rejects_corruption(mutation):
    row=next(r for r in RECORD['result']['rows'] if r['scenario']=='removed' and not r['variant'])
    combat=prepare(row)
    begin(combat,row)
    from game.headless.core.draw_hooks import remove_power
    remove_power(combat.player,'corrosive_wave')
    before=saved(combat)
    bad=deepcopy(before)
    rules=bad['player']['rules']
    task=next(t for t in rules['tasks'] if t[0]=='draw_power_removed')
    receipt=next(r for r in rules['pending_events'] if r['task']==task)
    if mutation=='receipt':
        rules['pending_events'].remove(receipt)
    else:
        task[1 if mutation=='power' else 4]='missing' if mutation=='power' else -1
        receipt['task']=list(task)
    with pytest.raises(ValueError):
        combat.restore(bad)
    assert saved(combat)==before
