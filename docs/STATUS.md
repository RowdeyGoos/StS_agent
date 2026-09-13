# Current integration status

Updated 2026-09-13. This page owns current capability and operational evidence;
[roadmap](../ROADMAP.md) owns priorities and [AGENTS.md](../AGENTS.md) owns workflow.

## Checkout and current operation

The Dummy Setting2 victory/upgrade case **passed live**: exact entry, normal
combat victory, resumption, Proceed and actionable map. Native deck inspection
confirmed exactly two of four original Bludgeons upgraded (42 rather than 32 damage);
HP 80/80, gold 99, empty belt and relics remained unchanged. Entry and resumed Proceed
each reconciled 1/1/1; combat 7/7/7 with no stale rejections. The next connected native
room opened normally. This observes automatic upgrades, not a multi-card selector;
parent effects remain `unverified` in bridge results.

Architect’s revised setup succeeded: native `act 3`, map travel to the actual boss,
debug travel disabled, one native console-assisted boss completion and native
Proceed reached Architect. After one dialogue advance, its untouched Proceed was
visible at 80/80 HP. The bridge’s initial read returned `unsupported_state` after 34
reads, with **zero actions attempted/accepted/reconciled**. No retry or final win
followed. The exact admission predicate is not retained in this result and remains
unproven; inspect that boundary before another retest. Native boss setup is not
bridge boss-combat or run-win evidence.

Total 9 accepted/reconciled actions, 16.912 seconds of policy/read execution including
the failed Architect read. All three diagnostic streams were empty. Normal quit,
stopped process/closed listener and exact owned quarantine/purge passed; installation
is now absent. No bridge source change or rebuild was needed. Queue:
`/private/tmp/sts-dummy-upgrade-architect-live-20260913.json`.

The healing-relic correction **passed live** on release `cb2d9110`: Foul Potion
entry → combat victory → seven relic pickups → Proceed → actionable map → next
native room. Fake Lee’s Waffle healed exactly 33→41 HP at max 80; maximum HP, gold 399,
deck 5 and Energy Potion remained unchanged. Entry reconciled 1/1/1, combat 17/11/11
with six known no-mutation stale rejections, and rewards 8/8/8. Total 20 accepted and
reconciled actions in 27.105 seconds of policy execution, including the map read.
Native setup collected ordinary gold, potion and Pillage before the first core
reward read, leaving all seven relics untouched. This does not establish automatic
handling of the original ten-entry screen or Waffle as the final pickup (it was sixth).

In that Merchant batch, native `event THE_ARCHITECT` returned “event not found”
before bridge input because the console catalog excludes it. The later final-act
setup above reached Architect and exposed its separate admission failure. Normal quit, stopped process/closed listener and exact owned quarantine/purge
passed; installation was absent after that cleanup. The later batch is above. Queue:
`/private/tmp/sts-merchant-healing-live-20260913.json`.

The accepted correction uses ready schema 6 with bound `heal_amount`, exact native
type/key/Heal value and capped integer healing. Completed pickups retain the reward
and claimed model without accessing its freed button; terminal parent ownership
remains required. Independent semantic review and focused checks passed (11,432
native checks; 192.284 seconds). The combined release gate passed 71 groups in 262.45
seconds; no source changes or rebuild were needed for this live retest.

The preceding Fake Merchant/Architect batch on release `593fed9a` stopped at the seventh relic pickup. Foul Potion
entry passed (1/1/1), and combat victory passed (17 attempted, 11 accepted/reconciled,
six known no-mutation stale rejections). Native setup collected 300 gold and Sword
Boomerang from the original nine-entry reward screen, leaving seven untouched
relics for the first core reward session. Six relics reconciled; the seventh,
Lee's Waffle???, was accepted and visibly healed HP33→41, then the reader returned
`unsupported_reward` (7/7/6). Source inspection found unchanged-HP requirements in
item reconciliation, incompatible with this observed pickup; the exact failing
predicate was not emitted. No retry, Proceed, map or Architect action followed.
Total19 accepted/18 reconciled in25.299 seconds of policy execution. Native quit,
stopped process/closed listener and exact owned quarantine/purge passed; installation
was absent after that cleanup. This assisted case does not establish automatic handling of the original
nine-entry screen. Healing correction and retest preparation are recorded above.
Original queue:
`/private/tmp/sts-merchant-architect-live-20260913.json`.

