# Combat search strength diagnosis — 2026-10-06

Heavy search produced a useful development result: **56/64 challenge wins**, versus
51/64 for the cheaper searched reference and 49/64 for the network alone. It averaged
**29.77 seconds per decision**, so it misses the 1–5 second target. The incremental
win-rate interval against cheaper search touches zero; the combat-return interval is
positive. Extra passes over the existing labels improved fit without producing a student
that beat the original searched checkpoint.

## Question and scope

This follows the [previous frozen search-learning
study](COMBAT_SEARCH_LEARNING_2026_10_06.md). That study established a combat search
benefit on fresh authored fights but no incremental searched-win benefit from its
student. This experiment asks whether more simulations, longer leaf continuations or
more passes over the existing search targets address that remaining limitation.

The original checkpoint and combat objective remain fixed. The checkpoint is
`runs/direct-search-learning-student-20261004/initial.sts-model`, SHA-256
`e22bd23bc0783d67e081816c4066f04a65f2eb1d22be96b19677e0634dbc4862`. Utility is combat
victory plus 0.1 times settled HP fraction, defeat zero, discount one. This is not a
campaign objective or a claim about natural Act 1 win rates.

The protocol was frozen at 08:00:54 UTC, with production sources, checkpoint, benchmark,
original training/development data and core runners bound before gameplay. Its SHA-256
is `2a6b54fcfbe8d2dd2116ca2ed24b92b7903388203c5cb2d793702871ea8b8d36`. New gameplay uses
**validation only**. No held-out test was opened in this study.

The balanced panel has 48 starts at indices 70000–70047: 32 challenge and 16 Slimes
control fights across the existing 12 developed-deck families. Each comparison verifies
identical public openings. Repeated controllers and learner seeds are grouped by source
fight. Development intervals are exploratory paired percentile bootstraps with 10,000
resamples, not confirmatory promotion evidence. There are only four starts per family;
this panel cannot rule out small gains.

Search uses `direct_belief_v1`, depth 16, two belief particles, fixed simulation counts
and deterministic evaluation selection. A 120-second thinking ceiling allows the
research budgets to finish; each game separately has 160 decisions and 3,600 seconds.
Each gameplay study uses four single-threaded Torch workers; the budget and student
studies ran concurrently. Reported latency is local headless timing under that load, not
a native or isolated single-game guarantee.

## Search budgets and horizon

| Simulations / leaf actions | Challenge wins / 32 | Control wins / 16 | Mean / p95 thinking time | Mean tree depth | Simulations ending in terminal return |
| --- | ---: | ---: | ---: | ---: | ---: |
| 24 / 4 | 25 | 16 | 1.48 / 1.96 s | 1.98 | 24.2% |
| 64 / 4 | 25 | 16 | 4.28 / 5.79 s | 2.38 | 25.1% |
| 256 / 4 | 26 | 16 | 15.47 / 21.41 s | 2.78 | 26.7% |
| 256 / 16 | 26 | 16 | 30.38 / 54.00 s | 2.79 | 68.2% |

The unchanged greedy checkpoint wins 24/32 challenges and 16/16 controls. Every recorded
eligible decision completed its full simulation budget; all comparisons had complete
search coverage and no unsupported fallback or thinking/episode cutoff. Forced decisions
are excluded from coverage and latency.

The initial panel has ceiling effects: every searched setting wins the other 24
challenge fights, so all win-count differences occur among the eight
block-conversion/exhaust-draw Vantom starts. The declared challenge/control roles stay
unchanged; this limits how broadly the aggregate result can be interpreted.

Paired challenge differences versus 24 simulations/four leaf actions:

- `budget-64`: +0.00 pp [-9.38, +9.38]; mean return -0.00199 [-0.09625, +0.09207].

- `budget-256`: +3.12 pp [+0.00, +9.38]; mean return +0.03035 [-0.00488, +0.09645].

- `leaf-16-budget-256`: +3.12 pp [+0.00, +9.38]; mean return +0.03922 [+0.00445, +0.10442].

The selection rule chose `leaf-16-budget-256`.

The frozen fresh-development comparison used 96 additional starts: 64 challenges and 32
controls. Reference won 51/64 challenges; candidate won 56/64. The paired effect was
+7.81 pp [+0.00, +15.62]; mean return +0.08357 [+0.00465, +0.16514]. Control wins were
32/32 and 32/32 respectively. Mean/p95 thinking times were 1.32/1.76 seconds for the
reference and 29.77/53.62 seconds for the candidate. This remains development
confirmation.

