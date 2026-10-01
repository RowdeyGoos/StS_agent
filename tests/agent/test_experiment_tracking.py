"""Local tracking is a faithful, recoverable view; it never owns the learner."""
import copy
import json
import os
from pathlib import Path
import zipfile
import warnings

import pytest

os.environ['MLFLOW_DISABLE_TELEMETRY'] = 'true'
os.environ['MLFLOW_DISABLE_AGENT_HINT'] = 'true'
pytest.importorskip('mlflow')

from game.agent.tracking import TrackingConfig, report_progress, tracking_session
from game.agent.tracking import records as r
from game.agent.tracking.store import TrackingStore
from game.cli.agent_track import import_reports


def checkpoint(path, resume, *, config=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'schema': 'sts_inference_bundle_v3', 'algorithm': 'ppo',
                'architecture': {'hidden_size': 16, 'message_layers': 1},
                'resume_state_sha256': resume, 'learner_config': config or {},
                'implementation': {'build': 'historical-source'}, 'feature_identity': 'features:1',
                'reward_spec': {'win': 1}, 'action_policy': 'commit_decisions_v1'}
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('manifest.json', json.dumps(manifest))
        z.writestr('weights.pt', b'Not a pickle: tracking must never load weights')
        z.comment = str(path).encode()  # Same state, different container digest.
    return r.digest(path)


def segment(root, name, *, start=0, initial='state0', final='state1', resumed=False):
    path = root/name/'ppo.json'
    first = checkpoint(path.parent/'initial.sts-model', initial)
    last = checkpoint(path.parent/'final.sts-model', final)
    report = {'schema': 'sts_ppo_report_v1', 'status': 'complete',
        'initial_sha256': first, 'final_sha256': last,
        'initialization': {'resumed': resumed}, 'start_decisions': start, 'start_iteration': start//10,
        'experiment': {'source': 'frozen-train', 'training': {'mode': 'combat'}, 'ppo': {'gamma': 1}},
        'runtime': {'python': '3.11'}, 'collection': {'workers': 8},
        'iterations': [{'iteration': start//10+1,
            'collection': {'steps': 10, 'seconds': 2., 'episodes': [
                {'status': 'terminated', 'combat': {'outcome': 'victory'}, 'steps': 10, 'task_return': 1.}]},
            'update': {'decisions': 10, 'status': 'updated', 'seconds': 1.,
                       'mean_update': {'entropy': .5, 'approx_kl': .01}}}],
        'summary': {'accepted_decisions': 10, 'trained_decisions': 10}, 'total_seconds': 4.}
    path.write_bytes(r.data(report))
    return path, report


@pytest.fixture
def store(tmp_path):
    with TrackingStore(tmp_path/'tracking', experiment='Tests') as value:
        yield value


def test_continuations_idempotency_and_forks(store, tmp_path):
    a, _ = segment(tmp_path, 'a')
    b, _ = segment(tmp_path, 'b', start=10, initial='state1', final='state2', resumed=True)
    c, _ = segment(tmp_path, 'c', start=10, initial='state1', final='fork', resumed=True)
    fresh, _ = segment(tmp_path, 'fresh')
    first = store.import_report(a)
    second = store.import_report(b)
    assert first['run_id'] == second['run_id']
    assert second['lineage'] == 'exact_resume'
    assert store.import_report(a)['status'] == 'unchanged'
    curve = store.client.get_metric_history(first['run_id'], 'ppo/entropy')
    assert [(m.step, m.value) for m in curve] == [(10, .5), (20, .5)]
    wall = store.client.get_metric_history(first['run_id'], 'system/cumulative_wall_seconds')
    assert [(m.step, m.value) for m in wall] == [(10, 4.), (20, 8.)]
    fork = store.import_report(c)
    assert fork['lineage'] == 'fork' and fork['run_id'] != first['run_id']
    assert store.import_report(fresh)['run_id'] not in (first['run_id'], fork['run_id'])


