"""CPU execution settings preserve deterministic PPO continuation and CLI ownership."""
import json
import multiprocessing
from types import SimpleNamespace

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('gymnasium')
from game.agent.training.checkpoint import load_policy, restore_ppo, runtime, save_ppo_checkpoint
from game.agent.training.model import Architecture
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.cli.agent_train import main, _configure_ppo_cpu
from .test_ppo import comparable, long_env, owner


@pytest.fixture(autouse=True)
def restore_cpu_settings():
    settings = (torch.get_num_threads(), torch.are_deterministic_algorithms_enabled(),
                torch.is_deterministic_algorithms_warn_only_enabled())
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(False)
    yield
    torch.set_num_threads(settings[0])
    torch.use_deterministic_algorithms(settings[1], warn_only=settings[2])


def single_thread_collector(**settings):
    if multiprocessing.current_process().name == 'sts-ppo-collector':
        assert torch.get_num_threads() == 1
    return long_env(**settings)


def equal_state(left, right):
    if isinstance(left, torch.Tensor):
        return torch.equal(left, right)
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal_state(left[k], right[k]) for k in left)
    if isinstance(left, (tuple, list)):
        return len(left) == len(right) and all(equal_state(a, b) for a, b in zip(left, right))
    return left == right


def test_four_thread_update_and_spawned_collectors_resume_exactly(tmp_path):
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    config = PPOConfig(rollout_steps=32, batch_size=16, epochs=2)
    public, private = tmp_path/'public/model.sts-model', tmp_path/'private/model.resume.pt'
    with owner(env_factory=single_thread_collector, config=config, workers=2,
               architecture=Architecture(48, 2)) as uninterrupted:
        uninterrupted.update(uninterrupted.collect())
        save_ppo_checkpoint(public, uninterrupted, resume_path=private)
        saved = load_policy(public).manifest['runtime']
        assert saved['threads'] == 4 and saved['deterministic_algorithms']
        assert saved['deterministic_warn_only'] is False
        with restore_ppo(public, private, env_factory=single_thread_collector) as restored:
            for _ in range(2):
                a, b = uninterrupted.collect(), restored.collect()
                assert comparable(a) == comparable(b)
                left, right = uninterrupted.update(a), restored.update(b)
                assert {k:v for k,v in left.items() if k != 'seconds'} == {
                    k:v for k,v in right.items() if k != 'seconds'}
                assert equal_state(uninterrupted.model.state_dict(), restored.model.state_dict())
                assert equal_state(uninterrupted.optimizer.state_dict(), restored.optimizer.state_dict())
                assert torch.equal(uninterrupted.action_generator.get_state(), restored.action_generator.get_state())
                assert torch.equal(uninterrupted.update_generator.get_state(), restored.update_generator.get_state())
        for threads, deterministic, warn_only in ((1, True, False), (4, False, False), (4, True, True)):
            torch.set_num_threads(threads)
            torch.use_deterministic_algorithms(deterministic, warn_only=warn_only)
            with pytest.raises(ValueError, match='resume state'):
                restore_ppo(public, private, env_factory=single_thread_collector)


@pytest.mark.parametrize('change', (
    {'threads':True}, {'threads':0}, {'threads':16},
    {'deterministic_algorithms':1}, {'deterministic_warn_only':0},
    {'deterministic_algorithms':False}, {'deterministic_warn_only':True},
))
def test_resume_rejects_invalid_or_nondeterministic_saved_execution(change):
    saved = dict(runtime(), threads=4, deterministic_algorithms=True, deterministic_warn_only=False)
    saved.update(change)
    policy = SimpleNamespace(manifest={'runtime':saved})
    args = SimpleNamespace(update_threads=None, resume_state='saved.resume.pt', checkpoint='saved.sts-model')
    before = runtime()
    with pytest.raises(ValueError):
        _configure_ppo_cpu(args, lambda _:policy)
    assert runtime() == before


def test_cli_training_restores_global_settings_and_auto_resumes_saved_threads(tmp_path, monkeypatch):
    from game.agent import performance
    monkeypatch.setattr(performance, 'available_cpus', lambda:18)
    initial = tmp_path/'input/initial.sts-model'
    with owner() as source:
        save_ppo_checkpoint(initial, source, resume_path=tmp_path/'input-private/initial.resume.pt')
    experiment = PPOExperiment(ppo=PPOConfig(rollout_steps=8, batch_size=4, epochs=1))
    config = tmp_path/'config.json'
    config.write_text(json.dumps(experiment.to_dict()))
    torch.set_num_threads(2)
    before = runtime()
    first = tmp_path/'first'
    common = ['ppo', '--config', str(config), '--decisions', '8', '--time-limit', '60']
    assert main([*common, '--checkpoint', str(initial), '--output-dir', str(first), '--workers', '2']) == 0
    assert runtime() == before
    report = json.loads((first/'ppo.json').read_text())
    assert report['runtime']['threads'] == 4 and report['runtime']['deterministic_algorithms'] is True
    assert report['summary']['trained_decisions'] == 8
    bundle, state = first/'final.sts-model', tmp_path/'first-private/final.resume.pt'
    resumed = tmp_path/'resumed'
    assert main([*common, '--checkpoint', str(bundle), '--resume-state', str(state),
                 '--output-dir', str(resumed)]) == 0
    assert runtime() == before
    later = json.loads((resumed/'ppo.json').read_text())
    assert later['runtime'] == report['runtime'] and later['start_decisions'] == 8
    assert later['collection']['workers'] == report['collection']['workers'] == 2
    with pytest.raises(SystemExit):
        main([*common, '--checkpoint', str(bundle), '--resume-state', str(state),
              '--output-dir', str(tmp_path/'mismatch'), '--update-threads', '1'])
    assert runtime() == before and not (tmp_path/'mismatch').exists()


def test_cli_restores_global_settings_after_configuration_failure(tmp_path):
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True, warn_only=True)
    before = runtime()
    with pytest.raises(SystemExit):
        main(['ppo', '--checkpoint', str(tmp_path/'missing.sts-model'), '--config', str(tmp_path/'missing.json'),
              '--output-dir', str(tmp_path/'output'), '--update-threads', '4'])
    assert runtime() == before
