# Phase 1 actor-ready and elite-continuation execution plan

The later shop/event functional successor is tracked in the
[room-flow implementation plan](PHASE_1_SHOP_EVENT_IMPLEMENTATION_PLAN.md) and
[acceptance ledger](research/PHASE_1_ROOM_FLOWS_V1_ACCEPTANCE.md).
The actor-ready packet contracts and historical evidence below remain preserved.

- **Date:** 2026-09-04
- **Verified parent baseline:** clean `42a3c4e895851188f7179cbc48dcff6ca5974a93`
  on `codex/phase1-parallel-integration`; the handoff commit containing this
  plan is intended to be fast-forwarded to local `main`.
- **Coordinator:** `gpt-6-astra`, Ultra reasoning.
- **Worker policy:** persistent project worktrees, focused local commits, and
  no Ultra workers.
- **Status:** accepted successor scope for the new coordinator. Start only the
  packets below; this plan does not authorize adjacent game-content, protocol,
  fidelity, or retained-data work.
- **Authority:** implementation is accepted. This document does not itself
  create live-game authority; the new coordinator may execute packet `26` only
  under the explicit bounded Profile 3 authority carried in its opening task.
- **Operating rules:** [multi-agent execution](MULTI_AGENT_EXECUTION.md).
- **Current truth:** [Phase 1 current status](PHASE_1_CURRENT_STATUS.md).
- **Prior increment ledger:**
  [next-increment acceptance](research/PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md).
- **Successor ledger:**
  [actor-ready acceptance](research/PHASE_1_ACTOR_READY_ACCEPTANCE.md).

## 1. Outcome

Advance the two useful boundaries that are no longer blocked by live game
research:

1. Let the existing bounded Python host treat an advertised `elite` map
   destination as combat, using the existing generic combat, reward and map
   clients without changing the C# bridge or wire protocol.
2. Turn the accepted public `PolicyView` and trusted trajectory artifacts into
   a variable-candidate encoding, leakage-safe supervised dataset, candidate
   scorer and tiny deterministic behavior-cloning plumbing smoke.

These lanes are independent. Dispatch ready packets concurrently and release a
dependent as soon as its own dependency is integrated. Do not wait for a whole
wave when one lane can advance.

The result is still a bounded `R0i` bridge substrate and a structurally tested
headless experiment path. It is not a complete run controller, game-fidelity
claim, learned-policy quality claim or near-optimal agent.

## 2. Verified handoff state

At the verified parent baseline:

- the complete repository suite passed **1,052 tests** and the explicit
  phase-entry join passed 21 run fixtures, 11 independent entry-wire checks,
  the established transport/wire gates and 244 focused live-parser/
  differential tests;
- explicit fresh reward entry is live-demonstrated through reward resolution,
  one reconciled map selection and terminal combat defeat with truthful partial
  accounting;
- explicit fresh map entry and a composed room handoff are not live-demonstrated;
  elite continuation is currently rejected host-side as
  `unsupported_destination_kind` and therefore is neither implemented nor
  live-demonstrated;
- `R0I-MAP-LIFECYCLE-18` commit `889cc5e` was rejected and is not integrated;
- no live campaign remains active; the last campaign ended with normal quit,
  exact bridge quarantine, a clean unmodded launch/quit, purge, zero overlay,
  no game process and no bridge listener;
- the verified base projection is 429 files with SHA-256
  `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`; and
- the unchanged reviewed bridge `0.8.0` artifact identities are recorded in the
  [bridge guide](../bridge/Sts2AgentBridge/README.md) and
  [prior acceptance ledger](research/PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md).
  Python host changes do not by themselves justify a new DLL or package
  identity.

The new coordinator must verify its worktree is clean and local `main` contains
the handoff baseline and this plan. Do not fetch, reset, or assume
`origin/main` contains the local planning and integration history.

## 3. Frozen coordinator decisions

These decisions are accepted for this increment and recorded as D52/D53 in
[`DECISIONS.md`](../DECISIONS.md). A worker must stop and return a proposal
rather than changing one.

### 3.1 Elite host semantics

- `elite` is a **combat-like host destination**. After an elite map action is
  accepted and reconciled, the runner waits for a fresh existing combat
  decision and invokes the existing bounded combat client.
