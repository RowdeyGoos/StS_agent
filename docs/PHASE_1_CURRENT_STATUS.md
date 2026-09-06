# Phase 1 Current Integration Status

- **Status date:** 2026-09-06
- **Fresh-session handoff:** [Astra handoff](PHASE_1_ASTRA_HANDOFF.md)
- **Active bridge milestone:** `R0i`
- **Bridge version:** `0.8.0`
- **Protocol:** `live_probe_v0`
- **Pinned target:** Slay the Spire 2 `v0.107.1`, Steam build `23811903`,
  macOS arm64
- **Program disposition:** the project-owned bridge is the selected live path
  and has passed bounded live observation and control smokes; Phase 1 remains
  open and no full-run or near-optimal-agent claim has been made

This is the living status page for the full-game integration track. It records
what the current repository can do, what has actually been exercised in the
game, and what remains open. Exact requests, approvals, manifests, and
historical evidence reports remain preserved in their original documents; this
page supersedes their old point-in-time status statements without changing
their authorization scope.

## Active card-selection development — 2026-09-06

**Active Cheese test:** the unchanged reviewed package is installed with the
Cheese configuration and fresh state. User setup is pending at Room Full of
Cheese's initial untouched choices; no client has run in this campaign. The
[completion ledger](research/PHASE_1_CARD_SELECTION_COMPLETION_V1_ACCEPTANCE.md)
owns the new installed-state hash and required cleanup. The prior Smith campaign
is fully closed. Other native event card operations remain unsupported.

**Current live result:** the corrective Smith test passed on a fresh rest site:
parent2/2/2 and child2/2/2, including one upgrade effect and Proceed/map handoff.
Normal quit, quarantine, exact purge, unchanged base429/zero overlay, stopped/closed
and fixed absences passed by14:57:35 UTC. That Smith campaign is closed. The
[completion ledger](research/PHASE_1_CARD_SELECTION_COMPLETION_V1_ACCEPTANCE.md)
records the exact result and closed states. Ordinary single-card Smith upgrading
is live-demonstrated; Cheese exact-two remains awaiting a separate live test.

The user selected event card addition/removal/upgrade/transform support and
rest-site card upgrading, explicitly including multiple-card event selections
and exactly one card for ordinary rest upgrades. Development is isolated in
`card_selection_v1`; the nine accepted predecessors and old 0.8.0 sources remain
byte-exact. Read the [contract](PHASE_1_CARD_SELECTION_V1_CONTRACT.md),
[static evidence](research/PHASE_1_CARD_SELECTION_STATIC_RESULT.md) and
[acceptance ledger](research/PHASE_1_CARD_SELECTION_V1_ACCEPTANCE.md).

The shared pure core models all four operations with explicit minimum/maximum
counts, per-selection receipts, preview/confirmation modes, complete candidate
and deck witnesses, and exact effect reconciliation. Initial native entries are
Room Full of Cheese/Gorge (add exactly two of eight) and ordinary SmithCount=1
(upgrade exactly one). Native other-event removal/transform/multi-card upgrade,
scrolling and partial visible domains remain unsupported pending exact callsite
and effect proof. This does not change the currently accepted live package.

The functional component passed independent source review and its aggregate
gate, including actual C#/Python composition and two identical clean builds of
each native adapter. Its 40-file source inventory is frozen. Repository
regression for the functional component passed 1,192 tests. The separately
isolated [release composition](PHASE_1_CARD_SELECTION_RELEASE_V1_CONTRACT.md)
is now independently accepted, frozen and published for live testing. Four
production builds match; full repository regression passes 1,206 tests in
106.62 seconds. The complete aggregate passed, including 57 verifier mutations,
3 actual runtime/host socket scenarios and all packaging/operations checks.
Read its [ledger](research/PHASE_1_CARD_SELECTION_RELEASE_V1_ACCEPTANCE.md) for
exact identities and the untouched Smith setup. The first Smith live test returned `unsupported_state` during child
reconciliation: parent counts1/1/1, child2/2/1. Rest Proceed was subsequently
visible, but no upgrade, child completion or map handoff is accepted as proven.
Normal quit/quarantine/purge and clean base429/zero-overlay/stopped/closed checks
passed by 14:19:58 UTC; that campaign is closed. Focused diagnosis proved two
native projection mismatches against the unchanged core. The isolated
[completion repair](PHASE_1_CARD_SELECTION_COMPLETION_V1_CONTRACT.md) is now
independently accepted, frozen (41 files) and published. Its actual-adapter/core
fixtures pass87 checks and frozen-original controls reproduce both rejections.
The complete offline aggregate passes, four production builds match, and full
repository regression passes1206 tests in107.35 seconds. Read the
[completion ledger](research/PHASE_1_CARD_SELECTION_COMPLETION_V1_ACCEPTANCE.md)
for exact identities and current campaign state. The fresh corrective Smith test
now passes with all four actions reconciled and visible map handoff. Its complete
cleanup is recorded above. The earlier uncertain action was never retried.
All twelve accepted successor trees and old48 remain byte-exact. Next is a
separate Cheese exact-two card-add live test.
Do not reuse closed campaign state or retry a historical uncertain action.
Fresh Steam capture still returns `-3811`, separately from controller behavior.

## Current result

The repository now contains a functional, authenticated, project-owned live
bridge and external bounded controllers. Together they can:

- verify the pinned game build and classify the main menu and Settings screen;
- expose one public combat decision with advertised legal actions;
- apply snapshot-bound card-play and end-turn actions and reconcile the result;
- complete one turn or repeat the combat loop to an authoritative victory or
  defeat under a replaceable external decision provider;
