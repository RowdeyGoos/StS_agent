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


## September 13: first shop/inventory batch stopped at removal

Release manifest `86c5646c8891716a6eb166a40b823fa58555229144b58441a4cacf8ab7a4d298`,
installed state `bac5f7d49d16bb533da707cb76117ee8bc6efe578f65d979f99d173718f7ef06`.
The user manually launched Profile3. UI setup started an Ironclad run, took Golden
Pearl, entered a native map combat room, then used the native console `room Shop`.
The console was closed and ordinary merchant inventory opened. Original deck:
five Strikes, four Defends, one Bash; gold249, displayed removal price75.

The existing client used removal policy `first`, purchase limit1, reserve100.
Health passed immediately before the attempt. Result: **failed**, `unsupported_state`,
**1 attempted /1 accepted /0 reconciled**, no child actions. No mutation was retried.
UI afterward showed gold174, four Strikes/four Defends/Bash, deck9 and exhausted
removal service. These visible effects do not establish exact object identity or
completed native reconciliation. The client did not close/leave or verify map return.
The exact failing predicate remains undetermined; no safeguard was bypassed.

Result: `/private/tmp/sts-shop-inventory-20260913-shop_removal.json`; SHA256
`e8e72ad9c5c293aeaf67450dddcfada51d115af8fd54e5626e5df0e9c70ccee5`. Policy elapsed time: **0.681 seconds**.
Queue: `/private/tmp/sts-shop-inventory-batch-20260913.json`; seven other cases
remain unattempted. Normal application quit completed. Fresh require-stopped
passed with three process/two port samples; owned quarantine and purge passed,
removing four generated files and leaving installation phase `absent`. Quarantine
state: `3913cc7d53bbac227bdf7b59f3341680b95f158d2a2970db8cdc591f6cba0acc`.
No profile/save/history/Cloud filesystem content was accessed.

### Removal investigation: asynchronous observer ordering

Read-only static IL inspection verified the pinned `sts2.dll` SHA256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
`NCardGridSelectionScreen.CardsSelected()` is an async method: separate calls
produce separately completing waiter tasks over its completion source. Native
removal spends gold, removes the card, increments the removal counter, marks the
service used and publishes purchase completion. The bridge invokes CardsSelected
a second time to observe the result. Its `ReadCompletion()` treats successful
purchase plus an incomplete observer as Invalid through `SelectedExactly()`.
`Advance()` also rejects an already-completed wrapper while that observer is
still pending and latches `_failed`. Completion cannot recover afterward.

A bounded inert experiment reused the accepted release's compiled removal fixture
and replaced only its private observer task with a separately scheduled waiter.
The control removed one card, debited10gold, incremented the counter and returned
Succeeded. Delaying the bridge observer produced the same effects but returned
Invalid, rejected Advance and stayed Invalid after the observer completed.
The fixture's ordinary `CardsSelected()` stub returns the same task on every call,
which explains why its existing cases miss this ordering. This demonstrates a
logic defect, not the actual scheduling or failing predicate of the live attempt;
that response preserved only `unsupported_state`.

Probe source/result: `/private/tmp/sts-removal-order-probe/Program.cs` and
`/private/tmp/sts-removal-order-probe/result.json`. Pinned native IL:
`/private/tmp/sts-removal-investigation-il.json`. The correction should wait
within the existing bound for both owned tasks, reject fault/cancellation/wrong
selection, and then verify the exact effects before acknowledging completion.
No production sources, package identities or runtime guards were changed during
this investigation, and no additional live mutation was sent.


### Removal correction prepared for a fresh attempt

Release `350783f794a740359c9114f7b0e6b0eabf752e0832d4a200c95e325019ccfb89` contains the independent-observer completion fix. The new
regression failed against the old implementation and passes with the correction:
229 focused removal checks, including delayed observer/callback/wrapper orders,
wrong/faulted/canceled observations, changed context and sticky failed disposal.
Independent semantic review found no blockers. Direct-input fixture integration
passed in 3.815 seconds after mirroring its separate per-call test stub. The accepted
full gate passed 71 groups in 313.883 seconds. One earlier gate stopped at
the missing mirrored test-stub member; it did not produce an accepted release.
The exact original live predicate remains unconfirmed; offline reproduction is
not repinned as a live pass.

New installed state `3b6c114fa0c853b2e302a722c2b8f35fca79a65cebc154b2e101f1b6c5158cdf`; fresh queue `/private/tmp/sts-shop-inventory-removal-order-20260913.json`. Owned installation and
metadata verification passed while the game and listener were stopped. Manual
Profile 3 launch is pending; no input has been sent on this corrected package.


### September 13: corrected removal and inventory batch completed

Release `350783f794a740359c9114f7b0e6b0eabf752e0832d4a200c95e325019ccfb89`,
installed state `3b6c114fa0c853b2e302a722c2b8f35fca79a65cebc154b2e101f1b6c5158cdf`,
passed seven cases in one manually launched Profile 3 session. Fresh runtime and
authenticated health checks passed before input. Each later setup followed a
native map room entry; console-created shops/events were visibly confirmed and
the console closed before bridge actions. No uncertain mutation was retried.

Counts below are attempted/accepted/reconciled. Event counts include parent and
child actions. Each shop ended with separate inventory close and Leave, followed
by an independent actionable-map read; event-map also checked the map independently.

| Case | Actions | Visible outcome | Execution seconds |
| --- | --- | --- | --- |
| Exact shop removal | 3/3/3 | Gold 249→174, deck 10→9; four Strike, four Defend and Bash retained; removal reconciled before close/Leave | 1.150 |
| Mixed shop purchases | 10/10/10 | Seven cards and one potion; gold 2174→1532, deck 9→16 | 1.379 |
| Restock and replacement | 8/8/8 | Three original-potion discards and three purchases; gold 1532→1394, deck16, all three original icons replaced | 1.119 |
| Potion Courier skip-full | 3/3/3 | Full original belt retained; three offered potions unclaimed; deck16 | 3.037 |
| Potion Courier replace-first | 8/8/8 | Three discards and three acquisitions; full belt of Foul Potions; deck16 | 3.690 |
| Lost Coffer skip-full | 5/5/5 | Card acquired, deck16→17; three original Foul Potions retained | 3.444 |
| Lost Coffer replace-first | 6/6/6 | Card acquired, deck17→18; first original potion replaced, other two retained | 3.526 |

All seven map checks passed: one candidate each except the final case, which
had two. All 43 actions were accepted and reconciled. Execution totaled
17.345 seconds; setup, user wait and cleanup were not separately timed.

