# Solo event branch comparisons — 2026-09-20

The [capture manifest](native_event_branches_2026_09_20/manifest.json) retains
**9,376 native branch-prefix cases across 65 event families**. The separately
rerun [Architect ending](native_campaign_ending_2026_09_20.json) supplies the
66th solo family. These are actual commands and callbacks from pinned native
build 0.107.1, compared with the independent headless engine. They are bounded
semantic-branch evidence, not an exhaustive Cartesian product of game states.

## Matrix

Ordinary events use seeds 0/2/42, A0/A10, 61/80 HP, 500 gold, an Ironclad starter
deck plus Inflame/Offering, five ordinary relics and Foul/Fire Potions. Enhanced
inventories add all three Eggs, Wing Charm and Bing Bong. The A10 inventory starts
with full potion slots. War Historian Repy covers zero, one and two Lantern Keys.

Every offered unlocked event option is explored. Repeated Baths and Conveyor
pages continue through resource changes; Fake Merchant explores the remaining
stock subsets and all offered purchases/leave/Foul Potion transitions. Additional
seed-0 enhanced A0 cases select the minimum or maximum number of cards, reverse
physical-card selection order, select the last card reward, or decline rewards.
The standard cases select the first eligible card/reward. This covers selection
mechanisms and their boundaries without enumerating every interchangeable card
combination.

| Mechanism | Retained native cases |
| --- | ---: |
| Fake Merchant purchases, stock subsets, Foul Potion and combat rewards | 3,852 |
| Crystal Sphere, both payments/tools and targeted item reveals | 780 |
| Endless Conveyor through changing gold, HP and dishes | 376 |
| Abyssal Baths through repeated costs and terminal outcomes | 322 |
| Tinker Time, all nine type/rider configurations | 320 |
| Slippery Bridge | 266 |
| Battleworn Dummy, all three settings and victory/timeout continuations | 96 |

Ancient discovery searches seeds 0–127 and retains extra cases when a new offer
appears. All **99 solo Ancient relic offers** are selected, including all 27 Neow
offers. Later Ancients run at their real act indices; Darv covers both later acts.
Scroll Boxes exercises both bundles through the native replay-choice waiter.
Trial additionally uses seed 6 to cover the noble alongside the merchant and
nondescript defendants. Repy's one-key path finishes after its first reward; two
keys permit the second unlock. The manifest lists every family's count and observed option keys.

## Compared boundaries and persistence

`tests/headless/native_event_replay.py` compares legal event options, ordered
physical deck changes, upgrades/enchantments, Mad Science configuration, HP,
maximum HP, gold, relic order, potion slots, generated rewards and event/Rewards/
Niche/Transformations/Shops RNG counters plus next draws. It selects the matching
reward offer when native reward sorting reorders equal-priority rewards.
Each headless command resumes from JSON and verifies the restored state and legal
actions before execution. Shared prefix snapshots reduce duplicate replay work.
Malformed continuation tests reject missing, duplicated, orphaned or foreign
Hefty Tablet work and altered combat-layout construction state atomically.

Corrections exposed by these comparisons:

- Morphic Grove uses its owned event RNG. Jungle Maze uses native float gold
  variation and consumes the solo shuffle draws.
- Wellspring and Legends draw uniform potions from native character/shared order
  on Rewards. Whispering Hollow generates independent potion rewards, permitting
  duplicates. Custom fixed gold rewards still consume their native RNG draw.
- Reflections acquisitions can trigger Bing Bong; Nest and Wellspring validators
  accept exactly the resulting owned clone.
- Claws and Archaic Tooth append transformed cards. Ancient offer enchantments
  apply before acquisition hooks; Arcane Scroll includes reward decoration.
- Hefty Tablet adds both originals before acquisition clones, and its saved card
  reward remains bound to its required Injury. Lost Coffer generates cards before
  its potion but presents the potion first.
- Repy finishes immediately when its initial unlock leaves no Lantern Key.
- Punch-Off and Lantern Key construct enemy HP on event entry and reuse that
  constructor input at combat startup. JSON stores owned data rather than
  callbacks, and the shared HP RNG is not advanced twice.

