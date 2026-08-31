# Phase 1 Parallel Execution Plan

- **Status date:** 2026-08-31
- **Planning base:** `R0i`, bridge `0.8.0`, protocol `live_probe_v0`
- **Target build:** Slay the Spire 2 `v0.107.1`, Steam build `23811903`,
  macOS arm64
- **Intended workers:** separate non-ultra coding agents in isolated worktrees
- **Maximum active implementers per batch:** three, leaving one coordinator for
  review and integration

This document turns the current Phase 1 priority into bounded work packets that
can be delegated without asking each worker to rediscover the architecture. It
is an execution plan, not a new long-term roadmap and not authorization for a
live installation, game launch, profile access, or credential access.

## 1. Executive decision

Parallel work will proceed on two levels:

1. finish and stabilize the already implemented `R0i` bridge slice; and
2. prepare, then implement, a narrow Python host adapter around the accepted
   `R0i` public contract.

The Python work is deliberately staged. Before the next live acceptance, an
agent may audit existing payloads and the legacy `CombatEnv`, but may not invent
the Phase 2 universal `GameBackend`, full `RunState`, snapshot service, or
full-run rules. After the existing bridge slice is repeatable and its narrow
adapter contract is accepted, agents may build a strict parser, fixture
playback environment, public trajectory recorder, and clearly labelled
`combat_v0` adapter in parallel.

This gets useful Python work moving early without freezing speculative full-game
semantics before the live evidence exists.

## 2. Audited starting point

The current repository and live evidence establish:

- authenticated, pinned-build public reads at menu, Settings, combat, reward,
  map, and supported room boundaries;
- snapshot-bound combat, reward, map, and room actions through separate host
  clients;
- live complete-combat, reward, map, and one composed combat-to-next-room floor
  transition;
- fixture coverage for a bounded rest-site client, safe standard-event client,
  and a batched combat/reward/map runner capped at three completed combats; and
- a generic `decision_response_mismatch` observed once in a batched live run.

The source audit also found three facts that affect the work graph:

1. `decision_response_mismatch` is emitted by
   `probe_live.py::_validate_combat` when strict combat JSON validation fails.
   The evidence does not yet prove a race, timing issue, or stale-decision root
   cause.
2. `apply_run_live.py` currently calls combat, reward, and map clients only. It
   continues only when the selected destination is `monster`; it does not call
   `apply_room_live.py` for `rest_site` or `ancient` destinations.
3. `apply_map_live.py` is the only granular live mutation client without its
   own disposable socket-level fixture suite.

Those gaps are the immediate critical path. Shops, potions, broad events,
models, search, training, a complete run, and a general simulator remain out of
scope for the packets below.

## 3. Worker and integration rules

Every delegated worker must:

- read `AGENTS.md`, `docs/MULTI_AGENT_EXECUTION.md`, this document, the task's
  listed inputs, and the relevant production files before editing;
- start from the exact integration commit supplied by the coordinator in an
  isolated worktree and a `codex/` branch;
- edit only its owned files;
- treat every dependency outside those files as read-only;
- avoid broad formatting, public exports, dependency changes, and edits to
  `AGENTS.md`, `DECISIONS.md`, `ROADMAP.md`, `README.md`, or living status docs;
- run only repository-local, install-free tests unless the task explicitly
  says otherwise;
- never access the real operator configuration, credential, profile, save,
  Steam Cloud state, or game installation as an operational target;
- never install the bridge, launch the game, or conduct a live probe;
- make one clean logical commit; and
- return the handoff record in Section 8.

If an owned-file boundary proves insufficient, the worker must stop and report
the needed semantic or file change. It must not silently expand ownership.

The coordinator alone owns:

- accepted contract revisions and fingerprints;
- shared exports and package manifests;
- high-contention documentation;
- cross-packet conflict resolution;
- aggregate validation and claim wording; and
- any separately approved live campaign.

## 4. Dependency and batch schedule

The batches are ordered to keep all three worker slots useful while preventing
consumers from coding against an unaccepted contract.

