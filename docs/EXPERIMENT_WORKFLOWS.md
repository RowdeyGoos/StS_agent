# Experiment Workflows

This guide connects the experiment tooling around the combat simulator. It
focuses on reproducible training, performance diagnosis, architecture
comparisons, and finding decisions where a learned policy is weaker than an
oracle.

## End-To-End Workflow

```text
JSON training config
        │
        ▼
sts-train ──────────────► run directory
                            ├── checkpoint.pt
                            ├── config.json
                            ├── run.json
                            └── profile.json (optional)
                                  │
                 ┌────────────────┼────────────────┐
                 ▼                ▼                ▼
          sts-watch       sts-analyze-training   sts-oracle
                 │                                 │
                 ▼                                 ▼
          episode trace                  seeded oracle/regret
                 │
                 ▼
        sts-analyze-trace
```

Use the trace analyzer to spot obvious tactical mistakes. Use the oracle tools
when the question is whether a particular decision was actually optimal. Use
information-aware regret when the exact seeded oracle benefits from hidden draw
order or future RNG that the policy could not observe.

## Reproducible Training Runs

Training arguments can be stored in strict JSON files:

```bash
sts-train --config configs/masked_ppo_overgrowth.json
```

Resolution order is:

1. built-in defaults
2. values from the JSON config
3. explicit command-line overrides

For example, this changes only the seed and episode count:

```bash
sts-train \
  --config configs/masked_ppo_overgrowth.json \
  --seed 19 \
  --episodes 50000
```

The resolved configuration is printed before training. That complete version,
not only the fields present in the input file, is written to `config.json`.

### Run directories and checkpoint provenance

`output_dir` is the preferred save mechanism. Every run receives a unique
directory:

```text
runs/masked-ppo-overgrowth/
└── 20260825T153000123456Z-masked_ppo-seed-7/
    ├── checkpoint.pt
    ├── config.json
    ├── run.json
    └── profile.json
```

- `checkpoint.pt` contains model/optimizer state and embedded metadata.
- `config.json` is a reusable resolved training configuration.
- `run.json` contains timestamps, duration, environment and optimizer steps,
  evaluation summaries, actual device, Python/Torch versions, platform, Git
  revision, and dirty-worktree state.
- `profile.json` is present only for profiled PPO runs.

Inspection commands accept either `checkpoint.pt` or the containing run
directory. Older file-oriented `--save-agent` checkpoints and their sidecars
remain supported.

Checkpoint metadata records how a model was configured, but it does not contain
replay buffers, PPO rollout samples, or complete training trajectories.

## PPO Collection And Optimization

The important PPO size controls describe different things:

| Setting | Meaning |
| --- | --- |
| `episodes` | Total completed training combats |
| `num_envs` | Concurrent environment slots used for batched policy inference |
| `rollout_steps` | Total transitions collected before one PPO update, across all environments |
| `env_workers` | CPU processes that own and step environment slots |
| `ppo_minibatch_size` | Samples processed by one optimizer step |
| `ppo_epochs` | Passes over each collected rollout |

With `num_envs=64` and `rollout_steps=2048`, an update contains 2,048 total
transitions, not 2,048 transitions from every environment. If work is evenly
distributed, that is roughly 32 transitions per environment per update.

Increasing `num_envs` improves inference batching and sample diversity. It does
not automatically increase the amount of data in an update; increase
`rollout_steps` separately when a larger rollout is desired.

### CPU process parallelism

`CombatEnv` is mostly Python. Python threads cannot execute its CPU-heavy code
in parallel because of the GIL, so `env_workers` uses persistent spawned
processes instead. Workers own environment shards and exchange numeric data
through shared NumPy buffers. Torch inference and optimization stay in the
parent process.

The resource use of these controls multiplies:

```text
parallel sweep trials × environment workers per trial
```

Too many workers can make training slower through CPU oversubscription and
memory-bandwidth contention.

### CPU, CUDA, and Apple MPS

Neural agents support automatic CUDA, Apple MPS, and CPU selection, plus an
explicit `--device` override. MPS is not necessarily faster for this project:
the policy networks are relatively small, inference batches can be small, and
device dispatch/synchronization can cost more than the matrix operations save.
The current CPU-oriented PPO configs specify `device: "cpu"` and use environment
processes to exploit more cores. Benchmark rather than assuming an accelerator
will win.

Policy logits remain on the selected neural device, but stochastic PPO action
sampling uses CPU multinomial. This avoids an observed Apple MPS failure that
could occasionally select a masked zero-probability action. The sampled action
index is moved back to the policy device afterward.

## Shared Enemy PPO Architecture

