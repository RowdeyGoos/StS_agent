"""Real spawned PPO workers: ownership, deterministic sampling and cleanup."""
from dataclasses import replace
import json
import multiprocessing
import os
import threading
import time

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('gymnasium')
from game.agent.runner import RunCancelled, RunFailure
from game.agent.training.checkpoint import load_policy, restore_ppo, save_ppo_checkpoint
from game.agent.training.env import CombatTrainingEnv
from game.agent.training.features import Vocabulary
from game.agent.training.model import ActorCritic, Architecture, policy_statistics
from game.agent.training.parallel import allocations
from game.agent.training.ppo import PPOLearner, replay_batch
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.agent.training.ppo_run import run_ppo
from game.agent.training.rollout import advantages, fingerprint
from game.agent.training.scenarios import episode_seed
from .test_combat_training import fixture
from .test_ppo import controlled_env, long_env, comparable
from .test_training_model import cpu_threads


def learner(*, workers=2, seed=17, env_factory=controlled_env, config=None, encounters=('strike_or_die',)):
    experiment = PPOExperiment(ppo=config or PPOConfig(rollout_steps=8, batch_size=4, epochs=1),
                               encounters=encounters, source='controlled_parallel_v1')
    with controlled_env(encounter='strike_or_die') as env:
        env.reset(seed=0)
        vocabulary = Vocabulary.fit([env.public_state], split='train')
    return PPOLearner(ActorCritic(vocabulary, Architecture(16, 1), seed=0), experiment,
                      seed=seed, env_factory=env_factory, workers=workers)


def child_pids():
    return {p.pid for p in multiprocessing.active_children() if p.name == 'sts-ppo-collector'}


def test_quotas_and_reserved_seed_ranges_are_disjoint_and_bounded():
    assert allocations(7, 3, 100) == ((100, 3), (103, 2), (105, 2))
    assert allocations(2, 8, 4) == ((4, 1), (5, 1))
    for count in range(1, 17):
        ranges = allocations(19, count, 30)
        indexes = [i for start, n in ranges for i in range(start, start+n)]
        assert indexes == list(range(30, 49))
    for args in ((0, 2, 0), (2, True, 0), (2, 17, 0), (1, 2, 2**60-1)):
        with pytest.raises(ValueError):
            allocations(*args)


def test_spawn_collection_has_fixed_total_budget_frozen_policy_and_private_seeds(tmp_path):
    before = child_pids()
    with learner(workers=3) as owner:
        rng = torch.get_rng_state().clone()
        original = fingerprint(owner.model)
        batch = owner.collect(decisions=7, output_dir=tmp_path/'public', audit_dir=tmp_path/'private')
        pids = child_pids()-before
        assert len(pids) == 3
        assert torch.equal(rng, torch.get_rng_state())
        assert batch.behavior == fingerprint(owner.model) == original
        assert len(batch.steps) == batch.next_episode == 7
        assert [b['quota'] for b in batch.progress['worker_batches']] == [3, 2, 2]
        for step in batch.steps:
            original_batch = replay_batch([step], owner.model.vocabulary)
            with torch.inference_mode():
                logits, _ = owner.model(original_batch)
                logp, _ = policy_statistics(logits, original_batch['mask'], torch.tensor([step.action]))
            assert logp.item() == step.old_log_probability
        audits = [json.loads(p.read_text()) for p in (tmp_path/'private').glob('*.audit.json')]
        assert sorted(a['environment_reset_seed'] for a in audits) == [episode_seed('train', i) for i in range(7)]
        assert all(p.stat().st_mode & 0o077 == 0 for p in (tmp_path/'private').iterdir())
        assert 'seed' not in json.dumps(batch.progress) and 'cursor' not in json.dumps(batch.progress)
        owner.update(batch)
        owner.update(owner.collect(decisions=2))
        assert child_pids()-before == pids  # Idle third process survives the small tail.
        assert owner.decisions == owner.episode_cursor == 9
    assert child_pids() == before