| Batch | Worker 1 | Worker 2 | Worker 3 | Gate before next batch |
| --- | --- | --- | --- | --- |
| A — current bridge critical path | `R0I-DIAG-01` | `R0I-MAP-02` | `R0I-RUN-03` | Focused review; rebase; complete bridge fixture matrix |
| B — pre-live closure and readiness | `R0I-RUN-04` | `R0I-ROUTE-05` | `R0I-HOST-AUDIT-01` | Build/package/verifier gates; documentation correction; exact live candidate |
| Live gate — sequential | Coordinator and user only | — | — | New explicit approval; bounded campaign; teardown and clean-base check |
| Evidence prep — non-blocking for live | `R0I-VECTORS-06` | independent bridge review | spare for a live blocker | Golden vectors ready for the host contract |
| Contract gate — one owner | `R0I-HOST-CONTRACT-01` | read-only reviewers only | — | Coordinator marks one exact revision accepted for the slice |
| C — host foundations | `R0I-HOST-PARSER-01` | `R0I-HOST-REVIEW-01` | spare for bridge blocker only | Parser accepted and contract review clean |
| D — Python components | `R0I-HOST-FIXTURE-02` | `R0I-HOST-TRACE-03` | `R0I-HOST-COMBAT-04` | Each focused suite passes on the same contract revision |
| E — consolidation | `R0I-HOST-CONFORMANCE-01` | independent bridge review | coordinator | Aggregate regression and accurate capability/status update |

Hard dependencies:

- `R0I-RUN-03` uses the current room-client callable interface as a frozen
  fixture dependency. It must not require a parallel change to that interface.
- `R0I-RUN-04`, `R0I-ROUTE-05`, and the integrated results of Batch A are hard
  dependencies of the live gate.
- `R0I-VECTORS-06` is not a live-campaign dependency. It may begin after Batch A
  and finish while the live gate is being prepared or exercised, but it is a
  hard input to `R0I-HOST-CONTRACT-01`.
- the live gate and `R0I-HOST-AUDIT-01` are hard inputs to
  `R0I-HOST-CONTRACT-01`.
- no Python contract consumer may start before the coordinator accepts the
  exact `R0I-HOST-CONTRACT-01` revision.
- `R0I-HOST-FIXTURE-02`, `R0I-HOST-TRACE-03`, and `R0I-HOST-COMBAT-04`
  depend on the accepted output of `R0I-HOST-PARSER-01`.
- `R0I-HOST-CONFORMANCE-01` depends on all three Batch D implementations.

If the live campaign finds a contract-shape defect, the host batches pause. The
contract owner publishes a new proposed revision; consumers never adapt by
guessing.

## 5. Batch A: current bridge critical path

### `R0I-DIAG-01` — Classify the combat decision mismatch safely

- **Outcome:** Replace the single opaque combat-decision validation failure
  with a small fixed taxonomy that identifies which public structural section
  failed, while preserving accepted payload semantics and never exposing raw
  response content.
- **Context:** The observed `decision_response_mismatch` comes from strict
  validation in `probe_live.py::_validate_combat`. It is not evidence by itself
  of a controller race. A later live recurrence must be diagnosable without
  retaining a response body.
- **Inputs:** `docs/PHASE_1_CURRENT_STATUS.md`, `live_probe_v0`,
  `probe_live.py`, `probe_live_fixtures.py`, canonical combat encoder tests.
- **Dependency:** none.
- **In scope:** Split or annotate validation into fixed categories such as
  envelope/identity, player, enemies, hand, legal actions, and provider result;
  add one minimized synthetic failure fixture per category; retain strict
  duplicate-key and unknown-field rejection.
- **Out of scope:** Polling or retry policy, endpoint/schema changes, C# source,
  raw-body logging, hashes of raw live bodies, timing changes, and claiming the
  original failure is fixed.
- **Owned files:**
  `bridge/Sts2AgentBridge/tools/probe_live.py` and
  `bridge/Sts2AgentBridge/tools/probe_live_fixtures.py`.
- **Read-only dependencies:** every other bridge source, tool, fixture, and
  document.
- **Contract version:** existing `live_probe_v0`, schema version `1`; accepted
  inputs and outputs are unchanged, only sanitized local failure classification
  may change.
- **Acceptance evidence:** the focused fixture suite passes; all previously
  valid combat fixtures still normalize identically; every added invalid
  fixture reaches exactly one fixed category; a test proves error output
  contains no raw body, token, correlation ID, path, card text, or enemy text.
- **Required docs:** none; the coordinator records the final taxonomy after
  integration.
- **Risk:** high, because this validator guards a live mutation client.
- **Blockers/approval:** offline fixtures only; no live approval is implied.
- **Handoff:** commit hash, category table, old-to-new compatibility note, exact
  commands and results, and any unclassified case.

### `R0I-MAP-02` — Add map-client fixture parity

- **Outcome:** Give `apply_map_live.py` a disposable socket-level fixture suite
  comparable to combat, reward, and room clients, fixing only defects exposed
  by that suite.
- **Context:** Map selection is part of every composed route but currently lacks
  a dedicated client fixture file.
- **Inputs:** current map client, room/reward socket-fixture patterns, map reader
  and encoder tests, `live_probe_v0` map routes.
