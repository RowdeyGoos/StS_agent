# DECISIONS.md

This file records the main architectural decisions behind the current simulator. It is intentionally lightweight: the goal is to help future contributors and coding sessions understand why the code looks the way it does.

When a change alters core assumptions about observations, actions, rewards, encounter structure, or training defaults, update this file.

## D1. Keep Structured Observations Separate From RL Encoding

### Context

The simulator needs to be readable for debugging and tests, but RL agents want fixed-width numeric inputs.

### Decision

- `CombatEnv.get_observation()` returns a structured dict that is easy for humans and tests to inspect.
- `ObservationEncoder` in `game/simulation/encoding.py` converts that dict into a fixed-width numeric vector and handles discrete action encoding.

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
- statuses are modeled in `game/simulation/status.py` with simple helper logic
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

- `sts-train` keeps separate defaults for tabular and DQN-family learning rates
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

- training environments created by `sts-train` do not record full trajectory histories by default
- DQN-family trainers optimize every 4 environment steps by default instead of every step
- policy evaluation helpers and training loops reuse environment instances across episodes
- replay sampling avoids rebuilding the entire replay container on every batch sample
- action-feature encoding caches static schema values for the encoder lifetime
- neural collectors derive action masks and action features from one shared legal-action list
- action summaries prepare shared state once and reuse feature rows for duplicate card/target effects

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

- add a dedicated `sts-sweep` entry point for hyperparameter search
- use Optuna with TPE as the default sampler
- score each trial by averaging over multiple fixed train seeds
- keep the default sweep metric aligned with the project objective by combining win rate and remaining HP

### Why

- TPE handles mixed continuous, discrete, and categorical search spaces well
- averaging across fixed seeds makes comparisons less noisy than manual tuning
- a separate sweep entry point keeps `sts-train` focused on running one concrete experiment cleanly

## D18. Define The Seeded Combat Oracle As Win, HP, Then Speed

### Context

Aggregate evaluation can show whether an RL policy wins often, but it cannot say
how far one concrete seeded line is from the best play available in the simulator.
Raw exhaustive search is also complicated by reshuffles, stochastic enemy scripts,
and legal lines that deliberately stall combat.

### Decision

- add a best-first brute-force solver over the full mutable combat state
- treat pile order, enemy-private behavior state, RNG state, and shared-RNG identity as part of the search key
- rank terminal outcomes lexicographically by victory, remaining player HP, remaining enemy HP, and fewer player decisions
- expose explicit step, node, and optional time limits
- report `proven_optimal` separately from the best terminal line found so bounded searches are never presented as exact
- allow the CLI to replay a saved agent against the identical encounter and seed

### Why

- the objective matches the project goal of winning while preserving HP without depending on incidental reward-shaping magnitude
- full RNG-aware keys keep seed-specific future behavior exact when states are deduplicated
- HP never increases in the current simulator, which provides a useful upper bound for proving many victories optimal early
- explicit proof status makes the tool useful both for tiny exact benchmarks and larger best-effort investigations

## D19. Share Automatic CUDA, Apple MPS, And CPU Selection

### Context

The DQN-family and PPO agents previously selected CUDA when available and
otherwise always used CPU. That left Apple Silicon GPU acceleration unused unless
callers knew to pass `--device mps` explicitly.

### Decision

- use one shared Torch device resolver for DQN-family and PPO agents
- prefer CUDA, then an available Apple Metal (`mps`) backend, then CPU
- preserve explicit device overrides for training, sweeps, checkpoint loading, and policy inspection

### Why

- gives macOS users accelerated defaults without creating a separate training path
- keeps device behavior consistent across neural algorithm families
- retains reproducible CPU runs and explicit backend control when needed

## D20. Analyze Oracle Regret In The Agent's Visited States

### Context

Comparing an agent's action list directly with one optimal line only identifies
an exact common prefix. It incorrectly treats alternative optimal actions as
mistakes, and after the first real divergence the two trajectories no longer
occupy comparable states.

### Decision

