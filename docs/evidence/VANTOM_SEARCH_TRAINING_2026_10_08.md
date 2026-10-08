# Vantom: search coverage and 50k training decisions — 2026-10-08

**The new student with Search won 25/42 validation fights (59.5%), versus 26/42 (61.9%) for the current 250k PPO specialist.** This rough comparison does not establish that the new system is better or equivalent: the paired 95% interval is [-19.05, +11.90] percentage points.

The student started from the **same pre-specialization initializer** as the PPO specialist. Collection completed exactly **50,000 fresh game decisions**, including **39,167 searched choices** and **10,833 forced actions**. All eligible collection decisions were searched. No held-out test fight was opened, and no model was promoted to the default.

## Matched validation results

| Controller | Wins | Win rate | Mean remaining HP on wins |
| --- | ---: | ---: | ---: |
| Original initializer | 22/42 | 52.4% | 22.91 |
| Initializer, search input view | 22/42 | 52.4% | 22.91 |
| Initializer + Search | 22/42 | 52.4% | 24.36 |
| Original PPO, 50k decisions | 19/42 | 45.2% | 24.16 |
| Current PPO specialist, 250k decisions | 26/42 | 61.9% | 22.04 |
| 250k specialist, search input view | 26/42 | 61.9% | 22.04 |
| 250k specialist + Search | 28/42 | 66.7% | 22.36 |
| New Search student, network only | 19/42 | 45.2% | 23.63 |
| New Search student + Search | 25/42 | 59.5% | 24.44 |

All nine arms completed all 42 fights: no game cutoff, interruption or execution failure. Each arm used 17 potions across the panel. Each opening belongs to a different source campaign; all arms share the same actual starts and the searched arms share analysis seeds. These are previously used development cases, not a fresh held-out benchmark.

| Paired comparison | Observed difference | 95% paired campaign bootstrap |
| --- | ---: | ---: |
| Student + Search versus 250k specialist | -2.38 pp | [-19.05, +11.90] pp |
| Student + Search versus student alone | +14.29 pp | [-2.38, +30.95] pp |
| Student alone versus initializer with same input view | -7.14 pp | [-16.67, +2.38] pp |
| Student alone versus original 50k PPO | +0.00 pp | [-9.52, +9.52] pp |
| 250k specialist + Search versus same-view specialist | +4.76 pp | [-7.14, +16.67] pp |

Intervals resample paired source campaigns 20,000 times with a fixed seed. The raw report also retains conservative Hoeffding intervals. Secondary comparisons are descriptive. The student-alone result does not demonstrate that distillation improved the network. Search improves its observed score, but this small panel does not establish a reliable win-rate gain. The original 50k PPO endpoint is a useful budget reference; fifty thousand Search decisions, fifty thousand PPO decisions and the specialist's 250,000 decisions have different compute costs. The 50k PPO endpoint was not separately evaluated with Search here.

## Coverage repair and information boundary

The [October 7 comparison](VANTOM_SPECIALIST_SEARCH_2026_10_07.md) searched only 62.2% of non-forced decisions. Autoplay, visible generation, retention, turn-triggered draws and several potions exhausted its supported prefixes. The new `revealed_belief_v1` producer supplies public intermediate reveal receipts and advances hypothetical states through the ordinary engine.

The observer records drawn/autoplayed card descriptions, visible generated cards and potions, and displayed random energy costs. It exports no actual draw order, private identity, seed or masked raw cost setter. Proposals retain duplicate-card multiplicity and sum probabilities of hidden setters with identical visible costs. Known placements survive ordinary movement, random insertion and reshuffling. Enabling the observer leaves actual game state and RNG consumption unchanged.

The original source collector was replayed to recover the public prefixes for **935 train/validation starts**. Every replay reproduced its exact saved snapshot and public root. All prefixes then reconstructed and sampled successfully. The planner receives public pre-combat inventory, opening, accepted actions/successors and reveal receipts. Private continuation snapshots remain evaluator inputs. The split delegation chain and current validation owner were checked; old evidence was not repinned.

Collection used 101 training fights, with 101 openings and 567 continuation starts. The unchanged PPO sampler selects a source fight uniformly, chooses opening versus continuation with equal probability where both exist, then samples the continuation. Collection covered all 101 fights and 586 distinct starts, without filtering decks using support or evaluation outcomes.

| Corrected evaluation arm | Searched / eligible | Eligible coverage | Forced actions | Unsupported fallbacks |
| --- | ---: | ---: | ---: | ---: |
| Initializer + Search | 937/937 | 100.0% | 251 | 0 |
| 250k specialist + Search | 990/990 | 100.0% | 258 | 0 |
| New Search student + Search | 959/959 | 100.0% | 245 | 0 |

The initial frozen evaluation uncovered one additional selector failure on case `08ebccdda466438bae165f82e10fc89a`. Resampling hypothetical draw order left **Droplet of Precognition**'s cached internal candidate order stale; strict snapshot validation correctly refused the next fork. The repair refreshes only derived ordering using ordinary eligibility queries. It preserves membership, selected order, bounds, known placements and sampled whitelists, consumes no engine RNG, and covers the other draw-selector families as well.

