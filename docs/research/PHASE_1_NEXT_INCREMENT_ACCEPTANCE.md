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
| `R0I-COMPOSE-LIVE-13` | Coordinator | Campaigns closed; rest checks passed; follow-up reward-response failure, full chain open | Sequential live campaign and evidence |
| `H5-ARTIFACT-01` | Terra/high → Sol/high | Integrated through `df55c93` | New reporting module and tests |
| `H5-CLI-02` | Terra/medium | Integrated through `6372c36` | New CLI, tests and sample config; explicitly reassigned lazy public exports |
| `H5-METAMORPHIC-03` | Sol/high | Integrated `b533caa` | New conformance and matched-panel tests |
| `H4-EVIDENCE-03` | Sol/high | Integrated `ecac394` + `20eeaf7`; contract frozen | New evidence module/tests and preregistered case spec |
| `H4-GOLD-04` | Sol/high | Integrated `6927878` | New gold evaluator and tests |
| `H4-CORPUS-05` | Terra/high | Integrated through `951da15` | New corpus codec and tests; synthetic data only |
| `H4-GOLD-ADAPTER-06` | Terra/high → Sol/high | Integrated through `f95aa85`; zero-POST ineligibility live-observed, eligible comparison unobserved | New capture-off gold adapter and fixtures |

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

### Final adapter acceptance

Worker chain `41f9fba`, `619c1f2`, `422ecf0` integrated as `c3cc554`, `b5913be`,
`f95aa85` after complete diff/ownership review. Final independent review passed
33 maintained checks, four separately injected first-receive leak mutations and
two transport-cleanup probes with real sockets blocked. Coordinator: **267
differential/reward/wire tests passed in 2.38 s**, plus 33 isolated fixture checks
from outside the repository using Python 3.11 with `-B -E -s -S` and no editable
installation/PYTHONPATH dependency. Final observed Sol task-turn duration:
177588 ms; tokens remain `unavailable`.

One eligible claim at most, exact receipt binding, fresh/stable post observations,
strict unrelated-reward preservation, cancellation and no mutation retries are
covered by mocked tests. Removed/reindexed selected rewards conservatively remain
unobserved. The full named proposal never leaves the adapter; only the narrowed
fixed verdict/identity projection is emitted. No eligible live invocation was
performed and no corpus admission or fidelity promotion occurred.

A stronger diagnostic forbidding *any attempt* to import optional RL modules
found an existing eager `game.analysis` namespace import. That is distinct from
the packet's no-optional-dependency requirement: isolated `-S` execution passes
all 33 checks with those packages unavailable. No unplanned analysis-namespace
refactor was added. The headless CLI's stricter no-import-attempt test passes.

The other twelve bridge fixture suites passed **122 named checks**. Together
with the gold adapter this is **155 checks across thirteen fixture suites**,
not live evidence. Compileall and diff whitespace checks passed.

### Milestone disposition

- Offline implementation and conformance-preparation milestones: reviewed and
  integrated. All eleven implementation workers returned accepted local commits;
  the event study is complete without production changes.
- Live composition acceptance remains **open/unobserved**, not complete. The
  bounded campaign produced the narrower rest/inspection evidence and verified
  cleanup; it did not offer the required ordinary-combat route. Gold live
  comparison is also unobserved.
- Event-to-map completion/root-cause investigation, target-game fidelity,
  retained live-case admission, optional encoder/dataset work, content expansion
  and training remain outside completed claims. Original synthetic comparator
  results remain 3 matches, 14 divergences and 2 unobserved cases.
- No remote writes occurred. The smallest next milestone is one eligible
  bounded live composition with a capture-off gold check when offered. Retained
  sanitized data still needs its separate exact authorization.

Final post-adapter repository regression: **1,050 passed in 99.81 s**.
Final compileall/diff checks and independent documentation consistency review
passed. A final stopped guard again reported no game process and no accepting
bridge port (three process samples, two port samples). The integration worktree
is clean after committing this acceptance update; no push or pull request.

## Follow-up campaign after the user's “continue” request

### Frozen setup and offline review

- Starting source: clean `300d230d5441c9e690e13bf3d56810258d43ccd5` on the
  same integration branch. No production implementation changed during this
  campaign. Existing implementation packet commits above remain unchanged.
- Exactly one coordinator operated the game. Two independent read-only
  reviewers checked the join; subsequent failure analysis also ran in parallel.
  No worker used live endpoints, installed files, or accessed profiles.
