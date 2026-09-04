# Phase 1 Current Integration Status

- **Status date:** 2026-09-04
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

No live campaign is active.

## Parallel headless execution status

The accepted offline stack now includes the canonical `headless_v0` public
contract, named RNG streams, reduced structural content, serializable private
world state and snapshots, combat projection/candidates, fixture playback, a
bounded episode runner, immutable trajectory records, the `combat_v0` adapter,
deterministic reduced reward/map/room rules, and the composed multi-phase
`ReducedRunBackend`. The independent `H3-CONFORMANCE-04` gate is integrated;
that checkpoint passed `66` conformance tests and `829` repository tests. The
latest integrated tree passes `1,052` repository tests.

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

The accepted next increment adds pre-action room-context binding, real-client
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
| `R0i` | Granular reward handling, a separate supported-room controller, and a capped combat/reward/map/room runner with explicit fresh-phase entry | Repository gates and fixtures passed. Historical campaigns exercised event and rest slices with the recorded fail-closed residuals. Later campaigns live-passed a fresh reward diagnostic, one complete ordinary combat/reward/map floor, and explicit reward entry from an untouched reward through map selection to terminal defeat with truthful partial-prefix counts. Explicit map entry and composed room handoff remain unobserved live. |

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
smallest remaining live targets are the separate explicit map-entry branch and
a composed supported-room handoff when a rest route is offered, using only
already implemented combat, reward, map and room contracts. A compatible
campaign should:

1. for the remaining entry branch, begin only at a declared visibly fresh map
   phase and verify its partial-prefix result without scanning, fallback, retry
   or retained raw data;
2. build on the live-accepted standalone rest-site repair to exercise a composed
   combat/rest/combat handoff when supported destinations are available,
   retaining the reviewed Python readiness fix; the original `R0I-RUN-03/04`
   C# exclusions remain unchanged;
3. preserve fail-closed multi-step event handling; any event-step identity
   redesign requires a separately approved scope;
4. retain `reward_action_response_mismatch` as a separate historical residual until
   reproduced or explained;
5. obtain bounded live evidence for a fully reconciled rest-site or standard-
   event handoff when encountered;
6. preserve separate combat, reward, map, and room providers so components can
   still be compared independently;
7. finish with the existing quarantine, clean-base relaunch, and purge checks;
   and
8. avoid expanding the live bridge into shops, models, search, or broader
   control surfaces until the existing slice is repeatable.

Independently of that live target, the provisional headless environment has
passed its composed-backend, independent conformance, and public-only baseline
and bounded rollout/throughput gates. None may claim target-game fidelity
until named live differential cases pass, and the ordinary bridge campaign did
not authorize creation of a persistent differential-capture artifact.

The dependency-aware worker packets for both the live and headless tracks are
maintained in
[`PHASE_1_PARALLEL_EXECUTION_PLAN.md`](PHASE_1_PARALLEL_EXECUTION_PLAN.md).

## Document map

- [`PHASE_1_NEXT_INCREMENT_PLAN.md`](PHASE_1_NEXT_INCREMENT_PLAN.md) is the
  accepted active increment. Pre-action context binding, its composed handoff,
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
