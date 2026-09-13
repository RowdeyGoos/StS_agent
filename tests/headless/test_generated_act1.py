"""Generated map, native queue rules and full-length restricted continuation."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from game.cli.headless_play import choose_demo_action, play_slice
from game.headless.core.rng import GameRandomService
from game.headless.encounters.catalog import ENCOUNTERS
from game.headless.encounters.progression import EncounterProgression, WEAK, NORMAL, ELITES, BOSSES, TAGS
from game.headless.map.overgrowth import BASE_PROFILE as PROFILE, generate_overgrowth_map
from game.headless.run.actions import ChooseNode, ClaimRelic, LeaveRewards
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic
from game.headless.run.state import RunPhase


def saved(engine):
    return json.loads(json.dumps(engine.snapshot()))


def step(engine, action):
    clone = RunEngine(); clone.restore(saved(engine))
    assert clone.legal_actions() == engine.legal_actions()
    clone.apply(action)
    result = engine.apply(action)
    assert saved(clone) == saved(engine)
    return result


def win_fixture(engine):
    """Synthetic lifecycle fixture, never reported as a natural policy win."""
    for _ in range(10):
        for enemy in tuple(engine.combat.enemies):
            if enemy.is_alive:
                enemy.take_damage(10000, is_attack=False)
    engine.combat.resolve_external_effect()
    engine.finish_combat()


@pytest.mark.parametrize('seed', range(20))
def test_full_length_topology_and_owned_queues(seed):
    run = RunEngine.ironclad_act1(map_profile=PROFILE, seed=seed)
    graph = run.graph
    assert graph.generation == PROFILE
    assert graph == RunEngine.ironclad_act1(map_profile=PROFILE, seed=seed).graph
    assert 2 <= len(graph.entry_node_ids) <= 7
    assert set(n.row for n in graph.nodes) == set(range(1, 17))
    assert all(n.kind == 'combat' for n in graph.nodes if n.row == 1)
    assert all(n.kind == 'treasure' for n in graph.nodes if n.row == 9)
    assert all(n.kind == 'rest' for n in graph.nodes if n.row == 15)
    assert [(n.row, n.column) for n in graph.nodes if n.kind == 'boss'] == [(16, 3)]
    # Every available branch has exactly the same remaining room count.
    lengths = {}
    for node in sorted(graph.nodes, key=lambda n: -n.row):
        children = [lengths[c] for c in node.next_node_ids]
        assert not children or len(set(children)) == 1
        lengths[node.node_id] = 1 + (children[0] if children else 0)
    assert {lengths[n] for n in graph.entry_node_ids} == {16}
    before = saved(run)
    for _ in range(3):
        assert run.legal_actions() == tuple(ChooseNode(n) for n in graph.entry_node_ids)
    assert saved(run) == before
    clone = RunEngine(); clone.restore(before)
    assert clone.graph == graph
    assert saved(clone) == before
    progression = run.state.encounter_progression
    assert len(progression.normal_queue) == len(progression.elite_queue) == 15
    assert len(set(progression.normal_queue[:3])) == 3
    assert set(progression.normal_queue[:3]) <= set(WEAK)
    assert set(progression.normal_queue[3:]) == set(NORMAL)
    for index in range(0, 15, 3):
        assert set(progression.elite_queue[index:index+3]) == set(ELITES)
    assert progression.boss in BOSSES


def test_native_tag_exclusion_at_weak_to_normal_boundary_and_bag_refill():
    seen = set()
    for seed in range(100):
        p = EncounterProgression.generate(GameRandomService(seed))
        a, b = p.normal_queue[2:4]
        assert not TAGS.get(a, set()) & TAGS.get(b, set())
        assert all(a != b for a, b in zip(p.elite_queue, p.elite_queue[1:]))
        seen.add(p.boss)
    assert seen == set(BOSSES)


def test_map_rng_is_isolated_from_rewards_and_encounter_queues():
    a, b = GameRandomService(71), GameRandomService(71)
    for _ in range(100):
        b.randint('reward_gold', 10, 20)
    assert EncounterProgression.generate(a) == EncounterProgression.generate(b)
    kwargs = {'event_pool': ('aroma_of_chaos',), 'profile': PROFILE}
    assert generate_overgrowth_map(a, **kwargs) == generate_overgrowth_map(b, **kwargs)
    assert all(n.event_id == 'aroma_of_chaos' for n in generate_overgrowth_map(GameRandomService(7), **kwargs).nodes if n.kind == 'event')
    with pytest.raises(ValueError):
        RunEngine.ironclad_act1(map_profile=PROFILE, discovery='first_run')
    with pytest.raises(ValueError):
        RunEngine.ironclad_act1(map_profile=PROFILE, ascension=1)


@pytest.mark.parametrize('seed,path', [(0,'left'), (1,'right'), (2,'left'), (3,'right'), (4,'left'), (5,'right')])
def test_full_length_synthetic_route_every_decision_restores(seed, path):
    run = RunEngine.ironclad_act1(map_profile=PROFILE, seed=seed)
    encounter_history = []
    for _ in range(500):
        if run.state.phase == RunPhase.COMBAT:
            encounter_history.append(run.state.active_encounter_id)
            clone = RunEngine(); clone.restore(saved(run))
            win_fixture(run); win_fixture(clone)
            assert saved(run) == saved(clone)
        if run.state.phase == RunPhase.ACT_COMPLETE:
            break
        action = choose_demo_action(run, rest_choice='rest', path=path)
        step(run, action)
    assert run.state.phase == RunPhase.ACT_COMPLETE
    assert len(run.state.visited_nodes) == 16
    assert run.state.act_completion.boss_encounter_id == run.state.encounter_progression.boss
    assert len(encounter_history) == run.state.combats_completed
    assert len(run.state.encounter_progression.assignments) == len(encounter_history)
    normal = [n for n in encounter_history if ENCOUNTERS[n].room_kind == 'combat']
    assert normal == run.state.encounter_progression.normal_queue[:len(normal)]
    before = saved(run)
    altered = deepcopy(before)
    altered['state']['phase'] = 'route'
    altered['state']['act_completion'] = None
    with pytest.raises(ValueError):
        run.restore(altered)
    assert saved(run) == before


def test_failed_room_entry_does_not_consume_queue_or_navigation(monkeypatch):
    run = RunEngine.ironclad_act1(map_profile=PROFILE, seed=7)
    before = saved(run)
    def fail(**kwargs):
        raise ValueError('fixture construction failure')
    monkeypatch.setattr(run, 'start_combat', fail)
    with pytest.raises(ValueError):
        run.apply(run.legal_actions()[0])
    assert saved(run) == before
    with pytest.raises(ValueError):
        run.apply(ChooseNode('act1.boss'))
    assert saved(run) == before


def test_direct_pending_node_restores_without_consuming_encounter():
    run = RunEngine.ironclad_act1(map_profile=PROFILE, seed=8)
    node = run.choose_node(run.graph.entry_node_ids[0])
    clone = RunEngine(); clone.restore(saved(run))
    assert clone.state.encounter_progression.assignments == {}
    expected = run.state.encounter_progression.normal_queue[0]
    before = saved(clone)
    with pytest.raises(ValueError):
        clone.start_combat(encounter_id='overgrowth_vantom')
    assert saved(clone) == before
    run.start_combat(encounter_id=expected); clone.start_combat(encounter_id=expected)
    assert saved(run) == saved(clone)
    assert run.state.encounter_progression.assignments == {node.node_id: expected}


def test_restricted_exhaustion_can_offer_and_claim_multiple_distinct_circlets():
    run = RunEngine.ironclad_slice()
    run.state.config = replace(run.state.config, relic_fallback='circlet')
    for name in run.state.config.reward_relics:
        add_relic(run.state, name)
    ids = []
    for _ in range(2):
        run.start_combat(encounter_id='overgrowth_byrdonis')
        win_fixture(run)
        assert run.state.pending['relic'] == 'circlet'
        clone = RunEngine(); clone.restore(saved(run))
        step(run, ClaimRelic())
        ids.append(run.state.pending['relic_instance_id'])
        step(run, LeaveRewards())
    assert len(set(ids)) == 2
    assert [r.instance_id for r in run.state.relics if r.definition_id == 'circlet'] == ids


@pytest.mark.parametrize('corrupt', [
    lambda s: s['graph'].__setitem__('generation', 'unknown'),
    lambda s: s['graph'].__setitem__('entry_node_ids', s['graph']['entry_node_ids'][:1]),
    lambda s: s['graph']['nodes'][0].__setitem__('row', True),
    lambda s: s['graph']['nodes'][0].__setitem__('kind', 'rest'),
    lambda s: s['graph']['nodes'][0].__setitem__('column', 6 - s['graph']['nodes'][0]['column']),
    lambda s: s['graph']['nodes'][0].__setitem__('next_node_ids', ['act1.boss']),
    lambda s: s['state'].__setitem__('encounter_progression', None),
    lambda s: s['state']['encounter_progression'].__setitem__('normal_queue', []),
    lambda s: s['state']['encounter_progression']['normal_queue'].__setitem__(1, s['state']['encounter_progression']['normal_queue'][0]),
    lambda s: s['state']['encounter_progression'].__setitem__('boss', 'overgrowth_nibbit'),
    lambda s: s['state']['encounter_progression'].__setitem__('discovery', 'first_run'),
    lambda s: s['state'].__setitem__('combats_completed', 1),
    lambda s: s['state'].__setitem__('phase', 'victory'),
    lambda s: s['state']['encounter_progression']['assignments'].__setitem__('act1.boss', 'overgrowth_vantom'),
    lambda s: s.__setitem__('schema', 'headless_run_state_v9'),
])
def test_malformed_generated_continuation_rejects_atomically(corrupt):
    run = RunEngine.ironclad_act1(map_profile=PROFILE, seed=7)
    before = saved(run)
    altered = deepcopy(before); corrupt(altered)
    with pytest.raises(ValueError):
        run.restore(altered)
    assert saved(run) == before


def test_active_encounter_assignment_cannot_be_changed_on_restore():
    run = RunEngine.ironclad_act1(map_profile=PROFILE, seed=7)
    step(run, run.legal_actions()[0])
    before = saved(run)
    altered = deepcopy(before)
    altered['state']['encounter_progression']['assignments'][run.state.current_node_id] = 'overgrowth_mawler'
    with pytest.raises(ValueError):
        run.restore(altered)
    assert saved(run) == before


def test_generated_demo_uses_normal_inventory_and_reaches_a_real_terminal():
    run, trace = play_slice(route='overgrowth-generated', seed=2, rest_choice='rest', verify_restore=True)
    assert trace and run.state.phase in (RunPhase.DEFEAT, RunPhase.ACT_COMPLETE)
    assert run.state.max_hp < 200
    with pytest.raises(ValueError):
        play_slice(route='overgrowth-generated', boss='overgrowth_vantom')
