"""Repository-only identity measurement for the frozen offline corpus."""

from dataclasses import asdict
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess

from game.backends.headless import combat_v0_backend, reduced_run_backend
from game.backends.live import r0i_wire
from game.content import reduced_v0
from game.contracts import headless_v0
from game.engine import map_rules, reward_rules, room_rules

from synthetic_cases import fixture_bodies


ROOT = Path(__file__).resolve().parents[2]
IDENTITY_PATH = Path(__file__).with_name("offline_fixture_identity.json")
# The accepted September 4 corpus names this exact original bridge inventory.
# Current Python regressions do not execute the subsequently changed C# bridge.
RETAINED_BRIDGE_REVISION = "778cadd1a5e24de1c316a45831ffd1aa4be4f1dc"
SOURCE_PATHS = (
    "game/contracts/headless_v0.py",
    "game/backends/live/r0i_wire.py",
    "game/backends/headless/reduced_run_backend.py",
    "game/backends/headless/combat_v0_backend.py",
    "game/backends/headless/combat_candidates.py",
    "game/backends/headless/combat_projection.py",
    "game/content/reduced_v0.py",
    "game/engine/map_rules.py",
    "game/engine/reward_rules.py",
    "game/engine/room_rules.py",
    "tests/conformance/test_headless_v0_contract.py",
    "tests/conformance/test_headless_v0_replay.py",
    "tests/conformance/test_headless_v0_public_boundary.py",
    "tests/conformance/test_headless_v0_capabilities.py",
    "bridge/Sts2AgentBridge/package/Sts2AgentBridge.json",
    "tests/differential/common_public_subset.py",
    "tests/differential/synthetic_cases.py",
)


def bridge_source_inventory(repository_root: Path) -> tuple[int, str]:
    """Hash authored bridge inputs, excluding generated directory components."""
    bridge_root = repository_root / "bridge/Sts2AgentBridge"
    source_root = bridge_root / "src"
    source_paths = (
        path for pattern in ("*.cs", "*.csproj") for path in source_root.rglob(pattern)
        if not {"bin", "obj"}.intersection(path.relative_to(source_root).parts[:-1])
    )
    bridge_paths = sorted(
        list(source_paths)
        + [bridge_root / path for path in ("Directory.Build.props", "global.json", "Sts2AgentBridge.sln", "package/Sts2AgentBridge.json")],
        key=lambda path: path.relative_to(repository_root).as_posix(),
    )
    bridge_records = "".join(
        sha256(path.read_bytes()).hexdigest() + "  " + path.relative_to(repository_root).as_posix() + "\n"
        for path in bridge_paths
    ).encode("ascii")
    return len(bridge_paths), sha256(bridge_records).hexdigest()


def _identities(bridge_inventory):
    build_path = "manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json"
    build = json.loads((ROOT / build_path).read_text())
    vector_path = ROOT / "bridge/Sts2AgentBridge/contracts/live_probe_v0/vectors"
    r0i_wire.verify_accepted_vector_inventory(vector_path)
    manifest = reduced_run_backend.ReducedRunBackend().manifest()
    bridge_count, bridge_digest = bridge_inventory
    body_hashes = {name: sha256(body).hexdigest() for name, body in sorted(fixture_bodies().items())}
    return {
        "schema": "h4_offline_common_subset_fixture_v1",
        "evidence": "structural_fixture",
        "wire_source_evidence": "bridge_fixture",
        "headless_combat_evidence": "combat_v0",
        "live_capture": "unobserved",
        "live_authority": "blocked_pending_separate_capture_request_and_retained_artifact",
        "build": {"id": build["identity"]["game"]["build_id"],
                  "release": build["identity"]["release"]["version"],
                  "identity_sha256": build["integrity"]["identity_payload_sha256"],
                  "manifest_sha256": sha256((ROOT / build_path).read_bytes()).hexdigest()},
        "wire": asdict(r0i_wire.PARSER_MANIFEST),
        "bridge": {
            "version": r0i_wire.BRIDGE_VERSION,
            "source_scope": "src/**/*.cs and src/**/*.csproj excluding bin/obj directory components; Directory.Build.props, global.json, Sts2AgentBridge.sln, package/Sts2AgentBridge.json; repository-only",
            "source_canonicalization": "sha256 + two spaces + repository-relative path + LF; sorted by path",
            "source_file_count": bridge_count,
            "source_inventory_sha256": bridge_digest,
            "binary_verification": "unobserved; no bridge build or installed binary accessed",
        },
        "headless": {
            "contract": headless_v0.CONTRACT_VERSION,
            "contract_fingerprint": headless_v0.CONTRACT_FINGERPRINT,
            "backend_version": reduced_run_backend.BACKEND_VERSION,
            "backend_fingerprint": reduced_run_backend.BACKEND_FINGERPRINT,
            "rules_version": reduced_run_backend.RULES_VERSION,
            "rules_fingerprint": reduced_run_backend.RULES_FINGERPRINT,
            "content_version": reduced_v0.CONTENT_VERSION,
            "content_fingerprint": reduced_v0.CONTENT_FINGERPRINT,
            "combat_rules_fingerprint": combat_v0_backend.RULES_FINGERPRINT,
            "map_rules_fingerprint": map_rules.RULES_FINGERPRINT,
            "reward_rules_fingerprint": reward_rules.REWARD_RULES_FINGERPRINT,
            "room_rules_fingerprint": room_rules.ROOM_RULES_FINGERPRINT,
            "component_evidence": [item.to_dict() for item in manifest.evidence],
        },
        "source_sha256": {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_PATHS},
        "synthetic_body_sha256": body_hashes,
        "synthetic_body_inventory_sha256": sha256("".join(digest + "  " + name + "\n" for name, digest in body_hashes.items()).encode("ascii")).hexdigest(),
    }


