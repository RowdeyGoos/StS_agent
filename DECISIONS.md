# DECISIONS.md

This file records the main architectural decisions behind the current simulator
and the accepted full-game program. It is intentionally lightweight: the goal
is to help future contributors and coding sessions understand why the code and
project boundaries look the way they do.

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

This slot rule belongs to the fixed-width `combat_v0` representation. Full-game
state and candidate contracts use stable semantic entity IDs independent of a
temporary tensor position, while an encoder may still assign stable slots inside
one batch or encounter.

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

This fixed grid is a `combat_v0` training interface, not the full-game action
contract. The full-game path uses typed variable legal candidates and accepts an
explicit retraining boundary.

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
- provides useful combat-local learning pressure and diagnostics

This shaped reward applies to `combat_v0`. It does not define the full-game
utility accepted in D37: complete-run win probability is canonical, while HP is
an auxiliary consequence or diagnostic.

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

This decision describes the synthetic `combat_v0` observation. Before any
`behavior_state` field enters a deployed full-game `PublicObservation`, it must
be classified as currently player-visible or reconstructible solely from public
history and known rules. Enemy-internal script positions that fail that test
remain privileged simulator/debug state; D12 does not authorize exposing them.

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
- preserve the complete visible observation while sampling unseen current draw
  order hypotheses and separately sampling future chance rollouts
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

The sampled future rollouts estimate chance outcomes; they are not an assertion
that ungenerated future events are latent current facts. Any explicit deployed
belief is limited to action-relevant hidden current state and remains
evidence-gated under D37.

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
- retain and timestamp the latest optimizer state completed at or before an
  equal-time cutoff, rolling back a near-boundary update that finishes late
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

## D37. Build The Full-Game Program Behind Backend-Neutral Decision Contracts

### Context

The combat prototype is valuable for controlled RL research, but extending its
fixed observation vector, global discrete action grid, and combat-local utility
cannot produce a reliable full-run Slay the Spire 2 agent. The full project also
needs to support direct policy play, optional planning, and parallel development
without splitting state/action semantics across several controllers.

### Decision

- freeze and preserve the current combat environment through the pending Phase
  0 `combat_v0` baseline package, then retain it as an adapter rather than making
  its interfaces the final full-game contracts
- treat one exactly pinned live game build as the semantic authority and require
  simulator behavior to earn support through differential evidence
- put live, simulator, and replay backends behind one versioned, typed decision
  protocol containing public information and variable legal action candidates
- optimize complete-run win probability and build one reduced-content full-run
  vertical slice before investing in an advanced tactical learner or broad
  content parity
- replace catalog-sized one-hot outputs with shared entity representations and
  ragged candidate scoring at the explicit retraining boundary
- make heuristic, policy-only, tactical-search, and later strategic-search
  controllers interchangeable `DecisionStrategy` implementations over the same
  information and candidate contract; report policy-only and planner-enhanced
  budgets separately
- begin with normalized public observation and observable history; treat
  recurrence and explicit hidden-state beliefs as evidence-gated additions, and
  model future ungenerated randomness as chance rather than belief state
- gate implementation and claims through the accepted Phase 0 target charter,
  phase-specific evidence plans, public/privileged separation, artifact
  fingerprints, and preregistered evaluation

### Why

- live authority and conformance prevent optimizing a subtly different game
- backend-neutral contracts let integration, simulation, learning, search, and
  evaluation progress independently behind stable boundaries
- a common decision-strategy interface makes search genuinely optional and makes
  with/without-search comparisons attributable rather than architectural
- an early full-run slice exposes long-horizon state and value problems before
  effort is spent on shallow content breadth
- evidence-gated memory and belief retain useful tools without assuming that a
  mostly observable game needs a complex partial-observability solution

### Consequence

This decision records direction, not a completed migration. Existing combat
commands and tests remain current behavior until an explicit phase changes them.
The short-term `ROADMAP.md` continues to track nearby combat work; the strategic
roadmap, target charter, and active phase plan own the full-game program.
Parallel tasks may proceed where contracts and file ownership are stable, using
the multi-agent execution model and consolidated milestone updates so the user
can follow decisions and evidence without coordinating the agents directly.
Earlier decisions D2–D4 and D12 continue to define the legacy combat path rather
than immutable full-game contracts. D18, D24, and D25 remain diagnostic search
references, not deployed-planner or global-objective definitions.

## D38. Start Live Integration With A Project-Owned Read-Only Bridge

### Context

The pinned STS2MCP source compiles cleanly against the exact target assemblies,
but compilation does not make its runtime boundary suitable for the project.
Its bootstrap, transport, state builder, action dispatch, profile operations,
and lifecycle are tightly coupled. Reads can alter UI, actions are positional
and non-transactional, and broad unauthenticated routes mix public,
operational, privileged, and destructive capabilities.

Narrowing that code would require replacing the central seams that otherwise
justify a fork. The first live experiment needs a much smaller claim: prove that
an authenticated mod can load, verify the pinned build, classify one visible
screen without side effects, and shut down cleanly.

### Decision

- build the first live path as a lean project-owned C# bridge rather than an
  STS2MCP fork or unchanged third-party binary
- retain the pinned MIT STS2MCP source as compatibility/coverage evidence and
  permit only individually audited snippet reuse with file-level source/license
  provenance behind project-owned typed interfaces
- stage capabilities so the first `live_probe_v0` binary contains only
  authenticated health, manifest, and passive visible-screen reads; compile no
  action, profile, privileged, Harmony, or bridge-write surface into it
