# ROADMAP.md

This file tracks the most useful next steps for the project. It is not a strict commitment list; it is a guide for future work and for quickly understanding where the simulator is headed.

The goal is to keep the scope growing in a way that stays useful for RL research without turning the codebase into a full game clone too early.

## Current Position

The project currently has:

- a modular combat simulator
- deterministic seeded runs
- single-enemy and multi-enemy encounters
- starter deck cards plus `Slimed`
- `vulnerable` and `shrink`
- structured observations and fixed-width RL encodings
- random, heuristic, Q-learning, DQN, and Double DQN baselines
- the `simple` encounter and the `overgrowth_easy` encounter pool

## Near-Term Priorities

These are the highest-value next steps.

### 1. Better Evaluation Reporting

- break down evaluation results by encounter type
- report per-enemy or per-encounter win rates
- surface damage taken, not just final reward
- make it easier to compare heuristic, tabular, and neural policies fairly

Why:

- the env now contains more than one matchup
- aggregate win rate alone is no longer enough to understand policy quality

### 2. More Encounter Diversity

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

Good next card types:

- draw cards
- multi-hit attacks
- mixed attack/block cards
- cards that care about statuses

Why:

- increases decision depth without requiring a much larger engine rewrite

### 5. Model Checkpoint Save/Load

- save the best DQN / Double DQN checkpoint to disk
- allow later evaluation without retraining
- make benchmark runs reproducible

Why:

- useful for experiments and comparisons
- natural follow-up to the existing in-memory best-checkpoint restore behavior

## Medium-Term Direction

These are good next layers once the near-term items are in a solid place.

### PPO Or Other Policy-Gradient Methods

- add PPO after the environment and benchmarking are a bit richer
- keep masking support explicit

Why:

- worth comparing once the state/action complexity grows beyond the current small DQN-friendly setup

### Better Observation Features

- consider richer deck-order uncertainty summaries
- possibly add compact history features if needed
- only do this when there is a clear learning bottleneck

Why:

- representation quality has already proven to matter a lot in this project

### Better Experiment Tooling

- benchmark scripts with fixed seed splits
- automated comparison tables
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
