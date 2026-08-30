#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping

EXIT_OK = 0
EXIT_INVALID_INVOCATION = 2
EXIT_UNSAFE_BOUNDARY = 3
EXIT_MISMATCH = 4
EXIT_INTERNAL = 5
_HEX_64 = re.compile(r"[0-9a-f]{64}\Z")


class ToolFailure(Exception):
    def __init__(self, exit_code: int, error_code: str) -> None:
        super().__init__(error_code)
        self.exit_code = exit_code
        self.error_code = error_code


def fail(exit_code: int, error_code: str) -> None:
    raise ToolFailure(exit_code, error_code)


def _require_hex_64(value: str, label: str) -> str:
    if _HEX_64.fullmatch(value) is None:
        fail(EXIT_INVALID_INVOCATION, f"invalid_{label}")
    return value


def _path_components(path: Path) -> list[Path]:
    components: list[Path] = []
    current = path
    while current != current.parent:
        components.append(current)
        current = current.parent
    components.reverse()
    return components


def _reject_symlink_components(path: Path) -> None:
    for component in _path_components(path):
        try:
            metadata = component.lstat()
        except OSError:
            fail(EXIT_UNSAFE_BOUNDARY, "missing_input_component")
        if stat.S_ISLNK(metadata.st_mode):
            fail(EXIT_UNSAFE_BOUNDARY, "symlink_path_component")


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))


def _run_cli(operation: Callable[[], dict[str, object]]) -> int:
    try:
        payload = operation()
        _emit(payload)
        return EXIT_OK
    except KeyboardInterrupt:
        _emit({"schema_version": 1, "status": "failed", "code": "interrupted"})
        return EXIT_INTERNAL
    except ToolFailure as failure:
        _emit({"schema_version": 1, "status": "failed", "code": failure.error_code})
        return failure.exit_code
    except Exception:
        _emit({"schema_version": 1, "status": "failed", "code": "internal_failure"})
        return EXIT_INTERNAL


def main(operation: Callable[[], dict[str, object]]) -> None:
    raise SystemExit(_run_cli(operation))

INPUT_SET_ID = "r0a_preliminary_menu_smoke_inputs_v1"
_SELF_RELATIVE = Path(
    "bridge/Sts2AgentBridge/tools/verify_live_campaign_inputs.py"
)
_REQUEST_RELATIVE = Path("docs/PHASE_1_R0A_LIVE_CAMPAIGN_REQUEST.md")
_ARTIFACT_ROOT = Path("/private/tmp/sts-r0a-final-output.5HNUil")
_OS_SHELL = Path("/bin/bash")
_OS_PYTHON_LAUNCHER = Path("/usr/bin/python3")
_OS_PYTHON_EXECUTABLE = Path("/Library/Developer/CommandLineTools/usr/bin/python3")
_OS_PYTHON_EXECUTABLE_LINK = (
    "../../Library/Frameworks/Python3.framework/Versions/3.9/bin/python3"
)
_OS_PYTHON_RUNTIME_LINK = Path(
    "/Library/Developer/CommandLineTools/Library/Frameworks/"
    "Python3.framework/Versions/3.9/bin/python3"
)
_OS_PYTHON_RUNTIME_LINK_TARGET = "python3.9"
_OS_PYTHON_RUNTIME = Path(
    "/Library/Developer/CommandLineTools/Library/Frameworks/"
    "Python3.framework/Versions/3.9/bin/python3.9"
)
_OS_PYTHON_VERSION = (3, 9, 6)


@dataclass(frozen=True)
class _Record:
    label: str
    scope: str
    relative_path: str
    sha256: str
    size: int = 0
    link_count: int = 1
    uid: int | None = None
    mode: int | None = None