The private run schema is **v63**; combat remains **v42**. Older run snapshots
are rejected. Content fingerprint serialization retains exactly the previous
values while avoiding a redundant recursive copy at every snapshot.

## Native boundaries and limits

All captures use the existing isolated queue runner, in-memory `MockGodotFileIo`,
disabled saves/uploads, owned presentation stubs and disposable user directories.
Accepted executions have empty stderr and confirmed cleanup. Compressed files
preserve the exact captured JSON bytes; the manifest binds both raw and compressed
hashes, and each capture retains its original source/build/dependency identity.

- Event combats use **authored finished children** followed by actual native
  end/victory hooks, reward generation/selection and parent resume. They do not
  claim a combat-policy victory or execution of the entire native combat cleanup.
- Trial's popup opening is a source contract because native TestMode omits its
  factory. Confirmation and cancellation invoke the actual popup callbacks.
- Crystal Sphere runs its native payment option with presentation disabled, then
  reconstructs the same board from a copy of its pre-option RNG and checks the
  consumed counter before running actual tool/cell/completion callbacks.
- Calling Bell's TestMode-only fixed rewards are replaced by its actual production
  `GenerateRewards`, followed by native population and claims. This establishes
  that factory boundary; it does not claim an untouched production RewardsSet
  modifier pass. The authored inventory has no modifier affecting that pass.
- Scroll Boxes temporarily leaves TestMode only until its remote bundle waiter
  suspends, with local presentation disabled. TestMode and local ownership are
  restored before delivering the native replay choice and acquiring cards.

The suite does not enumerate every seed, Crystal Sphere click permutation,
physical-card combination, inventory cross-product, unlock history, or hidden
native field. Relic IDs/order are compared; every persistent relic field and every
combat power/status are not recorded here. Live UI behavior, multiplayer and
alternate modes are outside this scope.

## Reproduction and validation

Use the existing [native oracle instructions](../../tools/native_combat_oracle/README.md)
and isolated runner with `--mode event-roster --event-name FakeMerchant` (or another
manifest event name), plus the pinned engine/native-data/SDK/generator/dotnet/Spine
inputs. Supply a new output directory. Omit `--event-name` only when intentionally
running the complete roster in one process; individual-family runs give clearer
bounded failure reports.

The pure-Python retained comparisons need no installed game:

```sh
PYTHONPATH=. python3 -m pytest -q tests/headless/test_native_event_branches.py
PYTHONPATH=. python3 -m pytest -q tests/headless/test_event_branch_persistence.py
```

[Thirteen fresh baseline executions](native_event_branch_regressions_2026_09_20.json)
match the original ten A0/A10 campaign results, 144-case event inventory capture,
reward handoff and Architect ending byte-for-byte at the parsed result boundary.
Historical evidence and original hashes remain unchanged. Native event execution
times sum to 164.40 seconds across 65 isolated processes, excluding builds; this is
summed execution time, not elapsed wall time. Final regression results are recorded
in the implementation change summary.

Final validation completed:

- All 9,376 retained native cases pass headless comparison. The initial matrix's
  67 pytest groups ran in three shards (194.55 / 295.84 / 326.62 seconds).
  The final capture preserves every previously tested row exactly; Trial and
  Repy's expanded families plus the final census/bindings passed in 11.37 seconds.
- Thirteen native baseline reruns preserve the prior parsed results. A10/boss and
  other campaign replay checks passed after updating consumers to the fresh
  report; the final affected correction group passed in 107.38 seconds.
- Ten focused persistence/Repy checks passed in 0.38 seconds. Compilation and
  diff/link checks passed. Independent RNG/persistence review found no remaining
  blockers, including Repy's completion and detached content fingerprints.
- The broad repository run completed 8,254 tests in 842.62 seconds: 8,171 passed,
  20 failed and 63 errored. Ten headless failures were stale stream expectations
  or references to the prior harness report; their corrected checks passed.
  The local socket test passed outside the sandbox. The remaining **nine failures
  and 63 setup errors are unrelated baseline issues**: eight bridge fixture gates
  use socket doubles without `shutdown`, and the differential fixtures reject an
  existing frozen identity mismatch. All nine failures and the shared setup error
  reproduce on unchanged integration commit `9477b72`; historical identities were
  not repinned to conceal them. The broad repository suite is therefore not green.
