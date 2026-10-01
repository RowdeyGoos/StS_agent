"""Checkpoint catalog provenance, recovery and evaluation comparisons."""
import os
from pathlib import Path

import pytest

os.environ['MLFLOW_DISABLE_TELEMETRY'] = 'true'
os.environ['MLFLOW_DISABLE_AGENT_HINT'] = 'true'
pytest.importorskip('mlflow')
from game.agent.tracking import records as r
from game.agent.tracking.store import TrackingStore
from .test_experiment_tracking import segment, store


def models(store):
    return list(store.client.search_logged_models([store.experiment_id], max_results=100))


def test_backfill_preserves_existing_curves_and_publishes_verified_checkpoints(store, tmp_path, monkeypatch):
    first, _ = segment(tmp_path, 'first')
    second, _ = segment(tmp_path, 'second', start=10, initial='state1', final='state2', resumed=True)
    sync = store._checkpoint_models
    monkeypatch.setattr(store, '_checkpoint_models', lambda *_a, **_k: None)
    run = store.import_report(first)['run_id']
    store.import_report(second)
    original = store.client.get_run(run)
    wall = [(m.step, m.value) for m in store.client.get_metric_history(run, 'system/cumulative_wall_seconds')]
    monkeypatch.setattr(store, '_checkpoint_models', sync)
    for _ in range(2):
        for path in (first, second):
            assert store.import_report(path)['status'] == 'unchanged'
    catalog = models(store)
    assert len(catalog) == 2
    assert len(store.client.get_run(run).outputs.model_outputs) == 2
    assert store.client.get_run(run).data.metrics == original.data.metrics
    assert store.client.get_run(run).data.tags['sts.last_report'] == str(second)
    assert [(m.step, m.value) for m in store.client.get_metric_history(run, 'system/cumulative_wall_seconds')] == wall
    for model in catalog:
        assert model.source_run_id == run and str(model.status) == 'READY'
        assert model.params['architecture.hidden_size'] == '16'
        artifacts = store.client.list_logged_model_artifacts(model.model_id)
        assert {a.path for a in artifacts} == {'README.md', 'source.json', 'manifest.json', 'checkpoint.sts-model'}
        from urllib.parse import unquote, urlsplit
        saved = Path(unquote(urlsplit(model.artifact_location).path))/'checkpoint.sts-model'
        assert r.digest(saved) == model.tags['sts.checkpoint']
        assert model.params['checkpoint.axis'] == 'decisions'


def test_failed_model_publication_recovers_same_entry_and_checks_staged_bytes(store, tmp_path, monkeypatch):
    path, _ = segment(tmp_path, 'first')
    original = store.client.log_model_artifacts
    monkeypatch.setattr(store.client, 'log_model_artifacts', lambda *_a, **_k: (_ for _ in ()).throw(OSError('disk')))
    with pytest.raises(OSError):
        store.import_report(path)
    pending = models(store)
    assert len(pending) == 1 and str(pending[0].status) == 'PENDING'
    monkeypatch.setattr(store.client, 'log_model_artifacts', original)
    initial = path.parent/'initial.sts-model'
    saved = initial.read_bytes()
    initial.write_bytes(b'changed after manifest validation')
    with pytest.raises(ValueError, match='digest changed'):
        store.import_report(path)
    initial.write_bytes(saved)
    result = store.import_report(path)
    catalog = models(store)
    assert len(catalog) == 2 and pending[0].model_id in {m.model_id for m in catalog}
    assert all(str(m.status) == 'READY' for m in catalog)
    assert len(store.client.get_metric_history(result['run_id'], 'ppo/entropy')) == 1


