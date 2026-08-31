#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import json
import os
import pwd
import socket
import stat
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from decision_providers import get_decision_provider

from tool_common import (
    EXIT_INTERNAL,
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    EXIT_UNSAFE_BOUNDARY,
    ToolFailure,
    absolute_path,
    fail,
    main,
    reject_symlink_components,
)

_BASE_ROUTES = (
    ("health", "/probe/v0/health"),
    ("manifest", "/probe/v0/manifest"),
)
_SCREEN_ROUTE = (
    ("screen", "/probe/v0/public/screen"),
)
_COMBAT_ROUTE = (
    ("decision", "/probe/v0/public/combat-decision"),
)
_ACTION_ROUTE = "/probe/v0/public/combat-action"
_REWARD_ROUTE = (
    ("reward", "/probe/v0/public/reward-decision"),
)
_REWARD_ACTION_ROUTE = "/probe/v0/public/reward-action"
_MAP_ROUTE = (
    ("map", "/probe/v0/public/map-decision"),
)
_MAP_ACTION_ROUTE = "/probe/v0/public/map-action"
_ROUTES = _BASE_ROUTES + _SCREEN_ROUTE + _COMBAT_ROUTE + _REWARD_ROUTE + _MAP_ROUTE
_EXPECTED_SCREENS = frozenset(("main_menu", "settings", "combat"))
_CREDENTIAL_COMPONENTS = (
    "Library",
    "Application Support",
    "Sts2AgentBridge",
    "r0a",
    "credential.hex",
)
_LOWER_HEX = frozenset(b"0123456789abcdef")

_CONNECT_TIMEOUT_SECONDS = 1.0
_SOCKET_OPERATION_TIMEOUT_SECONDS = 1.0
_CONNECTION_DEADLINE_SECONDS = 3.0
_PROBE_DEADLINE_SECONDS = 10.0
_MAXIMUM_RESPONSE_BYTES = 8192
_MAXIMUM_RESPONSE_HEADER_BYTES = 1024
_MAXIMUM_RESPONSE_BODY_BYTES = 4096
_RECEIVE_CHUNK_BYTES = 1024

_CANONICAL_HEADER_PREFIX = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: application/json; charset=utf-8\r\n"
    b"Content-Length: "
)
_CANONICAL_HEADER_SUFFIX = (
    b"\r\n"
    b"Cache-Control: no-store\r\n"
    b"X-Content-Type-Options: nosniff\r\n"
    b"Connection: close\r\n"
    b"\r\n"
)
_HEADER_TERMINATOR = b"\r\n\r\n"

_RATE_LIMITED_BODY_PREFIX = (
    b'{"schema_version":1,"code":"rate_limited","retryable":true,'
    b'"mutation_state":"none","correlation_id":"'
)
_RATE_LIMITED_BODY_SUFFIX = b'"}'
_RATE_LIMITED_BODY_LENGTH = (
    len(_RATE_LIMITED_BODY_PREFIX) + 32 + len(_RATE_LIMITED_BODY_SUFFIX)
)
_RATE_LIMITED_HEADER = (
    b"HTTP/1.1 429 Too Many Requests\r\n"
    b"Content-Type: application/json; charset=utf-8\r\n"
    b"Content-Length: "
    + str(_RATE_LIMITED_BODY_LENGTH).encode("ascii")
    + b"\r\n"
    b"Cache-Control: no-store\r\n"
    b"X-Content-Type-Options: nosniff\r\n"
    b"Retry-After: 1\r\n"
    b"Connection: close\r\n"
    b"\r\n"
)
_RETRYABLE_BACKEND_BODY_PREFIX = (
    b'{"schema_version":1,"code":"backend_fault","retryable":true,'
    b'"mutation_state":"none","correlation_id":"'
)
_RETRYABLE_BACKEND_BODY_SUFFIX = b'"}'
_RETRYABLE_BACKEND_BODY_LENGTH = (
    len(_RETRYABLE_BACKEND_BODY_PREFIX) + 32 + len(_RETRYABLE_BACKEND_BODY_SUFFIX)
)
_RETRYABLE_BACKEND_HEADER = (
    b"HTTP/1.1 503 Service Unavailable\r\n"
    b"Content-Type: application/json; charset=utf-8\r\n"
    b"Content-Length: "
    + str(_RETRYABLE_BACKEND_BODY_LENGTH).encode("ascii")
    + b"\r\n"
    b"Cache-Control: no-store\r\n"
    b"X-Content-Type-Options: nosniff\r\n"
    b"Connection: close\r\n"
    b"\r\n"
)
_BACKEND_FAULT_BODY_PREFIX = (
    b'{"schema_version":1,"code":"backend_fault","retryable":false,'
    b'"mutation_state":"none","correlation_id":"'
)
_BACKEND_FAULT_BODY_SUFFIX = b'"}'
_BACKEND_FAULT_BODY_LENGTH = (
    len(_BACKEND_FAULT_BODY_PREFIX) + 32 + len(_BACKEND_FAULT_BODY_SUFFIX)
)
_BACKEND_FAULT_HEADER = (
    b"HTTP/1.1 500 Internal Server Error\r\n"
    b"Content-Type: application/json; charset=utf-8\r\n"
    b"Content-Length: "
    + str(_BACKEND_FAULT_BODY_LENGTH).encode("ascii")
    + b"\r\n"
    b"Cache-Control: no-store\r\n"
    b"X-Content-Type-Options: nosniff\r\n"
    b"Connection: close\r\n"
    b"\r\n"
)

