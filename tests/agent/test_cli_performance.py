"""Command defaults scale by CPU availability without overriding saved runs."""
import json
from types import SimpleNamespace

import pytest

from game.agent import performance


@pytest.mark.parametrize('cpus,games,artifacts,threads', [
    (None,1,1,1), (1,1,1,1), (2,2,2,2), (3,3,3,2), (4,4,4,4),
    (8,8,8,4), (18,16,8,4), (64,16,8,4)])
def test_cpu_aware_defaults_and_supported_thread_counts(monkeypatch, cpus, games, artifacts, threads):
    monkeypatch.setattr(performance.os, 'process_cpu_count', lambda:cpus, raising=False)
    assert performance.game_workers() == games
    assert performance.artifact_workers() == artifacts
    assert performance.ppo_update_threads() == threads


def test_older_python_uses_standard_cpu_count(monkeypatch):
    monkeypatch.delattr(performance.os, 'process_cpu_count', raising=False)
    monkeypatch.setattr(performance.os, 'cpu_count', lambda:6)
    assert performance.game_workers() == 6 and performance.ppo_update_threads() == 4


def test_unavailable_cpu_detection_falls_back_to_one(monkeypatch):
    def unavailable():raise OSError('CPU availability unavailable')
    monkeypatch.setattr(performance.os, 'process_cpu_count', unavailable, raising=False)
    assert performance.game_workers() == performance.artifact_workers() == performance.ppo_update_threads() == 1


@pytest.fixture
def machine(monkeypatch):
    monkeypatch.setattr(performance, 'available_cpus', lambda:18)


@pytest.mark.parametrize('workers,expected', [(None,16), ('1',1), ('12',12)])
def test_new_ppo_cli_resolves_workers_and_threads_before_dispatch(tmp_path, monkeypatch, machine, workers, expected):
    torch = pytest.importorskip('torch')
    pytest.importorskip('gymnasium')
    from game.agent.training.ppo_config import PPOExperiment
    from game.agent.training import ppo_run
    from game.cli.agent_train import main
    config = tmp_path/'config.json'
    config.write_text(json.dumps(PPOExperiment().to_dict()))
    calls = []
    def run(**kwargs):
        calls.append((kwargs, torch.get_num_threads(), torch.are_deterministic_algorithms_enabled()))
        return tmp_path/'ppo.json', {'status':'complete'}
    monkeypatch.setattr(ppo_run, 'run_ppo', run)
    before = torch.get_num_threads(), torch.are_deterministic_algorithms_enabled()
    arguments = ['ppo', '--checkpoint', 'source.sts-model', '--config', str(config), '--output-dir', str(tmp_path/'run')]
    if workers is not None:arguments += ['--workers', workers]
    assert main(arguments) == 0
    assert calls[0][0]['workers'] == expected and calls[0][0]['resume_state'] is None
    assert calls[0][1:] == (4, True)
    assert (torch.get_num_threads(), torch.are_deterministic_algorithms_enabled()) == before


@pytest.mark.parametrize('mode', ['--act1', '--full-run', '--combat-corpus'])
@pytest.mark.parametrize('workers,expected', [(None,16), ('1',1)])
def test_parallel_evaluation_cli_defaults_and_explicit_serial(tmp_path, monkeypatch, machine, mode, workers, expected):
    torch = pytest.importorskip('torch')
    pytest.importorskip('gymnasium')
    from game.agent.training import combat_benchmark, run_evaluation
    from game.cli.agent_evaluate import main
    calls = []
    def run(**kwargs):
        calls.append(kwargs)
        return tmp_path/'evaluation.json', dict(status='complete', summary={}, coverage={}, total_seconds=0,
            execution={'workers':kwargs['workers']}, paired_vs_heuristic={})
    monkeypatch.setattr(combat_benchmark, 'evaluate_corpus', run)
    monkeypatch.setattr(run_evaluation, 'evaluate_full_run', run)
    arguments = ['--output-dir', str(tmp_path/'run'), '--checkpoint', 'source.sts-model', mode]
    arguments += ['corpus.json'] if mode == '--combat-corpus' else ['--reference-checkpoint','reference.sts-model']
    if workers is not None:arguments += ['--workers', workers]
    before = torch.get_num_threads()
    try:
        assert main(arguments) == 0
        assert calls[0]['workers'] == expected
    finally:
        torch.set_num_threads(before)


def test_serial_only_evaluation_default_still_dispatches(tmp_path, monkeypatch, machine):
    pytest.importorskip('gymnasium')
    from game.agent.training import evaluation
    from game.cli.agent_evaluate import main
    calls = []
    def run(**kwargs):
        calls.append(kwargs)
        return tmp_path/'evaluation.json', dict(status='complete', summary={})
    monkeypatch.setattr(evaluation, 'evaluate_baselines', run)
    assert main(['--output-dir', str(tmp_path/'run')]) == 0
    assert len(calls) == 1 and 'workers' not in calls[0]


@pytest.mark.parametrize('command', ['build','compress'])
@pytest.mark.parametrize('workers,expected', [(None,8), ('1',1)])
def test_analysis_cli_uses_artifact_defaults(tmp_path, monkeypatch, machine, command, workers, expected):
    from game.agent.analysis import report
    from game.agent import trace_compression
    from game.cli.agent_analyze import main
    calls = []
    def build(*args, **kwargs):
        calls.append(kwargs)
        return dict(runs=[], export={'workers_requested':kwargs['workers']})
    def compress(*args, **kwargs):
        calls.append(kwargs)
        return {'failed_groups':0}
    monkeypatch.setattr(report, 'build_report', build)
    monkeypatch.setattr(trace_compression, 'compress_traces', compress)
    arguments = [command,'--input','recordings']
    if command == 'build':arguments += ['--output-dir',str(tmp_path/'analysis')]
    if workers is not None:arguments += ['--workers',workers]
    assert main(arguments) == 0
    assert calls[0]['workers'] == expected


@pytest.mark.parametrize('workers,expected', [(None,16), ('1',1)])
def test_playback_cli_uses_game_worker_default(tmp_path, monkeypatch, machine, workers, expected):
    from game.agent.workers import BatchResult
    from game.cli import agent_play
    calls = []
    def run(*args, **kwargs):
        calls.append(kwargs)
        return BatchResult((), 0)
    monkeypatch.setattr(agent_play, 'run_batch', run)
    arguments = ['--output-dir',str(tmp_path/'play')]
    if workers is not None:arguments += ['--workers',workers]
    assert agent_play.main(arguments) == 0
    assert calls[0]['workers'] == expected


def test_saved_one_thread_runtime_wins_over_new_default(monkeypatch, machine):
    torch = pytest.importorskip('torch')
    from game.cli.agent_train import _configure_ppo_cpu
    before = (torch.get_num_threads(), torch.are_deterministic_algorithms_enabled(),
              torch.is_deterministic_algorithms_warn_only_enabled())
    saved = dict(threads=1, deterministic_algorithms=False, deterministic_warn_only=False)
    args = SimpleNamespace(update_threads=None, resume_state='saved.resume.pt', checkpoint='saved.sts-model')
    try:
        _configure_ppo_cpu(args, lambda _:SimpleNamespace(manifest={'runtime':saved}))
        assert torch.get_num_threads() == 1 and not torch.are_deterministic_algorithms_enabled()
    finally:
        torch.set_num_threads(before[0]);torch.use_deterministic_algorithms(before[1], warn_only=before[2])
