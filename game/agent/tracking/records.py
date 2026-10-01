"""Read public experiment records without restoring an engine or unpickling a model."""
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import zipfile

REPORT_NAMES = {'ppo.json', 'imitation.json', 'combat-benchmark.json', 'benchmark.json',
                'act1.json', 'full-run.json', 'baseline.json', 'evaluation.json',
                'diagnosis.json', 'tiny.json', 'smoke.json', 'hybrid.json'}
EVALUATION_SCHEMAS = {'sts_combat_corpus_comparison_v1', 'sts_combat_corpus_comparison_v2',
                      'sts_combat_comparison_v1', 'sts_act1_evaluation_v1',
                      'sts_full_run_evaluation_v1', 'sts_act1_pilot_panel_v1',
                      'sts_combat_baseline_v1', 'sts_combat_baseline_v2', 'sts_hybrid_campaign_v1',
                      'sts_training_readiness_campaigns_v1'}


def data(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))+'\n').encode()


def identity(value):
    return hashlib.sha256(data(value)).hexdigest()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def public_path(path):
    path = Path(path).absolute()
    parts = path.parts
    if parts[:3] in (('/', 'private', 'tmp'), ('/', 'private', 'var')):
        parts = parts[2:]
    return (not any(p.startswith('.') or p.lower() in ('private', 'audit', 'audits')
                    or p.lower().endswith('-private') for p in parts)
            and not any(p.is_symlink() for p in (path, *path.parents)))


def read_json(path):
    path = Path(path)
    if not public_path(path) or path.stat().st_size > 64*1024*1024:
        raise ValueError('Expected compact public metadata without symlinks')
    def invalid(value):
        raise ValueError('Non-finite JSON: '+value)
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    result = json.loads(path.read_bytes(), parse_constant=invalid, object_pairs_hook=unique)
    if not isinstance(result, dict):
        raise ValueError('Expected a report object')
    return result


def discover(inputs, *, exclude=None):
    """Only named public reports; never walk private audits or follow report paths."""
    found = set()
    excluded = Path(exclude).resolve() if exclude else None
    for item in inputs:
        path = Path(item).absolute()
        if not public_path(path) or not path.exists():
            raise ValueError('Inputs must be existing public paths without symlinks')
        if path.is_file():
            found.add(path)
            continue
        for root, directories, names in os.walk(path, followlinks=False):
            directories[:] = sorted(n for n in directories if public_path(Path(root)/n)
                                    and (excluded is None or (Path(root)/n).resolve() != excluded))
            for name in sorted(REPORT_NAMES.intersection(names)):
                candidate = Path(root)/name
                if public_path(candidate):
                    found.add(candidate)
    return sorted(found)


def bundle(path, expected):
    """Verify bytes, inspect bounded JSON only. weights.pt is never deserialized."""
    path = Path(path)
    if not public_path(path) or path.suffix != '.sts-model' or not re.fullmatch('[0-9a-f]{64}', expected or ''):
        raise ValueError('Invalid public checkpoint binding')
    if path.stat().st_size > 128*1024*1024:
        raise ValueError('Oversized checkpoint bundle')
    if digest(path) != expected:
        raise ValueError('Checkpoint digest differs from its report: '+str(path))
    try:
        with zipfile.ZipFile(path) as archive:
            entry = archive.getinfo('manifest.json')
            if entry.file_size > 4*1024*1024 or archive.namelist().count('manifest.json') != 1:
                raise ValueError('Oversized or ambiguous checkpoint manifest')
            result = json.loads(archive.read(entry))
    except zipfile.BadZipFile as error:
        raise ValueError('Invalid checkpoint archive') from error
    if result.get('schema') not in ('sts_inference_bundle_v1', 'sts_inference_bundle_v2', 'sts_inference_bundle_v3'):
        raise ValueError('Unsupported checkpoint manifest')
    return result


def numbers(value, prefix=''):
    result = {}
    if not isinstance(value, dict):
        return result
    for key, item in value.items():
        name = prefix+re.sub(r'[^\w./ -]', '_', str(key))
        if isinstance(item, dict):
            result.update(numbers(item, name+'/'))
        elif isinstance(item, (int, float)) and math.isfinite(item):
            result[name] = float(item)
    return result


def params(value, prefix=''):
    result = {}
    for key, item in value.items():
        name = prefix+str(key)
        if isinstance(item, dict):
            result.update(params(item, name+'.'))
        elif item is not None:
            result[name] = (json.dumps(item, sort_keys=True) if isinstance(item, (list, tuple)) else str(item))[:500]
    return result


def outcome(row, goal):
    if goal == 'act1':
        return 'victory' if row.get('act1_cleared') is True else (row.get('outcome') or {}).get('kind')
    if goal == 'full_run':
        return (row.get('outcome') or row.get('run_outcome') or {}).get('kind')
    return (row.get('combat') or {}).get('outcome')


