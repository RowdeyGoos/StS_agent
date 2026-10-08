# Vantom: second Search training round — 2026-10-08

The existing 50k Search student was both the **frozen teacher and exact weight
initializer** for another **50,000 fresh game decisions**. The resulting student
has **100,000 cumulative Search collection decisions**. With Search, it won
**27/42 validation fights (64.3%)**, versus
**25/42 (59.5%)** for the 50k teacher.
The paired interval includes zero, so this panel does not establish a reliable improvement over the 50k teacher.

## Matched validation comparison

| Controller | Wins | Win rate | Mean remaining HP on wins |
| --- | ---: | ---: | ---: |
| 50k Search student, network only | 19/42 | 45.2% | 23.63 |
| 50k Search student + Search | 25/42 | 59.5% | 24.44 |
| 100k Search student, network only | 19/42 | 45.2% | 24.21 |
| 100k Search student + Search | 27/42 | 64.3% | 22.22 |
| 250k PPO specialist, network only | 26/42 | 61.9% | 22.04 |
| 250k PPO specialist + Search | 28/42 | 66.7% | 22.36 |

All six controllers completed the same 42 previously used validation openings:
252 completed fights, with no execution failures or episode cutoffs. The four
unchanged controls reproduce all 168 prior action sequences and scores exactly.
Evaluation uses the original analysis seeds, deterministic Search selection,
and a fixed final checkpoint after two epochs. No checkpoint or search setting
was selected using these new results.

| Paired comparison | Observed difference | 95% paired campaign bootstrap |
| --- | ---: | ---: |
| 100k Search student + Search versus 50k Search student + Search | +4.76 pp | [-7.14, +16.67] pp |
| 100k Search student, network only versus 50k Search student, network only | +0.00 pp | [-11.90, +11.90] pp |
| 100k Search student + Search versus 100k Search student, network only | +19.05 pp | [+7.14, +30.95] pp |
| 100k Search student + Search versus 250k PPO specialist, network only | +2.38 pp | [-7.14, +11.90] pp |
| 100k Search student + Search versus 250k PPO specialist + Search | -2.38 pp | [-11.90, +7.14] pp |

Intervals resample paired source campaigns 20,000 times with a fixed seed;
each opening has a distinct source campaign. The report also retains the
existing conservative Hoeffding intervals and paired HP/return/potion metrics.
Secondary comparisons are descriptive. Repeated development evaluation is not
held-out evidence: **all 57 reserved test fights remain unopened**. No model or
searched controller is promoted to the default, and no Act 1 benefit is measured.

The network-only win count is unchanged: three earlier defeats became wins, but
three earlier wins became defeats. Search wins eight additional cases over the
new student's network alone and loses none of its 19 wins. That Search benefit
has a paired bootstrap interval of [+7.14, +30.95] percentage points on this
development panel. It supports using Search with this checkpoint here; it does
not establish that the second training round improved the actor or that the
new searched student is reliably stronger than the previous searched student.

## Continuation and learning

The teacher is the [first-round student](../../runs/vantom-search-training-20261008/student/final.sts-model),
SHA-256 `eb608a617bd68e1c4f39b3e72ae8a7c1568bcde31b06b05936ac30624dd2e00e`.
All 38 initial parameter tensors, architecture, vocabulary and public input view
match that checkpoint exactly. The student uses a fresh Adam optimizer for this
distillation round; it is a continuation of the learned weights, not an exact
optimizer-state resume. The teacher stays frozen across all five collection
chunks. This is fresh collection, not reanalysis or reuse of the old 50k targets.

Both Search students descend from the same pre-specialization initializer as the
250k PPO specialist. The original first-round data, protocols and checkpoints
remain immutable. Round 2 has its own frozen protocol, fresh collection/analysis
seeds, and separately bound artifacts.

Collection produced **50,000 actual game decisions**:
**39,423 searched choices** and **10,577 forced actions**.
The 2,351 episodes include 2,273 completed fights and
78 unfinished quota-limited fights. There are
38,522 searched examples with completed-return critic labels;
901 retain missing labels. Unfinished fights are not defeats.
Forced actions count toward the real-decision budget but are excluded from
distillation examples.