_HEALTH_PREFIX = (
    b'{"schema_version":1,"lifecycle_state":"running","correlation_id":"'
)
_HEALTH_SUFFIX = b'"}'
_MANIFEST_COMPATIBLE = (
    b'{"schema_version":1,"protocol":"live_probe_v0","bridge_id":"sts2_agent_bridge",'
    b'"bridge_version":"0.8.0","mode":"live_probe_v0","build_compatibility":"compatible",'
    b'"target_build_manifest_id":"sts2-steam-main-build-23811903-macos-universal",'
    b'"target_game_version":"v0.107.1","target_steam_build_id":"23811903","capabilities":'
    b'{"observe_public_screen":true,"observe_decision":true,"apply":true,'
    b'"profile_access":false,"privileged_state":false,"snapshot_restore":false,'
    b'"bridge_filesystem_writes":false,"host_logging":"sanitized_existing_sink",'
    b'"harmony_patches":false,"outbound_network":false,"hot_unload":false}}'
)
_SCREEN_MAIN_MENU = (
    b'{"schema_version":1,"status":"ready","screen_kind":"main_menu",'
    b'"actionable":false,"candidates":[]}'
)
_SCREEN_SETTINGS = (
    b'{"schema_version":1,"status":"ready","screen_kind":"settings",'
    b'"actionable":false,"candidates":[]}'
)
_SCREEN_WAITING = (
    b'{"schema_version":1,"status":"waiting","screen_kind":"unknown",'
    b'"actionable":false,"candidates":[]}'
)
_SCREEN_UNSUPPORTED = (
    b'{"schema_version":1,"status":"unsupported","screen_kind":"unknown",'
    b'"actionable":false,"candidates":[]}'
)
_CANONICAL_SCREENS = (
    _SCREEN_MAIN_MENU,
    _SCREEN_SETTINGS,
    _SCREEN_WAITING,
    _SCREEN_UNSUPPORTED,
)
_COMBAT_WAITING = (
    b'{"schema_version":1,"status":"waiting","decision_kind":"combat",'
    b'"actionable":false,"decision_id":null,"round":0,"player":null,'
    b'"enemies":[],"hand":[],"legal_actions":[]}'
)
_COMBAT_UNSUPPORTED = _COMBAT_WAITING.replace(b'"waiting"', b'"unsupported"')
_COMBAT_COMPLETE_PREFIX = b'{"schema_version":1,"status":"complete",'

_COMBAT_MISMATCH_ENVELOPE = "decision_envelope_mismatch"
_COMBAT_MISMATCH_IDENTITY = "decision_identity_mismatch"
_COMBAT_MISMATCH_PLAYER = "decision_player_mismatch"
_COMBAT_MISMATCH_ENEMIES = "decision_enemies_mismatch"
_COMBAT_MISMATCH_HAND = "decision_hand_mismatch"
_COMBAT_MISMATCH_LEGAL_ACTIONS = "decision_legal_actions_mismatch"
_COMBAT_MISMATCH_PROVIDER_RESULT = "decision_provider_result_mismatch"


def _parse_effective_uid(value: str) -> int:
    if not value or not value.isascii() or not value.isdecimal():
        fail(EXIT_INVALID_INVOCATION, "invalid_effective_uid")
    if len(value) > 1 and value[0] == "0":
        fail(EXIT_INVALID_INVOCATION, "invalid_effective_uid")
    try:
        parsed = int(value, 10)
    except ValueError:
        fail(EXIT_INVALID_INVOCATION, "invalid_effective_uid")
    if parsed < 0:
        fail(EXIT_INVALID_INVOCATION, "invalid_effective_uid")
    return parsed


def parse_args(arguments: list[str] | None = None) -> tuple[str, int, str]:
    values = sys.argv[1:] if arguments is None else arguments
    if len(values) != 6:
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")

    allowed = frozenset(("--user-profile", "--effective-uid", "--expected-screen"))
    parsed: dict[str, str] = {}
    for offset in range(0, len(values), 2):
        name = values[offset]
        if name not in allowed or name in parsed:
            fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
        parsed[name] = values[offset + 1]

    if set(parsed) != allowed:
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    expected_screen = parsed["--expected-screen"]
    if expected_screen not in _EXPECTED_SCREENS:
        fail(EXIT_INVALID_INVOCATION, "invalid_expected_screen")
    return (
        parsed["--user-profile"],
        _parse_effective_uid(parsed["--effective-uid"]),
        expected_screen,
    )


