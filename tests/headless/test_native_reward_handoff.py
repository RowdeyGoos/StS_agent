"""Native reward claims, offer refresh and room/act handoff boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import re

import pytest

from game.headless.potions.pools import ORDINARY_POTIONS
from game.headless.relics.base import RelicInstance
from game.headless.run import rewards, events
from game.headless.run.actions import ClaimGold, ClaimPotion, ChooseRewardCard, LeaveRewards, ChooseEventOption
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic
from game.headless.run.state import RunPhase

RECORD = json.loads((Path(__file__).parents[2] / 'docs/evidence/native_reward_handoff_2026_09_20.json').read_text())
ROWS = RECORD['result']['rows']


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def clone(run):
    other = RunEngine()
    other.restore(saved(run))
    assert saved(other) == saved(run)
    return other


def step(run, action):
    other = clone(run)
    run.apply(action)
    other.apply(action)
    assert saved(other) == saved(run)
    clone(run)


def native_id(name):
    return {'strike': 'STRIKE_IRONCLAD', 'defend': 'DEFEND_IRONCLAD'}.get(name, name.upper())


def offers(run):
    return [dict(id=native_id(n), upgrade=m['upgrade_level'],
                 enchantment=m['enchantment']['definition_id'].upper() if m['enchantment'] else None)
            for n, m in zip(run.state.pending['offers'], run.state.pending['card_modifiers'])]


@pytest.mark.parametrize('row', [r for r in ROWS if 'before' in r], ids=lambda r:f'{r["seed"]}-{r["scenario"]}')
def test_native_claims_and_relic_refresh(row):
    run = RunEngine(seed=int(row['seed']), gold=99, rng_profile='native',
                    config=RunConfig(reward_potions=ORDINARY_POTIONS))
    run.state.relics = [RelicInstance('burning_blood', run.state.allocate_item_id())]
    rewards.begin_combat_rewards(run.state, run.cards)
    assert offers(run) == row['before']
    scenario = row['scenario']
    if scenario[0].isupper():
        # The native fixture adds an authored relic reward to the generated set.
        # Acquire the same relic through the shared pickup boundary here.
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', scenario).lower()
        other = clone(run)
        add_relic(run.state, name, cards=run.cards)
        add_relic(other.state, name, cards=other.cards)
        assert saved(other) == saved(run)
        clone(run)
        relic = run.state.relics[-1]
        if row['relicCounter'] is not None:
            assert relic.counter == row['relicCounter']
    assert offers(run) == row['after']
    if scenario != 'leave':
        step(run, ClaimGold())
        index = 2 if scenario == 'last' else 0
        step(run, ChooseRewardCard(run.state.pending['offers'][index]))
        if run.state.pending['potion'] is not None:
            step(run, ClaimPotion())
    step(run, LeaveRewards())
    assert run.state.phase is RunPhase.ROUTE and run.state.pending is None
    assert run.state.gold == row['gold']
    assert [dict(id=native_id(c.definition.definition_id), upgrade=c.upgrade_level,
                 enchantment=c.enchantment.definition_id.upper() if c.enchantment else None)
            for c in run.state.deck] == row['deck']
    assert [p.definition_id.upper() for p in run.state.potions if p] == row['potions']
    for stream in ('rewards', 'niche'):
        rng = run.state.rng.stream(stream)
        assert rng.counter == row[stream + 'Counter']
        assert deepcopy(rng).next_double() == row[stream + 'Suffix']
    assert row['roomsAfterProceed'] == row['rooms'] == 1 and row['room'] == 'Map'
    assert row['canceledStillOpen'] == (scenario == 'cancel_then_first')


@pytest.mark.parametrize('row', [r for r in ROWS if r['scenario'].startswith('dummy_')], ids=lambda r:f'{r["seed"]}-{r["scenario"]}')
def test_dummy_reward_occurs_during_resume(row):
    run = RunEngine(seed=int(row['seed']), rng_profile='native', config=RunConfig())
    events.begin(run.state, 'battleworn_dummy', cards=run.cards)
    step(run, ChooseEventOption(run.state.pending['event_instance_id'], 'setting_2'))
    if row['scenario'] == 'dummy_timeout':
        from game.headless.core.actions import EndTurn
        for _ in range(3):
            step(run, EndTurn())
    else:
        other = clone(run)
        for engine in (run, other):
            for enemy in engine.combat.enemies:
                enemy.take_damage(10000, is_attack=False)
            engine.combat.resolve_external_effect()
            engine.finish_combat()
        assert saved(other) == saved(run)
    clone(run)
    assert run.state.pending['stage'] == 'resolved'
    assert [dict(id=native_id(c.definition.definition_id), upgrade=c.upgrade_level) for c in run.state.deck] == row['deck']
    rng = run.state.rng.stream('event:BATTLEWORN_DUMMY')
    assert rng.counter == row['eventCounter']
    assert deepcopy(rng).next_double() == row['eventSuffix']
    assert row['rooms'] == 1 and row['room'] == 'Event'


def test_previous_pending_reward_semantics_rejected_atomically():
    run = RunEngine(config=RunConfig())
    rewards.begin_combat_rewards(run.state, run.cards)
    before = saved(run)
    old = deepcopy(before)
    old['schema'] = 'headless_run_state_v52'
    with pytest.raises(ValueError):
        run.restore(old)
    assert saved(run) == before


@pytest.mark.parametrize('seed', ['0', '2', '42'])
def test_native_act_handoffs_preserve_hp_until_ancient(seed):
    from game.headless.run.actions import ContinueAct
    from tests.headless.test_act2_run import complete_act
    run = RunEngine.ironclad_run(seed=int(seed), rng_profile='native', last_act='glory')
    for scenario in ('act_1', 'act_2'):
        row = next(r for r in ROWS if r['seed'] == seed and r['scenario'] == scenario)
        # Synthetic victories isolate the transition from policy strength.
        run.state.max_hp = run.state.hp = 10000
        complete_act(run)
        run.state.hp = 31
        step(run, ContinueAct())
        assert run.state.act_index == row['act']
        assert run.state.hp == row['hp'] == 31
        assert len(run.state.visited_nodes) == row['floor'] == 0
        assert run.state.current_node_id is None and run.state.pending is None
        assert run.state.phase is RunPhase.ROUTE
        assert (run.graph is not None) == row['hasMap']
        assert row['room'] == 'Map' and row['rooms'] == 1


@pytest.mark.parametrize('resolved', [False, True])
def test_claim_egg_refreshes_only_unresolved_extra_offers(resolved):
    from game.headless.run.actions import ClaimRelic
    run = RunEngine(seed=2, config=RunConfig(
        reward_cards=('anger', 'sword_boomerang', 'pommel_strike'),
        reward_relics=('molten_egg',)))
    add_relic(run.state, 'white_star')
    rewards.begin_combat_rewards(run.state, run.cards, encounter_id='overgrowth_byrdonis')
    extra = run.state.pending['extra_rewards'][0]
    if resolved:
        from game.headless.run.actions import ChooseExtraReward
        step(run, ChooseExtraReward(0, None))
    before = deepcopy(extra['modifiers'])
    step(run, ClaimRelic())
    assert all(m['upgrade_level'] == 1 for m in run.state.pending['card_modifiers'])
    for name, old, new in zip(extra['offers'], before, extra['modifiers']):
        upgraded = not resolved and run.cards.definition(name).levels[0].kind == 'attack'
        assert new['upgrade_level'] == (1 if upgraded else old['upgrade_level'])


def test_pickup_refresh_does_not_reapply_owned_modifiers_or_manual_grids():
    run = RunEngine(seed=2, rng_profile='native', config=RunConfig())
    add_relic(run.state, 'wing_charm')
    add_relic(run.state, 'silver_crucible')
    rewards.begin_combat_rewards(run.state, run.cards)
    before = run.state.rng.snapshot()
    crucible = next(r for r in run.state.relics if r.definition_id == 'silver_crucible')
    used = crucible.counter
    add_relic(run.state, 'molten_egg')
    assert run.state.rng.snapshot() == before
    assert crucible.counter == used
    # Kaleidoscope's explicit card rewards never register an acquisition listener.
    add_relic(run.state, 'kaleidoscope', cards=run.cards)
    manual = deepcopy(run.state.relic_work)
    add_relic(run.state, 'fresnel_lens')
    assert run.state.relic_work == manual


def test_refresh_failure_rolls_back_relic_offers_and_rng(monkeypatch):
    from game.headless.relics import rewards as modifiers
    run = RunEngine(rng_profile='native', config=RunConfig())
    rewards.begin_combat_rewards(run.state, run.cards)
    before = saved(run)
    original = modifiers.decorate
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise ValueError('injected after modifier RNG consumption')
    monkeypatch.setattr(modifiers, 'decorate', fail)
    with pytest.raises(ValueError, match='injected'):
        add_relic(run.state, 'wing_charm')
    assert saved(run) == before


@pytest.mark.parametrize('pickup', ['molten_egg', 'dollys_mirror'])
def test_paels_wing_pickup_refreshes_waiting_orrery_and_prioritizes_nested_work(monkeypatch, pickup):
    from game.headless.generation import relics
    from game.headless.run.actions import SacrificeCardReward, ChooseRelicCard
    monkeypatch.setattr(relics, 'pull', lambda *args, **kwargs: pickup)
    run = RunEngine(seed=2, rng_profile='native', config=RunConfig())
    add_relic(run.state, 'paels_wing')
    add_relic(run.state, 'orrery', cards=run.cards)
    step(run, SacrificeCardReward())
    step(run, SacrificeCardReward())
    remaining = run.state.relic_work
    if pickup == 'dollys_mirror':
        assert remaining[0]['kind'] == 'select'
        assert any(isinstance(a, ChooseRelicCard) for a in run.legal_actions())
        remaining = remaining[1:]
    assert len(remaining) == 3
    if pickup == 'molten_egg':
        attacks = [o for w in remaining for o in w['offers'] if run.cards.definition(o['definition_id']).levels[0].kind == 'attack']
        assert attacks and all(o['upgrade_level'] == 1 for o in attacks)


def test_nested_pickup_failure_restores_suspended_factory_rewards(monkeypatch):
    from game.headless.relics import run_rules
    run = RunEngine(rng_profile='native', config=RunConfig())
    add_relic(run.state, 'orrery', cards=run.cards)
    before = saved(run)
    original = run_rules.pickup
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise ValueError('injected after nested potion rewards')
    monkeypatch.setattr(run_rules, 'pickup', fail)
    with pytest.raises(ValueError, match='injected'):
        add_relic(run.state, 'cauldron', cards=run.cards, prioritize_pickup=True)
    assert saved(run) == before


def test_native_fixture_identity_and_declared_coverage():
    import hashlib
    source = Path(__file__).parents[2] / 'tools/native_combat_oracle/queue_runtime'
    for name in ('reward_handoff.cs', 'Oracle.cs', 'run.py'):
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == RECORD['fixtureSources'][name]
    assert RECORD['userDirectoryRemoved']
    assert len(ROWS) == 48
    assert len({(r['seed'], r['scenario']) for r in ROWS}) == 48
