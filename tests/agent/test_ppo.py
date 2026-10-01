"""PPO math, task boundaries, frozen masks and exact CPU batch continuation."""
from dataclasses import replace
import io
import threading

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('gymnasium')
from game.agent.runner import RunCancelled
from game.agent.training.checkpoint import load_policy, publish, save_ppo_checkpoint, restore_ppo
from game.agent.training.env import CombatTrainingEnv
from game.agent.training.features import Vocabulary
from game.agent.training.model import ActorCritic, Architecture
from game.agent.training.ppo import PPOLearner, normalize, objective, replay_batch
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.agent.training.rollout import RolloutStep, advantages
from game.agent.training.records import load_training_episode
from .test_combat_training import fixture
from .test_training_model import cpu_threads


def controlled_env(**settings):
    return CombatTrainingEnv(engine_factory=lambda seed:fixture(seed, hp=1, enemy_hp=6, relics=()), **settings)


def owner(seed=0, *, env_factory=controlled_env, config=None, workers=1, architecture=None):
    experiment = PPOExperiment(ppo=config or PPOConfig(rollout_steps=16, batch_size=8, epochs=2),
                               encounters=('strike_or_die',), source='controlled_strike_or_die_v1')
    with env_factory(encounter='strike_or_die') as env:
        env.reset(seed=0)
        vocabulary = Vocabulary.fit([env.public_state], split='train')
    return PPOLearner(ActorCritic(vocabulary, architecture or Architecture(16, 1), seed=seed), experiment,
                      seed=seed, env_factory=env_factory, workers=workers)


def numeric_step(*, value, next_value, reward, episode='a', index=0, terminated=False, truncated=False):
    return RolloutStep(None, (), (), 0, -.5, value, next_value, reward, {},
                       terminated, truncated, episode, index)


def test_gae_matches_hand_calculation_and_stops_at_each_reset():
    rows = [numeric_step(value=.2, next_value=.4, reward=0),
            numeric_step(value=.4, next_value=0, reward=1, index=1, terminated=True),
            numeric_step(value=.1, next_value=.7, reward=.3, episode='b', truncated=True),
            numeric_step(value=.9, next_value=0, reward=0, episode='c', terminated=True)]
    adv, returns = advantages(rows, gamma=1, gae_lambda=.5)
    assert adv.tolist() == pytest.approx([.5, .6, .9, -.9])
    assert returns.tolist() == pytest.approx([.7, 1, 1, 0])
    with pytest.raises(ValueError, match='close'):
        advantages(rows[:1])
    with pytest.raises(ValueError):
        advantages([replace(rows[1], next_value=999)])
    assert torch.equal(normalize(torch.tensor([2.])), torch.tensor([2.]))
    assert torch.equal(normalize(torch.ones(3)), torch.ones(3))


def test_clipped_objective_uses_the_correct_side_for_both_advantage_signs():
    new = torch.log(torch.tensor([.5, .25])).requires_grad_()
    old = torch.log(torch.tensor([.25, .5]))
    zero = torch.zeros(2)
    loss, stats = objective(new, old, torch.tensor([1., -1.]), zero, zero, zero, PPOConfig())
    assert loss.item() == pytest.approx(-.2)
    assert stats['clip_fraction'] == 1
    loss.backward()
    assert new.grad.tolist() == [0, 0]
    with pytest.raises(ValueError, match='Nonfinite'):
        objective(torch.tensor([1000.]), torch.tensor([-1.]), torch.ones(1),
                  torch.zeros(1), torch.zeros(1), torch.zeros(1), PPOConfig())


def test_real_wins_and_defeats_use_task_flags_not_canonical_run_cutoffs():
    learner = owner()
    global_rng = torch.get_rng_state().clone()
    rollout = learner.collect()
    assert torch.equal(global_rng, torch.get_rng_state())
    assert len(rollout.steps) == 16
    assert {s.reward for s in rollout.steps} == {0, 1}
    assert all(s.terminated and not s.truncated and s.next_value == 0 for s in rollout.steps)
    wins = [e for e in rollout.progress['episodes'] if e['combat']['outcome']=='victory']
    assert wins and all(e['outcome']['kind']=='truncated' for e in wins)
    assert all(s.mask[s.action] and s.candidate_refs == s.state.candidate_refs for s in rollout.steps)
    result = learner.update(rollout)
    assert result['optimizer_steps'] > 0 and learner.phase == 'boundary' and learner.episode_cursor == 16
    with pytest.raises(ValueError):
        learner.update(rollout)


