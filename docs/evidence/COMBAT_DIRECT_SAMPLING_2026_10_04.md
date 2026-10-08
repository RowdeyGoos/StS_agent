# Direct combat belief sampling: performance proof

Date: 2026-10-04. **Experimental, evaluation-only; no promotion.** This milestone
tests whether conditional draw/HP proposals remove the bottleneck measured in
the [earlier coverage audit](COMBAT_BELIEF_COVERAGE_2026_10_04.md). The
[architecture plan](../COMBAT_SEARCH_ARCHITECTURE.md) owns the design and remaining
gates; the [training guide](../AGENT_TRAINING.md#experimental-combat-search) owns
usage. The [JSON extract](combat_direct_sampling_2026_10_04.json) binds reports,
source and public artifacts.

## Implemented boundary

The new opt-in `direct_belief_v1` receives an explicit fresh-inventory declaration
and reconciled public observations/actions. It never receives the real engine,
its RNG, private identities or a continuation snapshot. For this bounded slice,
the existing public inputs are sufficient; no additional headless exporter or
native protocol extension was needed.

Hypothetical worlds retain engine-evolved effects, counters, pending work and
enemy state. Unknown remaining draw order is represented as a uniform permutation
between known top/bottom cards. Each independent search simulation samples that
permutation directly. Filtering proposes the observed draw sequence using physical
card multiplicities, then validates the complete remaining public successor.
Coarse guidance by definition/upgrade does not merge copies with different
modifiers. Known positions contribute likelihood one or zero. Initial HP guidance
uses the engine's sequential eligible-HP rule, including avoidance of already
used HP. Accepted proposals carry these likelihood weights exactly once.

Other chance outcomes still use normal engine sampling and public rejection;
weighted particles and bounded public-prefix recovery remain. This is an
approximate belief over other latent variables, not a universal exact sampler.
All card, enemy, potion and cleanup effects continue through the normal engine.
Conditional helpers are optional and local to hypothetical execution; ordinary
gameplay RNG behavior is unchanged.

The guard covers the eight tested encounters, fresh supported card templates,
four relic definitions and eight potion definitions listed in
[`direct.py`](../../game/agent/search/direct.py). Innate/enchantment ordering,
random insertion, autoplay, retention and generated/moved-to-hand sources remain
excluded. Unsupported content returns a named fallback without switching models.
Known-bottom sampling has an engine primitive test; no supported agent-side
content source introduces a bottom placement yet.

## Historical duplicate identities and input compatibility

The first smoke exposed a separate ambiguity: legacy displayed history can link
an earlier Strike play to the particular physical Strike that reappears after an
unobserved reshuffle. That association is not established for identical copies.
It also made complete-public matching reject otherwise equivalent worlds.

The direct model uses `detached_combat_history_cards_v1`: historical card-subject
links are detached in real and hypothetical network inputs and matching keys.
Ordered action kinds, stable targets, current card descriptions/candidates and
the full original observation/action journal remain. The normalized greedy
baseline uses the same view and receives a distinct policy identity; its frozen
checkpoint is unchanged. Existing public protocol records and older search
models are unchanged. This is a conservative input view, not a global repair of
historical identity semantics in every existing consumer.

The learner currently encodes original recorded decisions. To avoid training on
different inputs from the teacher, direct collection, reanalysis and distillation
are explicitly disabled pending matching learner support. The earlier
`public_belief_v1` learning path remains available.

## Frozen development comparisons

The teacher remains the undiscounted Vantom specialist at
`runs/vantom-specialist-training-20261002/ppo/chunk-15/final.sts-model`, SHA-256
`4f06f6566a83bf658685ddbf799e0e4c2856d00eb979a7b7d35b890c25562595`.
Its objective is victory plus 0.1 times winning HP fraction after cleanup.
No held-out test was opened and no checkpoint/configuration was selected from
these results.

The primary panel retains the earlier eight ordinary-deck starts, validation
indices 200–207 and encounter order. It pairs normalized greedy, root-only and
Gumbel controllers at 16 simulations, depth 16, two particles, 1,024 conditioning
proposals, 2,048 recovery proposals, 16,384 replay steps, five-second action/belief
ceilings, 48 decisions and 90 seconds per episode. Four CPU workers each own one
fight and use one Torch thread. The comparison with the historical audit measures
the combined direct sampler and history-view change, not an isolated sampling
algorithm ablation. All three policies within the new panel use the same view.

A separate bounded single-worker Vantom comparison at validation index 203 uses
64 simulations with the same other limits. It checks the play budget's latency
on one fight; it does not establish a general five-second guarantee. The 256
simulation research setting and large training runs are deferred.

## Results

The primary panel completed all 24 executions in **17.12 seconds** on the local
arm64 Mac, macOS 26.6.2 and Python 3.11.15. No reviewer or test run overlapped
this panel. The eight public openings were verified equal to the historical
audit's openings.

| Controller | Victories | Actual defeats | Cutoffs | Mean HP on its victories | Searched / non-forced decisions |
| --- | ---: | ---: | ---: | ---: | ---: |
| Normalized greedy network | 6 / 8 | 2 | 0 | 55.33 | — |
| Root-only simulation | 6 / 8 | 2 | 0 | 57.33 | 111 / 111 |
| Gumbel | 6 / 8 | 2 | 0 | 54.50 | 110 / 110 |

Gumbel made 148 decisions: 110 searched and 38 forced. Every searched decision
completed 16 simulations, totaling 1,760. There were no belief-budget fallbacks,
episode timeouts, recovery replays or operational failures. Its largest
per-fight p95 action duration was **0.325 seconds**; the maximum individual
action was **0.346 seconds**. Root-only simulation completed 1,776 simulations,
with a largest per-fight p95 of 0.218 seconds.

| Gumbel measure | Historical rejection panel | Direct panel |
| --- | ---: | ---: |
| Searched / non-forced attempts | 23 / 102 (22.5%) | 110 / 110 (100%) |
| Belief-budget fallbacks | 79 | 0 |
| Episode time cutoffs | 3 | 0 |
| Reconstruction + conditioning / summed policy time | 574.80 / 580.13 s (99.1%) | 2.79 / 26.29 s (10.6%) |
| Largest per-fight p95 action duration | 5.034 s | 0.325 s |

The current Gumbel timers instead spend 8.31 seconds in inference, 7.92 seconds
in public projection and 5.44 seconds sampling/forking worlds. These are summed
coarse timers across workers, not elapsed panel time. The historical audit also
had brief reviewer-test overlap at its start; the table is evidence of the
coverage/bottleneck change, not an isolated throughput speedup factor.

Both searched controllers have a paired win-rate difference of zero versus the
normalized network, with conservative grouped 95% bounds **[−96.0, +96.0]
percentage points**. They win and lose the same encounters. This small panel
demonstrates useful search coverage and latency; it establishes **no strength
improvement**. Conditional HP differences do not establish such an improvement
either. The starter inventories have no potions, so potion behavior is covered
by focused fixtures, not these performance results.

The separate 64-simulation, one-worker Vantom check completed all three
executions in **34.56 seconds**. Gumbel searched all 24 non-forced decisions
(plus nine forced), completing 1,536 simulations without fallback or replay.
Its p95 was **1.174 seconds**, maximum **1.206 seconds**, and summed policy time
22.52 seconds. Reconstruction/conditioning accounted for 2.7% of that time.
All three controllers actually lost the fight; there were no cutoffs. This
supports the requested play budget's latency on this one fixture, without
claiming general content coverage or improved decisions.

Local full reports are `runs/direct-belief-development-20261004/search.json`
and `runs/direct-belief-play-latency-20261004/search.json`. To reproduce the
primary panel with a fresh output directory:

```bash
sts-agent-evaluate \
  --checkpoint runs/vantom-specialist-training-20261002/ppo/chunk-15/final.sts-model \
  --search --search-model direct_belief_v1 --search-simulations 16 \
  --search-depth 16 --search-seconds 5 --belief-particles 2 \
  --belief-proposals 1024 --belief-replay-proposals 2048 \
  --belief-replay-steps 16384 --belief-seconds 5 \
  --search-cases 8 --start-index 200 --split validation --workers 4 \
  --max-decisions 48 --time-limit 90 \
  --encounter overgrowth_nibbit --encounter overgrowth_slimes \
  --encounter overgrowth_bygone_effigy --encounter overgrowth_vantom \
  --encounter underdocks_corpse_slugs_weak --encounter underdocks_living_fog \
  --encounter underdocks_skulking_colony --encounter underdocks_lagavulin_matriarch \
  --output-dir runs/direct-belief-development-repeat
```

For the latency check, use `--search-simulations 64 --search-cases 1
--start-index 203 --workers 1`, retain only `--encounter overgrowth_vantom`,
and choose another fresh output directory. The recorded runs invoked the same
CLI via `PYTHONPATH=. .venv/bin/python -m game.cli.agent_evaluate`.

## Validation

Focused checks cover enumerated duplicate-draw probabilities, known ends,
reshuffles, distinct cost lifetimes, the exact one-third/two-thirds posterior
for an unknown versus known-top hypothesis, HP uniqueness and RNG requests,
ordinary engine progress in all eight encounters, selectors and potion branches,
fixed-seed hidden-state invariance, no real-engine mutation, snapshot round trips,
history normalization, unsupported setup and explicit training gates.

One independent semantic reviewer found no remaining blocker for the guarded
evaluation-only scope. The reviewer independently passed 148 checks in 6.57 s
across direct beliefs, combat choices, shuffle hooks and native RNG fidelity,
then passed the corrected setup-fallback regression in 0.14 s. A separate
reviewer smoke completed eight fights through 133 reconciled decisions in
3.07 s with no belief failures; these were heuristic fixture checks, not search
strength measurements.

Author validation passed 166 search/belief/training checks in 30.88 s, followed
by 22 direct/integration checks in 6.79 s after the named-fallback correction,
and 21 runner/package checks in 28.18 s. Three additional exhaust-selector,
potion/cleanup and guided-recovery fixtures passed in 0.35 s. These runs overlap;
their counts are not a count of unique tests. Compileall and whitespace checks
passed. Artifact verification checked all 27 completed trajectories and 359
search targets in 0.68 s: source/checkpoint/policy/configuration bindings,
applied legal actions, normalized probabilities, simulation counts and completed
combat returns matched their reports. Both report implementations still match
the current production sources.
A broader exploratory headless run was deliberately stopped after 1,790 passing
checks in 163.61 s; its full 7,364-test headless suite was not completed and is
not claimed as acceptance evidence. Focused native RNG/choice/shuffle evidence
above covers the changed ordinary-engine call sites.

Separate implementation wall time was not retained. No native build, package,
installation, user setup wait or live-data access was required. Campaign/corpus
anchors, native proof, learner-view integration and statistically credible combat
and Act 1 improvement remain separate gates.

The next learning milestone must first make the normalized planning view explicit
in learner inputs and validate collection, distillation and reanalysis against
that view. Establish credible paired combat improvement before scaling training.
Broader content and bridge support still require their own public setup/history
provenance and conformance evidence. Search remains opt-in; no default-promotion
gate has passed.