- keep transport, public projection, operational metadata, future control, and
  privileged conformance capture as explicit boundaries; privileged capture is
  a separate package that is never co-loaded with the deployed actor
- introduce read-only decision/candidate capture only after the minimal load and
  passivity gate, and introduce one leased transactional mutation surface only
  after public-boundary, phase, recovery, and fixture gates pass
- keep search, policies, models, simulators, and training outside the bridge so
  policy-only and planner-enhanced strategies consume the same public decision
  and candidate contract

### Why

- the smallest binary gives security and passivity claims a tractable audit
  surface
- an allowlisted public projector prevents privileged engine state from
  becoming the de facto actor schema
- the absence of dormant mutation/profile code is stronger than a runtime
  `disabled` flag
- a transport-independent typed core prevents an experimental REST shape from
  becoming the permanent full-game domain API
- staged artifacts make failures attributable and keep installation/load
  approval separate from source design and compilation
- a backend-neutral bridge preserves the optional-search architecture selected
  in D37

### Consequence

The detailed boundary and gates are normative in
`docs/PHASE_1_RESTRICTED_BRIDGE_DESIGN.md`. No bridge implementation or live
authorization follows from this decision alone. Before any source is installed,
the project-owned read-only package must pass its exact compile, reproducibility,
forbidden-surface, and independent-review gates. Before any game launch, the
dedicated profile must have a separately approved recoverable baseline and the
user must approve the exact overlay, configuration, launch, close, and removal
procedure.

## D39. Compose The Final Metadata Boundary Check Into The Baseline Fingerprint

### Context

After D1 and D1B, a standalone D1C request was reviewed to repeat the complete
profile-root, saves, and empty-history predicate without reading bytes. Running
it separately would add an approval and execution round, followed by the same
predicate again before a content fingerprint. The user asked to shorten this
sequence while preserving the privacy and fail-closed boundary.

### Decision

- leave the exact D1C request and review immutable, but mark that alternative as
  deliberately unselected/skipped and never executed
- incorporate D1C's complete two-snapshot predicate as the mandatory pre-read
  gate of `PF-HASH-BASELINE-V1`
- permit no candidate-file open, size check, or byte read until both complete
  snapshots match
- limit PF-HASH to two fresh-open samples of four fixed roles at their already
  observed exact sizes, with protected hashes and explicit content-only claims
- keep copying, offline parsing, Cloud containment, restore, launch, and bridge
  work as distinct later requests and approval IDs

### Why

- the composition removes a redundant user round without removing the reviewed
  pre-read predicate
- performing the predicate immediately before hashing is fresher than relying
  on a separate earlier observation
- strict byte roles and size bounds prevent the accelerated approval from
  becoming a general save-content read
- separate later approvals keep reversible evidence work distinct from Cloud or
  game-state changes

### Consequence

The next profile request is PF-HASH, not D1C. Its first approved invocation
stopped before target-content access after the runner used the protected slot
itself instead of the statically required `profile<number>` component. The
request and reviewed hash remain unchanged, but that invocation consumed its
approval; one corrected invocation requires fresh explicit approval and all
immediate confirmations. A passing result would establish only two matching
path-scoped content samples; it would not establish file-object continuity,
atomicity, semantic validity, recoverability, or Cloud behavior.

## D40. Freeze The Minimal Live Probe Before Parallel Bridge Implementation

### Context

The first project-owned bridge is small enough to implement in parallel only if
its wire bytes, resource limits, game accessors, filesystem roots, build guard,
package shape, forbidden surface, and file ownership are fixed first. Early
preflight drafts still left individual implementers discretion over security
boundaries such as overloads, generated async callsites, symbolic-link order,
path provenance, and verifier fixtures.

### Decision

- accept `docs/PHASE_1_BR0_PREFLIGHT.md` as the implementation freeze for
  `R0a` / `live_probe_v0` after independent contract/test, security, and pinned
  loader/game-API reviews
- keep the first production artifact to one attributed DLL plus one manifest,
  with exactly authenticated health, manifest, and passive public-screen routes
- default-deny game, Godot, filesystem, environment, and network surfaces
  outside the exact reviewed members, callsites, constants, paths, and type
  closure
- assign contract/configuration, host/build identity, transport, public reader,
  packaging/verifiers, and integration to disjoint write boundaries
- require executable golden vectors, malformed/fuzz coverage, known-good and
  known-bad verifier fixtures, dual-SDK compilation, deterministic clean-root
  packaging, and independent source/package review before installation

### Why

- parallel workers can now consume one byte- and overload-exact contract rather
  than inventing subtly different seams
- default-deny metadata and path-provenance checks make absence of profile,
  mutation, outbound-network, and undeclared IPC capabilities reviewable
- keeping the live artifact deliberately small makes load, passivity, and
  teardown failures attributable before observation or control is expanded

### Consequence

Repository-local implementation may proceed behind the frozen ownership table.
Any substantive contract change invalidates the freeze and requires focused
re-review. Compilation and package success remain install-free evidence only;
operator-configuration writes, game overlay installation, launch, live probing,
and removal still wait for the exact built artifacts and a consolidated
reversible operational checkpoint. The corrected profile baseline hash probe
also remains a separate approval-bound task.

## D41. Accept One Reproducible R0a Artifact Without Promoting It To A Live Claim

### Context

