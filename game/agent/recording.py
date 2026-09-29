"""Strict, public-only JSONL trajectories with cancellation-safe publication.

This module never opens audit files, snapshots, or paths supplied by file content.
Private replay information belongs outside the public dataset directory.
"""
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.contracts.codec import _invalid_constant, _unique_object
from game.agent.provenance import ENCODING, Implementation

SCHEMA = 'sts_public_trajectory_v1'
SUFFIX = '.trajectory.jsonl'
SPLITS = ('train', 'validation', 'test')
EVIDENCE = ('headless_rollout', 'controlled_fixture')


class TrajectoryError(ValueError):
    """An incomplete, incompatible or malformed public artifact."""


@dataclass(frozen=True, slots=True)
class Metadata:
    episode_id: str
    target: str
    build: str
    rules: str
    policy: str
    scenario: str
    split: str
    evidence: str
    encoding: str = ENCODING

    @classmethod
    def create(cls, identity: Implementation, *, episode_id, scenario, split,
               evidence='headless_rollout'):
        return cls(episode_id, identity.target, identity.build, identity.rules,
                   identity.policy, scenario, split, evidence)


@dataclass(frozen=True, slots=True)
class Transition:
    observation: f.PublicDecision
    action: f.Candidate
    execution: c.ExecutionReport
    successor: f.PublicDecision | c.RunOutcome
    reward: int


@dataclass(frozen=True, slots=True)
class Trajectory:
    metadata: Metadata
    initial: f.PublicDecision | c.RunOutcome
    transitions: tuple[Transition, ...]
    outcome: c.RunOutcome
    # Exact published file, INCLUDING the footer. Additive loader metadata;
    # neither the wire format nor semantic episode equality changes.
    sha256: str = field(default='', compare=False)


def _require(condition, reason):
    if not condition:
        raise TrajectoryError(reason)


def _keys(value, keys):
    _require(type(value) is dict and set(value) == set(keys), 'Unexpected record fields')


def _metadata(value):
    _keys(value, Metadata.__dataclass_fields__)
    _require(all(type(v) is str and 0 < len(v) <= 256 for v in value.values()), 'Invalid metadata')
    _require(re.fullmatch(r'[0-9a-f]{32}', value['episode_id']) is not None, 'Invalid episode identity')
    _require(all(re.fullmatch(r'[0-9a-f]{64}', value[key]) for key in ('build', 'rules')), 'Invalid source identity')
    _require(value['split'] in SPLITS and value['evidence'] in EVIDENCE, 'Invalid split or evidence label')
    _require(value['encoding'] == ENCODING, 'Unsupported public encoding')
    return Metadata(**value)


def _public(value):
    try:
        result = f.from_dict(value)
    except (c.ContractError, RecursionError) as error:
        raise TrajectoryError('Invalid public observation') from error
    _require(type(result) in (f.PublicDecision, c.RunOutcome), 'Invalid public observation')
    return result


def _transition(current, value, index):
    _keys(value, ('record', 'index', 'action', 'execution', 'next', 'reward'))
    _require(value['record'] == 'transition' and type(value['index']) is int
             and value['index'] == index, 'Invalid transition sequence')
    _require(type(current) is f.PublicDecision, 'Action after terminal outcome')
    _require(type(value['action']) is str, 'Invalid chosen action')
    action = next((a for a in current.candidates if a.ref == value['action']), None)
    _require(action is not None, 'Chosen action was not advertised')
    try:
        report = c.from_dict(value['execution'])
    except c.ContractError as error:
        raise TrajectoryError('Invalid execution report') from error
    _require(type(report) is c.ExecutionReport and report.status == 'reconciled'
             and report.reason == 'none' and report.mutation in ('none', 'applied'),
             'Only reconciled actions are transitions')
    successor = _public(value['next'])
    reward = int(isinstance(successor, c.RunOutcome) and successor.kind == 'victory')
    _require(type(value['reward']) is int and value['reward'] == reward, 'Invalid sparse reward')
    return Transition(current, action, report, successor, reward)


