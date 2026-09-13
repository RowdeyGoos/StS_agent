# Current integration status

Updated 2026-09-12. This page owns current capability and operational evidence;
[roadmap](../ROADMAP.md) owns priorities and [AGENTS.md](../AGENTS.md) owns workflow.

## Checkout and current operation

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
Dummy upgrade rewards remain untested.

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
base files and zero overlays passed. No bridge remains installed. No
profile/save/history/Cloud filesystem access occurred.

Current accepted release:
`0dd12fd10f84125eb5e8b32ea7bde6da91809358b2d85b8261d5458d2696737c`,
from the uncommitted working checkout based on `267b36b`. Its manifest binds all
338 exact source/test inputs, not claimed to exist at that base commit.
All **71 release groups passed in 212.643 seconds**, with 10,358 native
assertions, 1,233 shared checks, 485 C#/Python integration cases (423 native),
69 client tests, 128 event-host tests and reproducible packaging. Independent
semantic review found no remaining blocker. Trial’s owned abandonment confirmation
is included: default Cancel verifies return to the same event choices; explicit
confirmation verifies the native task and terminal run outcome. Neither branch
has live validation. This new package has not been installed.

Lantern Key and Punch Off’s live results above belong to the preceding release
`6cc54f193c98028f1bfe94d8f65558fc3d513ef2793125b692969c1c83c68319`.
The [current release record](../bridge/Sts2AgentBridge/releases/current/README.md)
retains the exact new manifest and validation, with original live identities.

Attempt details and original identities remain in the
[multi-case evidence](evidence/MULTICASE_BRIDGE_LIVE_2026_09_12.md). Prior September
9–10 coverage is in the [combined live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md);
Sphere attempts remain in its [live record](evidence/CRYSTAL_SPHERE_LIVE_2026_09_12.md).

## Current capability and evidence

Live evidence below is representative, not all-branch coverage or an autonomous
full-run result. Automatic parent effects generally remain unverified even when
the selected child effect and map return are verified.

