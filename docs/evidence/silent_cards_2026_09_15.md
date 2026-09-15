# Silent ordinary-family implementation — 2026-09-15

## Scope and evidence strength

The explicit `SILENT_CARDS` catalog extends the Ironclad environment with all
**80 ordinary solo Silent cards**, both upgrade levels, four starter cards and Shiv.
The default catalog and all-unlocked acquisition gates are unchanged. This is
foreign-card execution support, not a playable Silent run. Suppress and Wraith Form
are Ancient entries outside this ordinary-family batch.

Pinned source: game **0.107.1**, Steam build **23811903**, assembly SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The existing [native oracle](../../tools/native_combat_oracle/README.md), with its
`silent` mode, directly enumerates all unlocked solo Silent entries plus Shiv,
upgrades mutable instances and reads resolved local costs, keywords and dynamic
variables. Its 87-row output exactly reproduces
[the retained fixture](../../tests/fixtures/headless_native_silent_values.json).
The oracle build passed with zero warnings/errors and accessed no profiles or saves.

Metadata is direct native execution evidence. Card/power ordering and selection
semantics below are pinned-source findings, exercised by Python integration tests.
They are not a demonstration of native whole-turn or complete Act 1 parity.

Useful pinned method anchors: `CardCmd.DiscardAndDraw` (100712173), Poison's
side-start continuation (100707554), Outbreak's amount-change continuation
(100707519), `NightmarePower.SetSelectedCard` (100685772), Echoing Slash's play
continuation (100709926), `NPlayerHand.Add` (100679461), hand-selection visibility
refresh (100679480), `SetupPlayerTurn` (100712569) and `StartTurn` (100712573).
These identify static source findings; they are not additional execution cases.

## Implemented rules

- Explicit discards record history, finish their batch, perform requested draws,
  then autoplay captured Sly cards. Ordinary hand flush has no discard/Sly trigger.
- Poison uses captured side participants after block clear. Accelerant captures its
  iteration count, with current Poison damage and a surviving-target decrement per
  iteration. Outbreak counts positive applications, deals blockable unpowered
  damage every third application, and completes its reset even after a lethal hit.
- Shivs support Accuracy, Phantom Blades, Fan of Knives, generated-entry hooks,
  Knife Trap and Inky. Blade of Ink follows the pinned build's enchanted-Shiv rule.
- Turn/draw/discard histories drive Finisher, Flechettes, Memento Mori, Murder and
  Pinpoint. Pinpoint discounts after completed skills and expires at turn cleanup;
  existing Stomp cost semantics remain separate.
- Nightmare stores independent templates under ordered power-instance IDs.
  Infinite Blades and Nightmare run in acquisition order before hand draw. Clones
  receive current generated-entry powers while preserving native clone exemptions.
- Afterimage, Serpent Form and Strangle capture their amounts before each play.
  Echoing Slash counts kills in its own attack results, including all repeats in
  one attack context; unrelated reaction kills do not create extra waves.
- Side-start powers resolve after normal draw/turn-start work, including when setup
  pauses at a choice. Separate execution context ownership prevents accidental
  card attribution. Already-visible choices keep priority over deferred Horn
  choices; native hand-selection options refresh after new cards enter.
- The Hunt records an earned reward count without generation RNG on the fatal hit.
  Post-combat reward population uses the room's card-reward factory and existing
  acquisition commands. Snapshot validation binds all offers to the earned count.

Private snapshots use combat **v20** and run **v32**. They include temporary costs
and keywords, captured effects, ordered delayed templates, side-start continuations
and earned rewards. Incompatible older snapshots reject; malformed current state
rejects atomically. The legacy encoder vocabulary is unchanged.

## Validation and review

[Silent tests](../../tests/headless/test_silent_cards.py) cover both levels of every
ordinary card through play, choices and three turns, native metadata, shared
interactions, RNG/transform ordering, JSON continuation and adversarial snapshots.
The independent semantic review identified and verified corrections for Pinpoint
and Shadow Step timing, Echoing Slash reaction kills, Nightmare entry/order,
reward ownership, live hand selectors and terminal side-start cleanup. Its final
bounded pass reported no remaining blockers.

- Independent review: 290 Silent tests in 14.84s, then 15 affected checks in 0.26s.
- Final broad headless run: **2,780 passed, one failure in 325.44s**. The failure
  was an existing standalone relic-reward validator call with no pending reward.
  The validator now accepts the earned Hunt count explicitly; the run decoder
  still requires its persisted binding. **613 affected checks passed in 36.47s**
  after this correction, including the failing case, all Silent tests, reward
  integration and snapshots. The scoped correction was independently reviewed.
- Final simulation/engine/conformance/data checks: **355 passed in 79.29s**.
- Rebuilt installed-wheel Silent and runtime-eligibility checks: **332 passed in 16.36s**.
- `compileall game tests` and diff whitespace checks passed.
- All **163** headless Python modules in the wheel match the working sources.
- Installed first-slice seed 2, smith: 38 commands, completed with 66 HP and restore verification.
- Installed generated Act 1 seed 2, right/rest, Neow: 198 commands, 16 rooms, nine completed
  combats, defeat at the boss; every command restored. This confirms executable
  continuation, not victory or native full-run parity.

Wheel SHA-256:
`9be5d6fc7cfd56fa6e58a829e81ccb49fef2d380a693a3152f015c182914e3a4`.
Artifact: `/private/tmp/sts-headless-silent-native/package/sts_agent-0.1.0-py3-none-any.whl`.

Implementation/source inspection and independent review overlapped from 18:35:18
UTC to final validation starting at 19:13:03 UTC (37m45s). Final test durations are
measured wall times; concurrent checks shared the host. No user-readiness wait or
live game launch was involved.

## Remaining assignments

Regent is next: its 80 ordinary cards and Stars/Forge/Sovereign Blade dependencies.
Necrobinder and Defect follow, leaving 240 ordinary cards across those three families.
Only after complete foreign catalogs should default Kaleidoscope/Splash acquisition
be enabled and checked against the native factories. Actual native card/selector
composition and the complete Act 1 boundary-comparison gate remain open in the
[implementation backlog](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
