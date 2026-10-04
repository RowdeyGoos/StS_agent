"""Saved layouts are reusable, non-destructive views of existing measurements."""
import base64
import json
import os
import zlib

import pytest

os.environ['MLFLOW_DISABLE_TELEMETRY'] = 'true'
os.environ['MLFLOW_DISABLE_AGENT_HINT'] = 'true'
pytest.importorskip('mlflow')

from game.agent.tracking.store import TrackingStore
from game.agent.tracking.views import MANAGED_TAG, VIEW_PREFIX
from game.cli.agent_track import main
from .test_experiment_tracking import segment


@pytest.fixture
def store(tmp_path):
    with TrackingStore(tmp_path/'tracking', experiment='New combat study') as value:
        yield value


def saved(store):
    return {key: value for key, value in store.client.get_experiment(store.experiment_id).tags.items()
            if key.startswith(VIEW_PREFIX)}


def state(raw):
    return json.loads(zlib.decompress(base64.b64decode(json.loads(raw)['state'].split(';', 1)[1])))


def visible(raw):
    return {c['metricKey'] for c in state(raw)['compareRunCharts'] if not c['deleted']}


def view_key(slug):
    return VIEW_PREFIX + 'sts-' + slug + '-v1'


def test_reports_automatically_add_views_and_later_evaluation_populations(store, tmp_path):
    assert saved(store) == {}
    path, report = segment(tmp_path, 'learner')
    learner = store.import_report(path)['run_id']
    views = saved(store)
    assert len(views) == 3  # Fight quality requires a recorded fixed-case HP score.
    assert visible(views[view_key('combat-performance')]) == {'train/win_rate'}
    assert visible(views[view_key('ppo-diagnostics')]) == {'ppo/entropy', 'ppo/approx_kl'}
    for raw in views.values():
        layout = state(raw)
        assert [r.info.run_id for r in store.client.search_runs(
            [store.experiment_id], filter_string=layout['searchFilter'])] == [learner]
        assert layout['columnOrder'] == []  # Preserve MLflow's fixed Run Name column.
        assert layout['useGroupedValuesInCharts'] is False
        assert all(c['xAxisKey'] == 'step' and c['lineSmoothness'] == 0
                   for c in layout['compareRunCharts'] if not c['deleted'])
    original_entropy = store.client.get_metric_history(learner, 'ppo/entropy')
    for mode in ('greedy', 'sampled'):
        evaluation = {'schema': 'sts_combat_corpus_comparison_v2', 'status': 'complete',
            'policies': {'learned': 'ppo_v1:'+report['final_sha256']},
            'episodes': [{'policy': 'learned', 'case_id': 'case', 'split': 'validation',
                          'mode': mode, 'status': 'terminated',
                          'combat': {'outcome': 'victory', 'hp': 31}}]}
        file = tmp_path/(mode+'-evaluation.json')
        file.write_text(json.dumps(evaluation))
        store.import_report(file)
    views = saved(store)
    assert len(views) == 4
    metrics = visible(views[view_key('combat-performance')])
    greedy = next(k for k in metrics if '/validation/greedy/' in k)
    sampled = next(k for k in metrics if '/validation/sampled/' in k)
    assert greedy.split('/')[3] != sampled.split('/')[3]
    assert all(k.endswith('/mean_hp_on_win') for k in visible(views[view_key('fight-quality')]))
    assert store.client.get_metric_history(learner, 'ppo/entropy') == original_entropy
    assert [m.step for m in store.client.get_metric_history(learner, greedy)] == [10]
    assert store.import_report(path)['status'] == 'unchanged'
    assert saved(store) == views


def test_cli_reuses_templates_in_another_experiment_without_touching_runs(store, tmp_path, capsys):
    path, _ = segment(tmp_path, 'learner')
    store.import_report(path)
    with TrackingStore(store.path, experiment='Different architecture') as other:
        run = other.client.create_run(other.experiment_id, tags={'sts.kind': 'ppo'}).info.run_id
        other.client.log_metric(run, 'ppo/entropy', .4, step=50)
        other.client.log_metric(run, 'ppo/value_mse', .2, step=50)
        assert not saved(other)  # Direct MLflow writes do not invoke our reporting boundary.
        before = other.client.get_run(run).to_dictionary()
        assert main(['views', '--store', str(store.path), '--experiment', other.experiment_name]) == 0
        assert json.loads(capsys.readouterr().out)['views'][0]['status'] == 'created'
        assert len(saved(other)) == 1
        assert visible(saved(other)[view_key('ppo-diagnostics')]) == {'ppo/entropy', 'ppo/value_mse'}
        assert other.client.get_run(run).to_dictionary() == before
        first = saved(other)
        assert main(['views', '--store', str(store.path), '--experiment', other.experiment_name]) == 0
        capsys.readouterr()
        assert saved(other) == first


