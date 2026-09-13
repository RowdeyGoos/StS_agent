# Aroma of Chaos — 2026-09-13

Aroma of Chaos now resolves permanent upgrade and transformation choices in the
restricted single-player Ironclad A0 run. This evidence covers static native
inspection and headless execution, not a live game demonstration.

## Native source

Source: v0.107.1, Steam build 23811903, the pinned `sts2.dll` reference.
SHA-256: `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The bounded metadata reader inspected these methods without executing native
code or accessing profiles, saves or Cloud state.

| Method / metadata token | Verified behavior |
| --- | --- |
| `Overgrowth.get_AllEvents`, 100694203 | Includes Aroma of Chaos. |
| `AromaOfChaos.GenerateInitialOptions`, 100689233 | Exactly Let Go and Maintain Control, with no initial leave. |
| `AromaOfChaos.LetGo` async body, 100708980 | Selects one transformable deck card, transforms the first result to random when present, then finishes. |
| `AromaOfChaos.MaintainControl` async body, 100708982 | Selects one upgradeable deck card, upgrades the first result when present, then finishes. |
| `CardSelectorPrefs` constructors, 100697916/100697917 | Min and max both equal one; cancellation is false, manual confirmation is false for equal limits. |
| `CardSelectCmd.FromDeckGeneric` async body, 100712310 | No eligible cards returns empty; when manual confirmation is false and candidates do not exceed the minimum, returns candidates automatically. |
| `CardModel.get_IsTransformable`, 100682147 | Master-deck eligibility follows removability; Eternal is excluded. |
| `CardFactory.GetDefaultTransformationOptions`, 100695705 | Chooses the original card pool, with special status/rarity cases falling back to colorless. |
| `CardFactory.GetFilteredTransformationOptions`, 100695708; predicates 100711620/100711625 | Ordinary candidates are common/uncommon/rare and exclude the original definition. |
| `CardFactory.CreateRandomCardForTransform`, 100695706/100695707; `CardTransformation.GetReplacement`, 100696554 | Creates a new card from the chosen candidate; original upgrade level is not transferred. |
| `CardCmd.Transform` async body, 100712181 | Captures original position, resolves replacement before removing original, and inserts at the original index out of combat. Native deck-addition/transform hooks remain outside this restricted implementation. |

## Implementation and scope

`events/aroma_of_chaos.py` owns the choices, eligibility, resolution and saved
state validation. `run/events.py` dispatches `ChooseEventCard` by exact event and
card identity. Pending selectors hold only plain IDs/data. Neither cancellation
nor other commands are legal during the mandatory selector. Zero candidates
finish without mutation; a sole candidate resolves automatically. Completion
exposes the existing `LeaveEvent` continuation.

`run/deck.py::transform_card` validates the pool before drawing from cloned owned
RNG, excludes the original definition and preserves its deck position. The
replacement gets a new owned ID and base upgrade level. Rejected content, stale
selection and draw failures preserve the original deck, allocator and RNG.

The explicit replacement pool contains the 12 implemented nonstarter Ironclad
cards. Source decks may contain those cards and Strike/Defend/Bash. Unsupported
source cards or missing catalog content reject event entry atomically. This does
not implement native full-card pools, status/curse/colorless transformations,
Eternal, deck-addition/transform hooks or native RNG parity.

The authored Act 1 fork offers Jungle Maze on the left and Aroma on the right.
The demo selects Maintain Control and upgrades Bash when eligible. Private run
snapshots advance to v8 and bind event catalog/pool and pending candidate/result
data; v7 and earlier reject. Combat v4 and public reduced fixtures are unchanged.

## Validation

- Focused Aroma plus preserved Maze/elite defeat regression: **35 passed in 1.20 s**.
  Coverage includes duplicate cards, exact upgrades, new base-level transform
  identity, original exclusion, deck position, zero/one/multiple selection,
  no cancel, stale/repeated commands, unsupported content, draw rollback, malformed
  selector/result snapshots and permanent effects in the next combat.
- Compilation passed: `python -m compileall -q game tests`.
- Final affected integration: **885 passed in 18.60 s**, covering headless,
  simulation, analysis, engine, headless backends, content, lazy imports, package
  layout and headless CLI.
- Independent semantic review found no production blockers. Its additional
  probes covered 240 runs / 585 exact continuation decisions, malformed snapshots,
  illegal commands, unsupported content and invalid transformation pools. It
  independently verified native mandatory/automatic selection semantics.
  Two test corrections identified during review were resolved before final
  validation: catalog injection belongs on construction, and the Aroma route
  legitimately wins where the former Maze route lost. Defeat remains explicitly
  tested on the original Maze/elite path.
- Wheel SHA-256:
  `84957d11db604076d9f38fd59ffdcbb71508a983a4a63b005b21370a4a25b67f`.
  Built offline, installed in the existing disposable environment, and executed
  outside the repository with `PYTHONPATH` unset and restore verification:

| Installed demo | Result |
| --- | --- |
| Act 1 seed 2, right path, rest | Act complete, 12/104 HP, 332 gold, 118 commands; Aroma upgrades Bash, chest, elite and Vantom. |
| Act 1 seed 2, left path, rest | Act complete, 11/94 HP, 236 gold, 124 commands; Maze, chest, shop and Vantom. |
| Default first slice seed 2 | Slice complete, 66 HP, 127 gold, 38 commands. |
| Direct Let Go → combat | Upgraded Strike `run.card.1` becomes base Impervious `run.card.3` at the same index; five decisions replay exactly after JSON restore. |

These are seeded results on an authored five-fight route, not full native Act 1
fidelity or full-game victory. The initial direct smoke script incorrectly guessed
event ID 1; it rejected without mutation. The corrected check selects observed
legal commands and passes, with no implementation change required.

The turn started at 15:16:07 UTC. Implementation, independent review, validation
and installed execution were complete by 15:27:03 UTC (10 minutes 56 seconds).
Review overlapped implementation; separate implementation/review durations were
not recorded. Final integration tests took 18.60 seconds; wheel build/install
commands took under one second combined. Documentation and Git integration
followed. No user wait was required.

The next bounded assignment is a second source-verified Overgrowth elite; see the
[current implementation queue](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