- **Dependency:** none.
- **In scope:** Ready/waiting/unsupported/complete payloads; exact request
  canonicalization; accepted and known rejected receipts; stale/already-applied
  reconciliation; destination mismatch; malformed candidate/action rejection;
  invocation validation; credential and socket cleanup.
- **Out of scope:** Provider priorities, new map kinds, new routes, C# behavior,
  live execution, or a general HTTP test framework.
- **Owned files:**
  `bridge/Sts2AgentBridge/tools/apply_map_live.py` and new
  `bridge/Sts2AgentBridge/tools/apply_map_live_fixtures.py`.
- **Read-only dependencies:** `probe_live.py`, `decision_providers.py`,
  `tool_common.py`, `PinnedPublicMapDecisionReader.cs`, and encoder tests.
- **Contract version:** existing `live_probe_v0` map decision/action schema
  version `1`.
- **Acceptance evidence:** the new suite runs entirely in memory and covers all
  named cases; existing bridge tests remain green; any production fix is paired
  with a fixture that failed before it.
- **Required docs:** none; the coordinator adds the fixture command after merge.
- **Risk:** medium-high because the production client can submit a live action,
  though this packet performs no live operation.
- **Blockers/approval:** no live approval; stop if a C# or protocol change is
  required.
- **Handoff:** commit hash, check list/count, exact command/result, production
  defect if any, and unsupported cases.

### `R0I-RUN-03` — Add one safe room handoff to the bounded runner

- **Outcome:** Make the batched runner invoke the existing safe room client for
  one supported rest-site or standard-event destination, verify the room
  result, wait for the next map, and then stop at an explicit successful
  boundary.
- **Context:** The current runner stops at every non-`monster` destination. The
  room client exists and is fixture-tested but is not composed into the run.
- **Inputs:** current combat/reward/map/room clients and their result contracts;
  existing run fixtures; `live_probe_v0` process/action caps.
- **Dependency:** fixture dependency on the current
  `apply_room_live._run_apply_room` signature and result shape. That interface
  is frozen for this packet.
- **In scope:** Add an explicit `safe` room-provider argument; after one map
  action, route `rest_site` to a verified rest screen and treat `ancient` only
  as a hint that must be confirmed by a successful room result whose
  `screen_kind` is `event`; invoke the frozen room client; wait for the next
  public map; return a bounded `supported_room_complete_map_ready` termination;
  preserve the existing ordinary-`monster` behavior and limits. Add synthetic
  rest, event, destination/screen mismatch, unsupported-room, and existing
  monster/terminal cases.
- **Out of scope:** Changing room semantics, custom/dangerous events, shops,
  treasure, elite/boss support, full route planning, new C# behavior, new
  endpoints, or live execution.
- **Owned files:**
  `bridge/Sts2AgentBridge/tools/apply_run_live.py` and
  `bridge/Sts2AgentBridge/tools/apply_run_live_fixtures.py`.
- **Read-only dependencies:** all granular live clients and fixtures,
  `decision_providers.py`, bridge public models, and encoder tests.
- **Contract version:** `live_probe_v0`; additive room component and termination
  reason in the local `r0i_bounded_run` result, plus the room-provider CLI
  argument. The worker documents the exact delta in its handoff rather than
  editing shared docs.
- **Acceptance evidence:** in-memory transcripts prove: unchanged monster-only
  behavior; rest heal/proceed to a verified map-ready stop; safe event to a
  verified map-ready stop; destination/screen mismatch rejection;
  unsupported/dangerous fail-stop; credential zeroing; and no calls after a
  terminal or map-ready stop.
- **Required docs:** none; coordinator updates bridge README/status after merge.
- **Risk:** high because this composes several mutation clients and changes a
  CLI/result shape.
- **Blockers/approval:** no live approval. If correct composition requires a
  room-interface or wire-contract change, stop and return that blocker.
- **Handoff:** commit hash, old/new CLI and result schemas, supported transition
  table, fixture transcripts/checks, exact results, and remaining live gate.

## 6. Batch B: pre-live closure and Phase 2 readiness

### `R0I-RUN-04` — Continue from one completed room to the next combat

- **Outcome:** Extend the accepted one-room handoff so a bounded run can select
  one further map destination and resume the next ordinary combat in the same
  controller invocation.
- **Context:** `R0I-RUN-03` proves room composition without also redesigning the
  whole travel loop. This follow-on adds only the continuation needed for the
  next multi-combat live milestone.
- **Inputs:** integrated `R0I-RUN-03`, map client, next-combat waiter, and their
  fixture result shapes.
