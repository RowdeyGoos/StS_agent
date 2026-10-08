# Combat search action selection — 2026-10-07

**No tested change established a stronger practical teacher.** Longer continuations
won one extra challenge in the initial panel, but fresh confirmation reversed the
point estimate: **47/64 wins versus 49/64** for the existing 24-by-4 search, at
2.95 versus 1.34 seconds per action. Its p95 also exceeded five seconds. Keep the
existing checkpoint and reference settings; no new training round was started.

This follows the [search strength diagnosis](COMBAT_SEARCH_STRENGTH_2026_10_06.md)
and tests stronger value weighting, a different final choice and longer
continuations. The checkpoint, game rules, public-information boundary and combat
objective stay fixed.

## Frozen design

The checkpoint is `runs/direct-search-learning-student-20261004/initial.sts-model`,
SHA-256 `e22bd23bc0783d67e081816c4066f04a65f2eb1d22be96b19677e0634dbc4862`.
Utility is combat victory plus 0.1 times settled HP fraction on victory, zero on
defeat, with discount one. All new gameplay uses development (`validation`), not
held-out tests or native-game data. These are authored developed-deck fights,
not natural Act 1 completion measurements.

The initial panel has 48 starts at indices 80000–80047: 32 challenges and 16
Slimes controls, balanced across the existing 12 deck/encounter families. Every
configuration includes the same greedy checkpoint baseline. Cross-configuration
comparisons verify identical public openings and pair by source fight.

| Setting | Simulations | Greedy leaf actions | Q scale | Final action |
| --- | ---: | ---: | ---: | --- |
| Control | 24 | 4 | 0.1 | Existing prior/value score |
| Stronger value weight | 24 | 4 | 1.0 | Existing prior/value score |
| Final empirical value | 24 | 4 | 0.1 | Highest visited Q among last-round contenders |
| Longer continuation | 24 | 16 | 0.1 | Existing prior/value score |

All use `direct_belief_v1`, depth 16, two belief particles and deterministic
evaluation selection. Q scale affects tree allocation, interior selection and
training targets. The final-choice variant changes only the returned action;
simulation allocation and completed-value training targets are unchanged. It
cannot resurrect an eliminated action or select an unvisited imputed value.
Nondefault settings receive distinct teacher identities; defaults preserve
historical identities and behavior.

Each phase runs four single-threaded Torch workers. A 120-second per-action
ceiling allows fixed simulation budgets to finish; games separately have 160
actions and 1,800 seconds. Admission requires measured mean and p95 search time
at most five seconds. Audits and timed fight panels run separately. Measurements
describe local headless execution under that worker load, not native latency.

One healthy candidate can advance to 96 fresh development starts at indices
81000–81095: 64 challenges and 32 controls. Selection requires strictly more
challenge wins, or equal wins with a positive paired-return lower confidence
bound; ties use return and latency. It also requires no paired control loss.
The stronger-teacher gate on fresh starts requires a positive paired win-rate
lower bound, nonnegative return lower bound, no paired control loss, healthy
baseline/candidate, full coverage and acceptable latency. The gate does not
promote default play or establish campaign benefit.

Intervals use 10,000 paired source-fight percentile bootstrap resamples.
Development comparisons are exploratory. Multiple actions, simulation seeds or
controller runs from the same source fight do not become independent fights.

The protocol was frozen at 10:19:04 UTC. Independent review tightened the
implementation of two already declared requirements before any panel gameplay:
require zero *paired* control losses rather than aggregate control-win parity,
and require the baseline itself to be healthy. The original protocol and audit
runner bytes are preserved; a digest-bound amendment records the corrected
evaluation runner without changing audit results, configurations or starts.

## Initial paired fight results

| Controller | Challenge wins / 32 | Control wins / 16 | Mean combat return on challenges | Mean / p95 thinking time |
| --- | ---: | ---: | ---: | ---: |
| Network alone | 23 | 16 | 0.75598 | — |
| 24 simulations / 4 leaf actions | 25 | 16 | 0.82137 | 1.36 / 1.87 s |
| Q scale 1.0 | 24 | 16 | 0.78262 | 1.38 / 1.82 s |
| Final empirical value | 25 | 16 | 0.81406 | 1.36 / 1.79 s |
| 24 simulations / 16 leaf actions | 26 | 16 | 0.85406 | 2.94 / 4.97 s |

Every setting completed its full simulation budgets with complete eligible
coverage and no fallback or search/game cutoff. All 16 Bygone Effigy challenge
fights were won by every controller; differences remain concentrated in the
Vantom and Lagavulin Matriarch families. The declared challenge/control roles
were not changed after seeing results.

Paired changes relative to the searched control:

| Variant | Win difference, 95% interval | Return difference, 95% interval | Rescued / lost baseline wins |
| --- | ---: | ---: | ---: |
| Q scale 1.0 | -3.12 pp [-12.58, +6.25] | -0.03875 [-0.14521, +0.06023] | 1 / 2 |
| Final empirical value | +0.00 pp [-12.50, +12.50] | -0.00730 [-0.13438, +0.12137] | 2 / 2 |
| 16 leaf actions | +3.12 pp [+0.00, +9.38] | +0.03270 [-0.00184, +0.09930] | 1 / 0 |

