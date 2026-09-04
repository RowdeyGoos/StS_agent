"""Consumer-level tests for bounded headless rollout collection."""

from __future__ import annotations

from dataclasses import replace
import json
import os
import signal
import subprocess
import sys

import pytest

from game.backends.headless.reduced_run_backend import HeadlessRunConfig, ReducedRunBackend
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.data.headless_trajectory import validate_trajectory
import game.training.headless_rollout as rollout_module
from game.training.headless_rollout import (
    ChooserKind,
    CollectorWorkerConfig,
    HeadlessBatchConfig,
    HeadlessRolloutConfig,
    RolloutStopReason,
    run_headless_batch,
    run_headless_rollout,
)


def _config(
    trajectory_id: str,
    *,
    game_seed: int = 7,
    policy_seed: int = 11,
    transition_budget: int = 300,
    settings: dict | None = None,
    chooser_kind: ChooserKind = ChooserKind.STRUCTURAL_HEURISTIC,
) -> HeadlessRolloutConfig:
    return HeadlessRolloutConfig(
        trajectory_id=trajectory_id,
        run_config=HeadlessRunConfig(
            scenario_id="simple__starter",
            content_fingerprint=CONTENT_FINGERPRINT,
            game_seed=game_seed,
            backend_settings={} if settings is None else settings,
        ),
        transition_budget=transition_budget,
        chooser_kind=chooser_kind,
        policy_seed=policy_seed,
    )


def test_multiple_seeded_episodes_are_deterministic_and_preserve_evidence() -> None:
    left = run_headless_rollout(_config("rollout-left"))
    right = run_headless_rollout(_config("rollout-right"))

    assert left.stop_reason is RolloutStopReason.ROUTE_COMPLETE
    assert right.stop_reason is RolloutStopReason.ROUTE_COMPLETE
    assert left.transition_count == right.transition_count
    assert left.final_decision_json == right.final_decision_json
    assert left.initial_snapshot_sha256 == right.initial_snapshot_sha256
    assert left.final_snapshot_sha256 == right.final_snapshot_sha256
    assert left.trajectory is not None and right.trajectory is not None
    assert left.trajectory.policy_replay_jsonl == right.trajectory.policy_replay_jsonl
    assert {item.label.value for item in left.evidence} == {
        "combat_v0", "structural_fixture"
    }


def test_replay_and_hindsight_sidecars_are_separate_and_independently_bound(tmp_path) -> None:
    result = run_headless_rollout(_config("rollout-sidecars"))
    assert result.trajectory is not None
    trajectory = result.trajectory
    validated = validate_trajectory(
        trajectory.manifest_json,
        trajectory.policy_replay_jsonl,
        trajectory.hindsight_target_jsonl,
        trajectory.synthetic_audit_jsonl,
        expected_manifest_sha256=trajectory.manifest_sha256,
    )
    assert validated == trajectory
    paths = trajectory.write_to(tmp_path)
    assert paths.policy_replay.exists()
    assert paths.hindsight_target.exists()
    assert paths.policy_replay != paths.hindsight_target
    assert b"terminal_outcome" not in trajectory.policy_replay_jsonl
    assert b"terminal_outcome" in trajectory.hindsight_target_jsonl


def test_game_policy_and_collector_seeds_are_independent_with_fixed_actions() -> None:
    fixed_action = _config(
        "rollout-fixed-action",
        policy_seed=1,
        chooser_kind=ChooserKind.FIRST_LEGAL,
    )
    changed_policy_seed = replace(fixed_action, policy_seed=999)
    fixed_left = run_headless_rollout(fixed_action)
    fixed_right = run_headless_rollout(changed_policy_seed)

    assert fixed_left.final_decision_json == fixed_right.final_decision_json
    assert fixed_left.initial_snapshot_sha256 == fixed_right.initial_snapshot_sha256
    assert fixed_left.final_snapshot_sha256 == fixed_right.final_snapshot_sha256
    assert fixed_left.trajectory is not None and fixed_right.trajectory is not None
    assert fixed_left.trajectory.policy_replay_jsonl == fixed_right.trajectory.policy_replay_jsonl

    random_panel = tuple(
        _config(
            f"rollout-random-{seed}",
            game_seed=seed,
            policy_seed=5,
            chooser_kind=ChooserKind.SEEDED_RANDOM,
        )
        for seed in (7, 8, 9)
    )
    left = run_headless_batch(
        HeadlessBatchConfig(random_panel, CollectorWorkerConfig(worker_count=1, worker_seed=1))
    )
    right = run_headless_batch(
        HeadlessBatchConfig(random_panel, CollectorWorkerConfig(worker_count=1, worker_seed=999))
    )
    assert [item.final_decision_json for item in left.results] == [
        item.final_decision_json for item in right.results
    ]
    assert [item.final_snapshot_sha256 for item in left.results] == [
        item.final_snapshot_sha256 for item in right.results
    ]
    assert [item.trajectory.policy_replay_jsonl for item in left.results] == [
        item.trajectory.policy_replay_jsonl for item in right.results
    ]