def _require_identity(user_profile: Path, supplied_uid: int) -> int:
    if sys.platform != "darwin":
        fail(EXIT_UNSAFE_BOUNDARY, "unsupported_platform")
    effective_uid = os.geteuid()
    if supplied_uid != effective_uid:
        fail(EXIT_UNSAFE_BOUNDARY, "effective_uid_mismatch")
    try:
        os_home = os.path.normpath(pwd.getpwuid(effective_uid).pw_dir)
    except KeyError:
        fail(EXIT_UNSAFE_BOUNDARY, "user_identity_unavailable")
    if str(user_profile) != os_home:
        fail(EXIT_UNSAFE_BOUNDARY, "user_profile_mismatch")
    if "\n" in os_home or "\r" in os_home:
        fail(EXIT_UNSAFE_BOUNDARY, "unsafe_user_profile")
    return effective_uid


def _reject_acl(path: Path) -> None:
    try:
        completed = subprocess.run(
            ["/bin/ls", "-lde", str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
            encoding="utf-8",
            timeout=2,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        fail(EXIT_UNSAFE_BOUNDARY, "acl_check_failed")
    if completed.returncode != 0:
        fail(EXIT_UNSAFE_BOUNDARY, "acl_check_failed")
    lines = completed.stdout.splitlines()
    if not lines:
        fail(EXIT_UNSAFE_BOUNDARY, "acl_check_failed")
    mode_field = lines[0].split(maxsplit=1)[0]
    has_acl_marker = mode_field.endswith("+")
    saw_acl_entry = False
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped and stripped[0].isdigit() and ":" in stripped:
            saw_acl_entry = True
            fields = stripped.split()
            if "allow" in fields:
                fail(EXIT_UNSAFE_BOUNDARY, "granting_acl")
            if "deny" not in fields:
                fail(EXIT_UNSAFE_BOUNDARY, "acl_check_failed")
    if has_acl_marker and not saw_acl_entry:
        fail(EXIT_UNSAFE_BOUNDARY, "granting_acl")


def _require_directory(path: Path, uid: int, required_mode: int | None) -> None:
    reject_symlink_components(path)
    try:
        metadata = path.lstat()
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "missing_credential_component")
    if not stat.S_ISDIR(metadata.st_mode):
        fail(EXIT_UNSAFE_BOUNDARY, "non_directory_credential_component")
    if metadata.st_uid != uid:
        fail(EXIT_UNSAFE_BOUNDARY, "credential_owner")
    if required_mode is not None and stat.S_IMODE(metadata.st_mode) != required_mode:
        fail(EXIT_UNSAFE_BOUNDARY, "credential_directory_mode")
    _reject_acl(path)


def _require_credential_metadata(path: Path, uid: int) -> os.stat_result:
    reject_symlink_components(path)
    try:
        metadata = path.lstat()
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "missing_credential_file")
    if not stat.S_ISREG(metadata.st_mode):
        fail(EXIT_UNSAFE_BOUNDARY, "non_regular_credential_file")
    if metadata.st_uid != uid:
        fail(EXIT_UNSAFE_BOUNDARY, "credential_owner")
    if metadata.st_nlink != 1:
        fail(EXIT_UNSAFE_BOUNDARY, "credential_link_count")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        fail(EXIT_UNSAFE_BOUNDARY, "credential_file_mode")
    if metadata.st_size != 64:
        fail(EXIT_MISMATCH, "credential_shape")
    _reject_acl(path)
    return metadata


def _metadata_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _zero(buffer: bytearray) -> None:
    for offset in range(len(buffer)):
        buffer[offset] = 0


def _credential_is_canonical(credential: bytearray) -> bool:
    return len(credential) == 64 and all(value in _LOWER_HEX for value in credential)


