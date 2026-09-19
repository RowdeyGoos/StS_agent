# Defect cards — 2026-09-19

## Scope and implementation

The cumulative `DEFECT_CARDS` catalog extends `NECROBINDER_CARDS` with all 80
ordinary solo Defect cards at both upgrade levels, four starters and Fuel (85
definitions). Acquired cards execute under the existing Ironclad owner. Biased
Cognition and Quadcast are inventoried Ancient exclusions. All 320 ordinary foreign
cards now have explicit implementations; native Kaleidoscope/Splash acquisition
remains the next assignment. Default acquisition is still gated. Playable foreign
characters, higher ascensions and native full-run parity remain separate work.

Definitions and immutable operations live beside their content in `cards/defect.py`,
`cards/defect_effects.py` and `cards/orb_effects.py`. `core/orbs.py` owns physical orb
IDs, active order, slot capacity and lifetime values. `powers/defect.py` connects
Focus, delayed effects, replays and Status generation to existing ordered hooks.
Lightning, Frost, Dark, Plasma and Glass have distinct passive and evoke behavior.
Ironclad starts without slots and gains one on his first channel. Random orb
creation uses the dedicated saved native OrbGeneration stream; attacks use the
existing CombatTargets stream. Removed instances remain in channel history for
captured callbacks and Voltaic. Confirmed death clears active orbs and capacity.

Genetic Algorithm grows the physical card's permanent block and synchronizes its
matching run-deck ID after an action. Orb/card continuations extend the existing
owned context/task receipts and plain-data choices. Private formats advance to
combat v23 and run v35; older versions reject. No combat projection or RL encoding
was added, and the default catalog remains unchanged.

## Native reference and evidence boundary

Target: **0.107.1 / Steam build 23811903**. Pinned `sts2.dll` SHA-256:
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.

The existing native combat oracle accepts `defect` and reproduces
[`headless_native_defect_vectors.json`](../../tests/fixtures/headless_native_defect_vectors.json).
Its 87 rows include the two Ancient exclusions. Mutable native card construction
and actual upgrade methods supply costs, targeting, keywords, generation eligibility
and dynamic variables. A fresh oracle invocation reproduced the retained JSON
exactly. The oracle build completed without warnings or errors.

Behavior recipes were inspected in the pinned assembly's decompiled card, power,
orb, energy-cost and creature-death commands. Python regressions exercise those
recipes. This is direct native metadata evidence plus source-backed simulated
behavior, **not native card/turn execution or full-run parity evidence**. No live
game, profile, save, history or Cloud access was used.

## Review corrections

Independent semantic review found and rechecked these concrete issues:

- Legacy exact-search clones now own/copy the orb RNG and include it in state keys.
- Stacking Feral preserves its usage counter; first application includes already
  started zero-cost attacks.
- Rocket Punch uses a local absolute cost setter lasting until play. Tangled and
  Borrowed Time still apply, Scrape sees the local zero, later local setters retain
  chronological precedence, and turn cleanup expires the corresponding relative
  baselines. Snapshots reject missing ambiguous setter order.
- Confirmed owner death clears the active orb queue/capacity after Fairy/Tail have
  had their opportunity. Revival preserves orbs.
- Doom and Hailstorm preserve application order across the side-end boundary.
  Snapshots reject missing ambiguous listener order, which otherwise could change
  the winner after restoration.

The initial focused run also exposed incorrect Flak target dispatch and Scrape
continuation API assumptions; both were corrected before broad validation. A Glass
kill followed by Horn/Stratagem now has a retained JSON continuation regression.
No unresolved findings remain in the bounded independent review.

## Validation

- Native inventory: 87 reproduced rows; all 85 implemented definitions checked at
  both levels. Each of the 80 ordinary cards exercises choices, JSON continuation
  and three turns at both levels.
- Focused families before final review corrections: **943 passed in 99.19 seconds**.
- Final compatibility: **362 passed in 80.59 seconds** across simulation, engine,
  conformance, data and brute-force tests.
- After stricter ordering validation: **12 focused cases passed in 0.80 seconds**;
  affected Snecko/Slither/Flatten/cost cases **10 passed in 0.91 seconds**. Independent
  final recheck: **8 passed in 0.28 seconds**.
- Installed Defect/runtime-eligibility suite: **332 passed in 35.03 seconds**;
  one subsequently retained Glass/Horn continuation passed against source and the
  installed package. The final wheel differs only by an EOF whitespace cleanup
  from the wheel used for the 332-case suite and smoke routes.
- Full headless suite: **3,676 passed in 434.39 seconds (7m14s)**. This run began
  before the final two ordering-validation guards; the focused checks and installed
  suite above cover those corrections. The two forged-order cases and Glass/Horn
  case added afterward bring the retained headless case count to **3,679**.
- `compileall game tests`, whitespace review, documentation file links and the guide
  example passed.

## Package and operational checks

Final wheel: `sts_agent-0.1.0-py3-none-any.whl`, SHA-256
`0feb5158ea0aa5e01f284553393f83b7e1b16aa8e399ca0088389b724b69ae0c`.
The disposable package is in `/private/tmp/sts-defect-package/`; installed
verification uses `/private/tmp/sts-defect-installed/`. All **182** headless Python
modules match between source, wheel and installed files. Tests imported the
installed package from outside the checkout with `PYTHONPATH` removed.

Installed `sts-headless-play` outcomes, with restoration verified after every command:

| Route | Outcome |
| --- | --- |
| `first-slice --seed 2 --rest-choice smith --verify-restore` | Slice complete; 38 commands, four rooms, two combats, 66 HP. |
| `overgrowth-generated --ancient neow --seed 2 --path right --rest-choice rest --verify-restore` | Defeat; 198 commands, 16 rooms, nine combats, 0 HP. |

These are deterministic compatibility smoke routes. Their default catalog remains
restricted; neither establishes complete foreign acquisition or native parity.

## Timing

Work began at 11:24:12 UTC. Implementation, source inspection, independent review
and validation overlapped; their separate elapsed times were not measured. No
user readiness wait was required. The oracle build took 1.09 seconds. Compatibility
ran in 80.59 seconds, and the installed suite in 35.03 seconds. Final broad-suite
and completion timings are recorded below.

Validation and package preparation finished at 12:19:34 UTC, **55m22s elapsed**.
The broad headless run took 434.39 seconds; the subsequently added Glass/Horn case
passed in 0.30 seconds from source and 0.27 seconds installed. Git integration time
is not included in that elapsed figure.