- replay the trained agent's seeded trace and run counterfactual search from every state it actually visited
- evaluate every legal committed first action, not only the action in one selected oracle line
- preserve all tied best actions and mark the selected action optimal when it matches any of them
- report regret along the oracle's lexicographic objective dimensions: winner, player HP, enemy HP, then action count
- rank weak points and identify the first proven divergence
- retain per-action proof status and label incomplete comparisons as best-found

### Why

- makes later decisions meaningful even after the agent has left the globally optimal trajectory
- distinguishes genuine behavior weaknesses from harmless action-order alternatives
- produces actionable debugging output while keeping uncertainty from bounded search explicit

## D21. Make Resolved Training Configurations Reusable And Checkpoint-Visible

### Context

CLI-only experiments are difficult to reproduce after the original command is
lost. Model checkpoints previously stored network and optimizer parameters but
not encounter selection, reward shaping, or the complete training setup.

### Decision

- allow `sts-train` arguments to be supplied through strict JSON config files
- resolve values in the order built-in defaults, config file, then explicit CLI overrides
- print the complete resolved configuration before training by default
- embed that resolved configuration in saved agent payloads
- write a readable, reusable `.config.json` sidecar beside every saved agent
- version checkpoint payloads and embed compact runtime metadata and outcome summaries
- prefer one unique run directory containing `checkpoint`, `config.json`, and `run.json`
- allow agent readers to resolve a standard checkpoint from its run directory
- retain the older checkpoint-file plus sidecars layout for compatibility
- exclude replay buffers and full episode trajectories from normal checkpoints

### Why

- makes named experiment setups easy to review and version
- keeps quick CLI overrides convenient
- ensures the effective setup, including inherited defaults, remains attached to a checkpoint
- lets the generated sidecar reproduce the same setup without reconstructing a command line
- distinguishes the intended setup from what actually ran and which checkpoint was selected
- keeps checkpoints inspectable without making them unnecessarily large
- avoids scattered same-stem files and leaves room for future run-specific artifacts

## D22. Batch PPO Rollouts Across Independent Environment Slots

### Context

The initial PPO trainer collected every transition from one environment. It
could still build a multi-episode rollout, but neural policy inference operated
on one state at a time and consecutive samples came from one serial trajectory.

### Decision

- expose `num_envs` as a PPO training and sweep option, defaulting to one
- batch policy inference across active environments while keeping simulator steps local
- define `rollout_steps` as the total transition budget across all environments
- assign deterministic episode seeds to slots from one global episode sequence
- track environment identity in the rollout and calculate GAE independently per slot
- sample masked stochastic actions on CPU while keeping network inference and optimization on the selected Torch device
- optionally shard CPU simulator slots across persistent spawned worker processes
- exchange numeric policy inputs and step results through shared NumPy memory instead of pickling observation dictionaries
- keep process-parallel collection CPU-only and retain the in-process collector as the default library behavior

### Why

- amortizes neural inference overhead across multiple observations
- increases trajectory diversity inside each on-policy update
- preserves the existing single-environment behavior as the compatibility default
- prevents return or advantage leakage between interleaved trajectories
- avoids an Apple MPS multinomial defect that can select zero-probability masked actions
- bypasses the CPython GIL for simulator work while preserving deterministic slot and episode ordering
- amortizes process startup and coordination across long training runs without changing PPO semantics

## D23. Profile Semantic PPO Phases Instead Of Only Raw Python Functions

### Context

Wall-clock training speed alone cannot show whether time is spent simulating,
encoding, running policy inference, calculating advantages, optimizing, or
evaluating. Generic Python profilers also misattribute asynchronous CUDA and MPS
work unless the accelerator is synchronized at useful boundaries.

### Decision

- make training profiling opt-in because accelerator synchronization adds overhead
- time named PPO phases and synchronize only phases that submit device work
- report process CPU core equivalents, logical capacity, peak RSS, Torch backend, and available accelerator-memory metrics
- save a versioned `profile.json` alongside profiled run artifacts
- provide a separate analyzer that reads either a profile file or its run directory
- explicitly report that reliable portable average MPS utilization is unavailable through PyTorch

### Why

