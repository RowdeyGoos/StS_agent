"""Replay recorded native event branch prefixes with exact JSON continuation."""
from copy import deepcopy
import re

from game.headless.cards.base import Card
from game.headless.enchantments.base import restore
from game.headless.relics.base import RelicInstance
from game.headless.relics.pools import ORDINARY_RELICS
from game.headless.potions.pools import ORDINARY_POTIONS
from game.headless.run import events
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run.deck import add_card
from game.headless.run.inventory import add_relic, add_potion
from game.headless.run.actions import ClaimGold, ClaimPotion, ClaimRelic, ChooseRewardCard, ChooseExtraReward, LeaveRewards
from game.headless.run.actions import ChooseEventOption, ChooseEventCard, ChooseRelicCard, ConfirmRelicSelection, ChooseRelicReward, ChooseAncientRelic
from tests.headless.test_native_event_inventory import boundary as inventory_boundary, card_record as inventory_card_record
from tests.headless.test_remaining_events_neow import clone
import json


def card_record(card):
    return dict(inventory_card_record(card), eventData=dict(card.event_data) if card.event_data else None)


def boundary(run):
    return dict(inventory_boundary(run), hp=run.combat.player.hp if run.combat else run.state.hp, deck=[card_record(c) for c in run.state.deck])


def step(run, action):
    saved = json.loads(json.dumps(run.snapshot()))
    legal = run.legal_actions()
    run.restore(saved)
    assert json.loads(json.dumps(run.snapshot())) == saved and run.legal_actions() == legal
    assert action in legal
    run.apply(action)


def setup(row):
    run = RunEngine(seed=int(row['seed']), hp=61, gold=500, rng_profile='native',
                    config=RunConfig(ascension=row['ascension'], reward_relics=ORDINARY_RELICS, reward_potions=ORDINARY_POTIONS))
    if row['eventName'] == 'Neow':
        run = RunEngine.ironclad_act1(seed=int(row['seed']), ascension=row['ascension'])
        run.state.hp, run.state.gold = 61, 500
    if row['eventName'] != 'Neow':
        run.state.relics = [RelicInstance('burning_blood', run.state.allocate_item_id())]
    for name in (('inflame', 'offering') + ('lantern_key',) * (2 - row.get('variant', 0)) if row['eventName'] == 'WarHistorianRepy' else ('inflame', 'offering')):
        add_card(run.state, run.cards.definition(name))
    relics = ['anchor', 'bag_of_preparation', 'bronze_scales', 'the_boot', 'hand_drill']
    if row['enhanced']:
        relics += ['molten_egg', 'toxic_egg', 'frozen_egg', 'wing_charm', 'bing_bong']
    for name in relics:
        add_relic(run.state, name, cards=run.cards)
    for name in ('foul_potion', 'fire_potion'):
        add_potion(run.state, name)
    run.state.act_index = row.get('actIndex', 0)
    assert boundary(run) == row['before']
    name = re.sub(r'(?<!^)(?=[A-Z])', '_', row['eventName']).lower()
    if name == 'neow':
        from game.headless.run import ancient
        ancient.begin(run.state, profile=ancient.PROFILE, cards=run.cards)
    else:
        events.begin(run.state, name, cards=run.cards)
    saved = json.loads(json.dumps(run.snapshot()))
    run.restore(saved)
    return run, name


def key_name(key):
    name = re.sub(r'(?<=[a-z])(?=[A-Z])', '_', key.split('.')[-1]).lower()
    return {'bargain_bin': 'bargain', 'featured_item': 'featured', 'mystery_box': 'mystery'}.get(name, name)


def choice(run, key, index=None):
    name = key_name(key)
    if run.state.pending['kind'] == 'ancient':
        return ChooseAncientRelic(name)
    actions = [a for a in run.legal_actions() if isinstance(a, ChooseEventOption)]
    if run.state.pending['definition_id'] == 'the_future_of_potions':
        name = f'trade_{index}'
    if run.state.pending['definition_id'] == 'tablet_of_truth' and name.startswith('decipher'):
        name = next(a.option_id for a in actions if a.option_id.startswith('decipher'))
    if run.state.pending['definition_id'] == 'slippery_bridge':
        name = next(a.option_id for a in actions if a.option_id.startswith(name.split('_')[0] + '_'))
    return next(a for a in actions if a.option_id == name)


def offers(run, names, modifiers):
    result = []
    for index, name in enumerate(names):
        saved = modifiers[index] if isinstance(modifiers, list) else modifiers[name]
        card = Card(run.cards.definition(name), upgrade_level=saved['upgrade_level'])
        card.enchantment = restore(saved['enchantment'])
        result.append(card_record(card))
    return result


