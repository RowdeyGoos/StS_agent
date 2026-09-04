#!/usr/bin/env python3
"""Emit a capture-off, sanitized acceptance summary for one bounded run."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import apply_run_live as run
from tool_common import EXIT_INTERNAL, ToolFailure, fail, main
from verify_room_acceptance import _KNOWN_PRODUCTION_FAILURE_CODES, summarize_run_acceptance_result


def _clear_mutable_buffers(value: object, seen: set[int] | None = None) -> None:
    """Best-effort zeroization for an unexpected mutable nested producer value."""
    if seen is None:
        seen = set()
    identity = id(value)
    if identity in seen:
        return
    seen.add(identity)
    if isinstance(value, bytearray):
        for index in range(len(value)):
            value[index] = 0
        return
    if isinstance(value, dict):
        for child in value.values():
            _clear_mutable_buffers(child, seen)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _clear_mutable_buffers(child, seen)


def _operation() -> dict[str, object]:
    # ``run.operation`` owns the established 14/16 argument parsing and all
    # production failures.  Do not parse, copy, or log those arguments here.
    result: object = None
    try:
        result = run.operation()
        return summarize_run_acceptance_result(result)
    except ToolFailure as failure:
        if failure.error_code == "run_acceptance_result_mismatch" or failure.error_code in _KNOWN_PRODUCTION_FAILURE_CODES:
            raise
        fail(EXIT_INTERNAL, "run_acceptance_callback_failure")
    except KeyboardInterrupt:
        raise
    except BaseException:
        fail(EXIT_INTERNAL, "run_acceptance_callback_failure")
    finally:
        _clear_mutable_buffers(result)


def operation() -> dict[str, object]:
    return _operation()


if __name__ == "__main__":
    main(operation)