- claim gold, open a card reward, choose an offered card, skip a skippable card
  reward, and proceed;
- expose currently travelable map destinations and select one advertised legal
  destination;
- represent bounded rest-site and safe standard-event choices through a
  separate room controller; and
- compose combat, reward, map, and supported-room controllers into an external
  controller capped at three reconciled map selections, with explicit
  fail-closed handoff and reconciliation checks. The default starts at combat;
  an explicitly named fresh reward or map boundary can be used instead.

The bridge does not contain a learned model, search implementation, simulator,
or gameplay policy. Those remain host-side replaceable components behind the
same decision-provider seams.

The user-approved `R0I-ROOM-LIFECYCLE-07` repair is integrated through
`b86d1b4`, with artifact/policy bindings at `778cadd`. Independent reviewers
accepted foreground-map action suppression, immediate stale revalidation,
rest-only completion, and stable bounded room identity across disappearance
and revisits. All 12 C# groups, 70 surface fixtures, and reproducible packaging
passed; the final post-campaign repository rerun passed 829 tests in 37.01 seconds.

The resumed campaign at clean source `3679f8b` live-accepted the bounded
rest-site slice. An inspection map suppressed all room candidates/legal actions;
one original snapshot-bound heal request was rejected as stale with no mutation
reported. After closing the map, the bounded controller accepted heal and
literal Proceed and returned passed, with a complete rest-site projection.
Closing the completed map left the room projection non-actionable despite the
persistent native Proceed control. Event suppression, broader replay-identity
cases, and other lifecycle races remain fixture-tested, not live-demonstrated.

The earlier locked-desktop attempt was cleaned up without launching the game.
The subsequent successful campaign ended with normal quit, exact quarantine,
a clean unmodded base-game launch/quit with the bridge port closed, and purge
of four generated files including the temporary credential. Final checks show
no game process/listener and the unchanged 429-file base with no overlay.

The latest bounded campaign at source `bbada1a` used the exact reviewed `0.8.0`
artifact and consolidated host transport. Its authenticated main-menu probe
passed all three routes. At a fresh reward boundary the capture-off diagnostic
reported four attempted, accepted and reconciled actions with an applied,
decision-bound receipt, then the visible game reached the map. Standalone live
controllers subsequently completed a six-round three-enemy combat, resolved its
reward and selected the next destination. A one-floor composed run starting at
the next ready combat then passed with 16 combat actions, four reward actions
and one map action, reached another ordinary combat, and stopped at its declared
floor limit. No supported rest destination was offered, so combat/rest/combat
composition remains unobserved rather than failed.

The host-only explicit phase-entry increment is integrated through `5750602`.
The old invocation and explicit combat entry retain the exact existing success
JSON; reward/map entry records a truthful partial prefix and shares the
three-map selection cap without phase scanning, fallback or retry. Its
independent actual-client gate uses literal request bytes and an `8212886`
negative control.

A bounded campaign from reviewed production source `919abc0` subsequently
live-demonstrated the explicit fresh reward-entry success path. After a
standalone setup combat won in 10 rounds with 42 accepted actions, the
coordinator visibly confirmed an untouched reward and invoked only
the runner once with `--entry-phase reward` and `--floor-limit 2`. The entry
invocation reconciled four reward actions, one map selection and 24 actions in
the next combat before normal defeat. Its sanitized result reported
`processed_floor_count=1`, `completed_floor_count=0`, and 29 total actions. The
setup combat is correctly excluded from those totals. This promotes reward
entry and truthful partial-prefix accounting to live-demonstrated; explicit map
entry, a complete post-prefix floor, batched room handoff and entry failure/
uncertainty behavior remain fixture-tested or unobserved.

No live campaign is active; the successor result and completed cleanup are below.

The host-only elite producer and independent actual-client gate are integrated
through `8fd4320`. Normal, explicit-prefix and post-room elite paths reuse the
existing combat clients and preserve their different final-slot behavior. The
opt-in `elite` provider ranks elite, rest, monster and ancient first; old
providers remain unchanged. Historical negative controls and uncertainty,
cancellation and cleanup checks pass with synthetic transport. Elite remains
unobserved live. The maintained capture-off acceptance validator and independent
whole-bridge review are accepted through `847882f`; 246 live/differential tests
pass. The full integrated bridge suite passed 1,100 tests. The authorized
campaign attempt stopped during read-only Steam inspection: the tool stalled
beyond the 30-minute limit and returned that Steam was not running. No overlay
or operator configuration was installed, no game launched, and no controller
invoked. Post-attempt checks confirm the unchanged 429-file base, zero overlay,
no game process and no accepting bridge port. A bounded infrastructure retry
opened Steam but repeatedly failed screen capture with macOS error `-3811`,
including after resetting the automation session. The user subsequently
launched the game manually: game-window capture succeeded and Profile 3 was
visibly confirmed. After normal quit and fresh passing stopped/base/package
checks, the reviewed overlay and transient operator configuration were installed
and verified. Packet `26` then invoked the capture-off runner once from a
visibly fresh map; it returned `room_interaction_timeout` with no accepted run
summary. No phase/action totals or completed map/elite/room chain are certified.
Normal quit, exact quarantine, clean unmodded launch/quit with the bridge port
closed, and the four-file purge all passed. Final checks at **2026-09-05
09:46:42 UTC** confirm the unchanged 429-file base with zero overlay, no game
process and no bridge listener. The resumed campaign finished in **16 minutes
23 seconds**, including cleanup. The live gate did not pass; its fixed timeout
is observed, while successful map entry, elite combat and composed room
handoff remain unaccepted at their required evidence level. See the actor-ready
ledger for the exact failure and cleanup binding.

