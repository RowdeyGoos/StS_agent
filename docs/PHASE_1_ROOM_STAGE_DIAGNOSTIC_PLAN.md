# Bounded room-stage diagnostic

- **Date:** 2026-09-05
- **Baseline:** `135bc1fd562b68e0cc5351b7084ceb0d49364d8f`, clean
  `codex/phase1-actor-ready-integration` in the existing `23cf` checkout.
- **Status:** proposed exact contract; implementation waits for independent
  review and the coordinator's accepted hash in the actor-ready ledger.
- **Authority:** the user selected further development after the timeout
  diagnosis and renewed the same bounded live authority. This packet selects
  the proposed capture-off diagnostic only; previous exclusions remain.
- **Parent:** [actor-ready plan](PHASE_1_ACTOR_READY_EXECUTION_PLAN.md),
  [current status](PHASE_1_CURRENT_STATUS.md),
  [acceptance ledger](research/PHASE_1_ACTOR_READY_ACCEPTANCE.md), and
  [multi-agent execution](MULTI_AGENT_EXECUTION.md).

## Outcome and unchanged boundaries

Implement an explicitly selected Python diagnostic for one existing bounded
run. Distinguish the room client's host stage when it stops, while retaining
only a fixed aggregate. The prior `room_interaction_timeout` is not reclassified.
No production defect, event identity repair or timeout increase is selected.

C# bridge `0.8.0`, `live_probe_v0`, package pins, granular receipt validators,
existing run/acceptance JSON, argument parsing, providers, caps, completion and
replay rules remain unchanged. The new diagnostic neither adds requests nor
retries, fallback, phase scanning, action adoption or continuation. Every
existing command retains its exact default behavior and output.

The diagnostic cannot distinguish C# reasons that share the same canonical
waiting projection. An accepted receipt is distinct from room completion and
is not independently verified delivery, effect or whole-run reconciliation.

## Separate output contract

New entry point: `bridge/Sts2AgentBridge/tools/diagnose_run_room_live.py`.
Accept exactly the existing 14/16 arguments by delegating their parsing to
`apply_run_live.py`; add no flags, capture directory or automatic phase selection.
Execute its existing bounded-run producer once with a private optional diagnostic.

The exact top-level keys, in order, are:

1. `schema_version`: integer `1`.
2. `status`: `passed` or `failed`.
3. `milestone`: `r0i_run_room_diagnostic`.
4. `code`: `none` on success; an existing allowlisted production error on
   failure, `interrupted`, or the existing fixed `internal_failure`.
5. `room`: the exact record below, or null only when the diagnostic state or
   its cleanup cannot be safely validated.
6. `run_acceptance`: the unchanged full sanitized aggregate returned by
   `summarize_run_acceptance_result`, or null on every failure.

Success requires strict existing run acceptance and consistency with the room
record: zero room actions iff the client was not entered; otherwise room
completion must be confirmed and aggregate room actions must equal accepted
room receipts, with no unaccepted exchange. Failure never emits a partial run
summary or adopts any discarded component. A successful run without a room is
valid with `stage=not_entered` and zero room counters.

The exact `room` keys, in order, are:

| Field | Allowed values |
| --- | --- |
| `stage` | `not_entered`, `context_validation`, `health_read`, `manifest_read`, `room_read`, `room_validation`, `room_waiting`, `action_exchange`, `action_receipt`, `post_action`, `complete` |
| `last_observation_status` | `none`, `ready`, `waiting`, `unsupported`, `complete` |
| `last_ready_kind` | `none`, `rest_site`, `event` |
| `action_exchange_attempt_count` | integer 0 through 12 |
| `accepted_receipt_count` | integer 0 through attempt count |
| `last_attempted_action` | `none`, `rest_heal`, `rest_proceed`, `event_choice` |
| `last_accepted_action` | same fixed action categories |
| `completion_confirmed` | boolean |

Counters never saturate or reset to fabricate a valid record. At most one
exchange may lack acceptance because the first uncertain/rejected exchange
stops the producer: attempted minus accepted must be exactly zero or one.
Attempted is zero iff last attempted action is `none`; accepted is zero iff last
accepted action is `none`. When attempted equals accepted and is positive, last
attempted and last accepted categories must be equal.
`not_entered` requires all defaults; setup stages require no room observations
or actions. `complete` and `completion_confirmed=true` imply each other and
require at least one accepted receipt, equal counts and last status `complete`.
The last ready kind survives waiting; it is not an assertion about the current
hidden room. A later validated wrong-kind ready decision may update that fact
before the existing mismatch rejection; no identity is retained.

`last_observation_status` refers only to the last successfully parsed room
body, not a failed/current request. `stage` always describes the latest host
operation, not an inferred game transition. Thus `room_waiting` plus last
accepted action `rest_proceed` differs from `post_action` with the same action:
the latter has not yet observed waiting after that accepted receipt.

No raw body, body hash, request ID, decision/action/control ID, ordinal, stable
content ID, candidate text, credential, profile/save value, player scalar,
timestamp, duration, poll count, per-action list or transition history enters
this object or output. No file writes or live corpus are added. Only bounded
primitive values cross the private instrumentation seam.

## Instrumentation and failure behavior

New `RoomStageDiagnostics` lives in `room_stage_diagnostics.py`.
It stores the fixed primitive record and exposes explicit validated methods.
Add optional keyword-only `diagnostics=None` to `_run_apply_room` and optional
keyword-only `room_diagnostics=None` to `_run_bounded_run` and `_operation`.
The unchanged public `run.operation()` continues to call `_operation()`.
Only the new CLI passes the diagnostic. When absent, the runner does not pass
a new keyword to substituted room callbacks, preserving their old signatures.