On the fresh panel, heavy search rescued six reference losses and lost one reference
win. Against the network alone, its paired win gain was +10.94 percentage points with a
95% interval of [+3.12, +20.31]. These are still development comparisons on authored
encounters, with no campaign or held-out promotion claim.

| Fresh challenge family | Network wins | 24 / 4 search wins | 256 / 16 search wins |
| --- | ---: | ---: | ---: |
| Block conversion / Vantom | 2/8 | 2/8 | 1/8 |
| Exhaust and draw / Vantom | 1/8 | 2/8 | 7/8 |
| Strength / Vantom | 7/8 | 8/8 | 8/8 |
| Strength / Lagavulin Matriarch | 7/8 | 7/8 | 8/8 |
| All four Bygone Effigy inventories | 32/32 | 32/32 | 32/32 |

The gain is concentrated in the exhaust/draw Vantom family. Increasing both simulation
count and leaf length also changes the prior/value balance, so this comparison does not
isolate which mechanism caused that gain.

A post-hoc comparison isolates leaf length at 256 simulations: 16 leaf actions versus
four gave +0.00 pp [-9.38, +9.38]; mean return +0.00887 [-0.08582, +0.10270], rescuing 1
win and losing 1. Higher mean HP among wins therefore compares partly different winning
subsets; it is not by itself evidence of a causal HP gain.

The predeclared rule first compares 24, 64 and 256 simulations with four leaf actions.
It then tries 16 leaf actions at the healthy candidate with most challenge wins, then
highest return, then fewer simulations. A strictly higher win count admits a frozen
comparison against 24-by-4 on 96 fresh development starts at index 71000. This selection
never changes the original checkpoint.

`SearchResult.tree_work` now records simulation depth, node expansions, exact tree
terminals and sequential-halving rounds with public action references and visits. These
counters do not participate in selection or consume randomness. Together with
`leaf_work`, they distinguish completed hypothetical fights from critic-dependent
estimates. They are optional sidecar diagnostics; older target artifacts remain
readable.

At 24 simulations, 86.5% of actions removed in the first halving round had only one
evaluation. Larger budgets allocate more samples but still leave many simulations
dependent on a critic. A configured depth ceiling is not the depth actually reached; the
table reports measured tree depth before any leaf continuation. These observations
identify limited and potentially noisy lookahead; they do not establish one causal
defect.

## Training budget and target transfer

The existing corpus contains **480 completed training fights and 8,645 eligible search
decisions**. Each of three seeds, 17, 23 and 41, starts from the original weights and a
fresh optimizer, then follows one continuous 32-pass trajectory. Checkpoints at passes
4, 16 and 32 therefore share the same training prefix. Settings remain batch 32,
learning rate 0.0001, value weight 0.25 and gradient clip 1. Each pass has 271 updates,
including its five-example final minibatch.

Actual training totals are **96 passes, 26,016 updates and 829,920 sample
presentations**, taking 719.35 seconds including corpus loading and fit checks. Saving
intermediate checkpoints does not add more independent training. No new training fights
were collected, labels were not refreshed, and no search trajectory entered PPO. All
three four-pass parameter sets reproduce the previous study's corresponding student
tensors exactly.

This isolates optimization effort on fixed labels. It does not test fresh experience or
additional teacher–student/reanalysis rounds; a plateau here is not evidence that search
learning in general cannot improve.

Challenge wins on the same 32 starts (columns are learning seeds 17, 23, 41):

| Passes | Network wins | Network + 24-by-4 search wins |
| --- | --- | --- |
| 4 | 23, 24, 24 | 24, 24, 25 |
| 16 | 24, 24, 24 | 25, 25, 25 |
| 32 | 24, 23, 25 | 25, 25, 25 |

All student controllers retain all 16 control wins.

The six 16-/32-pass searched students improve mean challenge return by about
0.0020–0.0039 over the original searched checkpoint, but every individual paired return
interval includes zero. These positive point estimates do not establish an additional
combat-return benefit. Full paired comparisons are retained in the JSON evidence.

Paired effects relative to four passes average the three fixed learner seeds **within
each source fight**, then resample the 32 fights:

| Passes | Network win difference, 95% interval | Searched win difference, 95% interval |
| --- | ---: | ---: |
| 16 | +1.04 pp [+0.00, +3.12] | +2.08 pp [-2.08, +6.25] |
| 32 | +1.04 pp [+0.00, +3.12] | +2.08 pp [+0.00, +6.25] |

These intervals are conditional on the three learner seeds; they do not treat 96
repeated challenge outcomes as independent starts.