Training uses **2 complete epochs**, **78,846 sample
presentations**, and **2,464 optimizer updates** over the fresh targets only.
Settings match round 1: batch 32, learning rate 0.0001, value-loss weight 0.25,
gradient clip 1, combat graph actor–critic with hidden size 48 and two message
layers. The actor learns the Search probability distribution; the critic learns
completed undiscounted behavior returns. No searched trajectory enters PPO.
Learner seed: 2026100802.

## Search and data boundaries

Use 16 workers with one Torch thread each and four learner threads. Search uses
24 simulations, depth 16, four greedy leaf actions, two belief particles,
4,096 proposals and 2,048 replay proposals. Gumbel exploration is enabled during
collection and disabled during evaluation. Search and belief ceilings are 120s;
separate episode limits are 512 decisions and 1,800s. The combat objective remains
victory plus 0.1 times settled winning HP fraction, defeat zero.

The unchanged sampler draws from the same 101 training fights, with 101 openings
and 567 continuation starts. It balances opening/continuation starts within each
sampled fight. This round covers 101 source fights and
595 distinct saved starts. These are fresh trajectories from
the existing training population, not 50,000 distinct fights.

The accepted public-prefix producer and corrected rules proof are reused.
Actual private snapshots remain evaluator inputs; Search receives only the
public inventory, accepted history and reveal receipts. Split delegation and
artifact hashes are checked at execution boundaries. The independent review
confirmed fresh seeds, exact action accounting, frozen teacher identity, public
information boundaries and safe continuation.

All eligible collection decisions were searched, completing
**946,152 simulations** and **3,176,597 leaf actions**.
There were zero unsupported fallbacks, search cutoffs or timed leaf bootstraps.
All three searched validation arms likewise have full eligible coverage and no
search cutoffs. Searched collection latency was median **2.019s**,
p95 **2.481s**, maximum **4.565s**;
0 actions exceeded five seconds. These measurements include
concurrent worker scheduling and belief work, not a universal latency guarantee.

## Cost and validation

| Phase | Measured wall time |
| --- | ---: |
| 50k collection | 83.39 min |
| Data preparation, two training epochs and checkpoint publication | 12.11 min |
| Optimization/checkpoint work within that phase | 47.00 s |
| Six-arm validation | 6.85 min |

This run uses the optimized implementation measured in the
[speed benchmark](SEARCH_TRAINING_SPEED_2026_10_08.md). The teacher and sampled
trajectories differ from round 1, so elapsed-time differences are not an isolated
optimization experiment.

No production source changed for this round. Source-identical accepted agent,
package, focused and compilation evidence is reused, rather than rerun during
timed collection. A new 256-decision smoke and two learner updates passed and
are excluded from the 50k budget. Independent semantic review has no remaining
blockers. The postrun audit verifies exact initialization, all collection/evaluation
artifact bindings, target counts and normalized distributions, complete fixed
search work, completed-fight handling and the 168 unchanged control games.
Separate preparation/review elapsed times were not recorded. No live release or
installation was involved.

## Saved artifacts

- [Machine-readable evidence](vantom_search_round2_2026_10_08.json)
- [100k cumulative student](../../runs/vantom-search-round2-20261008/student/final.sts-model), SHA-256 `b026cc683387db0fb01e01594d8a5b25fca7dbbf2919ffd2a0876ad7d889be36`
- [Frozen protocol](../../runs/vantom-search-round2-20261008/protocol.json)
- [Learner report](../../runs/vantom-search-round2-20261008/student/search-distillation.json)
- [Complete evaluation](../../runs/vantom-search-round2-20261008/evaluation.json)
- [Initialization audit](../../runs/vantom-search-round2-20261008/initialization-audit.json) and [control audit](../../runs/vantom-search-round2-20261008/control-audit.json)
- [Source archive manifest](../../runs/vantom-search-round2-20261008/source-archive.json)

The bundle is `runs/vantom-search-round2-20261008/`. New student Search traces are
under `evaluation-student_search/` and retain the existing viewer's Search panel.
The local **Vantom search 50k** experiment stores this continuation under clearly
named **round 2 / 100k cumulative** learner and matched-comparison runs.