The original `action_feature` PPO architecture flattened all enemy slots into
the state vector and exposed `target_slot_fraction` to the action scorer. That
allowed the model to distinguish enemies, but also allowed it to learn shortcuts
such as preferring a lower-numbered target.

The opt-in `shared_enemy` architecture uses this flow:

```text
enemy slot 0 ─► shared enemy MLP ─► enemy embedding 0 ─┐
enemy slot 1 ─► shared enemy MLP ─► enemy embedding 1 ─┼─► mean pool ─┐
enemy slot 2 ─► shared enemy MLP ─► enemy embedding 2 ─┘             │
                                                                     ├─► state context
non-enemy observation features ──────────────────────────────────────┘

selected action ─► selected target embedding ─┐
action features without target slot position ─┼─► shared scorer ─► action logit
state context ────────────────────────────────┘
```

Dead and padded enemies are excluded from the pool. Non-target actions receive
a zero target embedding. The environment still uses stable enemy slots and
fixed discrete action indices; only the neural representation changes.

Because the same MLP handles every enemy and raw target position is removed,
swapping two enemy rows and their corresponding action targets swaps their
policy logits. Position alone cannot change which enemy is preferred.

Train it with the A/B config:

```bash
sts-train --config configs/masked_ppo_shared_enemy_overgrowth.json
```

This is a distinct architecture, so existing `action_feature` checkpoints remain
loadable but cannot be converted into a trained `shared_enemy` model. A new run
is required.

## Finding Training Bottlenecks

Profile a representative PPO run:

```bash
sts-train \
  --config configs/masked_ppo_overgrowth.json \
  --profile-training
```

Then inspect or compare reports:

```bash
sts-analyze-training runs/baseline/run-id
sts-analyze-training runs/baseline/run-id runs/tuned/run-id
```

The profiler separates rollout preparation, policy inference, environment
updates, encoding, GAE/tensorization, gradient updates, evaluation, and
checkpoint work. It also reports average CPU core equivalents, logical CPU
capacity, peak RSS, and available Torch/device details.

Typical tuning responses are:

- Gradient updates dominate: increase minibatch size, reduce `ppo_epochs`, or
  collect more rollout data per update.
- Environment stepping dominates: increase `env_workers`, within available CPU
  and memory limits.
- Policy inference dominates: increase `num_envs` so inference batches are
  larger.
- Evaluation dominates: increase `eval_interval` or use `eval_interval=0` for
  exploratory runs.
- Encoding/preparation dominates: profile before changing the observation
  representation; legal-action and action-feature preparation already share
  cached context.

Profiling synchronizes accelerators and adds overhead, so use it for diagnostic
runs rather than every final experiment. PyTorch does not expose reliable,
portable average MPS utilization; Activity Monitor's GPU History is the useful
external check on macOS.

### Feature-preparation optimizations already applied

Policy input preparation was a visible Python bottleneck, so the hot path now:

- caches encoder-lifetime schema names, widths, and counts
- calculates legal actions once and reuses that result for both the action mask
  and action-feature matrix
- prepares observation-wide tactical context once per decision
- reuses semantic action rows for equivalent card/target combinations

These caches contain derived schema or decision-local values, not mutable combat
state. They preserve the structured observation as the debugging source of truth
and keep legality explicit.

## PPO Parameter Sweeps

The reproducible sweep entry point is:

```bash
sts-sweep --config configs/masked_ppo_sweep_overgrowth.json
```

The top level defines fixed study/training settings. `search_space` accepts:

```json
{
  "learning_rate": {
    "type": "float",
    "low": 0.0001,
    "high": 0.0008,
    "log": true
  },
  "ppo_epochs": {
    "type": "int",
    "low": 2,
    "high": 4
  },
  "rollout_steps": {
    "type": "categorical",
    "choices": [2048, 4096]
  },
  "hp_loss_penalty_scale": {
    "type": "float",
    "low": 0.5,
    "high": 3.0
  }
}
```

A scalar fixes a parameter. Custom specifications replace the built-in range
for that parameter, while omitted parameters retain their built-in search
ranges. Console floats are shown with six significant digits for readability;
the exact sampled values remain in Optuna storage and saved JSON.

### Parallel trials

Independent trials can run in spawned processes. On one machine, use a shared
Optuna journal:

```json
{
  "trials": 30,
  "trial_workers": 2,
  "study_name": "masked_ppo_overgrowth",
  "journal_file": "sweeps/masked_ppo_overgrowth.journal"
}
```

`trials` is the global number of new trials, not a per-worker count. Reusing the
same journal and study name resumes the study. Use a new study name or journal
for a materially different search space.

`trial_workers` parallelizes complete training runs. `env_workers` parallelizes
environment simulation inside each run. Benchmark their combination to avoid
oversubscribing the machine.

## Inspecting A Learned Policy

Generate a deterministic one-combat trace:

```bash
sts-watch \
  --policy masked_ppo \
  --agent-path runs/example/run-id \
  --encounter slimes \
  --seed 7 \
  --log-file logs/masked_ppo_trace.json
```

Run the fast heuristic analyzer:

```bash
sts-analyze-trace \
  logs/masked_ppo_trace.json \
  --json-out logs/masked_ppo_analysis.json
```

It flags high-confidence patterns such as missed lethal, avoidable incoming
damage, wasted dead-card plays, poor target choice, and premature end turns.
These findings are useful leads, not proofs of optimality.

`sts-watch` and `sts-oracle` use the same named encounter factory.
Matching encounter, seed, player/deck settings, and actions produce the same
combat realization. Once two policies choose different actions, their later
states can naturally diverge despite sharing the original seed.

## Seeded Brute-Force Oracle

Run the exact seeded search with explicit safety limits:

```bash
sts-oracle \
  --encounter slimes \
  --seed 7 \
  --max-nodes 250000 \
  --time-limit-seconds 60 \
  --json-out logs/slimes_seed_7_oracle.json
```

The search operates on complete simulator states, including ordered card piles,
enemy behavior state, RNG state, and shared-RNG identity. It uses a best-first
frontier and a lexicographic objective:

1. win the combat
2. maximize remaining player HP
3. minimize remaining enemy HP
4. minimize player decisions

Equivalent card actions and already-seen states are removed conservatively.
Optimistic damage/action bounds can prove that no remaining branch beats the
current best victory. Search remains exponential in the worst case.

Always inspect `proven_optimal`. A node, step, or time limit may return a useful
best-found line without proving it globally optimal.

### Agent divergence and per-decision regret

Supply a checkpoint or run directory:

```bash
sts-oracle \
  --encounter slimes \
  --seed 7 \
  --agent-path runs/example/run-id \
  --search-workers 4
```

The tool replays the policy and evaluates every legal committed first action at
each state the policy visited. It reports tied optimal actions, the first proven
divergence, and ranked weak points in win/HP/enemy-HP/action-count terms.

`search_workers` parallelizes independent counterfactual continuations in regret
analysis. It does not split the primary exact search frontier, where workers
would duplicate the large transposition table and reduce pruning efficiency.

Use `--no-oracle-regret` when only the final outcome comparison is needed.

### Hindsight versus information-aware regret

The exact seeded oracle knows the realized hidden draw order and future RNG. It
therefore measures hindsight optimality, which is useful and reproducible but
can attribute impossible foreknowledge to the agent.

Use sampled information-aware analysis when that distinction matters:

```bash
sts-oracle \
  --encounter slimes \
  --seed 7 \
  --agent-path runs/example/run-id \
  --information-aware-regret \
  --information-samples 16 \
  --search-workers 4
```

It preserves the visible observation while sampling unseen draw orders and
future RNG streams. Legal actions are compared on common samples using expected
win rate, player HP, enemy HP, and action count. Reports include Wilson 95%
win-rate intervals and how often each action is hindsight-best.

This is a Monte Carlo root-action estimate, not a complete POMDP solution:
continuations within each sampled world are still solved with hindsight. Its
cost scales approximately with:

```text
visited decisions × legal actions × information samples × search per action
```

Keep samples and per-action limits small while iterating, then increase them for
the few decisions that remain important.

## Recommended Architecture Comparison

For a clean `action_feature` versus `shared_enemy` comparison:

1. Keep encounter, reward, seed set, episode budget, and PPO hyperparameters
   identical.
2. Change only `ppo_policy_architecture` and use separate output directories.
3. Compare multiple training seeds, not one checkpoint.
4. Evaluate both policies on the same held-out encounter/seed list.
5. Compare win rate and remaining HP first.
6. Trace recurring failures and run oracle regret on the same fixed combats.
7. Profile both runs because representation changes can alter optimizer cost.

The slot-permutation regression test guarantees the structural property of the
shared encoder. It does not guarantee that a trained policy will use enemy
intent correctly; trace/oracle analysis is still needed to measure learned
behavior.

## Known Encounter-Fidelity Caveat

The current `build_overgrowth_slimes_encounter` samples two small slime types
independently. This can produce two Leaf Slimes (S) or two Twig Slimes (S).
Current [Overgrowth reference data](https://slaythespire.wiki.gg/wiki/Slay_the_Spire_2%3AOvergrowth)
describes the easy encounter as exactly one Leaf Slime (S), one random medium
slime, and one Twig Slime (S). Until the builder is corrected, training and
oracle results for `slimes` include non-canonical compositions.

The `overgrowth_easy` helper samples one independent encounter from the
four-item early pool. It does not model a complete run's selection of three
unique fights without replacement.