def test_checkpoint_scores_keep_populations_modes_and_experiments_separate(store, tmp_path, monkeypatch):
    path, report = segment(tmp_path, 'train')
    owner = store.import_report(path)['run_id']
    sha = report['final_sha256']
    model = next(m for m in models(store) if m.tags['sts.checkpoint'] == sha)
    evaluation = {'schema': 'sts_combat_corpus_comparison_v2', 'status': 'complete',
        'policies': {'learned': 'ppo_v1:'+sha}, 'episodes': [
            {'policy': 'learned', 'case_id': 'case', 'room_kind': 'boss', 'split': 'validation', 'mode': 'greedy',
             'status': 'terminated', 'combat': {'outcome': 'victory'}},
            {'policy': 'learned', 'case_id': 'case', 'split': 'validation', 'mode': 'sampled',
             'status': 'terminated', 'combat': {'outcome': 'defeat'}}]}
    evaluation_path = tmp_path/'evaluation.json'
    evaluation_path.write_bytes(r.data(evaluation))
    set_tags = store.client.set_logged_model_tags
    monkeypatch.setattr(store.client, 'set_logged_model_tags', lambda *_a, **_k: (_ for _ in ()).throw(OSError('after metrics')))
    with pytest.raises(OSError):
        store.import_report(evaluation_path)
    monkeypatch.setattr(store.client, 'set_logged_model_tags', set_tags)
    for _ in range(2):
        store.import_report(evaluation_path)
    current = store.client.get_logged_model(model.model_id)
    assert not any('/by_room_kind/' in m.key for m in current.metrics)
    wins = [m for m in current.metrics if m.key.endswith('/win_rate')]
    assert len(wins) == 2 and {m.value for m in wins} == {0., 1.}
    assert len({m.dataset_digest for m in wins}) == 2
    assert all('/validation/' in m.dataset_name for m in wins)
    assert current.tags['sts.evaluated'] == current.tags['sts.validation'] == 'true'
    for metric in wins:
        child = store.client.get_run(metric.run_id)
        if '/greedy/' in metric.key:
            assert child.data.metrics['eval/by_room_kind/boss/win_rate'] == 1.
        assert child.data.tags['sts.model_id'] == model.model_id
        assert len(child.inputs.dataset_inputs) == 1
        assert len(store.client.get_metric_history(metric.run_id, metric.key)) == 1
        assert [m.step for m in store.client.get_metric_history(owner, metric.key)] == [10]
    with TrackingStore(store.path, experiment='Other') as other:
        other.import_report(path)
        other.import_report(evaluation_path)
        counterpart = next(m for m in models(other) if m.tags['sts.checkpoint'] == sha)
        assert counterpart.model_id != model.model_id and counterpart.source_run_id != owner
        assert all(m.run_id not in {v.run_id for v in wins} for m in counterpart.metrics)


def test_model_artifact_destination_cannot_escape_local_store(store, tmp_path, monkeypatch):
    path, _ = segment(tmp_path, 'first')
    create = store.client.create_logged_model
    def redirected(*args, **kwargs):
        model = create(*args, **kwargs)
        model.artifact_location = 'https://example.invalid/models'
        return model
    monkeypatch.setattr(store.client, 'create_logged_model', redirected)
    with pytest.raises(ValueError, match='destination'):
        store.import_report(path)
    assert not list((store.path/'artifacts').rglob('checkpoint.sts-model'))


