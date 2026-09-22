# Runtime acquisition eligibility — 2026-09-14

Feature branch `codex/headless-runtime-eligibility`, based on integration
`a54e3b8`, for local merge into `codex/headless-integration`. Main and the production
bridge are unchanged. Scope remains solo Ironclad A0, Overgrowth Act 1, all unlocked
and all seen; this change does not enable first-run profiles or later-act gameplay.

## Native reference

Game 0.107.1 / Steam 23811903, `sts2.dll` SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The retained [oracle](../../tools/native_eligibility_oracle/README.md) executes
actual native methods against explicit in-memory contexts. No game, RunManager,
profile, save, history or Cloud access is involved. Expected data in the
[fixture](../../tests/fixtures/headless_runtime_eligibility_vectors.json) comes
from this assembly, not the Python implementation.

Coverage:

- All 161 scoped relics at six floor/prior-run combinations: 966 `IsAllowed`
  comparisons, plus native shop and Neow predicate ownership metadata.
- Native order for six solo card/relic/potion pools. Removing individual epochs
  identifies 18 relevant gates: three Ironclad card, five colorless card, five
  shared relic, two Ironclad relic, one Ironclad potion and two shared potion gates.
  Exact IDs and their excluded definitions are retained in the fixture.
- Four seeds at floors 0 and 41, each with nine front/back/filter/fallback bag
  operations, complete shared/player bag contents, RNG counters and suffixes.
- Six actual Dingy Rug pool-modification contexts, including direct grants,
  explicit suppression, custom pools, existing colorless pools and rarity filters.
- Eight actual potion batches spanning combat eligibility and a blacklist, with
  distinct initial choices and exact RNG consumption/suffixes.

Pinned anchors: `RelicModel.IsAllowed` 100682941, `IsAllowedAtNeow` 100682942,
`IsBeforeAct3TreasureChest` 100682943; `RelicGrabBag.GetAvailableDeque` 100666211,
`RemoveDisallowedRelicsFromDeques` 100666213, front/back pulls 100666206/100666207;
merchant predicate 100711783; Dingy Rug 100683384; Lasting Candy 100683843;
`CardFactory.CreateForReward` 100695701/100695709 and `RollForRarity` 100695710.
The older decompiled reference differs in bag handling and Dingy Rug semantics;
pinned IL and actual execution take precedence.

## Behavior

`relics/eligibility.py` owns pure predicates. Seventeen relics have the native
before-Act-3-chest cutoff (solo floor <41), and Lasting Candy additionally excludes
Ironclad's first-ever run. Silver Crucible and Winged Boots are solo-only; the
excluded Massive Scroll remains unregistered. Generated runtime uses the existing
all-unlocked profile (`UnlockState.all`, 9,999 prior runs). Boundary predicate
inputs do not add arbitrary unlock/progression configuration.

Every native relic pull first removes globally disallowed entries from **all
player rarity bags**. A caller's restriction or blacklist preserves rejected
entries, including when the draw falls through to another rarity. Selected relics
are removed from the shared bag; global purging of the player bag does not purge
its shared counterpart. Filtering consumes no RNG and cannot reorder survivors.
Named acquisition still removes the acquired definition from both bags.

Shops exclude Amethyst Aubergine, Bowler Hat, Lucky Fysh, Old Coin and The Courier.
The first three exclusions were missing. They remain available to other acquisition
sources and survive shop skips, including Courier refill sequences.

Dingy Rug applies only to marked card rewards with modifiable named pools. It now
extends Orrery and Lost Coffer rewards. Direct grants such as Brain Leech's Share
Knowledge, Hefty Tablet and Room Full of Cheese retain their native pools, as do
explicitly protected event offers and custom pools. Existing rarity/type filters
remain in force. Merchant cards remain unaffected.

Lasting Candy's extra power now uses native Source.Other/base rarity odds followed
by its pick and upgrade check, preserving the normal rarity offset. White Star
consumes boss rarity rolls and composes with the extra-power hook. These full hook
sequences are checked against inspected call/flag semantics, not executed by the
oracle. Potion batches now expose blacklist and combat-context inputs; native
rarity selection follows filtering, and selected definitions leave the batch.

Private run snapshots advance to **v25**, combat remains **v13**. Older run schemas
reject explicitly because acquisition/configuration semantics changed.

A deliberately restricted card pool can exhaust every power in the initial offer.
Native Lasting Candy then permits a duplicate power. The current definition-ID
reward choices cannot represent independently modified duplicate options, so this
case now rejects explicitly and rolls back the complete reward transaction. The
full Ironclad/colorless pools cannot reach this boundary with three initial offers.
Implement instance-based reward choices before enabling this restricted fallback.

## Validation and packaging

- Initial focused run: **92 passed in 2.81 seconds**. Added concrete pickup/event,
  combined-relic and snapshot regressions; final focused run: **99 passed in 3.07
  seconds**. The rollback test initially used ancient-only Corruption, which failed
  before its intended boundary; it was corrected to ordinary Demon Form.
- Broad headless run: **1,834 passed in 292.17 seconds** (4 minutes 52 seconds).
  Its collection preceded the final restricted-fallback guard and two new tests;
  the affected final 99-test suite above and independent correction review cover
  that change. Unaffected broad results were reused.
- Independent semantic review: **97 tests passed in 3.03 seconds**; 30 combined
  Dingy Rug/Lasting Candy/White Star/Prayer Wheel reward restorations passed in
  0.72 seconds. The restricted duplicate fallback finding was corrected; its
  five-test review passed in 0.13 seconds, including helper/transaction atomicity.
  No remaining blocker for the declared scope.
- `compileall game tests`, diff whitespace and relevant local documentation links
  pass. Unrelated legacy bridge/frozen-evidence matrices were not rerun or repinned.

Built and installed `sts_agent-0.1.0-py3-none-any.whl`, SHA-256
`22c2d7d4827c5e82d74251114fac3a98cb911c7fc7fa481677b30760fd0d2ba7`, in a disposable
environment. With PYTHONPATH unset and imports verified from site-packages:

- 966 relic predicate comparisons, eight potion batches and 30 Courier
  purchase/refill commands passed with exact JSON continuation.
- All 13 native initialization/map reference seeds still matched, including
  restoration through 13 Neow choices.
- Authored seed-2 slice completed in 38 commands with 66 HP and restore verification.
- Generated seed 2/right/rest with Neow visited 16 rooms and lost at the boss after
  nine completed combats and 192 commands, with restoration verified throughout.
  This is execution/continuation evidence, not native combat parity or run victory.

Outputs are in `/private/tmp/sts-headless-runtime-eligibility`. Work started around
18:56 UTC; inspection/implementation/review overlapped and are not separately timed.
Validation times are above. Packaging and installed checks completed around
19:13 UTC; final documentation/integration finished around 19:15 UTC (about 19 minutes total). No user wait
or live release step was required.

## Next work

HF-05C: native combat construction, random draws and interaction ordering across
combat boundaries, followed by foreign-character Kaleidoscope content and a native
Act 1 acceptance matrix. Arbitrary unlock histories, modifiers outside the declared
profile and later-act gameplay remain separate. The duplicate restricted reward
fallback above is a concrete future extension, not silently treated as supported.