The fresh-session follow-up again returned Steam capture error `-3811`;
application inventory showed the game stopped and no new campaign began.
Independent repository/fixture diagnosis established that the room timeout can
occur before any room action or after accepted choices/Proceed while completion
remains unproved. Its one deadline includes health/manifest and every room
step. The frozen waiting projection contains no cause or room identity.
Event-to-map waiting is an explicit D47 limitation, while accepted same-room
rest Proceed can complete through a travel-ready map. No new production defect
or live root cause was established. The follow-up closes missing synthetic
timeout coverage without changing controller, C#, wire or acceptance semantics.
The independent 13-case gate passed review; the full repository suite passed
**1,109 tests in 105.46 seconds**. Exact validation is recorded in the
actor-ready ledger.

The renewed development step adds a separately selected capture-off
`diagnose_run_room_live.py` command under the
[frozen room-stage contract](PHASE_1_ROOM_STAGE_DIAGNOSTIC_PLAN.md). Independent
review accepted the primitive recorder, optional room/run propagation and exact
sanitized output. The final host stage, last validated public status/kind,
bounded exchange-attempt and accepted-receipt counts, last action categories,
and same-room completion flag classify a new failure without retaining live
bodies or identities. Success alone includes the unchanged strictly validated
run acceptance aggregate. Defaults, C#, wire, package, deadlines, caps, request
order and replay/completion rules remain unchanged.

The six-group unit gate and independent 25-case actual-client gate pass,
including exact success parity, cancellation/cleanup precedence and mutations
of requests, receipt accounting and output suppression. Integrated source
`dc8e666` passed the final full repository suite: **1,111 tests in 104.17
seconds**. The room-failure stage evidence remains **bridge_fixture**.

The subsequent user-assisted campaign live-passed the diagnostic from a fresh
map: three selected destinations, two completed floors and 54 actions (43
combat, 8 reward, 3 map). Its exact record reported `room.stage=not_entered` and
zero room actions. This closes the explicit fresh-map entry live gate and the
diagnostic's no-room success path; it does not test the unresolved room failure
or establish elite/room composition. The user requested a targeted fresh
question-mark event with choices untouched and offered to prepare that state.
The separate direct-room diagnostic adapter is accepted at `9d69df1`, with
independent actual-client review and **1,112 tests passing in 106.24 seconds**.
The user-prepared live event was then tested once: one event exchange and
receipt were accepted, followed by `room_state_unsupported`, with no room
completion. The fixed stage/count failure is now live-observed. A visible loot
overlay was consistent with the existing generic overlay guard, but the
aggregate does not identify a specific unsupported cause. No collect/skip or
retry was attempted. The matching authored actual-client regression passes;
the historical room timeout remains unclassified.

Cleanup ended at **2026-09-05 11:53:03 UTC**, **15 minutes 9 seconds** after
preflight began. Normal quit, exact quarantine/four-file purge and final base/
stopped/closed checks passed. The user explicitly waived the repeated unmodded
launch/quit check; that check is omitted, not passed. No campaign remains
active at that checkpoint. The later targeted event campaign completed cleanup
at **12:20:50 UTC**, **8 minutes 14 seconds** after its fresh preflight. Normal
quit, exact four-file quarantine/purge, stopped/closed and unchanged-base checks
passed; the repeated unmodded launch/quit remained waived. No campaign remains
active. Supported user-initiated launch worked; the restricted browser URI route
was not bypassed. Steam capture error `-3811` remains separate from the controller
timeout. See the actor-ready ledger for exact results and cleanup bindings.

## Parallel headless execution status

The accepted offline stack now includes the canonical `headless_v0` public
contract, named RNG streams, reduced structural content, serializable private
world state and snapshots, combat projection/candidates, fixture playback, a
bounded episode runner, immutable trajectory records, the `combat_v0` adapter,
deterministic reduced reward/map/room rules, and the composed multi-phase
`ReducedRunBackend`. The independent `H3-CONFORMANCE-04` gate is integrated;
that checkpoint passed `66` conformance tests and `829` repository tests. The
actor-ready handoff baseline passed `1,052` repository tests.

The trusted actor dataset is accepted through `1d1f430`. It admits only
manifest-anchored sources matching explicit accepted backend/content/rules/
contract pins, separates development and held-out requests, and exposes only
public views, chosen advertised IDs and provenance as actor examples. Exact
per-trajectory component evidence is retained outside examples, including
zero-example trajectories, with a sorted aggregate label set. Dataset,
trajectory and reporting checks pass 66 tests. The public encoder is accepted
through `23d07d7`, with frozen `headless_encoding_v1` schema, exact candidate
joins and out-of-band IDs, variable rows and explicit padding masks. Independent
review confirmed valid reference reallocation and candidate permutation without
numeric identity leakage. Integrated encoder/dataset/conformance checks pass
130 tests. The small masked candidate scorer is accepted through `436cef7`,
including variable/empty views, reference/permutation invariance and pinned
checkpoint payloads. Model/encoder/dataset and adjacent agent checks pass 74
tests. The serialized deterministic cloning smoke is accepted through
`7a34785`, including independent core and artifact review. The coordinator's
published CPU smoke performed four updates over three development examples,
with three held-out examples; both panels matched 3/3 heuristic choices with
finite loss 1.128239314. Repeated training on the same anchored inputs produced
identical reports and checkpoint tensors, and loading restored caller RNG and
float64 defaults. Exact component evidence includes zero-example trajectories.
These tiny structural metrics prove plumbing only, not policy strength.
The final combined repository suite passed **1,108 tests in 105.86 seconds**
at `7a34785`; compilation and diff checks also passed.

