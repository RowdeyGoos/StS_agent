"""Fixed-width controls and a new TRAIN/DEV source after parent TEST exposure."""
from copy import deepcopy
from dataclasses import asdict
import gzip
import json
from pathlib import Path

import pytest

pytest.importorskip('torch')
from game.agent.provenance import implementation
from game.agent.training.benchmark_suite import data
from game.agent.training.features import Vocabulary
from game.agent.training.search_sources import development_context, _sha_file, _owners, open_search_source
from game.agent.training.study.flat_width import configurations, load_config, SCHEMA
from game.agent.training.study.source import prepare_source, StudySource, reserve_test, DEVELOPMENT_SOURCE
from game.agent.training.study.spec import StudyArchitecture, FeatureSpec, RICHNESS
from game.agent.training.study.projection import study_catalog
from .test_search_consolidation import historical_source
from .test_training_model import cpu_threads


@pytest.fixture
def closed_parent(historical_source, tmp_path):
    """Synthetic completion metadata around four genuinely verified starts.

    The fake TEST case has no snapshot. Nothing can open it successfully.
    """
    original_path = historical_source['corpus_path']
    original = json.loads(original_path.read_text())
    original['cases'][-1]['start_kind'] = 'opening'
    original_path.write_bytes(data(original))
    prefix_path = historical_source['prefix_manifest']
    prefix = json.loads(gzip.decompress(prefix_path.read_bytes()))
    prefix['source_sha256'] = _sha_file(original_path)
    prefix_path.write_bytes(gzip.compress(data(prefix), mtime=0))
    parent_dir = tmp_path/'parent'
    path, source = prepare_source(**historical_source, output_dir=parent_dir/'source')
    parent = dict(schema='sts_vantom_feature_study_v1', source=str(path),
        source_identity=source['schema']+':'+_sha_file(path), implementation=asdict(implementation()),
        configuration={k: str(v) for k, v in historical_source.items()})
    parent['configuration']['corpus'] = parent['configuration'].pop('corpus_path')
    manifest = parent_dir/'manifest.json'; manifest.write_bytes(data(parent))
    (parent_dir/'report').mkdir()
    (parent_dir/'report'/'comparisons.json').write_bytes(data(dict(status='complete', learners_completed=96,
        manifest_sha256=_sha_file(manifest), evidence='synthetic completion fixture; four native starts')))
    reservation = dict(schema='sts_feature_study_test_reservation_v1', source=parent['source_identity'],
        manifest_sha256=_sha_file(manifest), no_further_training=True, no_reselection=True,
        cases=[original['cases'][-1]['case_id']])
    (parent_dir/'test-reservation.json').write_bytes(data(reservation))
    original_path.with_name('test-opened.json').write_bytes(data(reservation))
    return manifest, historical_source


def test_development_derivative_verifies_native_cases_and_keeps_old_sources_closed(closed_parent, tmp_path):
    manifest, original = closed_parent
    lock = original['corpus_path'].with_name('test-opened.json')
    before = {p: p.read_bytes() for p in (manifest, lock, original['corpus_path'])}
    with pytest.raises(ValueError, match='closed'):
        _owners(original['corpus_path'])
    parent = json.loads(manifest.read_text())
    with pytest.raises(ValueError, match='closed'):
        StudySource(parent['source'])
    path, report = prepare_source(**original, development_parent=manifest, output_dir=tmp_path/'development')
    assert report['schema'] == DEVELOPMENT_SOURCE and report['prior_test_exposure']
    assert report['test_access'] is False and report['test_gameplay_opened'] is False
    source = open_search_source(path)
    assert source.development_only and len(source.cases) == 4
    assert set(source.registry) == set(source.histories) == set(source.cases)
    for row in source.cases.values():
        source.restore(row['case_id'], split=row['split'])
        source.history_start(row['case_id'], split=row['split'])
    with pytest.raises(ValueError, match='another split'):
        source.restore(source.split('train')[0]['case_id'], split='validation')
    with pytest.raises(ValueError, match='TEST'):
        source.split('test')
    with pytest.raises(ValueError, match='held-out'):
        source.restore('does-not-exist', split='test')
    with pytest.raises(ValueError, match='TEST'):
        source.restore_test('does-not-exist', policy='x', mode='greedy', repeat=0)
    with pytest.raises(ValueError, match='TEST'):
        StudySource(path, reservation=tmp_path/'missing-reservation.json')
    with pytest.raises(ValueError, match='TEST'):
        reserve_test(source, tmp_path/'illegal-reservation', policies={}, manifest_sha256='', limits={},
                     execution_output=tmp_path/'illegal-test')
    assert not (tmp_path/'illegal-reservation').exists()
    assert all(p.read_bytes() == raw for p, raw in before.items())
    # Cached sources must also fail closed if the original reservation changes.
    lock.write_text('{}')
    with pytest.raises(ValueError, match='provenance changed'):
        source.restore(source.split('train')[0]['case_id'], split='train')
    with pytest.raises(ValueError, match='reservation changed'):
        StudySource(path)


