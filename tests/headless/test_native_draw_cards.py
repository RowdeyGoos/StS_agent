"""Native Pillage/Escape Plan draw results, blocked draws and shuffle resumption."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.combat import CombatEngine
from game.headless.core.native_service import NativeRandomService, COMBAT_STREAMS
from game.headless.core.resolution import find, move_out
from game.headless.encounters.randomness import MonsterConstruction
from game.headless.monsters.hive_normal import Chomper
from game.headless.relics.base import RelicInstance

RECORD = json.loads((Path(__file__).parents[2] / 'docs/evidence/native_draw_cards_2026_09_20.json').read_text())


def saved(combat):
    return json.loads(json.dumps(combat.snapshot()))


def prepare(row):
    service = NativeRandomService(int(row['seed']))
    streams = {name: service.stream(name) for name in COMBAT_STREAMS}
    shuffle_start = streams['shuffle'].getstate()
    definitions = ['strike' if row['scenario'] == 'attacks' or row['fillers'] == 3 and i != 1 else 'defend' for i in range(row['fillers'])]
    if row['scenario'] == 'full':
        definitions += ['defend'] * 9
    definitions += ['pillage' if row['cardName'] == 'Pillage' else 'escape_plan']
    def deck():
        cards = [DEFAULT_CARDS.create(n) for n in definitions]
        if row['upgraded']:
            cards[-1].upgrade()
        return cards
    combat = CombatEngine(cards=DEFAULT_CARDS, cards_per_turn=0, deck_factory=deck,
        encounter_factory=lambda _: [Chomper(MonsterConstruction(streams['monster_ai'], streams['niche']))])
    combat.native_streams, combat.rng = streams, streams['monster_ai']
    relics = [RelicInstance('the_abacus', 'relic.0')]
    if row['scenario'] == 'fiddle':
        relics.append(RelicInstance('fiddle', 'relic.1'))
    combat.reset(relics=relics)
    p = combat.player
    cards = sorted(p.deck.all_cards(), key=lambda c: int(c.instance_id.split('.')[-1]))
    p.deck.draw_pile, p.deck.discard_pile, p.deck.hand = [], cards[:row['fillers']], cards[row['fillers']:]
    p.deck.rng.setstate(shuffle_start)
    p.energy = 3
    p.rules.drawn_combat = p.rules.drawn_turn = 0
    p.rules.powers['stratagem'] = 1
    if row['scenario'] == 'no-draw':
        p.rules.powers['no_draw'] = 1
    return combat, cards[-1].instance_id


def label(card):
    return card.instance_id.removeprefix("combat.")


def state(combat):
    p = combat.player
    return dict(hand=[label(c) for c in p.hand],
                draw=[label(c) for c in reversed(p.deck.draw_pile)],
                discard=[label(c) for c in p.deck.discard_pile],
                play=[label(c) for c in p.deck.in_play],
                exhaust=[label(c) for c in p.deck.exhaust_pile],
                energy=p.energy, block=p.block, enemyHp=combat.enemies[0].hp)


@pytest.mark.parametrize('row', RECORD['result']['rows'], ids=lambda r: f"{r['cardName']}-{r['scenario']}-{r['seed']}-{r['upgraded']}")
def test_native_card_draw_and_paused_json_continuation(row, monkeypatch):
    combat, identity = prepare(row)
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
    combat.apply(PlayCard(identity, 0 if row['cardName'] == 'Pillage' else None))
    assert state(combat) == row['checkpoint']
    other = CombatEngine(cards=DEFAULT_CARDS)
    other.restore(saved(combat))
    assert saved(other) == saved(combat)
    for index, answer in enumerate(row['answers']):
        if index == 0:
            for engine in (combat, other):
                # Match the fixture's controlled native Add commands. This is
                # interference during an active choice, not a live schedule claim.
                for moved in row['moved']:
                    card = find(engine.player, "combat." + moved)
                    move_out(engine.player, card)
                    engine.player.deck.discard_card(card)
        assert state(combat) == answer['state']
        assert {label(c) for c in p.deck.draw_pile} == set(answer['options'])
        for action in (ChooseCombatCard('combat.' + answer['selected']), ConfirmCombatSelection()):
            combat.apply(action)
            other.apply(action)
        assert saved(combat) == saved(other)
        other.restore(saved(combat))
    assert state(combat) == row['after']
    assert drawn == row['draws']
    assert p.rules.drawn_turn == p.rules.drawn_combat == len(drawn)
    assert p.rules.plays_finished == len(row['plays']) == 1
    assert not p.rules.tasks and not p.rules.selection and not p.deck.in_play
    for engine in (combat, other):
        deck = engine.player.deck
        for rng, native in [(deck.rng,'shuffle'),(deck.target_rng,'targets'),(deck.selection_rng,'selection'),(deck.niche_rng,'niche'),(engine.rng,'ai')]:
            assert rng.counter == row[native]['counter']
            assert deepcopy(rng).next_double() == row[native]['suffix']


def paused(card_name='EscapePlan'):
    row = next(r for r in RECORD['result']['rows'] if r['cardName'] == card_name and r['scenario'] == 'mixed' and not r['upgraded'])
    combat, identity = prepare(row)
    combat.apply(PlayCard(identity, 0 if card_name == 'Pillage' else None))
    assert combat.player.rules.selection
    return combat


@pytest.mark.parametrize('mutation', ['missing_owner', 'wrong_owner', 'negative_block', 'extra_argument', 'old_schema'])
def test_invalid_escape_shuffle_continuation_rejects_atomically(mutation):
    combat = paused()
    before = saved(combat)
    bad = deepcopy(before)
    task = next(t for t in bad['player']['rules']['tasks'] if t[0] == 'silent_escape_after_shuffle')
    if mutation == 'missing_owner':
        task[1] = 'not-owned'
    elif mutation == 'wrong_owner':
        task[1] = combat.player.deck.draw_pile[0].instance_id
    elif mutation == 'negative_block':
        task[2] = -1
    elif mutation == 'extra_argument':
        task.append(False)
    else:
        bad['schema'] = 'headless_combat_state_v32'
    with pytest.raises(ValueError):
        combat.restore(bad)
    assert saved(combat) == before


def test_pillage_shuffle_phase_rejects_extra_arguments_atomically():
    combat = paused('Pillage')
    before = saved(combat)
    bad = deepcopy(before)
    next(t for t in bad['player']['rules']['tasks'] if t[0] == 'pillage_after_shuffle').append(1)
    with pytest.raises(ValueError):
        combat.restore(bad)
    assert saved(combat) == before


def test_run_rejects_previous_draw_semantics_atomically():
    from game.headless.run.engine import RunEngine
    run = RunEngine.ironclad_slice(seed=2)
    before = json.loads(json.dumps(run.snapshot()))
    bad = deepcopy(before)
    bad['schema'] = 'headless_run_state_v48'
    with pytest.raises(ValueError):
        run.restore(bad)
    assert json.loads(json.dumps(run.snapshot())) == before
