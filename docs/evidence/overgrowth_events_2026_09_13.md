# Tablet of Truth and Morphic Grove — 2026-09-13

The generated restricted Overgrowth route now includes Tablet of Truth and Morphic
Grove, bringing its event pool to four definitions. Both have complete option
flows within the implemented card/power scope. Morphic Grove also supplies the
first conditional event-eligibility rule, with saved entry conditions for replay.

## Behavior

- **Tablet of Truth:** Smash heals 20 HP and finishes. Decipher pays maximum HP
  costs of 3, 6, 12 and 24 for one automatic random upgrade per step. Give Up is
  available after each of those steps. The fifth decipher costs current maximum
  HP minus one and upgrades all remaining upgradable cards. Current HP is capped
  at the new maximum. A lethal cost leaves maximum HP at 1, kills the player and
  gives no upgrade. Empty/fully upgraded decks still pay, without consuming upgrade
  RNG. The fifth step at maximum HP 1 costs zero and remains legal.
- **Morphic Grove:** normally eligible with at least 100 gold and two transformable
  deck cards. Loner grants 5 maximum/current HP. Group spends all current gold,
  then transforms two selected originals. Both cards are selected before any result
  is revealed; transformations preserve positions, allocate fresh identities and
  exclude each original definition. At most two candidates resolve automatically.
  That includes zero/one-card states reachable through native exhausted-pool fallback.
- **Conditional queue:** event entry captures plain gold/card-count conditions.
  Selection skips visited or ineligible candidates for at most one full pass, then
  permits the fallback even if ineligible. Restore replays queue selection against
  those historical conditions, not the player's resources after the event.

`ChooseEventCard` now also nominates Morphic's two distinct originals, retaining
plain pending selection data between nominations. No transformation occurs after
just the first nomination. Preparing the second replacement on an independent
state copy prevents partial deck/allocator/RNG mutation if either transform fails.
This models the selected gameplay sequence, not native screen toggling or preview UI.

Shared transformation pool/source validation moved into
[events/transformation.py](../../game/headless/events/transformation.py), reused by
Aroma and Morphic. The pool remains the 12 implemented nonstarter Ironclad cards;
other transformation pools, Eternal and item/card hooks remain unimplemented.
No callback closures, projections, encoders or bridge changes were introduced.

## Pinned source

Static inspection used v0.107.1 / Steam build 23811903 macOS `sts2.dll`, SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
No game assembly execution, live launch, profile, save or history access occurred.
Metadata tokens below refer to that exact assembly:

| Rule | Source | Token |
| --- | --- | --- |
| Both events in the act pool | `Overgrowth.get_AllEvents` | 100694203 |
| Tablet initial choices/amounts | `GenerateInitialOptions`, `get_CanonicalVars` | 100689627, 100689628 |
| Repeated costs | `TabletOfTruth.GetDecipherCost` | 100689631 |
| Repeated page/count and completion | `<Decipher>d__10.MoveNext` | 100709293 |
| HP loss, lethal branch, random/all upgrade | `<LoseMaxHpAndUpgrade>d__13.MoveNext` | 100709295 |
| Smash healing | `<Smash>d__9.MoveNext` | 100709297 |
| Native max-HP/current-HP cap | `CreatureCmd.<LoseMaxHp>d__23.MoveNext` | 100712389 |
| Morphic HP amount | `MorphicGrove.get_CanonicalVars` | 100689422 |
| Morphic gold/card-count entry predicate | `<IsAllowed>b__5_0`, `<IsAllowed>b__5_1` | 100709146, 100709147 |
| Spend all gold, select two, then transform | `<Group>d__8.MoveNext` | 100709148 |
| Loner maximum-HP gain | `<Loner>d__7.MoveNext` | 100709150 |
| Master-deck transform/removal eligibility | `CardModel.get_IsTransformable`, `get_IsRemovable` | 100682147, 100682146 |
| Automatic small/empty transformation selections | `CardSelectCmd.<FromDeckForTransformation>...MoveNext` | 100712306 |
| Native selected-card collection | `NDeckTransformSelectScreen.OnCardClicked`, `CompleteSelection` | 100675413, 100675418 |

