# Milestone 7 campaign validation — 2026-09-24

Status: **Both controlled saved campaigns reached native victory. The latest
floor-33 continuation verified three Knowledge Demon choices, both remaining
bosses and the full ending: 481 actions accepted and reconciled, without manual
gameplay or new setup assistance.** Normal quit and owned cleanup passed with
429 unchanged base files and zero overlays. Earlier restarts mean no segment
certifies a fresh uninterrupted campaign. Original artifact identities and
results remain below.

The user chose a controlled run with extra HP to exercise all acts and the ending.
The first two attempts used `native_campaign_smoke_v1`, an integration policy
composed from existing native capability controllers. The explicit chest sequence
changes that policy to `native_campaign_smoke_v2` from the third candidate. It is separate from the headless
`full_run_v2` policy and fixed Gym encoding. It does not establish a normal-HP
win rate, arbitrary native content support, simulator equivalence or native reset.
The [bridge guide](../../bridge/Sts2AgentBridge/README.md#campaign-traversal) owns
its entry conditions, actions, counters, contracts and limits.

## First candidate and validation

- Working checkout base: `14182eb`; exact uncommitted inputs retained in the manifest.
- Manifest: `f7d487814eafd11bfcad5f2d7919b9e26cec2f8ee840264db58d68eb9bbb39c9`,
  binding 406 inputs across 50 projects.
- DLL: `2000cb0565fff763ac6c7f2481d86cc735ab3e8f2c5ce1ec7251a20e4ce9cba7`.
- Gate: `/private/tmp/sts-agent-m7-campaign-final`, **81 groups passed in 270.752 seconds**.
- Pinned target: v0.107.1 / Steam 23811903 / macOS arm64, SDK 9.0.303.
- Native fixture coverage includes delayed votes/tasks, exact MapRoom/Architect
  destinations, wrong-owner rejection, unresolved and failed cleanup remaining
  failures, revoked delayed votes, map identity across acts and closed-shop leave.
- Host regressions preserve known child and local counts across deadlines,
  reject stage-limit continuations before input, never retry lost receipts, and
  require all three witnessed boss victories plus `run_won` for campaign victory.
- Real TCP integration covers campaign navigation POSTs, exclusive ownership and
  reward-v2 act handoff. These are synthetic/inert fixtures, not game observations.
- The grouped event integration passed 490 checks, including 428 production-native
  fixture checks. The final release gate includes this evidence.

Independent read-only semantic review found no remaining blocker after corrections
to destination recognition, sticky cleanup, late-result counts, continuation
budgets and foreground ownership on closed-shop entry. The reviewer independently
ran three timeout/continuation regressions (0.04 seconds). Initial review ran
07:36:24–07:43:08 UTC; the correction/recheck window was 07:50:51–08:36:05 UTC,
including implementation interleaving and waits. It is not 45 minutes of continuous
review work. Implementation and review time were not otherwise isolated.

Earlier gate attempts exposed a missing rest-codec packaging dependency, a missing
Architect fixture type, and an obsolete expectation that reward revisions reset
between screens. These were corrected and covered by the final gate. An SDK analyzer
`MissingMethodException` occurred in an unchanged wire fixture; the isolated
fixture passed unchanged. A fresh SDK copy matched all 4,844 files in the previously
verified SDK. No analyzer, test or runtime safeguard was disabled. A focused gate
was invalidated by later host-test edits; its results were rerun in the final gate.

`compileall game tests` passed. The broad Python suite completed with 8,098 passed,
one sandbox failure and two Gym observation-space warnings in 1,871.75 seconds.
The sole failure was the local ephemeral-socket test being denied loopback bind;
that exact test passed separately with loopback permission (one test, 0.01 seconds).
The broad run started before the final host corrections; the final release gate
reran the affected bridge suites against the accepted inputs.

## Live preparation

The installer verified the pinned game and stopped process, then installed the
single owned bridge package/configuration. State SHA-256:
`badb1570cde3aa2f90982aea29e2558578b37e61cfb19f5dbca02a9c0c0dfe62`.
The user confirmed manual launch at the Profile 3 main menu; UI inspection verified
the profile and a health request verified the running bridge. The prior controlled
run was abandoned through the native menu, then a fresh standard Ironclad A0 run
was started. Before the first Neow choice, 64 native-console pairs of
`relic add LOOMING_FRUIT` / `relic remove LOOMING_FRUIT` raised HP from 80 to 2,064.
UI checks verified 111, 328, 1,072 and finally **2,064 / 2,064 HP**, with only the
original Burning Blood relic remaining, 99 gold and the ten-card starting deck.
The console was closed before the campaign controller started at **08:57:08 UTC**.
No strength, godmode, direct victory, room skip or combat skip was applied.
No profile/save/history/Cloud files or retained live observation corpus were read.

## First live attempt and correction

The first campaign stopped after 27.335 seconds with `reward_already_complete`:

| Stage | Observed result | Attempted / accepted / reconciled |
| --- | --- | --- |
| Neow | `map_handoff` | parent 2 / 2 / 2; children 3 / 3 / 3 |
| First map choice | Exact destination reconciled | 1 / 1 / 1 |
| First combat, floor 2 | `victory` | 23 / 23 / 23 |
| Combat rewards | `map` | 4 / 4 / 4 |
| Repeated reward routing | `reward_already_complete`, no input | 0 / 0 / 0 |

The host made 33 POST attempts and 374 reads. No mutation was retried. The UI
showed the actionable map; closing it revealed the retained reward screen.
Pinned `RunManager.ProceedFromTerminalRewardsScreen` opens the map without
removing that screen. The campaign router had prioritized the overlay over the
foreground map. The correction recognizes the open map above a sole reward
overlay, while retaining rejection of foreign/nested overlays, modals and capstones
and waiting during disabled travel or transitions. The fixture now models native
reward retention; eight routing cases cover the observed failure and exclusions.
The focused gate passed all 114 native checks in 4.23 seconds. Independent read-only
review of this correction found no blocker (09:01:38–09:02:05 UTC, 27 seconds).

The game exited through Save and Quit, then the main-menu Quit confirmation.
Fresh `require-stopped` checks passed with three stopped-process samples and two
closed-listener samples. A redundant `sample-base-port-closed` call returned
`game_not_running` because that mode is for an unmodded running game; it supplied
no additional cleanup evidence. Exact owned quarantine succeeded with state hash
`342cad8b876400a86af51b55e06e20c9ce9534f8d5aa511ab48965187a09e27b`;
purge reached `absent`, removing four generated files. The clean-install verifier
confirmed all 429 base files unchanged at SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`,
with zero overlay files. No additional unmodded launch was required.

## Corrected release and second attempt

The replacement release at `/private/tmp/sts-agent-m7-campaign-map-fix` passed
all 81 release groups in **270.534 seconds**. Its manifest is
`ebbd464ad85a4dfe41f1de86877ceea78fdbcad3ffc1f7dfaf5425b6bfc2e11a`,
binding 406 inputs and 50 projects; DLL SHA-256 is
`bc9a2fd7ef2b3e86318957adf3a412d674f5dd9bcabe58317e57ebb8f756714d`.
The first package and original operational record remain retained under
`/private/tmp/sts-agent-m7-first-install-input` and the first candidate's gate
directory. The first attempt is not repinned to this corrected release.

After fresh stopped-process/closed-listener checks, installation succeeded at
state `35eee751a227ea183c75b933aea821ccad7f0effef66796697aa6e16f394cd63`.
The overlay verifier matched both owned overlay files and the unchanged 429-file
base installation. Manual launch was requested at 09:07:42 UTC and confirmed by
the user. UI verified Profile 3; exact runtime and bridge-health checks passed.
The first test run was replaced through the native menu by a fresh standard
Ironclad A0 run. The same 64 Looming Fruit add/remove pairs yielded verified
2,064 / 2,064 HP, original Burning Blood only, 99 gold and ten starting cards
before any Neow choice. The console was closed and the controller started at
**09:11:21 UTC**. It stopped after **192.995 seconds**, at floor 10's unopened
chest, with `campaign_receipt`: one treasure POST attempted, zero accepted or
reconciled. The host made **196 POST attempts and 2,809 reads**. Earlier stages
reconciled 195 actions: Neow parent 2/children 4; nine map selections; six combat
victories (23, 17, 11, 29, 42 and 28 actions); six reward-to-map stages (four
actions each); floor 7 event parent 2/children 2; and rest Heal/Proceed (two).
Thus the reward-map correction was exercised through six consecutive fights.
Only act 0 was observed; no boss victory or ending was reached. No action was
retried and the failed host was not resumed.

The chest's Proceed control is hidden until the native chest is opened. Pinned
`NTreasureRoom.OpenChest` grants normal gold, opens the relic collection and
waits for relic picking or Skip; the task does not finish when Skip first appears.
A separate manual UI experiment on the stopped run confirmed that opening the
map before the chest did not permit travel. Native Open then delayed Skip raised
gold from 187 to 239, took no relic, and enabled map travel to the floor 11 shop.
The shop's native zero-purchase Proceed returned to the map. These manual actions
are separate behavior evidence, not autonomous campaign results.

Normal Save and Quit, main-menu Quit and fresh stopped-process/closed-listener
checks completed. Owned quarantine state was
`a853f8e6d13fccfc5f3613ccab43b353f69dbd1d11e7033a83864b6af06a5f2d`;
purge reached `absent` and removed four generated files. Verification confirmed
zero overlays and all 429 base files unchanged at the same base SHA-256 above.
The original operational result is retained in
`/private/tmp/sts-agent-m7-campaign-map-fix/operational-validation.json`.

The correction introduces explicit `open_chest` and `skip_relic` actions in
`campaign_v2`. The first native task remains exclusively owned across both
POSTs; reads never dispatch. Review caught two native details omitted by the
initial inert fixture: Skip queues `PickRelicAction(player, null)`, and the native
single-player branch leaves Open dormant on the relic collection's pending
picking task even after the map opens. The corrected adapter verifies exact Skip
action execution/completion, Proceed completion, completed delay/tutorial tasks,
the native skipped flag and the unchanged dormant Open/collection state before
cleanup. Queued action execution revalidates the full treasure owner before any
mutation, including after a synchronizer/collection change. It neither claims Open
completed nor changes native task completion. Unexpected extra
reward overlays or tutorials stop the controller; optional relic selection is
outside this integration policy.

The prior M3 manifest/package and operational record retain their original
identities; they were preserved before publishing this release. The
[M3 evidence](AGENT_BRIDGE_M3_2026_09_23.md) remains a separate acceptance result.


Focused chest validation passed **202 native checks in 3.969 seconds** and
**16 host tests in 0.05 seconds**. TCP integration exercised both campaign-v2
POSTs and exclusive ownership between them (combined client/socket gate,
69.413 seconds); the final release gate reran it against the final source.
The pinned production build passed after resolving a Godot/System namespace
collision. The correction/review window began with the 09:20:50 UTC context
check and includes the manual UI experiment, cleanup, implementation and waits;
those activities were not separately timed.

Independent read-only semantic review found no remaining blocker after the native
Skip queue, dormant-task and delayed-owner corrections. Review ran
**09:30:34–09:41:08 UTC (10m34s including correction waits)**. It did not execute
the live game. The second package is retained at
`/private/tmp/sts-agent-m7-map-fix-install-input`, with all three files verified
against its original manifest before relocation. The final chest-correction
release gate started at approximately **09:41:31 UTC**.


## Chest-correction release

The final gate at `/private/tmp/sts-agent-m7-campaign-chest-fix` passed **81 groups
in 270.676 seconds**, binding 407 inputs and 50 projects. Manifest SHA-256:
`edff11826d17052439f1bf711de944d464ab58a1d5aa6a0ecd10748e78ba0631`;
DLL SHA-256:
`3c760b8b10cd76337b4a71fecafc63fffe5a56ddeef37adce8d779a756f44b6d`.
The package was published only after the previous package was verified and retained.
Fresh stopped-process/closed-listener checks passed (three/two samples), and the
base verifier again matched all 429 files before installation.

Installation succeeded with state hash
`c4bc5c274c2931e0e9808af997d4c732d08edf79a7821e60410fdca42cbe0d62`.
The overlay verifier matched the two owned files and unchanged base installation.
Manual Profile 3 launch was requested near **09:46:50 UTC**. The user confirmed the game ready; UI verified Profile 3 at the main menu and
the exact installed bridge passed its health check. The prior test run was replaced
through the native menu by a fresh standard Ironclad A0 run. Before Neow, the
same 64 native Looming Fruit add/remove pairs raised HP to 2,064/2,064, verified
at 1,072 and 2,064, with Burning Blood only, 99 gold and ten starting cards.
The console was closed. The v2 controller started near **10:01:45 UTC** and
stopped after **528.933 seconds** at floor 19 in Act 2 with `combat_choice_failed`.
It made **491 POST attempts and 7,514 reads**, observing acts `[0, 1]` and the
Act 1 boss victory. The failed combat retained **21 attempted, 21 accepted and
20 reconciled** parent actions. No input was retried or failed host resumed.

Before the stop, the controller completed eight combats, including the Act 1
boss (93 actions); eight reward stages, including the native next-act transition;
18 map selections; five event stages; three Heal/Proceed visits; one zero-purchase
closed-shop leave; and the explicit chest Open then Skip, each separately accepted
and reconciled before subsequent map travel. The longest ordinary fight took
82 actions. The Act 2 ancient event completed two parent and 16 child actions.
This establishes representative autonomous chest/shop/Act 1-to-2 behavior, not
three-act victory or general event/card coverage.

UI inspection after the stop showed Séance's native "Choose a card to Transform"
draw-pile screen, with Bash and Soul as visible choices. The player had
2,052/2,064 HP, 340 gold and 26 deck cards after the earlier native event. The
existing combat selector explicitly excluded Draw. The campaign summary retained
the parent failure and counts but discarded the child summary; no more specific
native failure code was retained for this attempt.

Normal Save and Quit, main-menu Quit and fresh stopped-process/closed-listener
checks completed (three/two samples). Owned quarantine state was
`f4963567bf6dc031ca387f8336b809e0ca45264ebfcfa7ef261f0b64c5bceedb`;
purge reached `absent` and removed four generated files. Verification confirmed
zero overlays and all 429 base files unchanged at the same base SHA-256 above.
The original operational record is retained in
`/private/tmp/sts-agent-m7-campaign-chest-fix/operational-validation.json`.

## Draw-pile correction

`combat_card_choice_v2` adds the native public Draw grid to the same owned selector
service. The old v1 route retains discard/exhaust scope and its 32-episode process
cap; v2 permits 1,024 bounded episodes for campaigns. Both retain 64 candidates,
1–8 maximum selections, 32 inputs and exact native task-result reconciliation per
episode. Switching protocol during an active selector stops without input.
Native Draw selectors sort their grid by rarity/name. Slots bind only those
displayed holders, with exact model/owner/pile membership revalidation; hidden
draw order and undisplayed cards are not projected. The campaign uses v2 while
ordinary combat and shared `agent_v1` retain their prior coverage.

Campaign results now retain bounded child failure details and child action counts.
Review exposed lost acceptance on late POST receipts and lost reconciliation on
late GET completions. Both now retain proven counts before stopping at the
deadline, without reporting success or dispatching again. Native failures are
validated and preserved on both GET and POST; an episode-cap admission failure
does not import the previous child's counters.

Focused validation passed **1,389 native checks and five native-to-host scenarios
in 2.148 seconds**, and **33 combat/campaign host tests in 0.07 seconds** after the
timeout corrections. The pinned production build passed in 1.733 seconds.
The router's 1,371 checks and TCP scenarios passed, but that combined focused gate
was invalidated by the interleaved timeout correction. The final release gate
reruns them against stable inputs. An earlier router run was denied loopback bind
by the sandbox; the permission-enabled run exercised those checks.

Independent read-only semantic review found no remaining blocker and reran four
targeted corrections. Review ran **10:21:00–10:25:59 UTC (4m59s)**, including
correction interleaving; no live game was executed. The final release gate at
`/private/tmp/sts-agent-m7-campaign-draw-fix` started near **10:27:11 UTC**.

All **81 release groups passed in 269.810 seconds**, binding 407 inputs and
50 projects. Manifest SHA-256:
`63d4aaa3c267d6b29dda83c1547bea2d9923871619735bced632e641f4a3ca25`;
DLL SHA-256:
`71fc6e10f5b84c1b6ad377e3b0acb0d9374adcc0779edb72f11d4d9ba8cf5cd6`.
The preceding three-file package was verified against its original manifest and
retained at `/private/tmp/sts-agent-m7-chest-fix-install-input` before publishing
the replacement. Fresh three/two stopped-process/closed-listener checks passed.
Installation succeeded at state
`4d2f1dd63ac70782900789fe5fd73e9b2249fc71d5304c12751b778f18d130db`;
the verifier matched both owned overlays and the unchanged 429-file base.
Manual Profile 3 launch was requested near **10:33:09 UTC**. The bounded live
retest below verifies the corrected chooser; full-campaign victory remains open.

The user confirmed launch and requested continuing the saved run to verify Draw
immediately. Profile 3 was visually verified and the installed bridge passed
health. Native Continue restored floor 19 at turn 1, with 2,064/2,064 HP, 340 gold
and the same 26-card deck. No new HP setup or fresh campaign was applied.
Near **10:37:16 UTC**, the existing released `run_combat(..., campaign=True)` API
started one bounded fight with its v2 selector, after exact release/installation
preflight. This retests the restored checkpoint with a fresh native process; it
does not resume the failed host or attribute earlier campaign coverage to this
segment. It completed by **10:41:24 UTC** with victory: **217 attempted, accepted
and reconciled combat actions**, 1,700 reads, 1,482 choice probes and no stale
rejections. Two Draw episodes each verified one selected original with one
attempted/accepted/reconciled input and two reads. This is live evidence for the
representative Séance chooser, not every Draw selector or deck size.

The released reward controller then claimed 14 gold, skipped the potion and card,
and verified the actionable map: four attempted/accepted/reconciled inputs and
five reads. Native HP was 1,655/2,064; gold changed 340→354; deck size was 26.
The user explicitly approved adding damage cards and prioritizing Frantic Escape
because The Insatiable's Sandpit can kill regardless of HP. Four native console
`card BREAK Deck` and two `card FLASH_OF_STEEL Deck` commands were issued once.
The deck grid visibly showed all four Breaks and both Flash of Steels; the native
top-bar count remained stale. No duplicate commands were issued to correct that
counter. A single legal map POST selected the shop at column 2, row 2 and exact
completion was verified. Native UI showed floor 20. The existing run was saved
normally before quitting; no run was abandoned and no fresh campaign was started.

Fresh three-process/two-closed-listener checks passed. Owned quarantine state:
`09feb958b8df9a197ac8b919009ccfcba8feb290f3630317d4b49594dc836ee4`.
Purge removed four owned generated files; base verification matched all 429 files
and zero overlays by **10:56:24 UTC**. The original release and operational record
remain at `/private/tmp/sts-agent-m7-campaign-draw-fix`.

## Explicit resume and boss status priority

Client implementation began after cleanup near **10:56:24 UTC**. The default
fresh entry still requires the first-act event/map. Explicit `--campaign-entry
resume` starts a new coverage record at the loaded native checkpoint, preserves
run/act/floor continuity, and never infers earlier bosses. A verified native
ending reports `continued_victory` and `full_campaign_verified: false`; only a
fresh complete three-act run may report full victory.

The declared traversal policy advances to `native_campaign_smoke_v3`. Campaign
combat prioritizes an already advertised legal Frantic Escape action over the
ordinary heuristic. This uses only public hand identity and legality; it cannot
create an action for an unplayable card. Other combat ordering and standalone
combat behavior are unchanged. The six manually added cards remain explicit test
assistance. Focused host checks passed **42 tests in 0.08 seconds**. Independent
read-only semantic review found no blocker and checked the diff against the
accepted Draw candidate, **11:00:31–11:01:51 UTC (1m20s)**; it did not duplicate
the tests or perform live activity. The final release gate started near
**11:02:21 UTC** at `/private/tmp/sts-agent-m7-campaign-resume`.

All **81 release groups passed in 267.604 seconds**, binding 407 inputs and
50 projects. Manifest SHA-256:
`3886c245c591e468eebdee4ca827e69bd90b3950c1e6568752521c5c0a28835b`.
The native DLL and all three package files match the accepted Draw release
exactly; only the client source/test binding changes. The preceding exact package
was retained at `/private/tmp/sts-agent-m7-draw-fix-install-input` before publishing.
Fresh three/two stopped-process/listener checks passed. Installation state:
`e43ad87c454af31739804b2a7337b38db85a49a044b1b28ba592711ca7a38b7d`.
Both owned overlays and all 429 unchanged base files were verified. Manual
Profile 3 main-menu readiness was requested near **11:07:38 UTC** for native
Continue of the existing floor-20 shop checkpoint.

The user confirmed readiness. Fresh exact-process and installed-source/health
preflight passed. Native Continue restored the expected floor-20 shop at
1,655/2,064 HP, 354 gold and 32 cards, confirming the six added cards persisted.
The `--campaign-entry resume` controller started near **11:11:43 UTC**; its first
shop leave and map action each attempted, accepted and reconciled once. This
segment records its own coverage; prior Act 1 results are not inherited.

The segment was interrupted at the user's request after **302.131 seconds**,
with **270 POST attempts and 4,369 reads** across nine stages. Floors 21 and 22
ended in combat victory (46 and 20 fully reconciled combat actions), followed
by two four-action reward/map handoffs and subsequent map selections. Two Draw
children completed on floor 21 and another on floor 23, each with one selected
original and one attempted/accepted/reconciled action. No boss was observed.

On floor 23 the lowest-HP recommendation repeatedly targeted the reviving
21-HP minion. UI inspection showed the 123-HP enemy remained at 71 HP from
turn 12 through turn 35, while player HP fell to 600/2,064. The user paused
before defeat. One exact-controller SIGINT stopped execution; the final combat
retained **189 attempted, 189 accepted and 188 reconciled** parent actions.
The result is `interrupted`, with no outcome; it is not recorded as defeat,
success or a safely resumed pending action. No uncertain input was retried.

Native Save and Quit preserved the current run, then the game exited normally.
Fresh three-process/two-closed-listener checks passed. Quarantine state:
`c660578139215463e0cdb8a4410be159a2fc7b1af00b20404f2fa6416aea8ceb`.
Purge removed four generated files. At **11:18:50 UTC**, all 429 base files
matched and zero overlays remained. The original operational record is retained
at `/private/tmp/sts-agent-m7-campaign-resume/operational-validation.json`.
The saved floor-23 fight checkpoint has not yet been reloaded.

## Reviving-minion target correction

The pinned native source identifies the matching encounter: `TheObscura` has
123 HP at A0 and summons `Parafright`, with 21 HP and `IllusionPower`. The latter
applies `MinionPower` and revives after death. This identification is based on
the visible encounter and pinned source; no live enemy-ID response was retained.

Campaign policy v4 keeps legal Frantic Escape first, then redirects the same
recommended card from public `PARAFRIGHT` to a living `THE_OBSCURA` only when
that exact target action is advertised as legal. It uses the current decision's
enemy indexes, preserves the original legal fallback, and leaves ordinary combat,
self-targeted actions and untargeted actions unchanged. This is an explicit
encounter-specific strategy correction, not generic minion classification.
Focused host validation passed **46 tests in 0.10 seconds** at **11:25:32 UTC**,
including actual dispatch/receipt/reconciliation and both enemy slot orders.
Independent read-only review found no blocker and ran five focused policy tests,
**11:25:58–11:26:34 UTC (36 seconds)**. The final release gate started near
**11:27:06 UTC** at `/private/tmp/sts-agent-m7-campaign-target-fix`; gameplay
remains stopped.

All **81 release groups passed in 270.287 seconds**, binding 407 inputs and
50 projects. Manifest SHA-256:
`71f312dd93865c9703c2a1a6b2c2b280c125d2dcec3efbc5711a08a469bf3f88`.
The native DLL and all three package files match the preceding accepted release.
That release's exact package was verified and retained at
`/private/tmp/sts-agent-m7-resume-install-input` before publishing the correction.
Fresh three/two stopped-process/closed-listener checks passed. Installation state:
`bf95485d3c33d0f8068748a5d64822bd147a55304436800445fdfb0834f169d0`.
Both overlays and all 429 unchanged base files were verified. Manual Profile 3
readiness is pending for native Continue of the existing floor-23 fight.
No fresh campaign or new HP/deck setup has been applied, and the target correction
has not yet been demonstrated live.

The user confirmed manual launch. Fresh process and installed-release/health
checks passed, and the main menu visibly showed Profile 3. Native Continue
restored floor 23 at turn 1 with **1,598/2,064 HP, 391 gold and 32 cards**.
Policy v4 resumed near **11:49:45 UTC**. The restored Obscura combat ended in
victory with **22 attempted, accepted and reconciled combat actions**, plus one
successful one-action Draw selector. Four reward actions and the next map action
also reconciled. By **11:50:22 UTC**, native UI showed floor 24 at 1,597 HP and
404 gold. The controller cleared the encounter that previously looped; the live
record does not retain per-action target traces. Further traversal is running.

At the user's request to remove Eidolon, the exact controller received one
SIGINT. It stopped after **214.840 seconds**, **220 POST attempts and 3,090 reads**,
with 22 stage summaries and no observed boss. Completed combats were floors
23, 24, 28 and 30 (22, 47, 34 and 58 fully reconciled parent actions). Four
reward stages, three rest visits, chest Open/Skip and eight map actions completed.
Eight Draw selections reconciled across completed and interrupted fights.
The floor-31 combat retained **18 attempted, 18 accepted and 17 reconciled**
parent actions, with `interrupted` and no outcome. This interruption was for
the requested setup change, not defeat or another observed targeting loop.

The stopped native UI showed turn 4, 1,957/2,064 HP, 1,110 gold and 31 cards.
The alphabetically sorted permanent deck visibly contained Eidolon. One native
`remove_card EIDOLON Deck` command acknowledged removal and changed the deck
count to 30. No command was retried. Removal from the in-memory deck is verified;
persistence after a new checkpoint/reload is not yet verified. Pinned native
`NPauseMenu.CloseToMenu`/`NGame.ReturnToMainMenu` perform cleanup and menu return,
without creating a new run save themselves.

Manual card-selection attempts did not produce an observed combat effect; a
single core read reported ready, round 4, five hand cards and three energy.
Automatic approval review then rejected a manual enemy click as outside the
specific removal request. The unfinished selection was canceled and the game
left paused. Explicit approval to finish the fight, reach a checkpoint and
continue the test was requested. No failed controller was resumed; the prior
reconciliation count remains 17. Current installation cleanup is pending while
the unsaved deck change is preserved in the running game.

The user explicitly approved continuing the fight and run, then offered to finish
the current fight themselves. Manual target clicks had not produced an observed
card effect; the user is completing the fight and will leave rewards open for
the bridge continuation. The earlier blocked click is not a continuing permission
block. No further automated input is being sent during this handoff.

The user reported the fight complete at rewards and independently confirmed
Eidolon's removal. UI showed floor 31, **1,926/2,064 HP, 1,110 gold and 30 cards**.
A fresh validated native combat read returned terminal `victory`, allowing the
core module to clear its completed combat ownership. This is the user's manual
completion, not retrospective reconciliation of the interrupted controller.
The native process, accepted-decision history and process budgets were preserved.

A new `resume` segment started at rewards near **12:06:59 UTC**, using the same
accepted release and installation. Five reward actions completed, including
Potion Belt; UI subsequently showed five potion slots with both original potions
retained, up from three slots. The map/rest/next-map sequence completed with the
30-card deck. The Insatiable on floor 33 ended in victory after **61 attempted,
accepted and reconciled combat actions**, followed by four reward actions and
the native Act 3 transition. The UI showed **Game Saved** with 30 cards and
1,954/2,064 HP. Removal has now passed subsequent native checkpoints; this is
not an additional reload test. No per-action Frantic Escape trace was retained.
By **12:08:18 UTC**, the Act 3 ancient event and next map transition had also
completed. Continued campaign victory and final cleanup remain pending.

The segment subsequently won six Act 3 fights on floors 35, 37, 39, 40, 44 and
45 (40, 24, 47, 40, 44 and 59 reconciled combat actions). Shop leave, chest
Open/Skip, rest, three event flows and their map handoffs passed. The floor-43
event completed two parent and four child actions. Fourteen Draw selections
reconciled across completed and interrupted fights in this segment.

On floor 46 the user initially reported another minion-targeting stall, then
corrected that observation: the main enemy was taking damage. One exact-controller
SIGINT had already been sent. The segment ended with `interrupted` after
**472.336 seconds**, **525 POST attempts and 6,834 reads**, across 39 stages.
It observed acts 2 and 3 and the Act 2 boss. The final combat preserved
**129 attempted, 129 accepted and 128 reconciled** actions. The native UI showed
turn 19, **1,735/2,048 HP**, and the main enemy at **56/150 HP**. This does not
establish another targeting deadlock, and the policy was not changed.

A fresh validated combat read and campaign read both returned ready on floor 46;
the native module released its completed action reservation. No POST was issued
by this check, and the stopped controller's counts remain unchanged. The user
reported playing one card and explicitly requested continuation. A new resume
segment began near **12:16:38 UTC**, preserving the native process and counters.
The fight ended in victory after one further attempted/accepted/reconciled bridge
action; rewards, map, rest and entry to floor 48 followed. The manual card is
recorded as assistance, not controller output.

## Test Subject revive correction

The last continuation stopped after **39.551 seconds**, **40 POST attempts and
572 reads**, across six stages. It finished the assisted floor-46 fight, collected
rewards, selected the next map node, rested and entered the floor-48 boss. The boss
stage retained **31 attempted, 31 accepted and 30 reconciled** actions before
`invalid_response`. No mutation was retried and no victory was inferred.

The user identified Test Subject's revive mechanic. UI showed the downed first
form on turn 5, **1,952/2,048 HP**, 1,395 gold and 30 cards. One bounded diagnostic
read returned an actionable combat with zero living enemies, one hand card and
only legal End Turn. The existing validator rejected it with
`decision_enemies_mismatch`. Pinned `AdaptablePower` prevents combat ending and
removal after death; `TestSubject.RespawnMove` revives the creature on its enemy
move. The native reader already omits dead creatures and advertises End Turn;
the incompatible minimum was in the Python client.

Native Save and Quit preserved the existing run, then the game exited normally.
Fresh three-process/two-closed-listener checks passed. Quarantine state:
`2e3c3d493591a0088c7638f7faa69a8ea88495ae1cdca1240694a66871168832`.
Purge removed four generated files; at **12:20:55 UTC**, all 429 base files matched
and zero overlays remained. The accepted target-fix operational record is retained
at `/private/tmp/sts-agent-m7-campaign-target-fix/operational-validation.json`, and
all three package files were verified and retained at
`/private/tmp/sts-agent-m7-target-fix-install-input`.

The correction enables zero-to-six enemies only for campaign combat validation.
Standalone callers retain their earlier minimum of one. Exact ready envelopes,
legal-action validation, target indexes, receipt ownership, next-round checks and
explicit terminal results remain required. Focused combat/campaign checks passed
**49 tests in 0.09 seconds** at **12:23:18 UTC**, including two revive phases,
malformed/phantom targets, standalone rejection and uncertain-input accounting.
All **26 core probe fixtures** also passed. Implementation edits ran approximately
**12:22:11–12:23:18 UTC**; diagnosis, cleanup and documentation are separate from
that interval. Independent read-only review found no blocker and independently
passed the three focused revive regressions, **12:23:48–12:24:31 UTC (43 seconds)**.
The final release gate started near **12:24:56 UTC** at
`/private/tmp/sts-agent-m7-campaign-revive-fix`.

All **81 release groups passed in 270.263 seconds**, binding 407 inputs across
50 projects. Manifest SHA-256:
`68ca1b86cbf5be5f4b073fba2aec20555377c636b808640065868cfab124c709`.
The native DLL and all three package files match the preceding accepted release.
Fresh three-process/two-listener stopped checks passed; the verified package was
installed at state
`6502495dd8558654c36e1e22bcb4e79d64c3eb9909d4273e64e2608d0e9ccbac`.
Both overlays and all 429 unchanged base files were verified at **12:30:26 UTC**.
Manual Profile 3 readiness was requested near **12:30:35 UTC** for native Continue
of the existing boss checkpoint. No fresh campaign or new HP/deck setup is needed.

The user confirmed readiness near **12:32:49 UTC**. Fresh exact-process and
installed-source/health checks passed, and the native main menu showed Profile 3.
Continue restored floor 48, turn 1, Test Subject's first form at 100/100 HP,
with the player at **2,048/2,048 HP**, 1,395 gold and 30 cards. The resumed
campaign controller started near **12:33:59 UTC**. This checkpoint reload also
retained the post-Eidolon-removal deck count; no new setup commands were issued.

At **12:35:26 UTC**, the native UI showed Test Subject's three-headed final form
with 300 max HP and player HP **1,806/2,048**. Both revive phases had advanced
under the corrected controller, with no manual gameplay during this segment.
Boss victory and ending reconciliation were still pending at that observation.


## Empty final-boss reward correction

The revive-fix segment finished after **165.225 seconds**, **115 POST attempts and
2,424 reads**. Test Subject's combat stage resolved victory with **115 attempted,
115 accepted and 115 reconciled** actions, including both revive phases, with no
manual gameplay during this segment. The native post-boss UI showed
**1,662/2,048 HP**, 1,395 gold and 30 cards. The following reward stage stopped at
`reward_read_limit` with **zero attempted, accepted or reconciled actions**.
The controller did not infer a run victory.

Pinned `RewardsSet.WithRewardsFromRoom` deliberately supplies no entries after
the final act's boss. The native `NRewardsScreen` still owns that set and its
player, but the public reader learned its player from a visible entry or a prior
reward session. This fresh bridge process had neither. The screen was waiting
at Proceed; the map and boss-revive logic were not the failing boundary.

Native Save and Quit preserved the run, then the game exited normally. Three
stopped-process and two closed-listener checks passed. Quarantine state:
`7fea2926dc7646bd4f338f880d4f0b1da9d62db27b7e6d9762e83f620159e7c8`.
Purge removed four owned generated files. Cleanup was recorded at
**12:45:23 UTC**: all 429 base files matched and zero overlays remained.
The original operational record is retained at
`/private/tmp/sts-agent-m7-campaign-revive-fix/operational-validation.json`;
all three verified package files are retained at
`/private/tmp/sts-agent-m7-revive-fix-install-input`.

The correction binds an initially empty terminal screen to its exact native
reward set, player, run, room, run node, manager and Proceed button. A nonempty set
whose buttons have not appeared remains waiting. The native button must be
visible and enabled; identities are revalidated before input. Existing compaction
and native campaign transition ownership remain in place, and the standalone
completion contract still cannot report an act/ending transition.

Focused validation passed **46 empty-reward checks**, **940 combat-item checks**
and the production build in **12.506 seconds**. The unchanged real campaign
transition fixture separately passed **202 checks** during the initial focused
run. The Python campaign/reward consumers passed **45 tests in 0.11 seconds**,
including a fresh empty reward screen, two waiting reads, exactly one Proceed
and a reconciled `ending` destination. The initial button fixture accidentally
started disabled; its setup was corrected, and explicit disabled/loading cases
remain tested. These are inert/native and host fixtures, not a live ending pass.

Independent read-only semantic review completed at **12:50:40–12:55:26 UTC**
(**4 minutes 46 seconds**), covering owner identity, loading/readiness, revalidation
before dispatch, shared-reader/legacy compatibility and transition reconciliation.
No concrete blocker remained; reviewed test evidence was not rerun unnecessarily.
The final release gate began near **12:55:52 UTC** at
`/private/tmp/sts-agent-m7-campaign-empty-reward-fix`.

All **81 release groups passed in 261.163 seconds**, binding
407 source/test inputs. New manifest SHA-256:
`a3bc675cb3b15b3bcd01a99fd6885638e447e9d620204319baf67cda0f7d5eae`.
DLL SHA-256: `b98ef40adc268db2a9e4eeef015198222b9afb7070db28f82b77c104e28f57a4`.
Fresh three-process/two-closed-listener checks passed, then the exact package
was installed at state
`7b5d67bba2e4d2954b2655ff94a640ecc252a7ad1debe63bb81cc63c75eb280d`.
At **13:00:54 UTC**, both overlays matched and all 429 base files were unchanged.
Manual Profile 3 readiness was requested for native Continue of the existing run;
no fresh campaign or new setup commands are needed.

The user confirmed readiness near **13:04:46 UTC**. Fresh exact-process,
installed-source and authenticated health checks passed. Profile 3 was verified
visually. Native Continue restored the saved **empty final-boss reward screen**
on floor 48 at **1,662/2,048 HP**, 1,395 gold and 30 cards. The completed fight was
retained; no replay or setup commands were needed. The resumed controller started
near **13:06:14 UTC**, using the normal campaign/reward routes.

The saved-run retest **passed in 7.733 seconds**, with **3 POST attempts and
107 reads**. Empty terminal rewards sent one Proceed: **1 attempted, 1 accepted,
1 reconciled**, reaching `ending`. The Architect event completed **2 attempted,
2 accepted and 2 reconciled parent actions**, reaching `run_won`. There was no
manual gameplay during this segment. The controller reported
**`continued_victory`**, with **`full_campaign_verified: false`**, Act 3 observed
and no boss inferred from this reward-only entry.

At **13:06:46 UTC**, the native UI showed **Victory...?**. Its subsequent summary
showed **48 floors climbed and 3 bosses slain**. This establishes the controlled
resumed campaign's ending. Earlier manual fight assistance and HP/deck setup are
retained above; the result does not certify an uninterrupted autonomous campaign.

Normal victory-screen Continue and Main Menu completed, followed by normal Quit.
Fresh checks observed three stopped-process samples and two closed-listener
samples. The exact owned installation was quarantined at state
`6743773a391adf638dcdf386561bc92b7d3bfb0864725661d60d6c4ec6a98738`,
and purge removed four generated files. At **13:08:58 UTC**, all **429 base files
matched and zero overlays remained**. The accepted operational record is retained
at `/private/tmp/sts-agent-m7-campaign-empty-reward-fix/operational-validation.json`;
the current package remains at `/private/tmp/sts-unified-bridge-release`.
No profile/save/history/Cloud files or raw live corpus were accessed or retained.

Available final-correction timings: focused native/build validation **12.506 s**,
Python consumers **0.11 s**, independent review **286 s**, final release gate
**261.163 s**, user readiness approximately **232 s** from request to confirmed
running check, and final live segment **7.733 s**. Review overlapped implementation;
these intervals are not an additive measure of implementation time.

Milestone 7's controlled campaign/ending integration is demonstrated. The remaining
autonomous acceptance case is one uninterrupted run under a declared setup and
policy, with no manual gameplay or controller replacement. Native seeded reset,
normal-HP win rate and wider shared-agent projection remain separate scope.

## Uninterrupted campaign with declared upfront assistance

The user chose upfront HP and damage assistance, with no mid-run intervention.
The unchanged accepted package was reverified and installed at state
`65bff380583acf7a50fb5f10c3ce8c414278940865d57356b057014b41b4594b`.
Three stopped-process and two closed-listener samples preceded installation;
at **13:18:58 UTC**, all 429 base files matched and both overlays matched.
Manual Profile 3 readiness was confirmed near **13:19:48 UTC**; authenticated
health and exact running-process checks passed. No rebuild or repeated release
gate was needed for this unchanged artifact.

A fresh standard Ironclad A0 run began near **13:20:15 UTC**. Before the first
Neow choice, 64 native-console Looming Fruit add/remove pairs raised HP from
80 to **2,064/2,064**, retaining only Burning Blood. Four `card BREAK Deck`
commands and two `card FLASH_OF_STEEL Deck` commands succeeded. The native deck
view independently showed all six exact cards, in addition to the ten-card
starter deck. The top-bar deck counter was stale at 10; the opened deck view
showed the actual additions. Gold stayed 99 and all three potion slots were empty.
Console and deck panels were closed with the first Neow options untouched.

The declared controller remains `native_campaign_smoke_v4`, using fresh entry
and the existing campaign budgets. The acceptance case is one controller from
this entry through all three observed boss victories and native `run_won`, with
no manual gameplay, setup changes, save/reload or controller replacement after
its first action. Upfront assistance does not establish normal-HP policy strength.

The uninterrupted controller started near **13:30:01 UTC**.

The uninterrupted attempt stopped after **75.315 seconds**, **85 POST attempts
and 1,019 reads**, with `unsupported_reward`. Five fights resolved victory,
including the floor-8 elite. Its reward stage recorded **2 attempted, 2 accepted
and 1 reconciled** actions. Across all stages, including event parents, there
were **85 accepted and 84 reconciled** actions. The unreconciled pickup was not
retried. No manual gameplay or mid-run setup changes occurred.

Read-only native UI inspection showed Strawberry newly owned, **2,063/2,071 HP**,
340 gold and 17 cards. Potion/card rewards remained on the screen. Pinned
Strawberry grants seven max HP through `CreatureCmd.GainMaxHp`; the terminal item
reconciliation currently allows only unchanged max HP and the separately declared
Fake Lee's Waffle heal. This is a reward-effect compatibility failure, not a
combat loss or exhaustion of the upfront setup.

Normal Save and Quit preserved the checkpoint; normal game Quit followed. Three
stopped-process and two closed-listener samples passed. Quarantine state was
`0d2abb2a36b22f65ca4ebc8424afa96fe4e874bbc3590d4d0aad83030908e24f`;
purge removed four owned generated files. At **13:33:11 UTC**, all 429 base files
matched and zero overlays remained. This attempt's exact operational record is
`/private/tmp/sts-agent-m7-campaign-empty-reward-fix/uninterrupted-operational-validation.json`.
The previous resumed ending's operational record is unchanged.

## Strawberry terminal-pickup correction

The narrow correction recognizes the pinned Strawberry type/key/MaxHp variable,
permits exactly +7 max HP and +7 healing, and retains exact pickup ownership,
inventory/deck conservation, native completion and no-retry rules. Ready schema 7
adds `max_hp_gain` and keeps it through compaction and card children. The client
checks the same health effect, including mixed Waffle percentage healing.

Focused native/build validation passed **1,149 combat-item checks** and the
production/shared-wire builds in **15.745 seconds**. The campaign/reward host
suite passed **49 tests in 0.10 seconds**. Two real TCP producer/client cases
passed in **3.285 seconds**, covering Strawberry, card choose/Skip and map exit.
Independent read-only review ran **13:40:02–13:44:15 UTC (253 seconds)** and found
two boundary issues: the pinned native HP cap and the client's smaller public
integer limit. Both now reject before input and have explicit boundary regressions.
The reviewer independently ran four focused host tests; all passed. No remaining
semantic blocker was found. These are offline fixtures, not a live pickup pass.

The previous three package files were retained with their original hashes at
`/private/tmp/sts-agent-m7-empty-reward-fix-install-input`. The next final release
gate will bind the stable correction; the floor-8 run remains saved and the game
and installation remain absent until the new package is prepared.

The final Strawberry release gate passed **81 groups in 273.582 seconds**, binding
407 source/test inputs. Manifest SHA-256:
`4ca8b0bf9f9731b760c2bf4642fdccf4f83202fc3d19a2c6ddba1f355a36e7d9`.
DLL: **1,396,736 bytes**, SHA-256
`06b7aba972b295213ceff5b0e01d013b7357b7aba0089697966626046a33d2c2`.
Gate/package evidence is retained at `/private/tmp/sts-agent-m7-campaign-strawberry-fix`.
All three package files were verified and published to the existing operational
package location. Current source bindings match the manifest.

Fresh three-process/two-closed-listener checks passed, then the corrected bridge
was installed at state
`c9c09d21458735c8e43931b6b118dc234bcd4b2009af3fd4c8bb229617eb3765`.
At **13:51:48 UTC**, overlay verification confirmed both exact files and all 429
base files unchanged. The game has not been launched under this candidate.
The floor-8 checkpoint remains saved. Selecting continuation would provide a new
diagnostic segment; an uninterrupted acceptance attempt requires a fresh run.
No further HP/cards or manual gameplay are authorized during policy execution.

## Saved-run Strawberry pass and modified-gold correction

The user chose to continue the saved run. Fresh process, installed-source and
credential-bound health checks passed. At **13:58:31 UTC**, the already-open native
checkpoint was floor 8's original reward screen: **2,056/2,064 HP**, 297 gold,
17 cards, and Strawberry still offered. The controller entered with `resume` and
the unchanged `native_campaign_smoke_v4` policy; no new HP/cards or manual gameplay
were added. Profile 3 was also visible after native Save and Quit.

The floor-8 reward stage passed **5 attempted, 5 accepted and 5 reconciled** actions,
including Strawberry, card Skip and map return. Read-only UI inspection subsequently
showed Strawberry owned and max HP **2,071**. This establishes the narrow native
pickup correction. Rest, treasure Open/Skip, one event and three more fights
resolved before a separate floor-15 reward failure.

The resumed segment stopped with `unsupported_reward` after **53.378 seconds**,
**63 POST attempts and 680 reads**. Aggregate counts, including event parents,
were **63 accepted and 62 reconciled**. The final reward stage had **1 attempted,
1 accepted and 0 reconciled** actions. The native UI showed **2,066/2,071 HP**,
517 gold, 17 cards, Bowler Hat owned and only potion/card rewards remaining.
No uncertain action was retried; no further controller attached to that process.
The exact result is `/private/tmp/sts-agent-m7-live-strawberry-resume-result.json`.

Pinned `GoldReward.OnSelect` passes its printed amount to `PlayerCmd.GainGold`.
Bowler Hat's `GoldIncrease.BaseValue` is **1.25**, so the final gold gained differs
from the reward's printed amount. GainGold applies the modifier, awaits its
callback, truncates the final positive decimal to an integer, adds gold and awaits
AfterGoldGained before reward selection completes. The prior reconciliation used
the printed amount. The pinned Player.Gold setter has no separate gold cap.

Native Save and Quit preserved floor 15, followed by normal game Quit. Three
stopped-process and two closed-listener samples passed. Quarantine state was
`0b791686506398df0abb2a3d35444d380ee4a6326253f244f00765729e948872`;
purge removed four generated files. At **14:02:19 UTC**, all 429 base files matched
and zero overlays remained. Original operational evidence is retained at
`/private/tmp/sts-agent-m7-campaign-strawberry-fix/operational-validation.json` and
all three original package files at `/private/tmp/sts-agent-m7-strawberry-fix-install-input`.
No profile/save/history/Cloud filesystem access or raw live corpus was used.

The correction adds schema 8's `gold_gain`, preserving `gold_amount` as the printed
value. It predicts only ordinary gold and the exact active Bowler Hat multiplier,
without invoking gameplay hooks or RNG. The native hook census includes inactive
relic filtering, run subscribers and both native before/after listener domains.
Unknown gold hooks stop before input. Exact runtime, reward, deck, inventory and
listener identities are bound and checked through native completion. The schema
stays present through compaction and card children; both clients check the actual
gain and reject schema loss. Integer overflow and the client's 1,000,000 public
bound reject before input. Other gold-triggered effects remain unsupported.

Focused validation passed **1,437 native combat-item checks**, the production and
wire-fixture builds, **53 reward/campaign host tests in 0.12 seconds**, and two
real TCP modified-gold/card choose-or-Skip/map cases in **2.505 seconds**. The first
socket invocation lacked loopback permission; the same built cases passed with
that permission. Native fixture corrections also covered potion owner setup and
new failures for pending runtime replacement and a late overflow before dispatch.
No safeguard or validation was disabled.

Independent semantic review ran **14:03:14–14:14:07 UTC (653 seconds)**, including
correction waits. Active hook membership, runtime ownership and standalone schema
retention findings were fixed; four independently run focused host checks passed,
and no concrete blocker remained. The final release gate began near **14:15:14 UTC**
at `/private/tmp/sts-agent-m7-campaign-bowler-fix`.

The final gold-correction gate passed **81 groups in 275.843 seconds**, binding
407 exact inputs across 50 projects. Manifest SHA-256:
`11704f4e1975172eba72f5c98971c013733245ff2b47eb55aa194bdcf69de30d`.
DLL: **1,404,416 bytes**, SHA-256
`23ef407b475bded244fd521b5345fe8f2f1c8e3f01d87c2519b3e4540207b353`.
All three package files were verified and published to the existing operational
package location. Current sources match this manifest. Fresh three-process and
two-closed-listener checks preceded installation at state
`5523f138c5ed8fa080e10ce91c0cf5759b495de2e5effc05638d537548473d96`.
At **14:21:06 UTC**, both overlays matched and all 429 base files were unchanged.
Manual reopening on Profile 3 was requested for native Continue of floor 15.
No new HP/cards or manual gameplay are planned during controller execution.

## Bowler Hat live pass and Knowledge Demon chooser

Under manifest `11704f4e1975172eba72f5c98971c013733245ff2b47eb55aa194bdcf69de30d`,
manual Profile 3 readiness and authenticated health were verified at
**14:39:05 UTC**. Native Continue restored floor 15 with 2,066/2,071 HP, 492 gold,
17 cards and Bowler Hat. The displayed 20-gold reward reconciled as **25 gold**:
492 → 517. All four reward-stage actions reconciled and reached the map.
This is the narrow native pass for the modified-gold correction.

The same controller defeated the Act 1 boss, crossed the native act transition,
and traversed Act 2 through floor 32 without manual gameplay or setup changes.
At floor 33, Knowledge Demon opened **Disintegration / Mind Rot** in
`NChooseACardSelectionScreen`. The existing pile adapter did not recognize this
screen. The controller was deliberately interrupted; no offer was selected.
The bounded result is `/private/tmp/sts-agent-m7-live-bowler-resume-result.json`:
**313 attempted, 313 accepted, 312 reconciled**, 6,497 reads, 47 stages and
**453.394 seconds**. The final combat had four accepted inputs and three
reconciled inputs; its pending end-turn is not credited or retried. The run
remains `full_campaign_verified: false`.

The paused UI showed 2,071/2,071 HP, 838 gold and 20 cards. Native Save and Quit
returned to the saved-run main menu; normal Quit followed. Three stopped-process
samples and two closed-listener samples passed. Exact owned quarantine state was
`575709f3c0993b3a8a5e269da46cd6d91249c94eb3b25b654066135fd762ed9a`;
purge removed four generated files. The base verification passed for 429 files,
SHA-256 `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`,
with zero overlays. Cleanup was recorded at **15:01:12 UTC**.
The original operational record remains at
`/private/tmp/sts-agent-m7-campaign-bowler-fix/operational-validation.json`;
its three hash-verified package files are retained at
`/private/tmp/sts-agent-m7-bowler-fix-install-input`.

Pinned native source shows `KnowledgeDemon.ChooseCurse` calling
`CardSelectCmd.FromChooseACardScreen` during the enemy turn. It creates offered
cards, awaits one exact returned model and then calls its `IChoosable.OnChosen`.
These cards are not combat-pile selections or deck-grant rewards. The correction
extends the existing combat choice service with v3 `pile: offer`, mandatory
one-of-one-to-three visible cards, no skip/confirm action, native opening-delay
checks and exact task-result/overlay-close reconciliation. It certifies selection;
the enclosing combat separately reconciles the enemy turn. No new mod, listener,
policy assistance or saved-data filesystem access is involved.

The independent semantic review found two pre-dispatch issues: the keyboard
helper's deferred `EmitPressed` could outlive a checked holder, and a native modal
or card preview could leave the underlying chooser visible. The correction now
uses the existing event-offer adapter's synchronous native `Pressed` signal and
requires `ActiveScreenContext.IsCurrent(screen)`. Added fixtures cover a changed
holder/disposal leaving no queued input, uncertain signal failure without retry,
and an intervening foreground blocker producing zero input. Final focused
native/host checks passed in **1.956 seconds**, and the pinned production build
passed in **1.785 seconds**. Earlier affected unified ownership/socket checks
passed in **77.000 seconds**; 27 combat-host and 26 campaign-host tests passed.

The review closed with no remaining blocker at **15:07:00 UTC** after
**8 minutes 4 seconds**, including correction/recheck. The reviewer independently
ran three new v3 Python cases (0.02 seconds) and inspected the passing native/build
artifacts. Final release validation began at **15:07:33 UTC** in
`/private/tmp/sts-agent-m7-campaign-offer-fix`. This release still requires the
real Knowledge Demon chooser retest; no native success is inferred from fixtures.

The final offer-correction gate passed **81 groups in 276.140 seconds**, binding
408 exact inputs across 50 projects. Manifest SHA-256:
`28d5c9fba0ba8fc8a07a75e50da2ded4f94d386569193fed64db2570c3cc1b6d`.
DLL: **1,410,048 bytes**, SHA-256
`afb8a310767ea7c49dbe20fe513fda8e41c7b7ab56ab7a88e34aa3dd804e68c8`.
The final native chooser suite contains **1,434 checks**, with seven native/host
scenarios. All three package files and current transitive sources were verified.
The original Bowler operational record SHA-256 is
`b33b337e3f0e7f3fbb216343457d2aca35e6a10d0b21897d096eb02d138b66f1`;
it remains bound to its original release in current `prior_evidence`.

Fresh stopped-game/closed-listener and clean-base checks passed before install.
Installation state:
`78c82a9e4fc7b1f5b166834bd6e94526a2d46008d4adb27255c09299d37af829`.
At **15:13:34 UTC**, both installed overlays matched and all 429 base files were
unchanged. Manual Profile 3 reopening is requested to Continue the same saved
floor-33 campaign. Native generated-offer completion remains unverified; the
interrupted parent action is not retried or credited. The setup remains the
original upfront HP/cards, with no new assistance.

## Knowledge Demon offer live pass and unclaimed read recovery

Under manifest `28d5c9fba0ba8fc8a07a75e50da2ded4f94d386569193fed64db2570c3cc1b6d`,
manual Profile 3 readiness and authenticated health passed at **15:17:11 UTC**.
Native Continue restored floor 33 with 2,071/2,071 HP, 838 gold and 20 cards;
Knowledge Demon restarted at 379/379 HP. The policy selected one offered card,
verified its exact completion and resumed combat. The first-slot Disintegration
power was visible afterward. This is a narrow native pass for the v3 offer
adapter, with **one attempted, accepted and reconciled child action**. No manual
gameplay or new setup assistance occurred.

The segment then stopped on `dispatch_timeout_before_claim`, with an active
`dispatch` stage at **501 ms**. The result at
`/private/tmp/sts-agent-m7-live-offer-resume-result.json` records **14 attempted,
14 accepted and 13 reconciled** aggregate actions, 144 reads and **10.390 seconds**.
Combat accounts for 13 accepted/12 reconciled actions, plus the completed child.
The last parent remains uncredited; neither a new client nor a mutation retry was
used. The stopped UI showed turn 3, 2,058/2,071 HP and boss HP 321/379. No boss
victory or full-campaign result is established.

Native Save and Quit preserved the checkpoint, followed by normal Quit. Three
stopped-process and two closed-listener samples passed. Exact quarantine state:
`c6c7b299cb4c4c396fd124e8584fe0c9007197a95f8c9a7c288f603886c2437d`.
Purge removed four generated files. At **15:22:51 UTC**, installation was absent,
zero overlays remained and all 429 base files matched SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
The original operational record is retained at
`/private/tmp/sts-agent-m7-campaign-offer-fix/operational-validation.json`, SHA-256
`61697f7d1a6ec18f4b815be8e28adce313b647d061f1371fa989068eff68f801`.
Its three exact package files remain at
`/private/tmp/sts-agent-m7-offer-fix-install-input`.

Source inspection establishes that `TimedOutBeforeClaim` atomically cancels the
queued item under the same lock as `TryClaim`; a later owner frame cannot execute
it. The correction permits one internal replacement submission for such a GET,
within the same authenticated exchange and without releasing any module or
pending parent. It charges another existing read reservation and at most eight
replacement reservations per process. Each submission retains the 500 ms result
wait, and the existing connection lifetime remains. POSTs, claimed callbacks,
faults, second failures, expired exchanges and exhausted budgets keep the original
terminal behavior. No client retry or wire-schema change is involved.

Independent read-only review found no concrete blocker in the cancellation,
exchange ownership, liveness or budget semantics. It ran **15:21:55–15:27:26 UTC
(331 seconds)**, with a fixture coverage addendum **15:30:28–15:31:07 UTC
(39 seconds)**. The reviewer ran no new tests. Author validation passed **1,464
unified checks**, including delayed frame dispatch, retained pending parent/child,
late cancelled work, eight-retry exhaustion, total read budget exhaustion, expired
connection, unchanged POST/after-claim failures and cleanup. The new real Python/
C# socket case passed in **0.761 seconds**, including later GET, POST and map
handoff. Early fixture compilation/wire-shape mistakes were corrected without
changing production behavior. The complete socket suite is included in the final
gate, started at **15:34:18 UTC** in
`/private/tmp/sts-agent-m7-campaign-read-recovery`.

The read-recovery release gate passed **81 groups in 290.567 seconds**, binding
408 exact inputs across 50 projects. The complete shared socket suite passed in
**73.028 seconds**. Manifest SHA-256:
`8c3060c7b07f7cd9f4bc5cd07063a1ba0e2619000151994504a041a579426f71`.
DLL: **1,410,048 bytes**, SHA-256
`f90be5684c9a344ca125657a9020f08be4311133366205a0927ea47818867f3e`.
All three package files and current sources were verified before publication to
the existing operational package location. The original chooser operational
record and package remain hash-verified under their original identity.

Fresh preinstall stopped-game/closed-listener and clean-base checks passed at
**15:38:27 UTC**. Installation state:
`738984a5975a98c4693e56ece1e3a4902a59bd69efe8c60b75572d315839b5f9`.
At **15:40:18 UTC**, both installed overlays matched and all 429 base files were
unchanged. Manual Profile 3 reopening is requested to Continue the same saved
floor-33 campaign. Read recovery remains unverified live; no new HP/cards or
manual gameplay assistance is planned. Earlier unreconciled actions are not
retried or credited by the resumed segment.

## Saved continuation completed under the read-recovery release

The user reopened Profile 3, visually verified at the saved-run main menu.
Current package/base checks and authenticated health passed at **16:00:03 UTC**
under manifest
`8c3060c7b07f7cd9f4bc5cd07063a1ba0e2619000151994504a041a579426f71`.
Native Continue restored the same floor-33 fight: 2,071/2,071 HP, 838 gold,
20 cards and Knowledge Demon at 379/379 HP. No new HP/cards were granted as setup,
and neither the user nor the operator played cards during this segment.

The single `native_campaign_smoke_v4` controller then completed the run:

- Knowledge Demon: **59 combat actions and three separate offered-card choices**,
  all accepted and reconciled, followed by victory and the Act 3 handoff.
- Act 3: ordinary fights, nested event choices, chest Open/Skip, rewards, map travel
  and rest stops completed. The floor-45 Fabricator fight reconciled 58 actions.
- Floor-48 boss: **74 combat actions**, all accepted/reconciled, ending in victory.
- Ending: one empty-reward Proceed reached `ending`; three Architect parent
  actions reconciled and returned `run_won`. Native **Victory...?** and the
  completed-run summary were visually confirmed.

Result: **`continued_victory`**, **481 attempted / 481 accepted / 481 reconciled**
actions, **44 stages**, **7,477 reads**, **507.729 seconds**. There was no failure,
manual gameplay, controller replacement or new setup assistance in this segment.
Act indices 1 and 2 and both corresponding boss victories were witnessed. Earlier
segments/restarts remain distinct, so **`full_campaign_verified: false`** is
correct and the uninterrupted full-run acceptance case remains open.
The bounded result is
`/private/tmp/sts-agent-m7-live-read-recovery-resume-result.json`.

This is live success using the accepted read-recovery package. There was no read
failure, but successful responses do not expose the number of internal retry
reservations. It therefore does not establish that a retry occurred or explain
all intermittent cold-start failures. Exact cancellation/retry boundaries retain
their focused native/socket fixture evidence.

After victory, native Continue/Main Menu and normal Quit completed. Three exact
stopped-process samples and two closed-listener samples passed. Owned quarantine
state was
`4fc739b19ca64937b7315bed1de3c2fc20202f6bbc5b76f4c569a1c578c96c39`;
purge removed four generated files. At **16:11:53 UTC**, installation was absent,
zero overlays remained and all **429 base files** matched SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
No profile, save, history or Cloud filesystem access was used.

The completed original operational record is retained at
`/private/tmp/sts-agent-m7-campaign-read-recovery/operational-validation.json`,
SHA-256 `ebad12251c0796d015d617053fd65faec2c9eda109f2939410664cfc66d474c2`.
All three original package files are hash-verified and retained at
`/private/tmp/sts-agent-m7-read-recovery-install-input`. Documentation and evidence
updates follow the existing accepted release; no production changes or new gate
were needed after this live pass.


## Fresh campaign preparation with ordinary potions, 2026-09-24

The user requested another campaign attempt including potion usage. Campaign
policy `native_campaign_smoke_v5` now collects potion rewards when capacity is
available and uses 15 ordinary potion types. `combat_potions_v1` has separate core
routes; exact native inventory/target/run/foreground binding, raw effect and
execution/completion tasks, consumption and cleanup precede reconciliation.
Queued or failed potion ownership fences cards, choosers, rewards and the outer
event continuation. Unresolved disposal retains its execution revocation guard.
Choice/autoplay potions remain unadvertised. Shared `agent_v1` coverage is unchanged.
The [usage contract](../../bridge/Sts2AgentBridge/README.md#campaign-traversal)
contains the exact type list, policy and bounds.

Inspection, implementation and focused verification began at **16:45:06 UTC**;
the first release build began at **17:07:15 UTC**. This 22m09s window includes
review and correction waits, not isolated coding time. Independent review ran
**16:51:59–17:05:21 UTC** (802 seconds) and found no remaining blockers after
corrections for queued-action revocation, foreground binding, late completion
accounting and changed-combat target refresh. The reviewer ran five focused
Python tests; author-run client regression passed 142 tests in 0.456 seconds.
Native potion fixtures passed 120 checks; the focused shared core/socket gate
passed in 87.558 seconds. These are inert/native-shaped and transport evidence,
not game execution.

Release preparation caught a production `Environment` naming ambiguity after
adding the foreground guard, then an unwanted regular-expression assembly
reference. Both were removed without weakening the verifier. The accepted final
gate `/private/tmp/sts-agent-m7-campaign-potions-final` passed **83 groups in
291.491 seconds**, including a reproducible build, package and disposable
installation/cleanup. Its manifest SHA-256 is
`0aee0eb56eb48e7bd2cdeecb209f91b76df3dfafc7e82b6a4e464a1400b54c71`, binding
415 inputs and 51 projects from the working checkout based on `14182eb`.
DLL: 1,436,160 bytes, SHA-256
`b3b19b3769ba12c8fc562a6fc16861bd269274c6ef3e1c1488c677871a173eec`.
ZIP: 1,436,854 bytes, SHA-256
`bbd1625ca78132da711f331ac80b8acb2b97ecae46314273128bcfbdd2c32612`.
Exact package files are retained at `/private/tmp/sts-agent-m7-potions-install-input`.
The previous completed operational record remains unchanged at its original
`ebad1225…` hash and is linked in `prior_evidence.milestone_7_read_recovery_victory`.

Stopped-process/closed-listener preflight passed. Installation and overlay checks
completed at **17:19:22 UTC**, state hash
`3ce8602a3021849e28c046bdc055271cdf365851d97ab0909f82b45522c36c71`:
two exact overlays, 429 unchanged base files. Manual Profile 3 launch was requested
at that time and confirmed by the user. Running-process checks passed at
**17:21:05 UTC** and authenticated health passed with correlation
`c09afae8c03af7278e22d41777aa7ce6`. The native UI confirmed Profile 3 before starting
standard Ironclad A0. Before **17:27:15 UTC**, 64 native Looming Fruit add/remove
pairs established **2,064/2,064 HP**; the console added four Breaks, two Flash of
Steels, one Fire Potion and one Strength Potion. Console receipts and the visible
deck/potions/HP confirmed setup. The console and deck were closed at the untouched
Neow choices before the first policy action. No profile/save/history/Cloud content
was accessed.

### Potion demonstration and Waterfall Giant stop

One fresh `native_campaign_smoke_v5` controller started near **17:27:15 UTC**.
It reconciled these potion uses through the native effect and inventory checks:

| Floor | Potion | Native action | Attempted / accepted / reconciled |
| --- | --- | --- | --- |
| 2 | Fire Potion (setup) | `use:0:0` | 1 / 1 / 1 |
| 2 | Strength Potion (setup) | `use:1` | 1 / 1 / 1 |
| 4 | Fire Potion (collected reward) | `use:0:1` | 1 / 1 / 1 |
| 8 | Vulnerable Potion (collected reward) | `use:0:0` | 1 / 1 / 1 |

The controller completed eight fights, reward collection, events with selectors,
chest Open/Skip, rest and map travel without manual gameplay or added assistance.
It stopped during the floor-17 Waterfall Giant fight with `invalid_response`:
**23 combat actions attempted/accepted, 22 reconciled**. Overall: **200 attempted /
200 accepted / 199 reconciled**, **42 stages**, **2,347 reads**, **168.564 seconds**.
No boss victory was recorded and `full_campaign_verified` remains false.
The immutable result is `/private/tmp/sts-agent-m7-live-potions-fresh-result.json`,
SHA-256 `30e43d5f79b5c720d158897c5fbbbce20ba128492ce4f02fbb9fbf2d68f9618f`.

The user identified Waterfall Giant as the likely cause. The UI showed its
infinity health bar and End Turn 5, with 2,059/2,064 HP, 317 gold and 17 deck cards.
One diagnostic-only GET confirmed a ready round-5 Waterfall Giant decision and
the old validator's `decision_enemies_mismatch`. Only bounded labels/booleans
were retained; no raw response corpus was stored. This read did not replay an
action, restart a controller or grant reconciliation credit to the failed run.
Pinned native source sets a large internal health sentinel and
`HpDisplay.InfiniteWithoutNumbers` in `TriggerAboutToBlowState`; the old client
rejected that number at its ordinary integer bound. The native UI hides it.

Native Save and Quit retained the campaign and showed Continue on Profile 3.
Normal Quit, three stopped-process samples, two closed-listener samples and owned
quarantine/purge passed. Quarantine state:
`1af6de2539aab344ea36aece3a2f187cf420089560c08e4823bb7cbbbb84887c`.
At **17:34:13 UTC**, all four generated files were removed, zero overlays remained
and all **429 base files** matched the unchanged `d111d988…` base hash. The completed
operational record remains at
`/private/tmp/sts-agent-m7-campaign-potions-final/operational-validation.json`,
SHA-256 `b53acfc834d017d4cfabe1dc281f3972a4929d40f7ea7375ea0715b1d71ee11b`.
Its accepted package remains retained under the original `0aee0e…` manifest.

### Visible-infinity correction

The public combat reader now maps native `InfiniteWithoutNumbers` to an explicit
infinite display with no numeric HP. Schema 2 adds `hp_display` to every enemy
when at least one enemy is infinite and emits null HP/max HP for that enemy.
Hidden native HP changes affect neither public bytes nor identity. All-numeric
decisions retain schema 1, including `InfiniteWithNumbers` because the native UI
still displays its numbers. Unknown modes stop projection. Terminal defeat can
also use schema 2; native victory remains authoritative.

Campaign `native_campaign_smoke_v6` accepts the extension, ends turns when all
remaining enemies display infinity and conserves potions in that phase. Mixed
encounters retain finite targets. The numeric-only standalone and `agent_v1`
profiles reject hidden health; the shared agent rejects schema 2 before crediting
a pending action. No native legality, ownership, task, cleanup or retry guard was
relaxed. Bounded validator labels now accompany the existing `invalid_response`
code without retaining response data.

Independent source review ran **17:32:18–17:44:21 UTC** (723 seconds), with no
remaining blockers and no reviewer test reruns. Client regression passed **146
tests in 0.429 seconds** and the existing probe suite passed **26 cases**. Focused
native/core validation passed in **15.821 seconds**: 1,439 combat-choice/native
checks, 32 agent-native checks and 1,505 unified checks. A fixture-only missing
encoder dependency was corrected by keeping codec tests in the existing unified
project. The numeric → infinity → next-turn infinity → victory path passed over
the actual Python/C# test socket in **0.463 seconds**. Production build passed in
**1.687 seconds**. These remain offline evidence. The final release gate began at
**17:44:58 UTC** in `/private/tmp/sts-agent-m7-campaign-waterfall-final`; a saved-run
live retest is pending. This first gate stopped at an SDK `MissingMethodException`
in the unchanged item transport build, after 54 check groups. That component
passed unchanged in a fresh disposable focused build in **9.926 seconds**.
The release rerun at `/private/tmp/sts-agent-m7-campaign-waterfall-release` retains
all analyzers, tests and original compiler settings; no code was changed for the
compiler failure.

The unchanged rerun passed **83 check groups in 290.147 seconds**, binding
**416 inputs and 51 projects**. Accepted manifest SHA-256:
`96f48a88aed4dca0da4dcaf6a3530f565b6954f890219438a0cac5db38bcfe8f`.
DLL: **1,438,208 bytes**, SHA-256
`b454891e14951cf5870a80affec683931b572d09eebdfb12e98db89d5e35c8a9`.
ZIP: **1,438,902 bytes**, SHA-256
`fb36c91f77352f0f39fc5d4f8747c3f6fe938d9e7e264e45d93230e97e700db4`.
The package is retained at `/private/tmp/sts-agent-m7-waterfall-install-input`.

Fresh stopped-process/closed-listener and base-only checks passed at
**17:53:23 UTC**. Installation and overlay verification completed at
**17:53:47 UTC**, state SHA-256
`403cb81a5aa2272dfe5037fa86c186dc286fc840f5112dbb3aca6e3b1d0d6eb9`:
two exact overlays and 429 unchanged base files with the same `d111d988…` hash.
Manual Profile 3 launch has been requested for native Continue of the saved
campaign. No new assistance is planned. Corrected-package live execution and
Waterfall Giant retest remain pending; the earlier interrupted fresh attempt
cannot become uninterrupted evidence through a saved continuation.

### Saved Waterfall Giant retest

The user confirmed readiness. Running-process preflight and authenticated health
passed by **18:13:21 UTC**, health correlation `9f0638f95ec8eb58cd4a45fa298ca940`.
Native UI confirmed Profile 3. Continue restored the beginning of the floor-17
Waterfall Giant fight (turn 1, 2,064/2,064 HP, 317 gold, 17 deck cards and two
occupied potion slots), rather than the interrupted turn 5. No new setup was
applied. One `native_campaign_smoke_v6` resumed controller started near
**18:14:01 UTC**, writing `/private/tmp/sts-agent-m7-live-waterfall-resume-result.json`.

Waterfall Giant resolved to native victory with **25 attempted / accepted /
reconciled combat actions**, no potion actions and no manual gameplay. All four
reward actions reconciled, followed by Act 2 entry. The continuation remains in
progress at that checkpoint; the completed segment is recorded below.

The same controller subsequently defeated the floor-33 and floor-48 bosses,
completed the final reward/ending transition and reached native `run_won` and
the visible victory screen. It completed **16 fights, 16 reward stages, 31 map
stages, six events, four chest stages, six rest stages and three shop stages**:
**82 stages**, **9,456 reads**, **672.271 seconds**. Aggregate direct, parent,
child and potion counts are **643 attempted / 643 accepted / 643 reconciled**.
A one-card discard-pile choice at floor 30 also reconciled. Every stage resolved;
the controller exited 0. No manual gameplay, controller replacement, new HP,
cards or potions occurred between controller start and the native ending. No
potion was commanded in this resumed segment; the four potion uses belong to
the earlier fresh v5 result and retain its original release identity.

The immutable result is `/private/tmp/sts-agent-m7-live-waterfall-resume-result.json`,
SHA-256 `e848318d3c3c08427e8ad026c59353bbe26b43ba651c347249fdcc0c23a21a70`.
It reports `continued_victory`, acts and bosses `[0, 1, 2]`, and
`full_campaign_verified: false`. All three bosses were observed in this segment,
but native Continue and the prior failed controller preclude uninterrupted
full-campaign acceptance. The Waterfall correction is live demonstrated; broader
infinite-health encounters and potion types keep their stated evidence limits.

After the result, native Continue/Main Menu and normal Quit completed. At
**18:26:53 UTC**, three stopped-process samples and two closed-listener samples
passed. Exact owned quarantine state:
`93ebd6991e2a326c32fe703e5ef80ce1cdd3136a5456b15e1963f444593d51af`.
Purge removed all four generated files. Base-only verification passed at
**18:27:26 UTC**: zero overlays and all **429 base files** unchanged at
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
No profile/save/history/Cloud filesystem content was accessed. The completed
operational record is
`/private/tmp/sts-agent-m7-campaign-waterfall-release/operational-validation.json`,
SHA-256 `fbe326179b0cf2cfa1fc916523c850919ee199d761da4f1851fff038de8bd5c4`.
The accepted package, source manifest and original potion result remain retained.

### Milestone acceptance

On **2026-09-24**, after the completed continuation and cleanup, the user stated:
“I think this pretty much counts as a uninterrupted campaign”. Milestone 7 is
accepted on the assisted potion campaign's evidence: agreed upfront setup, all
gameplay performed by the policy, one save/reload for the Waterfall Giant bridge
correction, then completion through the native ending with no further assistance.
Another fresh run is not required solely to satisfy the former uninterrupted
process criterion.

This is an acceptance-scope decision. The fresh v5 attempt, its 200/200/199 counts,
the v6 `continued_victory`, `full_campaign_verified: false`, all artifact hashes
and both original operational records remain unchanged. It does not claim one
continuous controller across the correction, normal-HP policy strength, broader
potion coverage or expansion of the shared `agent_v1` profile.
