"""Gym lifecycle, exact dispatch, independent randomness and sparse run reward."""
from copy import deepcopy
from dataclasses import replace
import json
from random import Random
import subprocess
import sys

import pytest

gym = pytest.importorskip('gymnasium')
np = pytest.importorskip('numpy')

from gymnasium.utils.env_checker import check_env

from game.agent import contracts as c
from game.agent.encoding import CapacityError, DEFAULT_PROFILE, PublicEncoder
from game.agent.gym_env import EnvironmentFailure, StsEnv, combat_map_slice
from game.agent.headless import AdapterFault, UnsupportedProfile
from game.agent.policy import choose_action
from game.headless.run.state import RunPhase
from tests.agent.test_encoding import same_arrays
from tests.agent.test_headless_adapter import fury_game, game


def fury_factory(seed):
    run = fury_game()
    run.combat.enemies[0].hp = 22
    return run


def index_for(env, obs, kind, *, occurrence=0):
    public = env.encoder.decode(obs)
    return [i for i, a in enumerate(public.candidates) if a.kind == kind][occurrence]


def rollout(env, seed):
    obs, info = env.reset(seed=seed)
    trace = []
    contexts, actions = set(), []
    for _ in range(256):
        assert env.observation_space.contains(obs)
        public = env.encoder.decode(obs)
        contexts.add(public.context.kind)
        candidate = choose_action(public)
        index = public.candidates.index(candidate)
        assert obs['action_mask'][index] == 1
        actions.append(candidate.kind)
        trace.append(c.dumps(public))
        obs, reward, terminated, truncated, info = env.step(index)
        trace.append((reward, terminated, truncated, json.dumps(info, sort_keys=True)))
        if terminated or truncated:
            assert env.observation_space.contains(obs)
            return trace, contexts, actions, obs, info
    pytest.fail('Bounded policy failed to reach an endpoint')


def test_gym_checker_unmasked_sampling_and_masked_policy_slice():
    env = StsEnv()
    # The checker deliberately samples Discrete without a mask. Masked slots
    # return an explicit rejection; they do not silently choose a game action.
    check_env(env, skip_render_check=True)
    first = rollout(env, 3)
    second = rollout(env, 3)
    assert first[:3] == second[:3]
    assert first[4]['outcome'] == {'schema': 'sts_run_outcome_v1', 'kind': 'truncated', 'reason': 'slice_complete'}
    assert all(row[0] == 0.0 for row in first[0] if isinstance(row, tuple))
    env.close()
    env.close()


def test_fury_nested_selection_reward_choices_and_subsequent_map_dispatch():
    env = StsEnv(engine_factory=fury_factory)
    _, contexts, actions, final_obs, info = rollout(env, 4)
    assert contexts == {'combat', 'card_selection', 'rewards'}
    assert {'select_card', 'confirm_selection', 'open_card_reward', 'choose_reward_card'} <= set(actions)
    assert env.encoder.decode(final_obs).context.kind == 'map'
    assert final_obs['action_mask'].any()  # Final state remains useful for bootstrapping.
    with pytest.raises(gym.error.ResetNeeded):
        env.step(0)
    # Disabling the authored map cutoff leaves one genuine map decision to policy.
    obs, _ = env.reset(seed=4, options={'stop_at_map': False})
    for _ in range(30):
        public = env.encoder.decode(obs)
        if public.context.kind == 'map':
            break
        candidate = choose_action(public)
        obs, reward, terminated, truncated, _ = env.step(public.candidates.index(candidate))
        assert not terminated and not truncated and reward == 0.0
    else:
        pytest.fail('No map decision')
    obs, reward, terminated, truncated, _ = env.step(index_for(env, obs, 'choose_map_node'))
    assert env.encoder.decode(obs).context.kind == 'combat'
    assert reward == 0.0 and not terminated and not truncated


@pytest.mark.parametrize('bad', [-1, 256, 10**30, 1.0, True, np.bool_(False), '0', None,
                              np.array([0]), np.array(0.0), np.array(True)])
def test_invalid_actions_do_not_mutate_or_advance_game_or_budget(bad):
    env = StsEnv()
    obs, _ = env.reset(seed=5)
    before = deepcopy(env._adapter._engine.snapshot())
    returned, reward, terminated, truncated, info = env.step(bad)
    same_arrays(obs, returned)
    assert env._adapter._engine.snapshot() == before and env._steps == 0
    assert reward == 0.0 and not terminated and not truncated
    assert info['execution'] == {'schema': 'sts_execution_report_v1', 'status': 'rejected',
                                'mutation': 'none', 'reason': 'invalid_action'}


