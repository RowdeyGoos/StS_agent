# Combat search on the boss and elite benchmark — 2026-10-17

Status: **complete validation measurement**. No training, no test split and no
default change. The user approved the plan: measure search before choosing a
model or features. The network and search arms use the same checkpoint on every
elite and boss opening of the
[boss and elite benchmark](BOSS_ELITE_BENCHMARK_2026_10_17.md).

## Result

Gumbel search with the public belief model improves the Vantom specialist by
**6.8 points on bosses and 6.7 points on elites**. The paired intervals exclude
zero for both room kinds, and the estimated gain is positive for all twelve
encounters. Every fight finished, with no time cutoff and no belief-budget
fallback.

| Room kind | Encounters | Network | Search | Search − network, 95% |
| --- | ---: | ---: | ---: | --- |
| Boss (equal weight) | 6 | 48.7% [45.0, 52.5] | **55.5%** [51.7, 59.4] | **+6.8** [+4.1, +9.7] |
| Elite (equal weight) | 6 | 79.1% [76.7, 81.4] | **85.8%** [83.8, 87.9] | **+6.7** [+5.3, +8.2] |

| Encounter | Fights | Network | Search | Only search won | Only network won | Difference, 95% |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Ceremonial Beast | 100 | 78.0% | 82.0% | 5 | 1 | +4.0 [+0.0, +9.0] |
| The Kin | 100 | 49.0% | 60.0% | 15 | 4 | +11.0 [+3.0, +20.0] |
| Vantom | 120 | 54.2% | 63.3% | 12 | 1 | +9.2 [+3.3, +15.0] |
| Lagavulin Matriarch | 85 | 28.2% | 35.3% | 8 | 2 | +7.1 [+0.0, +14.1] |
| Soul Fysh | 97 | 59.8% | 66.0% | 11 | 5 | +6.2 [−1.0, +14.4] |
| Waterfall Giant | 87 | 23.0% | 26.4% | 6 | 3 | +3.4 [−3.4, +10.3] |
| Bygone Effigy | 204 | 81.9% | 86.8% | 11 | 1 | +4.9 [+2.0, +8.3] |
| Byrdonis | 201 | 83.6% | 85.6% | 4 | 0 | +2.0 [+0.5, +4.0] |
| Phrog Parasite | 207 | 81.6% | 89.9% | 17 | 0 | +8.2 [+4.8, +12.1] |
| Phantasmal Gardeners | 181 | 68.0% | 83.4% | 28 | 0 | +15.5 [+10.5, +21.0] |
| Skulking Colony | 170 | 81.8% | 84.7% | 6 | 1 | +2.9 [+0.0, +5.9] |
| Terror Eel | 176 | 77.8% | 84.7% | 14 | 2 | +6.8 [+2.8, +11.4] |

Intervals are 95% source-campaign bootstrap percentiles (2,000 resamples). Room-kind
rows weight each encounter equally and use the report's `balanced` section.
Per-encounter rows come from `runs/combat-search-20261017/analyze.py`.

- **Fewer losses, same win margins.** Search wins more often; its mean HP fraction
  on wins is essentially unchanged (bosses 0.311 vs 0.319, elites 0.449 vs 0.452).
  Fights last about 0.2 turns longer, and potion use per fight is identical.
- **The hardest bosses gain least.** Waterfall Giant and Soul Fysh intervals
  include zero. Search did not change the Giant result described in the benchmark
  record: learned play knocks the Giant out, then usually dies to the Steam
  explosion.
- **Reproducible baseline.** The network arm reproduced the original benchmark's
  `vantom_250k` outcome in 1,726 of 1,728 fights. The two exceptions diverged
  late in close fights, one in each direction, so the net win count is equal.

## Settings and cost

| Setting | Value |
| --- | --- |
| Checkpoint | Step-2 initializer `runs/combat-step2-20261017/initializers/frozen-s1/initial.sts-model` (`ppo_v1:a6a0dac3…`): the Vantom specialist with an unknown-row vocabulary fork, so its predictions are unchanged |
| Search | `combat_belief_v1`, 24 simulations, depth 16, 4-step leaf rollouts, 16 considered actions, prior/value final selection |
| Belief | 2 particles, 4,096 proposals, 2,048 replay proposals, 120 s belief and search limits per decision |
| Episodes | 1,728 validation openings × 2 arms, 512 decisions / 1,800 s per fight, 16 workers |
| Corpus | Rebuilt benchmark `act1_combat_corpus_v2:bc043513…`, verified identical to the original 1,728 fights (encounter, floor, HP, deck, inventory and public-state digests) |
| Implementation | Build `e63a5121…`, rules `404e413e…`, uncommitted on `b5eebc58` |
| Report | `runs/combat-search-20261017/full/search.json`, SHA-256 `89592f27…` |

