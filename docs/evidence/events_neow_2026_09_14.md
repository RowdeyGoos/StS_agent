# Remaining Act 1 events and Neow — 2026-09-14

Implemented on `codex/headless-events-neow-complete`, based on headless integration
`fcf2bea`, for merge into `codex/headless-integration`. Main and the production
bridge are unchanged. This is source-checked synthetic/installed headless evidence,
not a live demonstration or a native full-run fidelity claim.

## Scope and source

Pinned game 0.107.1, Steam build 23811903; `sts2.dll` SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Direct method-body inspection used the existing local scanner and pinned assembly;
older decompiled C# served only as navigation. No player profile/save/history was read.
The [scope inventory](../../tests/fixtures/headless_act1_event_scope.json) records
13 Overgrowth events, eight normally Act-1-eligible shared events, later-act/disabled
exclusions, Neow availability and curse pool counts.

Native anchors include Overgrowth.get_AllEvents (100694203),
ModelDb.get_AllSharedEvents (100682568), the selected event GenerateInitialOptions,
IsAllowed and asynchronous option methods, Neow's option construction/eligibility,
and CardFactory.GetDefaultTransformationOptions (100695705) /
GetFilteredTransformationOptions (100695708). CombatManager end-turn ordering and
native card/enchantment methods were inspected independently where hooks interact.
Folly's pinned keyword array `(4,7,3,2)` includes Ethereal, unlike older source text.

Ten events added: Luminous Choir, Unrest Site, Wood Carvings, Brain Leech,
Room Full of Cheese, Self Help Book, Tea Master, The Future of Potions,
The Legends Were True and This or That. This completes the normally eligible
solo Act 1 event census (21 definitions), under the existing all-unlocked profile.
The new events expose 22 normal selectable branches plus empty-eligibility handling.

`neow_solo_all_unlocked_v2` adds seeded two-positive/one-curse offers, paired
exclusions, Large Capsule conflict handling, catalog eligibility and nested pickup
continuation. The default catalog supports 26 of 27 native solo Neow relics;
Kaleidoscope remains excluded until foreign character card pools exist. Massive
Scroll is multiplayer-only. The older two-offer fixture and post-Ancient start
remain available explicitly.

## Behavior and architecture

Small content-owned branch operations reuse existing acquisition, damage, card
selection and relic work. Pending state contains values, owned IDs, a cursor,
receipts and validated resource checkpoints, with no resolver callbacks.
Checkpoints detect inconsistent continuation/state edits; they are not signatures
or authentication against coordinated edits. Event resource changes, nested relic
work, potion trades and failed selections remain transactionally restorable.

Supporting content: Peck, Toric Toughness, Spoils Map, Spore Mind, Poor Sleep,
Slither and the complete 18-card curse pool. Neow's Bones separately uses the ten
modifier-eligible curses, rolling after its relic choices finish. Eternal cards
cannot be transformed/removed, while transformations can produce Eternal curses.

Verified edge cases include captured Choir price/Unrest heal, multiple card grids,
Future's frozen potion inventory and upgraded rewards, duplicate event relics,
lethal effects/Fairy revival, and random Orrery pickup before an event's next effect.
Unconditional gold/relic effects still execute after lethal event damage; new card
acquisition/choices do not. Toric reapplies captured unpowered block even under
Barricade. Slither runs after Hellraiser early autoplay. Regret captures hand size
after Stampede; ethereal exhaustion precedes curse hand effects. Remaining curse
work survives reactive draws and rejects omitted tasks on restore.

Private schemas advance to combat v12 and run v22; generated event progression is
`supported_events_all_unlocked_v7`. Older private snapshots reject explicitly.

## Validation

- New focused suite: **116 passed in 21.09 seconds**, before the final Folly
  keyword correction; that correction is included in the affected rerun below.
- Final headless/simulation/content integration: **1,798 passed in 280.47 seconds**.
  The small late Folly and Eternal entry-count corrections were covered by the
  subsequent affected event/curse regression run: **230 passed in 52.83 seconds**.
- Pinned inventory membership check: **1 passed in 0.11 seconds** after adding the
  independent scope fixture. `compileall game tests` and `git diff --check` pass.
- Independent semantic review covered source branches, Neow offer exclusions,
  resource/continuation binding and supporting card timing. All concrete findings
  were corrected. Its bounded correction rerun passed **45 tests in 8.07 seconds**;
  the final Folly flag was subsequently corrected and verified in the affected run.
- Broad repository run: **3,019 passed, 17 failed, 63 errors in 396.67 seconds**.
  Seven failures were outdated headless catalog/index assertions, corrected and
  covered by the passing final runs. Eight unchanged bridge fake-socket fixtures
  lack `shutdown`; the frozen differential evidence has one identity failure and
  63 setup errors. Historical evidence was not repinned. The remaining sandbox
  loopback-binding failure passed outside the sandbox (**1 test, 0.01 seconds**).
  The whole repository is therefore not reported as green.