@pytest.mark.parametrize('damage', ('references', 'legal_mask', 'policy_mask', 'candidates'))
def test_compact_rollout_keeps_independent_action_mapping_checks(damage):
    with owner() as learner:
        rollout = learner.collect()
        step = rollout.steps[0]
        state = step.state
        if damage == 'references':
            state = replace(state, candidate_refs=tuple(reversed(state.candidate_refs)))
        elif damage == 'legal_mask':
            state = replace(state, legal_mask=tuple(False for _ in state.legal_mask))
        elif damage == 'policy_mask':
            state = replace(state, policy_mask=tuple(False for _ in state.policy_mask))
        else:
            state = replace(state, candidates=state.candidates[:-1])
        with pytest.raises(ValueError, match='mapping'):
            replay_batch([replace(step, state=state)], learner.model.vocabulary)


def long_env(**settings):
    return CombatTrainingEnv(engine_factory=lambda seed:fixture(seed, hp=80, enemy_hp=100, relics=()), **settings)


def test_quota_cutoff_bootstraps_the_actual_last_public_observation(tmp_path):
    final_states = []
    class EndingEnv(CombatTrainingEnv):
        def close(self):
            if getattr(self, '_public_state', None) is not None:
                final_states.append(self.public_state)
            super().close()
    def make(**settings):
        return EndingEnv(engine_factory=lambda seed:fixture(seed, hp=80, enemy_hp=100, relics=()), **settings)
    learner = owner(env_factory=make)
    final_states.clear()
    rollout = learner.collect(decisions=1, output_dir=tmp_path/'public', audit_dir=tmp_path/'private')
    step = rollout.steps[0]
    assert step.truncated and not step.terminated and len(final_states)==1
    from game.agent.training.features import FeatureEncoder
    from game.agent.training.model import collate
    state = FeatureEncoder(learner.model.vocabulary).encode(final_states[0])
    with torch.inference_mode():
        _, value = learner.model(collate([state], vocabulary=learner.model.vocabulary))
    assert step.next_value == value.item()
    row = rollout.progress['episodes'][0]
    recorded = load_training_episode(tmp_path/'public'/row['trajectory'], tmp_path/'public'/row['training'], split='train')
    assert len(recorded.transitions)==1 and recorded.ending.truncated


@pytest.mark.parametrize('after_one', [False, True])
def test_action_free_timeout_does_not_invent_a_transition_or_loop(after_one, tmp_path):
    class TimeoutEnv(CombatTrainingEnv):
        expired = False
        def _time_expired(self):
            return self.expired
        def step(self, action):
            if not after_one:
                self.expired = True
            result = super().step(action)
            self.expired = True
            return result
    def make(**settings):
        return TimeoutEnv(engine_factory=lambda seed:fixture(seed, hp=80, enemy_hp=100, relics=()), **settings)
    learner = owner(env_factory=make)
    rollout = learner.collect(output_dir=tmp_path/'public', audit_dir=tmp_path/'private')
    assert len(rollout.steps) == int(after_one) and rollout.next_episode == 1
    assert rollout.progress['stop_reason'] == 'time_budget'
    row = rollout.progress['episodes'][0]
    recorded = load_training_episode(tmp_path/'public'/row['trajectory'], tmp_path/'public'/row['training'], split='train')
    assert len(recorded.transitions) == int(after_one) and recorded.ending.truncated
    if after_one:
        assert rollout.steps[0].truncated and not rollout.steps[0].terminated


def test_masks_mappings_and_old_likelihood_cannot_be_replaced():
    learner = owner()
    rollout = learner.collect(decisions=1)
    step = rollout.steps[0]
    for changed in (replace(step, mask=(False,)*len(step.mask)), replace(step, candidate_refs=()),
                    replace(step, old_log_probability=float('nan')), replace(step, action=999)):
        with pytest.raises(ValueError):
            replay_batch([changed], learner.model.vocabulary)


def comparable(rollout):
    return [(s.action, s.old_log_probability, s.value, s.next_value, s.reward, s.terminated,
             s.truncated, s.mask, s.candidate_refs) for s in rollout.steps]


