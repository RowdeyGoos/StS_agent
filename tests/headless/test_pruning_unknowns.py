"""Native map cleanup and unknown-room decisions through the owned run flow."""
from copy import deepcopy
from dataclasses import asdict
import json

import pytest

from game.cli.headless_play import choose_demo_action
from game.headless.core.rng import GameRandomService
from game.headless.map.graph import MapGraph, MapNode
from game.headless.map.overgrowth import PROFILE, BASE_PROFILE, generate_overgrowth_map
from game.headless.map.pruning import matching_segments, prune_duplicates, prune_and_repair, _break_segment
from game.headless.run.engine import RunEngine
from game.headless.run.actions import ChooseNode, LeaveRewards
from game.headless.run.state import RunPhase
from game.headless.run.unknown_rooms import BASE_ODDS, roll_room, _single, blocked_types, room_node


def saved(run, *, sorted_keys=False):
    return json.loads(json.dumps(run.snapshot(), sort_keys=sorted_keys))


def step(run, action):
    clone = RunEngine(); clone.restore(saved(run, sorted_keys=True))
    assert clone.legal_actions() == run.legal_actions()
    clone.apply(action); result = run.apply(action)
    assert saved(run) == saved(clone)
    return result


def win(run):
    # Explicit synthetic outcome; this tests room continuity, not a policy win.
    for _ in range(10):
        for enemy in tuple(run.combat.enemies):
            if enemy.is_alive: enemy.take_damage(10000, is_attack=False)
    run.combat.resolve_external_effect(); run.finish_combat()


def topology(edges, kinds=None):
    edges = {point: set(children) for point, children in edges.items()}
    parents = {point: set() for point in edges}
    for point, children in edges.items():
        for child in children: parents[child].add(point)
    kinds = {point: (kinds or {}).get(point, 'combat') for point in edges}
    return edges, parents, kinds


def assert_connected(edges, root, boss):
    seen = set()
    def visit(point):
        if point in seen: return
        seen.add(point)
        assert point == boss or edges[point]
        for child in edges[point]: visit(child)
    visit(root)
    assert seen == set(edges)


def test_identical_diamond_prunes_one_alternative_and_retains_boss_path():
    root,a,b,end,boss = (0,3),(1,2),(1,4),(2,3),(3,3)
    edges,parents,kinds = topology({root:[a,b],a:[end],b:[end],end:[boss],boss:[]}, {root:'ancient',boss:'boss'})
    assert matching_segments(edges,parents,kinds,root)
    prune_duplicates(edges,parents,kinds,root,GameRandomService(3))
    assert len({a,b}&set(edges)) == 1
    assert len(parents[end]) == 1
    assert not matching_segments(edges,parents,kinds,root)
    assert_connected(edges,root,boss)


def test_different_room_sequences_are_not_duplicate_paths():
    root,a,b,end,boss = (0,3),(1,2),(1,4),(2,3),(3,3)
    edges,parents,kinds = topology({root:[a,b],a:[end],b:[end],end:[boss],boss:[]}, {root:'ancient',boss:'boss',b:'unknown'})
    before = deepcopy(edges)
    prune_duplicates(edges,parents,kinds,root,GameRandomService(3))
    assert edges == before


def test_overlap_detection_and_edge_fallback_preserve_shared_nodes():
    root,a,b,c,d,boss = (0,3),(1,2),(1,4),(2,2),(2,4),(3,3)
    edges,parents,kinds = topology({root:[a,b],a:[c,d],b:[c,d],c:[boss],d:[boss],boss:[]}, {root:'ancient',boss:'boss'})
    groups = matching_segments(edges,parents,kinds,root)
    for group in groups:
        for i, path in enumerate(group):
            for other in group[i+1:]:
                assert not set(path[1:-1]) & set(other[1:-1])
    count = len(edges)
    assert _break_segment(edges,parents,(root,a,c,boss))
    assert len(edges) == count
    assert_connected(edges,root,boss)
    prune_duplicates(edges,parents,kinds,root,GameRandomService(9))
    assert_connected(edges,root,boss)


def test_repair_replaces_only_modifiable_combat_points():
    root,a,b,c,d,boss = (0,3),(1,2),(1,4),(2,3),(3,3),(4,3)
    edges,parents,kinds = topology({root:[a,b],a:[c],b:[c],c:[d],d:[boss],boss:[]}, {root:'ancient',boss:'boss'})
    prune_and_repair(edges,parents,kinds,root,GameRandomService(5),
                     {'shop':0,'elite':0,'rest':1,'unknown':1}, lambda kind,p: p[0] in (2,3))
    assert {kinds[c],kinds[d]} == {'rest','unknown'}
    assert all(kinds[p]=='combat' for p in edges if p[0]==1)
    assert_connected(edges,root,boss)