- Reused the unchanged reviewed DLL
  `a586aa99b9deeeb04b22596340dcccd0c6894b59db27625dfa1a1a8c2508c285`
  (202,240 bytes), manifest
  `498e815fc742e85112e43823b3b2e291e60efe03353a22e263d316e6fb67b971`
  (323 bytes), and canonical ZIP
  `c97f3a0cd094523c769065fc921c3758569575c8dd5e754c5d2597ab7ee5a595`
  (202,879 bytes). Fresh package, forbidden-surface (11 routes/1,063 methods),
  config, base and overlay checks passed. One verifier invocation initially
  rejected a relative manifest argument before verification; the absolute-path
  invocation passed before launch.
- Disposable capture-off join `combined_sanitized.py` SHA-256
  `acd39c86ef1de33a3ae06d36f170bbe214332c59298dc90741a7817283926a1e`,
  importing the previously reviewed `run_sanitized.py`
  `56f355d9eecb844fffc3a6484fbfac67e17d30d9997f75e949349d1153c763af`.
  Its initial syntax error was caught before any operation, corrected, then
  the exact final source received two independent passing reviews.
- The join uses the existing reward-ready callback, latches one gold attempt
  before invocation, obtains fresh credentials for ordinary reward handling,
  and leaves original controller counts/history unchanged. Only known zero-POST
  ineligibility or one bound claim with five passing fields permits continuation.
  Uncertain, rejected, divergent or cancelled claims stop. Adapter claims are
  reported separately, never fabricated into the reward controller's history.
- Frozen invocation: repository Python 3.11 with `-B -E -s -S`, fixed OS
  identity/UID 501, providers `heuristic`, `first-card`, `coverage`, `safe`,
  and `--floor-limit 2`. One setup UI destination plus at most two controller
  destinations fits the total three-destination allowance. Existing combat/
  action caps and a coordinator-enforced 30-minute gameplay ceiling remained.
- Offline checks: 8 run wire fixture groups and 33 gold adapter checks;
  7 coordinator synthetic join cases; two independent sets of 8 mocked join/
  operation cases. These cover one-attempt behavior, eligible/ineligible paths,
  uncertain/rejected/divergent stop, credential freshness/zeroing, socket closure,
  canaries and cap enforcement. Full regression: **1,050 passed in 163.27 s**.
  These are fixture/synthetic results, not successful live composition.

### Live result and claim boundary

Steam launch began at 16:30:57 UTC on 2026-09-04. The menu visibly showed
Profile 3, Ironclad A0 was chosen through normal single-player setup, and exactly
one mod was loaded. Authenticated main-menu health/manifest/screen checks passed
(three routes). Steam Cloud settings were not accessed or changed; no unexpected
enabled/syncing state was observed.

The prior dedicated test run was ended through the normal Abandon Run UI,
which records a loss; one fresh run was started. Its initial choice/reward was
handled normally, then one ordinary-combat map destination was selected in UI.
No other profile or save filesystem was accessed. No restart farming occurred.
The public route did not offer the required rest sequence inside the total
three-destination allowance.

The reviewed wrapper reached the first post-combat reward. The gold adapter
returned the fixed `reward_gold_claim_v1` summary with
`unaligned` / `unsupported_gold_amount`, correspondence `uncertain`, all five
verdicts `unobserved` / `not_compared`, the fixed omissions and `not_admitted`.
It issued **zero gold-claim POSTs**. This live-demonstrates only its conservative
prestate-ineligibility path, not an eligible effect comparison. Adapter source
identity was
`d952b4891362936e0a25daa4c12154c8c4ef18405becf6e40d3db5d447d4c64a`;
the emitted fixed spec/parser/contract/rule/content identities matched the
reviewed pins. No observed gold amount, player scalar, reward identity, raw
body, receipt/control ID, raw-body hash or named record was retained.

Ordinary reward resolution then stopped with `reward_action_response_mismatch`
(exit 4). The returned run summary was not available, so action totals and the
accepted reward prefix are **unavailable**, not estimated. No mutation was
retried and no further gameplay followed. There was one setup UI destination
and zero controller destinations; no rest handoff or next combat occurred.
The post-stop UI showed a completed-combat background and Proceed without the
reward modal. This does **not** prove accepted Proceed, complete reward handling
or absence of mutation from the failed request.

