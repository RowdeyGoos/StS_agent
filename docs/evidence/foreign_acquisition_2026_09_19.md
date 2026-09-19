# Foreign acquisition — 2026-09-19

## Scope

`DEFAULT_CARDS` now includes all 320 ordinary solo foreign cards, their implemented
starters and generated cards. `IRONCLAD_CARDS` preserves the previous restricted
catalog; cumulative family catalogs remain available. Ordinary Ironclad reward/shop
pools retain their family. All 161 audited relics and 27 solo Neow offers are now
supported by the default catalog. No playable foreign character was added.

Kaleidoscope requires four complete ordinary families. Each group shuffles the
four pools with Niche and takes three; each selected family uses a singleton
Source.Other reward with base rarity odds and no pity mutation. Singleton hooks
run during creation of both groups, then each group's reward hooks run. Saved
upgrades/enchantments prevent Wing Charm, Silver Crucible, Silken Tress and eggs
from losing their first-stage modifications. Offers use existing optional relic
choices and can be skipped independently.

Splash uses all 112 eligible foreign attacks in native character/declaration order,
selects three distinct cards, and upgrades all offers for Splash+. Its optional
selection applies an absolute local Energy cost of zero until play/end and zero
Star cost until turn end. Energy-X and Star-X retain native resource spending.
Owned choices, costs and relic work survive JSON continuation. Private formats
advance to combat v24 / run v36; older formats reject.

Foreign ordinary/basic transformations preserve the source family and native pool
order in combat, transformation events and New Leaf. Restored pending relic groups
and Splash offers reject invalid counts, families, duplicate definitions and levels.

## Native reference and evidence boundary

Target: **0.107.1 / Steam build 23811903**. `sts2.dll` SHA-256:
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.

The existing oracle's `foreign` mode reproduces
[`headless_native_foreign_vectors.json`](../../tests/fixtures/headless_native_foreign_vectors.json):

- 30 Kaleidoscope cases: five seeds × six reward-hook configurations, two groups
  each, with exact definitions, upgrades, enchantments, counters and RNG suffixes.
- Ten Splash cases: five seeds × base/upgraded, exact 112-card pool, three selected
  definitions, upgrade levels, 111 shuffle draws and next RNG value.
- 16 transformation cases: ordinary/basic sources in four families, combat and run
  contexts; complete native option order and three sampled replacements per case.

The oracle invokes actual native StableShuffle, CreateForReward,
GetDistinctForCombat, reward hooks and transformation factories. Its all-unlocked
A0 context and acquisition orchestration reproduce inspected source. This does
**not** execute complete Kaleidoscope.AfterObtained/Splash.OnPlay, a card selector,
a native combat turn or an entire run. Native factory agreement and Python
continuation are distinct evidence. No live/profile/save/history/Cloud access was
used. A fresh invocation reproduced the retained JSON exactly; the oracle build
had zero warnings/errors.

## Review and validation

Independent semantic review found two blockers, both corrected and rechecked:
Star-X must bypass temporary Star cost overrides, and acquired foreign cards must
remain valid through events/New Leaf and keep native transformation pool order.
The final bounded review reported no remaining blockers (26 tests, 5.13 seconds).

- Broad headless suite: **3,759 passed in 895.58 seconds (14m55s)**. This run
  began before the final Star-X/transformation review corrections; the final
  affected source and installed tests above/below cover those changes.
- Final source acquisition suite: **120 passed in 33.09 seconds**; subsequently
  added forged Splash restoration cases: **3 passed in 0.29 seconds**.
- Affected acquisition/transformation/event suite: 386 passed, eight test setup
  failures in 87.44 seconds. Those tests illegally changed an owned native stream's
  seed; they now retain owner seeds while checking native raw-seed vectors
  separately. All eight pass in the final source and installed acquisition suites.
- Other focused acquisition, potion, generation and shuffle regressions:
  **371 passed in 74.21 seconds** before the final Star-X/transformation corrections;
  final affected tests cover those changes.
- Compatibility across simulation, engine, conformance, data and brute-force:
  **362 passed in 82.76 seconds**.
- Installed acquisition/runtime-eligibility tests: **161 passed in 33.83 seconds**.
  Imports were asserted to come from the fresh installation, outside the checkout.
- `compileall game tests` and `git diff --check` passed.

The wheel was installed into a fresh environment. All **183** headless Python
modules match source, wheel and installed bytes. Wheel SHA-256:
`b73d92ebbe8cceef90d9ded1a1ce861a9d472692a8ac2dfbd8555f07a10c70fd`.
This identifies the validated build; later documentation-only updates do not
repin it or claim a newly built wheel.

Installed CLI checks use `--verify-restore` after every command:

| Route | Result |
| --- | --- |
| Authored first slice, seed 2, smith | 38 commands; restoration verified |
| Generated Overgrowth + Neow, seed 2, right/rest | Fishing Rod; 158 commands, six completed combats, defeat; restoration verified |
| Generated Overgrowth + Neow, seed 0, right/rest | Kaleidoscope; 218 commands, nine completed combats, 16 rooms, defeat; restoration verified |

These are synthetic policy rollouts, not victories or native full-run comparisons.
The remaining acceptance work is actual native card/turn composition and a declared
Act 1 boundary matrix spanning bosses, events, shops, pickups and choices.

## Timing and performance observation

Work began at 12:24:41 UTC; validation and documentation were complete at
12:55:54 UTC (31m13s), before local Git integration. Native source/oracle work, implementation, review and
validation overlapped; separate phase elapsed times were not recorded. No user
readiness wait was required. Focused and installed timings are listed above.

A 50-call diagnostic measured `CardCatalog.snapshot_fingerprint()` at 3.62 ms
for the previous 173-definition restricted catalog and 11.74 ms for the complete
517-definition catalog on this host. Snapshots/restores currently recompute that
fingerprint. This identifies repeated work made more expensive by the default
catalog change, not a measured percentage of total suite runtime. Profiling and
safe per-catalog fingerprint caching remain a separate performance improvement.