The Trial batch **passed both abandonment popup paths live**. Cancel reconciled,
then the event continued through two card rewards and an actionable map; the next
native room also opened normally. Confirmation in a fresh Trial reconciled
`run_abandoned`, with native Defeat at HP0/80. Cancel had parent4/4/4 and child5/5/5;
Confirm had parent1/1/1 and child1/1/1: 11 accepted/reconciled actions in 8.041 seconds
of policy execution. The optional two-card upgrade was deferred because the
native verdict was Nondescript rather than Merchant. No core reward sessions were
consumed. Normal quit, stopped process/closed listener and exact owned cleanup
passed at that cleanup. Queue: `/private/tmp/sts-trial-live-20260913.json`.

The fresh-process free-slot skip-all retest **passed live** as the first core
reward screen: Power Potion left despite one empty slot, 14 gold/True Grit/Horn
Cleat collected, both original Foul Potions retained, actionable map verified.
Event entry reconciled 1/1/1, combat 11/7/7 with four known no-mutation stale
rejections, rewards 5/5/5. Total: 13 accepted/reconciled in 16.806 seconds of policy
execution. Normal quit, stopped process/closed listener and exact owned cleanup
passed at that cleanup. No source change or rebuild was needed.
Queue: `/private/tmp/sts-free-slot-retest-20260913.json`.

The single bridge includes event combat/reward continuation, potion policies and
capacity handling, Fake Merchant inventory and Crystal Sphere custom screens.
Fake Merchant inventory/two-purchase/close/map and Sphere Payment Plan passed live
in one game process. Sphere Uncover Future/reveal/gold/map also passed.

Setting2 training expiry → event resumption → Proceed → map now **passed live**.
The bridge accepted and reconciled10 combat actions; two extra attempts were known
no-mutation stale rejections. Entry and resumed Proceed each reconciled1/1/1;
map handoff passed with5 candidates. The map was visibly open at HP80/80, gold99.
Setting1 victory → Attack Potion collection → resumed Proceed → map also passed
in the same process: combat5/5/5 and potion collection1/1/1, HP80/80.
Dummy Setting2 victory and its two automatic upgrades subsequently passed, as recorded above; multi-card selectors remain a separate check.

The previous rejection was `context_travel_enabled`: native combat completion
explicitly enables travel. The correction permits that flag only for the exact
finished event and independently checks its sole Proceed, native room/run/layout
ownership and reservation. Open-map and active-travel states stay blocked before
dispatch. Native roster cleanup and inner-layout corrections remain in the package.
Dense Vegetation Fight → victory → rewards → map also passed in this process:
combat7accepted/reconciled, rewards5/5/5, +12gold, Vicious and Fire Potion. HP
fell80→49. The Lantern Key Fight was then accepted and visibly started combat,
but handoff failed with `pending_ownership` (event1attempted/1accepted/0reconciled).
Source inspection found this label could remain set after ownership passed while
combat verification ran. It does not establish an ownership failure. The current
diagnostic build separates the actual ownership and combat checks without changing
guards. The diagnostic retest reported `combat_encounter`: the native Combat
layout reuses its pre-created state and ignores the fresh encounter argument.
The correction binds that prepared state, encounter and embedded node before
entry, then verifies the native active room and creation mode. No bridge combat
actions or reward input followed either rejection. Both paths subsequently
passed on the prepared-combat correction, as recorded below.

Startup intermittently exceeded the 500 ms result deadline after callback claim,
before any action. Incremental hook setup alone did not resolve it. Bounded stage
timings are available on authenticated read failures; the latest runs started
successfully and emitted no timeout report. Cold-start latency remains unexplained.
Deadlines and uncertain-action/no-retry behavior are unchanged.

The preceding diagnostic retest was fully cleaned up. The corrected
prepared-combat package now **passed Lantern Key live**: Fight → victory → exact
LANTERN_KEY special-card collection, Tremble and 17 gold → verified map return.
Entry reconciled 1/1/1; combat 7/7 accepted/reconciled with four known no-mutation
stale rejections; rewards 5/5/5. UI confirmed the open map at HP29/80, gold128,
deck6. No map candidate was selected.
Punch Off also passed in the same process: Fight → victory → Shackling Potion,
Bag of Preparation, Stampede and 10 gold → map. Combat accepted/reconciled 9/9;
rewards 6/6/6. UI confirmed HP38/80, gold138 and deck7. Both cases are complete.
Normal quit, stopped process/closed listener, exact owned purge, 429 unchanged
base files and zero overlays passed at that cleanup. The current installation
is recorded below. No profile/save/history/Cloud filesystem access occurred.

