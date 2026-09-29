"""Bounded headless execution of public policy decisions; no optional dependencies."""
from dataclasses import asdict, dataclass, replace
import json
import math
import os
from pathlib import Path
import time
import uuid

from game.agent import contracts as c
from game.agent.full_policy import choose_action
from game.agent.headless import HeadlessAdapter
from game.agent.provenance import implementation
from game.agent.progress import completed_act
from game.agent.recording import EVIDENCE, SPLITS, Metadata, SUFFIX, TrajectoryWriter


class RunCancelled(Exception):
    """Interrupted work remains partial and is not a game outcome."""


class RunFailure(RuntimeError):
    """Execution failed; do not retry a possibly applied action."""


def _chooser(adapter, policy, combat_policy):
    summary = adapter.combat_summary if combat_policy is not None else None
    return combat_policy if summary is not None and not summary.completed else policy


@dataclass(frozen=True, slots=True)
class RunConfig:
    seed: int = 0
    character: str = 'ironclad'
    first_act: str = 'overgrowth'
    ascension: int = 0
    max_decisions: int = 4096
    time_limit_seconds: float = 300.0
    scenario: str = 'generated_campaign_all_unlocked_v1'
    split: str = 'train'
    evidence: str = 'headless_rollout'
    goal: str = 'full_run'

    def validate(self):
        from game.headless.characters import CHARACTERS
        if type(self.seed) is not int:
            raise ValueError('seed must be an integer')
        if self.character not in CHARACTERS or self.first_act not in ('overgrowth', 'underdocks'):
            raise ValueError('Unsupported character or Act 1 region')
        if type(self.ascension) is not int or not 0 <= self.ascension <= 10:
            raise ValueError('ascension must be between 0 and 10')
        if type(self.max_decisions) is not int or self.max_decisions < 1:
            raise ValueError('max_decisions must be a positive integer')
        if (type(self.time_limit_seconds) not in (int, float)
                or not math.isfinite(self.time_limit_seconds) or self.time_limit_seconds <= 0):
            raise ValueError('time_limit_seconds must be positive and finite')
        if type(self.scenario) is not str or not 0 < len(self.scenario) <= 256:
            raise ValueError('scenario must be a nonempty public identifier')
        if self.split not in SPLITS or self.evidence not in EVIDENCE:
            raise ValueError('Invalid split or evidence label')
        if self.goal not in ('full_run', 'act1'):
            raise ValueError('Unsupported campaign goal')


@dataclass(frozen=True, slots=True)
class Timings:
    reset_seconds: float
    observe_seconds: float
    policy_seconds: float
    step_seconds: float
    recording_seconds: float
    total_seconds: float
    observations: int
    steps: int


@dataclass(frozen=True, slots=True)
class RunResult:
    episode_id: str
    trajectory: str
    outcome: c.RunOutcome
    timings: Timings


def prepare_directories(output_dir, audit_dir):
    """Require disjoint public/private trees; private files use owner-only modes."""
    output, audit = Path(output_dir).resolve(), Path(audit_dir).resolve()
    if output == audit or output in audit.parents or audit in output.parents:
        raise ValueError('Public output and private audit directories must be disjoint')
    output.mkdir(parents=True, exist_ok=True)
    audit.mkdir(parents=True, exist_ok=True, mode=0o700)
    if audit.stat().st_mode & 0o077:
        raise ValueError('Private audit directory must have owner-only permissions (0700)')
    return output, audit


def _audit(path, *, episode_id, config, identity):
    # A private seed and exact configuration are enough to recreate this fresh
    # headless run. No engine snapshots or private state enter the public writer.
    settings = asdict(config)
    if config.goal == 'full_run':
        settings.pop('goal')
    value = {'schema': 'sts_private_replay_v2' if config.goal == 'act1' else 'sts_private_replay_v1',
             'episode_id': episode_id, 'config': settings, 'implementation': asdict(identity)}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as target:
        json.dump(value, target, sort_keys=True, allow_nan=False)
        target.write('\n')
        target.flush()
        os.fsync(target.fileno())