| Passes | Training target KL | Training target argmax agreement | Training value MSE | Development opening value RMSE | Development midpoint target agreement |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original | 0.2555 | 82.2% | 0.1161 | 0.413 | 83.3% |
| 4 | 0.2032 | 82.3% | 0.0362 | 0.216 | 85.9% |
| 16 | 0.1843 | 83.3% | 0.0327 | 0.185 | 83.0% |
| 32 | 0.1747 | 84.0% | 0.0297 | 0.182 | 82.7% |

Student fit cells average three checkpoints, not three independent datasets. Training
fit keeps improving; development action agreement is mixed. This is not evidence that
simply adding passes will yield a stronger searched teacher.

Development fit uses the same recorded opening and midpoint observations from 128
previous challenge fights for every checkpoint. There are 128 opening and 102 eligible
midpoint search targets. Values are checked against the recorded completed behavior, not
optimal counterfactual action returns. Better return prediction on those positions alone
does not establish better action ranking.

## Inspecting failing decisions

Selection took the first two searched Vantom losses per available deck from the previous
development report, then the first nonforced actor/search disagreement or the nearest
eligible midpoint. Strength had no searched losses, leaving four positions: block
conversion cases 32004/32016 and exhaust/draw 32011/32023. These are selected failures,
not a representative calibration sample.

For every position, each of five legal actions was followed by greedy public policy play
on 16 common belief-sampling seeds. **All 320 continuations completed**, so every action
comparison has the same 16 completed seeds. Hypothetical worlds came only from recorded
public declarations and accepted prefixes. Recorded final outcomes did not enter
planning. Newly seeded planner analyses do not reproduce the original trajectory's
planner RNG progression.

The resulting action values are often flat: every tested first action lost all 16
continuations at case 32011; attack alternatives at 32023 had equal sampled returns.
Other differences were small and based on few wins. These weak-policy continuations
neither bound optimal play nor prove that a search estimate is biased under continued
search.

The continuations averaged 43.6–45.5 remaining actions. All tested searches at these
four positions still bootstrapped every simulation, including the
64-simulation/16-action setting. They did not resolve the fight to its actual
hypothetical outcome. With four additional analysis seeds, chosen card types still
varied at three of the four positions even with 256 simulations. Those seeds change both
belief construction and tree simulations: this measures whole-planner seed sensitivity,
not isolated tree-selection noise.

Independent small references cover one-, two- and three-attack current-turn lethals and
a stochastic hidden-draw fixture. In the latter, drawing Strike wins and drawing Wound
loses with equal probability; root search agrees with the enumerated expected settled
return without critic bootstraps. These checks pass and preserve the real engine
snapshot. They establish the tested transitions, returns and lethal choices under the
supplied priors, not optimal play under arbitrary priors or on full fights.

### An exact counterexample with a skewed actor prior

A post-hoc synthetic diagnostic exposes a separate selection limitation. Give the player
one HP, Vantom one HP, and a hand containing Strike and an unplayable Wound. Strike
immediately wins with settled return 1.00875; ending the turn immediately loses with
return zero. Both outcomes are enumerated through the existing engine, without critic
estimates.

With actor probabilities 0.001 for Strike and 0.999 for ending the turn, 24 simulations
evaluate each action 12 times and recover those exact values, yet choose end turn. The
current score difference is `log(0.001 / 0.999) + 0.1 * (50 + 12) = -0.7068`, so the
target gives Strike only 33.0%. At a Strike prior of 0.00001, even 64 simulations choose
the loss; 256 simulations finally outweigh the prior. Three of 12 supplied-prior/budget
combinations miss the win. The real fixture snapshot remains unchanged.

