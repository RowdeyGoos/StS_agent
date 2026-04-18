# Project Context

This document is the deeper technical companion to the root [AGENTS.md](../AGENTS.md). It is meant to help a new coding session understand the current shape of the simulator quickly.

## Project Summary

The project is a small, modular combat simulator inspired by Slay the Spire. The main goal is to provide a controllable environment for reinforcement learning experiments, not to fully reproduce the game.

The current codebase already supports:

- structured observations for debugging
- fixed-width encoded observations for RL
- fixed discrete action encoding with legal-action masking
- single-enemy and multi-enemy encounters
- random, heuristic, tabular, and neural baselines
- deterministic seeded runs

## Main Gameplay Model

### Player

- Has HP, block, energy, strength, statuses, and a deck
- Draws cards at start of turn
- Plays cards from hand until ending turn
- Block resets at the start of the owner's turn

### Deck

- Tracks:
  - draw pile
  - discard pile
  - exhaust pile
  - hand
- Reshuffles discard into draw when needed

### Enemy

- Uses explicit `Intent` objects
- Each enemy class is responsible for producing its next intent and advancing its intent state
- Enemies can be used alone or as part of an encounter list

### Statuses

Current statuses are intentionally simple:

- `vulnerable`
  - target takes 50% more attack damage
- `shrink`
  - attacker deals 30% less attack damage
  - currently modeled as a persistent debuff cleared when no living `Shrinker Beetle` remains

## Supported Encounters

### Simple

The default debugging encounter is a single `SimpleEnemy` with a deterministic intent cycle. This mode is still important because many unit-style tests and smoke checks rely on it.

### Overgrowth Easy

This is the current multi-enemy encounter pool based on the first three Overgrowth encounters:

- `Nibbit`
- `Shrinker Beetle`
- `Fuzzy Wurm Crawler`
- `Slimes`
  - one medium slime
  - two small slimes

The slimes encounter is the first place where multi-enemy targeting matters.

## RL Interface

### Structured Observation

`CombatEnv.get_observation()` returns a dict that is designed to be human-readable and easy to inspect in logs or tests.

Important fields include:

- `player`
- `enemies`
- `enemy_count`
- `living_enemy_count`
- `hand`
- `draw_pile_size`
- `discard_pile_size`
- `exhaust_pile_size`
- `card_counts`
- `behavior_state` inside each enemy snapshot

The old single-enemy compatibility key `enemy` is still included when possible.

### Encoded Observation

`ObservationEncoder` converts the structured observation into a fixed-width vector.

The encoder currently includes:

- normalized player scalars
- player status features
- normalized pile sizes
- per-pile card-count features
- fixed enemy-slot features
- enemy behavior-state features
- one-hot hand-slot features

Enemy behavior-state features are meant to expose the state that determines future move probabilities, such as script position and possible next move names. They do not reveal an exact sampled future move queue.

Important design choice:

- enemy slots are fixed and stable across the episode
- dead enemies remain in the slot list with `alive = 0`

That stability matters for RL. It prevents target indices and observation layout from shifting after one enemy dies.

### Actions

Tuple action API:

- `("play", hand_index)`
- `("play", hand_index, target_index)`
- `("end_turn",)`

Discrete action space:

- `0` is always end turn
- the remaining action indices map to hand-slot and target-slot combinations

The legal-action mask is the authoritative way for RL policies to know which actions are currently allowed.

In multi-enemy fights, non-targeted cards such as `Defend` and `Slimed` are canonicalized to a single legal play instead of appearing once per enemy slot. This avoids duplicate actions that are semantically identical.

### Action Features

The encoder now also exposes fixed action-feature vectors for every discrete action slot.

These features are built from the structured observation plus the tuple action and include:

- card identity and coarse card type
- energy cost and remaining energy
- projected damage, block gain, and status application
- target-conditioned enemy features
- projected incoming HP-loss reduction

This layer exists so policies can score legal actions by their semantics instead of treating `play hand[0]` and `play hand[3]` as unrelated classes.

### Reward

Reward is intentionally shaped toward winning while preserving HP:

- `+1` on victory
- `-1` on defeat
- subtract scaled normalized player HP loss during the step
- add a small immediate bonus when a player action reduces projected incoming enemy HP loss

This means two winning policies can still be distinguished by how much damage they take.

## Current Training Stack

### Baselines

`game/baselines.py` contains:

- random policy
- heuristic policy
- tabular Q-learning

The heuristic is intentionally fairly competent for the current environment, so it is a meaningful baseline rather than a placeholder.

### Deep RL

`game/dqn.py` contains:

