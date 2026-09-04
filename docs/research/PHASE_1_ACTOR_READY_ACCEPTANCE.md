# Phase 1 actor-ready acceptance ledger

- **Opened:** 2026-09-04
- **Verified parent baseline:**
  `42a3c4e895851188f7179cbc48dcff6ca5974a93`
- **Active plan:**
  [Phase 1 actor-ready execution](../PHASE_1_ACTOR_READY_EXECUTION_PLAN.md)
- **Current state:** `22`, `23`, `04` and `05` reviewed and integrated locally; the user
  approved continuing the increment after the automatic-review block. Validator
  corrections are active; the candidate-policy implementation is released.
  No live campaign.

This is the integration ledger for the elite-continuation and actor-ready
headless successor increment. It begins after the completed
[predecessor ledger](PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md) and must not rewrite
or append new outcomes to that historical record.

## Packet state

| Packet | Current state | Accepted commit | Evidence |
| --- | --- | --- | --- |
| `R0I-ELITE-22` | reviewed and integrated | `85fa8ca` | fixture-only; independent join gate pending |
| `R0I-ELITE-GATE-23` | reviewed and integrated | `8fd4320` | actual-client synthetic gate, both historical controls |
| `R0I-RUN-ACCEPTANCE-24` | Sol/xhigh corrections active | — | through source `50ecd3b`, not accepted |
| `R0I-ELITE-REVIEW-25` | blocked on `22`-`24` | — | planned |
| `R0I-ELITE-LIVE-26` | blocked on review and aggregate gates | — | planned |
| `H5-ENCODER-04` | reviewed and integrated | `23d07d7` | public-only encoding; frozen schema unchanged |
| `H5-DATASET-05` | reviewed and integrated | `1d1f430` | trusted policy examples and exact evidence provenance |
| `H6-CANDIDATE-POLICY-06` | Terra/high implementation active | — | starts from accepted `23d07d7` |
| `H6-BC-SMOKE-07` | blocked on `04`-`06` | — | planned |

“Done” means reviewed, integrated and accepted, not merely implemented in a
worker branch. The coordinator updates the current state, accepted commit,
focused and aggregate commands, review disposition, contract assumptions,
evidence label, risks, model/effort and aggregate numeric telemetry when each
packet closes. Unavailable telemetry is recorded as `unavailable` and is never
estimated.

## Starting evidence boundary

- Bridge milestone remains `R0i`, bridge version `0.8.0`, protocol
  `live_probe_v0`.
- Elite is advertised by the existing map surface but the Python bounded runner
  currently stops at it as `unsupported_destination_kind`.
- Explicit reward entry is live-demonstrated. Explicit map entry, elite
  continuation and composed supported-room handoff are not live-demonstrated.
- Headless environment, artifacts, CLI, rollouts and conformance are accepted
  structural infrastructure. No encoder, actor dataset, variable-candidate
  learned policy or cloning smoke in this increment is accepted yet.
- The last complete repository suite passed 1,052 tests. The last live campaign
  completed normal teardown, exact overlay quarantine, clean unmodded
  launch/quit, purge and final zero-overlay/process/listener checks.
- No live campaign is active and no retained live corpus is authorized.

## Evidence rules

- Fake-client, unit and conformance gates are `bridge_fixture`, `combat_v0`,
  `structural_fixture` or synthetic as applicable.
- Only successful bounded observation of the pinned game may be called
  `live_observed` / live-demonstrated.
- No successor result is `differential_verified` without separate retained-case
  authorization and the established admission review.
- Do not retain raw responses, credentials, control IDs, profile/save content,
  arbitrary live text or hidden reasoning. Live entries contain only the
  minimal sanitized acceptance fields defined in the active plan.
- Do not infer full-run reliability, target-game parity, policy strength or
  near-optimality from this increment.

## Integration and live entries

### 2026-09-04 — Coordinator kickoff

- Verified clean coordinator worktree at exact
  `cd3e3ebb97594067d3693dc30d725152dda4dcf9`; local `main` matches that
  commit and is 147 commits ahead of the locally recorded remote-tracking ref.
  No fetch or remote write occurred.