- The same combat classification applies after default combat entry, explicit
  reward/map entry, and a supported-room post-room map selection, while each
  path preserves its current termination shape.
- `boss` remains an act boundary. Shop, treasure and every other unrecognized
  destination remain typed unsupported stops. No C# reader/applier, route, DTO,
  vector, protocol or bridge-version change is permitted.
- Existing `r0i_bounded_run` and `r0i_bounded_run_entry` result shapes and
  milestone names remain unchanged. Elite is an additive value already carried
  by `destination_kind`, not a new output schema.
- An elite selection consumes exactly one existing map/destination slot.
  `processed_floor_count <= floor_limit <= 3` remains invariant and every
  accepted component action is counted once.
- For a normal or explicit-prefix pending destination below the cap, elite
  defeat uses the existing terminal-combat result and elite victory enters the
  existing reward readiness and reward client path. If the current reward
  client cannot resolve advertised relic, potion or other content, the runner
  fails closed with its existing typed failure; it does not infer completion,
  skip content, retry or fall back.
- A supported-room post-room elite mirrors the existing post-room monster path:
  it stores `next_combat` inside `room_handoff` and returns immediately after
  that combat with existing `run_defeat` or `room_continuation_complete`
  semantics. It does not add a reward or another map to that special handoff.
- A normal/prefix elite map selection that consumes the final destination slot
  preserves the existing pending-monster behavior and returns
  `floor_limit_reached` before starting that combat. A post-room map is selected
  only when the pre-map count is below the cap; if that selection consumes the
  final slot, its one existing continuation combat still runs before the
  special handoff returns. No cap or counting rule is normalized across these
  intentionally different existing paths in this packet.
- Existing default, explicit-combat, reward-entry, map-entry, ordinary-monster,
  room, event, boss and non-elite unsupported-destination behavior must remain exact.
  D47-D52 replay, context, uncertainty, explicit-entry and no-retry protections remain
  controlling.
- Add one opt-in map provider named `elite`. It ranks advertised `elite` first,
  then `rest_site`, `monster` and `ancient`, followed by all other candidates
  under the existing deterministic row/column/index/action-ID tie-break. The
  existing `first`, `combat` and `coverage` providers remain unchanged.

### 3.2 `headless_encoding_v1`

`H5-ENCODER-04` owns the implementation, but not the meaning, of this new
consumer contract:

- input is exactly one validated `game.contracts.headless_v0.PolicyView`;
- output is a versioned, fingerprinted framework-neutral record containing a
  fixed-width global row, variable entity rows, variable public-event rows,
  one row per advertised candidate, and an out-of-band candidate-ID tuple in
  the same order;
- a collator may pad rows for a batch only when it also emits explicit boolean
  masks. Padding is never a legal entity, event or action;
- booleans use `0/1`; bounded numeric fields use documented contract maxima and
  deterministic finite normalization; finite public enums use frozen one-hot
  registries; public semantic definition IDs use a frozen current-content
  vocabulary plus an explicit unknown bucket;
- public opaque references, decision/candidate IDs, scopes, hashes, run IDs,
  control IDs, backend-private state, target records, audit records and
  hindsight outcomes never become numeric or categorical model features;
- opaque references may be used transiently only to join a candidate to its
  public entity. The resolved public semantic/numeric fields are copied into
  the candidate row; the reference and row ordinal are not emitted;
- ordered public events are represented in separate rows with their public
  kind, phase and payload. Sequence position may be encoded as a bounded
  public-order feature; future events and transition outcomes are unavailable;
- actionable, waiting, terminal and unsupported views are all encodable.
  Non-actionable views have zero candidate rows and an empty candidate-ID
  tuple; and
- valid opaque-reference reallocation and candidate permutation may change
  out-of-band IDs/order, but must leave corresponding numeric rows invariant
  modulo that permutation. `headless_v0` itself is read-only.

The encoder task begins with a read-only schema proposal containing its exact
public dataclasses/functions, ordered global/entity/event/candidate feature
names, categorical registries and unknown buckets, semantic-ID vocabulary,
numeric maxima and formulas, collation tensors/masks/dtypes, dimensions,
candidate mapping, and canonical fingerprint input. The coordinator records an
accepted proposal hash in the successor ledger **before the worker edits or
commits implementation**. The module then exports that accepted version,
schema and fingerprint unchanged. A contract conflict returns to the
coordinator; it is not resolved inside the implementation commit.

