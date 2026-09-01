# Phase 1 Current Integration Status

- **Status date:** 2026-09-01
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
  controller capped at three combat floors, with explicit fail-closed handoff
  and reconciliation checks.

The bridge does not contain a learned model, search implementation, simulator,
or gameplay policy. Those remain host-side replaceable components behind the
same decision-provider seams.

## Parallel headless execution status

The accepted offline stack now includes the canonical `headless_v0` public
contract, named RNG streams, reduced structural content, serializable private
world state and snapshots, combat projection/candidates, fixture playback, a
bounded episode runner, immutable trajectory records, the `combat_v0` adapter,
deterministic reduced reward/map/room rules, and the composed multi-phase
`ReducedRunBackend`. The independent `H3-CONFORMANCE-04` gate is integrated;
the integration branch passes `66` conformance tests and `740` repository
tests.

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

`H3-BASELINE-02` and `H3-ROLLOUT-03` remain unstarted. Therefore there is no
accepted backend-neutral smoke-policy package, process-batch collector, or
rollout throughput claim yet.

## Milestone evidence

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
| `R0i` | Granular reward handling, a separate supported-room controller, and a capped combat/reward/map/room runner | Repository gates and fixtures passed. The 2026-09-01 campaign live-demonstrated menu, Settings, combat, one safe event-to-map action, legal map selection, two completed combats, and their reward/map handoffs. The composed room handoff stopped fail-closed at `run_room_not_ready`; a narrowed multi-step event attempt then applied one action but ended at `room_interaction_timeout` |

Every completed campaign in this sequence ended with a normal game exit,
bridge quarantine/removal, a base-game main-menu relaunch with the listener
closed, and final cleanup. During the latest campaign Steam Cloud remained at
the previously established disabled setting; it was neither changed nor given
an idle-state acceptance claim. The final base projection again contained the
expected `429` base files and no bridge overlay, with no game process or bridge
listener. These results are bounded point observations, not proof that ordinary
Steam or game launches never touch profile, preference, save, or Cloud state.

## Evidence levels inside R0i

The current `R0i` source, contracts, tests, verifier, package, and disposable
fixture suites are complete for the declared bounded surface. Live evidence is
narrower:

- **Live demonstrated:** authenticated menu/Settings/combat reads; combat
  action and completion loops; gold and card-reward progression; card choice;
  card skip; legal map selection; a direct safe standard-event action reaching
  the map; two consecutive composed combat completions with intervening
  reward/map handoffs; and clean teardown/base relaunch.
- **Fixture demonstrated but not yet live accepted:** rest-site handling; a
  complete reconciled room handoff inside the batched runner; multi-step event
  completion; and the full three-combat-floor cap.
- **Observed residuals:** an earlier batched attempt stopped on
  `decision_response_mismatch`; the latest reached a real event after two
  combats but returned `run_room_not_ready`. A standalone safe-room retry
  applied the first action of the multi-step event and then returned
  `room_interaction_timeout`. Normal UI recovery completed the event without
  broadening bridge authority. These are live failures, not passed room cases.

## Current exclusions

The present bridge intentionally does not support:

- shops or purchases;
- potion acquisition, replacement, use, or discard decisions;
- custom, nested, dangerous, or otherwise unrecognized event interactions;
- full-map route planning;
- a complete autonomous run;
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

The smallest useful next live target is to stabilize the existing room handoff
inside one reproducible multi-floor sequence using only already implemented
combat, reward, map, and supported-room contracts. That target
should:

1. minimize the `run_room_not_ready` readiness race or classification mismatch
   without adding privileged state;
2. make multi-step event continuation either complete within its bounded
   contract or fail immediately with a precise supported/unsupported reason;
3. retain `decision_response_mismatch` as a separate historical residual until
   reproduced or explained;
4. obtain bounded live evidence for a fully reconciled rest-site or standard-
   event handoff when encountered;
5. preserve separate combat, reward, map, and room providers so components can
   still be compared independently;
6. finish with the existing quarantine, clean-base relaunch, and purge checks;
   and
7. avoid expanding the live bridge into shops, models, search, or broader
   control surfaces until the existing slice is repeatable.

Independently of that live target, the provisional headless environment has
passed its composed-backend and independent conformance gates. When development
resumes, the next unstarted consumers are the public-only smoke baselines and
then bounded rollout/throughput collection. None may claim target-game fidelity
until named live differential cases pass, and the ordinary bridge campaign did
not authorize creation of a persistent differential-capture artifact.

The dependency-aware worker packets for both the live and headless tracks are
maintained in
[`PHASE_1_PARALLEL_EXECUTION_PLAN.md`](PHASE_1_PARALLEL_EXECUTION_PLAN.md).

## Document map

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