def test_development_provenance_cannot_invent_completion_or_replace_source(closed_parent, tmp_path):
    manifest, original = closed_parent
    context = development_context(manifest)
    assert context['splits'] == ['train', 'validation'] and context['test_access'] is False
    report = manifest.parent/'report'/'comparisons.json'
    saved = report.read_bytes()
    value = json.loads(saved); value['status'] = 'in_progress'; report.write_bytes(data(value))
    with pytest.raises(ValueError, match='completed parent'):
        development_context(manifest)
    report.write_bytes(saved)
    other_corpus = tmp_path/'other-corpus.json'
    other_corpus.write_bytes(original['corpus_path'].read_bytes())
    with pytest.raises(ValueError, match='differs from its completed parent'):
        prepare_source(**dict(original, corpus_path=other_corpus),
                       development_parent=manifest, output_dir=tmp_path/'wrong')


@pytest.mark.parametrize('dependency', ['verified_source', 'reservation_copy'])
def test_cached_development_source_binds_all_parent_provenance(closed_parent, tmp_path, dependency):
    manifest, original = closed_parent
    path, _ = prepare_source(**original, development_parent=manifest, output_dir=tmp_path/'development')
    source = open_search_source(path)
    parent = json.loads(manifest.read_text())
    parent_source = json.loads(Path(parent['source']).read_text())
    changed = (Path(parent_source['verified_source']) if dependency == 'verified_source'
               else manifest.parent/'test-reservation.json')
    assert str(changed) in {r['path'] for r in source.verified.report['dependencies']}
    changed.write_bytes(changed.read_bytes()+b'\n')
    with pytest.raises(ValueError, match='provenance changed'):
        source.restore(source.split('train')[0]['case_id'], split='train')


def test_development_load_rejects_change_during_hash_validation(closed_parent, tmp_path, monkeypatch):
    manifest, original = closed_parent
    path, _ = prepare_source(**original, development_parent=manifest, output_dir=tmp_path/'development')
    from game.agent.training import search_sources
    target = original['prefix_manifest']
    sha_file = search_sources._sha_file
    def concurrent_change(candidate):
        result = sha_file(candidate)
        if Path(candidate) == target:
            target.write_bytes(target.read_bytes()+b'\n')
        return result
    monkeypatch.setattr(search_sources, '_sha_file', concurrent_change)
    with pytest.raises(ValueError, match='changed while opening'):
        open_search_source(path)


def test_development_source_rejects_test_rows_and_scope_tampering(closed_parent, tmp_path):
    manifest, original = closed_parent
    path, report = prepare_source(**original, development_parent=manifest, output_dir=tmp_path/'development')
    changed = deepcopy(report)
    changed['cases'].append(json.loads(original['corpus_path'].read_text())['cases'][-1])
    path.write_bytes(data(changed))
    with pytest.raises(ValueError, match='population'):
        StudySource(path)
    changed = deepcopy(report); changed['test_access'] = True; path.write_bytes(data(changed))
    with pytest.raises(ValueError, match='provenance'):
        StudySource(path)


def test_all_six_models_keep_same_width_features_and_real_parameter_counts():
    parent = {'configurations': {}}
    for identity in ('ids', 'mechanical'):
        for richness in RICHNESS:
            a = StudyArchitecture(8, 'flat_mlp', FeatureSpec(richness, identity=='ids').to_dict(), study_catalog().to_dict())
            parent['configurations'][f'flat_mlp-{identity}-{richness}'] = dict(
                architecture=asdict(a), vocabulary=Vocabulary(('strike',) if identity=='ids' else ()).to_dict())
    rows = configurations(parent, 64)
    assert len(rows) == 6
    for name, row in rows.items():
        assert row['architecture']['hidden_size'] == 64 and row['architecture']['message_layers'] == 2
        old = parent['configurations'][name]
        assert row['architecture'] == dict(old['architecture'], hidden_size=64)
        assert row['vocabulary'] == old['vocabulary']
    for identity in ('ids', 'mechanical'):
        counts = [rows[f'flat_mlp-{identity}-{r}']['parameters']['total'] for r in RICHNESS]
        assert counts[0] < counts[1] < counts[2]
        assert counts[-1] > 6*counts[0]
    assert all(row['parameters']['embedding'] == 0 for name, row in rows.items() if 'mechanical' in name)


def test_fixed_width_configuration_rejects_unregistered_changes(tmp_path):
    config = dict(schema=SCHEMA, parent_manifest=str(tmp_path/'parent.json'), hidden_size=64,
                  seeds=[11,29,47], collectors=16, learner_threads=4)
    path = tmp_path/'config.json'; path.write_bytes(data(config))
    assert load_config(path) == config
    for update in ({'seeds':[11,11,47]}, {'hidden_size':True}, {'learning_rate':.001}):
        path.write_bytes(data(dict(config, **update)))
        with pytest.raises(ValueError, match='configuration'):
            load_config(path)
    from game.agent.training.study.flat_width import run
    with pytest.raises(ValueError, match='no TEST'):
        run(path, tmp_path/'unused', phase='confirm')
