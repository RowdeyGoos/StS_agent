# StS Agent

Research toward a functional, eventually near-optimal Slay the Spire 2 agent.
The repository contains three complementary systems:

- A deterministic combat simulator for RL experiments, traces and exact small-combat search.
- A reduced headless run environment with public decision contracts, datasets and
  a deterministic behavior-cloning smoke. Progression rules are structural fixtures.
- A live-game bridge with bounded combat, reward, map, shop, rest and generic
  event capabilities. Supported event interactions are discovered by shared
  mechanisms, without adding an event-name registration for each caller.

This is not yet a complete autonomous agent or a verified full-game simulator.
[Current status](docs/STATUS.md) distinguishes implemented,
fixture-tested and live-demonstrated behavior, known failures and implementation gaps.

Requires Python 3.10+. New coding sessions follow [AGENTS.md](AGENTS.md).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .
```

For only the pure-Python simulator, `pip install -e .` is sufficient.
`requirements.txt` adds Gymnasium, PyTorch and Optuna.

## Combat experiments

```bash
sts-demo
sts-train --policy compare --episodes 500 --eval-episodes 100
sts-train --config configs/double_dqn_overgrowth.json
sts-train --config configs/masked_ppo_overgrowth.json
sts-watch --policy heuristic --encounter slimes --deck ironclad_sequencing --seed 7
sts-oracle --encounter simple --seed 7
sts-benchmark-suite --dry-run
```

The default deck is `starter`; the optional `ironclad_sequencing` deck adds draw
and block/damage sequencing. Supported policies include random, heuristic,
Q-learning, DQN, Double DQN, Dueling Double DQN and masked PPO. Neural families
default to action-conditioned scoring, with opt-in `shared_enemy` architectures.

JSON configuration uses CLI names in snake_case; explicit CLI arguments override
the file. Prefer `output_dir` for a unique run folder containing the checkpoint,
resolved configuration and run metadata. Saved-agent tools accept a checkpoint
or its run directory. The legacy `save_agent` plus sidecars remains supported.

Use [experiment workflows](docs/EXPERIMENT_WORKFLOWS.md) for configuration,
sweeps, profiling, device choice, tracing and oracle/regret analysis.
[Benchmarks](docs/BENCHMARKS.md) and the [benchmark suite](docs/BENCHMARK_SUITE.md)
describe comparable fixed-seed and controlled-budget evaluations.
Each command's `--help` lists its complete options.

## Reduced headless experiments

```bash
sts-headless --help
sts-headless run --config configs/headless_smoke.json --output-root runs/headless-smoke
sts-headless benchmark --config configs/headless_smoke.json --output-root runs/headless-benchmark
sts-headless validate --output-root runs/headless-smoke --manifest-sha256 "<reported-manifest-sha256>"
```

Use a new output directory for every invocation and keep the printed manifest
hash separately. `run` requires one repetition; `benchmark` uses the configured
count. The smoke config has a small transition budget and is not a training run.
Help and pure headless commands do not import Torch or Gymnasium. Current CLI
input/cancellation hardening was validated on POSIX systems.

Artifacts preserve declared settings, trajectories and cancellation accounting.
They do not prove target-game fidelity or independently authenticate declared seeds.

The separate programmatic actor path uses `game.agents.headless_encoding`,
`game.data.headless_policy_dataset`, `game.agents.headless_candidate_policy`
and `game.training.headless_behavior_clone`. `train_headless_behavior_clone`
takes separated, manifest-anchored development/held-out sources, an accepted
backend manifest and a `BehaviorCloneConfig`. An optional new `output_root`
publishes a report, CPU checkpoint and completion marker; cancellation does not
publish an accepted artifact. Keep the returned report and logical checkpoint
hashes for `load_behavior_clone_artifact`. This smoke establishes plumbing on
structural data, not strategic strength or a new `sts-train` policy.
[Headless actor guide](docs/HEADLESS_ACTOR.md) links the source, schema and evidence.

## Live integration

Read [current status](docs/STATUS.md) and the
[live development guide](docs/LIVE_DEVELOPMENT.md) before selecting a component
or preparing a live test. The [unified bridge](bridge/Sts2AgentBridge/README.md)
packages all supported capabilities in one mod, with one client and development
checker. The status page separates implemented support, known live failures,
missing features and remaining live tests. Use the [caller evidence index](docs/EVENT_COVERAGE.md)
to find exact tested branches and the [event contracts](docs/GENERIC_EVENTS.md)
for protocol/effect details. Dated ledgers retain test history and setup assistance.
Complete autonomous runs remain an open target.

## Project layout and documentation

| Location | Purpose |
| --- | --- |
| `game/simulation/` | Combat rules, observations, action encoding and factories |
| `game/agents/`, `game/training/` | Policies, persistence, collectors and training |
| `game/contracts/`, `game/backends/`, `game/data/` | Full-game interfaces, reduced backend and artifacts |
| `game/analysis/`, `game/cli/` | Evaluation, inspection and installed commands |
| `bridge/Sts2AgentBridge/` | One production bridge, shared capability modules and focused checks |
| `configs/`, `tests/`, `manifests/game-builds/` | Experiments, regression coverage and pinned build identities |

Use canonical subpackage imports and installed `sts-*` commands; there are no
flat-module aliases or root CLI wrappers.

[Documentation index](docs/README.md) · [Roadmap](ROADMAP.md) ·
[Decisions](DECISIONS.md) · [Combat context](docs/PROJECT_CONTEXT.md)
