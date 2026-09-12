# Multi-case bridge live session — September 12, 2026

The user requested multiple tests in one game session. Reused accepted release
`7db195a80d67296c6930b135785724505fa26ea3c4475588bfc55fabeacecccf` after verifying
all 334 source/test inputs and exact package hashes; no rebuild was needed.
Manual Profile 3 setup and user-prepared event transitions were used. No profile,
save, history or Cloud filesystem access occurred.

| Case | Observed result |
| --- | --- |
| Fake Merchant | Passed inventory open, two relic purchases, close and native Leave/map. Five parent actions attempted/accepted/reconciled; six event reads and one independent map read with one candidate. UI gold 119→24; two additional relic icons; HP 64/80→67/83 observed, not independently certified. |
| Crystal Sphere Payment Plan | Passed in the same process. Two parent and eight child actions attempted/accepted/reconciled; 23 event reads and one independent map read with one candidate. UI gold 124→144 and deck 12→13; automatic Debt provenance remains unverified. |
| Battleworn Dummy Setting2 | Failed resumption verification. Exact event combat entry reconciled; combat attempted 15, accepted 13, reconciled 12, with two known no-mutation stale rejections. 86 combat reads and 86 continuation reads. UI displayed the post-training humiliation/Proceed page. Final continuation response was backend_fault; host code invalid_event_resume. No resumed Proceed/map input was sent. Root cause remains unproven. |
| Setting1, Dense Vegetation, The Lantern Key, Punch Off | Not attempted after the Setting2 failure. |

The game remained open across the two successful cases and the third attempt.
One accepted combat action remained unreconciled at failure. No uncertain mutation
was retried and the batch stopped; visible event return was not treated as verified
native resumption.

Normal quit, stopped process/closed listener, exact owned quarantine/purge and
429 unchanged base files with zero overlays passed. Base hash:
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
No test bridge remains installed. Exact case summaries, diagnostic file hashes and
installation/cleanup identities are in
[current validation](../../bridge/Sts2AgentBridge/releases/current/validation.json).
The disposable queue and per-case commands are `/private/tmp/sts-multicase-20260912.json`.
Per-case wall times and user setup wait were not separately measured.

Next: diagnose the Setting2 backend fault at the native event-resumption boundary,
then retest it before claiming resumption support. The other prepared cases remain
pending; these results do not establish full-run autonomy or strategic quality.

## Resumption correction