The `live_probe_v0` implementation was completed behind the BR0 freeze, but a
first apparent release binary differed from two clean copied-root builds. The
direct repository build had inherited the Git source revision in its assembly
informational version, while a source copy without `.git` emitted the frozen
`0.1.0`. Static semantic checks alone correctly could not prove that those
different build contexts produced the same bytes.

### Decision

- explicitly disable source-revision suffix injection in the production and
  verifier-fixture projects, shared build properties, and controlled build
  invocation
- accept only the replacement artifact produced byte-identically by the pinned
  parity SDK, the servicing SDK, and two independent copied-source parity builds
- bind acceptance to exact contract artifacts, production-source and normalized
  whole-assembly fingerprints, a default-deny member/callsite surface, named
  adversarial fixtures, canonical two-entry packaging, and independent review
- keep the test-only OS-assigned loopback seam out of the release assembly and
  retain the production endpoint as literal `127.0.0.1:43117`
- record the unexpected post-start listener-fault/runtime-state gap as a
  fail-closed P2 liveness residual rather than broadening the first live scope

### Why

- byte reproducibility across repository and clean roots closes a provenance
  gap that normalized IL equivalence intentionally does not cover
- exact default-deny closure and an allowlisted public projector make the
  absence of profile, action, privileged, and undeclared network surfaces
  independently reviewable
- a discarded candidate history prevents a stale but semantically similar DLL
  from being mistaken for the approved package
- preserving a separate live checkpoint keeps install-free compatibility
  evidence distinct from actual loader, screen, passivity, and teardown claims

### Consequence

The canonical repository artifact and evidence are recorded in
`docs/research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md`. The repository boundary
is accepted, but `R0a` is not a live-load pass and Phase 1 is not complete.
Writing operator configuration, adding the game overlay, launching, probing,
and removing it require the exact reversible campaign in
`docs/PHASE_1_R0A_LIVE_CAMPAIGN_REQUEST.md`. The earlier Git-suffixed binary is
discarded and must never be installed.

## D42. Permit A Preliminary Menu Smoke Without Calling It R0a Acceptance

### Context

The exact `R0a` artifact is ready for controlled live evidence, while the
corrected dedicated-profile baseline fingerprint remains separately
unauthorized after its first invocation stopped before target-content access.
The full restricted-bridge design requires a recoverable fixture and Cloud
rollback before its first acceptance load. At the same time, loader discovery,
authenticated health/manifest reads, and the pinned main-menu/settings mapping
can be tested without starting a run or directly inspecting profile content.

Ordinary Steam and game launches may still read, write, or synchronize profile,
save, preference, and Cloud state. Without the baseline those effects are
unobserved and potentially unrecoverable, so a menu smoke cannot silently stand
in for the full gate.

### Decision

- allow one separately approved preliminary menu-only smoke before the
  recoverable-baseline prerequisite only when the user explicitly accepts the
  ordinary opaque Steam/game I/O and no-recovery risk
- require the dedicated profile to be already selected; forbid profile-screen
  visits, profile switching, run start/resume, and direct profile/save/Cloud
  content access or comparison by campaign helpers, bridge code, or operator
- bind exact artifacts and tool hashes, exclusive/no-follow file creation,
  finite process/port/UI/Cloud checkpoints, normal-exit-only quarantine, and
  exact generated-material deletion behind a reviewed operational request
- classify success only as a preliminary compatible-loader, authenticated
  happy-path, visible-screen, normal-exit, removal, and base-restart smoke
- retain the recoverable fixture and Cloud rollback as prerequisites for full
  `R0a`, `L-BOOT`, and `L-PASSIVE` acceptance

### Why

- the preliminary result answers the narrow engineering question needed before
  expanding the bridge while keeping the missing recovery evidence visible
- explicit risk acceptance is more honest than claiming approved launches have
  no profile or Cloud effects
- the same exact artifact can be removed after normal exit without authorizing
  gameplay, profile inspection, or a broader live security campaign

### Consequence

`docs/PHASE_1_R0A_LIVE_CAMPAIGN_REQUEST.md` is a preliminary smoke request, not
the full first isolated load gate. A pass cannot close full `R0a`, complete
`L-NET`/`L-ERROR`, establish passivity, test incompatible locked mode, or remove
the need for the profile baseline. If the game cannot exit normally, no overlay
or credential may be moved, revoked, or deleted under this authorization while
the process remains alive.

## D43. Advance The Live Bridge Through Bounded R0i Vertical Slices

### Context

The first `R0a` menu smoke and `R0b` read-only combat decision succeeded on the
pinned live build. Continuing with document-only design or one broad control
surface would not answer the next engineering question efficiently: whether the
same restricted public boundary could apply real decisions and compose them
across combat, rewards, map travel, and rooms. The user also asked to accelerate
development while keeping components replaceable and comparisons attributable.

The staged design originally reserved broad transactional control for `R1`.
The implemented `R0c` through `R0i` sequence instead exercised smaller
snapshot-bound control slices, each with explicit action caps, advertised legal
candidates, post-action reconciliation, separate approval-bound live campaigns,
and clean teardown. These slices provide useful evidence, but they do not close
the complete recovery, corpus, phase-coverage, or transaction gates assigned to
`R1`.

### Decision

- accept bridge version `0.8.0` / milestone `R0i` as the current project-owned
  live integration artifact for the pinned build
- retain the `R0c`–`R0i` capabilities as bounded pre-`R1` vertical slices:
  snapshot-bound combat actions, complete combat, granular reward handling,
  map selection, supported room choices, and an external controller capped at
  three combat floors
