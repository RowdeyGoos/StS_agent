# Event caller evidence index

Reviewed 2026-09-19; latest live evidence is September 13. Use
[bridge status](STATUS.md) for current support and gaps, and
[generic event contracts](GENERIC_EVENTS.md) for exact semantics. This page maps
**named tested paths to their evidence**. It is not an event allowlist or a second
family support matrix. No row establishes every branch of an event.

## September 12–13 cases

The [multi-case ledger](evidence/MULTICASE_BRIDGE_LIVE_2026_09_12.md) retains failed
attempts, corrected releases, setup assistance and cleanup. The path/result below
summarizes the final recorded case; it does not repin earlier tests to the latest DLL.

| Caller/path | Recorded result | Qualification |
| --- | --- | --- |
| Dense Vegetation: Rest → Fight | Victory, ordinary rewards and actionable map passed | Representative non-resuming combat |
| Battleworn Dummy: Setting2 expiry | Training expiry, exact callback, resumed Proceed/map passed | Expiry is `event_resumed`, not victory |
| Battleworn Dummy: Setting1 victory | Potion collect, full-belt skip and replacement passed through resumed Proceed/map | Consecutive matching combats also passed; no resume relic/set proof |
| Battleworn Dummy: Setting2 victory | Two of four Bludgeons visibly upgraded, resumed Proceed/map and next room passed | Automatic upgrades; parent effects unverified, **not a selector test** |
| Lantern Key: Keep the Key → Fight | Victory, exact special-card collection and map passed | Prepared-combat correction precedes accepted result |
| Punch Off: Take Them → Fight | Potion/relic extras, ordinary rewards and map passed | Terminal potion policy tests include skip-all with verified free capacity and distinct same-key replacement |
| Potion Courier: Grab Potions | Full-belt native skip and three original-potion replacements passed | New pickups protected; representative three-potion set |
| Neow/Lost Coffer | Full-belt card acquisition with potion skip or replacement passed | Uses actual advertised reward order |
| Fake Merchant: inventory | Open, two purchases, close/Leave and map passed | Zero/six purchase variants not demonstrated |
| Fake Merchant: initial Foul Potion | Combat, seven relics, Waffle healing33→41/max80, Proceed/map/next room passed | Native setup removed ordinary rewards first; original ten-entry screen not covered. Waffle was sixth, Strike Dummy last |
| Crystal Sphere: Payment Plan | Reveal/reward/exit and independent map check passed | Does not establish every reward/tool variant |
| Trial: Reject → Double Down | Cancel and Confirm both passed | Cancel continued to rewards/map/next room; Confirm produced `run_abandoned` and native Defeat/HP0 |
| The Architect: final Proceed | **Initial read failed `unsupported_state`; zero actions** | Native final-act setup succeeded; exact rejection predicate and terminal win remain unresolved |

The separate [Crystal Sphere ledger](evidence/CRYSTAL_SPHERE_LIVE_2026_09_12.md)
records Uncover Future/gold/map acceptance and exact completed-overlay cleanup.
Ordinary shop tests are also in the multi-case ledger; they are room flows, not
Fake Merchant event coverage.

## September 9–10 cases

The [combined ledger](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md) binds each result
to its original release. These remain representative evidence for the named path.

| Caller/path | Recorded result | Qualification |
| --- | --- | --- |
| Abyssal Baths | Two Lingers, Exit/Proceed and fresh map | Reused keys with fresh native controls |
| Grave of the Forgotten: Confront | Curse appended before SoulsPower selection, Proceed/map | Automatic grant provenance unverified |
| Amalgamator: CombineStrikes | Exact two-card removal plus observed merged grant, map | One appended grant; no arbitrary multi-grant proof |
| Sapphire Seed | Single upgrade including slot20/23; Sown selection, map | Allocated off-screen holder, not unallocated input |
| Waterlogged Scriptorium: Prickly Sponge | Fixed-two Steady, exact preview/effects, map | Other counts/enchantments need separate evidence |
| Potion Courier: Grab Potions | Three exact Foul Potion collections, map | Earlier singleton Ransack evidence also exists |
| Brain Leech: Rip | One ordinary card reward chosen, map | Singleton Skip/dismiss remains offline evidence |
| Colorful Philosophers: Necrobinder | Three menus choose/Skip/choose, final dismissal, map | Not every set size or outcome |
| Wood Carvings: Bird | Original-card preview, journal-verified transform, map | Peck separately confirmed by user; Torus untested live |
| Neow/Lost Coffer | Potion→card choose and Skip/dismiss paths, map | Construction order is not authoritative screen order |
| Orobas/Sea Glass | Zero, three and fifteen selected additions, map | One optional 15-card grid, not sequential children |
| Tanx/Claws | Zero, three and six transforms, preview/Confirm, map | Zero is confirmation, not cancellation |
| Neow/Lead Paperweight | Choose and Skip with no extra grant, map | Optional v2, not required v1 |
| Neow/Hefty Tablet | Choose plus Injury; Skip plus Injury; map | Original preceding release retained in ledger; grant provenance unverified |
| Neow/Scroll Boxes | Three-card bundle, preview/Confirm, map | Other bundles/preview cancellation not established |
| Punch Off: Nab | Meal Ticket collection and map | Automatic Injury unverified; Fight evidence is separate above |
| Darv/Pandora’s Box | Nine-result acknowledgment and map | Prior transformations and natural pool eligibility unverified |

Ancient cases used controlled console entry. They do not establish natural initial
dialogue or normal pool eligibility. Neow’s Fury zero/two-card combat choices are
in the same ledger and described in [combat choices](COMBAT_CHOICES.md).

## Earlier results and source candidates

[Unified smoke](evidence/UNIFIED_BRIDGE_SMOKE_2026_09_08.md) covers earlier core,
rest/shop, singleton potion and Aroma/Let Go paths. Its final generic `effects`
summary remained `unverified`; its legacy public-screen read was not a map probe.
The [V10 acceptance](archive/phase-1/research/PHASE_1_GENERIC_EVENT_RELEASE_V10_ACCEPTANCE.md)
is the original allocated off-screen transform result. Earlier
[Cheese add-two](archive/phase-1/research/PHASE_1_GENERIC_EVENT_RELEASE_V5_ACCEPTANCE.md)
and [Potion Courier singleton](archive/phase-1/research/PHASE_1_GENERIC_EVENT_V6_POTION_COURIER_LIVE.md)
records retain their exact original scope.

For untested caller candidates—including Endless Conveyor, Morphic Grove,
Symbiote, Whispering Hollow and Trial’s conditional selector branches—use the
[static research map](EVENT_INTERACTION_MAP.md). Its 68 types/105 branch groups
are a source census, not a count of supported events, reachable events or remaining
features. Keep future attempt chronology in the dated evidence ledger.