- produces configuration-level bottleneck evidence that maps directly to PPO tuning controls
- distinguishes simulator throughput problems from optimization problems
- keeps ordinary training free from profiling overhead
- makes profile results reusable and comparable after training finishes
- avoids presenting memory allocation or low CPU activity as proof of accelerator compute saturation

## D24. Separate Seeded Hindsight From Information-Aware Regret

### Context

The exact brute-force oracle includes draw-pile order and RNG state so it can
prove the best outcome for one realized seed. The trained agent cannot observe
those values. A divergence from that oracle can therefore reflect privileged
future knowledge rather than a weakness in the learned behavior.

### Decision

- retain the exact seeded oracle as the reproducible hindsight benchmark
- add opt-in sampled information-aware regret analysis at every visited agent state
- preserve the complete visible observation while randomizing unseen draw order and future RNG streams
- evaluate every legal action on the same hidden-state samples to reduce comparison noise
- rank actions lexicographically by sampled wins, total remaining player HP, total remaining enemy HP, and total action count
- report win-rate confidence intervals, resolved/proven sample counts, and hindsight-best frequency
- label the result as a Monte Carlo root-action estimate because each sampled continuation still uses the hindsight oracle
- mark a decision unresolved when any legal action lacks a terminal result for every sample

### Why

- distinguishes robust tactical mistakes from differences that only look wrong after seeing the realized seed
- common random samples make action comparisons more stable at small sample counts
- keeping the exact and sampled reports side by side exposes both realized regret and expected regret
- explicit limitations avoid presenting approximate determinization as an exact POMDP solution
- opt-in controls prevent the multiplicative search cost from slowing ordinary oracle use

## D25. Optimize Exact Search Without Weakening Seeded Proofs

### Context

Profiling the Slimes oracle showed that generic deep copies dominated runtime.
The solver also expanded duplicate actions for interchangeable adjacent cards,
and its original proof bound assumed every state could win in one more action.
That bound forced unnecessary exploration after a strong victory was found.

### Decision

- clone RNGs with `getstate`/`setstate` and retain their alias relationships
- explicitly copy mutable player/deck containers and share only known stateless built-in cards
- retain generic deep-copy behavior for unknown future card and enemy state
- cache semantic keys for card instances shared across branch clones
- collapse card actions only when playing either card leaves the same exact ordered hand and target
- keep pile order and RNG state in transposition keys so seeded behavior remains exact
- bound the minimum remaining actions by living target count and optimistic maximum card damage
- cache that upper bound on frontier nodes for pruning and proof scans

### Why

- removes Python object-copy work that does not contribute to branch isolation
- avoids duplicate child simulation without canonicalizing order-sensitive piles
- tighter safe bounds can prove an incumbent optimal before exhausting a much larger frontier
- unknown future mutable types retain conservative copy behavior
- on the profiled 2,000-node Slimes seed-7 workload, search time fell from about 6.24 seconds to about 1.72 seconds
- the same seed is now proven optimal after 6,771 expansions, while the previous bound remained unproven after 10,000

## D26. Make PPO Sweep Search Spaces Reproducible Configurations

### Context

The sweep CLI could configure study-level values, but its actual PPO parameter
ranges lived only in Python code. Reconstructing or reviewing an experiment
therefore required matching a command line to the exact source version.

### Decision

- let `sts-sweep` load strict JSON configs with config-first, CLI-override precedence
- keep study settings and fixed training settings as top-level snake-case keys
- add a PPO `search_space` object supporting fixed, categorical, integer, and float specifications
- overlay custom entries on built-in PPO ranges so small focused configs remain convenient
- support nested hidden-layer choices as JSON arrays while storing Optuna-safe labels
- print and optionally save the fully resolved configuration
- embed the expanded effective search space in the saved sweep summary
- provide a CPU-oriented 64-environment PPO sweep example

### Why

- makes the actual optimization domain reviewable before an expensive study starts
- preserves convenient CLI overrides for short test sweeps
- prevents omitted custom entries from silently disabling established search dimensions
- keeps trial summaries tied to both fixed settings and sampled parameter ranges

