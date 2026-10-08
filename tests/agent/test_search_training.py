"""Search data provenance, soft targets, truncation and existing worker integration."""
from dataclasses import replace
import gzip
import hashlib
import json

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('gymnasium')
from game.agent.search import SearchConfig
from game.agent.training.checkpoint import load_policy, save_checkpoint
from game.agent.training.learner import ImitationLearner, LearnerConfig
from game.agent.training.model import ActorCritic, Architecture, collate, log_probabilities
from game.agent.training.search_run import OBJECTIVE, run_search, load_search_corpus, distill_search, reanalyse_search
from .test_training_model import tiny_corpus, cpu_threads


@pytest.fixture
def checkpoint(tmp_path):
    corpus = replace(tiny_corpus(), reward_spec=OBJECTIVE)
    learner = ImitationLearner(ActorCritic(corpus.vocabulary, Architecture(24, 1), seed=7), corpus)
    path = tmp_path / 'teacher.sts-model'
    save_checkpoint(path, learner)
    return path


def collect(checkpoint, output, **kwargs):
    return run_search(checkpoint=checkpoint, output_dir=output,
        search=SearchConfig(simulations=4, time_limit=20, exploration=True),
        cases=1, split='train', collect=True, max_decisions=1, **kwargs)


def test_soft_cross_entropy_uses_the_full_distribution():
    corpus = tiny_corpus()
    example = corpus.examples[0]
    target = (.1, .2, .3, .4)
    corpus = replace(corpus, examples=(replace(example, policy_target=target),))
    model = ActorCritic(corpus.vocabulary, Architecture(24, 1), seed=7)
    batch = collate([example.state], vocabulary=corpus.vocabulary)
    with torch.no_grad():
        logits, _ = model(batch)
        expected = -(torch.tensor(target) * log_probabilities(logits, batch['mask'])[0]).sum().item()
    learner = ImitationLearner(model, corpus, LearnerConfig(batch_size=1))
    update = learner.step()
    assert update['imitation_loss'] == pytest.approx(expected)
    assert update['value_loss'] == 0


@pytest.mark.parametrize('target', [(0., 0., 0., 0.), (.2, .2, .2, .2), (1., -1., 1., 0.), (float('nan'), 0., 0., 0.)])
def test_invalid_soft_targets_reject(target):
    corpus = tiny_corpus()
    corpus = replace(corpus, examples=(replace(corpus.examples[0], policy_target=target),))
    with pytest.raises(ValueError, match='policy target'):
        ImitationLearner(ActorCritic(corpus.vocabulary, Architecture(24, 1)), corpus)


def test_collection_distillation_and_reanalysis_preserve_cutoffs(checkpoint, tmp_path):
    path, report = collect(checkpoint, tmp_path / 'collect')
    assert report['status'] == 'complete', report
    assert report['episodes'][0]['status'] == 'truncated'
    corpus = load_search_corpus(path, load_policy(checkpoint))
    assert corpus.examples and all(e.value_target is None for e in corpus.examples)
    assert all(sum(e.policy_target) == pytest.approx(1) for e in corpus.examples)
    distilled, training = distill_search(checkpoint=checkpoint, report_path=path,
        output_dir=tmp_path / 'student', updates=2)
    assert training['promotion'] == 'not_evaluated'
    assert training['updates'][-1]['value_loss'] == 0
    student = distilled.parent / 'final.sts-model'
    refreshed, report2 = reanalyse_search(checkpoint=student, report_path=path,
        output_dir=tmp_path / 'reanalysis', search=SearchConfig(simulations=4, time_limit=20))
    assert report2['status'] == 'complete'
    assert 'summary' not in report2 and 'paired_vs_network' not in report2
    assert report2['episodes'][0]['behavior_policy'] == report['policies']['gumbel']
    row, new = report['episodes'][0], report2['episodes'][0]
    assert (path.parent / row['trajectory']).read_bytes() == (refreshed.parent / new['trajectory']).read_bytes()
    assert (path.parent / row['training']).read_bytes() == (refreshed.parent / new['training']).read_bytes()
    assert all(e.value_target is None for e in load_search_corpus(refreshed, load_policy(student)).examples)
    from game.agent.tracking.records import evaluations
    metrics = list(evaluations(report2))[0]['metrics']
    assert not any(k.startswith('eval/') for k in metrics)