def episode_metrics(rows, goal='combat', *, planned=None):
    count = len(rows) if planned is None else planned
    if count < len(rows):
        raise ValueError('Reported episodes exceed planned evaluation population')
    wins = [r for r in rows if r.get('status') == 'terminated' and outcome(r, goal) == 'victory']
    metrics = {'planned': count, 'wins': len(wins),
               'losses': sum(r.get('status') == 'terminated' and outcome(r, goal) == 'defeat' for r in rows),
               'cutoffs': sum(r.get('status') == 'truncated' for r in rows),
               'failures': sum(r.get('status') in ('failed', 'interrupted') for r in rows),
               'unattempted': count-len(rows)+sum(r.get('status') == 'unattempted' for r in rows),
               'decisions': sum(r.get('steps', 0) for r in rows),
               'potion_use_actions': sum(r.get('potion_use_actions', 0) for r in rows)}
    if count:
        metrics['act1_clear_rate' if goal == 'act1' else 'win_rate'] = len(wins)/count
        if rows and all('task_return' in row for row in rows):
            metrics['mean_task_return'] = sum(row['task_return'] for row in rows)/count
    hp = [r.get('end_hp', (r.get('combat') or {}).get('hp')) for r in wins]
    hp = [v for v in hp if isinstance(v, (int, float))]
    if hp:
        metrics['mean_hp_on_win'] = sum(hp)/len(hp)
    return metrics


def training_points(report):
    """Return counters and measured durations; no invented historical timestamps."""
    step = report.get('start_decisions', report.get('start_update', 0))
    elapsed = 0.
    trained = 0
    goal = report.get('experiment', {}).get('training', {}).get('mode', 'combat')
    reward = report.get('experiment', {}).get('training', {}).get('reward', {})
    if reward.get('goal') == 'act1':
        goal = 'act1'
    for entry in report.get('iterations', []):
        collection, update = entry.get('collection', {}), entry.get('update', {})
        # Processed includes deliberately skipped updates; accepted rollouts with
        # a failed update must not be passed off as trained decisions.
        step += update.get('decisions', 0)
        trained += update.get('decisions', 0) if update.get('status') == 'updated' else 0
        elapsed += collection.get('seconds', 0.)+update.get('seconds', 0.)
        metrics = {'train/processed_decisions': step, 'train/segment_trained_decisions': trained,
                   'train/rollout_iteration': entry['iteration'],
                   'system/collection_seconds': collection.get('seconds', 0.),
                   'system/update_seconds': update.get('seconds', 0.),
                   'system/collection_decisions_per_second': collection.get('decisions_per_second', 0.),
                   'system/worker_spawn_seconds': collection.get('spawn_seconds', 0.)}
        metrics.update(numbers(episode_metrics(collection.get('episodes', []), goal), 'train/'))
        metrics.update(numbers(collection.get('components', {}), 'train/reward_components/'))
        metrics.update(numbers(update.get('mean_update', {}), 'ppo/'))
        metrics.update(numbers({k: update[k] for k in ('optimizer_steps_total', 'max_gradient_norm',
            'kl_early_stop', 'packed_rollout_bytes', 'batch_input_tensor_bytes') if k in update}, 'ppo/'))
        yield step, elapsed, metrics
    for entry in report.get('updates', []):
        step = entry.get('update', entry.get('updates', step+1))
        yield step, None, numbers(entry, 'imitation/')


def prepare_evaluation(path, report):
    """Explicit adapters for historical panels, using bounded sibling plans."""
    if report.get('schema') == 'sts_training_readiness_campaigns_v1':
        plan_path = path.with_name(path.stem+'-plan.json')
        plan = read_json(plan_path)
        protocol_path = path.with_name('protocol.json')
        protocol = read_json(protocol_path)
        if digest(plan_path) != report.get('plan_sha256') or digest(protocol_path) != plan.get('protocol_sha256'):
            raise ValueError('Readiness evaluation plan/protocol digest mismatch')
        planned = {row['episode_id']: row for row in plan['episodes']}
        if (len(planned) != len(plan['episodes']) or
                {row['episode_id'] for row in report['episodes']} != set(planned)):
            raise ValueError('Readiness evaluation population differs from plan')
        for row in report['episodes']:
            if any(row.get(k) != planned[row['episode_id']].get(k) for k in ('policy', 'case_id', 'source_group', 'first_act')):
                raise ValueError('Readiness evaluation row differs from plan')
        return {**report, 'goal': 'full_run', 'split': protocol['split'],
            'policies': {name: value['identity'] for name, value in plan['models'].items()},
            'implementation': protocol.get('implementation'), 'protocol_sha256': plan['protocol_sha256'],
            'limits': protocol['limits'], 'total_seconds': report.get('seconds'),
            'episodes': [{**row, 'potion_use_actions': row.get('actions', {}).get('use_potion', 0)}
                         for row in report['episodes']]}
    if path.name not in ('diagnosis.json', 'tiny.json', 'smoke.json') or report.get('schema'):
        return report
    plan_path = path.with_name(path.stem+'-plan.json')
    plan = read_json(plan_path)
    if digest(plan_path) != report.get('stage_sha256'):
        raise ValueError('Diagnostic plan digest mismatch')
    jobs = {r['episode_id']: r for r in plan['jobs']}
    if len(jobs) != len(plan['jobs']) or {r['episode_id'] for r in report['episodes']} != set(jobs):
        raise ValueError('Diagnostic episode set differs from plan')
    for row in report['episodes']:
        if any(row.get(k) != jobs[row['episode_id']].get(k) for k in ('case_id', 'model', 'mode', 'repeat', 'split', 'panel')):
            raise ValueError('Diagnostic episode differs from plan')
    return {**report, 'schema': 'sts_tracking_diagnostic_v1', 'policies': {
        name: 'checkpoint:'+value['sha256'] for name, value in plan['models'].items()},
        'total_seconds': report.get('seconds'), 'diagnostic_plan': plan}


