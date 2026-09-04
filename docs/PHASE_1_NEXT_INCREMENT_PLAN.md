# Next increment: reliable composition and usable headless experiments

- **Date:** 2026-09-04
- **Planning baseline:** `57a421440dd1dc6b879f91d42db7a63ac575d359`, on
  `codex/phase1-parallel-integration`; contains planning baseline `d93395c`.
- **Status:** accepted for execution by the user's subsequent “execute the
  plan” request. Sections 4–6 offline packets are reviewed and integrated from
  clean `cc2060ce1ffbb615ad5c42faaa621a56bbe5c062`. One bounded coordinator
  campaign passed the rest-context/inspection checks and verified cleanup;
  a follow-up at clean `300d230` exercised zero-POST ineligible gold handling
  but stopped on an unclassified reward response failure. Final cleanup passed;
  the full eligible composition and gold comparison remain unobserved. Event work
  remains investigation-only; retained real data and optional Section 7 remain
  outside this increment. No automatic evidence promotion is authorized.
  The subsequently approved Section 11 reward diagnostic is reviewed and
  integrated through `b77178f`. A later bounded campaign at `bbada1a`
  live-passed that diagnostic at a fresh reward boundary and passed one composed
  ordinary combat/reward/map floor. No supported rest route was offered, so the
  combat/rest/combat target remains unobserved. Cleanup and clean base launch
  passed; no retained live data was created.
- **Execution ledger:** [next-increment acceptance](research/PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md).
- **Relationship:** follows the implemented packets in
  [the existing execution plan](PHASE_1_PARALLEL_EXECUTION_PLAN.md), without
  reopening their accepted scope or declaring Phase 1 complete.
- **Operating rules:** [MULTI_AGENT_EXECUTION.md](MULTI_AGENT_EXECUTION.md).
  Exact prior outcomes are in the
  [acceptance ledger](research/PHASE_1_2026_09_04_ACCEPTANCE.md).

## 1. Recommended outcome

Make the existing slice dependable and easy to use before adding more game
content or training a model against it:

1. Bind room context **before** any room action, exercise the real Python
   clients together, and seek one bounded combat → reward → map → rest → map →
   ordinary-combat live sequence.
2. Provide a supported headless command that runs explicit experiment panels,
   writes reloadable artifacts, and reports truthful outcomes and cancellation.
3. Turn the successful ad-hoc headless panel into maintained, bounded
   generative regression coverage.
4. Prepare one independently reviewable gold-claim effect comparison, with a
   strict distinction between synthetic, transient-live, and retained-live
   evidence. Real retained input remains separately gated.

Do not make rest composition wait for event redesign or headless usability wait
for retained live data. A public-only encoder and policy-example loader are a
second, optional increment, not prerequisites for this one.

## 2. Evidence behind the priorities

| Current fact | Consequence for the next increment |
| --- | --- |
| Standalone rest heal/Proceed/completion and inspection-map stale rejection passed live; clean teardown passed | Reuse this accepted slice; the next missing live result is composition, not another standalone rest smoke |
| `apply_run_live.py` records room kind/ordinal, calls the room runner without that expectation, then compares identity after the interaction | Close the statically identified preflight-to-action wrong-room window; this is not a claim that it occurred live |
| Existing run fixtures substitute whole component callbacks | Add a deterministic transcript through actual component clients, not another copy of their logic |
| Headless batch/benchmark and three-stream persistence APIs already exist, but no headless CLI is installed | Add thin consumers and a small experiment manifest; do not build another runner, writer, or rules loop |
| Twelve serial/spawn episode pairs matched and 829 repository tests passed | Preserve those contracts and maintain broader generated tests; deterministic behavior is still not game fidelity |
| The old comparator has 19 synthetic cases: 3 matches, 14 divergences, 2 unobserved | Preserve those findings; a new narrow mechanic result must not erase the existing full-subset divergences |
| Room wire lacks HP/effect amounts; combat lacks accepted card/entity/timing correspondence; reward wire exposes gold amount and player gold | Start conditional effect comparison with gold, not a broad combat or healing-parity claim |

Source anchors at the planning baseline:

- [run handoff](../bridge/Sts2AgentBridge/tools/apply_run_live.py),
  `_run_bounded_run`, room preflight/result reconciliation around lines 413–446;
- [room interaction](../bridge/Sts2AgentBridge/tools/apply_room_live.py), first
  observation around line 513;
- [run fixtures](../bridge/Sts2AgentBridge/tools/apply_run_live_fixtures.py),
  component-callback fixtures around lines 144–224;
- [headless collector](../game/training/headless_rollout.py),
  [benchmark](../game/training/headless_benchmark.py), and
  [trajectory persistence](../game/data/headless_trajectory.py);
- [comparison dimensions and omissions](../tests/differential/common_public_subset.py),
  [structural reward tables](../game/content/reduced_v0.py), and
  [actual reward rules](../game/engine/reward_rules.py).

## 3. Scheduling and contract ownership

After implementation scope is accepted, dispatch **all ready packets** with
exclusive ownership, up to actual platform capacity. Use persistent visible
Codex worktree tasks for implementation, titles beginning with the packet ID,
and branches based on the verified local integration commit—not `origin/main`.
Read-only reviews may use internal agents. There is no project-imposed numeric
worker cap; do not fill slots with blocked consumers.

The initial ready set is:

- `R0I-ROOM-CONTEXT-08`: standalone room pre-action context seam;
- `R0I-WIRE-INTEGRATION-10`: actual-client synthetic transcript;
- `R0I-EVENT-STUDY-11`: read-only event-boundary investigation;
- `R0I-ACCEPTANCE-TOOLS-12`: reusable capture-off acceptance harness;
- `H5-ARTIFACT-01`: experiment configuration/report envelope;
- `H5-METAMORPHIC-03`: maintained generated headless checks;
- `H4-EVIDENCE-03`: named evidence/eligibility schema and case specification.

The coordinator freezes each small local interface before its dependent starts;
it is not necessary to finish the entire initial set first.

| Accepted dependency | Newly released work |
| --- | --- |
| `R0I-ROOM-CONTEXT-08` | `R0I-COMPOSE-09`; existing transcript worker receives its final join cases |
| `R0I-COMPOSE-09` + `10` + `12`, independent review, exact artifact gates | Coordinator-only `R0I-COMPOSE-LIVE-13` |
| `H5-ARTIFACT-01` | `H5-CLI-02`; optional later policy-example loader |
| `H4-EVIDENCE-03` | `H4-GOLD-04` and `H4-CORPUS-05` offline codecs, independently |
| `H4-GOLD-04` and accepted evidence schema | `H4-GOLD-ADAPTER-06` |
| Gold adapter review + `H4-CORPUS-05` + exact retained-data approval, if selected | Coordinator capture, then independent retained-case admission |
| Event investigation | A decision, not automatic C# implementation |

No live operator runs concurrently with another live operator. Offline workers
may continue during a campaign, but throughput measurements run while the game
and other heavy tests are idle. Implementation completion never substitutes for
reviewed integration or required live acceptance.

### Frozen shared boundaries