@pytest.mark.parametrize('evaluate_before_second_learner', [False, True])
def test_shared_bundle_scores_do_not_claim_exclusive_learner_ownership(store, tmp_path, evaluate_before_second_learner):
    import json
    path, report = segment(tmp_path, 'first')
    store.import_report(path)
    evaluation = {'schema': 'sts_combat_corpus_comparison_v2', 'status': 'complete',
        'policies': {'learned': 'ppo_v1:'+report['final_sha256']}, 'episodes': [
            {'policy': 'learned', 'case_id': 'case', 'status': 'terminated', 'combat': {'outcome': 'victory'}}]}
    evaluation_path = tmp_path/'evaluation.json'
    evaluation_path.write_bytes(r.data(evaluation))
    if evaluate_before_second_learner:
        store.import_report(evaluation_path)
    second, second_report = segment(tmp_path, 'other')
    # One exact bundle used to initialize a distinct learner is not proof that
    # an evaluation belongs to one particular training history.
    (second.parent/'initial.sts-model').write_bytes((path.parent/'final.sts-model').read_bytes())
    second_report['initial_sha256'] = report['final_sha256']
    second.write_bytes(r.data(second_report))
    store.import_report(second)
    for _ in range(2):
        store.import_report(evaluation_path)
    linked = [m for m in models(store) if m.tags['sts.checkpoint'] == report['final_sha256']]
    assert len(linked) == 2
    for model in linked:
        assert model.tags['sts.checkpoint_ownership'] == 'shared'
        assert [m.value for m in model.metrics if m.key.endswith('/win_rate')] == [1.]
    child = store.client.get_run(linked[0].metrics[0].run_id)
    assert 'sts.model_id' not in child.data.tags and 'sts.learner_run' not in child.data.tags
    assert child.data.tags['sts.checkpoint_ownership'] == 'shared'
    assert set(json.loads(child.data.tags['sts.model_ids'])) == {m.model_id for m in linked}
    assert len(store.client.get_metric_history(child.info.run_id, linked[0].metrics[0].key)) == 1


def test_continuation_hides_old_final_then_evaluation_restores_same_model(store, tmp_path):
    first, report = segment(tmp_path, 'first')
    run = store.import_report(first)['run_id']
    old = next(m for m in models(store) if m.tags['sts.checkpoint'] == report['final_sha256'])
    second, _ = segment(tmp_path, 'second', start=10, initial='state1', final='state2', resumed=True)
    store.import_report(second)
    assert old.model_id not in {m.model_id for m in models(store)}
    assert len(models(store)) == 2
    # Curation preserves the files, original output links and every curve point.
    assert (first.parent/'final.sts-model').exists()
    assert len(store.client.get_run(run).outputs.model_outputs) == 3
    original = [(m.step, m.value) for m in store.client.get_metric_history(run, 'ppo/entropy')]
    store.curate_models(keep=[first.parent/'final.sts-model'])
    assert old.model_id in {m.model_id for m in models(store)}
    store.curate_models(release=[first.parent/'final.sts-model'])
    assert old.model_id not in {m.model_id for m in models(store)}
    evaluation = tmp_path/'evaluation.json'
    evaluation.write_bytes(r.data({'schema': 'sts_combat_corpus_comparison_v2', 'status': 'complete',
        'policies': {'learned': 'ppo_v1:'+report['final_sha256']}, 'episodes': [
            {'policy': 'learned', 'case_id': 'one', 'status': 'terminated', 'combat': {'outcome': 'victory'}}]}))
    store.import_report(evaluation)
    for _ in range(2):
        store.import_report(first)
        store.import_report(second)
        store.curate_models()
    assert old.model_id in {m.model_id for m in models(store)}
    assert len(models(store)) == 3
    assert [(m.step, m.value) for m in store.client.get_metric_history(run, 'ppo/entropy')] == original
    assert [m.value for m in store.client.get_logged_model(old.model_id).metrics if m.key.endswith('/win_rate')] == [1.]


def test_intermediate_updates_are_only_published_when_selected(store, tmp_path):
    import copy
    from .test_experiment_tracking import checkpoint
    path, report = segment(tmp_path, 'train')
    first_update = path.parent/'update-00001.sts-model'
    sha = checkpoint(first_update, 'middle')
    report['iterations'][0]['checkpoint_sha256'] = sha
    other = copy.deepcopy(report['iterations'][0])
    other['iteration'] = 2
    other['checkpoint_sha256'] = checkpoint(path.parent/'update-00002.sts-model', 'state1')
    report['iterations'].append(other)
    path.write_bytes(r.data(report))
    store.import_report(path)
    assert len(models(store)) == 2
    assert store.db.execute('SELECT count(*) FROM checkpoint_models').fetchone()[0] == 2
    assert first_update.exists()
    store.curate_models(keep=[first_update])
    selected = next(m for m in models(store) if m.tags['sts.checkpoint'] == sha)
    assert selected.params['checkpoint.step'] == '10'
    store.import_report(path)
    assert len(models(store)) == 3
    store.curate_models(release=[first_update])
    assert len(models(store)) == 2
    # A rolled-back local index must recover the hidden catalog ID, not clone it.
    with store.db:
        store.db.execute('DELETE FROM checkpoint_models WHERE model=?', (selected.model_id,))
    store.curate_models(keep=[first_update])
    assert next(m.model_id for m in models(store) if m.tags['sts.checkpoint'] == sha) == selected.model_id