def run_episode(config, *, output_dir, audit_dir, episode_id=None, cancel=None,
                engine_factory=None, policy=choose_action, policy_identity=None, combat_policy=None):
    """Record one exclusively owned run, passing only public decisions to policy.

    Custom factories must be labelled controlled_fixture. Custom policies need
    an explicit implementation identity supplied by their caller. Timings include
    recording overhead; they are observational metrics, never policy features.
    """
    config.validate()
    if engine_factory is not None and config.evidence != 'controlled_fixture':
        raise ValueError('Custom engine factories require controlled_fixture evidence')
    if (policy is not choose_action or combat_policy is not None) and not policy_identity:
        raise ValueError('Custom policies require an explicit policy identity')
    episode_id = episode_id or uuid.uuid4().hex
    identity = implementation()
    if policy_identity is not None:
        identity = replace(identity, policy=policy_identity)
    metadata = Metadata.create(identity, episode_id=episode_id, scenario=config.scenario,
                               split=config.split, evidence=config.evidence)
    # Validate public metadata before constructing any output paths from IDs.
    from game.agent.recording import _metadata
    _metadata(asdict(metadata))
    output, audit = prepare_directories(output_dir, audit_dir)
    path = output / (episode_id + SUFFIX)

    def cancelled():
        if cancel is not None and cancel.is_set():
            raise RunCancelled('Run cancelled; unfinished recording remains partial')

    cancelled()
    _audit(audit / (episode_id + '.audit.json'), episode_id=episode_id, config=config, identity=identity)
    started = time.perf_counter()
    if engine_factory is None:
        from game.headless.run.engine import RunEngine
        from game.headless.run.ancient import PROFILE
        engine_factory = lambda seed: RunEngine.campaign(
            seed=seed, character=config.character, first_act=config.first_act,
            ascension=config.ascension, ancient_profile=PROFILE)
    adapter = HeadlessAdapter(engine_factory(config.seed), decision_profile='full_run_v2')
    reset_seconds = time.perf_counter() - started
    observations = steps = 0
    observe_seconds = policy_seconds = step_seconds = recording_seconds = 0.0

    def observe():
        nonlocal observe_seconds, observations
        before = time.perf_counter()
        frame = adapter.observe()
        observe_seconds += time.perf_counter() - before
        observations += 1
        return frame

    frame = observe()
    initial = frame if isinstance(frame, c.RunOutcome) else frame.decision
    if config.goal == 'act1' and (not hasattr(initial, 'run') or completed_act(initial) is not None
                                 or initial.run.get('act') != 1):
        raise RunFailure('Act 1 requires an unfinished Act 1 start')
    before = time.perf_counter()
    writer = TrajectoryWriter(path, metadata, initial)
    recording_seconds += time.perf_counter() - before
    with writer:
        while True:
            cancelled()
            if isinstance(frame, c.RunOutcome):
                outcome = frame
                break
            if config.goal == 'act1' and completed_act(frame.decision) == 1:
                # A successful task boundary is still an unfinished campaign.
                # This takes precedence over a coincident decision/time budget.
                outcome = c.RunOutcome('sts_run_outcome_v1', 'truncated', 'external_stop')
                break
            if steps >= config.max_decisions:
                outcome = c.RunOutcome('sts_run_outcome_v1', 'truncated', 'decision_budget')
                break
            if time.perf_counter() - started >= config.time_limit_seconds:
                outcome = c.RunOutcome('sts_run_outcome_v1', 'truncated', 'time_budget')
                break
            before = time.perf_counter()
            # Routing is a controller decision based on authoritative ownership.
            # Nested relic/selection contexts can still belong to a live fight;
            # a completed fight's reward/pickup choices belong to the heuristic.
            candidate = _chooser(adapter, policy, combat_policy)(frame.decision)
            policy_seconds += time.perf_counter() - before
            if candidate not in frame.decision.candidates:
                raise RunFailure('Policy returned an unadvertised action')
            cancelled()
            # A slow policy must not dispatch after its time budget expires.
            if time.perf_counter() - started >= config.time_limit_seconds:
                outcome = c.RunOutcome('sts_run_outcome_v1', 'truncated', 'time_budget')
                break
            before = time.perf_counter()
            report = adapter.step(frame.binding, candidate.ref)
            step_seconds += time.perf_counter() - before
            if report.status != 'reconciled':
                raise RunFailure('Action was not reconciled: ' + report.status)
            frame = observe()
            successor = frame if isinstance(frame, c.RunOutcome) else frame.decision
            before = time.perf_counter()
            writer.append(candidate, report, successor)
            recording_seconds += time.perf_counter() - before
            steps += 1
        cancelled()
        before = time.perf_counter()
        writer.finish(outcome, check_cancel=cancelled)
        recording_seconds += time.perf_counter() - before
    return RunResult(episode_id, str(path), outcome,
                     Timings(reset_seconds, observe_seconds, policy_seconds, step_seconds,
                             recording_seconds, time.perf_counter() - started, observations, steps))