Potion Belt/passive-relic purchases were deferred: Potion Belt was absent from
three inspected ordinary merchant inventories. Direct relic grants were not
substituted for purchase evidence. The restock setup used native console grants
of THE_COURIER, FIRE_POTION and FOUL_POTION before creating its shop. Mixed
purchases used 2000 console-added test gold. Fresh Lost Coffer setup used
`ancient NEOW LOST_COFFER`; the spent Coffer relic was removed before the second
case. No profile/save/history/Cloud filesystem content was accessed.

Evidence limits: the restock result retains aggregate counts; same-entry
restocking follows the first-eligible policy and successful native refreshed
generation checks, without a retained per-purchase trace. Lost Coffer used three
distinct original native objects of the same potion kind, carried from Courier;
UI cannot distinguish their object identities, while native slot/object checks
remain enforced. The mixed card menu belongs to the item child, so zero completed
pure-card children does not mean no card was collected. Generic parent effects
remain `unverified`; these passes establish the selected child policies and
verified map return, not every automatic parent effect. The original failed
removal predicate remains unlogged; this fresh pass establishes representative
corrected behavior without relabeling the earlier failed attempt.

The authoritative queue is
`/private/tmp/sts-shop-inventory-removal-order-20260913.json`; current validation
retains its setup, result and diagnostic records. Result files use the prefix
`/private/tmp/sts-shop-inventory-removal-order-20260913-` plus the case ID and `.json`.

| Case ID | Result SHA256 |
| --- | --- |
| `shop_removal` | `0f0c3ec09f5d7a80fc7243872abd8386eb5d37e1c697b68411207ae624a02b78` |
| `shop_mixed` | `109a5ea7850049fc6b3493d8a7b82a076ee95a5268b3c5f0c83189fedc307de3` |
| `shop_restock_replace` | `cb91474fd7959ca5d24d93d98a95ea91fc790685c942848bea32bedd1a809953` |
| `courier_skip_full` | `d3430aa617085bbc30cf72fa595dccdbb02d8b0ab88796522be783ed7e1f2ee6` |
| `courier_replace_first` | `8ddc575b44541f291c52dca71e6ef771493ba1d8ea010fa60ac6303bd567e43d` |
| `coffer_skip_full` | `da8593aeda0411e48fd054333f01ec4dd2c49cdfcda6cd5a30de58be5d4add75` |
| `coffer_replace_first` | `b05af6a2e8893c2e8069e51ce44b3e0d1b594c930fb452804e5286607dd87f13` |

Normal application quit completed. Fresh require-stopped passed with three
process samples and two port samples: game process stopped, listener closed.
Owned quarantine passed with state
`6139fb9fc7cbffeaa240b377e302c7f9fd5e3489fdab2e0e287f708584982ece`.
Purge passed, removed four generated files and left phase `absent`. The accepted
release package remains retained. Further live coverage includes actual-stock
capacity/pickup-selector purchases, full-inventory combat/resume rewards and
additional explicit policy variants; this session does not close those cases.


### September 13: combat/resume inventory batch stopped before gameplay

The same accepted release `350783f794a740359c9114f7b0e6b0eabf752e0832d4a200c95e325019ccfb89`
was installed with state
`b73d449cfd993fc470cba24635fc1b3a43eb9ed195159b26c0049bc25c04196e`.
Current source/package identities and owned installation metadata matched. Fresh
require-running and authenticated health passed; UI confirmed Profile 3.

After Continue, native Proceed/map and native rest-room entry, console
`event BATTLEWORN_DUMMY` created untouched initial choices. The previous full
belt was retained (gray rectangular potion and two Foul Potions), HP80/80 and
gold1394. The prior18-card deck was replaced through exact native console
remove/add commands with four Bludgeons; the open deck UI confirmed four
32-damage cards. One `STRIKE` lookup failed without mutation before using the
exact `STRIKE_IRONCLAD` ID. Console and deck overlays were closed before input.

The existing bounded client selected the Setting1/skip-full policy but stopped
on the initial GET: `invalid_response`, one read, zero attempted/accepted/
reconciled parent or child actions, effects `none_attempted`, combat not attempted.
Execution took0.732seconds. UI still showed the untouched initial choices. One
read-only follow-up through the existing client was refused; the listener was
no longer accepting connections. No gameplay mutation was retried or adopted.

Result: `/private/tmp/sts-combat-inventory-batch-20260913-dummy_skip_full.json`,
SHA256 `d47cd1a3b47973a9b27f1d12d4f0c30889fec72bb0c406a49a647a1fd53e99d1`.
The empty stderr diagnostic has SHA256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Follow-up metadata is in
`/private/tmp/sts-combat-inventory-batch-20260913-read-diagnostic.json`;
its hash is retained in the queue/current validation. No raw response or
credential was logged, and no profile/save/history/Cloud content was accessed.

The initial response bytes were not retained, so the exact failure category
and cause are unproven. Static inspection shows runtime read-dispatch failures
can return bounded error/stage metadata and terminate ownership; the generic
host expects its normal event envelope and can collapse that boundary to
`invalid_response`. This is a candidate explanation, not evidence of the actual
dispatch status. The next controlled attempt should retain the already-defined
bounded initial-read category/stages before host decoding. This attempt says
nothing about full-inventory reward behavior. All five cases remain open:
Dummy skip-full/replacement and Punch Off skip-full/replacement/skip-all.

Normal app quit completed. Fresh require-stopped passed with three process/two
port samples. Owned quarantine passed with state
`3c6c6c4f0f2822b7e0047a3638648571a67bf0e338f6c74c885b8b9ca4c286cb`;
purge removed four generated files and left phase `absent`. No code or package
was changed, and prior seven-case passing evidence retains its original scope.


### Initial-read diagnostic retention prepared

Release `3baa36cfda7ae2ce128412ff62fff9f2ea54deaf01c745fb1460999e3c9df419` retains only the already-defined runtime failure code and bounded stage timings in `read_diagnostic`. The normal host result and action counts remain unchanged. Duplicate/unknown fields, unbounded values, free-form text and malformed framing cannot become retained diagnostics; POST responses are excluded. Normal response parsing, native timeouts, owner termination and no-retry behavior are unchanged.

75 client tests passed. Focused actual-listener integration passed in60.465seconds, including an event read timing out before claim, host `invalid_response`, zero attempted actions, no map handoff and retained dispatch diagnostics. Independent semantic review found no blockers. The final release gate passed71groups in321.185seconds. Implementation/review/preparation were not separately timed. The accepted native DLL/package exactly matches the preceding350783 release; four Python client/test inputs changed. This closes diagnostic loss, not the unproven original native failure.

The original release/validation/README are retained at `/private/tmp/sts-read-diagnostic-previous-release`. Fresh stopped checks, owned installation and metadata verification passed. Installed state: `78aec70944eed0695d9cdafe2f1a610b1db10e655d4e516680f3e3f5123e71c6`. Fresh queue: `/private/tmp/sts-combat-inventory-diagnostic-20260913.json`. Manual Profile3 launch is pending, with no live input on this client revision. Final owned cleanup is pending the session.


