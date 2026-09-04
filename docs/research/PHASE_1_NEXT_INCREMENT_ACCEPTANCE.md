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
| `H5-METAMORPHIC-03` | Sol/high | Dispatched | New conformance and matched-panel tests |
| `H4-EVIDENCE-03` | Sol/high | Candidate `905d34e` in independent review | New evidence module/tests and preregistered case spec |
| `H4-GOLD-04` | Sol/high | Waiting for accepted evidence schema | New gold evaluator and tests |
| `H4-CORPUS-05` | Terra/high | Waiting for accepted evidence schema; synthetic data only | New corpus codec and tests |
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
are requested or retained for telemetry. No model escalation in this increment.