- **Dependency:** hard dependency on the accepted `R0I-RUN-03` result/CLI delta.
- **In scope:** From `supported_room_complete_map_ready`, perform exactly one
  additional advertised map selection; continue only when its destination is
  `monster`; wait for a new combat decision; resume the existing floor loop;
  record the second map action without losing the room record; propagate
  existing process/action limits; fail closed on another room or any unsupported
  destination.
- **Out of scope:** Arbitrary multi-room traversal, recursive routing, shops,
  treasure, elite/boss support, new room semantics, C# changes, full-map
  planning, or live execution.
- **Owned files:**
  `bridge/Sts2AgentBridge/tools/apply_run_live.py` and
  `bridge/Sts2AgentBridge/tools/apply_run_live_fixtures.py` after the Batch A
  owner has finished and its commit is integrated.
- **Read-only dependencies:** all granular clients/providers and bridge public
  models.
- **Contract version:** accepted local `r0i_bounded_run` revision from
  `R0I-RUN-03`; additive representation of the second map transition only.
- **Acceptance evidence:** fixtures prove rest-to-map-to-monster and
  event-to-map-to-monster continuation, next-combat readiness, unchanged
  monster-only behavior, second-room fail-stop, unsupported-destination
  fail-stop, cap propagation, credential cleanup, and no post-terminal calls.
- **Required docs:** none; coordinator updates shared docs after integration.
- **Risk:** high because it resumes mutation after a composed room boundary.
- **Blockers/approval:** offline fixtures only. Stop if a generalized travel
  state machine or wire change is required.
- **Handoff:** commit hash, exact delta from `R0I-RUN-03`, transition matrix,
  fixtures/results, and remaining unsupported routes.

### `R0I-ROUTE-05` — Make the coverage provider target supported rooms

- **Outcome:** Make the existing `coverage` map provider deterministically
  prefer the already supported room slice, then ordinary combat, while leaving
  `first` and `combat` unchanged.
- **Context:** `coverage` currently prioritizes `rest_site`, then `unknown`, and
  does not prioritize `ancient`. That makes a safe standard-event live sample
  less reproducible and may select an unsupported unknown node before combat.
- **Inputs:** current map-provider implementation and fixtures; integrated
  `R0I-RUN-03` transition table; the frozen destination matrix stated in the
  `R0I-RUN-04` brief.
- **Dependency:** hard dependency on accepted Batch A runner semantics and an
  advisory dependency on `R0I-RUN-04`; they may run in parallel because their
  owned files are disjoint.
- **In scope:** A deterministic priority order for `rest_site`, `ancient`, then
  `monster`; stable row/column/index/action tie-breaking; advertised-action
  alignment; explicit fallback behavior. `ancient` is only a routing hint—the
  room reader must still prove `screen_kind == event` or fail closed.
- **Out of scope:** New providers, learned routing, global map planning, shops,
  elites, bosses, or treating every ancient/custom event as safe.
- **Owned files:**
  `bridge/Sts2AgentBridge/tools/decision_providers.py` and
  `bridge/Sts2AgentBridge/tools/decision_providers_fixtures.py`.
- **Read-only dependencies:** map/run/room clients and public readers.
- **Contract version:** existing host provider contract; behavior change is
  limited to `coverage` ranking.
- **Acceptance evidence:** fixtures prove priorities, stable tie-breaks,
  advertised legality, absence fallbacks, and unchanged `first`/`combat` output.
- **Required docs:** none; coordinator records the final priority table.
- **Risk:** medium because it changes which live destination would be selected.
- **Blockers/approval:** fixtures only; the change cannot be exercised live
  without a later exact campaign approval.
- **Handoff:** commit hash, old/new priority table, fixtures and results.

### `R0I-HOST-AUDIT-01` — Audit the narrow host contract before coding it

- **Outcome:** Produce one consolidation-ready report defining what the Python
  host can safely implement from current evidence and what must remain absent.
- **Context:** We want Python development in parallel, but the universal Phase 2
  backend must not be guessed from an incomplete live slice.
- **Inputs:** `DECISIONS.md` entries D37 and D43;
  `docs/LONG_TERM_ARCHITECTURE_ROADMAP.md` Phase 1/2 gates; current bridge
  public models, clients, fixtures, and vectors; `CombatEnv` structured
  observation, actions, seeding, and serialization behavior.
- **Dependency:** advisory dependency on Batch A findings; it is otherwise
  read-only and can run alongside Batch B.
- **In scope:** Inventory exact wire fields/statuses/actions/receipts; distinguish
  policy-visible values from control tokens and audit metadata; map shared and
  missing semantics between live R0i and `combat_v0`; propose the smallest
  provisional adapter surface; list trajectory fields supported by actual
  evidence; identify reset/snapshot/run-ID/entity-ID capabilities that do not
  exist yet.
