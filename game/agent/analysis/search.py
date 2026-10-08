"""Read recorded public search diagnostics; never construct or simulate a world.

The exporter deliberately retains only presentation fields. In particular, the
planning supplement and any unknown fields are not copied into the viewer.
"""
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re

from game.agent import contracts as c
from game.agent.input_views import RAW, DETACHED_HISTORY, validate_view
from game.agent.trace_storage import logical_path
from game.agent.training.rewards import RewardSpec, finite, strict_json
from .sources import digest, identity, read_json, text

REPORTS = ('sts_search_report_v1', 'sts_search_report_v2')
TARGETS = ('sts_search_targets_v1', 'sts_search_targets_v2')
SUFFIX = '.search.json.gz'
LIMIT = 64 * 1024 * 1024
OBJECTIVE = RewardSpec({'combat_win': 1., 'win_hp_fraction': .1})


def _sibling(files, directory, filename):
    if type(filename) is not str or Path(filename).name != filename:
        raise ValueError('Expected a sibling public search artifact')
    path = directory / filename
    key = logical_path(path) if filename.endswith(('.trajectory.jsonl', '.trajectory.jsonl.gz')) else path
    if key not in files:
        raise ValueError('Missing public search artifact; include its public directory')
    return key


def collect_search(files):
    """Join only independently discovered files, never follow a report path."""
    files = set(files)
    bindings, used, sources, pending = {}, set(), [], []
    for path in sorted(files):
        if path.name != 'search.json':
            continue
        report = read_json(path)
        if report.get('schema') not in REPORTS:
            raise ValueError('Unsupported search report')
        if report.get('purpose') not in ('collection', 'evaluation', 'reanalysis'):
            raise ValueError('Unsupported search report purpose')
        goal = report.get('goal')
        if goal not in (None, 'combat', 'act1', 'full_run'):
            raise ValueError('Unsupported search report goal')
        source = {'name': path.name, 'sha256': digest(path), 'kind': 'search_report',
                  'coverage': 'recorded_search_targets_only'}
        sources.append(source)
        seen = set()
        for row in report['episodes']:
            key = identity(row['episode_id'])
            if key in seen:
                raise ValueError('Duplicate search report episode')
            seen.add(key)
            if not row.get('targets'):
                if row.get('status') in ('failed', 'interrupted', 'unattempted'):
                    pending.append({'id': key, 'policy': text(row['policy'], 'search policy label'),
                                    'goal': goal, 'reported_status': row['status'], 'source': source})
                continue
            trajectory = _sibling(files, path.parent, row['trajectory'])
            targets = _sibling(files, path.parent, row['targets'])
            if not targets.name.endswith(SUFFIX) or trajectory in bindings or targets in used:
                raise ValueError('Ambiguous search target binding')
            bindings[trajectory] = {'path': targets, 'report': {
                'source': source, 'schema': report['schema'], 'purpose': report['purpose'],
                'episode_id': key, 'steps': _count(row['steps'], 'episode steps'), 'split': report['split'],
                'policy_label': text(row['policy'], 'search policy label'),
                'teacher': report['policies'][row['policy']],
                'behavior': row.get('behavior_policy', report['policies'][row['policy']]),
                'checkpoint': report['checkpoint'], 'search': report['search_configs'][row['policy']],
                'planning_view': report.get('planning_view', RAW),
                'reward_spec': report['reward_spec'], 'targets_sha256': row['targets_sha256'],
                'outcome': row['run_outcome']}}
            if report['schema'] == REPORTS[1] and 'planning_view' not in report:
                raise ValueError('Search report lacks its public input view')
            used.add(targets)
    for path in sorted(files):
        if not path.name.endswith(SUFFIX) or path in used:
            continue
        # A standalone sidecar is supported only beside its exact named trace.
        # Reanalysis needs its report to distinguish teacher from real behavior.
        key = identity(path.name[:-len(SUFFIX)])
        trajectory = _sibling(files, path.parent, key + '.trajectory.jsonl')
        if trajectory in bindings:
            raise ValueError('Ambiguous search target binding')
        bindings[trajectory] = {'path': path, 'report': None}
    return bindings, sources, pending