def native_defaults(run):
    while run.state.relic_work and run.state.relic_work[0]['kind'] == 'bundle':
        # Native FromChooseABundleScreen explicitly picks bundle zero in TestMode.
        step(run, ChooseRelicReward(0))


def selections(run, records):
    for record in records:
        if record['kind'] == 'bundle':
            step(run, ChooseRelicReward(record['selected']))
            continue
        native_defaults(run)
        if record['kind'] == 'source_boundary':
            continue
        if record['kind'] == 'crystal_start':
            context = run.state.pending['data']['pages'][-1]['context']
            assert context['board'] == record['board']
            assert context['remaining'] == record['remaining']
            continue
        if record['kind'] == 'crystal_click':
            from game.headless.events.minigames import cleared
            context = run.state.pending['data']['pages'][-1]['context']
            option = f"{record['tool']}_{record['x']}_{record['y']}"
            expected, _ = cleared(context, option)
            assert expected == record['board']
            assert context['remaining'] - 1 == record['remaining']
            step(run, ChooseEventOption(run.state.pending['event_instance_id'], option))
            continue
        if (run.state.pending or {}).get('kind') == 'reward' and not run.state.relic_work:
            pending = run.state.pending
            if record['kind'] == 'claim':
                kind = {'PotionReward': 'potion', 'RelicReward': 'relic', 'GoldReward': 'gold', 'SpecialCardReward': 'special_card'}[record['reward']]
                content = record.get('content', 'LANTERN_KEY')
                if kind == 'gold':
                    assert pending['gold'] == content
                    if record['claimed']: step(run, ClaimGold())
                elif pending.get(kind) and pending[kind].upper() == content and not pending[kind + '_claimed']:
                    if record['claimed']: step(run, ClaimPotion() if kind == 'potion' else ClaimRelic())
                else:
                    j = next(j for j, r in enumerate(pending['extra_rewards']) if not r['resolved'] and r['kind'] == kind and r['offers'][0].upper() == content)
                    step(run, ChooseExtraReward(j, pending['extra_rewards'][j]['offers'][0] if record['claimed'] else None))
            else:
                assert record['kind'] == 'reward'
                index = record['selected']
                if not pending['card_resolved'] and offers(run, pending['offers'], pending['card_modifiers']) == record['offers']:
                    step(run, next(a for a in run.legal_actions() if isinstance(a, ChooseRewardCard) and a.definition_id == (pending['offers'][index] if index is not None else None) and a.offer_index in (None, index)))
                else:
                    j = next(j for j, r in enumerate(pending['extra_rewards']) if not r['resolved'] and r['kind'] == 'special_card' and [dict(id=r['offers'][0].upper(), upgrade=0, enchantment=None, eventData=None)] == record['offers'])
                    step(run, ChooseExtraReward(j, pending['extra_rewards'][j]['offers'][0] if index is not None else None))
            continue
        if record['kind'] == 'claim':
            if run.state.relic_work:
                assert run.state.relic_work[0]['kind'] in ('relic_reward', 'potion_reward')
                assert run.state.relic_work[0]['offers'][0].upper() == record['content']
                step(run, ChooseRelicReward(0 if record['claimed'] else None))
                continue
            stage = run.state.pending['stage']
            if stage == 'event_rewards':
                batch = run.state.pending['data']['active']['rewards']
                kind = {'PotionReward': 'potion', 'RelicReward': 'relic', 'GoldReward': 'gold', 'SpecialCardReward': 'special_card'}[record['reward']]
                i = next(i for i, r in enumerate(batch) if not r['resolved'] and r['kind'] == kind and (r['modifiers']['gold'] if kind == 'gold' else r['offers'][0].upper()) == record['content'])
                option = f'reward_{i}_0' if record['claimed'] else f'skip_{i}'
            elif stage == 'potion_rewards' and 'rewards' in run.state.pending['data']:
                if not record['claimed']:
                    continue
                option = next(a.option_id for a in run.legal_actions() if isinstance(a, ChooseEventOption) and a.option_id.startswith('claim'))
            elif not record['claimed']:
                option = 'skip'
            else:
                option = next(a.option_id for a in run.legal_actions() if isinstance(a, ChooseEventOption) and a.option_id.startswith('claim'))
            step(run, ChooseEventOption(run.state.pending['event_instance_id'], option))
            continue
        indices = record['selected'] if isinstance(record['selected'], list) else [record['selected']]
        if record['kind'] == 'grid' and all(i >= 0 for i in record['deckIndices']):
            assert [card_record(run.state.deck[i]) for i in record['deckIndices']] == record['offers']
            ids = [run.state.deck[record['deckIndices'][i]].instance_id for i in indices]
            for identity in ids:
                action = ChooseRelicCard(identity) if run.state.relic_work else ChooseEventCard(run.state.pending['event_instance_id'], identity)
                assert action in run.legal_actions()
                step(run, action)
            if run.state.relic_work and ConfirmRelicSelection() in run.legal_actions():
                step(run, ConfirmRelicSelection())
        elif run.state.relic_work:
            work = run.state.relic_work[0]
            assert work['kind'] in ('card_reward', 'card_grid'), work
            actual = [dict(id=o['definition_id'].upper(), upgrade=o['upgrade_level'],
                           enchantment=dict(id=o['enchantment']['definition_id'].upper(), amount=o['enchantment']['amount']) if o.get('enchantment') else None, eventData=None) for o in work['offers']]
            assert actual == record['offers']
            for i in indices:
                step(run, ChooseRelicReward(i))
            if ConfirmRelicSelection() in run.legal_actions():
                step(run, ConfirmRelicSelection())
        else:
            active = run.state.pending['data']['active']
            if run.state.pending['stage'] == 'event_rewards':
                j = next(j for j, r in enumerate(active['rewards']) if not r['resolved'] and r['kind'] == 'card' and offers(run, r['offers'], r['modifiers']) == record['offers'])
                reward = active['rewards'][j]
                assert offers(run, reward['offers'], reward['modifiers']) == record['offers']
                for i in indices:
                    step(run, ChooseEventOption(run.state.pending['event_instance_id'], f'reward_{j}_{i}' if i is not None else f'skip_{j}'))
            else:
                assert offers(run, active['offers'], active['modifiers']) == record['offers']
                for i in indices:
                    step(run, ChooseEventOption(run.state.pending['event_instance_id'], f'card_{i}' if i is not None else 'skip'))


