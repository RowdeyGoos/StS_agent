"""Developed inventories retain public anchors, case pairing and worker semantics."""
from dataclasses import replace
import gzip
import json
from pathlib import Path

import pytest

from game.agent.contracts.planning import StartingCard, to_dict
from game.agent.headless import HeadlessAdapter
from game.agent.search import SearchConfig
from game.agent.search.direct import DirectCombatBelief
from game.agent.search.belief import BeliefBudget
from game.agent.search.public_keys import public_key
from game.agent.input_views import planning_view
from game.agent.training.scenarios import Scenario
from game.agent.training.search_benchmark import SCHEMA, SearchBenchmark
from game.agent.training.search_run import run_search, _load_search_targets, _planning_trace
from game.agent.recording import load_trajectory
from .test_search_training import checkpoint, cpu_threads


def declaration():
    start = Scenario('overgrowth_vantom', 'controlled').planning_start()
    return dict(schema=SCHEMA, name='fixture', scenarios=[
        dict(id='block', deck_profile='block', role='challenge',
             start=to_dict(replace(start, deck=(StartingCard('impervious', 1), StartingCard('body_slam', 1)),
                                   potions=('block_potion', None, None)))),
        dict(id='draw', deck_profile='draw', role='control',
             start=to_dict(replace(start, deck=(StartingCard('pommel_strike', 1), StartingCard('strike', 0)),
                                   potions=(None, None, None))))])


def manifest(tmp_path):
    path = tmp_path / 'benchmark.json'
    path.write_text(json.dumps(declaration()))
    return path


@pytest.mark.parametrize('mutation', ['seed', 'private', 'duplicate', 'catalog', 'upgrade', 'ambiguous'])
def test_rejects_private_ambiguous_or_invalid_inventory(tmp_path, mutation):
    value = declaration()
    row = value['scenarios'][0]
    if mutation == 'seed':
        value['seed'] = 4
    elif mutation == 'private':
        row['start']['rng'] = 4
    elif mutation == 'duplicate':
        value['scenarios'][1]['id'] = row['id']
    elif mutation == 'catalog':
        row['start']['card_catalog'] = 'changed'
    elif mutation == 'upgrade':
        row['start']['deck'][0]['upgrade_level'] = -1
    path = tmp_path / 'invalid.json'
    text = json.dumps(value)
    if mutation == 'ambiguous':
        text = text.replace('"name": "fixture"', '"name": "fixture", "name": "other"')
    path.write_text(text)
    with pytest.raises(ValueError):
        SearchBenchmark.load(path)


def test_frozen_developed_population_has_sampleable_public_openings():
    path = Path(__file__).resolve().parents[2] / 'configs/training/search_developed_decks.json'
    benchmark = SearchBenchmark.load(path)
    assert len(benchmark.scenarios) == 12
    assert {s.deck_profile for s in benchmark.scenarios} == {'draw_order', 'block_conversion', 'strength', 'exhaust_draw'}
    for index, scenario in enumerate(benchmark.scenarios):
        run = scenario.make(41 + index)
        original = run.snapshot()
        opening = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
        belief = DirectCombatBelief(scenario.start, opening, seed=7, budget=BeliefBudget(2, 1024, 10))
        _, simulated = belief.sample(19)
        assert public_key(simulated) == public_key(planning_view(opening))
        assert run.snapshot() == original
        assert len(scenario.start.deck) >= 14
        assert sum(c.upgrade_level > 0 for c in scenario.start.deck) >= 2


def test_serial_and_parallel_use_exact_inventory_anchor_and_balanced_pairing(checkpoint, tmp_path):
    source = manifest(tmp_path)
    reports = []
    for workers in (1, 2):
        path, report = run_search(checkpoint=checkpoint, output_dir=tmp_path / f'run{workers}',
            benchmark_path=source, search=SearchConfig(model_version='direct_belief_v1',
                simulations=4, time_limit=20, belief_particles=2), cases=2, max_decisions=2, workers=workers)
        assert report['status'] == 'complete', report
        assert report['benchmark_identity'] == SearchBenchmark.load(source).identity
        assert json.loads((path.parent / 'search-plan.json').read_text())['benchmark'] == declaration()
        starts = {r['id']: r['start'] for r in declaration()['scenarios']}
        for scenario_id in starts:
            rows = [r for r in report['episodes'] if r['scenario_id'] == scenario_id]
            assert len(rows) == 3
            assert len({r['case_id'] for r in rows}) == len({r['source_group'] for r in rows}) == 1
            openings = []
            for row in rows:
                trajectory = load_trajectory(path.parent / row['trajectory'], split='validation')
                openings.append(trajectory.transitions[0].observation)
                if row['policy'] != 'network':
                    data = _load_search_targets(path, report, row, trajectory, report['planning_view'])
                    start, ends = _planning_trace(data, trajectory, row)
                    assert to_dict(start) == starts[scenario_id]
                    assert row['search']['searched'] > 0
                    assert set(row['search']['fallbacks']) <= {'forced_action'}
            assert openings[0] == openings[1] == openings[2]
        assert report['benchmark_breakdown']['deck_profile']['block']['summary']['network']['planned'] == 1
        from game.agent.tracking.records import evaluations
        assert all(r['population']['benchmark'] == report['benchmark_identity'] for r in evaluations(report))
        reports.append(report)
    def outcomes(report):
        return [(r['scenario_id'], r['policy'], r['status'], r['task_return'], r['combat'],
                 r.get('search', {}).get('simulations')) for r in report['episodes']]
    assert outcomes(reports[0]) == outcomes(reports[1])


