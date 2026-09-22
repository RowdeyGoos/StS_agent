"""Physical duplicate reward choices and native Slippery Bridge eligibility."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run import rewards, events
from game.headless.run.actions import ChooseRewardCard, ChooseExtraReward, RerollCardReward, SacrificeCardReward, ChooseEventOption
from game.headless.relics.run_rules import counter, owned

POOL = ('inflame', 'barricade', 'rupture')


def clone(run):
    other = RunEngine()
    other.restore(json.loads(json.dumps(run.snapshot())))
    assert other.legal_actions() == run.legal_actions()
    return other


def start(profile='native', *relics):
    run = RunEngine(seed=2, rng_profile=profile, config=RunConfig(reward_cards=POOL))
    for name in ('lasting_candy', *relics):
        run.obtain_relic(name)
    rewards.begin_combat_rewards(run.state, run.cards)
    return run


@pytest.mark.parametrize('profile', ['native', 'fixture'])
@pytest.mark.parametrize('extra', [False, True])
def test_duplicate_offers_can_be_chosen_independently_after_restore(profile, extra):
    run = start(profile, *(['prayer_wheel'] if extra else []))
    reward = run.state.pending['extra_rewards'][0] if extra else run.state.pending
    offers = reward['offers']
    positions = [i for i, n in enumerate(offers) if n == offers[-1]]
    assert len(positions) == 2
    modifiers = reward['modifiers' if extra else 'card_modifiers']
    modifiers[positions[0]]['upgrade_level'] = 0
    modifiers[positions[1]]['upgrade_level'] = 1
    modifiers[positions[1]]['enchantment'] = {'definition_id': 'swift', 'amount': 1, 'triggered': False, 'extra_damage': 0}
    for i in positions:
        copy = clone(run)
        action = ChooseExtraReward(0, offers[i], i) if extra else ChooseRewardCard(offers[i], i)
        assert action in copy.legal_actions()
        result = copy.apply(action)
        assert result.upgrade_level == modifiers[i]['upgrade_level']
        assert (result.enchantment is not None) == (i == positions[1])
        assert sum(c.definition.definition_id == offers[i] for c in copy.state.deck) == 1
        clone(copy)
    ambiguous = ChooseExtraReward(0, offers[-1]) if extra else ChooseRewardCard(offers[-1])
    assert ambiguous not in run.legal_actions()
    before = run.snapshot()
    with pytest.raises(ValueError):
        run.apply(ambiguous)
    assert run.snapshot() == before


@pytest.mark.parametrize('extra', [False, True])
def test_duplicate_reroll_and_sacrifice_restore(extra):
    run = start('native', 'prayer_wheel', 'driftwood', 'paels_wing')
    index = 0 if extra else -1
    run.apply(RerollCardReward(index))
    reward = run.state.pending['extra_rewards'][0] if extra else run.state.pending
    assert len(reward['offers']) == 4 and len(set(reward['offers'])) == 3
    clone(run)
    run.apply(SacrificeCardReward(index))
    assert reward['resolved' if extra else 'card_resolved']
    clone(run)


@pytest.mark.parametrize('change', ['length','mapping','missing_owner','attack_duplicate','three_copies','bad_modifier','old_schema'])
def test_malformed_duplicate_rewards_reject_atomically(change):
    run = start()
    bad = deepcopy(run.snapshot())
    p = bad['state']['pending']
    if change == 'length': p['card_modifiers'].pop()
    elif change == 'mapping': p['card_modifiers'] = dict(zip(p['offers'], p['card_modifiers']))
    elif change == 'missing_owner': bad['state']['relics'] = []
    elif change == 'attack_duplicate': p['offers'][0] = p['offers'][-1] = 'anger'
    elif change == 'three_copies': p['offers'][0] = p['offers'][1] = p['offers'][-1]
    elif change == 'bad_modifier': p['card_modifiers'][-1]['upgrade_level'] = -1
    else: bad['schema'] = 'headless_run_state_v44'
    before = run.snapshot()
    with pytest.raises(ValueError): run.restore(bad)
    assert run.snapshot() == before


@pytest.mark.parametrize('position', [-1, 10, True, '3'])
def test_invalid_offer_positions_do_not_mutate(position):
    run = start()
    before = run.snapshot()
    with pytest.raises(ValueError):
        rewards.choose_card(run.state, run.cards, run.state.pending['offers'][-1], position)
    assert run.snapshot() == before


@pytest.mark.parametrize('profile', ['native', 'fixture'])
def test_bridge_foreign_basics_and_all_eternal_keywords(profile):
    run = RunEngine(seed=2, rng_profile=profile, card_ids=('strike_silent', 'defend_defect', 'pommel_strike', 'greed', 'ascenders_bane'))
    events.begin(run.state, 'slippery_bridge')
    mapping = {c.instance_id: c for c in run.state.deck}
    assert mapping[run.state.pending['data']['offers'][0]].definition.definition_id == 'pommel_strike'
    for i in range(7):
        other = clone(run)
        action = ChooseEventOption(run.state.pending['event_instance_id'], f'hold_on_{i}')
        run.apply(action); other.apply(action)
        assert run.snapshot() == other.snapshot()
        assert not mapping[run.state.pending['data']['offers'][-1]].spec.eternal
    clone(run)


@pytest.mark.parametrize('deck', [(), ('greed',), ('ascenders_bane',)])
def test_bridge_without_removable_cards_is_unavailable_and_entry_is_atomic(deck):
    from game.headless.events.catalog import EVENTS
    run = RunEngine(seed=2, rng_profile='native', card_ids=deck)
    assert not EVENTS['slippery_bridge'].is_allowed({'floor': 10, 'transformable_cards': 0})
    before = run.snapshot()
    with pytest.raises(ValueError, match='removable card'):
        events.begin(run.state, 'slippery_bridge')
    assert run.snapshot() == before


VECTORS = json.loads((Path(__file__).parents[1] / 'fixtures/headless_native_reward_edge_vectors.json').read_text())


@pytest.mark.parametrize('row', VECTORS['rows'], ids=lambda r: f"{r['seed']}-act{r['act']}-{r['mode']}-{r['poolMode']}")
def test_native_factory_and_reward_hooks_match_physical_offers(row):
    from game.headless.generation.odds import card_offers
    from game.headless.relics.rewards import combat_modifiers
    run = RunEngine(seed=row['seed'], rng_profile='native')
    # Explicit isolated native context: no campaign/history is claimed by this fixture.
    run.state.act_index = row['act']
    run.obtain_relic('lasting_candy')
    if row['mode'] != 'candy': run.obtain_relic(row['mode'])
    offers, upgrades = card_offers(run.state, run.cards, row['pool'], mode='base')
    modifiers = combat_modifiers(run.state, run.cards, offers, row['pool'], upgraded=upgrades)
    actual = [dict(id=n, upgrade=m['upgrade_level'], enchantment=None if m['enchantment'] is None else m['enchantment']['definition_id']) for n,m in zip(offers, modifiers)]
    assert actual == row['offers']
    assert run.state.rng.request_count('rewards') == row['counter']
    assert run.state.rng.double('rewards') == row['suffix']
    assert run.state.rng.request_count('niche') == row['nicheCounter']
    assert run.state.rng.double('niche') == row['nicheSuffix']
    assert run.state.generation_odds['card_offset'] == row['offset']