@pytest.mark.parametrize('seed', range(10))
def test_pruned_maps_are_reproducible_full_length_and_keep_unknowns_hidden(seed):
    new = RunEngine.ironclad_act1(seed=seed)
    old = RunEngine.ironclad_act1(seed=seed,map_profile=BASE_PROFILE)
    assert len(new.graph.nodes) < len(old.graph.nodes)
    assert set(new.graph.entry_node_ids) <= set(old.graph.entry_node_ids)
    assert new.graph.generation == PROFILE
    assert new.state.unknown_rooms.outcomes == {}
    assert new.state.unknown_rooms.odds == dict(BASE_ODDS)
    assert any(n.kind=='unknown' for n in new.graph.nodes)
    assert all(n.event_id is None for n in new.graph.nodes)
    assert new.graph == RunEngine.ironclad_act1(seed=seed).graph
    lengths={}
    for node in sorted(new.graph.nodes,key=lambda n:-n.row):
        following=[lengths[c] for c in node.next_node_ids]
        assert len(set(following)) <= 1
        lengths[node.node_id]=1+(following[0] if following else 0)
    assert {lengths[n] for n in new.graph.entry_node_ids} == {16}
    before=saved(new)
    new.legal_actions();new.available_nodes()
    assert saved(new)==before
    clone=RunEngine();clone.restore(saved(new,sorted_keys=True))
    assert saved(clone)==before


class FixedRoll:
    def __init__(self,value): self.value=value;self.calls=0
    def random(self,name):
        assert name=='act1.unknown'
        self.calls+=1
        return self.value


@pytest.mark.parametrize('value,result',[(0,'combat'),(.1,'combat'),(.11,'treasure'),(.14,'shop'),(.8,'event')])
def test_native_initial_odds_boundaries_and_updates(value,result):
    odds=dict(BASE_ODDS);rng=FixedRoll(value)
    assert roll_room(odds,rng)==result
    assert rng.calls==1
    for kind,base in BASE_ODDS.items():
        assert odds[kind] == (base if kind==result else _single(base+base))
    assert odds['elite']==-2.0  # Disabled negative odds still follow the native increment.


def test_unselected_odds_accumulate_and_blocked_shop_odds_are_not_redistributed():
    odds=dict(BASE_ODDS)
    assert [roll_room(odds,FixedRoll(.99)) for _ in range(7)] == ['event']*6+['shop']
    odds=dict(BASE_ODDS)
    assert roll_room(odds,FixedRoll(.14),blocked=('shop',))=='event'
    assert odds['shop']==BASE_ODDS['shop']
    reordered=dict(reversed(list(BASE_ODDS.items())))
    assert roll_room(reordered,FixedRoll(.11))=='treasure'


def before_unknown(seed, *, next_kind='combat'):
    run=RunEngine.ironclad_act1(seed=seed)
    # A straight generated-map fixture makes all four room outcomes reachable
    # after one starter fight while retaining native fixed-row constraints.
    nodes=[]
    for row in range(1,17):
        kind={2:'unknown',3:next_kind,9:'treasure',15:'rest',16:'boss'}.get(row,'combat')
        identity='act1.boss' if row==16 else f'act1.{row}.3'
        children=() if row==16 else ('act1.boss',) if row==15 else (f'act1.{row+1}.3',)
        nodes.append(MapNode(identity,kind,children,row=row,column=3))
    run.graph=MapGraph(tuple(nodes),'act1.1.3',('act1.1.3',),PROFILE)
    run.apply(ChooseNode('act1.1.3'));win(run);run.apply(LeaveRewards())
    return run


