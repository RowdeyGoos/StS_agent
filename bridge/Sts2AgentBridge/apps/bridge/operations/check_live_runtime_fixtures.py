#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import contextlib
import errno
import io
import os
import socket
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_live_runtime as runtime
from tool_common import (
    EXIT_INTERNAL,
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    EXIT_UNSAFE_BOUNDARY,
    ToolFailure,
    fail,
    main,
    run_cli,
)


class _FakeClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, value: float) -> None:
        if value < 0.0:
            fail(EXIT_MISMATCH, "runtime_fixture_negative_time")
        self.value += value


class _ProcessSequence:
    def __init__(
        self,
        clock: _FakeClock,
        values: list[tuple[runtime._ProcessState, float]],
    ) -> None:
        self._clock = clock
        self._values = values
        self.calls = 0
        self.deadlines: list[float] = []

    def __call__(self, deadline: float) -> runtime._ProcessState:
        if self.calls >= len(self._values):
            fail(EXIT_MISMATCH, "runtime_fixture_process_probe_exhausted")
        state, duration = self._values[self.calls]
        self.calls += 1
        self.deadlines.append(deadline)
        self._clock.advance(duration)
        return state


class _PortSequence:
    def __init__(self, clock: _FakeClock, values: list[tuple[bool, float]]) -> None:
        self._clock = clock
        self._values = values
        self.calls = 0
        self.deadlines: list[float] = []

    def __call__(self, deadline: float) -> bool:
        if self.calls >= len(self._values):
            fail(EXIT_MISMATCH, "runtime_fixture_port_probe_exhausted")
        accepting, duration = self._values[self.calls]
        self.calls += 1
        self.deadlines.append(deadline)
        self._clock.advance(duration)
        return accepting


class _Sleeper:
    def __init__(self, clock: _FakeClock) -> None:
        self._clock = clock
        self.values: list[float] = []

    @property
    def calls(self) -> int:
        return len(self.values)

    def __call__(self, value: float) -> None:
        if value <= 0.0 or value > runtime._POLL_INTERVAL_SECONDS:
            fail(EXIT_MISMATCH, "runtime_fixture_sleep_bound")
        self.values.append(value)
        self._clock.advance(value)


def _process_values(
    *states: runtime._ProcessState,
) -> list[tuple[runtime._ProcessState, float]]:
    return [(state, 0.0) for state in states]


def _port_values(*states: bool) -> list[tuple[bool, float]]:
    return [(state, 0.0) for state in states]


def _expect_failure(
    operation: Callable[[], object],
    expected_code: str,
    expected_exit: int = EXIT_MISMATCH,
) -> None:
    try:
        operation()
    except ToolFailure as failure:
        if failure.exit_code == expected_exit and failure.error_code == expected_code:
            return
        fail(EXIT_MISMATCH, "runtime_fixture_wrong_rejection")
    fail(EXIT_MISMATCH, "runtime_fixture_unexpected_pass")


def _expect_deadline(operation: Callable[[], object]) -> None:
    try:
        operation()
    except runtime._DeadlineExpired:
        return
    fail(EXIT_MISMATCH, "runtime_fixture_deadline_not_enforced")


def _evaluate(
    mode: str,
    process_values: list[tuple[runtime._ProcessState, float]],
    port_values: list[tuple[bool, float]],
) -> tuple[dict[str, object], _ProcessSequence, _PortSequence, _Sleeper, _FakeClock]:
    clock = _FakeClock()
    process = _ProcessSequence(clock, process_values)
    port = _PortSequence(clock, port_values)
    sleeper = _Sleeper(clock)
    payload = runtime._evaluate(mode, process, port, sleeper, clock)
    return payload, process, port, sleeper, clock


def _exercise_identity_binding() -> None:
    identity = SimpleNamespace(pw_dir="/synthetic-profile")
    with (
        mock.patch.object(runtime.sys, "platform", "darwin"),
        mock.patch.object(runtime.os, "geteuid", return_value=501),
        mock.patch.object(runtime.pwd, "getpwuid", return_value=identity),
    ):
        if runtime._require_identity(Path("/synthetic-profile"), 501) != 501:
            fail(EXIT_MISMATCH, "runtime_fixture_identity_binding")
        _expect_failure(
            lambda: runtime._require_identity(Path("/different-profile"), 501),
            "user_profile_mismatch",
            EXIT_UNSAFE_BOUNDARY,
        )
        _expect_failure(
            lambda: runtime._require_identity(Path("/synthetic-profile"), 502),
            "effective_uid_mismatch",
            EXIT_UNSAFE_BOUNDARY,
        )