### 3.3 Actor-example eligibility and split identity

- Only an `ACTIONABLE` `PolicyReplayRecord` with non-null `chosen_action`
  becomes an actor example. Non-actionable final records and actionable
  no-choice boundaries left by budget/interruption are skipped and counted by
  reason; they never receive a synthetic label. A chosen action that does not
  equal an advertised candidate is rejected by the trusted loader/contract.
- One sample identity is `(trusted experiment manifest SHA-256,
  repetition_index, trajectory_id, trusted trajectory manifest SHA-256,
  policy-record ordinal)`. Duplicate sample identities within a split reject.
- Development and held-out overlap is tested on the canonical episode request
  excluding display `trajectory_id` and repetition index: backend/content/
  rules/contract pins plus `HeadlessRunConfig`. Transition budget, chooser kind
  and policy seed are deliberately excluded because different values can still
  share an identical public trajectory prefix. An equal key across splits
  rejects. Repetitions of one request inside a single declared split remain
  allowed and retain distinct sample identities.
- Actor samples expose the validated `PolicyView`, chosen candidate ID and the
  trusted provenance key only. Target/audit streams, terminal outcome, future
  events, returns and scalar value targets are never loaded into a sample.

## 4. Dependency graph and dispatch

```text
R0I-ELITE-22 -> R0I-ELITE-GATE-23 -> R0I-ELITE-REVIEW-25
      |                                      |
R0I-RUN-ACCEPTANCE-24 -----------------------+-> R0I-ELITE-LIVE-26

H5-ENCODER-04 -> H6-CANDIDATE-POLICY-06 --+
                                                +-> H6-BC-SMOKE-07
H5-DATASET-05 ------------------------------+
```

The initial ready set is `R0I-ELITE-22`, `R0I-RUN-ACCEPTANCE-24`,
`H5-ENCODER-04` and `H5-DATASET-05`. Dispatch as many as actual platform
capacity supports without overlapping file ownership. `R0I-ELITE-GATE-23` and
`H6-CANDIDATE-POLICY-06` start immediately after their own producer is reviewed
and integrated. The bridge lane never waits for the headless lane or vice
versa. `H6-BC-SMOKE-07` is the only serialized headless join.

Read-only reviews may use internal subagents. They do not replace persistent
worktree implementation tasks or independent commits.

## 5. Bridge packets

### R0I-ELITE-22 — Continue through an elite destination

- **Allocation:** `gpt-5.6-sol`, high reasoning.
- **Objective:** implement the frozen host-only elite semantics and opt-in
  elite-first provider with no duplicated transport, parsing or phase client.
- **Exclusive ownership:**
  `bridge/Sts2AgentBridge/tools/apply_run_live.py`,
  `bridge/Sts2AgentBridge/tools/apply_run_live_fixtures.py`,
  `bridge/Sts2AgentBridge/tools/decision_providers.py`, and
  `bridge/Sts2AgentBridge/tools/decision_providers_fixtures.py`.
- **Dependencies:** reviewed integrated phase-entry runner through `42a3c4e`
  and the frozen Section 3.1 contract.
- **Acceptance:** ordinary/default/room records remain exact; elite works after
  ordinary, prefix and post-room maps; normal/prefix victory reaches the
  existing reward/map loop while post-room victory preserves the special
  immediate handoff return; defeat terminates once; boss and non-elite
  unsupported destinations are unchanged; both final-slot behaviors in
  Section 3.1 remain exact; floor/action accounting is exact; no retry,
  fallback or phase scan; new provider ordering and all old provider choices
  are deterministic.
- **Required checks:** provider fixtures, run fixtures, established floor/run/
  entry/room/reward/map fixtures, focused `tests/backends/live` and
  `tests/differential`, compile and diff checks.
- **Forbidden:** every C# file, wire/vector schema, granular client, transport
  helper, package/policy pin, independent gate, headless source and shared doc.

### R0I-ELITE-GATE-23 — Independent actual-client join gate

