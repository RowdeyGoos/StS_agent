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
- seeded brute-force oracle searches for exact small-encounter comparisons

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

This is the current multi-enemy encounter pool based on the four encounters from
which an Overgrowth run selects its first three fights:

- `Nibbit`
- `Shrinker Beetle`
- `Fuzzy Wurm Crawler`
- `Slimes`
  - one random medium slime
  - currently two independently random small slimes

The slimes encounter is the first place where multi-enemy targeting matters.
The independent small-slime sampling is a known simulator-fidelity mismatch:
current [Overgrowth reference data](https://slaythespire.wiki.gg/wiki/Slay_the_Spire_2%3AOvergrowth)
specifies exactly one Leaf Slime (S) and one Twig Slime (S). See
[Experiment Workflows](EXPERIMENT_WORKFLOWS.md#known-encounter-fidelity-caveat).

## RL Interface

For a diagram of the complete inference and training paths, see
[Double DQN Agent Flow](AGENT_FLOW.md).

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
The action-feature hot path builds its static feature schema once per encoder,
and training collectors reuse one legal-action result for both masks and
features. Observation-wide tactical values are prepared once, and duplicate
copies of the same card reuse a feature row when they have the same target.
This preserves the exact representation while avoiding repeated schema,
legality, and tactical-effect reconstruction during neural rollout collection.

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

`game/agents/baselines.py` contains:

- random policy
- heuristic policy
- tabular Q-learning

The heuristic is intentionally fairly competent for the current environment, so it is a meaningful baseline rather than a placeholder.

### Deep RL

`game/agents/dqn.py` contains:

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

`game/agents/ppo.py` contains:

- masked PPO
- flat, action-conditioned, and shared-enemy actor-critic policy heads
- on-policy rollout storage
- optional multi-environment rollout collection with batched policy inference
- GAE advantage estimation
- clipped policy updates
- checkpoint payload support for saving trained agents

The default training path now uses the `action_feature` PPO architecture, which scores legal actions from state features plus encoded legal-action features. The older flat discrete policy head is still available as a compatibility option.

The opt-in `shared_enemy` PPO architecture splits the fixed observation back
into non-enemy features and enemy-slot rows. One MLP encodes every enemy row,
living embeddings are mean-pooled for global combat context, and each targeted
action gathers its selected enemy's embedding. The action scorer does not
receive `target_slot_fraction`; consequently, permuting enemy rows and the
matching target indices permutes target logits instead of changing their
meaning. Stable environment slots and discrete action indices are preserved.
The encoder-layout indices needed to reconstruct this model are stored in its
checkpoint.

PPO rollout collection accepts `num_envs`. Each environment has an independent,
deterministically seeded episode stream, while observations, legal-action masks,
and action features are evaluated by the policy as a batch. `rollout_steps`
counts total transitions across all environments, and GAE is calculated
separately for each environment slot so interleaved trajectories cannot affect
one another. The default `num_envs=1` retains the original serial behavior.

CPU PPO can additionally set `env_workers` above zero. Persistent spawned
processes own fixed environment-slot shards and write encoded observations,
masks, action features, rewards, and terminal summaries into shared NumPy
buffers. The parent process keeps Torch inference and optimization and sends
only action indices to workers. This bypasses the Python GIL without repeatedly
pickling structured observations. Worker count is opt-in because process startup
only amortizes well on substantial runs. The standard CLI factory is
pickle-friendly; custom parallel callers must also provide a pickle-friendly
top-level factory.

Optional PPO training profiling measures semantic phases with accelerator
synchronization around device work. It reports phase totals and call means,
process CPU core equivalents, logical CPU capacity, peak resident memory, Torch
backend details, and accelerator-memory values when the backend exposes them.
Profiled artifact runs add `profile.json`, which `sts-analyze-training` can read
from either the file itself or its run directory. MPS compute utilization is not
available through a reliable portable PyTorch API and must be corroborated with
Activity Monitor GPU History when needed.

DQN-family and PPO agents share automatic Torch device selection. With no
explicit `--device`, the order is CUDA, Apple Metal (`mps`), then CPU. This makes
the normal training and sweep commands use supported Apple Silicon GPUs without
requiring a Mac-specific command line.

### CLI

`sts-train` is the main training entry point, implemented by
`game/cli/train.py`.

Training setups can be stored as JSON and loaded with `sts-train --config`. The
file uses snake_case CLI destination names, explicit CLI arguments override file
values, and unknown keys fail fast. Before a run starts, `sts-train` resolves the
built-in defaults, config values, and CLI overrides into one complete
configuration. The preferred `output_dir` workflow creates a unique
timestamp/policy/seed directory per run containing `checkpoint.pt` (or
`checkpoint.json` for tabular Q-learning), `config.json`, and `run.json`.
Checkpoints embed the resolved configuration, versioned run metadata, and a
compact outcome summary. `run.json` exposes the same audit information without
requiring PyTorch. It records execution facts such as timestamps, duration,
environment and optimizer steps, best-checkpoint restoration, runtime versions,
actual device, and Git revision/dirty state, but deliberately excludes replay
buffers and full trajectories. Agent-loading workflows accept either the
checkpoint file or its run directory. The legacy `save_agent` file option and
sidecar layout remain supported.

`sts-sweep` is the hyperparameter-search entry point. It calls the trainers
directly, uses Optuna with TPE by default, and averages each trial over multiple
train seeds so comparisons are less noisy than one-off manual tuning runs.
Sweep CLI values can be loaded from strict JSON config files with explicit CLI
overrides. PPO configs may include a `search_space` object containing fixed
values or categorical/integer/float Optuna specifications. Custom entries
overlay the built-in PPO ranges, while resolved sweep configs and summaries
expand the complete effective search space for reproducibility.

The sweep can distribute one global trial budget across independent spawned
processes with `trial_workers`. Workers reopen the same Optuna study and use
distinct deterministic sampler streams. Local workers coordinate through
`JournalStorage` backed by `journal_file`; a shared database URL remains
available through `storage`. The journal is persistent and therefore also acts
as the resume record. Process-level trials are kept separate from PPO's
`env_workers`, which parallelizes simulation inside each individual trial.

`sts-watch` is the one-episode inspection entry point for:

- built-in policies such as `heuristic` or `random`
- saved trained `q_learning` agents
- saved trained `dqn` and `double_dqn` agents
- saved trained `dueling_double_dqn` and `masked_ppo` agents

`sts-watch` and `sts-oracle` share the same `CombatEnvFactory` and
named encounter set: `simple`, seed-sampled `overgrowth_easy`, and the fixed
`nibbit`, `slimes`, `shrinker_beetle`, and `fuzzy_wurm_crawler` encounters.
With matching combat settings and seed they start from the same visible and
hidden simulator state. Replaying the same actions preserves identical
transitions; selecting different actions creates different trajectories as
expected.

It can print a readable combat trace and write a structured JSON log for later analysis.

`sts-analyze-trace` is the post-hoc inspection entry point for those saved trace
logs. It flags high-confidence tactical mistakes such as:

- missed lethal
- avoidable incoming damage
- wasted dead-card plays
- suboptimal target choice
- premature end turns

`sts-oracle` is the exact seeded-combat inspection entry point. It searches
the real simulator state rather than the observation encoding and includes pile
order, enemy script internals, RNG state, and shared-RNG identity in its state
key. The objective is lexicographic: win, preserve player HP, reduce remaining
enemy HP, then minimize player decisions. A saved agent can be replayed on the
same seed for a direct outcome comparison.

When a saved agent is supplied, the brute-force CLI also replays the agent's
actual trace and evaluates every legal action at every visited decision state.
This produces a per-decision regret report with tied optimal alternatives,
winner/HP/enemy-HP/action-count regret, a first proven divergence, and ranked
weak points. Each legal-action continuation retains its own proof status, so a
resource-limited search is labeled best-found rather than exact.

The exact oracle is intentionally a hindsight benchmark: its full simulator
state includes the hidden draw order and RNG state. Optional information-aware
regret analysis constructs reproducible hidden-state samples that preserve the
agent's complete visible observation while randomizing unseen draw order and
future RNG. Every legal current action is evaluated on the same samples, then
ranked by sampled win rate, mean player HP, mean enemy HP, and mean action count.
It also reports Wilson 95% win-rate intervals and how often each action ties for
the hindsight-best action in a sample. This removes direct knowledge of the
realized seed from the current decision, but each sampled continuation still
uses the hindsight oracle; the result is a Monte Carlo root-action estimate,
not an exact POMDP policy or population-level proof.

Because a policy can intentionally stall, searches have explicit step and node
bounds plus an optional time bound. The result distinguishes a globally proven
optimum from the best terminal line found within those limits. A victory can
often be certified before exhausting the tree because player HP never increases;
once every remaining state has an HP/action-count upper bound no better than the
best victory, no unexplored line can win the objective.

The search hot path avoids generic copies where the simulator has stronger
invariants. RNGs are cloned through `getstate`/`setstate` while preserving shared
identity, player/deck state uses explicit mutable-container copies, and built-in
stateless cards are shared between branches. Semantic card keys are cached, and
duplicate card actions are skipped only when they leave the exact same ordered
hand, preserving the effect of discard order on future seeded shuffles. The
proof bound also includes an optimistic minimum number of damaging card plays,
based on remaining enemy HP, target count, and maximum possible card damage.
These changes preserve seeded oracle semantics while reducing both per-node
cost and the number of nodes needed for many optimality proofs.

Two especially important knobs:

- `--encounter-set`
- `--dqn-learning-rate`
- `--train-frequency`
- `--eval-interval`
- `--ppo-learning-rate`
- `--num-envs`
- `--rollout-steps`
- `--profile-training`
- `--ppo-policy-architecture`

The DQN-family defaults are separate from the tabular Q-learning defaults on purpose. This was added after discovering that a shared high default learning rate was bad for neural training. The DQN CLI also defaults to the action-conditioned architecture for the same reason PPO does: slot- and target-generalization is better when the network can see action semantics directly.
The training CLI also disables trajectory recording by default and only runs DQN optimization every 4 env steps, because this project is still more Python-bound than network-bound.

For systematic tuning, `sts-sweep` is now the preferred workflow over manual
one-run-at-a-time CLI tuning. Its default objective is `hp_preserving_score`,
which combines win rate with remaining HP so the sweep aligns with the project
goal of winning cleanly rather than merely surviving.

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

- `configs/`: reusable JSON training setups
- `game/simulation/`: rules, combat state, observations, encoders, and encounters
- `game/agents/`: baselines, DQN-family agents, PPO, devices, and persistence
- `game/training/`: process-parallel PPO collection and profiling infrastructure
- `game/analysis/`: policy traces, rendering, exact search, regret, and uncertainty
- `game/cli/`: training, sweep, inspection, analysis, and demo entry points
- `game/__init__.py`: stable symbol-level public API
- `tests/`: suites grouped by the same responsibilities as the package

Canonical internal imports use the responsibility-based paths, for example
`game.simulation.core`, `game.agents.ppo`, and `game.analysis.bruteforce`.
Installed `sts-*` commands map directly to `game.cli` modules. Flat paths such as
`game.core` and root command wrappers are intentionally unsupported so there is
only one module and command surface to maintain.

## Relationship To Other Docs

- See [DECISIONS.md](../DECISIONS.md) for why major architecture choices were made.
- See [Experiment Workflows](EXPERIMENT_WORKFLOWS.md) for practical training,
  profiling, sweep, trace-analysis, and oracle commands.
- See [ROADMAP.md](../ROADMAP.md) for likely next steps.
