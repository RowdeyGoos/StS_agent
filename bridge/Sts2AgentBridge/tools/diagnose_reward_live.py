#!/usr/bin/env python3
"""Opt-in, capture-off reward-action failure classification CLI."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from pathlib import Path

import apply_reward_live as reward
import probe_live as probe
from reward_action_diagnostics import RewardActionDiagnostics
from tool_common import EXIT_INTERNAL, ToolFailure, absolute_path, emit


def _execute() -> tuple[dict[str, object], int]:
    diagnostics = RewardActionDiagnostics()
    credential: bytearray | None = None
    try:
        user_profile_value, supplied_uid, provider = reward.parse_args()
        user_profile: Path = absolute_path(user_profile_value, "user_profile")
        uid = probe._require_identity(user_profile, supplied_uid)
        credential = probe._load_fixed_credential(user_profile, uid)
        reward._run_apply_reward(
            credential, provider, probe._literal_loopback_connector, diagnostics,
        )
        return diagnostics.payload("passed", "none"), 0
    except KeyboardInterrupt:
        diagnostics.interrupted()
        return diagnostics.payload("failed", "interrupted"), EXIT_INTERNAL
    except ToolFailure as failure:
        diagnostics.pre_action_failure()
        return diagnostics.payload("failed", failure.error_code), failure.exit_code
    except Exception:
        diagnostics.internal_failure()
        return diagnostics.payload("failed", "internal_failure"), EXIT_INTERNAL
    finally:
        if credential is not None:
            probe._zero(credential)


def operation() -> dict[str, object]:
    return _execute()[0]


def main() -> int:
    payload, exit_code = _execute()
    emit(payload)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