def test_shared_graph_rollout_matches_custom_encoder_and_releases_current_state():
    from game.agent.encoding.full import FullRunEncoder
    from game.agent.training.features import _RolloutEncoder
    class CustomEncoder(FullRunEncoder):
        pass
    environments = []
    def make(*, fallback=False, **settings):
        env = controlled_env(**settings)
        if fallback:
            env.encoder = CustomEncoder(env.encoder.profile)
        environments.append(env)
        return env
    shared = owner(env_factory=make)
    custom = owner(env_factory=lambda **settings: make(fallback=True, **settings))
    environments.clear()
    left, right = shared.collect(decisions=3), custom.collect(decisions=3)
    assert comparable(left) == comparable(right)
    assert any(type(env.encoder) is _RolloutEncoder for env in environments)
    for env in environments:
        if type(env.encoder) is _RolloutEncoder:
            assert env.encoder._decision is env.encoder._graph is None
        else:
            assert type(env.encoder) is CustomEncoder
    for a, b in zip(left.steps, right.steps):
        assert a.state.candidate_refs == b.state.candidate_refs
        assert a.state.legal_mask == b.state.legal_mask
        for key in ('nodes', 'parents', 'positions', 'fields', 'numbers', 'links', 'link_positions', 'candidates'):
            assert (getattr(a.state, key) == getattr(b.state, key)).all()
    ma, mb = shared.update(left), custom.update(right)
    assert {k:v for k,v in ma.items() if k != 'seconds'} == {k:v for k,v in mb.items() if k != 'seconds'}
    assert all(torch.equal(v, custom.model.state_dict()[k]) for k,v in shared.model.state_dict().items())