- **Allocation:** `gpt-5.6-terra`, high reasoning.
- **Objective:** prove elite continuation through literal fake transport using
  actual run and granular-client entry points, without reproducing production
  orchestration.
- **Exclusive ownership:**
  `bridge/Sts2AgentBridge/tools/apply_run_entry_wire_fixtures.py`,
  `tests/backends/live/test_apply_run_entry_wire_fixtures.py`, new
  `bridge/Sts2AgentBridge/tools/apply_run_elite_wire_fixtures.py`, and new
  `tests/backends/live/test_apply_run_elite_wire_fixtures.py`.
- **Dependency:** accepted `R0I-ELITE-22`. Author cases against the frozen
  contract, but execute the final negative/positive gates on the integrated
  producer.
- **Acceptance:** exact map-selection-to-fresh-combat request order for elite;
  victory/reward continuation; defeat; prefix and post-room entry; malformed or
  unsupported reward; stale/rejected/uncertain receipt; cancellation; no later
  POST or retry after ambiguity; all sockets closed and mutable sent/credential
  buffers zeroed; no canary in output. Preserve the existing phase-entry
  negative control against `8212886`. The dedicated elite gate must separately
  load exact `42a3c4e` production and prove it stops at
  `unsupported_destination_kind`, while the integrated source passes the same
  transcript for elite continuation.
- **Required checks:** isolated gate, pytest wrapper, 21-check run fixtures,
  8-check run-wire gate, 29-check transport gate, focused live/differential
  tests, compile and diff checks.
- **Forbidden:** production files, existing component behavior, C#, real I/O,
  identity/config/profile reads, docs and headless files. Return defects to
  `R0I-ELITE-22`.

### R0I-RUN-ACCEPTANCE-24 — Maintained capture-off run summary

- **Allocation:** `gpt-5.6-terra`, high reasoning.
- **Objective:** replace disposable live wrappers with a maintained validator
  that holds the complete run result only in memory and emits a minimal
  sanitized aggregate for both existing run milestones.
- **Exclusive ownership:**
  `bridge/Sts2AgentBridge/tools/verify_room_acceptance.py`,
  `bridge/Sts2AgentBridge/tools/verify_room_acceptance_fixtures.py`, new
  `bridge/Sts2AgentBridge/tools/apply_run_acceptance_live.py`, new
  `bridge/Sts2AgentBridge/tools/apply_run_acceptance_live_fixtures.py`, and new
  `tests/backends/live/test_apply_run_acceptance_live_fixtures.py`.
- **Dependencies:** current default and phase-entry result contracts; it may
  begin independently and must be rerun against accepted `R0I-ELITE-22`.
- **Acceptance:** validate exact top-level schema, floor/prefix/readiness/
  termination relationships, bounds and action-total arithmetic for
  `r0i_bounded_run` and `r0i_bounded_run_entry`; emit only the declared
  acceptance/source milestones, entry phase, processed/completed counts,
  aggregate component action counts,
  termination reason/destination and terminal combat outcome when present;
  reject unknown or internally inconsistent records. Never emit or persist
  nested payloads, identifiers, credentials, arbitrary text or raw hashes.
  Callback/exception output is fixed-code and mutable buffers are cleared.
- **CLI contract:** accept exactly the existing 14/16 `apply_run_live.py`
  arguments and call that module's operation in-process; add no flag or phase
  detection. On success emit exactly `schema_version`, `status`, milestone
  `r0i_bounded_run_acceptance`, `source_milestone`, `entry_phase` (default is
  `combat`), `processed_floor_count` (default derives from the validated map
  action count), `completed_floor_count`, the five existing `action_totals`,
  the exact three-field `termination`, and `terminal_combat_outcome`
  (`victory`, `defeat` or null). Termination reasons use the existing six-value
  allowlist and destination kinds use the existing eight-value map allowlist or
  null. Summary validation failure is exactly
  `run_acceptance_result_mismatch`; existing production failure codes pass
  through without arbitrary exception text.
- **Required checks:** acceptance fixtures, real synthetic outputs from run and
  entry fixtures, malformed/canary cases, relevant live/differential tests,
  compile and diff checks.
- **Forbidden:** controller semantics, transport, C#, wire, package, headless,
  real endpoints, filesystem capture and shared docs.