- Created local integration branch `codex/phase1-actor-ready-integration`.
- Dispatched the four ready packets into persistent project worktree tasks
  from that exact commit, with the plan's exclusive ownership. `22` uses
  Sol/high; `24`, `04` and `05` use Terra/high. No worker uses Ultra.
- `04` has no edit authority until its exact proposal is independently
  inspected and the coordinator records the accepted hash here.
- C#, `live_probe_v0`, `headless_v0`, existing run output schemas, artifact
  pins and retained-data boundaries remain frozen. Shared documentation is
  coordinator-owned.
- Opening task explicitly authorizes the bounded coordinator-only Profile 3
  campaign after packet `26` gates pass. No live campaign is active.
- Aggregate numeric token and elapsed telemetry: unavailable at kickoff.
- Baseline rerun: `PYTHONPATH=. <accepted-venv>/bin/python -m pytest -q`
  passed **1,052 tests in 103.13 seconds** on the clean handoff source.
- Permanent visible task IDs: `22` =
  `01a06e4d-fb8f-7ef2-8182-527969786118`; `24` =
  `01a06e4e-112a-7b63-9bf6-56c156d9ed2d`; `04` =
  `01a06e4e-2471-7183-add8-fa62d29a5862`; `05` =
  `01a06e4e-382b-7de1-8b39-08e7a3b6c6c9`. All four were confirmed active
  through compact task snapshots. The app listing lagged task creation;
  read-only task-index metadata resolved the IDs without reading transcripts.

### 2026-09-04 — Elite producer integration and review findings

- Reviewed all four owned-file diffs of `22` source
  `7c942db4b5fa53433c7a20f94581dd642e67f61f` and integrated as
  `85fa8ca8d2a6b8359652ba2de88b5651ec419314`. Production changes are the two
  frozen destination predicates and the opt-in `elite` provider. No C#/wire,
  granular client, artifact pin or output-schema change.
- Coordinator reran isolated run fixtures (**23 checks**) and provider fixtures
  (**6 checks**). Worker reported 68 adjacent fixture checks, 243 focused tests,
  and 1,051 full-suite passes with the one known packet-23-owned obsolete
  entry-wire assertion failing. This is not a passing aggregate bridge gate.
- Dispatched `23` as visible task
  `01a06e57-032d-73b3-925e-af127f0eee86`, Terra/high, from the reviewed local
  integration branch. Elite remains fixture-only.
- `24` source `a3244e5a9871e301bf8bcd4dbf7a99b740c26a1b` is not accepted.
  Read-only coordinator repros confirmed that mismatched termination
  destinations and unknown nested fields pass, a list-valued milestone raises
  `TypeError`, and arbitrary synthetic `ToolFailure` text reaches CLI output.
  Independent Sol/high review also found impossible producer histories accepted.
- Automatic approval review rejected the correction dispatch because trusted
  implementation authorization could not be established from quoted history.
  The rejected dispatch was not retried or bypassed. User confirmation is
  required before redispatching these corrections; no live work has begun.
- `04` remains read-only and unfrozen. Independent Sol/high review found the
  event width must be 78, normalization and inactive-category rules need exact
  definitions, and map-form coverage and the canonical payload require a
  complete disposition. A revised proposal has arrived but is not accepted;
  no encoder edit authority has been granted.
- `05` source `39b7c76a70de100cbc5235eec890cb62c9302b70` requires changes
  after independent Sol/high provenance/leakage review: retain exact admitted
  per-trajectory component evidence outside actor examples, and require
  caller-declared accepted pins across all sources and splits. Eligibility,
  sample identity, deterministic order and split-overlap identity were sound.
  Reviewer reran 7 focused tests (passed); worker reported 53
  trajectory/reporting and 90 conformance tests passed. It is not integrated.
- Assigned worker models remain as planned; no model escalation. Aggregate
  numeric token/elapsed telemetry remains unavailable.

### 2026-09-04 — Authorized continuation and independent elite gate

- The user replied **proceed** to dispatching the reviewed validator/dataset
  corrections and continuing the increment. Both correction requests were
  successfully delivered to their existing Terra/high tasks, with unchanged
  ownership and no live authority delegated.
