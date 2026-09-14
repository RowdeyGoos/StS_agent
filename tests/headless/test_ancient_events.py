"""Starting rewards and owned event progression across real room lifecycles."""
from copy import deepcopy
import json

import pytest

from game.cli.headless_play import choose_demo_action, play_slice, main
from game.headless.core.rng import GameRandomService
from game.headless.events.progression import EventProgression, PROFILE as EVENT_PROFILE
from game.headless.run.actions import ChooseAncientRelic, ChooseNode
from game.headless.run.ancient import RESTRICTED_PROFILE as PROFILE, OFFERS, begin
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion, remove_relic
from game.headless.run.state import RunPhase


def saved(run):
    return json.loads(json.dumps(run.snapshot(), sort_keys=True))


def step(run, action):
    clone = RunEngine()
    clone.restore(saved(run))
    assert clone.legal_actions() == run.legal_actions()
    clone.apply(action)
    run.apply(action)
    assert saved(run) == saved(clone)


def synthetic_win(run):
    # Lifecycle coverage only, not a natural policy victory.
    for _ in range(10):
        for enemy in tuple(run.combat.enemies):
            if enemy.is_alive:
                enemy.take_damage(10000, is_attack=False)
    run.combat.resolve_external_effect()
    run.finish_combat()


@pytest.mark.parametrize('relic,hp,gold', [('golden_pearl', 80, 249), ('nutritious_oyster', 91, 99)])
def test_neow_pickup_is_once_owned_and_reaches_first_combat(relic, hp, gold):
    run = RunEngine.ironclad_act1(seed=3, ancient_profile=PROFILE)
    assert run.legal_actions() == tuple(ChooseAncientRelic(r) for r in OFFERS)
    before = saved(run)
    rng_before = run.state.rng.snapshot()
    for _ in range(3):
        run.legal_actions()
    assert saved(run) == before
    with pytest.raises(ValueError):
        run.apply(ChooseNode(run.graph.entry_node_ids[0]))
    with pytest.raises(ValueError):
        run.apply(ChooseAncientRelic('mango'))
    assert saved(run) == before
    step(run, ChooseAncientRelic(relic))
    assert run.state.hp == run.state.max_hp == hp
    assert run.state.gold == gold
    assert run.state.rng.snapshot() == rng_before
    assert run.state.ancient_start.relic_instance_id == run.state.relics[-1].instance_id
    before = saved(run)
    with pytest.raises(ValueError):
        run.apply(ChooseAncientRelic(relic))
    with pytest.raises(ValueError):
        begin(run.state, profile=PROFILE)
    assert saved(run) == before
    step(run, run.legal_actions()[0])
    assert run.combat.player.hp == run.combat.player.max_hp == hp
    assert run.state.gold == gold
    assert any(r.definition_id == relic for r in run.state.relics)


def test_post_ancient_fixture_and_unsupported_start_are_explicit():
    run = RunEngine.ironclad_act1(ancient_profile=None)
    assert run.state.ancient_start is None
    assert all(isinstance(a, ChooseNode) for a in run.legal_actions())
    with pytest.raises(ValueError):
        RunEngine.ironclad_act1(ancient_profile='native_full_neow')
    with pytest.raises(ValueError):
        play_slice(ancient='neow')


def test_pickup_is_not_reapplied_on_restore_or_reversed_on_removal():
    run = RunEngine.ironclad_act1(ancient_profile=PROFILE)
    run.apply(ChooseAncientRelic('nutritious_oyster'))
    for _ in range(3):
        run.restore(saved(run))
    assert run.state.hp == run.state.max_hp == 91
    remove_relic(run.state, run.state.ancient_start.relic_instance_id)
    run.restore(saved(run))
    assert run.state.max_hp == 91
    assert not any(r.definition_id == 'nutritious_oyster' for r in run.state.relics)


@pytest.mark.parametrize('change', [
    lambda s: s['state'].__setitem__('ancient_start', None),
    lambda s: s['state']['ancient_start'].__setitem__('profile', 'full_native'),
    lambda s: s['state']['ancient_start'].__setitem__('selected', 'golden_pearl'),
    lambda s: s['state']['ancient_start'].__setitem__('relic_instance_id', 'run.item.0'),
    lambda s: s['state'].__setitem__('pending', None),
    lambda s: s['state'].__setitem__('phase', 'route'),
    lambda s: s['state']['pending'].__setitem__('profile', 'full_native'),
    lambda s: s.__setitem__('graph', None),
    lambda s: s.__setitem__('schema', 'headless_run_state_v11'),
])
def test_invalid_start_restore_is_atomic(change):
    run = RunEngine.ironclad_act1(ancient_profile=PROFILE)
    before = saved(run)
    bad = deepcopy(before)
    change(bad)
    with pytest.raises(ValueError):
        run.restore(bad)
    assert saved(run) == before


@pytest.mark.parametrize('change', [
    lambda s: s['state']['ancient_start'].__setitem__('selected', 'mango'),
    lambda s: s['state']['ancient_start'].__setitem__('relic_instance_id', 'run.item.0'),
    lambda s: s['state']['ancient_start'].__setitem__('relic_instance_id', 'run.item.999'),
    lambda s: s['state']['ancient_start'].__setitem__('relic_instance_id', 'run.item.01'),
    lambda s: s['state']['ancient_start'].__setitem__('relic_instance_id', None),
])
def test_invalid_claim_history_restore_is_atomic(change):
    run = RunEngine.ironclad_act1(ancient_profile=PROFILE)
    run.apply(ChooseAncientRelic('golden_pearl'))
    before = saved(run)
    bad = deepcopy(before)
    change(bad)
    with pytest.raises(ValueError):
        run.restore(bad)
    assert saved(run) == before


