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

If you only want the pure-Python simulator without optional RL tooling, `pip install -e .` is enough. Installing `requirements.txt` enables the Gymnasium wrapper, neural training with PyTorch, and Optuna-based sweeps.

## Run

```bash
python3 main.py
python3 train.py --policy compare --episodes 500 --eval-episodes 100
python3 train.py --policy dqn --episodes 1000 --eval-interval 100 --batch-size 64 --dqn-architecture action_feature
python3 train.py --policy double_dqn --episodes 1000 --eval-interval 100 --batch-size 64 --dqn-architecture action_feature
python3 train.py --policy dueling_double_dqn --episodes 1000 --eval-interval 100 --batch-size 64 --dqn-architecture action_feature
python3 train.py --policy masked_ppo --episodes 1000 --rollout-steps 512 --ppo-epochs 4 --ppo-policy-architecture action_feature
python3 train.py --policy double_dqn --episodes 1500 --train-frequency 4 --batch-size 128 --eval-interval 0
python3 sweep.py --policy double_dqn --trials 30 --episodes 750 --train-seeds 3 --evaluation-episodes 50 --sampler tpe --json-out sweeps/double_dqn.json
python3 train.py --policy q_learning --episodes 1000 --save-agent checkpoints/q_learning_agent.json
python3 train.py --policy double_dqn --episodes 1500 --save-agent checkpoints/double_dqn_agent.pt
python3 train.py --policy dueling_double_dqn --episodes 1500 --save-agent checkpoints/dueling_double_dqn_agent.pt
python3 train.py --policy masked_ppo --episodes 1500 --save-agent checkpoints/masked_ppo_agent.pt
python3 train.py --policy heuristic --encounter-set overgrowth_easy --episodes 200
python3 train.py --policy double_dqn --encounter-set overgrowth_easy --episodes 1500 --eval-interval 100
python3 watch_policy.py --policy heuristic --encounter-set overgrowth_easy --seed 7
python3 watch_policy.py --policy double_dqn --agent-path checkpoints/double_dqn_agent.pt --encounter-set overgrowth_easy --seed 7 --log-file logs/double_dqn_trace.json
python3 watch_policy.py --policy dueling_double_dqn --agent-path checkpoints/dueling_double_dqn_agent.pt --encounter-set overgrowth_easy --seed 7 --log-file logs/dueling_double_dqn_trace.json
python3 watch_policy.py --policy masked_ppo --agent-path checkpoints/masked_ppo_agent.pt --encounter-set overgrowth_easy --seed 7 --log-file logs/masked_ppo_trace.json
python3 analyze_trace.py logs/double_dqn_trace.json --max-findings 10
```

Useful options:

- `python3 train.py --policy random --episodes 1000`
- `python3 train.py --policy heuristic --episodes 1000`
- `python3 train.py --policy q_learning --episodes 2000 --eval-interval 200`
- `python3 train.py --policy dqn --episodes 2000 --eval-interval 100 --dqn-learning-rate 1e-3 --hidden-sizes 128,128 --dqn-architecture action_feature`
- `python3 train.py --policy double_dqn --episodes 2000 --eval-interval 100 --dqn-learning-rate 1e-3 --hidden-sizes 128,128 --dqn-architecture action_feature`
- `python3 train.py --policy dueling_double_dqn --episodes 2000 --eval-interval 100 --dqn-learning-rate 1e-3 --hidden-sizes 128,128 --dqn-architecture action_feature`
- `python3 train.py --policy masked_ppo --episodes 2000 --ppo-learning-rate 3e-4 --rollout-steps 512 --ppo-epochs 4 --ppo-policy-architecture action_feature`
- `python3 train.py --policy double_dqn --episodes 2000 --batch-size 128 --train-frequency 4 --eval-interval 0`
- `python3 train.py --policy double_dqn --incoming-damage-shaping-scale 0.75 --discount 0.999`
- `python3 train.py --encounter-set overgrowth_easy --policy compare --episodes 1000`
- `python3 sweep.py --policy masked_ppo --trials 20 --episodes 1000 --train-seeds 2 --evaluation-episodes 40`
- `python3 sweep.py --policy q_learning --trials 15 --episodes 500 --train-seeds 3 --sampler random`
- `python3 watch_policy.py --policy q_learning --agent-path checkpoints/q_learning_agent.json --seed 11 --log-file logs/q_learning_trace.json`
- `python3 analyze_trace.py logs/masked_ppo_trace.json --json-out logs/masked_ppo_analysis.json`

Notes:

- `q_learning`, DQN-family agents, and `masked_ppo` now use separate default learning rates.
- The DQN family currently includes `dqn`, `double_dqn`, and `dueling_double_dqn`, with `action_feature` as the default training architecture.
- The policy-gradient family currently includes `masked_ppo`, with `action_feature` as the default training architecture.
- DQN and Double DQN restore the best evaluation checkpoint before the final evaluation by default.
- `--save-agent` stores trained q_learning, DQN-family, and PPO agents for later inspection.
- Reward shaping is configurable with `--hp-loss-penalty-scale` and `--incoming-damage-shaping-scale`.
- DQN-family training now optimizes every 4 environment steps by default, which is much faster than updating on every single step in this Python-heavy environment.
- `train.py` environments do not record full per-step trajectories by default; use `--record-trajectories` if you explicitly need training-time episode histories.
- `--eval-interval 0` disables checkpoint evaluations and is the quickest way to speed up long exploratory runs.
- `--learning-rate` still works as a shared override when you want the same value everywhere.
- `--encounter-set overgrowth_easy` samples from the first-three-fights pool in Overgrowth, including solo enemies and the 3-slime pack.
- Multi-enemy encounters use targeted play actions under the hood, but the fixed discrete action encoder and legal-action mask handle that automatically for RL agents.
- `watch_policy.py` runs one traced combat with either a built-in policy or a saved trained agent and writes richer JSON logs, including pre-action legal actions and masks.
- `analyze_trace.py` reads a saved trace and flags high-confidence tactical mistakes such as missed lethal, avoidable incoming damage, wasted dead cards, bad target choice, and premature end turns.
- `sweep.py` runs Optuna-based hyperparameter sweeps, averages each trial over multiple train seeds, and can save the best-trial summary as JSON.

## Project layout

- `game/`: simulator package
- `main.py`: single-combat demo
- `train.py`: baseline training and evaluation CLI
- `sweep.py`: Optuna-based hyperparameter sweep CLI
- `watch_policy.py`: one-combat policy trace and JSON logging CLI
- `analyze_trace.py`: post-hoc tactical analysis for saved trace logs
- `tests/`: basic mechanics and RL interface tests
