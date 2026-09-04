# Next increment: reliable composition and usable headless experiments

- **Date:** 2026-09-04
- **Planning baseline:** `57a421440dd1dc6b879f91d42db7a63ac575d359`, on
  `codex/phase1-parallel-integration`; contains planning baseline `d93395c`.
- **Status:** accepted for execution by the user's subsequent “execute the
  plan” request. Sections 4–6 offline packets and bounded coordinator acceptance
  are active from clean `cc2060ce1ffbb615ad5c42faaa621a56bbe5c062`. Event work
  remains investigation-only; retained real data and optional Section 7 remain
  outside this increment. No automatic evidence promotion is authorized.
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
