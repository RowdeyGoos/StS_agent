"""Native event choices, physical deck mutations and inventory/reward interaction."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import pytest

from game.headless.cards.base import Card
from game.headless.enchantments.base import enchant, restore
from game.headless.relics.base import RelicInstance
from game.headless.run import events
from game.headless.run.actions import ChooseEventOption, ChooseEventCard, LeaveEvent, DiscardPotion
from game.headless.run.config import RunConfig
from game.headless.run.deck import add_card
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic, add_potion
from tests.headless.test_remaining_events_neow import clone, step, option

ROOT = Path(__file__).parents[2]
RECORD = json.loads((ROOT / 'docs/evidence/native_event_inventory_2026_09_20.json').read_text())
ROWS = RECORD['result']['rows']


def native_id(name):
    return {'strike': 'STRIKE_IRONCLAD', 'defend': 'DEFEND_IRONCLAD'}.get(name, name.upper())


def card_record(card):
    return dict(id=native_id(card.definition.definition_id), upgrade=card.upgrade_level,
                enchantment=dict(id=card.enchantment.definition_id.upper(), amount=card.enchantment.amount)
                if card.enchantment else None)


def boundary(run):
    state = run.state
    return dict(hp=state.hp, maxHp=state.max_hp, gold=state.gold,
                deck=[card_record(c) for c in state.deck],
                relics=[r.definition_id.upper() for r in state.relics],
                potions=[p.definition_id.upper() if p else None for p in state.potions])


@pytest.mark.parametrize('row', ROWS, ids=lambda r: f'{r["eventName"]}-{r["optionIndex"]}-s{r["seed"]}-a{r["ascension"]}-enhanced{r["enhanced"]}')
def test_native_event_inventory(row):
    run = RunEngine(seed=int(row['seed']), hp=31, gold=250, rng_profile='native',
                    config=RunConfig(ascension=row['ascension']))
    run.state.relics = [RelicInstance('burning_blood', run.state.allocate_item_id())]
    add_card(run.state, run.cards.definition('inflame'))
    for i in (0, 5):
        run.state.deck[i].upgrade()
    name = re.sub(r'(?<!^)(?=[A-Z])', '_', row['eventName']).lower()
    relics = ['molten_egg', 'toxic_egg', 'frozen_egg', 'wing_charm'] if row['enhanced'] else []
    if name == 'the_future_of_potions' and row['ascension'] >= 4:
        relics.append('potion_belt')
    if name == 'tea_master' and row['enhanced']:
        relics.append(('bone_tea', 'ember_tea', 'tea_of_discourtesy')[row['optionIndex']])
    for relic in relics:
        add_relic(run.state, relic, cards=run.cards)
    if row['enhanced']:
        enchant(run.state.deck[0], 'slither', 1)
    if name == 'the_future_of_potions':
        for potion in ('fire_potion', 'ashwater', 'soldiers_stew'):
            add_potion(run.state, potion)
    assert boundary(run) == row['before']
    selections = [run.state.deck[i].instance_id for i in row['selection']]
    events.begin(run.state, name, cards=run.cards)
    clone(run)
    choices = [a for a in run.legal_actions() if isinstance(a, ChooseEventOption)]
    expected = [f'trade_{i}' for i in range(3)] if name == 'the_future_of_potions' else [c.lower() for c in row['choices']]
    assert [a.option_id for a in choices] == expected
    if name == 'the_future_of_potions':
        assert not any(isinstance(a, DiscardPotion) for a in run.legal_actions())
    step(run, choices[row['optionIndex']])
    for identity in selections:
        if run.state.pending['stage'] == 'select_card':
            step(run, ChooseEventCard(run.state.pending['event_instance_id'], identity))
    if row['rewardOffers']:
        active = run.state.pending['data']['active']
        offers = []
        for card_id in active['offers']:
            modifiers = active['modifiers'][card_id]
            card = Card(run.cards.definition(card_id), upgrade_level=modifiers['upgrade_level'])
            if modifiers['enchantment']:
                card.enchantment = restore(modifiers['enchantment'])
            offers.append(card_record(card))
        assert [offers] == row['rewardOffers']
        step(run, option(run, 'card_0'))
    assert run.state.pending['stage'] == 'resolved'
    assert boundary(run) == row['state']
    assert row['canRemovePotions']
    if name == 'the_future_of_potions':
        assert any(isinstance(a, DiscardPotion) for a in run.legal_actions())
    for key, stream in [('eventRng', 'event:' + name.upper()), ('rewards', 'rewards'),
                        ('niche', 'niche'), ('transformations', 'transformations')]:
        rng = run.state.rng.stream(stream)
        assert rng.counter == row['rng'][key]['counter'], key
        assert deepcopy(rng).next_double() == row['rng'][key]['suffix'], key
    step(run, LeaveEvent(run.state.pending['event_instance_id']))


def test_native_event_inventory_capture_binding():
    assert len(ROWS) == 144
    assert RECORD['userDirectoryRemoved']
    # The original capture retains its original runner identity. The current
    # complete harness is freshly bound by the event branch regression report.
    path = 'event_inventory.cs'
    assert hashlib.sha256((ROOT / 'tools/native_combat_oracle/queue_runtime' / path).read_bytes()).hexdigest() == RECORD['fixtureSources'][path]


def test_old_transform_semantics_rejected_atomically():
    run = RunEngine()
    before = run.snapshot()
    old = deepcopy(before)
    old['schema'] = 'headless_run_state_v61'
    with pytest.raises(ValueError):
        run.restore(old)
    assert run.snapshot() == before


@pytest.mark.parametrize('event,branch', [('morphic_grove', 'group'), ('whispering_hollow', 'hug'),
                                         ('symbiote', 'kill_with_fire')])
def test_transform_continuation_with_bing_bong(event, branch):
    # Two retained duplicates distinguish physical identity from definition;
    # the other originals must remain ahead of each replacement/clone pair.
    run = RunEngine(card_ids=['strike', 'strike', 'defend', 'bash'], gold=250)
    add_relic(run.state, 'bing_bong', cards=run.cards)
    originals = [c.instance_id for c in run.state.deck]
    events.begin(run.state, event, cards=run.cards)
    step(run, option(run, branch))
    while run.state.pending['stage'] == 'select_card':
        identity = run.state.pending['data']['eligible'][0]
        step(run, ChooseEventCard(run.state.pending['event_instance_id'], identity))
    remaining = [c.instance_id for c in run.state.deck if c.instance_id in originals]
    assert [c.instance_id for c in run.state.deck[:len(remaining)]] == remaining
    new = run.state.deck[len(remaining):]
    assert len(new) % 2 == 0 and new
    for first, second in zip(new[::2], new[1::2]):
        assert first.instance_id != second.instance_id
        assert card_record(first) == card_record(second)
    clone(run)


@pytest.mark.parametrize('bing_bong', [False, True])
def test_hatching_appends_each_replacement_and_clone(bing_bong):
    from game.headless.run import rest_site
    from game.headless.run.actions import Hatch
    run = RunEngine(card_ids=['byrdonis_egg', 'strike', 'byrdonis_egg', 'defend'])
    if bing_bong:
        add_relic(run.state, 'bing_bong', cards=run.cards)
    kept = [card_record(run.state.deck[i]) for i in (1, 3)]
    rest_site.begin_rest_site(run.state)
    step(run, Hatch())
    assert [card_record(c) for c in run.state.deck[:2]] == kept
    assert [c.definition.definition_id for c in run.state.deck[2:]] == ['byrd_swoop'] * (4 if bing_bong else 2)
    before = run.snapshot()
    bad = deepcopy(before)
    bad['state']['deck'][0], bad['state']['deck'][-1] = bad['state']['deck'][-1], bad['state']['deck'][0]
    with pytest.raises(ValueError):
        run.restore(bad)
    assert run.snapshot() == before


@pytest.mark.parametrize('bing_bong', [False, True])
def test_partial_multi_transform_preserves_append_order(bing_bong):
    run = RunEngine(seed=3, card_ids=['strike', 'strike', 'defend', 'bash'])
    if bing_bong:
        add_relic(run.state, 'bing_bong', cards=run.cards)
    events.begin(run.state, 'trial', cards=run.cards)
    step(run, option(run, 'accept'))
    assert run.state.pending['data']['pages'][-1]['context']['accused'] == 'nondescript'
    step(run, option(run, 'innocent'))
    ids = list(run.state.pending['data']['eligible'])
    step(run, ChooseEventCard(0, ids[0]))
    assert run.state.pending['stage'] == 'select_card'
    before = run.snapshot()
    bad = deepcopy(before)
    bad['state']['deck'].insert(0, bad['state']['deck'].pop())
    with pytest.raises(ValueError):
        run.restore(bad)
    assert run.snapshot() == before
    step(run, ChooseEventCard(0, ids[1]))


def test_updated_native_harness_preserves_all_ten_campaign_results():
    report = json.loads((ROOT / 'docs/evidence/native_event_campaign_regressions_2026_09_20.json').read_text())
    assert len(report['runs']) == 10
    assert report['fixtureSources'] == RECORD['fixtureSources']
    for row in report['runs']:
        raw = (ROOT / row['baseline']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row['baselineSha256']
        result = json.loads(raw)['result']
        assert hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest() == row['resultSha256']
        assert row['userDirectoryRemoved'] and row['resultMatchesRetained']
        assert row['exitCode'] == row['stderrBytes'] == 0
