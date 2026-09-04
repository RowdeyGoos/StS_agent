# StS Agent

Research project for a functional, eventually near-optimal Slay the Spire 2
agent. The repository currently contains complementary executable
foundations: a compact combat simulator for reinforcement-learning research,
an experimental deterministic reduced-run headless environment, and an
authenticated live-game bridge at the bounded `R0i` integration milestone.
The headless progression rules are structural fixtures, not verified full-game
rules. The live bridge has verified standalone rest-site completion; multi-step
event completion, explicit map entry and a complete batched room handoff remain
unaccepted live. Elite continuation is implemented and independently fixture-tested
by the host runner; it remains unobserved live.
Explicit fresh reward entry has passed a bounded live campaign.

Requires Python 3.10+.

Project and contributor documentation:

- [AGENTS.md](AGENTS.md): working guide and repo invariants
- [DECISIONS.md](DECISIONS.md): why key architecture and training choices were made
- [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md): current technical state of the simulator
- [docs/LONG_TERM_ARCHITECTURE_ROADMAP.md](docs/LONG_TERM_ARCHITECTURE_ROADMAP.md): strategic architecture and phased plan for a full-game near-optimal agent
- [docs/PHASE_0_TARGET_CHARTER.md](docs/PHASE_0_TARGET_CHARTER.md): accepted initial scope, information rules, objective, and evaluation gates
- [docs/PHASE_0_PROFILE_FIXTURE_PLAN.md](docs/PHASE_0_PROFILE_FIXTURE_PLAN.md): privacy-safe dedicated profile, reset, and evidence design
- [docs/PHASE_0_PROFILE_METADATA_DISCOVERY_REQUEST.md](docs/PHASE_0_PROFILE_METADATA_DISCOVERY_REQUEST.md): preserved hash-bound scope for the approved metadata-only dedicated-profile lookup
- [docs/research/PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md](docs/research/PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md): sanitized result and limits of the approved shallow profile lookup
- [docs/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_REQUEST.md](docs/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_REQUEST.md): preserved approved fixed-allowlist check of the current shallow state against the predicted backup-sidecar pair
- [docs/research/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md](docs/research/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md): sanitized D1B current-projection result and limits
- [docs/research/PHASE_0_PROFILE_BACKUP_SIDECAR_RESULT_REVIEW.md](docs/research/PHASE_0_PROFILE_BACKUP_SIDECAR_RESULT_REVIEW.md): independent hash-bound review of the D1B execution result
- [docs/PHASE_0_PROFILE_RECOVERY_UNIT_METADATA_REQUEST.md](docs/PHASE_0_PROFILE_RECOVERY_UNIT_METADATA_REQUEST.md): preserved reviewed D1C metadata-only alternative, deliberately skipped and never executed
- [docs/research/PHASE_0_PROFILE_RECOVERY_UNIT_SCOPE_REVIEW.md](docs/research/PHASE_0_PROFILE_RECOVERY_UNIT_SCOPE_REVIEW.md): independent hash-bound review of the preserved D1C alternative
- [docs/PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md](docs/PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md): exact frozen two-sample byte-fingerprint scope with a mandatory fail-closed metadata preflight; no corrected invocation is currently authorized
- [docs/research/PHASE_0_PROFILE_BASELINE_HASH_SCOPE_REVIEW.md](docs/research/PHASE_0_PROFILE_BASELINE_HASH_SCOPE_REVIEW.md): independent exact-hash scope, privacy, and claim-boundary review of the fingerprint request
- [docs/research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md](docs/research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md): sanitized fail-closed first invocation, runner path-binding defect, and corrected-rerun gate
- [docs/research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_REVIEW.md](docs/research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_REVIEW.md): independent hash-bound review of attempt 1 and its fresh-approval boundary
- [docs/research/PHASE_0_PROFILE_BASELINE_HASH_CORRECTED_RUNNER_SYNTHETIC_VALIDATION.md](docs/research/PHASE_0_PROFILE_BASELINE_HASH_CORRECTED_RUNNER_SYNTHETIC_VALIDATION.md): disposable validation of the corrected runner without real-profile access
- [docs/research/PHASE_0_PROFILE_METADATA_RESULT_REVIEW.md](docs/research/PHASE_0_PROFILE_METADATA_RESULT_REVIEW.md): historical independent hash-bound review of the D1 result and D1B scope
- [docs/PHASE_1_INTEGRATION_SPIKE.md](docs/PHASE_1_INTEGRATION_SPIKE.md): preregistration and evidence plan for choosing the live bridge and fast backend
- [docs/PHASE_1_CURRENT_STATUS.md](docs/PHASE_1_CURRENT_STATUS.md): living account of demonstrated bridge progress, current limitations, and the next bounded target
- [docs/PHASE_1_ACTOR_READY_EXECUTION_PLAN.md](docs/PHASE_1_ACTOR_READY_EXECUTION_PLAN.md): active elite-continuation and actor-ready headless packet graph
- [docs/research/PHASE_1_ACTOR_READY_ACCEPTANCE.md](docs/research/PHASE_1_ACTOR_READY_ACCEPTANCE.md): active integration and evidence ledger for that graph
- [docs/research/PHASE_1_HEADLESS_ENCODING_SCHEMA.json](docs/research/PHASE_1_HEADLESS_ENCODING_SCHEMA.json): frozen public feature schema, candidate mapping and normalization for the separate headless actor representation
- [docs/PHASE_1_NEXT_INCREMENT_PLAN.md](docs/PHASE_1_NEXT_INCREMENT_PLAN.md): completed predecessor increment for reliable room composition, headless experiment tooling, and narrow conformance preparation; reviewed results are recorded in its acceptance ledger
- [docs/PHASE_1_STATIC_AUDIT_SYNTHESIS.md](docs/PHASE_1_STATIC_AUDIT_SYNTHESIS.md): preserved pre-implementation candidate shortlist, safety gaps, and ordered experiment gates
- [docs/PHASE_1_RESTRICTED_BRIDGE_DESIGN.md](docs/PHASE_1_RESTRICTED_BRIDGE_DESIGN.md): preserved initial read-only bridge boundary, staged control design, and gates
- [bridge/Sts2AgentBridge/README.md](bridge/Sts2AgentBridge/README.md): implemented `R0i` bridge boundary, contracts, controllers, and reproducible build/package commands
- [docs/research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md](docs/research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md): preserved initial repository evidence plus detailed `R0a` and `R0b` live results
- [docs/PHASE_1_R0A_LIVE_CAMPAIGN_REQUEST.md](docs/PHASE_1_R0A_LIVE_CAMPAIGN_REQUEST.md): preserved exact authorization for the completed first live smoke; not standing authorization for another campaign
- [docs/MULTI_AGENT_EXECUTION.md](docs/MULTI_AGENT_EXECUTION.md): coordination, ownership, review, and user-update model for parallel development
- [manifests/game-builds/README.md](manifests/game-builds/README.md): sanitized immutable identities for pinned game installations
- [docs/AGENT_FLOW.md](docs/AGENT_FLOW.md): visual walkthrough of observation encoding and Double DQN action scoring
- [docs/EXPERIMENT_WORKFLOWS.md](docs/EXPERIMENT_WORKFLOWS.md): practical training, profiling, sweep, trace, and oracle workflows
- [docs/BENCHMARKS.md](docs/BENCHMARKS.md): deterministic multi-policy benchmark workflow and JSON format
- [docs/BENCHMARK_SUITE.md](docs/BENCHMARK_SUITE.md): resumable controlled full-system campaign
- [docs/OVERGROWTH_HARD_V1.md](docs/OVERGROWTH_HARD_V1.md): partial hard-pool contents, Mawler behavior, and content sources
- [docs/IRONCLAD_CARDS.md](docs/IRONCLAD_CARDS.md): supported sequencing cards and source data
- [docs/CARD_REPRESENTATION.md](docs/CARD_REPRESENTATION.md): experimental fixed-capacity semantic card records and learned encoder
- [ROADMAP.md](ROADMAP.md): current priorities and likely next steps

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .
```

If you only want the pure-Python simulator without optional RL tooling, `pip install -e .` is enough. Installing `requirements.txt` enables the Gymnasium wrapper, neural training with PyTorch, and Optuna-based sweeps.

## Reduced headless experiments

The reduced backend has a separate, dependency-light experiment command:

```bash
sts-headless --help
sts-headless run --config configs/headless_smoke.json --output-root runs/headless-smoke
sts-headless benchmark --config configs/headless_smoke.json --output-root runs/headless-benchmark
sts-headless validate --output-root runs/headless-smoke --manifest-sha256 "<reported-manifest-sha256>"
```

Use a new output directory for each invocation; existing paths are rejected.
`run` requires one repetition; `benchmark` uses the repetition count in the
configuration. Keep the printed manifest hash separately for validation.
Artifacts bind declared scenario/settings/seeds and retain received trajectories,
pending episodes and unstarted repetitions after cancellation. They do not prove
target-game fidelity or independently authenticate producer seed declarations.
The smoke config deliberately stops at a small transition budget; it is not a
training run. Help and pure headless use do not import Torch or Gymnasium.
The current CLI input hardening and cancellation tests target POSIX systems
(macOS/Linux); Windows operation has not been validated.

## Run

```bash
sts-demo
sts-train --policy compare --episodes 500 --eval-episodes 100
sts-train --policy dqn --episodes 1000 --eval-interval 100 --batch-size 64 --dqn-architecture action_feature
sts-train --policy double_dqn --episodes 1000 --eval-interval 100 --batch-size 64 --dqn-architecture action_feature
sts-train --policy dueling_double_dqn --episodes 1000 --eval-interval 100 --batch-size 64 --dqn-architecture action_feature
sts-train --policy masked_ppo --episodes 1000 --num-envs 64 --env-workers 4 --device cpu --rollout-steps 2048 --ppo-epochs 4 --ppo-policy-architecture action_feature
sts-train --config configs/masked_ppo_shared_enemy_overgrowth.json
sts-train --config configs/double_dqn_shared_enemy_overgrowth.json
sts-train --policy double_dqn --deck ironclad_sequencing --episodes 1500
sts-train --policy double_dqn --episodes 1500 --train-frequency 4 --batch-size 128 --eval-interval 0
sts-sweep --policy double_dqn --trials 30 --episodes 750 --train-seeds 3 --evaluation-episodes 50 --sampler tpe --json-out sweeps/double_dqn.json
sts-sweep --config configs/masked_ppo_sweep_overgrowth.json
sts-sweep --config configs/masked_ppo_sweep_overgrowth.json --trial-workers 2
sts-train --policy q_learning --episodes 1000 --save-agent checkpoints/q_learning_agent.json
sts-train --policy double_dqn --episodes 1500 --save-agent checkpoints/double_dqn_agent.pt
sts-train --policy dueling_double_dqn --episodes 1500 --save-agent checkpoints/dueling_double_dqn_agent.pt
sts-train --policy masked_ppo --episodes 1500 --save-agent checkpoints/masked_ppo_agent.pt
sts-train --config configs/double_dqn_overgrowth.json
sts-train --config configs/masked_ppo_overgrowth.json
sts-train --config configs/masked_ppo_overgrowth.json --profile-training --episodes 500 --eval-interval 0 --eval-episodes 10
sts-analyze-training runs/masked-ppo-overgrowth/example-run
sts-train --policy heuristic --encounter-set overgrowth_easy --episodes 200
sts-train --policy heuristic --encounter-set overgrowth_hard_v1 --episodes 200
sts-train --policy double_dqn --encounter-set overgrowth_easy --episodes 1500 --eval-interval 100
sts-benchmark --encounter nibbit --encounter slimes --deck ironclad_sequencing --episodes 100 --seed 1000 --json-out benchmarks/fixed-seeds.json
sts-benchmark-suite --dry-run
sts-benchmark-suite
sts-benchmark-suite --mini --output-dir benchmarks/suites/smoke
sts-watch --policy heuristic --encounter overgrowth_easy --deck ironclad_sequencing --seed 7
sts-watch --policy heuristic --encounter mawler --seed 7
sts-watch --policy double_dqn --agent-path checkpoints/double_dqn_agent.pt --encounter slimes --seed 7 --log-file logs/double_dqn_trace.json
sts-watch --policy dueling_double_dqn --agent-path checkpoints/dueling_double_dqn_agent.pt --encounter nibbit --seed 7 --log-file logs/dueling_double_dqn_trace.json
sts-watch --policy masked_ppo --agent-path checkpoints/masked_ppo_agent.pt --encounter fuzzy_wurm_crawler --seed 7 --log-file logs/masked_ppo_trace.json
sts-analyze-trace logs/double_dqn_trace.json --max-findings 10
sts-oracle --encounter simple --seed 7
sts-oracle --encounter slimes --deck ironclad_sequencing --seed 7 --time-limit-seconds 60 --json-out logs/slimes_seed_7_oracle.json
sts-oracle --encounter overgrowth_easy --seed 7 --agent-path checkpoints/double_dqn_agent.pt --time-limit-seconds 60
sts-oracle --encounter slimes --seed 7 --agent-path runs/example/run-id --information-aware-regret --information-samples 16
```

Useful options:

- `sts-train --policy random --episodes 1000`
- `sts-train --policy heuristic --episodes 1000`
- `sts-train --policy q_learning --episodes 2000 --eval-interval 200`
- `sts-train --policy dqn --episodes 2000 --eval-interval 100 --dqn-learning-rate 1e-3 --hidden-sizes 128,128 --dqn-architecture action_feature`
- `sts-train --policy double_dqn --episodes 2000 --eval-interval 100 --dqn-learning-rate 1e-3 --hidden-sizes 128,128 --dqn-architecture action_feature`
- `sts-train --policy dueling_double_dqn --episodes 2000 --eval-interval 100 --dqn-learning-rate 1e-3 --hidden-sizes 128,128 --dqn-architecture action_feature`
- `sts-train --policy masked_ppo --episodes 2000 --ppo-learning-rate 3e-4 --num-envs 8 --rollout-steps 512 --ppo-epochs 4 --ppo-policy-architecture action_feature`
- `sts-train --policy double_dqn --episodes 2000 --batch-size 128 --train-frequency 4 --eval-interval 0`
- `sts-train --policy double_dqn --incoming-damage-shaping-scale 0.75 --discount 0.999`
- `sts-train --encounter-set overgrowth_easy --policy compare --episodes 1000`
- `sts-train --encounter-set overgrowth_hard_v1 --policy compare --episodes 1000`
- `sts-benchmark --encounter mawler --encounter nibbits --episodes 100 --seed 1000`
- `sts-sweep --policy masked_ppo --trials 20 --episodes 1000 --train-seeds 2 --evaluation-episodes 40`
- `sts-sweep --policy q_learning --trials 15 --episodes 500 --train-seeds 3 --sampler random`
- `sts-watch --policy q_learning --agent-path checkpoints/q_learning_agent.json --seed 11 --log-file logs/q_learning_trace.json`
- `sts-analyze-trace logs/masked_ppo_trace.json --json-out logs/masked_ppo_analysis.json`

Evaluation summaries now retain the aggregate metrics and add deterministic
per-encounter rows plus mean damage taken. `--policy compare` uses the same
held-out seed range for random, heuristic, Q-learning, DQN, and Double DQN final
evaluation. Use `sts-benchmark` when comparing built-ins and saved checkpoints
over an explicit grid of fixed encounters and seeds.

The canonical starter deck remains the default. Training, sweeps, watch, oracle,
and benchmark commands accept `--deck starter|ironclad_sequencing`; the resolved
name is recorded in run, checkpoint, trace, oracle, sweep, and benchmark
provenance. A non-canonical ten-card deck with Pommel Strike, Shrug It Off, Iron
Wave, and Body Slam is also available through the public Python API:

```python
from game import CombatEnv, create_ironclad_sequencing_deck