- **Out of scope:** Editing any file; implementing schemas, parser, environment,
  recorder, simulator rules, training, model, or search; claiming live/simulator
  parity.
- **Owned files:** none. The result is the agent handoff only.
- **Read-only dependencies:** entire repository.
- **Contract version:** proposed `r0i_slice_v1`; it has no accepted status from
  this audit.
- **Acceptance evidence:** report contains a four-decision capability matrix,
  policy/control/audit field partition, live-to-combat-v0 mismatch table,
  candidate-lifetime rules, missing-capability list, and explicit recommended
  contract/non-contract boundary with source references.
- **Required docs:** none.
- **Risk:** medium; overclaiming here would contaminate later data and APIs.
- **Blockers/approval:** read-only; no live access. Mark uncertain findings as
  unknown rather than resolving them by assumption.
- **Handoff:** the exact report described above, concise open questions, and a
  recommended accept/reject disposition for `r0i_slice_v1`.

## 7. Sequential gates and post-live Python packets

### Live gate — one consolidated R0i campaign

The live gate is not a background-agent task. After Batches A and B are merged,
the coordinator must build, test, package, and independently review one exact
artifact, then present one bounded campaign request to the user.

The campaign should attempt:

- a repeatable multi-combat sequence under the bounded runner;
- a rest-site and safe standard-event transition only if the run offers them;
- sanitized mismatch classification if a decision fails;
- normal game exit, bridge quarantine/removal, clean base-game relaunch, and
  final cleanup with Cloud idle.

If a room is not encountered, record it as not observed—not passed or failed.
No raw public response logging is enabled by default. A successful campaign
establishes evidence for this slice only; it does not complete Phase 1.

### `R0I-VECTORS-06` — Bind current public decisions to golden vectors

- **Outcome:** Extend the existing `live_probe_v0` golden-vector set beyond
  health/manifest/screen responses to the already implemented public combat,
  reward, map, and room decision bodies.
- **Context:** Exact C# encoder tests exist, but the checked-in protocol-vector
  directory does not yet cover the R0i decision surface needed by a strict
  Python adapter. This work is useful contract preparation, not a prerequisite
  for the next live campaign.
- **Inputs:** current C# public models, canonical encoder, contract tests, and
  existing vector conventions.
- **Dependency:** hard dependency on the integrated Batch A wire behavior for
  contract use, but advisory and non-blocking for the live campaign;
  independent of route-provider policy.
- **In scope:** Canonical public decision `.json` vectors for all four decision
  families across ready/waiting/unsupported/complete where valid, with tests
  binding exact encoder body bytes to those files. Reuse identical inactive
  bodies rather than inventing variants.
- **Out of scope:** Action-receipt vectors, `.http` expansion, new
  fields/statuses/routes, normalization into a universal domain model, Python
  code, live data, or unredacted captured payloads.
- **Owned files:** new R0i files under
  `bridge/Sts2AgentBridge/contracts/live_probe_v0/vectors/` and
  `bridge/Sts2AgentBridge/tests/Sts2AgentBridge.Tests/Contract/ContractArtifactBindingTestSuite.cs`.
- **Read-only dependencies:** all production C# source and existing tests.
- **Contract version:** exact existing `live_probe_v0`, schema version `1`.
- **Acceptance evidence:** byte-for-byte encoder/vector equality; all bridge
  tests pass; vector inventory and hashes are reported.
- **Required docs:** none; coordinator records the inventory after integration.
- **Risk:** medium; vector mistakes can become false contract authority.
- **Blockers/approval:** synthetic public data only; no live capture.
- **Handoff:** commit hash, vector inventory/hashes, exact tests/results, and any
  source shape that could not be represented without a protocol change.

### `R0I-HOST-CONTRACT-01` — Freeze the provisional `r0i_slice_v1` host contract

- **Outcome:** One owner turns accepted live/fixture evidence into a narrow,
  versioned interoperability packet for the Python host.
- **Context:** This is an adapter contract over `live_probe_v0`, not the final
  Phase 2 universal `GameBackend`.
- **Inputs:** integrated golden vectors, `R0I-HOST-AUDIT-01`, sanitized live
  result, and all R0i public models.
- **Dependency:** hard dependency on the live gate or an explicit coordinator
  decision that the missing live observation is non-blocking for a
  fixture-labelled contract.
- **In scope:** Exact combat/reward/map/room decision shapes; ready/waiting/
  unsupported/complete states; currently advertised action grammars; receipt
  correlation; decision-scoped token lifetime; capability claims; strict public
  information boundary; canonical synthetic fixtures.