The progression producers remain deliberately separate from the composed
backend boundary:

- combat behavior is attributed to `combat_v0` evidence;
- reduced content, persistent state, snapshots, rewards, map, and rooms are
  attributed to `structural_fixture` evidence; and
- none of the headless progression behavior is live-demonstrated or
  differentially verified.

The composed backend keeps combat evidence at `combat_v0` and all reduced
progression/composition evidence at `structural_fixture`. Its private snapshot
records the complete accepted outer candidate-ID history, closed map history,
combat-entry chronology, RNG provenance, child snapshot, public events, and
current boundary. Restore replays the accepted outer history and compares the
complete reconstructed boundary. Ordinary reset/apply paths use the bounded
local checks instead of replaying the full history on every step; this preserves
the accepted integrity gate without the earlier order-of-magnitude throughput
regression.

The snapshot commitments are deterministic consistency checks, not keyed
authenticators. They reject local splices and the conformance suite exercises
coordinated rehashed mutations, but a wholesale alternative history that is
internally valid and fully replayable is outside this trust boundary. The
reduced terminal public outcome `victory` means only that the structural route
completed; the authoritative non-policy reason is `route_complete`, not a
full-game win.

`H3-BASELINE-02` is accepted: first-legal, explicitly seeded-random, and a
non-optimal structural heuristic consume only public policy views and
advertised candidates. `H3-ROLLOUT-03` is accepted through `feda7d6`: sequential
and spawned batches use independent game/policy/collector seeds, validated
separate replay/target/audit streams, explicit stop reasons, and cancellation-
safe partial results with pending episode IDs. Real spawned SIGINT tests cover
collection, close, join, and repeated interruption during cleanup. Unpublished
worker state is not recoverable after forced cancellation.

A bounded local two-seed panel completed two reduced routes in 57 transitions:
0.448 seconds sequential and 0.978 seconds with two spawned workers, including
recording/snapshot and spawn overhead. These single-sample local measurements
are not training-performance promises or target-game wins.

A further independent panel compared 12 episodes per mode across both starter
scenarios, all three choosers, multiple game/policy seeds, and budget, defeat,
and unsupported-state controls. Sequential and two-worker spawned results
matched exactly, including complete record streams and snapshot digests. Each
mode produced 343 transitions: eight reduced route completions, two budget
stops, one defeat, and one unsupported stop. No worker survived cleanup.
This is synthetic reproducibility evidence, not target-game parity or a
performance measurement.

The offline portion of `H4-LIVE-DIFF-02` is integrated. Its 19 synthetic cases
contain 3 narrow common-subset matches, 14 divergences, and 2 unobserved cases.
No case is live captured or `differential_verified`. Room/map matches do not
prove effect amounts or entity/destination identity. A separately authorized
retained live input remains required. The exact reviewed commits, identity
bindings, test results, and campaign evidence are in the
[2026-09-04 acceptance record](research/PHASE_1_2026_09_04_ACCEPTANCE.md).

## Milestone evidence

The completed predecessor increment added pre-action room-context binding, real-client
synthetic transport composition tests, a reusable capture-off acceptance helper,
persisted headless experiment artifacts and `sts-headless` run/benchmark/validate,
maintained generated invariants and serial/spawn panels, named conformance
evidence, a production-rule gold evaluator and a bounded offline corpus codec.
The capture-off gold adapter is also reviewed and integrated. Exact commits,
review corrections and evidence are in the
[next-increment ledger](research/PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md).

The preceding bounded Profile 3 campaign repeated inspection-map suppression and
one stale/no-mutation rejection, then live-demonstrated the new expected-context
rest handoff with two accepted actions (heal/proceed) and completed map return.
Its route led to an elite, so the full combat/rest/ordinary-combat composition
and narrow gold comparison remain **unobserved**, not passed. No destination was
selected or new run started. Normal quit, exact removal, clean base-game menu
launch/quit, closed listener, four-file purge and unchanged 429-file base with
zero overlay passed. No live campaign is active.

A follow-up at clean `300d230` started one normal Ironclad A0 Profile 3 run
and reached the first post-combat reward. The capture-off gold adapter
live-demonstrated its ineligible-prestate path: `unsupported_gold_amount`, zero
claim POSTs, five unobserved fields and no admission. Ordinary reward resolution
then stopped at `reward_action_response_mismatch`, with no retry or further
gameplay. That code conflates receipt rejection and HTTP/backend failures;
the failed action and mutation outcome remain unclassified. Modal disappearance
does not prove accepted Proceed or completed reward handling. One setup UI
destination and no controller destinations were used; full composition remains
open. Cleanup ultimately passed, including clean launch/quit and final base/
listener checks. The ledger records a quarantine-before-Quit-confirmation
ordering error, its recovery, and the independent diagnostic review.

The approved `R0I-REWARD-DIAG-14` follow-up adds an explicitly selected,
capture-off reward diagnostic. It separates transport, exact known HTTP and
receipt failures without changing default reward acceptance or permitting a
retry. Attempted exchanges, accepted/bound receipts and reconciled actions are
counted separately. Synthetic actual-client tests cover strict receipts,
multi-action failure prefixes, the 17-action cap, whole-CLI privacy and
cancellation cleanup, including a repaired exceptional-exit mutable-response
wipe in the shared Python transport. No C#, wire or headless contract changed.
Failure classifications and exceptional-exit behavior remain fixture-tested.
The later campaign live-demonstrated only the successful four-action
attempt/receipt/reconciliation path; the discarded historical response and its
mutation outcome remain unknown. Exact reviewed commits and validation are
recorded in the next-increment ledger.