## D27. Parallelize Sweep Trials With Spawned Processes And Shared Storage

### Context

PPO already parallelized environment collection inside one trial, but Optuna
still trained complete hyperparameter trials one after another. Thread-level
Optuna parallelism is a poor fit for the Python-heavy simulator and also lets
concurrent neural trainers interfere through process-global Torch RNG state.

### Decision

- expose `trial_workers`, defaulting to one for backward compatibility
- treat `trials` as one global per-command budget and split it across workers
- use spawned processes so each trial trainer has isolated Python and Torch state
- require shared storage when more than one worker is requested
- prefer Optuna `JournalStorage` with an explicit `journal_file` on one machine
- retain database URL storage for external or multi-machine coordination
- seed every worker's sampler from a distinct deterministic stream
- keep trial-level parallelism separate from PPO environment-worker parallelism

### Why

- bypasses the GIL for independent training runs
- avoids thread races in process-global neural-library state
- gives every worker a consistent view of completed trials and pruning metadata
- preserves an append-only study record that can be resumed after interruption
- prevents `trials` from accidentally multiplying by the worker count
- makes CPU oversubscription visible and configurable instead of implicit

## D28. Share Named Seeded Encounters Across Inspection Tools

### Context

The brute-force CLI supported each fixed Overgrowth encounter, while
`sts-watch` only exposed `simple` and the sampled `overgrowth_easy` pool.
The two CLIs also duplicated environment-construction logic, which could drift
and make same-seed policy/oracle comparisons misleading.

### Decision

- define the supported named encounters in the shared `CombatEnvFactory`
- construct both brute-force and watched-policy environments through that factory
- expose the same `--encounter` choices in both CLIs
- retain `sts-watch --encounter-set` as a deprecated argument alias
- regression-test initial observation, action mask, RNG state, and subsequent
  transitions for every encounter under matching seeds and actions

### Why

- guarantees that same encounter settings and seed represent the same combat
  realization in both inspection workflows
- removes duplicated encounter mappings from user-facing CLIs
- makes a watched agent trace directly comparable with its seeded oracle
- keeps the expected caveat explicit: different actions produce different later
  trajectories even when the initial hidden randomness is identical

## D29. Add A Permutation-Equivariant Shared Enemy PPO Encoder

### Context

The action-conditioned PPO policy could distinguish enemies, but it received
both flattened slot-specific state features and `target_slot_fraction`. A traced
Slimes decision showed that raw target position explained most of an incorrect
preference for a non-attacking slime, indicating that the policy had learned a
slot shortcut instead of consistently using target state.

### Decision

- add `shared_enemy` as an opt-in PPO policy architecture
- encode every enemy slot with the same learned MLP
- mask dead/padded slots and mean-pool living enemy embeddings for global context
- gather the selected target's embedding from the stable discrete action index
- zero the target embedding for non-target actions
- omit `target_slot_fraction` from this policy's action scorer
- persist all observation-layout and action-feature indices needed to reload it
- retain `action_feature` as the default so existing experiments and checkpoints
  remain directly reproducible
- provide a separate shared-enemy Overgrowth config for clean A/B training

### Why

- enemy semantics, rather than raw list position, determine target scores
- corresponding enemy/target permutations now produce corresponding policy-logit
  permutations by construction
- stable simulator slots and legal-action masking do not need to change
- a separate architecture name prevents an accidental semantic change when
  loading or comparing older checkpoints

## D30. Organize The Package By Responsibility With One Canonical Path

### Context

The original `game/` package accumulated simulator rules, neural agents,
training workers, profiling, exact search, trace analysis, and rendering in one
flat directory. Root CLI scripts also contained their complete implementations.
As the research tooling grew, file discovery and dependency boundaries became
harder to understand.

### Decision

- split implementation modules into `game/simulation`, `game/agents`,
  `game/training`, `game/analysis`, and `game/cli`
- mirror those responsibilities in the test directory
- keep `game/__init__.py` as a small, symbol-level public facade
- remove flat imports such as `game.core` and root command wrappers instead of
  carrying a second compatibility surface forward