_RECORDS = (
    _Record(
        "target_manifest",
        "repo",
        "manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json",
        "ea9046a6a66e2388be3fb1db4e287e0982ae1b3772bec28546a40ef48c23b470",
        11807,
    ),
    _Record(
        "enabled_config",
        "repo",
        "bridge/Sts2AgentBridge/contracts/live_probe_v0/config_enabled.json",
        "f8c6ff9592fa330cc9317cd63200c9ee5b0f8023c23efc328f04eea57d6dffea",
        129,
    ),
    _Record(
        "surface_policy",
        "repo",
        "bridge/Sts2AgentBridge/contracts/live_probe_v0/forbidden_surface.json",
        "798c7b809de1db1765ec416dd73e9a6f1757b4b9115ea2323ef603b1966dd9a7",
        9584,
    ),
    _Record(
        "tool_common",
        "repo",
        "bridge/Sts2AgentBridge/tools/tool_common.py",
        "57283b9aafe98579b91e1293948677fb498951fe38375841c71fa2db9597bd1e",
        10098,
    ),
    _Record(
        "verify_package",
        "repo",
        "bridge/Sts2AgentBridge/tools/verify_package.py",
        "e21948fcbac48b4ad9df8ccfcc8c20d957c97fb3ec78b09eeb0572dd8b02a690",
        1435,
    ),
    _Record(
        "verify_clean_install",
        "repo",
        "bridge/Sts2AgentBridge/tools/verify_clean_install.py",
        "552ab2e2a051f563f9c474368860de2e7042de0e86c3a6a8a6ad34aac9148b00",
        6625,
    ),
    _Record(
        "verify_operator_config",
        "repo",
        "bridge/Sts2AgentBridge/tools/verify_operator_config.py",
        "f6d08adae0b13ce69a595ef2d3891655e9447fb63e04c1cd927f3232db25a46c",
        8140,
    ),
    _Record(
        "verify_operator_config_fixtures",
        "repo",
        "bridge/Sts2AgentBridge/tools/verify_operator_config_fixtures.py",
        "d6c12933f11e5e1642ffcc8b2824316b2b9588fe094ada9655608cc96bb93c1d",
        17078,
    ),
    _Record(
        "check_live_runtime",
        "repo",
        "bridge/Sts2AgentBridge/tools/check_live_runtime.py",
        "43ab6f1375486336dffd6343265ed7605c15ba4612f23cfc97086d03a9b91ccc",
        12981,
    ),
    _Record(
        "check_live_runtime_fixtures",
        "repo",
        "bridge/Sts2AgentBridge/tools/check_live_runtime_fixtures.py",
        "64cab3009a98ee1c86441b20ee81bbce1daf35cd445f3b6e89816654f01c13ad",
        18354,
    ),
    _Record(
        "verify_live_campaign_inputs_fixtures",
        "repo",
        "bridge/Sts2AgentBridge/tools/verify_live_campaign_inputs_fixtures.py",
        "4751e9a5f9dab3146a9ad290b4f7a382dc39789426fa322c279873ed3b452274",
        14724,
    ),
    _Record(
        "manage_live_campaign",
        "repo",
        "bridge/Sts2AgentBridge/tools/manage_live_campaign.py",
        "a7177b3a6440770754abd1a727d55a949da233813367f14011e382a32dddab92",
        96235,
    ),
    _Record(
        "manage_live_campaign_fixtures",
        "repo",
        "bridge/Sts2AgentBridge/tools/manage_live_campaign_fixtures.py",
        "c654e6e0bf55ceb08bb7c59ca0f1ede601000c779c8c562f0eed11806f18f008",
        71843,
    ),
    _Record(
        "probe_live",
        "repo",
        "bridge/Sts2AgentBridge/tools/probe_live.py",
        "2ed5a41b606aced24b3d13d5445f054f01d0c1410a1f66ab1dcbcca026e889aa",
        18082,
    ),
    _Record(
        "probe_live_fixtures",
        "repo",
        "bridge/Sts2AgentBridge/tools/probe_live_fixtures.py",
        "5d1bcb1c420f08be19bccac327cc7459dc850442eeb547a06d1e040a9c33bb3f",
        8314,
    ),
    _Record(
        "br0_preflight",
        "repo",
        "docs/PHASE_1_BR0_PREFLIGHT.md",
        "ae90bc33e08cf38b152dc110c4805b39ca329a5002cf66e9788519e0743b1ea3",
        57870,
    ),
    _Record(
        "restricted_bridge_design",
        "repo",
        "docs/PHASE_1_RESTRICTED_BRIDGE_DESIGN.md",
        "adeb4eb8de55812649bdc38a0519b59d7b265c970f2ef3befa6ecf17a128a38e",
        37456,
    ),
    _Record(
        "implementation_evidence",
        "repo",
        "docs/research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md",
        "e514c5f08c949062a61092d723e63f339c089dbaa8aa163b0de789205531e2a6",
        26505,
    ),
    _Record(
        "canonical_dll",
        "artifact",
        "Sts2AgentBridge.dll",
        "ebb9423d61bdf942904995e99c3b8bc5f5753eb052b134edfce25d5e1148733f",
        77824,
    ),
    _Record(
        "loader_manifest",
        "artifact",
        "Sts2AgentBridge.json",
        "622d5fbcb301ee8ba59223095e27a6558a2d4b94a63c9117f979dd2bb451ab53",
        316,
    ),
    _Record(
        "canonical_zip",
        "artifact",
        "Sts2AgentBridge-0.1.0.zip",
        "eeaaec5f6313a6ae4cf2e843d8380b4a7a0421c82989f1147cfe71c54f2eba4a",
        78456,
    ),
    _Record(
        "os_shell",
        "os",
        "shell",
        "fde343ee184953c1fa1185abddeaa8be61c6acbebae4eb54db5d6b55b09a5755",
        1293840,
        1,
        0,
        0o555,
    ),
    _Record(
        "os_python_launcher",
        "os",
        "launcher",
        "179301dcb41ea78accc3fa0048a7e6f6710d891945a751a34addd622020c1818",
        118928,
        78,
        0,
        0o755,
    ),
    _Record(
        "os_python_runtime",
        "os",
        "runtime",
        "bdea59019a38eb6600cc9e71e984a97fedadc406448431281e7657030f54987e",
        102352,
        1,
        0,
        0o755,
    ),
)


