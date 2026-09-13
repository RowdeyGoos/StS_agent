# Map pruning and unknown-room resolution — 2026-09-13

The default generated Overgrowth route now prunes duplicate path segments, repairs
special-room counts and resolves unknown map points on entry through native base
odds. The map keeps unresolved points unknown. Room outcomes, odds, encounter
assignments and the room's pending decisions survive exact JSON continuation.

## Usage and scope

```sh
sts-headless-play --route overgrowth-generated --seed 2 --path left --rest-choice rest --verify-restore
```

`RunEngine.ironclad_act1()` now uses `overgrowth_a0_pruned_restricted_v2`. The earlier
`overgrowth_a0_base_restricted_v1` fixture remains selectable with `map_profile=`;
its earlier tests retain that profile explicitly. Authored routes are unchanged.
All profiles remain single-player Ironclad A0 with declared all-seen discovery,
restricted event/card/item/shop pools and no Ancient starting choice. Full event
eligibility/depletion, tutorial/discovery overrides, room-modifying relics, native
RNG parity and visual coordinate postprocessing remain open.

## Source identity

Bounded static IL inspection used the pinned v0.107.1 / Steam build 23811903 macOS
assembly, SHA-256:
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
No assembly execution, live launch, profile, save or history access occurred.
Native metadata tokens below refer to that assembly. Local working extracts are
in `/private/tmp/sts-headless-map-native/`, including `helpers.json`, `unknown.json`,
`point.json`, `pruning-a.txt`, `pruning-b.txt` and `unknown-rules.txt`. These are
scratch material, not portable evidence dependencies.

## Pruning and repair

[The pruning module](../../game/headless/map/pruning.py) operates on the generator's
owned coordinate graph before publishing an immutable map. It preserves surviving
node identities and coordinates; it does not rebuild a route after entry.

- `PruneAndRepair` (100694373) runs at most three prune/repair rounds, stopping when
  repair makes no changes. Duplicate pruning uses the native 50-change bound
  (`PruneDuplicateSegments`, 100694376).
- Path enumeration and segment grouping (100694377–100694382) compare segments
  beginning at a branch or the temporary row-zero root and ending at a merge.
  Segments need at least three points. Keys include endpoint coordinates and the
  entire room-type sequence; the root key deliberately omits its column.
- Interior overlap disqualifies alternatives (100694383/100694384). Shared endpoints
  are permitted. Identical segments reached through different longer paths dedupe.
- `PrunePaths` / `PruneAllButLast` (100694386/100694387) shuffle equivalent alternatives
  and retain at least one. `PruneSegment` (100694388 and lambdas 100711242,
  100711243, 100711247, 100711248) protects branching/merging nodes, indispensable
  parent/child links and unrelated outgoing routes. Removal updates both sides of
  every edge (`RemovePoint`, 100694389).
- If vertices cannot be removed, the native edge-breaking fallback can remove a
  redundant branch-to-merge edge while retaining both vertices (100694392/100694393).
- Repair runs in shop, elite, rest, unknown order (100694374/100694375), replacing
  only modifiable ordinary combat points and respecting the same placement rules.
  Fixed row-one fights cannot be replaced (100711239 and 100711281). The targets
  are three shops, five elites, the sampled six/seven rests and ten–fourteen
  unknowns. The rest count includes surviving fixed final-rest points, matching
  native counting rather than adding a second repair allowance.

Pruning may reduce the initial entrances to one; every surviving path still visits
rows 1–15 and the boss on row 16. The temporary row-zero root participates only in
pruning comparisons; it does not grant or simulate an Ancient choice. Native map
centering, spreading and straightening are not implemented. Deterministic Python
iteration/sampling does not claim native seed-to-layout coordinates.

## Unknown outcomes

[Unknown-room state](../../game/headless/run/unknown_rooms.py) owns odds and resolved
outcomes separately from the immutable map. Before entry, unknown markers contain
neither an event ID nor a preselected combat. A visited room can be inspected with
`room_node(state, graph, node_id)` without changing the original marker.

`UnknownMapPointOdds` constructor and `Roll` (100667556/100667558) establish:

| Outcome | Base probability | Unselected update |
| --- | --- | --- |
| Ordinary combat | 10% | Add 10 percentage points |
| Elite | Disabled, represented by -1 | Continue native negative accumulation |
| Treasure | 2% | Add 2 percentage points |
| Shop | 3% | Add 3 percentage points unless blocked |
| Event | Remaining roll space | No independent stored odds |