- keep combat, reward, map, and room decision providers outside the bridge and
  independently replaceable so heuristic, learned, and future search-enhanced
  strategies use the same public action boundary
- distinguish repository/fixture evidence from bounded live evidence; do not
  promote fixture-only room handling or the three-floor cap to a live claim
- record the observed batched-controller `decision_response_mismatch` as an
  open stability residual; narrower combat control subsequently resumed, but
  that does not establish a transient, timing, or stale-decision root cause
- preserve exact historical requests and freezes, and maintain
  `docs/PHASE_1_CURRENT_STATUS.md` as the living cross-milestone status source
- make the next target a repeatable multi-floor composition of existing
  capabilities before adding shops, models, search, or a broader control API

### Why

- small live slices made failures attributable and produced working evidence
  faster than another broad design phase
- snapshot binding, advertised-candidate checks, reconciliation, and strict
  process budgets retain a narrow safety boundary while real control is tested
- external provider seams preserve the optional-search architecture and permit
  direct with/without-component comparisons
- explicit evidence levels prevent a successful fixture suite or isolated live
  checkpoint from being mislabeled as full-run reliability
- stabilizing composition before adding more decision types reduces the risk of
  carrying an intermittent protocol/controller defect into a much larger
  surface

### Consequence

The project has a functional bounded live bridge, not merely a combat prototype
or install-free artifact. It still does not have a complete autonomous run,
selected fast backend, trained full-game policy, deployed search component, or
near-optimal result. Phase 1 remains open. Any new installation or game launch
still requires its own explicit authorization; the completed campaign requests
are historical evidence, not standing permission.

## D44. Start The Provisional Headless Environment In Parallel With Live Stabilization

### Context

The live bridge has reached a useful but incomplete `R0i` slice. It is the
semantic oracle and deployment boundary, but running the real game cannot
provide the reset, snapshot, branching, and throughput required for large-scale
training and search. Waiting for complete Phase 1 evidence before implementing
generic backend, state, RNG, replay, and episode infrastructure would serialize
work that can be developed and tested independently. The user explicitly chose
maximum sensible parallelism and removed the earlier planning assumption of
three coding-agent slots. This does not change the bounded subprocess limits of
individual training or benchmark protocols such as D36.

At the same time, reward, map, and room behavior implemented before live
differential evidence cannot be presented as Slay the Spire 2 fidelity. The
existing `CombatEnv` also remains a valuable deterministic combat research
environment whose behavior must not silently become the universal full-game
contract.

### Decision

- begin a real Python headless-environment track immediately, in parallel with
  the existing live-bridge stabilization track
- define one provisional, versioned `headless_v0` backend/decision/candidate
  contract with explicit capability and evidence labels; treat it as accepted
  only for the named experimental slice, not as a final immutable Phase 2 API
- deliver a usable `combat_v0` episode backend first by adapting the existing
  structured observation and legal-action APIs without modifying legacy combat
  semantics
- concurrently build explicit named RNG, serializable reduced run/world state,
  snapshots, fixture playback, trajectory separation, an episode runner, and a
  small project-authored structural progression slice covering current
  reward/map/supported-room verbs
- distinguish `live_observed`, `bridge_fixture`, `combat_v0`,
  `structural_fixture`, and later `differential_verified` evidence in manifests,
  fixtures, traces, and claims
- keep live and headless implementations independent; parse bridge payloads
  through a separately fingerprinted strict wire contract, compare only an
  explicit common public subset, and promote only named mechanics that pass
  later differential comparisons
- apply no fixed numerical worker cap: start every task whose hard dependencies
  are accepted and writable paths are exclusive, while retaining one writer
  for shared contracts and dependency-ordered integration
- continue deferring learned models, search, broad content, shops, potions, and
  target-game parity claims until their required contracts and evidence exist

### Why

- the bridge and simulator solve different problems and can progress in
  parallel without sharing mutable implementation files
- early backend and episode plumbing exposes architectural mistakes before
  expensive content, training, or search work depends on them
- a first combat backend is immediately useful for algorithm and throughput
  integration, while the reduced structural run exposes long-horizon state and
  snapshot requirements
- explicit evidence labels permit fast implementation without turning synthetic
  rules into undocumented assumptions about the pinned game
- dependency and ownership constraints scale better than an arbitrary worker
  count and keep consolidation reviewable

### Consequence

The prior live-first gate for Python implementation is superseded. Headless
contract, infrastructure, combat adapter, and structural reduced-run work may
start now and does not wait for another game launch. This acceleration accepts
that some provisional contracts or rules may require versioned migration when
live evidence disagrees. The live bridge remains authoritative for game
semantics, and only named passing differential cases earn fidelity claims.

`docs/PHASE_1_PARALLEL_EXECUTION_PLAN.md` preserves the completed foundational
task graph and ownership source. The active successor graph is
`docs/PHASE_1_ACTOR_READY_EXECUTION_PLAN.md`. Phase 1 remains open, and this
decision grants no installation, launch, profile, credential, Cloud, or
live-probe authorization.

## D45. Accept The Reduced Headless Join With Restore-Time History Replay

### Context

The provisional `headless_v0` producers now cover deterministic combat,
structural reward/map/room progression, explicit RNG, serializable world state,
public candidates, snapshots, a generic episode runner, and separated replay,
target, and audit records. Composing them exposed two competing risks. A shallow
snapshot could accept individually valid state fragments that did not share one
history, while replaying the complete run after every accepted action reduced
local throughput by roughly an order of magnitude.

