# Search distillation on the boss and elite benchmark — 2026-10-18

Status: **complete; the registered rule was not met.** Distilling search targets
into the step-2 initializer gave small greedy gains, recovering 10–20% of the
search gain. Normal fights were unchanged. The targets carry a strong
improvement signal, but no student fit them well: training cross-entropy
plateaued near 0.61 nats at learning rates from 1e-4 to 1e-3. The
[follow-up](#follow-up-learning-rate) rules out the optimizer as the limit.
Target noise explains only part of the gap, which points to the network's
representation. No default changed; `search-distill` gained a
`--learning-rate` option (default unchanged).

## Result

| Arm (three seeds) − initializer | Bosses | Elites | Search gain recovered (boss / elite) |
| --- | --- | --- | --- |
| 1 epoch | +0.4 [−0.9, +1.7] | +0.7 [−0.2, +1.5] | 5% / 10% |
| **4 epochs (primary)** | **+0.6** [−1.0, +2.2] | **+0.7** [−0.2, +1.7] | 9% / 11% |
| 16 epochs | +1.3 [−0.4, +3.0] | +0.8 [−0.2, +1.9] | 19% / 12% |
| View control | +0.0 [−0.4, +0.5] | +0.0 [0.0, 0.0] | — |

Differences are percentage points of equal-weight win rate (each encounter
weighted equally), with 95% source-campaign bootstrap intervals shared by all
learners (4,000 resamples). The initializer won 48.7% of boss and 79.1% of elite
fights. The search gain is the
[2026-10-17 measurement](COMBAT_SEARCH_BENCHMARK_2026_10_17.md): +6.8 boss and
+6.7 elite points from search over the same weights.

- **Decision rule:** an improvement required a primary-arm boss or elite interval
  above zero. Neither excludes zero, so the rule is not met. Neither room kind
  fell, and normal fights stayed within the 1-point guard (97.7% for the
  initializer, −0.1 points [−0.2, +0.0] for the primary arm, 6,698 fights).
- **Dose.** Gains grow slightly with training: bosses +0.4 → +0.6 → +1.3 points
  over 1, 4 and 16 epochs. Seeds within an arm span up to 1.9 boss and 0.6
  elite points.
- **Input view has no effect.** Distilled students use the detached
  card-history view that search uses. The view control (the initializer's exact
  weights under that view) reproduced the initializer's outcome in every elite
  fight and in 587 of 589 boss fights. Play differed in only 11 fights.

## Why so little transferred

The targets are informative. Across the 60,738 searched training decisions:
- The target's most likely action differs from the network's in **18.8%** of
  decisions (19.7% for bosses). The mean probability margin for the new choice
  is 0.53.
- KL(target ‖ network prior) averages 0.29 nats; target entropy averages 0.40.

The students fit those targets only slightly. Training cross-entropy at the
last tenth of updates:

| Arm | Start | End | Remaining gap to target entropy |
| --- | ---: | ---: | ---: |
| 1 epoch | 0.67 | 0.65 | ≈ 0.25 |
| 4 epochs | 0.66 | 0.63 | ≈ 0.23 |
| 16 epochs | 0.65 | 0.615 | ≈ 0.22 |

The existing `search-distill` learner uses batch 32, learning rate 1e-4 and
gradient clipping at 1.0. Its gradient norms are 1.7–3, so most steps are
clipped. After 16 epochs the loss was still falling slowly. The students moved
little, so their greedy play moved little.

Two explanations remain once the optimizer is ruled out (see the follow-up).
- **Target noise.** 872 openings were collected 2–10 times with different planner
  seeds, and their first decisions have identical inputs.
  - Across 3,285 such visit pairs from 872 openings, the target's top action
    agreed 85% of the time, with mean total variation 0.14.
  - Fitting the mean target is the best a network can do for identical inputs.
    That mean has entropy 0.46 nats, against 0.41 for the individual targets.
  - So noise explains about 0.06 of the roughly 0.2-nat gap at openings. Later
    decisions, with more hidden-state uncertainty, cannot be measured this way.
- **Representation.** Targets cover exactly the network's legal action set, so
  no probability mass is unreachable. The rest of the gap means the network
  does not separate the states where search changes its choice. It still has
  that problem on its own training data.

## Design

The protocol (`runs/combat-distill-20261018/protocol.json`) was frozen before
any corpus build. One amendment, made after an unused 16-fight pilot and before
collection, added the view control.

- **Teacher:** the step-2 initializer (`ppo_v1:a6a0dac3…`, the Vantom specialist
  with a catalog fork) with `combat_belief_v1` search at the benchmark settings.
  These are 24 simulations, depth 16, 4 leaf steps, 2 particles, 4,096 proposals
  and 120 s limits. Collection keeps its root exploration.
- **Data:** the step-2 training campaigns (start index 32,000,000, 512 per region)
  rebuilt with planning receipts, openings only. They contain 1,666 elite and
  boss openings (70–215 per encounter).
- **Collection:** 3,072 training fights, uniform by encounter (233–277 each),
  played to completion.
  - Results: 0 cutoffs, failures or belief fallbacks; searched training win rate
    67%.
  - Yield: 60,738 searched decisions, 78% coverage (the rest had one legal action).
  - The fights cover 1,341 distinct openings. Rare bosses repeat theirs about 3.5
    times on average, with different planner seeds.
- **Students:** `search-distill` from the initializer for 1, 4 and 16 epochs
  (1,899 updates per epoch), with learner seeds 101/202/303 and a fresh
  optimizer each. Policy targets are the search distributions; value targets are
  completed searched-play returns.
- **Evaluation:** the benchmark rebuilt for the current code, which reproduced
  all 1,728 original openings. Greedy play, 512 decisions / 120 s per fight.
  - The evaluator compares at most eight checkpoints per report, so the 16-epoch
    students ran in a second report with the initializer and view control.
  - The analysis merged the two reports only after checking that those shared
    policies had identical outcomes in all 1,728 fights.

| Artifact | Identity |
| --- | --- |
| Implementation | Build `dd9ed991…` (commit `7e975686`) |
| Training corpus / benchmark corpus | `act1_combat_corpus_v2:a8d3f8aa…` / `…:7f3820c9…` |
| Collection report | `collection/search.json`, SHA-256 `d4a05654…` |
| Evaluation reports | `evaluation/hard` `403d1b40…`, `hard-e16` `f356f970…`, `normal` `ebb160c5…` |

Elapsed times:
- Corpus builds: 226 s and 225 s.
- Collection: 5,767 s on 16 workers.
- Distillation: 12–32 minutes per student. Loading the targets takes about 11
  minutes and 7 GB, so students ran four at a time after the first. Total wall
  time 64 minutes.
- Evaluations: 629, 440 and 864 s.
- User wait: none.

## Follow-up: learning rate

Exploratory, frozen in the protocol's `follow_up` section after the primary
analysis and before any follow-up training. The same collected targets were
distilled for 16 epochs at learning rates 3e-4 and 1e-3, with the same three
seeds. Evaluation used a benchmark rebuilt for the changed code, which again
reproduced all 1,728 fights, and the initializer reproduced 48.7% / 79.1%.

| 16 epochs, three seeds − initializer | Bosses | Elites | Final training cross-entropy |
| --- | --- | --- | ---: |
| 1e-4 (e16 above, previous build) | +1.3 [−0.4, +3.0] | +0.8 [−0.2, +1.9] | 0.615 |
| 3e-4 | +0.5 [−1.2, +2.4] | +1.1 [+0.1, +2.1] | 0.611 |
| 1e-3 | +1.0 [−1.0, +3.2] | +1.1 [+0.1, +2.2] | 0.614–0.615 |

A tenfold faster learner fits the policy targets no better; only the value loss
falls (0.085 → 0.070 → 0.061). Elite gains are slightly above zero at both
higher rates, and the boss intervals include zero. All arms recover at most
about 17% of the search gain. The optimizer was not the limit.

Report: `follow-up/evaluation/combat-benchmark.json`, SHA-256 `53c24a72…`,
build `997cde1d…`. Elapsed: rebuild 4 minutes, six students 65 minutes (four at
a time), evaluation 656 s.

## Next step

Training fit, not the amount of data or the optimizer, is what limits
distillation. The collected labels are a direct test set for the planned
representation screen:
- Fit each candidate encoder to the targets of a subset of training campaigns.
- Measure held-out cross-entropy and top-action agreement on the other campaigns.
- Confirm only the best encoder with greedy benchmark play.

Repeated collection rounds or reanalysis would add data to a network that
cannot yet fit what it has, so they wait.

## Limits

- The validation panel is reused from steps 1–2 and the minibatch study; there is
  no held-out claim.
- One teacher round and one dataset; dataset sampling variation is not measured.
- Collection used root exploration, and value targets are searched-play returns.
- Act 1 clear rate is not measured.
