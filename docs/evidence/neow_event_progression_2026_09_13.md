# Neow pickup choices and event progression — 2026-09-13

Generated restricted Ironclad A0 runs can now begin with a mandatory Neow choice.
Golden Pearl grants 150 gold; Nutritious Oyster grants 11 maximum/current HP.
Both use owned relic pickup rules and persist into combat. Generated unknown
rooms now select events from a saved shuffled queue, skipping visited definitions
until a complete exhausted pass permits repetition.

## Usage and declared scope

```sh
sts-headless-play --route overgrowth-generated --ancient neow --seed 2 --rest-choice rest --verify-restore
```

In Python, use `RunEngine.ironclad_act1(ancient_profile="neow_pickups_restricted_v1")`
and choose either `ChooseAncientRelic("golden_pearl")` or
`ChooseAncientRelic("nutritious_oyster")`. The CLI example player chooses Golden
Pearl. Omitting the Ancient option retains the existing post-Ancient fixture.

This fixed two-positive profile is deliberately restricted. It does not implement
native Neow's randomized two-positive/one-curse offers, remaining relics, curse
exclusions, dialogue, modifiers or unlock epochs. The event profile is
`supported_events_all_unlocked_v1`, containing only Jungle Maze Adventure and
Aroma of Chaos; both have unconditional native eligibility. Full Overgrowth/shared
event content and conditional/unlock filtering remain open. The older base-map
fixture retains its explicit event substitutions. Native RNG parity remains open:
all draws still use the owned Python RNG service.

## Pinned source

Bounded static inspection used v0.107.1 / Steam build 23811903 macOS `sts2.dll`,
SHA-256 `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
No assembly execution, live launch, profile, save or history access occurred.
The following metadata tokens identify the source in that pinned assembly:

| Rule | Source token | Finding |
| --- | --- | --- |
| Overgrowth Ancient | `Overgrowth.get_AllAncients`, 100694201 | Neow is the act's Ancient |
| Neow positive options | 100689433, 100689436 | Golden Pearl and Nutritious Oyster are positive rewards |
| Native offer generation | `Neow.GenerateInitialOptions`, 100689443 | Two shuffled eligible positives plus one selected curse, with exclusions and paired alternatives; full algorithm remains unimplemented |
| Golden Pearl amount | `get_CanonicalVars`, 100683664 | 150 gold |
| Golden Pearl pickup | `<AfterObtained>d__6.MoveNext`, 100706692 | Gain the configured gold once |
| Nutritious Oyster amount | `get_CanonicalVars`, 100684068 | 11 maximum HP |
| Nutritious Oyster pickup | `<AfterObtained>d__6.MoveNext`, 100706858 | Gain the configured maximum HP through the native creature operation |
| Event queue generation | `ActModel.GenerateRooms`, 100681924 | Combine act/shared events, apply epoch filters, shuffle once |
| Event selection history | `ActModel.PullNextEvent`, 100681930 | Validate candidate, apply hook, mark the selected event visited |
| Queue indexing | `RoomSet.get_NextEvent`, 100666905 | Index by events-visited cursor modulo pool size |
| Visited/eligibility skipping | `RoomSet.EnsureNextEventIsValid`, 100666909 | Skip visited/ineligible entries for at most one pool-length pass, then allow repetition |
| Cursor advance | `RoomSet.MarkVisited`, 100666904 | Increment on event-room visit |
| Base eligibility | `EventModel.IsAllowed`, 100682486 | True; neither supported event overrides it |

Working extracts were `/private/tmp/sts-headless-ancient-native/initial.json` and
`relics.json`, plus `/private/tmp/sts-headless-map-native/initial.json` and
`helpers.json`. These are scratch files, not portable evidence dependencies.

## Ownership and continuation

- [Ancient start](../../game/headless/run/ancient.py) owns its profile, selection
  and acquired item ID. Its pending state is plain data. Before selection, map
  actions are unavailable; afterward, ordinary map navigation resumes. Repeated
  and unsupported claims reject. Restore never reapplies a pickup. Removal keeps
  the pickup effect and historical ID; that ID cannot belong to another relic or
  a currently owned potion.
- [Event progression](../../game/headless/events/progression.py) owns one shuffled
  queue, cursor and node-to-event assignments. Selection draws no additional RNG.
  With two always-eligible events, the first two visits are unique. Each later
  visit performs the native full-pass fallback before advancing once more.
- Unknown resolution prepares independent copies of RNG, room odds/outcomes and
  event progression. Failed room construction restores all of them and navigation;
  unsupported content does not cause a replacement roll.
- Private run snapshots are **v12**, including Ancient and event progression
  records; private combat remains **v5**. Earlier private run versions reject.
  Restore checks event assignments/cursor against visited room outcomes and the
  declared pool, and checks Ancient pending state and acquisition identity.
  Public reduced fixture protocols and projections are unchanged.

## Validation

- Focused Ancient/generated/pruning/CLI integration: **127 passed in 15.30 s**.
- Broad affected integration: **1,096 passed in 34.97 s**:

  ```sh
  PYTHONPATH=. python -m pytest -q tests/headless tests/simulation tests/analysis tests/engine tests/backends/headless tests/content tests/test_lazy_public_api.py tests/test_package_layout.py tests/cli/test_headless.py
  ```

- Independent review found a snapshot that could bind the Ancient acquisition to
  an owned potion ID. The correction checks potion ownership and adds a regression.
  After that correction, the complete new feature suite passed **32 tests in
  3.45 s**; the reviewer independently passed seven acquisition/history cases.
  The broad suite above predates this narrow validation correction.
- Independent review closed with no remaining blockers. It checked **825 exact
  continuations across 12 synthetic complete Neow routes**, both rewards, queue
  exhaustion/repetition, failed event construction rollback and base-map compatibility.
- Python 3.11 `compileall -q game tests` and `git diff --check` passed.
- Built and installed `sts_agent-0.1.0-py3-none-any.whl` without dependency/index
  access or build isolation. SHA-256:
  `0185acdb84cb77af34a6b1136052f063fcd922100bcd238ad0c8dea03ecdb1c0`.
  Installation took 0.30 s. Build duration was not measured separately.
- Installed checks ran outside the checkout with `PYTHONPATH` unset. Three
  synthetic 16-room routes covered seed 0 left/Ceremonial Beast, seed 2 right/Vantom
  and seed 4 left/The Kin, including both Neow rewards. All **229 continuation checks**
  matched. Import origin was the disposable environment's `site-packages/game`.
  These fixtures force fight victory to validate lifecycle, not policy strength.

Installed normal-inventory CLI results, seed 2, with `--verify-restore`:

| Route | Outcome | Rooms | Final HP | Gold | Commands |
| --- | --- | --- | --- | --- | --- |
| Neow, generated left/rest | Defeat | 12 | 0/111 | 127 | 148 |
| Neow, generated right/rest | Defeat at boss | 16 | 0/94 | 188 | 179 |
| Post-Ancient, generated left/rest | Defeat at boss | 16 | 0/111 | 34 | 191 |
| Authored Act 1 left/rest | Act complete: Vantom | 10 | 11/94 | 236 | 124 |
| First slice, smith | Slice complete | 4 | 66/80 | 127 | 38 |

All installed commands terminated without restore mismatches. Extra starting gold
changes the demo's merchant purchases; it does not guarantee stronger play. No
natural generated-route victory is claimed.

Work began at the recorded 16:37:54 UTC startup check. Source inspection,
implementation and review overlapped; separate phase timings were not recorded.
No user readiness wait was needed. Continue with full Neow offers and additional
reachable event definitions in the [implementation backlog](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