### Diagnostic-enabled session: Dummy skip passed; second combat stopped

Release `3baa36cfda7ae2ce128412ff62fff9f2ea54deaf01c745fb1460999e3c9df419`, installed state
`78aec70944eed0695d9cdafe2f1a610b1db10e655d4e516680f3e3f5123e71c6`. Fresh running/health and source/owned-install
checks passed; UI confirmed Profile3. Continue resumed the native rest room.
The18-card saved test deck was replaced through console commands with four
Bludgeons; open-deck UI verified them. The first event command arrived as `ent`
and was rejected without mutation; corrected `event BATTLEWORN_DUMMY` succeeded.
Console and deck overlays were closed before bridge input. Full original belt:
gray rectangular potion and two Foul Potions; HP80/80 and gold1394.

Dummy Setting1/skip-full passed in14.775seconds. Event entry1/1/1; combat5/5/5
with no stale rejections; owned resume-item dismissal1/1/1, collected none,
discarded0, skipped true; resumed Proceed1/1/1. Native outcome `event_resumed`.
Independent map check passed in1read with2candidates. UI confirmed the map,
HP80/80, gold1394 and unchanged original potion icons. Parent automatic effects
remain unverified. Initial-read failure did not recur; there was no read diagnostic.
Result SHA256: `e1e3775dcad1222ae4d28c1a06bfcd6872e851493c5eda8e296c2d36e38db3b3`.

After native map entry into a treasure room, a fresh console-created Dummy had
untouched initial choices, the same four Bludgeons, HP80/80/gold1394 and full belt.
Replacement policy entered combat successfully (event1/1/1), then failed with
`invalid_response` at the first combat action:1attempted/0accepted/0reconciled,
8reads,7choiceprobes, no resume-item episode. Execution4.690seconds. UI showed
Dummy75/75, player80/80,3energy, four Bludgeons and turn1. No reward or map was
reached; no action was retried or adopted. No read diagnostic was present, as this
failure followed a POST. The three Punch Off cases were not attempted.
Result SHA256: `da8191d577521b1e9b40aa85adb28a656e21a11fc37272a3c6c8ff0b72551358`.

Both result paths, empty stderr hashes, actual setup and UI observations are in
`/private/tmp/sts-combat-inventory-diagnostic-20260913.json` and current validation. Policy execution totaled19.465seconds; setup and
cleanup were not separately timed. No profile/save/history/Cloud content was read.

Narrow source inspection found a concrete collision risk: PublicCombatDecisionIdentity
hashes round, public player/enemy/hand state and legal actions, without an encounter
or session identity. BeginObservedCombat resets terminal bookkeeping only.
BridgeTransportRuntime.ReservePost keeps path/decision/action reservations for its
entire lifetime and stops on duplicates. Two identical native combat openings can
therefore reuse an already-reserved action. This fits these identical setups but
is not exact evidence of the failed POST: its request identity and original response
were not retained. A focused cross-combat regression is the next correction step;
no runtime safeguard, source or package was changed during this investigation.

Normal quit, fresh require-stopped (three process/two port samples), owned
quarantine and purge passed. Quarantine state:
`d6fd496d459e1dec6390a5392ee094954b5d5aeffac4e1dae105f91e6f02ac1e`.
Four generated files were removed; installation is absent. The accepted package
and both original live results remain retained under this release identity.


### Cross-combat identity correction prepared

Release `593fed9a09e7a9ee69c73903dfbdc9dbdc1f28d55f8bb12b3556c4e3563851d2` binds 358 inputs and a rebuilt native package. A real native reader/action-applier regression reproduced rejection of the first action in a second identical combat with the old public-state-only identity. An opaque scope keyed to the exact native CombatState now separates those combats; the same object retains its ID across repeated reads, waits, BeginObservedCombat and public-state A→B→A. No native action or transport reservation ledger is cleared. Scoped IDs remain opaque 64-character hexadecimal strings.

The corrected regression passes, including stale prior-combat IDs, same-combat replay, no extra enqueue and enqueue-then-throw protection. Actual listener fixtures accept both combat openings and still stop on old reserved POST replay or a lost response. Focused validation passed in 64.438 seconds: 269 native combat/chooser checks, 1261 unified checks and shared-client socket integration. Independent semantic review found no blockers. Pinned static IL establishes native combat allocation and exact reader state identity; it is not game execution. The original failed live POST is still not exact causal proof.

The first full release attempt at `/private/tmp/sts-combat-identity-release` failed inside the Roslyn compiler in unchanged item transport code (MissingMethodException), and was not accepted. The affected check passed with the same SDK/settings in 10.179 seconds. All 4844 installed SDK archive files matched (1.617 seconds). A fresh full release gate then passed 71 groups in 267.627 seconds, including reproducible build/package/clean-install validation, at `/private/tmp/sts-combat-identity-release-accepted`. Implementation, review and preparation were not separately timed.

Fresh stopped checks, owned installation and credential-free metadata verification passed. Installed state: `b6b15df69a5926d693372e2bc15920fdb8280b1dd850292852ab6a1e251e28f8`. The five-case queue `/private/tmp/sts-combat-identity-live-20260913.json` is prepared for manual Profile 3 launch at the main menu. No live action has been sent on this release. Both fresh Dummy combats must run consecutively in one process with matched initial public states; then three Punch Off policy cases follow if successful. Old failed actions are not retried or adopted. Final owned cleanup is pending the live session; no profile/save/history/Cloud content was accessed.


### Combat-identity release: first Dummy passed; native transition stalled

Release `593fed9a09e7a9ee69c73903dfbdc9dbdc1f28d55f8bb12b3556c4e3563851d2`, installed state `b6b15df69a5926d693372e2bc15920fdb8280b1dd850292852ab6a1e251e28f8`. Fresh running, release/source, owned-install and authenticated health checks passed. UI confirmed Profile 3; Continue resumed a native treasure room at HP80/80, gold1394, four Bludgeons (verified in deck UI), gray rectangular potion and two Foul Potions. Native console created a fresh untouched Battleworn Dummy; console was closed before client input.

Setting1/skip-full passed in 14.830 seconds. Entry 1/1/1; combat 5/5/5, zero stale rejections; resume-item native dismissal 1/1/1, collected none, discarded0, skipped true; resumed Proceed 1/1/1. Independent map check passed in one read with two candidates. UI confirmed open map, HP80/80, gold1394 and retained original potion icons. Result SHA256 `88b31b95b2cf711e9549c07232ed4bf7796f942994e45f64f0a68ede78983bb5`. No read diagnostic was emitted. Automatic parent effects remain unverified.