### R0I-ELITE-REVIEW-25 — High-risk join review

- **Allocation:** `gpt-5.6-sol`, high reasoning, read-only.
- **Scope:** complete diffs and commits for packets `22`, `23` and `24` plus
  integrated tests.
- **Acceptance:** verify frozen host/output/provider semantics, actual-client
  oracle independence, no mutation after uncertainty, exact accounting,
  D47-D52 compatibility, sanitized summary boundaries, unchanged C#/wire/
  artifact pins and a meaningful negative control. Findings return to the
  owning task before live work.

### R0I-ELITE-LIVE-26 — Coordinator-only bounded campaign

Begin only after the bridge join, independent review, focused gates and a full
repository suite pass. This is sequential coordinator work, never a worker
packet.

- Confirm no other live operator/campaign is active, the game is closed, the
  exact base projection and the exact reviewed bridge artifact. Do not alter
  Steam Cloud or wait for an idle marker; if it unexpectedly appears enabled or
  actively syncing, stop live mutation and report it.
- Package/install only through the supported overlay; never modify base-game
  files. Keep raw-response logging and persistent capture disabled.
- Use dedicated Profile 3 only. Cap the campaign at 30 minutes and three
  controller-selected destinations.
- Start at one visibly fresh map and invoke
  `apply_run_acceptance_live.py --combat-provider first-legal
  --reward-provider first-card --map-provider elite --room-provider safe
  --floor-limit 3 --entry-phase map`, with the transient profile path and UID
  supplied through their existing required flags. Perform no manual game action
  after controller entry. If an elite is offered, require selected-map
  reconciliation and a fresh bounded
  elite combat terminal result. If none is offered, map entry may pass while
  elite remains `unobserved`; do not farm runs.
- Continue through a supported rest/ordinary/elite route only while existing
  bounds permit. A safe `ancient` event may be selected only when higher-ranked
  advertised destinations are absent and remains governed by the existing
  fail-closed event controller; it is not a campaign success requirement. A
  post-elite unsupported relic, potion or reward is a truthful
  fail-closed content boundary, not failed elite combat or accepted reward
  support.
- Any crash, wrong profile, unknown mutation state, unexpected Cloud activity
  or cleanup uncertainty stops the campaign.
- Quit normally, quarantine the exact overlay, verify the base, launch/quit one
  clean unmodded game with the bridge port closed, purge the quarantine, and
  finish with zero overlay/process/listener checks.
- Retain only the accepted sanitized summary. No raw bridge payload, credential,
  control ID, profile/save content or differential corpus may be retained.

## 6. Headless actor packets

### H5-ENCODER-04 — Public variable-candidate encoding

- **Allocation:** `gpt-5.6-terra`, high reasoning; independent Sol/high
  information-boundary review.
- **Exclusive ownership:** new `game/agents/headless_encoding.py` and
  `tests/agents/test_headless_encoding.py`.
- **Dependencies:** accepted `headless_v0`, current reduced content and frozen
  Section 3.2 contract. No bridge or live dependency.
- **Deliverable:** versioned schema, framework-neutral encoding/collation,
  reversible out-of-band candidate mapping and canonical fingerprint.
- **Acceptance:** cover all current phases, candidate kinds and public entity/
  event forms; actionable/waiting/terminal/unsupported; variable and empty row
  sets; unknown semantic categories; exact numeric bounds; padding exclusion;
  candidate permutation and valid opaque-reference reallocation invariance;
  malformed input rejection; no hidden/audit/target/identity leakage.
- **Required checks:** its focused test, `tests/contracts`, `tests/conformance`,
  headless projection/candidate/trajectory tests, compile and diff checks.
- **Forbidden:** `headless_v0`, simulation/rules/content, legacy
  `ObservationEncoder`, baselines, training, exports, CLI, bridge and docs.

### H5-DATASET-05 — Trusted actor-example dataset

- **Allocation:** `gpt-5.6-terra`, high reasoning; independent Sol/high
  provenance/leakage review.
- **Exclusive ownership:** new `game/data/headless_policy_dataset.py` and
  `tests/data/test_headless_policy_dataset.py`.
- **Dependencies:** accepted experiment envelope, trusted trajectory loader and
  frozen Section 3.3 eligibility/split identity.
  It starts independently and does not import the encoder until `04` is
  accepted.
