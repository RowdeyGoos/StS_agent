# Focused interaction and monster verification — 2026-09-20

The focused pass adds **14 native scenarios / 156 observed boundaries**, with
one seed and an appropriate ascension per behavior. It fixes concrete hook and
move-selection mismatches without a new seed × ascension × inventory matrix.
The [capture](native_focused_behavior_2026_09_20.json.gz) retains runtime/source
identities, results, timing and successful isolated-user-directory removal.

## Cases and corrections

| Named behavior | Native evidence and headless result |
| --- | --- |
| Tender before Ritual / Ritual before Tender | Artifact blocks the first Strength loss. Two card plays earn two stat refunds. Ruined Helmet doubles whichever positive Strength application occurs first: final Strength 4 versus 3. Refunds now use ordered power hooks and ordinary power application. |
| Regen before late Disintegration | Starting at 2 HP, Regen 4 heals before Disintegration 4; Tungsten Rod reduces damage to 3, leaving 3 HP. Existing timing matches. |
| The Lost / The Forgotten, with or without a surviving enemy | First steal is blocked by Artifact; second loses 2. Native Possess callbacks refund actual loss while active, with Ruined Helmet doubling Strength. Ending suppresses the refund. Both headless raw-stat refunds are corrected. |
| Ovicopter with three eggs | Authored Tenderizer and three Nibbles use real encounter slot order. One egg dies to Doom at enemy-side end. Native next-player setup chooses Lay Eggs. Headless now delays its roster-dependent roll until that same boundary. |
| Living Shield with Turret Operator | Turret dies to Doom after acting. Shield switches from Shield Slam to Smash; the subsequent Smash deals 16 and grants 3 Strength at A0. Headless now delays its roll. |
| Flail Knight, Hunter Killer, Sludge Spinner | Twenty actual moves per monster at A10 compare damage, active powers, next moves, repeat restrictions and RNG. All match. |
| Exoskeleton | Twenty A10 moves from the native first-slot opening compare Skitter/Mandibles/Enrage, Strength and RNG; Hard to Kill is present. Damage-cap behavior remains covered by the existing focused Hive regression. |
| Bowlbug Rock | Twenty A10 moves alternate authored fully blocked and unblocked attacks. Native Imbalanced/Stunned transitions match Headbutt/Dizzy, including recovery. |

All new cases use seed 2; the five move traces use A10 and the interaction/roster
cases A0. These are deliberate mechanism probes, not an ascension census.
The native fixture freshly reruns the previous **216 item/conditional cases**;
all parsed rows are identical to their retained captures.

## Continuations and shared rules

`DeferredMoveEnemy` factors Fabricator's existing owned pending-roll mechanism
for Ovicopter and Living Shield. The pending roll belongs to a completed living
actor in the active enemy continuation. Death clears it. A paused later selector
must neither invent nor drop it. Private schemas are **combat v44 / run v65**;
older records reject rather than inventing the new monster fields.

The new test module has 14 native trace cases and three local adversarial cases:
a later ally's death across a Centennial Puzzle/Stratagem selector, the actor's
own death to Thorns before that selector, and rejection of old/unowned records.
Each native step runs from the original state and a JSON-restored state, and
compares exact subsequent snapshots. Native comparisons include resources, all
four card piles, potion slots, Ruined Helmet memory, active power amounts,
next moves and Shuffle/CombatTargets/Niche/MonsterAi counters and next values.

The extra actor-death probe caught an inherited validator assumption: an actor
that died before advancing had a completed action but no pending roll. The
validator now requires a roll only from a living actor, and restore succeeds.

## RNG source audit

