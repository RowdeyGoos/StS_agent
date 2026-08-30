#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import errno
import os
import pwd
import socket
import stat
import subprocess
import time
from enum import Enum
from pathlib import Path
from typing import Callable

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

_PROCESS_NAME = "Slay the Spire 2"
_EXECUTABLE_COMPONENTS = (
    "Library",
    "Application Support",
    "Steam",
    "steamapps",
    "common",
    "Slay the Spire 2",
    "SlayTheSpire2.app",
    "Contents",
    "MacOS",
    "Slay the Spire 2",
)
_MODES = frozenset(
    (
        "require-stopped",
        "require-running",
        "sample-base-port-closed",
        "wait-stopped",
    )
)

_LISTENER_ADDRESS = "127.0.0.1"
_LISTENER_PORT = 43117
_PORT_CONNECT_TIMEOUT_SECONDS = 0.2
_PGREP_TIMEOUT_SECONDS = 2.0
_POLL_INTERVAL_SECONDS = 0.5
_PROCESS_EXIT_MAXIMUM_SECONDS = 30.0
_PORT_RELEASE_MAXIMUM_SECONDS = 5.0
_STOP_CONFIRMATION_SAMPLES = 2
_POSIX_ERE_META_CHARACTERS = frozenset(r"\.^$|?*+()[]{}")


class _ProcessState(Enum):
    Stopped = "stopped"
    ExactRunning = "exact_running"
    AmbiguousRunning = "ambiguous_running"


class _DeadlineExpired(Exception):
    pass


def _parse_uid(value: str) -> int:
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
    allowed = frozenset(("--mode", "--user-profile", "--effective-uid"))
    parsed: dict[str, str] = {}
    for offset in range(0, len(values), 2):
        name = values[offset]
        if name not in allowed or name in parsed:
            fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
        parsed[name] = values[offset + 1]
    if set(parsed) != allowed:
        fail(EXIT_INVALID_INVOCATION, "invalid_invocation")
    mode = parsed["--mode"]
    if mode not in _MODES:
        fail(EXIT_INVALID_INVOCATION, "invalid_mode")
    return parsed["--user-profile"], _parse_uid(parsed["--effective-uid"]), mode


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


def _require_game_executable(user_profile: Path, uid: int) -> Path:
    executable = user_profile.joinpath(*_EXECUTABLE_COMPONENTS)
    reject_symlink_components(executable)
    try:
        metadata = executable.lstat()
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "game_executable_unavailable")
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != uid:
        fail(EXIT_UNSAFE_BOUNDARY, "game_executable_identity")
    return executable


def _remaining(deadline: float, monotonic: Callable[[], float]) -> float:
    remaining = deadline - monotonic()
    if remaining <= 0.0:
        raise _DeadlineExpired
    return remaining


