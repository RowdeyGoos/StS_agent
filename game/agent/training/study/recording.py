"""Public history supplements bound to canonical trajectories, not game saves."""
import gzip
import json
import hashlib
from pathlib import Path
from .history import PublicHistory

SUFFIX = '.public-history.json.gz'


def write_history(output, episode, sha, records):
    from ..benchmark_suite import data
    from ..checkpoint import publish
    return publish(Path(output)/(episode+SUFFIX), gzip.compress(data(dict(
        schema='sts_recorded_public_history_v1', trajectory_sha256=sha, records=records)), mtime=0))


def read_history(path, trajectory, expected_sha=None):
    if expected_sha is not None and hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected_sha:
        raise ValueError('Published public history supplement changed')
    with gzip.open(path, 'rb') as stream:
        raw = stream.read(16*1024*1024+1)
    if len(raw) > 16*1024*1024:
        raise ValueError('Oversized public history supplement')
    value = json.loads(raw)
    if (value.get('schema') != 'sts_recorded_public_history_v1'
            or value['trajectory_sha256'] != trajectory.sha256
            or len(value['records']) != len(trajectory.transitions)):
        raise ValueError('History supplement differs from its public trajectory')
    public = trajectory.initial
    for record, transition in zip(value['records'], trajectory.transitions):
        PublicHistory().restore(record, public)
        public = transition.successor
    return value['records']


def collect_history(files):
    """Bind only independently discovered public files, never follow paths."""
    files, bindings = set(files), {}
    from game.agent.analysis.sources import read_json
    for path in sorted(files):
        if path.name not in ('ppo.json', 'evaluation.json'):
            continue
        report = read_json(path)
        if report.get('schema') == 'sts_ppo_report_v1':
            rows = [e for i in report['iterations'] for e in i.get('collection', {}).get('episodes', ())]
        elif report.get('schema') == 'sts_feature_study_evaluation_v1':
            rows = report['episodes']
        else:
            continue
        for row in rows:
            if 'public_history_sha256' not in row:
                continue
            episode = row['episode_id']
            from game.agent.analysis.sources import identity
            identity(episode)
            supplement = path.parent/(episode+SUFFIX)
            if supplement not in files:
                raise ValueError('Include the recorded public history supplement')
            if supplement in bindings and bindings[supplement] != row['public_history_sha256']:
                raise ValueError('Conflicting history supplement bindings')
            bindings[supplement] = row['public_history_sha256']
    return bindings