The public bridge wire, normalized policy observation, private headless state,
training encoding, and replay/audit records also overlap semantically without
having the same identity or trust contract. Treating them as one representation
would manufacture live identity and blur structural evidence into a fidelity
claim.

### Decision

- accept `ReducedRunBackend` as the composed experimental `headless_v0`
  backend for the current reduced slice
- retain the complete accepted outer candidate-ID history, closed map history,
  combat-entry chronology, RNG provenance, child snapshot, events, and current
  boundary in the versioned private snapshot
- on untrusted restore, replay the accepted outer history and compare the full
  reconstructed private/public boundary; on ordinary reset/apply, retain the
  bounded local invariants and history-length check instead of replaying the
  full prefix
- treat snapshot hashes and semantic keys as deterministic consistency checks,
  not keyed authenticity or proof against a wholesale internally valid
  alternative history
- keep live wire DTOs, public normalized observations, private headless state,
  training encodings, and replay/target/audit streams as explicit separate
  contracts
- preserve component-addressable evidence: legacy combat remains `combat_v0`,
  reduced content/state/composition remains `structural_fixture`, and no
  headless capability becomes `live_observed` or `differential_verified`
  without a named comparison
- interpret the reduced public terminal outcome `victory` only as structural
  route completion; retain the non-policy reason `route_complete` and never
  report it as a full target-game win
- require the independent conformance suite to verify exact source-suffix
  restore, semantically rehashed tamper rejection, stale-binding atomicity,
  public-boundary equality, terminal/unsupported semantics, and exact evidence
  identities before downstream policies or rollout collection consume the
  backend

### Why

- restore-time replay closes the high-risk cross-component provenance join
  while keeping the normal stepping path fast enough for later rollout work
- explicit representation boundaries prevent control identity, RNG, hindsight,
  or live-wire omissions from leaking into actor-facing data
- evidence labels make the reduced environment useful immediately without
  misrepresenting project-authored structural rules as demonstrated game truth
- the independent black-box gate can catch a deterministic but wrong restore,
  schema-valid covert public values, and truthful-capability regressions that
  producer-owned tests may miss

### Consequence

`H3-REDUCED-BACKEND-01` and `H3-CONFORMANCE-04` are accepted on the integration
branch. The accepted fingerprints and current test evidence are recorded in
`docs/PHASE_1_CURRENT_STATUS.md`. This does not accept target-game parity,
training quality, a full-game win contract, or rollout throughput.
`H3-BASELINE-02` and `H3-ROLLOUT-03` are unblocked but remain unstarted until
development resumes.

## D46. Keep Headless Collection Cancellable And Differential Claims Narrow

### Context

The resumed 2026-09-04 work added public-only smoke policies, rollout consumers,
and offline comparisons without changing the accepted headless or wire
contracts. Independent review found that catching episode failures alone did
not preserve a batch when cancellation arrived during process cleanup.

### Decision

- collect through the existing generic runner and serializable reduced-backend
  factory; keep game, chooser, and collector scheduling seeds independent
- retain received episode results and explicitly identify pending episodes on
  cancellation; stop subsequent benchmark repetitions and never fabricate
  unpublished worker results
- include worker close/join in cancellation recovery, restore signal handlers,
  and validate with real bounded spawned-process interruption tests
- keep replay, hindsight targets, audit records, and component evidence separate;
  reduced `route_complete` is not a target-game win
- compare only explicitly shared wire/headless public dimensions; preserve
  divergent and unobserved cases, with no fidelity promotion from synthetic
  matches or queued receipts
- bind offline inputs to reviewed authored-source identities, excluding generated
  build directories before content reads; never automatically bless pin drift

### Consequence

`H3-BASELINE-02`, `H3-ROLLOUT-03`, and the offline portion of
`H4-LIVE-DIFF-02` are accepted. The two-route local benchmark includes recording
and startup costs, not a training performance guarantee. Retained live
differential input remains a separately authorized gate. Exact commits,
measurements, and evidence limits are recorded in
`docs/research/PHASE_1_2026_09_04_ACCEPTANCE.md`.

## D47. Separate Room Identity From Foreground And Completion Evidence

### Context

The 2026-09-04 live campaign found persistent underlying room controls behind
the foreground map and failed rest completion reconciliation. The user approved
a narrow C# lifecycle repair. Independent review rejected its first candidate:
temporarily hiding a room could allocate another ordinal on return, changing
the decision hash and bypassing an intact replay dictionary.

### Decision

- Suppress room candidates and immediately revalidate before dispatch when the
  map is foreground or traveling; do not consume action budget on stale input.
- Recognize map completion only after an accepted literal rest `proceed`, bound
  to the same current run/room, with an open, travel-enabled, nontraveling map
  and no unsupported overlay/content evidence. Inspection alone is insufficient.
- Retain at most 1,000 numeric run/room identity pairs with immutable first kind
  and ordinal, no eviction/reset, and no Godot-object retention. Known pairs
  retain their identity at capacity; new pairs and conflicting kinds fail closed.
- Clear volatile readiness/completion evidence independently of that registry.
  Disappearance and A → B → A returns must not make an accepted action new again.
- Keep wire encoders, decision hashing, action reservations/caps, and event-step
  identity unchanged. Event-to-map completion stays fail-closed; existing
  embedded-combat completion additionally requires an accepted same-event action.

