"""Frozen, witnessed-win diagnostics alongside the natural combat population.

A witness proves a legal win for this frozen realization. It neither proves a
robust win over hidden draws nor labels failed attempts as impossible fights.
Qualification is validation-only, with whole-campaign splits inherited from
the corpus. These files are not a training source.
"""
from dataclasses import asdict
import hashlib
from pathlib import Path

from game.agent.headless import HeadlessAdapter
from .benchmark_suite import data, digest
from .combat_corpus import CombatCorpus, public_digest, _read
from .comparison import won, summarize
from .records import load_training_episode

SCHEMA = 'sts_combat_diagnostics_v1'


def _attempts(rows):
    return [dict(episode_id=r['episode_id'], policy=r['policy'], status=r['status'],
                 outcome=(r.get('combat') or {}).get('outcome'), cutoff=(r.get('run_outcome') or {}).get('reason'))
            for r in rows]


def _sibling(directory, name):
    if type(name) is not str or Path(name).name != name:
        raise ValueError('Expected a sibling diagnostic artifact')
    path = directory / name
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing diagnostic artifact')
    return path


def verify_witness(corpus, row, directory, *, replay=True):
    """Independently replay advertised actions, with no policy access to state."""
    if not won(row):
        raise ValueError('A witness must be a completed victory')
    case = corpus.cases[row['case_id']]
    if case['split'] != 'validation' or case['start_kind'] != 'opening':
        raise ValueError('Witnesses require validation opening fights')
    path = _sibling(directory, row['trajectory'])
    sidecar = _sibling(directory, row['training'])
    episode = load_training_episode(path, sidecar, split='validation')
    trajectory = episode.trajectory
    if (not episode.ending.terminated or episode.ending.combat.outcome != 'victory'
            or asdict(episode.ending.combat) != row['combat']
            or trajectory.metadata.policy != row['policy_identity']
            or public_digest(trajectory.initial) != case['public_state_sha256']):
        raise ValueError('Winning attempt disagrees with its public trace or frozen start')
    if replay:
        # This verifier owns the private replay. The portfolio chose every
        # recorded action from public observations before qualification began.
        adapter = HeadlessAdapter(corpus.restore(case['case_id'], split='validation'), decision_profile='full_run_v2')
        for transition in trajectory.transitions:
            frame = adapter.observe()
            if not hasattr(frame, 'decision') or frame.decision != transition.observation:
                raise ValueError('Witness replay public observation mismatch')
            if transition.action not in frame.decision.candidates:
                raise ValueError('Witness action was not advertised')
            report = adapter.step(frame.binding, transition.action.ref)
            if report.status != 'reconciled':
                raise ValueError('Witness action did not reconcile')
        if asdict(adapter.combat_summary) != row['combat'] or adapter.combat_completion.result != 'victory':
            raise ValueError('Witness replay did not complete the recorded victory')
    return dict(episode_id=row['episode_id'], policy=row['policy'],
        trajectory=row['trajectory'], trajectory_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        training=row['training'], training_sha256=hashlib.sha256(sidecar.read_bytes()).hexdigest())


def qualify_comparison(*, corpus_path, comparison_path):
    """Freeze diagnostics from a portfolio planned before any attempt ran."""
    from .checkpoint import publish
    corpus = CombatCorpus(corpus_path)
    path = Path(comparison_path).resolve()
    report = _read(path)
    plan = _read(path.parent / 'combat-plan.json')
    if (report.get('schema') != 'sts_combat_corpus_comparison_v2' or report.get('split') != 'validation'
            or report.get('start_kind') != 'opening' or report.get('corpus') != corpus.identity
            or report.get('status') != 'complete'):
        raise ValueError('Qualification requires a complete validation opening comparison')
    for key in ('policies', 'checkpoints', 'limits', 'corpus', 'implementation', 'search_configs'):
        if report.get(key) != plan.get(key):
            raise ValueError('Qualification portfolio changed after planning')
    planned = [(r['case_id'], r['source_group'], r['policy'], r['episode_id']) for r in plan['episodes']]
    actual = [(r['case_id'], r['source_group'], r['policy'], r['episode_id']) for r in report['episodes']]
    cases = [r for r in corpus.split('validation') if r['start_kind'] == 'opening']
    if (planned != actual or len(set(planned)) != len(planned)
            or {(r[0], r[2]) for r in planned} != {(r['case_id'], p) for r in cases for p in report['policies']}
            or len(planned) != len(cases) * len(report['policies'])):
        raise ValueError('Qualification must retain every planned case and attempt')
    labels = []
    for case in cases:
        attempts = [r for r in report['episodes'] if r['case_id'] == case['case_id']]
        winners = [r for r in attempts if won(r)]
        witness = None
        if winners:
            first = winners[0]
            witness = verify_witness(corpus, dict(first, policy_identity=report['policies'][first['policy']]), path.parent)
        labels.append(dict(case_id=case['case_id'], source_group=case['source_group'],
            encounter=case['encounter'], region=case['region'], room_kind=case['room_kind'],
            label='witnessed_win' if witness else 'unresolved', witness=witness,
            attempts=_attempts(attempts)))
    value = dict(schema=SCHEMA, status='complete', corpus=corpus.identity, split='validation',
        comparison=path.name, comparison_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        plan_sha256=hashlib.sha256((path.parent / 'combat-plan.json').read_bytes()).hexdigest(),
        policies=report['policies'], limits=report['limits'], cases=labels,
        counts=dict(natural=len(labels), witnessed=sum(r['witness'] is not None for r in labels),
                    unresolved=sum(r['witness'] is None for r in labels)),
        interpretation='A replay-verified public-policy win for one frozen realization, not a probability of winning. '
            'Unresolved means no recorded winner under this portfolio and budget, never proven impossible. '
            'Report natural-population results alongside this portfolio-selected diagnostic subset. '
            'Qualifying policies are not an independent test of the subset they selected.')
    destination = path.parent / 'combat-diagnostics.json'
    publish(destination, data(value))
    return destination, value