For the next setup, the agent clicked the connected unknown native map node above the current treasure room. The game stayed on a black screen across repeated observations; console still opened and showed only the prior successful Dummy creation. No console command was submitted during the stall. After closing console, one read-only map request reported status waiting, screen_kind unknown, actionable false, no candidates/legal actions. This did not fail transport and does not establish the native transition cause. No second Dummy combat started; replacement and all three Punch Off cases were unattempted. The cross-combat identity correction remains offline-proven but not yet demonstrated in consecutive live combats. No uncertain action was retried or adopted.

Normal app quit succeeded. Fresh require-stopped passed (three process/two port samples). Owned quarantine state `a7acf046803ae2a04df06931e2b26910fefca240c9b48d7f3ffe8f2b2aa6a0ec` passed; purge removed four generated files and left phase absent. Queue/results are retained at `/private/tmp/sts-combat-identity-live-20260913.json`. Policy execution was 14.830 seconds; setup/cleanup were not separately timed. No profile/save/history/Cloud content was accessed.


### Native transition investigation and control prepared

Pinned static IL `/private/tmp/sts-map-transition-il.json` (SHA256 `36006cc1660b15f2008179b2f7ddd80e652d2dbfc31c25df77688c61c294c7cf`) shows fade-out precedes native map entry; successful entry clears IsTraveling and fades in. EventRoom.Exit awaits tracked option tasks, followed by other synchronization/generation/entry stages. The existing waiting/unknown public map response cannot identify which stage stalled. RoomSet uses modulo indexing and permits event repetition after one bounded eligibility scan, ruling out a simple claim that unique-event exhaustion necessarily hangs. No exact runtime exception or task state was retained; neither a native/setup cause nor a bridge cause is proven. No source or runtime safeguard was changed.

Reused accepted release `593fed9a09e7a9ee69c73903dfbdc9dbdc1f28d55f8bb12b3556c4e3563851d2` after exact source and retained package verification; no redundant build/test pipeline. Fresh stopped checks, installation and credential-free metadata verification passed. Installed state `f4d20cd032d2ca96030746a1d275bdb8a206cb0a1bd23bfa29cb21cb9ba9169b`. Queue `/private/tmp/sts-transition-control-20260913.json` starts with a fresh disposable Profile 3 run and a native-UI-only Dummy/skip/Proceed/next-room control, then the two consecutive bridge Dummy cases plus Punch Off policies. Prefer known connected room nodes for setup, and verify actual settled room content. This is a diagnostic comparison, not a claimed transition fix. Manual launch and final cleanup are pending. No gameplay or profile/save/history/Cloud content access occurred during preparation. Investigation/preparation elapsed times were not separately measured.


### Fresh-run native comparison and reward-policy live batch

Release `593fed9a09e7a9ee69c73903dfbdc9dbdc1f28d55f8bb12b3556c4e3563851d2`, installed state `f4d20cd032d2ca96030746a1d275bdb8a206cb0a1bd23bfa29cb21cb9ba9169b`. Running/source/owned-install/authenticated health checks passed. Profile 3 was visible. The prior disposable run was abandoned through native UI and a new standard Ironclad/no-ascension run started. Golden Pearl was chosen. The verified starter deck was replaced via native console with four Bludgeons and three Foul Potions added. HP80/80, gold249. No profile/save/history/Cloud content was read.

The native control used a fresh console-created Dummy after completed Neow. CUA drag/click card targeting did not complete; Escape restored all four cards and the read-only combat snapshot showed HP80, Dummy75, energy3, four Bludgeons. The user finished the native control directly and reported the next room. Agent UI inspection verified the next 45-HP monster room with full original belt/HP80 and four Bludgeons. No bridge gameplay mutations were used for the control; exact human action counts were not recorded. This input limitation was not classified as a bridge/game failure.

Both bridge Dummy cases then ran consecutively in the same process with matched HP80/80, gold249, four Bludgeons and three Foul Potions. Each entry/combat/resumed-Proceed reconciled 1/1/1, 5/5/5, 1/1/1 with zero stale rejections. Skip-full dismissed the owned potion in 1/1/1; replacement reconciled original discard and offer collection in 2/2/2. UI showed Clarity in slot0 and two retained Foul Potions. Both maps and subsequent native room entries passed (39-HP monster, then unknown→Tea Master). This demonstrates the combat identity correction for matching repeated Dummy openings; original historical POST cause remains unconfirmed.

Punch Off setup used its native I Can Take Them option, then bridge Fight. HP and four-card deck were restored between cases through console; actual relics carried forward. Full-belt skip collected 13 gold, Cinder and The Courier, left Explosive Ampoule, and verified map. Replacement discarded original Clarity and collected a new Clarity, plus 12 gold, Pommel Strike and Bronze Scales; map passed. Exact native replacement supports same-key objects, not just different potion names.

The first skip-all case collected 15 gold, Bludgeon and Tuning Fork while leaving Stable Serum, and verified map. The intended setup discard did not take effect: screenshot review showed a full belt. Its initially recorded empty-slot premise was corrected in the queue, and the result is retained only for full-belt skip-all. User then discarded Clarity; agent independently observed the empty slot on the map, next native elite room, fresh Punch Off and Fight page. The fresh free-slot case won combat, but rewards stopped with unsupported_reward (0 attempted/accepted/reconciled reward actions, 8 reads). UI showed 17 gold, Fruit Juice, Ornamental Fan and a card offer at HP62/80, gold289, empty slot0 and two Foul Potions. No map was reached. The live result did not retain the exact unsupported predicate. No failed bridge mutation was retried or adopted.

Subsequent source investigation on September 13 found an independently sufficient
blocker: `PublicRewardActionBudget.MaximumRewardSessionsPerProcess` is 3.
`CoreNativeFactory` creates one reward reader retained by `BridgeRouter`; a new
client invocation does not replace it. Each completed Punch Off reward screen
advances `PinnedPublicRewardInteractionSession.PrepareParentScreen`'s count.
The fourth screen returns false before `TryCollectParentTargets`, which becomes
the unsupported snapshot and then the client's `unsupported_reward`. The three
preceding Punch Off cases completed terminal rewards and map; the fourth was the
free-slot case. Dummy resume items are served by the event-owned item policy
session and do not consume this counter. The existing `RewardInteractionTestSuite`
explicitly specifies rejection of a fourth session (source inspected here, not
newly executed). This establishes that the configured limit prevents this test,
although the collapsed live response cannot exclude an earlier independent guard.
There is no evidence implicating Fruit Juice, Ornamental Fan or the empty slot.
The batching plan overlooked the module limit. Retest free-capacity skip-all first
in a fresh game process; preserve the limit and bound future batches to three core
reward screens. This investigation changed documentation only, with no game
launch, bridge mutation or release rebuild.