- **Deliverable:** deterministic iterable actor samples containing only the
  public policy boundary and its chosen advertised candidate label, with
  manifest/provenance pins.
- **Acceptance:** trusted-manifest loading, deterministic order, chosen-ID
  resolution, declared development/held-out panel separation, duplicate and
  overlap rejection using the exact Section 3.3 key, pin/fingerprint mismatch
  rejection, exact skip counts for interrupted/no-choice records, and tests
  proving target/audit/hindsight streams cannot enter actor
  inputs or labels. No scalar return or value target.
- **Required checks:** focused test, headless trajectory/reporting/artifact
  tests, conformance, compile and diff checks.
- **Forbidden:** encoder before acceptance, trajectory format/writer, rules,
  reward labels, model/training/CLI/export, bridge and docs.

### H6-CANDIDATE-POLICY-06 — Score advertised candidates

- **Allocation:** `gpt-5.6-terra`, high reasoning; independent Sol/high
  shape/permutation review.
- **Exclusive ownership:** new `game/agents/headless_candidate_policy.py` and
  `tests/agents/test_headless_candidate_policy.py`.
- **Dependency:** accepted `H5-ENCODER-04` schema and fingerprint.
- **Deliverable:** a small candidate-conditioned model that pools the global,
  entity and public-event context and emits one logit for each unmasked
  advertised candidate.
- **Acceptance:** variable batch/candidate/entity/event sizes; exact empty-view
  behavior; padded candidates never score as legal; finite forward/backward;
  candidate-permutation equivariance; invariance to valid opaque-reference
  reallocation; serialization with encoding/model fingerprints. No fixed global
  action head, value head, hidden-state reconstruction or policy claim.
- **Required checks:** focused model and encoder tests, relevant agent
  persistence tests, conformance, compile and diff checks.
- **Forbidden:** encoder contract edits, dataset, rollout workers, legacy agent
  defaults, PPO/DQN, CLI/export, bridge and docs.

### H6-BC-SMOKE-07 — Deterministic behavior-cloning plumbing smoke

- **Allocation:** `gpt-5.6-sol`, high reasoning; serialized high-risk join.
- **Exclusive ownership:** new
  `game/training/headless_behavior_clone.py` and
  `tests/training/test_headless_behavior_clone.py`.
- **Dependencies:** accepted and independently reviewed packets `04`, `05` and
  `06`.
- **Deliverable:** one bounded deterministic train/evaluate function over an
  explicitly declared structural-heuristic development/held-out panel, with a
  provenance-bound checkpoint/report.
- **Acceptance:** same seed/config/data yields identical canonical report and
  checkpoint tensors; changed schema/data/model pins reject; finite loss and
  gradients; chosen candidate always belongs to the advertised set; held-out
  structural accuracy/loss is reported; interruption leaves no accepted final
  artifact. Run CPU-only in one process and one training thread with fixed
  dtype, explicit local seeds and deterministic algorithms, restoring any
  process-global Torch settings afterward. Byte-identical tensor requirements
  apply only within that declared environment. The report retains every
  per-component evidence attribution from admitted trajectory manifests and an
  exact sorted unique aggregate set (normally both `combat_v0` and
  `structural_fixture`); it never selects the more convenient single label and
  says only that training plumbing works.
- **Required checks:** all four new focused tests, trajectory/reporting/
  artifact/rollout tests, `tests/conformance`, compile and diff checks, then the
  full repository suite.
- **Forbidden:** large training, target-game policy claims, live data, reward or
  value learning, PPO/DQN integration, `sts-train`, spawned online inference,
  rules/content, bridge and shared docs.

## 7. Review, integration and evidence

Every visible implementation task title begins with its exact packet ID. Every
implementation worker prompt must include the exact packet objective and
acceptance above, owned and forbidden paths, available dependencies, required
commands, contract-preservation rule, focused local commit requirement, and a
final report with outcome, commit, files, tests/results, contract assumptions,
risks, model/effort and aggregate numeric token/elapsed telemetry when
available. Each implementation worker produces one focused commit unless an
explicit correction commit or coordinator-approved safety split is clearer.
Unavailable metrics are `unavailable`; never request or retain prompts,
transcripts, hidden reasoning or chain-of-thought. Workers may not
launch/install the game, access profiles/saves/credentials/endpoints, alter
Steam Cloud, push or perform destructive Git work.

