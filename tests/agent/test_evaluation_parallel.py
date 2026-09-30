"""Paired evaluation parity, frozen policies, failure accounting and cleanup."""
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

pytest.importorskip('torch')
pytest.importorskip('gymnasium')

from game.agent.analysis.report import build_report
from game.agent.recording import load_trajectory
from game.agent.training import evaluation_workers as pool
from game.agent.training import run_evaluation
from game.agent.training.run_task import campaign_seed
from .test_full_run_training import bundles
from .test_training_model import cpu_threads


def _children():
    return {p.pid for p in multiprocessing.active_children()}


def _die(*_):
    os._exit(7)


def _hang(checkpoints, policies, source, output, private, stopped, connection):
    connection.send(('ready', None, None))
    connection.recv()
    (Path(private)/f'{os.getpid()}.started').touch()
    time.sleep(60)


def _stop_without_result(checkpoints, policies, source, output, private, stopped, connection):
    connection.send(('ready', None, None))
    connection.recv()
    (Path(private)/f'{os.getpid()}.started').touch()
    stopped.wait(30)
    connection.close()


def _failure(checkpoints, policies, source, output, private, stopped, connection):
    original = pool.run_episode
    def run(config, **kwargs):
        if config.seed == campaign_seed('validation', 101):
            raise RuntimeError('PRIVATE_EXCEPTION_MUST_NOT_ESCAPE')
        return original(config, **kwargs)
    pool.run_episode = run
    pool._worker(checkpoints, policies, source, output, private, stopped, connection)


@pytest.mark.parametrize('goal,other', [('act1','reference'), ('full_run','hybrid')])
def test_serial_parallel_games_and_planned_pairing_agree(bundles, tmp_path, goal, other):
    before = _children()
    kwargs = {'reference_checkpoint': bundles[1]} if other == 'reference' else {'combat_checkpoint': bundles[0]}
    reports = []
    for workers in (1, 2):
        output = tmp_path/f'eval-{workers}'
        path, report = run_evaluation.evaluate_full_run(checkpoint=bundles[1], **kwargs, output_dir=output,
            cases=2, split='validation', start_index=100, goal=goal, max_decisions=12, workers=workers)
        assert report['status'] == 'complete', report
        assert report['execution']['workers'] == workers
        assert all(s['planned'] == 2 and s['cutoffs'] == 2 for s in report['summary'].values())
        plan = json.loads(path.with_name(path.stem+'-plan.json').read_text())
        assert all(row['status'] == 'unattempted' for row in plan['episodes'])
        assert [r['episode_id'] for r in plan['episodes']] == [r['episode_id'] for r in report['episodes']]
        episodes = [load_trajectory(output/row['trajectory'], split='validation') for row in report['episodes']]
        for offset in (0, 3):
            assert episodes[offset].initial == episodes[offset+1].initial == episodes[offset+2].initial
        for row, episode in zip(report['episodes'], episodes):
            assert episode.metadata.policy == report['policies'][row['policy']]
            assert episode.metadata.build == report['implementation']['build']
        private = output.with_name(output.name+'-private')
        seeds = json.loads((private/'cases.json').read_text())
        for row in report['episodes']:
            audit = json.loads((private/(row['episode_id']+'.audit.json')).read_text())
            assert audit['config']['seed'] == seeds[row['case_id']]
        assert all(p.stat().st_mode & 0o077 == 0 for p in private.iterdir())
        assert not list(output.glob('*.partial'))
        reports.append((report, episodes))
    for left, right in zip(reports[0][1], reports[1][1]):
        assert (left.initial, left.transitions, left.outcome) == (right.initial, right.transitions, right.outcome)
    for policy in ('heuristic', other, 'learned'):
        for key in ('planned', 'attempted', 'cutoffs', 'defeats', 'failures', 'steps', 'unattempted'):
            assert reports[0][0]['summary'][policy][key] == reports[1][0]['summary'][policy][key]
    exported = build_report([tmp_path/'eval-2'], tmp_path/'viewer', goal=goal, workers=2)
    assert exported['paired_cases_verified'] == 2 and len(exported['runs']) == 6
    assert _children() == before


def test_failed_game_keeps_completed_games_and_all_planned_denominators(bundles, tmp_path, monkeypatch):
    before = _children()
    monkeypatch.setattr(pool, '_worker', _failure)
    path, report = run_evaluation.evaluate_full_run(checkpoint=bundles[1], reference_checkpoint=bundles[1],
        output_dir=tmp_path/'failed', goal='act1', workers=2, cases=4, split='validation',
        start_index=100, max_decisions=12)
    assert report['status'] == 'failed'
    statuses = [r['status'] for r in report['episodes']]
    assert 'truncated' in statuses and 'failed' in statuses and 'unattempted' in statuses
    assert len(statuses) == 12 and all(s['planned'] == 4 for s in report['summary'].values())
    assert report['paired_vs_reference']['conclusion'] == 'incomplete'
    assert 'PRIVATE_EXCEPTION' not in path.read_text()
    for row in report['episodes']:
        if row['status'] == 'truncated':
            assert load_trajectory(path.parent/row['trajectory']).sha256 == row['trajectory_sha256']
    assert _children() == before


