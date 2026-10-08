"""Search collection, paired evaluation, distillation and public reanalysis.

All real engine construction/restoration stays in the evaluator. The planner
receives only recorded public decisions through the existing episode runner.
"""
from dataclasses import asdict, replace
import gzip
import hashlib
import json
import math
from pathlib import Path
import time
import uuid

from game.agent.search import SearchConfig, SearchPolicy, BELIEF_MODELS
from game.agent.search.direct import MODEL as DIRECT_MODEL, VIEW as DIRECT_VIEW, PlanningViewPolicy
from game.agent.search.policy import DETACHED_MODELS
from game.agent.search.observed import MODEL as OBSERVED_MODEL
from game.agent.input_views import RAW, validate_view
from game.agent.provenance import implementation
from game.agent.runner import RunCancelled, RunConfig, prepare_directories, run_episode
from game.agent.recording import load_trajectory
from .checkpoint import load_policy, publish, save_checkpoint
from .config import TrainingConfig
from .evaluation import BaselineCase, _episode
from .rewards import RewardSpec
from .scenarios import Scenario, episode_seed

SCHEMA = 'sts_search_report_v2'
TARGETS = 'sts_search_targets_v2'
REPORT_SCHEMAS = (SCHEMA, 'sts_search_report_v1')
TARGET_SCHEMAS = (TARGETS, 'sts_search_targets_v1')
OBJECTIVE = RewardSpec({'combat_win': 1., 'win_hp_fraction': .1})


