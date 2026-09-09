# Current integration status

Updated 2026-09-09. This is the single current capability/evidence and operational
handoff page. [AGENTS.md](../AGENTS.md) owns workflow; [roadmap](../ROADMAP.md) owns
priorities. Historical acceptance ledgers retain exact artifact identities.

## Checkout and current operation

Main includes the integrated generic-handler work. Use the user's current checkout
and inspect Git state; do not switch to the historical 23cf worktree.

The five-feature generic-event batch has representative live acceptance:
WoodCarvings/Bird transformation; Prickly Sponge fixed-two Steady enchantment;
Potion Courier's three Foul Potions; Brain Leech's singleton card reward; and
Colorful Philosophers' three menus with choose/Skip/choose and final dismissal.
Each successful case independently verified a fresh core map. Colorful Philosophers
added Fear+ and Necro Mastery, skipped the middle menu and reconciled all nine
actions. These cases do not establish all counts, branches or full-inventory /
nested pickup handling.

The checkout now implements **mixed card/item reward sets** (`mixed_reward_set_v1`)
with ordered card choice/Skip and potion/relic collection, typed settlements and
one final dismissal when needed. This is an unreleased, offline-tested increment.
Lost Coffer supplies the pinned card-plus-potion caller; ancient entry now has
unreleased offline support, while its full live route remains unverified. See the
[mixed-set contract](GENERIC_EVENTS.md#implemented-offline-mixed-carditem-reward-sets).
Its focused event gate passed **15 groups in 238.607 seconds**, including **6,417
native assertions**, **125 host tests** and **341 C#/Python cases** (279 through
actual native adapters). Shared bridge validation passed **689 checks**; the
production build passed in **1.772 seconds**. Independent semantic review found
no blockers; item reentry and cleanup interference regressions also passed.
A final fixture refinement uses three-card mixed menus, matching Lost Coffer;
the affected **953 native reward-set checks** and **69 native/host cases** passed
again after that test-only change. Production sources were unchanged.
Evidence outputs: `/private/tmp/sts-bridge-ajht2u5w` (event gate),
`/private/tmp/sts-mixed-boundary` (shared checks) and
`/private/tmp/sts-bridge-x6aizyt2` (production build). No live installation started.

