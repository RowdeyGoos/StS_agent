"""Bounded, replay-recorded batch collection for ``headless_v0``.

This module is deliberately a consumer of the accepted backend, runner, and
trajectory contracts.  It does not add policy inputs, game rules, or an
alternate episode loop.  Collector scheduling randomness is kept separate
from both the supplied game seed and chooser seed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from multiprocessing import get_context
from random import Random
from typing import Any, Callable, Mapping, Protocol

from game.agents.headless_baselines import (
    FirstLegalChooser,
    SeededChooserConfig,
    SeededRandomChooser,
    choose_structural_heuristic,
)
from game.backends.headless.reduced_run_backend import (
    HeadlessRunConfig,
    ReducedRunBackend,
    create_reduced_run_backend,
)
from game.contracts.headless_v0 import DecisionState, DecisionStatus, Transition, canonical_json
from game.data.headless_trajectory import (
    FinalizedTrajectory,
    TrajectoryRecorder,
    TrajectoryValidationError,
)
from game.runtime.episode_runner import EpisodeResult, EpisodeStopReason, run_episode


class RolloutStopReason(str, Enum):
    """Collector-level reasons, intentionally distinct from game outcomes."""

    DEFEAT = "defeat"
    ROUTE_COMPLETE = "route_complete"
    UNSUPPORTED = "unsupported"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TERMINAL = "terminal"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


class ChooserKind(str, Enum):
    """The small pickle-safe chooser registry available to spawned workers."""

    FIRST_LEGAL = "first_legal"
    SEEDED_RANDOM = "seeded_random"
    STRUCTURAL_HEURISTIC = "structural_heuristic"


class RolloutBackend(Protocol):
    def manifest(self) -> Any: ...
    def reset(self, configuration: Any) -> DecisionState: ...
    def observe(self) -> DecisionState: ...
    def apply(self, action: Any) -> Transition: ...
    def snapshot(self) -> Mapping[str, Any]: ...
    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class BackendFactoryDescriptor:
    """Serializable factory selector; it intentionally contains no callable."""

    backend_id: str = "reduced_headless"

    def __post_init__(self) -> None:
        if self.backend_id != "reduced_headless":
            raise ValueError("Only the accepted reduced_headless factory is supported.")

    def to_dict(self) -> dict[str, str]:
        return {"backend_id": self.backend_id}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BackendFactoryDescriptor":
        if not isinstance(value, Mapping) or set(value) != {"backend_id"}:
            raise ValueError("Backend factory descriptor fields must be exact.")
        return cls(backend_id=value["backend_id"])

    def create(self) -> ReducedRunBackend:
        return create_reduced_run_backend()


@dataclass(frozen=True, slots=True)
class HeadlessRolloutConfig:
    """One serializable episode request with independent game and policy seeds."""

    trajectory_id: str
    run_config: HeadlessRunConfig
    transition_budget: int
    chooser_kind: ChooserKind = ChooserKind.STRUCTURAL_HEURISTIC
    policy_seed: int = 0
    factory: BackendFactoryDescriptor = BackendFactoryDescriptor()

    def __post_init__(self) -> None:
        if not isinstance(self.trajectory_id, str) or not self.trajectory_id:
            raise ValueError("trajectory_id must be a nonempty string.")
        if not isinstance(self.run_config, HeadlessRunConfig):
            raise TypeError("run_config must be a HeadlessRunConfig.")
        if (
            not isinstance(self.transition_budget, int)
            or isinstance(self.transition_budget, bool)
            or self.transition_budget < 0
        ):
            raise ValueError("transition_budget must be a nonnegative integer.")
        object.__setattr__(self, "chooser_kind", ChooserKind(self.chooser_kind))
        if not isinstance(self.policy_seed, int) or isinstance(self.policy_seed, bool):
            raise TypeError("policy_seed must be an integer, not bool.")
        if not isinstance(self.factory, BackendFactoryDescriptor):
            raise TypeError("factory must be a BackendFactoryDescriptor.")


@dataclass(frozen=True, slots=True)
class CollectorWorkerConfig:
    """Collector-owned scheduling configuration, never backend configuration."""

    worker_count: int = 1
    worker_seed: int = 0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.worker_count, int)
            or isinstance(self.worker_count, bool)
            or self.worker_count <= 0
        ):
            raise ValueError("worker_count must be a positive integer.")
        if not isinstance(self.worker_seed, int) or isinstance(self.worker_seed, bool):
            raise TypeError("worker_seed must be an integer, not bool.")


@dataclass(frozen=True, slots=True)
class HeadlessBatchConfig:
    """A bounded ordered panel plus collector-only worker configuration."""

    episodes: tuple[HeadlessRolloutConfig, ...]
    worker: CollectorWorkerConfig = CollectorWorkerConfig()

    def __post_init__(self) -> None:
        episodes = tuple(self.episodes)
        if not episodes:
            raise ValueError("episodes must not be empty.")
        if any(not isinstance(item, HeadlessRolloutConfig) for item in episodes):
            raise TypeError("episodes must contain HeadlessRolloutConfig values.")
        identifiers = tuple(item.trajectory_id for item in episodes)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("trajectory_id values must be unique within a batch.")
        object.__setattr__(self, "episodes", episodes)
        if not isinstance(self.worker, CollectorWorkerConfig):
            raise TypeError("worker must be a CollectorWorkerConfig.")


@dataclass(frozen=True, slots=True)
class HeadlessRolloutResult:
    """One local episode result with separately validated trajectory sidecars."""

    config: HeadlessRolloutConfig
    stop_reason: RolloutStopReason
    transition_count: int
    final_decision_json: str | None
    initial_snapshot_sha256: str | None
    final_snapshot_sha256: str | None
    trajectory: FinalizedTrajectory | None
    failure: str | None = None

    @property
    def evidence(self) -> tuple[Any, ...]:
        return () if self.trajectory is None else self.trajectory.manifest.evidence


@dataclass(frozen=True, slots=True)
class HeadlessBatchResult:
    """Order-stable completed results plus an explicit cancellation remainder."""

    results: tuple[HeadlessRolloutResult, ...]
    process_safe: bool
    worker: CollectorWorkerConfig
    interrupted: bool = False
    pending_trajectory_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.interrupted, bool):
            raise TypeError("interrupted must be a boolean.")
        pending = tuple(self.pending_trajectory_ids)
        if any(not isinstance(item, str) for item in pending):
            raise TypeError("pending_trajectory_ids must contain strings.")
        if pending and not self.interrupted:
            raise ValueError("Only an interrupted batch can retain pending episodes.")
        completed = tuple(item.config.trajectory_id for item in self.results)
        if len(set(completed)) != len(completed):
            raise ValueError("Batch results must not duplicate a trajectory ID.")
        if set(completed) & set(pending):
            raise ValueError("Completed and pending trajectory IDs must be disjoint.")
        object.__setattr__(self, "pending_trajectory_ids", pending)

    @property
    def transition_count(self) -> int:
        return sum(item.transition_count for item in self.results)


def _make_chooser(config: HeadlessRolloutConfig) -> Callable[[Any], str]:
    if config.chooser_kind is ChooserKind.FIRST_LEGAL:
        return FirstLegalChooser()
    if config.chooser_kind is ChooserKind.SEEDED_RANDOM:
        return SeededRandomChooser(SeededChooserConfig(config.policy_seed))
    return choose_structural_heuristic


def _snapshot_digest(backend: RolloutBackend) -> str | None:
    try:
        snapshot = backend.snapshot()
    except Exception:
        return None
    return sha256(canonical_json(snapshot).encode("utf-8")).hexdigest()


class _RecordingBackend:
    """Backend adapter that records receipts while leaving runner semantics intact."""

    def __init__(self, backend: RolloutBackend, recorder: TrajectoryRecorder) -> None:
        self.backend = backend
        self.recorder = recorder
        self.current: DecisionState | None = None
        self.initial_snapshot_sha256: str | None = None
        self.transition_count = 0

    def reset(self, configuration: Any) -> DecisionState:
        self.current = self.backend.reset(configuration)
        self.initial_snapshot_sha256 = _snapshot_digest(self.backend)
        return self.current

    def observe(self) -> DecisionState:
        self.current = self.backend.observe()
        return self.current

    def apply(self, action: Any) -> Transition:
        transition = self.backend.apply(action)
        self.transition_count += 1
        self.recorder.record_transition(transition)
        self.current = transition.next_decision
        return transition


class _RecordingChooser:
    def __init__(self, chooser: Callable[[Any], str], adapter: _RecordingBackend) -> None:
        self._chooser = chooser
        self._adapter = adapter

    def __call__(self, view: Any) -> str:
        chosen = self._chooser(view)
        current = self._adapter.current
        if current is None:
            raise RuntimeError("runner called chooser before backend reset")
        if chosen in {item.candidate_id for item in current.candidates}:
            self._adapter.recorder.record_boundary(current, chosen)
        return chosen


def _ensure_final_boundary(recorder: TrajectoryRecorder, decision: DecisionState) -> None:
    """Record the runner's final boundary when it was not presented to a chooser."""

    try:
        recorder.record_boundary(decision, None)
    except TrajectoryValidationError:
        # The current actionable boundary may already have been recorded before
        # a chooser/backend interruption.  In that case its partial state is
        # exactly what finalize_interrupted is designed to preserve.
        pass


