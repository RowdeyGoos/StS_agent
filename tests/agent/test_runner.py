"""Owned execution, real outcomes, controlled multi-act data and bounded workers."""
from dataclasses import asdict, replace
import json
import multiprocessing
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import pytest

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.full_policy import choose_action
from game.agent.headless import AdapterFault
from game.agent.trace_storage import is_trajectory
from game.agent.recording import SUFFIX, load_trajectory
from game.agent.runner import RunCancelled, RunConfig, RunFailure, prepare_directories, run_episode
from game.agent.workers import run_batch
from game.headless.run.engine import RunEngine


def test_policy_gets_only_public_input_and_invalid_action_never_mutates(tmp_path):
    run = RunEngine.campaign(seed=2)
    before = run.snapshot()
    calls = []
    def invalid(decision):
        assert type(decision) is f.PublicDecision
        calls.append(decision)
        return replace(decision.candidates[0], ref='action:99999')
    with pytest.raises(RunFailure, match='unadvertised'):
        run_episode(RunConfig(evidence='controlled_fixture'), output_dir=tmp_path/'public',
                    audit_dir=tmp_path/'private', engine_factory=lambda seed: run,
                    policy=invalid, policy_identity='test_invalid_v1')
    assert len(calls) == 1 and run.snapshot() == before
    assert not any(is_trajectory(p) for p in (tmp_path/'public').glob('*'))
    assert len(list((tmp_path/'public').glob('*.partial'))) == 1


def test_uncertain_mutation_is_not_retried_or_published(tmp_path):
    run = RunEngine.campaign(seed=2)
    original, attempts = run.apply, []
    def failed(action):
        attempts.append(action)
        original(action)
        raise RuntimeError('synthetic failure after mutation')
    run.apply = failed
    with pytest.raises(AdapterFault):
        run_episode(RunConfig(evidence='controlled_fixture'), output_dir=tmp_path/'public',
                    audit_dir=tmp_path/'private', engine_factory=lambda seed: run)
    assert len(attempts) == 1
    assert not any(is_trajectory(p) for p in (tmp_path/'public').glob('*'))
    assert len(list((tmp_path/'public').glob('*.partial'))) == 1


def test_time_limit_keeps_initial_public_state_without_fake_action(tmp_path):
    result = run_episode(RunConfig(time_limit_seconds=1e-9),
                         output_dir=tmp_path/'public', audit_dir=tmp_path/'private')
    trace = load_trajectory(result.trajectory)
    assert not trace.transitions and isinstance(trace.initial, f.PublicDecision)
    assert trace.outcome == c.RunOutcome('sts_run_outcome_v1', 'truncated', 'time_budget')
    assert result.timings.observations == 1 and result.timings.steps == 0


def test_real_defeat_is_a_terminal_transition(tmp_path):
    run = RunEngine.ironclad_slice(seed=1)
    run.state.hp = 1
    def end_turn(decision):
        return next((a for a in decision.candidates if a.kind == 'end_turn'), None) or choose_action(decision)
    result = run_episode(RunConfig(evidence='controlled_fixture', max_decisions=20),
                         output_dir=tmp_path/'public', audit_dir=tmp_path/'private',
                         engine_factory=lambda seed: run, policy=end_turn, policy_identity='test_end_turn_v1')
    trace = load_trajectory(result.trajectory)
    assert trace.outcome.kind == 'defeat' and run.state.hp == 0
    assert trace.transitions[-1].successor == trace.outcome
    assert all(step.reward == 0 for step in trace.transitions)
    assert result.combats[-1]['outcome'] == 'defeat'
    assert result.combats[-1]['hp'] == 0


def test_combat_metrics_capture_post_cleanup_victory_once(tmp_path):
    from .test_search import fixture, card_action
    run, _ = fixture(('strike',), enemy_hp=1)
    result = run_episode(RunConfig(evidence='controlled_fixture', max_decisions=2),
        output_dir=tmp_path/'public', audit_dir=tmp_path/'private', engine_factory=lambda _: run,
        combat_policy=lambda d: card_action(d, 'strike'), policy_identity='controlled_lethal_v1')
    assert len(result.combats) == 1
    assert result.combats[0]['outcome'] == 'victory'
    assert result.combats[0]['hp'] == 46  # Includes Burning Blood's end-of-combat heal.