Two independent read-only investigations found that the same error covers
noncanonical/non-200 HTTP envelopes and any non-exact accepted/applied receipt,
including canonical rejected receipts. Final Proceed is only a hypothesis;
the discarded response cannot establish the action, rejection reason, HTTP
category or mutation outcome. One reviewer passed 9 actual-client synthetic
cases; another passed 6. Canonical rejections, 429/503 and malformed accepted
responses reproduce the code; accepted Proceed followed by waiting instead
reaches a separate post-state timeout. Failure cases did not retry and preserved
credential/request zeroing and socket closure. No C# repair is justified by
these facts alone. A narrow fixed-classification diagnostic packet was proposed
to the user; it is not implemented or silently added to the completed scope.

### Cleanup and ordering deviation

Normal Save and Quit returned to the modded Profile 3 menu. The coordinator
clicked Quit but initially missed its confirmation dialog. A stopped guard
reported `game_still_running`; nevertheless the next already-sequenced manager
call quarantined the exact overlay/configuration successfully. A second guard
still reported the game running. **This was a coordinator cleanup-order error,
not a passed stopped-before-quarantine gate.** No further gameplay or bridge
actions were attempted. The visible Quit dialog was then confirmed normally,
and `wait-stopped` passed with no process/listener (three process/two port
samples). Future cleanup calls must be gated on the observed successful stop
result, not merely sequenced after the check.

The base verifier then passed with 429 unchanged files, zero overlay and SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
A clean Steam launch visibly reached the unmodded Profile 3 menu; the bridge
port was closed while the game ran. Quit and its confirmation completed
normally, then the stopped guard passed. The exact quarantined campaign was
purged: four generated bridge/manifest/configuration/credential files removed,
campaign state absent. No save or base-game file was removed; the bridge can
be rebuilt from source, and its purged credential is not retained.

At **16:38:16 UTC**, final base verification again passed (429 files/zero overlay,
same hash), and the final guard again found no game process or accepting bridge
port. The campaign is closed and cleanup verified, with the ordering deviation
explicitly preserved. Gameplay stopped well inside the 30-minute ceiling.

### Disposition

Full live composition and eligible gold comparison remain **open/unobserved**.
The ineligible gold guard was live-observed; ordinary reward response handling
has a newly observed, unclassified failure. Headless evidence and all accepted
implementation commits are unchanged; no target-game fidelity promotion or
retained corpus admission occurred. No model escalation or new implementation
worker was used for this follow-up. Aggregate tokens and reviewer elapsed-time
telemetry are `unavailable`. No remote writes occurred.

## Approved reward-diagnostic implementation

The user's subsequent “yes” approved `R0I-REWARD-DIAG-14`, defined in Section 11
of the active plan. Scope checkpoint `5d4fea9` follows clean `d958a0a`.
Implementation was initially assigned to one persistent Terra/high worktree task,
`01a06d4f-2517-7503-9ab0-e1a28c42198c`, with exclusive ownership of the reward
client and three new diagnostic/CLI/fixture files. Protocol/privacy and counter/
fixture design received independent read-only review. No other implementation
packet, game surface, C# repair or raw retention was added.

The app's task listing initially omitted this running task. Its existing
worktree and a read-only query of only task identity/model metadata resolved the
ID; supported task waiting/messaging then confirmed it active. No duplicate task,
model change to resolve that infrastructure issue, transcript extraction,
app-state modification or reset was used. A mistaken draft reference to a second
503 response was corrected: the existing exact envelopes are rate-limited 429,
retryable backend-unavailable 503 and nonretryable backend-fault 500.

This packet is now reviewed and integrated as recorded below, but not live-tested.
The previous campaign's failed action and mutation outcome remain unknown.

### First commit review and narrow ownership correction

The worker returned `fc9e44b` after one draft correction round. One independent
review accepted default compatibility and protocol classification after 13
additional probes, including eight actual-client default/opt-in transcript
comparisons. A separate review rejected acceptance: partial HTTP bytes followed
by cancellation escaped mutable-response zeroization, and the maintained
22-check suite did not detect disabled HTTP-response wiping. Actual multi-action
prefixes, the seventeenth-action boundary, CLI no-I/O failures and several
strict receipt cases also lacked maintained coverage, although 12 independent
ad hoc semantic cases passed. Those ad hoc results do not replace regression
tests. That first commit was not integrated by itself.

