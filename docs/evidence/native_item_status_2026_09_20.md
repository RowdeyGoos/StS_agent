# Native relic/potion and power comparisons — 2026-09-20

The retained [native capture](native_item_status_2026_09_20.json.gz) contains
**144 cases and 1,272 state boundaries**: 12 scenarios × seeds 0/2/42 × A0/A10 ×
normal/Artifact variants. There are 1,128 action continuations; each is also
replayed from a JSON combat snapshot in Python. The native DLL is pinned to
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18` (0.107.1).

## Interactions

All cases own Belt Buckle and Reptile Trinket. The variant adds Artifact 1 to
both player and enemy and reverses relic order. Potion columns are use order.

| Scenario | Potions | Additional interaction |
| --- | --- | --- |
| flex | Flex, Flex, Strength | Stacked temporary Strength expires before Trinket |
| flex_late | Strength, Flex, Flex | Trinket expires first; Artifact protects a different amount |
| speed | Speed, Dexterity, Fortifier | Frail 2 and initial block 8; temporary Dexterity expires first |
| speed_late | Strength, Speed, Dexterity | Trinket expires before temporary Dexterity |
| binding | Potion of Binding, Vulnerable, Beetle Juice | Enemy debuffs, Artifact and damage multipliers |
| shackles | Shackling, Weak, Powdered Demise | Temporary enemy Strength loss, duration and direct damage |
| ward | Lucky Tonic, Liquid Bronze, Heart of Iron | Tungsten Rod, Buffer, Thorns and Plating |
| replay | Duplicator, Gigantification, Soldier's Stew | Shuriken, Kunai and Ornamental Fan count repeated attacks |
| healing | Blood, Fruit Juice, Regen | Current/max HP and regeneration decrement |
| duration | Ship in a Bottle, Mazaleth's Gift, Radiant Tincture | Next-turn block, Ritual and Radiance |
| fairy | Fairy in a Bottle, Foul, Foul | HP 1, Tungsten Rod and Lizard Tail; Fairy triggers automatically, then Tail during Clamp |
| chaos | Strength, Energy, Distilled Chaos | Last potion autoplays three Defends before Belt Buckle activates |

The matrix uses **27 potion definitions, seven relics and 21 distinct native
power IDs**. Every boundary compares all active player/enemy power IDs and
amounts, including negative Strength, rather than a hand-picked subset of the
powers present. It also compares HP/max HP/block/energy, turn number, next move,
physical card piles, potion slots, relic order and Belt Buckle/Lizard Tail flags.
Final Shuffle, CombatTargets, Niche and MonsterAi counters and next values match.
Unexpected or missing powers fail comparison; duplicate native power IDs reject
until explicit instance comparison is implemented.

## Corrections established by comparison

- Temporary Flex/Speed and Trinket stat loss now uses the existing Artifact-aware
  stat-loss rule. A blocked expiry removes its temporary wrapper while retaining
  the protected stats.
- Reptile Trinket's temporary Strength is an ordinary insertion-ordered power,
  instead of a relic-memory counter that always expired after other powers.
  With Artifact, Flex-first retains 12 Strength; Trinket-first retains 11.
- Belt Buckle activates after the potion and all nested work finish. Last-potion
  Distilled Chaos grants 15 block from three Defends, rather than the erroneous
  21. Subsequent manually played Defend receives the new Dexterity normally.

Independent review also checked the run-owned boundary, which the authored
combat matrix does not invoke. Synchronization now responds to actual inventory
changes instead of applying consumption hooks during a pending selector.
Run-level tests cover Skill Potion and nested Distilled Chaos with JSON replay,
immediate last-potion discard activation, and no Dexterity application after a
lethal potion starts combat ending. These additional cases are source-reviewed
Python regressions, not new native captures.

Private formats advance to **combat v43 / run v64** because old snapshots do not
encode the temporary Trinket power's application order. Old formats reject rather
than silently reconstructing an unknowable order.

## Native execution and limits

`queue_runtime/item_status.cs` uses the existing isolated Godot queue runtime.
It invokes actual `UsePotionAction`, `PlayCardAction`, end-player-turn phases and
`SwitchFromPlayerToEnemySide`, including native enemy execution and next-player
setup. Actions must finish with an empty queue and no outstanding hook tasks.
The native capture took **1.625 seconds to build and 1.907 seconds to execute**.
The runner enforced empty stderr and removed its unique owned user directory.
No live scene, profile, save, history or Cloud data is accessed.

Setup is explicitly authored: Ironclad max HP 80/current HP 41 (Fairy case 1),
energy 10, three potion slots at both ascensions, three Strikes plus eleven
Defends, and one Chomper at 1,000 HP. Initial room/join hooks are omitted; enemy
Artifact is supplied only in the variant. `RunManager` receives an owned state
marker for its in-progress check and the real native AscensionManager. A native
assertion and differing A0/A10 Clamp outcomes verify the difficulty is active.
This is not an ordinary A10 starting inventory or a complete-run setup.

Only the first Clamp turn is executed; the following Screech is recorded as the
next move. No native selector UI, executor frame loop, complete combat-end
lifecycle or native disk-save round trip is claimed. The Python fixture invokes
the production potion entry point with an authored owner and checks combat JSON;
separate run regressions exercise persistent synchronization. Per-monster RNG,
all relic counters, later turns, all power families and the full inventory
cross-product remain outside this matrix.

## Regression evidence

The [fresh baseline report](native_item_status_regressions_2026_09_20.json) binds
13 native runs to the final shared harness. All parsed results exactly match
retained baselines: generated start/route, eight A0/A10 campaign paths,
event-inventory, Architect ending and reward handoff. Original captures and their
source hashes remain unchanged. The event branch implementations are unchanged;
the 9,376-case branch capture is replayed in Python, not claimed as newly executed
in native here.

See `tests/headless/test_native_item_status.py` for the exact census, source
bindings, boundary comparison and JSON continuation checks.

Validation performed:

- Full `tests/headless`: **7,078 passed in 1,675.74 seconds (27m55s)**. Fake
  Merchant took 294.28 seconds and Crystal Sphere 279.15 seconds; native campaign
  JSON replays account for the other longest cases.
- The final explicit discard correction was verified separately with the complete
  potion module: **133 passed in 3.98 seconds**, including its newly added test.
- `tests/backends/headless`: **156 passed in 5.36 seconds**.
- `compileall game tests`, diff/links and independent semantic review passed.
- Independent replay of the 144 new native cases: **2.65 seconds**. Their native
  build/execution times above are separate from Python validation.

No bridge release or live installation was needed. Implementation and review
elapsed times were not separately measured.