def test_parallel_resume_reproduces_next_rounds_weights_and_rng(tmp_path):
    with learner() as left:
        left.update(left.collect())
        bundle, state = tmp_path/'public/model.sts-model', tmp_path/'private/model.resume.pt'
        save_ppo_checkpoint(bundle, left, resume_path=state)
        assert load_policy(bundle).algorithm == 'ppo'
        with restore_ppo(bundle, state, env_factory=controlled_env) as right:
            assert right.collection_settings == left.collection_settings
            for _ in range(2):
                a, b = left.collect(), right.collect()
                assert comparable(a) == comparable(b)
                left.update(a)
                right.update(b)
                assert all(torch.equal(v, right.model.state_dict()[k]) for k, v in left.model.state_dict().items())
            assert left.episode_cursor == right.episode_cursor
            assert torch.equal(left.action_generator.get_state(), right.action_generator.get_state())
            assert torch.equal(left.update_generator.get_state(), right.update_generator.get_state())
        with pytest.raises(ValueError, match='worker allocation'):
            restore_ppo(bundle, state, env_factory=controlled_env, workers=1)


def test_sixteen_collectors_resume_reuses_exact_schedule_and_cleans_up(tmp_path):
    before = child_pids()
    config = PPOConfig(rollout_steps=19, batch_size=8, epochs=1)
    with learner(workers=16, config=config) as owner:
        first = owner.collect()
        assert len(child_pids()-before) == 16
        assert [b['quota'] for b in first.progress['worker_batches']] == [2]*3+[1]*13
        assert len(first.steps) == first.next_episode == 19
        owner.update(first)
        bundle, state = tmp_path/'public/model.sts-model', tmp_path/'private/model.resume.pt'
        save_ppo_checkpoint(bundle, owner, resume_path=state)
        expected = owner.collect()
        owner.update(expected)
        expected_weights = {k:v.clone() for k,v in owner.model.state_dict().items()}
        action_rng = owner.action_generator.get_state()
        update_rng = owner.update_generator.get_state()
    assert child_pids() == before
    with restore_ppo(bundle, state, env_factory=controlled_env) as restored:
        actual = restored.collect()
        assert restored.collection_settings['workers'] == 16
        assert len(child_pids()-before) == 16
        assert comparable(actual) == comparable(expected)
        restored.update(actual)
        assert all(torch.equal(value, restored.model.state_dict()[key]) for key,value in expected_weights.items())
        assert torch.equal(restored.action_generator.get_state(), action_rng)
        assert torch.equal(restored.update_generator.get_state(), update_rng)
        assert restored.decisions == restored.episode_cursor == 38
    assert child_pids() == before
    assert not any(t.name == 'sts-ppo-transfer' for t in threading.enumerate())
    with pytest.raises(ValueError, match='worker allocation'):
        restore_ppo(bundle, state, env_factory=controlled_env, workers=8)


def test_long_episode_cutoffs_keep_gae_separate_and_rotate_encounters():
    config = PPOConfig(rollout_steps=6, episode_decisions=10, batch_size=3, epochs=1)
    with learner(workers=2, env_factory=long_env, config=config,
                 encounters=('region_a', 'region_b', 'region_c')) as owner:
        seen = []
        for _ in range(3):
            batch = owner.collect()
            seen += [e['encounter'] for e in batch.progress['episodes']]
            assert len(batch.progress['episodes']) == 2
            assert [s.episode_step for s in batch.steps] == [0, 1, 2, 0, 1, 2]
            assert batch.steps[2].truncated and batch.steps[5].truncated
            combined, _ = advantages(batch.steps)
            assert torch.equal(combined, torch.cat([advantages(batch.steps[:3])[0], advantages(batch.steps[3:])[0]]))
            owner.update(batch)
        assert seen == ['region_a', 'region_b', 'region_c', 'region_a', 'region_b', 'region_c']
        assert owner.episode_cursor == 18  # Reserved, unused indexes are not reused.


class BrokenEnv(CombatTrainingEnv):
    def step(self, action):
        raise RuntimeError('private sentinel must not enter reports')


def broken_env(**settings):
    return BrokenEnv(engine_factory=lambda seed:fixture(seed, hp=1, enemy_hp=6, relics=()), **settings)


class BlockingEnv(CombatTrainingEnv):
    def step(self, action):
        # Deliberately non-cooperative custom fixture, forced cleanup must work.
        time.sleep(30)
        return super().step(action)


def blocking_env(**settings):
    return BlockingEnv(engine_factory=lambda seed:fixture(seed, hp=1, enemy_hp=6, relics=()), **settings)


class ExitEnv(CombatTrainingEnv):
    def step(self, action):
        os._exit(7)


def exit_env(**settings):
    return ExitEnv(engine_factory=lambda seed:fixture(seed, hp=1, enemy_hp=6, relics=()), **settings)


