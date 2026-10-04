"""Metric-aware saved Runs views for the pinned MLflow 3.16 UI.

Only experiment tags are written. Templates retain exact metric names and native
steps; they never aggregate populations or change recorded results. The envelope
and chart fields are the format produced by MLflow's own Save view action.
"""
import base64
from dataclasses import dataclass
import hashlib
import json
import re
import time
import zlib


VIEW_PREFIX = 'mlflow.sharedViewState.'
MANAGED_TAG = 'sts.saved_view_templates.v1'


@dataclass(frozen=True)
class Chart:
    metric: str
    title: str
    kind: str = 'LINE'


@dataclass(frozen=True)
class View:
    slug: str
    name: str
    filter: str
    charts: tuple[Chart, ...]
    metrics: frozenset[str]
    params: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()


def _fingerprint(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _literal(value):
    # MLflow strips the delimiters but does not unescape the string contents.
    from mlflow.utils.search_utils import SearchUtils
    for quote in ("'", '"'):
        if quote not in value:
            literal = quote + value + quote
            try:
                parsed = SearchUtils.parse_search_filter('tags.value = ' + literal)
                if len(parsed) == 1 and parsed[0]['value'] == value:
                    return literal
            except Exception:
                pass
    raise ValueError('Benchmark label cannot be represented by an exact MLflow filter')


def _evaluation_chart(metric):
    """Recognize aggregate scores, not arbitrary encounter/bucket breakdowns."""
    fixed = re.fullmatch(
        r'evaluation/(train|validation|test)/(greedy|sampled)/([0-9a-f]{12})/'
        r'(win_rate|act1_clear_rate|mean_hp_on_win)', metric)
    if fixed:
        split, mode, population, score = fixed.groups()
        label = {'win_rate': 'win rate', 'act1_clear_rate': 'Act 1 clear rate',
                 'mean_hp_on_win': 'reported HP on wins ↑'}[score]
        return ('quality' if score == 'mean_hp_on_win' else 'performance',
                Chart(metric, f'{split.title()} · {mode} · population {population} · {label}'))

    # Historical experiment drivers used these explicit aggregate namespaces.
    # Keep every namespace distinct, even when their suffixes look similar.
    match = re.fullmatch(
        r'(combat|diagnostic)/(train|validation|test)/(greedy|sampled)/(.*)', metric)
    if match:
        family, split, mode, score = match.groups()
        context = f'{split.title()} · {mode}'
        if family == 'diagnostic':
            context += ' · additional decisions'
        if score == 'win_rate':
            return 'performance', Chart(metric, context + ' · win rate')
        if score == 'paired_to_parent/win_difference_pp':
            return 'performance', Chart(metric, context + ' · win-rate change vs parent (pp)')
        score = score.removeprefix('hp/')
        labels = {
            'mean_player_hp_on_win': 'player HP on wins · before healing ↑',
            'mean_boss_hp_on_loss': 'boss HP on losses ↓',
            'paired_to_initial/both_won/player_hp_change': 'HP change · shared wins vs initial ↑',
            'paired_to_initial/both_lost/boss_hp_change': 'boss HP change · shared losses vs initial ↓',
            'paired_to_parent/mean_player_hp_change_both_won': 'HP change · shared wins vs parent ↑',
            'paired_to_parent/mean_boss_hp_change_both_lost': 'boss HP change · shared losses vs parent ↓',
            'paired_to_parent/paired_player_hp_on_same_wins/delta': 'HP change · shared wins vs parent ↑',
            'paired_to_parent/paired_boss_hp_on_same_losses/delta': 'boss HP change · shared losses vs parent ↓',
        }
        if score in labels:
            return 'quality', Chart(metric, context + ' · ' + labels[score])

    match = re.fullmatch(r'(eval|research/original_validation|research/fresh_validation)/'
                         r'(greedy|sampled)/win_rate', metric)
    if match:
        source, mode = match.groups()
        label = 'Fresh' if source.endswith('fresh_validation') else 'Original'
        return 'performance', Chart(metric, f'{label} validation · {mode} · win rate')
    return None


def templates(runs):
    """Build only views supported by currently recorded metrics, on any experiment ID."""
    result = []
    learners = [r for r in runs if r.data.tags.get('sts.kind') == 'ppo'
                and 'sts.benchmark' not in r.data.tags]
    metrics = frozenset(k for r in learners for k in r.data.metrics)
    filter_string = "tags.sts.kind = 'ppo' AND tags.sts.benchmark IS NULL"

    def add(slug, name, charts, *, aliases=(), params=()):
        selected = tuple(c for c in charts if c.metric in metrics)
        if selected:
            result.append(View(slug, name, filter_string, selected, metrics, params, aliases))

    performance, quality = [], []
    for metric in sorted(metrics):
        recognized = _evaluation_chart(metric)
        if recognized:
            group, item = recognized
            (performance if group == 'performance' else quality).append(item)
    # Online rollout results stay explicitly labelled and separate from fixed
    # evaluation cases. They also make the first view useful before evaluation.
    performance += [
        Chart('train/win_rate', 'Training rollouts · win rate (includes cutoffs)'),
        Chart('train/act1_clear_rate', 'Training rollouts · Act 1 clear rate (includes cutoffs)'),
    ]
    combat = (all(r.data.params.get('experiment.training.mode', 'combat') == 'combat' for r in learners)
              and not any(k.endswith('/act1_clear_rate') for k in metrics))
    add('combat-performance', '01 · Combat performance' if combat else '01 · Performance', performance,
        aliases=('01 · Combat performance', '01 · Performance'))
    add('fight-quality', '02 · Fight quality', quality)
    add('ppo-diagnostics', '03 · PPO diagnostics', [
        Chart('ppo/entropy', 'Action diversity · entropy'),
        Chart('ppo/approx_kl', 'Policy change per update · approximate KL'),
        Chart('ppo/clip_fraction', 'Clipped update fraction'),
        Chart('ppo/value_mse', 'Critic prediction error · MSE'),
        Chart('ppo/policy_loss', 'Policy loss'),
        Chart('ppo/max_gradient_norm', 'Largest gradient norm'),
    ])
    add('training-speed', '04 · Training speed', [
        Chart('system/collection_seconds', 'Collection time per rollout · seconds'),
        Chart('system/update_seconds', 'PPO update time · seconds'),
        Chart('system/collection_decisions_per_second', 'Collection throughput · decisions / second'),
        Chart('system/cumulative_wall_seconds', 'Cumulative training wall time · seconds'),
    ], params=('collection.workers', 'runtime.threads'))

    # Benchmark dates and experiment IDs are data, not template configuration.
    # Keep differing workloads, panels and benchmark/training run kinds apart.
    groups = {}
    for run in runs:
        tag = run.data.tags.get('sts.benchmark')
        kind = run.data.tags.get('sts.kind')
        if tag and kind in ('ppo', 'benchmark'):
            groups.setdefault((tag, kind, run.data.params.get('panel')), []).append(run)
    for (tag, kind, panel), group in sorted(groups.items(), key=lambda item: str(item[0])):
        metrics = frozenset(k for r in group for k in r.data.metrics)
        filter_string = f'tags.sts.benchmark = {_literal(tag)} AND tags.sts.kind = {_literal(kind)}'
        filter_string += (' AND params.panel IS NULL' if panel is None else
                          f' AND params.panel = {_literal(panel)}')
        slug = 'benchmark-' + _fingerprint(_json([tag, kind, panel]))[:16]
        median = 'summary/median_evaluation_seconds' in metrics
        titles = ([
            Chart('summary/median_process_seconds', 'Complete evaluation · median seconds ↓', 'BAR'),
            Chart('summary/median_evaluation_seconds', 'Evaluation · median seconds ↓', 'BAR'),
            Chart('summary/speedup_vs_8', 'Speedup relative to 8 workers ↑', 'BAR'),
        ] if median else [
            Chart('benchmark/process_seconds', 'Complete process · seconds ↓', 'BAR'),
            Chart('benchmark/seconds', 'Complete training · seconds ↓', 'BAR'),
            Chart('benchmark/warm_collection_seconds', 'Warm collection · seconds ↓', 'BAR'),
            Chart('benchmark/collection_seconds', 'Collection · seconds ↓', 'BAR'),
            Chart('benchmark/update_seconds', 'PPO updates · seconds ↓',
                  'LINE' if kind == 'benchmark' and metrics == {'benchmark/update_seconds'} else 'BAR'),
            Chart('benchmark/decisions_per_second', 'Complete training · decisions / second ↑', 'BAR'),
        ])
        add(slug, 'Benchmark · ' + tag + ' · ' + (panel or kind), titles,
            params=('workers', 'collection.workers', 'runtime.threads', 'cpu_threads'))
    return result


def view_state(view):
    """Native Runs layout; deleting generated chart entries only hides charts."""
    charts, sections = [], []
    for item in view.charts:
        key = 'sts-' + _fingerprint(item.metric)[:16]
        section = key + '-section'
        sections.append(dict(uuid=section, name=item.title, display=True,
                             isReordered=True, deleted=False, isGenerated=False))
        chart = dict(uuid=key, type=item.kind, metricKey=item.metric, displayName=item.title,
                     metricSectionId=section, deleted=False, isGenerated=False, runsCountToCompare=100)
        if item.kind == 'LINE':
            chart.update(xAxisKey='step', yAxisKey='metric', selectedXAxisMetricKey='',
                         yAxisExpressions=[], xAxisScaleType='linear', scaleType='linear', range={},
                         lineSmoothness=0, useGlobalLineSmoothing=False, useGlobalXaxisKey=False,
                         displayPoints=True, ignoreOutliers=False)
        charts.append(chart)
    visible = {item.metric for item in view.charts}
    for metric in sorted(view.metrics - visible):
        charts.append(dict(uuid='sts-hidden-' + _fingerprint(metric)[:16], type='BAR',
                           metricKey=metric, displayName=metric, metricSectionId='sts-hidden',
                           deleted=True, isGenerated=True, runsCountToCompare=100))
    return dict(searchFilter=view.filter, orderByKey='attributes.start_time', orderByAsc=False,
                startTime='ALL', lifecycleFilter='Active', datasetsFilter=[], modelVersionFilter='All Runs',
                selectedColumns=[f'metrics.`{c.metric}`' for c in view.charts] +
                                [f'params.`{p}`' for p in view.params],
                columnOrder=[], columnWidths={}, compareRunCharts=charts, compareRunSections=sections,
                runsHiddenMode='SHOW_ALL', viewMaximized=False, runListHidden=True,
                isAccordionReordered=True, hideEmptyCharts=True, useGroupedValuesInCharts=False,
                groupBy=None, groupsExpanded={}, chartsSearchFilter='',
                globalLineChartConfig=dict(xAxisKey='step', lineSmoothness=0, selectedXAxisMetricKey=''))


def sync_views(client, experiment_id):
    """Create/refresh owned templates; callers serialize writers through the store.

    A companion experiment tag records exactly what we last wrote. UI edits and
    deletions take precedence. A pending fingerprint makes interrupted tag writes
    recoverable without claiming a user-created view with the same ID or name.
    """
    from mlflow.utils.validation import MAX_EXPERIMENT_TAG_VAL_LENGTH

    runs, token = [], None
    while True:
        page = client.search_runs([experiment_id], max_results=1000, page_token=token)
        runs.extend(page)
        token = page.token
        if not token:
            break
    tags = client.get_experiment(experiment_id).tags
    registry = json.loads(tags.get(MANAGED_TAG, '{"version":1,"views":{}}'))
    if not isinstance(registry, dict) or registry.get('version') != 1 or not isinstance(registry.get('views'), dict):
        raise ValueError('Unrecognized saved-view template registry; existing views were preserved')
    saved_names = set()
    for key, raw in tags.items():
        if key.startswith(VIEW_PREFIX):
            try:
                saved_names.add(json.loads(raw)['name'])
            except (ValueError, KeyError, TypeError):
                pass  # Unknown native views remain user-owned.

    def write_tag(key, value):
        if len(value) > MAX_EXPERIMENT_TAG_VAL_LENGTH:
            raise ValueError('Saved view exceeds the MLflow experiment tag limit')
        client.set_experiment_tag(experiment_id, key, value)
        tags[key] = value

    results = []
    for view in templates(runs):
        key = VIEW_PREFIX + 'sts-' + view.slug + '-v1'
        # Recheck at the mutation boundary as the UI does not use our writer lock.
        current = client.get_experiment(experiment_id).tags.get(key)
        entry = registry['views'].get(key)
        reason = None
        if entry is None:
            if current is not None or saved_names.intersection((view.name, *view.aliases)):
                reason = 'existing user-owned view'
        elif current is None:
            # A missing first write may also be a successful write followed by
            # a user deletion before acknowledgement. Respect that ambiguity.
            reason = ('deleted by user' if entry.get('applied') is not None else
                      'first save interrupted; preserving the missing view')
        elif _fingerprint(current) not in (entry.get('applied'), entry.get('pending')):
            reason = 'edited by user'
        if reason:
            results.append(dict(name=view.name, status='preserved', reason=reason))
            continue

        state = 'deflate;' + base64.b64encode(zlib.compress(_json(view_state(view)).encode(), 9)).decode()
        old = json.loads(current) if current else {}
        if old.get('name') == view.name and old.get('state') == state:
            # Finish an interrupted acknowledgement without rewriting the view.
            if entry.get('pending'):
                registry['views'][key] = {'applied': _fingerprint(current)}
                write_tag(MANAGED_TAG, _json(registry))
            results.append(dict(name=view.name, status='unchanged'))
            continue
        now = int(time.time() * 1000)
        value = _json(dict(name=view.name, state=state, createdAt=old.get('createdAt', now), updatedAt=now))
        if len(value) > MAX_EXPERIMENT_TAG_VAL_LENGTH:
            raise ValueError('Saved view exceeds the MLflow experiment tag limit: ' + view.name)
        registry['views'][key] = dict(applied=entry.get('applied') if entry else None,
                                     pending=_fingerprint(value))
        write_tag(MANAGED_TAG, _json(registry))
        write_tag(key, value)
        registry['views'][key] = {'applied': _fingerprint(value)}
        write_tag(MANAGED_TAG, _json(registry))
        saved_names.add(view.name)
        results.append(dict(name=view.name, status='updated' if current else 'created'))
    return {'experiment_id': experiment_id, 'views': results}