- Independent Sol/high review approved `23` source
  `a3910ac242931549bbed3ad6bd824316b6bc6a83`; coordinator read its complete
  diff and reran the isolated elite gate (**8 checks**, passed). Integrated as
  `8fd4320fa9d4a790fdb0676f79bb268600c9bcb7`.
- Reviewer independently passed entry and elite gates (**8 checks each**).
  Worker reported run **23**, run-wire **8**, transport **29**, and focused
  live/differential **245 tests** passed. The entry suite count now names its
  eight top-level check groups; only its obsolete elite-negative case changed.
- Actual production clients run over literal fake transport. The original
  `8212886` entry control remains intact; the new exact `42a3c4e` control stops
  before the queued elite combat while integrated production continues.
  Uncertainty/cancellation cases verify no later request, closed sockets and
  zeroed mutable sent/credential buffers. This is `bridge_fixture` evidence.
- No C#/wire/artifact pin or production output-schema change; full bridge join
  acceptance and live work still await corrected `24` and aggregate review.

### 2026-09-04 — H5 encoding schema freeze before implementation

- Accepted exact proposal:
  [PHASE_1_HEADLESS_ENCODING_SCHEMA.json](PHASE_1_HEADLESS_ENCODING_SCHEMA.json).
  File SHA-256:
  `1b1daa78066e9c3911eea4d673c39d5d13e1182fcd82a979fa3a2cf8a35f3e67`.
- Exported version is `headless_encoding_v1`; encoding fingerprint:
  `3eee27f82ad803d1d47ac5d2ac6ba6fcce2d236f977fde589fe6ee38a9608fa1`.
  It is SHA-256 of UTF-8 `headless_encoding_v1.schema.v1`, one zero byte,
  and `headless_v0.canonical_json_bytes` of the complete parsed proposal.
- Ordered row dimensions are global **47**, entity **90**, public event **78**,
  candidate **557**. The JSON contains every expanded feature name, exact
  registry/API/source/normalization rule, absence convention, join, batch order,
  empty shape, validation rule and fingerprint input. Candidate IDs remain
  canonical out-of-band strings with no numeric/categorical identity feature.
- Independent Sol/high review approved all boundaries, dimensions, registries,
  joins and reallocation rules subject to exact global-source, batch-order,
  canonical-ID and canonicalization clarifications. The coordinator applied
  those corrections and checked the final hash and dimensions before release.
- The map representation deliberately retains public node fields plus current
  node nullness, edge count and visited count. It omits current-node identity
  and edge connectivity; it is a bounded lossy actor representation, not a
  reversible structured observation. No additional opaque-reference join is
  introduced outside candidate resolution.
- Earlier worker proposal fingerprints are not accepted. `04` must export the
  exact accepted JSON schema/fingerprint and may edit only its two owned files
  after receiving the committed freeze. Implementation and independent review
  remain required; no headless actor capability is accepted yet.

### 2026-09-04 — Dataset acceptance and validator allocation correction

- Integrated `05` source `39b7c76a70de100cbc5235eec890cb62c9302b70` as
  `7b8afad3531fc451f5e70ce88a6468600399d415`, followed by correction
  `4daf16545997a78fac79f7371d8c6a786c037a11` as
  `1d1f43011293442563667afc38b23283a1475fac` after clean independent
  Sol/high acceptance and coordinator diff inspection.
- Coordinator verified worktree imports and reran dataset/trajectory/reporting:
  **66 passed in 2.70 seconds**. Independent focused rerun: **13 passed in
  1.13 seconds**. Worker conformance: **90 passed**. Evidence remains
  `combat_v0`/`structural_fixture`, never live or differential verification.
- `load_actor_dataset` requires caller-declared `accepted_backend_manifest` and
  manifest-anchored development/held-out sources. Every source must match the
  exact backend/content/rules/contract identity. Examples remain only public
  `PolicyView`, chosen advertised ID and sample provenance. Split-level
  `admitted_trajectories` retains exact component evidence even for zero-example
  trajectories; `aggregate_evidence_labels` returns the sorted unique set.