def _stop_reason(result: EpisodeResult, backend: RolloutBackend) -> RolloutStopReason:
    if result.stop_reason is EpisodeStopReason.UNSUPPORTED:
        return RolloutStopReason.UNSUPPORTED
    if result.stop_reason is EpisodeStopReason.TRANSITION_BUDGET_EXHAUSTED:
        return RolloutStopReason.BUDGET_EXHAUSTED
    if result.stop_reason is EpisodeStopReason.TERMINAL:
        if getattr(backend, "terminal_reason", None) == "route_complete":
            return RolloutStopReason.ROUTE_COMPLETE
        if result.final_decision.observation.data.get("outcome") == "defeat":
            return RolloutStopReason.DEFEAT
        return RolloutStopReason.TERMINAL
    return RolloutStopReason.INTERRUPTED


def _partial_trajectory(adapter: _RecordingBackend) -> FinalizedTrajectory | None:
    """Safely retain an available authoritative boundary after cancellation."""

    decision = adapter.current
    if decision is None:
        return None
    _ensure_final_boundary(adapter.recorder, decision)
    try:
        if decision.status in {DecisionStatus.TERMINAL, DecisionStatus.UNSUPPORTED}:
            return adapter.recorder.finalize()
        return adapter.recorder.finalize_interrupted()
    except TrajectoryValidationError:
        return None


