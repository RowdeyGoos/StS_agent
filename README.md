# StS Agent

Research toward a functional Slay the Spire 2 agent, built around two systems:

- An independent headless game engine with content, combat and persistent run rules.
- One live-game bridge with bounded combat, reward, map, shop, rest and event capabilities.

The engine supports all five solo characters at A0–A10 through either Act 1 region,
Hive, Glory and the Architect ending on pinned build 0.107.1, with all content
unlocked. Native comparisons cover selected full campaigns and focused interactions;
this is not a claim of exhaustive equivalence or a complete autonomous agent.
[Current status](docs/STATUS.md) distinguishes implemented, fixture-tested and
live-demonstrated bridge behavior, known failures and implementation gaps.

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

The public adapter and reference choosers are available without optional
dependencies. Only the public decision goes to the chooser; its dispatch binding
stays with the caller:

```python
from game.agent.headless import HeadlessAdapter
from game.agent.policy import choose_action
from game.headless.run.engine import RunEngine

adapter = HeadlessAdapter(RunEngine.ironclad_slice(seed=2))
frame = adapter.observe()
candidate = choose_action(frame.decision)
report = adapter.step(frame.binding, candidate.ref)
next_frame_or_outcome = adapter.observe()
```

This is the first combat/selection/reward/map integration slice, with explicit
[content and decision limits](docs/AGENT_CONTRACT.md#headless-producer).
`observe()` raises `UnsupportedProfile` when that state cannot be represented
completely. A completed game returns `RunOutcome`; stale or invalid selections
return a rejection without mutation. For the full engine, select
`decision_profile="full_run_v2"` and use `game.agent.full_policy.choose_action`;
its [coverage table](docs/AGENT_CONTRACT.md#command-and-pending-surface-coverage)
includes every current engine command family and distinguishes live exclusions.

## Gymnasium environment

Install `python -m pip install -e '.[gym]'` for the optional fixed-space environment:

```python
from game.agent.gym_env import FullRunEnv
from game.agent.full_policy import choose_action

with FullRunEnv(character="defect", first_act="underdocks", ascension=0) as env:
    observation, info = env.reset(seed=2)
    while True:
        decision = env.encoder.decode(observation)
        candidate = choose_action(decision)
        observation, reward, terminated, truncated, info = env.step(
            decision.candidates.index(candidate))
        if terminated or truncated:
            break
```

The full-run action space has 2,048 candidate slots and a legality mask. A slot
selects one of the current decision's legal commands. The lossless public encoding
preserves every candidate and fails explicitly on capacity overflow. Ordinary
transitions and real defeat earn 0; victory after the Architect earns 1. All five
characters, both Act 1 regions and A0–A10 are supported. The demonstration chooser
can lose. The original `StsEnv` remains the 256-slot authored combat/reward/map
slice, ending in truncation with reward 0. See
[encoding, lifecycle and scope](docs/AGENT_ENCODING.md) for masked sampling,
reset options, custom engine factories and failure behavior.

## Recording agent runs

The installed agent command records complete public decisions, chosen actions,
reconciled transitions and actual outcomes without optional dependencies:

```bash
sts-agent-play --output-dir runs/train --split train --seed 30 \
  --episodes 2 --workers 2 --max-decisions 600 --time-limit 120
```

Public trajectories go under `runs/train`; private replay seeds/configuration go
under the separate owner-only `runs/train-private` directory. Interrupted writes
remain `.partial`, and finished artifacts are never overwritten. Worker scheduling
preserves each episode's seed. The command reports actual outcomes and timings;
the demonstration policy can lose. See [execution, data loading and cancellation](docs/AGENT_EXECUTION.md).
`sts-headless-play` remains the direct gameplay command.

## Validation

```bash
python -m compileall game tests
PYTHONPATH=. python -m pytest -q
```

Use focused files under `tests/headless/` during gameplay development. The full
suite also checks the retained bridge wire codec and offline operational fixtures.
Install `'.[dev,gym]'` to include the optional encoding/Gym tests; those tests skip
when their optional dependencies are absent.
Native reference harnesses live under `tools/`; their guides explain build inputs
and evidence boundaries.

## Live integration

Read [current status](docs/STATUS.md) and the
[live development guide](docs/LIVE_DEVELOPMENT.md) before selecting a component
or preparing a live test. The [unified bridge](bridge/Sts2AgentBridge/README.md)
packages all supported capabilities in one mod, with one client and development
checker. The status page separates implemented support, known live failures,
accepted representative coverage and remaining limits. Use the [caller evidence index](docs/EVENT_COVERAGE.md)
to find exact tested branches and the [event contracts](docs/GENERIC_EVENTS.md)
for protocol/effect details. Dated ledgers retain test history and setup assistance.
Milestone 7's assisted campaign traversal is accepted: policy-controlled gameplay
through the ending, with one recorded reload for a bridge correction. Normal-HP
policy strength and exhaustive native coverage remain separate targets. The
shared-v2 producer has also reached the ending in an assisted saved continuation,
and the requested non-training coverage pass is complete. Agent-managed Steam
launch/restart and normal shutdown follow the live guide.

## Package layout

| Location | Purpose |
| --- | --- |
| `game/headless/` | Canonical game rules, content, combat, persistent state and private continuation |
| `game/agent/` | Public contract/adapter, choosers, trajectories, workers, optional encoding and Gymnasium environment |
| `game/cli/` | Direct gameplay (`sts-headless-play`) and public agent execution (`sts-agent-play`) |
| `game/backends/live/r0i_wire.py` | Retained bridge wire fixture codec and identity checks |
| `bridge/Sts2AgentBridge/` | Production bridge, shared capabilities, client and focused checks |
| `tools/`, `tests/`, `manifests/game-builds/` | Native reference harnesses, regression coverage and pinned build identities |

The old `CombatEnv`, RL/search/training/benchmark pipelines, reduced backend,
public fixture contracts and their commands were retired on 2026-09-22. They are
not compatibility APIs. Historical guides and exact source references remain in
the [archive](docs/archive/README.md#retired-simulator-pipelines).
Full-game public observations and fixed encoding now consume the current engine
without duplicating game rules. Public trajectories, data loaders, the installed
agent command and bounded workers deliver HF-46/47.
The [shared public contract, headless producer and bounded native adapter](docs/AGENT_CONTRACT.md)
are implemented, with the controlled shared-policy slice and map dispatch accepted
live. Full headless decision coverage and `FullRunEnv` are implemented in milestone 5;
the live bridge retains its bounded v1 profile and adds the
[shared native v2 producer](docs/AGENT_CONTRACT.md#native-full-run-v2-candidate)
over the existing owners. Milestone 6 completes the initial interface delivery.
Milestone 7 and the representative shared-interface follow-through are complete
under their separate scopes in the [delivery plan](docs/AGENT_ENVIRONMENT.md).

[Documentation index](docs/README.md) · [Roadmap](ROADMAP.md) · [Decisions](DECISIONS.md)