@pytest.mark.parametrize('factory', [broken_env, exit_env])
def test_worker_failure_closes_pool_and_retains_last_complete_checkpoint(tmp_path, factory):
    before = child_pids()
    with learner(env_factory=factory) as owner:
        bundle, state = tmp_path/'input/model.sts-model', tmp_path/'input-private/model.resume.pt'
        save_ppo_checkpoint(bundle, owner, resume_path=state)
        _, report = run_ppo(checkpoint=bundle, experiment=owner.experiment, output_dir=tmp_path/'run',
                            decisions=8, env_factory=factory, workers=2)
    assert report['status'] == 'failed' and report['summary']['trained_decisions'] == 0
    assert report['last_complete_checkpoint'] == 'initial.sts-model'
    assert 'private sentinel' not in json.dumps(report)
    assert not (tmp_path/'run/final.sts-model').exists()
    assert child_pids() == before


def test_cancellation_kills_noncooperative_workers_and_leaves_partial_recordings(tmp_path):
    before = child_pids()
    stopped = threading.Event()
    def cancel_after_recording():
        until = time.monotonic()+15
        while time.monotonic() < until:
            if len(list((tmp_path/'private').glob('*.audit.json'))) == 2:
                stopped.set()
                return
            time.sleep(.02)
        stopped.set()
    monitor = threading.Thread(target=cancel_after_recording)
    monitor.start()
    with learner(env_factory=blocking_env) as owner:
        started = time.monotonic()
        with pytest.raises(RunCancelled):
            owner.collect(output_dir=tmp_path/'public', audit_dir=tmp_path/'private', cancel=stopped)
        assert time.monotonic()-started < 20
        assert owner.phase == 'failed'
        with pytest.raises(ValueError, match='boundary'):
            save_ppo_checkpoint(tmp_path/'public/bad.sts-model', owner, resume_path=tmp_path/'private/bad.resume.pt')
    monitor.join(1)
    assert child_pids() == before
    assert list((tmp_path/'public').glob('*.partial'))


def test_spawn_failure_cleans_already_started_workers(monkeypatch):
    from multiprocessing.process import BaseProcess
    original = BaseProcess.start
    calls = []
    def fail_second(self):
        calls.append(self)
        if len(calls) == 2:
            raise OSError('controlled spawn failure')
        return original(self)
    before = child_pids()
    monkeypatch.setattr(BaseProcess, 'start', fail_second)
    with learner() as owner:
        with pytest.raises(OSError, match='controlled spawn failure'):
            owner.collect()
        assert owner.phase == 'failed'
    assert child_pids() == before


def test_cancellation_during_spawn_registers_and_reaps_child(monkeypatch):
    import signal
    from multiprocessing.process import BaseProcess
    stopped, before = threading.Event(), child_pids()
    original = BaseProcess.start
    def interrupted(self):
        original(self)
        os.kill(os.getpid(), signal.SIGINT)
    previous = signal.signal(signal.SIGINT, lambda *_: stopped.set())
    monkeypatch.setattr(BaseProcess, 'start', interrupted)
    try:
        with learner() as owner:
            with pytest.raises(RunCancelled):
                owner.collect(cancel=stopped)
        assert child_pids() == before
    finally:
        signal.signal(signal.SIGINT, previous)


def test_hard_deadline_reaps_noncooperative_collectors():
    before, started = child_pids(), time.monotonic()
    with learner(env_factory=blocking_env) as owner:
        with pytest.raises(TimeoutError):
            owner.collect(deadline=started+2.)
        assert owner.phase == 'failed'
    assert time.monotonic()-started < 15
    assert child_pids() == before


def test_full_run_collectors_keep_genuine_region_evidence(tmp_path):
    from game.agent.training.config import TrainingConfig, RUN_SCENARIO_SET
    config = PPOConfig(rollout_steps=4, episode_decisions=20, batch_size=2, epochs=1)
    experiment = PPOExperiment(training=TrainingConfig.full_run(), ppo=config,
        encounters=('overgrowth', 'underdocks'), source=RUN_SCENARIO_SET)
    with PPOLearner(ActorCritic(Vocabulary(()), Architecture(16, 1)), experiment, workers=2) as owner:
        for _ in range(2):
            batch = owner.collect(output_dir=tmp_path/'public', audit_dir=tmp_path/'private')
            assert [e['encounter'] for e in batch.progress['episodes']] == ['overgrowth', 'underdocks']
            assert all(e['evidence'] == 'headless_rollout' for e in batch.progress['episodes'])
            assert all(s.truncated and not s.terminated for s in (batch.steps[1], batch.steps[3]))
            assert all(s.reward == 0 for s in batch.steps)
            owner.update(batch)