def _parse_args(arguments: list[str] | None = None) -> tuple[str, str]:
    values = sys.argv[1:] if arguments is None else arguments
    if len(values) != 4:
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    allowed = frozenset(("--expected-self-sha256", "--expected-request-sha256"))
    parsed: dict[str, str] = {}
    for offset in range(0, len(values), 2):
        name = values[offset]
        if name not in allowed or name in parsed:
            fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
        parsed[name] = values[offset + 1]
    if set(parsed) != allowed:
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    return (
        _require_hex_64(parsed["--expected-self-sha256"], "self_sha256"),
        _require_hex_64(parsed["--expected-request-sha256"], "request_sha256"),
    )


def _relative_path(value: str) -> Path:
    path = Path(value)
    if (
        path.is_absolute()
        or not value
        or value != path.as_posix()
        or any(component in ("", ".", "..") for component in path.parts)
        or "\n" in value
        or "\r" in value
        or "\\" in value
    ):
        fail(EXIT_INTERNAL, "invalid_input_manifest")
    return path


def _stable_sha256(
    path: Path,
    *,
    maximum_bytes: int,
    expected_size: int | None,
    expected_link_count: int,
    expected_uid: int | None = None,
    expected_mode: int | None = None,
) -> str:
    _reject_symlink_components(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != expected_link_count
            or before.st_size < 0
            or before.st_size > maximum_bytes
            or (expected_size is not None and before.st_size != expected_size)
            or (expected_uid is not None and before.st_uid != expected_uid)
            or (
                expected_mode is not None
                and stat.S_IMODE(before.st_mode) != expected_mode
            )
        ):
            fail(EXIT_UNSAFE_BOUNDARY, "invalid_input_file")
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
    except ToolFailure:
        raise
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "input_read_failed")
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if identity_before != identity_after:
        fail(EXIT_UNSAFE_BOUNDARY, "changing_input_file")
    return digest.hexdigest()


def _record_path(
    record: _Record,
    repo_root: Path,
    artifact_root: Path,
    os_shell: Path,
    os_python_launcher: Path,
    os_python_runtime: Path,
) -> Path:
    relative = _relative_path(record.relative_path)
    if record.scope == "repo":
        return repo_root / relative
    if record.scope == "artifact":
        if len(relative.parts) != 1:
            fail(EXIT_INTERNAL, "invalid_input_manifest")
        return artifact_root / relative
    if record.scope == "os" and record.relative_path == "shell":
        return os_shell
    if record.scope == "os" and record.relative_path == "launcher":
        return os_python_launcher
    if record.scope == "os" and record.relative_path == "runtime":
        return os_python_runtime
    fail(EXIT_INTERNAL, "invalid_input_manifest")


def _require_shell_environment(environment: Mapping[str, str]) -> None:
    if any(
        name in environment for name in ("BASH_ENV", "SHELLOPTS", "BASHOPTS")
    ):
        fail(EXIT_UNSAFE_BOUNDARY, "shell_environment_mismatch")


def _require_runtime_link_chain(
    *,
    executable_link_path: Path = _OS_PYTHON_EXECUTABLE,
    executable_link_target: str = _OS_PYTHON_EXECUTABLE_LINK,
    runtime_link_path: Path = _OS_PYTHON_RUNTIME_LINK,
    runtime_link_target: str = _OS_PYTHON_RUNTIME_LINK_TARGET,
    runtime_path: Path = _OS_PYTHON_RUNTIME,
    expected_uid: int = 0,
    expected_mode: int = 0o755,
    expected_link_count: int = 1,
) -> None:
    _reject_symlink_components(executable_link_path.parent)
    _reject_symlink_components(runtime_link_path.parent)
    _reject_symlink_components(runtime_path)
    try:
        executable_link = executable_link_path.lstat()
        runtime_link = runtime_link_path.lstat()
        executable_target = os.readlink(executable_link_path)
        runtime_target = os.readlink(runtime_link_path)
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "python_runtime_mismatch")
    executable_destination = Path(
        os.path.normpath(
            os.path.join(str(executable_link_path.parent), executable_target)
        )
    )
    runtime_destination = Path(
        os.path.normpath(
            os.path.join(str(runtime_link_path.parent), runtime_target)
        )
    )
    if (
        not stat.S_ISLNK(executable_link.st_mode)
        or executable_link.st_uid != expected_uid
        or stat.S_IMODE(executable_link.st_mode) != expected_mode
        or executable_link.st_nlink != expected_link_count
        or executable_target != executable_link_target
        or executable_destination != runtime_link_path
        or not stat.S_ISLNK(runtime_link.st_mode)
        or runtime_link.st_uid != expected_uid
        or stat.S_IMODE(runtime_link.st_mode) != expected_mode
        or runtime_link.st_nlink != expected_link_count
        or runtime_target != runtime_link_target
        or runtime_destination != runtime_path
    ):
        fail(EXIT_UNSAFE_BOUNDARY, "python_runtime_mismatch")