- **Out of scope:** General reset/snapshot/restore, run IDs, durable entity IDs,
  idempotency keys not present on the wire, full trajectory semantics, shops,
  potions, full-run rules, models, or search.
- **Owned files:** new `contracts/r0i_slice_v1/**` and new focused artifact tests
  under `tests/contracts/`. No other file.
- **Read-only dependencies:** bridge vectors/source, decisions, roadmaps, and
  sanitized live evidence.
- **Contract version:** proposed `r0i_slice_v1`; only the coordinator may change
  its lifecycle marker to `accepted_for_slice` after review.
- **Acceptance evidence:** fixtures cover every supported/inactive decision
  state and action receipt; artifacts round-trip and fingerprint stably; unknown
  fields fail; the capability matrix says shape/legality conformance only.
- **Required docs:** only the contract-local README; shared docs remain
  coordinator-owned.
- **Risk:** high because all host consumers depend on it.
- **Blockers/approval:** one writer only; any new bridge field requires a new
  proposed contract revision, not an implicit edit.
- **Handoff:** commit hash, contract fingerprint, fixture hashes, capability
  matrix, compatibility statement, and unresolved evidence gaps.

### `R0I-HOST-PARSER-01` — Implement the strict Python bridge reader

- **Outcome:** Parse the accepted R0i payloads into typed, public-only Python
  objects while keeping policy input separate from control and audit data.
- **Context:** This is the first executable Python host seam. It consumes the
  accepted adapter contract and does not alter `CombatEnv`.
- **Inputs:** accepted `r0i_slice_v1` and bridge golden vectors.
- **Dependency:** hard dependency on the exact accepted contract fingerprint.
- **In scope:** Strict models/parser; duplicate and unknown-key rejection;
  phase/status invariants; advertised-candidate validation; receipt/request
  correlation; separate `policy_view`, `control_token`, and `audit_metadata`.
- **Out of scope:** Network access, live client, environment loop, simulator
  rules, exports from `game/__init__.py`, dependency additions, model/search.
- **Owned files:** new `game/backends/r0i/__init__.py`, `models.py`, and
  `bridge_payload.py`; new focused tests under `tests/backends/r0i/`.
- **Read-only dependencies:** contract artifacts and bridge vectors.
- **Contract version:** one exact accepted `r0i_slice_v1` fingerprint.
- **Acceptance evidence:** every canonical fixture parses; malformed, duplicate,
  unknown, inconsistent, stale, and mismatched-receipt fixtures fail; serialized
  normalized data is stable; leakage tests keep decision IDs/hashes/receipts out
  of `policy_view`.
- **Required docs:** none.
- **Risk:** high; permissive parsing would silently corrupt data.
- **Blockers/approval:** no contract edits; stop if an accepted fixture is
  ambiguous.
- **Handoff:** commit hash, parsed type inventory, exact fingerprint, tests and
  results, rejected-case matrix, and limitations.

### `R0I-HOST-REVIEW-01` — Independently review the accepted host boundary

- **Outcome:** An independent reviewer verifies contract completeness,
  candidate lifetime, receipt semantics, and public-information separation.
- **Context:** The contract owner and parser implementer must not be the only
  judges of their shared assumptions.
- **Inputs:** accepted contract and bridge vectors/source. Parser-specific
  conformance is covered later by `R0I-HOST-CONFORMANCE-01`.
- **Dependency:** hard dependency on the accepted contract fingerprint; it may
  run in parallel with `R0I-HOST-PARSER-01`.
- **In scope:** Read-only semantic review plus adversarial test recommendations;
  verify all four decision families, inactive states, receipt correlation,
  queued combat re-observation, capability wording, and that the proposed
  adversarial test matrix is sufficient for the parser implementer.
- **Out of scope:** Production edits, expanding the contract, or accepting it on
  behalf of the coordinator.
- **Owned files:** none; handoff report only.
- **Read-only dependencies:** relevant repository and task branches.
- **Contract version:** exact accepted `r0i_slice_v1` fingerprint.
- **Acceptance evidence:** pass/fail checklist with file/fixture references and
  minimized counterexamples for every failure.
- **Required docs:** none.
- **Risk:** low operational risk, high claim-integrity importance.
- **Blockers/approval:** read-only.
- **Handoff:** verdict, blocking findings, non-blocking findings, and exact
  evidence inspected.

### `R0I-HOST-FIXTURE-02` — Build a fixture-playback Python environment

- **Outcome:** Provide a deterministic environment loop over accepted canonical
  R0i fixture sequences so host policies and controllers can be tested without
  launching the game.
