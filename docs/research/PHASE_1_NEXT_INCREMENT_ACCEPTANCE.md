# Next-increment execution and acceptance

- **Started:** 2026-09-04, following the user's “execute the plan” request.
- **Integration branch:** `codex/phase1-parallel-integration`.
- **Verified clean starting commit:** `cc2060ce1ffbb615ad5c42faaa621a56bbe5c062`,
  containing `d93395c`; no assumption about `origin/main` was made.
- **Plan:** [PHASE_1_NEXT_INCREMENT_PLAN.md](../PHASE_1_NEXT_INCREMENT_PLAN.md).
- **Starting automated evidence:** 829 repository tests passed at the preceding
  acceptance checkpoint. New packets are not accepted merely by dispatch.
- **Live state:** no active campaign at dispatch. The preceding campaign ended
  with verified cleanup and a clean base-game launch/quit.

The user approved the recommended first increment, not retained live data,
optional encoder/dataset work, a C# event repair, training, new game surfaces,
remote writes or direct profile/save access. Ordinary coordinator-only live
checks remain covered by standing authorization. Implementers operate only in
isolated project worktrees with exclusive paths; coordinator owns shared docs,
contracts, integration, pins, artifacts, and all live operation.

## Packet state

| Packet | Allocation | Current state | Ownership |
| --- | --- | --- | --- |
| `R0I-ROOM-CONTEXT-08` | Terra/high | Integrated `9a03c06` | Room client and its fixture file |
| `R0I-COMPOSE-09` | Sol/high | Integrated `cb3b08a`; transcript join accepted | Run client and its fixture file |
| `R0I-WIRE-INTEGRATION-10` | Terra/high → Sol/high | Integrated through `ab4ff5d` | New actual-client transcript fixture |
| `R0I-EVENT-STUDY-11` | Sol/high | Complete; retain D47 | No write ownership |
| `R0I-ACCEPTANCE-TOOLS-12` | Terra/high → Sol/high | Integrated through `de01074` | New acceptance tool and fixtures |
| `R0I-COMPOSE-LIVE-13` | Coordinator | Bounded campaign closed; full chain unobserved, rest checks passed | Sequential live campaign and evidence |
| `H5-ARTIFACT-01` | Terra/high → Sol/high | Integrated through `df55c93` | New reporting module and tests |
| `H5-CLI-02` | Terra/medium | Integrated through `6372c36` | New CLI, tests and sample config; explicitly reassigned lazy public exports |
| `H5-METAMORPHIC-03` | Sol/high | Integrated `b533caa` | New conformance and matched-panel tests |
| `H4-EVIDENCE-03` | Sol/high | Integrated `ecac394` + `20eeaf7`; contract frozen | New evidence module/tests and preregistered case spec |
| `H4-GOLD-04` | Sol/high | Integrated `6927878` | New gold evaluator and tests |
| `H4-CORPUS-05` | Terra/high | Integrated through `951da15` | New corpus codec and tests; synthetic data only |
| `H4-GOLD-ADAPTER-06` | Terra/high → Sol/high | Final privacy-fixture correction/review | New capture-off gold adapter and fixtures |

Exact owned paths and acceptance gates are defined in the plan and copied into
the implementation prompts. No overlapping production ownership was assigned.
The implementation tasks use persistent worktrees; the event study is an
internal read-only agent. The coordinator will release dependencies as soon as
they are reviewed and integrated, without waiting for unrelated packets.

## Contract and evidence decisions

- Existing `headless_v0`, wire, trajectory, state/RNG/snapshot and D47 lifecycle
  contracts remain frozen. New artifact/evidence consumer formats receive
  independent review before dependent implementation is dispatched.
- Benchmark repetition identity is `(repetition_index, trajectory_id)`; seeds
  and trajectory IDs remain unchanged, with exclusive repetition directories.
- Synthetic fixtures, live-observed transient acceptance and separately admitted
  retained differential cases remain distinct. No backend-wide fidelity claim.
- All live payload/control bindings stay transient. No real corpus collection
  or retention is approved by this execution request.

## Validation, review and telemetry

### Accepted action-context join

- `08`: worker `39de9c8d0a9f439cff786abed02999a51650ba16`, integrated
  `9a03c06c412a7c7d681670870599e757ab879c60`. Complete two-file diff and
  independent Sol/high review passed. Coordinator: 21 room, 14 then-existing
  run fixture groups and 81 wire/differential regressions passed. Independent
  review added 24 synthetic malformed/replacement/completion probes.
