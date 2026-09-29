"""Discover public artifacts without following report paths or private trees."""
from collections import defaultdict
from dataclasses import asdict
import hashlib
import math
import os
from pathlib import Path
import re

from game.agent import contracts as c
from game.agent.action_policy import ALL_LEGAL, action_mask
from game.agent.contracts import full as f
from game.agent.progress import completed_act
from game.agent.recording import SUFFIX
from game.agent.training.ppo_config import PPOExperiment
from game.agent.training.rewards import (ACT_RUN_SCHEMA, SHAPED_RUN_SCHEMAS, finite,
                                        measure_act_run, measure_full_run, measure_run, strict_json)

REPORT_NAMES = {'ppo.json', 'baseline.json', 'evaluation.json', 'act1.json', 'full-run.json'}
PLAN_NAMES = {name.replace('.json', '-plan.json') for name in REPORT_NAMES if name != 'ppo.json'}
PANEL_SCHEMAS = {'sts_act1_pilot_panel_v1', 'sts_act1_evaluation_v1', 'sts_full_run_evaluation_v1'}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024*1024), b''):
            result.update(chunk)
    return result.hexdigest()


def public_path(path):
    parts = Path(path).parts
    # macOS resolves /tmp and /var through the system /private volume.
    if parts[:3] in (('/', 'private', 'tmp'), ('/', 'private', 'var')):
        parts = parts[2:]
    return not any(part.startswith('.') or part.lower() in ('private', 'audit', 'audits')
                   or part.lower().endswith('-private') for part in parts)


def discover(inputs):
    files = set()
    for value in inputs:
        path = Path(value).absolute()
        if not path.exists() or not public_path(path) or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Inputs must be existing public paths without symlinks or private directories')
        if path.is_file():
            candidates = [path]
        else:
            candidates = []
            for root, directories, names in os.walk(path, followlinks=False):
                directories[:] = sorted(n for n in directories if public_path(n)
                                        and not (Path(root)/n).is_symlink())
                candidates.extend(Path(root)/n for n in sorted(names))
        for item in candidates:
            if item.is_symlink() or not public_path(item):
                continue
            if (item.name.endswith(SUFFIX) or item.name in REPORT_NAMES | PLAN_NAMES or
                    re.fullmatch(r'rollout-\d{5}\.json', item.name)):
                files.add(item)
    return sorted(files)


def read_json(path):
    # Training/panel metadata is compact. Trajectories use their streaming loader.
    if path.stat().st_size > 64*1024*1024:
        raise ValueError('Oversized analysis metadata')
    result = strict_json(path.read_text(encoding='utf-8'))
    if type(result) is not dict:
        raise ValueError('Expected an artifact object')
    return result


def text(value, field):
    if type(value) is not str or not 0 < len(value) <= 256:
        raise ValueError('Invalid '+field)
    return value