@pytest.mark.parametrize('boundary', ('reset', 'step'))
def test_shared_graph_is_released_after_collection_failure(boundary, monkeypatch):
    from game.agent.training.features import _RolloutEncoder
    environments = []
    def make(**settings):
        env = controlled_env(**settings)
        environments.append(env)
        return env
    learner = owner(env_factory=make)
    environments.clear()
    original = getattr(CombatTrainingEnv, boundary)
    def fail(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError('forced collection failure')
    monkeypatch.setattr(CombatTrainingEnv, boundary, fail)
    with pytest.raises(RuntimeError, match='forced collection failure'):
        learner.collect(decisions=1)
    assert learner.phase == 'failed' and len(environments) == 1
    env = environments[0]
    assert type(env.encoder) is _RolloutEncoder
    assert env.encoder._decision is env.encoder._graph is env.public_state is None


def test_cpu_resume_reproduces_collection_updates_rng_and_next_episode(tmp_path):
    a = owner()
    a.update(a.collect())
    public, private = tmp_path/'public/model.sts-model', tmp_path/'private/model.resume.pt'
    save_ppo_checkpoint(public, a, resume_path=private)
    assert load_policy(public).algorithm == 'ppo' and load_policy(public).identity.startswith('ppo_v1:')
    b = restore_ppo(public, private, env_factory=controlled_env)
    for _ in range(2):
        left, right = a.collect(), b.collect()
        assert comparable(left) == comparable(right)
        ma, mb = a.update(left), b.update(right)
        assert {k:v for k,v in ma.items() if k!='seconds'} == {k:v for k,v in mb.items() if k!='seconds'}
        assert all(torch.equal(v, b.model.state_dict()[k]) for k,v in a.model.state_dict().items())
    assert (a.episode_cursor, a.decisions, a.iterations, a.updates)==(b.episode_cursor, b.decisions, b.iterations, b.updates)
    assert torch.equal(a.action_generator.get_state(), b.action_generator.get_state())
    assert torch.equal(a.update_generator.get_state(), b.update_generator.get_state())


def test_resume_rejects_changed_source_or_experiment(tmp_path, monkeypatch):
    from game.agent.training import checkpoint
    learner = owner()
    public, private = tmp_path/'public/model.sts-model', tmp_path/'private/model.resume.pt'
    save_ppo_checkpoint(public, learner, resume_path=private)
    changed = replace(learner.experiment, ppo=replace(learner.config, gamma=.99))
    with pytest.raises(ValueError, match='experiment'):
        restore_ppo(public, private, experiment=changed, env_factory=controlled_env)
    identity = checkpoint.implementation()
    monkeypatch.setattr(checkpoint, 'implementation', lambda:replace(identity, build='0'*64))
    with pytest.raises(ValueError, match='unchanged'):
        restore_ppo(public, private, env_factory=controlled_env)


def test_policy_randomness_does_not_change_environment_reset_stream():
    resets = []
    class RecordingEnv(CombatTrainingEnv):
        def reset(self, **kwargs):
            result = super().reset(**kwargs)
            resets.append(self.public_state)
            return result
    def make(**settings):
        return RecordingEnv(engine_factory=lambda seed:fixture(seed, cards=('strike', 'defend', 'bash'),
                            hp=80, enemy_hp=100, relics=()), **settings)
    config = PPOConfig(rollout_steps=4, episode_decisions=1)
    a, b = owner(seed=0, env_factory=make, config=config), owner(seed=7, env_factory=make, config=config)
    resets.clear()
    a.collect()
    first = resets.copy()
    resets.clear()
    b.collect()
    assert first == resets and len(resets)==4
    assert not torch.equal(a.action_generator.get_state(), b.action_generator.get_state())


@pytest.mark.parametrize('key,value', [('episode_cursor',100), ('iterations',0), ('decisions',999),
                                     ('boundary','mid_combat'), ('runtime',{})])
def test_private_state_is_bound_to_its_public_checkpoint(tmp_path, key, value):
    a = owner()
    a.update(a.collect(decisions=4))
    public, private = tmp_path/'public/model.sts-model', tmp_path/'private/model.resume.pt'
    save_ppo_checkpoint(public, a, resume_path=private)
    state = torch.load(private, weights_only=True)
    state[key] = value
    data = io.BytesIO()
    torch.save(state, data)
    changed = private.parent/'changed.resume.pt'
    publish(changed, data.getvalue(), private=True)
    with pytest.raises(ValueError):
        restore_ppo(public, changed, env_factory=controlled_env)


def test_cancellation_closes_environment_and_forbids_partial_checkpoint(tmp_path):
    stopped, closed = threading.Event(), []
    class CancelEnv(CombatTrainingEnv):
        def step(self, action):
            result = super().step(action)
            stopped.set()
            return result
        def close(self):
            if getattr(self, '_adapter', None) is not None:
                closed.append(True)
            super().close()
    def make(**settings):
        return CancelEnv(engine_factory=lambda seed:fixture(seed, hp=80, enemy_hp=100, relics=()), **settings)
    learner = owner(env_factory=make)
    closed.clear()
    with pytest.raises(RunCancelled):
        learner.collect(cancel=stopped)
    assert closed == [True] and learner.phase == 'failed'
    with pytest.raises(ValueError, match='boundary'):
        save_ppo_checkpoint(tmp_path/'public/failed.sts-model', learner, resume_path=tmp_path/'private/failed.resume.pt')


def test_pending_batch_and_cancelled_update_never_publish(tmp_path):
    learner = owner()
    batch = learner.collect(decisions=4)
    with pytest.raises(ValueError, match='boundary'):
        save_ppo_checkpoint(tmp_path/'public/pending.sts-model', learner, resume_path=tmp_path/'private/pending.resume.pt')
    stopped = threading.Event()
    stopped.set()
    with pytest.raises(RunCancelled):
        learner.update(batch, cancel=stopped)
    assert learner.phase=='failed' and learner.updates==0


def test_deadline_during_final_measurement_cannot_commit_a_boundary(monkeypatch):
    from game.agent.training import ppo
    learner = owner(config=PPOConfig(rollout_steps=1, batch_size=1, epochs=1))
    batch = learner.collect()
    now = [0.]
    measure = learner._measure
    def crossing(*args, **kwargs):
        result = measure(*args, **kwargs)
        now[0] = 2.
        return result
    monkeypatch.setattr(ppo.time, 'monotonic', lambda:now[0])
    monkeypatch.setattr(learner, '_measure', crossing)
    with pytest.raises(TimeoutError):
        learner.update(batch, deadline=1.)
    assert learner.phase=='failed' and learner.iterations==learner.decisions==0 and learner.updates==1


@pytest.mark.parametrize('expired', [False, True])
def test_measurement_checks_cancellation_and_deadline_between_batches(monkeypatch, expired):
    from game.agent.training import ppo
    learner = owner(config=PPOConfig(rollout_steps=2, batch_size=1, epochs=1))
    batch = learner.collect()
    adv, returns = advantages(batch.steps)
    stopped, now, calls = threading.Event(), [0.], []
    forward = learner.model.forward
    def interrupt(*args, **kwargs):
        result = forward(*args, **kwargs)
        calls.append(True)
        if expired:
            now[0] = 2.
        else:
            stopped.set()
        return result
    monkeypatch.setattr(learner.model, 'forward', interrupt)
    monkeypatch.setattr(ppo.time, 'monotonic', lambda:now[0])
    with pytest.raises(TimeoutError if expired else RunCancelled):
        learner._measure(batch.steps, adv, returns, cancel=stopped, deadline=1.)
    assert calls == [True]


@pytest.mark.parametrize('mode', ['zero_progress', 'environment_failure', 'partial_update'])
def test_experiment_retains_complete_checkpoint_on_stopped_work(tmp_path, monkeypatch, mode):
    from game.agent.training.ppo_run import run_ppo
    learner, stopped = owner(), threading.Event()
    public, private = tmp_path/'input/model.sts-model', tmp_path/'input-private/model.resume.pt'
    save_ppo_checkpoint(public, learner, resume_path=private)
    factory = controlled_env
    if mode == 'partial_update':
        original = PPOLearner._measure
        def interrupt(self, *args, **kwargs):
            result = original(self, *args, **kwargs)
            stopped.set()
            return result
        monkeypatch.setattr(PPOLearner, '_measure', interrupt)
    else:
        class StopEnv(CombatTrainingEnv):
            def _time_expired(self):
                return mode == 'zero_progress'
            def step(self, action):
                if mode == 'environment_failure':
                    raise RuntimeError('controlled failure')
                return super().step(action)
        def factory(**settings):
            return StopEnv(engine_factory=lambda seed:fixture(seed, hp=1, enemy_hp=6, relics=()), **settings)
    output = tmp_path/'experiment'
    path, report = run_ppo(checkpoint=public, experiment=learner.experiment, output_dir=output,
                          decisions=4, env_factory=factory, cancel=stopped)
    assert path.is_file() and report['last_complete_checkpoint']=='initial.sts-model'
    assert report['summary']['trained_decisions']==0
    assert report['status']=={'zero_progress':'budget_reached', 'environment_failure':'failed',
                              'partial_update':'cancelled'}[mode]
    assert report['summary']['accepted_decisions']==(4 if mode=='partial_update' else 0)
    restored = restore_ppo(output/'initial.sts-model', tmp_path/'experiment-private/initial.resume.pt',
                           env_factory=controlled_env)
    assert restored.iterations==restored.updates==restored.decisions==0
    assert all(torch.equal(p, restored.model.state_dict()[k]) for k,p in learner.model.state_dict().items())
    assert not (output/'final.sts-model').exists()


@pytest.mark.parametrize('workers', [1, 2])
def test_cli_sigterm_publishes_cancelled_report_and_retains_resume(tmp_path, workers):
    import json
    from pathlib import Path
    import signal
    import subprocess
    import sys
    import time
    learner = owner()
    public, private = tmp_path/'input/model.sts-model', tmp_path/'input-private/model.resume.pt'
    save_ppo_checkpoint(public, learner, resume_path=private)
    output = tmp_path/'experiment'
    process = subprocess.Popen([sys.executable, '-m', 'game.cli.agent_train', 'ppo',
        '--checkpoint', str(public), '--config', 'configs/training/combat_ppo.json',
        '--output-dir', str(output), '--decisions', '20000', '--time-limit', '120', '--workers', str(workers)],
        cwd=Path(__file__).resolve().parents[2], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic()+30
        while not (tmp_path/'experiment-private/initial.resume.pt').exists():
            assert process.poll() is None, process.communicate()
            assert time.monotonic() < deadline
            time.sleep(.02)
        if workers > 1:
            while len(list((tmp_path/'experiment-private').glob('*.audit.json'))) < workers:
                assert process.poll() is None, process.communicate()
                assert time.monotonic() < deadline
                time.sleep(.02)
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode==130, (stdout, stderr)
        report = json.loads((output/'ppo.json').read_text())
        assert report['status']=='cancelled' and report['last_complete_checkpoint']=='initial.sts-model'
        assert report['summary']['trained_decisions']==0
        assert restore_ppo(output/'initial.sts-model', tmp_path/'experiment-private/initial.resume.pt').updates==0
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)


@pytest.mark.parametrize('change', [{'gamma':0}, {'gamma':float('nan')}, {'batch_size':True},
                                  {'epochs':0}, {'clip_ratio':1}, {'target_kl':0}])
def test_invalid_configurations_reject(change):
    with pytest.raises(ValueError):
        PPOConfig(**change)
