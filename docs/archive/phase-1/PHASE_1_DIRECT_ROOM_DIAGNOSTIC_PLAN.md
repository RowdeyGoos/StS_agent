# Direct room diagnostic contract

Date: 2026-09-05. Baseline: `dc8e666` source, `9673102` documentation.
The user requested a targeted question-mark event test after the first new
run diagnostic never entered the room client. The user will prepare the exact
state and explicitly waived repeated unmodded launch/quit cleanup checks.
This adds a separate direct-room adapter; the frozen run diagnostic remains
unchanged. The coordinator accepts this document by exact hash in the ledger
before implementation. Parent: [room-stage plan](PHASE_1_ROOM_STAGE_DIAGNOSTIC_PLAN.md)
and [actor-ready ledger](research/PHASE_1_ACTOR_READY_ACCEPTANCE.md).

## Exact implementation and output

- New `bridge/Sts2AgentBridge/tools/diagnose_room_live.py` delegates the existing
  room parser's six arguments: `--user-profile`, `--effective-uid`, and
  `--decision-provider safe`. It executes the existing room producer once.
- Add only optional keyword-only `diagnostics=None` to `apply_room_live._operation`.
  Pass it to the already instrumented `_run_apply_room` only when non-null.
  The unchanged public `room.operation()` and default runner call keep their
  signatures, arguments, results, checks and error behavior.
- Reuse `RoomStageDiagnostics`, its exact record validator, the run diagnostic's
  non-retaining sink and strict existing failure-code allowlist helper, and the
  acceptance wrapper's mutable-result cleanup helper. Do not refactor those
  accepted implementations or change any existing output contract.
- Exact top-level keys in order: `schema_version` (exact int 1), `status`
  (`passed`/`failed`), `milestone` (`r0i_room_diagnostic`), `code`, `room`.
  `code=none` only on success. Failure codes/exits, cancellation and unsafe-state/
  cleanup precedence are identical to the frozen run diagnostic. Unknown failure
  is `internal_failure`/exit 5; cancellation is `interrupted`/exit 5 unless unsafe
  state/cleanup overrides it. The direct wrapper additionally passes through
  only the exact room-parser pair `(exit 2, "invalid_decision_provider")`, checking
  exact int/string types locally before delegating other failures to the frozen
  helper. Do not expand the shared allowlist. `room=null` only for unsafe state
  or cleanup.
- `room` is exactly the already frozen eight-field room-stage record. No extra
  summary, route/poll count, raw body, ID, arbitrary text, timing, history, file
  output or capture directory is added.
- Success requires existing `verify_room_acceptance.summarize_room_result` to
  validate the full producer result before any output; discard its aggregate.
  Require diagnostic stage complete, completion true, positive equal attempt/
  accepted counts equal to the validated result's accepted count, and last ready
  kind equal to the validated result's screen kind. No direct-room success may
  use the not-entered default. Failure emits no partial acceptance result.
- Recorder construction, producer execution, result/state validation and cleanup
  all occur under the existing non-retaining stdout/stderr sink. Restore streams
  before exactly one final compact emission. Stop on the first error, never
  resume, retry, reconstruct a previous response or run without diagnostics.
- Same existing 30-second room deadline, 12-action cap, safe provider, receipt,
  replay, identity/completion, transport and credential cleanup rules. No map,
  reward or combat action is added. C#, wire, package and run contracts stay frozen.

## Ownership and gates

`DR-IMPLEMENT` owns only `apply_room_live.py`, new `diagnose_room_live.py`,
new `diagnose_room_live_fixtures.py` and its new pytest wrapper under
`tests/backends/live`. All tool files are under `bridge/Sts2AgentBridge/tools`.
The coordinator owns this plan and current-status/ledger/README/roadmap updates.
`DR-REVIEW` is independent and read-only. Use Sol/high per the active execution
plan. No worker commits or live operations. Freeze the exact plan before writes.

Use synthetic literal actual-client requests through the real new CLI and room
producer (substitute only OS identity, credentials, connector/clock). Verify
accepted-event then waiting timeout with useful stage/count output, zero-action
waiting, a failed/uncertain receipt, strict successful room completion, default
room CLI parity, argument rejection, cleanup/cancellation/unknown-noisy failures,
unsafe state/cleanup precedence and no extra requests. Reuse the independent
existing wire-fixture transport where useful; do not substitute a room outcome
for the timeout gate. Run the new gate plus existing room-stage/run-wire/timeout/
transport/acceptance tests and final full suite. Independently review source,
fixture evidence and exact hashes before a live invocation.

## User-prepared live state

After cleanup and reviewed repository gates, install the same pinned bridge
through the existing manager and prompt the user to launch and prepare Profile
3, Ironclad, Ascension 0, at a fresh event reached through a question-mark node,
with choices visible and no choice selected. Verify the visible state; a node
that resolves to combat, shop or another unsupported surface is not this test.
Do not enter a previous uncertain room or replay its action. The user may handle
navigation to this exact target; it is outside the direct room client's evidence.

Run the new diagnostic once at the untouched event. Retain only its fixed final
aggregate. Do not manually continue after the controller stops. Limit the live
campaign to 30 minutes including cleanup. Normal quit, stopped/closed checks,
exact quarantine/purge and final base verification remain required. At the user's
explicit direction, omit the repeated unmodded launch/quit check and record that
waiver; do not claim that original gate passed. No profile/save filesystem access,
Cloud change, retained corpus, remote Git or broader capabilities are authorized.