| Case | Seconds | Combat attempted/accepted/reconciled | Reward/item accepted | Map | Result SHA256 |
| --- | --- | --- | --- | --- | --- |
| dummy_skip_full | 14.714 | 5/5/5 | 1 | passed | `a4c3e957a5c6a1d0f50e1181da0f34e064e83ed3cb55a632b21e7cc1cf01db78` |
| dummy_replace_first | 14.431 | 5/5/5 | 2 | passed | `5b20659e4c1f7b8ee4bc683de0554e4ca6f38350d73b0a3e2a5f0d7c94b06cef` |
| punch_skip_full | 16.194 | 11/7/7 | 5 | passed | `e5d4c66586f7e9288b28cf0cff9665257680bac0e5290d5998327effde02b373` |
| punch_replace_first | 16.724 | 11/7/7 | 7 | passed | `2f37b30094bcfbf1508a392b68e9a871b5f2f83c6444c4dcf88f251bf6922dce` |
| punch_skip_all | 17.078 | 11/7/7 | 5 | passed | `85b5d67b40baabc8431fc520091df54b1c3dd1c727004f05791259ce02852790` |
| punch_skip_all_free_slot | 15.856 | 11/7/7 | 0 | not_attempted | `2f1fd3ac5310f4346e306fcfb71a4d9ad5654b89d3d444d2589ba363d88f1dbf` |

Total: 66 accepted/reconciled bridge actions including completed combat before the last failure; 16 known no-mutation stale rejections; five independent map checks and five following native room entries passed. Policy execution 94.997 seconds. Native-control/user-assistance/setup/cleanup were not separately timed. Black-screen and initial-read failures did not recur; this does not identify the earlier cause. No transition source changes or builds occurred.

Normal quit and fresh require-stopped passed (three process/two port samples). Owned quarantine state `ca2b97f00e070d073f561cdc32bde14c1aea6cb94e59c726309c949d85825b39` passed; purge removed four generated files and left phase absent. Full queue, corrected setup evidence, native read result and per-case result/diagnostic hashes: `/private/tmp/sts-transition-control-20260913.json`. Remaining acceptance: skip-all with free capacity, currently blocked by unsupported reward projection before input.


### September 13: first-session skip-all with free capacity

The unchanged accepted release `593fed9a09e7a9ee69c73903dfbdc9dbdc1f28d55f8bb12b3556c4e3563851d2`
was installed with state `177c11ebfac3de03bd6d335a9ac25b672cafb2cfab7e625137ecddb30cba7f4d`.
User manually launched Profile 3. The previous disposable run was abandoned through
native UI; a standard Ironclad run with no ascension was started. Neow/New Leaf was
resolved natively, then the first connected monster room was entered before console
setup. The final deck was independently verified as four Bludgeons, HP80/80, gold99,
with two Foul Potions and slot2 empty. Burning Blood and New Leaf were retained.
Punch Off's native I Can Take Them choice led to the sole Fight option, console
closed. No core reward session preceded this case in the fresh process.

The existing event-combat-map client ran once with potion policy skip-all and reward
policy first-card. Entry reconciled 1/1/1 (35 reads), combat 11/7/7 with four known
no-mutation stale rejections (98 reads), rewards 5/5/5 (13 reads). Power Potion was
left for policy despite free capacity; 14 gold, True Grit and Horn Cleat were
collected. No potion was discarded. The independent map check passed in one read
with one candidate. UI confirmed HP52/80, gold113, deck5, both original Foul Potions
and the empty third slot. During shutdown, Escape closed the map and exposed the
remaining Power Potion reward, independently confirming it was unclaimed. No map
candidate was selected. This establishes the representative free-capacity skip-all
path; it does not test Fruit Juice/Ornamental Fan or all offers.

Total: 13 accepted/reconciled actions; policy execution 16.806 seconds. Native setup,
user wait and cleanup were not separately timed. Result:
`/private/tmp/sts-free-slot-retest-20260913-result.json`, SHA256
`04daff582d8fed8c9d08d0b62c2c5bd0d3ff9806df805a4961bc4eaaab3ba079`.
The diagnostic stream was empty. Queue and actual setup/cleanup evidence:
`/private/tmp/sts-free-slot-retest-20260913.json`.

Normal Save and Quit, main-menu Quit and native confirmation completed. An initial
stopped check correctly rejected while the confirmation remained open; after Yes,
require-stopped passed with three process/two port samples. Exact owned quarantine
`2b8505f404c86908dcbf56e66f35433c0803c73fe988cb6cb8a197af81b00b83`
and purge passed, removing four generated files and leaving phase absent. No source
changes, rebuild or profile/save/history/Cloud filesystem access occurred.


### September 13: Trial popup cancellation and confirmation

Unchanged release `593fed9a09e7a9ee69c73903dfbdc9dbdc1f28d55f8bb12b3556c4e3563851d2`,
installation `99d5eba5397b9a7971bb0bb5450ca9bab5d2ced0ffef5b2b290b1ee06938f5cd`.
User manually launched Profile 3. A fresh standard Ironclad/no-ascension disposable
run used native Precarious Shears to remove two Strikes, leaving HP64/80, gold99,
three Strikes/four Defends/Bash, empty belt and Burning Blood/Precarious Shears.
The first connected native monster room settled before console Trial creation.
Native Accept offered Nondescript, so the optional Merchant/Innocent two-upgrade
case was deferred without bridge input or rerolls. Native Guilty added Doubt;
both offered card rewards were skipped natively, Proceed reached map and the next
connected known room opened with a 38HP enemy.

Fresh Trial was created there, Reject selected via UI, then untouched Double Down
was dispatched by the maintained event-map client with abandon policy cancel.
Baseline deck nine unupgraded cards, HP64/80, gold99, empty belt and both relics
were independently verified. Cancellation resolved its owned modal and fresh
parent bindings; subsequent first-legal actions completed a card-reward child and
map. Parent4/4/4, child5/5/5, two child episodes, 53 reads; map passed in one read
with one candidate. UI confirmed HP64/80, gold99, deck12 and no modal. Deck view
showed another Doubt plus Iron Wave and Anger; these later event effects are
separate from the cancellation's unchanged-state guarantee. The next native
connected room opened normally with enemy HP27/25. Policy time5.035 seconds.
Result SHA256 `6eab9a4e16e51c27522d5ff614eb15567b466e365278b1f482a66e5e5daa33c9`.