The following remain read-only for every new worker unless ownership is
explicitly transferred: `game/contracts/headless_v0.py`, private state/RNG and
snapshot contracts, all `game/simulation/**`, rule/content producers, existing
trajectory formats, wire DTOs/encoders, C# lifecycle/identity/hash/reservation
logic, verifier policy, and accepted golden vectors.

The coordinator owns all shared documentation, `DECISIONS.md`, public exports,
`pyproject.toml`, accepted schema lifecycles, final fingerprints, package
identities, live operation, and evidence promotion. New experiment/evidence
formats are separate versioned consumer contracts, not additions to
`headless_v0` or `live_probe_v0`.

## 4. Bridge packets

### R0I-ROOM-CONTEXT-08 — Reject the wrong room before acting

- **Allocation/risk:** Terra/high; high-risk action seam, independent Sol/high
  review. Hard dependency: accepted current room client and D47 only.
- **Owned:** `bridge/Sts2AgentBridge/tools/apply_room_live.py` and
  `apply_room_live_fixtures.py` in the same directory.
- **Deliverable:** optional keyword-only expected context derived from a
  previously validated preflight: exactly screen kind and room ordinal.
  Standalone calls remain supported. Validate the supplied expectation and
  reject a differing ready context before the first POST. Preserve existing
  within-interaction binding, deadlines, action limits, and no-ambiguous-retry
  behavior. Context is local control data, never a policy feature.
- **Acceptance:** same kind/different ordinal and wrong kind produce zero
  POSTs; initial inactive completion is not readiness; wrong post-action
  completion rejects; ordinary heal/Proceed/complete and standalone callers
  still pass. No arbitrary body/ID/exception text enters errors.
- **Validation:** room fixtures; integrate with run and wire regressions.
- **Forbidden:** run-client edits, C#, wire/status changes, resetting replay
  state, extra actions, and a general diagnostics redesign. A new diagnostic
  schema is not necessary to close this window.

### R0I-COMPOSE-09 — Carry expected context through the run handoff

- **Allocation/risk:** Sol/high, high-risk mutating join.
- **Hard dependency:** accepted `08`; no event-study dependency.
- **Owned:** `bridge/Sts2AgentBridge/tools/apply_run_live.py` and
  `apply_run_live_fixtures.py`.
- **Deliverable:** pass the validated preflight context to the room client;
  retain the post-interaction reconciliation as a second check. Preserve the
  one-room and one-ordinary-combat continuation scope and exact existing caps.
- **Acceptance:** a replacement room is rejected before its first action; no
  later component POST follows failed reconciliation. Cross-kind inactive
  completion is polled, never treated as ready. Keep second-room/unsupported
  destinations fail-closed. Do not count continuation combat twice or conflate
  it with a fully completed reward/map floor.
- **Validation:** run and room fixtures, then `10` real-client transcript.
- **Forbidden:** granular client edits, new providers, additional map budget,
  automatic route farming, C#, or wire changes.

### R0I-WIRE-INTEGRATION-10 — Test the actual clients together

- **Allocation/risk:** Terra/high, independent protocol-boundary testing.
- **Owned, new:** `bridge/Sts2AgentBridge/tools/apply_run_wire_fixtures.py`.
- **Dependency:** current accepted clients suffice for initial useful tests.
  The context-window regression requires accepted `09` for final acceptance;
  no proposed interface is implemented independently in the test harness.
- **Deliverable:** one deterministic fake connector/clock routes the actual
  combat, reward, map, room, and run clients through a synthetic transcript.
  It replaces transport/time/credential hooks, not entire component clients.
- **Acceptance:** a supported combat/reward/map/rest/map/combat sequence,
  delayed phase readiness, defeat, wrong-room replacement, rejected receipts,
  timeout/uncertain POST, second room, and unsupported destination. Check exact
  request order, no mutation retries, no POST after failure, component action
  totals, resource closure, and secret-canary absence from output.
- **Forbidden:** production fixes or rewriting existing component fixtures.
  Report concrete defects to the owner; the harness must not normalize them
  away. Final evidence is `bridge_fixture`, not live.

### R0I-EVENT-STUDY-11 — Decide what event continuation can safely mean

- **Allocation/risk:** Sol/high, read-only high-risk investigation.
- **Owned:** none. Coordinator records the bounded findings in this plan or
  its acceptance ledger; do not generate an unrelated architecture document.
- **Dependencies:** baseline source, D47, sanitized historical failures.
- **Deliverable:** distinguish pending/stall classification, repeated visible
  event projections, and evidence for event exit. Source-bound cases include
  unchanged projection, A → B → A, map/overlay disappearance, and accepted
  same-event embedded combat. Where practical exercise the existing C# test
  seam in a disposable test environment; a copied Python model is not C# proof.
- **Acceptance:** identify whether already allowed public information can
  distinguish a new event step/exit. Return a minimized reproduction or state
  explicitly that the historical cause remains unproven. Compare conservative
  unsupported/stall behavior with an identity change, listing every affected
  producer, consumer, schema/vector, reservation invariant and artifact gate.
- **Forbidden:** production edits, live acquisition, inferred event completion,
  speculative hash/registry resets. Any repair is a separately accepted packet
  after this evidence and contract review; it does not block rest composition.

### R0I-ACCEPTANCE-TOOLS-12 — Reusable capture-off acceptance checks

- **Allocation/risk:** Terra/high, independent privacy/action-boundary review.
- **Owned, new:** `bridge/Sts2AgentBridge/tools/verify_room_acceptance.py` and
  `verify_room_acceptance_fixtures.py`.
- **Dependency:** accepted clients and the reviewed transient harness behavior
  recorded in the 2026-09-04 ledger. No event or new wire dependency.
- **Deliverable:** make the existing inspection-map negative check and minimal
  room/run result summaries reproducible. Accept original snapshots in memory,
  retain the bounded operator acknowledgement, and require exactly one stale
  action attempt with an exact stale/no-mutation receipt. Summaries contain
  only fixed codes and aggregate counts; no raw logging or corpus output mode.
- **Acceptance:** mocked partial/late/invalid acknowledgement, EOF, wrong initial
  state, unsuppressed actions, wrong receipt binding, accepted-instead-of-stale,
  deadlines, exception cleanup, and credential canaries. All actual networking
  and identity/configuration hooks are replaced before fixtures execute.
- **Forbidden:** launch/install automation, manager/config/bootstrap edits,
  bridge schema changes, worker access to credentials/endpoints. Composed
  result coverage is finalized against accepted `09`.

### R0I-COMPOSE-LIVE-13 — Coordinator-only bounded acceptance

After `08`, `09`, `10`, and `12` pass focused/shared tests and independent
review, bind the exact integrated source, artifact, harness, and invocation.
Python-only edits need reviewed authored-source inventory changes where
applicable, not automatic DLL/policy repinning. A changed C# artifact requires
the complete build/test/surface/package/reproducibility gates again.