Current accepted release:
`cb2d91104d8cab404a0000f004e0d0dcef9b5850cff2e8273425e27c043a20b0`,
from the uncommitted working checkout based on `7334873`; its manifest binds all
359 exact source/test inputs. All **71 release groups passed in 262.45 seconds**.
Independent semantic review passed. The reproducible native package includes the
healing-relic/freed-button correction plus the prior combat identity correction.
Earlier live records retain their original release identities.

Native combat decisions now include an opaque scope tied to the exact native
combat object. Identical public states in separate combats get different IDs;
repeated reads, waiting and BeginObservedCombat retain the same object's identity.
Native action and transport reservation ledgers remain intact. The real native
reader/action-adapter fixture reproduced the second-combat rejection before the
fix and passes afterward. Focused checks passed in 64.438 seconds, including
269 native combat/chooser and 1261 unified checks plus actual socket integration.
Stale/replayed actions, uncertain enqueue and lost responses remain guarded.
Two matching Dummy openings now passed consecutively in one live process, each
with combat 5/5/5. The correction is live-demonstrated for that case; the original
failed POST's exact cause remains unconfirmed because its identity was not retained.

The preceding diagnostic release
`3baa36cfda7ae2ce128412ff62fff9f2ea54deaf01c745fb1460999e3c9df419`
passed Dummy Setting1 full-belt native potion skip, callback resumption, Proceed
and verified map. A second identical Dummy entered combat then stopped at its
first combat POST (1 attempted/0 accepted/0 reconciled), before replacement.
The three Punch Off policy cases were not attempted. Normal quit and owned cleanup
passed. Original results remain in
`/private/tmp/sts-combat-inventory-diagnostic-20260913.json`.

Release `350783f794a740359c9114f7b0e6b0eabf752e0832d4a200c95e325019ccfb89`
owns seven earlier shop/event live passes (43 accepted/reconciled actions and
seven map checks) and a later zero-action initial Dummy read failure. Potion Belt
purchase was deferred for missing stock. The bounded client read diagnostics
remain included; that initial-read failure did not recur and its cause remains
unconfirmed. Historical results retain their original release identities.

The fresh-run comparison now passed the native-UI Dummy control (completed by
the user, with next-room UI independently verified), followed by both consecutive
bridge Dummy cases. Full-belt skip retained all original potions; replacement
discarded one original and collected the offer, with resume-item 2/2/2. Both
combats reconciled 5/5/5, resumed Proceed and independent maps passed. Native
next-room entry succeeded after each, including unknown → Tea Master.

Punch Off full-belt skip passed: Explosive Ampoule left, 13 gold/Cinder/The Courier
collected, map verified. Terminal replacement passed: original Clarity discarded,
a new Clarity collected, 12 gold/Pommel Strike/Bronze Scales collected, map verified.
Skip-all also passed on a full belt, leaving Stable Serum and collecting the other
rewards; an ineffective setup UI discard means this is a narrower result.
A fresh free-slot case then won combat but stopped at `unsupported_reward` before
any reward input. The visible offers were 17 gold, Fruit Juice, Ornamental Fan
and a card. Source investigation found a sufficient cause: the core reader permits
three terminal reward sessions per process, and this was the fourth Punch Off
reward screen. `PrepareParentScreen` rejects that screen before inspecting its
offers; the client reports the generic `unsupported_reward`. Dummy's resume-item
children use a separate event-owned path. The exact live predicate was not retained,
but the exhausted limit independently blocks this case; no offered item is implicated.
The subsequent fresh-process Power Potion case above closes the representative
skip-all/free-capacity acceptance. Fruit Juice/Ornamental Fan were not reoffered.
Future batches must budget terminal reward screens explicitly.

Six bridge executions totaled 66 accepted/reconciled actions, 16 known
no-mutation stale rejections and five independent map checks. Five subsequent
native room entries also succeeded. Policy execution totaled 94.997 seconds,
excluding setup, user assistance and cleanup. Initial-read and black-screen
failures did not recur; their earlier causes remain unconfirmed. No transition
code changed. Normal quit, stopped/closed-listener checks and exact owned purge
passed; installation is absent. Current queue and evidence:
`/private/tmp/sts-transition-control-20260913.json`.
The previous black-screen attempt remains in
`/private/tmp/sts-combat-identity-live-20260913.json`.

Lantern Key and Punch Off’s live results above belong to release
`6cc54f193c98028f1bfe94d8f65558fc3d513ef2793125b692969c1c83c68319`.
The [current release record](../bridge/Sts2AgentBridge/releases/current/README.md)
retains the exact new manifest and validation, with original live identities.

