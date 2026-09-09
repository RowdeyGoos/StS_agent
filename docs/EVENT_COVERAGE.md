# Event coverage

Updated 2026-09-09. This page records family and caller evidence. It is not a
production event allowlist: supported shared interactions are discovered at runtime.
[Generic events](GENERIC_EVENTS.md) explains the architecture; [status](STATUS.md)
owns the latest operational result and [roadmap](../ROADMAP.md) owns priorities.
The [all-event research map](EVENT_INTERACTION_MAP.md) classifies native interaction
requirements across all 68 pinned event types; static findings are not live acceptance.

## Interaction families

| Family | Implemented behavior and evidence | Remaining limits |
| --- | --- | --- |
| Ordinary option pages and Proceed | Generic native control; Dense Vegetation continuation live | Longer chains and other branches need evidence |
| Item rewards | Singleton potion/relic children and Potion Courier/Ransack live; `item_set_v1` now has native/C#/Python fixtures for 2–8 potion/relic entries, exact ordered collection and retained prior effects; Potion Courier/Grab Potions three-Foul-Potion set and fresh map passed live | Other counts, relic-containing sets, full-inventory handling, nested pickups and broader relic/caller evidence |
| Add cards | Positive variable counts up to eight in fixtures; Cheese/Gorge two-of-eight live | Other callers/domains/counts are not all live-proven |
| Upgrade cards | Fixed counts 1–8, exact preview mapping and allocated off-screen holder selection in native-to-Python fixtures; Smith and Sapphire Seed single upgrades live, including Sapphire Seed off-screen slot 20 of 23 | Multi-upgrade live evidence, variable counts and unallocated holders |
| Enchant cards | Single-card v1 has Sapphire Seed/Sown and Grave/SoulsPower live evidence; fixed multi-card v2 (2–8) has native/C#/Python fixtures; Prickly Sponge fixed-two Steady, exact original preview/effects and fresh core map passed live | Other counts and callers remain open; candidates must be unenchanted; stacking/replacement and optional counts unsupported |
| Remove cards | Generic `card_remove_v2`: positive counts up to eight, exact removal preview/effect and optional single appended parent grant with separate unverified metadata; strict standalone v1 remains unchanged; Amalgamator/CombineStrikes fixed-two removal, upgraded Ultimate Strike observation and fresh core map passed live | Other removal callers/counts, optional selection and unallocated holders |
| Transform cards | Fixed counts and positive variable counts up to eight in G7 fixtures; Aroma/Let Go fixed-one live | Variable-count live evidence and unallocated holders; optional v3 is described below |
| Optional/zero selection | Unreleased `card_add_v2` (0..15, explicit confirm) and `card_transform_v3` (0..8, preview/confirm), exact zero task/deck/command checks, native/C#/Python fixtures; source callers SeaGlass and Claws | Full native caller live acceptance pending; empty candidate domains and true cancellation remain separate |
| Repeated option pages | Fresh native controls plus completed callbacks permit identical keys/text and revisits; AbyssalBaths passed two Lingers through Exit/Proceed and fresh core map live; fixtures also cover separate completed item children | EndlessConveyor and SlipperyBridge need caller evidence |
| Deck changes around selectors | Append-only additions before the first owned selector request form its fixed baseline; Grave/Confront passed live; native-to-host enchant/upgrade/transform shapes pass through Proceed/map; removal followed by one appended grant passed Amalgamator/CombineStrikes live in v2 | Trial and other callers need live evidence; changed survivors, multiple grants and additions after other selector operations remain unsupported; automatic addition provenance is not verified |
| Event card rewards and multiple reward entries | `card_reward_v1` covers singleton menus; `card_reward_set_v1` now has native/C#/Python fixtures for 2–8 ordinary CardReward entries with 1–5 offers each, per-menu choice/Skip and final dismissal. BrainLeech/Rip chose Equilibrium and returned to map live; ColorfulPhilosophers/Necrobinder passed three menus with choose/Skip/choose, final dismissal and fresh map. `item_set_v1` supports 2–8 potion/relic entries in fixtures and a three-potion set live; Cheese uses a different add-grid surface | Other menu counts/outcomes and singleton Skip/dismiss live acceptance, mixed-set live acceptance, repeated offers within one option, SpecialCardReward, reroll/multipick, substituted cards and nested pickup/selector ownership remain gaps |
| Mixed card/item reward sets | Unreleased `mixed_reward_set_v1` native/C#/Python implementation for 2–8 entries, card choice/Skip, exact potion/relic collection and final dismissal; retains deck/inventory/task witnesses across interleavings; LostCoffer supplies the pinned card-plus-potion shape | No live acceptance; full-inventory replacement and nested pickup selectors remain unsupported |
| Embedded event combat | Five concrete static callers; BattlewornDummy requests resumption, four callers do not | Combat handoff and event resumption are not accepted |
| Ancient layout and dialogue | Unreleased exact native layout/hitbox admission, one-line dialogue progress before and after pickup, ordinary options and map handoff; native/C#/Python fixtures | Live ancient routes and unsupported pickup families remain open |
| Custom/combat layouts and terminal flows | Static caller/surface map identifies combat layouts, CrystalSphere, FakeMerchant, Trial popup and TheArchitect | Runtime adapters/admission and terminal outcomes remain unsupported; see the research map |
| Generic deck transformations | Fixed-one native transform-prompt `FromDeckGeneric` → `NDeckCardSelectScreen` uses original preview and exact `card_transform_v2` journal; Bird/Peck and Torus/ToricToughness shapes pass native/C#/Python fixtures; WoodCarvings/Bird passed live with upgraded Strike slot 0 of 21, exact preview, verified transformation and fresh core map | Torus live acceptance, selectorless automatic cases, optional/multiple generic selection and other prompt semantics remain open |
| Choose-one offered cards | Unreleased `card_offer_v1` uses the owned native ChooseACard request/screen; 1–3 offers, one click, exact chosen card addition; native/C#/Python fixtures. LeadPaperweight and MassiveScroll supply concrete callers | No live acceptance; Skip, extra grants/copies and substitution remain unsupported |
| Card bundles | Unreleased `bundle_offer_v1`: 1–5 bundles of 1–8 cards, exact native preview/Confirm and ordered additions; native/C#/Python fixtures. ScrollBoxes supplies the concrete caller | No live acceptance; preview cancellation, extra grants and nested pickups remain unsupported |
| Other card surfaces | Static pickup callers identify card-results acknowledgment | Result screens still require a separate adapter |