def build_diagnostics(*, corpus_path, output_dir, checkpoints=None, search_configs=None,
                      max_decisions=512, time_limit_seconds=600., workers=1, cancel=None):
    from .combat_benchmark import evaluate_corpus
    path, report = evaluate_corpus(corpus_path=corpus_path, output_dir=output_dir,
        checkpoints=checkpoints, search_configs=search_configs, split='validation',
        max_decisions=max_decisions, time_limit_seconds=time_limit_seconds, workers=workers, cancel=cancel)
    if report['status'] != 'complete':
        # All attempts remain in the comparison. Never publish a partial
        # qualification as a finished validation population.
        return path, report
    return qualify_comparison(corpus_path=corpus_path, comparison_path=path)


class CombatDiagnostics:
    def __init__(self, path, *, corpus):
        self.path = Path(path).resolve()
        self.report = value = _read(self.path)
        if (value.get('schema') != SCHEMA or value.get('corpus') != corpus.identity
                or value.get('split') != 'validation' or value.get('status') != 'complete'):
            raise ValueError('Diagnostics require their original validation corpus')
        self.identity = SCHEMA + ':' + digest(value)
        comparison = _read(_sibling(self.path.parent, value['comparison']), expected_sha=value['comparison_sha256'])
        plan = _read(self.path.parent / 'combat-plan.json', expected_sha=value['plan_sha256'])
        if (comparison.get('status') != 'complete' or comparison.get('corpus') != corpus.identity
                or comparison.get('split') != 'validation' or comparison.get('start_kind') != 'opening'
                or any(value.get(k) != comparison.get(k) or plan.get(k) != comparison.get(k)
                       for k in ('policies', 'limits', 'corpus'))):
            raise ValueError('Diagnostic qualification provenance changed')
        self.cases = {r['case_id']: r for r in value['cases']}
        expected = {r['case_id'] for r in corpus.split('validation') if r['start_kind'] == 'opening'}
        if len(self.cases) != len(value['cases']) or set(self.cases) != expected:
            raise ValueError('Diagnostic population changed')
        for key, row in self.cases.items():
            attempts = [r for r in comparison['episodes'] if r['case_id'] == key]
            winners = [r for r in attempts if won(r)]
            if (any(row[k] != corpus.cases[key][k] for k in ('source_group', 'encounter', 'region', 'room_kind'))
                    or row['label'] != ('witnessed_win' if winners else 'unresolved')):
                raise ValueError('Diagnostic classification changed')
            if row['attempts'] != _attempts(attempts):
                raise ValueError('Diagnostic attempts changed')
            if winners:
                first = winners[0]
                verified = verify_witness(corpus, dict(first, policy_identity=comparison['policies'][first['policy']]),
                                           self.path.parent, replay=False)
                if row['witness'] != verified:
                    raise ValueError('Diagnostic witness changed')
            elif row['witness'] is not None:
                raise ValueError('Unresolved case has a fabricated witness')
        counts = dict(natural=len(self.cases), witnessed=sum(r['witness'] is not None for r in self.cases.values()),
                      unresolved=sum(r['witness'] is None for r in self.cases.values()))
        if value['counts'] != counts:
            raise ValueError('Diagnostic counts changed')

    def require_population(self, cases, split):
        if split != 'validation' or {r['case_id'] for r in cases} != set(self.cases):
            raise ValueError('Comparison must retain the full diagnostic validation population')

    def summarize(self, rows, policies):
        from .comparison import summary, paired
        result = {}
        for label in ('witnessed_win', 'unresolved'):
            keys = {k for k, r in self.cases.items() if r['label'] == label}
            groups = {p: [r for r in rows if r['case_id'] in keys and r['policy'] == p] for p in policies}
            baseline = 'heuristic' if 'heuristic' in policies else 'network'
            result[label] = (dict(summary={p: summary(v) for p, v in groups.items()},
                paired={p: paired(v, groups[baseline], baseline_name=baseline)
                        for p, v in groups.items() if p != baseline}) if keys else None)
        return result
