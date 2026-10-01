"""Portable, compressed analysis exports; canonical inputs are never modified."""
from collections import Counter
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import hashlib
from importlib.resources import files as resource_files
from pathlib import Path
import time

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.contracts.codec import _wire
from game.agent.progress import completed_act
from game.agent.recording import SUFFIX, load_trajectory
from game.agent.trace_storage import open_trajectory
from game.agent.training.rewards import strict_json
from .decisions import json_bytes, state_digest, summarize
from .sources import collect_metadata, discover, identity, validate_overlay

SCHEMA = 'sts_analysis_report_v1'
CHUNK_SIZE = 16


def _export_episode(job):
    path, key, annotated, overlay, goal, output = job
    started = time.perf_counter()
    trajectory = load_trajectory(path, expected={'episode_id': key})
    loaded = time.perf_counter()
    pair = signature = None
    data = summarize(trajectory)
    episode_goal = annotated['goal'] if annotated else overlay['spec'].episode_goal if overlay else goal
    if goal is not None and episode_goal != goal:
        raise ValueError('Requested goal conflicts with recorded task goal')
    if episode_goal == 'act1' and (type(trajectory.initial) is not f.PublicDecision
            or trajectory.initial.run.get('act') != 1 or completed_act(trajectory.initial) is not None):
        raise ValueError('Act 1 analysis requires an unfinished Act 1 start')
    act1 = any(item['act'] == 1 for item in data['completed_acts'])
    if episode_goal == 'act1' and act1:
        final = trajectory.transitions[-1].successor
        if (completed_act(final) != 1 or trajectory.outcome.kind != 'truncated'
                or trajectory.outcome.reason != 'external_stop'):
            raise ValueError('An Act 1 task must stop at the public Act 1 completion boundary')
    success = act1 if episode_goal == 'act1' else trajectory.outcome.kind == 'victory' if episode_goal == 'full_run' else None
    status = ('success' if success else 'cutoff' if trajectory.outcome.kind == 'truncated'
              else trajectory.outcome.kind)
    if annotated:
        if (annotated['sha256'] != trajectory.sha256 or annotated['steps'] != len(trajectory.transitions)
                or annotated['policy_identity'] != trajectory.metadata.policy
                or annotated['outcome'] != c.to_dict(trajectory.outcome)
                or episode_goal == 'act1' and annotated['act1_cleared'] != act1
                or annotated['reported_status'] != ('truncated' if status == 'cutoff' else 'terminated')):
            raise ValueError('Evaluation metadata disagrees with public trajectory')
        pair = (annotated['case_id'], episode_goal, trajectory.metadata.split, trajectory.metadata.evidence)
        signature = (state_digest(trajectory.initial), trajectory.metadata.build, trajectory.metadata.rules)
    summarized = time.perf_counter()
    diagnostics = validate_overlay(trajectory, overlay) if overlay else []
    validated = time.perf_counter()
    label = annotated['policy'] if annotated else overlay['policy'] if overlay else path.parent.name
    row = {'id': key, 'source': path.name, 'sha256': trajectory.sha256, 'policy': label,
           'metadata': asdict(trajectory.metadata), 'goal': episode_goal, 'status': status,
           'task_success': success, 'act1_cleared': act1, 'outcome': c.to_dict(trajectory.outcome),
           'steps': len(trajectory.transitions), 'canonical_return': sum(t.reward for t in trajectory.transitions),
           'case_id': annotated['case_id'] if annotated else None, 'chunks': [], **data,
           'training': None}
    if overlay:
        components = Counter()
        for item in diagnostics:
            components.update(item['components'])
        row['training'] = {'source': overlay['source'], 'iteration': overlay['iteration'],
                           'collection_id': overlay['collection_id'],
                           'behavior': overlay['behavior'], 'reward_spec': overlay['spec'].to_dict(),
                           'reward_identity': overlay['spec'].identity,
                           'return': sum(item['reward'] for item in diagnostics), 'components': dict(components)}
    # The canonical loader has already validated the whole immutable graph.
    # Reuse its pure wire serializer without re-parsing every graph twice.
    current_wire = _wire(trajectory.initial)
    for offset in range(0, len(trajectory.transitions), CHUNK_SIZE):
        values = []
        for index in range(offset, min(offset+CHUNK_SIZE, len(trajectory.transitions))):
            transition = trajectory.transitions[index]
            next_wire = _wire(transition.successor)
            values.append({'step': index, 'observation': current_wire,
                           'action': asdict(transition.action), 'execution': c.to_dict(transition.execution),
                           'successor': next_wire, 'canonical_reward': transition.reward,
                           'training': diagnostics[index] if overlay else None})
            current_wire = next_wire
            if overlay:
                row['timeline'][index]['training_reward'] = diagnostics[index]['reward']
        compressed = gzip.compress(json_bytes(values), compresslevel=6, mtime=0)
        chunk = len(row['chunks'])
        (output/'decisions'/f'{key}-{chunk}.json.gz').write_bytes(compressed)
        row['chunks'].append(hashlib.sha256(compressed).hexdigest())
    return row, pair, signature, {'load_validate': loaded-started,
        'summarize': summarized-loaded, 'validate_overlay': validated-summarized,
        'encode_compress_write': time.perf_counter()-validated}