Instrumentation order:

1. After the existing deadline is created, mark entry/context validation inside
   the credential-cleanup try/finally.
2. Immediately before health and manifest requests, set their read stage.
3. Before every room GET, set `room_read`. After its body returns and before
   parsing, set `room_validation`. Copy only validated status and ready kind.
4. A validated waiting response sets `room_waiting` before the existing sleep.
   Other statuses retain `room_validation` during existing semantic checks.
5. Immediately before the existing room action exchange, set `action_exchange`,
   increment the attempt count and record only the mapped action category.
   This is an entered exchange attempt, not a delivery or mutation claim.
6. After the body returns, set `action_receipt`; increment accepted count and
   copy the attempted category only after `_validate_action_response` succeeds,
   then set `post_action`. Do not parse or relax receipts independently.
7. Mark `complete` only after the existing nonempty-action and exact same-room
   completion checks pass. Do not infer completion from a receipt or map.

No new time read, sleep or transport operation is introduced by the diagnostic.
Default result dictionaries and all existing checks retain their order. A
failure inside diagnostic instrumentation stops the opt-in execution; it never
retries the affected operation or resumes without diagnostics.

The CLI uses the existing finite production-code allowlist, without echoing
unknown exception codes/text or coercing user-defined values. Known failures
retain their allowed exit code; cancellation is fixed `interrupted`/exit 5;
unknown exceptions/state failures are `internal_failure`/exit 5. A ToolFailure
passes through only when its code is an exact string in the existing frozen
production allowlist and its exit code is an exact integer in 2, 3, 4 or 5,
as in the existing acceptance wrapper; every other code/exit pair becomes
`internal_failure`/exit 5 without echoing or coercing the unknown value.
A failed diagnostic-state validation emits `room=null`, never false zero counts.

Suppress incidental nested stdout/stderr during execution with a non-retaining
sink and restore streams before the one final emission. No unbounded StringIO
or transcript logging is permitted in production. Validate every emitted enum,
exact primitive type, count bound and cross-field relationship. On success,
validate the run aggregate before publishing anything. Reuse the existing
mutable-result cleanup helper. If diagnostic-state validation or result cleanup
cannot be confirmed, it supersedes every outcome (including a primary failure
or cancellation): emit failed/`internal_failure`/exit 5, `room=null` and
`run_acceptance=null`. Preserve credential/socket/buffer cleanup, cancellation
stops and no-retry behavior.

## Ownership and gates

| Task | Exclusive writes | Dependency |
| --- | --- | --- |
| `RD-IMPLEMENT` | `apply_room_live.py`, `apply_run_live.py`, new `room_stage_diagnostics.py`, new `diagnose_run_room_live.py`, new `room_stage_diagnostics_fixtures.py`, new `tests/backends/live/test_room_stage_diagnostics_fixtures.py` | exact contract accepted |
| `RD-GATE` | new `diagnose_run_room_wire_fixtures.py`, new `tests/backends/live/test_diagnose_run_room_wire_fixtures.py` | frozen contract; final run on accepted producer |
| `RD-REVIEW` | none | contract and final joined implementation |
| Coordinator | this plan, actor-ready ledger, current status, bridge README, DECISIONS, ROADMAP; all integration and any live operation | reviews and passing gates |

All tool paths above are under `bridge/Sts2AgentBridge/tools` unless specified.
Use Sol/high for implementation and independent review, a shared checkout with
exclusive ownership, and focused local commits after review. Do not redispatch
completed actor/headless packets. No worker performs live, profile/save,
operator-credential, installation, Cloud or remote Git operations.

Require exact-output/default-parity tests, literal-request actual-client
coverage, count/category/state integrity, cancellation/exception/canary cases,
no extra request after failure, socket and mutable-buffer cleanup, and positive
strict accepted aggregate cases with and without a room. Exercise zero-action
waiting, accepted heal/Proceed/event waiting, setup deadline, failed receipts,
transport, replay/context/completion mismatch, and real composed propagation.
Use meaningful synthetic mutations to prove the independent gate detects bad
attempt/accept accounting and leaked output. Neither mocked ToolFailure nor
C# presampled booleans count as host production-timeout coverage.

Run the new gates, existing timeout/room/run/entry/elite/transport/acceptance gates,
focused live/differential tests, syntax compilation and the full repository
suite. Verify imports resolve from the integration checkout. Evidence remains
`bridge_fixture` until a bounded actual-game observation passes.

## Coordinator live gate

After independent implementation review and aggregate tests pass, one fresh
campaign may use the new diagnostic CLI under the renewed authority. Retain
only this separate fixed diagnostic aggregate and, on success, its validated
existing acceptance summary. This does not authorize a retained live corpus.

Keep Profile 3 only, pinned unchanged bridge, 30 minutes total including cleanup,
at most three selected destinations, and first-legal/first-card/elite/safe
providers with explicit fresh map entry. Do not resume the previous uncertain
run or retry its action. Use supported UI and the existing campaign manager,
fresh stopped/base/package gates, exact quarantine, clean unmodded launch/quit
and purge. Stop on uncertainty, unexpected enabled/syncing Cloud, wrong profile,
crash, or cleanup ambiguity. No Cloud change or idle-marker wait.

The user supplied `steam://rungameid/2868840` as the requested browser launch
route. The handoff's recorded browser-policy rejection is not bypassed through
another browser, shell, raw command or indirect route. If supported launch is
blocked, finish repository work and report the concrete infrastructure blocker.
Steam capture remains a separate `-3811` issue; no session change is assumed to
repair it or the controller.