Built and installed the wheel into a disposable environment, with imports verified
from `site-packages` while running outside the checkout with `PYTHONPATH` unset.
All **22 new event branches and 26 supported Neow pickups** completed with exact
JSON restore and legal-action equality at each decision, including nested choices.
Installed first-slice seed 2 completed two combats in 38 commands with 66 HP and
restore verification. Generated seed 2/right/rest selected Lost Coffer and ended
in defeat after six rooms, five combats and 103 commands; restore verified throughout.
That run establishes execution, not a victory or native fidelity.

Wheel: `sts_agent-0.1.0-py3-none-any.whl`, SHA-256
`a38d9bd50a23a076776a5cdd0c501c8982bbc27d3b46b899e517b67f9af5a356`.
Local build/inspection outputs are under `/private/tmp/sts-headless-events-neow`.

## Remaining limits and next work

Spoils Map is an Act 1 quest card; its Act 2 map target and 600-gold quest await
Act 2 implementation. Later-act-only and disabled events remain excluded. The
all-unlocked event queue and current catalog availability are explicit simulator
assumptions. Native card reward odds, pool ordering, unlock epochs and RNG parity
remain separate work; seeded headless reproducibility does not prove native parity.
Default Kaleidoscope eligibility awaits foreign-character cards and their rules.
The [implementation guide](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment)
now assigns generation fidelity, Kaleidoscope and end-to-end Act 1 acceptance next.

Work began at 16:51 UTC. Implementation, source inspection and review overlapped;
these phases were not separately timed. Validation times are recorded above.
Installed packaging and final documentation finished around 17:28 UTC. No user
readiness wait or live release/install step was required.

## Native event and inventory conformance — 2026-09-20

The [retained capture](native_event_inventory_2026_09_20.json) adds 144 actual
native choices: four events × three branches × seeds 0/2/42 × A0/A10 × two
inventories. Self-Help Book selects Attack/Skill/Power for Sharp/Nimble/Swift;
Wood Carvings selects a Basic for Peck/Toric Toughness or a Slither-eligible card;
Tea Master buys each tea, including an existing identical tea; The Future of
Potions trades each of common/uncommon/rare potions and claims the first reward.

Authored setup is HP31/maxHP80/gold250, native starter deck plus Inflame and two
upgraded basics. Enhanced setup adds Molten/Toxic/Frozen Egg, Wing Charm and a
Slither-enchanted Strike. A10 potion cases obtain Potion Belt to fit three bottles.
Selection indices identify physical cards; singleton grids use native auto-selection.
The fixture checks legality and selection consumption, uses actual event/reward
commands and in-memory run history, and cleans up each mock-persistence run.
The final native capture built in 1.557s and executed in 1.851s with empty stderr
and successful removal of its isolated user directory. No player files were read.

Python compares ordered deck values/enchantments, HP/maxHP/gold, duplicate relics,
potion slots and release of potion restrictions, every generated reward offer,
and event/Rewards/Niche/Transformations counters plus next-value suffixes. Every
choice is replayed from JSON, including the intermediate card/reward selection.

This exposed two engine discrepancies. Native `CardCmd.Transform` removes a
permanent-deck source and appends its replacement; only combat-pile transforms
reuse their old position. Shared random/explicit deck replacement and the Morphic,
Whispering Hollow, partial-selection and Hatch validators now follow that order.
Bing Bong copies remain adjacent to each replacement. The event reward type filter
also needs to treat the internal `block` category as native Skill: excluding Shrug
It Off had changed The Future of Potions' seed42 common-skill offers.
Run schema v62 rejects earlier transformation continuation semantics; combat v42
is unchanged. Focused regressions include partial two-card transformation restores,
physical duplicates, egg upgrades, Bing Bong copies, Hatch ordering, invalid deck
reordering and old-schema rejection. An independent semantic review checked native
transformation behavior, the four affected validators and fixture isolation.

[Ten freshly executed native baselines](native_event_campaign_regressions_2026_09_20.json)
match their original A0/A10 results exactly and bind the extended harness to those
unchanged captures. Their older evidence identities are preserved. None of these
retained campaign paths contains the newly corrected event/transform callers;
new focused event replays exercise those behaviors directly.

This capture proves the specified inventories and first-eligible/first-reward
choices, not every eligible target, tea combat activation, every event branch,
all relic combinations or live UI behavior. Continue conformance with additional
ordinary-event branches and inventory interactions under the declared solo scope.

Final validation: **1,378 passed in 162.66s**, covering the new 144 native cases,
transformation/restore consumers, all-solo event branches, relic/Ancient acquisition,
foreign cards and native reward handoffs. Compileall, diff checks and changed-document
relative links passed. The ten native baseline runs took 15.905s total compilation
and 25.059s execution. Independent focused checks took 0.43s; total implementation
and review wall times were not measured. No release packaging or user wait was needed.