def test_spawned_workers_match_sequential_panel_without_seed_coupling() -> None:
    panel = HeadlessBatchConfig(
        (_config("rollout-spawn-a", game_seed=7), _config("rollout-spawn-b", game_seed=8)),
        CollectorWorkerConfig(worker_count=2, worker_seed=17),
    )
    sequential = run_headless_batch(panel)
    spawned = run_headless_batch(panel, process_safe=True)

    assert spawned.process_safe is True
    assert [item.final_decision_json for item in spawned.results] == [
        item.final_decision_json for item in sequential.results
    ]
    assert [item.final_snapshot_sha256 for item in spawned.results] == [
        item.final_snapshot_sha256 for item in sequential.results
    ]


def test_explicit_route_defeat_budget_and_unsupported_stop_reasons() -> None:
    route = run_headless_rollout(_config("rollout-route"))
    defeat = run_headless_rollout(_config("rollout-defeat", settings={"initial_hp": 1}))
    budget = run_headless_rollout(_config("rollout-budget", transition_budget=1))

    assert route.stop_reason is RolloutStopReason.ROUTE_COMPLETE
    assert defeat.stop_reason is RolloutStopReason.DEFEAT
    assert budget.stop_reason is RolloutStopReason.BUDGET_EXHAUSTED
    assert budget.trajectory is not None
    assert budget.trajectory.manifest.completion.value == "interrupted"
    unsupported = run_headless_rollout(
        _config(
            "rollout-unsupported",
            policy_seed=5,
            chooser_kind=ChooserKind.SEEDED_RANDOM,
            settings={
                "event_id": "cool_spring",
                "combat_settings": {"enemy_max_hp": 1},
            },
        )
    )
    assert unsupported.stop_reason is RolloutStopReason.UNSUPPORTED
    assert unsupported.trajectory is not None
    assert unsupported.trajectory.manifest.completion.value == "unsupported"


def test_backend_failure_returns_a_validated_interrupted_partial_trajectory(monkeypatch) -> None:
    def interrupted_apply(self, action):
        raise RuntimeError("synthetic collector interruption")

    original_close = ReducedRunBackend.close
    close_calls = []

    def tracked_close(self):
        close_calls.append(self.observe().decision_hash)
        original_close(self)

    monkeypatch.setattr(ReducedRunBackend, "apply", interrupted_apply)
    monkeypatch.setattr(ReducedRunBackend, "close", tracked_close)
    result = run_headless_rollout(_config("rollout-failure"))

    assert result.stop_reason is RolloutStopReason.FAILED
    assert result.failure == "RuntimeError: synthetic collector interruption"
    assert result.trajectory is not None
    assert result.trajectory.manifest.completion.value == "interrupted"
    assert len(close_calls) == 1
    validate_trajectory(
        result.trajectory.manifest_json,
        result.trajectory.policy_replay_jsonl,
        result.trajectory.hindsight_target_jsonl,
        result.trajectory.synthetic_audit_jsonl,
        expected_manifest_sha256=result.trajectory.manifest_sha256,
    )


def test_backend_is_closed_after_a_normal_finalized_rollout(monkeypatch) -> None:
    original_close = ReducedRunBackend.close
    close_calls = []

    def tracked_close(self):
        close_calls.append(self.observe().decision_hash)
        original_close(self)

    monkeypatch.setattr(ReducedRunBackend, "close", tracked_close)
    result = run_headless_rollout(_config("rollout-close"))

    assert result.stop_reason is RolloutStopReason.ROUTE_COMPLETE
    assert result.trajectory is not None
    assert len(close_calls) == 1


def test_sequential_batch_interrupt_between_episodes_keeps_only_completed_results(monkeypatch) -> None:
    panel = HeadlessBatchConfig(
        tuple(_config(f"rollout-interrupt-{index}") for index in range(3))
    )
    original_entry = rollout_module._run_batch_entry
    calls = 0

    def interrupt_between_episodes(config):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        return original_entry(config)

    monkeypatch.setattr(rollout_module, "_run_batch_entry", interrupt_between_episodes)
    result = run_headless_batch(panel)

    assert result.interrupted is True
    assert [item.config.trajectory_id for item in result.results] == ["rollout-interrupt-0"]
    assert result.pending_trajectory_ids == ("rollout-interrupt-1", "rollout-interrupt-2")