def test_manual_deletion_is_not_undone_by_catalog_or_evaluation(store, tmp_path, monkeypatch):
    first, report = segment(tmp_path, 'first')
    store.import_report(first)
    old = next(m for m in models(store) if m.tags['sts.checkpoint'] == report['final_sha256'])
    second, _ = segment(tmp_path, 'second', start=10, initial='state1', final='state2', resumed=True)
    store.import_report(second)
    # Even an additional manual deletion of a policy-hidden entry takes precedence.
    monkeypatch.setattr('mlflow.store.tracking.sqlalchemy_store.get_current_time_millis', lambda: 9999999999999)
    store.client.delete_logged_model(old.model_id)
    from game.agent.tracking.models import CheckpointCatalog
    with store.db:
        CheckpointCatalog(store).promote(report['final_sha256'])
    store.curate_models()
    assert old.model_id not in {m.model_id for m in models(store)}
    # An active endpoint manually deleted by the user also remains deleted.
    initial = next(m for m in models(store) if m.params['checkpoint.step'] == '0')
    store.client.delete_logged_model(initial.model_id)
    store.import_report(first)
    assert initial.model_id not in {m.model_id for m in models(store)}


def test_interruption_after_unsaved_update_retains_latest_saved_endpoint(store, tmp_path):
    from .test_experiment_tracking import checkpoint
    path, report = segment(tmp_path, 'interrupted')
    saved = path.parent/'update-00001.sts-model'
    report['iterations'][0]['checkpoint_sha256'] = checkpoint(saved, 'state1')
    report.pop('final_sha256')
    report['status'] = 'cancelled'
    report['iterations'].append({'iteration': 2, 'collection': {'steps': 5, 'seconds': 1., 'episodes': []},
                                 'update': {'decisions': 5, 'status': 'updated', 'seconds': 1.}})
    path.write_bytes(r.data(report))
    store.import_report(path)
    assert sorted(m.params['checkpoint.step'] for m in models(store)) == ['0', '10']
    assert store.db.execute('SELECT end FROM segments').fetchone()[0] == 15


def test_running_continuation_keeps_previous_completed_endpoint(store, tmp_path):
    from .test_experiment_tracking import checkpoint
    first, first_report = segment(tmp_path, 'first')
    run = store.import_report(first)['run_id']
    old = next(m for m in models(store) if m.tags['sts.checkpoint'] == first_report['final_sha256'])
    second, report = segment(tmp_path, 'second', start=10, initial='state1', final='state2', resumed=True)
    final_sha = report.pop('final_sha256')
    report['status'] = 'running'
    report['iterations'][0]['checkpoint_sha256'] = checkpoint(second.parent/'update-00002.sts-model', 'state2')
    second.write_bytes(r.data(report))
    assert store.import_report(second)['run_id'] == run
    assert len(models(store)) == 2
    assert old.model_id in {m.model_id for m in models(store)}
    report.update(status='complete', final_sha256=final_sha)
    second.write_bytes(r.data(report))
    store.import_report(second)
    assert len(models(store)) == 2
    assert old.model_id not in {m.model_id for m in models(store)}
    assert {m.tags['sts.checkpoint'] for m in models(store)} == {first_report['initial_sha256'], final_sha}