def build_report(inputs, output_dir, *, title='Act 1 · Decision lab', goal=None, progress=None, workers=1):
    if goal not in (None, 'act1', 'full_run'):
        raise ValueError('Choose act1 or full_run; omit the goal for unlabelled recordings')
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError('Analysis workers must be between 1 and 8')
    started = time.perf_counter()
    paths = discover(inputs)
    trajectories = [p for p in paths if p.name.endswith(SUFFIX)]
    if not trajectories:
        raise ValueError('No completed public trajectories found')
    annotations, overlays, jobs, pending, sources = collect_metadata(paths)
    output = Path(output_dir).absolute()
    # Reserve identities before any worker writes a chunk. Filenames need not
    # equal episode IDs; each worker rechecks its reservation in the full loader.
    jobs_to_export, reserved = [], set()
    for path in trajectories:
        with open_trajectory(path) as source:
            key = identity(strict_json(source.readline().decode('utf-8'))['metadata']['episode_id'])
        if key in reserved:
            raise ValueError('Duplicate trajectory episode identity')
        reserved.add(key)
        jobs_to_export.append((path, key, annotations.get(key), overlays.get(key), goal, output))
    prepared = time.perf_counter()
    # A failed export remains visibly incomplete; it never replaces a report.
    output.mkdir(parents=True, exist_ok=False)
    (output/'decisions').mkdir()
    report = {'schema': SCHEMA, 'title': title, 'created_at': datetime.now(timezone.utc).isoformat(),
              'chunk_size': CHUNK_SIZE, 'runs': [], 'training': jobs, 'pending': pending,
              'sources': sources, 'limitations': [
                  'Public recording playback, not an engine re-simulation.',
                  'Review flags describe behavior; they do not prove a strategic mistake.',
                  'Net HP change includes healing. Terminal HUD values are unavailable without a measurement.',
                  'Checkpoint preferences are recomputed on the displayed state. Critic values predict shaped return, not Act 1 clear probability.',
                  'Training and evaluation, evidence kinds, objectives and source identities must be compared separately.']}
    seen, paired_starts, paired_policies = set(), {}, {}
    worker_seconds = Counter()
    ordered = {}
    if workers == 1:
        results = ((index, _export_episode(job)) for index, job in enumerate(jobs_to_export))
    else:
        from .parallel import map_episodes
        results = map_episodes(_export_episode, jobs_to_export, workers)
    with closing(results):
        for index, (row, pair, signature, timings) in results:
            key = row['id']
            seen.add(key)
            if pair is not None:
                if pair in paired_starts and paired_starts[pair] != signature:
                    raise ValueError('Paired evaluation cases do not share the same public initial state and sources')
                paired_starts[pair] = signature
                paired_policies.setdefault(pair, set()).add(row['metadata']['policy'])
            ordered[index] = row
            worker_seconds.update(timings)
            if progress:
                progress(len(ordered), len(trajectories), row)
    report['runs'] = [ordered[index] for index in range(len(trajectories))]
    exported = time.perf_counter()
    missing = (set(annotations) | set(overlays))-seen
    if missing:
        raise ValueError(f'{len(missing)} declared completed episodes are missing; include their public trajectory directories')
    by_id = {row['id']: row for row in report['runs']}
    for job in jobs:
        count = 0
        for iteration in job['iterations']:
            runs = [by_id[key] for key in sorted(iteration.pop('episodes')) if key in by_id]
            count += sum(r['steps'] for r in runs)
            iteration.update(decisions=count, episodes=len(runs), clears=sum(r['act1_cleared'] for r in runs),
                             cutoffs=sum(r['status']=='cutoff' for r in runs),
                             mean_return=sum(r['training']['return'] for r in runs)/len(runs) if runs else None)
    report['paired_cases_verified'] = sum(len(policies) > 1 for policies in paired_policies.values())
    report['export'] = {'workers_requested': workers, 'workers_used': min(workers, len(trajectories)),
                        'metadata_seconds': prepared-started, 'episodes_wall_seconds': exported-prepared,
                        'episode_phase_seconds_sum': dict(worker_seconds),
                        'timing_scope': 'Episode phases sum worker wall time and may exceed elapsed wall time.'}
    for filename in ('index.html', 'app.js', 'style.css'):
        (output/filename).write_bytes(resource_files('game.agent.analysis').joinpath('assets', filename).read_bytes())
    report['build_seconds'] = time.perf_counter()-started
    partial = output/'report.json.partial'
    partial.write_bytes(json_bytes(report))
    partial.rename(output/'report.json')
    return report
