# Search labels: data scaling and target quality — 2026-11-01

Status: **complete; both registered readings were met.**
- More labelled fights improve held-out fit, but slowly for the specialist.
- 96-simulation search is a stronger teacher than 24 simulations (+3.5 win
  points on the same fights), and students learn its targets better.
- Neither effect is large. Search at play time remains the biggest measured
  gain.

No default changed. This follows the
[representation screen](COMBAT_REPRESENTATION_SCREEN_2026_10_22.md), which found
that generalization from search labels, not the representation, limits
distillation.

## Results

### Part A: more labelled fights

The screen's 11,770 held-out decisions (156 campaigns) were reused. Students
were fitted on nested subsets of the fit campaigns, with the same number of
updates for every subset. Each row reports the best held-out KL over checkpoints
at equal update counts; lower is better.

| Fit decisions (campaigns) | Distilled specialist | Combat graph 48, fresh |
| --- | ---: | ---: |
| 12,132 (172) | 0.272 | 0.328 |
| 21,524 (320) | 0.264 | 0.296 |
| 48,968 (677) | 0.258 | 0.278 |
| 100% − 50%, 95% | −0.0065 [−0.0087, −0.0042] | −0.018 [−0.023, −0.013] |
| 100% − 25%, 95% | −0.014 [−0.017, −0.011] | −0.050 [−0.062, −0.038] |

- **Registered reading.** The last doubling lowered best held-out KL by at least
  0.005 nats with an interval excluding zero, so more fights are expected to help.
- **The specialist gains about 0.006 nats per doubling.** For scale, distilling
  all 49k labels moved it from its untrained 0.308 to 0.258, and that gave
  +0.6 to +1.3 greedy win points in step 3. One more doubling would therefore
  be worth well under a point.
- **The fresh graph gains three times faster but starts far behind.** It was
  still improving at its last 100% checkpoint, and at this rate it needs several
  more doublings to reach the specialist.
- **Smaller subsets overfit sooner.** The specialist's best checkpoint came at
  roughly 1.5k, 3k and 6k updates for the three sizes. Its top-action agreement
  rose only from 78.8% to 79.6%.

### Part B: 24 versus 96 simulations

The training corpus was rebuilt for the current code and reproduced all 1,666
step-3 elite and boss openings. Two collections of 768 fights used the same
schedule, so case *i* has the same opening and planner seed in both, and only
the simulation count differs.

| Measurement | 24 simulations | 96 simulations |
| --- | ---: | ---: |
| **b1** Searched training win rate (768 paired fights) | 68.4% | **71.9%** |
| — bosses (398) / elites (370) | 51.8% / 86.2% | 56.8% / 88.1% |
| **b2** Overrides of the specialist at the first decision | 15.8% | 18.6% |
| **b3** Same top action across repeat visits (200 pairs, 144 openings) | 81.5% | 78.5% |
| — noise floor (entropy of mean target − mean entropy) | 0.058 | 0.071 |
| Search time per searched decision (16 workers) | 1.9 s | 7.4 s |

- **b1, strength.** 96 simulations won +3.5 points [+1.6, +5.5] of the same
  fights: 43 fights won only at 96 and 16 only at 24. Bosses gained 5.0 points.
- **b2, labels.** At the identical first state, the two top actions agree 81%
  [78%, 84%] of the time, with mean total variation 0.17.
- **b3, consistency.** 96-simulation targets are not more consistent across
  repeat visits. Two 24-simulation runs disagree about as often as 24 and 96 do.
  Better play comes from many slightly better decisions, not from sharper single labels.
- **b4, learnability.** Each label set was fitted on about 12k decisions, then
  scored on the same held-out decisions (3,468 for 96, 3,429 for 24).

