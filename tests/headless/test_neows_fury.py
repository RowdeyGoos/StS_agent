"""Native Neow's Fury choices, exact originals and private continuation."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS, CardCatalog
from game.headless.cards.operations import CardOperation
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection, EndTurn
from game.headless.core.combat import CombatEngine
from game.headless.core.native_service import COMBAT_STREAMS, NativeRandomService
from game.headless.core.resolution import start_play, drain
from game.headless.run.engine import RunEngine

ROOT = Path(__file__).parents[2]
RECORD = json.loads((ROOT / 'docs/evidence/native_neows_fury_2026_09_22.json').read_text())


def test_native_capture_binding():
    assert RECORD['userDirectoryRemoved']
    assert RECORD['pins']['sts2.dll'] == 'e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18'
    assert len(RECORD['result']['rows']) == 14
    for name, digest in RECORD['fixtureSources'].items():
        source = ROOT / 'tools/native_combat_oracle/queue_runtime' / name
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest


def saved(engine):
    return json.loads(json.dumps(engine.snapshot()))


def setup(row):
    engine = CombatEngine(cards=DEFAULT_CARDS, deck_factory=lambda: [], cards_per_turn=0)
    service = NativeRandomService(row['seed'])
    engine.native_streams = {key: service.stream(key) for key in COMBAT_STREAMS}
    engine.reset()
    p = engine.player
    identities = []
    def card(name, pile):
        c = DEFAULT_CARDS.create(name)
        p.deck._ensure_identity(c)
        identities.append(c.instance_id)
        getattr(p.deck, pile).append(c)
        return c
    for i in range(row['count']):
        card('strike' if i % 2 == 0 else 'defend', 'discard_pile')
    for _ in range(row['handCount']):
        card('defend', 'hand')
    # Full hand is an authored autoplay state, not an illegal eleven-card hand.
    fury = card('neows_fury', 'draw_pile' if row['scenario'] == 'full' else 'hand')
    if row['upgraded']:
        fury.upgrade()
    engine.enemies[0].hp = row['before']['enemyHp']
    engine.enemies[0].max_hp = 100
    return engine, fury, identities


def compared(engine, identities):
    p = engine.player
    label = lambda c: 'card.' + str(identities.index(c.instance_id))
    return dict(hand=[label(c) for c in p.hand], discard=[label(c) for c in p.deck.discard_pile],
                enemyHp=engine.enemies[0].hp, ending=p.combat_is_ending,
                selectionCounter=p.deck.selection_rng.counter)


@pytest.mark.parametrize('row', RECORD['result']['rows'], ids=lambda r:f"{r['scenario']}-{r['upgraded']}")
def test_native_choice_effects_and_json_continuation(row):
    engine, fury, identities = setup(row)
    if row['scenario'] == 'full':
        start_play(engine.player, fury, engine.enemies[0], auto=True)
        drain(engine.player)
    else:
        engine.apply(PlayCard(fury.instance_id, 0))
    selection = engine.player.rules.selection
    assert bool(selection) == bool(row['calls'])
    if selection:
        assert selection['minimum'] == row['minimum'] == 0
        assert selection['maximum'] == min(row['maximum'], row['count'])
        assert selection['candidates'] == [identities[int(ref.split('.')[1])] for ref in row['options']]
        assert ConfirmCombatSelection() in engine.legal_actions()
        actions = [ChooseCombatCard(identities[int(ref.split('.')[1])]) for ref in row['selected']]
        actions.append(ConfirmCombatSelection())
        for action in actions:
            clone = CombatEngine(cards=DEFAULT_CARDS)
            clone.restore(saved(engine))
            assert clone.legal_actions() == engine.legal_actions()
            engine.apply(action)
            clone.apply(action)
            assert saved(clone) == saved(engine)
    assert compared(engine, identities) == {k:v for k,v in row['after'].items() if k != 'play'}
    assert engine.player.deck.selection_rng.next_double() == row['selectionSuffix']
    assert engine.player.energy == (3 if row['scenario'] == 'full' else 2)
    if row['scenario'] != 'lethal':
        assert fury in engine.player.deck.exhaust_pile and not engine.player.deck.in_play


def pending_run():
    run = RunEngine(card_ids=('neows_fury', 'strike', 'strike', 'defend'))
    combat = run.start_combat(cards_per_turn=0)
    cards = list(combat.player.deck.draw_pile)
    combat.player.deck.draw_pile.clear()
    fury = next(c for c in cards if c.definition.definition_id == 'neows_fury')
    combat.player.hand.append(fury)
    combat.player.deck.discard_pile.extend(c for c in cards if c is not fury)
    run.apply(PlayCard(fury.instance_id, 0))
    return run


def test_optional_selection_toggle_bounds_illegal_actions_and_run_restore():
    run = pending_run()
    options = run.combat.player.rules.selection['candidates']
    for action in (ChooseCombatCard(options[0]), ChooseCombatCard(options[0]),
                   ChooseCombatCard(options[2]), ChooseCombatCard(options[1])):
        run.apply(action)
    assert run.combat.player.rules.selection['selected'] == [options[2], options[1]]
    before = saved(run)
    for bad in (ChooseCombatCard(options[0]), EndTurn(), PlayCard(options[1], 0)):
        with pytest.raises(ValueError):
            run.apply(bad)
        assert saved(run) == before
    clone = RunEngine()
    clone.restore(before)
    for target in (run, clone):
        target.apply(ConfirmCombatSelection())
        assert [c.instance_id for c in target.combat.player.hand] == [options[2], options[1]]
        assert target.combat.player.energy == 2
    assert saved(run) == saved(clone)


def test_native_hashset_reselection_order_and_restore():
    run = pending_run()
    a, b, c = run.combat.player.rules.selection['candidates']
    # Pinned .NET HashSet reuses removed slots rather than appending selections.
    for identity in (a, b, a, a):
        run.apply(ChooseCombatCard(identity))
    assert run.combat.player.rules.selection['selected'] == [a, b]
    for identity in (a, b):
        run.apply(ChooseCombatCard(identity))
    snapshot = saved(run)
    clone = RunEngine()
    clone.restore(snapshot)
    for target in (run, clone):
        for identity in (c, a):
            target.apply(ChooseCombatCard(identity))
        assert target.combat.player.rules.selection['selected'] == [a, c]
        target.apply(ConfirmCombatSelection())
        assert [card.instance_id for card in target.combat.player.hand] == [a, c]
    assert saved(run) == saved(clone)


@pytest.mark.parametrize('field,value', [('order_slots', ['missing']), ('free_slots', [0]),
                                       ('order_slots', [None]), ('free_slots', [True])])
def test_forged_native_order_slots_reject(field, value):
    snapshot = saved(pending_run())
    snapshot['combat']['player']['rules']['selection'][field] = value
    with pytest.raises(ValueError):
        RunEngine().restore(snapshot)


@pytest.mark.parametrize('damage', ['minimum', 'maximum', 'pile', 'source', 'effect', 'free'])
def test_forged_pending_choice_rejects(damage):
    snapshot = saved(pending_run())
    rules = snapshot['combat']['player']['rules']
    selection = rules['selection']
    if damage == 'minimum': selection['minimum'] = 1
    elif damage == 'maximum': selection['maximum'] = 3
    elif damage == 'pile': selection['candidates'] = [selection['source']]
    elif damage == 'source': selection['source'] = 'missing'
    elif damage == 'effect': selection['destination'] = 'draw_pile'
    else: selection['free'] = 'free_this_turn'
    with pytest.raises(ValueError):
        RunEngine().restore(snapshot)


def test_old_content_fingerprint_rejects_in_both_snapshot_formats():
    original = DEFAULT_CARDS.definition('neows_fury')
    old = replace(original, effects=(original.effects[0], CardOperation('random_discard_to_hand', 2, 3)))
    old_cards = CardCatalog(old if d.definition_id == 'neows_fury' else d for d in DEFAULT_CARDS.definitions)
    run = RunEngine(cards=old_cards, card_ids=('neows_fury',))
    run.start_combat()
    assert old_cards.snapshot_fingerprint() != DEFAULT_CARDS.snapshot_fingerprint()
    with pytest.raises(ValueError, match='card definitions'):
        RunEngine().restore(saved(run))
    with pytest.raises(ValueError, match='card definitions'):
        CombatEngine(cards=DEFAULT_CARDS).restore(saved(run.combat))