- **Context:** This accelerates host development but is not a simulator and
  cannot generate counterfactual game states.
- **Inputs:** `R0I-HOST-PARSER-01` normalized types and accepted fixtures.
- **Dependency:** hard dependency on the accepted parser implementation.
- **In scope:** Reset to a named fixture sequence; observe current decision;
  apply only an advertised action; reject stale/unadvertised actions; advance to
  the recorded next decision/receipt; deterministic replay; honest capability
  manifest.
- **Out of scope:** Synthesizing outcomes, rules, RNG, snapshots outside fixture
  replay, network/live access, Gym compatibility, training reward, or parity
  claims.
- **Owned files:** new `game/backends/r0i/fixture_backend.py` and focused tests.
- **Read-only dependencies:** accepted contract/parser/fixtures.
- **Contract version:** exact accepted `r0i_slice_v1` fingerprint.
- **Acceptance evidence:** all canonical sequences replay; stale and illegal
  choices reject; queued combat receipt requires a later observation; manifest
  advertises `fixture_playback=true`, `live_truth=false`,
  `counterfactual=false`, and `snapshot_restore=false` unless replay cursor
  restoration is explicitly distinguished.
- **Required docs:** none.
- **Risk:** medium; the main risk is callers mistaking playback for simulation.
- **Blockers/approval:** no live work.
- **Handoff:** commit hash, supported sequences/capabilities, tests/results, and
  anti-parity wording.

### `R0I-HOST-TRACE-03` — Build the public trajectory recorder

- **Outcome:** Record normalized observation/action/re-observation boundaries
  from fixtures in a public trajectory, with operational receipt/correlation
  data in a physically separate audit sidecar.
- **Context:** Phase 1 needs auditable trajectory evidence, while the canonical
  long-term recorder remains a later Phase 2 deliverable.
- **Inputs:** accepted normalized types and contract fixtures.
- **Dependency:** hard dependency on `R0I-HOST-PARSER-01`.
- **In scope:** Two deterministic, physically separate outputs. The public JSONL
  contains local monotonic sequence, fixture provenance, contract fingerprint,
  normalized policy view, advertised policy candidate IDs, chosen policy
  action, and next-public-observation reference. The non-policy audit sidecar
  contains control-token correlation and receipt details needed to verify the
  fixture transition. Types must prevent audit records from being passed as
  policy views.
- **Out of scope:** Raw payloads or raw-payload hashes, live audit output,
  privileged data, profile/seed data, full event sourcing, dataset sharding,
  replay backend, training targets, or scalar shaped reward.
- **Owned files:** new `game/backends/r0i/trajectory.py` and focused tests.
- **Read-only dependencies:** accepted parser/models/fixtures.
- **Contract version:** exact accepted `r0i_slice_v1` fingerprint.
- **Acceptance evidence:** golden public JSONL and audit-sidecar output; queued
  combat represented in audit as a receipt followed by a later public
  observation rather than a fabricated post-state; stable serialization;
  interrupted-record detection; type and content tests prove the public stream
  contains no decision/control token, receipt, audit hash, or future outcome.
- **Required docs:** none.
- **Risk:** high because early data-format mistakes can poison later datasets.
- **Blockers/approval:** fixture data only in this packet. Writing an audit
  sidecar from live data would require a separately reviewed scope and approval.
- **Handoff:** commit hash, record schema/example, tests/results, privacy audit,
  and explicit non-canonical limitations.

### `R0I-HOST-COMBAT-04` — Adapt legacy `CombatEnv` without changing it

- **Outcome:** Expose the existing `combat_v0` structured observation and legal
  actions through the accepted normalized combat-decision types, clearly
  labelled as simulator-origin fixture behavior.
- **Context:** D37 preserves `CombatEnv` as a legacy adapter instead of expanding
  its fixed vector/action grid into the full-game contract.
- **Inputs:** `R0I-HOST-PARSER-01`, current `CombatEnv`, structured
  observations, action semantics, deterministic factory tests.
- **Dependency:** hard dependency on the accepted normalized types; fixture
  dependency on current simulation tests.
- **In scope:** Public projection from structured combat observations;
  decision-scoped typed candidate IDs; all-and-only current legal-action
  mapping; deterministic named scenario/reset; accepted-action application;
  terminal victory/defeat; explicit capability/semantic caveats.
- **Out of scope:** Editing `game/simulation/**`; using fixed RL encodings as the
  domain contract; persistent full-run IDs; reward/map/room rules; claiming live
  parity; training/model/search changes.
- **Owned files:** new `game/backends/legacy/__init__.py`,
  `combat_v0_adapter.py`, and focused tests under `tests/backends/legacy/`.
