# Combat search with short policy rollouts and search learning

**October 6, 2026 — bounded local study.** This record uses authored Ironclad A0
inventories. It does not establish campaign or native-bridge performance.

Rollout-assisted search improved the original checkpoint from **90/128 to
100/128 wins on fresh challenge fights**, a paired gain of **7.81 percentage
points [3.13, 13.28]**. The cost-matched development comparison had selected
24 simulations with four greedy leaf actions, averaging about **1.4 seconds per
eligible decision**. The engine still executes every simulated game rule.

One 480-fight learning round produced three students. The selected student's
fresh score was **94/128 without search and 100/128 with search**. It therefore
did not improve searched wins over the original searched checkpoint. The small
network-only gain rests on four changed outcomes. Inventory-variant results
also failed to show an extra benefit from the learned checkpoint. Search remains
experimental, with a useful combat result on this authored population; campaign
benefit and an incremental search-learning gain remain unestablished.

## What changed

Search optionally continues a sampled leaf with a bounded greedy policy rollout
through the existing engine. The network receives only public simulated
observations. A completed hypothetical fight returns its settled combat utility;
an unfinished rollout uses its final public critic. That estimate is backed up
for the current simulation, without replacing a shared node's network value.
The default remains critic-only search, including its historical teacher identity.

The existing collection command now accepts balanced developed inventories.
Distillation accepts exact dataset passes and multiple disjoint fresh/reanalysed
reports. It validates their input views and rejects repeated source fights,
including reruns with fresh UUIDs. Bounded reanalysis records its original source
and selected episode IDs, retaining actual behavior and outcome bytes. These
records remain offline actor/critic supervision, separate from PPO rollouts.
Root teachers, paired root-only evaluation and target-refresh tracking are also
supported. A narrow compatibility fix restores immediate damage previews when
the engine queries the optional draw-history observer; unknown random operations
still fail closed.

