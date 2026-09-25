"""Opt-in public native decision/action journal, without transport bindings.

Nested native actions can complete out of dispatch order. This format retains
aggregate native completion counts; it never labels an accepted parent as a
reconciled training transition. The headless trajectory loader stays separate.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.contracts.codec import _invalid_constant, _unique_object
from game.agent.recording import SPLITS, TrajectoryError

SCHEMA = 'sts_public_live_trajectory_v1'
SUFFIX = '.live.jsonl'


def require(ok, reason):
    if not ok:
        raise TrajectoryError(reason)


def metadata(value):
    require(type(value) is dict and set(value) == {'release_sha256', 'split', 'setup'}, 'Invalid live metadata')
    require(type(value['release_sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['release_sha256']), 'Invalid release identity')
    require(type(value['split']) is str and value['split'] in SPLITS and type(value['setup']) is str and value['setup'] in ('normal', 'assisted', 'controlled', 'resumed'), 'Invalid live setup')
    return dict(value)


def counts(value, before):
    require(type(value) is list and len(value) == 3 and all(type(n) is int and 0 <= n <= 8192 for n in value), 'Invalid native counts')
    require(value[2] <= value[1] <= value[0] and all(a >= b for a, b in zip(value, before)), 'Native counts regressed')
    return value


class LiveTrajectoryWriter:
    def __init__(self, path, *, release_sha256, split, setup):
        self.path = Path(path)
        require(self.path.name.endswith(SUFFIX), 'Use a .live.jsonl filename')
        self.metadata = metadata(dict(release_sha256=release_sha256, split=split, setup=setup))
        self.partial = self.path.with_name(self.path.name + '.partial')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError(self.path)
        self.file = self.partial.open('xb')
        self.digest = hashlib.sha256()
        self.current = None
        self.observed = False
        self.uncertain = False
        self.counts = [0, 0, 0]
        self.closed = False
        try:
            self._write(dict(record='header', schema=SCHEMA, metadata=self.metadata))
        except BaseException:
            self.abort()
            raise

    def _write(self, value):
        require(not self.closed, 'Journal is closed')
        raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
        self.file.write(raw)
        self.file.flush()
        self.digest.update(raw)

    def observe(self, observation, native_counts):
        public = f.from_dict(f.to_dict(observation))
        require(type(public) is f.PublicDecision and self.current is None, 'Invalid live observation sequence')
        f.require_ready(public)
        updated = counts(list(native_counts), self.counts)
        require(updated[:2] == self.counts[:2], 'Unrecorded native actions')
        self.counts = updated
        self.observed = True
        self.current = public
        self._write(dict(record='observation', public=f.to_dict(public), counts=self.counts))

    def action(self, candidate, execution, native_counts):
        require(self.current is not None and candidate in self.current.candidates, 'Unadvertised recorded action')
        report = c.from_dict(c.to_dict(execution))
        require(type(report) is c.ExecutionReport and report.status in ('pending', 'rejected', 'uncertain'), 'Invalid live execution report')
        updated = counts(list(native_counts), self.counts)
        if report.status != 'uncertain':
            require(updated[0] == self.counts[0] + 1 if report.status == 'pending' else updated[0] in (self.counts[0], self.counts[0] + 1), 'Attempt count mismatch')
            require(updated[1] == self.counts[1] + int(report.status == 'pending'), 'Action count mismatch')
            require(updated[2] <= self.counts[1], 'Pending action already reconciled')
        else:
            self.uncertain = True
        self.counts = updated
        self._write(dict(record='action', action=candidate.ref, execution=c.to_dict(report), counts=self.counts))
        self.current = None

    def finish(self, outcome, native_counts):
        result = c.from_dict(c.to_dict(outcome))
        require(type(result) is c.RunOutcome, 'Missing live outcome')
        updated = counts(list(native_counts), self.counts)
        require(self.observed and not self.uncertain and updated[:2] == self.counts[:2], 'Unrecorded or uncertain native actions')
        self.counts = updated
        require(self.counts[1] == self.counts[2], 'Cannot publish unresolved native actions')
        if result.kind == 'truncated':
            require(result.reason == 'external_stop' and self.current is not None, 'Invalid live cutoff')
        self._write(dict(record='complete', outcome=c.to_dict(result), counts=self.counts, sha256=self.digest.hexdigest()))
        os.fsync(self.file.fileno())
        self.abort()
        os.link(self.partial, self.path)
        self.partial.unlink()
        return self.path

    def abort(self):
        if not self.closed:
            self.closed = True
            self.file.close()


@dataclass(frozen=True)
class LiveTrajectory:
    metadata: dict
    records: tuple[dict, ...]
    outcome: c.RunOutcome


def load_live_trajectory(path, *, split=None, release_sha256=None):
    path = Path(path)
    require(path.name.endswith(SUFFIX), 'Only published live journals can be loaded')
    digest, rows, current, previous = hashlib.sha256(), [], None, [0, 0, 0]
    with path.open('rb') as source:
        def parse(raw):
            try:
                return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
            except (ValueError, TypeError, RecursionError) as error:
                raise TrajectoryError('Invalid public live JSON') from error
        raw = source.readline()
        header = parse(raw)
        require(type(header) is dict and set(header) == {'record', 'schema', 'metadata'} and header['record'] == 'header' and header['schema'] == SCHEMA, 'Invalid live header')
        meta = metadata(header['metadata'])
        require(split is None or meta['split'] == split, 'Live split mismatch')
        require(release_sha256 is None or meta['release_sha256'] == release_sha256, 'Live release mismatch')
        digest.update(raw)
        for raw in source:
            row = parse(raw)
            require(type(row) is dict, 'Invalid live record')
            kind = row.get('record')
            expected = {'observation': {'record', 'public', 'counts'}, 'action': {'record', 'action', 'execution', 'counts'}, 'complete': {'record', 'outcome', 'counts', 'sha256'}}
            require(kind in expected and set(row) == expected[kind], 'Unexpected live fields')
            new_counts = counts(row['counts'], previous)
            if kind == 'observation':
                require(current is None and new_counts[:2] == previous[:2], 'Unrecorded native actions')
                current = f.from_dict(row['public'])
                require(type(current) is f.PublicDecision, 'Invalid live public decision')
                f.require_ready(current)
            elif kind == 'action':
                require(current is not None and row['action'] in {a.ref for a in current.candidates}, 'Unadvertised live action')
                report = c.from_dict(row['execution'])
                require(type(report) is c.ExecutionReport and report.status in ('pending', 'rejected'), 'Uncertain journal cannot be complete')
                require(new_counts[0] == previous[0] + 1 if report.status == 'pending' else new_counts[0] in (previous[0], previous[0] + 1), 'Attempt count mismatch')
                require(new_counts[1] == previous[1] + int(report.status == 'pending'), 'Action count mismatch')
                require(new_counts[2] <= previous[1], 'Pending action already reconciled')
                current = None
            else:
                require(rows and row['sha256'] == digest.hexdigest() and new_counts[:2] == previous[:2] and new_counts[1] == new_counts[2] and not source.read(1), 'Incomplete or corrupt live journal')
                result = c.from_dict(row['outcome'])
                require(type(result) is c.RunOutcome and (result.kind != 'truncated' or result.reason == 'external_stop' and current is not None), 'Invalid live ending')
                return LiveTrajectory(meta, tuple(rows), result)
            rows.append(row)
            previous = new_counts
            digest.update(raw)
    raise TrajectoryError('Incomplete live journal')