Target **one** combat/reward/map/rest/map/ordinary-combat sequence using the
existing maximum three accepted destinations and existing action/combat caps.
Set a 30-minute campaign gameplay ceiling; stop sooner at any controller bound.
Use the existing deterministic providers; do not change coverage ranking or
silently choose unsupported content. If no eligible route is offered, report
`unobserved`, not failure of an unexercised capability or a passed milestone.
No repeated run farming is part of this packet. Starting/resuming dedicated
Profile 3 normally remains within the user's standing live authorization.

The user has already authorized ordinary coordinator bridge installation,
game launch, Profile 3 gameplay, transient authenticated checks, and cleanup.
**Do not ask for renewed project-level permission for those actions.** Review
the exact artifact before use and request only a required system permission.
No launch is performed during this planning turn.

Keep Steam Cloud unchanged and do not impose a Cloud-idle gate. Unexpected
enabled/syncing Cloud, wrong profile, crash, uncertain mutation scope, or failed
cleanup stops live work. Finish with normal quit, exact quarantine/removal,
clean unmodded launch/quit, closed listener, final base verification and purge.
No direct profile/save access, other profiles, multiplayer, or base-game writes.

## 5. Headless usability and validation packets

### H5-ARTIFACT-01 — Versioned experiment envelope over existing trajectories

- **Allocation/risk:** Terra/high, serialization/provenance boundary.
- **Owned, new:** `game/training/headless_reporting.py` and
  `tests/training/test_headless_reporting.py`.
- **Dependencies:** accepted rollout, benchmark and trajectory APIs only.
- **Deliverable:** strict `headless_experiment_v1` configuration/report codec
  and writer/loader. Bind ordered episode configurations, scenario and chooser,
  separate game/policy/collector seeds, budgets, exact backend/content/rules/
  contract identities, completed/pending IDs, stop reasons and each trajectory
  manifest hash. Put elapsed time, process mode and host measurements in a
  clearly separate nondeterministic measurement section.
- **Repetition identity:** the existing benchmark repeats the same episode
  configurations and trajectory IDs. Identify an experiment episode by
  `(repetition_index, trajectory_id)`, reject duplicates within a repetition,
  and use separate repetition directories with the existing writer/loader.
  Preserve seeds and trajectory IDs; do not rewrite them to avoid collisions.
  Track received/pending/interrupted results per repetition, including unstarted
  repetitions. A single run uses repetition index zero.
- **Acceptance:** reuse `FinalizedTrajectory.write_to` and `load_trajectory`;
  never flatten replay, target and audit streams. Caller supplies the expected
  experiment manifest hash on trusted reload; hashes prove consistency, not
  authenticity. Refuse overwrite, paths escaping the chosen output root,
  truncated/unfinalized reports, duplicate/swapped trajectories, bad types and
  pin mismatches. Interrupted results preserve received/pending distinctions;
  failed/no-trajectory episodes are explicit. Write final manifest last.
- **Forbidden:** another persistence implementation, runner or factory,
  collector/trajectory schema changes, pickle, implicit backend repair or
  resumable worker-state promises. Independent provenance review is required.

### H5-CLI-02 — One supported headless experiment command

- **Allocation/risk:** Terra/medium, bounded consumer of accepted APIs.
- **Hard dependency:** accepted `H5-ARTIFACT-01` envelope.
- **Owned, new:** `game/cli/headless.py`, `tests/cli/test_headless.py`,
  `configs/headless_smoke.json`.
- **Deliverable:** run/benchmark/validate subcommands over the existing
  collector, benchmark and trusted loader. Explicit bounded configuration,
  no import-time execution, deterministic panel order, conservative defaults,
  a summary of real stop reasons, interruption and unstarted repetitions.
  Coordinator wires one `sts-headless` entry point in `pyproject.toml`.
- **Acceptance:** CLI subprocess tests; identical semantic artifacts for serial
  and two-worker spawned runs; declared timing/mode fields excluded only from
  performance-independent equality. Real bounded SIGINT preserves received
  artifacts/pending IDs and leaves no workers; stopped benchmark does not start
  another repetition. Invalid configuration fails before backend construction;
  output collisions fail before new episodes run. Help/example works without
  optional Torch/Gymnasium imports. Validate mode needs an externally supplied
  manifest hash, not a self-trusting hash read from the same manifest.
- **Forbidden:** changes to `sts-train`, legacy benchmarks, worker internals,
  new rules, model training, or reporting structural route completion as a game
  win. All package/export/docs edits are integration-owned.

### H5-METAMORPHIC-03 — Maintain the broader reproducibility checks

- **Allocation/risk:** Sol/high, independent state/RNG/snapshot verification.
- **Owned, new:** `tests/conformance/test_headless_v0_metamorphic.py` and
  `tests/training/test_headless_matched_panel.py`.
- **Dependencies:** baseline accepted APIs only; no CLI or report dependency.
- **Deliverable:** persist the twelve-case serial/spawn panel and add bounded
  deterministic generated action prefixes over both supported scenarios and
  every reduced phase. Use the standard-library seeded RNG; no new dependency.
- **Acceptance:** complete episode/record equality across process modes and
  collector seeds; injected stale/invalid requests leave state/RNG unchanged;
  extra observe/snapshot calls do not alter continuation; branch
  A → restore → B → restore → A has the same A suffix. Include zero/one budgets,
  defeat, unsupported state and terminal empty-candidate behavior. Cap the
  generated panel at 24 cases and 300 transitions per episode; emit only a
  minimized synthetic seed/prefix for failures, not unbounded fuzzing output.
- **Forbidden:** rewriting existing fixed conformance examples or production
  fixes to make tests green. Report new defects as separately owned packets.
  Passing means structural consistency, not target-game accuracy.

## 6. Named conformance preparation, independent of event work

### H4-EVIDENCE-03 — Freeze provenance, eligibility and the named case

- **Allocation/risk:** Sol/high, shared evidence/privacy contract.
- **Owned, new:** `game/analysis/conformance_evidence.py`,
  `tests/differential/test_conformance_evidence.py`, and
  `tests/differential/reward_gold_case_spec.json`.
- **Dependencies:** accepted strict wire DTOs, old comparator, production
  reward rules, and current identity inventory. No live input needed.
- **Deliverable:** closed versioned `named_conformance_v1` records separating
  source provenance, alignment eligibility, field findings and coordinator
  admission. Preregister a conditional gold-claim case before seeing any live
  post-state. Freeze the explicit scalar allowlist and omissions below.
- **Acceptance:** reject duplicate/unknown fields, bool-as-int, missing or
  swapped boundaries, changed pins, fabricated live origin, unsupported
  alignment and self-promoted evidence. A hash or `live` string is not admission;
  retained admission requires an independently supplied reviewed capture
  manifest identity. Existing synthetic comparator results remain unchanged.
- **Forbidden:** backend capability promotion, replacement of the old
  comparator, live data, or rule/content changes. Shared acceptance is owned
  by the coordinator; consumers wait for this version to be frozen/integrated.

### H4-GOLD-04 — Compare one production rule, not a copied formula

- **Allocation/risk:** Sol/high, high-risk alignment/claim semantics.
- **Hard dependency:** accepted `H4-EVIDENCE-03`.
- **Owned, new:** `game/analysis/reward_gold_conformance.py` and
  `tests/differential/test_reward_gold_conformance.py`.