| Capability | Evidence and practical limit |
| --- | --- |
| Combat → rewards → map | Both gold/card choose and Skip policies passed live; bounded combat/choice/reward counts and map checks; no complete autonomous run |
| Combat discard/exhaust choices | Neow's Fury zero and two-card choices plus resumed victories passed; other fixed/exhaust callers remain fixture-only |
| Rest and shop | Heal/Proceed, Smith upgrade-one and bounded purchase/close/map demonstrated |
| Generic options and repeated pages | Shared parent/children; Abyssal Baths two Lingers and exit passed |
| Changes around selectors | Grave/Confront append-before-selection and Amalgamator two removals plus one separate grant passed; broader compositions remain open |
| Upgrades | Single off-screen upgrade at slot 20 in a 23-card domain passed; fixed counts 1–8 have fixtures, multi-upgrade live remains open |
| Enchantment | Sapphire Seed/Sown and Grave/SoulsPower single selection, Prickly Sponge fixed-two Steady passed; other counts/callers remain narrower |
| Transformation | Allocated off-screen input, Wood Carvings/Bird and Claws zero/three/six passed; Torus remains a branch candidate |
| Add-card grids | Cheese add-two and Sea Glass zero/three/fifteen passed |
| Ordinary card rewards | Brain Leech singleton and Colorful Philosophers three menus with choose/Skip/choose and final dismissal passed |
| Potion/relic rewards | Singleton collection and Potion Courier three-potion set passed; full inventories require free slots or a preceding known Potion Belt (offline); nested pickup interactions remain unsupported |
| Mixed card/item sets | Lost Coffer potion→card choose and Skip/final-dismissal passed; native/host fixtures cover 2–8 entries and other orders |
| Ancient options and dialogue | Console-selected ancient options and map return passed; dialogue before/after pickup has fixtures, natural entry/dialogue and normal Darv pool eligibility retain narrower evidence |
| Optional card offers | Lead Paperweight choose/Skip without extra cards passed; Hefty Tablet choose/Skip plus Injury passed on preceding release `c73fde6c` |
| Required card offers | `card_offer_v1` has fixtures; no required-choice caller identified in the bounded retained inspection (Lead Paperweight/Massive Scroll allow Skip and use v2) |
| Bundles | Scroll Boxes three-card bundle, native preview/Confirm and map return passed |
| Inactive combat layout | Punch Off/Nab and Meal Ticket collection passed; its Fight branch separately passed through combat, potion/relic rewards and map |
| Non-resuming event combat | Dense Vegetation Fight after Rest passed live through victory, gold/card/potion rewards and map; exact combat transfer and full reconciliation demonstrated for this caller |
| Event combat resumption | Setting2 training expiry and Setting1 victory both passed through verified resumption, Proceed and map in one live process; enabled-travel, roster-cleanup and inner-layout corrections included |
| Resume-time item rewards | Setting1 Attack Potion collection passed live with exact item reconciliation and resumed Proceed/map; relics and 2–8 ordered entries remain fixture-tested; nested selectors unsupported |
| Extra special-card event combat reward | Lantern Key Fight → victory → exact LANTERN_KEY special-card collection, ordinary card/gold rewards and map passed live after prepared-combat correction; other callers remain narrower |
| Extra potion/relic combat rewards | Punch Off Fight → victory → exact Shackling Potion and Bag of Preparation collection, ordinary card/gold rewards and map passed live; broader 1–8 entry combinations and full-inventory policies retain offline coverage; complex pickup effects stop |
| Terminal potion policy | Implemented offline: `skip-full` leaves potions that do not fit; `skip-all` leaves all potions, while gold/card/relic collection continues; skipped results require verified native exit and unchanged inventory; custom event/resume screens retain capacity checks |
| Terminal potion replacement | Implemented offline: `replace-first` removes one eligible original inventory potion through the single-player native queue, verifies exact removal, then collects; new pickups are protected and each discard is accounted separately; ready schema 4 publishes potion slots |
| Terminal Potion Belt pickup | Implemented offline: exact native +2 empty-slot gain, retained original/collected potions, schema 5 capacity hint and verified gain accounting; controller uses available capacity pickup before stopping or replacement; capped at eight slots |
| Event/resume Potion Belt pickup | Implemented offline: singleton, ordered item sets, mixed card/item sets and owned resume items admit exact +2 empty-slot gains; original order, eight-slot limit and settled ownership/inventory retained; no event item skip/discard policy |
| Fake Merchant custom screen | Live open → two relic purchases → close → map passed, with five reconciled actions and an independent actionable-map check; zero/six purchase variants retain offline coverage; combat branch remains separate |
| Crystal Sphere custom screen | Uncover Future and Payment Plan reveal/reward/native exit and exact overlay cleanup passed live; independent actionable-map checks passed. Other reward/tool variants retain offline coverage. Supports: small/big tool selection, legal reveals on the 11×11 fog grid, earned gold/card/potion/relic rewards, card Skip and native map exit; hidden items are never projected |
| Trial abandonment popup | Implemented offline: exact native Double Down callback → owned modal; Cancel verifies unchanged event return, explicit confirmation verifies the native task, abandoned state and HP zero. Cancel is the default; live coverage remains open |
| Initial event-option policy | `--event-option` chooses an exact legal first option and stops if absent/illegal; subsequent actions use first-legal policy |
| Results acknowledgment | Pandora's Box nine-card screen Confirm/map passed; preceding automatic transformations are not certified |
| Reduced headless/actor stack | Structural backend and cloning pipeline accepted; no target-game fidelity or learned live-policy claim |
| Headless game engine | [Independent gameplay package](HEADLESS_ENGINE.md): content-owned card rules and upgrades, combat execution, owned run state, map/reward/room primitives and JSON continuation. Legacy experiment APIs consume the same combat rules. Native full-run fidelity remains open; [remaining tasks](HEADLESS_FULL_GAME_IMPLEMENTATION.md). |

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
Trial abandonment confirmation is implemented offline; cancellation and explicit
termination still need live validation. Next implementation candidates are a
concrete shop pickup selector or resume-time card reward. Ordinary random relic
reward pools do not contain the identified pickup selector relics. Further work includes
custom-event full-inventory policy beyond known capacity grants, nested pickups,
broader deck changes around selectors, special rewards and The Architect’s terminal progression. See the [research map](EVENT_INTERACTION_MAP.md)
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