The checkout also implements three unreleased capabilities in one batch:
**ancient dialogue/options**, **optional add-card grids** (`card_add_v2`, up to
15 selections), and **optional deck transformation** (`card_transform_v3`, up to
eight). Sea Glass's native grid is 0..15; Claws is 0..6. Zero still requires native
confirmation, exact empty task results, unchanged deck and, for transformation,
one successful empty command. Ancient dialogue works before and after pickup.
See the [contract and limits](GENERIC_EVENTS.md#implemented-offline-ancient-dialogue-and-optional-selections).
No live launch or installation was performed; the retained release below remains
unchanged. The next live batch can cover ancient entry, Sea Glass zero/partial/full,
Claws zero/partial/full, and the earlier mixed reward-set increment.

Validation: the event gate's **14 completed groups** passed, including **6,784
native assertions** and **125 host tests**; its final cross-language group required
a test-helper version correction. Its rerun passed **360 C#/Python cases**,
including **298 through native adapters**. The additional post-pickup regression passed
in **379 focused optional-event checks**. The existing card component passed
**20 groups in 12.922 seconds**. Shared bridge validation passed **703 checks**
and the production build passed in **1.597 seconds**. Independent semantic review
found no production blockers. Evidence: `/private/tmp/sts-bridge-4u2id5yc`
(completed event groups), `/private/tmp/sts-optional-dev` (final focused regression),
`/private/tmp/sts-bridge-w3xbn9ld` (cards), `/private/tmp/sts-optional-boundary`
(shared bridge), `/private/tmp/sts-bridge-4mw3qegw` (production), and
`/private/tmp/sts-optional-host-final.log` (final integration).

Two more capabilities are implemented offline: **choose-one offered cards**
(`card_offer_v1`, native 1–3 choices) and **card bundles** (`bundle_offer_v1`,
1–5 bundles of 1–8 cards, native preview/Confirm). LeadPaperweight/MassiveScroll
and ScrollBoxes are the representative Neow callers. Both retain exact model,
control, task and deck ownership through event/map return. See the
[contract and limits](GENERIC_EVENTS.md#implemented-offline-choose-one-cards-and-bundles).
Add these to the next live batch alongside ancient entry, Sea Glass, Claws and
mixed reward sets. This v1 increment excludes HeftyTablet's additional grant and
Skip (now covered by v2 below), cancellation and nested pickup composition. No live
install or launch ran.

Validation: all **15 individual event check groups** passed in **291.307 seconds**,
including **7,435 native assertions**, **125 host tests**, and **404 C#/Python cases**
(**342 through native adapters**). The checker's closing source-consistency check
rejected the run because final hardening edits landed during its snapshot run;
this is not recorded as a passed final gate. Unchanged results were reused, with
final affected checks passing **680 native offer assertions**, **44 native/host
cases**, and **736 shared bridge checks**. Final production build and source
closure checks passed (build **1.687 seconds**, 308 files / 46 projects).
Independent semantic review found no remaining blockers. Evidence outputs:
`/private/tmp/sts-bridge-wxszur_s` (completed snapshot groups),
`/private/tmp/sts-offers-final` (final native and host fixtures),
`/private/tmp/sts-offers-boundary` (shared checks), and
`/private/tmp/sts-bridge-elkbf7uv` (final build). The retained release is unchanged.

A further offline batch adds **inactive combat-layout options** and **automatic
card-results acknowledgment** (`card_results_v1`). PunchOff/Nab-shaped Injury plus
relic pickup now composes through Proceed/map; active combat and changed embedded
room identities stop the handler. Darv/PandorasBox supplies the inspected results
screen: one native Confirm closes the owned capstone with unchanged post-show
deck and successful Chosen completion. Acknowledgment leaves automatic card
effects **unverified**. Darv pool eligibility, embedded combat execution/resumption,
nested pickups and alternate results screens remain open. See the
[contract and limits](GENERIC_EVENTS.md#implemented-offline-inactive-combat-layouts-and-result-acknowledgment).
Neither feature has live acceptance; no live launch/install was performed.

Final validation passed **15 event groups in 306.026 seconds**: **7,650 native
assertions**, **125 host tests** and **430 C#/Python cases** (**368 through native
adapters**). Native execution took 78.563 seconds; cross-language integration took
211.928 seconds. Shared bridge validation passed **781 checks**, and the production
build passed in **1.547 seconds**. Final source closure covers 313 files / 46
projects. Independent semantic review found no remaining blockers. Evidence:
`/private/tmp/sts-bridge-3xonexx4` (final event gate),
`/private/tmp/sts-surfaces-boundary` (shared checks), and
`/private/tmp/sts-bridge-8q85ewwe` (production build). The retained release below
remains unchanged.

The latest offline batch adds **optional card offers** and **one appended grant**
under `card_offer_v2`. HeftyTablet's concrete branches are choose → selected card
plus Injury, and Skip → Injury. The native Skip control, exact task outcomes,
unchanged baseline and bounded appended-card identities are checked through
Proceed/map. Resolved payloads expose the extra card separately; grant provenance
and parent effects remain **unverified**. Required offers and bundles keep their
v1 behavior. See the [contract and limits](GENERIC_EVENTS.md#implemented-offline-optional-card-offers-and-one-appended-grant).
No live launch/install was performed. Add both HeftyTablet branches to the next
live batch; nested pickups and broader selector grant composition remain open.

Final validation passed **15 event groups in 319.959 seconds**: **7,788 native
assertions**, **125 host tests** and **450 C#/Python cases** (**388 through native
adapters**). Native execution took 80.320 seconds; cross-language integration took
224.234 seconds. Focused offer checks separately passed 818 native assertions and
64 native/host cases. Shared bridge validation passed **809 checks**. The production
build passed in **1.748 seconds**, with source closure covering 313 files / 46
projects. Independent semantic review found no blockers. Evidence:
`/private/tmp/sts-bridge-0yfivulm` (final event gate),
`/private/tmp/sts-optional-offers` (focused native/host fixtures),
`/private/tmp/sts-offer-v2-boundary` (shared checks), and
`/private/tmp/sts-bridge-izl7m9bm` (production build). The retained release is unchanged.

The current release is
`748e3172a886a499342810aec43e86fd0987ce003e7989c9f5ffb1594f52c1d3`, from source
commit `c531b4c`. It corrected the production event response classifier and reward
request grammar after the earlier Prickly Sponge attempt stopped before any card
actions. Native legality, parent ownership, terminal failures and no-retry behavior
remain enforced. Bird's pass retains its original release; the four later cases
passed on this corrected package.

The twelfth installation is **cleaned up**. Normal quit, stopped-process /
closed-port checks, exact owned quarantine/purge and all **429 unchanged base
files with zero overlays** passed. The earlier installations are also cleaned up. The
[live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#twelfth-installation-production-event-boundary-correction)
owns exact per-case results, timings, setup, release and cleanup bindings.

All **71 release groups passed in 257.219 seconds**: **6,004 native assertions**,
**125 host tests**, **311 event C#/Python cases** (249 using actual native adapters),
**664 shared bridge checks**, reproducible packaging and installation/cleanup
fixtures. Native event integration now includes the production terminal classifier
and independent ownership checks; shared parser cases cover reward actions and
malformed inputs. Independent semantic review found no blockers. All 303 accepted
inputs match the recorded source commit. Outputs are at
`/private/tmp/sts-bridge-ot98xkue`. No new package was needed between the four
successful cases. No profile/save/history/Cloud filesystem content was accessed.

Generic removal followed by one appended event grant has live acceptance.
The previous live-accepted release was
`fcfdd9e9deb162a5ca1f0b0756505048b48cdb83e18255520fcc788081a526dd`.
Removal now uses exact allocated native holders without computed whole-grid fit
or retained scroll/grid dimensions. Native clickability, valid exact grid and
holder/control identity, visibility, enabled state, preview and task/deck-effect
checks remain enforced. Derived native hitboxes remain supported.
All **71 combined release groups** passed in **161.665 seconds**, including
**4,687 native assertions**, **221 event integration cases**, reproducible
packaging and owned installation/cleanup fixtures. Its package is retained at
`/private/tmp/sts-unified-bridge-release-before-event-batch-20260909`; the tenth
live campaign is cleaned up.
The live Amalgamator/CombineStrikes test passed: two upgraded Strikes (slots 0
and 1 of five eligible cards) removed after exact preview, one upgraded Ultimate
Strike reported separately, then a fresh actionable core map. All five actions
reconciled. Normal quit, owned quarantine/purge and the 429-file base check passed;
that campaign no longer remains installed.

The ninth live campaign used release
`5869376503308299efe15cddec8b237848967314b0ae6f5a0cc9eb7fa55ec25d`.
It passed candidate binding but stopped at `prepare_geometry` before admitting a
child; Combine Strikes was accepted and zero card actions were sent. The user
confirmed all five Strikes were visible without scrolling. Normal quit, owned
cleanup and the 429-file base check passed. The
[live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#ninth-installation-corrected-removal-hitboxes)
retains that failure and the subsequent layout correction. Off-screen removal
has fixture coverage only; the successful case used the ordinary Amalgamator setup.

The passed **Amalgamator/CombineStrikes** case demonstrates one fixed-two removal
followed by an appended grant. The `card_remove_v2` child verifies selected removals and unchanged
ordered survivors, separately reporting the appended card as an unverified parent
effect. Strict standalone removal v1 remains unchanged.

The eighth installation used release
`f1563b68b94fa62b64d387205b1e35a002085b7cefcc1016ca15ce5821ee32b9`.
It accepted Combine Strikes but stopped at `prepare_candidates` before admitting
a child (zero card actions); the user saw five selectable Strikes. The derived
hitbox defect was subsequently reproduced offline, but the coarse diagnostic
does not establish that it caused the live stop. Normal quit, owned cleanup and
the 429-file base check passed. The
[live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#eighth-installation-removal-followed-by-one-appended-grant)
retains the failed attempt and correction at their original artifact identities.
See [generic semantics](GENERIC_EVENTS.md#implemented-removal-followed-by-one-appended-grant)
and the [release record](../bridge/Sts2AgentBridge/releases/current/validation.json).

The previous release `65c4e3d526b799f53795ab77131ba8947ad42be1db7f8261c1cacb064fe52dc9`
passed Abyssal Baths (Immerse, two Lingers, Exit/Proceed/map) and Grave/Confront
(SoulsPower on Neow's Fury, exact preview/effect and map). One earlier Grave setup
stopped before any action; its exact cause remains unresolved. All seven live
installations were cleaned up: 429 unchanged base files and zero overlays. No
previous campaign remains installed. The
[seventh-installation record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#seventh-installation-repeated-pages-and-pre-selector-additions)
retains those exact release identities and evidence; they are not live acceptance
of the new removal package.

The prior release `19142148f81ab5363aa3a131c9ff28ca8f9745af29b322a2ef2e1fb25099ccf0`
passed the single-enchantment live test: Sapphire Seed Plant and Nourish,
Sown amount 1 on unupgraded Defend slot 5 of 24, exact preview/effect verification,
Proceed and an independently checked actionable map. All four actions reconciled.
Normal quit, owned quarantine/purge and the 429-file base check passed. The
[sixth-installation record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#sixth-installation-single-card-enchantment)
retains exact artifact/state identities, counters, timings and limits.

The representative combined live batch passed on an earlier release, including
the allocated **off-screen single-upgrade** test. Those live results retain their
original artifact identity in the linked evidence; they are not live acceptance
of the current removal-plus-grant package.

Sapphire Seed admitted 23 eligible cards. The bridge directly selected the
unupgraded Defend at slot 20, below the unscrolled selector viewport, verified
its exact preview and completed upgrade, then returned to a fresh actionable
map. All four actions reconciled. No selector scrolling or manual card input
was used. The Bashes' absence from the earlier selector is now explained:
Molten Egg was visibly confirmed, and the console-added Bashes were already upgraded. Defend skills
provided the eligible targets. The deck counter also required a one-card removal
to refresh; its value alone is not an eligible-card count.

That earlier live-tested release completed Neow's Fury two-card and zero-card choices, resumed
both combats to victory, exercised both card-reward policies and verified fresh
maps without UI assistance inside those flows. Normal quit, stopped process and
closed listener, exact quarantine/purge, and 429 unchanged base files with zero
overlays passed after the final test. [The live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md)
owns exact counters, setup assistance, unsuccessful attempts, timings and cleanup
identities. These are representative paths, not all-branch or full-run evidence.

The September 8 unified module smoke is complete and its three installations are cleaned up.
Representative paths covered combat (one UI-assisted chooser), rewards, map, shop,
Smith/card selection, a singleton potion and a generic event/card child. Two real
integration bugs were corrected: safe stale combat rejections stopped the host,
and the shared client rejected valid shop action names. A console-created Smith
setup was rejected; native map entry passed with unchanged card code.
The [live record](evidence/UNIFIED_BRIDGE_SMOKE_2026_09_08.md) owns the exact
artifact/state identities, bounded results, assistance and cleanup evidence.

The earlier [V10 result](archive/phase-1/research/PHASE_1_GENERIC_EVENT_RELEASE_V10_ACCEPTANCE.md#live-result-direct-card16-selection-passed-campaign-closed)
is the specific off-screen evidence: native slot15/card16 in a controlled 20-card
Aroma of Chaos/Let Go setup, exact-original preview, transformation and map return.
Campaign and cleanup records are dated observations; verify current runtime state
before any new authorized live operation.


## Current capability and evidence

| Capability | Evidence and practical limit |
| --- | --- |
| Combat, rewards and map | Bounded live observation/control, combat completion, reward progression and fresh reward/map entry; no complete autonomous run |
| Combat → rewards → map | One shared-client command, gold/card choose-or-skip policies, separate stage/effect counts and request pacing; both policies completed live with combat victory and actionable map return |
| Combat discard/exhaust choices | Optional zero, fixed and variable counts up to eight in native/host fixtures; Neow's Fury zero and two-card choices plus combat resume live-demonstrated; exhaust/fixed-count callers remain fixture-only |
| Rest and shop | Standalone heal/Proceed, older Smith upgrade-one, one bounded shop purchase/close/map path live-demonstrated |
| Generic event parent/children | Shared native discovery and orchestration; successful bounded paths through Dense Vegetation, Cheese, Potion Courier and Aroma |
| Repeated generic event pages | Fresh controls and completed callbacks permit repeated keys/text; Abyssal Baths passed two Lingers through Exit/Proceed and fresh core map live |
| Appended cards before selectors | First owned request binds appended cards while preserving the original deck; Grave/Confront SoulsPower preview/effect and map passed live; Trial caller tests remain open |
| Card rewards | Positive variable counts up to eight in native/controller fixtures; Cheese/Gorge add-two live in release v5 |
| Removal | Generic v2 supports counts up to eight and one appended parent grant, with exact survivor checks and separate unverified grant metadata; Amalgamator/CombineStrikes fixed-two removal, upgraded Ultimate Strike observation and fresh core map passed live |
| Upgrades | Sapphire Seed single upgrade of off-screen slot 20 in a 23-card eligible domain and core map return live-demonstrated; fixed counts 1–8 have fixtures; multi-upgrade live remains open |
| Enchantment | Single-card v1 has Sapphire Seed/Sown and Grave/Confront live evidence; fixed counts 2–8 in v2 now have native and C#/Python fixtures, including original-card preview, partial effects and deferred input; Prickly Sponge fixed-two Steady and core map passed live; other counts/callers remain open |
| Transformation | Fixed and positive variable counts up to eight in G7 fixtures; fixed-one card16 live in release v10 |
| Mixed card/item reward sets | Unreleased native/C#/Python implementation for 2–8 entries, exact per-entry effects and final task/closure gating; Lost Coffer card-plus-potion shape is source-backed; no live acceptance or nested pickup support |
| Ancient layout/dialogue | Unreleased exact native hitbox/line ownership, dialogue before/after pickup, ordinary options and map handoff; offline fixtures, no live acceptance |
| Optional add/transform selection | Unreleased `card_add_v2` 0..15 and `card_transform_v3` 0..8 with confirmed zero results and exact effects; SeaGlass and Claws are source-backed live candidates |
| Potion/relic rewards | Singleton v1 has Potion Courier/Ransack live evidence; sets of 2–8 entries now have native/C#/Python fixtures with per-entry reconciliation and final owner-task gating; sufficient free potion capacity required; Potion Courier/Grab Potions three-item set and map passed live; other counts/relic sets remain fixture-only |
| Allocated off-screen transform holder | Direct selection demonstrated in the controlled v10 setup; other selector families and unallocated cards are separate questions |
| Reduced headless/actor stack | Deterministic backend, public encoder, trusted datasets, masked candidate scorer and cloning smoke accepted on structural data; no target-game parity or learned live-policy claim |

Event identities supply ownership and test coverage, not a production admission
list for each supported shared interaction. No event has complete all-branch
evidence. Choice strategy remains a replaceable host decision provider.

The current production artifact is **Sts2AgentBridgeUnified 1.0.0**. It combines
core combat/reward/map/rest, item collection, room flows, card selection and
generic events in one mod, listener and owner-frame queue. Native modules are
created lazily and remain exclusive through reconciliation and successful cleanup.
A failed/uncertain mutation or failed disposal stops the shared host. Confirmed
no-mutation stale rejections allow a fresh decision. Clean completion
allows the next capability without replacing or restarting the mod.

The canonical transformation adapter now offers all eligible allocated holders
using the successful direct-input mechanism. The card16-only restriction is gone;
identity, legality, preview, deferred-input and completion checks remain.
Direct-input fixtures exercise different slots and invalid/deferred targets.
Generic single/multi-upgrade selectors also accept allocated holders beyond the
viewport, retaining native clickability, exact preview and effect checks. This
upgrade extension has 20-card native-to-host fixtures and a live single-upgrade
result for off-screen slot 20 in a 23-card domain; other counts retain narrower
evidence.
The [current release evidence](../bridge/Sts2AgentBridge/releases/current/README.md)
records offline native/host regressions, shared socket handoff and failure cases,
actual Python clients, reproducible packaging and owned cleanup fixtures.
The unified package demonstrated the representative paths above. The successful
shop client correction is now in the maintained source. Generic orchestration
resolved with one completed card child, but its final `effects` summary remained
`unverified`; that field tracks the latest parent action, including Proceed,
while cumulative child counts retain verified completions. See the
[generic guide](GENERIC_EVENTS.md) for the precise distinction. The legacy
public-screen reader recognizes only main menu/settings, so its unsupported/unknown
result on the map did not test core map readiness. The shared client's new
`event-map` mode performs a bounded, read-only check of the existing core map
decision after event resolution and preserves event evidence if that check fails.
It has controller/codec and shared-socket fixture coverage; the Sapphire Seed live event-to-core
map check passed. The original live observations remain unchanged.

The shared client now also has `combat` and `combat-choice` modes. The new native
adapter resolves public discard/exhaust grid selectors, including the optional
Neow's Fury surface identified in pinned source. Zero confirmation, positive and
multiple selection, deselection, deferred completion, exact task results and
cleanup have offline coverage. The shared listener fixture resumes the original
combat action after child completion; failures retain separate counts. See
[combat choices](COMBAT_CHOICES.md) for scope and limits. The combined live batch
completed zero and two-card Neow's Fury choices, resumed both combats and won.
Other caller/count combinations retain their narrower offline evidence.

`combat-map` now carries one victorious combat through gold/card rewards to an
independently validated actionable map. Standalone `rewards` uses the same bounded
reward host. Uncollected unsupported rewards stop the flow; defeat never starts
reward actions. Stage summaries preserve prior combat/choice/reward evidence on
later failure. Shared-client pacing prevents a fast multi-stage flow from
exhausting the existing listener burst allowance. Actual shared-socket fixtures
and the September 9 live batch cover both first-card and native skip-card policies. The live flows independently
verified gold/card effects and an actionable map after each victory. The
composition uses the existing combat/reward/map adapters.

Only `apps/bridge/` is a production composition. The old four feature apps and
separate original production project are retired. Use one checker with focused
`--component` selection, one package identity and one client/operational entry
point. Historical sources and earlier release records remain in Git; original
identities remain in [release history](../bridge/Sts2AgentBridge/releases/history/README.md).

## Next work

The user prioritized generic event coverage before longer-run orchestration.
Single-card enchantment now has live acceptance through Sapphire Seed Plant and
Nourish. The [all-event research map](EVENT_INTERACTION_MAP.md) now accounts for
all 68 pinned types, with branch families, concrete blockers and ancient pickup
paths. Repeated-page progress is the first implemented increment from that map,
with live acceptance through Abyssal Baths. Append-only additions before selectors
passed Grave/Confront. Removal followed by one appended grant passed
Amalgamator/CombineStrikes live. Multiple potion/relic rewards, fixed multi-card
enchantment, ordinary singleton card reward menus now have representative live acceptance.
Colorful Philosophers also passed three card-reward menus with choose/Skip/choose
and final dismissal. Mixed card/item sets now have unreleased offline implementation
and validation. Ancient dialogue, optional SeaGlass add selection and optional
Claws transformation now also have unreleased offline implementation. Full-inventory
handling and nested pickup composition remain concrete gaps; the static inventory itself
adds no live acceptance.
The [roadmap](../ROADMAP.md#immediate-priorities) owns the priority order.
The [generic event guide](GENERIC_EVENTS.md) distinguishes implemented behavior
from remaining native coverage. Reuse completed evidence when choosing the next
observable behavior to test.

## Current exclusions

The [research map](EVENT_INTERACTION_MAP.md) identifies concrete gaps in
deck changes after selectors and other pre-selector deck mutations and broader pickup composition,
combat layouts, embedded combat, repeated/nested
pickup selectors, broader generic-deck transformation and custom/terminal surfaces.
Unallocated holder support remains limited. Variable upgrades, true native
cancellation and enchantment stacking/replacement remain unsupported but have no
confirmed caller in the inspected event/immediate-pickup paths. Variable
transformation has offline evidence but no variable-count live case.
Elite continuation and complete room/run composition remain broader open evidence
targets. A successful fixed-one event does not certify all selectors or deck sizes.

Profile/save/preference/history/Cloud filesystem access, retained live corpora,
unpinned builds and a near-optimal/full-run claim are outside ordinary development.
The [live guide](LIVE_DEVELOPMENT.md) owns operational and user-data boundaries.

## Relevant code and semantic references

Paths in the first column are relative to `bridge/Sts2AgentBridge/`.

| Location | Responsibility |
| --- | --- |
| `apps/bridge/client/reward_host.py`, `run_live.py` | Bounded reward resolution and combat/reward/map composition |
| `components/cards/combat/`, `components/cards/combat_native/`, `apps/bridge/client/combat_host.py` | Combat selector protocol, native binding and bounded combat/choice host |
| `components/events/native/GenericEventV7Hooks.cs`, `GenericEventV7Binding.cs` | Owned native discovery and parent/child identity |
| `components/events/native/PinnedGenericEventV7NativeAdapter.cs` | Parent capture and child integration |
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
