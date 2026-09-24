"""Public implementation identities; never inspect a running engine or its RNG."""
from dataclasses import dataclass
import hashlib
from pathlib import Path

TARGET = 'sts2-v0.107.1-steam-23811903'
ENCODING = 'sts_public_json_v2'
POLICY = 'full_run_demo_v2'


@dataclass(frozen=True, slots=True)
class Implementation:
    target: str
    build: str
    rules: str
    policy: str


def _digest(root, files):
    digest = hashlib.sha256()
    for path in sorted(files):
        name = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(name).to_bytes(8, 'big') + name)
        digest.update(len(data).to_bytes(8, 'big') + data)
    return digest.hexdigest()


def implementation():
    """Hash shipped Python sources, including dirty-checkout edits, identically in a wheel."""
    root = Path(__file__).resolve().parents[1]
    return Implementation(TARGET, _digest(root, root.rglob('*.py')),
                          _digest(root, (root / 'headless').rglob('*.py')),
                          POLICY + ':' + _digest(root, [root / 'agent/full_policy.py']))