A fresh Trial there was prepared at Reject/untouched Double Down, same living
HP64/80, gold99, deck12 and empty belt. Final-case events client explicitly used
abandon policy confirm. Parent1/1/1 and child1/1/1, 40 reads, destination
run_abandoned, policy time3.006 seconds. UI independently showed Defeat and HP0/80,
with no modal. This is native task/abandoned-state reconciliation, not a claim
about persisted history. Result SHA256
`719d4fb11e51e7b9ce2f2229a6818841b7092eb77984e438ceab4b96bc690fd3`.

Both diagnostic streams were empty. Total11 accepted/reconciled actions and
8.041 seconds policy execution; setup/user wait/cleanup were not separately timed.
No core reward session was consumed. Queue, commands, actual setup and per-case
results: `/private/tmp/sts-trial-live-20260913.json`. No gameplay mutation was retried.

Native Continue/results/Main Menu/Quit/Yes completed normal shutdown. Fresh
require-stopped passed with three process/two port samples. Exact owned quarantine
`7ccdfeb56d844d07cea0207ecdf97531710422bf36c051f441f208a7b040b3b2`
and purge passed; four generated files removed and phase absent. No source change,
rebuild or profile/save/history/Cloud filesystem access occurred. Trial multi-upgrade
remains open solely because the native Merchant setup was unavailable in this batch.

### September 13: Fake Merchant combat and healing-relic stop

Unchanged release `593fed9a09e7a9ee69c73903dfbdc9dbdc1f28d55f8bb12b3556c4e3563851d2`,
installation `552aec7850a9b1eb6afa5b6ba3750627bbe3cbebcf779d4df428eec6e58eab79`.
User manually launched Profile3. A fresh standard Ironclad/no-ascension disposable
run chose Fishing Rod through native Neow UI and entered the first connected
monster room (enemyHP27/26). Native console removed the starter deck, added four
unupgraded Bludgeons and one Foul Potion, and created Fake Merchant. Deck view,
HP80/80, gold99, slot0 Foul Potion/other slots empty and Burning Blood/Fishing Rod
were verified. The console was closed; merchant inventory was never opened and
no purchase preceded the fight.

The maintained events client dispatched FAKE_MERCHANT.FOUL_POTION.0 once and resolved
combat_handoff, parent1/1/1,59 reads,4.676 seconds. Native combat was independently
visible with enemy165/165HP and consumed potion. The maintained combat client then
resolved victory:17 attempted/11 accepted/11 reconciled, six known no-mutation
stale rejections,152 reads,19.633 seconds. Native loot appeared at HP33/80, gold99,
empty belt. No force kill or combat guard changes were used.

Native scrolling inspected all nine reward entries before any core reward read:
300 gold, The Merchant's Rug???, Venerable Tea Set???, Blood Vial???, Strike Dummy???,
Happy Flower???, Anchor???, Lee's Waffle??? and a card reward. Explicit setup
assistance collected300gold. Opening the card chooser and Skip returned to the
retained offer; reopening and collecting Sword Boomerang removed it. Body Slam
and Colossus were the other card choices. Seven untouched relic offers remained,
HP33/80, gold399, deck5, empty belt. This does not test automatic handling of the
original nine-entry screen, which exceeds the core reader's eight-entry bound.

The first core reward session failed with unsupported_reward after7 attempted/
7 accepted/6 reconciled,8 reads,0.990 seconds. Successfully reconciled items were
FAKE_MERCHANTS_RUG, FAKE_VENERABLE_TEA_SET, FAKE_BLOOD_VIAL, FAKE_STRIKE_DUMMY,
FAKE_HAPPY_FLOWER and FAKE_ANCHOR in that order. The seventh accepted pickup was
Lee's Waffle???. Independent UI showed all seven relic icons, HP41/80, gold399,
deck5, empty belt and native Proceed with the loot screen closed. The host's
reported after_player remained HP33 because the final effect was not reconciled.
No retry, Proceed, map read, next-room entry or Architect setup/action followed.

Narrow source inspection found ReconcileItem and ReconcileNestedClosed require
SamePlayer, including unchanged HP, for CollectItem. The observed33→41 heal is
incompatible with those requirements. This is an independently sufficient source
incompatibility, not a claim that the generic response identified the exact failing
predicate. Further correction must verify the exact native healing effect and
preserve unrelated-state/ownership checks; this session changed no runtime source.

| Stage | Result | Seconds | Result SHA256 |
| --- | --- | --- | --- |
| merchant_foul_entry | resolved combat_handoff,1/1/1 | 4.676 | `803186ff708fef626a11665d922aeeb734627611fb818e54552c9899c2980d42` |
| merchant_combat | victory,17/11/11 | 19.633 | `f5acffe2224eba313b61d17660fd2fdde2d614ba787ed07ff55a170e1c3daae7` |
| merchant_seven_relics | unsupported_reward,7/7/6 | 0.990 | `24c52199724bd65bf4e4ac978a2fbe7c0e2bfa884cd1040850d59b752f60a828` |

All three diagnostic streams were empty. Total25 attempted/19 accepted/18 reconciled,
including six known stale rejections; policy execution25.299 seconds. Setup, user
wait and cleanup were not separately timed. Queue, exact commands and actual setup:
`/private/tmp/sts-merchant-architect-live-20260913.json`. Static prerequisite inspection
`/private/tmp/sts-merchant-ending-il.json` SHA256
`5fedd17900b33574d3cee0821de1a331562e24b563058f2ac900b270244f8052`
remains static IL evidence, not Architect live evidence.

Native Save and Quit/Main Menu Quit/Yes completed shutdown. Fresh require-stopped
passed with three process/two port samples. Exact owned quarantine
`32c2ebace162c35e87fbefbfce911d4a6f809905aa8d452aa5bc46302a5424b9`
and purge passed, removing four generated files and leaving phase absent. No
rebuild or profile/save/history/Cloud filesystem content access occurred.

### September 13: healing pickup correction and fresh retest preparation

The correction recognizes exact native FakeLeesWaffle/FAKE_LEES_WAFFLE with
Heal.BaseValue10. Static pinned IL confirms floor(maxHP/10) healing capped at maxHP,
with no maxHP gain. Terminal reward collection still requires the exact original
parent overlay, selected reward, claimed model and surviving deck/potion/relic
identities; only the exact healing delta is permitted in public player values.
Ready schema6 publishes heal_amount after potion_capacity_gain, binds it into
reward_v6 identity, and retains that schema through later parent/card-child reads.
The maintained Python codec/controller validate its exact declared and observed
effect while preserving the earlier ready schemas and schema1 receipts/completion.

Static native screen inspection clarified the prior screenshot: the loot *panel*
was hidden; terminal NRewardsScreen remains in the overlay stack. The native last
pickup removes and frees its button. Completed item reconciliation now uses the
retained reward/effect data without reading that freed control. An uncompleted
reward still needs its original live button, and the terminal parent guard was
not relaxed. No terminal auto-close exception or retry path was added.