def test_completed_search_fight_gets_actual_return(checkpoint, tmp_path, monkeypatch):
    from .test_search import fixture
    from game.agent.training.scenarios import Scenario
    monkeypatch.setattr(Scenario, 'make', lambda self, seed: fixture(('strike', 'defend'), enemy_hp=1)[0])
    path, report = run_search(checkpoint=checkpoint, output_dir=tmp_path / 'won',
        search=SearchConfig(simulations=16, time_limit=20), cases=1, split='train', collect=True,
        max_decisions=20)
    assert report['episodes'][0]['combat']['outcome'] == 'victory', report
    corpus = load_search_corpus(path, load_policy(checkpoint))
    assert all(e.value_target == pytest.approx(report['episodes'][0]['task_return']) for e in corpus.examples)
    assert corpus.examples[0].value_target > 1
    from game.agent.training.search_run import audit_critic
    _, audit = audit_critic(checkpoint=checkpoint, report_path=path, output_path=tmp_path / 'audit.json',
                            positions=1, rollouts=2, depth=4)
    assert audit['summary']['positions'] == 1
    assert audit['summary']['rollout_completions'] + audit['summary']['rollout_cutoffs'] == 2
    assert audit['positions'][0]['completed_behavior_return'] == report['episodes'][0]['task_return']


def test_fresh_and_reanalysed_training_reports_preserve_bindings_and_exact_epochs(checkpoint, tmp_path):
    from game.agent.training.search_run import _search_corpora
    old, _ = collect(checkpoint, tmp_path/'old', start_index=4)
    refreshed, _ = reanalyse_search(checkpoint=checkpoint, report_path=old, output_dir=tmp_path/'refreshed',
        search=SearchConfig(simulations=4, time_limit=20), max_episodes=1)
    fresh, _ = collect(checkpoint, tmp_path/'fresh', start_index=8)
    corpus, sources = _search_corpora([fresh, refreshed], load_policy(checkpoint))
    assert corpus.episodes == 2 and len(sources) == 2
    assert sources[0]['report_sha256'] == hashlib.sha256(fresh.read_bytes()).hexdigest()
    _, report = distill_search(checkpoint=checkpoint, report_path=[fresh, refreshed],
        output_dir=tmp_path/'combined-student', epochs=4, seed=17)
    assert report['source_reports'] == sources
    assert report['sample_presentations'] == 4 * len(corpus.examples)
    assert report['episodes'] == 2
    for paths in ([old, refreshed], [fresh, fresh]):
        with pytest.raises(ValueError, match='duplicate source fight'):
            _search_corpora(paths, load_policy(checkpoint))


def test_combined_training_reports_reject_different_public_views(checkpoint, tmp_path, monkeypatch):
    from game.agent.training import search_run
    first, _ = collect(checkpoint, tmp_path/'first', start_index=4)
    second, _ = collect(checkpoint, tmp_path/'second', start_index=8)
    loader = search_run.load_search_corpus
    def changed(path, policy):
        corpus = loader(path, policy)
        return replace(corpus, input_view='detached_combat_history_cards_v1') if path == second else corpus
    monkeypatch.setattr(search_run, 'load_search_corpus', changed)
    with pytest.raises(ValueError, match='incompatible public views'):
        search_run._search_corpora([first, second], load_policy(checkpoint))


