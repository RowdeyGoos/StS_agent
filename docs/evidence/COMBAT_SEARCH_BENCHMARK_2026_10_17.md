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
  budget sweep was run; 24 simulations is the existing reference setting.
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
