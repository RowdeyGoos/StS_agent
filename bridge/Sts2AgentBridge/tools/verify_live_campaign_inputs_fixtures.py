#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import hashlib
import io
import os
import stat
import subprocess
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import Callable

import verify_live_campaign_inputs as verifier
from tool_common import (
    EXIT_MISMATCH,
    fail,
    main,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _expect_failure(
    operation: Callable[[], object],
    code: str,
    exit_code: int,
) -> None:
    try:
        operation()
    except verifier.ToolFailure as failure:
        if failure.error_code == code and failure.exit_code == exit_code:
            return
        fail(EXIT_MISMATCH, "input_fixture_wrong_failure")
    fail(EXIT_MISMATCH, "input_fixture_unexpected_pass")


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _exercise_verification() -> list[str]:
    checks: list[str] = []
    with tempfile.TemporaryDirectory(
        prefix="sts-r0a-input-fixture.",
        dir="/private/tmp",
    ) as temporary:
        root = Path(temporary)
        repo = root / "repo"
        artifact = root / "artifact"
        os_root = root / "os"
        self_path = repo / "tools" / "self.py"
        request_path = repo / "docs" / "request.md"
        fixture_path = repo / "tools" / "fixture.py"
        dll_path = artifact / "bridge.dll"
        python_path = os_root / "python3"
        shell_path = os_root / "bash"

        payloads = {
            self_path: b"synthetic self",
            request_path: b"synthetic request",
            fixture_path: b"synthetic fixture",
            dll_path: b"MZ synthetic bridge",
            python_path: b"synthetic python",
            shell_path: b"synthetic shell",
        }
        for path, data in payloads.items():
            _write(path, data)

        records = (
            verifier._Record("fixture", "repo", "tools/fixture.py", _sha256(payloads[fixture_path]), len(payloads[fixture_path])),
            verifier._Record("artifact", "artifact", "bridge.dll", _sha256(payloads[dll_path]), len(payloads[dll_path])),
            verifier._Record("python", "os", "launcher", _sha256(payloads[python_path]), len(payloads[python_path])),
            verifier._Record("shell", "os", "shell", _sha256(payloads[shell_path]), len(payloads[shell_path])),
        )
        kwargs = {
            "expected_self": _sha256(payloads[self_path]),
            "expected_request": _sha256(payloads[request_path]),
            "repo_root": repo,
            "artifact_root": artifact,
            "os_shell": shell_path,
            "os_python_launcher": python_path,
            "os_python_runtime": python_path,
            "self_path": self_path,
            "request_path": request_path,
            "records": records,
            "enforce_runtime": False,
        }

        result = verifier._verify_inputs(**kwargs)
        if result.get("checked_file_count") != 6 or result.get("input_set_id") != verifier.INPUT_SET_ID:
            fail(EXIT_MISMATCH, "input_fixture_success")
        checks.append("success")

        _expect_failure(
            lambda: verifier._verify_inputs(**{**kwargs, "expected_self": "0" * 64}),
            "self_hash_mismatch",
            EXIT_MISMATCH,
        )
        checks.append("self_hash")

        _expect_failure(
            lambda: verifier._verify_inputs(**{**kwargs, "expected_request": "0" * 64}),
            "request_hash_mismatch",
            EXIT_MISMATCH,
        )
        checks.append("request_hash")

        fixture_path.write_bytes(b"tampered fixture!")
        _expect_failure(
            lambda: verifier._verify_inputs(**kwargs),
            "input_hash_mismatch",
            EXIT_MISMATCH,
        )
        fixture_path.write_bytes(payloads[fixture_path])
        checks.append("input_hash")

        fixture_path.unlink()
        fixture_path.symlink_to(request_path)
        _expect_failure(
            lambda: verifier._verify_inputs(**kwargs),
            "symlink_path_component",
            verifier.EXIT_UNSAFE_BOUNDARY,
        )
        fixture_path.unlink()
        fixture_path.write_bytes(payloads[fixture_path])
        checks.append("symlink")

        hardlink = repo / "tools" / "hardlink.py"
        os.link(fixture_path, hardlink)
        _expect_failure(
            lambda: verifier._verify_inputs(**kwargs),
            "invalid_input_file",
            verifier.EXIT_UNSAFE_BOUNDARY,
        )
        hardlink.unlink()
        checks.append("hardlink")

        python_hardlink = os_root / "python-hardlink"
        os.link(python_path, python_hardlink)
        hardlinked_os_record = (
            verifier._Record(
                "python",
                "os",
                "launcher",
                _sha256(payloads[python_path]),
                len(payloads[python_path]),
                2,
            ),
        )
        result = verifier._verify_inputs(
            **{**kwargs, "records": hardlinked_os_record}
        )
        if result.get("checked_file_count") != 3:
            fail(EXIT_MISMATCH, "input_fixture_os_hardlink_success")
        wrong_os_link_count = (
            verifier._Record(
                "python",
                "os",
                "launcher",
                _sha256(payloads[python_path]),
                len(payloads[python_path]),
                1,
            ),
        )
        _expect_failure(
            lambda: verifier._verify_inputs(
                **{**kwargs, "records": wrong_os_link_count}
            ),
            "invalid_input_file",
            verifier.EXIT_UNSAFE_BOUNDARY,
        )
        python_hardlink.unlink()
        checks.append("os_link_count_policy")

        wrong_size = (
            verifier._Record(
                "fixture",
                "repo",
                "tools/fixture.py",
                _sha256(payloads[fixture_path]),
                len(payloads[fixture_path]) + 1,
            ),
        )
        _expect_failure(
            lambda: verifier._verify_inputs(**{**kwargs, "records": wrong_size}),
            "invalid_input_file",
            verifier.EXIT_UNSAFE_BOUNDARY,
        )
        checks.append("exact_size_bound")

        duplicate = records + (
            verifier._Record("fixture", "repo", "tools/fixture.py", _sha256(payloads[fixture_path]), len(payloads[fixture_path])),
        )
        _expect_failure(
            lambda: verifier._verify_inputs(**{**kwargs, "records": duplicate}),
            "invalid_input_manifest",
            verifier.EXIT_INTERNAL,
        )
        checks.append("duplicate_label")

        duplicate_path = records + (
            verifier._Record(
                "second_fixture_label",
                "repo",
                "tools/fixture.py",
                _sha256(payloads[fixture_path]),
                len(payloads[fixture_path]),
            ),
        )
        _expect_failure(
            lambda: verifier._verify_inputs(
                **{**kwargs, "records": duplicate_path}
            ),
            "invalid_input_manifest",
            verifier.EXIT_INTERNAL,
        )
        checks.append("duplicate_path")

        traversal = (
            verifier._Record("traversal", "repo", "../outside", "0" * 64, 1),
        )
        _expect_failure(
            lambda: verifier._verify_inputs(**{**kwargs, "records": traversal}),
            "invalid_input_manifest",
            verifier.EXIT_INTERNAL,
        )
        checks.append("manifest_traversal")

    return checks


def _exercise_isolated_subprocess() -> list[str]:
    with tempfile.TemporaryDirectory(
        prefix="sts-r0a-input-isolation-fixture.",
        dir="/private/tmp",
    ) as temporary:
        root = Path(temporary)
        helper = root / verifier._SELF_RELATIVE
        request = root / verifier._REQUEST_RELATIVE
        source = Path(verifier.__file__).read_bytes()
        request_data = b"synthetic approved request"
        _write(helper, source)
        _write(request, request_data)

        marker = root / "shadow-imported"
        shadow = (
            b"from pathlib import Path\n"
            + b"Path("
            + repr(str(marker)).encode("utf-8")
            + b").write_text('unsafe')\n"
        )
        _write(root / "hashlib.py", shadow)
        _write(helper.parent / "hashlib.py", shadow)

        completed = subprocess.run(
            [
                "/usr/bin/python3",
                "-I",
                "-B",
                "-S",
                str(helper),
                "--expected-self-sha256",
                _sha256(source),
                "--expected-request-sha256",
                _sha256(request_data),
            ],
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=5,
        )
        if marker.exists() or completed.returncode == 0:
            fail(EXIT_MISMATCH, "input_fixture_isolation")
        if (
            completed.stderr != b""
            or len(completed.stdout) > 128
            or not completed.stdout.startswith(
                b'{"schema_version":1,"status":"failed","code":"'
            )
            or not completed.stdout.endswith(b'"}\n')
        ):
            fail(EXIT_MISMATCH, "input_fixture_isolation_output")
    return ["isolated_stdlib_imports"]


def _exercise_arguments() -> list[str]:
    checks: list[str] = []
    valid = [
        "--expected-self-sha256",
        "1" * 64,
        "--expected-request-sha256",
        "2" * 64,
    ]
    if verifier._parse_args(valid) != ("1" * 64, "2" * 64):
        fail(EXIT_MISMATCH, "input_fixture_arguments")
    checks.append("arguments")

    _expect_failure(
        lambda: verifier._parse_args(valid + ["--root", "/private"]),
        "invalid_invocation",
        verifier.EXIT_INVALID_INVOCATION,
    )
    _expect_failure(
        lambda: verifier._parse_args(valid[:2] + valid[:2]),
        "invalid_invocation",
        verifier.EXIT_INVALID_INVOCATION,
    )
    _expect_failure(
        lambda: verifier._parse_args(valid[:-1] + ["not-a-hash"]),
        "invalid_request_sha256",
        verifier.EXIT_INVALID_INVOCATION,
    )
    checks.append("argument_closure")
    return checks


def _exercise_runtime_link_chain() -> list[str]:
    checks: list[str] = []
    with tempfile.TemporaryDirectory(
        prefix="sts-r0a-python-link-fixture.",
        dir="/private/tmp",
    ) as temporary:
        root = Path(temporary)
        executable_link = root / "CommandLineTools" / "usr" / "bin" / "python3"
        runtime_link = (
            root
            / "CommandLineTools"
            / "Library"
            / "Frameworks"
            / "Python3.framework"
            / "Versions"
            / "3.9"
            / "bin"
            / "python3"
        )
        runtime = runtime_link.with_name("python3.9")
        executable_link.parent.mkdir(parents=True)
        runtime_link.parent.mkdir(parents=True)
        runtime.write_bytes(b"synthetic runtime")
        first_target = (
            "../../Library/Frameworks/Python3.framework/Versions/3.9/bin/python3"
        )
        second_target = "python3.9"
        executable_link.symlink_to(first_target)
        runtime_link.symlink_to(second_target)
        link_mode = stat.S_IMODE(executable_link.lstat().st_mode)

        kwargs = {
            "executable_link_path": executable_link,
            "executable_link_target": first_target,
            "runtime_link_path": runtime_link,
            "runtime_link_target": second_target,
            "runtime_path": runtime,
            "expected_uid": os.geteuid(),
            "expected_mode": link_mode,
            "expected_link_count": 1,
        }
        verifier._require_runtime_link_chain(**kwargs)
        checks.append("runtime_link_chain")

        for field, value in (
            ("executable_link_target", "../wrong"),
            ("runtime_link_target", "wrong-runtime"),
            ("expected_uid", os.geteuid() + 1),
            ("expected_mode", link_mode ^ 0o100),
            ("expected_link_count", 2),
        ):
            _expect_failure(
                lambda field=field, value=value: verifier._require_runtime_link_chain(
                    **{**kwargs, field: value}
                ),
                "python_runtime_mismatch",
                verifier.EXIT_UNSAFE_BOUNDARY,
            )
        checks.append("runtime_link_metadata_and_targets")

        aliased_parent = root / "aliased-runtime-parent"
        aliased_parent.symlink_to(runtime_link.parent, target_is_directory=True)
        _expect_failure(
            lambda: verifier._require_runtime_link_chain(
                **{
                    **kwargs,
                    "runtime_link_path": aliased_parent / "python3",
                    "runtime_path": aliased_parent / "python3.9",
                }
            ),
            "symlink_path_component",
            verifier.EXIT_UNSAFE_BOUNDARY,
        )
        checks.append("runtime_link_parent_chain")

    return checks


def _exercise_shell_environment() -> list[str]:
    verifier._require_shell_environment({})
    for name in ("BASH_ENV", "SHELLOPTS", "BASHOPTS"):
        _expect_failure(
            lambda name=name: verifier._require_shell_environment({name: ""}),
            "shell_environment_mismatch",
            verifier.EXIT_UNSAFE_BOUNDARY,
        )
    return ["shell_environment"]


def _exercise_sanitized_output() -> list[str]:
    def failing() -> dict[str, object]:
        verifier.fail(verifier.EXIT_MISMATCH, "input_hash_mismatch")

    output = io.StringIO()
    with redirect_stdout(output):
        code = verifier._run_cli(failing)
    if (
        code != verifier.EXIT_MISMATCH
        or output.getvalue()
        != '{"schema_version":1,"status":"failed","code":"input_hash_mismatch"}\n'
    ):
        fail(EXIT_MISMATCH, "input_fixture_sanitized_output")
    return ["sanitized_output"]


def operation() -> dict[str, object]:
    checks = _exercise_verification()
    checks.extend(_exercise_arguments())
    checks.extend(_exercise_runtime_link_chain())
    checks.extend(_exercise_shell_environment())
    checks.extend(_exercise_sanitized_output())
    checks.extend(_exercise_isolated_subprocess())
    return {
        "schema_version": 1,
        "status": "passed",
        "suite": "verify_live_campaign_inputs_fixtures",
        "checks": checks,
        "check_count": len(checks),
    }


if __name__ == "__main__":
    main(operation)