def test_target_teacher_binding_and_probability_integrity(checkpoint, tmp_path):
    path, report = collect(checkpoint, tmp_path / 'collect')
    target = path.parent / report['episodes'][0]['targets']
    original = json.loads(gzip.decompress(target.read_bytes()))
    for change in ('teacher', 'probabilities'):
        data = json.loads(json.dumps(original))
        if change == 'teacher':
            data['teacher'] = 'another_teacher'
        else:
            data['targets'][0]['probabilities'] = dict.fromkeys(data['targets'][0]['probabilities'], 0.)
        target.write_bytes(gzip.compress(json.dumps(data).encode(), mtime=0))
        report['episodes'][0]['targets_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
        path.write_text(json.dumps(report))
        with pytest.raises(ValueError, match='match|normalized'):
            load_search_corpus(path, load_policy(checkpoint))


def test_serial_and_parallel_use_frozen_search_and_distinct_tracking_modes(checkpoint, tmp_path):
    reports = []
    for workers in (1, 2):
        _, report = run_search(checkpoint=checkpoint, output_dir=tmp_path / f'eval{workers}',
            search=SearchConfig(simulations=4, time_limit=20), cases=1, max_decisions=1, workers=workers)
        assert report['status'] == 'complete', report
        reports.append(report)
    for first, second in zip(reports[0]['episodes'], reports[1]['episodes']):
        assert (first['status'], first['task_return']) == (second['status'], second['task_return'])
        if 'search' in first:
            assert first['search']['simulations'] == second['search']['simulations'] == 4
    from game.agent.tracking.records import evaluations
    rows = list(evaluations(reports[0]))
    assert {r['mode'] for r in rows} == {'greedy', 'search_root', 'search_gumbel'}
    assert len({r['population_id'] for r in rows}) == 3


def test_serial_failure_keeps_all_planned_rows(checkpoint, tmp_path, monkeypatch):
    from game.agent.training.search_run import SearchEvaluator
    def fail(*args, **kwargs):
        raise ValueError('controlled failure')
    monkeypatch.setattr(SearchEvaluator, 'run', fail)
    path, report = run_search(checkpoint=checkpoint, output_dir=tmp_path / 'failed', cases=2)
    assert report['status'] == 'failed'
    assert report['episodes'][0]['failure'] == 'ValueError'
    assert len(report['episodes']) == 6
    assert all(r['status'] == 'unattempted' for r in report['episodes'][1:])
    assert json.loads(path.read_text())['status'] == 'failed'


def test_direct_evaluation_parallel_workers_match_network_view_and_record_anchor(checkpoint, tmp_path):
    from game.agent.search.direct import VIEW, PlanningViewPolicy
    teacher = load_policy(checkpoint)
    path, report = run_search(checkpoint=checkpoint, output_dir=tmp_path / 'direct',
        search=SearchConfig(model_version='direct_belief_v1', simulations=4, time_limit=10,
                            belief_particles=2), cases=1, max_decisions=3, workers=2)
    assert report['status'] == 'complete', report
    assert report['planning_view'] == VIEW
    assert report['policies']['network'] == PlanningViewPolicy(teacher).identity
    assert report['checkpoint'] == teacher.identity
    for row in report['episodes']:
        assert row['status'] == 'truncated'
        if row['policy'] != 'network':
            assert row['search']['searched'] > 0
            target = json.loads(gzip.decompress((path.parent / row['targets']).read_bytes()))
            assert target['planning']['start']['provenance'] == 'declared_fresh_inventory'
            assert target['search']['model_version'] == 'direct_belief_v1'


def test_direct_campaign_path_still_fails_before_producing_artifacts(checkpoint, tmp_path):
    search = SearchConfig(model_version='direct_belief_v1')
    output = tmp_path / 'blocked-direct'
    with pytest.raises(ValueError, match='declared controlled'):
        run_search(checkpoint=checkpoint, output_dir=output, search=search, act1=True)
    assert not output.exists()


def test_controlled_underdocks_start_has_matching_region():
    from game.agent.training.scenarios import Scenario
    run = Scenario('underdocks_seapunk_weak', 'controlled').make(3)
    assert run.state.config.act == 'underdocks'


def test_belief_collection_and_reanalysis_retain_declared_public_anchor(checkpoint, tmp_path):
    search = SearchConfig(model_version='public_belief_v1', simulations=4, time_limit=20,
                          belief_particles=2, belief_seconds=10, exploration=True)
    path, report = run_search(checkpoint=checkpoint, output_dir=tmp_path / 'belief',
        search=search, cases=1, split='train', collect=True, max_decisions=2)
    assert report['status'] == 'complete', report
    row = report['episodes'][0]
    assert row['status'] == 'truncated'
    assert row['search']['searched'] > 0, row['search']
    data = json.loads(gzip.decompress((path.parent / row['targets']).read_bytes()))
    assert data['planning']['start']['provenance'] == 'declared_fresh_inventory'
    assert data['planning']['completions'] == {}
    assert 'seed' not in data['planning']['start']
    corpus = load_search_corpus(path, load_policy(checkpoint))
    assert corpus.examples and all(e.value_target is None for e in corpus.examples)
    refreshed, new = reanalyse_search(checkpoint=checkpoint, report_path=path,
        output_dir=tmp_path / 'belief-reanalysis', search=search)
    assert new['status'] == 'complete'
    assert new['episodes'][0]['search']['searched'] > 0
    target = json.loads(gzip.decompress((refreshed.parent / new['episodes'][0]['targets']).read_bytes()))
    assert target['planning'] == data['planning']
    assert (path.parent / row['training']).read_bytes() == (refreshed.parent / row['training']).read_bytes()


def test_belief_search_rejects_undeclared_campaign_or_corpus_starts(checkpoint, tmp_path):
    search = SearchConfig(model_version='public_belief_v1', simulations=4)
    for settings in ({'act1': True}, {'corpus_path': tmp_path / 'missing.json'}):
        with pytest.raises(ValueError, match='declared controlled'):
            run_search(checkpoint=checkpoint, output_dir=tmp_path / 'blocked', search=search,
                       cases=1, **settings)
    assert not (tmp_path / 'blocked').exists()


@pytest.mark.parametrize('encounter', ['dense_vegetation_event', 'hive_chomper', 'unknown'])
def test_belief_search_rejects_unsupported_entry_before_creating_artifacts(checkpoint, tmp_path, encounter):
    with pytest.raises(ValueError, match='registered ordinary Act 1'):
        run_search(checkpoint=checkpoint, output_dir=tmp_path / 'blocked', cases=1,
                   search=SearchConfig(model_version='public_belief_v1'), encounters=(encounter,))
    assert not (tmp_path / 'blocked').exists()


def test_underdocks_belief_collection_records_search_and_public_anchor(checkpoint, tmp_path):
    path, report = run_search(checkpoint=checkpoint, output_dir=tmp_path / 'underdocks',
        search=SearchConfig(model_version='public_belief_v1', simulations=4, time_limit=20,
                            belief_particles=1, belief_seconds=10),
        encounters=('underdocks_sewer_clam',), cases=1, split='train', collect=True, max_decisions=1)
    assert report['status'] == 'complete', report
    row = report['episodes'][0]
    assert row['search']['searched'] == 1
    target = json.loads(gzip.decompress((path.parent / row['targets']).read_bytes()))
    assert target['planning']['start']['encounter_id'] == 'underdocks_sewer_clam'
    assert target['search']['model_version'] == 'public_belief_v1'
    assert all(example.value_target is None for example in load_search_corpus(path, load_policy(checkpoint)).examples)


@pytest.mark.parametrize('model', ['public_belief_v1', 'direct_belief_v1'])
def test_belief_completion_supplement_binds_settlement_and_reanalysis(checkpoint, tmp_path, monkeypatch, model):
    from game.agent.training.scenarios import Scenario
    from .test_belief import setup, actual
    declared = setup(deck=('defend',), hp=1, relics=(('burning_blood', 0),))
    monkeypatch.setattr(Scenario, 'planning_start', lambda self: declared)
    monkeypatch.setattr(Scenario, 'make', lambda self, seed: actual(declared, seed=seed)[0])
    search = SearchConfig(model_version=model, simulations=4, time_limit=20,
                          belief_particles=2, exploration=True)
    path, report = run_search(checkpoint=checkpoint, output_dir=tmp_path / 'completed-belief',
        search=search, cases=1, split='train', collect=True, max_decisions=20)
    row = report['episodes'][0]
    assert row['status'] == 'terminated' and row['combat']['outcome'] == 'defeat', report
    data = json.loads(gzip.decompress((path.parent / row['targets']).read_bytes()))
    assert list(data['planning']['completions']) == [str(row['steps'] - 1)]
    assert next(iter(data['planning']['completions'].values()))['result'] == 'defeat'
    corpus = load_search_corpus(path, load_policy(checkpoint))
    assert all(e.value_target == 0 for e in corpus.examples)
    refreshed, new = reanalyse_search(checkpoint=checkpoint, report_path=path,
        output_dir=tmp_path / 'completed-reanalysis', search=search)
    target = json.loads(gzip.decompress((refreshed.parent / new['episodes'][0]['targets']).read_bytes()))
    assert target['planning'] == data['planning']
    assert new['episodes'][0]['behavior_policy'] == report['policies']['gumbel']
    # The supplement is bound to the actual recorded outcome, not a synthetic
    # terminal value or the new teacher's suggested actions.
    last = next(iter(data['planning']['completions']))
    data['planning']['completions'][last]['result'] = 'victory'
    file = path.parent / row['targets']
    file.write_bytes(gzip.compress(json.dumps(data).encode(), mtime=0))
    row['targets_sha256'] = hashlib.sha256(file.read_bytes()).hexdigest()
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match='settled|completion'):
        load_search_corpus(path, load_policy(checkpoint))