def current_identities():
    return _identities(bridge_source_inventory(ROOT))


def verify_identities(expected):
    """No blessing or auto-update on mismatch; coordinator must review a new pin."""
    if json.dumps(expected, sort_keys=True) != json.dumps(current_identities(), sort_keys=True):
        raise ValueError("offline fixture identity mismatch")


def retained_bridge_source_inventory() -> tuple[int, str]:
    """Measure original Git blobs, never substitute today's bridge for old evidence."""
    prefix = "bridge/Sts2AgentBridge/"
    fixed = {prefix + name for name in (
        "Directory.Build.props", "global.json", "Sts2AgentBridge.sln",
        "package/Sts2AgentBridge.json",
    )}
    tree = subprocess.run(
        ["git", "ls-tree", "-rz", RETAINED_BRIDGE_REVISION, "--", prefix],
        cwd=ROOT, check=True, capture_output=True, timeout=10,
    ).stdout
    entries = []
    for entry in tree.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        path = raw_path.decode("ascii")
        relative = Path(path).relative_to(prefix)
        authored = (relative.parts[0] == "src" and relative.suffix in (".cs", ".csproj")
                    and not {"bin", "obj"}.intersection(relative.parts[:-1]))
        if path in fixed or authored:
            if kind != b"blob" or mode not in (b"100644", b"100755"):
                raise ValueError("retained bridge source is not a regular Git blob")
            entries.append((path, oid))
    entries.sort()
    blobs = subprocess.run(
        ["git", "cat-file", "--batch"], cwd=ROOT, check=True, capture_output=True,
        input=b"".join(oid + b"\n" for _, oid in entries), timeout=10,
    ).stdout
    stream = io.BytesIO(blobs)
    records = []
    for path, oid in entries:
        returned_oid, kind, length = stream.readline().split()
        if returned_oid != oid or kind != b"blob":
            raise ValueError("retained bridge Git blob mismatch")
        body = stream.read(int(length))
        if len(body) != int(length) or stream.read(1) != b"\n":
            raise ValueError("truncated retained bridge Git blob")
        records.append(sha256(body).hexdigest() + "  " + path + "\n")
    if stream.read():
        raise ValueError("unexpected retained bridge Git output")
    return len(entries), sha256("".join(records).encode("ascii")).hexdigest()


def retained_fixture_identities():
    """Current Python inputs against the original, source-bound bridge reference.

    This does not establish current-bridge fidelity. Missing Git history is an
    error; there is no fallback to trusted constants or today's bridge sources.
    """
    return _identities(retained_bridge_source_inventory())


def verify_retained_fixture_identities(expected):
    if json.dumps(expected, sort_keys=True) != json.dumps(retained_fixture_identities(), sort_keys=True):
        raise ValueError("retained offline fixture identity mismatch")