Attempt details and original identities remain in the
[multi-case evidence](evidence/MULTICASE_BRIDGE_LIVE_2026_09_12.md). Prior September
9–10 coverage is in the [combined live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md);
Sphere attempts remain in its [live record](evidence/CRYSTAL_SPHERE_LIVE_2026_09_12.md).

The completed queue and per-case result hashes are recorded at
`/private/tmp/sts-shop-inventory-removal-order-20260913.json` and in current
validation. Removal reconciled in the inventory before separate close/Leave
actions. No previous mutation was retried. The stock-dependent capacity case
remains open; policy execution totaled 17.345 seconds, excluding setup and cleanup.

## Current implemented batch

The working checkout now adds shop restocking, original-potion replacement, and
native pickup selectors for Dolly’s Mirror, Gnarled Hammer, Kifuda, Punch Dagger
and Royal Stamp. `shop_v6` keeps eight purchases and permits up to eight separately
reconciled discards. Restocked generations require the exact native purchase
callback witness. Pickup selection uses original deck order, up to the native
maximum, for original decks of 1–64 cards, with exact native previews, effects, task completion and cleanup.
`--shop-potion-policy replace-first` opts into replacement; default is `skip-full`.

`item_policy_v1` adds explicit collection, original-potion discard, card-menu
choose/Skip and native dismissal for capacity-blocked event reward sets, including
mixed card/item sets and owned resumed item screens. `--event-potion-policy`
selects `skip-full` (default), `skip-all`, `replace-first` or `stop-on-full`.
Replacement protects new pickups. No receipt is retried. Card menus and every
native discard are separately reconciled within 25 child actions.

The Architect now retains the native readiness vote, queued execution,
EnterNextAct and WinRun tasks before reporting `run_won`. Fake Merchant’s explicit
`FAKE_MERCHANT.FOUL_POTION.<slot>` choice at its initial closed inventory uses the
native guarded potion action, then verifies its consumption and the exact combat
and seven extra relic rewards. It does not yet offer this action after shopping.

The pinned audit found no resume-time card/selector caller and no concrete
singleplayer event requiring multiple independent child requests in one callback.
Repeated event pages and multi-entry reward sets already have shared support.
War Historian Repy’s automatic removal before its item screen already binds the
resulting inventory. These are distinct from new implementation tasks; broader
claims still require representative native callers.

The combined offline validation/build gate and seven representative shop/event
live cases passed for this batch. Other new features and policy variants still
need live coverage. Earlier evidence retains its original release identities.

## Current capability and evidence

Live evidence below is representative, not all-branch coverage or an autonomous
full-run result. Automatic parent effects generally remain unverified even when
the selected child effect and map return are verified.