def _json(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def _artifact(directory, name):
    if not isinstance(name, str) or Path(name).name != name:
        raise ValueError('Expected a sibling public search artifact')
    path = directory / name
    if path.is_symlink():
        raise ValueError('Search artifacts cannot be symlinks')
    return path


def _report_input_view(report):
    """The teacher's effective view is part of the dataset, not a loader guess."""
    configs = report.get('search_configs', {})
    if not configs:
        raise ValueError('Search report requires its teacher configuration')
    views = {DIRECT_VIEW if SearchConfig(**config).model_version in DETACHED_MODELS else RAW
             for config in configs.values()}
    if len(views) != 1:
        raise ValueError('Search report mixes public input views')
    expected = next(iter(views))
    view = validate_view(report.get('planning_view', RAW))
    if view != expected or report.get('schema') == SCHEMA and 'planning_view' not in report:
        raise ValueError('Search report public input view mismatch')
    return view


def _aggregate_search(rows):
    from collections import Counter
    counts, cutoffs, timings = Counter(), Counter(), Counter()
    for row in rows:
        stats = row.get('search', {})
        counts.update(stats.get('fallbacks', {}))
        cutoffs.update(stats.get('cutoffs', {}))
        timings.update(stats.get('timings', {}))
    stats = [r['search'] for r in rows if 'search' in r]
    decisions = sum(v['decisions'] for v in stats)
    searched = sum(v['searched'] for v in stats)
    result = dict(decisions=decisions, searched=searched, coverage=searched / decisions if decisions else 0.,
                simulations=sum(v['simulations'] for v in stats), seconds=sum(v['seconds'] for v in stats),
                fallbacks=dict(counts), cutoffs=dict(cutoffs), timings=dict(timings),
                max_episode_p95_seconds=max((v['p95_seconds'] for v in stats), default=0.))
    if any('leaf_work' in v for v in stats):
        result['leaf_work'] = {key: sum(v.get('leaf_work', {}).get(key, 0) for v in stats)
                               for key in ('steps', 'terminals', 'bootstraps', 'time_bootstraps')}
    return result


def _targets(path, row, policy, split):
    trajectory = load_trajectory(path / row['trajectory'], split=split)
    if len(trajectory.transitions) != len(policy.reconciled_results):
        raise ValueError('Search targets differ from reconciled trajectory')
    target = {'schema': TARGETS, 'trajectory_sha256': trajectory.sha256,
              'teacher': policy.identity, 'checkpoint': policy.base.identity,
              'reward_spec': policy.reward_spec.to_dict(), 'search': asdict(policy.config),
              'planning_view': policy.input_view,
              'split': split, 'targets': [dict(step=i, **r.to_dict()) for i, r in enumerate(policy.reconciled_results)]}
    if policy.planning_start is not None:
        from game.agent.contracts.planning import to_dict, end_to_dict
        observed = policy.config.model_version == OBSERVED_MODEL
        target['planning'] = {'schema': 'sts_public_planning_trace_v2' if observed else 'sts_public_planning_trace_v1',
            'start': policy.planning_start if observed else to_dict(policy.planning_start),
            'completions': {str(i): end_to_dict(end) for i, end in policy.planning_ends.items()}}
        if observed:
            if len(policy.planning_reveals) != len(trajectory.transitions):
                raise ValueError('Reveal receipts differ from reconciled trajectory')
            target['planning']['reveals'] = policy.planning_reveals
    filename = row['episode_id'] + '.search.json.gz'
    digest = publish(path / filename, gzip.compress(_json(target), mtime=0))
    return filename, digest


class SearchEvaluator:
    """Per-worker frozen teacher and exclusively owned real game per job."""
    def __init__(self, settings, checkpoints, policies, source):
        if asdict(implementation()) != source:
            raise ValueError('Search implementation changed after planning')
        self.settings, self.policies, self.source = settings, policies, source
        self.corpus = None
        if settings.get('corpus_path'):
            from .combat_corpus import CombatCorpus
            self.corpus = CombatCorpus(settings['corpus_path'], expected=settings['corpus'])
        self.benchmark = None
        if settings.get('benchmark'):
            from .search_benchmark import SearchBenchmark
            self.benchmark = SearchBenchmark.from_dict(settings['benchmark'])
            if self.benchmark.identity != settings['benchmark_identity']:
                raise ValueError('Declared search benchmark changed after planning')
        self.models = {}
        for name, (path, digest, task) in checkpoints.items():
            model = load_policy(path, expected_sha256=digest, task=task)
            if name != 'network':
                model = SearchPolicy(model, SearchConfig(**settings['configs'][name]))
            elif settings.get('planning_view') == DIRECT_VIEW:
                model = PlanningViewPolicy(model)
            if model.identity != policies[name]:
                raise ValueError('Search teacher changed after planning')
            self.models[name] = model

    def run(self, config, episode, policy, output, private, cancel=None):
        output, private = Path(output), Path(private)
        chooser = self.models[policy]
        if self.settings['goal'] == 'act1':
            from .run_demonstrations import describe
            result = run_episode(config, output_dir=output, audit_dir=private, episode_id=episode,
                                 combat_policy=chooser, policy_identity=self.policies[policy], cancel=cancel)
            row = describe(result, split=config.split, goal='act1')
            row['potion_use_actions'] = row['actions'].get('use_potion', 0)
            row['combats'] = list(result.combats)
            # describe()'s last decision precedes terminal defeat; report the
            # authoritative outcome instead of presenting pre-lethal HP as exit HP.
            row['end_hp'] = 0 if result.outcome.kind == 'defeat' else (row['last_public_hud'] or {}).get('hp')
            if result.search is not None:
                row['search'] = result.search
            return row
        factory, expected, planning = None, None, None
        scenario_set = self.settings.get('corpus') or 'search_controlled_combat_v1'
        if self.corpus:
            case = self.corpus.cases[config.case_id]
            factory = lambda _: self.corpus.restore(config.case_id, split=config.split)
            expected = case['public_state_sha256']
        elif self.benchmark:
            scenario = next(s for s in self.benchmark.scenarios if s.name == config.scenario_id)
            if scenario.start.encounter_id != config.encounter:
                raise ValueError('Benchmark job encounter mismatch')
            factory = scenario.make
            scenario_set = self.benchmark.identity + ':' + scenario.name
            if isinstance(chooser, SearchPolicy) and chooser.config.uses_belief:
                planning = scenario.start
        else:
            scenario = Scenario(config.encounter, 'controlled')
            factory = scenario.make
            if isinstance(chooser, SearchPolicy) and chooser.config.uses_belief:
                planning = scenario.planning_start()
        row = _episode(config, policy, replace(implementation(), policy=self.policies[policy]),
            output, private, TrainingConfig(reward=OBJECTIVE, action_policy=chooser.model.action_policy),
            chooser=chooser, engine_factory=factory, episode_id=episode,
            scenario_set=scenario_set,
            expected_start=expected, evidence='headless_rollout' if self.corpus else 'controlled_fixture', cancel=cancel,
            planning_start=planning)
        if isinstance(chooser, SearchPolicy) and row['status'] in ('terminated', 'truncated'):
            row['targets'], row['targets_sha256'] = _targets(output, row, chooser, config.split)
        return row


def run_search(*, checkpoint, output_dir, search=SearchConfig(), corpus_path=None,
               cases=8, split='validation', start_index=0, max_decisions=256,
               time_limit_seconds=600., workers=1, collect=False, act1=False,
               encounters=('overgrowth_vantom',), benchmark_path=None,
               critic_baseline_simulations=None, include_root=True, cancel=None):
    from .evaluation_workers import settings as worker_settings, evaluate_parallel
    if type(cases) is not int or not 1 <= cases <= 10000 or max_decisions < 1:
        raise ValueError('Invalid search experiment size')
    if type(include_root) is not bool:
        raise ValueError('Invalid root comparison switch')
    if critic_baseline_simulations is not None and (collect or search.method != 'gumbel' or not search.leaf_rollout_steps or
            type(critic_baseline_simulations) is not int or not 1 <= critic_baseline_simulations <= 4096):
        raise ValueError('A critic baseline requires rollout-leaf evaluation and a valid simulation budget')
    episode_seed(split, start_index + cases - 1)
    if not math.isfinite(time_limit_seconds) or not 0 < time_limit_seconds <= 86400 or not encounters:
        raise ValueError('Invalid search episode limit or encounters')
    if collect and (split != 'train' or act1):
        raise ValueError('Search collection uses only training combats')
    if act1 and corpus_path:
        raise ValueError('Campaign evaluation starts genuine runs, not combat snapshots')
    if search.uses_belief:
        if act1 or corpus_path:
            raise ValueError('The public belief model requires declared controlled starts; campaign/corpus anchors are not available')
        # Validate every requested public declaration before creating artifacts.
        for encounter in encounters:
            Scenario(encounter, 'controlled').planning_start()
    benchmark = None
    if benchmark_path is not None:
        if act1 or corpus_path or not search.uses_belief:
            raise ValueError('Declared search inventories require combat runs with a public belief model')
        from .search_benchmark import SearchBenchmark
        benchmark = SearchBenchmark.load(benchmark_path)
        if cases % len(benchmark.scenarios):
            raise ValueError('Search cases must contain complete balanced benchmark rounds')
    execution = worker_settings(workers)
    teacher = load_policy(checkpoint, reward_spec=OBJECTIVE)
    planner = SearchPolicy(teacher, search)
    names = ((search.method,) if collect else ('network', 'root') if search.method == 'root'
             else ('network', 'root', 'gumbel') if include_root else ('network', 'gumbel'))
    configs = {name: asdict(replace(search, method=name, exploration=collect)) for name in names if name != 'network'}
    if critic_baseline_simulations is not None:
        names += ('gumbel_critic',)
        configs['gumbel_critic'] = asdict(replace(search, simulations=critic_baseline_simulations,
                                                leaf_rollout_steps=0, exploration=False))
        if 'root' in configs:
            configs['root'] = asdict(replace(search, method='root', simulations=critic_baseline_simulations,
                                           leaf_rollout_steps=0, exploration=False))
    policies = {name: teacher.identity if name == 'network' else
                SearchPolicy(teacher, SearchConfig(**configs[name])).identity for name in names}
    if search.model_version in DETACHED_MODELS and 'network' in policies:
        policies['network'] = PlanningViewPolicy(teacher).identity
    output = Path(output_dir).resolve()
    if (output / 'search-plan.json').exists():
        raise FileExistsError(output / 'search-plan.json')
    output, private = prepare_directories(output, output.with_name(output.name + '-private'))
    source = asdict(implementation())
    settings = dict(kind='search', goal='act1' if act1 else 'combat', configs=configs,
                    planning_view=planner.input_view)
    if benchmark:
        settings.update(benchmark=benchmark.to_dict(), benchmark_identity=benchmark.identity)
    source_rows = None
    if corpus_path:
        from .combat_corpus import CombatCorpus
        corpus = CombatCorpus(corpus_path)
        settings.update(corpus_path=str(corpus.path), corpus=corpus.identity)
        locks = [corpus.path.parent / n for n in ('test-opened.json', 'search-test-opened.json')]
        if split == 'validation' and any(p.exists() for p in locks):
            raise ValueError('Development is closed after held-out test was opened')
        source_rows = [r for r in corpus.split(split) if r['start_kind'] == 'opening']
        source_rows = source_rows[start_index:start_index+cases]
        if not source_rows:
            raise ValueError('No opening cases in requested corpus partition')
    rows, jobs = [], []
    count = len(source_rows) if source_rows is not None else cases
    for index in range(count):
        identity = uuid.uuid4().hex
        source_row = source_rows[index] if source_rows is not None else None
        case_id = source_row['case_id'] if source_row else identity
        group = source_row['source_group'] if source_row else identity
        declared = benchmark.scenarios[index % len(benchmark.scenarios)] if benchmark else None
        for name in names:
            row = dict(case_id=case_id, source_group=group, policy=name, status='unattempted', episode_id=uuid.uuid4().hex)
            if declared:
                row.update(scenario_id=declared.name, deck_profile=declared.deck_profile, benchmark_role=declared.role,
                           case_index=start_index + index)
            rows.append(row)
            if act1:
                jobs.append(RunConfig(seed=episode_seed(split, start_index+index), split=split, goal='act1',
                    first_act=('overgrowth', 'underdocks')[index % 2], max_decisions=max_decisions,
                    time_limit_seconds=time_limit_seconds))
                row['first_act'] = jobs[-1].first_act
            else:
                encounter = (declared.start.encounter_id if declared else
                             source_row['encounter'] if source_row else encounters[index % len(encounters)])
                args = (encounter, split, episode_seed(split, start_index+index), 0, max_decisions, time_limit_seconds)
                if source_row:
                    from .combat_benchmark import FrozenCombatCase
                    jobs.append(FrozenCombatCase(*args, case_id))
                elif declared:
                    from .search_benchmark import DeclaredCase
                    jobs.append(DeclaredCase(*args, declared.name))
                else:
                    jobs.append(BaselineCase(*args))
    report = dict(schema=SCHEMA, status='running', split=split, goal=settings['goal'],
        purpose='collection' if collect else 'evaluation', policies=policies, checkpoint=teacher.identity,
        search_configs=configs, reward_spec=OBJECTIVE.to_dict(), implementation=source,
        limits=dict(max_decisions=max_decisions, time_limit_seconds=time_limit_seconds),
        execution=execution, corpus=settings.get('corpus'), start_kind='opening', episodes=rows)
    if benchmark:
        report.update(benchmark=benchmark.to_dict(), benchmark_identity=benchmark.identity,
                      evidence='authored_developed_inventory', allocation='balanced_round_robin')
    if 'planning_view' in settings:
        report['planning_view'] = settings['planning_view']
    if act1:
        report['noncombat_policy'] = source['policy']
    if corpus_path and split == 'test':
        # Freeze every compared policy and its compute budget before reading a
        # single held-out engine snapshot. Existing locks are never rewritten.
        lock = corpus.path.parent / 'search-test-opened.json'
        binding = dict(corpus=corpus.identity, policies=policies, cases=[r['case_id'] for r in source_rows],
                       search_configs=configs, limits=report['limits'], implementation=source)
        if locks[0].exists():
            raise ValueError('This corpus test was already opened by another experiment')
        if lock.exists() and json.loads(lock.read_text()) != binding:
            raise ValueError('Held-out search configuration is already frozen')
        if not lock.exists():
            publish(lock, _json(binding))
    publish(output / 'search-plan.json', _json(report))
    digest = hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()
    bundles = {name: (str(Path(checkpoint).resolve()), digest, 'combat') for name in names}
    started = time.perf_counter()
    if workers > 1:
        report.update(evaluate_parallel(rows, jobs, checkpoints=bundles, policies=policies, source=source,
            output=output, private=private, workers=workers, cancel=cancel, combat=settings))
    else:
        owner = SearchEvaluator(settings, bundles, policies, source)
        report['status'] = 'complete'
        for row, config in zip(rows, jobs):
            if cancel is not None and cancel.is_set():
                report['status'] = 'interrupted'
                break
            try:
                row.update(owner.run(config, row['episode_id'], row['policy'], output, private, cancel))
            except (Exception, KeyboardInterrupt) as error:
                row.update(status='interrupted' if isinstance(error, (RunCancelled, KeyboardInterrupt)) else 'failed',
                           failure=type(error).__name__)
            if row['status'] not in ('terminated', 'truncated'):
                report['status'] = row['status']
                break
    report['total_seconds'] = time.perf_counter() - started
    grouped = {name: [r for r in rows if r['policy'] == name] for name in names}
    if act1:
        from .run_evaluation import compare, _won
        from .comparison import interval
        from game.agent.tracking.records import episode_metrics
        report['summary'] = {n: dict(episode_metrics(v, 'act1'),
            act1_clear_rate_group_hoeffding_95=interval(sum(_won(r, 'act1') for r in v) / len(v), v))
                            for n, v in grouped.items()}
        for name, values in grouped.items():
            completed = [c for row in values for c in row.get('combats', ())]
            wins = [c for c in completed if c['outcome'] == 'victory']
            report['summary'][name].update(combats_completed=len(completed), combat_wins=len(wins),
                combat_defeats=sum(c['outcome'] == 'defeat' for c in completed),
                mean_combat_hp_on_win=sum(c['hp'] for c in wins) / len(wins) if wins else None)
        report['paired_vs_network'] = {n: compare(v, grouped['network'], goal='act1', baseline_name='network')
                                       for n, v in grouped.items() if n != 'network'}
    else:
        from .comparison import summary, paired
        report['summary'] = {n: summary(v) for n, v in grouped.items()}
        if not collect:
            report['paired_vs_network'] = {n: paired(v, grouped['network'], baseline_name='network')
                                           for n, v in grouped.items() if n != 'network'}
    for name, values in grouped.items():
        if name != 'network':
            report['summary'][name]['search'] = _aggregate_search(values)
    if benchmark:
        from .comparison import summary, paired
        report['benchmark_breakdown'] = {}
        for field in ('deck_profile', 'scenario_id', 'benchmark_role'):
            values = {}
            for label in sorted({r[field] for r in rows}):
                selected = {n: [r for r in v if r[field] == label] for n, v in grouped.items()}
                values[label] = dict(summary={n: summary(v) for n, v in selected.items()})
                if not collect:
                    values[label]['paired_vs_network'] = {
                        n: paired(v, selected['network'], baseline_name='network')
                        for n, v in selected.items() if n != 'network'}
            report['benchmark_breakdown'][field] = values
    report['promotion'] = 'experimental_only'
    path = output / 'search.json'
    publish(path, _json(report))
    from game.agent.tracking import report_progress
    report_progress(path, report)
    return path, report


def _planning_trace(data, trajectory, row):
    """Strict public supplement; no inference from a private audit or snapshot."""
    from game.agent.contracts.planning import from_dict, end_from_dict
    value = data.get('planning')
    if value is None:
        if data['search'].get('model_version') in BELIEF_MODELS:
            raise ValueError('Belief targets require their recorded public planning anchor')
        return None, {}
    observed = data['search'].get('model_version') == OBSERVED_MODEL
    fields = {'schema', 'start', 'completions'} | ({'reveals'} if observed else set())
    if (type(value) is not dict or set(value) != fields or
            value['schema'] != ('sts_public_planning_trace_v2' if observed else 'sts_public_planning_trace_v1')
            or type(value['completions']) is not dict):
        raise ValueError('Invalid public planning trace')
    if observed:
        from game.agent.search.observed import validate_anchor
        from game.headless.reveals import validate_reveals
        start = validate_anchor(value['start'])
        if not isinstance(value['reveals'], list) or len(value['reveals']) != len(trajectory.transitions):
            raise ValueError('Invalid planning reveal receipts')
        for events in value['reveals']:
            validate_reveals(events)
    else:
        start = from_dict(value['start'])
    ends = {}
    for key, record in value['completions'].items():
        if not key.isascii() or not key.isdigit() or str(int(key)) != key or int(key) != len(trajectory.transitions) - 1:
            raise ValueError('Planning completion must bind to the last recorded action')
        end = end_from_dict(record)
        summary = row.get('combat') or {}
        if (row['status'] != 'terminated' or summary.get('outcome') not in ('victory', 'defeat') or
                end.result != summary.get('outcome') or end.run.get('hp') != summary.get('hp') or
                end.run.get('max_hp') != summary.get('max_hp')):
            raise ValueError('Planning completion differs from its recorded combat result')
        ends[int(key)] = end
    if row['status'] == 'terminated' and not ends:
        raise ValueError('Missing public combat completion')
    return start, ends


def _load_search_targets(report_path, report, row, trajectory, input_view):
    """Bind a public planning supplement to its recorded behavior and teacher."""
    target_path = _artifact(report_path.parent, row['targets'])
    if hashlib.sha256(target_path.read_bytes()).hexdigest() != row['targets_sha256']:
        raise ValueError('Search target artifact changed')
    data = json.loads(gzip.decompress(target_path.read_bytes()))
    if (data.get('schema') not in TARGET_SCHEMAS or data.get('split') != report['split'] or
            data['trajectory_sha256'] != trajectory.sha256 or
            data['reward_spec'] != report['reward_spec'] or
            data.get('teacher') != report['policies'][row['policy']] or
            data.get('checkpoint') != report['checkpoint'] or
            data.get('search') != report['search_configs'][row['policy']] or
            len(data['targets']) != len(trajectory.transitions)):
        raise ValueError('Search targets do not match their public trajectory')
    if (validate_view(data.get('planning_view', RAW)) != input_view or
            data['schema'] == TARGETS and 'planning_view' not in data or
            data['schema'] != TARGETS and input_view != RAW):
        raise ValueError('Search target public input view mismatch')
    return data


def load_search_corpus(report_path, policy):
    from .learner import _corpus_from_episodes
    from .dataset import training_episode
    from .features import FeatureEncoder
    report_path = Path(report_path).resolve()
    report = json.loads(report_path.read_text())
    if (report.get('schema') not in REPORT_SCHEMAS or report.get('split') != 'train' or report.get('status') != 'complete' or
            report.get('purpose') not in ('collection', 'reanalysis')):
        raise ValueError('Distillation requires a complete training search report')
    input_view = _report_input_view(report)
    if report['reward_spec'] != policy.reward_spec.to_dict():
        raise ValueError('Search dataset objective mismatch')
    episodes = [r for r in report['episodes'] if r.get('targets')]
    examples = []
    bindings = []
    for row in episodes:
        trajectory_path = _artifact(report_path.parent, row['trajectory'])
        trajectory = load_trajectory(trajectory_path, split='train', expected={
            'policy': row.get('behavior_policy', report['policies'][row['policy']])})
        data = _load_search_targets(report_path, report, row, trajectory, input_view)
        _planning_trace(data, trajectory, row)
        selected = []
        for index, (transition, target) in enumerate(zip(trajectory.transitions, data['targets'])):
            if target['step'] != index or target['action_ref'] not in {a.ref for a in transition.observation.candidates}:
                raise ValueError('Search target candidate mapping changed')
            if report['purpose'] == 'collection' and target['action_ref'] != transition.action.ref:
                raise ValueError('Collected search target differs from applied behavior action')
            selected.append(target['reason'] is None and target['simulations'] >= 1)
        episode = training_episode(trajectory, _artifact(report_path.parent, row['training']),
                                   reward_spec=policy.reward_spec)
        encoder = FeatureEncoder(policy.model.vocabulary,
            action_policy=policy.model.action_policy, representation=policy.model.architecture.schema,
            input_view=input_view)
        corpus = _corpus_from_episodes((episode,), encoder, split='train', compact=True, selected=selected)
        for example, target in zip(corpus.examples, (t for t, keep in zip(data['targets'], selected) if keep)):
            refs = example.state.candidate_refs
            if set(target['probabilities']) != {ref for ref, ok in zip(refs, example.state.policy_mask) if ok}:
                raise ValueError('Search target legal support changed')
            probabilities = tuple(target['probabilities'].get(ref, 0.) for ref in refs)
            if any(not math.isfinite(p) or p < 0 for p in probabilities) or not math.isclose(sum(probabilities), 1., abs_tol=1e-6):
                raise ValueError('Search target probabilities are not normalized')
            examples.append(replace(example, policy_target=probabilities))
        bindings.append((row['targets_sha256'], corpus.identity))
    if not examples:
        raise ValueError('No supported searched decisions available for distillation')
    identity = 'sts_search_corpus_v1:' + hashlib.sha256(_json(bindings)).hexdigest()
    return replace(corpus, examples=tuple(examples), identity=identity, episodes=len(episodes))


def _search_corpora(report_paths, policy):
    """Combine fresh and refreshed training data without counting a fight twice."""
    paths = [report_paths] if isinstance(report_paths, (str, Path)) else list(report_paths)
    if not 1 <= len(paths) <= 16:
        raise ValueError('Distillation requires between one and sixteen training reports')
    corpora, bindings, seen = [], [], set()
    for path in paths:
        path = Path(path).resolve()
        corpus = load_search_corpus(path, policy)
        report = json.loads(path.read_text())
        for row in report['episodes']:
            if not row.get('targets'):
                continue
            identities = [('episode', row['episode_id'])]
            if report.get('benchmark_identity') and 'case_index' in row:
                identities.append(('start', report['benchmark_identity'], report['split'],
                                   row['case_index'], row['scenario_id']))
            else:
                identities.append(('case', row['case_id']))
            if any(identity in seen for identity in identities):
                raise ValueError('Training reports contain a duplicate source fight')
            seen.update(identities)
        if corpora and any(getattr(corpus, name) != getattr(corpora[0], name)
                           for name in ('vocabulary', 'reward_spec', 'split', 'action_policy', 'input_view')):
            raise ValueError('Training reports have incompatible public views or contracts')
        corpora.append(corpus)
        bindings.append(dict(report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             corpus=corpus.identity, episodes=corpus.episodes, examples=len(corpus.examples)))
    if len(corpora) == 1:
        return corpora[0], bindings
    identity = 'sts_search_corpora_v1:' + hashlib.sha256(_json(bindings)).hexdigest()
    return replace(corpora[0], examples=tuple(e for c in corpora for e in c.examples), identity=identity,
                   episodes=sum(c.episodes for c in corpora),
                   encoding_seconds=sum(c.encoding_seconds for c in corpora)), bindings


def distill_search(*, checkpoint, report_path, output_dir, updates=None, epochs=None, seed=0, cancel=None):
    from .learner import ImitationLearner, LearnerConfig
    if epochs is not None and (updates is not None or type(epochs) is not int or not 1 <= epochs <= 100):
        raise ValueError('Choose a bounded epoch count or an update count')
    if updates is None and epochs is None:
        updates = 128
    if updates is not None and (type(updates) is not int or not 1 <= updates <= 100000):
        raise ValueError('Invalid bounded distillation updates')
    teacher = load_policy(checkpoint, reward_spec=OBJECTIVE)
    # Validate the objective/discount without silently selecting a different
    # input view for an already distilled checkpoint.
    SearchPolicy(teacher, SearchConfig(model_version=DIRECT_MODEL if teacher.model.input_view == DIRECT_VIEW
                                      else 'reconstruction_v1'))
    corpus, sources = _search_corpora(report_path, teacher)
    if epochs is not None:
        updates = epochs * math.ceil(len(corpus.examples) / 32)
        if updates > 100000:
            raise ValueError('Epoch budget exceeds bounded distillation updates')
    if teacher.model.input_view not in (RAW, corpus.input_view):
        raise ValueError('Distillation cannot restore raw historical links to a detached public input view checkpoint')
    output = Path(output_dir).resolve()
    output, private = prepare_directories(output, output.with_name(output.name + '-private'))
    if (output / 'initial.sts-model').exists():
        raise FileExistsError(output)
    from .model import ActorCritic
    model = ActorCritic(teacher.model.vocabulary, teacher.model.architecture,
                       action_policy=teacher.model.action_policy, input_view=corpus.input_view)
    model.load_state_dict(teacher.model.state_dict(), strict=True)
    learner = ImitationLearner(model, corpus, LearnerConfig(batch_size=32, learning_rate=.0001), seed=seed)
    initial = save_checkpoint(output / 'initial.sts-model', learner)
    started = time.perf_counter()
    metrics = []
    for _ in range(updates):
        if cancel is not None and cancel.is_set():
            break
        metrics.append(learner.step())
    final = save_checkpoint(output / 'final.sts-model', learner, resume_path=private / 'final.resume.pt')
    report = dict(schema='sts_search_distillation_v1', status='complete' if len(metrics) == updates else 'interrupted', split='train',
        teacher=teacher.identity, corpus=corpus.identity, source_reports=sources, reward_spec=OBJECTIVE.to_dict(),
        examples=len(corpus.examples), episodes=corpus.episodes, updates=metrics,
        initial_sha256=initial, final_sha256=final, corpus_identity=corpus.identity,
        learner_config=asdict(learner.config), initialization={'resumed': False, 'checkpoint': teacher.identity,
            'source_input_view': teacher.model.input_view, 'input_view': corpus.input_view},
        input_view=corpus.input_view, feature_identity=model.feature_identity,
        policy_targets='search_distribution', value_targets='completed_behavior_returns',
        implementation=asdict(implementation()),
        total_seconds=time.perf_counter()-started, promotion='not_evaluated')
    if epochs is not None:
        report.update(requested_epochs=epochs, sample_presentations=sum(m['samples'] for m in metrics))
    path = output / 'search-distillation.json'
    publish(path, _json(report))
    from game.agent.tracking import report_progress
    report_progress(path, report)
    return path, report


def _audit_rollout(model, seed, first_key, policy, depth, deadline, cancel):
    """One hypothetical continuation; no value is fabricated at a work cutoff."""
    from game.agent.search.public_keys import action_key
    from game.headless.planning import UnsupportedSearch
    steps = 0
    first_value = None
    try:
        if cancel is not None and cancel.is_set():
            return dict(status='cutoff', reason='cancelled', steps=0)
        if time.perf_counter() >= deadline:
            return dict(status='cutoff', reason='rollout_time_budget', steps=0)
        world, public = model.sample(seed)
        for index in range(depth):
            if cancel is not None and cancel.is_set():
                return dict(status='cutoff', reason='cancelled', steps=steps)
            if time.perf_counter() >= deadline:
                return dict(status='cutoff', reason='rollout_time_budget', steps=steps)
            key = first_key if index == 0 else action_key(public, policy(public))
            public = world.step(public, key)
            steps += 1
            if public is None:
                return dict(status='completed', steps=steps, value=world.terminal_value,
                            first_successor_value=world.terminal_value if index == 0 else first_value)
            if index == 0:
                _, first_value = policy.probabilities(public)
        return dict(status='cutoff', reason='rollout_depth_budget', steps=steps)
    except UnsupportedSearch as error:
        return dict(status='unsupported', reason=str(error), steps=steps)


def audit_critic(*, checkpoint, report_path, output_path, positions=8, rollouts=4, depth=64,
                 rollout_seconds=30., cancel=None):
    """Compare public-prefix search/critic estimates with completed continuations.

    Maintained beliefs require each selected episode's recorded public anchor.
    The original return describes original behavior. Paired model rollouts take
    the greedy/search first action and then the same greedy policy; neither is
    a fresh real-game outcome or an estimate of continued tree-search behavior.
    """
    from random import Random
    from collections import Counter
    from game.agent.search.model import PublicCombatModel, action_key
    from game.headless.planning import UnsupportedSearch
    from .dataset import load_training_dataset
    if any(type(n) is not int or n < 1 for n in (positions, rollouts, depth)) or positions > 256 or rollouts > 64 or depth > 512:
        raise ValueError('Invalid bounded critic audit size')
    if type(rollout_seconds) not in (int, float) or not math.isfinite(rollout_seconds) or not 0 < rollout_seconds <= 600:
        raise ValueError('Invalid critic rollout deadline')
    source_path = Path(report_path).resolve()
    source = json.loads(source_path.read_text())
    if (source.get('schema') not in REPORT_SCHEMAS or source.get('status') != 'complete' or
            source.get('split') not in ('train', 'validation') or source.get('goal') != 'combat'):
        raise ValueError('Critic audits use complete training/development combat reports')
    if source.get('reward_spec') != OBJECTIVE.to_dict():
        raise ValueError('Critic audit objective mismatch')
    input_view = _report_input_view(source)
    # Preserve the source simulator, action budget, seed and depth. Only disable
    # root exploration for the diagnostic recommendation; never silently switch
    # a maintained belief to the restricted reconstruction simulator.
    config = replace(SearchConfig(**source['search_configs']['gumbel']), exploration=False)
    teacher = load_policy(checkpoint, reward_spec=OBJECTIVE)
    planner = SearchPolicy(teacher, config)
    if planner.input_view != input_view:
        raise ValueError('Critic audit public input view mismatch')
    policy = PlanningViewPolicy(teacher) if input_view == DIRECT_VIEW else teacher
    # Greedy recordings from older evaluators have no public planning anchor.
    # Use the explicitly anchored Gumbel behavior for maintained-belief audits.
    behavior = 'gumbel' if config.uses_belief or 'network' not in source['policies'] else 'network'
    episodes = [r for r in source['episodes'] if r['policy'] == behavior and r['status'] == 'terminated']
    rows, bindings, rng = [], [], Random(0)
    started = time.perf_counter()
    for row in episodes:
        if cancel is not None and cancel.is_set():
            break
        pair = (_artifact(source_path.parent, row['trajectory']), _artifact(source_path.parent, row['training']))
        identity = row.get('behavior_policy', source['policies'][row['policy']])
        expected = {'policy': identity}
        if source.get('purpose') != 'reanalysis':
            expected.update({key: source['implementation'][key] for key in ('build', 'rules')})
        # No reward conversion: the sidecar must declare the same objective.
        episode = next(iter(load_training_dataset([pair], split=source['split'], expected=expected)))
        if (episode.reward_spec != OBJECTIVE or not episode.ending.terminated or episode.ending.truncated or
                asdict(episode.ending.combat) != row['combat'] or not episode.transitions or
                len(episode.transitions) != row['steps'] or
                not math.isclose(sum(s.reward for s in episode.transitions), row['task_return'], abs_tol=1e-8)):
            raise ValueError('Critic audit requires matching completed behavior labels')
        start, ends = None, {}
        binding = dict(episode_id=row['episode_id'], trajectory_sha256=episode.trajectory.sha256,
                       training_sha256=hashlib.sha256(pair[1].read_bytes()).hexdigest(),
                       behavior_build=episode.trajectory.metadata.build,
                       behavior_rules=episode.trajectory.metadata.rules)
        if config.uses_belief:
            if not row.get('targets'):
                raise ValueError('Critic audit requires its recorded public planning anchor')
            data = _load_search_targets(source_path, source, row, episode.trajectory, input_view)
            start, ends = _planning_trace(data, episode.trajectory, row)
            binding['targets_sha256'] = row['targets_sha256']
        bindings.append(binding)
        planner.reset()
        if config.uses_belief:
            planner.begin_combat(start, episode.trajectory.initial)
        else:
            planner.history.attach(episode.trajectory.initial)
        selected = {0, len(episode.transitions) // 2}
        for index, step in enumerate(episode.transitions):
            if cancel is not None and cancel.is_set():
                break
            transition = step.transition
            if index in selected:
                probabilities, value = policy.probabilities(transition.observation)
                greedy_ref = max(probabilities, key=probabilities.get)
                result = planner.choose(transition.observation)
                actions = {a.ref: a for a in transition.observation.candidates}
                keys = {name: action_key(transition.observation, actions[ref]) for name, ref in
                        (('greedy', greedy_ref), ('search', result.action_ref))}
                item = dict(episode_id=row['episode_id'], case_id=row['case_id'], source_group=row['source_group'],
                    encounter=row['encounter'], trajectory_sha256=episode.trajectory.sha256, step=index,
                    behavior_policy=identity, critic=value, search_clipped_critic=min(1.1, max(0., value)),
                    completed_behavior_return=sum(s.reward for s in episode.transitions[index:]),
                    greedy_action_ref=greedy_ref, search_action_ref=result.action_ref,
                    search_disagrees=result.action_ref != greedy_ref, search_fallback=result.reason,
                    search_cutoff=result.cutoff, search_simulations=result.simulations,
                    search_values={name: result.values[ref] for name, ref in
                                   (('greedy', greedy_ref), ('search', result.action_ref))},
                    search_visits={name: result.visits[ref] for name, ref in
                                   (('greedy', greedy_ref), ('search', result.action_ref))},
                    rollouts=[])
                deadline = time.perf_counter() + rollout_seconds
                try:
                    if config.uses_belief:
                        model = planner.belief
                        if model is None:
                            raise UnsupportedSearch(planner._belief_failure)
                        if model.reason == 'belief_budget':
                            model.recover(seconds=max(0., deadline - time.perf_counter()))
                        if model.reason:
                            raise UnsupportedSearch(model.reason)
                    else:
                        model = PublicCombatModel(transition.observation, planner.history)
                    for _ in range(rollouts):
                        if cancel is not None and cancel.is_set():
                            break
                        seed = rng.randrange(2**63)
                        greedy = _audit_rollout(model, seed, keys['greedy'], policy, depth, deadline, cancel)
                        searched = (dict(greedy) if keys['greedy'] == keys['search'] else
                                    _audit_rollout(model, seed, keys['search'], policy, depth, deadline, cancel))
                        item['rollouts'].append(dict(seed=seed, greedy=greedy, search=searched))
                except UnsupportedSearch as error:
                    item['rollout_fallback'] = str(error)
                item['completed_rollout_returns'] = [r['greedy']['value'] for r in item['rollouts']
                                                     if r['greedy']['status'] == 'completed']
                item['rollout_cutoffs'] = sum(r['greedy']['status'] == 'cutoff' for r in item['rollouts'])
                rows.append(item)
            if len(rows) >= positions or index >= max(selected):
                break
            # Advance the public belief with the RECORDED action even when the
            # diagnostic recommendation differs. Rollouts only own forks.
            if planner.needs_combat_reveals:
                planner.observe_reveals(data['planning']['reveals'][index])
            planner.observe_transition(transition.observation, transition.action, transition.execution,
                                       ends.get(index, transition.successor) if config.uses_belief else transition.successor)
        if len(rows) >= positions:
            break
    errors = [r['critic'] - r['completed_behavior_return'] for r in rows]
    report = dict(schema='sts_search_critic_audit_v2', status='interrupted' if cancel is not None and cancel.is_set() else 'complete',
        checkpoint=teacher.identity, rollout_policy=policy.identity, implementation=asdict(implementation()),
        source_report_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        split=source['split'], reward_spec=OBJECTIVE.to_dict(), planning_view=input_view,
        search=asdict(config), selected_behavior=behavior, selection='opening_and_midpoint_in_report_order',
        source_bindings=bindings, positions=rows,
        limits=dict(positions=positions, rollouts=rollouts, depth=depth, rollout_seconds=rollout_seconds),
        interpretation='Original completed behavior labels; model rollouts use greedy continuation after the named first action. Cutoffs/unsupported branches have no value label. Correlated positions share source_group.',
        summary=dict(positions=len(rows), source_groups=len({r['source_group'] for r in rows}),
            eligible_episodes=len(episodes), search_disagreements=sum(r['search_disagrees'] for r in rows),
            critic_mae_vs_completed_behavior=sum(abs(e) for e in errors) / len(rows) if rows else None,
            critic_mse_vs_completed_behavior=sum(e*e for e in errors) / len(rows) if rows else None,
            critic_bias_vs_completed_behavior=sum(errors) / len(rows) if rows else None,
            rollout_completions=sum(len(r['completed_rollout_returns']) for r in rows),
            rollout_cutoffs=sum(r['rollout_cutoffs'] for r in rows),
            rollout_unsupported=sum(t['greedy']['status'] == 'unsupported' for r in rows for t in r['rollouts']),
            rollout_fallbacks=dict(Counter(r['rollout_fallback'] for r in rows if 'rollout_fallback' in r))),
        total_seconds=time.perf_counter() - started)
    path = Path(output_path).resolve()
    publish(path, _json(report))
    return path, report


def reanalyse_search(*, checkpoint, report_path, output_dir, search=SearchConfig(simulations=16, exploration=True),
                     max_episodes=None, cancel=None):
    source_path = Path(report_path).resolve()
    source = json.loads(source_path.read_text())
    if (source.get('schema') not in REPORT_SCHEMAS or source.get('split') != 'train' or source.get('status') != 'complete' or
            source.get('purpose') not in ('collection', 'reanalysis')):
        raise ValueError('Reanalysis accepts only complete training search collections')
    selected = [r for r in source['episodes'] if r.get('targets')]
    if max_episodes is not None:
        if type(max_episodes) is not int or not 1 <= max_episodes <= len(selected):
            raise ValueError('Invalid bounded reanalysis prefix')
        if source.get('benchmark') and max_episodes % len(source['benchmark']['scenarios']):
            raise ValueError('Developed reanalysis must contain balanced benchmark rounds')
        selected = selected[:max_episodes]
    teacher = load_policy(checkpoint, reward_spec=OBJECTIVE)
    # Validate target/outcome bindings before producing a refreshed dataset.
    load_search_corpus(source_path, teacher)
    policy = SearchPolicy(teacher, search)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'search.json').exists():
        raise FileExistsError(output / 'search.json')
    report = {k: source[k] for k in ('schema', 'split', 'goal', 'corpus', 'start_kind', 'reward_spec', 'limits')}
    for key in ('benchmark', 'benchmark_identity', 'evidence', 'allocation'):
        if key in source:
            report[key] = source[key]
    report.update(schema=SCHEMA, status='complete', purpose='reanalysis', checkpoint=teacher.identity, policies={search.method: policy.identity},
                  planning_view=policy.input_view,
                  search_configs={search.method: asdict(search)}, episodes=[], implementation=asdict(implementation()),
                  source_report_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
                  outcome_provenance='original_behavior_unchanged', promotion='not_evaluated')
    if max_episodes is not None:
        report['selection'] = dict(kind='recorded_prefix', max_episodes=max_episodes,
                                   episode_ids=[r['episode_id'] for r in selected])
    started = time.perf_counter()
    for original in selected:
        if cancel is not None and cancel.is_set():
            report['status'] = 'interrupted'
            break
        if not original.get('targets'):
            continue
        row = dict(original, policy=search.method)
        row['behavior_policy'] = original.get('behavior_policy', source['policies'][original['policy']])
        trajectory = load_trajectory(_artifact(source_path.parent, row['trajectory']), split='train')
        policy.reset()
        data = json.loads(gzip.decompress(_artifact(source_path.parent, row['targets']).read_bytes()))
        start, ends = _planning_trace(data, trajectory, row)
        if (search.model_version == OBSERVED_MODEL) != (data['search']['model_version'] == OBSERVED_MODEL):
            raise ValueError('Reanalysis cannot convert between observed and legacy planning traces')
        if search.uses_belief:
            if start is None:
                raise ValueError('Belief reanalysis requires a recorded public planning anchor')
            policy.begin_combat(start, trajectory.transitions[0].observation)
        elif start is not None:
            # An explicitly selected older teacher may refresh policy targets,
            # but must not discard the original public planning provenance.
            policy.planning_start, policy.planning_ends = start, dict(ends)
        for index, transition in enumerate(trajectory.transitions):
            if cancel is not None and cancel.is_set():
                report['status'] = 'interrupted'
                break
            policy.choose(transition.observation)
            # Reanalysis follows the recorded behavior, not its newly suggested
            # action. Only policy targets change; realized returns stay original.
            if policy.needs_combat_reveals:
                policy.observe_reveals(data['planning']['reveals'][index])
            policy.observe_transition(transition.observation, transition.action,
                                      transition.execution, ends.get(index, transition.successor)
                                      if search.uses_belief else transition.successor)
        if report['status'] == 'interrupted':
            break
        for key in ('trajectory', 'training'):
            publish(_artifact(output, row[key]), _artifact(source_path.parent, row[key]).read_bytes())
        row['targets'], row['targets_sha256'] = _targets(output, row, policy, 'train')
        row['search'] = policy.summary()
        report['episodes'].append(row)
    report['total_seconds'] = time.perf_counter() - started
    report['target_refresh'] = _aggregate_search(report['episodes'])
    path = output / 'search.json'
    publish(path, _json(report))
    from game.agent.tracking import report_progress
    report_progress(path, report)
    return path, report