def test_user_edits_deletions_and_existing_named_views_survive_refresh(store, tmp_path):
    legacy_key = VIEW_PREFIX + 'handmade'
    legacy = json.dumps({'name': '01 · Combat performance', 'state': 'user layout'})
    store.client.set_experiment_tag(store.experiment_id, legacy_key, legacy)
    path, _ = segment(tmp_path, 'learner')
    run = store.import_report(path)['run_id']
    assert view_key('combat-performance') not in saved(store)
    original = saved(store)
    edited = json.loads(original[view_key('ppo-diagnostics')])
    edited['name'] = 'My PPO layout'
    edited = json.dumps(edited)
    store.client.set_experiment_tag(store.experiment_id, view_key('ppo-diagnostics'), edited)
    store.client.delete_experiment_tag(store.experiment_id, view_key('training-speed'))
    store.client.log_metric(run, 'ppo/clip_fraction', .2, step=20)
    with TrackingStore(store.path, experiment=store.experiment_name) as reopened:
        result = reopened.refresh_views()
        assert all(row['status'] == 'preserved' for row in result['views'])
        assert saved(reopened) == {legacy_key: legacy, view_key('ppo-diagnostics'): edited}


@pytest.mark.parametrize('failure', ['after_view', 'acknowledgement'])
def test_partial_view_writes_recover_without_duplicates(store, monkeypatch, failure):
    run = store.client.create_run(store.experiment_id, tags={'sts.kind': 'ppo'}).info.run_id
    store.client.log_metric(run, 'ppo/entropy', .7, step=20)
    write = store.client.set_experiment_tag
    acknowledgements = 0

    def interrupted(experiment, key, value):
        nonlocal acknowledgements
        if key == MANAGED_TAG:
            acknowledgements += 1
            if failure == 'acknowledgement' and acknowledgements == 2:
                raise OSError('acknowledgement interrupted')
        write(experiment, key, value)
        if key.startswith(VIEW_PREFIX) and failure == 'after_view':
            raise OSError('unknown write outcome')

    monkeypatch.setattr(store.client, 'set_experiment_tag', interrupted)
    with pytest.raises(OSError):
        store.refresh_views()
    monkeypatch.setattr(store.client, 'set_experiment_tag', write)
    store.refresh_views()
    assert len(saved(store)) == 1
    assert visible(saved(store)[view_key('ppo-diagnostics')]) == {'ppo/entropy'}
    tags = store.client.get_experiment(store.experiment_id).tags
    entry = json.loads(tags[MANAGED_TAG])['views'][view_key('ppo-diagnostics')]
    assert 'pending' not in entry
    before = saved(store)
    store.refresh_views()
    assert saved(store) == before


@pytest.mark.parametrize('write_happened', [False, True])
def test_missing_unacknowledged_view_is_preserved_even_after_user_deletion(store, monkeypatch, write_happened):
    run = store.client.create_run(store.experiment_id, tags={'sts.kind': 'ppo'}).info.run_id
    store.client.log_metric(run, 'ppo/entropy', .7, step=20)
    write = store.client.set_experiment_tag

    def interrupted(experiment, key, value):
        if not key.startswith(VIEW_PREFIX) or write_happened:
            write(experiment, key, value)
        if key.startswith(VIEW_PREFIX):
            raise OSError('unknown first-write outcome')

    monkeypatch.setattr(store.client, 'set_experiment_tag', interrupted)
    with pytest.raises(OSError):
        store.refresh_views()
    monkeypatch.setattr(store.client, 'set_experiment_tag', write)
    if write_happened:
        store.client.delete_experiment_tag(store.experiment_id, view_key('ppo-diagnostics'))
    result = store.refresh_views()
    assert result['views'][0]['status'] == 'preserved'
    assert 'first save interrupted' in result['views'][0]['reason']
    assert saved(store) == {}