- `09`: worker `7366a94d2e597caf5e2789a2a615316511a3ef03`, integrated `cb3b08a`.
  Complete two-file diff and independent Sol/high review passed. Coordinator:
  16 run, 21 room fixture groups and 18 wire tests passed. Independent review
  added six malformed preflights, three exception/cleanup checks and an actual
  room/preflight positive join: two room actions, two map actions, two combat
  calls, one completed floor. Continuation combat is not another completed floor.
- Evidence is **fixture-tested**, not live-demonstrated. Room expectation is a
  local optional keyword-only `(screen_kind, room_ordinal)` tuple. Ready-room
  mismatch rejects before POST; standalone behavior and post-action checks
  remain. No C#, wire, cap, replay or provider changes. `10` and `12` now consume
  the accepted dependency commits for their final integration cases.

### Event investigation

`11` ran the existing C# test seam in a disposable environment: 16 room tests
and two additional production-seam cases passed. Evidence is
**production-backed synthetic**. Unchanged accepted projections stay pending;
A → B → A does not authorize replay. Inspection maps suppress room actions;
disappearance does not reset replay identity. Accepted same-event embedded
combat can complete only while the accepted evidence remains. Observing an
unaccepted B or an unsupported overlay before embedded combat conservatively
returns waiting. These are not new live reproductions of the historical timeout.

The allowed public surface has no authoritative event-step or exit marker.
Keep D47 and fail-closed event behavior; historical Baths timeout cause remains
unproven. A future identity repair would require a separately accepted contract
brief covering readers/appliers, reservation/replay, wire/parsers/vectors and
full artifact/live gates. No production edit or new C# packet is authorized by
this study, and it does not block rest composition.

### Corrections before acceptance

- `12` candidate `09ceefe` rejected: weak original-state parsing could allow a
  dangerous/wrong-kind action; nonfinite deadlines and invalid-config cleanup
  had gaps; callback exceptions could leak text; partial invented aggregates
  were labelled valid. Same worker corrects the same two owned files and adds
  adversarial fixtures. No integration or model escalation.
- `H5-ARTIFACT-01` candidate `f70e658` rejected despite 46 focused/shared tests
  passing: writer/loader accepted contradictory trajectory metadata, a valid
  trajectory from different seeds under a pasted configuration, and impossible
  repetition interruption/unstarted combinations. Same worker adds semantic
  cross-binding against existing trajectory data and maintained negative tests.
  The experiment contract is not frozen and CLI remains dependency-blocked.

### Aggregate telemetry

Observed task-turn durations: `08` 139195 ms, `09` 173918 ms, first `12` attempt
217560 ms, first artifact attempt 403081 ms, evidence attempt 427329 ms.
These are per-turn elapsed values, not total project time or performance
benchmarks. Token usage and other unavailable metrics: `unavailable`.
No unavailable metric is estimated; no prompts, transcripts or hidden reasoning
are requested or retained for telemetry.

### Evidence and maintained headless tests

- Evidence worker `905d34e` integrated as `ecac394`; a separately reviewed
  coordinator hardening `20eeaf7` normalizes oversized JSON integer failures
  without changing the schema/spec. Complete diff review, 206 coordinator
  differential/wire/reward-rule tests, independent 187 tests and 166 additional
  synthetic rejection cases passed. Frozen case spec SHA-256:
  `41ced248e52ca27e42d6318d63568f271edd605be3365afffd92c5e78a896a28`;
  schema SHA-256:
  `b797e69c160179795d3ed3cab9c66b0aabc4e4bd535af36c5a9d72349c428380`.
  Field correctness and temporal correspondence remain evaluator/adapter/review
  responsibilities. External review objects are trusted assertions, not proof
  against a dishonest caller. Gold and corpus consumers were released immediately.
- Metamorphic worker `4a9479c` integrated as `b533caa`. Complete diff and
  independent review passed; coordinator conformance/panel run: 91 passed in
  87.20 s. Independent new tests: 25 passed in 70.66 s. These include 24 generated
  cases and a twelve-episode full serial/spawn × two-collector-seed panel.
  Runtime is material but bounded; passing demonstrates structural consistency,
  not target-game fidelity. Unexpected exceptions retain a bounded reproducible
  prefix, not a generally minimized counterexample.
- Broad suite after context/evidence integration, before the new metamorphic
  tests: **910 passed in 37.98 s**.

### Explicit experiment provenance boundary

Existing trajectory streams do not contain independently verifiable scenario,
settings or game/policy/collector seed declarations. The coordinator approved
keeping these as exact caller-declared, manifest-bound experiment conditions.
The envelope must cross-check obtainable trajectory ID/pins/count/decision/
completion facts and declared budgets; it must not label decision hashes as
snapshot hashes or claim it can prove a dishonest producer's seed declarations.
CLI will pass its actual collector configuration directly. No private run-ID
derivation, producer schema change or live-world reconstruction was authorized.

