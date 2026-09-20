"""Native Mayhem gather-before-play semantics and owned paused reservations."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.combat import CombatEngine
from game.headless.core.native_service import NativeRandomService, COMBAT_STREAMS
from game.headless.core.resolution import push, drain
from game.headless.encounters.randomness import MonsterConstruction
from game.headless.monsters.hive_normal import Chomper
from game.headless.relics.base import RelicInstance

FLAK = json.loads((Path(__file__).parents[2] / 'docs/evidence/native_autoplay_flak_2026_09_20.json').read_text())
RECORD = json.loads((Path(__file__).parents[2] / 'docs/evidence/native_autoplay_2026_09_20.json').read_text())


def saved(combat):
    return json.loads(json.dumps(combat.snapshot()))


def prepare(row):
    service = NativeRandomService(int(row['seed']))
    streams = {name: service.stream(name) for name in COMBAT_STREAMS}
    shuffle_start = streams['shuffle'].getstate()
    definitions = ['flak_cannon', 'slimed', 'wound', 'defend', 'defend', 'defend'] if row.get('flak') else ['defend'] * row['fillers']
    combat = CombatEngine(
        cards=DEFAULT_CARDS, cards_per_turn=0,
        deck_factory=lambda: [DEFAULT_CARDS.create(n) for n in definitions],
        encounter_factory=lambda _: [Chomper(MonsterConstruction(streams['monster_ai'], streams['niche']))],
    )
    combat.native_streams, combat.rng = streams, streams['monster_ai']
    combat.reset(relics=[RelicInstance('the_abacus', 'relic.0')])
    p = combat.player
    cards = sorted(p.deck.all_cards(), key=lambda c: c.instance_id)
    identities = {c.instance_id: f'card.{i}' for i, c in enumerate(cards)}
    p.deck.draw_pile, p.deck.discard_pile = [], cards
    opening = 3 if row.get('flak') else int(row['drawFirst'])
    p.deck.draw_pile = list(reversed(p.deck.discard_pile[:opening]))
    del p.deck.discard_pile[:opening]
    p.deck.rng.setstate(shuffle_start)
    p.energy = 0
    p.rules.powers['mayhem'] = row['count']
    if row['withStratagem']:
        p.rules.powers['stratagem'] = 1
    if row.get('darkEmbrace'):
        p.rules.powers['dark_embrace'] = 1
    return combat, identities


def state(combat, identities):
    p = combat.player
    return dict(hand=[identities[c.instance_id] for c in p.hand],
                draw=[identities[c.instance_id] for c in reversed(p.deck.draw_pile)],
                discard=[identities[c.instance_id] for c in p.deck.discard_pile],
                play=[identities[c.instance_id] for c in p.deck.in_play],
                exhaust=[identities[c.instance_id] for c in p.deck.exhaust_pile],
                energy=p.energy, block=p.block)


@pytest.mark.parametrize('row', RECORD['result']['rows'] + FLAK['result']['rows'], ids=lambda r: '-'.join(str(r[k]) for k in ('seed','fillers','count','drawFirst','withStratagem','answerLast')))
def test_native_mayhem_collects_before_plays_and_restores_at_shuffle(row, monkeypatch):
    combat, identities = prepare(row)
    p = combat.player
    assert state(combat, identities) == row['before']
    from game.headless.powers import ironclad
    original = ironclad.after_play
    plays = []
    def after_play(player, card):
        if player is p:
            plays.append(identities[card.instance_id])
        return original(player, card)
    monkeypatch.setattr(ironclad, 'after_play', after_play)
    push(p, ['mayhem'])
    drain(p)
    assert state(combat, identities) == row['checkpoint']
    assert bool(p.rules.selection) == bool(row['answers'])
    other = CombatEngine(cards=DEFAULT_CARDS)
    other.restore(saved(combat))
    assert saved(other) == saved(combat)
    for answer in row['answers']:
        assert state(combat, identities) == answer['state']
        actual_options = [identities[i] for i in p.rules.selection['candidates']]
        if row.get('flak'):
            # Replay supplies physical draw-pile candidates, not UI sort order.
            assert set(actual_options) == set(answer['options'])
        else:
            assert actual_options == answer['options']
        selected = next(i for i, label in identities.items() if label == answer['selected'])
        for action in (ChooseCombatCard(selected), ConfirmCombatSelection()):
            combat.apply(action)
            other.apply(action)
            assert saved(combat) == saved(other)
    assert state(combat, identities) == row['after']
    assert plays == row['plays']
    assert [e.hp for e in combat.enemies if e.is_alive] == row['enemyHp']
    assert p.rules.plays_finished == len(row['plays'])
    assert not p.rules.autoplay_batches and not p.rules.plays and not p.rules.tasks
    for engine in (combat, other):
        deck = engine.player.deck
        for stream, native in [(deck.rng, 'shuffle'), (deck.target_rng, 'targets'), (deck.selection_rng, 'selection'), (deck.niche_rng, 'niche'), (engine.rng, 'ai')]:
            assert stream.counter == row[native]['counter']
            assert deepcopy(stream).next_double() == row[native]['suffix']


def paused_batch():
    row = next(r for r in RECORD['result']['rows'] if r['count'] == 3 and r['drawFirst'] and r['fillers'] == 3 and r['withStratagem'])
    combat, _ = prepare(row)
    push(combat.player, ['mayhem'])
    drain(combat.player)
    return combat


@pytest.mark.parametrize('mutation', [
    'missing_batch', 'missing_reservation', 'duplicate_card', 'foreign_context',
    'negative_remaining', 'boolean_remaining', 'bad_exhaust', 'missing_task',
    'duplicate_task', 'wrong_phase', 'unowned_task', 'move_reserved',
    'reserved_selector', 'old_schema',
])
def test_invalid_autoplay_reservations_are_rejected_atomically(mutation):
    combat = paused_batch()
    before = saved(combat)
    bad = deepcopy(before)
    r = bad['player']['rules']
    batch = r['autoplay_batches']['0']
    if mutation == 'missing_batch':
        r['autoplay_batches'].clear()
    elif mutation == 'missing_reservation':
        batch['cards'].clear()
    elif mutation == 'duplicate_card':
        batch['cards'] *= 2
    elif mutation == 'foreign_context':
        batch['context'] = 1
    elif mutation == 'negative_remaining':
        batch['remaining'] = -1
    elif mutation == 'boolean_remaining':
        batch['remaining'] = True
    elif mutation == 'bad_exhaust':
        batch['force_exhaust'] = 1
    elif mutation == 'missing_task':
        r['tasks'] = [t for t in r['tasks'] if t[0] != 'autoplay_take']
    elif mutation == 'duplicate_task':
        r['tasks'].append(['autoplay_take', '0'])
    elif mutation == 'wrong_phase':
        batch['stage'] = 'play'
    elif mutation == 'unowned_task':
        r['tasks'].append(['autoplay_next', '100'])
    elif mutation == 'move_reserved':
        r['tasks'].insert(0, ['exhaust', batch['cards'][0]])
    elif mutation == 'reserved_selector':
        r['selection']['source'] = batch['cards'][0]
        r['selection']['operation'] = 'discard'
    else:
        bad['schema'] = 'headless_combat_state_v31'
    with pytest.raises(ValueError):
        combat.restore(bad)
    assert saved(combat) == before


def test_nested_havoc_choice_keeps_other_reserved_cards_and_force_exhaust():
    combat = CombatEngine(cards=DEFAULT_CARDS, cards_per_turn=0,
                          deck_factory=lambda: [DEFAULT_CARDS.create(n) for n in ('havoc','defend','armaments','strike','defend')])
    combat.reset()
    p = combat.player
    cards = sorted(p.deck.all_cards(), key=lambda c: c.instance_id)
    havoc, reserved, armaments, strike, defend = cards
    p.deck.draw_pile, p.hand[:] = list(reversed(cards[:3])), cards[3:]
    push(p, ['autoplay_draw', 2, False])
    drain(p)
    assert p.pending_play and p.current_card is armaments
    assert p.deck.in_play == [reserved, havoc, armaments]
    assert set(p.rules.plays) == {havoc.instance_id, armaments.instance_id}
    assert p.rules.autoplay_batches['0']['cards'] == [reserved.instance_id]
    other = CombatEngine(cards=DEFAULT_CARDS)
    other.restore(saved(combat))
    action = ChooseCombatCard(strike.instance_id)
    combat.apply(action)
    other.apply(action)
    assert saved(other) == saved(combat)
    assert strike.upgraded and armaments in p.deck.exhaust_pile
    assert p.deck.discard_pile == [havoc, reserved]
    assert p.block == 10
    assert not p.rules.autoplay_batches and not p.deck.in_play


def test_terminal_autoplay_disposes_unplayed_reservations_without_playing_them():
    combat = CombatEngine(cards=DEFAULT_CARDS, cards_per_turn=0,
                          deck_factory=lambda: [DEFAULT_CARDS.create(n) for n in ('strike','defend')])
    combat.reset()
    p = combat.player
    cards = sorted(p.deck.all_cards(), key=lambda c: c.instance_id)
    p.deck.draw_pile = list(reversed(cards))
    combat.enemies[0].hp = 1
    push(p, ['autoplay_draw', 2, True])
    combat.resolve_external_effect()
    assert combat.done and combat.winner == 'player'
    assert p.rules.plays_finished == 1 and p.block == 0
    assert cards[0] in p.deck.exhaust_pile and cards[1] in p.deck.discard_pile
    assert not p.rules.autoplay_batches and not p.deck.in_play
    other = CombatEngine(cards=DEFAULT_CARDS)
    other.restore(saved(combat))
    assert saved(other) == saved(combat)


@pytest.mark.parametrize('mutation', ['receipt_missing', 'receipt_context', 'task_missing'])
def test_reserved_status_exhaust_requires_its_producing_event(mutation):
    row = next(r for r in FLAK['result']['rows'] if r['darkEmbrace'])
    combat, _ = prepare(row)
    push(combat.player, ['mayhem'])
    drain(combat.player)
    before = saved(combat)
    bad = deepcopy(before)
    r = bad['player']['rules']
    event = next(e for e in r['pending_events'] if e['task'][0] == 'exhaust')
    if mutation == 'receipt_missing':
        r['pending_events'].remove(event)
    elif mutation == 'receipt_context':
        event['context'] = 100
    else:
        r['tasks'].remove(event['task'])
    with pytest.raises(ValueError):
        combat.restore(bad)
    assert saved(combat) == before
