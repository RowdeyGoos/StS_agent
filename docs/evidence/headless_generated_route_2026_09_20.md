# Continuous generated Act 1 trace — 2026-09-20

The pinned 0.107.1 native fixture now plays seed 0 from actual Neow offers through
16 Act 1 rooms, ending in **defeat against Vantom**. The 170 combat actions and all
recorded combat/reward/room boundaries match headless. Every Python action also
executes from a JSON-restored copy, checking identical snapshots and legal actions.
This is continuous native gameplay evidence through a loss, not a completed act
or a winning three-act campaign.

## Retained evidence and scope

- [Native route capture](native_generated_route_2026_09_20.json): pinned engine,
  assemblies, dependencies, fixture source hashes, build identity, timings,
  cleanup and complete selected path/actions/results.
- [First-combat regression capture](native_generated_start_route_regression_2026_09_20.json):
  the extended fixture's original `generated-start` mode still produces exactly
  the [previous accepted result](native_generated_start_verified_2026_09_20.json).
- [Replay](../../tests/headless/test_native_generated_route.py) verifies both
  executed source bindings and the action-by-action route. Historical matrix and
  earlier captures are preserved unchanged.

The route comprises 11 combats, three healing rests, an unopened chest and a
merchant exit without purchases. It claims native gold, selected cards and earned
relics, and skips potions. Relics at defeat are Burning Blood, Scroll Boxes,
Lantern and Ripple Basin; gold is 295. Final Rewards/Niche/Shuffle counters are
142/19/362. Comparisons include ordered hand and deck IDs/upgrades, player HP,
block and energy, living enemy IDs/HP/block, card reward offers and choices, relic
claims, inventory, gold and those three RNG counters. These fields do not expose
every native power, hidden pile or RNG stream.

The fixture uses real native card actions/executor and reward selection objects.
It invokes end-turn phases explicitly, uses mock localization/textures and
in-memory saves, asserts saving and uploads disabled, bounds actions/awaits and
runs cleanup in `finally`. Both retained executions had empty stderr and removed
their owned temporary user directories. No game project, profile or Cloud data
was loaded and no HP, kill or victory was injected.

## Corrected behavior

1. Chest offers pull from the shared relic bag only. A skipped offer remains in
   the player's bag; actual pickup removes both copies. Previously the unopened
   chest also depleted the player bag, changing the later elite reward from
   native Ripple Basin to Tiny Mailbox. Player reward/shop pulls retain their
   existing removal from both bags.
2. Inklet starts with Slippery 1. The first unblocked damage is capped at one and
   consumes the stack; subsequent hits apply normally.
3. Inklet's random follow-up branch orders Piercing Gaze before Whirlwind. The
   probabilities were equal before, but the reversed ordering changed exact
   seeded moves and later HP.

Private snapshot versions are now **combat v36 / run v55**. Both old versions
reject atomically; standalone combat snapshots must not reinterpret the corrected
Inklet RNG continuation. Independent source review confirmed the three behavior
changes and identified the standalone schema issue, which was corrected.

## Validation

The final native route build took 1.50 seconds and execution 1.81 seconds. The
legacy first-combat regression build took 1.59 seconds and execution 1.80 seconds.
The final affected integration batch passed **736 tests in 173.84 seconds** across
native RNG, chest bags, relic eligibility, Overgrowth encounters/routes, generated
start/route, rewards, endings and Act 2/3 progression. Six targeted chest, Slippery
and old-schema cases passed in 0.42 seconds during correction. After adding exact
room-entry comparisons, the two route/identity tests passed again in 12.47 seconds.
Compilation with the project Python environment, diff checks and all file links
in changed guides passed. An initial compile attempt used the system Python and
could not write its macOS cache directory; the project environment completed it.

The previous [repository-wide verification](headless_verification_2026_09_20.md)
remains the record for unrelated bridge/frozen-corpus failures; this batch does
not claim they are repaired. The full suite was not repeated. End-to-end
implementation and review elapsed times were not separately measured.

## Remaining limits and next implementation

The fixture must gain legal winning decisions and continue through actual Acts
2/3, their Ancient starts and Architect before full native campaign parity can be
claimed. It currently avoids unknown rooms, leaves shops and skips potions. One
unopened chest does not verify a second chest's native synchronizer lifecycle;
exercise actual opened-skip/claim cleanup before expanding across acts. These
limits are separate from the existing Python synthetic progression tests and the
native prepared-ending matrix.

Fresh native shared bags also refill an initially empty requested rarity in
canonical order without RNG. Current headless exhaustion behavior, owned-item
filtering and unique treasure-history validation do not implement that boundary.
Add native exhaustion/filter/fallback cases and update generation, duplicate
pickup and persistence together. Do not infer native disk-save reload parity
from Python JSON continuation: native deserialized bags use different refill
configuration. This is an explicit remaining fidelity task, not part of the
ownership correction proved by this trace.