The same task was escalated from Terra/high to Sol/high for these reproduced
defects and repeated acceptance gaps. The coordinator explicitly reassigns
only `probe_live.py::_exchange` exceptional-exit buffer cleanup as a fifth
owned path. An independent design review requires preservation of successful
response ownership, existing exception translation/precedence and socket-close
behavior, including failures raised during cleanup itself. No transport,
retry, timeout, wire, C#, capability or live authority change is authorized.
The first implementation turn's reported duration is **622,036 ms**; aggregate
token usage is `unavailable`.

### Accepted integration and validation

The same worker returned the focused correction `531b887`, without rewriting
its first commit. The coordinator inspected both complete diffs, confirmed
exclusive ownership and default-contract compatibility, and integrated them
without semantic merge changes:

| Worker commit | Integrated commit | Outcome |
| --- | --- | --- |
| `fc9e44b5b112102bbf395f03daea858204b41be1` | `6e0cf8fd680d97b4892b1cbe4afc7eb10c76ce33` | Opt-in diagnostic recorder, reward seam and CLI |
| `531b887f7db1a9c02e231dad49687fecc4b3a29f` | `b77178f39477f0341583672cd834501509cfece0` | Exceptional-exit response cleanup, closed transport codes and maintained acceptance gates |

Only the five explicitly assigned Python tool files changed. Shared contracts,
ordinary CLI output, byte-exact receipt acceptance, deadlines, caps, replay
protections, C# sources, wire vectors, fixture identities and headless behavior
remain unchanged. The integration tree at `b77178f` exactly matches the final
worker tree; the accompanying coordinator documentation records D49 and the
new command without changing evidence levels.

Independent protocol/default-compatibility review accepted the opt-in seam.
Independent cleanup review passed **40** exception combinations and confirmed
the immutable final source hash. Independent fixture/privacy review accepted
the final **16 groups**, with additional adversarial checks of response wiping,
privacy-guard removal, exact request validation, post-acceptance cancellation,
`SystemExit` propagation, received canaries, cleanup exception precedence and
unknown-code redaction. No review accessed live data or changed source files.

Coordinator validation:

- Final `reward_action_diagnostics_fixtures.py`: **16 groups passed**, including
  multiple scenarios per group. These exercise actual client code, full literal
  request oracles, `2/1/1` and `2/2/1` prefixes, the 17-action cap, strict receipt
  forms, known 429/503/500 responses, malformed HTTP, partial-buffer failures,
  cancellation, no-I/O CLI rejection and deliberate privacy/transport mutants.
- Eleven existing isolated fixture suites passed **137 checks**: probe 26,
  turn 3, combat 5, floor 6, reward 6, room 21, run 16, actual run-wire 8,
  room-acceptance helper 7, decision providers 6 and gold adapter 33. Each used
  the repository interpreter with `-B -E -s -S`; all were rerun on integration.
- Full repository pytest passed **1,050 tests in 102.41 seconds** on the
  reviewed worker code. Production hashes were unchanged at final handoff;
  the final strengthened fixture was separately rerun. The integrated tree
  was verified equal to the final worker tree.
- Integrated `tests/backends/live` plus `tests/differential`: **242 passed in
  1.94 seconds**, with `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.` and
  `-p no:cacheprovider`. The worker independently passed the same 242 tests.
- Integrated `.venv/bin/python -m compileall -q game tests
  bridge/Sts2AgentBridge/tools` and `git diff --check` passed. Worker validation
  also checked Python 3.10 grammar and compilation of all five assigned files.

Reviewed Python source identities at `b77178f` (not live payload hashes):

| Tool file | SHA-256 |
| --- | --- |
| `apply_reward_live.py` | `502af7e33300ba6f4202817cae644148a2e565cdcf9bbe356d025435310c049b` |
| `reward_action_diagnostics.py` | `6e71a822dc1f6c1e0e874a553ab248b133121644256474da8243c5dfbfa9c39a` |
| `diagnose_reward_live.py` | `184d03da75e4d8d4048018955b9d7408a0d2fc1790a79e1a98373e5b495c9cef` |
| `probe_live.py` | `e550d1d20e48314d9203eee0af892341a6696e5f62ef30f2d5c4de90faa2de65` |
| `reward_action_diagnostics_fixtures.py` | `b98cd5ffca07ef30a9897b05a254cd2d7fa88ce0f7805a8cd1d91b54eb48ada7` |