Operational commands and compatibility limits are in the
[training guide](../AGENT_TRAINING.md#experimental-combat-search).

## Frozen protocol and initializer

The existing [developed benchmark](COMBAT_SEARCH_DEVELOPED_BENCHMARK_2026_10_05.md)
provides four decks and 12 calibrated deck/encounter families. Every fresh start
has its explicitly declared cards/upgrades, 80 HP, relic counters and potion.
These are authored inventories, not sampled campaign decks.

The initializer is
`runs/direct-search-learning-student-20261004/initial.sts-model`, with the
`detached_combat_history_cards_v1` input view, `commit_decisions_v1`, and the exact
combat objective `victory + 0.1 × cleanup HP / max HP`, defeat zero, discount one.
Its weights match specialist PPO chunk 15: **199,152 specialist decisions** in
**1,096.91 seconds** of recorded chunk execution. This is not the total training
of every ancestor. The previous "250k endpoint" description was incorrect;
original checkpoint/report bytes and hashes remain unchanged.

A training-split timing pilot used 12 starts at index 30000. Budget selection used
latency only, without selecting on its win outcomes. Thirty-two simulations with
four greedy leaf actions averaged 1.870 seconds, versus 1.405 seconds for 64
critic-only simulations. The predeclared scaling rule selected **24 simulations
with four leaf actions** for the main rollout candidate.

The main development panel used **192 fresh starts**, indices 32000–32191:
128 challenge and 64 control fights. Every controller used the same initializer,
public information and actual starting seeds. Depth was 16, with two belief
particles and a five-second thinking ceiling; games had separate 160-action and
600-second limits. Four workers each used one Torch thread. Production source,
checkpoint, inventory, study runner, analysis and budgets were frozen before play.

Selection required completed fights, full work budgets, at least 95% eligible
search coverage, a positive paired challenge-return 95% lower bound and no fewer
challenge wins than the network. Paired percentile bootstrap intervals use
10,000 resamples of source fights, with analysis seed 60626. Controllers,
positions and learner repetitions are not counted as independent fights.
Development intervals are exploratory because they participate in selection.

## Teacher comparison

| Controller | All wins / 192 | Challenge wins / 128 | Mean / p95 eligible search time |
| --- | ---: | ---: | ---: |
| Network only | 158 | 94 | — |
| Root simulation/critic, 64 simulations | 159 | 95 | 0.791 / 0.961 s |
| Gumbel/critic, 64 simulations | 160 | 96 | 1.401 / 1.782 s |
| Gumbel + four-action rollout, 24 simulations | **165** | **101** | **1.399 / 1.887 s** |

All controllers won all 64 Slimes control fights and used the supplied potion in
every fight. There were no episode failures/cutoffs. All eligible search decisions
completed their full simulation budget, with no unsupported fallback or search
cutoff. Forced actions are excluded from the eligible denominator. The selected
teacher searched 3,386 eligible decisions; its longest recorded search was
**2.208 seconds**. These are local headless measurements at four workers, not
native end-to-end latency guarantees.

The selected teacher's paired challenge gain was **+5.47 percentage points**,
with a development bootstrap interval of **[+2.34, +9.38] pp**. Its mean return gain
was **+0.05681 [0.02305, 0.09782]**. The root and critic-only Gumbel return intervals
included zero, so neither qualified as the collection teacher.

The gains address the earlier benchmark concern directly:

| Vantom deck | Network wins / 16 | Rollout-search wins / 16 |
| --- | ---: | ---: |
| Block conversion | 0 | 1 |
| Strength | 14 | 16 |
| Exhaust/draw | 0 | 4 |

Both controllers won all other challenge families in this panel. On their 158
common wins, rollout search finished with **0.905 more HP on average**. Its lower
HP conditional on *all* wins is partly a denominator effect from adding difficult
wins; it should not be interpreted as a paired HP regression.

Profiling puts roughly 56% of selected-teacher search time in inference (including
encoding), 30% in public projection and 3% in game-rule transitions. The current
measurements support retaining the exact engine and profiling inference/projection
before considering learned dynamics as a performance remedy.

## Learning and fresh confirmation

The learning protocol admits up to two rounds, each with 480 fresh training
fights: 40 per family, comprising 320 challenges and 160 controls. Each round
freezes the teacher's weights and search configuration. Collection enables the
normal search exploration mode; evaluation uses deterministic selection. Three
students start from that round's same teacher checkpoint with fresh optimizers
and learning seeds 17, 23 and 41. Each receives exactly four dataset passes,
using minibatches of 32 and learning rate 0.0001. Actor supervision is the legal
search distribution; critic supervision is the recorded completed fight return.
The three repetitions do not create three independent training populations.

The selection panel is the same 192 development starts used for the teacher
comparison. Student ranking uses searched challenge wins, searched challenge
return, network-only challenge wins and finally learning seed. A later round
requires the predeclared development gate plus enough estimated time to finish
the round and confirmation before the deadline. If admitted, round two also
refreshes a predeclared balanced 96-fight prefix of round one; those value labels
remain outcomes of the original behavior.

Before any confirmation gameplay, the runner locks the selected checkpoint,
original checkpoint, search settings and populations. Confirmation compares
both checkpoints with and without search on 192 fresh test starts, followed by
96 starts with the reserved one-Strike-upgrade inventory variants. These test
results cannot select another student or change the settings.

Round one collected **480 completed fights: 409 wins and 71 losses**, in
**3,017.84 seconds (50.30 minutes)**. It produced 11,236 real decisions, of which
8,645 were eligible and searched with all 24 simulations. The other 2,591 were
forced actions and do not enter the eligible-search denominator or distillation
examples. There were no failures, cutoffs, unsupported fallbacks or incomplete
search budgets. The behavior used 478 potions across 480 fights.

Each student received **8,645 examples, 34,580 sample presentations and 1,084
optimizer updates**. That is one shared dataset and three learning repetitions,
not 1,440 independent training fights. The final minibatch in every epoch had
five examples and was retained.

| Learning seed | Network challenge wins / 128 | With search / 128 | Mean / p95 search time |
| --- | ---: | ---: | ---: |
| Original initializer | 94 | 101 | 1.399 / 1.887 s |
| 17 | 95 | 102 | 1.331 / 1.781 s |
| 23 | 95 | 104 | 1.336 / 1.765 s |
| **41 (selected)** | **95** | **105** | **1.334 / 1.773 s** |

Every controller retained all 64 control wins. All three student evaluations
completed without episode failures/cutoffs or incomplete eligible search
budgets. All passed the development gate. Seed 41's searched win gain over the
original network was **+8.59 pp [3.91, 14.06]**. Its gain over the original
searched teacher was **+3.13 pp [-2.34, 8.59]**; network-only improvement was
**+0.78 pp [-1.56, 3.91]**. The extra learning benefit was therefore inconclusive
on development, despite retention of the search benefit.

The round, including collection, training and all three evaluations/analyses,
took **7,160.02 seconds (1 hour 59 minutes)**. The predeclared admission estimate
for a second round plus reanalysis and confirmation was about 4 hours 36 minutes,
against about 4 hours 5 minutes left before the execution cutoff. The runner
therefore skipped round two and its 96-fight reanalysis. This was a conservative
time-admission decision, not exhaustion of the full eight hours or failure of
the student quality gate.

The confirmation lock selected seed 41 at **02:31:48 UTC**, checkpoint SHA-256
`7b381a4aa4dc05f87735a5f569cbf2c84d9d1248575c49adeaed5c137abb61a7`.
No test results had been produced when this lock was written.

On the main fresh test panel:

| Frozen controller | Challenge wins / 128 | Control wins / 64 |
| --- | ---: | ---: |
| Original network | 90 | 64 |
| Original network + selected search | **100** | 64 |
| Selected student alone | 94 | 64 |
| Selected student + selected search | **100** | 64 |

The original checkpoint's search gain was **+7.81 pp [3.13, 13.28]**, with
11 rescued losses and one regression. The selected student with search had the
same net gain over the original network, but **zero net gain over the original
searched teacher**, interval **[-4.69, 4.69] pp**. Between the two searched
controllers, five wins were rescued and five were lost. The student's mean
challenge return changed by **-0.00039 [-0.04858, 0.04790]** relative to that
searched teacher. There is no evidence here that the learning round improved
searched performance.

The student alone rescued four losses without a regression: **+3.13 pp**, with
the predeclared percentile interval **[0.78, 6.25] pp**. Only four pairs differed,
however. A supplementary exact two-sided paired-win test gives **p = 0.125**,
so this is a promising small gain, not strong evidence of a general improvement.
The same sensitivity check supports the original search gain (**p = 0.00635**).
These additional tests are descriptive and did not alter selection, budgets or
the frozen confirmation. The student's own search-versus-network win interval
was **[0.00, 9.38] pp**, also illustrating why its point estimate alone should
not replace the frozen original-control comparison.

The selected student's eligible confirmation search averaged **1.341 seconds**,
p95 **1.766 seconds**, maximum **2.043 seconds**. All 3,475 eligible decisions
completed their 24 simulations without a search cutoff or fallback.

On the reserved one-Strike-upgrade variants:

| Frozen controller | Challenge wins / 64 | Control wins / 32 |
| --- | ---: | ---: |
| Original network | 48 | 32 |
| Original network + selected search | **53** | 32 |
| Selected student alone | 49 | 32 |
| Selected student + selected search | 52 | 32 |

The original search gain was **+7.81 pp [1.56, 15.63]**, with five rescues and no
regressions. Its supplementary exact paired-win p-value was **0.0625**: the
direction is consistent with the main panel, but only five pairs differ. The
student with search was one win behind the original searched teacher,
**-1.56 pp [-9.38, 4.69]**, with two rescues and three regressions. Its own
network-only gain was one win, interval **[0.00, 4.69] pp**. These results provide
no reason to promote the student as a stronger searched teacher.

All **3,552 main-study gameplay executions** completed without episode failures,
cutoffs or unattempted cases. The 48-game timing pilot brings the total to
**3,600 gameplay executions**. Repeated controllers and learning seeds are not
independent starting fights. The main study contains 960 distinct declared
starts across training, development and the two confirmation populations.

### Public-data diagnostic after confirmation

Both checkpoints were evaluated on the same recorded training and development
observations, at the opening and midpoint of each completed fight. This did not
use test trajectories or change any model. Against the original searched
teacher's development challenge outcomes, clipped critic RMSE fell from
**0.413 to 0.218** at openings and **0.297 to 0.175** at midpoints. Agreement
with the recorded search target's top action changed much less: **85.9% to
89.1%** at openings and **83.3% to 85.3%** on 102 eligible midpoints. Training
observations showed a similar reduction in value error.

These are descriptive fits to recorded behavior, not counterfactual action
values or independent outcome evidence. The student also produced more raw
values outside the objective range at development midpoints (28/128 versus
0/128 on the searched trajectories); search's existing clipping bounds still
apply. Better average return prediction did not establish better action ranking
or a stronger searched controller. The diagnostic used only public trajectories
and took **160.12 seconds**.

## Validation and limits

The broad local suite passed **8,900 tests**, with one skip. After the final
tracking provenance correction, **97 affected consumer checks** passed. The
focused rollout/boundary, preview and tracking checks also passed. Compilation,
diff and relevant documentation-link checks passed. One independent semantic
review found no blocking public-information, RNG or provenance issues.

The selected inventory population is calibrated and narrow. Controls are at a
ceiling, and development gains were concentrated in Vantom. The reserved
confirmation inventory variants upgrade one additional Strike; they do not
represent broad unseen-deck coverage. Combat utility ignores future potion value.
No Act 1, native parity or default-promotion claim follows from this study.

## Recorded budget, artifacts and next gate

The main frozen study took **14,338.76 seconds (3 hours 59 minutes)**, excluding
initial implementation, the timing pilot and final documentation. The three
training runs together used **3,252 optimizer updates and 103,740 sample
presentations**. Their update loops and final saves took **54.70 seconds**;
including data validation/preparation, training wall time was **429.96 seconds
(7.17 minutes)**. Most compute time went to collecting and evaluating decisions,
not gradient updates. The broad validation run took **1,628.34 seconds**; final
affected-consumer checks took **24.70 seconds**. Implementation and independent
review were not separately timed, and these durations are not all additive.

The [machine-readable evidence](combat_search_learning_2026_10_06.json) retains
the protocol, frozen identities, every learning seed, paired comparisons,
supplementary sensitivity tests, timing/work counts, public-data diagnostics and
52 artifact hashes. The full local artifacts remain in
`runs/search-learning-20261006/`. The selected experimental student is
`round-1-student-41/final.sts-model` within that directory. Original artifact
bytes and historical hashes were preserved.

The useful-search gate is now met for this authored combat population. Keep the
original checkpoint with rollout-assisted search as the benchmark teacher; the
student has not earned promotion as a stronger searched controller. The next
bounded learning experiment should examine policy-target transfer and action
ranking before another large collection budget, using fresh confirmation after
development selection. Campaign/corpus opening anchors remain a separate
prerequisite for the paired Act 1 gate, followed by native bridge validation.
No learned dynamics or larger model is justified by these measurements alone.