def _pgrep(
    arguments: list[str],
    deadline: float,
    monotonic: Callable[[], float],
) -> bool:
    timeout = min(_PGREP_TIMEOUT_SECONDS, _remaining(deadline, monotonic))
    try:
        completed = subprocess.run(
            ["/usr/bin/pgrep", *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=timeout,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
    except subprocess.TimeoutExpired:
        if monotonic() >= deadline:
            raise _DeadlineExpired from None
        fail(EXIT_UNSAFE_BOUNDARY, "process_check_failed")
    except (OSError, subprocess.SubprocessError):
        fail(EXIT_UNSAFE_BOUNDARY, "process_check_failed")
    if monotonic() > deadline:
        raise _DeadlineExpired
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    fail(EXIT_UNSAFE_BOUNDARY, "process_check_failed")


def _escape_posix_ere_literal(value: str) -> str:
    return "".join(
        f"\\{character}" if character in _POSIX_ERE_META_CHARACTERS else character
        for character in value
    )


def _anchored_executable_pattern(executable: Path) -> str:
    escaped = _escape_posix_ere_literal(str(executable))
    return f"^{escaped}([[:space:]]|$)"


def _process_probe(
    executable: Path,
    deadline: float,
    monotonic: Callable[[], float],
) -> _ProcessState:
    exact_arguments = ("-q", "-f", _anchored_executable_pattern(executable))
    if _pgrep(list(exact_arguments), deadline, monotonic):
        return _ProcessState.ExactRunning
    if _pgrep(["-q", "-x", _PROCESS_NAME], deadline, monotonic):
        return _ProcessState.AmbiguousRunning
    return _ProcessState.Stopped


def _port_probe(deadline: float, monotonic: Callable[[], float]) -> bool:
    timeout = min(_PORT_CONNECT_TIMEOUT_SECONDS, _remaining(deadline, monotonic))
    client: socket.socket | None = None
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(timeout)
        result = client.connect_ex((_LISTENER_ADDRESS, _LISTENER_PORT))
    except (socket.timeout, TimeoutError):
        if monotonic() >= deadline:
            raise _DeadlineExpired from None
        fail(EXIT_UNSAFE_BOUNDARY, "port_check_failed")
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "port_check_failed")
    finally:
        if client is not None:
            try:
                client.close()
            except OSError:
                pass
    if monotonic() > deadline:
        raise _DeadlineExpired
    if result == 0:
        return True
    if result == errno.ECONNREFUSED:
        return False
    fail(EXIT_UNSAFE_BOUNDARY, "port_check_failed")


def _sleep_bounded(
    deadline: float,
    sleeper: Callable[[float], None],
    monotonic: Callable[[], float],
) -> None:
    duration = min(_POLL_INTERVAL_SECONDS, _remaining(deadline, monotonic))
    sleeper(duration)
    if monotonic() >= deadline:
        raise _DeadlineExpired


def _evaluate(
    mode: str,
    process_probe: Callable[[float], _ProcessState],
    port_probe: Callable[[float], bool],
    sleeper: Callable[[float], None],
    monotonic: Callable[[], float],
) -> dict[str, object]:
    process_samples = 0
    port_samples = 0

    def observe_process(deadline: float, timeout_code: str) -> _ProcessState:
        nonlocal process_samples
        process_samples += 1
        try:
            state = process_probe(deadline)
        except _DeadlineExpired:
            fail(EXIT_MISMATCH, timeout_code)
        if monotonic() > deadline:
            fail(EXIT_MISMATCH, timeout_code)
        return state

    def observe_port(deadline: float, timeout_code: str) -> bool:
        nonlocal port_samples
        port_samples += 1
        try:
            accepting = port_probe(deadline)
        except _DeadlineExpired:
            fail(EXIT_MISMATCH, timeout_code)
        if monotonic() > deadline:
            fail(EXIT_MISMATCH, timeout_code)
        return accepting

    def sleep_until_next(deadline: float, timeout_code: str) -> None:
        try:
            _sleep_bounded(deadline, sleeper, monotonic)
        except _DeadlineExpired:
            fail(EXIT_MISMATCH, timeout_code)

    def require_exact_running(state: _ProcessState) -> None:
        if state is _ProcessState.ExactRunning:
            return
        if state is _ProcessState.AmbiguousRunning:
            fail(EXIT_UNSAFE_BOUNDARY, "game_process_identity_ambiguous")
        fail(EXIT_MISMATCH, "game_not_running")

    def confirm_stopped_and_closed(deadline: float, wait_for_port: bool) -> None:
        consecutive = 0
        while consecutive < _STOP_CONFIRMATION_SAMPLES:
            accepting = observe_port(deadline, "port_release_timeout")
            state = observe_process(deadline, "port_release_timeout")
            if state is not _ProcessState.Stopped:
                code = (
                    "game_restarted_during_port_release"
                    if wait_for_port
                    else "game_still_running"
                )
                fail(EXIT_MISMATCH, code)

            if accepting:
                if not wait_for_port:
                    fail(EXIT_MISMATCH, "port_accepting")
                consecutive = 0
            else:
                consecutive += 1
                if consecutive == _STOP_CONFIRMATION_SAMPLES:
                    return
            sleep_until_next(deadline, "port_release_timeout")

    if mode == "require-running":
        deadline = monotonic() + _PROCESS_EXIT_MAXIMUM_SECONDS
        state = observe_process(deadline, "process_check_timeout")
        require_exact_running(state)
        return {
            "schema_version": 1,
            "status": "passed",
            "mode": mode,
            "game_process_running": True,
            "process_samples": process_samples,
            "port_samples": port_samples,
        }

    if mode == "sample-base-port-closed":
        process_deadline = monotonic() + _PROCESS_EXIT_MAXIMUM_SECONDS
        state = observe_process(process_deadline, "process_check_timeout")
        require_exact_running(state)
        port_deadline = monotonic() + _PORT_CONNECT_TIMEOUT_SECONDS
        if observe_port(port_deadline, "port_check_timeout"):
            fail(EXIT_MISMATCH, "port_accepting")
        return {
            "schema_version": 1,
            "status": "passed",
            "mode": mode,
            "game_process_running": True,
            "port_accepting": False,
            "process_samples": process_samples,
            "port_samples": port_samples,
        }

    if mode == "require-stopped":
        process_deadline = monotonic() + _PROCESS_EXIT_MAXIMUM_SECONDS
        state = observe_process(process_deadline, "process_check_timeout")
        if state is not _ProcessState.Stopped:
            fail(EXIT_MISMATCH, "game_still_running")
        port_deadline = monotonic() + _PORT_RELEASE_MAXIMUM_SECONDS
        confirm_stopped_and_closed(port_deadline, wait_for_port=False)
        return {
            "schema_version": 1,
            "status": "passed",
            "mode": mode,
            "game_process_running": False,
            "port_accepting": False,
            "process_samples": process_samples,
            "port_samples": port_samples,
        }

    if mode != "wait-stopped":
        fail(EXIT_INTERNAL, "internal_failure")

    process_deadline = monotonic() + _PROCESS_EXIT_MAXIMUM_SECONDS
    while True:
        state = observe_process(process_deadline, "process_exit_timeout")
        if state is _ProcessState.Stopped:
            break
        sleep_until_next(process_deadline, "process_exit_timeout")

    port_deadline = monotonic() + _PORT_RELEASE_MAXIMUM_SECONDS
    confirm_stopped_and_closed(port_deadline, wait_for_port=True)
    return {
        "schema_version": 1,
        "status": "passed",
        "mode": mode,
        "game_process_running": False,
        "port_accepting": False,
        "process_samples": process_samples,
        "port_samples": port_samples,
    }


def _operation() -> dict[str, object]:
    user_profile_value, supplied_uid, mode = parse_args()
    user_profile = absolute_path(user_profile_value, "user_profile")
    uid = _require_identity(user_profile, supplied_uid)
    executable = _require_game_executable(user_profile, uid)
    monotonic = time.monotonic
    return _evaluate(
        mode,
        lambda deadline: _process_probe(executable, deadline, monotonic),
        lambda deadline: _port_probe(deadline, monotonic),
        time.sleep,
        monotonic,
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