def _interrupted_result(
    config: HeadlessRolloutConfig,
    backend: RolloutBackend | None,
    adapter: _RecordingBackend | None,
    interruption: BaseException,
) -> HeadlessRolloutResult:
    """Report a cancellation separately from an ordinary backend failure."""

    decision = None if adapter is None else adapter.current
    return HeadlessRolloutResult(
        config,
        RolloutStopReason.INTERRUPTED,
        0 if adapter is None else adapter.transition_count,
        None if decision is None else decision.to_json(),
        None if adapter is None else adapter.initial_snapshot_sha256,
        None if backend is None else _snapshot_digest(backend),
        None if adapter is None else _partial_trajectory(adapter),
        failure=f"{type(interruption).__name__}: {interruption}",
    )


def _failed_result(
    config: HeadlessRolloutConfig,
    backend: RolloutBackend | None,
    adapter: _RecordingBackend | None,
    failure: BaseException,
) -> HeadlessRolloutResult:
    decision = None if adapter is None else adapter.current
    return HeadlessRolloutResult(
        config,
        RolloutStopReason.FAILED,
        0 if adapter is None else adapter.transition_count,
        None if decision is None else decision.to_json(),
        None if adapter is None else adapter.initial_snapshot_sha256,
        None if backend is None else _snapshot_digest(backend),
        None if adapter is None else _partial_trajectory(adapter),
        failure=f"{type(failure).__name__}: {failure}",
    )


