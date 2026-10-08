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

The current training goal is **clearing Act 1 with Ironclad at A0**, measured by
Act 1 clear rate across both regions. The current learning focus is
[combat specialization with campaign-derived starts and matched benchmarks](docs/AGENT_TRAINING.md#campaign-derived-combat-training),
with a fixed noncombat controller for hybrid Act 1 checks. The
[Act 1 preset and paired evaluation](docs/AGENT_TRAINING.md#act-1-training-and-configurable-act-rewards)
retain the configurable act-clear reward and stopping boundary.

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

New traces use lossless gzip compression. Existing plain traces remain readable;
`sts-agent-analyze compress --input runs` previews a verified migration that
preserves their content hashes. See [trace storage](docs/AGENT_EXECUTION.md#compress-existing-public-traces).

Public trajectories go under `runs/train`; private replay seeds/configuration go
under the separate owner-only `runs/train-private` directory. Interrupted writes
remain `.partial`, and finished artifacts are never overwritten. Worker scheduling
preserves each episode's seed. The command reports actual outcomes and timings;
the demonstration policy can lose. See [execution, data loading and cancellation](docs/AGENT_EXECUTION.md).
`sts-headless-play` remains the direct gameplay command.

## Combat episodes and baseline evaluation

With the optional `gym` extra, `game.agent.training.env.CombatTrainingEnv` runs
one fight through the existing full public adapter. It includes nested card and
potion choices, ends after automatic combat cleanup, and reports final HP and
the confirmed fight outcome. Its default task reward is +1 for a combat win and
0 otherwise. A validated JSON configuration can weight victory, defeat, final HP
on victory, end-turn commands and potion-use commands. An opt-in
[potential-based objective](docs/AGENT_TRAINING.md#potential-based-combat-reward-shaping)
adds public HP progress signals during combat. Canonical full-run
recordings retain their original sparse reward.
An optional [defeat reward based on remaining enemy health](docs/AGENT_TRAINING.md#partial-credit-for-enemy-health-on-defeat)
can distinguish near-wins from losses with little enemy damage; it changes the
combat objective and is evaluated separately from the default win/HP reward.

```bash
sts-agent-evaluate --output-dir runs/combat-baseline --cases-per-scenario 4 \
  --split validation --max-decisions 256 --time-limit 30 \
  --config configs/training/combat_victory.json
```

This measures random-legal and current-heuristic performance on the same 24
ordinary-HP Ironclad A0 development cases across six controlled Overgrowth
encounters. It saves `baseline.json`, public trajectories, compact training
sidecars and separate private replay audits; use a new output directory per
experiment. Reports retain the resolved objective, component totals, training
return and actual game results. See the
[training guide](docs/AGENT_TRAINING.md#milestone-2-usage-and-record-semantics)
for configuration, offline rescoring and remaining milestones.

## Learning a combat policy

Install `python -m pip install -e '.[train]'` for the optional CPU PyTorch learner.
Collect separate heuristic demonstrations, then run a bounded imitation warm-up:

```bash
sts-agent-train collect --output-dir runs/demos-train --split train
sts-agent-train collect --output-dir runs/demos-validation --split validation
sts-agent-train imitate --train-dir runs/demos-train \
  --validation-dir runs/demos-validation --output-dir runs/imitation --updates 128
sts-agent-evaluate --checkpoint runs/imitation/final.sts-model \
  --output-dir runs/imitation-combat --cases-per-scenario 1
sts-agent-evaluate --checkpoint runs/imitation/final.sts-model --hybrid \
  --output-dir runs/imitation-campaigns --campaign-cases 2
```

The small actor-critic scores the current legal candidates from public graph
features. New learners include all registered public content identities plus
structured potion effects and partial relic descriptions; additional observed
names come only from training data. Saved checkpoints keep their own frozen
vocabulary. Use `sts-agent-train audit-representation` to check identity and
description coverage; see [catalog features and auditing](docs/AGENT_TRAINING.md#catalog-backed-vocabulary-and-coverage-audits).
Demonstrations include
potion use and combat selectors. Inference bundles and reports are public;
optimizer/RNG resume state lives in a separate owner-only sibling directory.
The initial untrained bundle is retained for comparison.

Imitation also accepts `--representation combat` for an experimental actor with
explicit public combat numbers and separate player/enemy/hand/potion/selection
pools. The default remains `graph`. PPO and evaluation select the matching encoder
from the checkpoint; exact resume preserves its representation. See
[combat representation](docs/AGENT_TRAINING.md#combat-representation-experiment).
The same option exposes experimental
[immediate action previews](docs/AGENT_TRAINING.md#vantom-action-preview-experiment)
for supported attacks against Vantom, including damage and Slippery removal.

Hybrid evaluation runs ordinary-HP Ironclad A0 campaigns with learned combat
choices and the heuristic elsewhere. Existing playback also accepts
`sts-agent-play --combat-checkpoint runs/imitation/final.sts-model --output-dir runs/playback`.
See [checkpoint, resume and measured results](docs/AGENT_TRAINING.md#milestone-3-usage-and-implementation-choices).

Experimental public-information combat search is available with a compatible
unshaped combat critic:

```bash
sts-agent-play --combat-checkpoint runs/combat-model/final.sts-model \
  --search --act1 --output-dir runs/searched-play
```

See [combat search](docs/AGENT_TRAINING.md#experimental-combat-search) for supported
content, paired comparisons, search distillation and reanalysis. Unsupported
states explicitly fall back to the same checkpoint. Search remains opt-in.

Continue the checkpoint with bounded, masked combat PPO:

```bash
sts-agent-train ppo --checkpoint runs/imitation/final.sts-model \
  --config configs/training/combat_ppo.json --output-dir runs/ppo \
  --decisions 256 --time-limit 120 --seed 17
```

This freezes the policy during each collected batch, then updates the same
candidate model. It records actual fight outcomes, cutoff-aware returns and
learning metrics, with a resumable checkpoint after each complete update.
Use the same evaluation/playback commands with the PPO bundle. See
[PPO configuration, resume and results](docs/AGENT_TRAINING.md#milestone-4-usage-and-implementation-choices).

PPO skips a whole rollout update when every advantage and replayed value error
is exactly zero. Reports distinguish processed, trained and skipped decisions;
collection still advances to fresh episodes. See the
[signal guard and pilot](docs/AGENT_TRAINING.md#ppo-signal-guard-and-three-learner-pilot).

New `sts-agent-train ppo` runs default to up to **16 persistent collectors**
and **four learner CPU threads**, bounded by available CPUs. Use `--workers N`
(1–16) and `--update-threads N` (1, 2, 4 or 8) to override them. Rollout decisions
remain a total budget across workers; exact resume restores the saved worker count. See
[parallel collection and horizon choices](docs/AGENT_TRAINING.md#parallel-ppo-collection-2026-09-29).
Multithreaded PPO uses strict deterministic operations. Spawned collectors
use one thread each; exact resume restores its saved CPU settings.
See the [CPU update benchmark](docs/AGENT_TRAINING.md#cpu-ppo-update-threads-and-profiling-2026-10-01).

For the current combat focus, use the
[campaign-derived corpus workflow](docs/AGENT_TRAINING.md#campaign-derived-combat-training)
to train and compare policies on frozen fights from both Act 1 regions. PPO
and matched combat evaluation both support up to 16 workers. The
[command defaults](docs/AGENT_TRAINING.md#cpu-execution-defaults) also cover
playback, analysis export and compression. The earlier finite fixture curriculum remains available:

```bash
sts-agent-evaluate --freeze-suite configs/training/combat_benchmark.json \
  --output-dir runs/combat-suite
sts-agent-train curriculum --checkpoint runs/imitation/final.sts-model \
  --config configs/training/combat_curriculum.json --output-dir runs/curriculum
```

The curriculum adds varied decks, HP, upgrades, relics, potions, pending selectors,
elite/boss fights and early campaign-derived combats. See the
[paired evaluation and checkpoint-selection commands](docs/AGENT_TRAINING.md#milestone-5-protocol-and-usage)
for the 64-case development and 256-case held-out comparison. Reports include
all planned cases and uncertainty grouped by source campaign.

For full-run learning, `sts-agent-train collect-run` records canonical campaign
demonstrations. `imitate --full-run --initialize-combat PATH` transfers the combat
actor, expands the vocabulary from training records only, and resets the critic.
Run PPO with `configs/training/full_run_ppo_overgrowth.json`, then
`configs/training/full_run_ppo.json` to include Underdocks. Those configurations
retain +1 for actual Architect victory and zero otherwise. For configurable
combat and run rewards, use `configs/training/full_run_shaped_ppo.json`; add
`--reset-objective --reset-action-policy` when adopting that objective and its
card-selection commitment policy from an older full-run checkpoint. This keeps the
actor and starts a fresh critic and optimizer. The shared policy layer blocks
deselection in known deferred card selectors, including optional and multiple-card
choices. Picks retain their native order; confirmation remains a separate action
and is available whenever the minimum is met, including zero. The current
`commit_decisions_v1` policy also allows one inspection of each card reward,
then blocks closing it again after reopening without gameplay progress.
Choices, skips, rerolls and inspection of other rewards remain available.
Checkpoint metadata preserves the policy used during training. See the
[policy rules and selector inventory](docs/AGENT_TRAINING.md#shared-policy-actions-and-selection-order).
Assisted demonstrations are labelled separately and provide no normal-run value
targets. See the [reward configuration](docs/AGENT_TRAINING.md#configurable-full-run-rewards)
and the
[full-run commands and results](docs/AGENT_TRAINING.md#milestone-6-usage-and-implementation-choices).

For the current Act 1 goal, train with `configs/training/act1_ppo.json` and
`--reset-objective` when transferring an existing campaign actor. Add
`--reset-action-policy` when adopting its `commit_decisions_v1` policy from
an older checkpoint; omit each reset flag when that setting already matches.
The preset rewards each act clear at +1 alongside the existing combat shaping and ends the
episode after Act 1. `sts-agent-evaluate --act1 --checkpoint PATH
--reference-checkpoint INITIALIZER --output-dir runs/act1-eval` compares Act 1
clear rates against a frozen reference and the heuristic on identical starts.
`--workers` supports 1–16 parallel evaluation games for `--act1`, `--full-run`
and `--combat-corpus`, defaulting to up to 16 available CPUs. Other evaluation
modes remain serial. Workers retain frozen policies and validate their own recordings;
the report keeps every planned case, including failures and interruptions.
Goal and reward weights are configurable and bound to checkpoint identity.

Use `sts-agent-analyze summary --input runs/act1-pilot-20260929` for quick reported
metrics without replay validation. For validated viewer data, use
`sts-agent-analyze build --input runs/act1-pilot-20260929
--output-dir runs/act1-analysis-20260929 --goal act1`, then
`sts-agent-analyze serve runs/act1-analysis-20260929` for a local experiment
overview, run timeline, decision inspector and PPO reward diagnostics. Add
`--checkpoint LABEL=PATH` to compare checkpoint preferences on the same recorded
state. Analysis export and trace compression default to up to eight workers,
bounded by available CPUs. See the [analysis guide](docs/AGENT_TRAINING.md#decision-analysis-tools).

For cross-experiment learning curves, install the optional `tracking` extra and
use `sts-agent-track import runs --store runs/experiment-tracking`, then
`sts-agent-track serve --store runs/experiment-tracking --port 5050`. Add
`--tracking-dir runs/experiment-tracking` to training/evaluation commands for
live logging. The local MLflow dashboard joins exact PPO continuations, keeps
evaluation populations separate, curates initial, final, evaluated and retained
checkpoints with their scores in Models,
and links to the decision inspector. See the
[experiment tracking guide](docs/EXPERIMENT_TRACKING.md).

`sts-agent-play --checkpoint PATH --output-dir runs/run-playback` uses a full-run
checkpoint for every decision. `sts-agent-evaluate --full-run --checkpoint PATH
--combat-checkpoint COMBAT_PATH --output-dir runs/run-evaluation --split test
--campaign-cases 8 --max-decisions 1024 --time-limit 120` compares it with the
heuristic and combat-only hybrid on identical genuine campaign starts.

## Validation

```bash
python -m compileall game tests
PYTHONPATH=. python -m pytest -q
```

Use focused files under `tests/headless/` during gameplay development. The full
suite also checks the retained bridge wire codec and offline operational fixtures.
Install `'.[dev,train]'` to include encoding, Gym and training tests. The smaller
`'.[dev,gym]'` extra omits PyTorch; tests skip when their optional dependencies
are absent. See the [training delivery checks](docs/AGENT_TRAINING.md#milestone-7-usable-commands-and-final-delivery-checks)
for the clean wheel installation and command workflow.
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
| `game/cli/` | Direct gameplay (`sts-headless-play`), public agent execution (`sts-agent-play`) and combat baselines (`sts-agent-evaluate`) |
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