def test_controlled_multi_act_trajectory_round_trips_with_victory_and_training(tmp_path):
    from tests.headless.test_act2_run import win
    run = RunEngine.campaign(seed=4, ascension=10, first_act='underdocks')
    run.state.max_hp = run.state.hp = 10000
    apply = run.apply
    # The declared controlled fixture accelerates combat; it is never labelled
    # an ordinary policy victory or retained native evidence.
    def controlled(action):
        result = apply(action)
        if run.combat:
            run.apply = apply
            try:
                win(run)
            finally:
                run.apply = controlled
        return result
    run.apply = controlled
    result = run_episode(RunConfig(seed=4, evidence='controlled_fixture', scenario='controlled_fast_campaign_v1',
                                  max_decisions=500, time_limit_seconds=120),
                         output_dir=tmp_path/'public', audit_dir=tmp_path/'private',
                         engine_factory=lambda seed: run)
    trace = load_trajectory(result.trajectory)
    assert trace.metadata.evidence == 'controlled_fixture'
    assert trace.outcome.kind == 'victory'
    assert {t.observation.run.get('act') for t in trace.transitions} == {1, 2, 3}
    assert sum(t.action.kind == 'continue_act' for t in trace.transitions) == 3
    assert sum(t.reward for t in trace.transitions) == 1
    assert trace.transitions[-1].successor == trace.outcome
    # Every public decision and all candidate semantics survive the core loader.
    for transition in trace.transitions:
        assert f.loads(f.dumps(transition.observation)) == transition.observation
    pytest.importorskip('numpy')
    from game.agent.dataset import training_examples
    from game.agent.encoding.full import FullRunEncoder
    encoder = FullRunEncoder()
    count = 0
    for count, sample in enumerate(training_examples([result.trajectory], split='train', encoder=encoder), 1):
        transition = trace.transitions[count - 1]
        assert encoder.encode(transition.observation).candidate_refs[sample.action] == transition.action.ref
        assert sample.observation['action_mask'][sample.action]
    assert count == len(trace.transitions)
    assert sample.reward == 1 and sample.terminated and not sample.truncated
    assert not sample.successor['action_mask'].any()


def test_serial_and_two_worker_runs_match_by_episode_and_keep_independent_seeds(tmp_path):
    config = RunConfig(seed=30, max_decisions=5)
    batches = [run_batch(config, episodes=2, workers=n, output_dir=tmp_path/f'public{n}',
                         audit_dir=tmp_path/f'private{n}') for n in (1, 2)]
    traces = [[load_trajectory(result.trajectory) for result in batch.episodes] for batch in batches]
    for a, b in zip(*traces):
        assert a.initial == b.initial and a.transitions == b.transitions and a.outcome == b.outcome
        assert a.metadata.episode_id != b.metadata.episode_id
    assert traces[0][0].initial != traces[0][1].initial
    for n in (1, 2):
        audits = [json.loads(p.read_text()) for p in (tmp_path/f'private{n}').glob('*.audit.json')]
        assert sorted(a['config']['seed'] for a in audits) == [30, 31]
    assert not multiprocessing.active_children()


def test_two_worker_cancellation_leaves_partial_files_and_no_children(tmp_path):
    cancel = threading.Event()
    def stop_after_headers():
        deadline = time.monotonic() + 10
        while len(list((tmp_path/'public').glob('*.partial'))) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        cancel.set()
    thread = threading.Thread(target=stop_after_headers)
    thread.start()
    try:
        with pytest.raises(RunCancelled):
            run_batch(RunConfig(max_decisions=5000), episodes=4, workers=2,
                      output_dir=tmp_path/'public', audit_dir=tmp_path/'private', cancel=cancel)
    finally:
        thread.join(11)
    assert not multiprocessing.active_children()
    assert len(list((tmp_path/'public').glob('*.partial'))) == 2
    assert not any(is_trajectory(p) for p in (tmp_path/'public').glob('*'))