def test_masked_slot_and_caller_mutated_arrays_never_change_dispatch():
    env = StsEnv()
    obs, _ = env.reset(seed=7)
    original = {key: value.copy() for key, value in obs.items()}
    before = env._adapter._engine.snapshot()
    padded = int(np.flatnonzero(obs['action_mask'] == 0)[0])
    obs['action_mask'][:] = 1
    obs['candidates'][:] = 0
    returned, _, _, _, info = env.step(padded)
    same_arrays(original, returned)
    assert info['execution']['reason'] == 'invalid_action'
    assert env._adapter._engine.snapshot() == before


@pytest.mark.parametrize('wrap', [int, np.int32, np.int64, lambda i: np.array(i, dtype=np.int64)])
def test_discrete_scalar_action_forms_execute_the_exact_candidate(wrap):
    env = StsEnv(engine_factory=fury_factory)
    obs, _ = env.reset(seed=3)
    candidate = wrap(index_for(env, obs, 'play_card'))
    assert env.action_space.contains(candidate)
    obs, _, _, _, info = env.step(candidate)
    assert info['execution']['status'] == 'reconciled'
    assert env.encoder.decode(obs).context.kind == 'card_selection'


def test_duplicate_selection_targets_dispatch_to_the_exact_original():
    env = StsEnv(engine_factory=fury_factory)
    obs, _ = env.reset(seed=3)
    obs, *_ = env.step(index_for(env, obs, 'play_card'))
    native_context = env._frame.decision.context
    strikes = [card for pile in native_context.combat.piles for card in pile.cards.value
               if card.ref in native_context.options and card.definition_id == 'strike']
    wanted = strikes[1].ref
    index = next(i for i, ref in enumerate(env._encoded.candidate_refs)
                 if next(a for a in env._frame.decision.candidates if a.ref == ref).subject == wanted)
    obs, *_ = env.step(index)
    assert env._frame.decision.context.selected == (wanted,)
    obs, *_ = env.step(index_for(env, obs, 'deselect_card'))
    assert env._frame.decision.context.selected == ()
    obs, *_ = env.step(index_for(env, obs, 'confirm_selection'))
    assert env.encoder.decode(obs).context.kind == 'combat'


def test_stale_binding_preserves_the_cached_public_decision_without_retry():
    env = StsEnv()
    obs, _ = env.reset(seed=1)
    env._adapter._engine.combat.player.energy += 1  # Deliberate exclusive-owner violation.
    state = env._adapter._engine.snapshot()
    returned, _, _, _, info = env.step(int(np.flatnonzero(obs['action_mask'])[0]))
    same_arrays(obs, returned)
    assert info['execution']['reason'] == 'stale_decision'
    assert env._adapter._engine.snapshot() == state and env._steps == 0


def test_decision_cutoff_preserves_distinct_successor_states_for_bootstrapping():
    def factory(hp):
        def make(seed):
            run = fury_factory(seed)
            run.state.hp = run.combat.player.hp = hp
            return run
        return make
    states = []
    for hp in (80, 40):
        env = StsEnv(engine_factory=factory(hp), max_decisions=1)
        obs, _ = env.reset(seed=1)
        obs, reward, terminated, truncated, info = env.step(index_for(env, obs, 'play_card'))
        assert reward == 0.0 and not terminated and truncated
        assert info['outcome']['reason'] == 'decision_budget'
        public = env.encoder.decode(obs)
        assert public.context.kind == 'card_selection' and public.run.hp == hp
        states.append(obs)
    assert not np.array_equal(states[0]['nodes'], states[1]['nodes'])


def test_time_cutoffs_before_and_after_action_preserve_coherent_public_state(monkeypatch):
    now = [100.0]
    monkeypatch.setattr('game.agent.gym_env.time.monotonic', lambda: now[0])
    env = StsEnv(time_limit_seconds=2)
    obs, _ = env.reset(seed=1)
    before = env._adapter._engine.snapshot()
    now[0] += 3
    returned, reward, terminated, truncated, info = env.step(0)
    same_arrays(obs, returned)
    assert env._adapter._engine.snapshot() == before
    assert reward == 0.0 and not terminated and truncated and info['outcome']['reason'] == 'time_budget'
    obs, _ = env.reset(seed=1)
    original = env._adapter.step
    def delayed(*args):
        result = original(*args)
        now[0] += 3
        return result
    monkeypatch.setattr(env._adapter, 'step', delayed)
    obs, reward, terminated, truncated, info = env.step(index_for(env, obs, 'play_card'))
    assert isinstance(env.encoder.decode(obs), c.PublicDecision)
    assert reward == 0.0 and not terminated and truncated and info['outcome']['reason'] == 'time_budget'