Independent semantic review passed. New native fixtures cover HP33/max80→41,
max85 rounding, capped/full-health and zero-integer-gain cases; final button removal;
delayed selection completion; missing/extra heal, maxHP/gold/deck/potion/relic changes,
wrong claimed/reward model/key/Heal value, foreign overlay, early free and replay.
Client cases cover malformed declarations, exact effect, schema loss and lost
receipts. Producer-to-client socket cases exercise both card policies after healing.
Initial socket validation caught canonical field ordering and was corrected.
The first native-only run compiled but was not accepted because source inputs
changed during it; its new fixture was subsequently wired into the actual entrypoint.
The accepted stable focused run passed eight groups in192.284 seconds, including
11,432 native checks, all client/codec checks and shared socket integration:
`/private/tmp/sts-bridge-4vlya_h1/result.json`.

An initial release attempt found missing FakeLeesWaffle/BaseValue stubs in the
separate direct-input fixture; no release was accepted. That fixture was updated,
and its focused39 checks passed in3.061 seconds (`/private/tmp/sts-bridge-i10_a29y`).
The final combined release passed all71 groups in262.450 seconds, including the
full event matrix, native tests, reproducible production binary, package mutations
and owned installation/cleanup fixtures (`/private/tmp/sts-bridge-rxl2j59z/result.json`).
Accepted manifest:
`cb2d91104d8cab404a0000f004e0d0dcef9b5850cff2e8273425e27c043a20b0`.
It binds359 inputs/46 projects from the uncommitted checkout based on7334873.
Production DLL:1224192bytes,
SHA256`f3a9b522b2af36c91451b6befc5436fc4be08d60eb171012a4293671b26d30a0`.

The prior accepted manifest and evidence remain at
`/private/tmp/sts-healing-previous-release-593fed9a`; its verified package was moved
to `/private/tmp/sts-unified-bridge-release-retained-593fed9a`. Original failed live
results retain their prior identity. The new package was published with the maintained
tool, a fresh stopped-process/closed-port check passed (three/two samples), and
installation passed with state
`beb1095b7bda6dd5a6731993282d95d2064315f7b02479956fa43fcd9b0c96d1`.
The maintained client's installed-package/owned-metadata preflight also passed,
without connecting to the game or sending gameplay input.

Fresh queue: `/private/tmp/sts-merchant-healing-live-20260913.json`, awaiting manual
Profile3 launch at the main menu. The failed disposable run must not be resumed
for the reward retry. Native UI will prepare a fresh run, Merchant entry/combat,
ordinary-reward assistance before the first core reward read, seven-relic collection
and map, then Architect win last. Native stock may omit Waffle; that defers healing
acceptance rather than proving it. Static console inspection found no chosen-reward
command; direct relic grant bypasses reward selection and is not substitute evidence.
Original nine-entry screen support, broader pickup effects and Architect live win
remain open. No corrected-release live claim is made. Implementation/review/release
preparation/user wait were not separately timed; no profile/save/history/Cloud
filesystem content was accessed.

### September 13: corrected Merchant healing retest passed; Architect setup deferred

The fresh Profile3 process used accepted release `cb2d9110` (full identity above).
The failed disposable run was abandoned through the native menu. A fresh standard
Ironclad run selected Neow’s Talisman. In the first connected monster room, native
console setup replaced the starter deck with four unupgraded Bludgeons, granted
Foul Potion and entered FAKE_MERCHANT. HP80/80, gold99, belt slot0 Foul Potion,
Burning Blood/Neow’s Talisman and untouched closed Merchant inventory were checked.
No shopping occurred before entry.

| Stage | Result | Attempted / accepted / reconciled | Policy seconds |
| --- | --- | --- | --- |
| Foul Potion entry | Exact option resolved combat_handoff; enemy165/165HP, empty belt | 1 / 1 / 1 | 4.618 |
| Combat | Victory; six known no-mutation stale rejections | 17 / 11 / 11 | 21.258 |
| Seven relics + Proceed | All seven exact pickups and terminal Proceed reconciled | 8 / 8 / 8 | 1.125 |
| Map read | Ready/actionable, two legal candidates | No mutation | 0.104 |
| Architect | Native setup rejection before bridge read/input | 0 / 0 / 0 | Not run |

The original native loot list contained **ten entries**:300gold, Energy Potion,
seven relics and an ordinary card offer. Before any core reward read, native UI
collected gold, Energy Potion into slot0 and Pillage from Pillage/True Grit/Setup
Strike. All seven relics remained untouched. This assistance left HP33/80, gold399,
deck5 and one Energy Potion for the first core reward session. It is not automatic
handling of the original ten-entry screen and did not exercise card-reward Skip.

The bridge collected, in order:FAKE_MERCHANTS_RUG, FAKE_VENERABLE_TEA_SET,
FAKE_ORICHALCUM, FAKE_HAPPY_FLOWER, FAKE_ANCHOR, FAKE_LEES_WAFFLE and
FAKE_STRIKE_DUMMY. Public before/after values and native UI verified HP33→41,
maxHP80/gold399/deck5 unchanged, Energy Potion retained and all seven new relic icons.
Waffle was sixth, not last; final-button completion was exercised by Strike Dummy.
Native Proceed exposed an actionable map. Native UI then entered its connected
column1/row2 monster room, which settled at enemy42/42HP and player41/80HP. No further
combat input was sent. Total26 attempted/20 accepted/20 reconciled,27.105 seconds
including map read. All four diagnostic streams were empty.

