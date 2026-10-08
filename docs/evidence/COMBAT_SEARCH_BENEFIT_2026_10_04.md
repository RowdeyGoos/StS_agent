# Combat search benefit and critic diagnosis

Date: 2026-10-04. **Development evidence; no promotion.** The larger frozen
comparison found **85/128 wins for each of greedy, root-only and Gumbel search**,
on exactly the same starts. Search exercised every eligible decision but did not
improve the observed win rate or mean winning HP. This closes the bounded
measurement milestone; the architecture's credible-combat-benefit gate remains
open. It does not establish that search cannot help a different policy or state
population.

The [training guide](../AGENT_TRAINING.md#experimental-combat-search) owns usage;
the [architecture](../COMBAT_SEARCH_ARCHITECTURE.md) owns remaining gates.
The [evidence extract](combat_search_benefit_2026_10_04.json) binds the frozen
protocol, checkpoints, implementation, public trajectories, targets and results.
Historical search/learning evidence retains its original identities.

## What changed

The existing `search-audit` command now supports maintained public and direct
beliefs. It inherits the source report's simulator, search budget and public input
view, uses recorded planning anchors, and follows recorded actions through the
public prefix. A diagnostic recommendation never replaces recorded behavior.
No actual private snapshot or gameplay RNG is used for reconstruction.

At each audited position it compares greedy continuation with the search first
action followed by greedy continuation, using the same sampled-world seed.
Identical first actions share a rollout. The audit records raw critic values,
clipped search values, action visits, completed simulated returns, unsupported
branches and work cutoffs. A cutoff has no invented terminal value. These model
continuations do not estimate the value of using search at every later decision.

Audit v2 binds original behavior policy/build/rules and completed returns even
when its input is a reanalysis produced by newer code. The independent review
found and verified that compatibility correction. The shared target loader
retains the existing distillation checks. No search algorithm, game rule,
checkpoint weight, reward or training schedule changed in this milestone.

## Frozen protocol

Use the unchanged-weight normalized initializer from the
[learning verification](COMBAT_SEARCH_LEARNING_2026_10_04.md):
`runs/direct-search-learning-student-20261004/initial.sts-model`, SHA-256
`e22bd23bc0783d67e081816c4066f04a65f2eb1d22be96b19677e0634dbc4862`.
Its public input view is `detached_combat_history_cards_v1`, and its action
restriction is `commit_decisions_v1`. The small trained student remains unpromoted.

Freeze 128 validation starts, indices 10,000–10,127, cycling the eight supported
encounters in the table below: 16 starts each. These are declared fresh
Ironclad A0 starter inventories, not campaign-derived decks or a natural Act 1
encounter distribution. All three controllers receive identical public opening
states. Each triplet shares a source-fight group.

Use `direct_belief_v1`, 64 simulations, depth 16, two particles, 1,024 proposals,
2,048 recovery proposals, 16,384 replay steps and five-second search/belief
ceilings. Planner seed is zero, exploration disabled. Each fight has a separate
96-decision / 300-second limit. Four workers execute independent fights, one
Torch thread each. The objective is victory plus 0.1 times final winning HP
fraction after cleanup; defeat is zero. Depth was kept fixed while testing the
higher simulation budget.

The primary contrast is Gumbel minus the same normalized greedy policy. Root-only
simulation is a descriptive secondary comparison. Use the existing grouped
Hoeffding 95% interval, with no outcome-adaptive sample extension or tuning.
No held-out test, training update, campaign or native run is included.

Before the panel, audit 16 positions from the previous eight development fights.
Afterward, audit 32 positions from the first 16 completed Gumbel fights in the new
panel. Position selection is opening and midpoint in report order, fixed before
examining results. Each position has eight paired sampled seeds, a 128-action
continuation limit and a shared 60-second rollout ceiling. Original behavior
returns are labeled separately from simulated returns.

Repeat the first eight paired starts with one worker for timing. These 24 repeat
executions are not additional independent evaluation cases. The frozen protocol,
CLI commands, logs and analysis script are in `runs/search-benefit-20261004/`.

## Paired fight results

| Controller | Wins | Defeats | Mean HP on wins | Mean combat return |
| --- | ---: | ---: | ---: | ---: |
| Greedy network | 85 / 128 | 43 | 59.38 | 0.71335 |
| Root-only simulation, 64 | 85 / 128 | 43 | 58.26 | 0.71242 |
| Gumbel tree search, 64 | 85 / 128 | 43 | 58.92 | 0.71297 |

Every fight completed: zero game cutoffs, failures or unattempted cases. Both
search controllers have zero wins unique to search and zero wins unique to the
greedy baseline. The observed paired win difference is **0 percentage points**;
the conservative grouped 95% interval is **[−24.01, +24.01] percentage points**.
This interval is wide; the panel does not prove future equivalence. Conditional
winning-HP means are descriptive, not a separate promotion criterion.

| Encounter | Greedy wins | Root-only wins | Gumbel wins |
| --- | ---: | ---: | ---: |
| Nibbit | 16 / 16 | 16 / 16 | 16 / 16 |
| Slimes | 16 / 16 | 16 / 16 | 16 / 16 |
| Bygone Effigy | 5 / 16 | 5 / 16 | 5 / 16 |
| Vantom | 0 / 16 | 0 / 16 | 0 / 16 |
| Corpse Slugs weak | 16 / 16 | 16 / 16 | 16 / 16 |
| Living Fog | 16 / 16 | 16 / 16 | 16 / 16 |
| Skulking Colony | 16 / 16 | 16 / 16 | 16 / 16 |
| Lagavulin Matriarch | 0 / 16 | 0 / 16 | 0 / 16 |

Gumbel searched **1,849/1,849 non-forced decisions** with all 64 simulations,
plus 659 forced actions. Root-only searched **1,833/1,833**, plus 606 forced
actions. There were no belief fallbacks or search deadline cutoffs. Gumbel used
118,336 simulations; root-only used 117,312. Coverage against *all* decisions
is lower because forced actions correctly bypass search. No potions were present
in the declared starter inventories; this panel cannot establish potion utility.

## Critic diagnosis

Across all 128 greedy opening states, the critic predicted a mean combat return
of **0.8601**, versus **0.7133** actually achieved. Opening-state mean absolute
error was **0.3051**. Across all 2,622 greedy decisions, MAE was 0.2045; giving
each fight equal weight yields 0.1895. These are errors in the combat objective,
not win-probability calibration. Per-decision figures reuse correlated outcome
labels and are descriptive, not 2,622 independent trials.

The most useful differences are encounter-specific:

| Greedy opening states | Mean critic | Mean realized return | Wins |
| --- | ---: | ---: | ---: |
| Bygone Effigy | 1.0155 | 0.3191 | 5 / 16 |
| Vantom | 0.5242 | 0 | 0 / 16 |
| Lagavulin Matriarch | 0.5827 | 0 | 0 / 16 |

The other five encounters were all won, and their opening values generally
underestimated completed returns. A single overall bias would conceal these
different errors. Search also clips negative estimates: the greedy recordings
contain 503 negative raw critic values in the losing Vantom/Matriarch fights.
Clipping barely changes overall MSE (0.1131 raw, 0.1123 clipped); it is a bound,
not a remedy for inaccurate values.

The new-position audit covered 32 positions from 16 source fights. All **256
greedy continuations** completed, as did the additional 88 continuations for
different search first actions: 344 actual simulated continuations, no rollout
cutoffs, unsupported branches or belief fallbacks. Raw critic MAE was 0.1389
against those positions' recorded outcomes and **0.2310** against their mean
sampled greedy returns. These comparisons use different continuation behavior
and approximate beliefs; neither makes a simulated mean ground truth.

Search disagreed with greedy at 11 audited positions. Inspection of the public
candidates showed six choices between different copies of the same card type
with the same target, and five Strike/Defend choices. **Every paired rollout
return tied at all 11 positions.** Recommendations are recomputed at the selected
positions; they are not replayed recorded search decisions. The larger played
panel changed 460 action references from greedy along Gumbel's own trajectories,
yet changed no final win/loss result. Reference-level disagreement is therefore
not a sufficient measure of useful planning.

One Bygone Effigy opening illustrates the value problem: critic 1.0321, but only
one of eight sampled greedy continuations won (mean return 0.1264). The recorded
fight happened to win. The 128-case panel's broader Effigy result supports
investigating overestimation; the eight simulated outcomes alone would not.
The earlier eight-fight audit likewise completed its 128 greedy continuations;
its two disagreement positions tied or slightly worsened mean HP return.

These findings make critic reliability and useful action ranking the next
questions. They do not prove either one caused the whole lack of benefit, or
that a winning strategy exists for every starter-deck encounter.

## Latency and throughput

The serial repeat produced identical public action sequences and outcomes to
the same first eight cases in the parallel panel. All requested simulations
finished. Across its non-forced decisions:

| Controller | Decisions | Mean | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Root-only, 64 | 113 | 0.468 s | 0.554 s | 0.693 s |
| Gumbel, 64 | 113 | 0.849 s | 1.057 s | 1.269 s |

The largest *per-fight* Gumbel p95 was 1.199 s; that differs from the pooled p95
above. The tested slice meets the five-second ceiling, including reconciliation
conditioning. The larger parallel panel's maximum Gumbel action duration was
1.407 s. These measurements do not generalize to unsupported content or native
bridge latency.

Of instrumented Gumbel time in the serial repeat, public projection consumed
40.6%, inference 30.5%, sampling/forking 20.8%, engine transitions 5.2%,
conditioning 2.8% and reconstruction 0.1%. Rejection/reconstruction is no longer
the dominant cost here. The measurements do not motivate a rules-engine rewrite
or learned dynamics.

The local arm64 Mac (macOS 26.6.2, Python 3.11.15) reported 728.85 s for the
384-fight parallel panel and 156.29 s for the 24-fight serial repeat. The previous
and current critic audits reported 19.23 s and 66.97 s. Commands ran sequentially
without competing test/reviewer workloads. Full CLI wall times, which also
include startup/exit, are separately retained in `execution.json`.

## Validation and limits

The final focused author suite passed **116 tests in 30.68 seconds** across the
critic audit, search training, input views, direct beliefs, search and package
layout. Compileall and whitespace checks passed. Independent semantic review
found no remaining blockers; its final audit suite passed **14 tests in 6.73
seconds**, including a separate check of the reanalysis provenance correction.

Artifact verification took 58.92 s and checked **408 fight records, 8,029 public
transitions and 5,251 search targets**. Public openings match across every paired
triplet; checkpoint/source/config/target bindings, legal distributions, actual
actions and completed outcomes match. The 24 serial repeats contribute no extra
independent cases. The JSON extract retains per-fight identities, calibration,
latencies and both diagnostic audits.

Implementation/review preparation from the retained start marker to protocol
freeze took about 7m 29s; separate author/reviewer wall totals were not retained.
No native build, release packaging, installation or user setup wait was needed.

This is controlled headless evidence. Direct sampling retains its bounded
content support and finite-particle approximation. Campaign/corpus anchors and
native bridge integration remain separate work. No checkpoint or default was
promoted. Credible combat benefit remains a prerequisite for scaling search
training; default searched play still requires the positive paired Act 1 gate.

The next bounded experiment should compare critic-only leaf estimates with
rollout-assisted estimates under the same time budget, while keeping the actor,
objective and paired starts fixed. Record whether changed choices alter card
type, target or ordering, rather than only instance references. This can test
whether better continuation estimates help before committing to larger search
training or deeper trees. Validation outcomes remain evaluation data; any new
critic fitting needs separate training fights.

For reproduction, use the commands saved in `execution.json`, or copy
`protocol.json` and `run_experiment.py` into a fresh directory directly under
`runs/` and execute the copied script with `PYTHONPATH=. .venv/bin/python`.
It verifies the frozen sources/checkpoint before executing the existing CLIs.
Published outputs are never overwritten. `analyze.py` contains the extraction
and public-artifact checks; its output path must be new when reproducing.