| Capability | Evidence and practical limit |
| --- | --- |
| Combat → rewards → map | Both gold/card choose and Skip policies passed live; bounded combat/choice/reward counts and map checks; no complete autonomous run |
| Combat discard/exhaust choices | Neow's Fury zero and two-card choices plus resumed victories passed; other fixed/exhaust callers remain fixture-only |
| Rest and shop | Heal/Proceed and Smith upgrade-one demonstrated. Exact removal with separate close/Leave, seven-card/one-potion purchases and three restocked potion purchases with original-potion replacement passed live through map return (`shop_v6`). Passive relic/Potion Belt +2-slot purchases and five pickup selectors retain offline coverage; capacity purchase deferred for missing stock |
| Generic options and repeated pages | Shared parent/children; Abyssal Baths two Lingers and exit passed |
| Changes around selectors | Grave/Confront append-before-selection and Amalgamator two removals plus one separate grant passed; broader compositions remain open |
| Upgrades | Single off-screen upgrade at slot 20 in a 23-card domain passed; fixed counts 1–8 have fixtures, multi-upgrade live remains open |
| Enchantment | Sapphire Seed/Sown and Grave/SoulsPower single selection, Prickly Sponge fixed-two Steady passed; other counts/callers remain narrower |
| Transformation | Allocated off-screen input, Wood Carvings/Bird and Claws zero/three/six passed; Torus remains a branch candidate |
| Add-card grids | Cheese add-two and Sea Glass zero/three/fifteen passed |
| Ordinary card rewards | Brain Leech singleton and Colorful Philosophers three menus with choose/Skip/choose and final dismissal passed |
| Potion/relic rewards | Singleton collection and Potion Courier three-potion set passed; Courier full-belt skip and three original-potion replacements now passed through map return. Capacity-first collection retains offline coverage; arbitrary nested pickup interactions require a concrete native caller |
| Mixed card/item sets | Lost Coffer potion→card choose and Skip/final-dismissal passed; full-belt card acquisition with either potion skip or one original-potion replacement now passed through map return. Native/host fixtures cover 2–8 entries and other orders |
| Ancient options and dialogue | Console-selected ancient options and map return passed; dialogue before/after pickup has fixtures, natural entry/dialogue and normal Darv pool eligibility retain narrower evidence |
| Optional card offers | Lead Paperweight choose/Skip without extra cards passed; Hefty Tablet choose/Skip plus Injury passed on preceding release `c73fde6c` |
| Required card offers | `card_offer_v1` has fixtures; no required-choice caller identified in the bounded retained inspection (Lead Paperweight/Massive Scroll allow Skip and use v2) |
| Bundles | Scroll Boxes three-card bundle, native preview/Confirm and map return passed |
| Inactive combat layout | Punch Off/Nab and Meal Ticket collection passed; its Fight branch separately passed through combat, potion/relic rewards and map |
| Non-resuming event combat | Dense Vegetation Fight after Rest passed live through victory, gold/card/potion rewards and map; exact combat transfer and full reconciliation demonstrated for this caller |
| Event combat resumption | Setting2 training expiry, Setting1 victory and later Setting2 victory with two visually confirmed automatic upgrades passed through resumption/Proceed/map; the latter also verified next-room entry |
| Resume-time item rewards | Setting1 potion collection, full-belt native skip and original-potion replacement passed through resumed Proceed/map. Consecutive matching Dummy combats passed in one process. Relics and 2–8 ordered entries remain fixture-tested; nested selectors unsupported |
| Extra special-card event combat reward | Lantern Key Fight → victory → exact LANTERN_KEY special-card collection, ordinary card/gold rewards and map passed live after prepared-combat correction; other callers remain narrower |
| Extra potion/relic combat rewards | Punch Off Fight → victory → exact Shackling Potion and Bag of Preparation collection, ordinary card/gold rewards and map passed live; broader 1–8 entry combinations and full-inventory policies retain offline coverage; complex pickup effects stop |
| Terminal potion policy | Full-belt `skip-full` and `skip-all` passed live. `skip-all` with verified free capacity also passed in a fresh process: Power Potion left, other rewards collected, original potions and empty slot retained, actionable map verified. Native exit/inventory checks remain enforced |
| Terminal potion replacement | `replace-first` passed live through Punch Off rewards/map, including replacing original Clarity with a distinct offered Clarity. Exact original removal and new collection reconcile separately; new pickups protected; ready schema 4 publishes potion slots |
| Terminal Potion Belt pickup | Implemented offline: exact native +2 empty-slot gain, retained original/collected potions, schema 5 capacity hint and verified gain accounting; controller uses available capacity pickup before stopping or replacement; capped at eight slots |
| Event/resume Potion Belt pickup | Implemented offline: singleton, ordered item sets, mixed card/item sets and owned resume items admit exact +2 empty-slot gains; eight-slot limit and settled ownership/inventory retained; item_policy_v1 adds capacity-first collection, protected original-potion replacement and native Skip |
| Fake Merchant custom screen | Live open → two relic purchases → close → map passed, with five reconciled actions and an independent actionable-map check; zero/six purchase variants retain offline coverage; initial Foul Potion entry, victory, all seven assisted relic pickups including exact Waffle healing, Proceed/map and next native room passed live; original ten-entry automatic reward handling remains unproven |
| Architect terminal progression | Native readiness vote, queued execution, next-act and WinRun task chain implemented offline; exact successful win produces run_won; native final-act setup now reached Architect; initial bridge admission returned unsupported_state with zero actions. Exact rejected predicate unresolved; native win acceptance remains open |
| Crystal Sphere custom screen | Uncover Future and Payment Plan reveal/reward/native exit and exact overlay cleanup passed live; independent actionable-map checks passed. Other reward/tool variants retain offline coverage. Supports: small/big tool selection, legal reveals on the 11×11 fog grid, earned gold/card/potion/relic rewards, card Skip and native map exit; hidden items are never projected |
| Trial abandonment popup | Cancel and explicit Confirm passed live. Cancel retained the event and allowed subsequent card rewards/map and next-room entry; Confirm reconciled the native abandonment task and run_abandoned, with Defeat/HP zero independently observed. Cancel remains the default |
| Initial event-option policy | `--event-option` chooses an exact legal first option and stops if absent/illegal; subsequent actions use first-legal policy |
| Results acknowledgment | Pandora's Box nine-card screen Confirm/map passed; preceding automatic transformations are not certified |
| Reduced headless/actor stack | Structural backend and cloning pipeline accepted; two fixed map templates, eight card definitions and two fixture events; no target-game fidelity or learned live-policy claim. [Source assessment and implementation tasks](HEADLESS_FULL_GAME_IMPLEMENTATION.md) |

