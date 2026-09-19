"""Generated Underdocks Act 1: declared pools, complete routes and ownership."""
from copy import deepcopy
import json
import pytest
from game.cli.headless_play import choose_demo_action, play_slice
from game.headless.core.actions import EndTurn
from game.headless.encounters.progression import pools_for, native_ids
from game.headless.events.eligibility import entry_conditions
from game.headless.events.progression import EventProgression, NATIVE_PROFILE
from game.headless.generation.room_pools import ACT1_POOLS, SHARED_EVENTS, ACT1_INELIGIBLE_EVENTS
from game.headless.map.act1 import UNDERDOCKS_PROFILE, UNDERDOCKS_BASE_PROFILE, PROFILE
from game.headless.run.ancient import PROFILE as NEOW
from game.headless.run.actions import ChooseAncientRelic, ChooseNode, LeaveEvent, LeaveRewards
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def clone(run):
    result = RunEngine()
    result.restore(saved(run))
    assert result.legal_actions() == run.legal_actions()
    return result


def step(run, action):
    copy = clone(run)
    copy.apply(action)
    run.apply(action)
    assert saved(copy) == saved(run)


@pytest.mark.parametrize('profile', ['fixture', 'native'])
@pytest.mark.parametrize('seed', range(12))
def test_underdocks_start_owns_pools_and_pure_restoration(profile, seed):
    run = RunEngine.ironclad_act1(seed=seed, act='underdocks', rng_profile=profile, ancient_profile=NEOW)
    weak, normal, elites, bosses = pools_for('underdocks')
    q = run.state.encounter_progression
    assert run.state.config.act == q.act == 'underdocks'
    assert run.graph.generation == UNDERDOCKS_PROFILE
    assert len(q.normal_queue) == len(q.elite_queue) == 15
    assert len(set(q.normal_queue[:3])) == 3 and set(q.normal_queue[:3]) <= set(weak)
    assert set(q.normal_queue[3:]) == set(normal)
    assert q.boss in bosses
    for i in range(0, 15, 3):
        assert set(q.elite_queue[i:i + 3]) == set(elites)
    for a, b in zip(q.normal_queue, q.normal_queue[1:]):
        assert a != b
        for family in ('corpse_slugs', 'seapunk'):
            assert not (a.startswith('underdocks_' + family) and b.startswith('underdocks_' + family))
    local_events = set(ACT1_POOLS['underdocks'][3])
    expected = local_events | set(SHARED_EVENTS)
    assert set(run.state.event_progression.queue) == (expected if profile == 'native' else expected - set(ACT1_INELIGIBLE_EVENTS))
    assert set(run.state.config.event_pool) == expected - set(ACT1_INELIGIBLE_EVENTS)
    if profile == 'native':
        assert [a['act'] for a in run.state.initialization['acts']] == ['underdocks', 'hive', 'glory']
        assert run.state.initialization['acts'][0]['ancient'] == 'neow'
    before = saved(run)
    for _ in range(3): run.legal_actions()
    assert saved(run) == before == saved(clone(run))
    assert all(isinstance(a, ChooseAncientRelic) for a in run.legal_actions())
    step(run, run.legal_actions()[0])
    for _ in range(30):
        if not run.state.relic_work: break
        step(run, choose_demo_action(run))
    step(run, next(a for a in run.legal_actions() if isinstance(a, ChooseNode)))
    assert run.state.active_encounter_id == q.normal_queue[0]
    clone(run)


def win_fixture(run):
    """Synthetic combat victories test room flow, not policy strength or live parity."""
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
    pytest.fail('Encounter did not terminate.')