Neither selection change qualified. Longer continuation recovered one strength
Vantom loss and qualified for the frozen fresh-development comparison. Its
incremental intervals still include zero; this initial result does not establish
a stronger teacher. Its maximum decision latency was 5.51 seconds, so passing
the declared mean/p95 gate is not a guarantee that every action stays below five
seconds. Practical five-second ceilings can produce partial searches.

## Fresh confirmation and training decision

| Controller | Challenge wins / 64 | Control wins / 32 | Mean challenge return | Mean / p95 thinking time |
| --- | ---: | ---: | ---: | ---: |
| Network alone | 47 | 32 | 0.76648 | — |
| 24 simulations / 4 leaf actions | 49 | 32 | 0.79977 | 1.34 / 1.79 s |
| 24 simulations / 16 leaf actions | 47 | 32 | 0.76973 | 2.95 / 5.07 s |

The candidate rescued one reference loss and lost three reference wins. Its
paired win difference was **-3.12 pp [-9.38, +3.12]**; its return difference was
**-0.03004 [-0.09438, +0.03193]**. The intervals include zero, so this does not
establish that longer continuations are generally worse. It fails to establish
the required improvement. Mean/p95 latency also failed the declared gate because
p95 was 5.068 seconds; maximum latency was 5.74 seconds.

Both controllers completed all fights and every eligible search budget, with
full coverage and no fallback or cutoff. Each used 96 potions across the 96
fights. Control fights remained 32/32 wins, with a small conditional HP/return
gain; that does not compensate for the missing challenge improvement.

| Challenge family | Network | 4 leaf actions | 16 leaf actions |
| --- | ---: | ---: | ---: |
| Block conversion / Vantom | 0/8 | 0/8 | 0/8 |
| Exhaust and draw / Vantom | 0/8 | 1/8 | 1/8 |
| Strength / Vantom | 7/8 | 8/8 | 7/8 |
| Strength / Lagavulin Matriarch | 8/8 | 8/8 | 7/8 |
| All four Bygone Effigy inventories | 32/32 | 32/32 | 32/32 |

The one win in the exhaust/draw family occurred on different starts for the two
search settings. Equal family totals can hide paired rescues and losses.

Longer continuations increased the share of backed-up simulations ending in an
exact terminal return from **24.2% to 67.5%**, but that did not translate into a
confirmed combat gain. These shares describe each controller's own visited
positions. They do not isolate the effect of horizon on identical states; the
separate action audit below provides that narrower comparison.

The stronger-teacher gate is **false**. No fresh training data was collected,
no student was trained, no prior value labels were refreshed, and no default
was promoted. This implements the planned gate: training from a proposed
improvement waits until that improvement is established. Held-out tests and
campaign promotion remain unopened.

## Public-information action audit

The diagnostic selection takes the first available completed win and loss per
scenario from the previous heavy-search development report. Within each, it
prefers a target/chosen-action disagreement, then an actor/search disagreement,
then a nonforced midpoint. The user's Vantom opening is included. This produces
14 positions from 14 source fights. It deliberately samples disagreements and
outcomes; it is not an unbiased population-calibration sample.

Each position compares distinct recorded choices, target argmax, highest
visited Q, actor favorite and new-variant recommendations. Worlds are built
only from the recorded public declaration and accepted observation/action
prefix. Every alternative gets the same 32 sampled-world seeds. After its
first action, the frozen greedy public policy continues for at most 160 actions;
a shared 1,200-second position deadline bounds the work. The audit completed
all **1,344 continuations**, without cutoff or unsupported branches.

These are hypothetical outcomes under greedy continuation. They do not measure
optimal play or continued tree-search behavior. Conditional intervals over
sampled worlds must not be interpreted as benchmark win-rate intervals.

### The Vantom opening in the viewer

Episode `80394402596c4023ab25006b5c0f06e6`, case 71011, is the exhaust/draw Vantom
opening discussed in the viewer. Rerunning the original heavy configuration
from its public opening reproduced its action, targets, values, visits and
simulation count exactly. New diagnostics add evidence without changing those
decisions or consuming additional randomness.

| Stage | Shrug It Off Q / visits | Energy Potion Q / visits | What happened |
| --- | ---: | ---: | --- |
| Round 1, 80 simulations | 0.5246 / 10 | 0.4810 / 10 | Both continued |
| Round 2, 164 simulations | 0.4301 / 31 | 0.4924 / 31 | Potion eliminated by prior/value ranking |
| Final, 256 simulations | 0.3867 / 73 | 0.4924 / 31 | Shrug chosen; potion estimate remained unchanged |

The actor prior is 92.15% for Shrug and 3.93% for the potion. At elimination,
the combined scores are 5.363 and 4.152, respectively. Later evidence reduces
Shrug's Q while the eliminated potion's estimate is frozen. The value term also
grows with the maximum visit count. The final training target assigns 91.32%
to the potion, but the actual action must come from the remaining contenders.
This explains the displayed discrepancy; it does not prove the potion is better.