def _exercise_executable_metadata() -> None:
    with tempfile.TemporaryDirectory(
        prefix="sts-item-v1-runtime-fixture.",
        dir="/private/tmp",
    ) as temporary:
        user_profile = Path(temporary)
        executable = user_profile.joinpath(*runtime._EXECUTABLE_COMPONENTS)
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"synthetic executable")
        uid = os.geteuid()
        if runtime._require_game_executable(user_profile, uid) != executable:
            fail(EXIT_MISMATCH, "runtime_fixture_executable_path")
        _expect_failure(
            lambda: runtime._require_game_executable(user_profile, uid + 1),
            "game_executable_identity",
            EXIT_UNSAFE_BOUNDARY,
        )

        target = user_profile / "synthetic-target"
        target.write_bytes(b"target")
        executable.unlink()
        executable.symlink_to(target)
        _expect_failure(
            lambda: runtime._require_game_executable(user_profile, uid),
            "symlink_path_component",
            EXIT_UNSAFE_BOUNDARY,
        )


def _exercise_process_subprocess_boundary() -> None:
    executable = Path("/synthetic profile/SlayTheSpire2.app/Contents/MacOS/Slay the Spire 2")
    clock = _FakeClock()
    completed = subprocess.CompletedProcess(args=[], returncode=0)
    with mock.patch.object(runtime.subprocess, "run", return_value=completed) as runner:
        state = runtime._process_probe(executable, 10.0, clock)
    if state is not runtime._ProcessState.ExactRunning or runner.call_count != 1:
        fail(EXIT_MISMATCH, "runtime_fixture_exact_process")
    command = runner.call_args.args[0]
    pattern = command[-1]
    if (
        command[:4] != ["/usr/bin/pgrep", "-q", "-f", pattern]
        or not pattern.startswith("^/synthetic profile/")
        or not pattern.endswith("([[:space:]]|$)")
        or runner.call_args.kwargs.get("timeout") != runtime._PGREP_TIMEOUT_SECONDS
        or runner.call_args.kwargs.get("stdout") is not subprocess.DEVNULL
        or runner.call_args.kwargs.get("stderr") is not subprocess.DEVNULL
    ):
        fail(EXIT_MISMATCH, "runtime_fixture_pgrep_invocation")

    not_found = subprocess.CompletedProcess(args=[], returncode=1)
    found = subprocess.CompletedProcess(args=[], returncode=0)
    with mock.patch.object(runtime.subprocess, "run", side_effect=[not_found, found]) as runner:
        state = runtime._process_probe(executable, 10.0, clock)
    if (
        state is not runtime._ProcessState.AmbiguousRunning
        or runner.call_count != 2
        or runner.call_args_list[1].args[0]
        != ["/usr/bin/pgrep", "-q", "-x", runtime._PROCESS_NAME]
    ):
        fail(EXIT_MISMATCH, "runtime_fixture_ambiguous_process")

    with mock.patch.object(runtime.subprocess, "run", side_effect=[not_found, not_found]):
        if runtime._process_probe(executable, 10.0, clock) is not runtime._ProcessState.Stopped:
            fail(EXIT_MISMATCH, "runtime_fixture_stopped_process")

    capped_clock = _FakeClock()
    with mock.patch.object(runtime.subprocess, "run", return_value=not_found) as runner:
        if runtime._pgrep(["-q", "-x", "synthetic"], 0.125, capped_clock):
            fail(EXIT_MISMATCH, "runtime_fixture_pgrep_cap_result")
    if runner.call_args.kwargs.get("timeout") != 0.125:
        fail(EXIT_MISMATCH, "runtime_fixture_pgrep_timeout_cap")

    timeout_clock = _FakeClock()

    def expire(command: list[str], **kwargs: object) -> object:
        duration = kwargs.get("timeout")
        if not isinstance(duration, float):
            fail(EXIT_MISMATCH, "runtime_fixture_timeout_type")
        timeout_clock.advance(duration)
        raise subprocess.TimeoutExpired(command, duration)

    with mock.patch.object(runtime.subprocess, "run", side_effect=expire):
        _expect_deadline(
            lambda: runtime._pgrep(["-q", "-x", "synthetic"], 0.1, timeout_clock)
        )

    invalid = subprocess.CompletedProcess(args=[], returncode=2)
    with mock.patch.object(runtime.subprocess, "run", return_value=invalid):
        _expect_failure(
            lambda: runtime._pgrep(["-q", "-x", "synthetic"], 1.0, _FakeClock()),
            "process_check_failed",
            EXIT_UNSAFE_BOUNDARY,
        )