def test_reimports_preserve_user_notes_and_existing_inspector_link(store, tmp_path):
    first, _ = segment(tmp_path, 'first')
    second, _ = segment(tmp_path, 'second', start=10, initial='state1', final='state2', resumed=True)
    store.inspector_url = 'http://127.0.0.1:51002/'
    run = store.import_report(first)['run_id']
    notes = store.client.get_run(run).data.tags['mlflow.note.content']
    store.client.set_tag(run, 'mlflow.note.content', 'Hypothesis: improve potion use.\n\n'+notes+'\n\nResult: compare bosses.')
    store.inspector_url = None
    assert store.import_report(second)['run_id'] == run
    description = store.client.get_run(run).data.tags['mlflow.note.content']
    assert description.startswith('Hypothesis: improve potion use.')
    assert description.endswith('Result: compare bosses.')
    assert description.count('<!-- sts-tracking:start -->') == 1
    assert str(second) in description and str(first) not in description
    assert '[Open decision inspector](http://127.0.0.1:51002/)' in description
    store.inspector_url = 'http://127.0.0.1:51003/'
    store.import_report(first)  # Reimporting an older segment must not rewind its description.
    description = store.client.get_run(run).data.tags['mlflow.note.content']
    assert str(second) in description and str(first) not in description
    assert '51003' in description and '51002' not in description
    assert 'Charts use cumulative processed decisions' in description
    store.client.set_tag(run, 'mlflow.note.content', 'Entirely handwritten experiment notes.')
    store.import_report(first)
    assert store.client.get_run(run).data.tags['mlflow.note.content'].startswith('Entirely handwritten experiment notes.')


def test_interrupted_import_reuses_mlflow_run_and_deduplicates_metrics(store, tmp_path, monkeypatch):
    path, _ = segment(tmp_path, 'a')
    original = store.client.log_artifact
    monkeypatch.setattr(store.client, 'log_artifact', lambda *_a, **_k: (_ for _ in ()).throw(OSError('disk')))
    with pytest.raises(OSError):
        store.import_report(path)
    assert store.db.execute('SELECT status FROM segments').fetchone()[0] == 'sync_pending:complete'
    monkeypatch.setattr(store.client, 'log_artifact', original)
    result = store.import_report(path)
    assert len(store.client.search_runs([store.experiment_id])) == 1
    assert len(store.client.get_metric_history(result['run_id'], 'ppo/entropy')) == 1


def test_failed_resume_import_reserves_its_curve_before_sibling(store, tmp_path, monkeypatch):
    parent, _ = segment(tmp_path, 'parent')
    run = store.import_report(parent)['run_id']
    a, _ = segment(tmp_path, 'a', start=10, initial='state1', final='state2', resumed=True)
    b, report_b = segment(tmp_path, 'b', start=10, initial='state1', final='state3', resumed=True)
    report_b['iterations'][0]['update']['mean_update']['entropy'] = .9
    b.write_bytes(r.data(report_b))
    original = store.client.log_artifact
    monkeypatch.setattr(store.client, 'log_artifact', lambda *_a, **_k: (_ for _ in ()).throw(OSError('disk')))
    with pytest.raises(OSError):
        store.import_report(a)
    monkeypatch.setattr(store.client, 'log_artifact', original)
    sibling = store.import_report(b)
    assert sibling['run_id'] != run
    assert store.import_report(a)['run_id'] == run
    assert [(m.step, m.value) for m in store.client.get_metric_history(run, 'ppo/entropy')] == [(10, .5), (20, .5)]
    assert [m.value for m in store.client.get_metric_history(sibling['run_id'], 'ppo/entropy')] == [.9]


def test_pending_terminal_import_retains_immutable_source_hash(store, tmp_path, monkeypatch):
    path, report = segment(tmp_path, 'a')
    original = store.client.log_artifact
    monkeypatch.setattr(store.client, 'log_artifact', lambda *_a, **_k: (_ for _ in ()).throw(OSError('disk')))
    with pytest.raises(OSError):
        store.import_report(path)
    monkeypatch.setattr(store.client, 'log_artifact', original)
    report['iterations'][0]['update']['mean_update']['entropy'] = .9
    path.write_bytes(r.data(report))
    with pytest.raises(ValueError, match='immutable'):
        store.import_report(path)


def test_partial_evaluation_cannot_accept_changed_results_on_retry(store, tmp_path, monkeypatch):
    report = {'schema': 'sts_combat_corpus_comparison_v2', 'status': 'complete',
        'policies': {'learned': 'ppo_v1:'+'a'*64},
        'episodes': [{'policy': 'learned', 'case_id': 'case', 'split': 'validation',
                      'status': 'terminated', 'combat': {'outcome': 'victory'}}]}
    path = tmp_path/'evaluation.json'
    path.write_bytes(r.data(report))
    original = store.client.set_terminated
    monkeypatch.setattr(store.client, 'set_terminated', lambda *_a, **_k: (_ for _ in ()).throw(OSError('disk')))
    with pytest.raises(OSError):
        store.import_report(path)
    assert store.db.execute('SELECT status FROM segments').fetchone()[0] == 'sync_pending:complete'
    monkeypatch.setattr(store.client, 'set_terminated', original)
    changed = copy.deepcopy(report)
    changed['episodes'][0]['combat']['outcome'] = 'defeat'
    path.write_bytes(r.data(changed))
    with pytest.raises(ValueError, match='immutable'):
        store.import_report(path)
    path.write_bytes(r.data(report))
    store.import_report(path)
    child = next(run for run in store.client.search_runs([store.experiment_id])
                 if run.data.tags.get('sts.kind') == 'evaluation_slice')
    assert [m.value for m in store.client.get_metric_history(child.info.run_id, 'eval/win_rate')] == [1.]