The corrective Sol/high turn took **492,557 ms**. Summed implementation-turn
duration is **1,114,593 ms**, excluding coordinator/reviewer work; aggregate
token usage and coordinator/reviewer elapsed metrics are `unavailable`. This
packet used one evidence-based Terra/high → Sol/high escalation and no worker
Ultra allocation. Telemetry contains only aggregate numbers; no hidden reasoning
or prompt/transcript extraction was performed.

### Evidence and remaining live gate

`R0I-REWARD-DIAG-14` is **complete as an offline diagnostic packet**. Its tests
are synthetic/fixture evidence, not live demonstration or differential fidelity.
The recorder is trusted internal state, not a validator for arbitrary external
attribute mutation. Mutable-buffer wiping does not claim erasure of immutable
Python receive chunks. Neither diagnostic classification nor a receipt's
reported mutation field authorizes replay of an uncertain request.

No game was launched or operated, no bridge was built or installed, and no
endpoint, credential, profile, save or Cloud setting was accessed during this
packet. The last actual-game campaign's verified cleanup at 16:38:16 UTC above
remains the last live cleanup evidence; this offline turn added no installation
to remove. No push or other remote write occurred.

The smallest next milestone is a separately recorded, bounded coordinator
campaign using these reviewed diagnostics at a fresh, known reward boundary
while seeking the already scoped composed rest handoff. It must not retry the
previous uncertain action, broaden C# behavior, retain raw responses or silently
promote the open eligible-gold/full-composition gates to passed.

## Targeted transport simplification and lifecycle study

The user accepted a targeted simplification after comparison with
`zhiyue/sts2-rl-agent`. The coordinator froze packets `R0I-TRANSPORT-15` through
`R0I-MAP-LIFECYCLE-18` at `134fff3`/`a26db96`. No AutoSlay, Harmony, debug mode,
third-party source, new game surface or headless/training work was adopted.

`R0I-TRANSPORT-15` worker commits `06496dc` and corrective `1a4e9df` integrated
as `3c9363d` and `9d7a0ae`. They leave only two production files changed from
the packet base: `probe_live.py` and `apply_room_live.py`, with 51 insertions and
66 deletions. Their existing `_exchange` signatures, request builders/routes,
deadline/error/cap semantics, successful response ownership and retry behavior
remain unchanged. One private implementation now owns connection, send,
bounded receive and cleanup. Room partial responses inherit the accepted probe
zeroization and exceptional-close precedence.

`R0I-TRANSPORT-TEST-17` commits `c7a2f90` and `d907252` integrated as `8824d4f`
and `e187dab`. Coordinator composition found that the first test commit called a
nonexistent probe helper after its expected baseline failure; the same task
corrected the masked harness defect before acceptance. The final independent
gate uses the actual probe/room entry points, literal request oracles and no real
I/O. Its 29 checks pass on the integrated implementation; the unchanged base
fails specifically with `room_keyboard_interrupt_response_not_zeroed`.

Independent protocol/privacy review accepted the aggregate with no blocking
finding. It verified one receive loop, exact wrapper signatures and bytes,
connector/clock ordering, fixed failure categories, bounds, no retries, buffer
ownership/zeroization and primary-versus-close exception precedence. The bound
tests consume the configured numeric constants rather than separately pinning
their values; the reviewed production diff establishes those constants did not
change. Evidence is `bridge_fixture`, not live-observed.

The read-only `R0I-LIFECYCLE-STUDY-16` found no verified compatible AutoSlay or
WaitHelper replacement. Upstream helpers organize asynchronous waits but their
callers still choose nonauthoritative map/proceed predicates. Our synchronous
frame queue and snapshot-bound actions would need a separately designed async
ownership/cancellation contract. Event-step identity therefore remains governed
by D47 and fail-closed.

`R0I-MAP-LIFECYCLE-18` produced worker commit `889cc5e` and passed its C# test,
parity build, package and reproducibility checks, but failed the frozen surface
source projection as any unpinned C# revision should. Independent review found
the refactor was not strictly behavior-neutral: it eagerly sampled travel
properties that the existing closed-map path short-circuits before reading.
Its pure tests did not exercise the production reader, accepted-destination
recording or reservations. The commit was rejected and is **not integrated**;
no policy/package pin changed. Retained static facts only: the map reader stores
no run identity; a valid closed map plus retained accepted destination completes
before travel state is considered; missing run/map waits. Direct coverage should
be bundled with a future justified semantic repair and its artifact/live gates.