def test_model_switch_keeps_public_planning_provenance_and_audit_does_not_switch_silently(checkpoint, tmp_path):
    from game.agent.training.search_run import audit_critic
    search = SearchConfig(model_version='public_belief_v1', simulations=4, time_limit=20,
                          belief_particles=2, exploration=True)
    path, report = run_search(checkpoint=checkpoint, output_dir=tmp_path / 'source-belief',
        search=search, cases=1, split='train', collect=True, max_decisions=1)
    assert report['status'] == 'complete'
    source = json.loads(gzip.decompress((path.parent / report['episodes'][0]['targets']).read_bytes()))
    _, audit = audit_critic(checkpoint=checkpoint, report_path=path, output_path=tmp_path / 'audit.json')
    assert audit['search']['model_version'] == 'public_belief_v1'
    assert audit['positions'] == []  # A truncated fight supplies no completed label.
    updated, result = reanalyse_search(checkpoint=checkpoint, report_path=path,
        output_dir=tmp_path / 'older-model-targets', search=replace(search, model_version='reconstruction_v1'))
    data = json.loads(gzip.decompress((updated.parent / result['episodes'][0]['targets']).read_bytes()))
    assert data['planning'] == source['planning']
    assert data['search']['model_version'] == 'reconstruction_v1'