- **Deliverable:** construct a local reward-rule scenario from allowed
  **pre-state only**, run actual `RewardRules`, and compare selected gold amount,
  gold delta, and HP/max-HP/deck-count preservation. Require a uniquely eligible
  advertised unclaimed gold reward. Current structural tables offer only 25
  and 35; another amount is unaligned, never a reason to tune content after
  observing the game. Other unrepresentable preconditions are unaligned too.
  Freeze the unavoidable synthetic deck/map/RNG/control-identity scaffold in
  the case specification; copy only the allowed public pre-state scalars.
  Test that the compared transfer is independent of those scaffold choices.
  This is not reconstruction of the live world. There is no retained evidence
  for how often an eligible 25/35 live reward will occur.
- **Acceptance:** independently authored positive/negative synthetic cases,
  unsupported amount, ambiguous selection, wrong receipt binding, absent/stale
  post-state, changed HP/deck, swapped boundaries, and post-conditioned setup.
  Do not equate full hidden states, live/headless seeds, card identities or RNG.
  Keep the old broader subset findings alongside the narrow result where
  available; otherwise state that broader comparison was not evaluated.
- **Forbidden:** modified production rules/tables, fabricated world parity,
  live capture or automatic `differential_verified` promotion. A match concerns
  this conditional transfer only, not reward generation/distribution or cards.

### H4-CORPUS-05 — Offline sanitizer and retention codec

- **Allocation/risk:** Terra/high, independent privacy review.
- **Hard dependency:** accepted `H4-EVIDENCE-03`; independent of `H4-GOLD-04`
  for synthetic codec tests.
- **Owned, new:** `game/analysis/conformance_corpus.py` and
  `tests/differential/test_conformance_corpus.py`.
- **Deliverable:** deterministic allowlisted records and manifest serialization,
  explicit case/byte ceilings, exclusive non-overwriting files, final manifest
  marker, and caller-anchored reload. Synthetic fixtures stay clearly synthetic.
- **Acceptance:** no raw/control/credential text or raw-body hashes; reject
  extra fields, path escapes, truncated/swapped/duplicated cases, changed source
  pins, and synthetic substitution for reviewed retained origin. Partial writes
  cannot be admitted as a complete corpus. Test exact output with secret canaries.
- **Forbidden:** obtaining/retaining real inputs or committing real fixtures.
  Coordinator prepares the exact retained-data request only if that option is
  selected. Offline codec acceptance grants no retention permission.

### H4-GOLD-ADAPTER-06 — Bounded transient collection through existing clients

- **Allocation/risk:** Terra/high, independent action and privacy review.
- **Hard dependencies:** accepted evidence and gold evaluator; retained mode,
  if later approved, additionally depends on `H4-CORPUS-05`.
- **Owned, new:** `bridge/Sts2AgentBridge/tools/compare_reward_gold_live.py` and
  `compare_reward_gold_live_fixtures.py`.
- **Deliverable:** a thin adapter reusing existing credential/HTTP/strict-parser
  boundaries and canonical `game.analysis` evaluator imports, not importing
  helpers from `tests/` or copying their rules. Default capture-off. At most one
  eligible claim POST, exact in-memory receipt binding, and a fresh stable
  reward post-state within the existing timeout/caps. No background polling
  service or general-purpose endpoint client. Explicit tested project import
  setup is part of the tool; no optional RL dependency is required.
- **Acceptance:** fully mocked request order, duplicate/invalid data, missing
  post-state, uncertainty/intervening action, timeout/cancellation, one-POST
  maximum, no mutation retry, resource closure, and no payload/secret logging.
  Stable repeated reads alone do not prove causality; uncertain correspondence
  cannot pass. A receipt alone never proves the post-state.
- **Forbidden:** worker live access, new routes, C#, scenario farming, direct
  profile access, automatic capture/retention, policy widening, or golden-vector
  repinning. Production fixes to existing clients require ownership reassignment.

### Live evidence and retention decision

Two distinct outcomes are available after offline review:

1. **Transient check:** coordinator uses the existing standing live authority,
   consumes full responses/control bindings only in memory, and retains case
   name, reviewed artifact/spec identities, fixed field verdicts, eligibility
   and omission facts. This is a bounded live-observed check, **not** a
   replayable corpus or automatic named fidelity admission. It does not close
   the original `H4-LIVE-DIFF-02` retained-input gate.
2. **Retained sanitized case:** requires a separate exact user-approved capture
   and retention request. Proposed first ceiling: one eligible transition,
   at most 64 KiB, in one explicitly named private local staging directory;
   no upload or publication. The request must settle exact retention/deletion
   timing and any local repository admission before collection. Default is
   no real data written. Raw capture remains prohibited in either mode.

Proposed retained fields, to be narrowed/frozen by `H4-EVIDENCE-03`: family,
status/screen category, pre/post HP/max HP/gold/deck count, selected gold amount
and category, normalized reward claimed flags/amounts/offer counts, candidate
category multisets, fixed validation codes, capture-local ordinal, and reviewed
build/bridge/parser/rules/content/schema/spec/harness identities. Full response
bytes, bridge decision/action IDs, authorization and receipt correlation stay
in memory only. Never retain arbitrary text, card/enemy/event identifiers,
profile/save contents, live seeds, inferred snapshots, or raw-payload hashes.

Only coordinator review of actual eligible retained evidence can admit a named
`differential_verified` claim. No aggregate backend/content label changes.
An unavailable 25/35 reward or another unmet precondition is a legitimate
`unobserved`/`unaligned` result; do not repeatedly play to force a passing case.

## 7. Optional next increment, not in the initial dispatch

Once the usability milestone lands, consider these independently scoped
consumers while waiting for additional fidelity evidence:

- **H5-ENCODER-04** — Terra/high, independent Sol/high information review.
  New `game/agents/headless_encoding.py` and
  `tests/agents/test_headless_encoding.py`. Hard dependency on a coordinator-
  approved local feature schema: only `PolicyView`, public scalar/categorical
  features, variable entities and one row per advertised candidate, with
  out-of-band reversible candidate mapping. No identity/hash values as numeric
  features, reconstructed legality, hidden previews, fixed global action head,
  or legacy `ObservationEncoder` reuse. Test every phase, missing/unknown
  categories, empty candidates, padding exclusion, and valid opaque-reference
  relabeling invariance. Compare corresponding semantic rows modulo candidate
  permutation: derived candidate IDs can change their sorted order. The scheme
  must respect the contract's derived references; malformed relabelings are not
  valid test inputs.
- **H5-DATASET-05** — Terra/high, independent provenance review. New
  `game/data/headless_policy_dataset.py` and
  `tests/data/test_headless_policy_dataset.py`. Hard dependency on the accepted
  experiment envelope; uses existing trusted trajectory loaders. Public actor
  inputs and chosen-action labels remain separate; hindsight/audit streams
  never enter actor features. Deterministic iteration, trusted manifests,
  duplicate/overlapping declared development-panel rejection, and no value
  target. Encoding integration waits for accepted `04`.

