# ROADMAP.md

This file tracks the most useful next steps for the project. It is not a strict commitment list; it is a guide for future work and for quickly understanding where the simulator is headed.

The goal is to keep the scope growing in a way that stays useful for RL research without turning the codebase into a full game clone too early.

## Current Position

The project currently has:

- a modular combat simulator
- deterministic seeded runs
- single-enemy and multi-enemy encounters
- starter deck cards plus `Slimed`, with an optional four-card Ironclad sequencing preset
- `vulnerable` and `shrink`
- structured observations and fixed-width RL encodings
- fixed legal-action feature encodings for policy architectures
- random, heuristic, Q-learning, DQN-family, and PPO baselines
- masked PPO with an action-conditioned policy head
- opt-in permutation-equivariant shared-enemy PPO policy scoring
- batched multi-environment PPO rollout collection with per-environment GAE
- opt-in process-parallel CPU PPO environment collection through shared memory
- opt-in PPO phase timing and CPU/memory/accelerator resource reports
- the `simple` encounter, canonical `overgrowth_easy`, and a versioned partial `overgrowth_hard_v1` pool with Mawler
- aggregate and per-encounter evaluation metrics, including damage taken
- deterministic fixed-seed policy benchmarks with table and JSON output
- saved trace analysis for common tactical mistakes
- a seeded brute-force oracle for small-encounter optimal-policy comparisons
- per-decision oracle regret traces for ranking trained-policy weak points
- sampled information-aware regret over hidden draw orders and future RNG
- automatic CUDA, Apple MPS, and CPU selection for neural training
- self-contained run directories with reusable configs, checkpoints, and metadata
- reusable PPO sweep configs with explicit Optuna search spaces
- process-parallel Optuna trials with resumable local journal storage
- responsibility-based `simulation`, `agents`, `training`, `analysis`, and `cli`
  packages with one canonical import and command surface

## Near-Term Priorities

These are the highest-value next steps.

### 1. Better Evaluation Reporting

Completed foundation:

- evaluation results break down by encounter composition
- aggregate and per-encounter rows report win rate, reward, final HP, steps, and damage taken
- compare mode and `sts-benchmark` use explicit shared held-out seeds across policies

Next:

- use the brute-force oracle on tractable fixed seeds to report policy optimality gaps
- compare hindsight and information-aware regret so hidden future knowledge is not mislabeled as an agent weakness

Why:

- the env now contains more than one matchup
- aggregate win rate alone is no longer enough to understand policy quality

### 2. More Encounter Diversity

Completed foundation:

- corrected easy Slimes to one Leaf Slime (S), one random medium slime, and one Twig Slime (S)
- added Mawler with per-hit intents and the partial `overgrowth_hard_v1` pool
- added fixed two-Nibbit and Shrinker Beetle plus Fuzzy Wurm Crawler matchups

Next:

- add a few more enemy types or encounter pools before adding full progression
- keep them small and explicit
- prefer encounter diversity over a huge card pool at first

Why:

- prevents overfitting to a tiny enemy set
- improves the value of the environment as a benchmark

### 3. More Status Effects

- add `weak`
- add `frail`
- consider poison or simple damage-over-time later

Why:

- statuses create delayed value and more interesting planning
- the codebase already has a basic status foundation

### 4. More Cards With Sequencing Decisions

Completed foundation:

- added Pommel Strike and Shrug It Off for draw decisions
- added Iron Wave for mixed block/attack sequencing
- added Body Slam for block-dependent damage
- kept the canonical starter deck as the default and exposed an optional research preset

Good next card types:

- multi-hit attacks
- cards that care about statuses

Why:

- increases decision depth without requiring a much larger engine rewrite

### 5. Trace-Guided Policy Improvement

- compare analyzer findings across heuristic, DQN-family, and PPO agents
- use those findings to guide reward tweaks, imitation data, or curriculum choices
- consider simple behavior-cloning pretraining from the heuristic baseline

Why:

- the repo now has trace analysis and an action-conditioned PPO path
- the next leverage point is reducing recurring tactical mistakes, not just adding more algorithms

## Medium-Term Direction

These are good next layers once the near-term items are in a solid place.

### Broader Action-Conditioned Policies

- consider extending the shared action-feature architecture beyond PPO
- evaluate whether action-conditioned value methods outperform flat DQN heads

Why:

- action semantics are now represented explicitly
- the same idea may help value-based agents too

### Better Observation Features

- consider richer deck-order uncertainty summaries
- possibly add compact history features if needed
- only do this when there is a clear learning bottleneck

Why:

- representation quality has already proven to matter a lot in this project

### Better Experiment Tooling

Completed foundation:

- versioned fixed-seed benchmark reports
- deterministic comparison tables and JSON output

Next:

- optional plotting utilities

Why:

- makes the project more useful as a research sandbox

## Later, But Not Yet

These are interesting, but they should probably wait until the combat core is more mature.

- relics
- potions
- multiple combat acts or map progression
- events or shops
- a large generic event-hook system
- full Slay the Spire parity

Why not yet:

- they add a lot of surface area quickly
- they can dilute the project’s value as a clean RL testbed if added too early

## Guidance For Choosing The Next Task

If unsure what to implement next, prefer work that does one of these:

1. improves benchmark quality
2. improves learning signal or observability
3. adds strategic depth without exploding engine complexity
4. keeps the simulator easy to reason about

Avoid work that mostly adds content volume without improving the research usefulness of the environment.

## How To Update This File

Update `ROADMAP.md` when:

- a near-term priority is completed
- priorities noticeably change
- a previously “later” item becomes immediate

When making a major architectural choice while doing that work, also update [DECISIONS.md](DECISIONS.md).