| Students fitted on 96 − fitted on 24 | Held-out KL vs 96-sim targets | Override agreement | Held-out KL vs 24-sim targets |
| --- | --- | --- | --- |
| Distilled specialist | −0.019 [−0.029, −0.008] | 11.8% → 15.1% | +0.010 [+0.002, +0.017] |
| Combat graph 48, fresh | −0.014 [−0.024, −0.004] | 14.9% → 19.0% | +0.012 [+0.003, +0.021] |

  - Students fitted to 96-simulation labels predict 96-simulation search better
    and follow more of its overrides. The registered reading is met.
  - The symmetric check reverses: each label set is predicted best by students
    fitted to it. Part of b4 is therefore students matching their own targets
    and play distribution. The b1 strength result is the firmer evidence.
  - 96-simulation targets sit further from the network's prior (prior KL 0.445
    versus 0.278), so each label carries more change.

## Interpretation and next step

- Both levers help distillation, but modestly.
  - More data: about 0.006 nats per doubling for the specialist.
  - Stronger targets: about 0.014–0.019 nats against the stronger teacher.
  - In step 3, about 0.05 nats of fit yielded about one greedy win point.
  - A 96-simulation collection the size of step 3's takes about 8 hours. Even
    with that and more fights, distillation would likely recover only a few more
    points of search's gain.
- Search at play time is a bigger lever:
  - 24 simulations already adds +6.8 boss and +6.7 elite points on the benchmark.
  - 96 simulations adds another +3.5 points (+5 on bosses) on training fights.
- **Next:** measure 96-simulation search on the boss/elite validation benchmark,
  paired with the 24-simulation result. Then check what searched play is worth
  in Act 1 clear rate, keeping the noncombat heuristic fixed.
- Larger distillation rounds should wait for that, because they recover only a
  fraction of what search gives directly.

## Design and reproduction

The protocol (`runs/combat-targets-20261101/protocol.json`) and all seven screen
configs were frozen before any build, collection or fit. The only prior run was
an unused 16-fight reanalysis timing pilot. Reanalysis runs serially, so it was
replaced by paired collections.

- **Part A:** the step-3 collection with the screen's split.
  - Fit campaigns were nested by sha256(`data-scaling-2026-11-01`:campaign).
  - Training ran 64/32/16 epochs for 25/50/100%, with checkpoints at equal update counts.
  - Candidates were the distilled specialist and the fresh combat graph, three
    seeds each, with the screen recipe.
- **Part B:** teacher = step-2 initializer with `combat_belief_v1`, depth 16, 4
  leaf steps, 2 particles, 4,096/2,048 proposals, 120 s limits, root exploration
  and planner seed 0.
  - Collections: 768 training elite/boss fights each from start index 0, with 0
    cutoffs, failures or belief fallbacks.
  - Learnability screens used the same split and recipe with `evaluation_reports`.
- **Tool changes:** `search-screen` gained `fit_fraction`/`fit_salt` (nested
  campaign subsamples) and `evaluation_reports`, which take held-out decisions
  from another collection. It now also stores per-checkpoint held-out arrays.
  Focused tests cover each change.

| Artifact | Identity |
| --- | --- |
| Build | `eed31c0b…` (uncommitted, on `7e975686`) |
| Training corpus | `act1_combat_corpus_v2:45ba71a3…`, reproduction `corpus-reproduction.json` |
| Collections | `c24/search.json` `b35be9d0…`, `c96/search.json` `cd06db9d…` |
| Analyses | `analysis-scaling.json` `f1c0e7d1…`, `analysis-targets.json` `ed7e185b…` |

Elapsed times (wall time 3 h 15 min, from 19:45 to 23:00, with stages
overlapping on 18 cores):
- Corpus: 4 minutes.
- Collections: 32 minutes (24 simulations) and 2 h 3 min (96 simulations).
- Scaling screens: 2.9–3.2 h each, running in parallel with the collections.
- Learnability screens: about 30 minutes each, in parallel.
- User wait: none.

## Limits

- One teacher network and one alternative simulation count.
- Part B fits on about 12k decisions, a quarter of the step-3 data.
- The 24- and 96-simulation trajectories diverge after the first decision, so b4
  held-out states come from each collection's own play.
- Win rates are on training fights with root exploration, not the validation
  benchmark; supervised fit is not play strength.
- The KL-to-win-point conversion comes from one study and is a rough guide.
