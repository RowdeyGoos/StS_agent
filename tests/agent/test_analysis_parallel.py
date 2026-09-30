"""Episode-level parity and failure cleanup for the public analysis export."""
from contextlib import closing
from dataclasses import replace
import multiprocessing
import os
import threading
import time

import pytest

from game.agent.analysis.parallel import map_episodes
from game.agent.analysis.report import build_report
from game.agent.analysis.sources import digest
from .test_analysis import panel, public, record


def _children():
    return {p.pid for p in multiprocessing.active_children()}


def _assert_clean(before):
    assert _children() == before
    assert not [t for t in threading.enumerate() if t.name == 'sts-analysis-transfer']


def _die(_):
    os._exit(7)


def _slow(job):
    if job:
        time.sleep(60)
    return job


def test_parallel_export_matches_serial_decisions_rows_and_pairing(tmp_path):
    root = tmp_path/'input'
    state = public()
    first = record(root, policy='one', choices=[(state.candidates[0], state)]*35)
    second = record(root, episode='2'*32, policy='two', choices=[(state.candidates[0], state)]*19)
    panel(root, [first, second])
    before = _children()
    serial = build_report([root], tmp_path/'serial', goal='act1')
    parallel = build_report([root], tmp_path/'parallel', goal='act1', workers=2)
    for key in ('runs', 'training', 'sources', 'pending', 'paired_cases_verified'):
        assert serial[key] == parallel[key]
    for chunk in (tmp_path/'serial/decisions').iterdir():
        assert digest(chunk) == digest(tmp_path/'parallel/decisions'/chunk.name)
    assert parallel['paired_cases_verified'] == 1
    assert parallel['export']['workers_used'] == 2
    _assert_clean(before)


def test_parallel_reserves_metadata_identity_even_with_different_filenames(tmp_path):
    source = record(tmp_path/'input')
    source.with_name('alias.trajectory.jsonl').write_bytes(source.read_bytes())
    before = _children()
    with pytest.raises(ValueError, match='Duplicate trajectory'):
        build_report([source.parent], tmp_path/'report', workers=2)
    assert not (tmp_path/'report').exists()
    _assert_clean(before)


@pytest.mark.parametrize('failure', ['pair', 'corruption', 'interrupt'])
def test_parallel_failure_never_publishes_report_and_stops_children(tmp_path, failure):
    root = tmp_path/'input'
    first = record(root, policy='one')
    second = record(root, episode='2'*32, policy='two', start=replace(public(), context=replace(public().context, kind='rest')))
    if failure == 'pair':
        panel(root, [first, second])
    elif failure == 'corruption':
        second.write_bytes(second.read_bytes().replace(b'"reward":0', b'"reward":1'))
    def progress(*_):
        if failure == 'interrupt':
            raise KeyboardInterrupt
    before = _children()
    with pytest.raises(KeyboardInterrupt if failure == 'interrupt' else ValueError):
        build_report([root], tmp_path/'report', workers=2, progress=progress)
    assert not (tmp_path/'report/report.json').exists()
    _assert_clean(before)


def test_dead_worker_fails_without_retry_or_leaked_children():
    before = _children()
    with closing(map_episodes(_die, [0, 1], 2)) as results:
        with pytest.raises(RuntimeError, match='exited without a result'):
            list(results)
    _assert_clean(before)


def test_generator_cancellation_terminates_a_busy_sibling():
    before = _children()
    started = time.monotonic()
    with closing(map_episodes(_slow, [0, 1], 2)) as results:
        assert next(results) == (0, 0)
    assert time.monotonic()-started < 10
    _assert_clean(before)


@pytest.mark.parametrize('workers', [0, 9, True, 1.5])
def test_invalid_worker_count_rejected_before_creating_output(tmp_path, workers):
    with pytest.raises(ValueError, match='workers'):
        build_report([], tmp_path/'report', workers=workers)
    assert not (tmp_path/'report').exists()
