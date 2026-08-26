# AGENTS.md

This file is the working guide for coding sessions in this repo.

Use it for:

- where to read first
- what not to break
- how to validate changes
- which docs to update when the project evolves

Do not treat this file as the full project description. For that, follow the reading order below.

## Read This First

When starting a fresh session, read in this order:

1. [README.md](README.md)
2. [DECISIONS.md](DECISIONS.md)
3. [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md)
4. [ROADMAP.md](ROADMAP.md)
5. [game/simulation/core.py](game/simulation/core.py)
6. [game/simulation/encoding.py](game/simulation/encoding.py)
7. [game/cli/train.py](game/cli/train.py)

## Doc Roles

- `README.md`: user-facing overview, setup, and run commands
- `AGENTS.md`: session workflow and repo invariants
- `DECISIONS.md`: why important architecture and training choices were made
- `docs/PROJECT_CONTEXT.md`: current technical state of the simulator
- `ROADMAP.md`: likely next steps and current priorities
- `.codex`: ultra-short bootstrap note for fresh Codex sessions

## Core Working Assumptions

- `CombatEnv` is the main RL-facing environment.
- The structured observation is the source of truth for debugging and tests.
- `ObservationEncoder` is the RL representation layer.
- Multi-enemy combat uses stable enemy slots. Dead enemies stay in the encounter list so target indices and encoded slots do not shift.
- The discrete action space is fixed-size and relies on legal-action masking.
- Reward is intentionally shaped toward winning while preserving player HP.

## Invariants To Preserve

- Keep structured observations and encoded observations conceptually separate.
- Keep randomness explicit and seeded through the environment RNG or objects created from it.
- Avoid global state.
- Keep game state serializable and easy to inspect.
- Preserve compatibility with the simple single-enemy path unless there is a good reason to change it.
- Maintain Python `3.10+` compatibility unless the project requirement is intentionally raised.

## If You Change Observation Or Action Semantics

Observation changes usually require updates to:

- `game/simulation/core.py`
- `game/simulation/encoding.py`
- `game/simulation/action_features.py`
- heuristic logic in `game/agents/baselines.py`
- tests
- demo formatting in `game/cli/demo.py`

Action changes usually require updates to:

- `game/simulation/actions.py`
- `game/simulation/core.py`
- `game/simulation/encoding.py`
- `game/simulation/action_features.py`
- action-mask tests

## File Map

- `game/simulation/`: combat rules, mutable state, observations, encoding, and factories
- `game/agents/`: baselines, DQN-family agents, PPO, devices, and persistence
- `game/training/`: PPO worker infrastructure and semantic profiling
- `game/analysis/`: traces, rendering, brute-force search, regret, and uncertainty
- `game/cli/`: real command-line implementations
- `game/__init__.py`: stable symbol-level public API
- `configs/`: reusable training and sweep configurations
- `tests/simulation/`: combat and encoding coverage
- `tests/agents/`: model architecture and persistence coverage
- `tests/training/`: trainer, profiling, and worker coverage
- `tests/analysis/`: trace and oracle coverage
- `tests/cli/`: command configuration and sweep coverage

Use canonical subpackage paths. Do not reintroduce flat-module aliases or root
CLI wrappers; stale imports and commands should fail visibly instead of creating
a permanent second API surface.

## Common Validation Commands

Setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .
```

Regression checks:

```bash
python3 -m compileall game tests
PYTHONPATH=. python3 -m pytest -q
```

Manual runs:

```bash
sts-demo
sts-train --policy compare --episodes 500 --eval-episodes 100
sts-train --policy heuristic --encounter-set overgrowth_easy --episodes 200
```

## When Editing

- Prefer minimal, explicit changes over clever abstraction.
- Keep the simulator readable as an RL research playground.
- Update docs when core assumptions change.
- Add or update a `DECISIONS.md` entry when you make a meaningful architecture or training-default choice.
- Update `ROADMAP.md` when priorities or likely next steps shift materially.
