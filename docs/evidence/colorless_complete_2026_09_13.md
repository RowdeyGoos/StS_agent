# Single-player colorless card pool — 2026-09-13

## Scope

All **53 single-player colorless cards** from pinned **0.107.1** now have base and
upgraded execution: **32 uncommon and 21 rare**, or **106 variants**. The native
pool has 64 entries. Beacon of Hope, Believe in You, Coordinate, Gang Up, Huddle Up,
Intercept, Knockdown, Lift, Mimic, Rally and Tag Team are omitted under the user's
multiplayer-only exclusion. The independent
[constructor inventory](../../tests/headless/fixtures/colorless_native_inventory.json)
records all 64 names, costs, types, rarities, target requirements and method tokens.

The full solo pool is available through colorless transformations and separate
uncommon/rare merchant slots. Ordinary Ironclad rewards remain the 80 character
cards. Merchant base costs are 86/172, applying the native 1.15 multiplier and
rounding before price variation; colorless stock is not eligible for a sale.
Stock composition and sampling remain project-authored rather than native RNG parity.

## Rules and ownership

- Explicit immutable definitions use shared builders and ordered effects. New
  mechanics live in `cards/colorless_effects.py`, `powers/colorless.py` and the
  existing resolution queue; no projection or encoder implementation was added.
- `ChooseCombatCard` toggles general selections and `ConfirmCombatSelection`
  finishes them. Purity permits zero to three/five hand cards; Discovery/Splash
  permit skipping. Existing immediate Ironclad selectors retain their behavior.
  Entropy and Stratagem can suspend at turn/draw boundaries without an active card.
- Selection records contain owned candidates, bounds and selected IDs. Offered
  cards have their own pile and allocator ownership; unchosen offers are retired.
  Restore validates candidate sets, operation/source agreement and limits before
  installing state. No resolver callbacks are stored.
- Retain/Retain Hand preserve cards while Ethereal still exhausts. Bolas/Hatchet
  return only exact instances played during the previous round. New clones inherit
  combat modifiers, but not the original instance's return history.
- Automation, Panache, Rolling Boulder and The Bomb have independent power IDs and
  counters. Shared after-card hooks preserve insertion order across card families.
  Mayhem follows hand draw/start powers; Plating precedes ordinary end-turn Bomb
  effects; Pillage finishes each actual draw hook before its next draw/shuffle.
- Hidden Gem adds combat-local replay counts, prefers playable attack/skill/power
  cards, permits X cards, and excludes already-replaying cards. Replays share one
  physical movement but execute play effects/hooks independently. Drum of Battle's
  exhaust energy uses the replay count too.
- Discovery's zero-cost modifier expires after physical play or end-turn cleanup;
  clones made before cleanup inherit it. Its native setter excludes negative
  canonical costs such as Cascade. Splash's whole-turn discount remains distinct.
- Fisticuffs and Omnislice use damage-result totals including block and overkill.
  Omnislice's secondary damage does not apply Strength/Weak/Vulnerable again.
  Vigor, Dexterity, Fasten, No Block, temporary Dark Shackles and The Gambit use
  shared attack/block/damage boundaries.
- Hand of Greed's fatal gold and successfully generated Alchemize potions enter
  the run inventory. Full potion slots still consume the separate potion RNG draw.
  Run restore binds free slots, configured pool and settled loot to actual inventory.
- Combat **v9** and run **v19** persist offered cards, general choices, replay/return
  modifiers, independent power instances, potion RNG and queued continuations.
  Older private schemas reject; public fixture schemas and the legacy fixed
  action/card/status vocabularies remain unchanged.

## Declared content limits

Generation uses explicit implemented catalogs. Alchemize uses Fire/Block Potions,
or the run's configured supported potion pool. Discovery/Calamity use Ironclad.
Splash uses other registered character pools when present; the default contains
only Ironclad and follows the native one-unlocked-character fallback. Other
characters' catalogs and native unlock-state modeling remain open.

