#!/usr/bin/env python3
"""Emit a capture-off, sanitized acceptance summary for one bounded run."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import apply_run_live as run
from tool_common import EXIT_INTERNAL, ToolFailure, fail, main
from verify_room_acceptance import _KNOWN_PRODUCTION_FAILURE_CODES, summarize_run_acceptance_result


def _clear_mutable_buffers(value: object, seen: set[int] | None = None) -> bool:
    """Zero reachable mutable byte storage without invoking container overrides."""
    if seen is None:
        seen = set()
    pending = [value]
    try:
        while pending:
            current = pending.pop()
            identity = id(current)
            if identity in seen:
                continue
            seen.add(identity)
            if isinstance(current, bytearray):
                length = bytearray.__len__(current)
                bytearray.__setitem__(current, slice(None), b"\x00" * length)
                continue
            if isinstance(current, memoryview):
                try:
                    backing = current.obj
                    readonly = current.readonly
                except ValueError:
                    # A released view exposes no reachable storage.
                    continue
                pending.append(backing)
                if readonly or isinstance(backing, bytearray):
                    continue
                byte_view: memoryview | None = None
                try:
                    byte_view = current.cast("B")
                    byte_view[:] = b"\x00" * byte_view.nbytes
                finally:
                    if byte_view is not None:
                        byte_view.release()
                continue
            if isinstance(current, dict):
                pending.extend(dict.values(current))
            elif isinstance(current, list):
                pending.extend(list.__iter__(current))
            elif isinstance(current, tuple):
                pending.extend(tuple.__iter__(current))
    except BaseException:
        return False
    return True


def _operation() -> dict[str, object]:
    # ``run.operation`` owns the established 14/16 argument parsing and all
    # production failures.  Do not parse, copy, or log those arguments here.
    result: object = None
    try:
        result = run.operation()
        return summarize_run_acceptance_result(result)
    except ToolFailure as failure:
        if (
            type(failure.exit_code) is int
            and type(failure.error_code) is str
            and (
                (
                    failure.exit_code == 4
                    and failure.error_code == "run_acceptance_result_mismatch"
                )
                or (
                    failure.exit_code in (2, 3, 4, 5)
                    and failure.error_code in _KNOWN_PRODUCTION_FAILURE_CODES
                )
            )
        ):
            raise
        fail(EXIT_INTERNAL, "run_acceptance_callback_failure")
    except KeyboardInterrupt:
        raise
    except BaseException:
        fail(EXIT_INTERNAL, "run_acceptance_callback_failure")
    finally:
        cleanup_ok = _clear_mutable_buffers(result)
        if not cleanup_ok and not isinstance(sys.exc_info()[1], KeyboardInterrupt):
            fail(EXIT_INTERNAL, "run_acceptance_callback_failure")


def operation() -> dict[str, object]:
    return _operation()


if __name__ == "__main__":
    main(operation)