def replay(row, cache=None):
    key = (row['eventName'], row['seed'], row['ascension'], row['enhanced'], row.get('variant', 0), row.get('selectionVariant', 0), tuple(row['path']))
    parent = (*key[:-1], key[-1][:-1])
    if cache is not None and row['path'] and parent in cache:
        run = RunEngine()
        run.restore(cache[parent])
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', row['eventName']).lower()
        traces = row['trace'][-2:] if row['trace'] and row['trace'][-1]['choice'] == 'NATIVE_COMBAT_RESUME' else row['trace'][-1:]
    else:
        run, name = setup(row)
        traces = row['trace']
    for trace in traces:
        if trace['choice'] == 'NATIVE_COMBAT_RESUME':
            # Both sides author a finished child to test the native reward/resume
            # boundary independently of a combat policy. Timeout has no kill.
            for enemy in run.combat.enemies:
                enemy.hp = 0
                if trace['timedOut']:
                    enemy.remaining_turns = 0
                    enemy.timed_out = True
            run.combat.resolve_external_effect()
            run.finish_combat()
        else:
            step(run, choice(run, trace['choice'], trace['index']))
        selections(run, trace['selections'])
        native_defaults(run)
        if trace['choice'] == 'NATIVE_COMBAT_RESUME' and LeaveRewards() in run.legal_actions():
            step(run, LeaveRewards())
        finish = next((a for a in run.legal_actions() if isinstance(a, ChooseEventOption) and a.option_id == 'finish_rewards'), None)
        if finish is not None:
            step(run, finish)
        assert boundary(run) == trace['state'], trace['choice']
    assert boundary(run) == row['state']
    if not row['finished']:
        actual = [a.option_id if isinstance(a, ChooseEventOption) else a.definition_id for a in run.legal_actions() if isinstance(a, (ChooseEventOption, ChooseAncientRelic))]
        expected = [key_name(key) for key, locked in zip(row['options'], row['locked']) if not locked]
        if name == 'the_future_of_potions':
            expected = [f'trade_{i}' for i in range(len(expected))]
        if name == 'tablet_of_truth':
            expected = [f'decipher_{run.state.pending["data"]["count"] + 1}' if k.startswith('decipher') else k for k in expected]
        if name != 'slippery_bridge':
            assert set(actual) == set(expected), (actual, expected)
    else:
        assert run.state.hp <= 0 or run.state.pending is None or run.state.pending.get('stage') == 'resolved' or row.get('combat') and run.combat is not None
    for rng_key, stream in [('eventRng', 'event:' + name.upper()), ('rewards', 'rewards'), ('niche', 'niche'), ('transformations', 'transformations'), ('shops', 'shops')]:
        rng = run.state.rng.stream(stream)
        assert rng.counter == row['rng'][rng_key]['counter'], (rng_key, rng.counter, row['rng'][rng_key])
        assert deepcopy(rng).next_double() == row['rng'][rng_key]['suffix'], rng_key
    if cache is not None:
        cache[key] = run.snapshot()
    return run