The pinned native assembly is `sts2.dll`
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18` (0.107.1).
Inspection of its decompiled monster models found one `MonsterModel.Rng`
consumer: `ToughEgg.SetupSkins`, selecting an egg skin. Other unseeded monster
calls are cosmetic skin/dialog/shake work. Gameplay move rolls use
`MonsterModel.RollMove` → `RunRng.MonsterAi`; Fabricator spawn choice also uses
MonsterAi, Tough Egg hatch HP uses Niche, and Hopper theft uses
CombatCardGeneration. No additional per-monster gameplay RNG state is needed
for this pinned roster. This source finding does not certify all shared-stream
callers or later game versions.

## Evidence boundaries

- The five monster traces invoke actual native `PerformMove` and the next move
  roll. They do not execute 20 complete turns; status decay and player phases
  are intentionally outside these traces.
- Tender and Disintegration execute native queued card plays where applicable,
  then both player-end phases. They stop before enemy-side work.
- The two roster cases execute the full native enemy side and next-player setup,
  including actual Doom death dispatch. Living power amounts are compared. Dead
  stable headless slots retain inert historical status data, whereas native
  removal clears powers; dead-slot power cleanup parity is **not** claimed.
  Dead HP, identity and move are retained in the comparison.
- Possess cases execute actual native steals and `AfterDeath`/PowerCmd under an
  authored HP-zero/ending premise. They establish callback behavior, not the
  full death dispatcher or final combat cleanup.
- High HP prevents unrelated defeats in move/roster fixtures. The Disintegration
  case specifically uses low HP. No live UI, profiles, saves or Cloud are read.
- Arbitrary inventory combinations and every encounter branch/seed remain
  outside this bounded coverage. Add further cases for concrete uncovered
  behavior rather than duplicating these cases across parameter products.

## Validation

Final native item capture: build **1.633 s**, execution **1.936 s**. A fresh
36-case `enemy-turn` run checks the changed shared fixture dispatcher against
its unchanged retained result: build **1.635 s**, execution **1.595 s**. The
capture's `sharedDispatcherRegression` records the baseline and result hashes;
historical captures retain their original identities. No unrelated campaign
matrix was rerun or repinned.

Independent semantic review covered the deferred-roll ownership, ordered stat
refunds, native fixture boundaries and tombstone limitation. The affected Python
integration run passed **1,237 tests in 34.68 s** before the final actor-death
validator correction. Final affected validation is recorded below.

After that correction, the new focused module plus the complete existing Hive
and Glory regressions passed **507 tests in 20.50 s**. The independent reviewer
reran four affected Shield/Fabricator ownership cases in **0.27 s** and found no
remaining blocker. Compile checks and `git diff --check` passed. The full
headless suite was not rerun; affected gameplay, native evidence bindings and
headless backend consumers were selected explicitly.


## Death-lifecycle follow-up

The [new capture](native_death_fidelity_2026_09_20.json.gz) adds **ten named native
cases / 32 observed boundaries**, all seed 2 / A0, and freshly reruns the prior
230 rows with identical parsed results. It uses the same pinned native assembly.
The original capture above keeps its original source identity and limitations.

| Cases | Actual native behavior and correction |
| --- | --- |
| Lost / Forgotten × surviving enemy / ending (four) | Two real steals, first blocked by Artifact, then actual `CreatureCmd.Kill`. With a survivor, actual loss is refunded through PowerCmd, Ruined Helmet doubles Strength, and Gremlin Horn draws/grants energy. At ending, both the refund and Horn are suppressed. These validate the existing refund fix through the death dispatcher. |
| Eye With Teeth / Parafright (two) | Actual Kill, actual revival move, then a full enemy side through next-player setup. Authored Poison, Doom and Weak clear; Artifact, Illusion, Minion and Enfeebling Touch survive death. The temporary penalty expires at its normal end-turn boundary. Headless now shares this cleanup rule. |
| Sic ’Em against Parafright / Test Subject (two) | Actual queued Flatten with Osty 5/5 and Sic ’Em 3 kills the target. The earned summon raises Osty to 8/8 even though revival cleanup removes the mark. Headless captures the earned amount before cleanup. |
| Sic ’Em against the last Chomper / Spiny Toad (two) | Final lethal Flatten leaves living Osty at 5/8. Authored Thorns 5 on Spiny Toad instead kills Osty during the hit: the earned summon sets its maximum to 3 while HP stays zero. Headless now processes this earned summon at ending, with native healing suppression. |

Native Illusion preserves buffs and `ITemporaryPower` during death cleanup;
negative Strength is still a native buff. The headless temporary-Strength wrappers
retain their normal expiry semantics. The source hook is combat-wide; this probe
specifically certifies cleanup on the two reviving illusion creatures. Permanent
dead stable slots remain inert historical records; the comparison clears their
projected powers only, while comparing reviving creatures' retained powers.

Each native step compares player resources, piles, relevant memory, target state
and powers, plus JSON-restored execution. Four RNG counters and next values match.
Osty HP/max HP and the native play pile are captured explicitly in pet cases.
At terminal card boundaries, native suppresses result-pile movement and retains
Flatten in play; headless canonically completes it into discard. Tests assert
both forms explicitly, following the existing terminal attack-hook convention.
They do not claim terminal pile equality.

One additional local regression combines a lethal Sic ’Em hit on Test Subject
with Gremlin Horn and a Stratagem shuffle selector. The summon settles before
the selector, the removed mark is not reread, and JSON restore/resume neither
loses nor duplicates the summon. No new continuation fields or schema revision
were needed.

The native fixtures use authored in-memory HP, powers, deck and survivor setup.
Test Subject gets an in-memory run counter; card logging receives static monster
labels. No live game, profile, save or Cloud data is accessed. Actual Kill closes
the earlier callback-only Possess gap, but these new cases do not run full
`EndCombatInternal` or reward generation. Existing complete-ending and campaign
evidence retains that separate scope.

Final native item capture: build **1.624 s**, execution **1.931 s**. The changed
shared dispatcher also passed a fresh 36-case enemy-turn run with identical
retained results: build **1.626 s**, execution **1.507 s**. Both isolated user
directories were removed. The new capture binds the actual current source files
and the shared regression; historical matrices were not repinned.

Independent semantic review found the terminal living/dead Osty branches and
confirmed the corrections, including the outer summon-dispatch guard. The reviewer
independently ran the ten native comparisons plus one local selector regression:
**11 passed in 0.14 s**, with no remaining blocker.

Final affected gameplay and native-binding validation passed **1,540 tests in
37.01 s**. Conditional relic regressions and headless backend consumers passed
**236 tests in 7.66 s**. Compile checks, affected evidence links and
`git diff --check` passed. The full headless suite was not rerun.
