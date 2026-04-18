# DECISIONS.md

This file records the main architectural decisions behind the current simulator. It is intentionally lightweight: the goal is to help future contributors and coding sessions understand why the code looks the way it does.

When a change alters core assumptions about observations, actions, rewards, encounter structure, or training defaults, update this file.

## D1. Keep Structured Observations Separate From RL Encoding

### Context

The simulator needs to be readable for debugging and tests, but RL agents want fixed-width numeric inputs.

### Decision

- `CombatEnv.get_observation()` returns a structured dict that is easy for humans and tests to inspect.
- `ObservationEncoder` in `game/encoding.py` converts that dict into a fixed-width numeric vector and handles discrete action encoding.

### Why

- keeps game logic independent from a specific model architecture
- makes debugging much easier than working only with vectors
- allows the RL representation to evolve without forcing a rewrite of the environment API

## D2. Use Stable Enemy Slots In Multi-Enemy Encounters

### Context

Once multi-enemy encounters were added, the environment needed targetable enemies and fixed-width observations.

### Decision

- `CombatEnv` stores `self.enemies` as a stable list of slots for the full combat.
- Dead enemies are not removed from the list mid-combat.
- Encoded observations include a fixed number of enemy slots, each with an `alive` feature.

### Why

- target indices stay stable across the episode
- RL action encoding does not shift when one enemy dies
- fixed-width observation encoding stays simple and predictable

### Consequence

Callers should filter on living enemies rather than assuming every slot is active.

## D3. Use A Fixed Discrete Action Space With Legal-Action Masking

### Context

RL methods in this repo currently assume a small discrete action space, but combat legality changes every turn.

### Decision

- tuple actions remain the readable source API:
  - `("play", hand_index)`
  - `("play", hand_index, target_index)`
  - `("end_turn",)`
- RL agents use a fixed discrete action space from `ObservationEncoder`
- `CombatEnv.get_action_mask()` is the authoritative legality signal

### Why

- easy to plug into DQN-style methods
- keeps invalid-action handling explicit
- preserves a clean debugging API while still supporting neural agents

## D4. Reward Should Favor Winning While Preserving HP

### Context

A pure win/loss reward made many policies look similar even when one survived comfortably and another barely scraped by.

### Decision

Reward is:

- `+1` on win
- `-1` on loss
- minus scaled normalized player HP lost during the step
- plus a small immediate bonus for reducing projected incoming enemy HP loss during the player turn

### Why

- encourages policies that win cleanly, not just eventually
- gives denser learning signal than terminal rewards alone
- lines up with the intended objective for this project: win with as much HP left as possible

## D5. Keep A Very Small "Simple" Encounter Alongside Richer Encounter Sets

### Context

The project needs richer combat for RL, but also a tiny stable environment for debugging and regression tests.

### Decision

- retain the single deterministic `SimpleEnemy` path
- add richer encounter pools, such as `overgrowth_easy`, without removing the simple mode

### Why

- faster smoke tests
- easier debugging of core mechanics
- avoids forcing every test or experiment into the more complex multi-enemy path

## D6. Prefer Explicit Combat Rules Over A Premature Generic Event System

### Context

The simulator may eventually need many statuses, relics, and triggered effects, but the current scope is still modest.

### Decision

- keep combat rules explicit in the relevant modules for now
- statuses are modeled in `game/status.py` with simple helper logic
- enemy and card effects directly call the small set of game-state methods they need

### Why

- easier to reason about correctness
- less abstraction overhead while the ruleset is still changing quickly
- better fit for a research playground than a full engine architecture

### Consequence

When adding more complex mechanics later, it may become worth introducing a more generic hook/event model. We are not there yet.

## D7. DQN And Tabular Q-Learning Need Different Defaults

### Context

A shared learning-rate default worked poorly once neural agents were added. The value was reasonable for tabular Q-learning but too large for DQN.

### Decision

- `train.py` keeps separate defaults for tabular and DQN-family learning rates
- DQN and Double DQN restore the best evaluation checkpoint before the final evaluation by default

### Why

- avoids avoidable late-training collapse
- makes CLI defaults safer
- gives more trustworthy final evaluation summaries

## D8. Keep Python 3.10 Compatibility

### Context

The project currently targets Python 3.10+.

### Decision

- avoid syntax that requires newer Python versions unless the version floor is intentionally raised
- prefer broadly compatible language features in user-facing scripts and library code

### Why

- lowers setup friction
- keeps the project usable on more machines
- prevents subtle issues such as Python-3.12-only f-string expression syntax

## D9. Use Overgrowth Easy As The First Multi-Enemy Benchmark

### Context

The project needed a richer encounter pool than the original single enemy, but not the full complexity of a complete run structure.

### Decision

- implement the first-three-fights pool from Slay the Spire 2 Overgrowth as the first richer benchmark set
- support both solo fights and the 3-slime encounter

### Why

- introduces multi-enemy targeting and more diverse enemy behavior
- still small enough to debug and train on quickly
- a better intermediate step than jumping straight to relics, potions, or full map progression

## D10. Use A Shared Save/Load And Single-Episode Trace Workflow Across Agent Types

### Context

Once multiple agent families existed, it became awkward to inspect one concrete combat run in a consistent way.

### Decision