Coordinator integration validation passed 190 checks across 13 isolated bridge
fixture suites and 243 focused live-parser/differential tests. The pre-change
repository baseline passed 1,050 tests. The final integrated tree passed 1,051
tests in 100.92 seconds. No game was launched, bridge installed, live endpoint
or credential accessed, profile/save touched, or Cloud setting changed. No live
campaign was active and no cleanup was required.

No model escalation occurred. Workers used Terra/high. Reported implementation
turn durations were 309,785 ms for `15`, 356,584 ms for `17`, and 374,353 ms for
the rejected `18`; aggregate token counts were unavailable. Reviewer and
coordinator usage metrics were unavailable. No hidden reasoning, prompts or
transcripts are retained as telemetry.

## Bounded reward and ordinary-floor live campaign

The coordinator ran one bounded Profile 3 campaign at integrated source
`bbada1ac147d66f73f6f0ae8ea3a858a1ecee931`. The exact installed `0.8.0`
artifact identities were:

| Artifact | SHA-256 |
| --- | --- |
| `Sts2AgentBridge.dll` | `a586aa99b9deeeb04b22596340dcccd0c6894b59db27625dfa1a1a8c2508c285` |
| `Sts2AgentBridge.json` | `498e815fc742e85112e43823b3b2e291e60efe03353a22e263d316e6fb67b971` |
| `Sts2AgentBridge-0.8.0.zip` | `c97f3a0cd094523c769065fc921c3758569575c8dd5e754c5d2597ab7ee5a595` |

The reviewed host sources used by the campaign were `probe_live.py`
`5accc6da`, `apply_room_live.py` `e0bcacb8`, `apply_reward_live.py`
`502af7e3`, `diagnose_reward_live.py` `184d03da`, and `apply_run_live.py`
`eec89d24`. Raw-response logging and retained capture remained disabled.

### Sanitized acceptance results

- The exact game process and bridge listener were running, Profile 3 was
  visibly selected, and all three authenticated main-menu probe routes passed.
- At a fresh visible reward boundary, `diagnose_reward_live.py` passed with
  action category `proceed`: four exchanges attempted, four exact receipts
  accepted/bound, four actions reconciled, and the final receipt reported
  accepted/applied. The visible game advanced to the map.
- One legal map selection passed and reached an ordinary three-enemy combat.
  The standalone combat controller won in six rounds with 26 accepted actions.
- The following reward controller accepted four actions, claimed 13 gold,
  selected one offered card and reached the map; one further legal destination
  selection reached an ordinary combat.
- From that visibly ready combat, the composed runner passed one complete floor:
  16 combat actions, four reward actions, one map action, zero room actions and
  21 total. It reconciled victory, reward resolution and the next legal map
  destination, reached another ordinary combat, and stopped with
  `floor_limit_reached` as configured.
- An earlier invocation of the combat-oriented runner while the foreground was
  still a map failed closed at `combat_not_ready`; no controller destination or
  combat action was applied by that invocation. It is an entry-state mismatch,
  not a failed ready-combat composition result.
- The campaign used three controller destinations, the declared bound. No rest
  destination was offered, so combat/rest/combat and composed room handoff are
  `unobserved`, not failed or passed.

This promotes the fresh reward diagnostic and one ordinary
combat/reward/map/next-combat floor to **live-demonstrated**. Transport and
buffer-cleanup edge cases remain fixture evidence; this campaign did not force
an exceptional transport path. The historical discarded reward response
remains unclassified. No payload, credential, control ID, profile/save content
or differential corpus was retained.

### Teardown

The run was saved through the game UI and the modded game quit normally. The
runtime guard confirmed both process and listener stopped before the exact
installed state was quarantined. Base verification then passed with 429 files,
base SHA-256 `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`
and zero overlay files. A clean unmodded Steam launch visibly reached the
Profile 3 base menu without the mod indicator while `sample-base-port-closed`
passed. It quit normally; the exact quarantine was purged (four generated files).
Final base and stopped guards passed with zero overlay, no game process and no
listener. Steam Cloud was not changed and no unexpected sync state was observed.

No worker model escalation occurred in this campaign; live operation was
coordinator-only. Aggregate live token and elapsed-time telemetry is
`unavailable`.