def test_native_unique_queue_then_full_pass_repeat_fallback():
    progression = EventProgression(['aroma_of_chaos', 'jungle_maze_adventure'])
    assert [progression.pull(str(i)) for i in range(6)] == ['aroma_of_chaos', 'jungle_maze_adventure'] * 3
    # Two unique visits, then one full two-entry pass before every repeat.
    assert progression.cursor == 14
    before = deepcopy(progression)
    with pytest.raises(ValueError):
        progression.pull('0')
    assert progression == before
    one = EventProgression(['aroma_of_chaos'])
    assert [one.pull(str(i)) for i in range(3)] == ['aroma_of_chaos'] * 3
    assert one.cursor == 5


def test_event_shuffle_is_owned_once_and_isolated_from_other_draws():
    rng = GameRandomService(18)
    other = GameRandomService(18)
    other.random('reward_gold')
    pool = ('aroma_of_chaos', 'jungle_maze_adventure')
    queue = EventProgression.generate(rng, pool)
    assert queue == EventProgression.generate(other, pool)
    before = rng.snapshot()
    for i in range(5):
        queue.pull(str(i))
    assert rng.snapshot() == before
    assert rng.request_count('act1.events') == 1


@pytest.mark.parametrize('change', [
    lambda s: s['state'].__setitem__('event_progression', None),
    lambda s: s['state']['event_progression'].__setitem__('queue', []),
    lambda s: s['state']['event_progression'].__setitem__('queue', ['aroma_of_chaos'] * 2),
    lambda s: s['state']['event_progression'].__setitem__('cursor', True),
    lambda s: s['state']['event_progression'].__setitem__('cursor', 1),
    lambda s: s['state']['event_progression'].__setitem__('profile', 'locked'),
    lambda s: s['state']['event_progression'].__setitem__('assignments', {'unvisited': 'aroma_of_chaos'}),
])
def test_invalid_event_queue_restore_is_atomic(change):
    run = RunEngine.ironclad_act1()
    before = saved(run)
    bad = deepcopy(before)
    change(bad)
    with pytest.raises(ValueError):
        run.restore(bad)
    assert saved(run) == before


@pytest.mark.parametrize('seed,path,relic', [(0,'left','golden_pearl'), (2,'right','nutritious_oyster'), (4,'left','golden_pearl')])
def test_neow_to_all_bosses_with_synthetic_fights_restores_every_decision(seed,path,relic):
    run = RunEngine.ironclad_act1(seed=seed, ancient_profile=PROFILE)
    step(run, ChooseAncientRelic(relic))
    for _ in range(500):
        if run.state.phase is RunPhase.ACT_COMPLETE:
            break
        if run.state.phase is RunPhase.COMBAT:
            clone = RunEngine(); clone.restore(saved(run))
            synthetic_win(run); synthetic_win(clone)
            assert saved(run) == saved(clone)
        else:
            step(run, choose_demo_action(run, rest_choice='rest', path=path))
    assert run.state.phase is RunPhase.ACT_COMPLETE
    assert len(run.state.visited_nodes) == 16
    events = list(run.state.event_progression.assignments.values())
    assert len(set(events[:2])) == min(2, len(events))
    assert run.state.event_progression.profile == EVENT_PROFILE
    assert run.state.rng.request_count('act1.events') == len(run.state.config.event_pool) - 1
    if events:
        before = saved(run)
        bad = deepcopy(before)
        node_id = next(iter(bad['state']['event_progression']['assignments']))
        bad['state']['event_progression']['assignments'][node_id] = 'bad_event'
        with pytest.raises(ValueError):
            run.restore(bad)
        assert saved(run) == before


def test_cli_neow_start_reports_profile_and_pickup(capsys):
    main(['--route', 'overgrowth-generated', '--ancient', 'neow', '--seed', '2', '--rest-choice', 'rest', '--verify-restore'])
    result = json.loads(capsys.readouterr().out)
    from game.headless.run.ancient import PROFILE as NATIVE_PROFILE
    assert result['ancient_start']['profile'] == NATIVE_PROFILE
    assert result['ancient_start']['selected'] == result['ancient_start']['offers'][0]
    assert result['ancient_start']['selected'] in result['relics']
    assert result['event_profile'] == EVENT_PROFILE
    assert result['restore_verified'] is True
    assert result['phase'] in ('act_complete', 'defeat')


def test_ancient_acquisition_cannot_refer_to_a_potion_instance():
    run = RunEngine.ironclad_act1(ancient_profile=PROFILE)
    run.apply(ChooseAncientRelic('golden_pearl'))
    potion = add_potion(run.state, 'fire_potion')
    before = saved(run)
    bad = deepcopy(before)
    bad['state']['ancient_start']['relic_instance_id'] = potion.instance_id
    with pytest.raises(ValueError, match='potion'):
        run.restore(bad)
    assert saved(run) == before