### Consequence

Fresh-returned-snapshot tests must prove rejection through public `Apply`, not
merely resubmit an old ID. After evidence loss, an unchanged previously accepted
projection can be advertised ready but still rejects application; this does
not imply automatic continuation. Source/assembly fingerprints require deliberate
review, not broader verifier allowances. Artifact and live acceptance are recorded
separately in the 2026-09-04 acceptance record.

## D48. Keep Experiment Provenance, Named Evidence And Transient Checks Distinct

### Context

The next increment adds headless experiment artifacts and narrow gold-transfer
conformance consumers without changing the accepted environment or live wire
contracts. Review exposed two important trust limits: trajectories cannot prove
caller-declared seeds, and even a sanitized named evidence record contains more
state than a capture-off live check should emit.

### Decision

- Bind exact declared experiment configuration to finalized manifests and
  validate observable trajectory IDs, pins, counts, decisions, completion and
  budget facts. Do not claim to independently prove scenario/seed declarations
  absent from the trajectory producer contract.
- Preserve received, pending and unstarted work distinctly on cancellation;
  stop later repetitions and never synthesize lost worker results.
- Freeze named-conformance evidence separately from wire observations,
  headless private state, training encodings and replay streams. Evaluate the
  preregistered gold transfer using production rules and pre-only scaffolding.
- Keep external source/admission reviews explicit trusted assertions. Hashes
  detect inconsistency; they do not authenticate a dishonest producer. Synthetic
  matches never promote an entire backend to `differential_verified`.
- A capture-off live adapter may emit fixed findings, eligibility, omissions
  and reviewed code/spec identities only. Its full named record stays transient;
  retained live cases require separate authorization and admission.
- Resolve the existing 95 package-level public symbols lazily from their same
  canonical providers, preserving names/order/identity while avoiding optional
  Torch/Gymnasium imports for lightweight headless commands.

### Consequence

Experiment, evidence and corpus consumers can evolve independently without
merging their representation or privacy boundaries. The offline corpus codec
does not grant capture authority. CLI and actual-client fixtures test the joins;
bounded live acceptance remains separately classified in the next-increment
ledger. Event-step identity and D47 remain unchanged.

## D49. Separate Reward Attempts, Receipt Acceptance And Reconciliation

### Context

A bounded live reward attempt stopped at `reward_action_response_mismatch`.
That compatibility code covers both HTTP-envelope failures and non-exact
receipts. Neither the failed action nor its mutation outcome can be recovered
from the sanitized result. The user approved a narrow capture-off diagnostic
follow-up, not a speculative C# repair or retained response capture.

### Decision

- Add an explicitly selected reward diagnostic CLI without changing ordinary
  controller output, receipt acceptance, timeouts, action caps or retry behavior.
- Keep three distinct bounded counters: attempted action exchanges, exactly
  accepted and bound receipts, and fully reconciled actions. An attempted
  exchange does not establish delivery; receipt acceptance does not establish
  successful post-state reconciliation.
- Emit only fixed action categories, stages and classifications, plus strictly
  validated receipt enums and nullable binding-match facts. No raw bodies,
  body hashes, control IDs, credentials, exception strings, player scalars or
  full histories belong in this diagnostic representation.
- Treat reported receipt mutation state as a receipt fact, not proof of the
  actual outcome of an unbound or uncertain request. Diagnostic failure never
  grants retry or continuation authority.
- Wipe mutable transport buffers on exceptional exits, including cancellation,
  while preserving successful response ownership and existing exceptions.
  This is not a claim that Python can erase immutable receive chunks.

### Consequence

The diagnostic record is separate from bridge wire observations, normalized
public observations, headless state, training encodings and replay records.
Synthetic transport/CLI fixtures establish its behavior; they do not classify
the discarded live response or resolve the open composed-run acceptance gate.
Any later live evidence must identify the reviewed Python sources as well as
the installed bridge artifact and retain only the approved sanitized facts.
The later `bbada1a` campaign satisfied that boundary for one fresh reward: all
four attempts had accepted/bound receipts and reconciled before map arrival.
It does not retroactively classify the discarded earlier response.

## D50. Centralize Bounded Host Transport Without Merging Phase Semantics

### Context

The probe and room Python clients independently implemented the same bounded
socket lifecycle. A cancellation-hardening correction reached the probe copy
but not the room copy, providing concrete maintenance-drift evidence. Comparison
with another project also raised whether game-native automation could replace
the current lifecycle machinery.

### Decision

- Use one private host-side request/send/receive/cleanup implementation for the
  existing probe and room exchange wrappers. Keep route-specific request
  construction, strict parsers, action binding and phase reconciliation outside
  that helper.
- Preserve wrapper signatures, exact request bytes and allowlists, deadline and
  size bounds, fixed failure codes, no-retry behavior and caller-owned successful
  response lifetime.
- Apply the accepted exceptional-exit mutable-buffer cleanup to room exchanges
  as well as probe exchanges. Keep immutable receive-chunk limitations explicit.
- Maintain an independently authored entry-point gate for request bytes, bounds,
  failure/close precedence and cancellation cleanup, including a negative
  control against the preceding implementation.
- Do not adopt AutoSlay, Harmony, generic asynchronous wait helpers or automatic
  overlay decisions as a simplification. Current evidence does not show that
  they supply the authoritative event transition identity this bridge needs.

### Consequence

