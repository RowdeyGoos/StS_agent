# Generated restricted Act 1 progression — 2026-09-13

The headless game now supports a seeded, full-length Overgrowth route through
15 map rows and a boss. This batch implements native base topology and encounter
queue rules. It does **not** claim complete native map or full-content Act 1 parity.

## Declared scope

Use `RunEngine.ironclad_act1(seed=..., discovery="all_seen")` or:

```sh
sts-headless-play --route overgrowth-generated --seed 2 --path left --rest-choice rest --verify-restore
```

The persisted map profile is `overgrowth_a0_base_restricted_v1`:

- Single-player Ironclad A0, normal starter deck, 80 HP, 99 gold and Burning Blood.
- All encounters assumed seen; first-run/discovery overrides reject as unsupported
  settings rather than reading a real profile. The unimplemented row-zero Ancient
  choice is omitted explicitly.
- Seven generated paths on seven columns, rows 1–15, followed by boss row 16.
  There are at least two entrances; paths can branch and merge, but opposing
  diagonals cannot cross. Every selectable path has 16 room visits if survived.
- Row 1 contains ordinary fights, row 9 treasure and row 15 rest sites. Additional
  special-room assignments follow native base placement constraints and counts.
- Native unknown points are explicitly substituted with visible supported event
  rooms. Jungle Maze Adventure and Aroma of Chaos are sampled with replacement;
  this is a declared content restriction, not native unknown/event generation.
- Cards, items, shops and rewards retain their existing restricted pools. Generated
  runs opt in to stackable Circlet fallback when their elite fruit-relic pool is
  exhausted; authored routes preserve their existing exhaustion rejection.

Native duplicate-path pruning/repair, visual coordinate postprocessing, unknown
outcome rolls, event eligibility/depletion, Ancient choices and native RNG parity
remain open. The generated route is for exercising longer game-logic sequences
while these pieces and the remaining Ironclad content are completed.

## Native source anchors