@pytest.mark.parametrize('schema',['sts_ppo_resume_v1','sts_ppo_resume_v2'])
def test_legacy_private_serial_state_still_restores_with_same_source(tmp_path,schema):
    from game.agent.training import checkpoint
    with learner(workers=1) as left:
        left.update(left.collect())
        bundle, private = tmp_path/'public/current.sts-model', tmp_path/'private/current.resume.pt'
        save_ppo_checkpoint(bundle, left, resume_path=private)
        state = torch.load(private, weights_only=True)
        if schema == 'sts_ppo_resume_v1':
            state.pop('collection')
        state.pop('update_policy')
        state.pop('skipped_iterations')
        state.pop('bundle_sha256')
        state['schema'] = schema
        old_bundle, old_private = bundle.with_name('old.sts-model'), private.with_name('old.resume.pt')
        state['bundle_sha256'] = checkpoint._save_inference(old_bundle, left.model, left.experiment.training.reward,
            left.updates, left.experiment.to_dict(), algorithm='ppo', resume_digest=checkpoint._state_digest(state))
        checkpoint.publish(old_private, checkpoint._tensor_bytes(state), private=True)
        with restore_ppo(old_bundle, old_private, env_factory=controlled_env) as right:
            assert right.collection_settings['workers'] == 1
            assert comparable(left.collect()) == comparable(right.collect())
        with pytest.raises(ValueError, match='worker allocation'):
            restore_ppo(old_bundle, old_private, env_factory=controlled_env, workers=2)


def test_parallel_merge_matches_identical_jobs_executed_sequentially():
    from game.agent.training.rollout import collect
    with learner(workers=3, config=PPOConfig(rollout_steps=7, batch_size=4, epochs=1)) as owner:
        generator = torch.Generator()
        generator.set_state(owner.action_generator.get_state())
        jobs = allocations(7, 3, 0)
        seeds = torch.randint(0, 2**63-1, (3,), generator=generator).tolist()
        sequential = [collect(owner.model, owner.experiment, torch.Generator().manual_seed(seeds[i]),
            cursor=start, iteration=0, decisions=count, env_factory=controlled_env,
            encounter_cursor=i, encounter_stride=3) for i, (start, count) in enumerate(jobs)]
        expected = replace(sequential[0], steps=tuple(s for batch in sequential for s in batch.steps))
        actual = owner.collect()
        assert comparable(expected) == comparable(actual)
        assert torch.equal(generator.get_state(), owner.action_generator.get_state())
        for left, right in zip(expected.steps, actual.steps):
            import numpy as np
            for name in ('nodes', 'parents', 'positions', 'fields', 'numbers', 'links', 'link_positions', 'candidates'):
                assert np.array_equal(getattr(left.state, name), getattr(right.state, name))
            assert left.state.candidate_refs == right.state.candidate_refs
            assert left.state.legal_mask == right.state.legal_mask


def unresponsive_transport_worker(vocabulary, architecture, experiment, env_factory, stopped, connection):
    # Never read the parent's multi-megabyte command: force a real blocked pipe.
    time.sleep(30)


def test_cancellation_unblocks_a_large_pipe_send(monkeypatch):
    from multiprocessing.connection import Connection
    from game.agent.training import parallel
    before, sending, stopped = child_pids(), threading.Event(), threading.Event()
    original = Connection.send
    def observe_send(self, value):
        if threading.current_thread().name == 'sts-ppo-transfer':
            assert sum(v.nbytes for v in value['weights'].values()) > 1024*1024
            sending.set()
        return original(self, value)
    monkeypatch.setattr(Connection, 'send', observe_send)
    monkeypatch.setattr(parallel, '_worker', unresponsive_transport_worker)
    def cancel_during_send():
        sending.wait(10)
        time.sleep(.1)
        stopped.set()
    monitor = threading.Thread(target=cancel_during_send)
    monitor.start()
    with PPOLearner(ActorCritic(Vocabulary(tuple(f'name_{i:05}' for i in range(4096))), Architecture(128, 4)),
                    PPOExperiment(), workers=2) as owner:
        with pytest.raises(RunCancelled):
            owner.collect(decisions=2, cancel=stopped)
    monitor.join(1)
    assert sending.is_set() and child_pids() == before
    assert not any(t.name == 'sts-ppo-transfer' for t in threading.enumerate())
