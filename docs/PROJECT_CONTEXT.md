# Combat research context

This is a task-specific technical reference for the combat simulator and RL
research path (`combat_v0`). [AGENTS.md](../AGENTS.md) owns the working process.
The [current integration status](PHASE_1_CURRENT_STATUS.md) covers live events
and the reduced headless actor; neither is full-game parity for this simulator.

## Gameplay and state

`CombatEnv` owns the player, encounter, seeded RNG and optional trajectory.
The player has HP, block, energy, strength, statuses and a deck with draw, discard,
exhaust and hand piles. Discards are reshuffled by the explicit environment RNG.
Keep mutable state serializable and avoid global randomness.

The starter deck is five Strikes, four Defends and Bash. The optional
`ironclad_sequencing` deck includes Pommel Strike, Shrug It Off, Iron Wave and
Body Slam. `Slimed` is a supported generated status card. Named deck factories
are pickle-safe and their names travel through training/inspection provenance.

Enemy slots stay stable for an encounter: dead enemies remain in the list.
Filter living enemies without renumbering targets. Intents distinguish per-hit
damage and attack count; block and rounding resolve each hit separately.
The supported statuses include vulnerable and shrink; refer to the status/rule
implementation for exact ordering.

## Encounters

| Pool | Contents |
| --- | --- |
| Simple | A small deterministic single-enemy smoke/debug encounter |
| Overgrowth easy | First-three-fights sample including solo enemies and three slimes |
| Overgrowth hard v1 | Deliberately partial pool: Mawler, two Nibbits, or Shrinker Beetle plus Fuzzy Wurm Crawler |

The slime encounter contains one random medium, one Leaf Slime (S) and one Twig
Slime (S). Named inspection factories share seeded realization with training.
Different actions can naturally produce different later trajectories.
[Hard-pool detail](OVERGROWTH_HARD_V1.md) and [card detail](IRONCLAD_CARDS.md)
retain content evidence and exclusions.

## Structured observation and encoding

`CombatEnv.get_observation()` returns the inspectable structured state.
`ObservationEncoder` turns that state into fixed-width numeric inputs and
action indices. Keep the layers separate; do not make debugging depend on an
opaque tensor.

Observations include player/card/pile state, stable enemy slots and public combat
intents. The combat prototype's `behavior_state` describes possible behavior
branches; it does not expose a sampled future move sequence. A field does not
automatically qualify for a deployed full-game public observation: classify it
against player-visible information and observable history first.

Enemy, card, status and move maps determine encoder layout. Derive widths and
capacities from the current encoder rather than copying numeric constants into
another consumer. Checkpoints must match the recorded representation.
The experimental `card_records_v1` kernel uses bounded semantic records and
learned embeddings; it is not yet integrated into the environment/trainer or
checkpoint path. See [card representation](CARD_REPRESENTATION.md).

## Actions and rewards

Readable actions are `("play", hand_index)`,
`("play", hand_index, target_index)` and `("end_turn",)`.
The fixed discrete representation uses authoritative legal-action masking.
Non-targeted cards have one canonical action in multi-enemy encounters.

`game.simulation.action_features` derives shared tactical summaries and
candidate features from structured observations and actions. Neural policies use
these features; do not duplicate game legality in an encoder or chooser.
Non-targeted actions have zeroed target-specific features.

Combat reward is +1 for victory, -1 for defeat, minus scaled normalized HP loss,
with configurable incoming-damage-reduction shaping. Full-game utility is complete
run victory probability; this combat-local shaping does not redefine it.

## Policies, training and analysis

| Area | Implementation |
| --- | --- |
| Baselines | Random, heuristic and tabular Q-learning |
| Value-based neural | DQN, Double DQN and Dueling Double DQN |
| Policy gradient | Masked PPO with batched rollout collection |
| Architectures | Action-conditioned scoring by default; flat compatibility paths and opt-in shared-enemy models |
| Shared-enemy representation | Shared enemy encoder, living-enemy pooling and target-conditioned scores; candidate scores respect slot permutations |
| Workers/devices | Explicit PPO environment workers and sweep trial workers; shared CPU/CUDA/MPS selection |
| Persistence | Resolved configuration, versioned checkpoint/run metadata and optional profiles |
| Analysis | Traces, tactical findings, fixed-seed benchmarks and bounded oracle/regret searches |

PPO samples actions on CPU to avoid the recorded MPS masked-action issue.
DQN-family optimization defaults to every four environment steps. DQN and Double
DQN restore the best evaluation checkpoint before final evaluation by default.
Training omits full trajectories unless explicitly requested. Profiling and
process concurrency have costs; measure them before changing defaults.

The exact oracle is a seeded hindsight diagnostic. It tracks full RNG-aware
state and reports `proven_optimal` separately from a bounded best-found result.
Information-aware regret samples uncertainty consistent with visible state; it
is not a full POMDP proof. Keep privileged search evidence out of live policy inputs.

[Experiment workflows](EXPERIMENT_WORKFLOWS.md) is the authoritative usage guide
for configuration, output folders, checkpoints, sweep storage, profiling, device
settings, trace inspection and regret analysis. [Agent flow](AGENT_FLOW.md),
[fixed-seed benchmarks](BENCHMARKS.md) and [benchmark suite](BENCHMARK_SUITE.md)
provide deeper explanations.

## Editing and validation

Observation changes affect the encoder, shared action features, heuristics,
demo formatting and relevant tests. Action changes affect
`game/simulation/actions.py`, core legality, encoder mapping and masks.
Check consumers that actually use changed fields; do not recreate a second API.

Run focused cases that would fail on the old defect or distinguish the intended
behavior. For rules/encoding changes cover stable slots, determinism, legal masks
and affected boundaries. Use the proportionate integration/review policy in
[AGENTS.md](../AGENTS.md); documentation edits do not require a simulator run.

Internal imports use canonical subpackages such as `game.simulation.core`,
`game.agents.ppo` and `game.analysis.bruteforce`. The symbol-level `game` API
remains stable; flat module aliases and root CLI wrappers are intentionally absent.
Maintain Python 3.10+ compatibility.

For architectural rationale read [current decisions](../DECISIONS.md); for
priorities read [roadmap](../ROADMAP.md). Completed phase plans and profile
filesystem investigations are not prerequisites for ordinary combat work.
