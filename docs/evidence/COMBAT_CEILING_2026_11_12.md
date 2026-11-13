# Perfect-information ceiling of the boss and elite benchmark — 2026-11-12

Status: **complete privileged diagnostic.** No training, no default change and
validation fights only. The user asked for it as step 2 of the
[roadmap's](../../ROADMAP.md) combat sequence. The solver reads private
snapshots: it is a measuring tool, never an agent or a teacher. Its winning
plans stay in an owner-only directory and must never become training data or
witnesses of a public policy.

## Result

A solver that may see the true draw order and RNG searched every boss fight of
the [boss and elite benchmark](BOSS_ELITE_BENCHMARK_2026_10_17.md). Each win it
reports was replayed to a victory through the benchmark's own environment.

| Bosses, equal weight | Win rate | 95% interval |
| --- | ---: | --- |
| Best network alone | 48.7% | 44.7–52.3% |
| Network with search, 24 simulations | 55.5% | 51.8–59.3% |
| Fight won by at least one of 75 players | 69.5% | 65.9–72.8% |
| **Perfect-information solver** | **81.6%** | 78.7–84.6% |
| **Solver or any player** | **82.8%** | 79.8–85.9% |
| Solver or any player − search | +27.3 points | +23.8 to +30.9 |

| Boss | Fights | Search | Any player | Solver | Solver or any player | Won by neither |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Ceremonial Beast | 100 | 82.0% | 89.0% | 97.0% | 97.0% | 3 |
| The Kin | 100 | 60.0% | 73.0% | 76.0% | 82.0% | 18 |
| Vantom | 120 | 63.3% | 74.2% | 82.5% | 82.5% | 21 |
| Lagavulin Matriarch | 85 | 35.3% | 52.9% | 74.1% | 75.3% | 21 |
| Soul Fysh | 97 | 66.0% | 89.7% | 96.9% | 96.9% | 3 |
| Waterfall Giant | 87 | 26.4% | 37.9% | 63.2% | 63.2% | 32 |

**75 of the 173 boss fights that no player had won have a winning line.** The
[any-player record](COMBAT_ANY_PLAYER_WINS_2026_11_12.md) left open whether
those fights were lost by the deck or by the play. For at least 75 of them it
was the play.

**The solver rarely misses a fight that is known to be winnable.** It solved 409
of the 416 boss fights that some player had won:

| Share of the 75 players that won the fight | Fights | Solved |
| --- | ---: | ---: |
| none | 173 | 75 (43.4%) |
| up to 10% | 59 | 54 (91.5%) |
| 10–50% | 68 | 67 (98.5%) |
| 50–90% | 146 | 145 (99.3%) |
| over 90% | 143 | 143 (100%) |

**A narrow beam finds most of the wins.** The solver keeps a number of lines of
play alive at each turn (its beam width):

| Widest beam used | Boss fights won | Equal-weight win rate |
| --- | ---: | --- |
| 1 line | 305 | 51.0% [47.3, 54.9] |
| up to 4 lines | 415 | 69.3% [66.0, 72.6] |
| up to 16 lines | 466 | 78.3% [75.3, 81.4] |
| up to 64 lines | 484 | 81.6% [78.7, 84.6] |

**HP on arrival still matters a great deal:**

| Boss entered with | Fights | Search | Any player | Solver or any player |
| --- | ---: | ---: | ---: | ---: |
| under 50% HP | 35 | 4 (11.4%) | 8 (22.9%) | 17 (48.6%) |
| 50–70% HP | 106 | 35 (33.0%) | 54 (50.9%) | 68 (64.2%) |
| 70–85% HP | 95 | 48 (50.5%) | 61 (64.2%) | 78 (82.1%) |
| 85% HP or more | 353 | 248 (70.3%) | 293 (83.0%) | 328 (92.9%) |

**Elites.** Only the 102 elite fights that no player had won were searched; 41
were solved. Counting those, 94.5% of elite fights [93.2, 95.8] were won by a
player or the solver, against 85.8% for search and 90.9% for any player. Of the
102, 93 were entered below half HP.

**The winning lines are not exotic.** One Waterfall Giant fight was entered at
90 of 90 HP and lost by all 75 players. The solver attacks on almost every turn,
knocks the Giant out on turn 7 with 36 HP left and survives the 30-damage
eruption. The Giant's Steam grows every turn, so a slower kill faces a larger
eruption.

## What it means

**Most boss fights can be won with the decks the collector brought.** At least
82.8% of them have a winning line, against 55.5% for the best public player. The
decks are not the main limit on the boss win rate. Combat has at least 27
points of room in this sense.

**This is an upper bound, not a level a player can be expected to reach.** The
solver has two advantages that no player has:
- it knows the order of every future draw and the outcome of every random
  effect;
- it follows up to 64 lines at once and counts a win if any one of them wins.

A player must commit to one action without knowing the draws. The best possible
public-information player lies somewhere between 55.5% and the perfect-information
ceiling, and this measurement does not say where.

**Without the many lines, the same planner is no better than the network.**
With a single line it wins 51.0% of bosses, close to the best network's 48.7%.
That single line takes, each turn, the end-of-turn result with the best balance
of own HP against enemy HP. It still sees the cards drawn during the turn, so it
is not a public player either. The step from 51.0% to 81.6% comes from keeping
several lines over several turns, which mixes real planning with hindsight.

**98 boss fights were won by neither a player nor the solver.** That is 16.6% of
the 589, and it is the most that can still be blamed on decks and HP alone. It
is not a count of unwinnable fights: 17 searches stopped on the clock, and The
Kin is a known weak spot of the solver (see Limits).

## Method

- **Fights.** The benchmark corpus was rebuilt for the current code (build
  `eed31c0b…`, rules `30256cad…`) with the benchmark's settings and no planning
  receipts, in 158 s. It reproduces all 1,728 original openings by encounter,
  public start digest, HP and deck size
  (`act1_combat_corpus_v2:936ae55f…`). Fights are matched to the any-player
  counts by encounter and public start digest.
- **Solver.** A beam search over the real engine (`runs/combat-ceiling-20261112/solver.py`,
  SHA-256 `01455ac4…`). Every transition is `RunEngine.apply` on a restored
  snapshot; no game rule is duplicated.
  - Inside a turn it enumerates every distinct line of play, up to a cap per
    turn start. States that differ only in card identities or in the order of
    equal plays are merged.
  - Of the states at the start of the next turn it keeps a fixed number. The
    `pareto` rule keeps the states that no other state beats at once on player
    HP, enemy HP, potions kept, a scaling term and living enemies. The `scores`
    rule takes the best by five weighted sums of those numbers.
  - It never discards a potion or undoes a card selection, and it treats equal
    cards as interchangeable. A simulated command may run at most 100,000
    resolution tasks, as in combat search.
  - The beam is widened in passes: 4, 16, then 64 lines.

**Runs.** All used 16 workers. A fight counts as solved if any run solved it.

| Run | Fights | Beam widths | Rule | Limit per fight | Solved | Wall time |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `boss-never` | 173 bosses no player won | 4, 16, 64 | pareto | 600 s | 75 | 41 min |
| `boss-won` | 416 bosses some player won | 4, 16, 64 | pareto | 600 s | 408 | 27 min |
| `boss-w1` | all 589 bosses | 1 | scores | 120 s | 305 | 3 min |
| `elite-never` | 102 elites no player won | 4, 16, 64 | pareto | 600 s | 41 | 12 min |
| `cal-rare-pareto`, `cal-rare-scores` | 59 bosses at most 10% of players won | 4, 16 | pareto, scores | 150 s | 49, 49 | 4 min each |
| `smoke-never` | 16 bosses no player won | 4, 16, 64 | scores | 300 s | 4 | 5 min |

The two calibration runs were used to compare the selection rules before the
main runs. They solved the same number of fights, 47 in common.

- **Verification.** A fight is recorded as won only after `solver.verify`
  replays the plan from a fresh restore, which checks the public start digest.
  The replay goes through the public adapter that the benchmark uses. Each
  command must be exactly one advertised candidate that `commit_decisions_v1`
  allows, the plan must fit the benchmark's 512 decisions, and the adapter's
  combat summary must report a completed victory. The 931 winning plans cover
  525 distinct fights (484 boss, 41 elite); the longest has 72 decisions.
- **Rates and intervals.** Each encounter has equal weight. Intervals use the
  benchmark's bootstrap: 2,000 resamples of whole source campaigns, seed
  20261017, grouped by the original benchmark's campaigns as in the any-player
  record. The analysis gives the same numbers for any order of the runs.
- **Work.** 18.4 worker-hours and 16.5 million engine commands; no engine error
  and no replay mismatch occurred.

## Independent review

One independent review found **no blocking issue**: a recorded win is a
benchmark win from the exact frozen start.
- It replayed 922 plans with its own code through the real Gym environment and
  through the evaluator's episode function. All 922 were victories. After each
  of 29,470 steps the environment's engine state equalled a separately restored
  engine that applied the stored command directly.
- The remaining 9 elite plans finished after the review. The author replayed
  them with the reviewer's script: 9 victories.
- Tampered plans were rejected: a dropped or added step, another fight's plan, a
  legal losing line, 513 steps and an undo.
- The per-fight player counts were regenerated byte for byte and recounted from
  all 14 source reports.
- Plans exist only in the owner-only directory, public results contain no plan
  or snapshot content, and nothing under `game/` refers to the experiment.

Its non-blocking findings are reflected here:
- The analysis depended on the order of the runs for its unsolved-fight
  diagnostics; that is fixed.
- A "closest approach" statistic was dropped. It was an artefact for the Giant,
  whose knocked-out state counts as zero HP, and for The Kin.
- The Kin weakness, the engine build and the witness caution are in Limits.

## Limits

- **Hindsight.** The numbers bound what any player could do; they are not a
  target for one.
- **Unsolved is not unwinnable.** Of the 98 unsolved boss fights, 81 ended with
  every kept line dead and 17 on the clock; 41 hit a per-turn cap. Clock stops
  depend on machine load, and the review ran beside the solver.
- **The Kin, the only boss with several enemies, is a weak spot.** The solver
  measures progress by the total HP of all living enemies, but the Kin's
  followers die with the Priest, so damage to followers looks like progress.
  Three targets also triple the branching. On fights some player won, it solved
  67 of 73 Kin fights against 342 of 343 for the other bosses. Elites with
  several enemies share this.
- **Solver restrictions.** No potion discard, no undo, equal cards
  interchangeable even when a card is chosen from the draw pile, and a merge key
  that leaves out the record of cards in play. The review saw no wrong merge in
  14,346 checked expansions.
- **Shared snapshot state.** The solver restores many engines from one
  snapshot, and during these runs the engine's restore shared a few mutable
  containers with the snapshot it read. In about 0.1% of expansions a sibling
  line's cost bookkeeping changed. This was found in the review of the
  [public planner](COMBAT_PUBLIC_PLANNER_2026_11_12.md). It can make the search
  miss a win; it cannot create one, because every win was replayed separately.
  The engine was fixed afterwards (`tests/headless/test_restore_ownership.py`),
  so a rerun can differ slightly.
- **Engine build.** The wins hold on the current build with byte-identical
  starts. The original nine policies ran on an earlier rules build. Policies
  that play deterministically had identical results on all 1,728 fights across
  the builds, which is strong evidence of equivalence, not proof.
- **Elites** were searched only where no player had won, so there is no
  solver-alone rate for them.
- **One realization per fight**, from one collector's decks, routes and
  survival, on a reused development panel.
- **Thinking time is not comparable.** A plan executes in about a second, but
  finding one took up to 600 s.
- **Witness caution.** A plan replayed through the evaluator produces an
  ordinary public trajectory that the witness verifier would accept. Never
  replay these plans into a diagnostics set or a corpus.

## Reproduce

```bash
sts-agent-train build-combat-corpus --output-dir runs/combat-ceiling-20261112/benchmark/corpus \
  --checkpoint runs/act1-increased-500k-8workers-20260930/chunk-15/final.sts-model \
  --train-campaigns 1 --validation-campaigns 512 --test-campaigns 1 \
  --start-index 30000000 --route-policy mixed_elites --capture-turns 1 --no-record-planning --workers 16
.venv/bin/python runs/boss-elite-benchmark-20261017/any_policy_wins.py /dev/null \
  runs/combat-ceiling-20261112/benchmark-fights.json
.venv/bin/python runs/combat-ceiling-20261112/run.py boss-never --select never_won --time-limit 600
.venv/bin/python runs/combat-ceiling-20261112/run.py boss-won --select won_hard --time-limit 600
.venv/bin/python runs/combat-ceiling-20261112/run.py boss-won --select won_easy --time-limit 600
.venv/bin/python runs/combat-ceiling-20261112/run.py boss-w1 --select all --schedule 1:150:1 \
  --selection scores --time-limit 120
.venv/bin/python runs/combat-ceiling-20261112/run.py elite-never --select never_won --room-kind elite \
  --time-limit 600
.venv/bin/python runs/combat-ceiling-20261112/run.py cal-rare-pareto --select won_rare \
  --schedule 4:150:1,16:300:1 --time-limit 150
.venv/bin/python runs/combat-ceiling-20261112/run.py cal-rare-scores --select won_rare \
  --schedule 4:150:1,16:300:1 --selection scores --time-limit 150
.venv/bin/python runs/combat-ceiling-20261112/run.py smoke-never --select never_won --limit 16 \
  --selection scores --time-limit 300
.venv/bin/python runs/combat-ceiling-20261112/analyze.py runs/combat-ceiling-20261112/analysis.json \
  boss-w1 boss-never boss-won cal-rare-pareto cal-rare-scores smoke-never elite-never
```

Analysis output `analysis.json`, SHA-256 `b4bcdaf5…`; per-fight player counts
`benchmark-fights.json`, SHA-256 `149a4c64…`. Results that end on the clock can
differ between runs.

Elapsed times: corpus rebuild 158 s; solver runs 96 minutes of wall time in
total on 16 workers; independent review 75 minutes, beside the runs. From the
first build to the final analysis took 1 hour 47 minutes. Implementation time
was not measured separately. User wait: none.