All 256 simulations ultimately bootstrapped from the critic; none reached
combat completion. In the independent continuation audit, both first actions
lost all 32 sampled greedy continuations. The recorded heavy-search fight was
a victory with later decisions also searched. The greedy audit therefore cannot
settle the better first action under continued search.

### What longer continuations reveal

The same 1,344 hypothetical trajectories record clipped public critic estimates
after 1, 4, 16 and 32 actions, or their exact settled return if already terminal.
Errors compare each estimate with that trajectory's eventual completed return.

| Horizon | Already terminal | Overall value MSE | Critic-only MSE | Critic-only mean bias |
| --- | ---: | ---: | ---: | ---: |
| 1 | 0 | 0.1878 | 0.1878 | +0.1554 |
| 4 | 98 | 0.1738 | 0.1875 | +0.1329 |
| 16 | 756 | 0.1166 | 0.2665 | +0.3107 |
| 32 | 966 | 0.0410 | 0.1457 | +0.2303 |

Longer continuations remove some reliance on the critic by resolving fights.
The remaining nonterminal positions still show optimistic estimates in this
diagnostic sample. They are a changing, harder subset, so the critic-only rows
do not establish that the same positions become less accurate with depth.
These descriptive figures include correlated actions and sampled continuations;
they are not population error estimates.

## What this resolves and what remains open

The source audit and exact fixtures found no backup/sign, engine-transition or
actual-hidden-state defect in these changes. Finite prior regularization can
miss an exactly known tactical win in the synthetic fixture, but increasing Q
weight or bypassing the final prior score did not improve the development fight
results. A large target on an eliminated action is therefore a diagnostic clue,
not sufficient evidence for changing the selected action.

The continuation audit exposes optimistic critic estimates on difficult sampled
positions and demonstrates that greedy continuations can fail after every tested
first move. It does not prove that value error is the sole limitation, or rank
those moves under continued search. More simulation depth alone did not solve
the observed problem within the tested budgets.

The next bounded experiment should **hold actor probabilities and search settings
fixed while changing only the critic**. Existing distilled checkpoints improved
value fit in the previous study; using their value predictions separately from
their changed actors would test whether that better fit improves action ranking.
Declare both checkpoint identities and the common objective/input view, compare
the original critic with fixed candidate critics on development positions and
paired fights, and keep incomplete outcomes explicit. This is a proposed
diagnostic, not an implemented improvement or a promoted model.

If improved value fit still fails to improve decisions, investigate the quality
of continuation policies and early elimination using the new per-action evidence.
Do not infer that a larger budget, a sharper target or another pass over unchanged
labels is sufficient. The exact engine and public-information boundary remain the
foundation.

## Implementation and validation

The control can be repeated through the existing installed command:

```bash
sts-agent-evaluate \
  --checkpoint runs/direct-search-learning-student-20261004/initial.sts-model \
  --output-dir runs/search-selection-repeat \
  --search --search-model direct_belief_v1 --search-skip-root-baseline \
  --search-benchmark configs/training/search_developed_decks.json \
  --search-cases 48 --start-index 80000 --split validation --workers 4 \
  --search-simulations 24 --search-depth 16 --search-leaf-rollout-steps 4 \
  --search-seconds 120 --belief-particles 2 --belief-seconds 5 \
  --max-decisions 160 --time-limit 1800
```

Use a distinct output directory for each variant. Change only Q scale to `1.0`,
final selection to `max_value`, or leaf steps to `16`, as specified in the table.
Repeating these indices reproduces development cases; it does not create new
independent evidence.

The installed commands expose `--search-q-scale` and
`--search-final-selection`. New sidecars retain per-round action values/scores
and per-action root priors, terminal/bootstrap counts and squared-return sums.
These are compact public diagnostics; they do not expose simulated hidden worlds
or actual game RNG. The viewer accepts new settings and optional diagnostics
while retaining older records.

Focused validation passed **174 Python tests and 18 browser-client tests**.
Fixtures cover default identity preservation, the exactly known lethal/prior
counterexample, final-choice-only isolation, explicit exclusion of an eliminated
highest-Q action, zero/partial time budgets, direct-belief private-state
invariance, target loading and malformed diagnostic rejection. One independent
semantic review covered selection, public information/RNG, the audit and paired
evaluation gates. Its concrete findings were resolved before panel gameplay.

Preparation through protocol freeze took about 12.4 minutes; the action audit
took 452 seconds (7.5 minutes), and the six fight-evaluation phases took 3,830
seconds (63.8 minutes), excluding their report-analysis overhead. The broad
focused Python check took 30.53 seconds. Independent review overlapped preparation
and analysis; its separate active duration was not measured. No live build or
installation was required.

The [machine-readable evidence](combat_search_selection_2026_10_07.json) binds
the checkpoint, protocol/amendment, source identities, public reports, diagnostic
records and analysis. Detailed local artifacts are under
`runs/search-selection-20261007/`.