For each returned commit, the coordinator reads the final report, inspects the
complete diff, checks ownership and contracts, runs focused and adjacent tests,
requests corrections from the same task where practical, obtains the required
independent review, and integrates only accepted work in dependency order. Run
the broader regression suite after the bridge join and after the serialized
headless join, not only at the end.

Typical aggregate commands, using the integration checkout's accepted venv:

```bash
STS_PLAN_PYTHON=/Users/rowdeygoos/code/github/RowdeyGoos/StS_agent/.venv/bin/python
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/decision_providers_fixtures.py
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/apply_run_live_fixtures.py
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/apply_run_wire_fixtures.py
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/apply_run_entry_wire_fixtures.py
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/apply_run_elite_wire_fixtures.py
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/verify_room_acceptance_fixtures.py
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/apply_run_acceptance_live_fixtures.py
PYTHONPATH=. "$STS_PLAN_PYTHON" -m pytest -q tests/backends/live tests/differential
PYTHONPATH=. "$STS_PLAN_PYTHON" -m pytest -q tests/agents/test_headless_encoding.py tests/data/test_headless_policy_dataset.py tests/agents/test_headless_candidate_policy.py tests/training/test_headless_behavior_clone.py tests/data/test_headless_trajectory.py tests/training/test_headless_reporting.py tests/conformance
PYTHONPATH=. "$STS_PLAN_PYTHON" -m pytest -q
"$STS_PLAN_PYTHON" -m compileall -q game tests
git diff --check
```

New worktree imports must resolve from that worktree, not an editable install in
the integration checkout. Verify module paths before accepting a worker test.

Evidence labels remain exact:

- C#/Python fixtures and fake actual-client transcripts: `bridge_fixture` or
  synthetic;
- successful bounded observation of the actual pinned game:
  `live_observed` / user-facing **live-demonstrated**;
- encoder and model unit behavior: synthetic structural evidence; dataset and
  cloning reports preserve per-component provenance plus the sorted aggregate
  evidence-label set from admitted trajectories, without promotion; and
- `differential_verified`: unavailable unless a separately authorized retained
  named case passes the established admission process.

## 8. Stop and defer boundaries

Stop for coordinator review if a packet appears to require a C#/wire change,
`headless_v0` mutation, new public information, output schema change, recovery/
retry semantics, retained live data or overlapping ownership. Model escalation
does not broaden authority. Retry transient infrastructure failures without an
escalation; use Luna -> Terra -> Sol or one reasoning-level increase only when
failed acceptance shows the assigned allocation is insufficient. Ultra remains
coordinator-only.

Defer all of the following:

- boss, shop, treasure, potion and relic control;
- event identity redesign or generic modal/protocol refactoring;
- crash recovery, journals, action adoption, idempotency or automatic phase
  detection;
- profile/save/seed access, Steam Cloud changes and retained raw or sanitized
  transition capture;
- Harmony, AutoSlay or copied third-party implementation;
- headless rule/content expansion or target-game fidelity tuning;
- Gymnasium, `sts-train`, PPO/DQN/value learning, large training and online or
  spawned learned-policy rollout; and
- a new C# capability family until bounded live evidence identifies the first
  actual unsupported blocker.

## 9. Completion and next decision

This increment is complete only when every selected packet is reviewed,
integrated and passes its required aggregate tests; bridge cleanup is verified
after any live campaign; the bridge guide, current status, roadmap and
[successor acceptance ledger](research/PHASE_1_ACTOR_READY_ACCEPTANCE.md) are
updated by the coordinator; and evidence levels remain truthful. The coordinator
also updates README/AGENTS pointers if the accepted capability or active graph
changes.

If the live route does not offer an elite or supported room, the campaign may
still accept explicit map entry, but the unoffered target remains `unobserved`.
Do not repeatedly play to manufacture it. The smallest following decision is
then based on observed evidence: either add the first real unsupported C# modal
family under a separately frozen generic typed route, or authorize one narrow
retained sanitized differential case to begin headless fidelity work. Neither
is pre-approved by this plan.
