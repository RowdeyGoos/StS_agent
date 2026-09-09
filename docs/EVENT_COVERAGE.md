# Event coverage

Updated 2026-09-08. This page records family and caller evidence. It is not a
production event allowlist: supported shared interactions are discovered at runtime.
[Generic events](GENERIC_EVENTS.md) explains the architecture; [status](STATUS.md)
owns the latest operational result and [roadmap](../ROADMAP.md) owns priorities.

## Interaction families

| Family | Implemented behavior and evidence | Remaining limits |
| --- | --- | --- |
| Ordinary option pages and Proceed | Generic native control; Dense Vegetation continuation live | Longer chains and other branches need evidence |
| Item rewards | Singleton potion/relic children in native fixtures; Potion Courier/Ransack potion collection live | Broader relic/caller evidence and multiple-offer sets |
| Add cards | Positive variable counts up to eight in fixtures; Cheese/Gorge two-of-eight live | Other callers/domains/counts are not all live-proven |
| Upgrade cards | Fixed counts 1–8, exact preview mapping and allocated off-screen holder selection in native-to-Python fixtures; Smith and Sapphire Seed single upgrades live | Generic off-screen and multi-upgrade live evidence, variable counts and unallocated holders |
| Remove cards | Positive variable counts up to eight, preview confirmation and exact remaining-deck reconciliation in native fixtures | Live caller evidence, optional selection and unallocated holders |
| Transform cards | Fixed counts and positive variable counts up to eight in G7 fixtures; Aroma/Let Go fixed-one live | Variable-count live evidence, optional selection and unallocated holders |
| Optional/zero selection and repeated choices | Unsupported by the current generic implementation | Cancellation, bounds and loop ownership need explicit semantics |
| Embedded event combat | Metadata/shared API evidence only | Combat handoff and event resumption are not accepted |
| Custom/ancient layouts | Limited static inventory | Caller/layout connections and action semantics remain unproved |

All eligible allocated transform holders now use direct input in the unified
bridge. Native fixtures cover different slots, including 0, 15 and 19 in a
20-card domain, plus missing/disabled/reassigned and deferred targets. The earlier
card16-only mask was a test restriction and is removed. The controlled
[V10 result](archive/phase-1/research/PHASE_1_GENERIC_EVENT_RELEASE_V10_ACCEPTANCE.md)
is the specific live evidence for an allocated off-screen holder; it does not
prove unallocated cards or every selector family. A further test should answer
a new behavior question rather than repeat the geometry investigation.

## Caller evidence

The [accepted census](archive/phase-1/research/PHASE_1_EVENT_COVERAGE_CENSUS_GENERIC_RESULT.md)
contains 68 concrete types, including ancient/deprecated types. That count does
not establish the reachable pool or runtime eligibility. The rows below retain
positive caller evidence; all unlisted types and untested branches remain
unclassified. No event has complete all-branch evidence.

| Event | Observed path | Evidence limit |
| --- | --- | --- |
| `DenseVegetation` | Ordinary choice → follow-up → Proceed/map | One bounded live path |
| `RoomFullOfCheese` | Gorge adds exactly two of eight; Search returns to map with zero item children | Bounded live paths; other branches unclassified |
| `PotionCourier` | Ransack collects one potion then Proceed/map | Bounded live path; other branches unclassified |
| `AromaOfChaos` | MaintainControl upgrade-one fixtures; LetGo fixed-one transformation live, including direct card16 in V10 | Other targets/counts and MaintainControl live remain open; unified smoke has the final-summary limit below |
| `SapphireSeed` | Consume/Eat single upgrade, Proceed and independently checked core map live in the September 9 batch | Off-screen targets and Plant enchantment remain unverified/unsupported |
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