All eligible allocated transform holders now use direct input in the unified
bridge. Native fixtures cover different slots, including 0, 15 and 19 in a
20-card domain, plus missing/disabled/reassigned and deferred targets. The earlier
card16-only mask was a test restriction and is removed. The controlled
[V10 result](archive/phase-1/research/PHASE_1_GENERIC_EVENT_RELEASE_V10_ACCEPTANCE.md)
establishes one allocated off-screen transform holder. The September 9
[combined batch](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md) separately establishes
an allocated off-screen single-upgrade holder. Neither proves unallocated cards
or every selector family. A further test should answer
a new behavior question rather than repeat the geometry investigation.

## Caller evidence

The [accepted census](archive/phase-1/research/PHASE_1_EVENT_COVERAGE_CENSUS_GENERIC_RESULT.md)
contains 68 concrete types, including ancient/deprecated types. That count does
not establish the reachable pool or runtime eligibility. The rows below retain
positive caller evidence from earlier inspection, fixtures or live tests. The new
research map supplies broader static classification; unlisted or untested paths
have no additional runtime acceptance. No event has complete all-branch evidence.

| Event | Observed path | Evidence limit |
| --- | --- | --- |
| `DenseVegetation` | Ordinary choice → follow-up → Proceed/map | One bounded live path |
| `RoomFullOfCheese` | Gorge adds exactly two of eight; Search returns to map with zero item children | Bounded live paths; other branches unclassified |
| `PotionCourier` | Ransack collects one potion; Grab Potions collects three Foul Potions; both complete Proceed/map | Representative bounded live paths; full-inventory behavior remains unsupported |
| `AromaOfChaos` | MaintainControl upgrade-one fixtures; LetGo fixed-one transformation live, including direct card16 in V10 | Other targets/counts and MaintainControl live remain open; unified smoke has the final-summary limit below |
| `SapphireSeed` | Consume/Eat single upgrade, including off-screen Defend slot 20 of 23; Plant and Nourish/Sown on Defend slot 5 of 24; both passed Proceed and independently checked core map live | Other domains/counts and enchantments/callers unverified |
| `EndlessConveyor` | JellyLiver fixed-one transform caller statically audited | No native caller/live acceptance; selected body did not establish finish |
| `MorphicGrove` | Group fixed-two transform caller statically audited; loses current gold first | No native caller/live acceptance |
| `Symbiote` | KillWithFire equal-count transform request statically audited | Dynamic count unproved; no native caller/live acceptance |
| `Trial` | NondescriptInnocent fixed-two transform caller statically audited; adds curse first | No native caller/live acceptance |
| `WhisperingHollow` | Hug fixed-one transform caller statically audited; dynamic HP loss afterward | No native caller/live acceptance |

The latest [unified module smoke](evidence/UNIFIED_BRIDGE_SMOKE_2026_09_08.md)
includes singleton potion collection and Aroma/Let Go with one completed card
child. Generic orchestration resolved, but its final `effects` summary remained
`unverified`; legacy public-screen observation after the controlled event setup
was unsupported/unknown. Preserve those distinctions when reporting completion.

## Detailed evidence

Use the [archive index](archive/README.md) for historical contracts and the
[G7 acceptance](archive/phase-1/research/PHASE_1_GENERIC_EVENT_V7_ACCEPTANCE.md),
[Cheese live result](archive/phase-1/research/PHASE_1_GENERIC_EVENT_RELEASE_V5_ACCEPTANCE.md)
and [potion live result](archive/phase-1/research/PHASE_1_GENERIC_EVENT_V6_POTION_COURIER_LIVE.md)
for exact artifact-level results. Superseded checkpoint chronology is in Git at
`176882fe2016832d7dbafd355f76c42bb89cf1ae`; do not append it back to this matrix.