@pytest.mark.parametrize('kind,reason,reward,terminated,truncated', [
    ('victory', 'none', 1.0, True, False), ('defeat', 'none', 0.0, True, False),
    ('abandoned', 'none', 0.0, True, False), ('truncated', 'slice_complete', 0.0, False, True),
    ('truncated', 'act_complete', 0.0, False, True)])
def test_outcome_mapping_and_actual_outcome_precedence_over_budget(monkeypatch, kind, reason, reward, terminated, truncated):
    # Synthetic adapter outcome injection tests mapping, not a full-run victory.
    env = StsEnv(max_decisions=1)
    obs, _ = env.reset(seed=1)
    outcome = c.RunOutcome('sts_run_outcome_v1', kind, reason)
    monkeypatch.setattr(env._adapter, 'observe', lambda: outcome)
    obs, r, term, trunc, info = env.step(index_for(env, obs, 'play_card'))
    assert (r, term, trunc) == (reward, terminated, truncated)
    assert env.encoder.decode(obs) == outcome
    assert info['outcome'] == c.to_dict(outcome)
    assert not obs['action_mask'].any()


def test_real_engine_defeat_is_terminal_and_combat_victory_is_not():
    def doomed(seed):
        run = game(cards=('strike',))
        run.state.hp = run.combat.player.hp = 1
        return run
    env = StsEnv(engine_factory=doomed)
    obs, _ = env.reset(seed=1)
    obs, reward, terminated, truncated, info = env.step(index_for(env, obs, 'end_turn'))
    assert reward == 0.0 and terminated and not truncated
    assert info['outcome']['kind'] == 'defeat'
    def won_combat(seed):
        run = fury_factory(seed)
        run.combat.enemies[0].hp = 1
        return run
    env = StsEnv(engine_factory=won_combat)
    obs, _ = env.reset(seed=1)
    obs, reward, terminated, truncated, info = env.step(index_for(env, obs, 'play_card'))
    assert reward == 0.0 and not terminated and not truncated
    assert env.encoder.decode(obs).context.kind == 'rewards'


def test_terminal_reset_and_safe_close_require_a_new_episode():
    def terminal(seed):
        run = combat_map_slice(seed)
        run.state.phase = RunPhase.VICTORY
        return run
    env = StsEnv(engine_factory=terminal)
    obs, info = env.reset(seed=1)
    assert env.encoder.decode(obs).kind == 'victory'
    with pytest.raises(gym.error.ResetNeeded): env.step(0)
    env.close()
    env.close()
    assert env._adapter is None
    with pytest.raises(gym.error.ResetNeeded): env.step(0)
    assert env.reset(seed=1)[1] == info


@pytest.mark.parametrize('interruption', [RuntimeError, KeyboardInterrupt, SystemExit])
def test_mutation_then_failure_stops_environment_and_never_retries(monkeypatch, interruption):
    env = StsEnv(render_mode='ansi')
    obs, _ = env.reset(seed=1)
    run = env._adapter._engine
    before = run.state.gold
    def fail(action):
        run.state.gold += 10
        raise interruption('private backend diagnostic')
    monkeypatch.setattr(run, 'apply', fail)
    expected = AdapterFault if interruption is RuntimeError else interruption
    with pytest.raises(expected): env.step(index_for(env, obs, 'play_card'))
    assert run.state.gold == before+10
    with pytest.raises(EnvironmentFailure): env.step(0)
    assert run.state.gold == before+10 and env._frame is None
    with pytest.raises(EnvironmentFailure): env.render()
    env.close()
    env.reset(seed=1)


@pytest.mark.parametrize('status,mutation,reason', [('pending', 'queued', 'none'),
    ('uncertain', 'unknown', 'transport_failure'), ('faulted', 'applied', 'cleanup_failure'),
    ('unsupported', 'none', 'unsupported_capability')])