def _verify_inputs(
    *,
    expected_self: str,
    expected_request: str,
    repo_root: Path,
    artifact_root: Path,
    os_shell: Path,
    os_python_launcher: Path,
    os_python_runtime: Path,
    self_path: Path,
    request_path: Path,
    records: Iterable[_Record],
    enforce_runtime: bool,
) -> dict[str, object]:
    if enforce_runtime:
        _require_shell_environment(os.environ)
        _require_runtime_link_chain()
        if (
            Path(sys.executable) != _OS_PYTHON_EXECUTABLE
            or Path(sys.executable).resolve(strict=True) != _OS_PYTHON_RUNTIME
            or sys.version_info[:3] != _OS_PYTHON_VERSION
        ):
            fail(EXIT_UNSAFE_BOUNDARY, "python_runtime_mismatch")
        expected_self_path = repo_root / _SELF_RELATIVE
        expected_request_path = repo_root / _REQUEST_RELATIVE
        if self_path != expected_self_path or request_path != expected_request_path:
            fail(EXIT_UNSAFE_BOUNDARY, "repository_binding_mismatch")

    if _stable_sha256(
        self_path,
        maximum_bytes=64 * 1024,
        expected_size=None,
        expected_link_count=1,
    ) != expected_self:
        fail(EXIT_MISMATCH, "self_hash_mismatch")
    if _stable_sha256(
        request_path,
        maximum_bytes=128 * 1024,
        expected_size=None,
        expected_link_count=1,
    ) != expected_request:
        fail(EXIT_MISMATCH, "request_hash_mismatch")

    checked = 2
    labels: set[str] = set()
    paths: set[tuple[str, str]] = set()
    for record in records:
        path_key = (record.scope, record.relative_path)
        if (
            record.label in labels
            or path_key in paths
            or _require_hex_64(record.sha256, "input_sha256") != record.sha256
            or type(record.size) is not int
            or record.size <= 0
            or type(record.link_count) is not int
            or record.link_count <= 0
            or (record.uid is not None and type(record.uid) is not int)
            or (record.mode is not None and type(record.mode) is not int)
        ):
            fail(EXIT_INTERNAL, "invalid_input_manifest")
        labels.add(record.label)
        paths.add(path_key)
        path = _record_path(
            record,
            repo_root,
            artifact_root,
            os_shell,
            os_python_launcher,
            os_python_runtime,
        )
        if _stable_sha256(
            path,
            maximum_bytes=record.size,
            expected_size=record.size,
            expected_link_count=record.link_count,
            expected_uid=record.uid,
            expected_mode=record.mode,
        ) != record.sha256:
            fail(EXIT_MISMATCH, "input_hash_mismatch")
        checked += 1

    return {
        "schema_version": 1,
        "status": "passed",
        "input_set_id": INPUT_SET_ID,
        "checked_file_count": checked,
    }


def _operation() -> dict[str, object]:
    expected_self, expected_request = _parse_args()
    repo_root = Path.cwd()
    return _verify_inputs(
        expected_self=expected_self,
        expected_request=expected_request,
        repo_root=repo_root,
        artifact_root=_ARTIFACT_ROOT,
        os_shell=_OS_SHELL,
        os_python_launcher=_OS_PYTHON_LAUNCHER,
        os_python_runtime=_OS_PYTHON_RUNTIME,
        self_path=repo_root / _SELF_RELATIVE,
        request_path=repo_root / _REQUEST_RELATIVE,
        records=_RECORDS,
        enforce_runtime=True,
    )


def operation() -> dict[str, object]:
    try:
        return _operation()
    except ToolFailure:
        raise
    except Exception:
        fail(EXIT_INTERNAL, "internal_failure")


if __name__ == "__main__":
    main(operation)