- expose installed `sts-*` console commands through `pyproject.toml`
- require code and documentation to use canonical subpackage paths and commands

### Why

- makes ownership and dependency direction visible from the filesystem
- separates combat semantics from learning and post-hoc analysis
- keeps process-worker and CLI infrastructure out of the simulator namespace
- makes stale imports and commands fail immediately instead of silently depending
  on compatibility magic
- avoids accumulating wrappers before the project has a public ecosystem that
  requires a managed deprecation window
- does not affect state-dict checkpoints, whose model formats are independent of
  the removed Python module aliases

## D31. Version Partial Encounter Pools And Represent Multi-Hit Intents Per Hit

### Context

The easy Slimes builder allowed duplicate small-slime types, and adding Mawler
required attacks whose block and status interactions depend on individual hit
boundaries. Calling a small subset the complete Overgrowth hard pool would also
make benchmark results misleading as more encounters are added later.

### Decision

- make Slimes exactly one random medium, one Leaf Slime (S), and one Twig Slime (S)
- name the bounded hard subset `overgrowth_hard_v1`
- keep its three compositions explicit: Mawler, two Nibbits, and Shrinker Beetle plus Fuzzy Wurm Crawler
- store enemy attack damage per hit and add an explicit `attack_count`
- execute and project every hit separately, including block consumption and status rounding
- append Mawler, its move identities, and the intent-count feature to the encoder
- treat the resulting observation/action-feature expansion as a new representation that requires retraining

### Why

- versioned names avoid presenting partial content as full game parity
- per-hit execution is necessary for correct Strength, Shrink, Vulnerable, block, and integer rounding behavior
- stable structured intent semantics keep rendering, heuristics, rewards, and encoders consistent
- explicit incompatibility is safer than silently padding or remapping older checkpoints

### Consequence

Before the card expansion in D32, simple observations grow from 108 to 113,
three-enemy observations from 186 to 201, and action features from 42 to 43.
The checkpoint file format is unchanged, but old neural dimensions and tabular
state keys are not compatible with the new representation.

## D32. Model Draw And Dynamic Card Damage Without Changing The Action Space

### Context

Pommel Strike, Shrug It Off, Iron Wave, and Body Slam add useful sequencing
decisions, but static base-damage/block metadata cannot describe draw effects or
damage based on current player block. Adding them directly to the canonical
starter deck would also change every existing experiment at once.

### Decision

- add `draw_count` and `damage_equals_player_block` to card metadata
- summarize draw count and state-dependent Body Slam damage in legal-action features
- resolve card effects in printed order and draw before the played card enters discard
- expose the four cards in a separate non-canonical sequencing deck factory
- leave the starter deck, tuple/discrete action structure, and action-space sizes unchanged
- append card identities and `cards_drawn_fraction` to the encoders
- make heuristics, trace analysis, and the exact oracle consume the same dynamic action summaries
- require retraining rather than silently adapting checkpoints trained on the earlier schema

### Why

- the simulator can add decision depth without introducing a generic event engine
- one source of tactical summaries prevents Body Slam and mixed-effect cards from drifting across policies and analysis tools
- keeping the preset opt-in preserves old starter-deck combat semantics
- unchanged action spaces preserve legal-action mapping while richer features describe the new cards

### Consequence

The card identities add 56 observation features and five action features. After
both D31 and D32, simple observations have width 169, three-enemy observations
have width 257, and action features have width 48; discrete action spaces remain
11 and 31. The checkpoint serialization version is unchanged, but old neural
models and tabular state keys require retraining.

## D33. Select Complete Decks By Stable Name And Record Their Provenance

### Context

The sequencing deck was available only through Python construction, which made
training it through the standard commands awkward and made saved results
ambiguous about which complete deck had been used.

### Decision

- add a top-level, pickle-safe named registry for `starter` and
  `ironclad_sequencing`
- keep `starter` as the default and avoid extra RNG consumption when resolving it
- expose one fixed `deck` setting in training, sweep, watch, oracle, and benchmark
- record the resolved name in configs, checkpoints, run summaries, traces,
  oracle output, and benchmark reports