def test_late_evaluation_binding_does_not_invent_a_step_zero_learner_point(store, tmp_path):
    path, report = segment(tmp_path, 'train')
    evaluation = {'schema': 'sts_combat_corpus_comparison_v2', 'status': 'complete',
        'policies': {'learned': 'ppo_v1:'+report['final_sha256']},
        'episodes': [{'policy': 'learned', 'case_id': 'case', 'split': 'validation',
                      'status': 'terminated', 'combat': {'outcome': 'victory'}}]}
    evaluation_path = tmp_path/'evaluation.json'
    evaluation_path.write_bytes(r.data(evaluation))
    store.import_report(evaluation_path)
    child = next(run for run in store.client.search_runs([store.experiment_id])
                 if run.data.tags.get('sts.kind') == 'evaluation_slice')
    assert child.data.tags['sts.checkpoint_step'] == 'unknown'
    learner = store.import_report(path)['run_id']
    store.import_report(evaluation_path)
    assert store.client.get_run(child.info.run_id).data.tags['sts.checkpoint_step'] == '10'
    assert len(store.client.get_metric_history(child.info.run_id, 'eval/win_rate')) == 1
    key = next(k for k in store.client.get_run(learner).data.metrics if k.startswith('evaluation/') and k.endswith('/win_rate'))
    assert [m.step for m in store.client.get_metric_history(learner, key)] == [10]


def test_completed_source_and_checkpoint_cannot_be_rewritten(store, tmp_path):
    path, report = segment(tmp_path, 'a')
    store.import_report(path)
    report['summary']['trained_decisions'] = 99
    path.write_bytes(r.data(report))
    with pytest.raises(ValueError, match='immutable'):
        store.import_report(path)
    other, _ = segment(tmp_path, 'other')
    (other.parent/'initial.sts-model').write_bytes(b'changed')
    with pytest.raises(ValueError, match='digest'):
        store.import_report(other)


def test_population_separates_mode_cases_goal_and_failures(store, tmp_path):
    path, training = segment(tmp_path, 'train')
    learner = store.import_report(path)['run_id']
    rows = [{'policy': 'learned', 'case_id': str(i), 'split': 'validation', 'steps': 1,
             'status': status, 'combat': {'outcome': result}, 'room_kind': 'boss'}
            for i, (status, result) in enumerate([('terminated', 'victory'), ('failed', None),
                                                 ('truncated', None), ('unattempted', None)])]
    report = {'schema': 'sts_combat_corpus_comparison_v2', 'status': 'failed',
        'policies': {'learned': 'ppo_v1:'+training['final_sha256']}, 'episodes': rows,
        'corpus': 'frozen-corpus', 'limits': {'max_decisions': 512}}
    base = list(r.evaluations(report))[0]
    assert base['metrics']['eval/win_rate'] == .25
    assert base['metrics']['eval/failures'] == 1
    sampled = copy.deepcopy(report)
    for row in sampled['episodes']:
        row['mode'] = 'sampled'
    changed = copy.deepcopy(report)
    changed['episodes'][0]['case_id'] = 'different'
    campaign = {**report, 'schema': 'sts_act1_evaluation_v1'}
    assert len({list(r.evaluations(x))[0]['population_id'] for x in [report, sampled, changed, campaign]}) == 4
    evaluation = tmp_path/'eval/combat-benchmark.json'
    evaluation.parent.mkdir()
    evaluation.write_bytes(r.data(report))
    store.import_report(evaluation)
    store.import_report(evaluation)
    key = 'evaluation/validation/greedy/'+base['population_id'][:12]+'/win_rate'
    history = store.client.get_metric_history(learner, key)
    assert [(m.step, m.value) for m in history] == [(10, .25)]


