"""Compact combat-task sidecars joined to unchanged public trajectories.

Terminal HUD facts are attested by the combat owner, not reconstructed from
hidden state. Digests bind the exact canonical file, including its run footer.
Loaders accept explicit paths only and never open private replay audits.
"""
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.headless.combat_summary import CombatSummary
from game.agent.trace_storage import is_trajectory, logical_path
from game.agent.recording import (SUFFIX as TRAJECTORY_SUFFIX, Trajectory, TrajectoryError,
                                  TrajectoryWriter, Transition, load_trajectory)
from .rewards import RewardComponents, RewardSpec, finite, measure, public_summary, strict_json

SCHEMA = 'sts_combat_training_v1'
SUFFIX = '.training.json'


class TrainingRecordError(TrajectoryError):
    """Incomplete, incompatible or inconsistent training measurements."""


def _require(condition, reason):
    if not condition:
        raise TrainingRecordError(reason)


def _keys(value, names):
    _require(type(value) is dict and set(value) == set(names), 'Unexpected training record fields')


def _flags(summary, terminated, truncated):
    _require(type(terminated) is bool and type(truncated) is bool and not (terminated and truncated),
             'Invalid task flags')
    _require(terminated == summary.completed, 'Task termination disagrees with combat result')


def _state(summary, state):
    if summary.completed:
        _require(type(state) is c.RunOutcome, 'Completed combat must end its canonical trajectory')
        expected = ('truncated', 'external_stop') if summary.outcome == 'victory' else ('defeat', 'none')
        _require((state.kind, state.reason) == expected, 'Incompatible canonical combat endpoint')
    else:
        _require(type(state) is f.PublicDecision and state.context.kind in ('combat', 'relic_choice'),
                 'Ongoing task must retain a combat-owned public decision')
        _require((state.run.get('hp'), state.run.get('max_hp')) == (summary.hp, summary.max_hp),
                 'Combat measurement disagrees with the public HUD')
        if state.context.kind == 'combat':
            _require(state.context.get('round') == summary.turn, 'Combat turn measurement mismatch')


@dataclass(frozen=True, slots=True)
class TaskEnding:
    terminated: bool
    truncated: bool
    combat: CombatSummary


@dataclass(frozen=True, slots=True)
class TrainingTransition:
    index: int
    transition: Transition
    components: RewardComponents
    reward: float
    terminated: bool
    truncated: bool
    combat: CombatSummary


@dataclass(frozen=True, slots=True)
class TrainingEpisode:
    trajectory: Trajectory
    recorded_spec: RewardSpec
    reward_spec: RewardSpec
    transitions: tuple[TrainingTransition, ...]
    ending: TaskEnding


def _read(path):
    path = Path(path)
    _require(path.name.endswith(SUFFIX), 'Only published training sidecars can be loaded')
    value = strict_json(path.read_text(encoding='utf-8'))
    _keys(value, ('schema', 'task', 'trajectory_sha256', 'episode_id', 'reward_spec',
                  'reward_spec_id', 'initial_combat', 'transitions', 'ending'))
    _require(value['schema'] == SCHEMA and value['task'] == 'combat', 'Unsupported training sidecar')
    spec = RewardSpec.from_dict(value['reward_spec'])
    _require(spec.task == 'combat', 'Combat sidecars require a combat objective')
    _require(value['reward_spec_id'] == spec.identity, 'Reward specification identity mismatch')
    return value, spec


def _validate(value, spec, trajectory, reward_spec=None):
    effective = spec if reward_spec is None else reward_spec
    _require(type(effective) is RewardSpec and effective.task == 'combat', 'Expected an explicit combat RewardSpec conversion')
    _require(value['trajectory_sha256'] == trajectory.sha256 and bool(trajectory.sha256),
             'Training trajectory digest mismatch')
    _require(value['episode_id'] == trajectory.metadata.episode_id, 'Training episode identity mismatch')
    before = public_summary(value['initial_combat'])
    _require(not before.completed, 'Combat task must start in an ongoing fight')
    _state(before, trajectory.initial)
    rows = value['transitions']
    _require(type(rows) is list and len(rows) == len(trajectory.transitions), 'Missing or extra training transitions')
    result = []
    for index, (row, transition) in enumerate(zip(rows, trajectory.transitions)):
        _keys(row, ('index', 'components', 'reward', 'terminated', 'truncated', 'combat'))
        _require(type(row['index']) is int and row['index'] == index, 'Invalid training transition sequence')
        after = public_summary(row['combat'])
        components = RewardComponents.from_dict(row['components'])
        _require(components == measure(transition.action, transition.execution, before, after),
                 'Reward components disagree with the public transition')
        _require(finite(row['reward']) == spec.evaluate(components), 'Recorded training reward mismatch')
        _flags(after, row['terminated'], row['truncated'])
        _state(after, transition.successor)
        last = index == len(rows) - 1
        _require(last or not (row['terminated'] or row['truncated']), 'Action after task boundary')
        result.append(TrainingTransition(index, transition, components, effective.evaluate(components),
                                         row['terminated'], row['truncated'], after))
        before = after
    ending = value['ending']
    _keys(ending, ('terminated', 'truncated', 'combat'))
    final = public_summary(ending['combat'])
    _require(final == before, 'Ending cannot introduce an unrecorded combat result')
    _flags(final, ending['terminated'], ending['truncated'])
    _require(ending['terminated'] or ending['truncated'], 'Missing task endpoint')
    if final.completed:
        _state(final, trajectory.outcome)
    else:
        _require(trajectory.outcome.kind == 'truncated' and trajectory.outcome.reason in
                 ('decision_budget', 'time_budget', 'external_stop'), 'Invalid combat cutoff')
    if rows:
        _require((rows[-1]['terminated'], rows[-1]['truncated']) ==
                 (ending['terminated'], ending['truncated']), 'Final transition task flags mismatch')
    return TrainingEpisode(trajectory, spec, effective, tuple(result),
                           TaskEnding(ending['terminated'], ending['truncated'], final))