@pytest.mark.parametrize('seed,kind',[(0,'event'),(6,'treasure'),(32,'shop'),(2,'combat')])
def test_every_unknown_outcome_restores_and_uses_the_existing_room_handler(seed,kind):
    run=before_unknown(seed)
    before=saved(run)
    for _ in range(3):run.legal_actions()
    assert saved(run)==before
    step(run,ChooseNode('act1.2.3'))
    assert run.graph.node('act1.2.3').kind=='unknown'
    assert room_node(run.state,run.graph,'act1.2.3').kind==kind
    assert run.state.rng.request_count('act1.unknown')==1
    assert len(run.state.unknown_rooms.outcomes)==1
    if kind=='combat':
        assert run.state.active_encounter_id==run.state.encounter_progression.normal_queue[1]
        assert len(run.state.encounter_progression.assignments)==2
        win(run)
    else:
        assert len(run.state.encounter_progression.assignments)==1
        assert run.state.pending['kind']=={'event':'scripted_event','shop':'shop','treasure':'treasure'}[kind]
    while run.state.phase not in (RunPhase.ROUTE,RunPhase.DEFEAT):
        step(run,choose_demo_action(run,rest_choice='rest'))
    assert run.state.rng.request_count('act1.unknown')==1


def test_shop_blacklist_checks_previous_resolved_room_and_all_next_markers():
    run=before_unknown(32,next_kind='shop')
    point=run.graph.node('act1.2.3')
    assert blocked_types(run.graph,point,'combat')==('shop',)
    step(run,ChooseNode(point.node_id))
    assert run.state.unknown_rooms.outcomes[point.node_id].kind=='event'
    assert run.state.unknown_rooms.odds['shop']==BASE_ODDS['shop']
    run=before_unknown(2)
    assert blocked_types(run.graph,run.graph.node('act1.2.3'),'shop')==('shop',)


@pytest.mark.parametrize('seed,target',[(0,'event'),(6,'treasure'),(32,'shop'),(2,'combat')])
def test_failed_unknown_construction_rolls_back_all_owned_state(seed,target,monkeypatch):
    run=before_unknown(seed);before=saved(run)
    def fail(*args,**kwargs):raise ValueError('fixture failure')
    if target=='combat':monkeypatch.setattr(run,'start_combat',fail)
    else:
        from game.headless.run import events,treasure,shop
        monkeypatch.setattr({'event':events,'treasure':treasure,'shop':shop}[target],'begin',fail)
    with pytest.raises(ValueError):run.apply(ChooseNode('act1.2.3'))
    assert saved(run)==before


@pytest.mark.parametrize('seed,path',[(0,'left'),(1,'right'),(2,'left'),(3,'right'),(4,'left'),(5,'right')])
def test_full_pruned_route_synthetic_continuation(seed,path):
    run=RunEngine.ironclad_act1(seed=seed)
    for _ in range(500):
        if run.state.phase is RunPhase.ACT_COMPLETE:break
        if run.state.phase is RunPhase.COMBAT:
            clone=RunEngine();clone.restore(saved(run));win(run);win(clone)
            assert saved(run)==saved(clone)
        else:step(run,choose_demo_action(run,rest_choice='rest',path=path))
    assert run.state.phase is RunPhase.ACT_COMPLETE
    assert len(run.state.visited_nodes)==16
    assert set(run.state.unknown_rooms.outcomes)=={n for n in run.state.visited_nodes if run.graph.node(n).kind=='unknown'}


@pytest.mark.parametrize('corrupt',[
    lambda s:s['state'].__setitem__('unknown_rooms',None),
    lambda s:s['state']['unknown_rooms']['odds'].__setitem__('combat',.2),
    lambda s:s['state']['unknown_rooms']['odds'].__setitem__('elite',-1),
    lambda s:s['state']['unknown_rooms']['odds'].__setitem__('shop',float('nan')),
    lambda s:s['state']['unknown_rooms']['outcomes'].__setitem__('act1.2.3',{'kind':'event','event_id':'aroma_of_chaos'}),
    lambda s:s.__setitem__('schema','headless_run_state_v10'),
])
def test_unvisited_outcomes_and_corrupt_odds_reject_atomically(corrupt):
    run=before_unknown(2);before=saved(run);changed=deepcopy(before);corrupt(changed)
    with pytest.raises(ValueError):run.restore(changed)
    assert saved(run)==before


def test_resolved_outcome_cannot_disagree_with_pending_room_or_vanish():
    run=before_unknown(2);step(run,ChooseNode('act1.2.3'));before=saved(run)
    for outcome in ({},{'act1.2.3':{'kind':'elite','event_id':None}},{'act1.2.3':{'kind':'shop','event_id':'aroma_of_chaos'}}):
        changed=deepcopy(before);changed['state']['unknown_rooms']['outcomes']=outcome
        with pytest.raises(ValueError):run.restore(changed)
        assert saved(run)==before
