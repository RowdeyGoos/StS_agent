# Shared agent bridge milestone 3 — September 23, 2026

Status: **milestone 3 accepted**, including the controlled combat/selection/reward
slice, separate map dispatch and owned cleanup. This record separates authored
fixtures from live game execution and retains both earlier failed attempts.
All three attempts were normally quit and fully cleaned up.

The [plan](../AGENT_ENVIRONMENT.md) owns subsequent milestones and the
[contract](../AGENT_CONTRACT.md#native-producer) owns supported public semantics and
limits. The existing bridge now exposes `agent_v1` and runs the same
`game.agent.policy.choose_action` as the headless adapter, preserving the existing
transport, native action owners and installation/cleanup workflow.

## Artifact

- Source base: `14182eb`, current working checkout; no implementation commit yet.
- Accepted [manifest](../../bridge/Sts2AgentBridge/releases/current/bridge.json)
  SHA-256: `22c752d8c20ffb1f5c8d28266342f0b97356c24fc1cf34ad99766a630c0a3e69`.
- 393 source/test inputs, 49 explicit projects; shared Python contract/policy
  dependencies are included in the release source identity.
- Pinned .NET SDK 9.0.303 and game `sts2.dll`
  `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
- Gate and package output: `/private/tmp/sts-agent-m3-completion-release-sdk-refresh`; published install
  input: `/private/tmp/sts-unified-bridge-release`.
- [Validation binding](../../bridge/Sts2AgentBridge/releases/current/validation.json)
  retains each gate result and its log filename.

## Evidence and corrections

The corrected combined gate passed **78 check groups in 261.3 seconds**, including
the reproducible production binary, pinned native metadata/surface checks,
Python/C# integration, actual loopback POSTs, package rejection cases and
disposable owned installation/cleanup. Gate results alone do not establish live
reconciliation; the actual game attempts are recorded separately below.

Focused checks preceding the initial gate (the correction's checks follow below):

| Check | Result |
| --- | --- |
| Unified runtime/parser/ownership fixture | 1,340 checks passed |
| Native public-reader fixture | 28 checks passed, inert native API objects |
| Paired public projection | Five authored matching observations/transitions passed |
| Agent host failure paths | Seven tests passed, including lost/invalid receipts, interrupts, stale rejection and cleanup failure |
| Headless adapter + Neow's Fury | 121 tests passed before the additional preview regression |
| Final adapter/pair regression | 48 tests passed, including the additional preview regression |
| Shared client socket integration | Passed in 64.849 seconds, including the actual new agent POST and nested ownership |
| Shared release dependency binding | Ten maintenance tests passed |

Broad validation: `python -m compileall -q game tests` passed. The full
`PYTHONPATH=. python -m pytest -q` run completed with **7,774 passed and one failed
in 1,205.64 seconds**. The failure was the existing ephemeral-socket test's
`PermissionError` binding loopback in the sandbox. Its complete 16-test module
passed when rerun with loopback permission, as it also did in the accepted release
gate. The additional preview and release-dependency tests were added after broad
collection and passed in their focused suites above. No gameplay failure remained.

The paired scenario covers an initial Neow's Fury play, the open discard selector,
two selected cards and return to combat after confirmation. It normalizes public
reference names and semantic candidate ordering while retaining visible pile,
selection and history order. It is not a live capture or a matched-RNG claim.

Independent semantic review found and then rechecked corrections to public power
card freezing, native variable/power IDs, missing Zap/Dualcast/Twin Strike values,
off-character resources, nested parent history, skipped rewards, pending uncertain
dispatch and repeated defeat reads. Final review found no remaining concrete
blockers within the declared bounded scope.

Native preview inspection also corrected the headless producer's global
damage/block modifiers outside hand/play. A pinned SDK HashSet experiment and
native selector inspection established Neow's Fury's slot reuse order; headless
deselect/reselect and restore now preserve it. Private continuation versions are
combat v48 and run v69. The public contract remains v1.

## First controlled live attempt

The initial package had manifest
`7b59e89d6ca0cf50b8d08224b8758984676194534c1e9a17d24673c91689688f`,
392 source/test inputs and a 78-group gate of 270.881 seconds, retained at
`/private/tmp/sts-agent-m3-release`. Those results are not repinned to the correction.

The user manually opened Profile 3. Native UI/console setup established Ironclad
at 80/80 HP with Burning Blood, no potions, a deck of Neow's Fury/two Strikes/Defend,
one ordinary Nibbit at 46 HP, and two additional Strikes in discard. No profile,
save, history or Cloud filesystem access was used. The UI tool briefly required
the user to foreground the game; no uncertain setup command was retried.

The shared acceptance callback uses `choose_action` for combat, selection and map,
then claims gold and leaves optional rewards. Its SHA-256 is
`94f28948503e381e67718e55e7b1b394ac43ece2de2d4c1a7ba4445955957d5f`.
The identical callback first passed the headless combat/selection/rewards/map
slice and separate map dispatch. It does not establish live card-offer selection.

The live attempt stopped after 0.345 seconds with `unsupported_profile`: one
accepted Neow's Fury play opened its native selector and dealt ten damage. The
bridge prematurely reported one reconciled parent from changed HP/energy/hand,
offered another combat choice, safely stale-rejected it, then lacked a parent for
the arriving selector. Its reported `attempted=2, accepted=1, reconciled=1` is
retained as failure evidence, not a clean completion certificate. No action was
retried; map dispatch was not attempted.

Normal quit, exact process/listener shutdown, owned quarantine and purge passed.
The base installation remained **429 files**, SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`,
with zero overlay files. The validation record retains the installed/quarantined
state identities and bounded result summary.

The correction retains the exact queued native action in the existing combat
reader. Changed public state and terminal HP cannot release it before execution
finishes; existing nested chooser routes remain available. Native completion and
its underlying execution task are both checked, along with cancellation, exact
card play-pile entry and end-turn advancement. Unresolved disposal stays failed
even on repeated cleanup. Focused cases cover the delayed selector and parent
resumption, native faults/cancellation/no-op, terminal outcomes and cleanup.

The correction passed **306 native combat/choice checks** and **1,347 unified
runtime checks** in the affected fixture run (5.277 seconds), and compiled against
the pinned native assemblies. Independent review took 1m37s and found no remaining
blocker after making repeated unresolved disposal fail consistently.

The first correction release gate stopped in an unchanged rest-site project with
SDK analyzer `AD0001`/`MissingMethodException`; it emitted no accepted package.
The isolated affected project then passed with the same SDK/settings (7.456
seconds), and all 61 compiler/analyzer DLLs matched the retained SDK archive.
The second correction gate passed behavior, socket and reproducibility checks,
then hit another SDK `MissingMethodException` while compiling the package verifier.
Neither failed gate emitted an accepted manifest. Extracting a fresh copy of the
same retained SDK archive verified all 4,844 files against the previous SDK with
zero mismatches. The complete replacement gate then passed all 78 groups in
261.3 seconds. No analyzer or check was disabled; the compiler failure's underlying
cause is not established.

## Second controlled live attempt

The corrected package was installed with state identity
`0a63d47b67eb646fb50b1cc9b08de39350116c783418ef34de4e34398db23f32`.
The user manually reopened Profile 3. The restored run had the original four
Bludgeons and five relics, so native console setup reestablished the supported deck,
Burning Blood, empty belt, Nibbit at 46 HP and two discard Strikes before agent
ownership began.

The same callback completed **15 attempted, accepted and reconciled actions**:
eight card plays, two end turns, two selections, one confirmation, one gold claim
and one reward leave. There were no stale rejections or pending actions. The
native UI showed victory, HP 68/80 and gold 99→115. This demonstrates the corrected
parent completion behavior through the nested choice and subsequent turns.

The host nevertheless reached its 180-second limit (`deadline`, 180.039 seconds,
2,688 reads): the visible map never produced an actionable decision. No map action
was attempted. Closing the map showed the ordinary remaining card reward; reopening
the map did not establish travel readiness. The user also observed the map problem.
Native `FightConsoleCmd`/`EnterRoomDebug` preserves the prior map coordinate, which
motivated a fresh act map for the next setup check. The exact rejected map predicate
was not observed; this attempt alone does not establish a bridge defect or a clean
end-to-end result.

Normal quit, exact stopped-process/closed-listener checks, quarantine and purge
passed. Quarantine identity was
`3dac39d409677ab654d2a7fb886676af603332d1deacf3fb780cd039c5abb391`.
Four owned files were removed; all 429 base files retained the original hash and
the overlay count returned to zero. The unchanged accepted package was then
reinstalled for the fresh-map setup, with identity
`b4ba75be30b9a48f9a8eab4053ee662f9e0b418cbbef2fe4a5f1567455bbb820`.

## Third controlled live attempt — accepted

The user manually reopened Profile 3 at the main menu. Exact process identity and
bridge health passed before setup, initializing the public observer. Continue
restored the supported four-card deck, Burning Blood and empty potion belt.
The native console `act 1` command generated a fresh act map and entered its Neow
starting coordinate normally. An initial mistyped `ct 1` was explicitly rejected
as an unknown command before the valid command was entered; no uncertain mutation
was retried. UI inspection verified the Underdocks map and onward monster paths.
No Neow boon was selected.

The player was healed to 80/80. Native console setup entered `NIBBITS_WEAK` from
this starting coordinate and added two Strikes to discard. The UI verified the
supported deck/inventory, one ordinary Nibbit at 44 HP and exactly two discard
targets before the first agent request. All setup panels were closed. The package
was unchanged from the second attempt; no further bridge correction was made.

The identical headless/live acceptance callback completed the slice in **9.552
seconds**, with 130 reads and **15 attempted, accepted and reconciled actions**:
eight card plays, two end turns, two selections, one confirmation, one gold claim
and one reward leave. The result was `resolved`, with `slice_complete` truncation,
no pending action and no stale rejection. Native UI confirmed victory, HP 68/80,
gold 99→109 and an actionable map.

The separate bounded map case then selected one legal monster node and reconciled
its native transition in **0.730 seconds**, with ten reads. Its counters are
**cumulative session totals: 16 attempted, accepted and reconciled**, a delta of
one from the preceding slice. Native UI confirmed arrival in a new three-enemy
combat. No further policy action was taken. This case also returned
`slice_complete`, with no pending action or stale rejection.

The fresh native map resolved the earlier map stall with the same package. This
supports a setup-sensitive interpretation; the original rejected map predicate
was not observed, so no general map-code fix or precise root cause is claimed.

Normal quit and exact process/listener shutdown passed. Owned quarantine used
identity `5b5a02af28eb84d3b3edde1d0d46c68d607609e1ba5e6d666fa90c2e320c9777`;
purge removed four owned files. At **2026-09-23 19:14:56 UTC**, the installation was
absent, overlay count was zero and all **429 base files** retained SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
The [validation binding](../../bridge/Sts2AgentBridge/releases/current/validation.json)
retains both result summaries, the exact shared callback source and its identity.

## Limits and timing

The controlled policy uses the shared chooser for combat, selection and map, with
the same gold-then-leave reward override on both backends. It does **not** establish
live card-offer selection, arbitrary content coverage or a full autonomous run.
The native producer retains its explicit card/inventory allowlist; unsupported
cards, powers, owned potions or visible reward offers stop the profile. Native and
headless random outcomes were not matched. The five authored paired transitions
remain separate evidence from these assisted live cases.

Milestone work began at 16:44:48 UTC. Initial independent review took 10m37s plus
5m57s (16m34s total); the initial release gate took 270.881 seconds and its package
was prepared by 17:43:53 UTC. The live feedback interval from 18:06:06 through
19:14:56 UTC was 68m50s, including correction, its 1m37s review, release work,
native setup and user wait. The corrected focused run took 5.277 seconds and the
accepted replacement gate 261.3 seconds. These intervals overlap; no separate
implementation or user-wait duration is claimed.