def _ending(current, value, count, digest):
    _keys(value, ('record', 'steps', 'outcome', 'sha256'))
    _require(value['record'] == 'complete' and type(value['steps']) is int
             and value['steps'] == count, 'Invalid completion record')
    _require(value['sha256'] == digest, 'Trajectory digest mismatch')
    outcome = _public(value['outcome'])
    _require(type(outcome) is c.RunOutcome, 'Missing final outcome')
    if isinstance(current, c.RunOutcome):
        _require(current == outcome, 'Conflicting terminal outcomes')
    else:
        _require(outcome.kind == 'truncated' and outcome.reason in
                 ('decision_budget', 'time_budget', 'external_stop'),
                 'A ready decision can only end at an external cutoff')
    return outcome


def _line(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def _parse(line):
    try:
        return json.loads(line, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (ValueError, TypeError, UnicodeDecodeError, RecursionError) as error:
        raise TrajectoryError('Invalid trajectory JSON') from error


class TrajectoryWriter:
    """Write one new artifact; never overwrite a finished file, even on a race.

    A .partial file is retained on errors or cancellation. Only finish publishes
    the complete artifact, via an atomic, no-clobber hard link on the same volume.
    """

    def __init__(self, path, metadata, initial):
        self.path = Path(path)
        _require(self.path.name.endswith(SUFFIX), 'Use a .trajectory.jsonl filename')
        self.metadata = _metadata(asdict(metadata))
        self.current = _public(f.to_dict(initial))
        self.count, self._digest, self._closed = 0, hashlib.sha256(), False
        self.partial = self.path.with_name(self.path.name + '.partial')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError(self.path)
        self._file = self.partial.open('xb')
        try:
            self._write({'record': 'header', 'schema': SCHEMA,
                         'metadata': asdict(self.metadata), 'initial': f.to_dict(initial)})
        except BaseException:
            self.abort()
            raise

    def _write(self, value):
        _require(not self._closed, 'Writer is closed')
        line = _line(value)
        self._file.write(line)
        self._file.flush()
        self._digest.update(line)

    def append(self, action, execution, successor):
        value = {'record': 'transition', 'index': self.count, 'action': action.ref,
                 'execution': c.to_dict(execution), 'next': f.to_dict(successor),
                 'reward': int(isinstance(successor, c.RunOutcome) and successor.kind == 'victory')}
        transition = _transition(self.current, value, self.count)
        _require(action == transition.action, 'Chosen action does not match its advertised identity')
        self._write(value)
        self.current = transition.successor
        self.count += 1

    def finish(self, outcome, *, check_cancel=None):
        value = {'record': 'complete', 'steps': self.count,
                 'outcome': c.to_dict(outcome), 'sha256': self._digest.hexdigest()}
        _ending(self.current, value, self.count, self._digest.hexdigest())
        try:
            self._write(value)
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
        if not self._closed:
            self._file.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.abort()


def load_trajectory(path, *, split=None, expected=None):
    """Validate the whole completed artifact before exposing any training samples.

    ``expected`` may pin any metadata fields, including rules/build/policy.
    ``split`` rejects cross-split inputs rather than silently mixing datasets.
    No file content is ever interpreted as a filesystem path.
    """
    path = Path(path)
    _require(path.name.endswith(SUFFIX), 'Only published public trajectories can be loaded')
    digest, file_digest, transitions, outcome = hashlib.sha256(), hashlib.sha256(), [], None
    with path.open('rb') as source:
        line = source.readline()
        header = _parse(line)
        _keys(header, ('record', 'schema', 'metadata', 'initial'))
        _require(header['record'] == 'header' and header['schema'] == SCHEMA, 'Unsupported trajectory version')
        metadata = _metadata(header['metadata'])
        if split is not None:
            _require(split in SPLITS and metadata.split == split, 'Dataset split mismatch')
        if expected is not None:
            _require(type(expected) is dict and set(expected) <= set(Metadata.__dataclass_fields__), 'Unknown metadata expectation')
            _require(all(getattr(metadata, key) == value for key, value in expected.items()), 'Artifact identity mismatch')
        initial = current = _public(header['initial'])
        digest.update(line)
        file_digest.update(line)
        for line in source:
            file_digest.update(line)
            value = _parse(line)
            _require(type(value) is dict, 'Invalid trajectory record')
            if value.get('record') == 'complete':
                outcome = _ending(current, value, len(transitions), digest.hexdigest())
                _require(not source.read(1), 'Records after completion')
                break
            transition = _transition(current, value, len(transitions))
            transitions.append(transition)
            current = transition.successor
            digest.update(line)
    _require(outcome is not None, 'Incomplete trajectory')
    return Trajectory(metadata, initial, tuple(transitions), outcome, file_digest.hexdigest())
