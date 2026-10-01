"""Container compatibility and lossless, bounded migration failure cases."""
import gzip
import hashlib
import json
import os
import time
from pathlib import Path

import pytest

from game.agent.recording import TrajectoryWriter, load_trajectory
from game.agent.trace_storage import logical_path, open_trajectory, trajectory_digest
from game.agent.trace_compression import compress_group, compress_traces
from game.agent.analysis.sources import discover
from game.agent.analysis.report import build_report
from game.agent.analysis.server import AnalysisStore
from .test_analysis import record, panel


def zipped(path):
    return path.with_name(path.name+'.gz')


def test_migration_preserves_manifest_hashes_legacy_paths_and_inspection(tmp_path):
    path = record(tmp_path/'public')
    panel(path.parent, [path])
    original = path.read_bytes()
    expected = load_trajectory(path)
    row = compress_group([path])
    assert row['sha256'] == hashlib.sha256(original).hexdigest()
    assert row['compressed_bytes'] < len(original)
    assert not path.exists() and zipped(path).is_file()
    assert load_trajectory(path) == load_trajectory(zipped(path)) == expected
    assert trajectory_digest(zipped(path)) == expected.sha256
    assert discover([path]) == discover([zipped(path)]) == [path]
    exported = build_report([path.parent], tmp_path/'export')
    assert exported['runs'][0]['sha256'] == expected.sha256
    assert AnalysisStore(tmp_path/'export').decision('1'*32, 0)['action']['ref'] == expected.transitions[0].action.ref
    assert compress_traces([path.parent])['groups'] == 0


def test_gzip_writer_preserves_bytes_and_uses_shared_publication_reservation(tmp_path):
    plain = record(tmp_path/'input')
    trace = load_trajectory(plain)
    target = tmp_path/('new.trajectory.jsonl.gz')
    with TrajectoryWriter(target, trace.metadata, trace.initial) as writer:
        with pytest.raises(FileExistsError):
            TrajectoryWriter(logical_path(target), trace.metadata, trace.initial)
        for step in trace.transitions:
            writer.append(step.action, step.execution, step.successor)
        writer.finish(trace.outcome)
    assert load_trajectory(target) == trace
    with open_trajectory(target) as stream:
        assert stream.read() == plain.read_bytes()
    with pytest.raises(FileExistsError):
        TrajectoryWriter(logical_path(target), trace.metadata, trace.initial)
    with pytest.raises(FileExistsError):
        TrajectoryWriter(zipped(plain), trace.metadata, trace.initial)


@pytest.mark.parametrize('corrupt', [lambda b:b[:-8], lambda b:b[:-1]+bytes([b[-1]^1]),
                                    lambda b:b+gzip.compress(b'{}\n')])
def test_gzip_trailer_and_trailing_decompressed_records_are_checked(tmp_path, corrupt):
    path = record(tmp_path)
    zipped(path).write_bytes(corrupt(gzip.compress(path.read_bytes())))
    with pytest.raises(ValueError):
        load_trajectory(zipped(path))


def test_existing_plain_file_is_never_silently_bypassed(tmp_path):
    path = record(tmp_path)
    zipped(path).write_bytes(gzip.compress(path.read_bytes()))
    assert discover([path.parent]) == [path]
    path.write_bytes(b'broken original')
    with pytest.raises(ValueError):
        load_trajectory(path)
    with pytest.raises(ValueError, match='different contents'):
        compress_group([path])
    assert path.read_bytes() == b'broken original'


def test_hardlinked_aliases_share_compressed_storage_and_restart_safely(tmp_path):
    first = record(tmp_path/'first')
    alias = tmp_path/'second'/first.name
    alias.parent.mkdir()
    os.link(first, alias)
    zipped(first).write_bytes(gzip.compress(first.read_bytes()))  # Simulate interrupted publication.
    preview = compress_traces([tmp_path])
    assert preview['groups'] == 1 and preview['paths'] == 2
    report = tmp_path/'migration.jsonl'
    result = compress_traces([tmp_path], apply=True, report=report, workers=2)
    assert result['compressed_groups'] == 1 and result['failed_groups'] == 0
    assert not first.exists() and not alias.exists()
    assert zipped(first).stat().st_ino == zipped(alias).stat().st_ino
    assert load_trajectory(first) == load_trajectory(alias)
    assert compress_traces([tmp_path])['groups'] == 0