This is a decision-quality limitation of finite prior regularization, not an incorrect
transition or backup. DeepMind's implementation also combines prior logits with
transformed values for final selection; its public Q-scale default is 0.1. [Final
selection](https://github.com/google-deepmind/mctx/blob/main/mctx/_src/policies.py), [Q
transform](https://github.com/google-deepmind/mctx/blob/main/mctx/_src/qtransforms.py).
The paper used scale 1.0 for Go/chess. That makes the scale an experimental choice, not
a correctness constant. [Gumbel planning paper, Appendix
F](https://davidstarsilver.wordpress.com/wp-content/uploads/2025/04/gumbel-alphazero.pdf).

On recorded evaluation decisions, the chosen action had a lower empirical Q than another
evaluated finalist at these frequencies:

| Simulations | Disagreements / eligible decisions | Fraction | Mean Q gap in those disagreements |
| --- | ---: | ---: | ---: |
| 24 | 252/862 | 29.2% | 0.0292 |
| 64 | 218/864 | 25.2% | 0.0225 |
| 256 | 217/879 | 24.7% | 0.0157 |

These discrepancies are not automatically mistakes: empirical values may be noisy or
critic-dependent, and priors can help. The synthetic counterexample does not establish
how much this mechanism contributes to benchmark losses. Increasing the simulation
budget also increases the value coefficient in this selection formula, so the budget
curve does not isolate extra sampling from stronger reliance on estimated values.
Likewise, observing wins in finitely many sampled worlds is not a general proof of
victory across every possible hidden state. The frozen gameplay study and production
selection rule were left unchanged.

## Cost and implementation decision

Profiling a public position locates most work in public encoding and projection. The
profiled 64-simulation decision made 321 network calls; feature encoding took 4.47
seconds, projection 3.18 seconds and rule transitions 0.41 seconds. These are inclusive
profiling measurements with profiler overhead and are not additive latency percentages.

A prototype using the existing validated prepared-public encoding path matched all
features, legal mappings and network outputs on 96 observations. Median encoding time
improved from 0.678 to 0.604 seconds, about 10.9%; an end-to-end search gain was not
established. Exact public-input memoization preserved all search results in 12 paired
measurements, but hit only 7.5% of calls and made aggregate time 13.5% worse. Neither
prototype was adopted in production.

Keep the original checkpoint and 24-simulation/four-leaf-action configuration as the
practical experimental reference. The 256-by-16 setting is a useful expensive research
comparator: its fresh result supports further work on search, but its mean thinking time
is about 22.6 times the reference and exceeds the play target. Its incremental win
interval still includes zero. No checkpoint or default budget is promoted.

The next bounded experiment should test action selection at **24 simulations**: retain
the current rule as the control, compare a stronger Q scale such as 1.0, and compare a
final-choice-only variant that takes the highest empirical Q among the evaluated
finalists. That last variant should retain the existing tree allocation so the change is
attributable to the final decision rule. Label all variants explicitly; do not silently
change historical teacher identities. The exact supplied-prior counterexample is an
acceptance fixture for these variants, while paired fights must check whether noisier
values introduce losses.

Also include a 24-simulation/16-leaf-action control to test whether extending the
horizon cheaply can recover some of the expensive setting's gain. Freeze the checkpoint
and each configuration, keep the existing public-information boundary, and confirm any
selected improvement on fresh development starts with measured latency. The present
study has not evaluated that combination in full fights.

Use a stronger verified teacher for the next collection/reanalysis round only after that
comparison. Reusing the existing 480 fights for more optimization is not a substitute
for fresh experience or improved policy targets. Preserve the original
completed-behavior value labels during target refresh. Keep the exact engine, and target
measured projection/encoding cost if the chosen planning behavior needs further
acceleration.

## Validation and retained evidence

The author ran **239 distinct focused tests**, including search, target loading,
beliefs, public-input normalization, RNG separation and the exact references. The
independent semantic reviewer found no blocking issues in diagnostic-only
instrumentation, public-prefix construction, sampled continuations, fixed-label training
or the isolated probes. Its reporting conditions are reflected above.

Final checks passed for compilation, diff whitespace, 210 local link targets,
96 artifact hashes and the identities of all 11 focused test files. Production
sources still match the frozen protocol, and the saved JSON is an exact copy
of the exported result.

The study completed 1,632 controller-game executions on **144 distinct development
starts**. Repeated baseline runs and learner seeds do not increase that
independent-start count. The 320 hypothetical action continuations are separate from
those gameplay executions.

The [machine-readable evidence](combat_search_strength_2026_10_06.json) retains the
frozen protocol, all paired summaries, checkpoint/corpus identities, review, test
bindings and hashes for raw reports and research runners. Raw trajectories, search
sidecars, checkpoints and scripts remain under `runs/search-strength-20261006/`.

At evidence export, elapsed session time was 7.52 hours from the observed 07:53:54 UTC
start. Curve phases took 6.2, 17.6, 63.0, 122.3 minutes; fresh reference/candidate
phases took 10.3/222.6 minutes. Training took 12.0 minutes; the four focused pytest
commands took 67.24 seconds in total. Concurrent phases must not be summed into session
time. Implementation and independent review were not timed separately. No release
preparation or user-readiness wait was required.

Search remains experimental. No student or budget is promoted, and no campaign, bridge
or native-game behavior changes in this experiment. The exact engine continues to own
all game mechanics.
