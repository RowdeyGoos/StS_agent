# Maintained combat beliefs: Act 1 coverage audit

Date: 2026-10-04. **Experimental; no promotion.** Stage 4 broadens declared
headless construction and shared state mechanisms. The ordinary-deck panel
also exposes a substantial remaining sampling problem. It does not establish
campaign coverage, native parity, stronger play or the general latency target.
The [architecture plan](../COMBAT_SEARCH_ARCHITECTURE.md) owns the implementation
sequence; the [training guide](../AGENT_TRAINING.md#experimental-combat-search)
owns command usage. The [evidence extract](combat_belief_coverage_2026_10_04.json)
retains exact source, checkpoint, report and public-trajectory bindings.

## Delivered behavior

The engine constructor resolves all **42 registered ordinary Act 1 encounters**
from the existing Overgrowth and Underdocks registries. It retains the correct
region and normal/elite/boss room behavior. Event fights remain excluded because
they need an event continuation. Neither enemy setup nor damage/turn logic is
duplicated in the planner.

Validated engine-owned selectors can now suspend setup, turn-end cleanup or an
enemy turn. Snapshot validation retains materialized offers, queued effects,
captured enemy intent and hit cursor before refreshing unresolved future RNG.
Pending work without a valid owned selector remains unsupported.

A reactive draw selector exposed a shared public-identity defect: repeatedly
projecting an unchanged group of identical draw-pile cards could rename them.
The real adapter caches a decision while the simulator can project repeatedly,
so the same public choice produced contradictory selected-card references.
Unresolved groups now retain their opaque references across repeated reads and
selector toggles. When cards actually leave the unordered pile, the existing
public destination rule still prevents tracking indistinguishable private copies.

The public declaration remains `sts_declared_combat_start_v1`. It requires fresh
card templates, explicit owned inventory/counters, a revealed encounter and a
compatible catalog. No gameplay seed, private snapshot or native transport was
added. The existing evaluation/collection commands accept the broader declared
encounters; campaign/corpus starts still reject this model without their own
supported public anchor. Search remains opt-in and does not change models inside
a teacher run.

## Dependencies, including previously masked gaps

The audit reread only the **public** traces of the prior pilot's four frozen
greedy development campaigns: **36 combat openings and 563 combat decisions**.
It did not open private replay audits or use a continuation snapshot as an
anchor. The original report and its historical implementation identity remain
unchanged.

The complete content census contains 42 card, 14 relic, 17 potion and 34 enemy
definitions, plus 23 power, six enemy-counter and four selector-operation types.
Against the old reconstruction lists, there are **27 excluded card definitions,
11 relics, 11 potions and 29 enemies**. These are all observed dependencies,
not just the first exception from each decision. Exact names and occurrence
counts are in the extract. Presence in this census does not by itself certify
a reconstructed world or every legal branch.

| Dependency | Resolution in this milestone | Remaining limit |
| --- | --- | --- |
| Encounter composition, enemy HP, opening moves and later latent state | Normal engine setup and complete public rejection; observed actions advance retained worlds | Joint opening matches and later replay can be rare; no guessed enemy phase |
| Ordinary/elite/boss context | Registry-derived region and existing room entry/settlement rules | Event fights and campaign route context need additional public provenance |
| Generated cards and timed modifiers, including previously blocked Infernal Blade/Hemokinesis | Existing engine effects carry state forward; production-catalog generation and temporary-cost tests remain in the suite | Rare generated outcomes can exhaust rejection budgets; no claim that every generated branch was tested |
| Persistent counters, pickup effects and cleanup | Explicit counters, no replay of pickups; Fishing Rod counter/upgrade and room-sensitive lifecycle tests | Missing relic instance data cannot be assumed empty from a tooltip; Lava Rock/New Leaf appearing in the census is not an independent campaign conformance result |
| Potions and choices | Every advertised root branch in the selected fixtures, plus prior generated-potion selector tests | Source checkpoint masks still apply during actual search; generated-offer conditioning remains expensive |
| Setup, end-turn and reactive enemy choices | Validated suspended engine state now forks; no copied selector rules | Native accepted/progress/reconciled lifecycle is still future work |
| Duplicate cards, draw ordering and reshuffles | Repeated-reference correction plus existing hidden-order, posterior and prefix-replay tests | Small populations can lose the observed continuation and fail to recover |
| Enchantments and previous inventory history | Census finds Sharp in 218 public combat decisions | Current fresh-template declaration cannot express an enchanted starting card; no actual campaign start was imported |
| Map, floor and history | All 563 audited inputs have a public map and nonzero floor | Controlled starts do not reconstruct that run context or establish fresh inventory; ordinary observations alone remain insufficient |

This separates rule reuse from setup coverage: the engine already executes
these mechanics. A public anchor and a tractable posterior over unknown state
are still required before that execution becomes useful search.

## Controlled conformance panel

All 42 encounters pass independent normal-setup/public-projection/snapshot
checks. Eight selected encounters also pass actual Gumbel search and **every
advertised root action**, including potions and each enemy target. These use
small synthetic inventories with the production catalog: Hemokinesis, Defend,
Burning Blood, Fire Potion and Block Potion. They isolate state correctness
without claiming ordinary-deck sampling performance.

Additional cases exercise initial Gambling Chip/Pendulum setup, end-turn
retention, a Centennial Puzzle/Stratagem selector after the first of Terror
Eel's three hits, Living Fog summons and Smog expiry, room-sensitive relics,
defeat cleanup and Fishing Rod's victory upgrade. The captured two remaining
enemy hits execute once after selection. Fixed-seed search is unchanged when
the actual hidden draw order/RNG changes. Invalid queued work fails validation.

These checks are in [the coverage tests](../../tests/agent/test_belief_coverage.py)
and [the belief/search tests](../../tests/agent/test_belief_search.py). They are
controlled headless evidence, not native demonstrations.

## Ordinary starter-deck development panel

The frozen teacher is the same compatible Vantom specialist used by the prior
pilot, `runs/vantom-specialist-training-20261002/ppo/chunk-15/final.sts-model`,
SHA-256 `4f06f6566a83bf658685ddbf799e0e4c2856d00eb979a7b7d35b890c25562595`.
Its undiscounted objective is victory plus 0.1 times winning HP fraction. This
is not a new model-selection exercise.

Eight controlled ordinary starter inventories use validation indices 200–207,
paired across greedy, root-only simulation and Gumbel. Settings were fixed before
execution: 16 simulations, depth 16, two particles, 1,024 conditioning proposals,
2,048 replay proposals, 16,384 replay steps, five-second action/belief ceilings,
48 decisions and a 90-second episode ceiling. Four local CPU workers each own
one fight, with one Torch thread each. No held-out tests were opened.

The 24 planned executions completed in **323.21 seconds**, including six explicit
episode truncations. For Gumbel:

| Encounter | Searched / decision attempts | Belief-budget fallback | Forced | Outcome |
| --- | ---: | ---: | ---: | --- |
| Overgrowth Nibbit | 1 / 6 | 4 | 1 | Victory |
| Overgrowth Slimes | 0 / 19 | 14 | 5 | Time cutoff |
| Bygone Effigy | 4 / 20 | 11 | 5 | Victory |
| Vantom | 5 / 25 | 13 | 7 | Time cutoff |
| Underdocks Corpse Slugs, weak | 3 / 12 | 6 | 3 | Victory |
| Living Fog | 3 / 15 | 8 | 4 | Victory |
| Skulking Colony | 2 / 16 | 10 | 4 | Victory |
| Lagavulin Matriarch | 5 / 25 | 13 | 7 | Time cutoff |
| **Total** | **23 / 138** | **79** | **36** | **5 victories, 3 cutoffs** |

There were 135 reconciled Gumbel actions. Three additional decisions finished
thinking after their episode deadline and were not applied. All 23 searched
decisions completed 16 simulations and are present in the public target sidecars.
Coverage is **16.7% of attempts**, or **22.5% of non-forced attempts**. Search ran
in seven of eight ordinary-deck fights; the Slimes case remained entirely on
fallback. No unsupported-content or operational-failure category occurred in
this panel, but that does not prove unseen branches are supported.

| Controller | Victories | Actual defeats | Time cutoffs | Mean HP on its victories |
| --- | ---: | ---: | ---: | ---: |
| Greedy network | 6 / 8 | 2 | 0 | 55.33 |
| Root-only simulation | 5 / 8 | 0 | 3 | 53.80 |
| Gumbel | 5 / 8 | 0 | 3 | 52.20 |

Cutoffs remain unfinished fights, never relabeled defeats or terminal training
returns. The planned-case paired win difference for each searched controller is
−12.5 percentage points, with conservative 95% bounds **[−100, +83.5] points**.
This panel establishes neither a strength gain nor a clean comparison of
completed-combat win probabilities: thinking time prevented three completions
per searched controller.

Gumbel spent 400.33 seconds in reconstruction/recovery and 174.47 seconds in
post-action conditioning, out of 580.13 summed policy seconds across workers:
**99.1%** together. These are existing coarse timers, not a full profiler
breakdown. Its largest per-episode p95 action duration was 5.034 seconds;
indivisible operations can slightly exceed the configured ceiling. Frequent
budget exhaustion and episode cutoffs mean the general 1–5 second target is
**not validated**. The brief independent reviewer tests overlapped the panel's
start; these measurements are a coverage diagnostic, not isolated throughput.

Local full report: `runs/belief-coverage-development-20261004/search.json`.
To reproduce the declared comparison with a fresh output directory:

```bash
sts-agent-evaluate \
  --checkpoint runs/vantom-specialist-training-20261002/ppo/chunk-15/final.sts-model \
  --search --search-model public_belief_v1 --search-simulations 16 \
  --search-depth 16 --search-seconds 5 --belief-particles 2 \
  --belief-proposals 1024 --belief-replay-proposals 2048 \
  --belief-replay-steps 16384 --belief-seconds 5 \
  --search-cases 8 --start-index 200 --split validation --workers 4 \
  --max-decisions 48 --time-limit 90 \
  --encounter overgrowth_nibbit --encounter overgrowth_slimes \
  --encounter overgrowth_bygone_effigy --encounter overgrowth_vantom \
  --encounter underdocks_corpse_slugs_weak --encounter underdocks_living_fog \
  --encounter underdocks_skulking_colony --encounter underdocks_lagavulin_matriarch \
  --output-dir runs/belief-coverage-development-repeat
```

## Validation and next gate

**513 affected checks passed across focused runs**: 406 in the aggregate, one
corrected fixture rerun, and 106 additional projection/recording/runner/package
checks. The aggregate's only failure was an incorrect new assertion expecting
Smog after its ordinary end-turn expiry; the corrected test checks presence
before expiry and absence afterward. Production sources were unchanged between
that aggregate and the correction. Compileall and whitespace checks passed.

One independent semantic review found no remaining blocker in the declared
public-information/RNG/lifecycle scope and independently passed 73 checks.
Measured durations: affected aggregate 42.55 s, corrected fixture 0.23 s,
additional integration 32.52 s, reviewer checks 6.97 s, development panel
323.21 s. A separate implementation/review wall-time split was not retained.
No native package, installation or user setup wait was needed.

Stage 4 delivers broader controlled state coverage and identifies the blockers
that earlier content gates concealed. It does **not** make ordinary-deck search
consistently usable. Stage 5 should first profile and improve conditioning and
recovery, particularly draw/permutation and multi-enemy opening constraints,
using generic engine-owned random operations with correct posterior weights.
Preserve public-prefix checks and bounded fallback; increasing depth or spending
more time on repeated full-prefix rejection is not an established solution.
Then repeat the frozen paired panel and verify student/reanalysis behavior before
scaling training. Campaign/corpus anchors and the native bridge still require
their planned public setup/history support. No promotion gate has passed.