def _exercise_live_loopback_boundary() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.settimeout(1.0)
    listener.bind((runtime._LISTENER_ADDRESS, 0))
    listener.listen(1)
    accepting_port = listener.getsockname()[1]
    try:
        with mock.patch.object(runtime, "_LISTENER_PORT", accepting_port):
            if not runtime._port_probe(time.monotonic() + 1.0, time.monotonic):
                fail(EXIT_MISMATCH, "runtime_fixture_accepting_port")
        accepted, _ = listener.accept()
        accepted.close()
    finally:
        listener.close()

    closed_scout = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    closed_scout.bind((runtime._LISTENER_ADDRESS, 0))
    closed_port = closed_scout.getsockname()[1]
    closed_scout.close()
    with mock.patch.object(runtime, "_LISTENER_PORT", closed_port):
        if runtime._port_probe(time.monotonic() + 1.0, time.monotonic):
            fail(EXIT_MISMATCH, "runtime_fixture_refused_port")

    class _RefusedSocket:
        def __init__(self) -> None:
            self.timeout: float | None = None

        def settimeout(self, value: float) -> None:
            self.timeout = value

        def connect_ex(self, endpoint: tuple[str, int]) -> int:
            if endpoint != (runtime._LISTENER_ADDRESS, runtime._LISTENER_PORT):
                fail(EXIT_MISMATCH, "runtime_fixture_port_endpoint")
            return errno.ECONNREFUSED

        def close(self) -> None:
            return

    refused = _RefusedSocket()
    cap_clock = _FakeClock()
    with mock.patch.object(runtime.socket, "socket", return_value=refused):
        result = runtime._port_probe(0.05, cap_clock)
    if result or refused.timeout != 0.05:
        fail(EXIT_MISMATCH, "runtime_fixture_connect_timeout_cap")


def _exercise_argument_closure() -> None:
    base_arguments = [
        "--mode",
        "require-stopped",
        "--user-profile",
        "/synthetic-profile",
        "--effective-uid",
        "501",
    ]
    if runtime.parse_args(base_arguments) != ("/synthetic-profile", 501, "require-stopped"):
        fail(EXIT_MISMATCH, "runtime_fixture_valid_arguments")
    _expect_failure(
        lambda: runtime.parse_args(base_arguments + ["--port", "43117"]),
        "invalid_invocation",
        EXIT_INVALID_INVOCATION,
    )
    duplicate = base_arguments.copy()
    duplicate[2:4] = ["--mode", "require-running"]
    _expect_failure(
        lambda: runtime.parse_args(duplicate),
        "invalid_invocation",
        EXIT_INVALID_INVOCATION,
    )
    _expect_failure(
        lambda: runtime.parse_args(base_arguments[:-2]),
        "invalid_invocation",
        EXIT_INVALID_INVOCATION,
    )
    invalid_mode = base_arguments.copy()
    invalid_mode[1] = "scan"
    _expect_failure(
        lambda: runtime.parse_args(invalid_mode),
        "invalid_mode",
        EXIT_INVALID_INVOCATION,
    )
    leading_zero_uid = base_arguments.copy()
    leading_zero_uid[5] = "0501"
    _expect_failure(
        lambda: runtime.parse_args(leading_zero_uid),
        "invalid_effective_uid",
        EXIT_INVALID_INVOCATION,
    )
    wrong_uid = base_arguments.copy()
    wrong_uid[5] = "502"
    _expect_failure(
        lambda: runtime.parse_args(wrong_uid),
        "invalid_effective_uid",
        EXIT_INVALID_INVOCATION,
    )


def _exercise_interrupt_sanitization() -> None:
    def interrupt() -> dict[str, object]:
        raise KeyboardInterrupt

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exit_code = run_cli(interrupt)
    if (
        exit_code != EXIT_INTERNAL
        or output.getvalue()
        != '{"schema_version":1,"status":"failed","code":"interrupted"}\n'
    ):
        fail(EXIT_MISMATCH, "runtime_fixture_interrupt_sanitization")