The run took **3,814 s** (64 minutes). Search covered 78% of decisions; the other
22% had one legal action (`forced_action`). Each searched decision took **1.86 s**
on average (episode p95 at most 20 s), 56,800 worker-seconds in total. Most of the
time went to projection (48%) and network inference (28%). Three decisions fell
back with `simulation_work_limit`, in the fight that previously hung (see below).

## Fixes required before the measurement

The first 24-boss smoke run exposed two search defects. Both are fixed with
regression tests and an independent review; real games are unchanged.

1. **Unbounded simulated commands.** In one Waterfall Giant fight, a hypothetical
   world reached Hellraiser + Pillage with only Strikes left against the erupting
   Giant's 999,999,999 HP. One `apply()` call then reshuffled and autoplayed
   practically forever, and the search deadline, which is checked only between
   commands, never fired. Simulated commands now carry a deterministic budget of
   100,000 resolution tasks; ordinary commands use well under a hundred (the
   review measured at most 45 across twelve boss and elite fights). A belief
   proposal that exceeds the budget is rejected; tree search falls back for that
   decision with `simulation_work_limit`. The actual engine is still unbounded,
   and native behavior for such loops is unverified.
2. **Equal cards swapped by public name.** The projection orders equal
   definitions by public name. A fresh reconstruction named copies by content,
   so a lone enchanted copy (for example the starting Defend enchanted with Spiral
   later) received another copy's name, and no fresh opening could ever match.
   Every decision then spent its 120 s belief budget and fell back; one Lagavulin
   game ran 1,907 s and was truncated. `CampaignWorld.attach` now gives each deck
   card the name of a publicly identical root card. This works for both the
   recording owner and the fresh adapter that observes restored corpus starts.
   - Before the fix, 199 of 1,728 openings (11.5%; 73 boss, 126 elite) produced
     no matching fresh opening in 32 attempts.
   - After it, all 1,728 recover a belief along the actual evaluation path:
     restored start, fresh adapter and reference budget. The slowest took 14 s.

The interrupted first smoke run (23 of 24 boss openings, 1 extra search win and
1 extra network win) and the post-hang smoke run (24 bosses, +1 net search win, one
truncated Lagavulin game) predate fix 2 and are superseded by this measurement.

## Interpretation and limits

- At this compute budget, search's decisions are clearly better than the
  network's greedy choices on hard fights. That gap is a usable improvement
  target for distillation into the network. Inference-time search remains a
  separate option.