def _read_credential(path: Path, metadata: os.stat_result, uid: int) -> bytearray:
    credential = bytearray(65)
    descriptor = -1
    stream: Any | None = None
    try:
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_CLOEXEC"):
            fail(EXIT_UNSAFE_BOUNDARY, "safe_open_unsupported")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        opened = os.fstat(descriptor)
        if (
            _metadata_identity(opened) != _metadata_identity(metadata)
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != uid
            or opened.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) != 0o600
            or opened.st_size != 64
        ):
            fail(EXIT_UNSAFE_BOUNDARY, "changing_credential_file")

        stream = os.fdopen(descriptor, "rb", buffering=0, closefd=True)
        descriptor = -1
        total = 0
        while total < len(credential):
            target = memoryview(credential)[total:]
            try:
                count = stream.readinto(target)
            finally:
                target.release()
            if count is None or count == 0:
                break
            if count < 0 or count > len(credential) - total:
                fail(EXIT_UNSAFE_BOUNDARY, "credential_read_failed")
            total += count

        opened_after = os.fstat(stream.fileno())
        try:
            path_after = path.lstat()
        except OSError:
            fail(EXIT_UNSAFE_BOUNDARY, "changing_credential_file")
        expected_identity = _metadata_identity(metadata)
        if (
            _metadata_identity(opened_after) != expected_identity
            or _metadata_identity(path_after) != expected_identity
            or total != 64
        ):
            fail(EXIT_UNSAFE_BOUNDARY, "changing_credential_file")

        del credential[64:]
        if not _credential_is_canonical(credential):
            fail(EXIT_MISMATCH, "credential_shape")
        return credential
    except ToolFailure:
        _zero(credential)
        raise
    except (OSError, ValueError):
        _zero(credential)
        fail(EXIT_UNSAFE_BOUNDARY, "credential_read_failed")
    finally:
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass
        elif descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _load_fixed_credential(user_profile: Path, uid: int) -> bytearray:
    library = user_profile / _CREDENTIAL_COMPONENTS[0]
    application_support = library / _CREDENTIAL_COMPONENTS[1]
    bridge_root = application_support / _CREDENTIAL_COMPONENTS[2]
    milestone_root = bridge_root / _CREDENTIAL_COMPONENTS[3]
    credential_path = milestone_root / _CREDENTIAL_COMPONENTS[4]

    _require_directory(library, uid, None)
    _require_directory(application_support, uid, None)
    _require_directory(bridge_root, uid, 0o700)
    _require_directory(milestone_root, uid, 0o700)
    metadata = _require_credential_metadata(credential_path, uid)
    return _read_credential(credential_path, metadata, uid)


def _literal_loopback_connector() -> socket.socket:
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.settimeout(_CONNECT_TIMEOUT_SECONDS)
        client.connect(("127.0.0.1", 43117))
        return client
    except OSError:
        try:
            client.close()
        except OSError:
            pass
        raise