The targeted transport simplification is also integrated: probe and room
clients retain their existing entry points and phase behavior but use one
private bounded socket lifecycle. Room partial responses are now wiped on every
exceptional exit under the same semantics as probe responses. An independent
29-check entry-point gate passes on the integrated implementation and fails on
the preceding implementation at the intended room-cancellation gap. This is
synthetic bridge-fixture evidence and made no C#, wire, package or live change.

A read-only AutoSlay/helper comparison found no compatible drop-in lifecycle
replacement: its helpers organize waits but do not supply the missing public
event-step/exit evidence and would change the synchronous action boundary. A
follow-up C# map-characterization implementation was deliberately rejected and
not integrated because it changed native property-read ordering while testing
only presampled booleans. The existing map reader therefore remains unchanged.

The following bounded campaign live-exercised the integrated host transport and
closed the fresh reward-diagnostic and one-floor ordinary-combat composition
checks. The diagnostic separated four attempts, four exact accepted/bound
receipts and four reconciliations; the composed floor reported 21 accepted
actions and `floor_limit_reached` after selecting the next ordinary combat.
Starting the combat-oriented run command while the foreground was still a map
failed closed at `combat_not_ready` before a controller mutation; starting it
at a visibly ready combat passed. No raw responses, credentials or retained
profile-derived records were produced.

Experiment configuration is caller-declared and hash-bound, not independently
proved from trajectories. Named evidence/corpus integrity likewise does not
authenticate source honesty or authorize retained live capture. Reduced
progression remains `structural_fixture`; no target-game fidelity promotion.

| Milestone | Capability added | Evidence disposition |
| --- | --- | --- |
| `R0a` | Authenticated health, manifest, main-menu, and Settings reads | Bounded live smoke passed; normal teardown and clean base-game relaunch passed |
| `R0b` | One real read-only combat decision and host recommendation | Bounded live smoke passed; no game action was applied |
| `R0c` | One snapshot-bound combat action | Bounded live application and reconciliation passed |
| `R0d` | One complete combat turn through a replaceable provider | Bounded live turn completed |
| `R0e` | Repeat combat decisions until authoritative victory or defeat | Bounded live complete-combat loop passed |
| `R0f` | One reward decision followed by map arrival | Initial screen-transition timing blocked the first attempt; the narrowed retry passed reward and map checkpoints |
| `R0g` | Read and apply one legal map destination | Bounded live map observation and destination application passed |
| `R0h` | Compose combat victory, reward handling, and map travel into one floor | Bounded live floor transition reached the next room and clean teardown passed |
| `R0i` | Granular reward handling, a separate supported-room controller, and a capped combat/reward/map/room runner with explicit fresh-phase entry | Repository gates and fixtures passed. Historical campaigns exercised event and rest slices with the recorded fail-closed residuals. Later campaigns live-passed a fresh reward diagnostic, one complete ordinary combat/reward/map floor, and explicit reward entry from an untouched reward through map selection to terminal defeat with truthful partial-prefix counts. Explicit fresh map entry subsequently live-passed; composed room handoff remains unobserved live. |

The earlier 2026-09-04 campaign reproduced the multi-step event timeout and newly
demonstrated advertised rest-site map selection, successful standalone rest
preflight, healing, and map opening. Both standalone room controllers still
returned `room_interaction_timeout`; neither is a passed room-completion case.
No combat or reward progression was rerun during that campaign. The later
repair campaign passed standalone rest-site completion and the negative
inspection-map/stale-action check. It did not rerun combat, rewards, map travel,
or event progression and did not accept a batched room handoff.

Every completed campaign in this sequence ended with a normal game exit,
bridge quarantine/removal, a base-game main-menu relaunch with the listener
closed, and final cleanup. The intervening locked-desktop installation attempt
did not launch the game and is not a completed live campaign. Steam Cloud was
not changed and no unexpectedly enabled/syncing state was observed; no fresh
Cloud-setting or idle-state acceptance claim is made. The final base projection
again contained the expected `429` base files and no bridge overlay, with no
game process or bridge listener. These results are bounded point observations, not proof that ordinary
Steam or game launches never touch profile, preference, save, or Cloud state.

## Evidence levels inside R0i

The current `R0i` source, contracts, tests, verifier, package, and disposable
fixture suites are complete for the declared bounded surface. Live evidence is
narrower:

- **Live demonstrated:** authenticated menu/Settings/combat reads; combat
  action and completion loops; gold and card-reward progression; card choice;
  card skip; legal map selection; a direct safe standard-event action reaching
  the map; two consecutive composed combat completions with intervening
  reward/map handoffs; rest-site destination selection, readiness, healing and
  standalone completion; rest-site inspection-map suppression and stale snapshot
  rejection; non-actionability after closing the completed rest map; and clean
  teardown/base relaunch; the gold adapter's zero-POST ineligible-prestate
  path; the successful capture-off reward diagnostic path with four attempted,
  accepted/bound and reconciled actions; and a one-floor composed ordinary-
  combat/reward/map run ending at the next ordinary combat under its floor cap;
  plus explicit fresh reward entry through one reconciled map selection into
  the next combat, ending on defeat with truthful partial-prefix counts.