The host clients have one transport lifecycle without combining their wire or
gameplay semantics. This is fixture evidence only and does not close live room,
reward or composition gates. Future consolidation must remove demonstrated
duplication behind accepted interfaces; it must not manufacture a common state
representation or add another framework merely to reduce line counts.
The later `bbada1a` campaign separately live-exercised the consolidated host
path during a fresh reward diagnostic and one composed ordinary floor; room
transport edge cases and exceptional-exit cleanup remain fixture evidence.

## D51. Keep Bounded Run Entry Explicit Rather Than Resumable

### Context

The combat-oriented bounded runner previously required a fresh combat even when
an authorized campaign was already at a fresh visible reward or map boundary.
The bridge has no durable run incarnation, controller lease, commit sequence or
retry idempotency key. Transparent recovery would therefore require a new wire
contract and retained live journal, not a host-only convenience flag.

### Decision

- Preserve the existing 14-argument combat entry and exact
  `r0i_bounded_run` success JSON. Add only explicit `--entry-phase
  combat|reward|map`, with explicit combat equivalent to omission.
- Let the named existing component client freshly validate only its own visible
  phase. Do not scan, auto-detect, fall back, retry, or adopt an earlier
  controller's uncertain action.
- Represent reward/map entry as a truthful partial prefix. Charge the prefix
  and every later reconciled map selection, including a post-room selection,
  against the unchanged maximum of three.
- Keep the resulting `r0i_bounded_run_entry` host summary separate from bridge
  wire DTOs, normalized observations, headless state, training encodings,
  replay records and persisted checkpoints.

### Consequence

Explicit entry reduces repeated manual setup at known fresh boundaries without
claiming crash recovery, automatic continuation or a full autonomous run.
Independent actual-client fixtures establish default equivalence, request
order, partial accounting, room-context binding and fail-closed behavior. The
reward-entry path is now live-demonstrated through reward/map composition to
terminal defeat with truthful partial-prefix accounting. Explicit map entry
remains fixture-tested and unobserved live.

## D52. Treat Elite As Host-Side Combat Without Expanding The Bridge

### Context

The live map contract already advertises typed `elite` destinations and the
generic combat endpoint reads and applies combat actions without distinguishing
ordinary and elite encounters. The bounded Python runner nevertheless stops at
`elite` as `unsupported_destination_kind`; this prevented the otherwise useful
room-composition campaign from continuing. Changing the C# bridge or wire would
add risk without adding information needed for this host transition.

### Decision

- Treat `elite` as combat-like only in the bounded Python host runner, including
  default, explicit reward/map entry and supported-room post-room paths.
- Preserve the existing run result schemas, milestone names, three-destination
  cap, accounting, replay/context checks, uncertainty stops and no-retry rules.
- Normal/prefix elite combat preserves the pending-monster cap behavior and,
  below the cap, continues to reward/map after victory. Post-room elite combat
  preserves the special existing monster handoff: it runs even when its map
  consumes the final slot, stores `next_combat` under `room_handoff`, and returns
  before reward.
- Add an opt-in map provider ordered elite, rest, monster, ancient, then other,
  while leaving all existing providers exact. Keep `boss` as an act boundary
  and shops, treasure, relics, potions and otherwise unsupported destinations
  fail-closed. Existing `unknown` room routing remains unchanged.
- Reuse the existing combat and reward clients. An unsupported post-elite reward
  is a truthful stop, not authority to infer, skip or retry it.
- Require an independent actual-client fixture gate and bounded coordinator
  live evidence before calling elite continuation live-demonstrated.

### Consequence

The bridge DLL, `live_probe_v0` wire and C# lifecycle remain frozen while one
already public destination becomes usable by the host. Existing behavior stays
compatible. Elite continuation now has implementation and independent
actual-client fixture evidence; its live disposition remains unobserved until
the applicable gate in `docs/PHASE_1_ACTOR_READY_EXECUTION_PLAN.md` passes.
This decision itself grants
no install, launch, profile, endpoint or retained-capture authority.

## D53. Encode Headless Decisions As Public Variable Candidate Sets

### Context

The accepted `headless_v0` boundary exposes a validated public `PolicyView`,
variable typed candidates and separated policy replay, hindsight target and
audit records. The legacy combat `ObservationEncoder` and fixed global action
space cannot represent this full-run boundary without coupling training to
opaque identities or a growing fixed action head.

### Decision

- Introduce a separate versioned `headless_encoding_v1` consumer of
  `PolicyView`; do not modify `headless_v0` or reuse the legacy combat encoder.
- Emit fixed global features plus variable public entity, event and candidate
  rows. Keep candidate IDs only as an out-of-band reversible label mapping.
- Use public opaque references transiently only for joins. Never encode
  references, scopes, hashes, control IDs, backend-private state, hindsight,
  target or audit fields as actor features.
- Require explicit masks for batch padding and preserve candidate-permutation
  and valid opaque-reference-reallocation invariance.
- Score one logit per advertised candidate. Do not add a fixed global action
  head or value head in this increment.
- Admit training only through trusted manifest-bound policy replay. The first
  learner is a tiny deterministic behavior-cloning plumbing smoke over
  structural data, not a policy-quality or fidelity experiment.

### Consequence