- replay buffer
- DQN
- Double DQN
- Dueling Double DQN
- flat and action-conditioned Q-network architectures
- target network logic
- progress reporting hooks
- best-checkpoint restoration before final evaluation
- checkpoint payload support for saving trained agents
- throughput-oriented training controls such as `train_frequency` and `gradient_steps`

The default DQN-family training path now uses the `action_feature` architecture, which scores legal actions from state features plus encoded legal-action features. The older flat Q-head is still available as a compatibility option.

`game/ppo.py` contains:

- masked PPO
- flat and action-conditioned actor-critic policy heads
- on-policy rollout storage
- GAE advantage estimation
- clipped policy updates
- checkpoint payload support for saving trained agents

The default training path now uses the `action_feature` PPO architecture, which scores legal actions from state features plus encoded legal-action features. The older flat discrete policy head is still available as a compatibility option.

### CLI

`train.py` is the main training entry point.

`sweep.py` is the hyperparameter-search entry point. It calls the trainers directly rather than shelling out through `train.py`, uses Optuna with TPE by default, and averages each trial over multiple train seeds so comparisons are less noisy than one-off manual tuning runs.

`watch_policy.py` is the one-episode inspection entry point for:

- built-in policies such as `heuristic` or `random`
- saved trained `q_learning` agents
- saved trained `dqn` and `double_dqn` agents
- saved trained `dueling_double_dqn` and `masked_ppo` agents

It can print a readable combat trace and write a structured JSON log for later analysis.

`analyze_trace.py` is the post-hoc inspection entry point for those saved trace logs. It flags high-confidence tactical mistakes such as:

- missed lethal
- avoidable incoming damage
- wasted dead-card plays
- suboptimal target choice
- premature end turns

Two especially important knobs:

- `--encounter-set`
- `--dqn-learning-rate`
- `--train-frequency`
- `--eval-interval`
- `--ppo-learning-rate`
- `--rollout-steps`
- `--ppo-policy-architecture`

The DQN-family defaults are separate from the tabular Q-learning defaults on purpose. This was added after discovering that a shared high default learning rate was bad for neural training. The DQN CLI also defaults to the action-conditioned architecture for the same reason PPO does: slot- and target-generalization is better when the network can see action semantics directly.
The training CLI also disables trajectory recording by default and only runs DQN optimization every 4 env steps, because this project is still more Python-bound than network-bound.

For systematic tuning, `sweep.py` is now the preferred workflow over manual one-run-at-a-time CLI tuning. Its default objective is `hp_preserving_score`, which combines win rate with remaining HP so the sweep aligns with the project goal of winning cleanly rather than merely surviving.

## Testing Philosophy

Tests are small, direct, and assert-based.

Current coverage focuses on:

- damage and block rules
- deck reshuffling
- terminal combat behavior
- observation encoding
- action masking and discrete action mapping
- training CLI helpers
- DQN support code
- trace-analysis heuristics

Tests are designed to be runnable without requiring a full external test runner.

## Important Gotchas

### Stable Enemy Slots

Do not remove dead enemies from `self.enemies` mid-combat unless you are prepared to redesign the encoding and action-target mapping.

### Observation Changes Ripple

If you change the structured observation, you likely also need to update:

- `ObservationEncoder`
- heuristic policy
- tests
- demo formatting

### Action Changes Ripple

If you change action structure, you likely also need to update:

- `game/actions.py`
- `CombatEnv.get_legal_actions()`
- `ObservationEncoder.encode_action()`
- `ObservationEncoder.decode_action()`
- action-mask tests

### Python 3.10 Compatibility

The project currently targets Python 3.10+. Avoid syntax that only works in newer Python versions.

Example:

- avoid backslashes inside f-string expressions

## Useful File Map

- `game/core.py`: environment logic and reward shaping
- `game/encoding.py`: RL representation layer
- `game/action_features.py`: semantic legal-action summaries and action-feature encodings
- `game/enemy.py`: encounters and enemy intent logic
- `game/status.py`: status definitions and damage modifiers
- `game/card.py`: card definitions and effects
- `game/player.py`: player state transitions
- `game/deck.py`: card pile bookkeeping
- `game/baselines.py`: non-neural baselines and evaluation helpers
- `game/dqn.py`: neural training loop
- `game/ppo.py`: masked PPO and action-conditioned policy scoring
- `game/trace_analysis.py`: post-hoc trace analysis heuristics
- `main.py`: manual demo output
- `train.py`: CLI orchestration

## Relationship To Other Docs

- See [DECISIONS.md](../DECISIONS.md) for why major architecture choices were made.
- See [ROADMAP.md](../ROADMAP.md) for likely next steps.