Neither needs event completion, but neither should widen the actor contract
to make learning convenient. No learner, PPO run, search, or policy-quality
benchmark is scheduled here. A tiny later learning plumbing smoke can be
considered only after these boundaries pass; large training awaits relevant
mechanic fidelity. Shops, potions, new content catalogs, generic effect-engine
rewrites, and engine-hosted fast-backend selection remain separate decisions.

## 8. Validation, integration and handoff

Use the accepted repository venv interpreter; system Python lacks pytest here.
New Git worktrees do not inherit the ignored `.venv` directory. Set the exact
interpreter below and `PYTHONPATH=.` from the selected worktree so imports come
from that worktree, not an editable-install path in the integration checkout.
Verify imported module paths before acceptance. An isolated provisioned worktree
venv is an alternative if dependency ownership requires it; do not silently
change shared dependencies. Typical gates (new paths become runnable only
after their packet exists):

```bash
STS_PLAN_PYTHON=/Users/rowdeygoos/code/github/RowdeyGoos/StS_agent/.venv/bin/python
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/apply_room_live_fixtures.py
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/apply_run_live_fixtures.py
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/apply_run_wire_fixtures.py
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/verify_room_acceptance_fixtures.py
PYTHONPATH=. "$STS_PLAN_PYTHON" bridge/Sts2AgentBridge/tools/compare_reward_gold_live_fixtures.py
PYTHONPATH=. "$STS_PLAN_PYTHON" -m pytest -q tests/training/test_headless_reporting.py tests/cli/test_headless.py
PYTHONPATH=. "$STS_PLAN_PYTHON" -m pytest -q tests/conformance tests/training/test_headless_matched_panel.py
PYTHONPATH=. "$STS_PLAN_PYTHON" -m pytest -q tests/differential tests/engine/test_reward_rules.py tests/backends/live/test_r0i_wire.py
PYTHONPATH=. "$STS_PLAN_PYTHON" -m pytest -q
"$STS_PLAN_PYTHON" -m compileall -q game tests
git diff --check
```

Each worker prompt includes its exact packet definition, owned and forbidden
paths, starting commit and integrated dependencies, acceptance commands,
contract-preservation rule and focused local commit requirement. It explicitly
forbids game launch/install/profile/save/Cloud/credential/endpoint access.
Production and integration defects return to the responsible owner; no worker
changes an adjacent contract to make its own test pass.

Review complete commits before integration. Run focused tests and relevant
shared regressions per packet, and the broad suite after meaningful joins.
Independent review is mandatory for action binding, protocol transcripts,
serialization/provenance, RNG/restore tests, actor-data boundaries and all
live evidence. The coordinator updates accepted pins deliberately; a fixture
failure is never fixed by automatically regenerating its expected identity.

Every handoff records outcome, exact commit/files, commands and results,
contract assumptions/fingerprints, evidence class, residual risks, repair cycles,
model/effort and available aggregate numeric token/elapsed telemetry. Missing
metrics are `unavailable`; no prompts, transcripts or reasoning content retained.
No remote writes, destructive Git, or unrelated changes are authorized.

### Model policy