- use shared persistence helpers to save trained `q_learning` and DQN-family agents
- use one common traced-rollout path for both built-in policies and saved trained agents
- write episode traces as structured JSON so they can be inspected later

### Why

- makes policy inspection architecture-independent
- supports debugging what a trained agent struggles with on one specific combat seed
- keeps the “watch one episode” workflow separate from the training loop itself

## D11. Favor Training-Loop Throughput Over Training-Time Trace Richness

### Context

Once the environment gained richer observations, multi-enemy encounters, and trace logging, neural training became noticeably Python-bound. GPU acceleration alone was not enough because much of the wall-clock time was spent in environment stepping, tensor conversion, replay sampling, and checkpoint evaluation.

### Decision

- training environments created by `train.py` do not record full trajectory histories by default
- DQN-family trainers optimize every 4 environment steps by default instead of every step
- policy evaluation helpers and training loops reuse environment instances across episodes
- replay sampling avoids rebuilding the entire replay container on every batch sample

### Why

- improves wall-clock training speed without changing the debugging and watch-policy workflows
- keeps the readable structured environment API intact
- targets the real bottleneck in this project: Python-side overhead rather than raw network compute

## D12. Expose Enemy Behavior State, Not Sampled Future Moves

### Context

Some enemies have deterministic scripts and others can branch stochastically. Current intent alone is not always enough to infer the correct future move distribution, especially when the same visible move can occur in multiple script positions.

### Decision

- structured enemy observations include a `behavior_state` block
- `behavior_state` exposes script-position information and the set of possible next move names
- observations do not expose the exact sampled future move sequence

### Why

- makes the environment closer to Markov for RL agents
- gives the agent the state needed to reason about future move probabilities
- avoids leaking unresolved randomness that a player would not know in advance

## D13. Add Dueling Double DQN As A Separate Policy, Not A Silent Replacement

### Context

The project already had `double_dqn` as the main stronger DQN-family baseline. Adding a dueling architecture is useful, but silently changing the existing Double DQN implementation would make old experiments and checkpoints harder to compare.

### Decision

- keep `double_dqn` unchanged
- add `dueling_double_dqn` as a separate selectable policy and checkpoint type

### Why

- preserves backward compatibility for existing runs and saved agents
- makes experiment comparisons cleaner
- lets the dueling head architecture be evaluated as an explicit ablation

## D14. Add Masked PPO As A Separate On-Policy Baseline

### Context

The project already had value-based baselines, but some policy-learning questions are easier to study with an on-policy actor-critic method that handles discrete masked actions directly.

### Decision

- add `masked_ppo` as a separate selectable policy and checkpoint type
- keep it in its own module and training path rather than mixing it into the DQN code

### Why

- provides a meaningful non-value-based baseline
- keeps the DQN codepath simpler
- makes algorithm-family comparisons explicit in the CLI and saved checkpoints

## D15. Add A Shared Legal-Action Feature Layer For Neural Policies

### Context

The fixed discrete action space works well for masking, but it makes neural policies treat semantically similar actions such as `play Strike from hand slot 0` and `play Strike from hand slot 3` as mostly unrelated logits.

### Decision

- add a shared action-summary and action-feature layer derived from the structured observation plus tuple action
- expose those action features through `CombatEnv` and `ObservationEncoder`
- keep the flat PPO policy head as a compatibility option
- keep the flat DQN-family Q-heads as compatibility options
- make action-conditioned PPO and DQN-family training the default architectures

### Why

- improves generalization across hand slots and target slots
- gives policies direct access to action semantics such as projected damage, block gain, and target-conditioned features
- creates one reusable place for future policy architectures and trace-analysis heuristics to share tactical action information

### Consequence

- non-targeted cards are canonicalized to a single legal action in multi-enemy fights instead of being duplicated once per enemy slot
- target-specific action features are zeroed out for non-target cards so they do not pick up irrelevant enemy identity noise

## D16. Keep Trace Analysis High-Confidence And Post-Hoc

### Context

Trace logs are useful only if they quickly surface the most actionable mistakes. Overly clever analysis risks producing noisy findings that are hard to trust.

### Decision

- keep trace analysis in a separate post-hoc CLI rather than mixing it into training
- focus on a small set of high-confidence tactical categories:
  - missed lethal
  - avoidable incoming damage
  - wasted dead-card plays
  - suboptimal target choice
  - premature end turns
- enrich saved traces with pre-action legal actions and masks so later tooling has the right context

### Why

- keeps training output uncluttered
- makes one-combat inspection more actionable
- provides a stable debugging tool that works across agent families

## D17. Prefer Optuna TPE Sweeps Over Manual Hyperparameter Guessing

### Context

Once the project had several neural agents and multiple reward-shaping knobs, manual CLI tuning became slow, noisy, and hard to reproduce. RL results also vary substantially with seed, so one-off runs are easy to over-interpret.

### Decision

- add a dedicated `sweep.py` entry point for hyperparameter search
- use Optuna with TPE as the default sampler
- score each trial by averaging over multiple fixed train seeds
- keep the default sweep metric aligned with the project objective by combining win rate and remaining HP

### Why

- TPE handles mixed continuous, discrete, and categorical search spaces well
- averaging across fixed seeds makes comparisons less noisy than manual tuning
- a separate sweep entry point keeps `train.py` focused on running one concrete experiment cleanly