- `24` correction `97722148d5ba061c2ba4c278b6e1302ff13104cb` remains
  unaccepted. Independent whole-bridge review reproduced invalid room histories,
  shallow nested-record validation and loss of legitimate production failures.
  Its purported actual-client fixture instead manufactured placeholder records.
- Per active-plan Section 8, coordinator escalated the same visible `24` task
  from Terra/high to Sol/high after repeated failed acceptance. Ownership and
  scope are unchanged; an independent Sol/high reviewer remains separate.
  No Ultra worker, live operation or C#/wire/artifact change occurred.

### 2026-09-05 — Source closure audits and encoder correction review

- `24` Sol/high correction `50ecd3bb6fb85b37a2928b477ba0327a78098815`
  remains unaccepted. Its new actual-client fixtures execute real production
  clients over fake transport, but independent review still found incomplete
  nested leaf validation and legitimate fixed production errors omitted from
  the output allowlist. Coordinator reproduced acceptance of negative final
  player HP, arbitrary nested card payloads and an unknown map kind.
- Per Section 8, the same owner received one reasoning-level increase to
  Sol/xhigh. Independent read-only source audits supplied the finite error-code
  closure and exact combat/map/reward constraints. The correction must preserve
  valid producer paths, including stale-rejection rereads that do not append a
  combat trace and bounded healing before reward readiness. No raw envelope or
  intermediate state may be invented as evidence of discarded fields.
- `04` source `fc3743b8da420c2076b7ab22da600db6c6de512c` required a
  malformed-ID fix and broader contract tests. The same Terra/high task returned
  `4c62b523b22a4afb5b3b23a35fa5403029623225`, with unchanged frozen schema.
  It reports 28 focused, 285 adjacent and 90 conformance tests passed. Independent
  Sol/high review is active; `06` remains gated on acceptance and integration.
- Dataset `05` is accepted; no dataset correction remains active. No live
  campaign or retained live data was created. Aggregate worker token telemetry
  is unavailable; observed app turn durations are not a total execution metric.

### 2026-09-05 — Encoder acceptance and candidate-policy release

- Accepted `04` at exact source `78c55612cabac86ba306c4b49aa0122b4e09a487`
  after independent Sol/high full source/schema review. The final focused
  correction replaces a one-candidate reversal with valid scopes 0 and 2 whose
  two candidate kinds actually reverse canonical order. Each view preserves its
  own ID/row alignment; public global/entity/event rows and candidate-row
  multisets remain invariant.
- Integrated source `fc3743b` as `39eb7d9`, source `4c62b52` as `4439f9f`,
  and final test correction `78c5561` as
  `23d07d7f3485057b625f78a502b48e83fedf15cd`. Only the two owned files changed.
  Frozen JSON, version and fingerprint remain exact; production file SHA-256 is
  `114279e3bc0f6a73e26045a19632d6dc694c1e8748d3aed380dce8fb1ea52afc`.
- Independent focused rerun: **27 passed in 0.60 seconds**. Coordinator final
  encoder/contracts/headless/trajectory run: **284 passed in 5.90 seconds**.
  Integration imports resolve from this checkout. Integrated conformance plus
  encoder/dataset aggregate: **130 passed in 75.04 seconds**.
- Released `06` as a persistent Terra/high project worktree from the accepted
  integration branch, with exclusive model/test ownership. It may consume the
  encoder but cannot alter it. Task ID:
  `01a06e7b-1412-7691-a7a9-af01f0e7deed` (confirmed active). `07` remains
  gated on reviewed model acceptance.
  No worker escalation for `04`; all evidence remains synthetic structural.

Add one dated subsection per reviewed integration wave and, if executed, one
separate coordinator live-campaign subsection. Each entry records:

- exact integration commit and source/artifact identity;
- packet commits and correction commits;
- ownership and independent-review disposition;
- focused and aggregate validation commands with exact results;
- contract/fingerprint changes or confirmation of none;
- evidence classification and remaining residuals;
- model escalation with reason, or none; and
- cleanup evidence for a live campaign.

Never store raw bridge payloads or a full transition/capture artifact in this
ledger.