The completed 50k training run, its checkpoint, and the original evaluation remain unchanged. A separately frozen correction reran the same nine arms and settings. All 252 network-only case action sequences and scores are identical across the two evaluations; the original specialist also reproduces the October 7 baseline exactly. Both evaluation versions and their differences are retained in the machine-readable evidence.

This coverage is verified for the admitted headless Vantom population. Generic CLI producers retain their existing admission rules. Arbitrary old snapshots and the live bridge do not gain automatic support: they need equivalent public inventory/history and ordered reveal receipts. Beliefs use two particles, and simulated tree child keys still omit intermediate reveal journals. These remain planning approximations.

## Training and search settings

Teacher and student initialization: `runs/vantom-specialist-training-20261002/initializer/initial.sts-model`, SHA-256 `a27da5b53aaa6332e0657a2fc3baa3d84e78e4714732d5d4e870e92376817fd2`. This is the original imitation actor with its calibrated value head, before PPO specialization. An exact tensor audit verifies identical starting weights, architecture and vocabulary. The student uses the declared detached combat-history input view.

Collection used 16 workers, one Torch thread each, in five operational chunks of 10,000 actions. **The same teacher stayed frozen throughout.** The 1,024-action smoke, prefix recovery and validation are outside the 50k training budget. There were 2,333 collected episodes: 2,256 completed fights and 77 quota truncations. Of 39,167 search targets, 38,301 have completed-return critic labels; 866 retain missing labels. Unfinished fights were never treated as defeats.

The student received two full epochs over the targets: **78,334 presentations and 2,448 optimizer updates**. Settings: batch 32, Adam learning rate 0.0001, value-loss weight 0.25, gradient clipping 1, seed 20261008. The existing rich combat graph actor–critic has hidden size 48 and two message-passing layers. Compact feature loading avoids duplicate lossless arrays. Search trajectories were not used as on-policy PPO data. This was one frozen-teacher distillation round, with no teacher promotion or reanalysis.

Search settings: 24 simulations, depth 16, four greedy policy actions at each leaf, two belief particles, 4,096 proposals, 2,048 replay proposals, q-scale 0.1, final prior/value selection. Gumbel exploration was enabled in collection and disabled in evaluation. Per-action and belief ceilings were 120 seconds so scheduling did not silently reduce fixed work; episodes had separate limits of 512 actions and 1,800 seconds. Objective: victory plus 0.1 × settled winning HP fraction, defeat zero, including combat cleanup healing. It is a combat proxy, not Act 1 success.

The checkpoint endpoint, settings and evaluation arms were frozen before the first new validation games. The selector correction was a correctness repair, not outcome-based tuning. The **57 reserved test fights remain unopened**.

## Measured cost and validation

| Phase | Wall time |
| --- | ---: |
| 50k collection, 16 workers | 102.96 min |
| Data loading, student optimization and publication | 17.38 min |
| Optimization and checkpoint work within that phase | 55.93 s |
| Original nine-arm evaluation | 8.47 min |
| Corrected nine-arm evaluation | 8.46 min |

Collection completed **940,008 simulations**, with no unsupported fallback or search-budget cutoff. Searched-action latency was median **2.512s**, p95 **3.112s**, maximum **5.763s**. Seven searched actions exceeded five seconds. These timings include belief conditioning and concurrent fights; the tail therefore does not establish a universal five-second bound. Broad validation overlapped the start of collection. Loading dominated the learner phase; optimization itself took under one minute.

The original implementation passed 7,372 headless/package checks (1,417.70s) and 1,616 agent checks (654.25s), with one skip. Focused precollection, consumer, smoke, public/RNG adversarial and prefix checks also passed; overlapping test counts are not added together. After the selector correction, **1,072 affected tests passed in 54.15s**, and all 935 prefixes were replayed/revalidated again. Independent semantic review covered the public/RNG boundary, selection repair, and experiment evidence/split boundaries. No blocking findings remain. Separate implementation/review elapsed times were not recorded. No live release packaging or user setup was needed.

## Saved artifacts

- [Final machine-readable evidence](vantom_search_training_2026_10_08.json)
- [Trained student](../../runs/vantom-search-training-20261008/student/final.sts-model), SHA-256 `eb608a617bd68e1c4f39b3e72ae8a7c1568bcde31b06b05936ac30624dd2e00e`
- [Original frozen training protocol](../../runs/vantom-search-training-20261008/protocol.json) and [learner report](../../runs/vantom-search-training-20261008/student/search-distillation.json)
- [Corrected evaluation protocol](../../runs/vantom-search-training-20261008/correction/protocol.json) and [complete evaluation](../../runs/vantom-search-training-20261008/correction/evaluation.json)
- [Original evaluation, preserved](../../runs/vantom-search-training-20261008/evaluation.json)
- [Initialization and historical baseline audit](../../runs/vantom-search-training-20261008/postrun-audit.json)
- [Original source archive manifest](../../runs/vantom-search-training-20261008/source-archive.json) and [corrected source archive manifest](../../runs/vantom-search-training-20261008/correction/source-archive.json)

The local bundle is `runs/vantom-search-training-20261008/`. Public trajectories and search diagnostics are separate from owner-only private replay records. The corrected student traces under `correction/evaluation-student_search/` can be opened by the existing trace viewer, including its Search panel. Local MLflow experiment **Vantom search 50k** retains the student and corrected comparison.