@pytest.mark.parametrize('seed,path', [(0, 'left'), (2, 'right'), (7, 'left')])
@pytest.mark.parametrize('profile', ['native', 'fixture'])
def test_generated_run_to_act_completion_with_every_decision_restored(seed, path, profile):
    run = RunEngine.ironclad_act1(seed=seed, act='underdocks', rng_profile=profile, ancient_profile=NEOW)
    run.state.max_hp = run.state.hp = 10000
    for _ in range(600):
        if run.state.phase is RunPhase.COMBAT:
            copy = clone(run)
            win_fixture(run); win_fixture(copy)
            assert saved(run) == saved(copy)
        if run.state.phase is RunPhase.ACT_COMPLETE:
            break
        actions = run.legal_actions()
        action = next((a for a in actions if isinstance(a, LeaveEvent)), None) or choose_demo_action(run, rest_choice='rest', path=path)
        step(run, action)
    assert run.state.phase is RunPhase.ACT_COMPLETE
    assert len(run.state.visited_nodes) == 16
    q = run.state.encounter_progression
    assert run.state.act_completion.boss_encounter_id == q.boss
    assert set(q.assignments.values()) <= set(native_ids('underdocks').values())
    assert run.state.combats_completed == len(q.assignments) + len(run.state.event_combats)
    clone(run)


@pytest.mark.parametrize('profile', ['fixture', 'native'])
@pytest.mark.parametrize('corrupt', [
    lambda s: s['state']['config'].__setitem__('act', 'overgrowth'),
    lambda s: s['state']['encounter_progression'].__setitem__('act', 'overgrowth'),
    lambda s: s['graph'].__setitem__('generation', PROFILE),
    lambda s: s['state']['encounter_progression'].__setitem__('boss', 'overgrowth_vantom'),
    lambda s: s['state']['encounter_progression']['normal_queue'].__setitem__(0, 'overgrowth_fuzzy'),
    lambda s: s['state']['event_progression']['queue'].__setitem__(0, 'jungle_maze_adventure'),
    lambda s: s['state']['config'].pop('act'),
    lambda s: s['state']['encounter_progression'].pop('act'),
])
def test_mixed_act_snapshots_reject_atomically(profile, corrupt):
    run = RunEngine.ironclad_act1(seed=3, act='underdocks', rng_profile=profile)
    before = saved(run)
    bad = deepcopy(before); corrupt(bad)
    with pytest.raises(ValueError): run.restore(bad)
    assert saved(run) == before


def test_all_local_events_reachable_and_native_entry_gates_respected():
    run = RunEngine.ironclad_act1(act='underdocks')
    conditions = entry_conditions(run.state)
    conditions.update(gold=200, floor=10)
    for name in ACT1_POOLS['underdocks'][3]:
        q = EventProgression([name, 'drowning_beacon'], profile=NATIVE_PROFILE)
        assert q.pull('event', conditions=conditions) == name
    for name, changed in (
        ('endless_conveyor', {'gold': 119}), ('punch_off', {'floor': 5}),
        ('spiraling_whirlpool', {'enchant_spiral': 0}), ('trash_heap', {'hp': 5}),
        ('waterlogged_scriptorium', {'gold': 54}),
    ):
        q = EventProgression([name, 'drowning_beacon'], profile=NATIVE_PROFILE)
        assert q.pull('event', conditions={**conditions, **changed}) == 'drowning_beacon'


@pytest.mark.parametrize('profile', ['fixture', 'native'])
def test_base_map_variant_and_unsupported_inputs(profile):
    run = RunEngine.ironclad_act1(act='underdocks', rng_profile=profile, map_profile=UNDERDOCKS_BASE_PROFILE)
    assert run.state.unknown_rooms is run.state.event_progression is None
    assert all(n.event_id in run.state.config.event_pool for n in run.graph.nodes if n.kind == 'event')
    clone(run)
    for kwargs in ({'act': 'hive'}, {'act': 'underdocks', 'map_profile': PROFILE}, {'act': 'underdocks', 'discovery': 'first_run'}, {'act': 'underdocks', 'ascension': 1}):
        with pytest.raises(ValueError): RunEngine.ironclad_act1(rng_profile=profile, **kwargs)


def test_cli_underdocks_route_with_neow_restores_natural_trajectory():
    run, trace = play_slice(route='underdocks-generated', ancient='neow', seed=2, verify_restore=True)
    assert run.state.phase in (RunPhase.DEFEAT, RunPhase.ACT_COMPLETE)
    assert trace[0]['action'] == 'ChooseAncientRelic'
    assert run.state.config.act == 'underdocks' and run.state.combats_completed > 0
