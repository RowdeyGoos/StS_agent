# StS Agent

Minimal Slay-the-Spire-style combat simulator for reinforcement learning experiments.

Requires Python 3.10+.

Contributor and coding-session docs:

- [AGENTS.md](AGENTS.md): working guide and repo invariants
- [DECISIONS.md](DECISIONS.md): why key architecture and training choices were made
- [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md): current technical state of the simulator
- [ROADMAP.md](ROADMAP.md): current priorities and likely next steps

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .
```

If you only want the pure-Python simulator without optional RL wrappers, `pip install -e .` is enough. Installing `requirements.txt` enables the Gymnasium wrapper and DQN training with PyTorch.

## Run

```bash
python3 main.py
python3 train.py --policy compare --episodes 500 --eval-episodes 100
python3 train.py --policy dqn --episodes 1000 --eval-interval 100 --batch-size 64
python3 train.py --policy double_dqn --episodes 1000 --eval-interval 100 --batch-size 64
python3 train.py --policy heuristic --encounter-set overgrowth_easy --episodes 200
python3 train.py --policy double_dqn --encounter-set overgrowth_easy --episodes 1500 --eval-interval 100
```

Useful options:

- `python3 train.py --policy random --episodes 1000`
- `python3 train.py --policy heuristic --episodes 1000`
- `python3 train.py --policy q_learning --episodes 2000 --eval-interval 200`
- `python3 train.py --policy dqn --episodes 2000 --eval-interval 100 --dqn-learning-rate 1e-3 --hidden-sizes 128,128`
- `python3 train.py --policy double_dqn --episodes 2000 --eval-interval 100 --dqn-learning-rate 1e-3 --hidden-sizes 128,128`
- `python3 train.py --encounter-set overgrowth_easy --policy compare --episodes 1000`

Notes:

- `q_learning` and DQN-family agents now use separate default learning rates.
- DQN and Double DQN restore the best evaluation checkpoint before the final evaluation by default.
- `--learning-rate` still works as a shared override when you want the same value everywhere.
- `--encounter-set overgrowth_easy` samples from the first-three-fights pool in Overgrowth, including solo enemies and the 3-slime pack.
- Multi-enemy encounters use targeted play actions under the hood, but the fixed discrete action encoder and legal-action mask handle that automatically for RL agents.

## Project layout

- `game/`: simulator package
- `main.py`: single-combat demo
- `train.py`: baseline training and evaluation CLI
- `tests/`: basic mechanics and RL interface tests
