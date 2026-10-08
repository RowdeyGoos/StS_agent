"""Matched combat comparisons over campaign-derived frozen starts."""
from dataclasses import asdict, dataclass, replace
import hashlib
from pathlib import Path
import time
import uuid

from game.agent.action_policy import ALL_LEGAL
from game.agent.provenance import implementation
from game.agent.runner import RunCancelled, prepare_directories
from .benchmark_suite import data
from .combat_corpus import CombatCorpus, coverage
from .comparison import paired, summarize
from .config import TrainingConfig
from .evaluation import BaselineCase, _episode
from .rewards import RewardSpec, strict_json


@dataclass(frozen=True, slots=True)
class FrozenCombatCase(BaselineCase):
    case_id: str


class CorpusEvaluator:
    """Per-worker models and corpus registry; every game gets a new restore."""
    def __init__(self, settings, checkpoints, policies, source):
        from .checkpoint import load_policy
        self.corpus = CombatCorpus(settings['path'], expected=settings['identity'])
        self.reward = RewardSpec.from_dict(settings['reward'])
        self.policies = policies
        self.identity = implementation()
        if asdict(self.identity) != source:
            raise ValueError('Combat evaluator implementation changed')
        self.models = {}
        for name, (path, sha, task) in checkpoints.items():
            model = load_policy(path, expected_sha256=sha, task=task)
            if model.identity != policies[name]:
                raise ValueError('Combat comparison checkpoint changed')
            self.models[name] = model

    def run(self, config, episode, policy, output, private, cancel=None):
        row = self.corpus.cases[config.case_id]
        model = self.models.get(policy)
        training = TrainingConfig(reward=self.reward,
            action_policy=model.model.action_policy if model else ALL_LEGAL)
        result = _episode(config, policy, replace(self.identity, policy=self.policies[policy]),
            Path(output), Path(private), training, chooser=model,
            engine_factory=lambda _: self.corpus.restore(config.case_id, split=config.split),
            scenario_set=self.corpus.identity, cancel=cancel, episode_id=episode,
            expected_start=row['public_state_sha256'], evidence='headless_rollout')
        result.update(case_id=config.case_id, source_group=row['source_group'],
                      start_sha256=self.corpus.registry[config.case_id]['snapshot_sha256'])
        return result


