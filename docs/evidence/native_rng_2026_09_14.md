# Native RNG and probability — 2026-09-14

Implemented on `codex/headless-native-rng`, based on headless integration
`9f05aa4`, for local merge into `codex/headless-integration`. Main and the
production bridge are unchanged. Scope: solo Ironclad A0, supported Overgrowth
Act 1 content, pinned game 0.107.1 / Steam build 23811903.

## Source and oracle

Pinned `sts2.dll` SHA-256:
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Method bodies were read from that assembly; older decompiled C# was used only
for navigation. The pinned RNG differs materially from the older source: it uses
MegaRandom/xoshiro256**, not `System.Random`.

Inspected anchors include `Rng` (constructor 100667292; `NextDouble` 100667303;
`NextGaussianInt` 100667307), `MegaRandom`, `StringHelper.GetDeterministicHashCode`,
`PlayerRngSet`, `RunRngSet`, `CardRarityOdds`, `PotionRewardOdds`, Card/Potion/Relic
factories, their ordered pool methods, `RelicGrabBag`, rewards, merchant entries,
Neow and event card creation flags. Final pickup checks include `RelicCmd.Obtain`
(100712471), New Leaf and Lava Rock.

The retained [oracle](../../tools/native_rng_oracle/README.md) executes actual
pinned RNG/hash methods by reflection. The assembly checksum is enforced before
loading. Game dependency assemblies resolve from a supplied directory; no game
launch, player-profile/save/history read or gameplay mutation is involved.
The headless package itself remains pure Python with no native dependency.

[Golden vectors](../../tests/fixtures/headless_native_rng_vectors.json) cover six
uint32 seeds (including high-bit and maximum values), bounded integers, float32,
double, shuffle and counters; eight UTF-16 hashes include supplementary Unicode.
Four Gaussian vectors cover rejection, counted double consumption and continuation
suffixes. Eight Neow vectors use the actual native RNG with a **source-derived
composition algorithm**, explicitly excluding multiplayer Massive Scroll and
unavailable Kaleidoscope. They do not execute the complete native Neow model.

## Implemented behavior

- Exact pinned primitives and seed arithmetic, with owned full RNG state and
  validated JSON continuation. Native runs hash the exact textual seed; solo
  player slot zero and event model-ID salts are explicit.
- Shared native domains for reward sources, shops, event-local rolls and seven
  combat domains. Combat restore rejects disagreement with owning run streams
  and rebinds their aliases. Authored fixtures retain their prior MT19937 profile.
- Float32 card rarity offsets/modes, normal/elite/boss/shop weights, wrapped
  rarity fallback, native candidate order and upgrade-draw consumption. Fixed
  and uniform event/relic callers retain their source-specific flags.
- Float32 adaptive potion odds, elite bonus, forced-drop updates without a
  clamp, native rarity boundaries and ordered ordinary pools.
- Shared/player relic bags populated using UpFront, rarity rolls, front/back
  acquisition, fallback and depletion when offered or obtained by name.
- Native merchant composition of seven cards, three relics and three potions;
  float32 prices and rounding; sale price reroll; Courier refills and live stock
  exclusions. Refilling a potion can duplicate another stocked potion.
- New Leaf uses Niche; Lava Rock pulls ordinary relic rewards from the front;
  Scroll Boxes draws successive common/uncommon choices rather than shuffling
  the whole card pool; Neow's Bones preserves native option order and curse domain.

Generated `ironclad_act1()` defaults to `rng_profile="native"`; generic scenarios
and authored slices retain `fixture`. `ironclad_act1(rng_profile="fixture")` is
available explicitly. Native text seeds work programmatically; the CLI currently
accepts integers. Current private schemas are combat v13/run v23; older records
reject instead of changing their semantics. In native snapshots, `generation_odds`
is authoritative; the old integer `potion_drop_chance` belongs to the fixture profile.

## Validation

- Direct assembly/hash and source-derived Neow vector agreement; final dedicated
  suite: **58 passed in 3.27 seconds**.
- Initial headless/simulation/content run: **1,830 passed, 10 failed in 276.92
  seconds**. Failures were old seeded unknown-room outcomes and event-shuffle
  request counts; revised native fixtures passed in the affected rerun below.
- Affected native/event/unknown/Neow rerun: **242 passed in 61.92 seconds**.
  The later named-pickup/New Leaf/Gaussian checks are included in the 58-test run.
- Independent semantic review checked stream ownership, native source arithmetic,
  probability modes, merchant consumption, bags and snapshot validation. Concrete
  findings were corrected. Its final six focused checks passed in 0.07 seconds,
  plus an independent Lava Rock bag/RNG continuation probe.
- Broad repository run: **3,086 passed, 14 failed, 63 errors in 381.07 seconds**.
  Four Gaussian counter failures came from the process importing the pre-correction
  implementation; the final 58-test rerun passes. Eight unchanged bridge fake-socket
  fixtures lack `shutdown`; frozen differential evidence has one identity failure
  and 63 setup errors. Historical evidence was not repinned. The sandbox localhost
  binding failure passed outside the sandbox (**1 test in 0.01 seconds**).
  The whole repository is not reported as green.
- Final affected native/map/unknown/Neow suite after the Gaussian correction:
  **132 passed in 39.85 seconds**.
- `compileall game tests`, diff whitespace and relevant documentation links checked.

Built wheel `sts_agent-0.1.0-py3-none-any.whl`, SHA-256
`2b25cb51d233ee081b90bc292388b536af704beb74e522b12316839c72ea1d98`.
Installed into a disposable environment and verified `site-packages` imports from
outside the checkout with `PYTHONPATH` unset. Eight seeds (including text/Unicode)
passed Neow/reward/13-slot shop JSON and legal-action continuation checks.
The authored seed-2 slice completed in 38 commands with 66 HP. Generated native
seed 2/right/rest selected Scroll Boxes, visited 16 rooms and lost at the boss
in 215 commands after 10 completed combats; restore verified throughout.
This is execution evidence, not proof of a native victory or whole-run seed parity.

Local inspection/build/test logs: `/private/tmp/sts-headless-native-rng`.

## Remaining limits

**Whole-run native same-seed parity remains open.** Map/encounter/event initialization
still includes authored domains and ordering. Native entity spawning, HP/move draws
and every gameplay consumer need boundary traces. Full runtime acquisition
eligibility, unlock epochs, foreign-character cards and tutorial/discovery inputs
are not yet reproduced. These inputs can change candidates and consumption before
otherwise exact probability rules execute. Gaussian transcendental calculations
match the retained vectors; exhaustive cross-platform libm agreement is not claimed.

The [next assignments](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment)
separate initialization, acquisition eligibility, combat draw consumption,
Kaleidoscope and the native Act 1 acceptance matrix. Existing content exclusions,
higher ascensions and later acts remain separate scope.

Work began around 17:32 UTC. Source inspection, implementation and independent
review overlapped and were not separately timed. Focused validation durations are
recorded above. Packaging/installed checks completed around 18:06 UTC; final
integration/documentation finished at 18:10 UTC. No user readiness wait or live
release step was required.