def evaluations(report):
    """Population keys exclude the model, but include cases, repeats and limits."""
    schema = report.get('schema', '')
    if schema not in EVALUATION_SCHEMAS | {'sts_tracking_diagnostic_v1'}:
        raise ValueError('Unsupported report schema: '+str(schema))
    goal = report.get('goal', 'act1' if 'act1' in schema else
                      'full_run' if 'full_run' in schema or schema == 'sts_hybrid_campaign_v1' else 'combat')
    if schema == 'sts_hybrid_campaign_v1':
        report = {**report, 'policies': {'heuristic': report['implementation']['policy'],
            'hybrid': 'hybrid_v1:'+report['checkpoint'].split(':')[-1]+':'+report['implementation']['policy']},
            'episodes': [{**row, 'status': ('truncated' if (row.get('outcome') or {}).get('kind') == 'truncated'
                         else 'terminated') if row['status'] == 'complete' else row['status']}
                         for row in report['episodes']]}
    groups = defaultdict(list)
    for row in report.get('episodes', []):
        label = row.get('policy', row.get('model'))
        groups[(label, row.get('split', report.get('split', 'unknown')),
                row.get('mode', 'greedy' if label not in ('random', 'random_legal') else 'random'),
                row.get('panel', 'default'))].append(row)
    legacy = schema in ('sts_combat_baseline_v1', 'sts_combat_baseline_v2', 'sts_hybrid_campaign_v1')
    if legacy:
        for label in report.get('policies', {}):
            groups.setdefault((label, report.get('split', 'unknown'),
                'random' if label in ('random', 'random_legal') else 'greedy', 'default'), [])
    for (label, split, mode, panel), rows in sorted(groups.items()):
        population = {'goal': goal, 'split': split, 'mode': mode, 'panel': panel,
            'corpus': report.get('corpus', report.get('suite')),
            'implementation': report.get('implementation'), 'reward_spec': report.get('reward_spec'),
            'limits': report.get('limits'), 'start_kind': report.get('start_kind'),
            'protocol': report.get('protocol_sha256'),
            'cases': sorted([(r.get('case_id', r.get('pair_id', r.get('episode_id'))), r.get('repeat', 0),
                              r.get('public_state_sha256', r.get('start_sha256')), r.get('start_kind'))
                             for r in rows], key=lambda x: str(x))}
        # Custom diagnostics carry their frozen limits/source in the stage plan.
        if schema == 'sts_tracking_diagnostic_v1':
            plan = report['diagnostic_plan']
            population['diagnostic_protocol'] = plan.get('protocol_sha256')
            population['limits'] = plan.get('limits')
        planned = None
        if legacy:
            policies = report.get('policies', {})
            requested = report.get('requested_episodes')
            if not policies or type(requested) is not int or requested % len(policies):
                raise ValueError('Baseline planned denominator is unavailable')
            planned = requested//len(policies)
            # Old baseline reports do not publish unattempted case identities.
            # Do not merge their incomplete populations with another report.
            population['planned'] = planned
            population['legacy_baseline_report'] = identity(report)
        metrics = numbers(episode_metrics(rows, goal, planned=planned), 'eval/')
        # Incomplete legacy reports omit identities of unattempted cases. Do
        # not fabricate the per-encounter/category planned denominator.
        fields = () if legacy and planned > len(rows) else ('room_kind', 'encounter', 'start_kind', 'threat', 'hp_band')
        for field in fields:
            for category in sorted({str(r[field]) for r in rows if field in r}):
                metrics.update(numbers(episode_metrics([r for r in rows if str(r.get(field)) == category], goal),
                                       'eval/by_'+field+'/'+category+'/'))
        policy = (report.get('policies', {}).get(label) or '')
        if isinstance(policy, dict):
            policy = policy.get('identity', '')
        pieces = policy.split(':')
        checkpoint = ''
        if len(pieces) == 2 and pieces[0] in ('ppo_v1', 'imitation_v1', 'checkpoint'):
            checkpoint = pieces[1]
        elif len(pieces) >= 4 and pieces[0] == 'hybrid_v1':
            checkpoint = pieces[1]
            population['fixed_controller'] = ':'.join(pieces[2:])
        yield {'label': label, 'split': split, 'mode': mode, 'panel': panel, 'goal': goal,
               'population': population, 'population_id': identity(population), 'metrics': metrics,
               'checkpoint': checkpoint, 'policy_identity': policy, 'episodes': rows}