- One checkpoint, one search configuration and the validation split only. No
  budget sweep was run; 24 simulations is the existing reference setting. The
  bosses were later measured at 96 simulations: see the
  [follow-up](#follow-up-2026-11-13-96-simulations-on-the-boss-fights).
- These are frozen campaign openings from one collector's routes. Act 1 clear-rate
  effects need a campaign evaluation with the fixed noncombat heuristic.
- Search adds about 1.9 s per searched decision on 16 parallel workers. Live
  latency and native compatibility are outside this measurement.

## Reproduce

```bash
sh runs/combat-search-20261017/build_benchmark.sh
.venv/bin/python runs/combat-search-20261017/verify_benchmark.py
sh runs/combat-search-20261017/search.sh full 10000 elite boss
.venv/bin/python runs/combat-search-20261017/analyze.py runs/combat-search-20261017/full
```

`search.sh` passes `--combat-room-kind elite --combat-room-kind boss` and the
settings above to `sts-agent-evaluate --search`. Elapsed times:
- Smoke runs: 32 minutes after the hang fix.
- Three benchmark rebuilds: about 5 minutes each.
- Opening audits: 1 and 8 minutes.
- Independent reviews: 6, 7 and 2 minutes.
- Full run: 64 minutes.
- User wait: none.

## Follow-up, 2026-11-13: 96 simulations on the boss fights

Status: **complete validation measurement** on the 589 boss openings. No
training, no test split and no default change. The user approved the run. Only
the simulation count differs from the settings above; elites were not run.

**Result.** With 96 simulations the same checkpoint wins **60.2%** of the boss
fights: **4.7 points more than with 24 simulations**, at four times the search
time. It is level with the [planner without a network](COMBAT_PUBLIC_PLANNER_2026_11_12.md).

| Player | Bosses (equal weight) | Wins of 589 |
| --- | ---: | ---: |
| Network alone | 48.7% [44.8, 52.4] | 294 |
| Search, 24 simulations | 55.5% [51.8, 59.3] | 335 |
| **Search, 96 simulations** | **60.2%** [56.4, 63.9] | 362 |
| Planner, 8 worlds with 4 lines (recorded 2026-11-12) | 59.6% [55.9, 63.2] | 358 |
| *Perfect-information solver (recorded 2026-11-12)* | *81.6%* [78.7, 84.6] | 484 |

| Paired comparison | Difference, 95% | Only the first won | Only the second won |
| --- | --- | ---: | ---: |
| 96 − 24 simulations | **+4.7** [+2.3, +7.3] | 41 | 14 |
| 96 simulations − network | **+11.5** [+8.6, +14.5] | 79 | 11 |
| 96 simulations − planner | +0.6 [−2.8, +4.1] | 56 | 52 |
| 96 simulations − solver | −21.4 [−25.0, −18.0] | 3 | 125 |

| Boss | Fights | Network | 24 | 96 | Only 96 won | Only 24 won | 96 − 24, 95% | Planner |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| Ceremonial Beast | 100 | 78.0% | 82.0% | 84.0% | 3 | 1 | +2.0 [−1.9, +6.4] | 86.0% |
| The Kin | 100 | 49.0% | 60.0% | 65.0% | 9 | 4 | +5.0 [−2.2, +12.0] | 49.0% |
| Vantom | 120 | 54.2% | 63.3% | 65.8% | 7 | 4 | +2.5 [−2.7, +7.6] | 66.7% |
| Lagavulin Matriarch | 85 | 28.2% | 35.3% | 44.7% | 9 | 1 | +9.4 [+2.5, +16.9] | 41.2% |
| Soul Fysh | 97 | 59.8% | 66.0% | 73.2% | 8 | 1 | +7.2 [+2.0, +13.8] | 81.4% |
| Waterfall Giant | 87 | 23.0% | 26.4% | 28.7% | 5 | 3 | +2.3 [−4.0, +8.8] | 33.3% |

Intervals are 95% source-campaign bootstrap percentiles (2,000 resamples, seed
20261017) from `runs/combat-search96-20261113/analyze.py`.

- **The gain has not flattened.** The first 24 simulations added 6.8 points to
  the network, and the next 72 added 4.7. The estimate is positive for every
  boss; only the Lagavulin Matriarch and Soul Fysh intervals exclude zero.
- **Search and the planner are level, and they win different fights.** Each won
  more than 50 fights that the other lost, and one or the other won 414 of the
  589 (69.0% [65.7, 72.5]). Near-identical learners differ as much among
  themselves, so this alone does not show that a combination would gain.
  Search is far ahead on The Kin (+16.0 [+6.2, +25.6]). The planner's estimate is higher on Soul Fysh (−8.2 [−17.5, +1.2])
  and Waterfall Giant (−4.6 [−13.5, +4.0]); neither interval excludes zero.
- **The ceiling is unchanged.** Search with 96 simulations won 7 boss fights
  that none of the 75 earlier players had won. The solver had won all 7, so a
  player or the solver still accounts for 82.8% of the boss fights.
- **Cost grows in step with the simulation count.** A searched decision took
  6.13 s against 1.51 s (4.1 times) for 4.0 times the simulations. Projection
  took 45% of the search time and network inference 35%, as at 24 simulations
  (43% and 35%). Most of the inference timer is encoding the observation, not
  the network: see the [search profile](SEARCH_PROFILE_2026_11_13.md).

**Checks.**
- The fights are the benchmark's 589 boss openings in a corpus rebuilt for the
  current engine, `act1_combat_corpus_v2:d0016172…` (build `9c3e75bd…`, rules
  `4af09d99…`). Fights are matched to the original by encounter and public
  start digest.
- The 24-simulation arm was rerun on this corpus. It reproduced the recorded
  search outcome in all 589 fights. The network arm had the same outcome in
  both runs in all 589 and matched the original benchmark in 587.
- All 2,356 fights finished. No fight was cut off and no decision hit a time or
  belief limit. In the 96-simulation run, search covered 78.2% of decisions
  (15,116 of 19,322); the rest had one legal action. The three
  `simulation_work_limit` fallbacks of the 24-simulation run did not recur.
- Mean HP fraction on wins was 0.315, against 0.311 at 24 simulations and 0.319
  for the network. Fights lasted 8.06 turns on average, against 8.01 and 7.82.

**Limits.**
- Bosses only, one checkpoint and one search seed. Elites at 96 simulations and
  any budget above 96 are unmeasured.
- A development result on a reused panel, as above.
- 6.1 s per searched decision on 16 parallel workers (episode p95 at most
  10.4 s). Live latency and native compatibility are outside this measurement.
- No independent review: the run uses the existing evaluation command with one
  changed setting.

**Reproduce.**

```bash
sh runs/combat-search96-20261113/search.sh s24 24
sh runs/combat-search96-20261113/search.sh s96 96
.venv/bin/python runs/combat-search96-20261113/analyze.py \
  runs/combat-search96-20261113/analysis.json
```

They use the corpus at `runs/combat-benchmark-20261113/corpus-planning`, built
with the benchmark's build settings and planning receipts. Reports:
`s24/search.json` (SHA-256 `1b3860af…`) and `s96/search.json` (`e5dc75ec…`);
analysis output `analysis.json` (`00b9f909…`).

Elapsed times: the 96-simulation run took 99 minutes of wall time on 16 workers
(25.7 worker-hours of search), the 24-simulation rerun 25 minutes and the
corpus rebuild 226 s. Implementation and analysis time was not measured. User
wait: none.

## Follow-up, 2026-11-13: leaf rollouts at equal search time

Status: **complete validation measurement** on the 589 boss openings. No
training, no test split and no default change. The user approved the run after
the [search profile](SEARCH_PROFILE_2026_11_13.md) showed that the greedy leaf
rollouts take more than half of the search time.

**Result.** The rollouts pay for themselves. Spending their time on more
simulations instead loses 3.8 points, and halving them is level with the
reference.

| Search setting, equal search time | Bosses (equal weight) | Wins of 589 | Difference to the reference, 95% | Only it won | Only the reference won |
| --- | ---: | ---: | --- | ---: | ---: |
| 24 simulations, 4 leaf steps (reference) | 55.5% [51.8, 59.3] | 335 | | | |
| 32 simulations, 2 leaf steps | 54.8% [51.1, 58.3] | 330 | −0.8 [−3.3, +1.6] | 24 | 29 |
| 54 simulations, no leaf steps | 51.7% [48.0, 55.3] | 312 | **−3.8** [−6.5, −1.1] | 21 | 44 |
| Network alone | 48.7% [44.8, 52.4] | 294 | −6.8 [−9.7, −4.0] | 16 | 57 |

| Boss | Fights | Network | 4 steps | 2 steps | No steps | No steps − 4 steps, 95% |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Ceremonial Beast | 100 | 78.0% | 82.0% | 82.0% | 77.0% | −5.0 [−9.9, −1.0] |
| The Kin | 100 | 49.0% | 60.0% | 58.0% | 53.0% | −7.0 [−15.4, +1.1] |
| Vantom | 120 | 54.2% | 63.3% | 60.8% | 59.2% | −4.2 [−10.4, +1.8] |
| Lagavulin Matriarch | 85 | 28.2% | 35.3% | 34.1% | 31.8% | −3.5 [−11.3, +3.8] |
| Soul Fysh | 97 | 59.8% | 66.0% | 66.0% | 62.9% | −3.1 [−8.9, +2.9] |
| Waterfall Giant | 87 | 23.0% | 26.4% | 27.6% | 26.4% | +0.0 [−6.3, +6.4] |

- **Without rollouts search is worse or equal on every boss**, although it
  runs 2.25 times the simulations and builds a deeper tree (mean depth 2.46
  against 2.14). It still beats the network alone, by 3.0 points [+0.2, +6.0].
- **Two steps are level with four.** The interval allows a loss of 3 points or
  a gain of 2, so the reference setting stays.
- **A reading, not a finding:** a few greedy plays before the critic is asked
  improve the evaluation more than twice the simulations do. That points at the
  critic's value of a mid-turn state as the weak part of the search.

**Checks.**
- Search time per searched decision was matched to the reference on all 589
  fights: 1.108 s for the reference, 1.099 s without rollouts (0.992) and
  1.104 s with two steps (0.997). The simulation counts were set on the first
  64 fights and not changed afterwards.
- All three runs use the same sources and corpus (build `188484ae…`,
  `act1_combat_corpus_v2:31c16ec4…`), 16 workers and an otherwise idle machine.
  The reference is the run that verified the speed change of the same day.
- The network arm had the same outcome as the reference run in all 589 fights
  of both new runs.
- All 2,356 new episodes finished. No fight was cut off and no decision hit a
  time or belief limit.

**Limits.**
- Bosses only, one checkpoint, one search seed and a 24-simulation time budget.
  Whether the balance shifts at a larger budget is not measured.
- Longer rollouts at equal time were not run.
- A development result on a reused panel, as above. No independent review:
  the runs use the existing evaluation command with two changed settings.

**Reproduce.**

```bash
sh runs/combat-search-rollouts-20261113/search.sh r0-s54 54 0
sh runs/combat-search-rollouts-20261113/search.sh r2-s32 32 2
.venv/bin/python runs/combat-search-rollouts-20261113/analyze.py \
  runs/combat-search-rollouts-20261113/analysis.json r0-s54 r2-s32
```

Analysis output `analysis.json`, SHA-256 `8246585a…`.

Elapsed times: each 589-fight run took 1,148 s of wall time on 16 workers and
each 64-fight calibration run about 145 s. Implementation and analysis time
was not measured. User wait: none.