def test_public_scope_never_follows_symlinks_or_private_artifacts(tmp_path):
    path, _ = segment(tmp_path, 'public')
    private = tmp_path/'audit'
    private.mkdir()
    (private/'ppo.json').write_text('private secret')
    (tmp_path/'linked').symlink_to(private, target_is_directory=True)
    assert r.discover([tmp_path]) == [path]
    for excluded in (private, tmp_path/'linked'):
        with pytest.raises(ValueError):
            r.discover([excluded])
    with pytest.raises(ValueError):
        r.bundle(private/'resume.pt', 'a'*64)


def test_import_sorts_parents_before_children_and_reports_unsupported(store, tmp_path):
    a, _ = segment(tmp_path, 'z-first')
    b, _ = segment(tmp_path, 'a-next', start=10, initial='state1', final='state2', resumed=True)
    unknown = tmp_path/'unsupported.json'
    unknown.write_text('{"schema":"unrelated"}')
    result = import_reports(store, [b, a, unknown])
    assert not result['failed'] and result['counts']['skipped'] == 1
    assert len({r['run_id'] for r in result['reports']}) == 1


def test_live_reporting_throttles_and_failure_does_not_escape(tmp_path, monkeypatch):
    class FailingStore:
        def import_report(self, *args):
            raise OSError('dashboard unavailable')
    from game.agent.tracking import reporting
    token = reporting._session.set(FailingStore())
    try:
        with pytest.warns(RuntimeWarning, match='Canonical outputs are retained'):
            report_progress(tmp_path/'ppo.json', {'status': 'running'})
        report_progress(tmp_path/'ppo.json', {'status': 'running'})
        with pytest.warns(RuntimeWarning):
            report_progress(tmp_path/'ppo.json', {'status': 'complete'})
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            report_progress(tmp_path/'ppo.json', {'status': 'complete'})
    finally:
        reporting._session.reset(token)


def test_two_live_resumes_cannot_claim_one_curve(store, tmp_path):
    path, _ = segment(tmp_path, 'parent')
    parent = store.import_report(path)['run_id']
    a, report_a = segment(tmp_path, 'resume-a', start=10, initial='state1', final='state2', resumed=True)
    b, report_b = segment(tmp_path, 'resume-b', start=10, initial='state1', final='state3', resumed=True)
    for report in (report_a, report_b):
        report.update(status='running', iterations=[])
        del report['final_sha256']
    first = store.import_report(a, report_a)
    second = store.import_report(b, report_b)
    assert first['run_id'] == parent
    assert second['run_id'] != parent and second['lineage'] == 'fork'


def test_tracking_destinations_are_bounded(tmp_path):
    from game.agent.tracking.store import local_store
    root = tmp_path/'tracking'
    root.mkdir()
    outside = tmp_path/'elsewhere'
    outside.write_text('preserved')
    (root/'mlflow.db').symlink_to(outside)
    with pytest.raises(ValueError, match='symlink'):
        local_store(root)
    assert outside.read_text() == 'preserved'
    (root/'mlflow.db').unlink()
    with TrackingStore(root, experiment='safe') as store:
        store.client.create_experiment('remote', artifact_location='https://example.invalid/artifacts')
    with pytest.raises(ValueError, match='not in this local store'):
        TrackingStore(root, experiment='remote')


def test_failed_episode_cannot_count_a_retained_victory_and_legacy_denominators():
    report = {'schema': 'sts_combat_baseline_v2', 'status': 'failed', 'split': 'validation',
        'policies': {'heuristic': 'h', 'random_legal': 'r'}, 'requested_episodes': 20,
        'episodes': [{'policy': 'heuristic', 'status': 'failed', 'combat': {'outcome': 'victory'}}]}
    groups = list(r.evaluations(report))
    assert len(groups) == 2
    for group in groups:
        assert group['metrics']['eval/planned'] == 10
        assert group['metrics']['eval/wins'] == 0
        assert group['metrics']['eval/win_rate'] == 0
    assert groups[0]['metrics']['eval/unattempted'] == 9
    assert groups[1]['metrics']['eval/unattempted'] == 10


def test_same_checkpoint_in_different_experiments_has_scoped_owner(store, tmp_path):
    path, report = segment(tmp_path, 'train')
    owner_a = store.import_report(path)['run_id']
    with TrackingStore(store.path, experiment='Other') as other:
        owner_b = other.import_report(path)['run_id']
        assert owner_a != owner_b
        evaluation = {'schema': 'sts_combat_corpus_comparison_v2', 'status': 'complete',
            'policies': {'learned': 'ppo_v1:'+report['final_sha256']},
            'episodes': [{'policy': 'learned', 'case_id': 'case', 'split': 'validation',
                          'status': 'terminated', 'combat': {'outcome': 'victory'}}]}
        result = other.import_report(tmp_path/'evaluation.json', evaluation)
        assert result['status'] == 'tracked'
        assert any(k.startswith('evaluation/') for k in other.client.get_run(owner_b).data.metrics)
        assert not any(k.startswith('evaluation/') for k in store.client.get_run(owner_a).data.metrics)


