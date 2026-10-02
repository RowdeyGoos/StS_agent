"""Verified, restartable compression of explicitly selected public recordings."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import time

from .trace_storage import SUFFIX
from .performance import ARTIFACT_WORKER_LIMIT


def _fingerprint(value):
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


def _sync(directory):
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def compression_groups(inputs):
    from .analysis.sources import discover
    groups = {}
    for path in discover(inputs):
        if not path.name.endswith(SUFFIX) or not path.exists():
            continue
        value = path.lstat()
        if not stat.S_ISREG(value.st_mode):
            raise ValueError('Expected a regular public trajectory')
        groups.setdefault((value.st_dev, value.st_ino), []).append(path)
    return list(groups.values())


def _verify(path, expected_sha, expected_size):
    digest, size = hashlib.sha256(), 0
    initial = path.lstat()
    if not stat.S_ISREG(initial.st_mode):
        raise ValueError('Compressed destination must be a regular file')
    identity = _fingerprint(initial)
    with path.open('rb') as raw:
        if _fingerprint(os.fstat(raw.fileno())) != identity:
            raise ValueError('Compressed file changed before verification')
        with gzip.GzipFile(fileobj=raw, mode='rb') as source:
            for chunk in iter(lambda: source.read(1024*1024), b''):
                size += len(chunk)
                if size > expected_size:
                    raise ValueError('Compressed sibling has different contents')
                digest.update(chunk)
        if _fingerprint(os.fstat(raw.fileno())) != identity:
            raise ValueError('Compressed file changed during verification')
    if _fingerprint(path.lstat()) != identity:
        raise ValueError('Compressed file changed during verification')
    if size != expected_size or digest.hexdigest() != expected_sha:
        raise ValueError('Compressed sibling has different contents')
    return identity


def compress_group(paths):
    """Publish/verify every alias before removing any original in this group."""
    paths = [Path(p).absolute() for p in paths]
    if not paths or len(paths) != len(set(paths)):
        raise ValueError('Expected distinct public trajectory aliases')
    from .analysis.sources import public_path
    for path in paths:
        if (not path.name.endswith(SUFFIX) or not public_path(path)
                or any(p.is_symlink() for p in (path, *path.parents))):
            raise ValueError('Select public plain trajectories without symlinks')
    first = paths[0]
    initial = first.lstat()
    if not stat.S_ISREG(initial.st_mode):
        raise ValueError('Expected a regular public trajectory')
    fingerprint = _fingerprint(initial)
    result = {'paths': [str(p) for p in paths], 'original_bytes': initial.st_size}
    if initial.st_nlink != len(paths):
        return {**result, 'status': 'retained', 'reason': 'hard_links_outside_selected_paths'}
    if any(p.with_name(p.name+'.partial').exists() for p in paths):
        return {**result, 'status': 'retained', 'reason': 'unfinished_recording_present'}
    for path in paths:
        if _fingerprint(path.lstat()) != fingerprint:
            raise ValueError('Trajectory aliases changed before compression')
    destinations = [p.with_name(p.name+'.gz') for p in paths]
    if any(p.is_symlink() for p in destinations):
        raise ValueError('Compressed destinations must not be symlinks')
    started = time.perf_counter()
    fd, temporary = tempfile.mkstemp(prefix=first.name+'.compress-', suffix='.partial', dir=first.parent)
    temporary = Path(temporary)
    try:
        digest, size = hashlib.sha256(), 0
        with os.fdopen(fd, 'wb') as target, first.open('rb') as source:
            if _fingerprint(os.fstat(source.fileno())) != fingerprint:
                raise ValueError('Trajectory changed before compression')
            os.fchmod(target.fileno(), stat.S_IMODE(initial.st_mode))
            with gzip.GzipFile(filename='', fileobj=target, mode='wb', compresslevel=6, mtime=0) as compressed:
                for chunk in iter(lambda: source.read(1024*1024), b''):
                    compressed.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            target.flush()
            os.utime(target.fileno(), ns=(initial.st_atime_ns, initial.st_mtime_ns))
            os.fsync(target.fileno())
            if _fingerprint(os.fstat(source.fileno())) != fingerprint or size != initial.st_size:
                raise ValueError('Trajectory changed while compressing')
        sha = digest.hexdigest()
        published_identity = _verify(temporary, sha, size)
        # No-clobber publication also recovers an interrupted prior migration.
        published = temporary
        existing_identity = None
        for destination in destinations:
            if destination.exists():
                if destination.is_symlink() or not destination.is_file():
                    raise ValueError('Compressed destination must be a regular file')
                identity = _verify(destination, sha, size)
                if existing_identity is not None and identity != existing_identity:
                    raise ValueError('Existing compressed aliases do not share one file')
                existing_identity = identity
                published = destination
                published_identity = identity
        with published.open('rb') as source:
            if _fingerprint(os.fstat(source.fileno())) != published_identity:
                raise ValueError('Compressed file changed before publication')
            os.fsync(source.fileno())
        for destination in destinations:
            try:
                os.link(published, destination)
            except FileExistsError:
                if destination.is_symlink() or not destination.is_file():
                    raise ValueError('Compressed destination must be a regular file')
                _verify(destination, sha, size)
        for directory in {p.parent for p in paths}:
            _sync(directory)
        for path in paths:
            if path.is_symlink() or _fingerprint(path.lstat()) != fingerprint:
                raise ValueError('Trajectory changed before removing its plain copy')
        for path in paths:
            # A new external alias is retained; never claim its space was freed.
            if path.lstat().st_nlink > len(paths):
                raise ValueError('Trajectory hard links changed during compression')
        for path, destination in zip(paths, destinations):
            if destination.is_symlink() or _fingerprint(destination.lstat()) != published_identity:
                raise ValueError('Compressed aliases changed during publication')
        for path, destination in zip(paths, destinations):
            if _fingerprint(path.lstat()) != fingerprint:
                raise ValueError('Trajectory changed before removing its plain copy')
            if destination.is_symlink() or _fingerprint(destination.lstat()) != published_identity:
                raise ValueError('Compressed aliases changed before removing the plain copy')
            path.unlink()
        for directory in {p.parent for p in paths}:
            _sync(directory)
        return {**result, 'status': 'compressed', 'sha256': sha,
                'compressed_bytes': published_identity[2], 'seconds': time.perf_counter()-started}
    finally:
        temporary.unlink(missing_ok=True)


def compress_traces(inputs, *, apply=False, workers=1, report=None, progress=None):
    """Default preview; apply uses bounded workers and an append-only result log."""
    if type(workers) is not int or not 1 <= workers <= ARTIFACT_WORKER_LIMIT:
        raise ValueError(f'Choose 1–{ARTIFACT_WORKER_LIMIT} compression workers')
    if apply and report is None:
        raise ValueError('Compression requires a new report path')
    groups = compression_groups(inputs)
    summary = {'status': 'preview', 'groups': len(groups), 'paths': sum(map(len, groups)),
               'original_bytes': sum(g[0].stat().st_size for g in groups),
               'compressed_groups': 0, 'retained_groups': 0, 'failed_groups': 0,
               'removed_plain_bytes': 0, 'compressed_bytes': 0}
    if not apply:
        return summary
    started = time.perf_counter()
    with Path(report).open('x', encoding='utf-8') as journal, ThreadPoolExecutor(max_workers=workers) as pool:
        def write(value):
            journal.write(json.dumps(value, sort_keys=True)+'\n')
            journal.flush()
        write({'schema': 'sts_trace_compression_v1', 'inputs': [str(p) for p in inputs], **summary})
        futures, pending = {}, iter(groups)
        completed = 0
        def submit():
            paths = next(pending, None)
            if paths is not None:
                futures[pool.submit(compress_group, paths)] = paths
        def receive(future):
            try:
                row = future.result()
            except Exception as error:
                row = {'status': 'failed', 'paths': [str(p) for p in futures[future]],
                       'reason': type(error).__name__+': '+str(error)}
            write(row)
            futures.pop(future)
            if row['status'] == 'compressed':
                summary['compressed_groups'] += 1
                summary['removed_plain_bytes'] += row['original_bytes']
                summary['compressed_bytes'] += row['compressed_bytes']
            else:
                summary['retained_groups' if row['status'] == 'retained' else 'failed_groups'] += 1
        try:
            for _ in range(workers):
                submit()
            while futures:
                ready, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in ready:
                    receive(future)
                    completed += 1
                    if progress:
                        progress(completed, len(groups), summary)
                    submit()
        except BaseException:
            # Never run the whole queued migration after Ctrl-C or a log failure.
            pool.shutdown(wait=True, cancel_futures=True)
            try:
                for future in list(futures):
                    if not future.cancelled():
                        receive(future)
                write({**summary, 'status': 'interrupted', 'seconds': time.perf_counter()-started})
                os.fsync(journal.fileno())
            except OSError:
                pass  # Already-verified files remain loadable even if the journal disk failed.
            raise
        summary.update(status='failed' if summary['failed_groups'] else 'complete', seconds=time.perf_counter()-started)
        write(summary)
        os.fsync(journal.fileno())
    return summary