def _count(value, label, maximum=None):
    if type(value) is not int or value < 0 or maximum is not None and value > maximum:
        raise ValueError('Invalid recorded search ' + label)
    return value


def _config(value, view):
    """Validate recorded v1 settings without importing the simulator or Torch."""
    if type(value) is not dict:
        raise ValueError('Invalid recorded search config')
    counts = {'simulations': (1, 4096), 'considered_actions': (1, 256),
              'max_depth': (1, 512), 'seed': (0, 2**63-1),
              'belief_particles': (1, 256), 'belief_proposals': (1, 1000000),
              'belief_replay_proposals': (0, 1000000), 'belief_replay_steps': (0, 10000000),
              'leaf_rollout_steps': (0, 512)}
    known = set(counts) | {'time_limit', 'belief_seconds', 'method', 'model_version', 'exploration',
                           'q_scale', 'final_selection'}
    if set(value)-known:
        raise ValueError('Unsupported recorded search settings')
    for key in ('simulations', 'considered_actions', 'max_depth', 'seed'):
        if key not in value:
            raise ValueError('Missing recorded search setting: ' + key)
    for key, (low, high) in counts.items():
        if key in value and (_count(value[key], key, high) < low):
            raise ValueError('Invalid recorded search ' + key)
    for key in ('time_limit', 'belief_seconds'):
        if key in value and finite(value[key]) <= 0:
            raise ValueError('Invalid recorded search time limit')
    if not 0 < finite(value.get('q_scale', .1)) <= 100:
        raise ValueError('Invalid recorded search Q scale')
    if value.get('final_selection', 'prior_value') not in ('prior_value', 'max_value'):
        raise ValueError('Invalid recorded search final selection')
    if ('time_limit' not in value or value.get('method') not in ('gumbel', 'root')
            or type(value.get('exploration')) is not bool):
        raise ValueError('Invalid recorded search method/budget')
    model = value.get('model_version', 'reconstruction_v1')
    if model not in ('reconstruction_v1', 'public_belief_v1', 'direct_belief_v1', 'revealed_belief_v1'):
        raise ValueError('Unsupported recorded search model')
    if view != (DETACHED_HISTORY if model in ('direct_belief_v1', 'revealed_belief_v1') else RAW):
        raise ValueError('Search model and recorded public input view differ')
    return dict(value)


