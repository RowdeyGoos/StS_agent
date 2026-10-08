# Vantom: third Search training round — 2026-10-08

The 100k Search student was both the **frozen teacher and exact weight initializer**
for another **50,000 fresh game decisions**, producing a **150k cumulative student**.
With Search, the new student won **28/42 validation fights
(66.7%)**, versus **27/42
(64.3%)** for its teacher. The paired interval includes zero, so this panel does not establish a reliable change from the 100k teacher.

## Matched validation comparison

| Controller | Wins | Win rate | Mean remaining HP on wins |
| --- | ---: | ---: | ---: |
| 100k Search student, network only | 19/42 | 45.2% | 24.21 |
| 100k Search student + Search | 27/42 | 64.3% | 22.22 |
| 150k Search student, network only | 22/42 | 52.4% | 23.23 |
| 150k Search student + Search | 28/42 | 66.7% | 21.32 |
| 250k PPO specialist, network only | 26/42 | 61.9% | 22.04 |
| 250k PPO specialist + Search | 28/42 | 66.7% | 22.36 |

All six controllers completed the same 42 previously used validation openings:
252 completed fights, with no execution failures or episode cutoffs. The four
unchanged controls reproduce all 168 prior action sequences and scores exactly.
Evaluation retains the original analysis seeds and deterministic Search selection.
The final checkpoint and two-epoch budget were fixed before collection; there
was no validation-based checkpoint or hyperparameter selection.

| Paired comparison | Observed difference | 95% paired campaign bootstrap |
| --- | ---: | ---: |
| 150k Search student + Search versus 100k Search student + Search | +2.38 pp | [-4.76, +11.90] pp |
| 150k Search student, network only versus 100k Search student, network only | +7.14 pp | [-2.38, +16.67] pp |
| 150k Search student + Search versus 150k Search student, network only | +14.29 pp | [+2.38, +28.57] pp |
| 150k Search student + Search versus 250k PPO specialist, network only | +4.76 pp | [-9.52, +19.05] pp |
| 150k Search student + Search versus 250k PPO specialist + Search | +0.00 pp | [-11.90, +11.90] pp |

The new network alone gains 4 cases and loses
1 case relative to the previous network.
Search gains 7 cases and loses
1 case relative to the new network alone.
These paired changes matter alongside the aggregate win counts.

Intervals resample paired source campaigns 20,000 times with a fixed seed.
Each opening belongs to a distinct source campaign. Raw reports retain the
existing conservative Hoeffding intervals and paired HP/return/potion metrics;
secondary comparisons are descriptive. These repeatedly used development fights
are not fresh held-out evidence. **All 57 reserved test fights remain unopened.**
No model/controller becomes the default, and no Act 1 benefit is measured.

## Continuation and learning

Teacher: [100k student](../../runs/vantom-search-round2-20261008/student/final.sts-model),
SHA-256 `b026cc683387db0fb01e01594d8a5b25fca7dbbf2919ffd2a0876ad7d889be36`.
All 38 initial tensors, architecture, vocabulary and public input view match
that checkpoint exactly. The teacher stays frozen through all five 10k chunks.
The student starts with those learned weights and fresh Adam state, matching
the previous round; this is not an exact optimizer-state resume.

This round uses fresh collection seeds and only its new targets. Earlier
collections, protocols, checkpoints and evidence remain immutable. It does not
reanalyze or retrain on earlier targets. All three Search rounds descend from
the same pre-specialization initializer as the 250k PPO specialist. Equal counts
of Search and PPO decisions do not imply equal compute budgets.

Collection produced **50,000 real game decisions**, comprising
**39,667 searched choices** and **10,333 forced actions**.
There are 2,308 episodes: 2,230 completed fights and
78 unfinished quota-limited fights.
The searched examples have 38,784 completed-return critic labels and
883 missing labels. Unfinished fights are never counted as defeats.
Forced actions remain in public trajectories and count toward the decision
budget, but are excluded from distillation examples.