def test_failed_optional_layout_write_does_not_fail_a_report(store, tmp_path, monkeypatch):
    path, _ = segment(tmp_path, 'learner')
    write = store.client.set_experiment_tag
    monkeypatch.setattr(store.client, 'set_experiment_tag',
                        lambda *_a, **_k: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.warns(RuntimeWarning, match='saved views'):
        result = store.import_report(path)
    assert result['status'] == 'tracked'
    assert store.client.get_run(result['run_id']).info.status == 'FINISHED'
    monkeypatch.setattr(store.client, 'set_experiment_tag', write)
    assert store.import_report(path)['status'] == 'unchanged'
    assert len(saved(store)) == 3
    assert len(store.client.get_metric_history(result['run_id'], 'ppo/entropy')) == 1


def test_benchmarks_keep_workloads_separate_and_select_their_recorded_metrics(store):
    expected = {}
    for benchmark, panel in [('evaluation-new', 'greedy'), ('evaluation-new', 'full'),
                             ('cpu-new', None)]:
        run = store.client.create_run(store.experiment_id, tags={
            'sts.kind': 'benchmark', 'sts.benchmark': benchmark}).info.run_id
        if panel:
            store.client.log_param(run, 'panel', panel)
            store.client.log_metric(run, 'summary/median_evaluation_seconds', 10)
        else:
            store.client.log_metric(run, 'benchmark/update_seconds', 3, step=0)
            store.client.log_metric(run, 'benchmark/update_seconds', 2, step=1)
        expected[run] = panel
    store.refresh_views()
    views = saved(store)
    assert len(views) == 3
    for raw in views.values():
        layout = state(raw)
        rows = store.client.search_runs([store.experiment_id], filter_string=layout['searchFilter'])
        assert len(rows) == 1
        chart = next(c for c in layout['compareRunCharts'] if not c['deleted'])
        assert chart['type'] == ('BAR' if expected[rows[0].info.run_id] else 'LINE')


@pytest.mark.parametrize('label', ["O'Reilly", r'back\slash', 'say "hello"'])
def test_benchmark_filters_match_literal_labels(store, label):
    run = store.client.create_run(store.experiment_id, tags={
        'sts.kind': 'benchmark', 'sts.benchmark': label}).info.run_id
    store.client.log_metric(run, 'benchmark/update_seconds', 2, step=0)
    store.refresh_views()
    raw, = saved(store).values()
    rows = store.client.search_runs([store.experiment_id], filter_string=state(raw)['searchFilter'])
    assert [row.info.run_id for row in rows] == [run]


def test_refresh_updates_owned_layout_and_hides_new_detailed_metrics(store):
    run = store.client.create_run(store.experiment_id, tags={'sts.kind': 'ppo'}).info.run_id
    store.client.log_metric(run, 'ppo/entropy', .6, step=10)
    store.refresh_views()
    first = saved(store)[view_key('ppo-diagnostics')]
    store.client.log_metric(run, 'ppo/value_mse', .2, step=20)
    store.client.log_metric(run, 'by_seconds/ppo/value_mse', .2, step=2)
    before = store.client.get_run(run).to_dictionary()
    store.refresh_views()
    updated = saved(store)[view_key('ppo-diagnostics')]
    assert visible(updated) == {'ppo/entropy', 'ppo/value_mse'}
    assert json.loads(first)['createdAt'] == json.loads(updated)['createdAt']
    detailed = next(c for c in state(updated)['compareRunCharts'] if c['metricKey'].startswith('by_seconds/'))
    assert detailed['deleted'] is True
    assert store.client.get_run(run).to_dictionary() == before


def test_refresh_reads_all_run_pages_and_never_touches_unrelated_experiments(store, monkeypatch):
    from mlflow.store.entities import PagedList
    old = store.client.create_run(store.experiment_id, tags={'sts.kind': 'ppo'}).info.run_id
    store.client.log_metric(old, 'ppo/value_mse', .2)
    latest = store.client.create_run(store.experiment_id, tags={'sts.kind': 'ppo'}).info.run_id
    store.client.log_metric(latest, 'ppo/entropy', .4)
    search = store.client.search_runs
    calls = []

    def pages(ids, *, max_results, page_token=None):
        assert ids == [store.experiment_id]
        calls.append(page_token)
        return (PagedList([store.client.get_run(latest)], 'next') if page_token is None else
                PagedList([store.client.get_run(old)], None))

    monkeypatch.setattr(store.client, 'search_runs', pages)
    store.refresh_views()
    assert calls == [None, 'next']
    assert visible(saved(store)[view_key('ppo-diagnostics')]) == {'ppo/entropy', 'ppo/value_mse'}
    monkeypatch.setattr(store.client, 'search_runs', search)


def test_unrecognized_registry_preserves_existing_views(store):
    run = store.client.create_run(store.experiment_id, tags={'sts.kind': 'ppo'}).info.run_id
    store.client.log_metric(run, 'ppo/entropy', .2)
    store.client.set_experiment_tag(store.experiment_id, MANAGED_TAG, '{"version":99}')
    store.client.set_experiment_tag(store.experiment_id, VIEW_PREFIX+'mine', 'custom bytes')
    before = store.client.get_experiment(store.experiment_id).tags
    with pytest.raises(ValueError, match='Unrecognized'):
        store.refresh_views()
    assert store.client.get_experiment(store.experiment_id).tags == before
