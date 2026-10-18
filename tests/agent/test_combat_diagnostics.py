"""Frozen qualification, exact winning replays and unresolved denominators."""
import json
from pathlib import Path
import pytest
pytest.importorskip('gymnasium')
pytest.importorskip('torch')

from game.agent.headless import HeadlessAdapter
from game.agent.search.belief import BeliefBudget
from game.agent.search.campaign import CampaignCombatBelief
from game.agent.training.benchmark_suite import data
from game.agent.training.combat_corpus import CorpusConfig, CombatCorpus, build_corpus
from game.agent.training.combat_diagnostics import build_diagnostics, CombatDiagnostics, qualify_comparison
from game.agent.training.combat_benchmark import evaluate_corpus
from .test_search_training import checkpoint
from .test_training_model import cpu_threads


@pytest.fixture(scope='module')
def corpus(tmp_path_factory):
    directory = tmp_path_factory.mktemp('diagnostic-corpus')
    path, report = build_corpus(directory / 'corpus', CorpusConfig(1, 1, 1,
        max_decisions=40, capture_turns=2, record_planning=True))
    assert report['status'] == 'complete'
    return CombatCorpus(path)


def test_opening_and_continuation_receipts_rebase_without_private_history(corpus):
    rows = corpus.split('validation')
    assert any(r['start_kind'] == 'continuation' for r in rows)
    for row in rows[:5]:
        anchor = corpus.planning_start(row['case_id'], split='validation')
        assert anchor is not None
        current = HeadlessAdapter(corpus.restore(row['case_id'], split='validation'),
                                 decision_profile='full_run_v2').observe().decision
        belief = CampaignCombatBelief(anchor, current, seed=5, budget=BeliefBudget(1, 128, 5))
        assert belief.recover().reason is None
    row = rows[0]
    with pytest.raises(ValueError, match='another split'):
        corpus.planning_start(row['case_id'], split='train')
    path = corpus.path.parent / (row['case_id'] + '.planning.json')
    original = path.read_bytes()
    try:
        path.write_bytes(original + b' ')
        with pytest.raises(ValueError, match='digest'):
            corpus.planning_start(row['case_id'], split='validation')
    finally:
        path.write_bytes(original)


def test_winning_witnesses_replay_and_new_evaluation_keeps_natural_denominator(corpus, tmp_path, monkeypatch):
    forbidden = {r['case_id'] + '.start.json' for r in corpus.split('test')}
    original = Path.read_bytes
    def read(path):
        assert path.name not in forbidden
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', read)
    path, report = build_diagnostics(corpus_path=corpus.path, output_dir=tmp_path / 'qualification',
                                     max_decisions=128, time_limit_seconds=30, workers=1)
    assert report['schema'] == 'sts_combat_diagnostics_v1'
    assert report['counts']['witnessed'] > 0
    diagnostics = CombatDiagnostics(path, corpus=corpus)
    cases = [r for r in corpus.split('validation') if r['start_kind'] == 'opening']
    assert report['counts']['natural'] == len(cases)
    assert all(len(r['attempts']) == 2 for r in report['cases'])
    _, compared = evaluate_corpus(corpus_path=corpus.path, output_dir=tmp_path / 'comparison',
        diagnostics_path=path, max_decisions=1, time_limit_seconds=30)
    assert compared['summary']['heuristic']['planned'] == len(cases)
    assert compared['summary']['heuristic']['cutoffs'] > 0
    assert compared['diagnostic_summary']['witnessed_win']['summary']['heuristic']['planned'] == report['counts']['witnessed']
    with pytest.raises(ValueError, match='full diagnostic'):
        diagnostics.require_population(cases[:1], 'test')
    witness = next(r['witness'] for r in report['cases'] if r['witness'])
    trace = path.parent / witness['trajectory']
    raw = trace.read_bytes()
    try:
        trace.write_bytes(raw + b'changed')
        with pytest.raises((ValueError, OSError, EOFError)):
            CombatDiagnostics(path, corpus=corpus)
    finally:
        trace.write_bytes(raw)