def _stalled_worker(config, output, audit, episode_id, stopped, sender):
    # A test-only child that cannot reach a cooperative cancellation point.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    (Path(output)/(episode_id + SUFFIX + '.partial')).write_text('test-only stalled child\n')
    time.sleep(60)


def test_unresponsive_workers_are_terminated_and_joined(tmp_path, monkeypatch):
    import game.agent.workers as workers
    monkeypatch.setattr(workers, '_worker', _stalled_worker)
    cancel = threading.Event()
    timer = threading.Timer(0.8, cancel.set)
    timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(RunCancelled):
            workers.run_batch(RunConfig(), episodes=2, workers=2,
                              output_dir=tmp_path/'public', audit_dir=tmp_path/'private', cancel=cancel)
    finally:
        timer.cancel()
    assert time.monotonic() - started < 7
    assert not multiprocessing.active_children()
    assert not any(is_trajectory(p) for p in (tmp_path/'public').glob('*'))


@pytest.mark.skipif(os.name != 'posix', reason='Exercises the POSIX spawn interrupt window')
def test_interrupt_after_os_spawn_before_process_handle_attachment_is_reaped(tmp_path, monkeypatch):
    from multiprocessing.popen_spawn_posix import Popen
    launched = []
    original = Popen._launch
    def launch(self, process):
        original(self, process)
        launched.append(self)
        os.kill(os.getpid(), signal.SIGINT)
    monkeypatch.setattr(Popen, '_launch', launch)
    try:
        with pytest.raises(KeyboardInterrupt):
            run_batch(RunConfig(), output_dir=tmp_path/'public', audit_dir=tmp_path/'private')
        assert len(launched) == 1 and launched[0].poll() is not None
        assert not multiprocessing.active_children()
    finally:
        # Even a regressed test must not leave its known, owned child running.
        for child in launched:
            if child.poll() is None:
                os.kill(child.pid, signal.SIGKILL)
                child.wait()


def test_cli_sigterm_cancels_and_reaps_workers(tmp_path):
    process = subprocess.Popen([sys.executable, '-S', '-m', 'game.cli.agent_play',
                                '--output-dir', str(tmp_path/'public'), '--max-decisions', '5000',
                                '--episodes', '4', '--workers', '2'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 10
        while len(list((tmp_path/'public').glob('*.partial'))) < 2 and time.monotonic() < deadline:
            assert process.poll() is None
            time.sleep(0.01)
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=8)
        assert process.returncode == 130, stderr
        assert json.loads(stderr)['status'] == 'cancelled' and not stdout
        assert len(list((tmp_path/'public').glob('*.partial'))) == 2
        assert not any(is_trajectory(p) for p in (tmp_path/'public').glob('*'))
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)


def test_private_directory_separation_and_permissions(tmp_path):
    for output, audit in ((tmp_path/'same', tmp_path/'same'),
                          (tmp_path/'public', tmp_path/'public/audit'),
                          (tmp_path/'audit/public', tmp_path/'audit')):
        with pytest.raises(ValueError, match='disjoint'):
            prepare_directories(output, audit)
    private = tmp_path/'insecure'
    private.mkdir(mode=0o755)
    private.chmod(0o755)
    with pytest.raises(ValueError, match='owner-only'):
        prepare_directories(tmp_path/'public', private)
    (tmp_path/'alias').symlink_to(tmp_path/'public', target_is_directory=True)
    with pytest.raises(ValueError, match='disjoint'):
        prepare_directories(tmp_path/'public', tmp_path/'alias')


def test_cli_works_without_optional_dependencies_and_does_not_print_private_seed(tmp_path):
    result = subprocess.run([sys.executable, '-S', '-m', 'game.cli.agent_play',
                             '--output-dir', str(tmp_path/'public'), '--seed', '992384723894723',
                             '--max-decisions', '2', '--episodes', '2', '--workers', '2'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary['status'] == 'complete' and len(summary['episodes']) == 2
    assert '992384723894723' not in result.stdout
    for episode in summary['episodes']:
        assert load_trajectory(episode['trajectory']).outcome.reason == 'decision_budget'