env = CombatEnv(deck_factory=create_ironclad_sequencing_deck)
observation = env.reset(seed=7)
```

## Training configuration files

`sts-train` accepts JSON configuration files whose keys use the snake_case form
of the CLI argument names. The included Double DQN example can be run directly:

```bash
sts-train --config configs/double_dqn_overgrowth.json
```

Explicit CLI arguments take precedence over values in the file, which makes
small variations easy without duplicating a complete setup:

```bash
sts-train --config configs/double_dqn_overgrowth.json --seed 19 --episodes 2000
```

Every run prints its fully resolved configuration by default. Use
`--resolved-config-out path.json` to write it explicitly, or `--no-print-config`
to suppress the terminal output. `hidden_sizes` may be a JSON integer array:

```json
{
  "policy": "double_dqn",
  "encounter_set": "overgrowth_easy",
  "episodes": 1500,
  "hidden_sizes": [128, 128],
  "incoming_damage_shaping_scale": 0.0
}
```

The preferred output setting is `output_dir`. Each completed training run gets a
unique timestamp/policy/seed folder containing stable artifact names:

```text
runs/double-dqn-overgrowth/
└── 20260825T153000123456Z-double_dqn-seed-7/
    ├── checkpoint.pt
    ├── config.json
    ├── run.json
    └── profile.json  # only when --profile-training is enabled