def test_cutoffs_are_unresolved_and_cannot_be_relabelled_as_wins(corpus, tmp_path):
    path, report = build_diagnostics(corpus_path=corpus.path, output_dir=tmp_path / 'cutoffs',
        max_decisions=1, time_limit_seconds=30)
    assert report['counts']['witnessed'] == 0
    assert report['counts']['natural'] == report['counts']['unresolved']
    assert all(r['label'] == 'unresolved' and not r['witness'] for r in report['cases'])
    original = path.read_bytes()
    changed = json.loads(original)
    changed['counts']['witnessed'] = changed['counts']['natural']
    path.write_bytes(data(changed))
    with pytest.raises(ValueError, match='counts'):
        CombatDiagnostics(path, corpus=corpus)
    changed = json.loads(original)
    changed['cases'][0]['attempts'][0]['outcome'] = 'victory'
    path.write_bytes(data(changed))
    with pytest.raises(ValueError, match='attempts'):
        CombatDiagnostics(path, corpus=corpus)
    path.write_bytes(original)
    changed = json.loads(path.read_bytes())
    changed['cases'][0]['label'] = 'witnessed_win'
    path.write_bytes(data(changed))
    with pytest.raises(ValueError, match='classification'):
        CombatDiagnostics(path, corpus=corpus)


def test_qualification_requires_unchanged_predeclared_attempt_population(corpus, tmp_path):
    path, _ = evaluate_corpus(corpus_path=corpus.path, output_dir=tmp_path / 'comparison',
        max_decisions=1, time_limit_seconds=30)
    changed = json.loads(path.read_bytes())
    changed['episodes'].pop()
    path.write_bytes(data(changed))
    with pytest.raises(ValueError, match='every planned'):
        qualify_comparison(corpus_path=corpus.path, comparison_path=path)


def test_named_search_portfolio_and_parallel_campaign_corpus_evaluation(corpus, checkpoint, tmp_path):
    from game.agent.search import SearchConfig
    from game.agent.training.search_run import run_search
    config = SearchConfig(model_version='campaign_belief_v1', simulations=2, max_depth=4,
                          belief_particles=1, time_limit=10)
    _, report = evaluate_corpus(corpus_path=corpus.path, output_dir=tmp_path / 'portfolio',
        checkpoints={'actor': checkpoint, 'search': checkpoint}, search_configs={'search': config},
        max_decisions=2, time_limit_seconds=30, workers=2)
    assert report['status'] == 'complete', report
    searches = [r for r in report['episodes'] if r['policy'] == 'search']
    assert searches and all(r['targets'] and r['search']['searched'] > 0 for r in searches)
    with pytest.raises(ValueError, match='not search collection'):
        run_search(checkpoint=checkpoint, output_dir=tmp_path / 'rejected', corpus_path=corpus.path,
            search=config, collect=True, split='train')
    assert not (tmp_path / 'rejected').exists()


def test_corpus_search_selects_room_kinds_and_reports_balanced_rates(corpus, checkpoint, tmp_path):
    from game.agent.search import SearchConfig
    from game.agent.training.search_run import run_search
    config = SearchConfig(simulations=2, max_depth=4, belief_particles=1, time_limit=10)
    _, report = run_search(checkpoint=checkpoint, output_dir=tmp_path / 'combat-only', corpus_path=corpus.path,
        search=config, cases=2, max_decisions=2, time_limit_seconds=30, room_kinds=('combat',),
        include_root=False)
    assert report['status'] == 'complete', report
    assert report['room_kinds'] == ['combat'] and 'balanced' in report
    assert {r['room_kind'] for r in report['episodes']} == {'combat'}
    assert all(r['encounter'] == corpus.cases[r['source_case_id']]['encounter'] for r in report['episodes'])
    with pytest.raises(ValueError, match='No opening cases'):
        run_search(checkpoint=checkpoint, output_dir=tmp_path / 'bosses', corpus_path=corpus.path,
            search=config, cases=2, room_kinds=('boss',))
    with pytest.raises(ValueError, match='Room-kind selection'):
        run_search(checkpoint=checkpoint, output_dir=tmp_path / 'controlled', search=config, room_kinds=('boss',))
    with pytest.raises(ValueError, match='room kinds'):
        run_search(checkpoint=checkpoint, output_dir=tmp_path / 'invalid', corpus_path=corpus.path,
            search=config, room_kinds=('hallway',))
