# Fights won by any player on the boss and elite benchmark — 2026-11-12

Status: **complete reanalysis of existing reports.** No new games, no training
and no default change. It was made for the [combat overview](../COMBAT_OVERVIEW.md),
because the benchmark's achievable ceiling has never been measured.

## Result

Count a fight as won if at least one evaluated player won it. On the
[boss and elite benchmark](BOSS_ELITE_BENCHMARK_2026_10_17.md), 75 players with
distinct outcomes have played the same 1,728 frozen openings.

| Room kind | Best network | Search, 24 simulations | Any of the first ten players | Any of the 75 players | Any player − search, 95% |
| --- | ---: | ---: | --- | --- | --- |
| Boss (equal weight) | 48.7% | 55.5% | 63.4% [59.9, 66.9] | **69.5%** [65.9, 72.8] | +13.9 [+11.3, +16.8] |
| Elite (equal weight) | 79.1% | 85.8% | 88.9% [87.0, 90.6] | **90.9%** [89.2, 92.5] | +5.1 [+3.8, +6.4] |

| Encounter | Fights | Best network | Search | Any player | Won by nobody |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ceremonial Beast | 100 | 78.0% | 82.0% | 89.0% | 11 |
| The Kin | 100 | 48.0% | 60.0% | 73.0% | 27 |
| Vantom | 120 | 55.0% | 63.3% | 74.2% | 31 |
| Lagavulin Matriarch | 85 | 28.2% | 35.3% | 52.9% | 40 |
| Soul Fysh | 97 | 59.8% | 66.0% | 89.7% | 10 |
| Waterfall Giant | 87 | 23.0% | 26.4% | 37.9% | 54 |
| Bygone Effigy | 204 | 81.9% | 86.8% | 92.6% | 15 |
| Byrdonis | 201 | 83.6% | 85.6% | 89.1% | 22 |
| Phrog Parasite | 207 | 81.6% | 89.9% | 95.7% | 9 |
| Phantasmal Gardeners | 181 | 68.0% | 83.4% | 88.4% | 21 |
| Skulking Colony | 170 | 81.8% | 84.7% | 88.2% | 20 |
| Terror Eel | 176 | 77.8% | 84.7% | 91.5% | 15 |

- **Nobody won 173 of the 589 boss fights or 102 of the 1,139 elite fights.** The
  Waterfall Giant (54 of 87) and Lagavulin Matriarch (40 of 85) account for 94
  of the 173 boss fights.
- **The search arm adds little to the union.** Without it, any player wins 69.0%
  of bosses and 90.6% of elites.
- **HP on arrival separates boss outcomes strongly:**

| Boss entered with | Fights | Best network | Search | Any player |
| --- | ---: | ---: | ---: | ---: |
| under 50% HP | 35 | 3 (8.6%) | 4 (11.4%) | 8 (22.9%) |
| 50–70% HP | 106 | 24 (22.6%) | 35 (33.0%) | 54 (50.9%) |
| 70–85% HP | 95 | 43 (45.3%) | 48 (50.5%) | 61 (64.2%) |
| 85% HP or more | 353 | 224 (63.5%) | 248 (70.3%) | 293 (83.0%) |

## What the union is, and is not

**It is a floor on the perfect-information ceiling.** A fight that some public
policy won from its frozen start has a winning line of play in that realization.
A player that could see the hidden draw order and RNG could win at least these
fights.

**It is not a floor for one policy.** Players of equal strength win different
fights. The six final learners of the
[hidden-state study](COMBAT_HIDDEN_STATE_2026_10_17.md) share one recipe:

| Six similar learners | Bosses | Elites |
| --- | ---: | ---: |
| Each alone (range) | 46.9–49.6% | 80.1–81.7% |
| At least one of the six | 60.6% | 87.9% |
| All six | 35.6% | 73.1% |

A quarter of the boss fights therefore change hands between near-identical
players. Part of the gap between search and the union is this spread of luck,
not skill that one policy could acquire.

**"Won by nobody" is not "unwinnable".** Nearly all of these players descend
from one training recipe and one collector's decks, so they can share blind
spots. The Waterfall Giant's eruption, which most learned players fail to
survive, is a likely one.

**The union grew with each batch of different players** and stopped growing with
near-copies. The distillation students barely moved from their initializer, so
they add no fights. This does not show that the union has converged.

| Players added | Policy arms | Any player, bosses | Any player, elites |
| --- | ---: | ---: | ---: |
| Benchmark, nine policies | 9 | 59.0% | 86.4% |
| + search run | 11 | 63.5% | 88.9% |
| + hidden-state PPO learners | 36 | 67.1% | 90.3% |
| + minibatch PPO learners | 79 | 69.5% | 90.9% |
| + distillation students | 106 | 69.5% | 90.9% |

The ceiling for a public-information player lies between search's 55.5% and
the unmeasured perfect-information ceiling, which is at least 69.5% for bosses.
A solver that may see the hidden state would measure that upper bound. The 173
boss fights that nobody has won are the informative place to start. The
[ceiling record](COMBAT_CEILING_2026_11_12.md) reports that measurement: a
player or the solver won 82.8% of the boss fights.

## Method

- **Sources:** 14 public reports: the benchmark, the
  [search run](COMBAT_SEARCH_BENCHMARK_2026_10_17.md), and the benchmark
  evaluations of the [hidden-state](COMBAT_HIDDEN_STATE_2026_10_17.md),
  [minibatch](COMBAT_MINIBATCH_2026_10_18.md) and
  [distillation](COMBAT_SEARCH_DISTILLATION_2026_10_18.md) studies, including
  their intermediate checkpoints and follow-ups.
- **Players:** 106 policy arms with 75 distinct outcome vectors: 68 greedy
  network arms, one search arm and six baseline rows. Arms with identical
  outcomes count once.
- **Matching:** by encounter and public start digest, because rebuilt corpora
  change the opaque case IDs. Every arm covers all 1,728 fights; the script
  stops otherwise.
- **Counting:** as in the reports. A fight is won only if it terminated in
  victory; failures and cutoffs are non-wins.
- **Rates and intervals:** each encounter has equal weight. Intervals use the
  benchmark's bootstrap: 2,000 resamples of whole source campaigns, seed
  20261017, shared by all columns. The script reproduces the published estimate
  and interval for the specialist exactly. It groups every arm by the original
  benchmark's campaigns, so its search interval ([51.8, 59.3]) differs in the
  last digit from the published one.
- **First ten players:** the nine benchmark policies and the search arm.

## Limits

- Greedy play on one frozen realization per fight, from one collector's decks,
  routes and survival.
- A reused development panel; these are descriptive counts, not a held-out claim.
- No perfect-information or exhaustive solver was run, so the upper bound is
  still unmeasured.
- The HP table pools fights across bosses; it does not separate HP from the
  decks and routes that produced it.

## Reproduce

```bash
.venv/bin/python runs/boss-elite-benchmark-20261017/any_policy_wins.py \
  runs/boss-elite-benchmark-20261017/any-policy-wins.json
```

The output, SHA-256 `8e111c9450d319ddfbbf68d895cb39f926407100533c152e5319f25d8c3618f1`,
lists every source report with its SHA-256. A second run reproduced it byte for
byte. The script runs in about two seconds; implementation time was not
measured. User wait: none.
