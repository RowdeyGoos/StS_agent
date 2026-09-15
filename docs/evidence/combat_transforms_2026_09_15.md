# Combat transformations and foreign-card census — 2026-09-15

Scope: pinned 0.107.1 / Steam 23811903, solo Ironclad A0, all-unlocked content.
Assembly SHA-256:
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.

## Native evidence

The existing [combat oracle](../../tools/native_combat_oracle/README.md) now has a
`transforms` mode. Its actual native GetDefaultTransformationOptions and
CreateRandomCardForTransform calls produce ordered candidate lists and three
replacement IDs at each of five seeds for **174 original definitions**. Every
sequence includes RNG counter and next-double suffix. The retained
[fixture](../../tests/fixtures/headless_native_transform_vectors.json) is native
output, compacted without changing its values. The fixture's player/context are
explicit in-memory objects; no native CardCmd.Transform, selection UI, run launch,
profile, save, history or Cloud access occurs.

**172 originals** are already implemented and compared directly. The two remaining
native originals, Soot and Frantic Escape, cannot be generated in combat and belong
to later-act callers. Pool inventories include all 12 statuses, 18 curses, 85
Ironclad definitions, 53 solo colorless definitions and 344 solo foreign definitions.
Each foreign family has **80 ordinary cards**, plus six basic/special entries.
Metadata includes native cost, type, rarity, combat-generation eligibility, upgrade
limit and keywords. This inventories foreign content; it does not implement it.

Pinned method-body inspection anchors:

- CardFactory.GetDefaultTransformationOptions `100695705` and filter `100695708`:
  own family except Ancient/event/token/quest inputs, which use colorless; ordinary
  rarity filtering except curses/statuses; combat-generation filter; exclude source.
- StatusCardPool.GenerateAllCards `100694009`: Wither appears before Slimed in
  native declaration order. Older decompiled source omitted Wither entirely.
- Beckon end-in-hand `100709592`: six unblockable, unpowered damage.
  Burn `100709675`: two blockable damage; Toxic `100710955`: five; Wither
  `100711036`: three at its base state. All have upgrade limit zero.
- Void draw callback `100711006` loses one energy. Native normal draw listeners
  visit powers before combat cards (`100711379`, `100712603`), so Automation's
  energy gain (`100707217`) precedes Void's loss. Early Hellraiser remains earlier.
- Kaleidoscope availability `100683781` requires all characters unlocked;
  acquisition `100706741` shuffles foreign families with Niche and invokes the
  reward factory for each of three families, twice. Existing custom-catalog
  acquisition is not claimed to match that factory yet.

## Implemented behavior

`generation/transforms.py` owns ordered combat transformation candidates.
Entropy now uses all ten combat-generatable statuses and all 18 curses, and native
Ironclad/colorless candidate order and filtering. Registered foreign originals
retain their family instead of being redirected to colorless. Invalid empty pools
or unowned originals reject before RNG or identity mutation.

Six added statuses execute: Beckon, Burn, Debris, base Wither, Toxic and Void.
Playable statuses spend their cost and discard/exhaust appropriately. Held damage
uses existing block, HP-cap, Buffer, revival and reactive-draw mechanisms. Beckon
bypasses block while still applying supported HP caps. Its Slippery test uses an
explicit synthetic player status, not a claim of natural Act 1 player acquisition.
Void loses energy only on actual draws, including Pillage, after normal power hooks;
generation/transformation into the hand does not count as drawing.

Transformation preserves pile position, allocates a fresh instance, clears upgrade
and combat modifiers, and runs generated-entry hooks such as Stomp. The persistent
deck remains unchanged. Status/curse pool metadata and Byrd Swoop/Egg metadata are
explicit. The new end-turn HP-loss value is part of immutable card specifications;
existing plain task/selection machinery owns its continuation. Private snapshots
advance to combat **v19** / run **v31**. Public adapters are unchanged.

## Validation and limits

- Actual oracle build: zero warnings/errors in **1.06s**; initial actual factory
  execution completed in **0.18s**. No initialized Godot runtime was required.
- Native pool equality and five-seed/three-draw sequences cover all **172**
  implemented originals. Status/curse costs, flags and generation membership match.
- Earlier focused transformation/colorless/generation/paused-hook scope:
  **480 passed in 14.87s**.
- Broad headless suite: **2,488 passed in 303.16s**. A final small Beckon HP-cap
  correction and two added regression cases were validated by the affected
  status/event/roster rerun: **401 passed in 29.00s**.
- Simulation, CLI and engine compatibility: **265 passed in 5.11s**.
- Independent semantic review identified the Void/Automation order correction;
  corrected transformation suite: **193 passed in 0.78s** before the final HP-cap
  case. No remaining blocker in the bounded review.
- Installed wheel, outside checkout with site-packages imports verified:
  **194 passed in 0.79s**. The test runner uses the existing pytest environment
  with the installed wheel's package directory explicitly first on its import path.
- All **158 headless Python sources** match the wheel. Installed CLI first-slice
  seed 2 completed in **38 commands / 66 HP**, with JSON restore after every command.
  This is continuation evidence, not native victory or full-act parity.
- Installed generated Neow seed 2/right/rest: **198 commands, 16 rooms, nine
  completed combats**, ending in boss defeat; JSON restore verified throughout.

Wheel SHA-256:
`698e7c3d6f23a21a31a710c7d37119d41bc366249a526f3e701524c59e1f05ca`.
Build/install outputs: `/private/tmp/sts-headless-transform-package/`.
Native inspection outputs: `/private/tmp/sts-headless-foreign-native/`.

Foreign-card implementation remains staged: Silent, Regent, Necrobinder and
Defect mechanics and generated dependencies must be executable before complete
Kaleidoscope/Splash pools are enabled. Wither's later-act fake upgrades and native
whole-command/whole-act interaction parity remain open. The
[backlog](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment)
assigns each family and final acquisition checks separately.

Work began at 18:04 UTC; implementation, native inspection and independent review
overlapped. Broad validation completed at 18:22 UTC. No game installation or live
release was performed; no required user wait blocked this bounded batch.