- **Fixture demonstrated but not yet live accepted:** event foreground-map
  suppression; identity-registry behavior across disappearance, A → B → A,
  kind conflict and capacity; other lifecycle races; a complete reconciled room
  handoff inside the batched runner; multi-step event
  completion at the Python-controller seam; the full three-combat-floor cap;
  explicit fresh map entry, default-combat equivalence, entry failure and
  no-fallback behavior, and completed post-prefix floors;
  capture-off transport, HTTP and receipt-failure classifications; and
  exceptional-exit mutable-buffer cleanup.
  The C# reader deliberately does not infer event-to-map completion.
- **Observed residuals:** an earlier batched attempt stopped on
  `decision_response_mismatch`; the 2026-09-01 attempt reached a real event
  after two combats but returned `run_room_not_ready`. The accepted Python
  repair now polls validated inactive completion without treating it as ready;
  its delayed cross-kind behavior is fixture-tested, not reproduced live.
  In the earlier 2026-09-04 campaign the multi-step event again timed out after
  visible advancement. A later rest interaction in that campaign healed and
  opened the map but also timed out.
  Under the foreground map, room responses exposed one stale event candidate
  or remained `waiting` for rest. Closing the map revealed the persistent
  underlying rest room. This demonstrates a foreground-map/room-lifetime
  mismatch, not the exact event-step pending-identity root cause. No behind-map
  action was attempted in that earlier campaign. The subsequent narrow repair
  passed the standalone rest completion and deliberately rejected one stale
  behind-map request. Event completion and the batched handoff remain open.
  The historical ordinary reward attempt stopped at
  `reward_action_response_mismatch`; independent synthetic review confirms that
  this fixed code cannot distinguish rejected receipts from HTTP/backend
  failures. The later fresh diagnostic passed but cannot retroactively classify
  that discarded response. No C# repair or success inference is justified by
  the historical code alone.

## Current exclusions

The present bridge intentionally does not support:

- shops or purchases;
- potion acquisition, replacement, use, or discard decisions;
- custom, nested, dangerous, or otherwise unrecognized event interactions;
- full-map route planning;
- a complete autonomous run;
- transparent crash recovery, automatic phase detection, or continuation from
  an uncertain earlier action;
- in-process policy inference, model training, or search;
- profile, save, progress, history, preference, replay, seed, or multiplayer
  identity access;
- arbitrary filesystem access, outbound networking, Harmony patches, or hot
  unload; or
- unpinned game builds.

This means the project has a useful live integration substrate, not yet a
general Slay the Spire 2 environment and not yet an agent that can play a full
run near optimally.

## Open gates and next bounded target

Phase 1 remains open because the program still lacks a complete public
trajectory corpus, representative phase coverage, sustained reliability and
latency evidence, a selected fast-backend role, and a repeatable full-run
control path. The recoverable dedicated-profile baseline and its broader
passivity/rollback claims also remain unresolved; the approved live smokes
accepted a narrower ordinary-game-I/O risk instead of closing those gates.

The capture-off reward diagnostic, one-floor composed ordinary-combat path and
explicit fresh reward entry are now live-demonstrated. None classifies the prior
discarded reward response or authorizes replay of its uncertain action. The
host-only elite continuation is now implemented with independent actual-client
fixtures, while C#, wire, caps and replay rules remain unchanged. The
maintained capture-off validator, independent review and aggregate bridge join
have passed. The one authorized successor run from a fresh map returned
`room_interaction_timeout`, and cleanup is complete. The focused fixture
diagnosis confirms that this code alone cannot identify the waiting stage or
select a repair. The separately reviewed capture-off room-stage diagnostic
subsequently live-passed fresh map entry, three destinations and two completed
floors, but reported the room client was not entered. The user selected a direct
untouched-event test to address the room issue and offered to prepare the exact
state. The [direct-room adapter plan](PHASE_1_DIRECT_ROOM_DIAGNOSTIC_PLAN.md)
is implemented and independently accepted at `9d69df1`; its direct event
fixture passes and the full suite passes 1,112 tests. The user-prepared event
has now yielded one accepted event receipt followed by explicit unsupported
state. The new 11-category direct fixture includes that boundary. This does not
close room completion or classify the previous timeout.

The tested entry boundary was Profile 3, Ironclad, Ascension 0, inside a fresh event
reached through a question-mark node, with choices visible and untouched. The
user prepared that state after the pinned bridge was staged. The direct
room client ran once under its existing 30-second/12-action limits. It adds
no map, combat or reward continuation. The 30-minute total campaign, capture-off,
no-retry and no profile/save-filesystem/Cloud/corpus/remote-Git boundaries remain.
Supported user-initiated launch is available; the restricted browser Steam-URI
route is not bypassed.

Normal quit, exact quarantine/purge and stopped/closed/base verification remain
required. The user explicitly waived repeated unmodded launch/quit checks; those
are omitted and recorded as waived, not passed. Full elite/combat and composed
room-handoff evidence remain future bounded targets. Keep the event identity and
completion exclusions, the historical reward mismatch residual, separate
providers and unsupported shops/content boundaries intact. No discarded response
or prior uncertain action is adopted to manufacture evidence.

Independently of that live target, the provisional headless environment has
passed its composed-backend, independent conformance, and public-only baseline
and bounded rollout/throughput gates. None may claim target-game fidelity
until named live differential cases pass, and the ordinary bridge campaign did
not authorize creation of a persistent differential-capture artifact.

The selected headless step is complete without retained live data: the public
`PolicyView` encoder, trusted actor examples without target/audit leakage,
variable advertised-candidate scorer and tiny deterministic behavior-cloning
smoke are reviewed and integrated. Their evidence remains `combat_v0` or
`structural_fixture` only where inherited as dataset/component provenance.
Encoder and model correctness is synthetic structural evidence; dataset/
cloning artifacts retain every per-component label and their sorted aggregate
without promotion. None is policy quality or target-game fidelity.

