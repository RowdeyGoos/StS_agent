"""Generated Hive maps, act transitions and run-owned history (solo A0)."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from game.headless.run.engine import RunEngine
from game.headless.run.actions import ContinueAct, ChooseNode, LeaveEvent
from game.headless.run.state import RunPhase
from game.cli.headless_play import choose_demo_action
from game.headless.core.actions import EndTurn
from game.headless.core.native_service import NativeRandomService
from game.headless.map.standard import generate_map, HIVE_PROFILE
from game.headless.generation.room_pools import REGION_POOLS, SHARED_EVENTS

VECTORS = json.loads((Path(__file__).parents[1] / 'fixtures/headless_native_hive_map_vectors.json').read_text())


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def clone(run):
    other = RunEngine()
    other.restore(saved(run))
    assert saved(other) == saved(run)
    assert other.legal_actions() == run.legal_actions()
    return other


def step(run, action):
    other = clone(run)
    run.apply(action); other.apply(action)
    assert saved(run) == saved(other)
    clone(run)


def win(run):
    """Synthetic victories isolate route ownership from policy strength."""
    for _ in range(20):
        if run.combat.done:
            run.finish_combat()
            return
        for enemy in tuple(run.combat.enemies):
            if enemy.is_alive and not getattr(enemy, 'about_to_blow', False):
                enemy.take_damage(10000, is_attack=False)
        run.combat.resolve_external_effect()
        if not run.combat.done:
            run.apply(EndTurn())
            if run.combat is None: return
    pytest.fail('Combat did not terminate.')


def complete_act(run, *, verify=False, path='left'):
    for _ in range(600):
        if run.combat is not None:
            if verify:
                other = clone(run)
                win(run); win(other)
                assert saved(run) == saved(other)
            else: win(run)
        if run.state.phase is RunPhase.ACT_COMPLETE:
            return
        assert run.state.phase is not RunPhase.DEFEAT
        actions = run.legal_actions()
        action = next((a for a in actions if isinstance(a, LeaveEvent)), None) or choose_demo_action(run, rest_choice='rest', path=path)
        if verify: step(run, action)
        else: run.apply(action)
    pytest.fail('Route did not terminate.')


@pytest.fixture
def first_act_complete():
    run = RunEngine.ironclad_run(seed=2)
    run.state.max_hp = run.state.hp = 10000
    complete_act(run)
    return run


@pytest.mark.parametrize('row', VECTORS['rows'], ids=lambda r:r['seed'])
def test_hive_map_matches_actual_native_geometry_and_rng(row):
    rng = NativeRandomService(row['seed'])
    graph = generate_map(rng, act='hive', event_pool=(*REGION_POOLS['hive'][3], *SHARED_EVENTS))
    kinds = {'Monster':'combat', 'Elite':'elite', 'Boss':'boss', 'RestSite':'rest', 'Treasure':'treasure', 'Shop':'shop', 'Unknown':'unknown'}
    actual = [dict(coord=[n.row,n.column], kind=n.kind, children=sorted([[graph.node(i).row,graph.node(i).column] for i in n.next_node_ids])) for n in graph.nodes]
    assert actual == [dict(n, kind=kinds[n['kind']]) for n in row['map']['nodes']]
    assert [[graph.node(i).row,graph.node(i).column] for i in graph.entry_node_ids] == row['map']['starts']
    assert rng.request_count('act2.map') == row['map']['counter']
    assert rng.double('act2.map') == row['map']['suffix']
    assert rng.request_count('act1.map') == 0


def test_transition_reuses_startup_queues_and_heals_only_at_ancient(first_act_complete):
    run = first_act_complete
    old = deepcopy(run.state)
    run.state.hp = 7
    assert run.legal_actions() == (ContinueAct(),)
    step(run, ContinueAct())
    s = run.state
    assert s.hp == 7 and s.act_index == 1 and s.config.act == 'hive'
    assert s.visited_nodes == [] and s.current_node_id is None
    from game.headless.core.snapshots import card_record
    assert [card_record(c) for c in s.deck] == [card_record(c) for c in old.deck]
    assert s.relics == old.relics and s.potions == old.potions
    assert s.combats_completed == old.combats_completed and s.gold == old.gold
    assert s.rng.request_count('up_front') == old.rng.request_count('up_front')
    assert len(s.encounter_progression.normal_queue) == 14
    assert run.graph.generation == HIVE_PROFILE
    assert run.graph.node('act2.ancient').event_id == old.initialization['acts'][1]['ancient']
    assert s.completed_acts[0].visited_nodes == old.visited_nodes
    step(run, ChooseNode('act2.ancient'))
    assert s.hp == s.max_hp and s.visited_nodes == ['act2.ancient']
    assert s.pending['definition_id'] == old.initialization['acts'][1]['ancient']


@pytest.mark.parametrize('first_act', ['overgrowth', 'underdocks'])
@pytest.mark.parametrize('profile', ['fixture', 'native'])
def test_both_acts_through_hive_boss_with_every_decision_restored(first_act, profile):
    run = RunEngine.ironclad_run(seed=2, first_act=first_act, rng_profile=profile)
    run.state.max_hp = run.state.hp = 10000
    complete_act(run, verify=True)
    step(run, ContinueAct())
    complete_act(run, verify=True)
    assert run.state.act_completion.act == 2
    assert run.state.act_completion.boss_encounter_id.startswith('hive_')
    assert len(run.state.completed_acts) == 1 and not run.legal_actions()
    assert len(run.state.visited_nodes) in (16, 18)  # Standard or Golden Compass, including Ancient.
    clone(run)


@pytest.mark.parametrize('corrupt', [
    lambda s: s['state']['completed_acts'].clear(),
    lambda s: s['state']['completed_acts'][0]['visited_nodes'].pop(),
    lambda s: s['state']['completed_acts'][0]['encounter_progression']['normal_queue'].reverse(),
    lambda s: s['state']['completed_acts'][0].__setitem__('act', 'underdocks'),
    lambda s: s['state']['completed_acts'][0]['unknown_rooms']['odds'].__setitem__('combat', 0.99),
    lambda s: s['state']['config'].__setitem__('campaign', []),
    lambda s: s['state']['config'].__setitem__('act', 'overgrowth'),
    lambda s: s['state'].__setitem__('act_index', 0),
    lambda s: s['state']['encounter_progression']['normal_queue'].reverse(),
    lambda s: s['state']['event_progression'].__setitem__('profile', 'native_act1_events_all_unlocked_v1'),
    lambda s: s['graph']['nodes'][0].__setitem__('event_id', 'neow'),
    lambda s: s['state'].__setitem__('combats_completed', 0),
])
def test_corrupted_cross_act_history_is_rejected_atomically(first_act_complete, corrupt):
    run = first_act_complete
    run.apply(ContinueAct())
    before = saved(run)
    invalid = deepcopy(before)
    corrupt(invalid)
    with pytest.raises(ValueError): run.restore(invalid)
    assert saved(run) == before


def test_invalid_or_failed_continue_cannot_advance_rng_or_history(first_act_complete, monkeypatch):
    run = RunEngine.ironclad_run(seed=0)
    before = saved(run)
    with pytest.raises(ValueError): run.apply(ContinueAct())
    assert saved(run) == before
    run = first_act_complete
    before = saved(run)
    def fail(*args, **kwargs):
        args[0].random('act2.map')
        raise ValueError('Synthetic map failure')
    monkeypatch.setattr('game.headless.map.standard.generate_map', fail)
    with pytest.raises(ValueError): run.apply(ContinueAct())
    assert saved(run) == before


def test_hive_skips_shared_events_seen_in_previous_act():
    from game.headless.events.progression import EventProgression, HIVE_PROFILE
    from game.headless.events.eligibility import entry_conditions
    run = RunEngine.ironclad_run(seed=0)
    conditions = entry_conditions(run.state)
    conditions.update(act_index=1, gold=200)
    queue = EventProgression(['room_full_of_cheese', 'brain_leech'], profile=HIVE_PROFILE)
    assert queue.pull('act2.2.1', conditions=conditions, seen_before={'room_full_of_cheese'}) == 'brain_leech'
    assert queue.cursor == 2


def test_ancient_room_heal_and_maw_bank_happen_once_in_native_order(first_act_complete, monkeypatch):
    from game.headless.run.inventory import add_relic
    run = first_act_complete
    add_relic(run.state, 'maw_bank', cards=run.cards)
    run.state.hp = 5
    gold = run.state.gold
    run.apply(ContinueAct())
    assert run.state.gold == gold and run.state.hp == 5
    from game.headless.events import ancients
    original = ancients.page
    observed = []
    def page(name, state, rng):
        observed.append((state.hp, state.gold))
        return original(name, state, rng)
    monkeypatch.setattr(ancients, 'page', page)
    step(run, ChooseNode('act2.ancient'))
    assert observed and set(observed) == {(run.state.max_hp, gold)}
    assert run.state.gold == gold + 12
    clone(run)
    assert run.state.gold == gold + 12


def test_prior_map_relics_retain_their_original_act_and_map():
    run = RunEngine.ironclad_run(seed=2)
    run.obtain_relic('golden_compass')
    run.obtain_relic('fur_coat')
    run.state.hp = run.state.max_hp = 10000
    complete_act(run)
    old_marks = deepcopy(next(r.data for r in run.state.relics if r.definition_id == 'fur_coat'))
    step(run, ContinueAct())
    assert run.graph.generation == HIVE_PROFILE
    assert next(r.data for r in run.state.relics if r.definition_id == 'fur_coat') == old_marks
    clone(run)


def test_generated_hive_ancient_can_replace_map_with_golden_compass(first_act_complete):
    from game.headless.map.golden_path import PROFILE
    run = first_act_complete
    run.apply(ContinueAct())
    # Direct acquisition at the pre-navigation boundary exercises the same map hook.
    run.obtain_relic('golden_compass')
    assert run.graph.generation == PROFILE
    assert run.graph.entry_node_ids == ('act2.ancient',)
    assert next(r.data['act'] for r in run.state.relics if r.definition_id == 'golden_compass') == 2
    step(run, ChooseNode('act2.ancient'))
    clone(run)


def test_total_floor_continues_into_hive_encounter_seed(first_act_complete):
    from game.headless.core.native_rng import deterministic_hash
    run = first_act_complete
    previous_floors = run.state.visited_room_count
    run.apply(ContinueAct())
    run.apply(ChooseNode('act2.ancient'))
    while run.state.phase is not RunPhase.ROUTE or run.state.relic_work:
        run.apply(choose_demo_action(run))
    node = next(a for a in run.legal_actions() if isinstance(a, ChooseNode))
    run.apply(node)
    encounter = run.combat.encounter_rng
    # One implicit Act1 Ancient, explicit Hive Ancient, and the first Hive fight.
    assert run.state.visited_room_count + 1 == previous_floors + 3
    native = next(n for n,v in __import__('game.headless.encounters.progression', fromlist=['native_ids']).native_ids('hive').items() if v == run.state.active_encounter_id)
    import re
    native_id = re.sub(r'(?<!^)(?=[A-Z])', '_', native).upper()
    expected = (run.state.rng.root_seed + previous_floors + 3 + deterministic_hash(native_id)) & 0xffffffff
    assert encounter.composition.seed == expected


SPOILS_VECTORS = json.loads((Path(__file__).parents[1] / 'fixtures/headless_native_spoils_map_vectors.json').read_text())


@pytest.mark.parametrize('row', SPOILS_VECTORS['rows'], ids=lambda r:r['seed'])
def test_spoils_map_matches_native_geometry_and_rng(row):
    from game.headless.map.standard import SPOILS_PROFILE
    rng = NativeRandomService(row['seed'])
    graph = generate_map(rng, act='hive', profile=SPOILS_PROFILE, event_pool=(*REGION_POOLS['hive'][3], *SHARED_EVENTS))
    kinds = {'Monster':'combat', 'Elite':'elite', 'Boss':'boss', 'RestSite':'rest', 'Treasure':'treasure', 'Shop':'shop', 'Unknown':'unknown'}
    actual = [dict(coord=[n.row,n.column], kind=n.kind, children=sorted([[graph.node(i).row,graph.node(i).column] for i in n.next_node_ids])) for n in graph.nodes]
    assert actual == [dict(n, kind=kinds[n['kind']]) for n in row['map']['nodes']]
    assert [[graph.node(i).row,graph.node(i).column] for i in graph.entry_node_ids] == row['map']['starts']
    assert rng.request_count('spoils_map') == row['map']['counter']
    assert rng.double('spoils_map') == row['map']['suffix']


def reach_spoils_chest(run, *, crucible=False):
    target = run.state.spoils_map['target']
    for _ in range(250):
        if run.combat is not None: win(run)
        if run.state.current_node_id == target and run.state.pending and run.state.pending.get('kind') == 'treasure':
            return
        actions = run.legal_actions()
        action = next((a for a in actions if isinstance(a, LeaveEvent)), None) or choose_demo_action(run, rest_choice='rest')
        if crucible and isinstance(action, ChooseNode) and action.node_id == target:
            from game.headless.run.inventory import add_relic
            add_relic(run.state, 'silver_crucible', cards=run.cards)
        run.apply(action)
    pytest.fail('Did not reach Spoils chest.')


@pytest.mark.parametrize('mode', ['ordinary', 'copies', 'removed', 'transformed', 'unopened', 'crucible', 'ectoplasm', 'compass'])
def test_spoils_quest_from_act1_through_hive_chest(first_act_complete, mode):
    from game.headless.run.deck import add_card, remove_card, replace_card
    from game.headless.run.actions import OpenChest, LeaveTreasure
    from game.headless.run.inventory import add_relic
    from game.headless.map.standard import SPOILS_PROFILE
    from game.headless.map.golden_path import PROFILE as GOLDEN
    run = first_act_complete
    card = add_card(run.state, run.cards.definition('spoils_map'))
    if mode == 'copies': add_card(run.state, run.cards.definition('spoils_map'))
    old_rng = run.state.rng.snapshot()
    step(run, ContinueAct())
    assert run.graph.generation == SPOILS_PROFILE
    assert run.state.spoils_map['target'] == 'act2.8.3'
    assert run.state.rng.request_count('spoils_map') == 0  # Constructor-local domain.
    assert run.state.rng.snapshot()['streams']['up_front'] == old_rng['streams']['up_front']
    if mode == 'compass':
        run.obtain_relic('golden_compass')
        assert run.graph.generation == GOLDEN
        assert run.state.spoils_map['target'] == 'act2.8.3'
    reach_spoils_chest(run, crucible=mode == 'crucible')
    if mode == 'removed': remove_card(run.state, card.instance_id)
    if mode == 'transformed': replace_card(run.state, card.instance_id, run.cards.definition('strike'))
    if mode == 'ectoplasm': add_relic(run.state, 'ectoplasm', cards=run.cards)
    if mode == 'crucible': assert run.state.pending['stage'] == 'empty'
    before = run.state.gold
    present = lambda: [c for c in run.state.deck if c.definition.definition_id == 'spoils_map']
    if mode in ('unopened', 'crucible'):
        step(run, LeaveTreasure())
        assert run.state.gold == before and len(present()) == 1
    else:
        step(run, OpenChest())
        chest_gold = run.state.pending['gold']
        bonus = 1200 if mode == 'copies' else 0 if mode in ('removed', 'transformed') else 600
        assert run.state.gold - before == (0 if mode == 'ectoplasm' else chest_gold + bonus)
        assert not present()
        step(run, LeaveTreasure())
    clone(run)


@pytest.mark.parametrize('corrupt', [
    lambda s: s['state'].__setitem__('spoils_map', None),
    lambda s: s['state']['spoils_map'].__setitem__('target', 'act2.boss'),
    lambda s: s['state']['spoils_map'].__setitem__('card_ids', ['run.card.999999']),
    lambda s: s['state']['spoils_map'].__setitem__('card_ids', []),
    lambda s: s['state']['config'].pop('campaign'),
])
def test_spoils_marker_restore_rejects_invalid_owner(first_act_complete, corrupt):
    from game.headless.run.deck import add_card
    run = first_act_complete
    add_card(run.state, run.cards.definition('spoils_map'))
    run.apply(ContinueAct())
    before = saved(run)
    invalid = deepcopy(before)
    corrupt(invalid)
    with pytest.raises(ValueError): run.restore(invalid)
    assert saved(run) == before


def test_golden_replacement_cannot_erase_spoils_quest(first_act_complete):
    from game.headless.run.deck import add_card
    from game.headless.map.standard import SPOILS_PROFILE
    run = first_act_complete
    add_card(run.state, run.cards.definition('spoils_map'))
    run.apply(ContinueAct())
    run.obtain_relic('golden_compass')
    assert run.graph.replaced_generation == SPOILS_PROFILE
    before = saved(run)
    invalid = deepcopy(before)
    invalid['state']['spoils_map'] = None
    with pytest.raises(ValueError): run.restore(invalid)
    assert saved(run) == before
