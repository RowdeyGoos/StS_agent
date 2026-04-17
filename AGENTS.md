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
5. [game/core.py](game/core.py)
6. [game/encoding.py](game/encoding.py)
7. [train.py](train.py)

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

- `game/core.py`
- `game/encoding.py`
- heuristic logic in `game/baselines.py`
- tests
- demo formatting in `main.py`

Action changes usually require updates to:

- `game/actions.py`
- `game/core.py`
- `game/encoding.py`
- action-mask tests

## File Map

- `game/core.py`: combat loop, observations, reward shaping, terminal logic
- `game/encoding.py`: fixed-width RL observation and action encoding
- `game/enemy.py`: enemy classes, intents, and encounter factories
- `game/card.py`: card definitions and effects
- `game/player.py`: player-side combat state transitions
- `game/deck.py`: draw/discard/exhaust/shuffle behavior
- `game/status.py`: status definitions and damage modifiers
- `game/baselines.py`: random, heuristic, and tabular baselines
- `game/dqn.py`: DQN and Double DQN training
- `game/gym_env.py`: optional Gymnasium wrapper
- `train.py`: CLI for training and evaluation
- `main.py`: readable combat demo
- `tests/`: assert-based regression coverage

## Common Validation Commands

Setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .
```

Smoke checks:

```bash
python3 -m compileall game train.py main.py tests
PYTHONPATH=. python3 tests/test_basic.py
PYTHONPATH=. python3 tests/test_rl.py
PYTHONPATH=. python3 tests/test_training.py
PYTHONPATH=. python3 tests/test_dqn.py
```

Manual runs:

```bash
python3 main.py
python3 train.py --policy compare --episodes 500 --eval-episodes 100
python3 train.py --policy heuristic --encounter-set overgrowth_easy --episodes 200
```

## When Editing

- Prefer minimal, explicit changes over clever abstraction.
- Keep the simulator readable as an RL research playground.
- Update docs when core assumptions change.
- Add or update a `DECISIONS.md` entry when you make a meaningful architecture or training-default choice.
- Update `ROADMAP.md` when priorities or likely next steps shift materially.
