"""Lossless trajectory containers; identities always describe the JSONL bytes."""
from contextlib import contextmanager
import gzip
import hashlib
from pathlib import Path
import zlib

SUFFIX = '.trajectory.jsonl'
COMPRESSED_SUFFIX = SUFFIX+'.gz'


def is_trajectory(path):
    return Path(path).name.endswith((SUFFIX, COMPRESSED_SUFFIX))


def logical_path(path):
    path = Path(path)
    if not is_trajectory(path):
        raise ValueError('Only published public trajectories can be opened')
    return path.with_suffix('') if path.name.endswith(COMPRESSED_SUFFIX) else path


def storage_path(path):
    """Resolve old report names, never mask a present but invalid plain file."""
    path = Path(path)
    logical_path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Trajectory paths must not contain symlinks')
    if path.name.endswith(SUFFIX) and not path.exists():
        path = path.with_name(path.name+'.gz')
    if path.is_symlink():
        raise ValueError('Trajectory paths must not contain symlinks')
    return path


@contextmanager
def open_trajectory(path):
    """Stream exact canonical bytes from either a plain or gzip container."""
    path = storage_path(path)
    try:
        with path.open('rb') as raw:
            if path.name.endswith(COMPRESSED_SUFFIX):
                with gzip.GzipFile(fileobj=raw, mode='rb') as source:
                    yield source
            else:
                yield raw
    except (gzip.BadGzipFile, EOFError, zlib.error) as error:
        raise ValueError('Invalid or truncated compressed trajectory') from error


def trajectory_digest(path):
    digest = hashlib.sha256()
    with open_trajectory(path) as source:
        for chunk in iter(lambda: source.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()