def test_chooser_interrupt_stops_sequential_batch_and_closes_available_partial(monkeypatch) -> None:
    original_close = ReducedRunBackend.close
    close_calls = []

    def tracked_close(self):
        close_calls.append(self.observe().decision_hash)
        original_close(self)

    def interrupting_chooser(config):
        def choose(_view):
            raise KeyboardInterrupt("synthetic chooser cancellation")

        return choose

    monkeypatch.setattr(ReducedRunBackend, "close", tracked_close)
    monkeypatch.setattr(rollout_module, "_make_chooser", interrupting_chooser)
    panel = HeadlessBatchConfig(tuple(_config(f"rollout-chooser-{index}") for index in range(3)))
    result = run_headless_batch(panel)

    assert result.interrupted is True
    assert len(result.results) == 1
    assert result.results[0].stop_reason is RolloutStopReason.INTERRUPTED
    assert result.results[0].initial_snapshot_sha256 is not None
    assert result.results[0].trajectory is not None
    assert result.pending_trajectory_ids == ("rollout-chooser-1", "rollout-chooser-2")
    assert len(close_calls) == 1


def test_process_collection_interrupt_terminates_and_joins_without_missing_fabrication(monkeypatch) -> None:
    class FakePool:
        terminated = False
        joined = False
        closed = False

        def imap_unordered(self, function, entries):
            iterator = iter(entries)
            yield function(next(iterator))
            raise KeyboardInterrupt

        def terminate(self):
            self.terminated = True

        def close(self):
            self.closed = True

        def join(self):
            self.joined = True

    pool = FakePool()

    class FakeContext:
        def Pool(self, *, processes):
            assert processes == 2
            return pool

    monkeypatch.setattr(rollout_module, "get_context", lambda method: FakeContext())
    panel = HeadlessBatchConfig(
        tuple(_config(f"rollout-process-{index}") for index in range(3)),
        CollectorWorkerConfig(worker_count=2, worker_seed=0),
    )
    result = run_headless_batch(panel, process_safe=True)

    assert result.interrupted is True
    assert len(result.results) == 1
    assert len(result.pending_trajectory_ids) == 2
    assert pool.terminated is True
    assert pool.joined is True
    assert pool.closed is False


@pytest.mark.parametrize("interrupt_stage", ("iteration", "close", "join"))
def test_real_spawn_sigint_preserves_results_through_cleanup(interrupt_stage) -> None:
    # Isolate real SIGINT from pytest. A process-group watchdog also kills any
    # pool descendants if recovery hangs, so a failed test cannot leak workers.
    script = r'''
import json
import multiprocessing
import os
import signal
import sys
import game.training.headless_rollout as rollout
from game.content.reduced_v0 import CONTENT_FINGERPRINT
from game.data.headless_trajectory import validate_trajectory

stage = sys.argv[1]
context = multiprocessing.get_context("spawn")
original_handler = signal.getsignal(signal.SIGINT)
events = []

class InterruptingPool:
    def __init__(self):
        self.pool = context.Pool(processes=1)
        self.fired = False

    def interrupt(self, where):
        if stage == where and not self.fired:
            self.fired = True
            os.kill(os.getpid(), signal.SIGINT)

    def imap_unordered(self, function, entries):
        for item in self.pool.imap_unordered(function, entries):
            yield item
            self.interrupt("iteration")

    def close(self):
        self.interrupt("close")
        self.pool.close()

    def join(self):
        self.interrupt("join")
        self.pool.join()
        events.append("joined")

    def terminate(self):
        events.append("terminated")
        # A second SIGINT during cancellation cleanup must not abort reaping.
        os.kill(os.getpid(), signal.SIGINT)
        self.pool.terminate()

pool = InterruptingPool()
class Context:
    def Pool(self, *, processes):
        return pool

rollout.get_context = lambda method: Context()
try:
    episodes = tuple(rollout.HeadlessRolloutConfig(
        "sigint-" + str(i),
        rollout.HeadlessRunConfig("simple__starter", CONTENT_FINGERPRINT, i, {}),
        0,
    ) for i in range(2))
    result = rollout.run_headless_batch(rollout.HeadlessBatchConfig(episodes), process_safe=True)
    assert result.interrupted
    assert len(result.results) == (1 if stage == "iteration" else 2)
    assert len(result.pending_trajectory_ids) == (1 if stage == "iteration" else 0)
    for item in result.results:
        trace = item.trajectory
        validate_trajectory(trace.manifest_json, trace.policy_replay_jsonl,
            trace.hindsight_target_jsonl, trace.synthetic_audit_jsonl,
            expected_manifest_sha256=trace.manifest_sha256)
    assert events == ["terminated", "joined"]
    assert signal.getsignal(signal.SIGINT) == original_handler
    assert multiprocessing.active_children() == []
    print(json.dumps({"received": len(result.results), "pending": len(result.pending_trajectory_ids)}))
finally:
    # Cleanup also runs against the unfixed implementation during reproduction.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    pool.pool.terminate()
    pool.pool.join()
'''
    process = subprocess.Popen(
        [sys.executable, "-c", script, interrupt_stage],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=25)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        pytest.fail("SIGINT cleanup exceeded the 25-second process-group watchdog")
    assert process.returncode == 0, stderr
    assert json.loads(stdout) == {
        "received": 1 if interrupt_stage == "iteration" else 2,
        "pending": 1 if interrupt_stage == "iteration" else 0,
    }