The active dependency-aware worker packets for the host-only elite continuation
and actor-ready headless path are maintained in
[`PHASE_1_ACTOR_READY_EXECUTION_PLAN.md`](PHASE_1_ACTOR_READY_EXECUTION_PLAN.md).

The user has now selected parallel repository development toward unsupported
shops, item rewards and event continuation. The
[missing-room capability plan](PHASE_1_MISSING_ROOM_CAPABILITIES_PLAN.md) assigns
three isolated proposal tasks and the coordinator's shared-contract ownership.
All three proposals have been recovered, independently reviewed, corrected and
integrated as design input. The [bounded static API result](research/PHASE_1_MISSING_ROOM_API_RESULT.md)
is now independently reviewed: full-belt potion claims need exact inventory
verification, event final-page state differs from exit, and shop close/leave
are separate actions. Generic event progression and exact shop dispatch seams
remain unresolved. The [item V1 contract](PHASE_1_ITEM_V1_CONTRACT.md) is frozen
for one isolated direct collection and is implemented in a separate successor
tree. Ten pure-core test groups pass, independent review is complete, and two
fresh builds reproduce the core/test/native assemblies. The native adapter
was compile-only at that stage.
The isolated [wire/host packet](PHASE_1_ITEM_V1_WIRE_PLAN.md) is also accepted:
9 producer groups, 27 host tests and 17 real C#-to-Python synthetic cases pass;
two verified source-snapshot builds match. Full regression passes 1,139 tests.
The service reports collection only after exact receipt and result correlation,
with one action attempt and no retry. The subsequent
[transport/frame packet](PHASE_1_ITEM_V1_TRANSPORT_PLAN.md) is also accepted:
11 C# groups, 16 Python tests and 15 actual synthetic socket cases pass; two
fresh builds match, and full regression is 1,155 tests. It adds exact injected
byte-configuration activation and an owned-thread queue, with no game bootstrap
or operator-filesystem loader.
The subsequent [secure operator/bootstrap packet](PHASE_1_ITEM_V1_BOOTSTRAP_PLAN.md)
is now accepted as an install-free candidate: 13 actual-backend operator groups,
24 synthetic lifecycle groups and 24 independent checker boundary cases pass.
Two fresh source-snapshot builds produce the same single candidate DLL. It
adds descriptor-bound operator loading and first-frame runtime creation with
truthful shutdown; at that stage its production entrypoint and game adapter
were still unexecuted.
Preserve its fourth frozen successor inventory. The fifth
[release packet](PHASE_1_ITEM_V1_RELEASE_PLAN.md) is independently accepted with an
exact reproduced package: 31 verifier, 10 production-CLI, 11 client, 5 package, 38 campaign
manager and 17 runtime groups. Full regression remains 1155 passing tests.
Its exact two-entry package contains the unchanged candidate. Separate bounded
campaigns now live-pass one potion and one relic collection, each with exactly
one attempted, accepted and reconciled action and matching visible inventory
change. Normal quit, exact quarantine/purge and unchanged 429-file
base/stopped/closed checks passed for both, most recently 2026-09-05 18:54:42 UTC.
No campaign remains active. The relic path proves exact reward-local
claimed-model reconciliation; relic hooks and parent room completion are not
promoted. The supported surface is the separate combat Loot reward list;
the chest “What’s Inside?” screen, Neow choices and shops remain unsupported.
The [acceptance ledger](research/PHASE_1_MISSING_ROOM_ACCEPTANCE.md) records the
results and the corrected setup instruction. Existing live capabilities,
0.8.0 source/artifact and operational limits remain unchanged. No full-room
or full-run claim follows. Shop dispatch/back/FTUE seams and parent event/child
lifecycle remain separate development gates.

## Shop and event implementation successor

The new [room-flow implementation](PHASE_1_SHOP_EVENT_IMPLEMENTATION_PLAN.md)
now has actual shop/event cores and pinned native adapters, a real item-child
broker, shared wire service and strict Python hosts. Module and integration
reviews and the fresh aggregate source-snapshot gate are accepted in the
[acceptance ledger](research/PHASE_1_ROOM_FLOWS_V1_ACCEPTANCE.md).
Shop fixtures cover zero/one ordinary-card purchase, inventory close and room
leave. Event fixtures cover bounded structural continuation, one real frozen
item child and explicit final Proceed/map handoff. Ordinary event option
effects remain dispatch-only with separately observed transitions.

The pure suites pass broker 575 assertions, shop 13 groups, event 36 groups,
wire 16 assertions and actual C#-to-Python 192 checks. Both native adapters compile
against the pinned game references and have independent source review.
The existing regression passes 1154 tests in the sandbox; its one ephemeral
loopback fixture was denied socket binding and passed unchanged in an
authorized focused rerun, covering all 1155 existing tests.

The combined room_release_v1 runtime, secure bootstrap, selected-flow client,
whole-assembly verifier, canonical package and campaign/cleanup tools are now
independently accepted. Two fresh aggregate runs produced identical results and
four identical production DLLs. The
[release ledger](research/PHASE_1_ROOM_RELEASE_V1_ACCEPTANCE.md) records the
corrected 52-input freeze, exact package and complete fixture evidence. All six predecessor
trees and the old bridge remain byte-exact.