def evaluate_corpus(*, corpus_path, output_dir, checkpoints=None, split='validation',
                    max_decisions=512, time_limit_seconds=120., workers=1, cancel=None,
                    start_kind='opening'):
    from .checkpoint import load_policy, publish, runtime
    from .env import CombatTrainingEnv
    from .evaluation_workers import evaluate_parallel, settings
    execution = settings(workers)
    if split not in ('validation', 'test'):
        raise ValueError('Combat benchmark uses validation or held-out test cases')
    if start_kind not in ('opening', 'continuation', 'all'):
        raise ValueError('Choose opening, continuation or all combat starts')
    if type(max_decisions) is not int or not 1 <= max_decisions <= 4096:
        raise ValueError('Choose 1–4096 evaluation decisions per combat')
    with CombatTrainingEnv(max_decisions=max_decisions, time_limit_seconds=time_limit_seconds):
        pass
    corpus = CombatCorpus(corpus_path)
    cases = [r for r in corpus.split(split) if start_kind == 'all' or r['start_kind'] == start_kind]
    if not cases:
        raise ValueError('No combat cases in requested evaluation split')
    checkpoints = {} if checkpoints is None else checkpoints
    if (type(checkpoints) is not dict or len(checkpoints) > 8 or any(
            type(n) is not str or not n or len(n) > 64 or n in ('heuristic', 'random_legal')
            for n in checkpoints)):
        raise ValueError('Choose up to eight distinct named checkpoint comparisons')
    source = asdict(implementation())
    policies = {'heuristic': source['policy'], 'random_legal': 'random_legal_v1:' + source['build']}
    metadata, bundles = {}, {}
    for name, path in checkpoints.items():
        path = Path(path).resolve()
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        model = load_policy(path, expected_sha256=sha)
        # Only the actor is used. Critics/objectives from Act 1 checkpoints do
        # not become combat-value estimates or redefine benchmark wins.
        policies[name] = model.identity
        bundles[name] = (str(path), sha, model.reward_spec.task)
        metadata[name] = {'identity': model.identity, 'sha256': sha,
            'training_reward': model.reward_spec.to_dict(), 'action_policy': model.model.action_policy}
    reward = RewardSpec({'combat_win': 1., 'win_hp_fraction': .1})
    limits = {'max_decisions': max_decisions, 'time_limit_seconds': time_limit_seconds}
    binding = {'schema': 'sts_combat_corpus_test_lock_v2', 'corpus': corpus.identity, 'start_kind': start_kind,
               'policies': policies, 'checkpoints': metadata, 'reward': reward.to_dict(), 'limits': limits}
    lock = corpus.path.parent / 'test-opened.json'
    search_lock = corpus.path.parent / 'search-test-opened.json'
    if split == 'validation' and (lock.exists() or search_lock.exists()):
        raise ValueError('Development benchmark is closed after this corpus test was opened')
    if split == 'test' and search_lock.exists():
        raise ValueError('Held-out corpus is already locked to a search experiment')
    if split == 'test' and lock.exists() and strict_json(lock.read_bytes()) != binding:
        raise ValueError('Held-out corpus is already locked to different checkpoints or limits')
    output = Path(output_dir).resolve()
    output, private = prepare_directories(output, output.with_name(output.name + '-private'))
    path = output / 'combat-benchmark.json'
    rows, configs = [], []
    for case in cases:
        policy_seed = int.from_bytes(hashlib.sha256(case['case_id'].encode()).digest()[:8], 'big')
        for name in policies:
            rows.append({**case, 'episode_id': uuid.uuid4().hex, 'policy': name,
                         'status': 'unattempted', 'steps': 0, 'combat': None, 'failure': None,
                         'potion_use_actions': 0, 'task_return': 0.})
            configs.append(FrozenCombatCase(case['encounter'], split, 0, policy_seed,
                           max_decisions, time_limit_seconds, case['case_id']))
    report = {'schema': 'sts_combat_corpus_comparison_v2', 'status': 'running', 'start_kind': start_kind,
        'split': split, 'corpus': corpus.identity, 'implementation': source, 'runtime': runtime(),
        'policies': policies, 'checkpoints': metadata, 'episodes': rows, 'limits': limits,
        'reward_spec': reward.to_dict(), 'execution': execution, 'evidence': 'headless_rollout',
        'coverage': coverage(cases)[split], 'corpus_coverage': corpus.report['coverage'][split],
        'interpretation': 'Win rates use all planned fights. Uncertainty groups fights by source campaign. '
            'HP on wins is conditional on winning; net HP includes cleanup healing. '
            'This measures the selected frozen start population, not Act 1 completion. '
            'Only opening starts measure whole fights; continuation results are tactical diagnostics.'}
    # Publish the complete evaluation plan and freeze test identities before any
    # private test snapshot can be restored. Games are never retried.
    publish(output / 'combat-plan.json', data(report))
    if split == 'test':
        try:
            publish(lock, data(binding))
        except FileExistsError:
            if strict_json(lock.read_bytes()) != binding:
                raise ValueError('Held-out corpus was concurrently locked to another comparison')
    combat = {'path': str(corpus.path), 'identity': corpus.identity, 'reward': reward.to_dict()}
    started = time.perf_counter()
    try:
        if cancel is not None and cancel.is_set():
            raise RunCancelled('Combat evaluation cancelled')
        if workers > 1:
            outcome = evaluate_parallel(rows, configs, checkpoints=bundles, policies=policies,
                source=source, output=output, private=private, workers=workers, cancel=cancel, combat=combat)
            report.update(outcome)
        else:
            owner = CorpusEvaluator(combat, bundles, policies, source)
            report['status'] = 'complete'
            for row, config in zip(rows, configs):
                if cancel is not None and cancel.is_set():
                    raise RunCancelled('Combat evaluation cancelled')
                result = owner.run(config, row['episode_id'], row['policy'], output, private, cancel)
                row.update(result)
                if row['status'] not in ('terminated', 'truncated'):
                    report.update(status=row['status'], failure=row['failure'])
                    break
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='interrupted' if isinstance(error, (RunCancelled, KeyboardInterrupt)) else 'failed',
                      failure=type(error).__name__)
    report.update(summarize(rows, policies))
    for field in ('encounter', 'region', 'room_kind', 'start_kind', 'threat', 'hp_band'):
        report['by_' + field] = {name: summarize([r for r in rows if r[field] == name], policies)
                                for name in sorted({r[field] for r in rows})}
    report['by_potion_availability'] = {name: summarize([r for r in rows if bool(r['potions']) == present], policies)
        for name, present in (('available', True), ('empty', False)) if any(bool(r['potions']) == present for r in rows)}
    report['paired_checkpoints'] = {name: {base: paired(
        [r for r in rows if r['policy'] == name], [r for r in rows if r['policy'] == base],
        baseline_name=base) for base in checkpoints if base != name} for name in checkpoints}
    report['total_seconds'] = time.perf_counter() - started
    publish(path, data(report))
    from game.agent.tracking import report_progress
    report_progress(path, report)
    return path, report