def _tree(value, refs, visits, simulations, config):
    if not value:
        return None  # Absence is not a measured zero in older recordings.
    if type(value) is not dict:
        raise ValueError('Invalid recorded search tree work')
    depths = value['depth_histogram']
    if (type(depths) is not dict or any(not re.fullmatch('[1-9][0-9]*', k)
            or int(k) > config['max_depth'] for k in depths)):
        raise ValueError('Invalid search depth histogram')
    result = {'depth_histogram': {k: _count(v, 'depth count') for k, v in depths.items()},
              'expansions': _count(value['expansions'], 'expansions'),
              'terminals': _count(value['terminals'], 'terminals'), 'root_rounds': []}
    previous_after, previous_ranked, previous_visits = 0, None, {}
    for row in value['root_rounds']:
        ranked = row['ranked']
        before = _count(row['simulations_before'], 'round start', simulations)
        after = _count(row['simulations_after'], 'round end', simulations)
        counts = row['visits']
        if (before != previous_after or after < before or type(ranked) is not list or not ranked
                or len(set(ranked)) != len(ranked) or not set(ranked) <= refs
                or type(counts) is not dict or set(counts) != set(ranked)
                or len(ranked) > min(config['considered_actions'], config['simulations'])):
            raise ValueError('Invalid search elimination round')
        if previous_ranked is not None:
            survivors = (previous_ranked[:max(2, len(previous_ranked)//2)]
                         if config['method'] == 'gumbel' else previous_ranked)
            if set(ranked) != set(survivors):
                raise ValueError('Search round survivor mapping changed')
        for ref, count in counts.items():
            if _count(count, 'round visits', visits[ref]) < previous_visits.get(ref, 0):
                raise ValueError('Search round visits went backwards')
        if sum(count - previous_visits.get(ref, 0) for ref, count in counts.items()) != after-before:
            raise ValueError('Search round visits do not match completed work')
        result['root_rounds'].append({'ranked': list(ranked), 'visits': dict(counts),
                                     'simulations_before': before, 'simulations_after': after})
        for field in ('values', 'scores'):
            if field in row:
                if type(row[field]) is not dict or set(row[field]) != set(ranked):
                    raise ValueError('Invalid search round ' + field)
                result['root_rounds'][-1][field] = {ref: finite(v) for ref, v in row[field].items()}
        previous_after, previous_ranked, previous_visits = after, ranked, counts
    if 'root_value' in value:
        result['root_value'] = finite(value['root_value'])
    if 'root_evidence' in value:
        evidence = value['root_evidence']
        if type(evidence) is not dict or set(evidence) != refs:
            raise ValueError('Invalid search root evidence mapping')
        result['root_evidence'] = {}
        for ref, entry in evidence.items():
            counts = {k: _count(entry[k], k, visits[ref])
                      for k in ('tree_terminals', 'leaf_terminals', 'critic_bootstraps')}
            prior, squares = finite(entry['prior']), finite(entry['value_sum_squares'])
            if sum(counts.values()) != visits[ref] or not 0 <= prior <= 1 or not 0 <= squares <= visits[ref] * 1.21 + 1e-8:
                raise ValueError('Invalid search root evidence values')
            result['root_evidence'][ref] = dict(counts, prior=prior, value_sum_squares=squares)
        if abs(sum(e['prior'] for e in result['root_evidence'].values()) - 1) > 1e-6:
            raise ValueError('Invalid search root evidence priors')
    return result


def validate_search(trajectory, binding):
    """Bind diagnostics to the canonical trajectory and export a small allowlist."""
    try:
        return _validate_search(trajectory, binding)
    except (KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError('Malformed public search diagnostics') from error


def _validate_search(trajectory, binding):
    path, report = binding['path'], binding['report']
    if any(p.is_symlink() for p in (path, *path.parents)) or path.stat().st_size > LIMIT:
        raise ValueError('Invalid public search sidecar')
    with path.open('rb') as stream:
        compressed = stream.read(LIMIT+1)
    if len(compressed) > LIMIT:
        raise ValueError('Oversized public search diagnostics')
    source = {'name': path.name, 'sha256': hashlib.sha256(compressed).hexdigest()}
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        content = stream.read(LIMIT + 1)
    if len(content) > LIMIT:
        raise ValueError('Oversized public search diagnostics')
    data = strict_json(content)
    if (data.get('schema') not in TARGETS or data['trajectory_sha256'] != trajectory.sha256
            or data['split'] != trajectory.metadata.split
            or len(data['targets']) != len(trajectory.transitions)):
        raise ValueError('Search targets do not match their public trajectory')
    view = validate_view(data.get('planning_view', RAW))
    if (data['schema'] == TARGETS[1] and 'planning_view' not in data
            or data['schema'] == TARGETS[0] and view != RAW):
        raise ValueError('Search targets lack their versioned public input view')
    config = _config(data['search'], view)
    objective = RewardSpec.from_dict(data['reward_spec'])
    if objective != OBJECTIVE:
        raise ValueError('Unsupported search reward objective')
    checkpoint = text(data['checkpoint'], 'search checkpoint identity')
    identity_config = dict(config)
    if not identity_config.get('leaf_rollout_steps'):
        identity_config.pop('leaf_rollout_steps', None)
    if identity_config.get('q_scale', .1) == .1:
        identity_config.pop('q_scale', None)
    if identity_config.get('final_selection', 'prior_value') == 'prior_value':
        identity_config.pop('final_selection', None)
    teacher = 'sts_combat_search_v1:' + hashlib.sha256(
        json.dumps([checkpoint, identity_config], sort_keys=True).encode()).hexdigest()
    if data['teacher'] != teacher:
        raise ValueError('Search teacher identity differs from checkpoint/settings')
    purpose = report['purpose'] if report else 'recorded_behavior'
    if report:
        if (report['targets_sha256'] != source['sha256']
                or report['episode_id'] != trajectory.metadata.episode_id
                or report['steps'] != len(trajectory.transitions)
                or report['outcome'] != c.to_dict(trajectory.outcome)
                or any(report[k] != data[k] for k in ('teacher', 'checkpoint', 'search', 'split', 'reward_spec'))
                or report['planning_view'] != view
                or report['behavior'] != trajectory.metadata.policy
                or purpose != 'reanalysis' and report['behavior'] != teacher):
            raise ValueError('Search report/sidecar/behavior binding mismatch')
    elif teacher != trajectory.metadata.policy:
        raise ValueError('Search teacher differs from behavior; reanalysis requires its public report')
    result = []
    for index, (row, transition) in enumerate(zip(data['targets'], trajectory.transitions)):
        refs = {a.ref for a in transition.observation.candidates}
        probabilities, values, visits = row['probabilities'], row['values'], row['visits']
        if (type(row['step']) is not int or row['step'] != index
                or any(type(x) is not dict for x in (probabilities, values, visits))
                or not probabilities or not set(probabilities) <= refs
                or set(probabilities) != set(values) or set(values) != set(visits)
                or row['action_ref'] not in probabilities
                or purpose != 'reanalysis' and row['action_ref'] != transition.action.ref):
            raise ValueError('Search target step/action/candidate mapping mismatch')
        if (any(not 0 <= finite(v) <= 1 for v in probabilities.values())
                or not math.isclose(sum(probabilities.values()), 1., abs_tol=1e-6)):
            raise ValueError('Search target probabilities are not normalized')
        if any(not -1e-9 <= finite(v) <= 1.1+1e-9 for v in values.values()):
            raise ValueError('Invalid completed search action values')
        simulations = _count(row['simulations'], 'simulations', config['simulations'])
        if sum(_count(v, 'visits', simulations) for v in visits.values()) != simulations:
            raise ValueError('Search visits do not match completed simulations')
        if finite(row['seconds']) < 0:
            raise ValueError('Invalid search elapsed time')
        reason, cutoff = row.get('reason'), row.get('cutoff')
        for label, value in (('fallback reason', reason), ('cutoff reason', cutoff)):
            if value is not None:
                text(value, label)
        if reason is None and simulations == 0:
            raise ValueError('Zero-work search must declare a fallback')
        if reason is None and cutoff is None and simulations != config['simulations']:
            raise ValueError('Incomplete search must declare a cutoff or fallback')
        timings = {k: finite(v) for k, v in row.get('timings', {}).items()
                   if k in ('conditioning', 'inference', 'projection', 'reconstruction', 'sampling', 'transition')}
        leaf = row.get('leaf_work')
        leaf = ({k: _count(leaf[k], 'leaf ' + k) for k in
                 ('steps', 'terminals', 'bootstraps', 'time_bootstraps')} if leaf else None)
        result.append({'action_ref': row['action_ref'], 'probabilities': dict(probabilities),
                       'values': dict(values), 'visits': dict(visits), 'simulations': simulations,
                       'seconds': row['seconds'], 'reason': reason, 'cutoff': cutoff,
                       'timings': timings, 'leaf_work': leaf,
                       'tree_work': _tree(row.get('tree_work'), set(probabilities), visits, simulations, config)})
    metadata = {'source': source, 'report': report['source'] if report else None,
                'schema': data['schema'], 'checkpoint': checkpoint, 'teacher': teacher,
                'config': config, 'planning_view': view, 'reward_spec': objective.to_dict(),
                'reward_identity': objective.identity, 'purpose': purpose,
                'policy_label': report['policy_label'] if report else None,
                'searched': sum(r['reason'] is None for r in result), 'decisions': len(result)}
    return metadata, result