def _build_request(route: str, credential: bytearray) -> bytearray:
    if route not in tuple(value for _, value in _ROUTES):
        fail(EXIT_INTERNAL, "internal_failure")
    if not _credential_is_canonical(credential):
        fail(EXIT_MISMATCH, "credential_shape")
    request = bytearray()
    request.extend(b"GET ")
    request.extend(route.encode("ascii"))
    request.extend(b" HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer ")
    request.extend(credential)
    request.extend(b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n")
    return request


def _build_action_request(
    route: str,
    credential: bytearray,
    decision_id: str,
    action_id: str,
) -> bytearray:
    canonical_play = (
        len(action_id) in (6, 8)
        and action_id.startswith("play:")
        and action_id[5].isdigit()
        and (
            len(action_id) == 6
            or action_id[6] == ":" and action_id[7] in "012345"
        )
    )
    canonical_combat = action_id == "end_turn" or canonical_play
    canonical_reward = (
        action_id in ("skip_card", "proceed")
        or len(action_id) == 7
        and action_id.startswith("claim:")
        and action_id[6] in "01234567"
        or len(action_id) == 6
        and action_id.startswith("open:")
        and action_id[5] in "01234567"
        or len(action_id) == 8
        and action_id.startswith("choose:")
        and action_id[7] in "01234"
    )
    canonical_map = (
        len(action_id) == 8
        and action_id.startswith("select:")
        and action_id[7] in "01234567"
    )
    if (
        len(decision_id) != 64
        or any(ord(value) not in _LOWER_HEX for value in decision_id)
        or route == _ACTION_ROUTE and not canonical_combat
        or route == _REWARD_ACTION_ROUTE and not canonical_reward
        or route == _MAP_ACTION_ROUTE and not canonical_map
        or route not in (_ACTION_ROUTE, _REWARD_ACTION_ROUTE, _MAP_ACTION_ROUTE)
    ):
        fail(EXIT_INTERNAL, "internal_failure")
    if not _credential_is_canonical(credential):
        fail(EXIT_MISMATCH, "credential_shape")
    request = bytearray()
    request.extend(b"POST ")
    request.extend(route.encode("ascii"))
    request.extend(b" HTTP/1.1\r\nHost: 127.0.0.1:43117\r\nAuthorization: Bearer ")
    request.extend(credential)
    request.extend(b"\r\nX-Sts2-Decision-Id: ")
    request.extend(decision_id.encode("ascii"))
    request.extend(b"\r\nX-Sts2-Action-Id: ")
    request.extend(action_id.encode("ascii"))
    request.extend(b"\r\nAccept: application/json\r\nConnection: close\r\n\r\n")
    return request


def _set_bounded_timeout(client: Any, deadline: float, label: str) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        fail(EXIT_MISMATCH, f"{label}_transport_timeout")
    client.settimeout(min(remaining, _SOCKET_OPERATION_TIMEOUT_SECONDS))


def _exchange(
    label: str,
    route: str,
    credential: bytearray,
    connector: Callable[[], Any],
    probe_deadline: float,
    decision_id: str | None = None,
    action_id: str | None = None,
) -> bytearray:
    client: Any | None = None
    request = bytearray()
    response = bytearray()
    try:
        if time.monotonic() >= probe_deadline:
            fail(EXIT_MISMATCH, "probe_transport_timeout")
        client = connector()
        connection_deadline = min(
            probe_deadline,
            time.monotonic() + _CONNECTION_DEADLINE_SECONDS,
        )
        if decision_id is None and action_id is None:
            request = _build_request(route, credential)
        elif (
            decision_id is not None
            and action_id is not None
            and route in (_ACTION_ROUTE, _REWARD_ACTION_ROUTE, _MAP_ACTION_ROUTE)
        ):
            request = _build_action_request(route, credential, decision_id, action_id)
        else:
            fail(EXIT_INTERNAL, "internal_failure")
        _set_bounded_timeout(client, connection_deadline, label)
        client.sendall(request)

        while True:
            _set_bounded_timeout(client, connection_deadline, label)
            chunk = client.recv(_RECEIVE_CHUNK_BYTES)
            if not isinstance(chunk, (bytes, bytearray, memoryview)):
                fail(EXIT_MISMATCH, f"{label}_transport_mismatch")
            if not chunk:
                break
            if len(chunk) > _RECEIVE_CHUNK_BYTES:
                fail(EXIT_MISMATCH, f"{label}_transport_mismatch")
            if len(response) + len(chunk) > _MAXIMUM_RESPONSE_BYTES:
                fail(EXIT_MISMATCH, f"{label}_response_too_large")
            response.extend(chunk)

        if not response:
            fail(EXIT_MISMATCH, f"{label}_empty_response")
        return response
    except ToolFailure:
        _zero(response)
        raise
    except (OSError, TimeoutError):
        _zero(response)
        fail(EXIT_MISMATCH, f"{label}_transport_failure")
    finally:
        _zero(request)
        if client is not None:
            try:
                client.close()
            except OSError:
                pass


def _canonical_body(response: bytearray, label: str) -> memoryview:
    separator = response.find(_HEADER_TERMINATOR)
    if separator < 0 or separator + len(_HEADER_TERMINATOR) > _MAXIMUM_RESPONSE_HEADER_BYTES:
        fail(EXIT_MISMATCH, f"{label}_response_mismatch")
    body_offset = separator + len(_HEADER_TERMINATOR)
    body_length = len(response) - body_offset
    if body_length > _MAXIMUM_RESPONSE_BODY_BYTES:
        fail(EXIT_MISMATCH, f"{label}_response_too_large")

    expected_header = bytearray(_CANONICAL_HEADER_PREFIX)
    expected_header.extend(str(body_length).encode("ascii"))
    expected_header.extend(_CANONICAL_HEADER_SUFFIX)
    header = memoryview(response)[:body_offset]
    try:
        if header != expected_header:
            fail(EXIT_MISMATCH, f"{label}_response_mismatch")
    finally:
        header.release()
    return memoryview(response)[body_offset:]


def _is_retryable_backend_response(response: bytes | bytearray) -> bool:
    expected_length = (
        len(_RETRYABLE_BACKEND_HEADER) + _RETRYABLE_BACKEND_BODY_LENGTH
    )
    if len(response) != expected_length or not response.startswith(
        _RETRYABLE_BACKEND_HEADER
    ):
        return False
    body_offset = len(_RETRYABLE_BACKEND_HEADER)
    prefix_end = body_offset + len(_RETRYABLE_BACKEND_BODY_PREFIX)
    correlation_end = prefix_end + 32
    return (
        response[body_offset:prefix_end] == _RETRYABLE_BACKEND_BODY_PREFIX
        and response[correlation_end:] == _RETRYABLE_BACKEND_BODY_SUFFIX
        and all(value in _LOWER_HEX for value in response[prefix_end:correlation_end])
    )


def _is_rate_limited_response(response: bytes | bytearray) -> bool:
    expected_length = len(_RATE_LIMITED_HEADER) + _RATE_LIMITED_BODY_LENGTH
    if len(response) != expected_length or not response.startswith(_RATE_LIMITED_HEADER):
        return False
    body_offset = len(_RATE_LIMITED_HEADER)
    prefix_end = body_offset + len(_RATE_LIMITED_BODY_PREFIX)
    correlation_end = prefix_end + 32
    return (
        response[body_offset:prefix_end] == _RATE_LIMITED_BODY_PREFIX
        and response[correlation_end:] == _RATE_LIMITED_BODY_SUFFIX
        and all(value in _LOWER_HEX for value in response[prefix_end:correlation_end])
    )


def _is_backend_fault_response(response: bytes | bytearray) -> bool:
    expected_length = len(_BACKEND_FAULT_HEADER) + _BACKEND_FAULT_BODY_LENGTH
    if len(response) != expected_length or not response.startswith(
        _BACKEND_FAULT_HEADER
    ):
        return False
    body_offset = len(_BACKEND_FAULT_HEADER)
    prefix_end = body_offset + len(_BACKEND_FAULT_BODY_PREFIX)
    correlation_end = prefix_end + 32
    return (
        response[body_offset:prefix_end] == _BACKEND_FAULT_BODY_PREFIX
        and response[correlation_end:] == _BACKEND_FAULT_BODY_SUFFIX
        and all(value in _LOWER_HEX for value in response[prefix_end:correlation_end])
    )


def _validate_health(body: memoryview) -> None:
    expected_length = len(_HEALTH_PREFIX) + 32 + len(_HEALTH_SUFFIX)
    if len(body) != expected_length:
        fail(EXIT_MISMATCH, "health_response_mismatch")
    if body[: len(_HEALTH_PREFIX)] != _HEALTH_PREFIX or body[-len(_HEALTH_SUFFIX) :] != _HEALTH_SUFFIX:
        fail(EXIT_MISMATCH, "health_response_mismatch")
    correlation_id = body[len(_HEALTH_PREFIX) : -len(_HEALTH_SUFFIX)]
    if any(value not in _LOWER_HEX for value in correlation_id):
        fail(EXIT_MISMATCH, "health_response_mismatch")


def _validate_manifest(body: memoryview) -> None:
    if body != _MANIFEST_COMPATIBLE:
        fail(EXIT_MISMATCH, "manifest_response_mismatch")


def _validate_screen(body: memoryview, expected_screen: str) -> None:
    expected = _SCREEN_MAIN_MENU if expected_screen == "main_menu" else _SCREEN_SETTINGS
    if body == expected:
        return
    if any(body == candidate for candidate in _CANONICAL_SCREENS):
        fail(EXIT_MISMATCH, "screen_mismatch")
    fail(EXIT_MISMATCH, "screen_response_mismatch")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _reject_json_constant(_: str) -> object:
    raise ValueError("non-finite number")


def _is_bounded_nonnegative_integer(value: object) -> bool:
    return type(value) is int and 0 <= value <= 1_000_000


def _is_public_string(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= 128
        and value.isascii()
        and all(" " <= character <= "~" for character in value)
    )


def _validate_exact_keys(value: object, expected: tuple[str, ...]) -> dict[str, object]:
    if not isinstance(value, dict) or tuple(value) != expected:
        raise ValueError("unexpected object shape")
    return value


def _validate_combat(
    body: memoryview,
    decision_provider: str = "heuristic",
) -> dict[str, object]:
    try:
        decoded = bytes(body).decode("ascii")
        root = json.loads(
            decoded,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
        root = _validate_exact_keys(
            root,
            (
                "schema_version",
                "status",
                "decision_kind",
                "actionable",
                "decision_id",
                "round",
                "player",
                "enemies",
                "hand",
                "legal_actions",
            ),
        )
        if (
            root["schema_version"] != 1
            or root["status"] != "ready"
            or root["decision_kind"] != "combat"
            or root["actionable"] is not True
        ):
            raise ValueError("decision envelope")
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        fail(EXIT_MISMATCH, _COMBAT_MISMATCH_ENVELOPE)

    try:
        if (
            not isinstance(root["decision_id"], str)
            or len(root["decision_id"]) != 64
            or any(ord(value) not in _LOWER_HEX for value in root["decision_id"])
            or not _is_bounded_nonnegative_integer(root["round"])
            or root["round"] < 1
        ):
            raise ValueError("decision identity")
    except (ValueError, TypeError, KeyError):
        fail(EXIT_MISMATCH, _COMBAT_MISMATCH_IDENTITY)

    try:
        player = _validate_exact_keys(
            root["player"],
            ("hp", "max_hp", "block", "energy"),
        )
        if any(not _is_bounded_nonnegative_integer(player[name]) for name in player):
            raise ValueError("player values")
        if player["max_hp"] < 1 or player["hp"] > player["max_hp"]:
            raise ValueError("player health")
    except (ValueError, TypeError, KeyError):
        fail(EXIT_MISMATCH, _COMBAT_MISMATCH_PLAYER)

    try:
        enemies = root["enemies"]
        if not isinstance(enemies, list) or not 1 <= len(enemies) <= 6:
            raise ValueError("enemy count")
        validated_enemies: list[dict[str, object]] = []
        for expected_index, raw_enemy in enumerate(enemies):
            enemy = _validate_exact_keys(
                raw_enemy,
                ("index", "id", "hp", "max_hp", "block", "intents"),
            )
            if enemy["index"] != expected_index or not _is_public_string(enemy["id"]):
                raise ValueError("enemy identity")
            if any(
                not _is_bounded_nonnegative_integer(enemy[name])
                for name in ("hp", "max_hp", "block")
            ):
                raise ValueError("enemy values")
            if enemy["max_hp"] < 1 or enemy["hp"] > enemy["max_hp"]:
                raise ValueError("enemy health")
            intents = enemy["intents"]
            if (
                not isinstance(intents, list)
                or len(intents) > 8
                or any(not _is_public_string(intent) for intent in intents)
            ):
                raise ValueError("enemy intents")
            validated_enemies.append(enemy)
    except (ValueError, TypeError, KeyError):
        fail(EXIT_MISMATCH, _COMBAT_MISMATCH_ENEMIES)

    try:
        hand = root["hand"]
        if not isinstance(hand, list) or len(hand) > 10:
            raise ValueError("hand count")
        validated_hand: list[dict[str, object]] = []
        for expected_index, raw_card in enumerate(hand):
            card = _validate_exact_keys(
                raw_card,
                ("hand_index", "id", "type", "cost", "target_type", "playable"),
            )
            if card["hand_index"] != expected_index:
                raise ValueError("hand index")
            if any(not _is_public_string(card[name]) for name in ("id", "type", "cost", "target_type")):
                raise ValueError("card text")
            if type(card["playable"]) is not bool:
                raise ValueError("card playable")
            validated_hand.append(card)
    except (ValueError, TypeError, KeyError):
        fail(EXIT_MISMATCH, _COMBAT_MISMATCH_HAND)

    try:
        legal_actions = root["legal_actions"]
        if not isinstance(legal_actions, list) or not 1 <= len(legal_actions) <= 64:
            raise ValueError("legal action count")
        validated_actions: list[dict[str, object]] = []
        action_ids: set[str] = set()
        end_turn_count = 0
        for raw_action in legal_actions:
            action = _validate_exact_keys(
                raw_action,
                ("action_id", "kind", "hand_index", "target_index"),
            )
            action_id = action["action_id"]
            if not _is_public_string(action_id) or action_id in action_ids:
                raise ValueError("action identity")
            action_ids.add(action_id)
            if action["kind"] == "end_turn":
                if (
                    action_id != "end_turn"
                    or action["hand_index"] is not None
                    or action["target_index"] is not None
                ):
                    raise ValueError("end turn action")
                end_turn_count += 1
            elif action["kind"] == "play_card":
                hand_index = action["hand_index"]
                target_index = action["target_index"]
                if type(hand_index) is not int or not 0 <= hand_index < len(validated_hand):
                    raise ValueError("play hand index")
                if validated_hand[hand_index]["playable"] is not True:
                    raise ValueError("unplayable action")
                if target_index is not None and (
                    type(target_index) is not int or not 0 <= target_index < len(validated_enemies)
                ):
                    raise ValueError("play target index")
                expected_id = f"play:{hand_index}"
                if target_index is not None:
                    expected_id += f":{target_index}"
                if action_id != expected_id:
                    raise ValueError("play action identity")
            else:
                raise ValueError("action kind")
            validated_actions.append(action)
        if end_turn_count != 1:
            raise ValueError("end turn cardinality")
    except (ValueError, TypeError, KeyError):
        fail(EXIT_MISMATCH, _COMBAT_MISMATCH_LEGAL_ACTIONS)

    try:
        recommendation = get_decision_provider(decision_provider).choose(
            validated_enemies,
            validated_hand,
            validated_actions,
        )
        recommendation = _validate_exact_keys(
            recommendation,
            ("action_id", "kind", "hand_index", "target_index", "card_id", "basis"),
        )
        if not _is_public_string(recommendation["basis"]):
            raise ValueError("provider basis")
        selected = next(
            action
            for action in validated_actions
            if action["action_id"] == recommendation["action_id"]
        )
        hand_index = selected["hand_index"]
        expected_card_id = None if hand_index is None else validated_hand[hand_index]["id"]
        if (
            recommendation["kind"] != selected["kind"]
            or recommendation["hand_index"] != hand_index
            or recommendation["target_index"] != selected["target_index"]
            or recommendation["card_id"] != expected_card_id
        ):
            raise ValueError("provider selection")
    except Exception:
        fail(EXIT_MISMATCH, _COMBAT_MISMATCH_PROVIDER_RESULT)

    return {
        "decision_id": root["decision_id"],
        "round": root["round"],
        "player": player,
        "enemies": validated_enemies,
        "hand": validated_hand,
        "legal_action_count": len(validated_actions),
        "legal_actions": validated_actions,
        "recommendation": recommendation,
    }


def _validate_combat_terminal(body: memoryview) -> dict[str, object]:
    try:
        decoded = bytes(body).decode("ascii")
        root = json.loads(
            decoded,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
        root = _validate_exact_keys(
            root,
            (
                "schema_version",
                "status",
                "decision_kind",
                "actionable",
                "decision_id",
                "round",
                "player",
                "enemies",
                "hand",
                "legal_actions",
                "outcome",
            ),
        )
        if (
            root["schema_version"] != 1
            or root["status"] != "complete"
            or root["decision_kind"] != "combat"
            or root["actionable"] is not False
            or root["decision_id"] is not None
            or not _is_bounded_nonnegative_integer(root["round"])
            or root["round"] < 1
            or root["outcome"] not in ("victory", "defeat")
            or root["hand"] != []
            or root["legal_actions"] != []
        ):
            raise ValueError("combat terminal header")

        player = _validate_exact_keys(
            root["player"],
            ("hp", "max_hp", "block", "energy"),
        )
        if any(not _is_bounded_nonnegative_integer(player[name]) for name in player):
            raise ValueError("combat terminal player")
        if player["max_hp"] < 1 or player["hp"] > player["max_hp"]:
            raise ValueError("combat terminal health")

        enemies = root["enemies"]
        if not isinstance(enemies, list) or len(enemies) > 6:
            raise ValueError("combat terminal enemies")
        validated_enemies: list[dict[str, object]] = []
        for expected_index, raw_enemy in enumerate(enemies):
            enemy = _validate_exact_keys(
                raw_enemy,
                ("index", "id", "hp", "max_hp", "block", "intents"),
            )
            if enemy["index"] != expected_index or not _is_public_string(enemy["id"]):
                raise ValueError("combat terminal enemy identity")
            if any(
                not _is_bounded_nonnegative_integer(enemy[name])
                for name in ("hp", "max_hp", "block")
            ):
                raise ValueError("combat terminal enemy values")
            if enemy["max_hp"] < 1 or not 1 <= enemy["hp"] <= enemy["max_hp"]:
                raise ValueError("combat terminal enemy health")
            intents = enemy["intents"]
            if (
                not isinstance(intents, list)
                or len(intents) > 8
                or any(not _is_public_string(intent) for intent in intents)
            ):
                raise ValueError("combat terminal enemy intents")
            validated_enemies.append(enemy)

        if root["outcome"] == "victory":
            if player["hp"] < 1 or validated_enemies:
                raise ValueError("combat terminal victory")
        elif player["hp"] != 0:
            raise ValueError("combat terminal defeat")
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        fail(EXIT_MISMATCH, "combat_terminal_response_mismatch")

    return {
        "status": "complete",
        "round": root["round"],
        "outcome": root["outcome"],
        "player": player,
        "enemies": validated_enemies,
    }


def _recommend_combat_action(
    enemies: list[dict[str, object]],
    hand: list[dict[str, object]],
    actions: list[dict[str, object]],
) -> dict[str, object]:
    return get_decision_provider("heuristic").choose(enemies, hand, actions)


def _run_probe(
    credential: bytearray,
    expected_screen: str,
    connector: Callable[[], Any],
) -> dict[str, object]:
    if expected_screen not in _EXPECTED_SCREENS:
        _zero(credential)
        fail(EXIT_INVALID_INVOCATION, "invalid_expected_screen")
    probe_deadline = time.monotonic() + _PROBE_DEADLINE_SECONDS
    try:
        routes = _BASE_ROUTES + (_COMBAT_ROUTE if expected_screen == "combat" else _SCREEN_ROUTE)
        combat_summary: dict[str, object] | None = None
        for label, route in routes:
            response = _exchange(label, route, credential, connector, probe_deadline)
            body: memoryview | None = None
            try:
                body = _canonical_body(response, label)
                if label == "health":
                    _validate_health(body)
                elif label == "manifest":
                    _validate_manifest(body)
                elif label == "screen":
                    _validate_screen(body, expected_screen)
                else:
                    combat_summary = _validate_combat(body)
            finally:
                if body is not None:
                    body.release()
                _zero(response)

        result: dict[str, object] = {
            "schema_version": 1,
            "status": "passed",
            "protocol": "live_probe_v0",
            "mode": "live_probe_v0",
            "build_compatibility": "compatible",
            "screen_kind": expected_screen,
            "routes_checked": 3,
        }
        if combat_summary is not None:
            result["combat"] = combat_summary
        return result
    finally:
        _zero(credential)


def _operation() -> dict[str, object]:
    user_profile_value, supplied_uid, expected_screen = parse_args()
    user_profile = absolute_path(user_profile_value, "user_profile")
    uid = _require_identity(user_profile, supplied_uid)
    credential = _load_fixed_credential(user_profile, uid)
    try:
        return _run_probe(credential, expected_screen, _literal_loopback_connector)
    finally:
        _zero(credential)


def operation() -> dict[str, object]:
    try:
        return _operation()
    except ToolFailure:
        raise
    except Exception:
        fail(EXIT_INTERNAL, "internal_failure")


if __name__ == "__main__":
    main(operation)
