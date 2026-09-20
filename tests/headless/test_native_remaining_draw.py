"""Native Scrape and before-hand-draw callbacks; controlled depleted-pile cases."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.combat import CombatEngine
from game.headless.core.native_service import NativeRandomService, COMBAT_STREAMS
from game.headless.core.resolution import find, move_out, push, drain
from game.headless.encounters.randomness import MonsterConstruction
from game.headless.monsters.hive_normal import Chomper
from game.headless.relics.base import RelicInstance

RECORD = json.loads((Path(__file__).parents[2] / 'docs/evidence/native_remaining_draw_2026_09_20.json').read_text())


def saved(combat):
    return json.loads(json.dumps(combat.snapshot()))


def prepare(row):
    service = NativeRandomService(int(row['seed']))
    streams = {name: service.stream(name) for name in COMBAT_STREAMS}
    shuffle_start = streams['shuffle'].getstate()
    definitions = [{'StrikeIronclad':'strike','DefendIronclad':'defend'}.get(n,n.lower()) for n in row['definitions']]
    def deck():
        cards = [DEFAULT_CARDS.create(n) for n in definitions]
        if row['subject'] == 'Scrape' and row['variant']:
            cards[-1].upgrade()
        return cards
    combat = CombatEngine(cards=DEFAULT_CARDS, cards_per_turn=0, deck_factory=deck,
        encounter_factory=lambda _: [Chomper(MonsterConstruction(streams['monster_ai'], streams['niche']))])
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
    if row['subject'] == 'ForegoneConclusion':
        p.rules.powers['foregone_conclusion'] = 3 if row['variant'] else 2
    extras = (['toasty_mittens'] if row['subject'] == 'ToastyMittens' else []) + (['fiddle'] if row['scenario'] == 'fiddle' else [])
    for name in extras:
        relic = RelicInstance(name, f'relic.{len(p.rules.relics)}')
        p.rules.relics.append(asdict(relic))
        p.rules.relic_data[relic.instance_id] = {}
    if row['subject'] == 'ToastyMittens' and row['variant']:
        p.rules.round_number = 2
    if row['scenario'] == 'no-draw':
        p.rules.powers['no_draw'] = 1
    return combat


def begin(combat, row):
    if row['subject'] == 'Scrape':
        combat.apply(PlayCard(combat.player.hand[-1].instance_id, 0))
    else:
        task = ['ancient_mittens','relic.1'] if row['subject'] == 'ToastyMittens' else ['regent_before_draw','foregone_conclusion']
        push(combat.player, task)
        drain(combat.player)


def label(card):
    return card.instance_id.removeprefix('combat.')


def state(combat):
    p = combat.player
    return dict(hand=[label(c) for c in p.hand], draw=[label(c) for c in reversed(p.deck.draw_pile)],
                discard=[label(c) for c in p.deck.discard_pile], play=[label(c) for c in p.deck.in_play],
                exhaust=[label(c) for c in p.deck.exhaust_pile], energy=p.energy, block=p.block,
                enemyHp=combat.enemies[0].hp, strength=p.strength, foregone=p.rules.powers.get('foregone_conclusion',0))


@pytest.mark.parametrize('row', RECORD['result']['rows'], ids=lambda r:f"{r['subject']}-{r['scenario']}-{r['seed']}-{r['variant']}")
def test_native_remaining_draw_callbacks_and_restore(row, monkeypatch):
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
    for index, answer in enumerate(row['answers']):
        if index == 0:
            for engine in (combat,other):
                # Explicit fixture interference, not a simulated live action.
                for moved in row['moved']:
                    card = find(engine.player,'combat.'+moved)
                    move_out(engine.player,card)
                    engine.player.deck.discard_card(card)
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
    assert not p.rules.tasks and not p.rules.selection and not p.deck.in_play
    for engine in (combat,other):
        deck = engine.player.deck
        for rng,native in [(deck.rng,'shuffle'),(deck.target_rng,'targets'),(deck.selection_rng,'selection'),(deck.niche_rng,'niche'),(engine.rng,'ai')]:
            assert rng.counter == row[native]['counter']
            assert deepcopy(rng).next_double() == row[native]['suffix']


def paused(subject):
    row = next(r for r in RECORD['result']['rows'] if r['subject']==subject and r['scenario']=='mixed' and not r['variant'])
    combat = prepare(row)
    begin(combat,row)
    assert combat.player.rules.selection
    return combat


@pytest.mark.parametrize('subject', ['Scrape','ToastyMittens','ForegoneConclusion'])
@pytest.mark.parametrize('mutation', ['extra_argument','missing_owner','old_schema'])
def test_invalid_remaining_draw_continuations_reject_atomically(subject, mutation):
    combat = paused(subject)
    before = saved(combat)
    bad = deepcopy(before)
    rules = bad['player']['rules']
    op = {'Scrape':'def_scrape_after_shuffle','ToastyMittens':'ancient_mittens_after_shuffle','ForegoneConclusion':'regent_foregone_after_shuffle'}[subject]
    task = next(t for t in rules['tasks'] if t[0]==op)
    receipt = next((e for e in rules['pending_events'] if e['task']==task),None)
    if mutation=='extra_argument':
        task.append(0)
    elif mutation=='missing_owner':
        if subject=='ForegoneConclusion':
            rules['powers'].pop('foregone_conclusion')
        else:
            task[1]='not-owned'
    else:
        bad['schema']='headless_combat_state_v33'
    if receipt:
        receipt['task']=list(task)  # Reach owner/shape checks beyond event matching.
    with pytest.raises(ValueError):
        combat.restore(bad)
    assert saved(combat)==before


def test_scrape_shuffle_requires_its_emitted_event_receipt():
    combat=paused('Scrape')
    before=saved(combat)
    bad=deepcopy(before)
    r=bad['player']['rules']
    r['pending_events']=[e for e in r['pending_events'] if e['task'][0]!='def_scrape_after_shuffle']
    with pytest.raises(ValueError):
        combat.restore(bad)
    assert saved(combat)==before


def test_mittens_strength_waits_for_dark_embrace_shuffle_and_restores():
    # Source-backed nested exhaust regression; not one of the native captures.
    row=next(r for r in RECORD['result']['rows'] if r['subject']=='ToastyMittens' and r['scenario']=='mixed' and not r['variant'])
    combat=prepare(row)
    p=combat.player
    first=p.deck.discard_pile.pop(0)
    p.deck.draw_pile=[first]
    p.rules.powers['dark_embrace']=1
    begin(combat,row)
    assert p.strength==0 and p.deck.exhaust_pile==[first]
    assert p.rules.selection['source']=='stratagem'
    assert ['ancient_strength','relic.1'] in p.rules.tasks
    other=CombatEngine(cards=DEFAULT_CARDS)
    other.restore(saved(combat))
    chosen=p.rules.selection['candidates'][0]
    for action in (ChooseCombatCard(chosen),ConfirmCombatSelection()):
        combat.apply(action)
        other.apply(action)
        assert saved(combat)==saved(other)
    assert p.strength==1 and p.rules.drawn_combat==1 and len(p.hand)==2
    assert not p.rules.tasks and not p.rules.selection


def test_previous_run_schema_rejects_atomically():
    from game.headless.run.engine import RunEngine
    run=RunEngine.ironclad_slice(seed=2)
    before=json.loads(json.dumps(run.snapshot()))
    bad=deepcopy(before)
    bad['schema']='headless_run_state_v49'
    with pytest.raises(ValueError):
        run.restore(bad)
    assert json.loads(json.dumps(run.snapshot()))==before