### Further review and model escalation

- Transcript candidate `39f8737` rejected for a vacuous canary assertion and
  transport-failure cases bypassing the run orchestrator. Same Terra/high task
  adds actual captured-output canaries and whole-composition failure tests.
- `12` correction `35717c2` still accepted boolean/float summary schema versions
  and leaked numeric overflow exception types; its callback deadline contract
  also needed to state cooperative versus bounded-hook behavior. Escalated
  **Terra/high → Sol/high** for these reproduced repeated validation gaps.
- Artifact correction `dc02394` passed 51 focused/shared tests but still allowed
  an interrupted episode inside a batch falsely labelled not interrupted,
  followed by another repetition. Escalated **Terra/high → Sol/high** for this
  repeated stop-after-interruption mismatch. The declared-config limitation is
  accepted and is not the reason for escalation.

### Live preparation only

No campaign installed or launched yet. Read-only preflight confirmed game
absent and port closed (the sandbox initially denied process inspection; the
supported guard passed with technical escalation). Exact existing package and
assembly hashes remain those of the preceding accepted artifact. Fresh package
verification passed two entries; forbidden-surface check passed 11 routes and
1,063 method bodies. Base verification passed 429 files, zero overlay files,
SHA-256 `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Python consumer changes do not silently repin the C# artifact or old inventory.

### Accepted second integration wave

- Acceptance tool chain `09ceefe`, `35717c2`, `4e34ce7` integrated through
  `de01074`. Complete diff and independent review passed; coordinator seven
  acceptance, 21 room and 16 run fixture groups passed. Acknowledgement hooks
  are explicitly cooperative and must bound their own waits. The room summary
  validates its complete producer structure; run aggregates deliberately say
  `run_result_unvalidated` and do not certify history.
- Transcript chain `0f006ef`, `39f8737`, `ad59031`, `cf0d04c` integrated through
  `ab4ff5d`. Eight transcript, 16 run, 21 room and 18 wire parser tests passed.
  Final independent review passed real-orchestrator failures, the single
  captured suite execution and four maintained one-shot leakage mutations.
  A third escalation, **Terra/high → Sol/high**, followed a repeated canary
  coverage gap; length of work was not the reason.
- Artifact chain `f70e658`, `dc02394`, `5728075` integrated through `df55c93`.
  Complete diff and independent review passed: 68 coordinator tests plus eight
  independent adversarial cases, including interruption after a completed
  collector boundary. Caller-declared config trust remains explicit.
- Gold evaluator `51fb215` integrated as `6927878`. Complete diff and independent
  review passed; 267 coordinator regressions and 249 independent tests plus 135
  synthetic probes passed. The five named field findings use production gold
  rules with pre-only scaffolding, not post-observation reconstruction. This is
  synthetic/fixture evidence, not a live match or retained admission.
- Broad repository regression after artifact/gold/metamorphic integration:
  **1,023 passed in 109.38 s**. No throughput claim is made.
- CLI and capture-off gold adapter were dispatched immediately from `6927878`.
  CLI review requires bounded input reads, all identifier checks before backend
  creation, actual received-result interruption evidence and seed-preserving
  serial/spawn comparison. To meet help-without-optional-imports, coordinator
  explicitly reassigned `game/__init__.py` and new `tests/test_lazy_public_api.py`
  to that worker, preserving all canonical public symbols. Entry points/docs
  remain coordinator-owned.
- Corpus review rejected unbounded reads and symlink/directory races. Corrections
  anchor directory descriptors, use exclusive private writes, bound reads and
  preflight aggregate bytes. A final FIFO fix rejects special files without
  blocking; its subprocess test needs separate startup/operation deadlines.
- Gold adapter's first candidate `41f9fba` is rejected pending a fixed-verdict
  output projection and actual captured-output canary tests. The evaluator's
  full sanitized record is still too much data for this capture-off CLI.

Additional observed task-turn durations (ms): acceptance corrections 282959 and
205943; transcript join/corrections 95505, 70504 and 151098; artifact final
154858; metamorphic 471392; gold 338572; corpus 250586, 155935 and 34847;
CLI initial 311405; adapter initial 431835. Unavailable totals/tokens remain
`unavailable`; these are not benchmark timings.

### Current bounded live campaign

Installed the exact previously verified artifact at 16:00:43 UTC on 2026-09-04,
from integration source state `ab4ff5d`. DLL SHA-256
`a586aa99b9deeeb04b22596340dcccd0c6894b59db27625dfa1a1a8c2508c285`;
package SHA-256 `c97f3a0cd094523c769065fc921c3758569575c8dd5e754c5d2597ab7ee5a595`.
Fresh stopped guard, configuration shape/hash, 429-file base identity and
two-file overlay verification passed. Direct UI showed Profile 3 and one mod;
authenticated menu probe passed three routes. No Cloud setting was changed.
Gameplay is capped at 30 minutes with at most three accepted destinations;
no route farming. Resumed rest is available for the inspection-map check.
Campaign ended at 16:10:08 UTC, including cleanup, within its 30-minute ceiling.

- **Live-demonstrated:** inspection-map room suppression and exactly one stale
  action rejection with `mutation_state=none`; helper returned
  `inspection_map_stale_rejection_verified`. Closing the inspection map left
  the original rest choice available. A separate expected-context-bound rest
  controller then completed heal and literal proceed, returning
  `expected_context_rest_complete` / `room_result_valid`, two accepted actions
  and 21 checked routes. Direct UI confirmed the completed foreground map.
- **Unobserved:** the full combat → reward → map → rest → map → ordinary-combat
  composition. The resumed rest's next connected destination was an elite, not
  the required ordinary combat. No destination was selected, no run was farmed
  or restarted, and no combat/reward or gold-conformance case was attempted.
  This does not promote the full `13` chain or gold adapter to live-demonstrated.
- The coordinator wrappers were independently reviewed by exact source hashes
  using only mocked checks: inspection
  `fe094ff1925f5c291c59865043bcbdab0fdc9c8c5f37e5dd723203343a5edd71`
  (seven cases) and expected-context rest
  `d8c24f77bbc561835a9e48ed4d6096fa638b3603638bc6ae364f4d14e8e393a6`
  (six cases). A run-summary wrapper was reviewed but never invoked live.
  Original snapshots, bindings and receipts stayed in process memory; only
  fixed codes/counts were emitted. No raw dataset or player scalars retained.
- **Cleanup passed:** normal save/quit and game exit, stopped process/port guard,
  exact quarantine, 429-file base verification with zero overlay, clean base-game
  Profile 3 menu launch with no mod indicator and port closed, normal quit,
  stopped guard, purge of four campaign-generated files including credential,
  and final unchanged base/zero-overlay verification. No game/listener or
  installed bridge remains active. Build/package outputs are preserved.
- Steam Cloud was not changed; no unexpected enabled/syncing state was observed.
  No fresh Cloud-idle or settings-inspection claim is made. Only normal Profile 3
  in-game mutations occurred; no direct profile/save filesystem access.

### Offline consumer integration and final corrections

- Corpus worker chain `f8bb0b1`, `8f0299e`, `dadc25d`, `bf7b3b7` integrated as
  `0bb636e`, `ad8600a`, `5186955`, `951da15`. Full diff/ownership and independent
  review passed, including real synthetic directory/symlink/FIFO races.
  Coordinator differential/wire/reward regression: **225 passed in 12.64 s**.
  Independent focused: 19 passed; the FIFO operation rejects promptly after
  separate bounded startup. An initial two-second whole-process test timed out
  during imports, then was corrected to distinguish startup and operation.
- CLI worker chain `d60e292`, `1752518`, `f8a060d` integrated as `9759eae`,
  `9ff66a1`, `6372c36`. Full diff and independent review passed. Coordinator
  CLI/API/reporting/rollout/benchmark: **50 passed in 8.75 s**. Independent eight
  CLI/API tests pass; all 95 public symbols/order/provider identities are unchanged.
  The initial reader race was fixed with a no-follow/nonblocking opened descriptor,
  regular-file validation and bounded reads. Received-result SIGINT, trusted reload,
  pending/unstarted distinctions and zero remaining workers passed.
- Coordinator registered `sts-headless` and installed the editable project using
  no dependencies/build isolation/network resolution. Installed help, sample
  `run`, `benchmark` and trusted-hash `validate` passed. Both small samples truthfully
  reported one budget-exhausted episode, no pending or unstarted work; these are
  smoke tests, not throughput measurements.
- Adapter correction `619c1f2` fixed the production output/post-shape/cancellation
  findings but repeated the uncaptured-execution canary gap. Independent first-recv
  leakage still escaped while fixtures passed. Fourth escalation:
  **Terra/high → Sol/high**, for this reproduced privacy-test defect. Maintained
  receipt/POST-failure zeroization/closure cases are also required before acceptance.

Additional observed task-turn durations (ms): corpus timeout-test correction
42966; CLI corrections 202967 and 68896; adapter first correction 386424.
Unavailable aggregate tokens/totals remain `unavailable`.

Post-corpus/CLI integration full repository regression: **1,050 passed in
104.59 s**. Coordinator documentation/entry-point diff received independent
read-only review with no blocking findings.