The roll accumulates enabled probabilities in combat/elite/treasure/shop order,
uses the native inclusive cumulative boundary and falls through to event.
Probabilities are not renormalized when a type is excluded. The selected type
resets to its base; other allowed types increase by their base. Single-precision
rounding is preserved for the draw, cumulative sum and each increment. JSON object
key ordering does not affect selection. Negative elite values remain disabled.

`RunManager.BuildRoomTypeBlacklist` (100666374, predicate 100700654) excludes shop
when the previous actual room was a shop, or when all next map markers are shops.
Its probability neither participates in that roll nor increases. First-run special
cases and hook modifiers were inspected as boundaries but are outside all-seen A0
base behavior. `RollRoomTypeFor` is 100666386.

Unknown combat consumes the existing normal encounter queue. Treasure/shop/event
outcomes enter their existing handlers. Event identity is chosen only after the
room resolves to an event, from the declared supported pool with replacement;
native event eligibility/depletion remains a separate task.

Outcome preparation copies RNG and unknown state. If construction fails, the run
restores navigation, RNG, odds and outcome identity together. Public direct
`choose_node` may retain a selected pending room, and that explicit boundary also
restores correctly. Reads and rejected actions do not consume a roll.

Private run snapshots are now **v11**; private combat remains **v5**. Older private
run formats reject, while public reduced fixture schemas are unchanged. Restore
checks outcome membership against visited unknown points, room legality/blacklists,
replayed odds updates, effective pending-room identity and encounter history.

## Validation

- New focused suite: **42 passed in 6.51 s**, covering pruning diamonds, distinct
  sequences, overlap/edge fallback, repair, ten reproducible seeded maps, native
  odds boundaries/accumulation, all four room handlers, transactional failures,
  six complete synthetic routes and malformed snapshots.
- Existing generated/base fixture suite: **48 passed in 4.11 s**. Earlier affected
  headless/CLI checks passed **587 tests in 18.61 s** before final integration.
- Final affected integration: **1,065 passed in 32.66 s**:

  ```sh
  PYTHONPATH=. python -m pytest -q tests/headless tests/simulation tests/analysis tests/engine tests/backends/headless tests/content tests/test_lazy_public_api.py tests/test_package_layout.py tests/cli/test_headless.py
  ```

  Used the existing Python 3.11 environment. `python -m compileall -q game tests`
  and `git diff --check` passed.
- Independent semantic review found no blockers. It checked **500 seeded maps**
  without topology/pruning failures and **40 synthetic complete routes** across
  **2,664 exact continuations**: 72 event, 18 combat, seven shop and seven treasure
  unknown outcomes. It also verified failed construction rollback, pending unknown
  selection, malformed-state rejection and independent restored odds dictionaries.
- Built and installed `sts_agent-0.1.0-py3-none-any.whl` without dependency/index
  access or build isolation. SHA-256:
  `14c27877412e0a161c673da6ece0175e5a2767e9c918f269a2cf7ac028201be3`.
  Build took 0.50 s and installation 0.39 s.
- Outside the checkout with `PYTHONPATH` unset, three installed synthetic 16-room
  runs completed: seed 0 left/Ceremonial Beast, seed 2 right/Vantom and seed 4
  left/The Kin. All **225 continuation checks** matched. Import origin was
  `/private/tmp/sts-headless-vertical-installed/lib/python3.11/site-packages/game/__init__.py`.
  These fixtures force combat victory to validate progression, not policy strength.

Installed CLI results with normal inventory, seed 2 and `--verify-restore`:

| Route | Outcome | Rooms | Final HP | Gold | Commands |
| --- | --- | --- | --- | --- | --- |
| Generated, left, rest | Defeat at boss | 16 | 0/111 | 34 | 191 |
| Generated, right, rest | Defeat at boss | 16 | 0/94 | 188 | 177 |
| Authored Act 1, left, rest | Act complete: Vantom | 10 | 11/94 | 236 | 124 |
| First slice, smith | Slice complete | 4 | 66/80 | 127 | 38 |

All installed runs terminated without restore mismatches. The normal generated
policies reached the boss and lost; no natural generated-route victory is claimed.
Work began at the recorded 16:20:18 UTC startup check. Source inspection,
implementation and independent review overlapped; separate phase timers were not
recorded. Test/build/install durations above are measured; no user readiness wait
was needed.

The next bounded batch is an Ancient starting choice and native event-pool
progression. Other Ironclad card/item/reward/shop/event definitions remain tracked
in the [implementation backlog](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