Bounded static IL inspection used the same pinned v0.107.1 / Steam build 23811903
macOS assembly as the [complete encounter roster](overgrowth_roster_2026_09_13.md):
SHA-256 `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
No game assembly execution, live launch, profile, save or history access occurred.
Metadata tokens below refer to this exact assembly. Local working extracts are in
`/private/tmp/sts-headless-map-native/`; they are not a portable dependency.

| Native method | Token | Implemented rule |
| --- | --- | --- |
| Overgrowth.NumberOfWeakEncounters / BaseNumberOfRooms | 100694206 / 100694207 | Three weak hallway entries; 15 ordinary map rows |
| ActModel.GetNumberOfRooms / GetNumberOfFloors | 100681897 / 100681898 | Single-player room count; Ancient and boss are additional floors |
| StandardActMap constructor / GenerateMap | 100694502 / 100694509 | Seven columns, seven path attempts, second start distinct, boss connections |
| PathGenerate / GenerateNextCoord / HasInvalidCrossover | 100694506–100694508 | Adjacent-column steps and opposing-diagonal exclusion |
| AssignPointTypes | 100694511 | Fixed first/treasure/final-rest rows and ordinary-fight fill |
| AssignRemainingTypesToRandomPoints / GetNextValidPointType | 100694516 / 100694517 | Three shuffled assignment passes and rotation of invalid queued types |
| IsValidPointType and its helpers / static constructor | 100694518–100694525 | No elite/rest below row 6; no random rest from row 13; parent, child and sibling restrictions |
| Overgrowth.GetMapPointTypes / MapPointTypeCounts constructor | 100694219 / 100694434 | Six or seven additional rests, three shops, five A0 elites |
| StandardRandomUnknownCount | 100694433 | Ten to fourteen unknown slots, substituted by this restricted profile |
| Rng.NextGaussianInt | 100667307 | Rounded sine Box–Muller, rejection within bounds; means 7 and 12, deviation 1 |
| ActModel.GenerateRooms | 100681924 | Precompute 15 normal entries, 15 elite entries and one boss |
| AddWithoutRepeatingTags / predicate / SharesTagsWith | 100681928 / 100706369 / 100682426 | Prefer remaining bag entries differing in identity and tags from the preceding entry; fall back if none qualify |
| RoomSet.NextNormalEncounter / NextEliteEncounter / MarkVisited | 100666906 / 100666907 / 100666904 | Separate consumed counts, queue indexing modulo length, no advance for other room kinds |
| ApplyDiscoveryOrderModifications / Overgrowth override | 100681926 / 100694204 | Source-checked but deliberately excluded by all-seen configuration |

The four weak encounters are Fuzzy Wurm, Nibbit, Shrinker and weak Slimes; their
native weak flags are 100690036, 100690153, 100690242 and 100690263. The other twelve
hallway encounters form the normal bag. Tag overrides are Nibbit weak (3), Shrinker
(4), Slimes weak/normal (5), Fuzzy (8), Crawlers (4,8), Flyconid (5,9) and Jaxfruit
(9), from the corresponding `get_Tags` methods. In particular, normal Nibbits does
not override the base empty tag set in this build.

All bags use equal weights and refill only when empty. Tag exclusions span the
weak-to-normal boundary. Each elite bag contains the three elites once; selection
avoids the preceding elite across refills when another candidate exists. Boss
selection is uniform across Vantom, Ceremonial Beast and The Kin in the declared
all-seen setting. Python owned streams preserve repeatability and continuation;
these results do not reproduce native seed-to-map coordinates or native draw order.

## Ownership and continuation

[Map generation](../../game/headless/map/overgrowth.py) produces an immutable
[MapGraph](../../game/headless/map/graph.py), including coordinates, entrances and
its named profile. Authored routes use the same graph API and remain unchanged.
The [encounter progression module](../../game/headless/encounters/progression.py)
owns plain queue/assignment data; no rule is embedded in an encoder or projection.
The run consumes a queue entry only after successful combat construction and binds
that encounter to its visited node. Reads and failed room entries cannot reroll it.

Private run snapshots are **v10**, adding topology metadata, encounter progression
and exact claimed relic item IDs. Private combat remains **v5**. Older private run
formats reject; public reduced fixture schemas are unchanged. Restore validates
queue membership, refill/tag rules, assignments against visited rooms, active and
completed combat counts, map geometry and legal terminal phases. It does not
regenerate the map or consume RNG. Generated success requires boss Act 1 completion.

## Validation

- Final focused generated-route suite: **48 passed in 3.72 s**. Generated plus
  elite-reward checks also passed (88 tests, 4.50 s) before the final boss-phase
  correction; that correction was independently verified with seven focused cases.
- Final affected integration: **1,023 passed in 25.57 s**:

  ```sh
  PYTHONPATH=. python -m pytest -q tests/headless tests/simulation tests/analysis tests/engine tests/backends/headless tests/content tests/test_lazy_public_api.py tests/test_package_layout.py tests/cli/test_headless.py
  ```

  Used the existing Python 3.11 environment. `python -m compileall -q game tests`
  and `git diff --check` passed.
- An additional 1,000 seeded maps passed geometry, queue and ownership validation.
  Six focused synthetic full-length traversals checked every decision and room
  transition against a JSON-restored continuation.
- Independent semantic review closed with no remaining blockers. It exercised
  30 randomized synthetic full routes across **2,017 exact continuation checks**;
  half began with all supported fruit relics owned to force fallback rewards.
  Review found and verified corrections for fabricated premature victory and a
  completed boss incorrectly restored into dead-end route navigation. Both reject
  atomically; a legitimate prelaunch pending boss node still restores and launches.
- Built and installed `sts_agent-0.1.0-py3-none-any.whl` without dependency/index
  access or build isolation. SHA-256:
  `f1304b1ceb6b875ea99c75f3ba05bc24c45485902d7003ebc4c4e6eeb6876749`.
  Build took 0.51 s and installation 0.42 s.
- Outside the checkout with `PYTHONPATH` unset, the installed package completed
  two synthetic 16-room traversals (seed 0 left, seed 1 right) through Ceremonial
  Beast. All **152 continuation checks** matched. Import origin was
  `/private/tmp/sts-headless-vertical-installed/lib/python3.11/site-packages/game/__init__.py`.
  These fixtures force combat victories to test progression, not policy strength.

Installed CLI runs used normal starting inventory, seed 2 and `--verify-restore`:

| Route | Outcome | Rooms visited | Final HP | Gold | Commands |
| --- | --- | --- | --- | --- | --- |
| Generated, left, rest | Defeat | 12 | 0/111 | 154 | 143 |
| Generated, right, rest | Defeat | 8 | 0/80 | 280 | 109 |
| Authored Act 1, left, rest | Act complete: Vantom | 10 | 11/94 | 236 | 124 |
| First slice, smith | Slice complete | 4 | 66/80 | 127 | 38 |

All runs terminated without restore mismatches. The generated natural demos lost;
no natural generated-route victory or native seed parity is claimed. Full-content
coverage and a stronger policy remain separate work.

Recorded work began at 16:02:41 UTC; installed checks were complete at 16:17:35 UTC
(14 min 54 s). Source inspection, implementation and review overlapped; separate
phase durations were not recorded. Test/build/install timings above are measured
command durations; there was no user-readiness wait.

## Remaining assignments

HF-29 is partial until native duplicate-segment pruning and room-count repair are
implemented. HF-30 now covers the A0 encounter queues in all-seen mode; unknown
outcomes, event eligibility/depletion and discovery overrides remain. HF-28 still
needs Ancient starting choices. The next bounded assignment and independent
card/item/event tasks are maintained in the
[implementation backlog](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