Keep the user's coordinator allocation, Sol/Ultra. Worker assignments above
reuse the prior policy: Sol/high for disputed contracts and high-risk joins,
Terra/high for bounded implementations with semantic risk, Terra/medium for
the thin CLI. No Ultra worker. This is an engineering allocation, not a speed
or cost guarantee. The tier roles are consistent with official OpenAI
documentation for [Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
and [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra).

Escalate only from observed failed acceptance: one focused correction, then
stop repeated blind attempts on the same cause. Terra may move to Sol; a real
contract conflict returns to the coordinator instead. Transient infrastructure
failures do not justify model escalation. Preserve the earlier rollout
escalation as historical evidence, not an automatic upgrade of every consumer.

## 9. Exit criteria and decisions left open

The first **offline implementation milestone** is complete when the context-
window fix, actual-client fixtures, reusable acceptance checks, headless
CLI/artifacts and maintained panel are integrated and independently reviewed,
with broad regression passing. **Live composition acceptance** additionally
requires a passed eligible sequence and verified cleanup. Failure or a route
not offered is reported accurately, but does not close live acceptance; an
unobserved sequence is not done. Cleanup remains mandatory for every campaign.

The conformance-preparation milestone is complete when its schema, evaluator,
offline codecs and mocked adapter pass review. A genuine retained-case fidelity
milestone additionally needs the exact approval, eligible live input and
independent replay/admission. Do not hold completed offline work open merely
to obscure that separate gate, or declare H4 live work complete without it.

Decisions for the next execution request:

The original planning choices below are preserved historically. Execution
accepted Sections 4–6, completed their offline implementation and conformance
preparation, and retained the event/data/optional-work boundaries. The next
small milestone is the still-open eligible live composition and transient gold
check; it is not a new retained dataset or broader content/training scope.

1. Accept the recommended first-increment scope (Sections 4–6 offline packets
   plus bounded coordinator acceptance), or select a smaller subset.
2. Keep event work investigation-only until its minimized evidence and contract
   proposal are reviewed; no assumed root cause or automatic C# repair.
3. Choose separately whether to prepare/approve one retained sanitized gold
   case. Ordinary bridge live checks do not need renewed approval.
4. Leave encoder/dataset and all model training out of the initial dispatch;
   reconsider them after the first usability milestone.

This planning turn used three concurrent read-only lane reviews. No new
implementation tasks, game launches, capture, rule changes or evidence
promotions were performed. The planning review reran 81 existing
parser/differential tests successfully; the latest full baseline remains
829 passing tests from the preceding acceptance turn.

Independent draft review accepted the bridge and evidence boundaries. The
headless reviewer identified repeated benchmark trajectory IDs; the envelope
now explicitly separates repetition directories and identities. Review also
clarified worktree interpreter provenance, valid reference-permutation testing,
the synthetic gold scaffold, and separate offline/live completion gates.

## 11. Approved narrow reward-diagnostic follow-up

After the documented campaign at `300d230` stopped with
`reward_action_response_mismatch`, the user explicitly approved this diagnostic
packet with “yes”. Starting checkpoint: clean `d958a0a` on the integration branch.
This is not approval for a C# repair, a broader bridge surface, retained raw
responses, or the optional headless/training increment.

### R0I-REWARD-DIAG-14 — Capture-off reward failure classification

- **Status:** accepted and integrated through `b77178f` after independent review,
  16 maintained diagnostic groups, 137 shared bridge fixture checks, 242 focused
  tests and a 1,050-test repository regression. It had not been used live at
  packet acceptance; the later `bbada1a` campaign passed its successful
  four-action path. It does not resolve the discarded response's mutation
  outcome or live-demonstrate its failure classifications.
- **Allocation:** Terra/high implementation in one persistent project worktree;
  independent read-only protocol/privacy and counter/fixture review, Sol/high.
  After the first correction round, review reproduced incomplete cancellation
  cleanup and missing maintained acceptance cases. The same task is escalated
  to Sol/high for these concrete defects, not for task duration.
- **Objective:** distinguish the previously conflated reward action transport,
  HTTP-envelope and receipt failures using only closed, sanitized classifications.
  The previous live cause remains unknown; diagnostics do not retroactively
  classify it or convert a failed request into success.
- **Ownership transfer:** this packet exclusively owns
  `bridge/Sts2AgentBridge/tools/apply_reward_live.py`, plus new
  `reward_action_diagnostics.py`, `diagnose_reward_live.py`, and
  `reward_action_diagnostics_fixtures.py` in the same directory. No other writer
  owns these files. Coordinator owns documentation, contract decisions and
  integration. Additional paths require explicit reassignment.
  Independent cancellation testing found an inherited partial-response buffer
  cleanup defect. The coordinator explicitly adds only exceptional-exit
  zeroization in `probe_live.py::_exchange` to this packet's ownership. Successful
  response ownership, exception propagation, transport behavior, request bytes,
  deadlines, retries and wire semantics must remain unchanged. This is a
  prerequisite of the existing cancellation/privacy gate, not a new capability.
- **Available dependencies:** accepted reward client, bounded transport and
  strict wire receipt semantics; actual-client synthetic fixtures; prior
  read-only failure review in the next-increment acceptance ledger.
- **Deliverables:** an explicit opt-in reward-only diagnostic seam and thin
  capture-off reward CLI. Default CLI output, success dictionaries, error codes/exit codes,
  receipt acceptance, decision/reconciliation checks, timeouts and action caps
  remain compatible. The opt-in diagnostic output must remain useful on a
  failure without outputting the full reward result or changing global CLI
  error handling. A shared diagnostic shape is reviewed before final acceptance.
- **Allowed facts:** fixed action category and failure stage; bounded counts of
  attempted action exchanges, exactly accepted receipts, and fully reconciled
  actions; exact known HTTP/error classification; strictly validated receipt
  status/reason/mutation enums and binding-match booleans or explicit unknowns.
  An attempted exchange does not prove delivery. Always preserve
  `0 <= reconciled <= accepted <= attempted <= 17`. Reported receipt fields do
  not prove mutation outcome for an unbound or uncertain request.
- **Forbidden facts:** raw response/request bodies, body hashes, decision/action/
  correlation IDs, reward/card/player/profile/seed data, credentials, arbitrary
  server strings, exception text, or full in-memory histories. No capture/output
  directory mode. Diagnostic failure must never authorize retry or continuation.
- **Acceptance:** actual-client fake-transport cases cover each canonical
  rejection, wrong bindings, malformed/noncanonical receipts, exact 429,
  retryable 503 and nonretryable 500, malformed/oversize HTTP and
  send/receive/deadline failures. Compare accepted-receipt vs reconciled-prefix
  counters on failures
  after an accepted response. Exercise whole CLI stdout/stderr, first-receive
  credential/source canary leak mutations, exception redaction, cancellation,
  request/response/credential zeroization and socket closure. Replace identity,
  credential and socket hooks before all fixture CLI execution; no live I/O.
  Preserve existing reward, run, actual-wire and gold-adapter fixture results.
- **Required commands:** repository Python 3.10+ with `-B -E -s -S` for the new
  fixture and `probe_live_fixtures.py`, `apply_reward_live_fixtures.py`,
  `apply_run_live_fixtures.py`, `apply_run_wire_fixtures.py`,
  `compare_reward_gold_live_fixtures.py`; relevant
  `tests/backends/live` and `tests/differential` pytest suites; compile and diff
  checks. Coordinator performs the broader regression before integration.
- **Forbidden overlapping changes:** `probe_live.py` outside the narrowly
  reassigned exceptional-exit cleanup, `tool_common.py`, all C#,
  other controller files, wire DTOs/vectors, manifests/pins, shared contracts,
  headless state/rules/content and documentation. Preserve public contracts;
  stop and propose any necessary change to the coordinator.
- **Handoff:** one focused local commit; outcome, exact commit/files, tests and
  results, assumptions, risks/blockers, model/effort and available aggregate
  numeric token/elapsed telemetry. Unavailable metrics are `unavailable`, never
  estimated. No prompts, transcripts or hidden reasoning retained.
- **Authority:** worker must not launch/operate the game, install the bridge,
  access endpoints/credentials/profiles/saves, or change Steam Cloud. No remote
  writes or destructive repository operations. Any later live attempt remains
  coordinator-only and requires the usual exact review, bounds and cleanup;
  this packet's fixture acceptance alone is not live demonstration.

## 12. Approved targeted simplification follow-up

The user's instruction to proceed after the `zhiyue/sts2-rl-agent` comparison
authorizes the following bounded increment from clean `3e11094`. It reduces
duplicated Python transport and evaluates compatible lifecycle helpers; it does
not adopt AutoSlay, Harmony, debug/seed/preference changes, third-party code,
new gameplay surfaces, or optional headless/training work. Existing live gates
and standing coordinator-only authorization remain unchanged. This increment's
acceptance is offline; it does not close the open live composition gate.

### R0I-TRANSPORT-15 — One bounded exchange implementation

- **Status:** accepted and integrated through `9d7a0ae`; production now has one
  receive/cleanup loop. The semantic correction is exceptional-exit wiping for
  room-owned response buffers. All other transport behavior is unchanged.
- **Allocation:** Terra/high in a persistent project worktree; independent
  protocol/privacy review before integration.
- **Objective:** make `probe_live._exchange` and `apply_room_live._exchange`
  use one socket/send/receive/cleanup implementation, carrying the accepted
  exceptional-exit buffer cleanup to room calls and preventing further drift.
- **Available dependencies:** integrated reward diagnostic and cancellation
  hardening through `b77178f`, room context binding, real-client composition
  fixtures, and unchanged `live_probe_v0` schema 1.
- **Exclusive ownership:** `bridge/Sts2AgentBridge/tools/probe_live.py`,
  `apply_room_live.py`, `probe_live_fixtures.py`, and
  `apply_room_live_fixtures.py` in the same directory. Prefer a small internal
  helper in the existing probe module, already consumed by every client; do not
  introduce a transport framework or additional public API.
- **Frozen behavior:** existing `_exchange` call signatures, route-specific
  request builders/allowlists, exact request bytes, connector and clock seams,
  initial `probe_transport_timeout` versus `room_transport_timeout` codes,
  subsequent label-specific errors, deadlines, caps, response ownership and
  exception precedence. No retries, extra exchanges, credential lookup changes,
  receipt/parser normalization, or changes to phase reconciliation. The only
  intended correction is wiping room-owned mutable responses on every
  exceptional exit, including cancellation and exceptional socket close.
- **Acceptance:** a single receive loop; unchanged ordinary results and fixed
  errors; empty/oversize/malformed chunks, send/receive/timeout failures,
  KeyboardInterrupt/SystemExit and close failures close sockets and wipe owned
  buffers without logging payloads. Successful returned buffers remain intact
  until caller cleanup. Existing room context/action/replay tests pass.
- **Required tests:** isolated probe, room, reward diagnostic, reward, map,
  turn, combat, floor, run, actual-client wire, room-acceptance and gold-adapter
  fixtures; focused live-parser/differential pytest; compile and diff checks.
  Coordinator runs the full regression and reviews authored-source bindings.
- **Forbidden overlap:** all C#, contracts/vectors, package/policy/bootstrap
  pins, other controllers, `tool_common.py`, headless files, shared docs and
  packet `17` tests. Propose any needed contract/ownership change before editing.

### R0I-LIFECYCLE-STUDY-16 — Compatible lifecycle reuse decision

- **Status:** complete, read-only. No verified AutoSlay/WaitHelper drop-in
  preserves the current synchronous public evidence/action boundary; no C#
  lifecycle replacement was selected.
- **Allocation:** read-only reviewer; owned files **none**.
- **Dependencies:** current accepted readers/lifecycle, prior event study and
  source-referenced `zhiyue` comparison at `1b7e7ce`.
- **Deliverable:** one bounded recommendation for existing reward/room/map
  lifecycle handling, distinguishing reusable public helpers from AutoSlay,
  debug, preference, seed or Harmony-dependent approaches. Do not repeat the
  completed event study or create a general architecture document.
- **Acceptance:** source anchors, current-build compatibility evidence or an
  explicit unknown, preserved public/action/replay boundaries, and the smallest
  proposed next step. A finding is static-only and does not authorize a C# fix.
- **Forbidden:** edits, third-party code copying/execution, decompiled-source
  access, game/profile/save/credential/Cloud access, launch or installation.

### R0I-TRANSPORT-TEST-17 — Independent exchange regression gate

- **Status:** accepted and integrated through `e187dab` after a coordinator-
  found masked harness correction. Its 29 checks pass on `15` and fail on the
  preceding room implementation at the intended cancellation-zeroization case.
- **Allocation:** Terra/high in a separate persistent project worktree.
- **Exclusive ownership, new:**
  `bridge/Sts2AgentBridge/tools/bounded_transport_fixtures.py` and
  `tests/backends/live/test_bounded_transport_fixtures.py`.
- **Dependencies:** frozen existing probe/room `_exchange` entry points only;
  useful test implementation starts before `15`. Final acceptance waits for
  reviewed integration of `15`, not a guessed private helper interface.
- **Deliverable:** compact maintained synthetic gate exercising actual probe
  and room clients through injected connectors/clocks, without reproducing the
  production transport logic. Pytest must discover and execute the gate.
- **Acceptance:** exact GET/POST bytes and allowlist rejection; unchanged
  initial/per-operation timeout/error codes and connection/response bounds;
  no retry; returned-buffer lifetime versus cancellation/exception zeroization;
  held request/response canaries; socket closure and body/close exception
  precedence. Cover both KeyboardInterrupt and SystemExit after partial reads
  and non-OSError close failures. No real sockets, identity/configuration reads
  or arbitrary exception/payload output. Report failing-before cases precisely.
- **Required tests:** isolated new fixture command, its focused pytest entry,
  existing probe/room/reward diagnostic/wire fixtures, compile and diff checks.
- **Forbidden overlap:** production files, existing fixtures, all contracts,
  C#, pins, docs and headless implementation. Return defects to packet `15`.

All implementation workers preserve public contracts, use a focused local
commit and return outcome, commit/files, commands/results, assumptions, risks,
model/effort and available aggregate numeric usage/elapsed telemetry (otherwise
`unavailable`). No prompts, transcripts or hidden reasoning are retained.
Workers must not operate/install the game or bridge, access real endpoints,
profiles/saves/credentials, change Cloud, push, or perform destructive Git work.
The coordinator owns integration, source bindings, documentation and any later
live campaign. Parsing consolidation and event identity redesign are deferred
until separately bounded evidence justifies them.

### R0I-MAP-LIFECYCLE-18 — Characterize map completion at the production seam

- **Status:** implementation commit `889cc5e` was independently rejected and
  is not integrated. Extracting the predicate changed native property-sampling
  order while its pure tests did not exercise `Read`; the accepted production
  reader and artifact therefore remain unchanged. Static findings are retained
  in the execution ledger for a later real semantic-repair packet.
- **Allocation:** Terra/high implementation; independent Sol/high review.
- **Dependencies:** the completed `R0I-LIFECYCLE-STUDY-16` static review and
  accepted current map reader/action contracts. Independent of packets `15`
  and `17` because ownership and semantics are disjoint.
- **Exclusive ownership:**
  `src/Sts2AgentBridge/Adapters/Public/PinnedPublicMapDecisionReader.cs`, new
  `tests/Sts2AgentBridge.Tests/Public/MapLifecycleTestSuite.cs`, and the single
  suite-registration addition in
  `tests/Sts2AgentBridge.Tests/Program.cs`, all below `bridge/Sts2AgentBridge/`.
- **Objective:** expose the existing production map completion/readiness
  predicate through a minimal pure internal test seam and freeze its transition
  behavior. Do not change that predicate in this packet. In particular,
  accepted destination plus closed map currently completes independently of
  `IsTraveling`; characterize this as existing behavior, not a proved defect.
- **Acceptance:** tests cover no accepted destination plus closed map; accepted
  destination with open/traveling, closed/traveling, and closed/not-traveling
  map; missing run/map; inspection reopening; a subsequent destination and
  changed run identity where expressible without inventing production state.
  Repeated reads remain passive and do not touch action reservations. The seam
  receives only already sampled primitive/public candidate inputs and is not
  added to the wire or policy view. Current behavior, candidates, hashes,
  action identity, caps and services remain byte/semantically unchanged.
- **Required gates:** full C# test/build/surface/package/reproducibility gates
  against the pinned assemblies, plus relevant Python map/run/wire fixtures,
  compile and diff checks. The coordinator verifies exact artifact/source
  identity before acceptance; no live claim follows from these tests.
- **Forbidden:** map action-applier edits, room/reward/controller changes,
  completion tightening, new game API members, asynchronous wait helpers,
  Harmony/AutoSlay, wire/vector/schema/policy/package changes, other tests,
  headless sources and shared docs. A real semantic repair requires a later
  source-backed contract packet and bounded live acceptance.

## 13. Approved explicit phase-entry follow-up

The user's subsequent “proceed” authorizes this narrow host-only increment from
clean `ece2092`. Its purpose is to remove avoidable manual setup when a bounded
campaign begins at a fresh visible reward or map boundary. It is **not** crash
recovery, action replay, automatic phase detection, save-game resume or adoption
of an earlier controller's uncertain mutation.

The bridge has no durable run/incarnation identity, controller lease, commit
sequence or retry idempotency key. A transparent resumable controller would
therefore require a new wire contract and retained live journal. Neither is
authorized here. The lean contract is explicit phase entry: the operator names
the currently visible phase, and that phase's existing client freshly validates
its own ready decision before the first POST. Waiting, complete/cached,
unsupported, malformed or mismatched entry state fails closed without probing a
different phase. D49 remains controlling: no failure or uncertain request grants
continuation or retry authority.

### Frozen phase-entry contract

- The existing 14-argument `apply_run_live.py` invocation and its exact success
  result remain unchanged and mean combat entry.
- One optional pair, `--entry-phase combat|reward|map`, may be supplied. Explicit
  `combat` is byte-for-byte equivalent to omission. No auto-detection or fallback
  is allowed.
- `reward` entry skips the unobserved combat, directly invokes the existing
  reward runner, waits for map readiness, and invokes the existing map runner.
  `map` entry directly invokes the existing map runner. These direct entry
  runners, not preliminary cross-phase scans, validate fresh readiness.
- The partial prefix consumes destination slot 1. Every later reconciled map
  selection, including a post-room map selection, consumes another slot. The
  invariant is `reconciled map selections <= floor_limit <= 3`. Subsequent
  complete floors use the existing combat/reward continuity, room context and
  fail-closed rules.
- Default/combat output remains the existing `r0i_bounded_run`. Reward/map entry
  uses `r0i_bounded_run_entry` with the existing providers, limit, floors,
  readiness, terminal-combat, room-handoff and termination concepts plus:
  `entry_phase`, `processed_floor_count`, truthful `completed_floor_count`, and
  `entry_prefix`. The prefix has exactly `floor_number`, `destination_kind`,
  ordered `observed_phases`, ordered `unavailable_phases`, `combat`, `reward`,
  `map`, and `readiness`. For reward entry, combat is `null`; for map entry,
  combat and reward are `null`. No outcome, continuity or action is inferred for
  an unavailable phase.
- `floors` contains only fully observed and reconciled combat/reward/map triples,
  numbered from logical floor 2 after a partial prefix; `readiness` remains
  one-to-one with those full floors. Prefix readiness stays in
  `entry_prefix.readiness` with the existing three keys. Direct entry attempts
  are zero; reward-to-map wait attempts retain their actual count.
- `processed_floor_count` is exactly the number of accepted-and-reconciled map
  selections charged to this invocation, including prefix and post-room map
  selections. `completed_floor_count` counts only entries in `floors`; the
  partial prefix is never complete. Map and aggregate action totals count each
  reconciled map selection exactly once and otherwise derive exactly once from
  successfully completed existing component records. Reward, map and room keep
  their current reconciliation rules; combat keeps its existing
  `already_applied` handling without adding any new inference.
  `termination.after_floor` retains the existing reason-specific semantics with
  logical numbering that includes prefix slot 1.
- Existing per-component action, round, deadline, stale/no-mutation retry,
  destination, room and transport bounds remain unchanged. No new retry exists.
  Phase-specific explicit rejection/idempotency outcomes retain each current
  client's behavior; no new cross-phase retry or continuation is added.
  Ambiguous transport/HTTP/receipt results, cancellation or failed
  reconciliation stop immediately.
- This host summary is not a bridge wire DTO, headless state, training encoding,
  replay record, persisted checkpoint or retained live artifact.

### R0I-PHASE-ENTRY-19 — Implement explicit fresh-boundary entry

- **Allocation/risk:** Sol/high in a persistent project worktree; high-risk
  mutating orchestration join. No Ultra worker.
- **Dependencies:** accepted `apply_run_live.py`, granular combat/reward/map/room
  clients, D47–D50, and live evidence through `ece2092`.
- **Exclusive ownership:** `bridge/Sts2AgentBridge/tools/apply_run_live.py`,
  `apply_run_live_fixtures.py`, and `bridge/Sts2AgentBridge/README.md`.
- **Deliverable:** implement the frozen optional entry phase with the smallest
  shared state-machine change. Preserve the default path and avoid duplicating
  granular client transport, parsing, action selection or reconciliation.
- **Acceptance:** old arguments/default JSON unchanged; explicit combat equals
  default; reward/map limit-1 prefixes are truthful partial floors with zero
  calls to unavailable phases; prefix accounting caps reconciled map selections;
  later ordinary floors retain player continuity; supported-room context binding,
  second-room/unsupported destinations, defeat and floor-limit outcomes retain
  current behavior; malformed/non-ready entry fails before POST and never falls
  back; no accepted action is double-counted; credential cleanup remains exact.
- **Required validation:** updated run fixtures; all established probe, reward,
  map, room, combat, floor, run-wire, transport and diagnostic fixtures; focused
  `tests/backends/live` and `tests/differential`; compile and diff checks. The
  coordinator runs the full repository suite after integration.
- **Forbidden overlap:** all C#, wire DTOs/vectors, granular client files,
  independent packet `20` files, verifier/package/policy pins, headless code and
  shared decision/status docs. Any necessary contract change stops for
  coordinator review.

### R0I-PHASE-ENTRY-TEST-20 — Independent actual-client gate

- **Allocation/risk:** Terra/high in a separate persistent project worktree.
- **Dependencies:** the frozen contract above. Implementation may begin from
  `ece2092`; final execution waits for reviewed packet `19` integration.
- **Exclusive ownership, new:**
  `bridge/Sts2AgentBridge/tools/apply_run_entry_wire_fixtures.py` and
  `tests/backends/live/test_apply_run_entry_wire_fixtures.py`.
- **Deliverable:** an independently authored fake connector/clock gate through
  the actual run and granular client entry points. It must use literal request
  oracles and must not reproduce or patch around the production state machine.
- **Acceptance:** exact request order and counts for combat equivalence, reward
  entry and map entry; prefix budget and action totals; delayed later-combat
  readiness; supported room binding; defeat; unsupported destinations; waiting,
  cached/complete, malformed and unsupported entry bodies; rejected/uncertain
  POST with no retry or later POST; all sockets closed, sent buffers and copied
  credentials zeroed, bounded canary absence from stdout/stderr. The unchanged
  base must fail for the missing phase-entry surface, not a harness defect.
- **Required validation:** isolated fixture and pytest wrapper, updated packet
  `19` fixtures, existing actual run-wire and bounded transport gates, focused
  live-parser/differential tests, compile and diff checks.
- **Forbidden overlap:** all production and existing fixture files, C#, wire,
  pins, docs, headless code, real sockets, identity/configuration/profile reads.
  Report production defects to packet `19`; never normalize them in the harness.

### R0I-PHASE-ENTRY-REVIEW-21 — Integration and live gate

An independent Sol/high read-only review must verify default-result identity,
truthful partial-floor accounting, exact destination/action caps, no fallback,
no mutation after uncertainty, room context/replay behavior, cleanup and the
independent negative control. The coordinator then runs all focused and broad
regressions. Only after acceptance may the coordinator use the user's current
thread-level standing authorization for one bounded Profile 3 campaign at a
fresh reward or map boundary, with the existing three-destination and 30-minute
caps. This plan does not itself create or preserve live authority. No retained
raw data or journal is created.
Normal quit, exact quarantine, clean unmodded launch/quit, purge and final
base/listener checks remain mandatory.

Both workers preserve existing public contracts and produce one focused local
commit unless a correction commit is safer. Their reports must include outcome,
commit, files, commands/results, contract assumptions, risks/blockers, model and
effort, and available aggregate numeric token/elapsed telemetry (`unavailable`
when absent; never estimated). Workers must not launch or operate the game,
install the bridge, access endpoints/credentials/profiles/saves, change Steam
Cloud, push, or perform destructive Git operations. Live work remains
coordinator-only.