def test_observed_collection_reanalysis_and_critic_replay_receipts(checkpoint, tmp_path, monkeypatch):
    from .test_observed_belief import fixture
    from game.agent.search.observed import MODEL
    from game.headless.run.snapshots import restore_run
    from game.agent.training.scenarios import Scenario
    from game.agent.training.search_run import audit_critic
    run, _, _, anchor = fixture(('strike', 'defend', 'defend', 'pillage', 'poor_sleep'), hp=20)
    snapshot = run.snapshot()
    monkeypatch.setattr(Scenario, 'planning_start', lambda self: anchor)
    monkeypatch.setattr(Scenario, 'make', lambda self, seed: restore_run(snapshot))
    config = SearchConfig(model_version=MODEL, simulations=4, time_limit=20,
                          belief_seconds=10, belief_particles=2, exploration=True)
    path, report = run_search(checkpoint=checkpoint, output_dir=tmp_path / 'observed',
        search=config, cases=1, max_decisions=80, split='train', collect=True)
    assert report['status'] == 'complete'
    assert report['episodes'][0]['status'] == 'terminated'
    data = json.loads(gzip.decompress((path.parent / report['episodes'][0]['targets']).read_bytes()))
    assert data['planning']['schema'] == 'sts_public_planning_trace_v2'
    assert any(data['planning']['reveals'])
    refreshed, rerun = reanalyse_search(checkpoint=checkpoint, report_path=path,
        output_dir=tmp_path / 'refreshed', search=config)
    assert set(rerun['target_refresh']['fallbacks']) <= {'forced_action'}
    assert load_search_corpus(refreshed, load_policy(checkpoint)).examples
    _, audit = audit_critic(checkpoint=checkpoint, report_path=path,
        output_path=tmp_path / 'critic.json', positions=2, rollouts=1, depth=32)
    assert len(audit['positions']) == 2
    assert all(p['search_fallback'] in (None, 'forced_action') for p in audit['positions'])
    with pytest.raises(ValueError, match='cannot convert'):
        reanalyse_search(checkpoint=checkpoint, report_path=path, output_dir=tmp_path / 'legacy',
                         search=SearchConfig(model_version='direct_belief_v1', simulations=4))
