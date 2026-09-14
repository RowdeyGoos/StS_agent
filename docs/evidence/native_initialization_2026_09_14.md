# Native run initialization — 2026-09-14

Implemented on `codex/headless-native-initialization`, based on headless
integration `22b87d9`, for local merge into `codex/headless-integration`.
Main and the production bridge are unchanged.

## Declared inputs and reference

Pinned game 0.107.1 / Steam build 23811903; `sts2.dll` SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Inputs are solo Ironclad A0, all unlocked/all seen, no modifiers, fixed
**Overgrowth → Hive → Glory**. Profile-dependent lobby act selection, discovery
and unlock histories are not part of this initialization profile.

The retained [oracle](../../tools/native_initialization_oracle/README.md) checks
that assembly identity and registers immutable act/encounter/event/relic models.
It runs actual `RelicGrabBag.Populate`, `ActModel.GenerateRooms` and `StandardActMap`
methods in a read-only .NET process. The small shared-Ancient partition prelude
mirrors inspected `RunManager.GenerateRooms` using the actual RNG. The native
RunManager/lobby is not launched; no player profile/save/history is read.

Relevant pinned anchors:

- `RunManager.InitializeNewRun` 100666369; `GenerateRooms` 100666378;
  `ActModel.GenerateRooms` 100681924 and `AddWithoutRepeatingTags` 100681928.
- `GrabBag.GrabIndex` 100695272/100695273: predicate availability check followed by
  rejection draws from the whole remaining weighted bag, not a filtered sampler.
- `StandardActMap` constructor 100694502, `GenerateMap` 100694509,
  `AssignRemainingTypesToRandomPoints` 100694516; repair 100694375.
- `MapPoint.CompareTo` 100694402 / `MapCoord.CompareTo` 100694371;
  `StableShuffle` 100695729; path traversal 100694378 / pruning 100694386.

The [golden fixture](../../tests/fixtures/headless_native_initialization_vectors.json)
retains native pool metadata and 13 seed records, including text and supplementary
Unicode seeds. Every record includes all three room sets, Ancient allocations,
UpFront counters/suffixes and complete Act 1 maps/counters/suffixes. Expected queues
and maps come from actual assembly execution rather than a Python self-comparison.

## Implementation

`generation/room_pools.py` owns immutable native event/encounter/Ancient metadata.
`generation/initialization.py` consumes the existing run's UpFront stream after
shared/player relic bags, partitions shared Ancients for the later acts, then
builds each act's event, weak/normal/elite, boss and Ancient sequences in order.
Tag exclusions persist across weak-to-normal transitions and bag refills.
Rejected eligible-bag draws consume RNG; an entirely ineligible predicate adds no
extra draw before the unfiltered fallback. Singleton Ancient choices still draw.

All three generated room sets are retained in `state.initialization`, with plain
IDs/lists and source-seed validation on restore. Hive/Glory records preserve their
startup consumption; they do not enable later-act gameplay or register placeholder
playable encounters/events. The running Overgrowth encounter/event queues are
separate owned copies bound to their initialization record.

Native event progression now has profile `native_act1_events_all_unlocked_v1`.
Its shuffle contains all **31 IDs**: 13 Overgrowth and 18 shared. The nine later-act
and one disabled shared events remain in queue order but are excluded at ordinary
Act 1 entry through explicit metadata. Missing implementation is not an eligibility
rule. A full-pass unsupported fallback raises without committing cursor/history;
this rare fallback is still outside supported gameplay.

Native maps now retry an occupied second entrance, stable-sort points by column
then row, retain child insertion order during pruning, and apply deterministic
centering, spreading and path straightening before publishing stable node IDs.
These corrections reproduce the actual map, not only its room-count distribution.
The authored RNG/profile path retains its original sampling and layout.

Private run snapshots advance to **v24**; combat snapshots remain **v13**. Earlier
run snapshots reject explicitly. Normal generated entry requires the initialization
record. Plain data and owned streams remain independent of projections/encoders.

## Validation and packaging

- Final focused initialization suite: **25 passed in 4.69 seconds**. Covers the
  13 actual assembly queue/map references, RNG suffixes, malformed/missing startup
  records, profile compatibility, predicate rejection draws and fallback atomicity.
- Broad headless run: **1,791 passed, three failed in 274.72 seconds**. All three
  failures were one parametrized synthetic event-combat test that replaced the
  native event queue. The new seed-bound validation correctly rejected that
  override. The test now explicitly uses the authored fixture backend; its entire
  event-combat file then passed: **29 passed in 8.91 seconds**. Only the test changed
  after the broad run, so unaffected passing results were reused rather than
  rerunning the full suite. No known failure remains from this run.
- The first focused run had **140 passes and six failures in 61.51 seconds**:
  one test helper import and old event-profile/entrance-coordinate assertions.
  They were corrected before the final headless run; no map expectation was
  changed to conceal a discrepancy with the actual assembly vectors.
- Independent semantic review found no blockers. Its 24-test run passed in 4.78
  seconds; 100 native map snapshot roundtrips, five native base-profile cases,
  clone ownership and unsupported fallback checks passed in 17.30 seconds.
- `compileall game tests`, diff whitespace and relevant documentation links pass.
  Validation was scoped to the affected headless engine; the unrelated legacy
  bridge/frozen-evidence failures recorded in the preceding RNG change were not
  rerun or repinned.

Wheel `sts_agent-0.1.0-py3-none-any.whl`, SHA-256
`22fb0708654a32e95cea0ba2dd3247fbd815e74b0e12875146033c31824d2ff8`, was built and
installed in a disposable environment. From outside the checkout with PYTHONPATH
unset, site-packages imports matched all 13 initialization/map references and
restored through 13 Neow selection commands. The authored seed-2 slice completed
in 38 commands with 66 HP. Generated native seed 2/right/rest selected Scroll Boxes,
visited 16 rooms and lost at the boss after nine completed combats and 192 commands;
restore verified throughout. This demonstrates execution, not native combat parity
or a natural Act 1 victory.

Local inspection, build and test outputs: `/private/tmp/sts-headless-native-init`.
Work began around 18:30 UTC. Source inspection, implementation and review overlapped
and were not separately timed. Validation durations are recorded above; packaging
and installed checks finished around 18:48 UTC, with final integration/documentation
around 18:54 UTC (about 24 minutes total). No user readiness wait or live release step was required.

## Remaining scope

Complete whole-run native parity still needs runtime acquisition eligibility and
pool modifiers, combat random-draw/interaction ordering, foreign-character support
for Kaleidoscope and a full native Act 1 acceptance matrix. Lobby act selection,
progress-dependent unlock/discovery changes, higher ascensions and later-act gameplay
remain separate. The [next assignments](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment)
now start with runtime acquisition eligibility; initialization is complete only
for the explicit input profile and reference coverage above.
