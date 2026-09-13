# StS Agent

Research toward a functional, eventually near-optimal Slay the Spire 2 agent.
The repository contains these complementary systems:

- An independent headless game engine for implementing cards, combat and persistent run rules.
- Combat research adapters for RL experiments, traces and exact small-combat search.
- A reduced headless run environment with public decision contracts, datasets and
  a deterministic behavior-cloning smoke. Progression rules are structural fixtures.
- A live-game bridge with bounded combat, reward, map, shop, rest and generic
  event capabilities. Supported event interactions are discovered by shared
  mechanisms, without adding an event-name registration for each caller.

This is not yet a complete autonomous agent or a verified full-game simulator.
[Current status](docs/STATUS.md) distinguishes implemented,
fixture-tested and live-demonstrated behavior, including the successful direct
off-screen transformation-card test.

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

## Implementing the game

Start with [`game/headless/`](game/headless/) and the [engine guide](docs/HEADLESS_ENGINE.md).
Game rules run directly through `CombatEngine` and `RunEngine`, without public
projections, encoders or training. Cards own their effect/upgrade definitions;
content catalogs and mutable instances are separate. The older experiment APIs
consume the same combat engine. Full target-game content and progression remain
unfinished; see the [feature backlog](docs/HEADLESS_FULL_GAME_IMPLEMENTATION.md).

```bash
PYTHONPATH=. python -m pytest -q tests/headless
sts-headless-play --seed 2 --rest-choice smith --verify-restore
sts-headless-play --route overgrowth --path right --seed 2 --rest-choice rest --verify-restore
```

The playable first slice starts Ironclad at Ascension 0, fights Nibbit, collects
rewards, rests or upgrades a card, then fights Overgrowth slimes and collects the
second rewards. It includes Burning Blood and Fire/Block Potions. The map and
reward pools are explicitly restricted; `slice_complete` is not full-game victory.
Use `--rest-choice rest` for the healing path and `--trace` to print every command.
The optional `--route overgrowth` plays four combats with two branches: choose
whether slimes or Fuzzy Wurm comes second, fight the other third, rest/smith, then
choose Mawler, paired Nibbits or the Byrdonis elite. Elite rewards include 35–45
gold and a relic from Strawberry/Pear/Mango, which permanently raises maximum HP
and heals on pickup. `--path right` selects the elite; `left` selects Mawler.
Add `--route overgrowth-act1` for a treasure chest after the third fight, followed
by the fourth fight, an optional shop, a second rest site and Vantom. Opening the
chest grants 42–52 gold; its relic can be taken or skipped. The restricted fruit
pool depletes on offers and falls back to Circlet when exhausted. `--path left` visits the shop; `right` bypasses it. The shop sells
supported cards, a fruit relic and Fire/Block Potions, and removes a chosen deck
card for 75 gold (25 more per prior shop removal). The demo buys one affordable
card and removes a starter if it can afford both; direct commands allow any legal
purchase sequence. Shop choices also support `--verify-restore`.
This route also offers Sword Boomerang, including its four-hit upgrade.
Leaving the boss rewards records `act_complete` for Act 1; it does not declare
full-game victory. The simple demo player can lose on this route. Boss rewards
use a restricted rare-card pool: Impervious, Offering and Fiend Fire.

Without reinstalling the console entry point, run
`PYTHONPATH=. python -m game.cli.headless_play` with the same arguments.

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
checker. The [unified module smoke](docs/evidence/UNIFIED_BRIDGE_SMOKE_2026_09_08.md)
demonstrated representative combat, reward, map, shop, card, item and event paths,
with recorded setup assistance and remaining limits. Generalized transform input
also has focused native fixtures. Complete autonomous runs remain an open target.

## Project layout and documentation

| Location | Purpose |
| --- | --- |
| `game/headless/` | Canonical game rules, content, combat, persistent state and private continuation |
| `game/simulation/` | Combat research compatibility, observations, encoding, shaping and factories |
| `game/agents/`, `game/training/` | Policies, persistence, collectors and training |
| `game/contracts/`, `game/backends/`, `game/data/` | Full-game interfaces, reduced backend and artifacts |
| `game/analysis/`, `game/cli/` | Evaluation, inspection and installed commands |
| `bridge/Sts2AgentBridge/` | One production bridge, shared capability modules and focused checks |
| `configs/`, `tests/`, `manifests/game-builds/` | Experiments, regression coverage and pinned build identities |

Use canonical subpackage imports and installed `sts-*` commands; there are no
flat-module aliases or root CLI wrappers.

[Documentation index](docs/README.md) · [Roadmap](ROADMAP.md) ·
[Decisions](DECISIONS.md) · [Combat context](docs/PROJECT_CONTEXT.md)