def run_headless_rollout(config: HeadlessRolloutConfig) -> HeadlessRolloutResult:
    """Run one bounded reduced episode through the generic runner.

    The finalized trajectory always keeps replay, hindsight target, and audit
    records in physically distinct byte streams.  Non-terminal stops produce a
    validated interrupted sidecar rather than an invented terminal target.
    """

    if not isinstance(config, HeadlessRolloutConfig):
        raise TypeError("config must be a HeadlessRolloutConfig.")
    backend: RolloutBackend | None = None
    adapter: _RecordingBackend | None = None
    output: HeadlessRolloutResult | None = None
    try:
        backend = config.factory.create()
        recorder = TrajectoryRecorder(config.trajectory_id, backend.manifest())
        adapter = _RecordingBackend(backend, recorder)
        chooser = _RecordingChooser(_make_chooser(config), adapter)
        result = run_episode(
            adapter,
            config.run_config,
            chooser,
            transition_budget=config.transition_budget,
        )
        _ensure_final_boundary(recorder, result.final_decision)
        reason = _stop_reason(result, backend)
        trajectory = (
            recorder.finalize()
            if reason
            in {
                RolloutStopReason.ROUTE_COMPLETE,
                RolloutStopReason.DEFEAT,
                RolloutStopReason.TERMINAL,
                RolloutStopReason.UNSUPPORTED,
            }
            else recorder.finalize_interrupted()
        )
        output = HeadlessRolloutResult(
            config, reason, result.transition_count, result.final_decision.to_json(),
            adapter.initial_snapshot_sha256, _snapshot_digest(backend), trajectory,
        )
    except KeyboardInterrupt as interruption:
        output = _interrupted_result(config, backend, adapter, interruption)
    except BaseException as exc:
        output = _failed_result(config, backend, adapter, exc)
    finally:
        if backend is not None:
            try:
                backend.close()
            except Exception as close_error:
                if output is None:
                    output = _failed_result(config, backend, adapter, close_error)
    assert output is not None
    return output


def _run_batch_entry(config: HeadlessRolloutConfig) -> HeadlessRolloutResult:
    """Top-level spawn target; do not close over collector state."""

    return run_headless_rollout(config)


def _run_indexed_batch_entry(
    entry: tuple[int, HeadlessRolloutConfig],
) -> tuple[int, HeadlessRolloutResult]:
    """Top-level indexed target so completed spawned work can be retained."""

    index, config = entry
    return index, _run_batch_entry(config)


def _batch_result(
    config: HeadlessBatchConfig,
    completed: Mapping[int, HeadlessRolloutResult],
    *,
    process_safe: bool,
    interrupted: bool,
) -> HeadlessBatchResult:
    results = tuple(completed[index] for index in sorted(completed))
    pending = tuple(
        episode.trajectory_id
        for index, episode in enumerate(config.episodes)
        if index not in completed
    )
    return HeadlessBatchResult(
        results,
        process_safe,
        config.worker,
        interrupted=interrupted,
        pending_trajectory_ids=pending,
    )


def run_headless_batch(
    config: HeadlessBatchConfig, *, process_safe: bool = False
) -> HeadlessBatchResult:
    """Collect a deterministic seed panel sequentially or in spawned workers."""

    if not isinstance(config, HeadlessBatchConfig):
        raise TypeError("config must be a HeadlessBatchConfig.")
    indices = list(range(len(config.episodes)))
    Random(config.worker.worker_seed).shuffle(indices)
    scheduled = [(index, config.episodes[index]) for index in indices]
    completed: dict[int, HeadlessRolloutResult] = {}
    if process_safe:
        context = get_context("spawn")
        pool = context.Pool(processes=config.worker.worker_count)
        cancelled = False
        try:
            for index, result in pool.imap_unordered(_run_indexed_batch_entry, scheduled):
                completed[index] = result
                if result.stop_reason is RolloutStopReason.INTERRUPTED:
                    raise KeyboardInterrupt
        except KeyboardInterrupt:
            cancelled = True
            pool.terminate()
        else:
            pool.close()
        finally:
            pool.join()
        return _batch_result(
            config,
            completed,
            process_safe=True,
            interrupted=cancelled,
        )

    try:
        for index, episode in scheduled:
            result = _run_batch_entry(episode)
            completed[index] = result
            if result.stop_reason is RolloutStopReason.INTERRUPTED:
                raise KeyboardInterrupt
    except KeyboardInterrupt:
        return _batch_result(
            config,
            completed,
            process_safe=False,
            interrupted=True,
        )
    return _batch_result(config, completed, process_safe=False, interrupted=False)