def test_external_alias_partial_and_private_trees_are_retained(tmp_path):
    first = record(tmp_path/'public')
    outside = tmp_path/'external.trajectory.jsonl'
    os.link(first, outside)
    assert compress_group([first])['reason'] == 'hard_links_outside_selected_paths'
    outside.unlink()
    first.with_name(first.name+'.partial').write_bytes(b'pending')
    assert compress_group([first])['reason'] == 'unfinished_recording_present'
    private = record(tmp_path/'private')
    assert private not in discover([tmp_path])
    with pytest.raises(ValueError, match='public plain'):
        compress_group([private])


def test_symlink_fallback_and_destinations_are_rejected(tmp_path):
    first = record(tmp_path/'public')
    secret = tmp_path/'secret'; secret.write_bytes(b'untouched')
    zipped(first).symlink_to(secret)
    with pytest.raises(ValueError, match='symlink'):
        compress_group([first])
    first.unlink()
    with pytest.raises(ValueError, match='symlink'):
        load_trajectory(first)
    assert secret.read_bytes() == b'untouched'


def test_failed_verification_keeps_original_and_cleans_only_own_temporary(tmp_path, monkeypatch):
    import game.agent.trace_compression as migration
    first = record(tmp_path)
    original = first.read_bytes()
    monkeypatch.setattr(migration, '_verify', lambda *_: (_ for _ in ()).throw(ValueError('bad compression')))
    with pytest.raises(ValueError, match='bad compression'):
        compress_group([first])
    assert first.read_bytes() == original and not zipped(first).exists()
    assert not list(tmp_path.glob('*.partial'))


def test_modified_source_is_not_removed(tmp_path, monkeypatch):
    import game.agent.trace_compression as migration
    first = record(tmp_path)
    verify = migration._verify
    def concurrent_change(*args):
        identity = verify(*args)
        first.write_bytes(b'changed while compressing')
        return identity
    monkeypatch.setattr(migration, '_verify', concurrent_change)
    with pytest.raises(ValueError, match='changed before removing'):
        compress_group([first])
    assert first.read_bytes() == b'changed while compressing'


def test_independent_existing_compressed_aliases_retain_originals(tmp_path):
    first = record(tmp_path)
    alias = tmp_path/'alias.trajectory.jsonl'
    os.link(first, alias)
    for path in (first, alias):
        zipped(path).write_bytes(gzip.compress(path.read_bytes()))
    with pytest.raises(ValueError, match='do not share'):
        compress_group([first, alias])
    assert first.exists() and alias.exists()


def test_compressed_sibling_changed_after_verification_keeps_original(tmp_path, monkeypatch):
    import game.agent.trace_compression as migration
    first = record(tmp_path)
    original = first.read_bytes()
    compressed = zipped(first)
    compressed.write_bytes(gzip.compress(original))
    verify = migration._verify
    def concurrent_change(path, *args):
        identity = verify(path, *args)
        if path == compressed:
            compressed.write_bytes(b'changed after verification')
        return identity
    monkeypatch.setattr(migration, '_verify', concurrent_change)
    with pytest.raises(ValueError, match='changed before publication'):
        compress_group([first])
    assert first.read_bytes() == original


def test_cancellation_stops_queued_groups_and_journals_running_results(tmp_path, monkeypatch):
    import game.agent.trace_compression as migration
    path = record(tmp_path)
    started = []
    def work(paths):
        started.append(paths)
        time.sleep(.02)
        return {'status': 'retained', 'paths': [str(path)], 'reason': 'test_only'}
    monkeypatch.setattr(migration, 'compression_groups', lambda _: [[path]]*100)
    monkeypatch.setattr(migration, 'compress_group', work)
    report = tmp_path/'migration.jsonl'
    def stop(*_):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        compress_traces([tmp_path], apply=True, report=report, workers=1, progress=stop)
    rows = [json.loads(line) for line in report.read_text().splitlines()]
    assert len(started) < 10
    assert rows[-1]['status'] == 'interrupted'
    assert sum(row['status'] == 'retained' for row in rows) == len(started)
    assert path.exists()