```

`config.json` is the reusable resolved setup. `run.json` records the checkpoint
format version, timestamps, duration, completed episode/environment/optimizer
steps, best-checkpoint restoration, actual device, Python and Torch versions,
platform, Git revision and dirty flag, and compact training/evaluation summaries.
It does not include replay data or episode trajectories.

`--profile-training` adds synchronized semantic PPO timings for rollout batch
preparation, policy inference, environment stepping, observation encoding,
bootstrap inference, GAE/tensorization, gradient updates, evaluation, and
checkpoint work. The terminal summary and optional `profile.json` also report
process CPU usage in average core equivalents, logical CPU capacity, peak RSS,
Torch/device details, and available accelerator-memory metrics. Profiling adds
some synchronization overhead and should be used for diagnostic runs. Inspect a
saved report later, or compare several reports, with:

```bash
sts-analyze-training runs/example/run-id
sts-analyze-training runs/baseline/run-id runs/tuned/run-id
```

PyTorch does not expose reliable portable average MPS utilization, so the report
points macOS users to Activity Monitor's GPU History when accelerator saturation
must be confirmed. CUDA users can pair it with `nvidia-smi`.

Inspection commands accept either the checkpoint itself or its run directory:

```bash
sts-watch --policy double_dqn --agent-path runs/example/run-id
sts-oracle --encounter slimes --seed 7 --agent-path runs/example/run-id
```

The older `save_agent` file setting remains supported. For example,
`checkpoints/agent.pt` produces both
`checkpoints/agent.config.json` and `checkpoints/agent.run.json`. The config
sidecar is itself a valid input to `--config`, while the run sidecar is intended
for inspection and experiment comparison.

## Sweep configuration files

`sts-sweep` accepts the same config-first, explicit-CLI-override workflow:

```bash
sts-sweep --config configs/masked_ppo_sweep_overgrowth.json
sts-sweep --config configs/masked_ppo_sweep_overgrowth.json --trials 5 --episodes 500
```

Top-level keys configure the study and fixed training setup. The optional
`search_space` object customizes PPO hyperparameters. A scalar fixes a value;
categorical, integer, and floating ranges use these forms:

```json
{
  "rollout_steps": {"type": "categorical", "choices": [2048, 4096]},
  "learning_rate": {"type": "float", "low": 0.0001, "high": 0.0008, "log": true},
  "ppo_epochs": {"type": "int", "low": 2, "high": 4}
}
```

Custom entries override the built-in PPO search ranges; omitted parameters keep
their built-in ranges. The resolved configuration expands the complete effective
space and is embedded in the sweep summary. Use `--resolved-config-out` to save
it separately or `--no-print-config` to suppress terminal output.

Sweep trials can run concurrently in independent spawned processes. Set
`trial_workers` and give the workers shared Optuna storage. A local journal is
the recommended single-machine setup:

```json
{
  "trials": 30,
  "trial_workers": 2,
  "study_name": "masked_ppo_overgrowth",
  "journal_file": "sweeps/masked_ppo_overgrowth.journal"
}
```

`trials` remains the total number of new trials for the command, not the number
per worker. The journal is persistent: rerunning the same study name and journal
resumes the study and adds the requested new trials. Use a new study name or
journal path when starting an unrelated search space. `--storage` remains
available for a shared Optuna database and is mutually exclusive with
`--journal-file`.

`trial_workers` parallelizes complete model-training trials; PPO `env_workers`
parallelizes simulator environments inside each trial. Their resource use
multiplies, so start with two trial workers on the current 18-logical-CPU Mac and
benchmark before increasing it. Concurrent TPE runs are reproducible at the
configuration/seed level, but scheduling can change the order in which completed
trials inform later suggestions.

Notes:

- `q_learning`, DQN-family agents, and `masked_ppo` now use separate default learning rates.
- The DQN family currently includes `dqn`, `double_dqn`, and `dueling_double_dqn`, with `action_feature` as the default training architecture. All three also support opt-in `shared_enemy`; use `configs/double_dqn_shared_enemy_overgrowth.json` for a direct run.
- The policy-gradient family currently includes `masked_ppo`, with `action_feature` as the default training architecture. The opt-in `shared_enemy` architecture is available in both neural families: it applies the same learned encoder to every enemy, mean-pools living-enemy context, and scores a targeted action using that target's embedding. It excludes `target_slot_fraction`, making target scores equivariant to enemy-slot reordering. The PPO and DQN implementations are deliberately local to their families so existing state dictionaries remain loadable; shared-enemy checkpoints must match the recorded encoder layout.
- Masked PPO supports batched rollout collection with `--num-envs`. `--rollout-steps` is the total number of transitions across all environments per update; `--num-envs 1` preserves serial collection.
- CPU PPO can use `--env-workers N` to shard simulator slots across persistent processes. Workers communicate through shared numeric arrays; use it for longer runs where process startup can amortize.
- Neural training automatically selects CUDA, then Apple Metal (`mps`), then CPU. Use `--device cpu`, `--device cuda`, or `--device mps` to override it explicitly.
- PPO policy inference stays on the selected neural device, while stochastic action sampling uses CPU multinomial to avoid an Apple MPS bug that can select masked zero-probability actions.
- DQN and Double DQN restore the best evaluation checkpoint before the final evaluation by default.
- `--save-agent` stores trained q_learning, DQN-family, and PPO agents for later inspection.
- `--config` loads a JSON training setup; explicit CLI options override file values.
- `--output-dir` creates one self-contained, non-overwriting directory per run; `--save-agent` remains the legacy file-oriented alternative.
- Reward shaping is configurable with `--hp-loss-penalty-scale` and `--incoming-damage-shaping-scale`.
- DQN-family training now optimizes every 4 environment steps by default, which is much faster than updating on every single step in this Python-heavy environment.
- Neural rollout collection reuses legal-action results, encoder-lifetime schemas, observation-wide tactical context, and identical card/target feature rows.
- `sts-train` environments do not record full per-step trajectories by default; use `--record-trajectories` if you explicitly need training-time episode histories.
- `--eval-interval 0` disables checkpoint evaluations and is the quickest way to speed up long exploratory runs.
- `--learning-rate` still works as a shared override when you want the same value everywhere.
- `--encounter-set overgrowth_easy` samples from the first-three-fights pool in Overgrowth, including solo enemies and the 3-slime pack.
- `--encounter-set overgrowth_hard_v1` samples a deliberately partial hard benchmark: Mawler, two Nibbits, or Shrinker Beetle plus Fuzzy Wurm Crawler.
- The Slimes encounter now always contains one random medium, one Leaf Slime (S), and one Twig Slime (S).
- Enemy intents represent multi-hit attacks as per-hit `attack_damage` plus `attack_count`; projections, block, and status rounding resolve each hit separately.
- The optional sequencing deck adds four base Ironclad cards without changing the default starter deck or discrete action-space size.
- Multi-enemy encounters use targeted play actions under the hood, but the fixed discrete action encoder and legal-action mask handle that automatically for RL agents.
- `sts-watch` runs one traced combat with either a built-in policy or a saved trained agent and writes richer JSON logs, including encounter name, seed, pre-action legal actions, and masks.
- `sts-watch --encounter` and `sts-oracle --encounter` accept `simple`, the sampled `overgrowth_easy` and `overgrowth_hard_v1` pools, and the fixed `nibbit`, `slimes`, `shrinker_beetle`, `fuzzy_wurm_crawler`, `mawler`, `nibbits`, and `shrinker_fuzzy` matchups. `sts-watch --encounter-set` remains a deprecated argument alias.
- `sts-benchmark` accepts fixed matchups only, always includes random and heuristic policies, and can add labeled saved checkpoints with repeated `--agent LABEL=PATH` options. Format-v2 JSON records the required named deck; version 1 is interpreted as the starter deck.
- `game.simulation.card_records` and `game.agents.card_encoder` provide an experimental `card_records_v1` kernel with fixed capacities, semantic records, exact pile counts, and shared learned embeddings. It is programmatic only and is not yet wired into environments, policies, trainers, or checkpoints.
- `sts-benchmark-suite` runs a resumable campaign across every policy architecture and both named decks. Its primary ranking uses equal transition budgets in up to three parallel processes; isolated equal-time finalist runs are reported separately. The balanced campaign takes roughly 4–6 hours on the current CPU host.
- Matching encounter, seed, player/deck settings, and action sequence now yields the same seeded combat realization in both tools. Different policy actions can naturally produce a different later state trajectory.
- `sts-analyze-trace` reads a saved trace and flags high-confidence tactical mistakes such as missed lethal, avoidable incoming damage, wasted dead cards, bad target choice, and premature end turns.
- `sts-sweep` runs Optuna-based hyperparameter sweeps, averages each trial over multiple train seeds, supports process-parallel trials through shared journal/database storage, and can save the best-trial summary as JSON.
- PPO sweeps accept `--config`; `configs/masked_ppo_sweep_overgrowth.json` records both fixed study settings and the complete custom search space.
- `sts-oracle` searches the complete seeded combat state, including pile order and RNG state, for an oracle line. It optimizes victory first, then remaining player HP, remaining enemy HP, and action count.
- The exact search uses alias-preserving fast state clones, cached card-state keys, equivalent-action elimination, and an optimistic damage/action lower bound for earlier proofs. Exact search is still exponential in the worst case, so keep node/time limits for large encounters.
- Oracle output always includes `proven_optimal`. Step, node, or time limits can return the best line found so far without incorrectly labeling it optimal. Fixed Overgrowth encounters are available alongside the seed-sampled `overgrowth_easy` pool.
- Pass `--agent-path` to `sts-oracle` to replay a saved agent on the identical encounter and seed and report HP, step, reward, and matching-action-prefix differences.
- Saved-agent comparisons also run per-decision oracle regret analysis by default. Every legal action is solved from each state the agent actually visited, tied optimal actions are accepted, and ranked weak points show whether the decisive loss was the winner, player HP, enemy HP, or action count. Use `--no-oracle-regret` for the faster outcome-only comparison.
- Control regret-search cost with `--regret-max-steps`, `--regret-max-nodes-per-action`, and `--regret-time-limit-per-action`. JSON output records every counterfactual line and whether each conclusion was proven or only best-found within those limits.
- The exact oracle is a seeded hindsight oracle: it knows hidden pile order and future RNG. Add `--information-aware-regret` to evaluate each agent decision over common sampled draw orders and future random streams that preserve the visible observation. The report compares expected win rate, HP, enemy HP, and action count, includes 95% win-rate intervals and the frequency with which each action is hindsight-best, and writes `information_aware_regret` to JSON.
- Information-aware analysis is opt-in because its cost scales with decisions × legal actions × `--information-samples`. Tune it with `--information-max-steps`, `--information-max-nodes-per-action`, and `--information-time-limit-per-action`. It is a reproducible Monte Carlo root-action estimate; continuations are solved with hindsight inside each sample, so it is not a full POMDP proof.

## Project layout

- `configs/`: reusable JSON training setups
- `game/simulation/`: combat rules, state, observations, encoding, and encounters
- `game/agents/`: baseline and neural agents plus checkpoint persistence
- `game/training/`: PPO process workers and training profiling
- `game/analysis/`: tracing, rendering, exact search, regret, and uncertainty
- `game/cli/`: packaged command implementations
- `tests/`: matching `simulation`, `agents`, `training`, `analysis`, and `cli` suites

Installing the package exposes `sts-train`, `sts-sweep`, `sts-benchmark`, `sts-benchmark-suite`, `sts-watch`,
`sts-oracle`, `sts-analyze-trace`, `sts-analyze-training`, and `sts-demo`.
These installed commands are the supported CLI surface; the removed root scripts
are intentionally not retained as wrappers. Code should use canonical module
paths such as `game.simulation.core` or `game.agents.ppo`. Stable top-level
symbols such as `from game import CombatEnv` remain available.