- advance benchmark JSON to format version 2; interpret version 1 as implicitly
  using `starter`
- allow cross-deck checkpoint evaluation whenever representation dimensions match
- defer per-episode named-deck-set sampling

### Why

- symbolic names remain pickle-safe in spawned workers
- complete experiment provenance no longer depends on remembering a Python factory
- a different deck is a useful robustness test and is not by itself a schema error
- benchmark schema versioning makes the new required provenance explicit

## D34. Give The DQN Family Its Own Shared-Enemy Architecture

### Context

PPO could remove incidental enemy-slot preferences with `shared_enemy`, while
DQN-family policies still consumed the enemy portion of state as one flat ordered
vector.

### Decision

- add opt-in `shared_enemy` networks for DQN, Double DQN, and Dueling Double DQN
- share one enemy encoder, mask dead/padded slots, and mean-pool living context
- combine targeted actions with the selected enemy embedding and exclude
  `target_slot_fraction` from learned action input
- keep the dueling value stream permutation-invariant and center advantages over
  legal actions when a mask is available
- implement the backbone locally in the DQN module instead of importing PPO
  network internals
- persist and preflight the complete enemy/action layout while leaving checkpoint
  format version 1 unchanged
- retain `action_feature` as the default architecture

### Why

- corresponding enemy and target permutations produce corresponding Q-values by
  construction
- separate implementations preserve existing PPO and DQN state-dict contracts
- explicit layout metadata rejects genuinely incompatible evaluation environments
- opt-in naming keeps legacy flat and action-feature checkpoints reproducible

## D35. Ship Card Records As An Experimental Kernel Before Trainer Integration

### Context

The current encoder grows a new group of one-hot observation and action features
for every card. Replacing it across all policies at once would combine schema,
trainer, replay, and checkpoint risks in one change.

### Decision

- define `card_records_v1` with stable append-only IDs, fixed capacities,
  immutable semantics, ordered hand IDs, and exact sorted pile counts
- reserve card ID zero for padding and preallocate 256 learned 16-value ID rows
- combine ID embeddings with fixed semantic rows through one shared MLP that
  produces 32-value card embeddings for hands, piles, and future actions
- pool pile records invariantly with exact count weighting and retain pile totals
- expose the kernel only through canonical programmatic subpackage imports
- do not alter current environments, policies, trainers, observation widths,
  checkpoint payloads, or defaults
- require a future card-aware checkpoint to record representation version, schema
  fingerprint, registry prefix, maximum trained ID, capacities, and dimensions

### Why

- the foundation can be tested without silently changing trained-agent behavior
- fixed capacity lets append-only card additions keep tensor and parameter shapes
  stable
- semantic sharing supports transfer while learned identity preserves unique cards
- existing models remain `legacy_flat`; later policy integration is an explicit
  retraining boundary rather than an unsafe automatic conversion

## D36. Separate Equal-Experience Rankings From Equal-Time Diagnostics

### Context

Comparing model families after different episode counts mixes policy quality with
episode length and training budget. Running every model sequentially for the same
wall time is fair but makes a broad multi-seed, multi-deck campaign unnecessarily
slow.

### Decision

- use identical environment-transition counts for the primary model ranking
- allow those independent transition-controlled runs to train in up to three
  bounded subprocesses
- rerun only confirmed finalists under one-at-a-time wall-time budgets
- keep historical checkpoints with different budgets in a contextual inventory
- evaluate both named decks and every fixed multi-enemy encounter on one shared
  combat-seed grid
- make every trainer accept optional transition and active-training-time limits
  while preserving episode-driven behavior when limits are absent
- keep `card_records_v1` to computational benchmarks until policy integration
  exists

### Why

- transitions compare sample efficiency without episode-length bias
- isolated time runs compare practical throughput without process contention
- staged selection keeps the complete campaign feasible on one CPU workstation
- separate leaderboards prevent a fast implementation from being confused with a
  data-efficient learner
- resumable per-cell artifacts make a multi-hour experiment auditable and safe to
  continue after interruption
