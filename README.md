# StS Agent

Research toward a functional Slay the Spire 2 agent, built around two systems:

- An independent headless game engine with content, combat and persistent run rules.
- One live-game bridge with bounded combat, reward, map, shop, rest and event capabilities.

The engine supports all five solo characters at A0–A10 through either Act 1 region,
Hive, Glory and the Architect ending on pinned build 0.107.1, with all content
unlocked. Native comparisons cover selected full campaigns and focused interactions;
this is not a claim of exhaustive equivalence or a complete autonomous agent.
[Current status](docs/STATUS.md) distinguishes implemented, fixture-tested and
live-demonstrated bridge behavior.

Requires Python 3.10+. New coding sessions follow [AGENTS.md](AGENTS.md).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

For runtime only, `python -m pip install -e .` is sufficient. The engine and its
CLI use the standard library; no Gymnasium, PyTorch or NumPy dependency is needed.

## Playing and implementing the game

```bash
# Short authored smoke with JSON restoration checked before each command
sts-headless-play --seed 2 --rest-choice smith --verify-restore

# Generated three-act campaigns
sts-headless-play --character defect --route overgrowth-glory --ancient neow --seed 2
sts-headless-play --character silent --route underdocks-glory --ascension 10 --seed 2

# Run directly from a checkout without installing the console command
python -m game.cli.headless_play --help
```

The CLI uses a simple demonstration policy that can lose. The default authored
route ends at `slice_complete`; generated `*-glory` campaigns continue through
the Architect to full-game victory when won. Use `--trace` to print commands and
`--verify-restore` to check continuation before each command.

Game rules live in [`game/headless/`](game/headless/) and run directly through
`CombatEngine` and `RunEngine`. For example:

```python
from game.headless.run.engine import RunEngine

run = RunEngine.campaign(character="defect", seed=2)
actions = run.legal_actions()
run.apply(actions[0])
private_state = run.snapshot()
```

Snapshots contain private game/RNG state and must not be supplied to policies as
public observations. Cards own their effects and upgrade values; explicit catalogs
separate immutable content from mutable instances. Consult the
[engine guide](docs/HEADLESS_ENGINE.md) for rules, character scope, commands,
continuation and native verification limits, and the
[implementation backlog](docs/HEADLESS_FULL_GAME_IMPLEMENTATION.md) for remaining work.

## Validation

```bash
python -m compileall game tests
PYTHONPATH=. python -m pytest -q
```

Use focused files under `tests/headless/` during gameplay development. The full
suite also checks the retained bridge wire codec and offline operational fixtures.
Native reference harnesses live under `tools/`; their guides explain build inputs
and evidence boundaries.

## Live integration

Read [current status](docs/STATUS.md) and the
[live development guide](docs/LIVE_DEVELOPMENT.md) before selecting a component
or preparing a live test. The [unified bridge](bridge/Sts2AgentBridge/README.md)
packages supported capabilities in one mod, with one client and development checker.
Complete autonomous runs remain an open target.

## Package layout

| Location | Purpose |
| --- | --- |
| `game/headless/` | Canonical game rules, content, combat, persistent state and private continuation |
| `game/cli/headless_play.py` | Direct gameplay CLI (`sts-headless-play`) |
| `game/backends/live/r0i_wire.py` | Retained bridge wire fixture codec and identity checks |
| `bridge/Sts2AgentBridge/` | Production bridge, shared capabilities, client and focused checks |
| `tools/`, `tests/`, `manifests/game-builds/` | Native reference harnesses, regression coverage and pinned build identities |

The old `CombatEnv`, RL/search/training/benchmark pipelines, reduced backend,
public fixture contracts and their commands were retired on 2026-09-22. They are
not compatibility APIs. Historical guides and exact source references remain in
the [archive](docs/archive/README.md#retired-simulator-pipelines).
Full-game public observations and subsequent policy/data adapters are future work
over the current engine, tracked as HF-44–47; they must not duplicate game rules.

[Documentation index](docs/README.md) · [Roadmap](ROADMAP.md) · [Decisions](DECISIONS.md)
