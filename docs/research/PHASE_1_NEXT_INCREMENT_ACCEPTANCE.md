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
| `R0I-COMPOSE-09` | Sol/high | Integrated `cb3b08a`; transcript join pending | Run client and its fixture file |
| `R0I-WIRE-INTEGRATION-10` | Terra/high | Dispatched baseline transcript; final context cases depend on 09 | New actual-client transcript fixture |
| `R0I-EVENT-STUDY-11` | Sol/high | Complete; retain D47 | No write ownership |
| `R0I-ACCEPTANCE-TOOLS-12` | Terra/high | First candidate rejected; focused correction active | New acceptance tool and fixtures |
| `R0I-COMPOSE-LIVE-13` | Coordinator | Waiting for reviewed 08/09/10/12 and artifact gates | Sequential live campaign and evidence |
| `H5-ARTIFACT-01` | Terra/high | First candidate rejected; semantic provenance correction active | New reporting module and tests |
| `H5-CLI-02` | Terra/medium | Waiting for accepted artifact envelope | New CLI, tests and sample config |
| `H5-METAMORPHIC-03` | Sol/high | Integrated `b533caa` | New conformance and matched-panel tests |
| `H4-EVIDENCE-03` | Sol/high | Integrated `ecac394` + `20eeaf7`; contract frozen | New evidence module/tests and preregistered case spec |
| `H4-GOLD-04` | Sol/high | Dispatched from `20eeaf7` | New gold evaluator and tests |
| `H4-CORPUS-05` | Terra/high | Dispatched from `20eeaf7`; synthetic data only | New corpus codec and tests |
| `H4-GOLD-ADAPTER-06` | Terra/high | Waiting for accepted evidence/evaluator | New capture-off gold adapter and fixtures |

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