The first live shop test reached the user-prepared merchant inventory but
returned unsupported_state before any action (0 attempted/accepted/reconciled).
The native rejection branch was unidentified at that point; pure captures do
not execute the live scene adapter. The separate passive shop_diagnostic_v1 successor now
passes independent review and two identical complete offline release runs.
Its 63-file freeze, four matching production builds, one-GET/no-action boundary
and exact package are recorded in the
[diagnostic acceptance ledger](research/PHASE_1_SHOP_DIAGNOSTIC_V1_ACCEPTANCE.md).
The single live diagnostic passed at 2026-09-06 09:54:54 UTC with shop_status
unsupported, stage core_context and reason map_travel_enabled on the intended
untouched merchant inventory. No action route or gameplay action was involved.
This localizes the first rejection; later predicates and shop control remain
unproven. Normal quit, exact quarantine/purge, base429/zero-overlay/stopped/closed
and fixed absences passed by 09:57:53 UTC. No campaign remains active. Next is
the bounded shop repair identified by the independently accepted
[static diagnosis](research/PHASE_1_SHOP_MAP_FLAG_DIAGNOSIS.md): merchant startup
enables travel permission by design, so exactly three pre-leave shop predicates
must change in a new derived sibling. Preserve leave reconciliation and event
behavior. The isolated shop_map_permission_v1 repair is now independently
accepted, with two identical complete offline runs/four matching production
builds and 1179 passing repository tests. The 45-file freeze and exact package are
published. The single fresh live shop test passed 3 attempted/accepted/reconciled
actions: one 25-gold ordinary-card purchase, inventory close and room leave to the
map. Normal quit, quarantine, exact 4-file purge, unchanged base429/zero-overlay,
stopped/closed and seven fixed absences completed by 10:38:10UTC. No campaign
remains active. The [repair ledger](research/PHASE_1_SHOP_MAP_PERMISSION_V1_ACCEPTANCE.md)
owns exact identities, summary and cleanup evidence. This promotes only that
ordinary-card shop path; the subsequent bounded event result is below.
Historical diagnostic and closed states remain preserved.
The subsequent fresh event-continuation campaign passed on Dense Vegetation:
one ordinary choice, one observed follow-up transition, final Proceed and map
handoff. The fixed client returned 2 attempted/accepted parent clicks,1 reconciled
final handoff and no child actions. Longer ordinary-choice chains and event item
children remain unobserved live. Normal quit/quarantine/exact purge and final
base429/zero-overlay/stopped/closed/seven absences passed by 11:06:16UTC. No
campaign remains active. The
[event test ledger](research/PHASE_1_EVENT_CONTINUATION_LIVE_ACCEPTANCE.md) owns
its exact bounded result, visible corroboration and complete cleanup.
Prior potion/relic campaigns remain the latest live item evidence. Rest healing
and map return are live-demonstrated; rest-site card upgrades remain unsupported.

## Document map

- [`PHASE_1_ACTOR_READY_EXECUTION_PLAN.md`](PHASE_1_ACTOR_READY_EXECUTION_PLAN.md)
  is the active successor graph. It freezes a C#/wire-neutral elite host path,
  public headless encoding, trusted actor dataset, variable-candidate scorer,
  tiny cloning smoke, and one bounded coordinator live gate.
- Its [acceptance ledger](research/PHASE_1_ACTOR_READY_ACCEPTANCE.md) records
  accepted implementation packets, reviews, exact test results, the failed
  live campaign with completed cleanup, and the fresh-session timeout fixture
  diagnosis. Packet `26`'s live acceptance gate remains open; new outcomes belong
  there rather than in the predecessor ledger.
- [`PHASE_1_NEXT_INCREMENT_PLAN.md`](PHASE_1_NEXT_INCREMENT_PLAN.md) is the
  completed predecessor increment. Pre-action context binding, its composed handoff,
  experiment CLI/artifacts, named evidence/gold evaluator/corpus and generated
  headless panels and capture-off gold adapter are reviewed and integrated.
  The subsequently approved reward diagnostic is fixture-tested and has passed
  one fresh capture-off live boundary. One ordinary combat/reward/map floor is
  also live-demonstrated. Explicit fresh reward entry has now passed a bounded
  live check with truthful partial-prefix accounting through terminal defeat.
  Explicit map entry and supported-room composition remain unobserved live.
  These results do not authorize retained live data.
  Exact results are in the
  [next-increment ledger](research/PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md).
- [`PHASE_1_PARALLEL_EXECUTION_PLAN.md`](PHASE_1_PARALLEL_EXECUTION_PLAN.md)
  preserves the completed foundational bridge/headless packet graph.
- [`bridge/Sts2AgentBridge/README.md`](../bridge/Sts2AgentBridge/README.md)
  defines the current `R0i` implementation, commands, exact limits, package,
  and operational boundaries.
- [`research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md`](research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md)
  preserves the initial repository evidence and the detailed `R0a`/`R0b` live
  results.
- [`PHASE_1_R0A_LIVE_CAMPAIGN_REQUEST.md`](PHASE_1_R0A_LIVE_CAMPAIGN_REQUEST.md)
  preserves the exact first live-smoke authorization. It is a historical
  request, not standing authorization for another installation or launch.
- [`PHASE_1_RESTRICTED_BRIDGE_DESIGN.md`](PHASE_1_RESTRICTED_BRIDGE_DESIGN.md)
  and [`PHASE_1_BR0_PREFLIGHT.md`](PHASE_1_BR0_PREFLIGHT.md) preserve the
  original staged boundary and `R0a` freeze.
- [`PHASE_1_INTEGRATION_SPIKE.md`](PHASE_1_INTEGRATION_SPIKE.md) defines the
  broader evidence required to finish Phase 1 and choose the fast backend.