def test_nonreconciled_dispatch_is_typed_failure_not_a_game_result(monkeypatch, status, mutation, reason):
    env = StsEnv()
    obs, _ = env.reset(seed=1)
    monkeypatch.setattr(env._adapter, 'step', lambda *_: c.ExecutionReport('sts_execution_report_v1', status, mutation, reason))
    with pytest.raises(EnvironmentFailure, match='dispatch_'+status): env.step(index_for(env, obs, 'play_card'))
    with pytest.raises(EnvironmentFailure): env.step(0)


def test_unsupported_and_capacity_failures_stop_without_fabricating_transitions(monkeypatch):
    def unsupported(seed):
        run = combat_map_slice(seed)
        from game.headless.run.inventory import add_potion
        add_potion(run.state, 'fire_potion')
        return run
    env = StsEnv(engine_factory=unsupported)
    with pytest.raises(UnsupportedProfile): env.reset(seed=1)
    with pytest.raises(EnvironmentFailure): env.step(0)
    small = StsEnv(profile=replace(DEFAULT_PROFILE, nodes=10))
    with pytest.raises(CapacityError): small.reset(seed=1)
    env = StsEnv(max_decisions=1)
    obs, _ = env.reset(seed=1)
    run, original = env._adapter._engine, env._adapter._engine.apply
    def grow(action):
        value = original(action)
        run.state.gold = 2**31
        return value
    monkeypatch.setattr(run, 'apply', grow)
    with pytest.raises(CapacityError): env.step(index_for(env, obs, 'play_card'))
    with pytest.raises(EnvironmentFailure): env.step(0)


def test_unclassified_backend_exception_becomes_typed_failure(monkeypatch):
    def broken(seed): raise ValueError('private factory detail')
    env = StsEnv(engine_factory=broken)
    with pytest.raises(EnvironmentFailure, match='backend_reset_failure'): env.reset(seed=1)
    env = StsEnv()
    obs, _ = env.reset(seed=1)
    monkeypatch.setattr(env._adapter, 'observe', lambda: 7)
    with pytest.raises(EnvironmentFailure, match='backend_step_failure'): env.step(index_for(env, obs, 'play_card'))
    with pytest.raises(EnvironmentFailure): env.step(0)


def test_two_environments_seeded_resets_sampling_and_policy_rng_are_independent():
    left, right = StsEnv(), StsEnv()
    a, _ = left.reset(seed=81)
    b, _ = right.reset(seed=81)
    same_arrays(a, b)
    left.action_space.seed(5)
    policy_rng = Random(73)
    before = left._adapter._engine.snapshot()
    for _ in range(50):
        left.action_space.sample(mask=a['action_mask'])
        left.observation_space.sample()
        policy_rng.random()
    assert left._adapter._engine.snapshot() == before == right._adapter._engine.snapshot()
    for _ in range(3):
        index = int(np.flatnonzero(a['action_mask'])[0])
        a, *first = left.step(index)
        b, *second = right.step(index)
        same_arrays(a, b)
        assert first == second
    a, _ = left.reset()
    b, _ = right.reset()
    same_arrays(a, b)
    right_snapshot = right._adapter._engine.snapshot()
    left.step(int(np.flatnonzero(a['action_mask'])[0]))
    assert right._adapter._engine.snapshot() == right_snapshot


def test_reset_options_and_info_keep_private_state_out():
    env = StsEnv(render_mode='ansi')
    obs, info = env.reset(seed=123, options={'max_decisions': 1, 'stop_at_map': False})
    assert set(info) == {'encoding', 'execution', 'outcome'}
    assert isinstance(c.loads(env.render()), c.PublicDecision)
    obs, _, _, truncated, info = env.step(index_for(env, obs, 'play_card'))
    assert truncated and info['outcome']['reason'] == 'decision_budget'
    env.reset(seed=123)
    assert env._settings['max_decisions'] == 256 and env._settings['stop_at_map']
    for options in ({'seed': 1}, {'max_decisions': 0}, {'max_decisions': True},
                    {'stop_at_map': 1}, {'time_limit_seconds': float('nan')}):
        with pytest.raises(ValueError): env.reset(options=options)


def test_contract_headless_and_direct_cli_do_not_import_optional_dependencies():
    code = """import sys
from game.agent.headless import HeadlessAdapter
from game.headless.run.engine import RunEngine
from game.agent.policy import choose_action
public=HeadlessAdapter(RunEngine.ironclad_slice(seed=2)).observe().decision
choose_action(public)
assert not {'numpy','gymnasium','torch'}.intersection(sys.modules)
"""
    result = subprocess.run([sys.executable, '-S', '-c', code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