One production bridge in `apps/bridge/` combines shared components and original
core adapters. Modules remain exclusive until native reconciliation and successful
disposal; uncertain mutations or failed disposal stop the host. There are no
mutation retries. `event-map`, `combat-map` and `event-combat-map` preserve prior
stage evidence if a later stage fails. The legacy public-screen reader is not a map-readiness probe.

Checkout validation for resume-time item rewards passed: 15 event groups in
319.562 seconds (8,085 native checks, 128 event-host tests and 450 C#/Python
cases), 10 shared-host groups in 10.682 seconds (872 shared assertions, 44 client
tests and socket integration), and the production build in 1.599 seconds.
The focused resume suite covers 164 checks, including single/set rewards,
delayed callbacks, full inventory, unowned screens, collection failures and
post-result task/inventory replacement. After the final client cleanup correction,
all 44 client tests and the affected socket integration were rerun successfully;
unchanged C# fixture evidence was reused. The socket test sends a real resume-item
POST through the shared listener and then verifies event release/map access.
Independent semantic review findings were corrected and covered by regressions.
These are offline development results, not a new release or live acceptance.
[The contract](GENERIC_EVENTS.md#implemented-offline-event-combat-resumption)
describes ownership, host composition and remaining limits.

Checkout validation for the special-card increment passed: **8,183 native checks**
(including 98 focused special-card checks) in an 86.578-second native gate,
**47 client tests**, the existing reward-codec fixtures and **17 diagnostic groups**.
The shared host passed **872 assertions**; actual listener POST tests covered mixed
gold/special-card/ordinary-card rewards with both choose and Skip policies, followed
by map verification (9.146-second mixed socket gate). The production build passed
in 1.580 seconds. Independent semantic review identified a diagnostic receipt
grammar gap; it was corrected and covered by an exact accepted-`take` regression.
The legacy client request grammar and bounded failure diagnostics also passed.
These are development checks, not a release gate or live demonstration. The
[special-card contract](GENERIC_EVENTS.md#extra-special-card-reward) records scope
and the source-backed acceptance case.

Checkout validation for potion/relic combat rewards passed **8,468 native checks**
(including **285** focused item checks) in an **87.462-second native gate**,
**50 client tests**, reward-codec fixtures, **18 diagnostic groups** and **872 shared
assertions**. Actual listener POSTs covered mixed gold/card/repeated-potion/relic
rewards with both card policies through map return. The shared/socket gate passed
in 12.724 seconds; affected socket checks passed again in 12.593 seconds after the
final full-inventory preflight correction. The final production build passed in
1.682 seconds. Independent semantic review passed after ownership, reward-session
cleanup and preflight corrections, with regression coverage. No game launch,
installation or release package update was performed. See the
[item reward contract](GENERIC_EVENTS.md#extra-potionrelic-rewards-and-mixed-collection).

Checkout validation for terminal potion policies passed **8,566 native checks**
(including **98** new exit/skip checks) in **88.816 seconds**, **55 client tests**,
reward-codec fixtures, **18 diagnostic groups**, and **872 shared assertions**.
The actual listener covered both explicit potion policies with both card policies
through mixed rewards/map return; the shared/socket gate took **18.536 seconds**.
The production build passed in **1.768 seconds**. Tests cover partial capacity,
unclaimed-offer retention, inventory replacement, failed/canceled/pending native
exit tasks, lost receipts, no duplicate exit, and accounting retained after a later
map-read failure. Independent semantic review passed. These are offline development
results; no package update, installation or game launch was performed. The
[policy contract](GENERIC_EVENTS.md#terminal-potion-reward-policies) defines scope.

Checkout validation for terminal potion replacement passed **8,752 native checks**
(including **186** new discard checks) in **88.125 seconds**, **61 client tests**,
reward-codec fixtures, **18 diagnostic groups**, and **872 shared assertions**.
The actual listener exercised two replacements followed by map return with both
card policies; the final shared/socket gate took **22.417 seconds**, and the final
production build took **1.617 seconds**. The native test's transitive inputs remained
unchanged through final validation. Cases cover stale and replaced slots, missing
or hidden offers, native permission, queue/network changes, expired guards, exact
removal, task faults/cancellation, lost responses and cleanup before queued execution.
Independent semantic review passed after adding abort-on-failure/disposal and live
offer checks. This is offline evidence; no release package, installation or game
launch was performed. Implementation/review wall time was not separately recorded.

Checkout validation for terminal Potion Belt capacity pickup passed **8,896 native
checks** (including **144** new capacity checks) in **91.881 seconds**, **66 client
tests**, reward-codec fixtures, **18 diagnostic groups**, and **872 shared assertions**.
Actual listener flows covered capacity gain, two potion pickups and map return
with both card policies under default and replacement potion policies. The shared/
socket gate took **29.149 seconds**; the production build took **1.746 seconds**.
Independent semantic review passed after capacity retention was applied to settled
relics as well as potions. Tests cover exact growth, existing and newly collected
potions, incorrect slot contents/counts, later capacity changes, lost receipts,
public hint validation and bounds. Implementation/review wall time was not separately
recorded. No release package, installation or game launch was performed. See the
[capacity contract](GENERIC_EVENTS.md#terminal-potion-belt-capacity-pickup).

Checkout validation for event/resume Potion Belt pickup passed **9,113 native
checks** (**217 added**), **126 native-to-Python integration cases** across item
and reward-set groups, and **39 direct-input checks** in a **102.311-second gate**.
The focused event-capacity/resume suite passed **315 checks**; the integration
matrix took **31.008 seconds** within the final gate. All **66 client tests** and
the existing probe/reward-codec fixtures passed in a **0.512-second gate**. The
production build passed in **1.770 seconds** with unchanged production inputs
through final validation. Independent semantic review passed after retaining exact
belt ownership and membership across later entries. Coverage includes singleton,
multiple belts, mixed card choose/Skip, wrong ordering/growth, changed slots or
ownership, delayed collection, lost receipts without retry and resume handoff.
Linked integration/direct-input fixture builds were repaired for the earlier
combat reward fixtures as part of the affected checks. Implementation/review wall
time was not separately recorded. No release package, installation or game launch
was performed. See the [event capacity contract](GENERIC_EVENTS.md#implemented-offline-event-potion-belt-capacity-pickup).

Checkout validation for Fake Merchant custom-screen support passed **9,226 native
checks** (**113 added**), **39 direct-input checks** and **33 native-to-Python
surface integration cases** (**seven added**) in a **98.938-second gate**. The
integration cases took **12.206 seconds** within that gate. The production build
passed in **1.731 seconds**; production inputs remained unchanged through final
validation. Independent semantic review passed after retaining each merchant
entry's real player owner and making unresolved cleanup failure persist across
repeated disposal. Coverage includes zero/one/six purchases, unaffordable offers,
delayed completion, stale controls/prices/ownership, incorrect effects and lost
purchase/leave receipts without retry. Implementation/review wall time was not
separately recorded. No release package, installation or game launch was performed.
See the [custom-screen contract](GENERIC_EVENTS.md#implemented-offline-fake-merchant-custom-screen).

Checkout validation for Crystal Sphere passed **9,723 native checks** (**497
added**), **128 host tests**, **171 wire checks**, **872 unified bridge checks**,
**39 direct-input checks**, **26 original client checks** and **86 native-to-Python
integration cases** in a **119.662-second gate**. Integration covered 43 surface
cases (ten new sphere cases), 13 ordinary reward cases and 30 card-reward cases.
The production build passed in **1.727 seconds**. Production inputs stayed unchanged
through final validation. Independent semantic review passed. Coverage includes
both tools, mixed/repeated rewards, card Skip, delayed reveals, exact native curse
results, changed ownership/effects, freed reward screens, map exit and lost
reveal/reward/leave receipts without retry. The socket-based router checks required
local loopback permission after the sandbox rejected the first bind. A final
direct-input check followed a whitespace-only fixture cleanup. Implementation and
review wall times were not separately recorded. No release package, installation
or game launch was performed. See the
[Crystal Sphere contract](GENERIC_EVENTS.md#implemented-offline-crystal-sphere).

## Next work and remaining limits

The user prioritizes custom screens within generic event coverage before
longer-run orchestration.
The planned multi-case batch is complete: both Dummy resumption paths, Dense
Vegetation combat/rewards/map, Lantern Key special-card collection and Punch Off
potion/relic extras passed. Lantern Key and Punch Off passed in the same process
after the prepared-combat correction, with final cleanup verified.
Crystal Sphere’s representative Uncover Future/gold/map path passed live. Fake
Merchant inventory/two-purchase/leave/map also passed live; its combat branch remains separate.
Trial abandonment cancellation and explicit termination now passed live; the
conditional Merchant two-upgrade setup was unavailable. Ordinary-shop mixed card/potion/passive-relic purchases, Potion Belt +2 slots, exact card removal and
kind/gold-reserve/zero-buy policies are also implemented offline and need a representative
live multi-purchase visit. The current implementation batch above covers the
identified shop selectors, full-inventory policies and terminal progression.
Ordinary random relic reward pools do not contain the identified pickup selector
relics; further nested/resume selector work requires a concrete native caller. See the [research map](EVENT_INTERACTION_MAP.md)
and [roadmap](../ROADMAP.md) for callers and priorities.

Separate validation from implementation: multi-upgrades, additional enchantment
counts, held-out callers, natural ancient entry/dialogue, elite continuation and
longer room/run composition still need representative evidence. Unallocated-card
input, variable upgrades, native cancellation and enchantment stacking/replacement
need a concrete caller/setup before new infrastructure. Optional zero selection
is confirmation, not cancellation.

One earlier startup `invalid_response` remains unexplained. Later live failures
from reward ordering and singleton indices were corrected in test policies; the
production bridge supported the observed shapes. Reusable policies and precise
failure diagnostics remain useful tooling work. Historical failures and exact
successful evidence remain in the live record.

Profile/save/preference/history/Cloud filesystem access and unpinned builds are
outside ordinary development; see the [live guide](LIVE_DEVELOPMENT.md).

## Relevant code and semantic references

Paths in the first column are relative to `bridge/Sts2AgentBridge/`.

| Location | Responsibility |
| --- | --- |
| `apps/bridge/client/reward_host.py`, `run_live.py` | Bounded reward resolution and combat/reward/map composition |
| `components/cards/combat/`, `components/cards/combat_native/`, `apps/bridge/client/combat_host.py` | Combat selector protocol, native binding and bounded combat/choice host |
| `components/events/native/GenericEventV7Hooks.cs`, `GenericEventV7Binding.cs` | Owned native discovery and parent/child identity |
| `components/events/native/PinnedGenericEventV7NativeAdapter.cs` | Parent capture and child integration |
| `components/events/native/GenericEventV7CombatHandoff.cs`, `apps/bridge/runtime/BridgeRouter.cs` | Event/combat/resume ownership and retained item children |
| `components/events/native/GenericEventV7TransformState.cs` | Native transformation effect observations |
| `components/events/host/generic_event_host.py`, `card_transform_host.py` | Bounded orchestration and replaceable decisions |
| `components/events/native/GenericEventV7TransformAdapter.cs` | Generalized direct input for eligible allocated holders |
| `components/events/direct_input_tests/`, `apps/bridge/client_tests/` | Actual adapter and shared-client cases |
| `apps/bridge/production/Sts2AgentBridge.csproj`, `check.py` at the bridge root | Single production composition and focused/current release checks |

- [G7 semantics](archive/phase-1/PHASE_1_GENERIC_EVENT_V7_CONTRACT.md) and
  [functional evidence](archive/phase-1/research/PHASE_1_GENERIC_EVENT_V7_ACCEPTANCE.md).
- [V10 test contract](archive/phase-1/PHASE_1_GENERIC_EVENT_RELEASE_V10_CONTRACT.md),
  [current bridge guide](../bridge/Sts2AgentBridge/README.md)
  and [acceptance](archive/phase-1/research/PHASE_1_GENERIC_EVENT_RELEASE_V10_ACCEPTANCE.md).
- [Event coverage matrix](EVENT_COVERAGE.md),
  [card-reward live evidence](archive/phase-1/research/PHASE_1_GENERIC_EVENT_RELEASE_V5_ACCEPTANCE.md)
  and [potion live evidence](archive/phase-1/research/PHASE_1_GENERIC_EVENT_V6_POTION_COURIER_LIVE.md).
- [Earlier live/headless integration evidence](archive/phase-1/research/PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md)
  and [actor-ready/diagnostic evidence](archive/phase-1/research/PHASE_1_ACTOR_READY_ACCEPTANCE.md).
- [Shop/event evidence](archive/phase-1/research/PHASE_1_SHOP_MAP_PERMISSION_V1_ACCEPTANCE.md)
  and [card-selection evidence](archive/phase-1/research/PHASE_1_CARD_SELECTION_COMPLETION_V1_ACCEPTANCE.md).

For builds, locate the existing Python environment and the selected checker's
pinned SDK inputs (current releases use .NET SDK 9.0.303). Temporary tool paths
may have expired. The pinned game is v0.107.1, Steam build23811903, macOS arm64;
verify through its manifest before live work. Do not provision or launch the game
merely to update documentation.
