# Boss and elite combat benchmark — 2026-10-17

Status: **complete validation benchmark**. No training, no test split, no
hidden-state resampling and no default change. The user requested this as the
first step of a combat-first plan, after the
[Act 1 loss analysis](#why-elites-and-bosses) showed where runs are lost.

## Why elites and bosses

The best held-out Act 1 model (250k, 256 starts) lost 200 runs: 135 to bosses,
32 to elites and 33 to normal fights. Normal fights are already won about 98% of
the time, so they carry little information about combat strength. Earlier
validation panels had 1–7 fights per boss, or 42 openings of one boss (Vantom),
which cannot resolve differences much below 20 percentage points. This
benchmark measures every Act 1 elite and boss with enough fights to compare
individual encounters and resolve differences of a few points.

## Implementation

- **Parallel corpus collection.** `sts-agent-train build-combat-corpus --workers N`
  runs whole source campaigns in persistent spawn workers (command default
  `min(16, CPUs)`; library calls stay serial). Seeds, routes and the collector are
  fixed before collection, results keep the predeclared campaign order, and no
  campaign is retried. A failure or cancellation stops assignment; finished
  campaigns are retained and the rest stay unattempted. Workers verify the
  implementation and collector digests before collecting.
- **Room-kind selection.** `sts-agent-evaluate --combat-corpus ... --combat-room-kind
  elite --combat-room-kind boss` evaluates only those openings. The selection is
  recorded in the plan and report and bound into the held-out test lock.
  Witnessed diagnostics still require the complete natural population.
- **Balanced summary.** Combat reports gain a `balanced` section: for elites and
  bosses, the mean of per-encounter win rates (each encounter weighted equally),
  with 95% percentile intervals from 2,000 source-campaign bootstrap resamples.
  All policies share each resample, so paired differences keep their correlation.
  Failed, cut-off and unattempted fights count as non-wins. Existing Hoeffding
  fields are unchanged.

Serial and parallel collection produced identical campaign outcomes, cases
(apart from opaque IDs), coverage and snapshot bytes, with both the heuristic and
a learned collector.

## Corpus

| Setting | Value |
| --- | --- |
| Collector | Act 1 increased-reward 500k, `ppo_v1:fce362d2…` (the large 7-hour corpus collector) |
| Routes | `mixed_elites`: alternate campaigns follow elite-maximizing public routes |
| Starts | Openings only (`--capture-turns 1`), public planning receipts recorded |
| Seeds | Start index 30,000,000, disjoint from every existing corpus range |
| Campaigns | 512 validation per region; 1 train and 1 test per region as unused placeholders |
| Identity | `act1_combat_corpus_v2:c134b8783eb5ad78c95156c151f94d73e87bc53036cc7713b5438efdd1b50134` |
| Location | `runs/boss-elite-benchmark-20261017/corpus` (+ owner-only `corpus-private`) |

The 1,024 validation campaigns produced 8,426 fights: 6,698 normal, **1,139 elite
(170–207 per elite) and 589 boss (85–120 per boss)**, with no missing encounter.
Bosses were almost always entered with more than half HP (549 of 589). The
collector cleared Act 1 in 159 of the 1,024 campaigns; because half of all
campaigns follow elite-seeking routes, this is not a natural clear rate. Collection took **343 s with 16
workers**; the comparable 1,028-campaign large corpus took 6,693 s serially with
eight captured turns. Storage is 3.2 GB public (mostly planning receipts) and
1.3 GB private; omit `--record-planning` when Search will not use a corpus.

## Evaluation

Nine policies played the same 1,728 elite and boss openings greedily:
**15,552 games, 16 workers, 512 decisions / 120 seconds per fight, 874 s**.
There were no cutoffs, failures or unattempted games. Implementation build
`69e9cd977a6576c374dcdd6dd4bd69a9e44e7aa2eb9aadb87c8a01b80592ce55`, rules
`a7aff887d75dc4de4e2691bb261c72886bdb863f47239dc7b025e71d008ee5cb`; report
SHA-256 `0facc943402666ddd943dca0c1a3a68258060ba3cd8789d30572a0c8cefa6fb2`.

| Label | Checkpoint | Training |
| --- | --- | --- |
| Vantom 250k | `vantom-specialist-training-20261002/ppo/chunk-20` | Imit. 8k s2 + value calibration + 250k Vantom-only PPO |
| Imit. 8k s1/s2 | `combat-research-7h-20261002/distill-longer-seed{1,2}` | Combat 250k s1/s2 + 8k imitation updates on successful elite/boss fights (exact 2k→4k→8k continuations) |
| Combat 250k s1/s2 | `combat-representation-250k-20261001/combat-seed{1,2}/chunk-20` | Fresh 250k combat PPO, rich combat graph, 64-campaign training corpus |
| Act 1 500k / 250k | `act1-increased-{500k,250k}-8workers-20260930/chunk-{15,09}` | Act 1 campaign PPO; only the actor plays here |

## Results

### Bosses

| Policy | Equal-weight win rate | 95% interval |
| --- | ---: | --- |
| Vantom 250k | 48.7% | 44.7–52.3% |
| Imit. 8k s2 | 45.6% | 41.8–49.3% |
| Imit. 8k s1 | 43.4% | 39.9–47.2% |
| Combat 250k s2 | 43.0% | 39.1–46.7% |
| Combat 250k s1 | 38.5% | 34.8–42.3% |
| Act 1 500k | 36.7% | 33.2–40.5% |
| Act 1 250k | 26.1% | 22.8–29.7% |
| Heuristic | 15.1% | 12.5–18.0% |
| Random legal | 0.3% | 0.0–0.9% |

| Boss | Fights | Vantom 250k | Imit. 8k s2 | Imit. 8k s1 | Combat 250k s2 | Combat 250k s1 | Act 1 500k | Act 1 250k | Heuristic |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ceremonial Beast | 100 | 78% | 77% | 72% | 72% | 71% | 68% | 48% | 34% |
| The Kin | 100 | 48% | 45% | 45% | 38% | 30% | 37% | 25% | 12% |
| Vantom | 120 | 55% | 49% | 52% | 47% | 38% | 34% | 26% | 17% |
| Lagavulin Matriarch | 85 | 28% | 26% | 24% | 29% | 29% | 24% | 14% | 8% |
| Soul Fysh | 97 | 60% | 62% | 52% | 56% | 46% | 48% | 38% | 16% |
| Waterfall Giant | 87 | 23% | 15% | 16% | 16% | 16% | 9% | 6% | 3% |

### Elites

| Policy | Equal-weight win rate | 95% interval |
| --- | ---: | --- |
| Imit. 8k s2 | 79.6% | 77.4–81.8% |
| Imit. 8k s1 | 79.3% | 76.9–81.6% |
| Vantom 250k | 79.1% | 76.7–81.4% |
| Combat 250k s2 | 78.2% | 75.8–80.6% |
| Act 1 500k | 75.8% | 73.4–78.3% |
| Combat 250k s1 | 75.7% | 73.2–78.2% |
| Act 1 250k | 71.1% | 68.4–73.7% |
| Heuristic | 66.7% | 63.8–69.5% |
| Random legal | 12.0% | 10.3–13.9% |

| Elite | Fights | Vantom 250k | Imit. 8k s2 | Imit. 8k s1 | Combat 250k s2 | Combat 250k s1 | Act 1 500k | Act 1 250k | Heuristic |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Bygone Effigy | 204 | 82% | 80% | 81% | 80% | 80% | 78% | 73% | 66% |
| Byrdonis | 201 | 84% | 84% | 84% | 84% | 84% | 84% | 79% | 75% |
| Phrog Parasite | 207 | 82% | 84% | 84% | 85% | 76% | 85% | 78% | 75% |
| Phantasmal Gardeners | 181 | 68% | 73% | 71% | 66% | 60% | 55% | 54% | 51% |
| Skulking Colony | 170 | 82% | 80% | 80% | 78% | 81% | 79% | 76% | 76% |
| Terror Eel | 176 | 78% | 77% | 76% | 77% | 74% | 74% | 68% | 57% |

### Paired comparisons

Differences in equal-weight win rate, with paired 95% source-campaign bootstrap
intervals:

| Comparison | Bosses | Elites |
| --- | --- | --- |
| Vantom 250k − its initializer Imit. 8k s2 | +3.0 [+0.3, +5.8] | −0.5 [−2.0, +0.9] |
| Imit. 8k s1 − its parent Combat 250k s1 | +4.9 [+2.1, +8.1] | +3.6 [+2.0, +5.1] |
| Imit. 8k s2 − its parent Combat 250k s2 | +2.7 [−0.3, +5.8] | +1.4 [−0.0, +2.8] |
| Combat 250k s2 − Combat 250k s1 (learner seeds) | +4.4 [+1.0, +8.0] | +2.5 [+0.8, +4.1] |
| Vantom 250k − Act 1 500k | +11.9 [+8.7, +15.1] | +3.3 [+1.6, +5.1] |
| Act 1 500k − Act 1 250k | +10.6 [+7.4, +13.8] | +4.8 [+2.9, +6.6] |

Paired boss intervals span about ±3.5 points and elite intervals about ±2
points. This benchmark therefore resolves boss differences of roughly 5 points
between two checkpoints, against about 20 points for the earlier 42-fight panel.

### Waterfall Giant eruption

At 0 HP the Giant becomes invulnerable, stuns for a turn, then explodes for its
accumulated Steam. Counting the 87 Giant fights per policy:

| Policy | Won | Lost after knocking it out | Lost before | Eruption survival |
| --- | ---: | ---: | ---: | ---: |
| Vantom 250k | 20 | 41 | 26 | 33% |
| Imit. 8k s2 | 13 | 50 | 24 | 21% |
| Imit. 8k s1 | 14 | 45 | 28 | 24% |
| Combat 250k s2 | 14 | 48 | 25 | 23% |
| Combat 250k s1 | 14 | 45 | 28 | 24% |
| Act 1 500k | 8 | 47 | 32 | 15% |
| Act 1 250k | 5 | 32 | 50 | 14% |
| Heuristic | 3 | 30 | 54 | 9% |

Every learned model knocks the Giant out in most fights and then usually dies
to the eruption.

### How close the boss losses are

Remaining boss HP at the last recorded decision of each loss (a knocked-out Giant
counts as 0%; The Kin sums its members). A near miss leaves less than 25%:

| Boss | Vantom 250k losses | Median HP left | Near misses | Act 1 500k losses | Median HP left | Near misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Ceremonial Beast | 22 | 14% | 68% | 32 | 15% | 72% |
| The Kin | 52 | 33% | 29% | 63 | 32% | 41% |
| Vantom | 54 | 29% | 46% | 79 | 26% | 48% |
| Lagavulin Matriarch | 61 | 27% | 49% | 65 | 21% | 57% |
| Soul Fysh | 39 | 10% | 79% | 50 | 14% | 72% |
| Waterfall Giant | 67 | 0% | 90% | 79 | 0% | 81% |

Many boss losses are close, so better tactics (HP preservation, block timing,
potion use and phase-specific play) can plausibly convert a substantial share.
HP fraction ignores later phases and healing, so this is descriptive, not a
winnability estimate. Produced by `runs/boss-elite-benchmark-20261017/boss_losses.py`. In the earlier held-out Act 1 runs, the 250k model reached the
eruption with a mean 13 HP against a mean 34 damage and usually ended that turn
without block. The Giant is the clearest targeted-training opportunity.

## Interpretation

- **The Vantom specialist is the strongest boss model overall**, not only on
  Vantom. Its 250k Vantom-only PPO gained 3 points across all six bosses over its
  initializer, including +5.8 on Vantom and +8.0 on the Giant, without changing
  elites. Earlier "regression" readings came from its noisy 42-fight panel.
- **Imitating successful hard fights helps.** The seed-1 gain is now resolved for
  bosses and elites; seed 2 points the same way. Learner seeds still differ by
  2–4 points, so method comparisons need several seeds.
- **Campaign models are weaker fighters** than dedicated combat models, which is
  consistent with the higher Act 1 clear rate of combat hybrids. Further Act 1
  training (250k to 500k) did improve combat substantially.
- **The hardest encounters** are the Waterfall Giant (best 23%), Lagavulin
  Matriarch (best 29%), The Kin (best 48%) and the Phantasmal Gardeners elite
  (51–73%). Ceremonial Beast is largely solved by the stronger models.
- All learned policies and the heuristic used every usable potion in boss fights
  (373 of 385 carried); only timing differs, not count.

## Limits

- Greedy play on frozen snapshots realizes one hidden draw order and RNG per
  fight. Replaying fights with resampled hidden state would further reduce
  checkpoint-to-checkpoint noise; it changes RNG semantics and awaits its own
  implementation and independent review.
- Starts are conditioned on one collector's decks, routes and survival. Bosses
  are nearly always entered healthy, so low-HP boss play is barely measured.
- Each model is one checkpoint. The benchmark measures checkpoints precisely; it
  does not measure repeatability across learner seeds.
- This is a development panel. Repeated use for selection makes later results
  optimistic; use a fresh seed range, not the placeholder test split, for a
  held-out claim.
- The corpus is bound to the implementation identity. After any source change,
  rebuild it with the same settings, start index and parallel workers (each
  campaign then runs the greedy collector with one Torch thread). Seeds, collector
  and rules determine the fights; compare public start digests to confirm.
- Normal fights were not evaluated in this run.

## Validation and timing

- Focused tests: `tests/agent/test_combat_corpus.py` 27 passed (6 new: serial and
  parallel parity with heuristic and learned collectors, parallel cancellation,
  collector change after planning, room-kind filter and test lock, balanced
  weighting and paired resampling); `tests/agent/test_cli_performance.py` 29
  passed (1 new worker-default test); diagnostics, curriculum and Search
  consolidation consumers 70 passed after one CLI robustness fix.
- Measured times: corpus collection 5 min 43 s; evaluation 14 min 37 s wall.
  Implementation and review time was not instrumented.

## Reproduce

```bash
sts-agent-train build-combat-corpus --output-dir runs/boss-elite-benchmark-20261017/corpus \
  --checkpoint runs/act1-increased-500k-8workers-20260930/chunk-15/final.sts-model \
  --train-campaigns 1 --validation-campaigns 512 --test-campaigns 1 \
  --start-index 30000000 --route-policy mixed_elites --capture-turns 1 --workers 16
runs/boss-elite-benchmark-20261017/evaluate-validation.sh
python runs/boss-elite-benchmark-20261017/analyze.py \
  runs/boss-elite-benchmark-20261017/eval-validation/combat-benchmark.json
```