The learner completed **2 epochs**, **79,334 presentations**,
and **2,480 updates**. Settings are unchanged: batch 32, learning rate 0.0001,
value-loss weight 0.25, gradient clip 1, hidden size 48, two graph message layers,
and the detached public combat-history view. The actor learns the Search
distribution; the critic learns completed undiscounted behavior returns. No
searched trajectory enters PPO. Learner seed: 2026100803.

## Search, coverage and cost

Use 16 workers with one Torch thread each and four learner threads. Search uses
24 simulations, depth 16, four greedy leaf actions, two belief particles,
4,096 proposals and 2,048 replay proposals. Gumbel exploration is enabled during
collection and disabled during evaluation. Search and belief ceilings are 120s;
separate episode limits are 512 decisions and 1,800s. The objective remains
victory plus 0.1 times settled winning HP fraction, defeat zero.

The unchanged sampler draws from the same 101 training fights, containing
101 openings and 567 continuation starts. It balances opening/continuation starts
within sampled fights. This round covers 101 source fights and
588 distinct saved starts. The budget counts fresh trajectories and
actions from that population, not distinct fights.

The accepted public-prefix producer, corrected rules proof and existing engine
are reused. Actual private snapshots remain evaluator inputs; Search receives
public inventory/history and reveal receipts. Source identity, split delegation
and artifact bindings are checked at execution boundaries.

All eligible collection decisions were searched, completing
**952,008 simulations** and **3,213,139 leaf actions**.
There were no unsupported fallbacks, search cutoffs or timed leaf bootstraps.
All three searched validation arms also have complete eligible coverage.
Searched collection latency: median **2.052s**, p95 **2.526s**,
maximum **4.567s**; 0 actions exceeded five seconds.
These include concurrent scheduling and belief work, not a universal latency bound.

| Phase | Measured wall time |
| --- | ---: |
| 50k collection | 85.48 min |
| Data preparation, training and publication | 12.08 min |
| Optimization/checkpoint work within that phase | 46.68 s |
| Six-arm validation | 6.81 min |

The implementation is unchanged from the [speed benchmark](SEARCH_TRAINING_SPEED_2026_10_08.md)
and [round 2](VANTOM_SEARCH_ROUND2_2026_10_08.md). Teachers and sampled trajectories
differ, so round-to-round wall times are not isolated optimization comparisons.

## Validation and artifacts

No production source changed. Source-identical accepted agent/package/focused
tests and compilation evidence are reused. A new 256-decision smoke and two
learner updates passed and are excluded from the budget. Independent review
confirmed exact quotas, seed disjointness across all three rounds, frozen
teacher/initializer identity, split/public-information boundaries, immutable
parent artifacts, continuation and prior-control mappings, with no blockers.
The final audit checks all collection/evaluation bindings, target normalization,
fixed simulation work, completed-value handling and the 168 unchanged controls.
Separate preparation/review elapsed times were not recorded. No live release
or installation was involved.

- [Machine-readable evidence](vantom_search_round3_2026_10_08.json)
- [150k cumulative student](../../runs/vantom-search-round3-20261008/student/final.sts-model), SHA-256 `7805954e02238a6928a3c15ce2b6d65e492f1743a3a1bb87054dc8ffa5d9c9b0`
- [Frozen protocol](../../runs/vantom-search-round3-20261008/protocol.json)
- [Learner report](../../runs/vantom-search-round3-20261008/student/search-distillation.json)
- [Complete evaluation](../../runs/vantom-search-round3-20261008/evaluation.json)
- [Initialization audit](../../runs/vantom-search-round3-20261008/initialization-audit.json) and [control audit](../../runs/vantom-search-round3-20261008/control-audit.json)
- [Source archive manifest](../../runs/vantom-search-round3-20261008/source-archive.json)

The bundle is `runs/vantom-search-round3-20261008/`. Student Search traces are in
`evaluation-student_search/` and retain the trace viewer's Search diagnostics.
The local **Vantom search 50k** experiment stores this continuation in clearly
named **round 3 / 150k cumulative** learner and matched-comparison runs.