- **Read-only dependencies:** all existing simulation and simulation tests,
  accepted host models.
- **Contract version:** `combat_v0` adapter onto the exact accepted
  `r0i_slice_v1` normalized combat subset.
- **Acceptance evidence:** every emitted candidate maps to exactly one legal
  current action; no legal current action is omitted; stale/invalid candidates
  reject; same seed/action history reproduces the same normalized observations;
  the existing simulation suite is unchanged and green.
- **Required docs:** none.
- **Risk:** medium; index-based legacy identities must not escape their decision
  lifetime.
- **Blockers/approval:** no edits to legacy behavior. Stop if the accepted
  normalized contract cannot represent a legal `CombatEnv` action honestly.
- **Handoff:** commit hash, mapping/lifetime table, supported scenarios,
  tests/results, and proof that legacy production files did not change.

### `R0I-HOST-CONFORMANCE-01` — Black-box contract and information-boundary tests

- **Outcome:** Independently demonstrate that the parser, fixture environment,
  recorder, and combat adapter honor their advertised subset of the accepted
  contract.
- **Context:** Implementation-owned unit tests can agree with the same mistaken
  assumption. This packet tests components through public APIs only.
- **Inputs:** integrated Batch D implementations, accepted fixtures/vectors, and
  the contract review.
- **Dependency:** hard dependency on all Batch D tasks.
- **In scope:** Strict-field checks; candidate soundness/completeness; stale
  action behavior; receipt correlation; serialization stability; deterministic
  replay; capability truthfulness; negative leakage tests for control tokens,
  audit hashes, hidden RNG, outcome labels, and future state.
- **Out of scope:** Production fixes, live evidence, performance, training,
  models, search, or generalized backend claims.
- **Owned files:** new focused tests under `tests/conformance/`; no production
  files.
- **Read-only dependencies:** all accepted contract and component paths.
- **Contract version:** exact accepted `r0i_slice_v1` fingerprint.
- **Acceptance evidence:** black-box suite passes; every failure has a minimized
  fixture; report distinguishes shape/legality conformance, fixture replay, and
  live evidence.
- **Required docs:** none; coordinator updates shared docs after acceptance.
- **Risk:** medium, primarily false assurance from incomplete tests.
- **Blockers/approval:** no live work.
- **Handoff:** commit hash, coverage matrix, commands/results, minimized failures,
  and unsupported surface.

The general `GameBackend`, persistent `RunState`, explicit full-game RNG,
snapshot/restore, reward/map/room simulator rules, shops, and full-run backend
are intentionally not delegated by this plan. They become separate Phase 2–4
packets only after the R0i host boundary and fast-backend decision are accepted.

## 8. Required worker handoff

Every worker returns exactly this information:

1. task ID and one-sentence outcome;
2. starting commit and final commit;
3. files changed, confirming no other ownership was touched;
4. contract/fixture fingerprint consumed;
5. behavior or schema delta;
6. commands run and exact pass/fail summary;
7. evidence level: static, fixture, repository, or live;
8. known limitations and unsupported cases;
9. blockers, follow-ups, and whether any assumption needs coordinator approval;
10. merge-order notes.

The worker must not call a task complete merely because code compiles. It must
either provide the requested acceptance evidence or return a precise blocker.

## 9. Consolidation checklist

For each batch, the coordinator will:

- verify the task started from the declared base and stayed within ownership;
- inspect semantic deltas before rebasing or cherry-picking;
- reject duplicate contract definitions or private state in public/policy data;
- merge in dependency order, never by agent completion time;
- run all focused tests, then the complete relevant regression matrix;
- build/package/verify the bridge when bridge source or tooling changes;
- use an independent reviewer for mutation, contract, and information-boundary
  changes;
- update shared documentation once with demonstrated-versus-fixture evidence;
- make clean, logically grouped integration commits; and
- ask once for a new exact live approval only when the offline candidate is
  complete.

Batch completion is not a live or parity claim. The living status page remains
the authority for what has actually been demonstrated.
## 10. Stop conditions

Pause the affected lane and return to the coordinator if:

- a task needs a file owned by another active worker;
- the bridge wire shape must change;
- a fixture contradicts the pinned C# encoder or sanitized live evidence;
- private, profile, save, seed, RNG, or future information would enter a public
  or policy-facing object;
- an unsupported room/action would need to be approximated;
- a Python component would need to claim simulation or live parity it cannot
  demonstrate; or
- any install, launch, credential, profile, Cloud, or live operation appears
  necessary.

These are coordination gates, not invitations for a worker to widen scope.
