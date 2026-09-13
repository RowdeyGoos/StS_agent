# First ordinary headless event — 2026-09-13

Jungle Maze Adventure is implemented for the single-player Ironclad A0 model.
The authored Act 1 route visits it after its third combat, before treasure.
This is native static source inspection and headless execution, not a live event
or multiplayer demonstration.

## Native source

Source: v0.107.1, Steam build 23811903, the existing pinned `sts2.dll` reference.
SHA-256: `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The bounded metadata reader verified this identity and inspected event/command
methods without executing game code or reading profiles, saves or Cloud state.
Scratch outputs were under `/private/tmp/sts-headless-event-native/`; the method
anchors below remain reproducible without retaining that temporary directory.

| Method / metadata token | Verified behavior |
| --- | --- |
| `Overgrowth.get_AllEvents`, 100694203 | Includes Jungle Maze Adventure and Aroma of Chaos among the act's native events. |
| `EventModel.IsAllowed`, 100682486 | Base eligibility is true; Jungle Maze does not override it. Native event selection/no-repeat rules are separate. |
| `JungleMazeAdventure.GenerateInitialOptions`, 100689401 | Exactly Solo Quest and Join Forces, with no initial leave option. Solo is marked as damaging. |
| `JungleMazeAdventure.get_CanonicalVars`, 100689402 | Solo gold 150, Solo damage 18, Join Forces gold 50. Damage uses ValueProp 6. |
| `JungleMazeAdventure.CalculateVars`, 100689403 | Adds independent `NextFloat(-15,15)` variation to each gold amount. |
| `JungleMazeAdventure.DontNeedHelp` async body, 100709130 | Cosmetic effects, then one damage command for 18, then gold gain, then the finished Solo page. No alive guard appears between damage and gold. |
| `JungleMazeAdventure.SafetyInNumbers` async body, 100709132 | Grants the smaller gold amount and finishes; no HP cost. |
| `PlayerCmd.GainGold` async body, 100712431 | Converts decimal gold to integer when updating player gold; inspected flow has no alive guard. |
| `EventOption.ThatDoesDamage`, 100695773; `ThatWillKillPlayerIf`, 100695775 | Records the lethal-choice predicate; does not lock the option. The ordinary option constructor derives locking from an absent callback, which these options have. |

The lethal-choice implementation follows this static ordered control flow:
damage, gold, resolved event, terminal defeat with no further legal actions.
It does not claim observed native death-screen timing or animation behavior.

## Implementation

`events/jungle_maze.py` owns immutable event values and generation, choices,
effects and content validation. `events/catalog.py` explicitly lists implemented
events. `run/events.py` owns entry, exact instance identity, dispatch, departure
and context validation. Pending state contains only definition/instance IDs,
stage, generated gold values and the selected choice; no callbacks are saved.

Payouts are generated once on entry using the owned `event.jungle_maze` stream.
The headless model samples integer 135–164 for Solo and 35–64 for Join Forces,
representing the truncated native float intervals. This is authored integer
sampling, not native float precision, seed or draw-order parity. Choosing or
inspecting an option never rerolls either offer. Entry constructs independently
with a cloned RNG before committing navigation or identity.

Both choices are available at any positive HP, including when Solo is lethal.
After a living choice, only event departure (plus ordinary inventory discards)
is available. There is no invented free leave before choosing. The demo takes
Join Forces. Repeated or stale choices/leave commands reject before mutation.

`MapNode.event_id` identifies the event explicitly and cannot be attached to a
non-event or combat node. The run schema advances to `headless_run_state_v7`,
binding event content, node IDs, allocator and pending data. Earlier private run
schemas reject; combat v4 and accepted public reduced fixtures are unchanged.
The old primitive synthetic event API remains distinct from native content.

## Validation

- Focused event tests: **45 passed in 1.10 s**. Both choices at HP 1/17/18/19/80,
  exact gold, terminal death, no initial leave, repeat/stale rejection, entry
  rollback, native payout intervals, RNG isolation, malformed snapshots, explicit
  map identity and next-combat continuation are covered.
- Compilation passed: `python -m compileall -q game tests`.
- Final affected integration: **851 passed in 17.59 s**, covering headless rules,
  simulation, analysis, engine, headless backends, content, lazy imports, package
  layout and headless CLI.
- Independent review found no blockers. Additional probes exercised 200 seeded
  outcomes / 500 continuation decisions, eight malformed snapshots and six
  illegal/repeated/stale commands. It independently checked lethal option marking
  and the native damage-then-gold call sequence.
- Built and installed wheel SHA-256:
  `7931fdd8e1ece298e0fc34090502dac5418394cf565319c7ff7bfce466c8ef01`.
  Installed commands ran outside the repository with `PYTHONPATH` unset and
  `--verify-restore` at every decision:

| Demo | Result |
| --- | --- |
| Act 1 seed 2, left path, rest | Act complete at 11/94 HP, 236 gold, 124 commands; one Join Forces event, one chest, one shop purchase/removal and five combats. |
| Act 1 seed 2, right path, rest | Defeat at Vantom, 0/104 HP, 288 gold, 114 commands; event, chest and elite path. |
| Default first-slice seed 2 | Slice complete at 66 HP, 127 gold, 38 commands. |

The left-path result is an ordinary seeded win on the restricted authored Act 1
route; no resources or combat outcome were injected. It is not a claim of full
native Act 1 map, event pool, content or RNG fidelity.

The turn began at 15:05:39 UTC. Implementation, review, validation, packaging and
installed smoke runs were complete by 15:13:45 UTC (about 8 minutes 6 seconds).
Review overlapped implementation; no separate review-only duration was recorded.
The final test matrix took 17.59 seconds; documentation/integration followed.
No user wait was required.

Remaining: native event eligibility/weights/no-repeat generation, multiplayer
shared decisions and the rest of the event catalog. The next bounded feature is
Aroma of Chaos with event-owned upgrade/transformation selections; see the
[current assignment](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