@pytest.mark.parametrize('kwargs', [dict(cases=1), dict(split='validation', collect=True),
                                    dict(act1=True), dict(search=SearchConfig())])
def test_invalid_benchmark_experiment_fails_before_artifacts(checkpoint, tmp_path, kwargs):
    settings = dict(checkpoint=checkpoint, output_dir=tmp_path / 'output', benchmark_path=manifest(tmp_path),
                    cases=2, search=SearchConfig(model_version='direct_belief_v1'))
    settings.update(kwargs)
    with pytest.raises(ValueError):
        run_search(**settings)
    assert not (tmp_path / 'output').exists()


@pytest.mark.parametrize('method', ['root', 'gumbel'])
def test_developed_training_round_retains_inventory_through_reanalysis(checkpoint, tmp_path, method):
    from game.agent.training.search_run import distill_search, reanalyse_search, load_search_corpus
    from game.agent.training.checkpoint import load_policy
    search = SearchConfig(method=method, model_version='direct_belief_v1', simulations=4,
                          leaf_rollout_steps=2, time_limit=20, belief_particles=2)
    path, report = run_search(checkpoint=checkpoint, output_dir=tmp_path / 'collect',
        benchmark_path=manifest(tmp_path), search=search, cases=4, split='train', collect=True,
        start_index=10, max_decisions=2, workers=2)
    assert report['status'] == 'complete'
    assert set(report['policies']) == {method}
    assert [r['case_index'] for r in report['episodes']] == [10, 11, 12, 13]
    assert 'paired_vs_network' not in report['benchmark_breakdown']['deck_profile']['block']
    corpus = load_search_corpus(path, load_policy(checkpoint))
    assert all(e.value_target is None for e in corpus.examples)
    _, fitted = distill_search(checkpoint=checkpoint, report_path=path, output_dir=tmp_path/'student', epochs=4)
    assert fitted['sample_presentations'] == 4 * len(corpus.examples)
    assert fitted['requested_epochs'] == 4
    refreshed, new = reanalyse_search(checkpoint=checkpoint, report_path=path,
        output_dir=tmp_path/'refreshed', search=search, max_episodes=2)
    for key in ('benchmark','benchmark_identity','evidence','allocation'):
        assert new[key] == report[key]
    assert set(new['policies']) == {method}
    assert new['selection']['episode_ids'] == [r['episode_id'] for r in report['episodes'][:2]]
    from game.agent.tracking.records import evaluations
    tracked = next(evaluations(new))
    assert tracked['policy_identity'] == new['policies'][method]
    assert tracked['population']['selection'] == new['selection']
    assert not any(key.startswith('eval/') for key in tracked['metrics'])
    assert [r['case_index'] for r in new['episodes']] == [10, 11]
    assert len(load_search_corpus(refreshed, load_policy(checkpoint)).examples) < len(corpus.examples)
    with pytest.raises(ValueError, match='balanced'):
        reanalyse_search(checkpoint=checkpoint, report_path=path,
            output_dir=tmp_path/'unbalanced', search=search, max_episodes=1)
    with pytest.raises(ValueError, match='training'):
        run_search(checkpoint=checkpoint, output_dir=tmp_path/'bad-test-collect',
            benchmark_path=manifest(tmp_path), search=search, cases=2, split='test', collect=True)


def test_declared_confirmation_and_critic_ablation_bind_frozen_configs(checkpoint, tmp_path):
    _, report = run_search(checkpoint=checkpoint, output_dir=tmp_path/'confirmation',
        benchmark_path=manifest(tmp_path), cases=2, split='test', max_decisions=1,
        search=SearchConfig(model_version='direct_belief_v1', simulations=4, leaf_rollout_steps=2,
                            time_limit=20, belief_particles=2), critic_baseline_simulations=8)
    assert report['status'] == 'complete' and report['split'] == 'test'
    assert set(report['policies']) == {'network','root','gumbel','gumbel_critic'}
    for name in ('root','gumbel_critic'):
        assert report['search_configs'][name]['leaf_rollout_steps'] == 0
        assert report['search_configs'][name]['simulations'] == 8
    assert report['summary']['gumbel']['search']['leaf_work']['steps'] > 0


def test_root_teacher_evaluates_against_the_same_network(checkpoint, tmp_path):
    _, report = run_search(checkpoint=checkpoint, output_dir=tmp_path/'root-only',
        benchmark_path=manifest(tmp_path), cases=2, max_decisions=1,
        search=SearchConfig(method='root', model_version='direct_belief_v1', simulations=4,
                            time_limit=20, belief_particles=2))
    assert report['status'] == 'complete'
    assert set(report['policies']) == {'network','root'}
    assert set(report['paired_vs_network']) == {'root'}