Pinned native metadata (`sts2.dll` SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`)
establishes the sequence: `RunManager.ResumePreviousRoom` awaits
`ExitCurrentRoom`, then calls the retained room's `Resume`. `CombatRoom.Exit`
removes each player creature; `CombatState.Players` derives from those creatures.
`EventRoom.Resume` calls `EventSynchronizer.ResumeEvents`, which invokes the
original model's `Resume`, then creates the new event node.

The bridge incorrectly required one player in the exited combat at this callback.
The correction accepts the empty, cleaned combat roster while retaining exact
combat room/state/encounter identity and requiring the original current event
room, run node, model owner and local event. A foreign nonempty roster still
fails. Focused fixtures pass 224 assertions, including cleared-roster resumption
and substituted player, owner, event, combat state and current-room rejection.
This demonstrates a concrete native/fixture mismatch explaining rejection; the
original live response did not identify its individual failing guard. A fresh
Setting2 live test remains necessary to establish successful end-to-end recovery.

## Corrected-release first-read attempt

Release `25af10183a8bb254dcb4ce7bfab4cf8016b530b233095c039762bfb9b63e4750`
passed 71 release groups in 197.753 seconds (9,849 native assertions) and
independent semantic review. After installation and manual user setup, the initial
Battleworn Dummy choices were visually confirmed. The first GET received zero
response bytes (`response_header` parser failure), producing `invalid_response`.
Parent attempted/accepted/reconciled were 0/0/0; combat was not attempted. This did
not exercise the resumption correction. No request was retried.

Normal quit, stopped process/closed listener, exact owned quarantine/purge and
429 unchanged base files/zero overlays passed. No test bridge remains installed.
The transport has several no-response failure paths; the retained client evidence
does not identify which occurred. Investigate that first-read failure before
another setup. Remaining batch cases were not attempted.

## First-read diagnostic preparation

Source inspection found that unsuccessful owner-frame dispatch already classifies
unavailable/busy, timeout before claim, timeout after claim, and service fault,
but the shared transport discarded that classification and closed the socket.
The correction returns a fixed `dispatch_*` error body for authenticated GETs at
that boundary. It still latches terminal before delivery; POST and unauthenticated
behavior, the 500 ms frame-result deadline, late-result disposal and no-retry
rules are unchanged. It does not reveal exception text, native values or tokens.
The live cause remains unproven until a new read produces evidence.

Focused native/shared Python socket checks passed in 32.107 seconds, including
946 unified checks. Regression cases exercise timeout before claim (no module
creation), timeout after claim (late module disposal), router fault, unchanged
silent POST timeout and unauthenticated rejection. Both event and core response
header forms decode through the actual Python client. Independent semantic
review found no blocker in terminal ownership or cleanup.

Diagnostic release `9dae293a74a3b8ab9bac9268263cc80d22d24577e1a22c5803d5af5cd5592291` passed all 71 release groups
in 201.6 seconds and is installed awaiting manual setup. Its exact source, binary,
installation and pending queue identities are in the current validation record.

## Diagnostic-release Setting2 result

Release `9dae293a74a3b8ab9bac9268263cc80d22d24577e1a22c5803d5af5cd5592291`
passed its initial read and selected Setting2. Event entry reconciled 1/1/1 with
13 event reads. Combat attempted/accepted/reconciled was 9/9/8, with 78 combat and
78 continuation reads, 50 choice probes and no stale rejections. The last response
was `backend_fault`; host result `invalid_event_resume`. The game visibly showed
the resumed humiliation/Proceed page (HP 69/83, gold 124). No Proceed/map input
was sent and no uncertain mutation was retried. Remaining batch cases were not
attempted. The roster correction alone did not resolve the handoff; the new
transport diagnostic did not fire because the first read succeeded this time.

Normal quit, stopped process/closed listener, exact owned quarantine/purge and
429 unchanged base files/zero overlays passed. No bridge remains installed.
Next investigate the specific remaining resumption rejection before another live
attempt; the prior intermittent first-read failure is still unexplained.

## Inner-layout resumption correction

Further pinned native inspection identified a second concrete mismatch:
`NEventRoom._Ready` instantiates the event scene, passes that inner `Control` to
`EventModel.SetNode`, and installs it in its scene container. `NEventRoom.Layout`
returns that container's current scene as `NEventLayout`. The bridge instead
compared `EventModel.Node` with the outer `NEventRoom`. Its fixture incorrectly
typed `EventModel.Node` as `NEventRoom`, hiding the impossible native comparison.
The same pinned game DLL identity recorded above applies.

The stub now uses native `Control` semantics and resumption fixtures bind the
inner layout. Those corrected fixtures failed on the original synchronous
resumption case before the production fix. The fix binds and retains both exact
room and layout identities, requiring valid layout identity through subsequent
resume-time item settlement. Focused resumption checks pass 240 assertions,
including foreign-layout, outer-room-as-node, freed-layout and replaced-layout
rejections. This explains a further deterministic native rejection; a new live
run remains necessary to establish the complete handoff.

Inner-layout release `a204ee937b08a91d77a3463a6c92c2066874235361f857c27bcb04131ecd8207` passed all 71 release
groups in197.289 seconds (9,865 native assertions) and is installed awaiting setup.
The first release run caught a duplicate old direct-input stub type; it was
corrected, its focused checks passed, then the final release gate passed.

## Inner-layout release: identified first-read timeout

The first live GET on `a204ee937b08a91d77a3463a6c92c2066874235361f857c27bcb04131ecd8207`
returned `dispatch_timeout_after_claim`. This establishes that its owner-frame
callback began but exceeded the 500 ms result deadline; the work responsible for
that duration remains unproven. Setup was visibly the untouched Battleworn Dummy
initial page (HP80/80, gold99, deck10, floor3). Parent actions were0/0/0 and combat
was not attempted. No retry occurred; the inner-layout correction was not exercised.

Normal quit, stopped process/closed listener, exact owned quarantine/purge and
429 unchanged base files/zero overlays passed. No bridge remains installed.
Next address the bounded initial-read callback work, then retest resumption.

## Bounded incremental hook preparation

The first event read previously constructed the native adapter and installed all
31 Harmony hooks synchronously. This is a plausible cold-start contributor to the
observed after-claim timeout, not a measured attribution of its entire duration.
Production now retains an exclusive partial hook lease and installs one target
per read. Until complete, the adapter reports internal preparation and the core
emits existing waiting responses. Preparation is allowed only before the first
publication/action and is capped at 32 reads; input cannot be armed early. Every
step checks existing exact patches and next-target exclusivity, and failed setup
retains sticky failure plus exact rollback/cleanup ownership. Normal partial
leases cannot be taken by failed-constructor recovery. The500 ms deadline and
uncertain-mutation/no-retry rules are unchanged.

Focused incremental/core boundary and hook-ownership checks pass 153 assertions.
A native-to-Python scenario covers 30 waiting reads, then ready, selection and map
completion. Its first selected gate was invalidated by a concurrent final test
edit; that run is not accepted as final source validation. The stable release
reruns the affected tests. Live resolution of startup and resumption remains
pending.

Final incremental release `cf181cbe61e88ccb4a099a7fec339bba8e3051dcbccf713ee5d6fc1d10a75d35` passed 71 release
groups in 199.018 seconds, with 10,005 native assertions and 474 C#/Python integration
cases (412 native), and is installed awaiting manual setup. A release-test order
error was corrected by moving new tests after the preserved 550/745 historical
assertion checkpoints; those checkpoints remain unchanged. Independent review
found no blocker. Cold-start latency and live resumption remain pending.

## Incremental release: first-read timeout persists

Release `cf181cbe61e88ccb4a099a7fec339bba8e3051dcbccf713ee5d6fc1d10a75d35`
returned `dispatch_timeout_after_claim` on its first GET, before any action.
User-prepared initial choices were visually confirmed (HP80/80, gold99, deck10,
floor3). Parent actions were0/0/0 and combat was not attempted. Incremental hook
installation alone was insufficient; the delayed initialization stage remains
unknown. No retry occurred and the resumption correction was not exercised.

Normal quit, stopped process/closed listener, exact owned quarantine/purge and
429 unchanged base files/zero overlays passed. No bridge remains installed.
Next measure bounded first-read initialization stages before choosing another fix.

## First-read stage instrumentation

Added per-read timing markers around routing/module creation, native module entry,
Harmony dependency verification, adapter construction, hook target lookup and
validation, hook installation, session/wire construction and native capture.
Authenticated failed reads retain at most15 fixed stage names with elapsed times
capped at3,000 ms and the active stage at snapshot time. Values contain no request,
credential, game or exception data. Timing includes work and compilation between
markers; it does not claim exact CPU attribution or capture precisely at deadline
expiry. Late callbacks retain existing ownership and cleanup. No timeout or action
behavior changed.

Focused native/shared Python socket checks passed in32.832 seconds. Fixtures cover
before-claim and after-claim timeout, plus a deliberately slow two-stage read with
both completed and active stage timing, bounds and terminal cleanup. The actual
Python client decodes stage reports for event and core routes. Live stage attribution
remains pending.

Stage-diagnostic release `3c959b417806235373fa6aea7af00d85eeecd6c312529debcaa1d556483aa2fa` passed all 71
release groups in 200.192 seconds and is installed awaiting manual setup.
Independent semantic review found no blocker in snapshot races, trace lifetime,
fixed vocabulary, public-data separation or terminal cleanup.

## Stage-diagnostic release: startup passed, resumption failed

Release `3c959b417806235373fa6aea7af00d85eeecd6c312529debcaa1d556483aa2fa`
completed staged startup and entered Setting2 (parent1/1/1,43 event reads).
Combat attempted/accepted/reconciled was13/10/9, with3 known no-mutation stale
rejections,73 combat and73 continuation reads, and42 choice probes. The last
response was backend_fault; host invalid_event_resume. UI showed the humiliation
Proceed page, HP80/80 and gold99. No resumed Proceed/map input was sent and no
uncertain mutation was retried. Remaining cases were not attempted.

The roster and inner-layout corrections alone were insufficient. The remaining
resumption rejection needs a bounded diagnostic. No timeout stage report was
emitted because startup succeeded on this attempt; cold-start intermittency is
not explained by that success.

Normal quit, stopped process/closed listener, exact owned quarantine/purge and
429 unchanged base files/zero overlays passed. No bridge remains installed.

## Resumption rejection diagnostics

Added a closed native enum describing callback ownership/context, retained versus
foreign callback parent, callback task/finalizer failure, run/room/layout identity,
map flags, capstone/selector state and item settlement. The first native rejection
is preserved; existing status and guard outcomes are unchanged. The shared core
adds its normalized value as `resume_diagnostic` to terminal `backend_fault`.
No native data, exception text or new action authority is exposed.

Focused resumption fixtures pass279 assertions, including retained callback parent,
individual map flags, invalid/replaced layouts, duplicate callback and task failure.
The shared-router gate passed in4.073 seconds, including normalized unknown enum
values and unchanged terminal response behavior. Independent review found and
resolved two diagnostic gaps: read exceptions now return the terminal diagnostic
status, and hook failures preserve an earlier handoff cause. Added fixtures cover
both. A subsequent focused shared run could not bind its loopback socket inside
the sandbox; the final release gate reruns it with that access. Live attribution
remains pending.

Resumption-diagnostic release `c626e0cf6b66d708afc3eda1fd165d62d1a0715bb083c0d35f6f24e16ef8f86a` passed all 71 release groups in
273.899 seconds, including 10,044 native assertions, 965 shared checks and
474 integration cases (412 native). Independent semantic review found no remaining
blocker after the two corrections. The package is installed after fresh stopped
runtime and unchanged-base checks, awaiting manual Profile 3 setup. No live input
has been sent with this release. Live resumption attribution remains pending.

## Resumption diagnostic: enabled travel flag

Release `c626e0cf6b66d708afc3eda1fd165d62d1a0715bb083c0d35f6f24e16ef8f86a` reached the Dummy humiliation ending again and emitted
`context_travel_enabled`. Initial choices were untouched: HP80/80, gold99, deck10,
floor5. Event entry was1/1/1 with41reads. Combat attempted/accepted/reconciled was
10/10/9, with0 stale rejections,68 combat/continuation reads and41 choice probes.
No Proceed/map input or uncertain retry occurred. Remaining cases were not run.

Pinned offline IL inspection shows `CombatManager.EndCombatInternal` calls
`NMapScreen.SetTravelEnabled(true)` at offset1119. This establishes a mismatch
with the bridge's requirement that travel remain disabled during resumption.
The correction must cover both retained resumption and fresh event binding while
preserving exact ownership and actual map-open/traveling checks.

Normal quit, stopped process/closed listener, exact quarantine/purge and429
unchanged base files/zero overlays passed. No bridge remains installed.

## Finished-event travel correction

The retained resumption path now permits enabled travel only for the exact finished
event. Map-open and traveling states still fail. Fresh event admission and Proceed
reservation independently require that finished event's exact sole Proceed, inner
layout, current native EventRoom and player run. No native travel flag is changed.
The normal successful callback/open-map reconciliation remains required.

Focused native checks pass336 assertions, including finished resumption through
old-owner disposal, a fresh event read, one Proceed and map reconciliation; owned
potion collection with enabled travel; and unfinished/open/traveling/identity and
reservation adversaries. The inert fixtures do not establish live success.

The focused native-to-Python surface gate passed in23.939 seconds, including the
new finished-event Proceed case. Independent semantic review found no remaining
blocker across admission, reservation, rewards, disposal and map reconciliation.

The first release attempt stopped at production compilation: the pinned game's
OptionButtons property is enumerable, while the fixture exposes a list. The
sole-option check now enumerates at most two entries. Production compilation
passed in1.815 seconds, focused native checks again passed336 assertions, and
independent review found no distinct issue. The final gate reruns integration
against this corrected source; the failed build is not accepted release evidence.

Finished-travel release `0ee889be012b9a8428fcdb75d5cc4c370b68eee33c9f33b92aedfe704cf78e78` passed all 71 release groups in
207.447 seconds, including 10,101 native assertions, 965 shared checks and
475 integration cases (413 native). Package/source identity and stopped runtime
were verified, and the package is installed awaiting manual Profile 3 setup.
No live input has been sent with this release; live resolution remains pending.

## Setting2 finished-travel release: passed

Release `0ee889be012b9a8428fcdb75d5cc4c370b68eee33c9f33b92aedfe704cf78e78` passed the training-expiry → resumed event → Proceed → map path.
User-prepared untouched choices were visually confirmed at HP80/80, gold99, deck10,
floor7. Entry was1/1/1 with42reads. Combat attempted/accepted/reconciled was12/10/10,
with2 known no-mutation stale rejections,73 combat/continuation reads and43 choice
probes. Resumed Proceed was1/1/1 with32reads (including fresh hook preparation).
Map handoff passed in1read with5 candidates; UI confirmed the open map at HP80/80
and gold99. No map candidate was selected.

This demonstrates training expiry and owned resumption through map return, not
victory, upgrades or Setting1 potion rewards. Startup succeeded on this attempt;
intermittent cold-start delay remains unresolved. The same game process and bridge
remain open awaiting Setting1 setup; final cleanup is pending batch completion.

## Setting1 potion reward: passed in the same process

Release `0ee889be012b9a8428fcdb75d5cc4c370b68eee33c9f33b92aedfe704cf78e78` passed Setting1 combat → owned Attack Potion collection → resumed
Proceed → map, in the same game process as the successful Setting2 test. User
setup was untouched initial choices, HP80/80, gold99, deck4, floor9, one occupied
potion slot and two free slots. Entry was1/1/1 with43reads. Combat was5/5/5,
0stale rejections,57combat/continuationreads and36choiceprobes. The owned item
collection was1/1/1 with2reads; its verified key was ATTACK_POTION. Resumed Proceed
was1/1/1 with32reads. Map handoff passed in1read with4candidates.

UI confirmed the open map, HP80/80, gold99 and a newly occupied second potion
slot. No map candidate was selected. The next case is Dense Vegetation; the game
and installed bridge remain open, with final cleanup pending batch completion.

## Dense Vegetation fight: passed in the same process

Release `0ee889be012b9a8428fcdb75d5cc4c370b68eee33c9f33b92aedfe704cf78e78` passed Fight after Rest → non-resuming combat victory → rewards →
map in the same process as both Dummy cases. User setup was HP80/80, gold99,
deck4, floor11, two occupied potion slots. Event entry was1/1/1 with43reads.
Combat attempted/accepted/reconciled was11/7/7, with4 known no-mutation stale
rejections,140reads and128choice probes. Rewards were5/5/5 with12reads:12gold,
VICIOUS and FIRE_POTION. Map handoff passed in1read with5candidates.

UI confirmed the open map, HP49/80, gold111, deck5 and all3potion slots occupied.
No map candidate was selected. The next case is The Lantern Key's Fight after
Keep the Key; user setup requests full HP and a free potion slot. Game and bridge
remain open; final cleanup is pending batch completion.

## The Lantern Key: combat handoff stopped

Release `0ee889be012b9a8428fcdb75d5cc4c370b68eee33c9f33b92aedfe704cf78e78` accepted Fight after Keep the Key in the same process after both
Dummy passes and Dense Vegetation. User setup was HP80/80,gold111,deck5,floor13,
two occupied potion slots. Event attempted/accepted/reconciled was1/1/0 with32reads.
The final response reported `pending_ownership`, and the host stopped with
`unsupported_state`. UI showed combat started against a101HP enemy,player80HP,
turn1. No bridge combat actions, reward input or map input were sent; no retry.

Pinned TheLanternKey.Fight IL calls the expected generic
EventModel.EnterCombatWithoutExitingEvent with special-card extras. The failed
GenericEventV7Hooks.Owns predicate remains unidentified; this observation does not
establish a hook, thread or binding root cause. The special-card reward remains
unexercised live. Punch Off was not attempted.

Normal quit, stopped process/closed listener, exact owned quarantine/purge and429
unchanged base files/zero overlays passed. Four generated files were removed.
The batch is stopped and fully cleaned up. Both Dummy cases and Dense Vegetation
retain their successful evidence; no bridge remains installed.

## Correcting the combat-handoff failure label

Source inspection found that `pending_ownership` remained set after Owns passed
and while CombatHandoff.Capture ran. The Lantern failure therefore does not
establish which ownership or combat condition failed; the previous diagnostic
was a stale stage label. No underlying handoff cause is yet confirmed.

The diagnostic path now separates the existing ownership predicates and combat
callback/run/reward/encounter/state/parent/player/node/retained-identity checks.
Waiting and successful combat states also have explicit labels. Existing enum
values remain fixed; the appended names are closed, normalized and bounded to
33characters. No native data or exception text is exposed, and no guard, action
authority, deadline or cleanup behavior changed.

Focused handoff/ownership tests pass58 assertions. Shared checks cover every
closed enum name and unknown-value normalization. Independent semantic review
found no blocker. Live attribution remains pending.

Handoff-diagnostic release `28a95ff64c53339cfe007bd50d094118b4c9a79935a4636718427be66fac1c35` passed all71 release groups in209.252 seconds:
10,134 native assertions,1,229 shared checks,475 integration cases (413 native),
reproducible packaging and installation/cleanup fixtures. Source/package identity,
stopped runtime and unchanged base installation were verified. The package is
installed awaiting manual Lantern Key setup. No live input has been sent with
this release; the underlying rejection remains unconfirmed.


## Lantern Key diagnostic: prepared encounter identified

Release `28a95ff64c53339cfe007bd50d094118b4c9a79935a4636718427be66fac1c35`
accepted Fight after Keep the Key, then stopped with `combat_encounter` and
`unsupported_state`. Event attempted/accepted/reconciled was 1/1/0 with 32 reads.
User setup was HP80/80, gold111, deck4, floor13 and two occupied potion slots.
UI showed turn1 against the 101HP Mysterious Knight, player80HP, three energy and
four Bludgeons. No bridge combat actions, reward input or map input followed.
There was no retry; Punch Off was not attempted.

Pinned native IL explains the mismatch: combat-layout events reuse the combat
state and mutable encounter created before the option is selected. Their entry
method ignores the fresh encounter argument. It clears EventModel.Node and
transitions the existing embedded combat node to the active CombatRoom before
setting up CombatManager. The ordinary event layout creates a new combat state.

Normal quit, three stopped-process samples, two closed-port samples, exact owned
quarantine/purge, four generated files removed, 429 unchanged base files and zero
overlays passed. Installed state was
`375ec26f9d8a639c4d70515855ce3022105a65d9b16997ccbd530e52da0e4a0a`;
quarantined state was
`556f447aac4cb6bdb1c32ad4d6948ca4ee705f46b07ee1e536e8685d75b14e81`.
The diagnostic attempt is fully cleaned up. No profile/save/history/Cloud files
were accessed. The corrective build is being validated; no corrected live result
is claimed here.


Prepared-combat correction release `6cc54f193c98028f1bfe94d8f65558fc3d513ef2793125b692969c1c83c68319`
passed all 71 release groups in 209.390 seconds: 10,210 native assertions,
1,229 shared checks, 475 integration cases (413 native), reproducible packaging
and installation/cleanup fixtures. Independent semantic review found no blocker.
Focused 174 checks cover different fresh/prepared encounter identities,
replacement state/encounter/node, creation mode, native node retirement,
post-disposal ownership and embedded special-card collection through map return.
The package is installed awaiting manual Lantern Key setup. Source/package and
installed overlay identities passed; base installation remains unchanged.
No corrected live result is claimed. Punch Off remains pending.


## Lantern Key prepared-combat correction: passed live

Release `6cc54f193c98028f1bfe94d8f65558fc3d513ef2793125b692969c1c83c68319`
passed Fight after Keep the Key → combat victory → exact LANTERN_KEY special-card
collection, Tremble and 17 gold → verified map return. User setup was Profile 3,
HP80/80, gold111, deck4, floor13 and two occupied potion slots.

Event entry attempted/accepted/reconciled was 1/1/1 with 32 reads. Combat was
11/7/7, with four known no-mutation stale rejections, 97 reads and 85 choice
probes. Rewards were 5/5/5 with 13 reads. Map handoff passed in one read with six
candidates. UI confirmed the open map at HP29/80, gold128, deck6 and two occupied
potion slots. No map candidate was selected.

This demonstrates the representative prepared-combat handoff and exact special
card grant; it does not establish every event branch or strategic quality.
The game and bridge remain open for Punch Off in the same session. Final batch
cleanup is pending; no profile/save/history/Cloud filesystem access occurred.


## Punch Off: passed in the same process; batch cleaned up

Release `6cc54f193c98028f1bfe94d8f65558fc3d513ef2793125b692969c1c83c68319`
passed Punch Off Fight after I can take them → combat victory → exact Shackling
Potion and Bag of Preparation collection, Stampede and 10 gold → map. This was
the same process as the successful Lantern Key test. User setup was HP80/80,
gold128, deck6, floor15 and two occupied potion slots.

Event entry attempted/accepted/reconciled was 1/1/1 with 32 reads. Combat was
13/9/9 with four known no-mutation stale rejections, 139 reads and 125 choice
probes. Rewards were 6/6/6 with 14 reads. Map handoff passed in one read with one
candidate. UI confirmed the open map at HP38/80, gold138, deck7, all three potion
slots occupied and the new relic visible. No map candidate was selected.

This demonstrates deferred potion/relic combat rewards with sufficient capacity;
it does not establish every pickup effect, full-inventory policies or strategic
quality. The two remaining cases passed and the planned batch is complete.

Normal quit, three stopped-process samples, two closed-port samples and exact
owned quarantine/purge passed. Four generated files were removed; all 429 base
files were unchanged and overlays were zero. Installed state was
`1107dfcbce43e361eb6e597bd6a17f443a8f60f35070f1337bece5fe1a74733f`;
quarantined state was
`838555ecd2479b19bfac369fa121ba7f358534721fecaa3f0604905f4cdc9c61`.
The game is stopped and no bridge remains installed. No profile/save/history/
Cloud filesystem access occurred. Exact result and sanitized diagnostic hashes
are retained in the current validation record under their original release.