def identity(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{32}', value) is None:
        raise ValueError('Invalid episode/case identity')
    return value


def collect_metadata(files):
    """Sidecars are opened only when discovered independently in explicit roots."""
    file_set, annotations, overlays, jobs, pending = set(files), {}, {}, [], []
    sources = []
    for path in files:
        if path.name not in REPORT_NAMES:
            continue
        report = read_json(path)
        schema = report.get('schema')
        if schema not in PANEL_SCHEMAS and schema != 'sts_ppo_report_v1':
            continue
        source = {'name': path.name, 'sha256': digest(path)}
        sources.append(source)
        if schema in PANEL_SCHEMAS:
            plan_path = path.with_name(path.stem+'-plan.json')
            if plan_path not in file_set or digest(plan_path) != report['plan_sha256']:
                raise ValueError('Missing or changed evaluation plan; include its public directory')
            plan = read_json(plan_path)
            policies = ({key: value['identity'] for key, value in plan['models'].items()}
                        if schema == 'sts_act1_pilot_panel_v1' else plan['policies'])
            if schema != 'sts_act1_pilot_panel_v1' and (report['policies'] != policies
                    or report['reward_spec'] != plan['reward_spec'] or plan.get('schema') != schema
                    or report.get('goal', 'full_run') != plan.get('goal', 'full_run')):
                raise ValueError('Evaluation policy/objective differs from plan')
            planned = {identity(row['episode_id']): row for row in plan['episodes']}
            if (len(planned) != len(plan['episodes']) or len(report['episodes']) != len(planned)
                    or {row['episode_id'] for row in report['episodes']} != set(planned)):
                raise ValueError('Evaluation report changed its planned episode set')
            for row in report['episodes']:
                key = identity(row['episode_id'])
                if any(row[k] != planned[key][k] for k in ('case_id', 'source_group', 'policy', 'first_act')):
                    raise ValueError('Evaluation case differs from plan')
                goal = row.get('goal', report.get('goal', 'act1' if 'act1' in schema else 'full_run'))
                if goal != ('act1' if 'act1' in schema else 'full_run'):
                    raise ValueError('Panel goal differs from its schema')
                if planned[key].get('goal', goal) != goal:
                    raise ValueError('Episode goal differs from the evaluation plan')
                value = {'policy': text(row['policy'], 'policy label'), 'case_id': identity(row['case_id']),
                         'policy_identity': text(policies[row['policy']], 'policy identity'),
                         'goal': goal, 'reported_status': row['status'], 'source': source,
                         'plan_sha256': report['plan_sha256']}
                if goal not in ('act1', 'full_run'):
                    raise ValueError('Unsupported panel goal')
                if key in annotations:
                    raise ValueError('Duplicate evaluation episode')
                if row['status'] in ('terminated', 'truncated'):
                    value.update(sha256=row['trajectory_sha256'], steps=row['steps'],
                                 outcome=row['outcome'], act1_cleared=row.get('act1_cleared'))
                    annotations[key] = value
                elif row['status'] in ('failed', 'interrupted', 'unattempted'):
                    pending.append({'id': key, **value})
                else:
                    raise ValueError('Unsupported evaluation status')
            continue
        experiment = PPOExperiment.from_dict(report['experiment'])
        if experiment.identity != report['experiment_identity']:
            raise ValueError('PPO experiment identity mismatch')
        if experiment.training.mode != 'full_run':
            # Combat trajectories remain inspectable; their separate task sidecars
            # are not silently interpreted as full-run rewards.
            continue
        job = {'label': path.parent.name, 'source': source, 'status': report['status'],
               'reward_spec': experiment.training.reward.to_dict(), 'iterations': []}
        jobs.append(job)
        for iteration in report['iterations']:
            if 'rollout' not in iteration:
                continue
            filename = iteration['rollout']
            if type(filename) is not str or not re.fullmatch(r'rollout-\d{5}\.json', filename):
                raise ValueError('Invalid rollout filename')
            rollout_path = path.parent/filename
            if rollout_path not in file_set or digest(rollout_path) != iteration['rollout_sha256']:
                raise ValueError('Missing or changed public rollout')
            rollout = read_json(rollout_path)
            spec = experiment.training.reward
            expected_schema = ('sts_ppo_rollout_v4' if spec.schema == ACT_RUN_SCHEMA else
                               'sts_ppo_rollout_v3' if experiment.training.action_policy != ALL_LEGAL else
                               'sts_ppo_rollout_v2' if spec.schema in SHAPED_RUN_SCHEMAS else 'sts_ppo_rollout_v1')
            if (rollout['schema'] != expected_schema or rollout['experiment'] != experiment.identity
                    or rollout['iteration']+1 != iteration['iteration']
                    or rollout['episodes'] != iteration['collection']['episodes']
                    or rollout.get('action_policy', ALL_LEGAL) != experiment.training.action_policy
                    or spec.schema in SHAPED_RUN_SCHEMAS and rollout.get('reward_spec') != spec.to_dict()):
                raise ValueError('PPO rollout provenance mismatch')
            behavior = rollout['behavior']
            if type(behavior) is not str or not re.fullmatch(r'sts_policy_state_v[12]:[0-9a-f]{64}', behavior):
                raise ValueError('Invalid behavior fingerprint')
            by_episode = defaultdict(list)
            for step in rollout['steps']:
                by_episode[identity(step['episode_id'])].append(step)
            seen = set()
            for episode in rollout['episodes']:
                key = identity(episode['episode_id'])
                if key in seen or key in overlays or key in annotations:
                    raise ValueError('Duplicate training episode')
                seen.add(key)
                if 'trajectory_sha256' not in episode:
                    if by_episode.get(key):
                        raise ValueError('Training steps lack a published trajectory')
                    pending.append({'id': key, 'policy': job['label'], 'goal': spec.episode_goal,
                                    'reported_status': episode['status'], 'source': source})
                    continue
                overlays[key] = {'steps': by_episode.get(key, []), 'episode': episode,
                                 'behavior': behavior, 'spec': spec, 'experiment': experiment,
                                 'policy': job['label'], 'source': {'name': filename,
                                 'sha256': iteration['rollout_sha256']}, 'collection_id': source['sha256'],
                                 'iteration': iteration['iteration']}
            if set(by_episode)-seen:
                raise ValueError('Undeclared PPO episode')
            job['iterations'].append({'iteration': iteration['iteration'], 'episodes': list(seen),
                                      'update_status': iteration.get('update', {}).get('status', 'not_recorded')})
    return annotations, overlays, jobs, pending, sources


def validate_overlay(trajectory, overlay):
    """Bind learner diagnostics to exact states/actions and recompute public rewards.

    Chosen log-probabilities, values and GAE are recorded learner diagnostics;
    they are not re-labelled as independently reproduced inference.
    """
    episode, rows, spec = overlay['episode'], overlay['steps'], overlay['spec']
    expected_policy = 'ppo_v1:'+overlay['behavior'].split(':')[-1]
    if (episode['trajectory_sha256'] != trajectory.sha256 or trajectory.metadata.split != 'train'
            or trajectory.metadata.policy != expected_policy
            or len(rows) != len(trajectory.transitions) or episode['steps'] != len(rows)):
        raise ValueError('PPO trajectory identity/count mismatch')
    result = []
    previous_combat = None
    for index, (transition, row) in enumerate(zip(trajectory.transitions, rows)):
        refs = row['candidate_refs']
        allowed = dict(zip((a.ref for a in transition.observation.candidates),
                           action_mask(transition.observation, overlay['experiment'].training.action_policy)))
        if (row['episode_step'] != index or type(row['episode_step']) is not int
                or type(refs) is not list or len(refs) != len(allowed) or set(refs) != set(allowed)
                or type(row['action']) is not int or not 0 <= row['action'] < len(refs)
                or row['action_ref'] != transition.action.ref or refs[row['action']] != row['action_ref']
                or row['legal_mask'] != [True]*len(refs)
                or any(type(v) is not bool for v in row['legal_mask'])
                or row.get('policy_mask', [True]*len(refs)) != [allowed[ref] for ref in refs]
                or any(type(v) is not bool for v in row.get('policy_mask', []))
                or not allowed[row['action_ref']]):
            raise ValueError('PPO action/mask join mismatch')
        for key in ('value', 'next_value', 'old_log_probability', 'advantage', 'return', 'reward'):
            finite(row[key])
        if row['old_log_probability'] > 1e-6:
            raise ValueError('Invalid recorded action probability')
        done, cut = row['terminated'], row['truncated']
        if (type(done) is not bool or type(cut) is not bool or done and cut
                or index < len(rows)-1 and (done or cut) or done and row['next_value'] != 0):
            raise ValueError('Invalid PPO task boundary')
        if spec.schema in SHAPED_RUN_SCHEMAS:
            context = row['reward_context']
            before, after = context['before_combat'], context['after_combat']
            if index and before != previous_combat:
                raise ValueError('Discontinuous public combat measurements')
            previous_combat = after
            if spec.schema == ACT_RUN_SCHEMA:
                if context['before_act'] != completed_act(transition.observation):
                    raise ValueError('PPO act reward context mismatch')
                measured = measure_act_run(transition.action, transition.execution, transition.successor,
                                          before, after, context['before_act'])
            else:
                measured = measure_full_run(transition.action, transition.execution, transition.successor, before, after)
        else:
            measured = measure_run(transition.successor)
        if asdict(measured) != row['components'] or not math.isclose(spec.evaluate(measured), row['reward'], abs_tol=1e-12):
            raise ValueError('PPO reward measurement mismatch')
        terminal = (type(transition.successor) is c.RunOutcome and transition.successor.kind != 'truncated'
                    or spec.episode_goal == 'act1' and completed_act(transition.successor) == 1)
        if done != terminal:
            raise ValueError('PPO task outcome mismatch')
        result.append({key: row[key] for key in ('old_log_probability', 'value', 'next_value', 'reward',
                                                'components', 'terminated', 'truncated', 'advantage', 'return')})
        result[-1].update(chosen_probability=math.exp(row['old_log_probability']),
                          policy_mask=[allowed[a.ref] for a in transition.observation.candidates])
    if rows and not (rows[-1]['terminated'] or rows[-1]['truncated']):
        raise ValueError('Unclosed PPO episode')
    return result