def test_worker_rechecks_checkpoint_digest_after_plan_publication(bundles, tmp_path, monkeypatch):
    original = run_evaluation.publish
    def publish(path, data, **kwargs):
        result = original(path, data, **kwargs)
        if Path(path).name == 'act1-plan.json':
            bundles[1].write_bytes(bundles[1].read_bytes()+b'changed')
        return result
    monkeypatch.setattr(run_evaluation, 'publish', publish)
    before = _children()
    path, report = run_evaluation.evaluate_full_run(checkpoint=bundles[1], reference_checkpoint=bundles[1],
        output_dir=tmp_path/'changed', goal='act1', workers=2, cases=2)
    assert report['status'] == 'failed' and report['failure'] == 'ValueError'
    assert all(r['status'] == 'unattempted' for r in report['episodes'])
    assert not list(path.parent.glob('*.trajectory.jsonl'))
    assert _children() == before


def test_pre_cancelled_batch_never_dispatches_a_game(bundles, tmp_path):
    stopped = threading.Event(); stopped.set()
    before = _children()
    path, report = run_evaluation.evaluate_full_run(checkpoint=bundles[1], reference_checkpoint=bundles[1],
        output_dir=tmp_path/'cancelled', goal='act1', workers=2, cases=2, cancel=stopped)
    assert report['status'] == 'interrupted'
    assert all(s['planned'] == s['unattempted'] == 2 for s in report['summary'].values())
    assert report['paired_vs_reference']['conclusion'] == 'incomplete'
    assert not list(path.parent.glob('*.trajectory.jsonl'))
    assert _children() == before


@pytest.mark.parametrize('fault', ['exit', 'deadline', 'cancel', 'cooperative_cancel'])
def test_dead_or_stuck_worker_stops_without_retry_or_orphans(bundles, tmp_path, monkeypatch, fault):
    before = _children()
    monkeypatch.setattr(pool, '_worker', _die if fault == 'exit' else
                        _stop_without_result if fault == 'cooperative_cancel' else _hang)
    if fault == 'deadline':
        monkeypatch.setattr(pool, 'REPORT_GRACE_SECONDS', .01)
    stopped, done = threading.Event(), threading.Event()
    output = tmp_path/fault
    def cancel_when_started():
        while not done.wait(.01):
            if list(output.with_name(output.name+'-private').glob('*.started')):
                stopped.set()
                return
    watcher = threading.Thread(target=cancel_when_started)
    if fault in ('cancel', 'cooperative_cancel'):
        watcher.start()
    started = time.monotonic()
    try:
        _, report = run_evaluation.evaluate_full_run(checkpoint=bundles[1], reference_checkpoint=bundles[1],
            output_dir=output, goal='act1', workers=2, cases=2, max_decisions=1,
            time_limit_seconds=.01, cancel=stopped)
    finally:
        done.set()
        if watcher.ident is not None:
            watcher.join(2)
    assert time.monotonic()-started < 15
    assert report['status'] == ('interrupted' if 'cancel' in fault else 'failed')
    assert report['failure'] == {'exit':'WorkerExited', 'deadline':'WorkerDeadlineExceeded',
                                 'cancel':'RunCancelled', 'cooperative_cancel':'RunCancelled'}[fault]
    if 'cancel' in fault:
        assert all(r['status'] in ('unattempted', 'interrupted') for r in report['episodes'])
    assert all(s['planned'] == 2 for s in report['summary'].values())
    assert report['paired_vs_reference']['conclusion'] == 'incomplete'
    assert sum(r['status'] != 'unattempted' for r in report['episodes']) <= 2
    assert _children() == before


@pytest.mark.parametrize('workers', [0, 9, True, 1.5])
def test_invalid_worker_setting_is_rejected_before_model_or_output_access(tmp_path, workers):
    with pytest.raises(ValueError, match='workers'):
        run_evaluation.evaluate_full_run(checkpoint='missing', reference_checkpoint='missing',
                                        output_dir=tmp_path/'output', workers=workers)
    assert not (tmp_path/'output').exists()


def test_cli_does_not_silently_ignore_workers_for_unsupported_evaluators(tmp_path):
    result = subprocess.run([sys.executable, '-S', '-m', 'game.cli.agent_evaluate', '--workers', '2',
                             '--output-dir', str(tmp_path/'output')], capture_output=True, text=True, timeout=30)
    assert result.returncode == 2 and 'require --act1 or --full-run' in result.stderr
    assert not (tmp_path/'output').exists()