Architect setup then sent native `event THE_ARCHITECT` once and received
`Event 'THE_ARCHITECT' not found`. No event bridge read/action or alternate console
mutation followed. Narrow static inspection established that EventConsoleCmd
searches only ModelDb.AllEvents plus AllAncients, excluding Architect. RunManager’s
EnterNextAct creates its EventRoom at final-act completion; CreateRoom has no direct
victory-room branch. Earlier preparation’s inference from EventRoom construction
was insufficient. Final-act setup remains to be exercised; no native win is claimed.
Additional static IL: `/private/tmp/sts-architect-route-il.json`, recorded SHA in
the queue, pinned game SHA`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.

Result SHA256 values (entry, combat, relics, map respectively):

- `e2fa4b59466cafa6165e5267bad906df9259573734f95e1e4929acf9a82c0d94`
- `f0e142da8abdd33107e6cb9a12130cf33f4016c8986decdf521f17b23e6afd4c`
- `ec29d19d708dd6c47cb4f85c9e7492a328679aaacfc04e6e6edb9b34a28281ab`
- `9d776057bd41e9f193d273d6f071d90b2cbb9927816fd9273f50b7955f49b2eb`

Completed queue: `/private/tmp/sts-merchant-healing-live-20260913.json`, SHA256
`b471e5e55ce5527cbc3d254be35f7f17c86402680249b19eb85f8610feeb5433`.
Native Save and Quit/Main Menu Quit/Yes shut down normally. Fresh require-stopped
passed with three process/two port samples. Exact owned quarantine state
`f0ec0a1343aa54d2472c0845775afb8296b85cb41591f1d371322fc983d94373`
and purge passed; four generated files removed and installation absent. Setup,
user wait, investigation and cleanup were not separately timed. No bridge source
change/rebuild or profile/save/history/Cloud filesystem content access occurred.


### September 13: next Dummy upgrade/Architect batch prepared

Accepted release `cb2d9110` sources still match. Fresh stopped-runtime preflight
passed (three process/two port samples). Owned installation passed with state
`77392cb81223c6d662936d8cadedad02d0b67eb702e5470a744c010cb9ab3db0`;
installed-package/metadata preflight passed without credential read or gameplay
connection. No rebuild or new gameplay claim was made.

Queue `/private/tmp/sts-dummy-upgrade-architect-live-20260913.json` binds three
maintained-client stages: Dummy `event-combat-map`, independent map observation,
and Architect terminal `events`. Dummy’s resume nonce stays within the combined
controller. Native setup targets four unupgraded Bludgeons plus Sozu, Philosopher’s
Stone and Velvet Choker: six energy, two attacks per turn against150HP. Static
native timer inspection confirms three player turns before escape. Setting2
victory randomly upgrades two eligible cards; native before/after deck inspection
is planned, without claiming a selector or bridge-certified automatic effect.

Architect setup is revised to native final-act progression. The console’s integer
`act 3` enters that act; native debug travel reaches the visible actual boss node,
then debug travel is disabled. Bounded native `win` may complete the boss combat
as recorded setup assistance only: its inspected implementation kills combat
enemies/checks combat victory, without calling terminal WinRun. Native boss rewards
Proceed uses act-change readiness. Final-act EnterNextAct creates Architect;
its own final Proceed remains untouched for the bridge check. Actual route/UI
settlement still needs live verification. No private run flags or direct WinRun
calls are permitted. The known-invalid `event THE_ARCHITECT` command is excluded.

Static inputs `/private/tmp/sts-next-batch-il.json` and
`/private/tmp/sts-dummy-timer-il.json` retain hashes in the queue, with pinned game
SHA`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Profile3 launch is manual; the game remains stopped awaiting the user. No
profile/save/history/Cloud filesystem content access occurred. Preparation/user
wait were not separately timed.

### September 13: Dummy victory/upgrades passed; Architect initial read rejected

Fresh manual Profile3 launch used the accepted release and installed state above.
The prior disposable run was abandoned through the native menu. A fresh standard
Ironclad/no-ascension run chose Precise Scissors and removed one Strike through its
native preview/Confirm. A connected left monster room settled at enemy37/37HP.
Native console setup removed the remaining four Strikes/four Defends/Bash, added
four unupgraded Bludgeons, and granted Sozu/Philosopher’s Stone/Velvet Choker. All
commands acknowledged. Native `event BATTLEWORN_DUMMY` exposed untouched choices.
Deck UI confirmed four original32-damage Bludgeons, HP80/80, gold99, empty belt,
Burning Blood/Precise Scissors and the three granted relics. Console/deck were closed.

The maintained `event-combat-map` flow selected exact Setting2 and preserved its
resume nonce. Entry reconciled1/1/1 in45 reads; combat7/7/7,57 reads/57 resume reads,
34 choice probes and no stale rejection. Native UI showed “YOU PASS THE TRAINING!”
and upgrade effects. Resumed Proceed reconciled1/1/1 in35 reads; map passed in one
read with one candidate. Combined policy time14.576 seconds. Native deck inspection
then showed upgrade levels `[1,0,1,0]` in obtained order: two42-damage and two32-damage
Bludgeons. HP80/80/gold99 and inventory were unchanged. These automatic upgrades
were observed natively; bridge parent effects remain unverified, and no selector
was exercised. Independent map read passed in0.094 seconds. Native column0/row2
entry settled enemies25/25 and22/22, player80/80HP and six energy.

Revised Architect setup succeeded. Native `act 3` acknowledged the final act;
`travel` enabled debug map travel. The visible actual boss node was selected, and
its room settled with enemies199/199 and400/400. `travel` then acknowledged disabled.
One native `win` setup command reported killed TORCH_HEAD_AMALGAM/QUEEN. Native
Proceed entered Architect directly, without ordinary reward collection. This is
explicitly assisted boss setup, not bridge combat or terminal-win evidence.
Native Threaten advanced one dialogue line to “Enemy... Kill...” with sole Proceed.
Player remained80/80HP, gold99, same four Bludgeons/two upgrades and same inventory.

The exact-PROCEED bridge invocation failed its initial read after34 reads in2.242
seconds: `unsupported_state`, **0 attempted/0 accepted/0 reconciled**, effects
`none_attempted`. Native UI still showed untouched Proceed at80/80HP. No retry or
native final Proceed followed. The response did not retain the exact native
admission diagnostic. Source inspection found room/layout/embedded-combat,
map/travel, capstone, overlay and exact-option predicates, but does not prove which
failed at runtime. Additional pinned static inspection is retained at
`/private/tmp/sts-architect-admission-il.json`, with SHA in the queue. No guard was
relaxed and no terminal win is claimed. The setup route is now live-demonstrated;
the next correction should resolve this admission boundary.

Total9 attempted/accepted/reconciled, no stale rejections,16.912 seconds of policy
and read execution. Three diagnostic streams empty; zero core reward sessions used.
Result SHA256 values for Dummy, map and Architect respectively:

- `1bf4583eef81b96d0ffc0dcddf35ad2171fd19becf70b356790f12b712aa1ba5`
- `230433a4d4917fa2ffc921b7800421240e562f8573869bfd48581637da8e9c3d`
- `f90d12f4dfdaf7b40295ffbccc15c73b36672ee7ecac45b5f349f268fcea1579`

Completed queue `/private/tmp/sts-dummy-upgrade-architect-live-20260913.json`, SHA256
`12a4a70b86a576bab4cca70c34fbe6d034f38e0b9e468b0391b3d7e598547ea7`.
Native Save and Quit/Main Menu Quit/Yes completed shutdown. Fresh stopped-runtime
check passed three process/two port samples. Exact owned quarantine state
`d2657d223584d5151bd5f17d40a1b0d8f979182c6867663401a5a3694c8759db`
and purge passed; four generated files removed, installation absent. No bridge
source change/build or profile/save/history/Cloud filesystem content access
occurred. Setup, investigation, user wait and cleanup were not separately timed.
