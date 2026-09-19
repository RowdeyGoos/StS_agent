"""Glory native map vectors and three-act campaign/Architect continuation."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from game.headless.run.engine import RunEngine
from game.headless.run.actions import ContinueAct, ChooseNode, ChooseEventOption, LeaveRewards
from game.headless.run.state import RunPhase
from game.headless.core.native_service import NativeRandomService
from game.headless.map.standard import generate_map, GLORY_PROFILE
from game.headless.generation.room_pools import REGION_POOLS, SHARED_EVENTS
from tests.headless.test_act2_run import saved, clone, step, win, complete_act

VECTORS = json.loads((Path(__file__).parents[1] / 'fixtures/headless_native_glory_map_vectors.json').read_text())


@pytest.mark.parametrize('row', VECTORS['rows'], ids=lambda r:r['seed'])
def test_glory_map_matches_native_geometry_and_rng(row):
    rng = NativeRandomService(row['seed'])
    graph = generate_map(rng, act='glory', event_pool=(*REGION_POOLS['glory'][3], *SHARED_EVENTS))
    kinds = {'Monster':'combat', 'Elite':'elite', 'Boss':'boss', 'RestSite':'rest', 'Treasure':'treasure', 'Shop':'shop', 'Unknown':'unknown'}
    actual = [dict(coord=[n.row,n.column], kind=n.kind, children=sorted([[graph.node(i).row,graph.node(i).column] for i in n.next_node_ids])) for n in graph.nodes]
    assert actual == [dict(n, kind=kinds[n['kind']]) for n in row['map']['nodes']]
    assert [[graph.node(i).row,graph.node(i).column] for i in graph.entry_node_ids] == row['map']['starts']
    assert rng.request_count('act3.map') == row['map']['counter']
    assert rng.double('act3.map') == row['map']['suffix']
    assert rng.request_count('act2.map') == rng.request_count('act1.map') == 0


@pytest.fixture(scope='module')
def hive_completed_snapshot():
    run = RunEngine.ironclad_run(seed=2)
    run.state.max_hp = run.state.hp = 10000
    complete_act(run)
    run.apply(ContinueAct())
    complete_act(run)
    return saved(run)


def from_snapshot(data):
    run = RunEngine(); run.restore(deepcopy(data)); return run


def test_glory_transition_reuses_startup_queues_then_heals_at_ancient(hive_completed_snapshot):
    run = from_snapshot(hive_completed_snapshot)
    old = deepcopy(run.state)
    run.state.hp = 7
    step(run, ContinueAct())
    s = run.state
    assert s.act_index == 2 and s.config.act == 'glory' and len(s.completed_acts) == 2
    assert s.hp == 7 and not s.visited_nodes and s.combats_completed == old.combats_completed
    assert s.rng.request_count('up_front') == old.rng.request_count('up_front')
    assert len(s.encounter_progression.normal_queue) == 13 and len(s.encounter_progression.elite_queue) == 15
    assert run.graph.generation == GLORY_PROFILE
    ancient = old.initialization['acts'][2]['ancient']
    assert run.graph.node('act3.ancient').event_id == ancient
    step(run, ChooseNode('act3.ancient'))
    assert s.hp == s.max_hp and s.pending['definition_id'] == ancient


@pytest.mark.parametrize('first_act', ['overgrowth','underdocks'])
@pytest.mark.parametrize('profile', ['native','fixture'])
def test_three_acts_and_architect_with_restored_decisions(first_act, profile):
    run = RunEngine.ironclad_run(seed=2, first_act=first_act, rng_profile=profile)
    run.state.max_hp = run.state.hp = 10000
    for act in (1,2,3):
        complete_act(run, verify=True)
        assert run.state.act_completion.act == act
        assert run.legal_actions() == (ContinueAct(),)
        step(run, ContinueAct())
    assert run.state.phase is RunPhase.ROOM and run.state.pending['definition_id'] == 'the_architect'
    assert len(run.state.completed_acts) == 2
    before = run.state.visited_room_count
    step(run, ChooseEventOption(run.state.epilogue_event_id, 'proceed'))
    assert run.state.phase is RunPhase.VICTORY and not run.legal_actions()
    assert run.state.visited_room_count == before and run.state.act_completion.act == 3
    clone(run)


@pytest.fixture(scope='module')
def glory_completed_snapshot(hive_completed_snapshot):
    run = from_snapshot(hive_completed_snapshot)
    run.apply(ContinueAct())
    complete_act(run)
    return saved(run)


def test_architect_has_no_extra_floor_or_heal_but_runs_room_hooks(glory_completed_snapshot):
    from game.headless.run.inventory import add_relic
    run = from_snapshot(glory_completed_snapshot)
    add_relic(run.state, 'maw_bank', cards=run.cards)
    run.state.hp = 7
    previous = saved(run)
    floor, gold = run.state.visited_room_count, run.state.gold
    step(run, ContinueAct())
    assert run.state.hp == 7 and run.state.gold == gold + 12
    assert run.state.visited_room_count == floor
    assert run.state.visited_nodes == previous['state']['visited_nodes']
    assert run.state.combats_completed == previous['state']['combats_completed']
    step(run, ChooseEventOption(run.state.epilogue_event_id, 'proceed'))
    assert run.state.hp == 7 and run.state.phase is RunPhase.VICTORY
    with pytest.raises(ValueError): run.apply(ContinueAct())


@pytest.mark.parametrize('corrupt', [
    lambda s: s['state']['completed_acts'].pop(),
    lambda s: s['state']['completed_acts'][1]['encounter_progression']['normal_queue'].reverse(),
    lambda s: s['state']['completed_acts'][1].__setitem__('act','glory'),
    lambda s: s['state']['completed_acts'][1]['graph']['nodes'][0].__setitem__('event_id','pael'),
    lambda s: s['state']['config'].__setitem__('act','hive'),
    lambda s: s['state']['event_progression'].__setitem__('profile','native_hive_events_all_unlocked_v1'),
    lambda s: s['graph']['nodes'][0].__setitem__('event_id','pael'),
    lambda s: s['state'].__setitem__('combats_completed',0),
])
def test_corrupt_glory_history_is_rejected_atomically(hive_completed_snapshot, corrupt):
    run = from_snapshot(hive_completed_snapshot); run.apply(ContinueAct())
    before = saved(run); bad = deepcopy(before); corrupt(bad)
    with pytest.raises(ValueError): run.restore(bad)
    assert saved(run) == before


@pytest.mark.parametrize('phase', ['room','victory'])
@pytest.mark.parametrize('corrupt', [
    lambda s: s['state'].__setitem__('epilogue_event_id',None),
    lambda s: s['state'].__setitem__('epilogue_event_id',-1),
    lambda s: s['state'].__setitem__('epilogue_event_id',True),
    lambda s: s['state'].__setitem__('act_completion',None),
    lambda s: s['state']['act_completion'].__setitem__('boss_encounter_id','hive_kaiser_crab'),
    lambda s: s['state']['config'].__setitem__('campaign',['overgrowth','hive']),
    lambda s: s['state']['completed_acts'][1]['visited_nodes'].pop(),
])
def test_epilogue_requires_completed_campaign_and_owned_event(glory_completed_snapshot, phase, corrupt):
    run = from_snapshot(glory_completed_snapshot); run.apply(ContinueAct())
    if phase == 'victory': run.apply(ChooseEventOption(run.state.epilogue_event_id,'proceed'))
    before = saved(run); bad = deepcopy(before); corrupt(bad)
    with pytest.raises(ValueError): run.restore(bad)
    assert saved(run) == before


@pytest.mark.parametrize('wongo',[False,True])
@pytest.mark.parametrize('profile',['native','fixture'])
def test_final_boss_has_no_baseline_reward_rolls_but_wongo_still_triggers(wongo, profile):
    from game.headless.run.inventory import add_relic
    from game.headless.run.config import RunConfig
    from game.headless.run.rewards import begin_combat_rewards
    run = RunEngine(seed=2, config=RunConfig(), rng_profile=profile)
    for name in ('amethyst_aubergine','white_beast_statue','lasting_candy','lava_rock'):
        add_relic(run.state, name, cards=run.cards)
    if wongo:
        add_relic(run.state, 'wongos_mystery_ticket', cards=run.cards)
        from game.headless.relics.run_rules import counter
        counter(run.state, run.state.relics[-1], 5)
    state = run.state
    state.act_index = 2; state.combats_completed = 1
    rng = deepcopy(state.rng.snapshot()); odds = deepcopy(state.generation_odds)
    potion_chance = state.potion_drop_chance
    begin_combat_rewards(state, run.cards, encounter_id='glory_queen', extra_cards=3, royalties=9)
    r = state.pending
    assert r['gold'] == 0 and r['gold_claimed'] and r['card_resolved'] and r['offers'] == []
    assert r['potion'] is None and r['relic'] is None and r['hunt_rewards_earned'] == r['royalties_earned'] == 0
    assert state.generation_odds == odds and state.potion_drop_chance == potion_chance
    if wongo:
        assert len(r['extra_rewards']) == 3 and state.relics[-1].counter == 6
    else:
        assert not r['extra_rewards'] and state.rng.snapshot() == rng
    before = saved(run)
    for key,value in [('gold',100),('gold_claimed',False),('offers',['bash']),('card_resolved',False),('royalties_earned',9)]:
        bad = deepcopy(before); bad['state']['pending'][key] = value
        with pytest.raises(ValueError): run.restore(bad)
        assert saved(run) == before
    step(run, LeaveRewards()); assert run.state.phase is RunPhase.ACT_COMPLETE


def test_failed_glory_transition_preserves_history_rng_and_items(hive_completed_snapshot, monkeypatch):
    run = from_snapshot(hive_completed_snapshot); before = saved(run)
    def fail(rng, **kwargs):
        rng.random('act3.map'); raise ValueError('Synthetic map failure')
    monkeypatch.setattr('game.headless.map.standard.generate_map',fail)
    with pytest.raises(ValueError): run.apply(ContinueAct())
    assert saved(run) == before


def test_failed_architect_entry_preserves_final_completion(glory_completed_snapshot, monkeypatch):
    run = from_snapshot(glory_completed_snapshot); before = saved(run)
    def fail(state, *args, **kwargs):
        state.rng.random('event.test'); state.hp = 1; raise ValueError('Synthetic entry failure')
    monkeypatch.setattr('game.headless.run.events.begin',fail)
    with pytest.raises(ValueError): run.apply(ContinueAct())
    assert saved(run) == before


def test_spoils_quest_stays_with_archived_hive_map():
    from game.headless.run.deck import add_card
    from game.headless.map.standard import SPOILS_PROFILE
    run = RunEngine.ironclad_run(seed=2)
    run.state.max_hp = run.state.hp = 10000
    add_card(run.state, run.cards.definition('spoils_map'))
    complete_act(run); run.apply(ContinueAct())
    assert run.graph.generation == SPOILS_PROFILE
    complete_act(run)
    quest = deepcopy(run.state.spoils_map)
    step(run, ContinueAct())
    assert run.graph.generation == GLORY_PROFILE and run.state.spoils_map is None
    assert run.state.completed_acts[1].graph.generation == SPOILS_PROFILE
    assert run.state.completed_acts[1].spoils_map == quest
    before = saved(run); bad = deepcopy(before)
    bad['state']['completed_acts'][1]['spoils_map'] = None
    with pytest.raises(ValueError): run.restore(bad)
    assert saved(run) == before


def test_glory_lantern_key_forces_repy_after_consuming_event_queue(hive_completed_snapshot):
    from game.headless.run.deck import add_card
    from game.headless.run.unknown_rooms import prepare_unknown
    from game.headless.events.eligibility import entry_conditions
    run = from_snapshot(hive_completed_snapshot); run.apply(ContinueAct())
    add_card(run.state, run.cards.definition('lantern_key'))
    node = next(n for n in run.graph.nodes if n.kind == 'unknown')
    rng, unknown, progression, chosen = prepare_unknown(run.state, run.graph, node)
    assert chosen.kind == 'event' and chosen.event_id == 'war_historian_repy'
    assert progression.cursor > run.state.event_progression.cursor
    assert progression.entry_conditions[node.node_id]['act_index'] == 2
    assert progression.entry_conditions[node.node_id]['lantern_keys'] == 1
    from game.headless.events.progression import EventProgression, GLORY_PROFILE as EVENTS_PROFILE
    conditions = entry_conditions(run.state)
    conditions['lantern_keys'] = 0
    queue = EventProgression(['brain_leech','tinker_time'], profile=EVENTS_PROFILE)
    assert queue.pull('glory.event',conditions=conditions,seen_before={'brain_leech'}) == 'tinker_time'
    assert queue.cursor == 2


def test_glory_golden_compass_and_fur_coat_bind_the_current_act(hive_completed_snapshot):
    from game.headless.map.golden_path import PROFILE as GOLDEN
    run = from_snapshot(hive_completed_snapshot); run.apply(ContinueAct())
    ancient = run.graph.node('act3.ancient').event_id
    run.obtain_relic('golden_compass'); run.obtain_relic('fur_coat')
    assert run.graph.generation == GOLDEN and run.graph.node('act3.ancient').event_id == ancient
    for relic in run.state.relics:
        if relic.definition_id in ('golden_compass','fur_coat'): assert relic.data['act'] == 3
    clone(run)
    complete_act(run)
    step(run,ContinueAct()); step(run,ChooseEventOption(run.state.epilogue_event_id,'proceed'))
    assert run.state.phase is RunPhase.VICTORY


@pytest.mark.parametrize('ancient',['nonupeipe','tanx','vakuu','darv'])
def test_all_glory_ancient_roots_are_valid_in_standard_and_golden_maps(ancient):
    from game.headless.map.golden_path import generate
    pool = (*REGION_POOLS['glory'][3], *SHARED_EVENTS)
    for graph in (generate_map(NativeRandomService(2),act='glory',event_pool=pool,ancient=ancient), generate(act_index=2,ancient=ancient)):
        assert graph.entry_node_ids == ('act3.ancient',)
        assert graph.node('act3.ancient').event_id == ancient


def test_unearned_wongo_final_rewards_are_rejected():
    from game.headless.run.inventory import add_relic
    from game.headless.run.config import RunConfig
    from game.headless.run.rewards import begin_combat_rewards
    run = RunEngine(seed=2, config=RunConfig())
    add_relic(run.state, 'wongos_mystery_ticket', cards=run.cards)
    run.state.act_index = 2; run.state.combats_completed = 1
    begin_combat_rewards(run.state, run.cards, encounter_id='glory_queen')
    before = saved(run); bad = deepcopy(before)
    owner = run.state.relics[0].instance_id
    bad['state']['pending']['extra_rewards'] = [dict(source=owner,kind='relic',offers=[name],modifiers={},resolved=False) for name in ('strawberry','pear','mango')]
    with pytest.raises(ValueError): run.restore(bad)
    assert saved(run) == before


@pytest.mark.parametrize('seed,boss', [(0,'glory_test_subject'),(1,'glory_queen'),(7,'glory_aeonglass')])
def test_neow_campaign_can_complete_each_glory_boss(seed, boss):
    from game.headless.run.ancient import PROFILE
    run = RunEngine.ironclad_run(seed=seed, ancient_profile=PROFILE)
    run.state.max_hp = run.state.hp = 10000
    for act in (1,2,3):
        complete_act(run)
        clone(run)
        if act == 3: assert run.state.act_completion.boss_encounter_id == boss
        step(run, ContinueAct())
    step(run, ChooseEventOption(run.state.epilogue_event_id,'proceed'))
    assert run.state.phase is RunPhase.VICTORY and run.state.ancient_start.selected is not None