Encoder, dataset and policy work can proceed in parallel with bridge work and
without retained live data. Encoder/model correctness is synthetic structural
evidence. Dataset and learner reports preserve each admitted component
attribution and the sorted aggregate set of `combat_v0` and/or
`structural_fixture`; they never promote it to a fidelity label. Learned-policy,
value-learning, PPO/DQN, spawned online rollout and target-game claims remain
deferred. Schema versioning, information
boundaries, ownership and acceptance gates are frozen in
`docs/PHASE_1_ACTOR_READY_EXECUTION_PLAN.md`.

The exact `headless_encoding_v1` schema is frozen in
[`docs/research/PHASE_1_HEADLESS_ENCODING_SCHEMA.json`](docs/research/PHASE_1_HEADLESS_ENCODING_SCHEMA.json),
with acceptance hashes recorded before implementation in the successor ledger.
It deliberately encodes map node fields and summary counts while omitting edge
connectivity and current-node identity. This bounded actor representation does
not replace the complete structured `PolicyView`. Candidate joins copy public
entity fields; public references and row indices remain absent from features.

## D54. Start The Headless Actor With A Small Masked Candidate Scorer

### Context

The accepted public encoding and trusted dataset need a trainable consumer
whose output follows the variable advertised action set, including empty
decision views.

### Decision

- Use separate linear/Tanh embeddings for global, entity, event and candidate
  features. Mean-pool only unmasked entity/event rows, combine them with global
  context, and apply one shared candidate-conditioned scoring head.
- Default to hidden size 64. Version and fingerprint the architecture,
  configuration and accepted encoder independently in checkpoint payloads.
- Return zero logits/probabilities for padding and `None` for selection from an
  empty candidate set. Training consumers must mask padding in their loss.
- Keep this programmatic model separate from legacy agent registration and
  the existing training CLI. Its first training use remains the bounded CPU
  cloning smoke in D53.

### Consequence

Candidate permutations change only output order, while valid public-reference
reallocations cannot change corresponding scores. Unit and persistence checks
establish structural behavior; they make no policy-quality or game-fidelity
claim. A value head, online rollout and larger training remain deferred.

## D55. Keep The First Headless Cloning Run Deterministic And Bounded

### Context

The encoder, trusted actor dataset and candidate scorer need a reproducible
training and artifact join before any larger experiment is useful.

### Decision

- Expose a programmatic structural-heuristic cloning function, separate from
  legacy agent registration and `sts-train`. Require explicit trusted
  development/held-out sources and an accepted backend manifest.
- Use the frozen hidden-size-64 scorer, CPU float32, one process/thread,
  deterministic algorithms and sequential SGD batches without shuffling.
  Default to seed 0, two epochs, batch size 16 and learning rate 0.01; keep
  explicit small-run bounds. Mask candidate padding before cross entropy.
- Restore caller Torch RNG, dtype, thread and deterministic settings after
  training, including failures. Checkpoint loading temporarily constructs in
  float32 and restores the caller's RNG and dtype.
- Bind the canonical report and checkpoint to data, backend, encoding, model
  and training identities. Retain all admitted component evidence, including
  zero-example trajectories, and its exact sorted label union. Validate nested
  counts, metrics, source membership and report/checkpoint consistency.
- Publish only a complete report/checkpoint pair with its final acceptance
  marker. Cancellation removes partial publication; callers keep both returned
  report and logical checkpoint hash anchors for loading.

### Consequence

Identical anchored inputs reproduce report bytes and tensor values within the
declared runtime environment. Regenerating source experiments can change their
operational metadata and manifest hashes. Tiny imitation metrics establish
training plumbing only; online inference, value learning, larger training and
target-game policy claims remain deferred.

## D56. Keep Room-Stage Diagnostics Separate From Run Acceptance

### Context

A live room-interaction timeout produced no accepted summary. Independent
actual-client fixtures proved that the same fixed code can occur before any
room action, after accepted choices or Proceed, or after setup consumes the
shared deadline. The waiting wire intentionally contains no reason or room
identity. The user selected the proposed capture-off host-stage diagnostic as
the next development step.

### Decision

- Add one explicitly selected Python diagnostic entry point around the existing
  bounded run, with the same arguments, providers, deadlines and action caps.
  Preserve all existing commands, result schemas, C# capabilities and wire.
- Record only a final fixed host stage, last validated status/kind category,
  bounded exchange-attempt and exact accepted-receipt counts, last fixed action
  categories and confirmed room completion. Store no identifiers, raw bodies,
  timing, poll counts, action histories or profile/save values.
- Update the stage before each request and after each validation boundary.
  An attempted exchange does not prove delivery; a receipt does not prove
  room completion. Existing same-room checks alone confirm completion.
- Publish an existing strictly validated run acceptance aggregate only on
  success and only when it agrees with the diagnostic. Failure has no partial
  acceptance summary. Invalid diagnostic state or cleanup overrides every
  outcome with the existing fixed internal failure and null records.
- Suppress incidental nested output with a non-retaining sink, preserve
  exceptional-exit cleanup, and stop on the first uncertainty. Diagnostics add
  no request, retry, phase scan, fallback or action adoption.

### Consequence

The separate diagnostic can identify the host stage of a new failure without
reclassifying a discarded run or forming a live transition corpus. It cannot
distinguish the C# causes behind the same waiting projection. D47's event-to-map
limitation remains unchanged. The exact accepted scope is frozen in
[`docs/PHASE_1_ROOM_STAGE_DIAGNOSTIC_PLAN.md`](docs/PHASE_1_ROOM_STAGE_DIAGNOSTIC_PLAN.md);
implementation, fixture, review and any later live evidence are recorded in the
actor-ready ledger with separate acceptance states.