def test_hybrid_preserves_combat_checkpoint_and_fixed_controller():
    checkpoint_sha, controller_sha = 'a'*64, 'b'*64
    report = {'schema': 'sts_full_run_evaluation_v1', 'policies': {
        'hybrid': 'hybrid_v1:'+checkpoint_sha+':full_run_demo_v2:'+controller_sha},
        'episodes': [{'policy': 'hybrid', 'case_id': 'case', 'status': 'terminated',
                      'outcome': {'kind': 'victory'}}]}
    group = list(r.evaluations(report))[0]
    assert group['checkpoint'] == checkpoint_sha
    assert group['population']['fixed_controller'] == 'full_run_demo_v2:'+controller_sha
    assert group['metrics']['eval/win_rate'] == 1
    assert 'eval/mean_task_return' not in group['metrics']


def test_named_imitation_resume_joins_update_axis(store, tmp_path):
    torch = pytest.importorskip('torch')
    from dataclasses import asdict
    from .test_training_checkpoint import learner
    from game.agent.training.checkpoint import save_checkpoint, restore_learner, runtime
    torch.set_num_threads(1)
    owner = learner()
    run_ids = []
    parent = None
    for name in ('first', 'second'):
        output = tmp_path/name
        report = {'schema': 'sts_imitation_report_v1', 'status': 'complete',
            'runtime': runtime(), 'learner_config': asdict(owner.config),
            'corpus_identity': owner.corpus.identity, 'start_update': owner.updates,
            'initialization': {'resumed': parent is not None, 'checkpoint': parent}, 'total_seconds': .5}
        report['initial_sha256'] = save_checkpoint(output/'initial.sts-model', owner)
        report['updates'] = [owner.step(), owner.step()]
        resume = tmp_path/(name+'-private')/'final.resume.pt'
        report['final_sha256'] = save_checkpoint(output/'final.sts-model', owner, resume_path=resume)
        path = output/'imitation.json'
        path.write_bytes(r.data(report))
        run_ids.append(store.import_report(path)['run_id'])
        parent = 'imitation_v1:'+report['final_sha256']
        owner = restore_learner(output/'final.sts-model', resume, owner.corpus)
    assert len(set(run_ids)) == 1
    assert [m.step for m in store.client.get_metric_history(run_ids[0], 'imitation/loss')] == [1, 2, 3, 4]


def test_real_training_logging_and_exact_resume_preserve_weights(tmp_path):
    torch = pytest.importorskip('torch')
    pytest.importorskip('gymnasium')
    from .test_ppo import controlled_env, owner
    from game.agent.training.checkpoint import save_ppo_checkpoint, load_policy
    from game.agent.training.ppo_run import run_ppo
    torch.set_num_threads(1)
    learner = owner()
    initial = tmp_path/'seed/start.sts-model'
    save_ppo_checkpoint(initial, learner, resume_path=tmp_path/'seed-private/start.resume.pt')
    config = TrackingConfig(str(tmp_path/'tracking'), experiment='Live')
    with tracking_session(config) as store:
        first, result = run_ppo(checkpoint=initial, experiment=learner.experiment, output_dir=tmp_path/'tracked',
                               decisions=8, env_factory=controlled_env, seed=0)
        assert result['status'] == 'complete'
        second, result = run_ppo(checkpoint=first.parent/'final.sts-model', experiment=learner.experiment,
            resume_state=tmp_path/'tracked-private/final.resume.pt', output_dir=tmp_path/'resumed',
            decisions=8, env_factory=controlled_env)
        assert result['status'] == 'complete'
        segments = store.db.execute('SELECT * FROM segments').fetchall()
        assert len(segments) == 2 and len({row['run'] for row in segments}) == 1
        run = segments[0]['run']
        assert [m.step for m in store.client.get_metric_history(run, 'ppo/entropy')] == [8, 16]
    plain, plain_result = run_ppo(checkpoint=initial, experiment=learner.experiment,
        output_dir=tmp_path/'plain', decisions=8, env_factory=controlled_env, seed=0)
    assert plain_result['status'] == 'complete'
    left, right = load_policy(first.parent/'final.sts-model'), load_policy(plain.parent/'final.sts-model')
    assert all(torch.equal(v, right.model.state_dict()[k]) for k, v in left.model.state_dict().items())
    learner.close()