def operation() -> dict[str, object]:
    checks: list[str] = []
    stopped = runtime._ProcessState.Stopped
    exact = runtime._ProcessState.ExactRunning
    ambiguous = runtime._ProcessState.AmbiguousRunning

    payload, process, port, sleeper, _ = _evaluate(
        "require-stopped",
        _process_values(stopped, stopped, stopped),
        _port_values(False, False),
    )
    if (
        payload.get("status") != "passed"
        or process.calls != 3
        or port.calls != 2
        or sleeper.calls != 1
        or payload.get("process_samples") != 3
        or payload.get("port_samples") != 2
    ):
        fail(EXIT_MISMATCH, "runtime_fixture_require_stopped")
    checks.append("joint_require_stopped")

    payload, process, port, sleeper, _ = _evaluate(
        "require-running",
        _process_values(exact),
        [],
    )
    if (
        payload.get("game_process_running") is not True
        or process.calls != 1
        or port.calls != 0
        or sleeper.calls != 0
    ):
        fail(EXIT_MISMATCH, "runtime_fixture_require_running")
    checks.append("exact_require_running")

    clock = _FakeClock()
    _expect_failure(
        lambda: runtime._evaluate(
            "require-running",
            _ProcessSequence(clock, _process_values(ambiguous)),
            _PortSequence(clock, []),
            _Sleeper(clock),
            clock,
        ),
        "game_process_identity_ambiguous",
        EXIT_UNSAFE_BOUNDARY,
    )
    checks.append("ambiguous_running_rejected")

    payload, process, port, sleeper, _ = _evaluate(
        "sample-base-port-closed",
        _process_values(exact),
        _port_values(False),
    )
    if (
        payload.get("port_accepting") is not False
        or process.calls != 1
        or port.calls != 1
        or sleeper.calls != 0
    ):
        fail(EXIT_MISMATCH, "runtime_fixture_base_sample")
    checks.append("base_port_closed_sample")

    payload, process, port, sleeper, _ = _evaluate(
        "wait-stopped",
        _process_values(exact, ambiguous, stopped, stopped, stopped, stopped),
        _port_values(True, False, False),
    )
    if (
        process.calls != 6
        or port.calls != 3
        or sleeper.calls != 4
        or payload.get("game_process_running") is not False
    ):
        fail(EXIT_MISMATCH, "runtime_fixture_bounded_wait")
    checks.append("bounded_joint_wait")

    for running_state in (exact, ambiguous):
        clock = _FakeClock()
        _expect_failure(
            lambda running_state=running_state: runtime._evaluate(
                "require-stopped",
                _ProcessSequence(clock, _process_values(running_state)),
                _PortSequence(clock, []),
                _Sleeper(clock),
                clock,
            ),
            "game_still_running",
        )
    checks.append("stopped_rejects_all_running")

    clock = _FakeClock()
    _expect_failure(
        lambda: runtime._evaluate(
            "sample-base-port-closed",
            _ProcessSequence(clock, _process_values(exact)),
            _PortSequence(clock, _port_values(True)),
            _Sleeper(clock),
            clock,
        ),
        "port_accepting",
    )
    checks.append("base_sample_rejects_open_port")

    clock = _FakeClock()
    process = _ProcessSequence(clock, _process_values(stopped, exact))
    port = _PortSequence(clock, _port_values(False))
    sleeper = _Sleeper(clock)
    _expect_failure(
        lambda: runtime._evaluate("wait-stopped", process, port, sleeper, clock),
        "game_restarted_during_port_release",
    )
    if process.calls != 2 or port.calls != 1 or sleeper.calls != 0:
        fail(EXIT_MISMATCH, "runtime_fixture_restart_counts")
    checks.append("restart_during_release_rejected")

    clock = _FakeClock()
    _expect_failure(
        lambda: runtime._evaluate(
            "wait-stopped",
            _ProcessSequence(clock, [(exact, 30.01)]),
            _PortSequence(clock, []),
            _Sleeper(clock),
            clock,
        ),
        "process_exit_timeout",
    )
    checks.append("process_probe_duration_bounded")

    clock = _FakeClock()
    _expect_failure(
        lambda: runtime._evaluate(
            "wait-stopped",
            _ProcessSequence(clock, [(stopped, 0.0), (stopped, 0.0)]),
            _PortSequence(clock, [(True, 5.01)]),
            _Sleeper(clock),
            clock,
        ),
        "port_release_timeout",
    )
    checks.append("port_probe_duration_bounded")

    clock = _FakeClock()
    sleeper = _Sleeper(clock)
    _expect_failure(
        lambda: runtime._evaluate(
            "wait-stopped",
            _ProcessSequence(clock, [(exact, 29.8)]),
            _PortSequence(clock, []),
            sleeper,
            clock,
        ),
        "process_exit_timeout",
    )
    if sleeper.calls != 1 or not 0.0 < sleeper.values[0] <= 0.21:
        fail(EXIT_MISMATCH, "runtime_fixture_capped_sleep")
    checks.append("sleep_capped_to_deadline")

    _exercise_identity_binding()
    checks.append("identity_binding")
    _exercise_executable_metadata()
    checks.append("executable_metadata")
    _exercise_process_subprocess_boundary()
    checks.append("pgrep_boundary")
    _exercise_live_loopback_boundary()
    checks.append("live_loopback_boundary")
    _exercise_argument_closure()
    checks.append("argument_closure")
    _exercise_interrupt_sanitization()
    checks.append("interrupt_sanitization")

    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "check_live_runtime_fixtures",
        "checks": checks,
        "check_count": len(checks),
    }


if __name__ == "__main__":
    main(operation)