Entropy creates fresh base cards without copied upgrades/enchantments/replays.
Status and curse transformations preserve their category using supported subsets
(Dazed, Infection, Slimed, Wound; Guilty and Clumsy). Ancient/event/token cards use
colorless combat replacements. Full potion/status/curse inventories, other-character
content, all item combinations, native RNG parity and live differential evidence
are not established by completing these colorless definitions.

## Source basis

Steam build **23811903**, macOS `sts2.dll`, SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
See the [build manifest](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
Evidence is static metadata/IL inspection and headless execution, not live gameplay.
No profile/save/history access or bridge changes were required. An older external
C# reference was used for navigation; changed values follow the pinned assembly.

| Native member/token | Checked rule |
| --- | --- |
| ColorlessCardPool.GenerateAllCards `100693916` | 64 native definitions, 11 multiplayer exclusions |
| Individual constructors | Costs/types/rarities/targets recorded in inventory fixture |
| Hidden Gem `100710179` / `100710180` / `100710181` | Eligibility, preference, replay addition |
| Drum of Battle `100709908` | Exhaust energy multiplied by generated play count |
| Production `100710525` | Energy 2/3, Exhaust at both levels |
| Splash `100710793` / `100710794`; Discovery `100709877` | Character attack offers, upgrades and optional selection; see constructor fixture for card identities |
| Choose-a-card helper `100712294` | Skip flag forwarded to selection |
| Alchemize `100709520`; potion procurement `100712447` / `100696102` | Generate before full-slot rejection, owned successful insertion |
| Entropy `100707353`; transform factory `100695705` / `100695706` / `100695708` | Mandatory selection, category pools and fresh replacement |
| Stratagem `100707711` | Draw-pile selection after shuffle, before underlying draw resumes |
| Automation `100685053`, Panache `100685854`, Bomb `100686394` | Independent instance mode |
| RunAutoPrePlayPhase `100712567`; SetupPlayerTurn `100712569` | Mayhem after draw and start-power hooks |
| Pillage `100710495` | Finish each draw before looping |
| Card wrapper `100706385` | After-card hooks, result movement, then cost cleanup |
| Cost setter/cleanup `100696480` / `100696487` / `100696488` | Negative-canonical guard; end-turn and played expiration |
| StartTurn `100712573` | AfterBlockCleared still fires with Barricade, enabling Prolong |
| AttackCommand `100712501`, Vigor `100686472` / `100707815`, Pact's End `100710461` | Zero-hit attacks consume Vigor; unmet attack condition preserves it |
| MerchantCardEntry.GetCost `100696243` | Colorless 1.15 multiplier before variation |

## Validation

`test_colorless_complete.py` checks every base/upgraded definition through play,
three turn boundaries and JSON continuation; meaningful cases cover choices,
foreign IDs, mandatory counts, malformed saves, owned loot, discounts, clone
history, draw/power ordering, damage, retain, replay and acquisition pools.

An independent semantic review identified and rechecked concrete ordering,
selection, cost and inventory findings. The final narrow checks passed (8 in
0.32s and clone/history checks 4 in 0.02s). This is bounded source review, not native
runtime differential certification.

- Broad affected suite: **1,625 passed in 179.25s**, covering headless gameplay,
  simulation, analysis/search, engine, headless backends, content, CLI and package imports.
- After the final clone-history and zero-hit Vigor corrections, affected card and
  search regressions: **371 passed in 15.12s**, including the 150 colorless cases.
- Compileall, diff checks and affected documentation links passed.
- Final wheel SHA-256:
  `37c9292f62e8338241def30ae1c4ef3075af890c7b8b9be82363562aa45fa327`.
  All 193 wheel Python sources were byte-compared with the workspace before delivery.

The final wheel was installed into a disposable environment and imported from
`site-packages` outside the checkout. Its 106-variant matrix exercised 29 selection
steps with exact JSON continuation in **6.63s**. The installed first-slice CLI at
seed 2 completed both combats: 66 HP, 127 gold, one potion used, 38 commands, and
restore verification enabled. That is a restricted slice result, not an Act 1
victory claim.

Implementation, review and validation overlapped. Assessment through verified
package took **38m29s** (19:23:00–20:01:29 UTC);
precise independent implementation/review phase timings were not tracked. Test and
installed-smoke durations above are measured. No user wait was required.