The native selector returns empty/all candidates when their count is at most the
required minimum without a manual-confirmation flag. Morphic waits for the full
selection, materializes it, then transforms that enumeration. The screen collects
selected cards in a HashSet, without sorting by master-deck position.

Source extracts in `/private/tmp/sts-headless-event-batch-native/` include
`simple.json`, `morphic.txt`, `helpers.json`, `losemaxhp.txt` and reviewer selector
extracts. These are working scratch files, not portable evidence dependencies.

## Profiles and compatibility

- Default generated event profile: `supported_events_all_unlocked_v2`, now Jungle
  Maze Adventure, Aroma of Chaos, Morphic Grove and Tablet of Truth. Unlock epochs
  remain explicitly all unlocked; native RNG parity remains open.
- Authored routes and the earlier base-map fixture keep their two-event pools.
  Neow's optional two-positive profile is unchanged.
- Private run snapshots are **v13**, including event entry conditions and each
  event's complete pending/result data. Private combat stays **v5**. Older private
  run versions reject; public reduced fixture protocols remain unchanged.
- The demo chooses Smash/Loner. Other branches remain legal through direct commands.
  Full Neow offers and remaining Overgrowth/shared events remain backlog work.

## Validation

- Existing affected Aroma/Ancient/pruning/generated checks: **156 passed in 15.65 s**.
- Initial new feature suite: **37 passed in 2.11 s**.
- Broad affected integration: **1,134 passed in 38.65 s** using Python 3.11:

  ```sh
  PYTHONPATH=. python -m pytest -q tests/headless tests/simulation tests/analysis tests/engine tests/backends/headless tests/content tests/test_lazy_public_api.py tests/test_package_layout.py tests/cli/test_headless.py
  ```

- Independent review found a resolved Morphic snapshot could forge a transform
  into its source definition. The correction saves original definitions and
  validates exclusion/current-original consistency. After correction, **38 new
  feature tests passed in 2.19 s**; the reviewer independently passed them in
  2.13 s. The broad result above predates that narrow validation correction.
- Review closed with no remaining blockers. Additional **96 exact continuations**
  covered 20 Morphic runs with different deck sizes/selection orders and 14 Tablet
  runs across lethal, low-current-HP and zero-cost-fifth-step boundaries. Source
  semantics, fixed-count selection and eligibility fallback were independently checked.
- `compileall -q game tests`, `git diff --check` and local documentation-link checks
  passed. Built a wheel without dependencies/index/build isolation in **0.47 s**,
  installed it into the disposable environment in **0.34 s**. Wheel SHA-256:
  `72273e79fb47d7df5bead2232601dc26655bd531975cfe66f0d45e845f1f5c60`.
- Outside the checkout, with `PYTHONPATH` unset and imports from installed
  `site-packages/game`, four event branch-to-first-combat traces passed **18 exact
  continuation checks**. Three synthetic complete 16-room runs covered Ceremonial
  Beast, Vantom and The Kin with **228 exact continuations**, including both new
  event definitions and both Neow rewards. Those traces force fight victory and
  only establish lifecycle coverage.

## Installed normal-play results

All used seed 2, rest preference and `--verify-restore`:

| Route | Outcome | Rooms | HP | Gold | Commands |
| --- | --- | --- | --- | --- | --- |
| Generated + Neow, right | Act complete: Vantom | 16 | 7/94 | 232 | 186 |
| Generated + Neow, left | Defeat | 12 | 0/111 | 127 | 148 |
| Authored Act 1, left | Act complete: Vantom | 10 | 11/94 | 236 | 124 |

The generated right-path completion is a normal starter-inventory demo run with
Golden Pearl and legal commands, without forced combat outcomes. It demonstrates
one complete generated restricted Act 1 run, not full native content/fidelity.

```sh
sts-headless-play --route overgrowth-generated --ancient neow --seed 2 --path right --rest-choice rest --verify-restore
```

Work started at **16:53:33 UTC**. Source inspection, implementation and review
were interleaved; separate phase durations were not recorded. Test/build/install
durations above are measured. No user readiness wait was needed. Next work:
Whispering Hollow, owned multiple-potion rewards, Wellspring and further Neow
content in the [implementation backlog](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