def load_training_episode(trajectory_path, sidecar_path, *, split, expected=None, reward_spec=None):
    """Validate the whole join; optionally rescore under a named new objective.

    Conversion is in memory and leaves both original artifacts untouched. All
    original components and rewards must validate even when weights are zero.
    """
    from game.agent.recording import SPLITS
    _require(split in SPLITS, 'An explicit train/validation/test split is required')
    value, spec = _read(sidecar_path)
    trajectory = load_trajectory(trajectory_path, split=split, expected=expected)
    return _validate(value, spec, trajectory, reward_spec)


class CombatTrainingRecorder:
    """Publish canonical data first, then its validated compact training sidecar.

    A failure between the two publications may leave a valid canonical artifact,
    but never a complete training pair. Partials are retained for diagnosis.
    """
    def __init__(self, path, metadata, initial, initial_combat, *, reward_spec=None, prepared=None):
        self.spec = RewardSpec() if reward_spec is None else reward_spec
        _require(type(self.spec) is RewardSpec and self.spec.task == 'combat', 'Expected a combat RewardSpec')
        self.initial = self.current = public_summary(initial_combat)
        _require(not self.initial.completed, 'Combat task must start in an ongoing fight')
        _state(self.initial, initial)
        path = Path(path)
        _require(is_trajectory(path), 'Use a .trajectory.jsonl or .trajectory.jsonl.gz filename')
        logical = logical_path(path)
        self.path = path.with_name(logical.name[:-len(TRAJECTORY_SUFFIX)] + SUFFIX)
        self.partial = self.path.with_name(self.path.name + '.partial')
        if self.path.exists():
            raise FileExistsError(self.path)
        self.writer = TrajectoryWriter(path, metadata, initial, prepared=prepared)
        self.rows = []
        self._file = None
        self._closed = False
        try:
            self._file = self.partial.open('x', encoding='utf-8')
        except BaseException:
            self.abort()
            raise

    def append(self, action, execution, successor, *, combat_summary, reward, terminated, truncated,
               prepared=None):
        _require(not self._closed, 'Recorder is closed')
        _require(not self.rows or not (self.rows[-1]['terminated'] or self.rows[-1]['truncated']),
                 'Action after task boundary')
        after = public_summary(combat_summary)
        components = measure(action, execution, self.current, after)
        _require(finite(reward) == self.spec.evaluate(components), 'Environment reward disagrees with recorder')
        _flags(after, terminated, truncated)
        _state(after, successor)
        self.writer.append(action, execution, successor, prepared=prepared)
        self.rows.append({'index': len(self.rows), 'components': asdict(components), 'reward': reward,
                          'terminated': terminated, 'truncated': truncated, 'combat': asdict(after)})
        self.current = after

    def finish(self, outcome, *, combat_summary, terminated, truncated, check_cancel=None):
        _require(not self._closed, 'Recorder is closed')
        final = public_summary(combat_summary)
        _require(final == self.current, 'Ending cannot introduce an unrecorded combat result')
        _flags(final, terminated, truncated)
        _require(terminated or truncated, 'Missing task endpoint')
        if final.completed:
            _state(final, outcome)
        else:
            _require(type(outcome) is c.RunOutcome and outcome.kind == 'truncated' and outcome.reason in
                     ('decision_budget', 'time_budget', 'external_stop'), 'Invalid combat cutoff')
        if self.rows:
            last = self.rows[-1]
            if not (last['terminated'] or last['truncated']):
                # A pre-dispatch timeout ends the last accepted transition, with
                # no extra command, measured event, or fabricated terminal reward.
                _require(truncated, 'Unrecorded task termination')
                last['truncated'] = True
            _require((last['terminated'], last['truncated']) == (terminated, truncated),
                     'Final transition task flags mismatch')
        try:
            self.writer.finish(outcome, check_cancel=check_cancel)
            trajectory = load_trajectory(self.writer.path, split=self.writer.metadata.split)
            value = {'schema': SCHEMA, 'task': 'combat', 'trajectory_sha256': trajectory.sha256,
                     'episode_id': trajectory.metadata.episode_id, 'reward_spec': self.spec.to_dict(),
                     'reward_spec_id': self.spec.identity, 'initial_combat': asdict(self.initial),
                     'transitions': self.rows,
                     'ending': {'terminated': terminated, 'truncated': truncated, 'combat': asdict(final)}}
            _validate(value, self.spec, trajectory)
            json.dump(value, self._file, sort_keys=True, separators=(',', ':'), allow_nan=False)
            self._file.write('\n')
            self._file.flush()
            os.fsync(self._file.fileno())
            self._file.close()
            self._closed = True
            if check_cancel is not None:
                check_cancel()
            os.link(self.partial, self.path)
            self.partial.unlink()
        except BaseException:
            self.abort()
            raise
        return self.path

    def abort(self):
        self.writer.abort()
        if self._file is not None and not self._file.closed:
            self._file.close()
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.abort()
