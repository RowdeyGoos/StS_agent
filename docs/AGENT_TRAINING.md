# Agent training guide

Prepared 2026-09-28, updated 2026-09-29 against checkout `05445c65`.
**Status: milestones 1–7 implemented and validated.**
**Current training goal: clear Act 1 with Ironclad at A0.** Measure improvement
by paired Act 1 clear rate across Overgrowth and Underdocks. Training all three
acts is deferred until this goal shows useful progress; see
[Act 1 training and configurable act rewards](#act-1-training-and-configurable-act-rewards).
The user authorized milestones 1–7 and requested a summary of key
implementation details and choices after each milestone. A bounded CPU imitation
warm-up and hybrid development evaluation are included in milestone 3. Milestone 4
adds bounded PPO and controlled learning checks, with continued hybrid evaluation.
Milestone 5 adds a frozen paired benchmark and a finite combat curriculum.
Milestone 6 extends the shared learner to full runs with a distinct objective,
broader demonstrations and paired genuine campaign evaluation. Milestone 7
checks the installed commands, dependency boundaries and complete delivery workflow.

This document owns training usage, implementation choices and measured results. The [target](TARGET.md)
owns the full-game objective, the [public contract](AGENT_CONTRACT.md) owns actor
information, and the [execution guide](AGENT_EXECUTION.md) owns existing recordings
and workers. The retired training pipelines are not implementation dependencies.

## Decision analysis tools

`sts-agent-analyze` builds a local report from existing **completed public
recordings**. It does not run the game or change checkpoints. The browser viewer
provides:

- An overview filtered by split, evidence kind and policy, with outcome counts,
  last observed floors, action categories and links into individual runs.
- A floor timeline and decision inspector for combat, card selections/rewards,
  route, shop, rest, event and other public decisions. The inspector retains the
  full public graph, available actions, actual choice and observed successor.
- A map graph with recorded room connections, visited/current rooms, legal next
  rooms and the recorded route choice. Click a room for its public details;
  unknown rooms remain unknown, and map rows are distinct from HUD floor counts.
- Selection-toggle and reward-navigation review signals after at least eight
  consecutive actions including reversals in the same floor/context. These link
  to the exact span. Ending a turn while a card is playable is informational,
  not proof of a bad decision. These exploratory signals are separate from the
  pilot's predeclared last-32-action cutoff metric.
- Full-run PPO collection curves and per-action reward components, recorded
  chosen-action probability, critic value, next value, advantage and return
  target. Combat-only PPO task sidecars are not currently joined; their public
  trajectories can still be inspected without inventing combat outcomes.
- Up to four explicitly supplied checkpoints compared on the **same recorded
  public state**. Native legality and the checkpoint's policy mask remain
  distinct. A forced confirmation is labelled as the only policy-allowed action.

Get the reported experiment results immediately, without building the viewer:

```bash
sts-agent-analyze summary --input runs/act1-50k-8workers-20260929
```

`summary` emits JSON from the compact PPO/evaluation reports. It checks PPO
configuration identities and pinned evaluation plans, retains failed/interrupted/
unattempted cases in the reported denominators, and keeps each source's status,
objective, checkpoint identities and results separate. Consecutive PPO chunks are
not pooled as independent learners. Its validation scope is explicitly
`report_metadata_only`: it does **not** read canonical trajectories, rollout
sidecars or checkpoint files, verify paired starting states, or recompute rewards.
Use these reported metrics for quick feedback; use `build` for independent
recording validation and the decision viewer.

Build once with parallel episode exporters, then serve the report locally:

```bash
sts-agent-analyze build \
  --input runs/act1-pilot-20260929 \
  --output-dir runs/act1-analysis-20260929 --goal act1 --workers 8

sts-agent-analyze serve runs/act1-analysis-20260929 \
  --checkpoint initializer=runs/training-readiness-20260929/filtered-initializer.sts-model \
  --checkpoint learner-2=runs/act1-pilot-20260929/learners/learner-2/final.sts-model
```

Open `http://127.0.0.1:8765`; stop the viewer with Ctrl-C. `--port` selects another
local port. The viewer uses bundled assets without online fonts, scripts or
services. It listens only on loopback, has no mutation endpoints, and serves only
its fixed assets and indexed analysis data. It does not serve the repository.

Repeat `--input` to include more public roots. Discovery skips hidden/private/audit
directories, symlinks and partial files. It reads canonical trajectories and
recognized public evaluation/PPO reports and plans; report strings cannot direct
it to arbitrary files. Include a report's full public directory so its pinned
plan, rollouts and completed episodes are present. Failed/unattempted rows stay
visible in provenance; descriptive table rates use completed recordings and are
not a replacement for the planned-population evaluation metrics. Distinct policy
identities, splits, evidence, source builds/rules and training objectives stay in
separate comparison groups. Paired cases require at least two distinct policy
identities with identical public initial state and source identities.

The builder validates each complete canonical artifact, including its digest,
before export. Full-run PPO joins verify the trajectory identity, episode step,
chosen candidate, legality/policy masks, behavior fingerprint and task boundary;
reward components are recomputed from the public owner measurements. Recorded
learner diagnostics are labelled as recorded, not independently reconstructed.
Comparison probabilities are recomputed from an explicitly loaded inference
bundle. Its identity and objective are displayed; different reward objectives
make critic values incomparable. Neither probabilities nor the critic explain
the model's reasoning or estimate calibrated correctness/Act 1 clear probability.

Act 1-labelled success requires an unfinished Act 1 start and a final public
Act 1 completion boundary with canonical `truncated/external_stop`. Full-campaign
victory remains distinct. Canonical terminal outcomes do not contain terminal HP;
the inspector displays it as unavailable instead of inventing a zero or reusing
the previous HUD. Net HP changes include healing and are not damage totals.

Exports use compressed chunks of 16 decisions, loaded on demand with two chunks
cached. The output directory is new and never overwrites an existing report;
failed builds have no completed `report.json`. `build --workers N` accepts 1–8
workers (default 1). These workers independently validate and export episodes;
they do not run training or inference. Episode identities are reserved before
writing, report order is stable, and paired-start checks run in the parent.
Worker errors stop the export without retries; Ctrl-C stops and cleans up workers
and exits with status 130. Start again with a new output directory after failure
or interruption. Compressed decision contents are the same as serial export.
The CLI reports full elapsed time and the report includes metadata preparation,
episode wall time and summed per-episode phase timings. Summed worker times can
exceed elapsed wall time when workers run in parallel.

The report can be copied and
inspected without its original trajectory files. Core export/inspection and the
viewer use the standard library; checkpoint comparison requires `sts-agent[train]`.

For scripts or a bug report, emit one decision (CLI step indexes are zero-based;
the browser shows one-based step numbers):

```bash
sts-agent-analyze inspect runs/act1-analysis-20260929 \
  --episode b2f9a87449a5498fa3ba1562a4cdf319 --step 1000
```

Add `--checkpoint LABEL=PATH` to emit same-state comparison JSON instead. Browser
links preserve the run and zero-based decision index in their URL fragment.
This is recording playback and inference, not counterfactual simulation. Existing
frozen pilot reports/hashes are preserved. Historical inference bundles remain
loadable; exact learner resume still requires its original implementation identity.

Delivery check (2026-09-29): the pilot export contains 383 trajectories / 44,027
decisions and verifies 16 paired evaluation starts. Export took 394.70 seconds
and produced approximately 279 MB of compressed data/assets. Both known floor-1
selector loops are linked from steps 7–1024 in the browser. The affected agent
integration suite passed 777 tests in 405.65 seconds; subsequent focused checks
cover the final plan-goal guard, observed combat deltas and forced policy
confirmation display. Independent semantic review closed its policy attribution,
pairing and Act 1 horizon findings (367 seconds across review and corrections).
Browser checks exercised overview, loop navigation, same-state inference and
training charts. Export and validation ran concurrently with implementation;
implementation time was not separately measured.

Parallel export benchmark (2026-09-29): on the existing 50k experiment's 541
episodes / 56,844 decisions, the installed `summary` command returned in
**0.128 seconds**, including startup. Full validation/export with eight workers
took **62.98 seconds**, compared with the previously measured 472.88-second
serial export of the same recordings (about **7.5× faster**). This comparison
reuses the historical serial timing; cache state and host load were not controlled.
All 3,801 compressed decision chunks (340,140,044 bytes) match the original
export byte for byte, as do every episode row and all 16 paired-start checks.
Sorting episode IDs before reducing collection returns makes aggregation order
stable; the largest difference from the old unsorted mean was 1.67e-16.

Summed worker phase time was about 57.2% canonical loading/validation and 41.8%
encoding/compression/writing; these are shares of worker time, not elapsed time.
The 39 focused analysis tests passed in 11.21 seconds, including the loopback
viewer check, and seven package checks passed in 5.63 seconds. Changed modules
compiled successfully. Independent semantic review took 166 seconds and found
no blockers; large-transfer, abrupt-exit and Ctrl-C probes left no worker or
transfer-thread leaks. Whole-export parity checking took 0.78 seconds.
The [benchmark evidence](evidence/analysis_export_optimization_2026_09_29.json)
retains source identities, timings, parity checks and artifact hashes. Benchmark
outputs are under `runs/analysis-export-optimization-20260929/`; earlier
experiment artifacts and the currently served viewer remain intact.

## Intended result

Deliver a trainable policy over the existing legal candidates, configurable
training objectives, reproducible evaluation, and checkpoints that the current
agent execution path can load. Start with isolated Ironclad A0 fights. As soon as
the first usable combat checkpoint exists, evaluate it in full campaigns with the
existing heuristic handling other decisions. Continue those evaluations alongside
combat training, then extend learning to every run decision once the pipeline is
reliable and combat learning shows progress.

The first observable acceptance case is a seeded, ordinary-HP Ironclad encounter:
initialize its deck and starter relic through existing game APIs, observe public
state, choose legal candidates including any nested combat selections, finish the
fight, assign the configured combat reward exactly once, and reset independently.
A small learned checkpoint must reload and play that same task through the public
adapter. This proves integration; separate evaluation establishes playing strength.

## Existing foundation and concrete gaps

| Area | Reuse | Work needed |
| --- | --- | --- |
| Game rules | [RunEngine](../game/headless/run/engine.py), isolated encounters, catalogs, seeded RNG, declared native starts | Broader campaign-state coverage where evidence calls for it |
| Actor boundary | [HeadlessAdapter](../game/agent/headless/adapter.py), `full_run_v2`, exact candidate bindings, immutable combat summary | New measurements only for objectives beyond combat components and canonical run victory |
| Gym | [FullRunEnv](../game/agent/gym_env.py), [CombatTrainingEnv](../game/agent/training/env.py), separate task objectives, masks and cutoff handling | Broader populations only after measured progress |
| Data | [Canonical recorder](../game/agent/recording.py), [training sidecars](../game/agent/training/records.py), [task loader](../game/agent/training/dataset.py), [full-run corpus](../game/agent/training/run_corpus.py), compact PPO rollouts | Better public demonstrations where measured behavior calls for them |
| Execution | [Runner](../game/agent/runner.py), [workers](../game/agent/workers.py), frozen checkpoint loading, [persistent PPO collectors](../game/agent/training/parallel.py) | Choose worker count and rollout horizon for the measured task |
| Learning | Public graph features, shared candidate scorer, combat/campaign imitation and PPO, checkpoints, paired evaluation | Act 1 clear rate, selector completion and combat strength |

The [full encoder](AGENT_ENCODING.md#full-run-profile-and-environment) allocates
6,789,184 bytes per padded observation. The milestone 1 baseline below measures
the actual simulation/dispatch, projection, encoding and recording costs for
combat episodes. These are workload-specific observations, not estimates of
neural training throughput. Milestone 3 measures a real CPU training batch below.

## Implementation boundaries

Keep game rules in `game/headless/`. New learning code belongs under
`game/agent/training/`, with installed commands in `game/cli/`. Proposed module
names below describe responsibilities; create them as their milestone needs them.

| Responsibility | Proposed location |
| --- | --- |
| Validated experiment configuration and scenario sampling | `game/agent/training/config.py`, `scenarios.py` |
| Combat task lifecycle and public transition measurements | `game/agent/training/env.py`; narrowly shared adapter helpers if needed |
| Reward component registry and evaluation | `game/agent/training/rewards.py` |
| Task sidecars, objective validation and offline rescoring | `game/agent/training/records.py`, `dataset.py` |
| Public feature extraction and candidate-scoring network | `game/agent/training/features.py`, `model.py` |
| Imitation/PPO updates and bounded collection | `game/agent/training/learner.py`, `ppo.py`, `rollout.py`, `parallel.py`, `ppo_run.py` |
| Checkpoints and comparison reports | `game/agent/training/checkpoint.py`, `evaluation.py` |
| Curriculum and frozen paired benchmarks | `game/agent/training/curriculum.py`, `curriculum_run.py`, `benchmark_suite.py`, `benchmark.py`, `comparison.py` |
| Full-run task, demonstrations, transfer and evaluation | `game/agent/training/run_task.py`, `run_corpus.py`, `run_demonstrations.py`, `run_evaluation.py` |
| Installed entry points | `game/cli/agent_train.py`, `agent_evaluate.py`, `agent_play.py` |

Use an optional `train` dependency extra containing a tested PyTorch/Gymnasium
stack. Preserve the standard-library engine and ordinary agent imports. Verify
Python 3.10 compatibility when selecting dependency versions; record exact versions
for experiments. Start with CPU as the reference execution mode. Device selection
can support available accelerators after the same numerical checks pass.

Actor and critic inputs contain only the public decision and its observable
history. Dispatch bindings, engine snapshots, seeds, RNG state, scenario registry
indexes and private replay metadata stay with the controller. Outcome labels and
rewards arrive after actions and never become pre-action hindsight features.

## Milestone 1: combat episodes and a measured baseline

Create a `CombatTrainingEnv` consumer using a fresh `RunEngine` and the existing
`HeadlessAdapter(..., decision_profile="full_run_v2")`. Reuse dispatch, validation,
identity and encoding machinery. Extract shared lifecycle helpers only where the
existing Gym implementation would otherwise need to be copied.

Start with a named Ironclad/A0/Overgrowth scenario set: ordinary starter inventory,
representative weak and normal encounters, and separate train/development/test
seed schedules. Use the existing native RNG profile explicitly; bare custom runs
otherwise default to fixture RNG. Initialize relics, potions, upgrades and decks
through existing game-owned APIs. Label authored starts as controlled scenarios.
Campaign-derived starts are a later addition and retain separate provenance.

Define the episode boundary precisely:

- Include play, target, end-turn, potion and nested selection decisions owned by
  the same fight. Do not end the episode merely because a selector changes the
  public context kind. Never hand a nested choice to an automatic fallback.
- End on the authoritative completed fight after automatic cleanup and synchronous
  end-of-combat hooks, before reward claims or another post-combat choice. Verify
  death/revival, escaping enemies and delayed resolution against engine outcomes.
- Return task termination on combat win/loss. Keep the underlying run outcome
  separate: winning a fight is not `sts_run_outcome_v1: victory`.
- External time/decision budgets truncate and retain the final public decision
  for bootstrapping. Failures remain failures; invalid/stale commands neither
  advance training nor receive rewards. Do not retry uncertain mutations.

Add a small immutable public transition summary for the controller. Capture the
completed combat's identity/outcome before losing its ownership reference, and
read only allowlisted public values after `RunEngine.apply` returns. Record final
HP/max HP after automatic end-of-combat effects and before reward choices. This
endpoint is necessary because `RunOutcome` currently has no final HUD state and
`finish_combat()` clears `run.combat`. Do not infer victory from an empty enemy
list, or infer cumulative damage taken from net HP change. No engine snapshot or
private effect-resolution dictionary enters the summary.

Use public decisions from the same owner for both fixed Gym encoding and the
later packed training representation. A narrow owner API may expose terminal
facts to training without changing the existing decision/outcome wire schemas.
Retain the current `StsEnv` and `FullRunEnv` defaults.

**Acceptance:** focused cases exercise normal victory, defeat, a nested selector,
a potion child, revival and an external cutoff; terminal facts and flags agree
with the engine. Identical seeds/actions reproduce traces and independent episodes
do not share mutable state. Report random-legal and current-heuristic performance
and the time spent in simulation, projection, encoding and recording.

### Milestone 1 usage and implementation choices

Install the existing optional `gym` extra; this milestone needs no PyTorch or
new dependency extra. Ordinary engine, adapter and training-package imports
remain standard-library only. The optional environment uses the existing full
encoder and its 2,048 candidate slots:

```python
from game.agent.full_policy import choose_action
from game.agent.training.env import CombatTrainingEnv

with CombatTrainingEnv(encounter="overgrowth_nibbit") as env:
    observation, info = env.reset(seed=42)
    while True:
        decision = env.public_state
        candidate = choose_action(decision)
        observation, reward, terminated, truncated, info = env.step(
            decision.candidates.index(candidate))
        if terminated or truncated:
            print(info["combat"], info["outcome"])
            break
```

`public_state` exposes the immutable structured decision used by the encoder,
without a binding or engine reference. Combat ownership, rather than a context
label, determines the endpoint. `info["combat"]` is the controller's allowlisted
`sts_combat_summary_v1`: attachment-local combat reference, ongoing/victory/defeat,
HP, max HP and turn. Terminal HP includes synchronous post-combat effects. It
contains no seed, engine identity, snapshot or effect-resolution dictionary.

The milestone 1 task reward, retained as the default, is +1 for a combat win and 0 otherwise.
A fight win returns `terminated=True` while `info["outcome"]` normally describes
an unfinished run cut off with `truncated/external_stop`. A real defeat preserves
the real run defeat. The terminal encoded state has no legal actions; time and
decision cutoffs instead retain the final public decision and legal mask, with
`truncated=True`. Rejected actions do not advance the episode or pay rewards;
execution failures require reset. Milestone 2 below adds configurable rewards
and training sidecars. Existing `StsEnv` and `FullRunEnv` rewards/defaults are unchanged.

The named scenario set `ironclad_a0_overgrowth_v1` contains Nibbit, Fuzzy Wurm and
Slimes weak encounters, plus Mawler, Nibbits and Cubex normal encounters. Each
starts a fresh native-RNG Ironclad A0 run with 80/80 HP, its ten starter cards,
Burning Blood, no upgrades and no potions, using game-owned setup APIs. These
are controlled starts, not campaign-derived states. `engine_factory(seed)` can
supply another fresh, exclusively owned live combat for controlled experiments.

Run both reference policies on paired development cases:

```bash
sts-agent-evaluate --output-dir runs/combat-baseline --cases-per-scenario 4 \
  --split validation --max-decisions 256 --time-limit 30
```

The command currently evaluates `random_legal` and the unchanged public heuristic;
it does not load learned checkpoints. Four seeds for each of six encounters
produce 24 episodes per policy. Use a new output directory for each experiment:
completed reports/trajectories are never overwritten. `--encounter` can select a
subset; `--start-index` selects a window of the trusted seed schedule. The existing
`validation` split means development/model selection. Train, validation and test
use disjoint external seed schedules; Gym game-seed generation and policy RNGs
are separate. The default evaluation leaves held-out test seeds unused.

`baseline.json` contains source/build/policy identities, software versions,
limits, paired episode IDs, actual combat/run outcomes, HP, action counts,
win rates with Wilson intervals, per-encounter summaries and timings. Every
completed episode has a canonical `.trajectory.jsonl` with its original sparse
run rewards (a combat win pays 0 there). Private replay configuration and seeds
live in the separate owner-only `runs/combat-baseline-private` directory.
Milestone 2 adds a separate `.training.json` per completed episode and records
resolved objectives/components in the version 2 evaluation report.

Timings distinguish initialization, action dispatch including simulation and
guards, public projection including its guard, fixed encoding, policy choice,
and canonical recording. Total wall time also includes array copies and replay
audit writes. Each padded observation occupies 6,789,184 bytes; compact learner
storage remains milestone 3. Infrastructure failures stop the batch, leave
unfinished trajectories `.partial`, and remain visible with the unattempted count
in a failed report. These are baseline measurements, not evidence of learning.

### Milestone 1 accepted results — 2026-09-28

The [retained public report](evidence/combat_baseline_2026_09_28.json) records the
final source fingerprint, runtime versions, paired episode results and timings.
Both policies played the same 24 development cases (four per encounter). The
final measurement ran without concurrent test execution; no held-out test cases
were used. All 48 episodes completed without cutoffs or infrastructure failures.

| Policy | Combat wins | Mean final HP on wins | Decisions/second, including recording |
| --- | ---: | ---: | ---: |
| Random legal | 14/24 (58.3%) | 52.50 | 22.23 |
| Current public heuristic | 22/24 (91.7%) | 64.91 | 20.07 |

The 1,009 decisions took 47.51 seconds of summed episode wall time: 2.14 seconds
in simulation/dispatch, 10.66 in projection, 16.30 in encoding, 14.83 in recording,
and 3.15 in policy choice; initialization and remaining overhead make up the rest.
These controlled starter-deck fights establish a small baseline, not campaign
strength or evidence of learning. Wilson intervals in the report describe this
small sample and do not establish general policy strength.

All 48 canonical trajectories were reloaded and validated against their final
source/policy fingerprints; their 1,009 original sparse rewards remain zero.
Full trajectories and private replay audits are retained locally under
`runs/combat-milestone1-20260928-verified` and its `-private` sibling. Trajectory
filenames in the retained report refer to that original output directory.

Validation: the full agent suite passed **424 tests in 610.51 seconds**. A final
explicit v1-profile rejection guard passed the focused combat/adapter suite
(**66 tests in 5.07 seconds**). Compilation of `game` and `tests`, Python 3.10
syntax checks, standard-library-only core imports, the installed command and its
missing-Gym error were checked. Runtime testing used Python 3.11.15,
Gymnasium 1.0.0 and NumPy 2.4.6. One independent semantic review passed, including
zero-action timeout and no-clobber checks. The only suite warnings were the
existing Gym checker warnings for fixed-value observation bounds.

Available delivery timings: initial implementation and focused checks occupied
approximately 18:37–18:50 UTC; the full regression pass took 10m 10.51s; the local
editable package install took 0.66s. Review, documentation and validation
overlapped; review and user-wait durations were not separately measured. The
final baseline duration above is a measured workload, not a training estimate.

## Milestone 2: configurable objectives and faithful records

Implemented with a versioned `RewardSpec` and a pure calculation over the public
action, reconciled report and before/after combat summaries. JSON configuration
accepts finite numeric weights and registered component names; unknown or
unavailable components fail explicitly, even at zero weight. Reward calculation
does not mutate the engine or consume game RNG.

Keep three concepts distinct: actual run outcome, combat-task outcome, and the
scalar training reward. Preserve the existing full-run base reward in recordings.

| Initial component | Exact measurement | Initial weight |
| --- | --- | ---: |
| `combat_win` | 1 once at genuine combat victory | 1.0 |
| `combat_loss` | 1 once at genuine combat defeat | 0.0 |
| `win_hp_fraction` | On victory only, final HP divided by final max HP at the declared endpoint, bounded to [0, 1] | 0.0 |
| `end_turn_action` | 1 for a reconciled `end_turn` command; nested selector actions do not increment it | 0.0 |
| `potion_use_action` | 1 for a reconciled `use_potion` command, irrespective of later belt replacement | 0.0 |

The last component measures the decision to use a potion, not an inferred count
of net potions consumed. Additional objectives such as exact damage prevented or
resource consumption need their own public measurement and focused tests before
they become selectable. A zero weight does not justify inventing a missing value.

The checked-in [default configuration](../configs/training/combat_victory.json)
is accepted by `sts-agent-evaluate --config`:

```json
{
  "mode": "combat",
  "scenario_set": "ironclad_a0_overgrowth_v1",
  "reward": {
    "schema": "sts_training_reward_v1",
    "weights": {
      "combat_win": 1.0,
      "combat_loss": 0.0,
      "win_hp_fraction": 0.0,
      "end_turn_action": 0.0,
      "potion_use_action": 0.0
    }
  }
}
```

Omitted weights retain the defaults above; resolved configurations always record
all five. Duplicate/unknown keys, unsupported versions/modes/scenario sets,
booleans, non-finite weights and unavailable components reject. The immutable
specification identity hashes its version and normalized weights, independently
of JSON key order.

The default optimizes fight victory probability. Experiments can add, for example,
a small positive terminal HP weight or a negative potion-use weight. Those weights
define a different training utility; win rate and HP remain separately reported.
Changing weights affects further training, not the behaviour of an already frozen
checkpoint. Goal-conditioned inference is outside the first implementation.

`sts_public_trajectory_v1` and its sparse reward validator remain intact. A successful
isolated combat ends its still-running canonical run recording with the existing
`truncated/external_stop` outcome; its training task has terminated successfully.
A real defeat keeps its real run outcome. The versioned training sidecar is keyed
by trajectory digest and transition index for reward components, `RewardSpec`,
task flags and the public terminal summary. It reuses canonical observations
instead of duplicating them in another dataset. The loader validates joins and
permits recomputing supported reward weights from those measured components. It uses
the sidecar's task flags and training reward; existing loaders continue to return
the original run flags and sparse reward.

For online learning, hold compact transitions in memory and retain selected
complete audit episodes with the same semantics. Never publish partial episodes
as complete data, overwrite original sparse rewards, or mix incompatible reward
specifications in a value-learning batch without an explicit conversion.

**Acceptance:** hand-calculated traces match component totals; terminal reward is
paid once; rejection/reset/truncation cannot manufacture success. Test healing,
HP costs, replacement potions and selector toggles against the declared meanings.
Old recordings still load unchanged. Reward sidecars reject mismatched digests,
duplicate transitions, missing measurements and incompatible task boundaries.

### Milestone 2 usage and record semantics

For example, copy the default JSON to a new experiment configuration and set
`win_hp_fraction` to `0.25` and `potion_use_action` to `-0.02`. Pass that file with
`--config`, or construct the same objective directly:

```python
from game.agent.training.env import CombatTrainingEnv
from game.agent.training.rewards import RewardSpec

objective = RewardSpec({"win_hp_fraction": 0.25, "potion_use_action": -0.02})
env = CombatTrainingEnv(reward_spec=objective)
```

The spec is fixed for an environment's lifetime. Each reconciled step returns
the scalar reward and `info["training_reward"]` containing `spec_id`, all five
measured `components`, and `total`. Reset, rejected actions and cutoffs before
dispatch return no measurement and reward zero. They cannot fabricate a victory
bonus. Nested selection/toggle/confirm commands are separate transitions and
count as neither end turns nor potion use. Consuming a potion that replaces or
refills the belt still contributes one potion-use command. Final HP fraction
includes HP costs, max-HP changes and automatic post-combat healing.

`CombatTrainingRecorder` wraps the existing canonical writer and buffers only
compact measurements. Each `.training.json` has schema `sts_combat_training_v1`:

- The exact canonical file SHA-256 **including the completion footer**, opaque
  episode ID, task kind and resolved reward specification/identity.
- An initial public combat summary and one indexed row per reconciled canonical
  transition: all five components, scalar reward, task flags and combat summary.
- An explicit final task boundary. A zero-action timeout has no fake transition;
  a timeout between actions marks the last recorded transition truncated without
  changing its reward or successor decision.

The compact summaries have the same allowlist as `info["combat"]`. Ongoing HP,
max HP and combat round are cross-checked against public observations. Final HP
is attested by the combat owner because canonical terminal outcomes do not carry
HUD values. This is a consistency/digest check, not independent proof against a
producer falsifying terminal facts. Private replay seeds and engine state never
enter the sidecar or actor observations.

Publication is canonical-first, sidecar-second. Each file uses an exclusive
`.partial`, flush/fsync and atomic no-clobber publication. Interruption between
them can leave a valid canonical file without a published training sidecar; the
training loader rejects that incomplete pair. Existing canonical readers still
load that file and retain their original sparse reward/run flags.

Load a pair or explicitly rescore supported components without replaying a game:

```python
import json
from pathlib import Path
from game.agent.training.dataset import load_training_dataset
from game.agent.training.rewards import RewardSpec

root = Path("runs/combat-baseline")
report = json.loads((root / "baseline.json").read_text())
pairs = [(root / row["trajectory"], root / row["training"])
         for row in report["episodes"] if row["status"] in ("terminated", "truncated")]
for episode in load_training_dataset(pairs, split="validation"):
    print(episode.reward_spec.identity, sum(step.reward for step in episode.transitions))

# Explicit conversion to one objective, leaving original files unchanged.
rescored = load_training_dataset(pairs, split="validation",
    reward_spec=RewardSpec({"combat_win": 0, "win_hp_fraction": 1}))
```

`load_training_episode(trajectory_path, sidecar_path, split=...)` validates one
complete pair. `load_training_dataset` preflights compact objective identities
before yielding its first episode and rejects mixed specs unless the caller
supplies one explicit conversion. Each episode retains `recorded_spec` alongside
the effective `reward_spec`. Original measurements/rewards must validate even
when rescoring. File contents never supply paths to the loader. Full observations
are loaded one episode at a time; compact sidecars are held for batch preflight.
Use trusted local evaluation manifests when constructing the explicit pairs above.

`game.agent.training.dataset.training_examples(..., encoder=FullRunEncoder())`
encodes the same canonical public observations with task rewards/flags and a
`reward_spec_id` sample label. That label is not an observation feature. Genuine
combat termination disables value bootstrapping even though the run was cut off;
ongoing time/decision cutoffs keep their public successor and legal mask.

The `sts_combat_baseline_v2` report and `sts_combat_replay_v2` private audit retain
the resolved configuration and objective identity. Reports add component totals
and mean training return while keeping win rate, HP and actual run outcomes
separate. Historical milestone 1 reports and trajectories remain unchanged;
they contain no training sidecars and are not silently upgraded. No learner,
checkpoint or online rollout buffer is introduced in this milestone.

### Milestone 2 accepted results — 2026-09-28

The affected regression run passed all **221 behavior checks** (new reward/data
cases plus combat, canonical recording, runner, Gym and adapter consumers).
That 83.18-second run also exposed a stale package inventory missing the milestone
1 evaluation CLI. The inventory was updated, and all **4 package/import checks**
passed in 0.31 seconds, including `--config` help and reward/config/data imports
with optional dependencies disabled. Compilation, Python 3.10 syntax checks and
diff/link checks passed. The earlier full campaign/engine acceptance was not
rerun for this consumer-only change.

One independent read-only semantic reviewer found no blockers. Its controlled
checks covered shaped terminal reward, unchanged canonical rewards, mixed-objective
rejection, explicit conversion, footer-bound digests, pre-dispatch timeout and
cancellation between the two publications. The focused tests additionally cover
HP costs, post-combat healing, max-HP changes, potion belt replacement, selector
toggles, malformed components, task-boundary tampering and publication races.

The installed `sts-agent-evaluate --config` command completed one paired Nibbit
development case, **2 episodes / 27 reconciled decisions**, under weights
`combat_win=1`, `combat_loss=-1`, `win_hp_fraction=0.25`, `end_turn_action=-0.01`
and `potion_use_action=-0.02`. The [retained public report](evidence/combat_rewards_2026_09_28.json)
records both wins: random-legal ended at 57/80 HP after five end turns for return
**1.128125**; the heuristic ended at 73/80 after two end turns for **1.208125**.
Both canonical returns remain zero. This small integration smoke establishes
scoring/recording agreement; the milestone 1 sample remains the performance baseline.

Online returns and all saved component totals matched the training loader.
Explicit offline conversion to the default objective returned **1.0** for each
fight and left every source file byte unchanged. All **48 milestone 1 episodes /
1,009 transitions** loaded with their original metadata/rewards; the retained
milestone 1 report still matches its original file byte for byte. Full local
smoke artifacts are under `runs/combat-milestone2-20260928-shaping/`, with private
replay audits in the disjoint owner-only sibling directory.

The smoke's shipped-source build identity is
`75b6905253a48a7c5d88dbf774b505af7cee97cd760a558d3121c5245981299e`.
Measured episode wall time totalled **1.419 seconds**. Implementation, review,
documentation and checks overlapped approximately **19:08–19:37 UTC**; review
duration was not separately measured. The existing editable installation exposed
the updated command; no new package build or user setup wait was needed.

## Milestone 3: learnable representation, imitation and checkpoints

Implement a small PyTorch actor-critic with a shared public state encoder. Encode
typed scalar fields, public content/mechanic names, entity links and ordered
children. Pool entity/state features and score each candidate using the state,
action kind, subject embedding and target embedding. Use a shared scorer over
all candidates, not a fixed interpretation of slot numbers. A separate value head
predicts expected return under the selected reward specification; only the pure
terminal-victory objective makes that return a victory probability.

Use a versioned feature schema and frozen vocabulary with explicit unknown-name
handling. Per-observation string-table indexes and raw entity ordinals are not
content IDs. Preserve availability markers, duplicate entities, hand/orb order,
selection bounds and the links needed to evaluate every legal candidate. Start
with a feed-forward encoder over the available public history; add recurrence
only if a measured learning limitation justifies it.

First prove one real forward/backward batch using the existing full encoding.
Then pack populated graph rows and candidate tables for rollout storage and
minibatches, preserving public values and exact candidate dispatch mappings.
Share traversal/canonicalization with the current encoder, and compare packed
and fixed representations. Do not silently clip cards, history or candidates to
meet memory limits. Avoid allocating the full padded graph at every stored step
or applying global quadratic attention over all serialized rows.

Apply the same legal-action mask during sampling, log-probability calculation,
entropy calculation and evaluation. Terminal observations are not sent through
an all-masked categorical distribution. Changing candidate enumeration or public
reference names must not change the corresponding action probabilities.

Use a small corpus from the current public chooser for a behaviour-cloning
warm-up. Include combat selections and potion decisions. Demonstrate that a tiny
set of distinguishable choices can be overfit; report held-out imitation accuracy
and episode performance. The teacher is an integration policy, not an expert.
Keep a no-imitation baseline for the later PPO comparison.

Save an inference bundle containing model weights, architecture, feature/vocabulary
identity, contract profile, reward identity and code/build provenance. Keep private
resume data separate. Initially support checkpoints at clean episode/collector
boundaries: optimizer state, learner RNGs and sampling cursor are recoverable,
while interrupted in-flight episodes are explicitly abandoned. Do not claim exact
mid-combat resume, which the public adapter does not currently support.

**Acceptance:** finite forward/backward updates, decreasing imitation loss, zero
invalid dispatches, candidate/reference invariance and duplicate-card coverage.
Reloading a checkpoint reproduces inference on a fixed corpus. A bounded CPU
resume experiment matches uninterrupted execution at the supported boundary.
Report batch memory, encoding cost and inference/update latency.

### Milestone 3 usage and implementation choices

Implemented under `game.agent.training` with the optional `train` extra. The
tested environment uses Python 3.11.15, PyTorch 2.13.0, NumPy 2.4.6 and Gymnasium
1.0.0 on CPU with one PyTorch thread. PyTorch's installed metadata permits Python
3.10+; source syntax is also checked for 3.10. A Python 3.10 interpreter was not
used for this acceptance run.

```bash
python -m pip install -e '.[train]'
sts-agent-train collect --output-dir runs/demos-train --split train
sts-agent-train collect --output-dir runs/demos-validation --split validation
sts-agent-train imitate --train-dir runs/demos-train \
  --validation-dir runs/demos-validation --output-dir runs/imitation --updates 128
sts-agent-evaluate --checkpoint runs/imitation/final.sts-model \
  --output-dir runs/imitation-combat --cases-per-scenario 1
sts-agent-evaluate --checkpoint runs/imitation/final.sts-model --hybrid \
  --output-dir runs/imitation-campaigns --campaign-cases 2 --time-limit 60
```

Each command publishes to a new output directory and keeps existing artifacts.
`collect` records eight controlled scenarios per case: the six milestone 1
encounters plus native Armaments/Gambler's Brew selectors and low-HP potion use.
It uses the unchanged public heuristic. Collection remains bounded by decisions
and time. These authored starts are not campaign-derived training data.

The default network has 48 hidden units and two graph message-passing layers.
Typed scalar features, frozen public-name embeddings, parent/child order and
typed entity links feed pooled state/entity representations. One shared scorer
handles every candidate; a separate value head fits complete-episode returns.
Unknown names have ID 0; validation/test corpora cannot fit a vocabulary. Exact
public values and dispatch mappings remain in populated tables from the shared
encoder. Scalar scaling/log transforms are explicitly lossy model features.
Every policy probability, sample, entropy and greedy decision uses the same legal
mask; terminal observations have no categorical distribution.

Imitation uses cross-entropy and a value MSE with weight 0.25, Adam learning rate
0.003, batch size 8 and gradient clipping at 1.0. Complete returns use gamma 1.
Cutoff demonstrations supply policy labels but no invented terminal value label.
The warm-up's value targets were all victories, so its small value error does not
demonstrate calibration or victory prediction on unfamiliar states. The value
head is unconstrained; its numerical output need not lie in [0, 1].

`imitation.json` records settings, corpus/vocabulary identities, initial/final
bundle hashes, train/validation losses and accuracy, per-update metrics, input
tensor bytes and timings. `initial.sts-model` retains the no-imitation baseline;
`final.sts-model` contains the completed warm-up. Each inference archive contains
only `manifest.json` and a model `state_dict`: architecture, contract/layout,
feature vocabulary, reward identity, build provenance, runtime and static learner
settings accompany the weights. Loading uses PyTorch's
[weights-only state-dictionary path](https://docs.pytorch.org/tutorials/beginner/saving_loading_models),
checks exact keys/shapes/dtypes and rejects nonfinite weights or incompatible
identities. No model object is unpickled.

Private `*.resume.pt` files in the sibling `OUTPUT-private` directory retain
Adam moments, learner RNG, shuffled example order and cursor. Resume validates
the bundle, objective, corpus, source build, Python/PyTorch/thread settings and
optimizer configuration. Files use mode 0600 and their directory 0700. Resume
supports the same CPU runtime between complete offline updates over a completed
corpus; it does not restore an in-flight game, guarantee cross-machine numerical
identity or continue a partially failed optimizer step.

```bash
sts-agent-train imitate --train-dir runs/demos-train \
  --validation-dir runs/demos-validation --output-dir runs/imitation-resumed \
  --resume-bundle runs/imitation/final.sts-model \
  --resume-state runs/imitation-private/final.resume.pt --updates 32
```

Here `--updates` is additional work. Omit `--seed`; saved RNG state is restored.
Explicit architecture, batch-size or learning-rate overrides must match the saved
settings. Interrupted collection is abandoned; collect a fresh bounded episode.
Checkpoints and reports publish atomically without replacing completed files.

The retained [milestone 3 report](evidence/imitation_training_2026_09_28.json)
records the bounded warm-up, combat and hybrid gameplay, memory/latency profile,
resume experiment and validation. Its development results do not consume held-out
test seeds or establish reliable gameplay strength. Detailed results are below.

The accepted local model is
`runs/imitation-milestone3-model-20260928-verified/final.sts-model`; its initial
baseline is beside it and private resume files are in the `-private` sibling.
The retained report identifies each demonstration, gameplay and profiling output
directory and original report hash. Binary models and full trajectories stay in
ignored `runs/`; the public evidence summary is retained in `docs/evidence/`.

The accepted warm-up used eight completed training fights (226 decisions) and
eight separate development fights (192 decisions), including six selected-card
actions, one selector confirmation and two potion-use actions in training.
After 128 updates, training cross-entropy fell **1.284 → 0.130** and action
agreement rose **25.7% → 98.2%**. Development agreement rose **26.6% → 92.2%**;
development cross-entropy was 0.324. The whole fit, including corpus loading and
publication, took **15.83 seconds**. A four-choice controlled test also reaches
100% agreement; it is an overfit check rather than game-performance evidence.

On six paired development combat cases, the checkpoint and heuristic each won
**6/6**, with mean post-hook HP **62.83/80**; random legal play won **3/6**.
All 18 episodes completed without cutoffs or infrastructure failures. The first
ordinary-HP hybrid campaign comparison used two fixed development cases with a
256-decision/60-second limit per run:

| Development pair | Heuristic | Learned combat / heuristic elsewhere |
| --- | --- | --- |
| 1 | Defeat; Act 1, floor 14; last HUD 3/80 HP; 5 potion-use actions | Defeat; Act 1, floor 16; last HUD 4/80 HP; 5 potion-use actions |
| 2 | Defeat; Act 1, floor 12; last HUD 14/80 HP; 1 potion-use action | Defeat; Act 2, floor 21; last HUD 4/87 HP; 5 potion-use actions |

These are the last public HUD values before terminal outcomes, not final HP;
every run ended in genuine defeat. There were no cutoffs, failures or invalid
dispatches in these campaigns or the combat comparison. Two campaign cases are
development feedback, not statistically persuasive evidence of an improvement.

A separate installed-command smoke ran the frozen checkpoint in two spawned
workers, each deliberately limited to 16 decisions. Both published valid
`decision_budget` truncations and 32 reconciled commands in total. One run exposed
a real policy gap: an unfamiliar `regent_cosmic_indifference` selector led to
repeated select/deselect actions instead of confirmation. These legal actions
stayed within the owning combat and the budget stopped the loop. This remains
recorded development evidence for broader selector training and PPO; the warm-up
is not a generally reliable combat policy.

The training corpus stores **35.94 MB** of packed tables plus neural features
(mean **159 KB/decision**, versus **6.79 MB** for one padded observation).
A representative batch of eight uses **229,552 bytes** of input tensors;
autograd retained **4,806,874 bytes** of unique tensor storage, including shared
inputs/parameters. Parameters, gradients and Adam tensors occupy 232,520,
232,520 and 465,176 bytes respectively. The profiling process peaked at 381.81 MB
RSS including libraries, corpora and multiple learner instances; this is not a
claim about minimum learner memory.

Across 32 development decisions, median feature encoding took **21.37 ms** and
complete greedy policy inference including encoding **21.85 ms**. Median update
latency was **3.54 ms** (preencoded minibatches). Representation validation and
encoding dominate this small network's computation. These timings describe this
CPU, corpus and workload. Eight real-corpus updates also matched four updates,
checkpoint/reload and four more updates exactly for weights, learner RNG, order
and cursor; focused tests separately cross an epoch boundary.

Final validation passed **540 agent/package tests in 623.55 seconds**, plus
compilation and Python 3.10 syntax checks. The only three warnings were the
existing Gymnasium notices about fixed observation bounds. The installed training,
combat evaluation, hybrid evaluation and two-worker checkpoint playback commands
were exercised. One independent semantic review completed with no remaining
blockers after fixes to optimizer/config/source bindings, terminal rejection and
audit-directory forwarding. Its focused checks included 14 passing tests.

Available timing: implementation began **19:44 UTC**; implementation, review,
experiments and documentation overlapped through final validation at **20:30 UTC**
on 2026-09-28. The final regression pass took **10m 23.55s**, and the editable
package refresh took **0.56s**. Review duration was not separately measured;
there was no user setup wait. No live bridge build or installation was needed.

### Begin hybrid full-run evaluation with the first usable checkpoint

Once a combat checkpoint reloads and selects legal actions through the adapter,
begin bounded ordinary-HP Ironclad A0 campaign evaluations. The learned policy
chooses combat actions and their nested choices; the existing heuristic chooses
all other actions. Ownership, not just the context's label, determines the handoff.
Reuse the same public adapter and candidate dispatch, with a frozen checkpoint
throughout each evaluated run.

Start this during milestone 3 and continue at selected checkpoints throughout
milestones 4 and 5. Completion of combat PPO, curriculum tuning or a strong combat
benchmark is not a prerequisite. Label these results as hybrid-policy evaluation;
full-run learning still begins in milestone 6.

Compare the hybrid with the unchanged heuristic on fixed development campaign
seeds, keeping held-out test seeds separate. Report actual run outcomes, campaign
progress, HP and potion usage, plus cutoffs and failures. Use these comparisons
to check whether better isolated combat performance improves campaign survival
or exposes poor consumable use and unfamiliar-deck weaknesses. Early evaluations
provide development feedback, not evidence of reliable full-run victory.

## Milestone 4: a bounded masked PPO learner

Implement a small project-owned PPO loop in PyTorch around the candidate-scoring
model. This is the initial baseline, not a claim that PPO is optimal for this game.
Use the published [PPO objective](https://arxiv.org/abs/1707.06347) and consistent
[invalid-action masking](https://arxiv.org/abs/2006.14171); avoid introducing another
environment or a second set of game rules to fit a training library.

Store the sampled candidate mapping, original legal mask, old log probability,
value prediction, reward components and termination/truncation flags with each
rollout transition. Compute advantages/returns using the configured training
reward. Start with `gamma=1` for terminal win-probability objectives. Any changed
discount or shaping is an explicitly different experiment. Configure learning
rate, clipping, entropy/value weights, gradient clipping and batch sizes in the
experiment file; record the resolved values.

Bootstrap external cutoffs from the final observation, never from the next reset.
Stop advantage recursion at episode boundaries; bootstrap value and continuation
masks are different. True combat/run termination has zero bootstrap. This follows
the [Gymnasium time-limit semantics](https://gymnasium.farama.org/tutorials/gymnasium_basics/handling_time_limits/).

Start with one synchronous environment and batched updates. Reuse existing seed
separation, cancellation, failure handling and atomic publication. When profiling
supports multiple collectors, extend shared worker lifecycle helpers and carry
an explicit checkpoint/policy identity to every worker. Current `run_batch` does
not already provide this training capability. Freeze a policy version during each
collection batch so PPO never unknowingly mixes behaviour policies.

Stop on non-finite losses, bad masks, incompatible artifacts or uncertain engine
execution. Retain the last complete checkpoint and an explicit failure category.
Track wins, losses, cutoffs, each reward component, entropy, value error, policy
divergence, decisions/second and peak memory using ordinary experiment reports.

Suggested development bounds are 256 collected decisions for the first update
smoke and, after it passes, a pilot capped at 20,000 decisions or one hour,
whichever comes first. These are planning defaults, not runtime estimates or
authorization to start a run. Select larger budgets from measured throughput.

**Acceptance:** compare return/advantage calculations to small manually worked
trajectories; exercise true termination and truncation separately. A controlled
learnable combat case improves relative to its initial policy across repeated
learner seeds. Check cancellation, checkpoint/resume, and independent environment
RNGs. A successful optimizer step alone does not establish learning.

### Milestone 4 usage and implementation choices

The installed `ppo` subcommand initializes the existing public candidate model
from an inference bundle. Starting from milestone 3's imitation bundle loads its
weights and frozen vocabulary and creates a fresh PPO optimizer. The retained
untrained bundle can also initialize a separate comparison. The declared reward
must match the bundle's objective.

```bash
sts-agent-train ppo --checkpoint runs/imitation/final.sts-model \
  --config configs/training/combat_ppo.json --output-dir runs/ppo \
  --decisions 256 --time-limit 120 --seed 17
sts-agent-evaluate --checkpoint runs/ppo/final.sts-model \
  --output-dir runs/ppo-combat --cases-per-scenario 1
sts-agent-evaluate --checkpoint runs/ppo/final.sts-model --hybrid \
  --output-dir runs/ppo-campaigns --campaign-cases 2 --time-limit 60
```

The resolved `sts_ppo_experiment_v1` configuration contains the training objective,
named encounters and PPO settings. The supplied configuration starts with the
existing ordinary-HP Nibbit encounter and sparse combat victory reward. Defaults
are 256 decisions per rollout, at most 96 per fight, gamma 1, GAE lambda 0.95,
Adam learning rate 0.0003, 32-example minibatches and four epochs. Policy clipping
is 0.2, entropy weight 0.01, value-MSE weight 0.5 and gradient clipping 0.5. A
post-epoch approximate-KL check stops additional epochs above 0.03; this is a
stopping heuristic and does not guarantee a hard divergence bound. Advantage
normalization uses population variance and retains the signal for singleton or
constant batches. Changing these settings declares a different experiment.

The synchronous learner freezes one model throughout a rollout, using one local
collector by default or persistent processes with `--workers`. Sampling,
likelihoods, entropy and update replay all use the original legal candidate mask
and mapping. The last unfinished fight closes at the rollout decision limit;
its final public observation supplies the bootstrap value. A true combat win or
loss uses zero bootstrap, even though the canonical run record for a combat win
ends with `external_stop`. GAE recursion stops at either task boundary. A timeout
before dispatch adds no fictional action and cannot trigger an endless reset loop.
Each collector closes every environment before optimization; it does not retain
live games across batches.

`ppo.json` records resolved configuration, source/runtime identities, initialization,
actual wins/losses/cutoffs/failures, accepted and trained decisions, reward components,
HP, potion use, update losses, entropy, value error, divergence, input memory,
parent-process peak RSS, worker allocation and throughput. Parent RSS excludes
collector processes; it is not total pool memory. `rollout-NNNNN.json` retains original candidate
references/masks, selected action, old likelihood/value, next value, rewards,
task flags and computed advantages/returns. It joins public canonical trajectories
and training sidecars by episode ID and trajectory digest. Private replay audits
retain engine reset seeds separately. These are controlled headless starts.

Unrestricted PPO inference bundles use `sts_inference_bundle_v2`; the
[filtered action policy](#shared-policy-actions-and-selection-order) uses v3.
Both retain `ppo_v1` identities, and existing v1 imitation bundles remain loadable.
Each completed rollout/update boundary, including a recorded no-signal skip, publishes a bundle
and separate private resume file. `initial.sts-model` is published before collection,
`update-NNNNN.sts-model` after each complete update, and `final.sts-model` on clean
completion. The report names the last complete checkpoint. Public inference has
no optimizer, RNG or sampling cursor; its digest binds the matching private state.

```bash
sts-agent-train ppo --checkpoint runs/ppo/final.sts-model \
  --resume-state runs/ppo-private/final.resume.pt \
  --config configs/training/combat_ppo.json --output-dir runs/ppo-resumed \
  --decisions 256 --time-limit 120
```

`--decisions` means additional work and is bounded to 1–20,000 per invocation;
`--time-limit` is at most one hour. Resume restores Adam state, separate action
sampling and minibatch RNGs, episode cursor, decision count, collection iteration
and optimizer-step count. Private `sts_ppo_resume_v3` state binds the
[signal guard and skipped iterations](#ppo-signal-guard-and-three-learner-pilot),
as well as worker count and allocation schedule introduced by v2.
Omitted `--workers` restores the saved count; changing it
requires a new experiment from an inference bundle. Same-source legacy v1 private
states restore serial collection. Omit `--seed` and `--start-index` when resuming. Exact
continuation requires matching source, experiment and CPU runtime, and a boundary
after a completed rollout/update with no live game. Interrupted collection or a
partly applied update is abandoned. SIGINT/SIGTERM, deadline checks and numerical
or execution failures retain the preceding complete artifact and report the stop.
The deadline is cooperative at action/minibatch/measurement boundaries. Parallel
collection additionally enforces a parent deadline with five seconds of grace
for results; cancellation or failure uses bounded cooperative, terminate and kill
cleanup. A stopped invocation may have no `final.sts-model`:
use `last_complete_checkpoint` and its matching private file instead.

### Milestone 4 measured results

The retained [milestone 4 report](evidence/ppo_training_2026_09_28.json) binds the
source, configuration, reports and checkpoints. Models and complete trajectories
remain under ignored `runs/`. The accepted ordinary-combat checkpoint is
`runs/ppo-milestone4-pilot-20260928/final.sts-model`, with the matching private
resume state in `runs/ppo-milestone4-pilot-20260928-private/final.resume.pt`.

A controlled learning probe used the real engine and three fresh learner seeds,
with no imitation. Each one-action fight offers Strike, which wins, or end turn,
which loses. A 16-unit/one-layer network trained for 512 decisions per replicate,
in 64-decision batches, with learning rate 0.003, GAE lambda 1 and KL threshold
0.05. These settings and all three replicates were fixed before running. Evaluation
uses a separate RNG and 32 paired stochastic development trials of that same
authored fight before and after learning:

| Replicate | Initial wins | Final wins | Exact policy probability of winning, before → after |
| --- | --- | --- | --- |
| 1 | 21/32 | 32/32 | 58.68% → 99.51% |
| 2 | 10/32 | 32/32 | 34.81% → 99.90% |
| 3 | 11/32 | 32/32 | 37.39% → 99.75% |

All three improved. Here the exact probability is the policy probability of the
single winning action, not a value-head estimate. This demonstrates that the
learner can acquire the authored decision; it is not evidence of broad combat
strength. Training took 14.37, 14.21 and 14.33 seconds respectively; the complete
probe including evaluation/publication took 47.00 seconds. No held-out test set
was used.

The ordinary-combat pilot initialized the accepted milestone 3 imitation weights
and used the supplied PPO configuration. It completed **1,024 decisions in 81.94
seconds**, across four batches and 120 optimizer steps: **113 combat wins, no
defeats, three batch-limit cutoffs and no execution failures**, out of 116 attempts.
Mean post-hook HP on wins was 70.88/80. All 1,024 accepted decisions were trained;
no potion-use actions occurred. This is training-distribution behavior, not an
unbiased evaluation result. The first 256-decision development smoke also passed;
a subsequently fixed deadline edge case and its original source identity remain
distinguished in the evidence record.

The pilot averaged 12.50 decisions/second including recording and updates, with
525.48 MB peak process RSS. A packed 256-decision rollout occupied about 41.03 MB;
minibatch inputs peaked at 924,200 bytes. Collection took 79.44 seconds in total,
while the four updates took 2.29 seconds. This workload supports retaining the
simple synchronous collector for now; these numbers include this machine's
runtime and public-recording overhead. All losses and gradients were finite;
post-update approximate KL ranged from 0.0054 to 0.0651. The value targets are
dominated by victories on easy fights and do not establish calibration elsewhere.

On six paired development combat cases, PPO and the heuristic each won **6/6**;
random legal play won **3/6**. Mean post-hook HP was 63.33/80 for PPO and 62.83/80
for the heuristic. All 18 evaluation episodes completed without cutoffs or
failures. Milestone 3's imitation checkpoint also won all six of these same cases;
the small comparison does not establish improved general strength.

The same two development campaigns were also run with the unchanged heuristic
and with PPO handling combat, under 256-decision/60-second per-run bounds:

| Development pair | Heuristic | PPO combat / heuristic elsewhere |
| --- | --- | --- |
| 1 | Defeat; Act 1, floor 14; last HUD 3/80 HP; 5 potion-use actions | Defeat; Act 1, floor 16; last HUD 3/80 HP; 5 potion-use actions |
| 2 | Defeat; Act 1, floor 12; last HUD 14/80 HP; 1 potion-use action | Decision cutoff; Act 2, floor 19; last HUD 71/87 HP; 4 potion-use actions |

The second PPO campaign used a Colorless Potion and then alternated 29 selections
and 28 deselections of `the_gambit`, despite a legal confirmation candidate. Its
budget stopped the loop. This is a policy failure to make progress, distinct from
an invalid command or infrastructure failure. Compared with milestone 3's second
hybrid reaching floor 21 before defeat, this is a regression in that development
case. Narrow Nibbit training has not solved unfamiliar selectors or established
campaign improvement. There were no failed/invalid dispatches; the cutoff remains
in the report. HUD values above are last observed values, not terminal HP.

A separate installed playback smoke loaded the PPO bundle in two spawned workers
and recorded 32 reconciled decisions with two intentional 16-decision cutoffs,
in 2.27 seconds. This exercised frozen inference in existing workers; PPO training
at that milestone used one synchronous collector. Parallel training was added later.

Final validation passed **199 affected tests in 31.01 seconds**, including manual
PPO/GAE calculations, deadline crossing during final measurement, real task endings,
action-free timeouts, independent engine resets, original masks, exact CPU resume,
source/config/private-state mismatches, interruption after optimizer work, real
CLI SIGTERM, legacy imitation compatibility, records, runner lifecycle and package
help without optional dependencies. The single warning is Gymnasium's existing
fixed-bound `Box` warning. One unchanged long multi-act runner test and the wider
engine/profile matrix were not repeated; milestone 3 retains their earlier evidence.
Compileall and Python 3.10 syntax checks passed for all 432 Python sources/tests;
runtime validation used Python 3.11.15. One independent semantic reviewer found
the deadline gap, verified its correction, passed 16 focused checks and exercised
installed training/resume and no-clobber publication. No review blockers remain.

An additional 54.45-second artifact check reloaded all 116 pilot episodes and
recomputed the 1,024 saved action likelihoods, values and successor bootstraps
from the corresponding frozen checkpoints. Candidate mappings, masks, component
rewards, task flags, canonical sparse rewards, trajectory digests and private
permissions all matched. Total owner time through the evidence summary was about
43 minutes, including implementation, overlapping review, experiments and reporting;
separate implementation/review totals were not recorded.

Milestone 5 below freezes a larger evaluation population and broadens the training
curriculum, including selector completion and consumable choices.

## Milestone 5: combat evaluation and curriculum

Freeze the evaluation population and comparison rules before tuning. Keep seed
registries with the trusted evaluator; policy inputs contain only public state.
Separate training seeds, development seeds used for model selection and a held-out
test set used after selecting the checkpoint. Group derived starts by source
campaign to prevent one run from leaking across dataset splits.

Begin with 64 development and 256 held-out combat cases as practical planning
defaults, stratified across the declared scenarios. Compare random legal actions,
the current heuristic, imitation-only and PPO policies on the same cases. Run at
least three learner seeds for the selected configuration and report uncertainty;
these sample counts are not a strong-agent certification design.

Report combat win rate, HP remaining conditional on victory, starting-to-ending
HP change, potion-use decisions, turn count, cutoffs and infrastructure failures.
Keep failures and unfinished fights visible in denominators; do not silently
discard them. Report paired differences and confidence intervals, per encounter
and overall. Choose checkpoints using development gameplay metrics, with win rate
primary, rather than shaped return alone.

Expand the curriculum in bounded steps: weak/normal encounters; multiple legal
decks and starting HP levels; upgrades/relics/potions; elites/bosses; then starts
sampled from actual headless campaigns. Include held-out deck/encounter combinations.
Keep the evaluation distribution fixed while changing the training curriculum.
Exercise low-HP/HP-cost decisions, optional selectors and consumable tradeoffs so
the model cannot appear strong merely by exploiting one authored fight.

Continue the hybrid development evaluations started in milestone 3. Use their
results to identify combat objectives or training distributions that do not
transfer to campaigns, and to decide when to begin full-run learning. Exhausting
the combat curriculum is not a gate for milestone 6.

**Acceptance:** a reproducible report establishes whether the chosen checkpoint
improves on the heuristic under a predeclared criterion. A useful combat-policy
claim requires positive held-out evidence, not just successful software delivery.
If results are inconclusive, record that result and change one measured bottleneck
or learning assumption at a time; do not start an unbounded parameter search.

### Milestone 5 protocol and usage

The first curriculum experiment is predeclared before training: freeze
[64 development and 256 held-out starts](../configs/training/combat_benchmark.json),
then run three independently seeded PPO learners from the accepted milestone 3
imitation bundle. Keep its public feature vocabulary, network and terminal-win
objective unchanged. The [curriculum settings](../configs/training/combat_curriculum.json)
allocate **256, 256, 512, 256 and 256 decisions** to five cumulative stages per
learner (1,536 each; 4,608 total). Each stage has a 180-second limit; every combat
has at most 96 decisions and 30 seconds. Report actual stage coverage because a
decision budget can expire before every available start is visited.

The stages add ordinary starter-deck encounters; low-HP/HP-cost choices and an
upgraded strength deck; pending Armaments, Colorless Potion and Gambler's Brew
selectors plus consumables; an elite and boss; and the first two combats reached
through genuine ordinary-inventory campaigns. Starts use existing native game
APIs and snapshot restoration. The latter campaigns use the public heuristic to
reach the declared combat, without replacing failed origins. Reattaching at a
start begins a fresh public history. This covers early campaign fights, not the
distribution of later campaign states. The Choice/Fuzzy and Strength/Kin
combinations occur only in the held-out population.

Each stage carries inference weights and the frozen vocabulary, resets Adam and
its action/shuffle RNG, and continues the private episode cursor. A change of
curriculum is an explicit new experiment, not an exact resume across changed
settings. Exact resume remains available within an individual stage. Learner
seeds and replay/snapshot data stay in owner-only sibling directories; public
reports identify replicas and hash-bound artifacts.

```bash
sts-agent-evaluate --freeze-suite configs/training/combat_benchmark.json \
  --output-dir runs/combat-suite
sts-agent-train curriculum --checkpoint runs/imitation/final.sts-model \
  --config configs/training/combat_curriculum.json --output-dir runs/curriculum
sts-agent-evaluate --suite runs/combat-suite/suite.json \
  --candidate imitation=runs/imitation/final.sts-model \
  --candidate ppo_1=runs/curriculum/learner-1/stage-4/final.sts-model \
  --candidate ppo_2=runs/curriculum/learner-2/stage-4/final.sts-model \
  --candidate ppo_3=runs/curriculum/learner-3/stage-4/final.sts-model \
  --output-dir runs/combat-development
sts-agent-evaluate --suite runs/combat-suite/suite.json \
  --select-development runs/combat-development/benchmark.json \
  --output-dir runs/combat-selection
sts-agent-evaluate --suite runs/combat-suite/suite.json --split test \
  --selection runs/combat-selection/selection.json --output-dir runs/combat-test
```

The evaluator restores the identical frozen engine start for each policy. It
includes random legal actions and the current heuristic automatically. Development
compares all three PPO finals and imitation; test compares only the selected PPO,
imitation and the two references. Selection ranks development wins first, then
fewer cutoffs, mean HP fraction conditional on winning and finally the policy
name. The test command binds this selection before opening any held-out snapshot;
the same suite then refuses further development evaluation or selection. Limits,
source identity, snapshot digests and policy artifacts must match their bindings.

Every planned case remains in the denominator, including failures, interrupted
and unattempted cases. Reports include overall and actual-native-encounter results,
authored scenario results, conditional winning HP, observed HP change, potion-use
commands, final combat turn and explicit cutoffs. Source failures stop evaluation
and prevent selection or a positive performance claim; no easier case replaces
them. HP-change metrics also report their observed count.

The predeclared primary comparison is **selected PPO minus heuristic held-out win
rate**. A positive claim requires a complete report and a positive lower bound
of its two-sided 95% source-group Hoeffding interval. Two fights from one campaign
share a group and cannot cross splits. For group sizes \(m_g\), total \(N\) and
\(\alpha=0.05\), the win-rate radius is
\(\sqrt{\log(2/\alpha)\sum_g m_g^2/2}/N\); the paired-difference radius is twice
that value. These conservative bounds permit dependence within a source group
and assume independent sampled sources. This is an application of
[Hoeffding's bounded-sum inequality](https://www.cs.rpi.edu/academics/courses/spring06/random/hoefding.pdf).
They describe the declared stratified population, not all game encounters or all
possible training seeds. Per-encounter intervals are descriptive, without a
multiple-comparison claim. Replica variation is reported separately on development.

After selection, continue the existing two-case hybrid development comparison at
256 campaign decisions and 60 seconds per case. Sparse win reward is unchanged:
training can finish a selector stochastically while greedy evaluation still
cycles. Record that failure if observed rather than introducing an undeclared
fallback or changing the objective after opening the held-out set.

### Milestone 5 measured results

The retained [milestone 5 evidence](evidence/combat_curriculum_2026_09_29.json)
binds the frozen suite, curriculum, three checkpoints, development selection,
held-out report and hybrid report. Full trajectories remain in the corresponding
local `runs/combat-milestone5-*-20260929` directories; private replay and resume
artifacts remain in their owner-only siblings. The accepted source build is
`96c280ae0446b970ff87dca8b42756d8f6c344f0779200a0458c545bbbe2c472`;
engine rules and heuristic identities are unchanged from milestone 4.

The fixed three-replica curriculum completed **4,608 decisions in 348.89 seconds**
on the existing CPU environment. Every learner visited every available profile
within each of its five stages, including the elite, boss and both early campaign
starts. Its 320 training episodes contained 298 wins, six defeats, 16 batch-quota
cutoffs and no infrastructure failures. Training included 39 selector confirmations,
39 potion-use commands and 26 deselections. These are sampled training outcomes;
they do not establish greedy policy strength.

Development evaluated all 384 planned case/policy pairs in **604.28 seconds**:

| Policy | Wins / 64 | Defeats | Cutoffs | Mean HP on wins |
| --- | --- | --- | --- | --- |
| Random legal | 36 | 28 | 0 | 45.81 |
| Heuristic | 60 | 4 | 0 | 56.12 |
| Imitation | 57 | 3 | 4 | 55.63 |
| PPO replica 1 (selected) | 60 | 3 | 1 | 56.08 |
| PPO replica 2 | 58 | 2 | 4 | 54.95 |
| PPO replica 3 | 56 | 4 | 4 | 56.89 |

There were no infrastructure failures or omitted cases. Across learner seeds,
development win rate averaged 90.625%, ranged from 87.5% to 93.75%, and had a
sample standard deviation of 3.125 percentage points. The selected replica tied
the heuristic overall but won four cases the heuristic lost and lost four cases
the heuristic won. Its paired interval was correspondingly inconclusive.

The profile breakdown explains the tie: the selected PPO won three of four
Gambler's Brew starts (imitation and the other two PPO replicas cut off on all
four), but only one of four Ceremonial Beast starts versus the heuristic's four.
It won all four low-HP potion starts versus the heuristic's one. Every learned
policy won the eight early campaign-derived development fights; that narrow
coverage does not establish late-campaign performance.

The locked selection is replica 1, bundle
`098b4d2c5d51da5f98af4c76179bb58cbfd93893f7be83d27d1931d8a6156691`.
The complete held-out evaluation ran **1,024 case/policy pairs in 1,440.99 seconds**:

| Policy | Wins / 256 | Win rate | Defeats | Cutoffs | Mean HP on wins |
| --- | --- | --- | --- | --- | --- |
| Random legal | 152 | 59.4% | 104 | 0 | 44.12 |
| Heuristic | 232 | 90.6% | 24 | 0 | 55.35 |
| Imitation | 231 | 90.2% | 19 | 6 | 54.76 |
| Selected PPO | 234 | 91.4% | 17 | 5 | 54.29 |

There were no infrastructure failures or omitted cases. Selected PPO won 14 cases
the heuristic lost and lost 12 that the heuristic won: **+0.78125 percentage
points**, with a source-group Hoeffding 95% interval of **−17.2248 to +18.7873
points**. The predeclared conclusion is **inconclusive**. The bounds are deliberately
conservative and too wide to establish a small improvement; this does not prove
the policies equivalent. Winning HP also did not improve in this sample.

All five PPO cutoffs were Gambler's Brew starts: 96 select/deselect commands with
no confirmation, still inside `discard_redraw`. It won 11/16 of these starts versus
imitation's 10/16 and the heuristic's 16/16. On the two excluded combinations, PPO
won 16/16 Choice/Fuzzy starts and 9/16 Strength/Kin starts; the heuristic won 16/16
and 11/16 respectively. Both won 9/16 authored Ceremonial Beast starts. The retained
report includes every native-encounter and authored-profile breakdown, including
HP change, potion-use commands and final combat turn.

The paired hybrid development check took **72.42 seconds**. Both selected-PPO
campaigns ended in actual defeat at floor 16 (Ceremonial Beast and Vantom), compared
with heuristic defeats at floors 14 and 12. There were no cutoffs or infrastructure
failures, and no learned full-run victory. Neither learned run used a Colorless
Potion or issued a combat selector command; the milestone 4 floor-19 Gambit loop
was not reached, so this check cannot establish that the earlier failure is fixed.

Validation passed 224 focused cases before the final lock correction, followed by
all 26 curriculum/benchmark cases after it (225 distinct cases overall). The one
unchanged long multi-act runner test remained deselected; the existing Gymnasium
fixed-bound warning remains. The independent reviewer passed eight selected checks
and separately verified restored optional confirmations and a concurrent selection
lock conflict with zero held-out snapshot access. Review corrected native encounter
reporting and that lock race; no blockers remain. Compileall, Python 3.10 syntax
checks for 438 files, installed command usage and diff checks passed.

The final artifact audit verified all **1,728 combat episodes / 34,810 decisions**,
all 320 frozen snapshot digests, policy initialization chains, unchanged model/
vocabulary/objective, summary calculations, canonical zero rewards, task outcomes
and 2,102 owner-only private files. The four hybrid trajectories also passed the
existing canonical loader. Evidence is entirely headless; no native bridge build
or live-policy capability is claimed. At this milestone boundary, full-run data
and selector behavior remained useful next work;
this result does not justify an unbounded combat parameter search.

## Milestone 6: full-run learning

Begin once the training pipeline is reliable and combat learning shows useful
progress, informed by the hybrid evaluations already running since milestone 3.
Reliable campaign victories and completion of all combat tuning are not entry
requirements. Keep the heuristic and frozen hybrid checkpoints as comparisons.

Train the shared model across every `full_run_v2` decision family using
`FullRunEnv`. Broaden the imitation corpus to rewards, shops, rests, map travel,
events and endings before online training. Expand the model's feature vocabulary
explicitly when required. Initialize from the combat encoder/policy where
compatible, and reinitialize or retrain its value head: combat return and full-run
return are different targets. Do not blend their transitions as one task.

The default full-run training reward remains +1 for actual Architect victory and
0 otherwise, with undiscounted episodic return. Add a `run_victory` component that
maps exactly to the canonical base reward and a separate full-run `RewardSpec`
preset with all combat weights zero. Combat shaping is optional and
separately identified; final selection/evaluation uses actual run victory. If
wins are too rare for a useful signal, use better public-information demonstrations
or a declared curriculum, including easier continuation starts where appropriate.
Evaluate from genuine run starts separately. Never expose future outcomes or a
real hidden draw order to a demonstrator/planner acting as a public policy.

Start with Overgrowth A0, then include Underdocks. Other characters and higher
ascensions follow measured Ironclad progress. Shared public schemas do not alone
guarantee model transfer to live producer details: native card previews and
headless descriptors need feature-level compatibility checks before deployment.

**Acceptance:** every current decision family reaches the learned policy through
the existing legal-candidate interface; real defeat, victory and cutoff semantics
remain intact. Produce held-out full-run win-rate and compute-budget comparisons
for heuristic, hybrid and fully learned policies. Do not label boosted fixtures
or assisted continuations as normal-HP agent victories.

### Milestone 6 usage and implementation choices

The shared PPO update/GAE code now collects either combat episodes or full
campaigns through the existing `FullRunEnv`. Full-run data uses canonical
trajectories directly, without combat sidecars. `sts_full_run_reward_v1` measures
only `run_victory`: +1 at the engine-owned Architect ending, zero on every other
transition. Its resolved preset declares every combat weight zero. Gamma must
be 1. The later [configurable v2 objective](#configurable-full-run-rewards) adds
combat shaping without changing v1 artifacts or canonical demonstrations. Existing
combat-v1 reward serialization and inference loading are preserved exactly;
cross-task resume, combat sidecars and hybrid initialization reject run objectives.

Collect separate training and development data, then transfer a selected combat
checkpoint explicitly. Replace `COMBAT_MODEL` with its `.sts-model` path:

```bash
sts-agent-train collect-run --output-dir runs/run-train --cases 4 \
  --include-fixtures --max-decisions 1536 --time-limit 300
sts-agent-train collect-run --output-dir runs/run-validation --cases 2 \
  --split validation --max-decisions 1024 --time-limit 120
sts-agent-train imitate --full-run --initialize-combat COMBAT_MODEL \
  --train-dir runs/run-train --validation-dir runs/run-validation \
  --output-dir runs/run-imitation --updates 256 --learning-rate .0003
sts-agent-train ppo --checkpoint runs/run-imitation/final.sts-model \
  --config configs/training/full_run_ppo_overgrowth.json \
  --output-dir runs/run-ppo-overgrowth --decisions 1024 --time-limit 600
sts-agent-train ppo --checkpoint runs/run-ppo-overgrowth/final.sts-model \
  --config configs/training/full_run_ppo.json --start-index 2000 \
  --output-dir runs/run-ppo-mixed --decisions 1024 --time-limit 600
```

The optional fixtures author rewards, shops, rests, events, treasure and relic
choices on a valid campaign map, with 40 HP/1,000 gold and a 32-decision cap.
One separate assisted campaign starts with 10,000 HP and five upgraded Byrd
Swoops to reach later acts and the ending through legal actions. The teacher
receives only public decisions. These records have `controlled_fixture` evidence;
they teach imitation actions but provide **no normal-run value labels**, including
on victory. Genuine starts and their outcomes remain separately counted.
Cutoff demonstrations also have no Monte Carlo value target. Review the recorded
context/ending coverage before starting PPO; a time limit can stop demonstrations
before their intended endpoint.

Vocabulary expansion unions the old vocabulary with training-only public names.
The transfer remaps embeddings by name, including unknown row zero, and copies
compatible shared/actor weights. The critic gets a fresh hidden layer and zero
output; Adam, learner RNG and sampling cursor start fresh. The imitation report
records this lineage. Validation/test names never expand the vocabulary.
Exact same-task resume still uses the public bundle plus its owner-only matching
resume file and requires unchanged implementation/runtime/configuration.

The two PPO configurations start with Overgrowth, then include Underdocks. A
changed region population is an explicit new experiment: carry inference weights
and vocabulary, use a fresh optimizer and distinct/continued training cursor.
The examples above reserve a later training cursor for the second stage. Both
configs cap batches at 512 decisions and episodes at 1,024; the remaining batch
quota can close an episode earlier. Such cutoffs retain the final ready public
observation for bootstrapping, while true victory, defeat and abandonment have
zero bootstrap. Timeouts before dispatch create no invented transition. These
bounded pilots do not guarantee enough late-run reward signal for strategic
improvement.

Play or compare the frozen full-run checkpoint:

```bash
sts-agent-play --checkpoint runs/run-ppo-mixed/final.sts-model \
  --output-dir runs/run-playback --max-decisions 1024 --time-limit 120
sts-agent-evaluate --full-run --checkpoint runs/run-ppo-mixed/final.sts-model \
  --combat-checkpoint COMBAT_MODEL --output-dir runs/run-test --split test \
  --campaign-cases 8 --max-decisions 1024 --time-limit 120
```

The full-run actor scores every headless decision family through legal candidates,
including nested selectors and reward presentations. The combat-only comparison
still uses authoritative combat ownership for hybrid routing. All three evaluation
policies start from identical genuine Ironclad A0 campaigns with the same
Gym-derived engine seed per case; separate interleaved train/development/test
roots keep their source populations separate. A public plan pins policy/source
identities, limits, cases and paired groups before the first action. Private
seeds stay in owner-only replay files. Reports retain all planned cases, including
failures and unattempted rows; incomplete comparisons cannot claim improvement.
Win rates, conservative grouped uncertainty, decisions and compute time are
reported for each policy. This bounded comparison fixes its checkpoint before
test; it is not a new adaptive checkpoint-selection system.

### Milestone 6 measured results

The 2026-09-29 pilot is retained under
`runs/full-run-milestone6-20260929/`. Its protocol fixed the corpus, 256 imitation
updates, 1,024 Overgrowth PPO decisions followed by 1,024 mixed-region decisions,
and the final-checkpoint comparison before training. Development feedback did
not select or tune the tested checkpoint.

Training demonstrations contain 1,665 decisions: four genuine campaigns ended
in defeat after 437 decisions; six authored room continuations supplied 192
decisions before their caps; the assisted campaign supplied 1,036 decisions and
completed the Architect ending. All ten current headless decision contexts were
present. The assisted 1,228 decisions supplied no value labels. Two separate
ordinary development demonstrations supplied 411 decisions and both ended in
defeat. Only the 437 ordinary training decisions supplied critic targets, all zero.

Transfer retained the combat checkpoint's 156 vocabulary names and added 818
names from training records, yielding 974. Teacher agreement rose from 28.95%
to 77.78% on training data and from 48.66% to 77.86% on the separate development
data. This is imitation agreement, not a game win rate. The warm-up took 419.57
seconds; 172.22 seconds were training-corpus encoding and 3.53 seconds were
optimizer updates. The packed training corpus occupied 1,081,776,955 bytes.
Loading, validating and encoding public histories dominate this small CPU model's
cost; these are measured workflow timings, not a dedicated hardware benchmark.

Each PPO stage recorded 11 ordinary-start attempts: nine defeats and two quota
cutoffs, with no failed episodes or victories. The stages took 136.58 and 127.14
seconds including collection/checkpoint/report work, with roughly 783 MB and
762 MB peak process RSS respectively. Four complete collection/update batches
trained all 2,048 requested decisions. Every return and advantage was zero, so
the policy changes came from entropy regularization; the policy-gradient and
value losses remained zero. This validates full-run collection/update/resume,
but does **not** demonstrate successful learning from run-victory reward.

The fixed final inference bundle is
`runs/full-run-milestone6-20260929/ppo-mixed/final.sts-model`, SHA-256
`afc6d63bd5a3be70c8d8243e689e3764db256f645a951f78e4de58aad1345248`.
Keep this pilot distinct from the selected milestone-5 combat policy. The two
development comparison cases produced no wins for any policy, and the fully
learned policy lost much earlier. A later continuation curriculum or better
public demonstrations must establish useful reward signal before longer
full-run training is justified; that is a separate experiment, not a reason
to retune this checkpoint on its held-out cases.

The held-out comparison used eight paired ordinary starts, four per first-act
region, with a 1,024-decision/120-second limit per episode:

| Policy | Run wins | Defeats | Cutoffs | Mean last observed floor | Decisions | Episode execution seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Heuristic | 0/8 | 8 | 0 | 10.13 | 1,016 | 71.95 |
| Frozen combat hybrid | 0/8 | 7 | 1 | 9.13 | 1,514 | 201.24 |
| Fully learned | 0/8 | 8 | 0 | 1.00 | 346 | 30.04 |

The fully learned policy died on floor 1 in **every** development and test case.
Its shorter execution time reflects earlier defeat, not better efficiency.
No evaluation episodes failed or were omitted. The hybrid timed out on floor
10 after 288 card selections and 287 deselections, without a confirmation. That
existing selector weakness remains unresolved by this milestone.

All primary win-rate differences are zero; the conservative paired 95% bounds
are ±96.03 percentage points, so the small pilot establishes neither improved
win rate nor equivalence. The observed progression is plainly worse for the
fully learned checkpoint. Higher teacher agreement did not translate into
useful autonomous play. This experiment does not isolate whether imitation,
entropy-only PPO updates, or both caused the degradation.

Episode execution timings include simulation, projection, policy and recording;
they exclude later canonical-file validation. The whole held-out command took
353.05 seconds. The complete declared pilot, including corpus collection,
preparation, learning and both comparisons, took 1,433.96 seconds (23.90 minutes).
The [retained evidence](evidence/full_run_training_2026_09_29.json) binds the
protocol, reports, model hashes, runtime, outcome rows and available timings.
Source build is `4a13646269563ca3625af45aa8ac7a5fa2e5d928347f552da60211e3bdbe67b4`;
game-rule and heuristic identities are unchanged from milestone 5.

Validation passed 223 distinct focused checks across incremental runs, including
all-family learned scoring, actual Architect/defeat/abandonment semantics,
cutoff bootstrapping, task rejection, vocabulary remapping, exact CPU resume,
worker loading and paired evaluation. One unchanged long multi-act runner test
was excluded; milestone 7 retains the broad integration gate. Project-environment
`compileall game tests` passed. The independent review found and verified the
room-continuation correction, then passed eight focused checks in 16.86 seconds
and six installed CLI integration/no-clobber checks in 10.076 seconds. Those
disposable checks are implementation evidence, not gameplay-strength evidence.
The final artifact audit verified 65 complete trajectories and 7,737 actions,
reloaded all 22 PPO episodes through the canonical loader, and matched all 401
recorded learned-policy evaluation choices by replaying the frozen checkpoint.
The poor choices are reproducible: for example, it ended its first three turns
in one development fight with all three energy unspent. Ten inference bundles
retain their source/objective identities; 78 private artifact files passed
permission checks, and no pilot partials remain. No live bridge work or
milestone-7 broad integration/clean-package gate was performed.

### Training-time benchmark (2026-09-29)

This baseline precedes the [performance optimization](#training-performance-optimization-2026-09-29)
reported below; retain these original measurements for comparison.

The dedicated timing experiment uses the unchanged milestone-6 source and final
full-run checkpoint on local macOS 26.6.2 / arm64, Python 3.11.15 and PyTorch
2.13.0. Each worker has one PyTorch CPU thread and one synchronous collector.
The host reports 18 logical CPUs; its hardware model was unavailable under the
sandbox. These are elapsed wall times, with no cold-file-cache claim.

Three fresh workers start from identical model weights, learner RNG and training
roots, each collecting 512 decisions with the current mixed-region PPO config.
Canonical recording, rollout reports, two PPO epochs (64 optimizer steps), and
three public/private checkpoint publications remain enabled. Replicas do not
continue training one another. All three have the same actions, masks,
likelihoods, targets and final model weights.

| PPO measurement | Seconds |
| --- | ---: |
| Complete process, median | 64.43 |
| Complete process, minimum–maximum | 64.06–64.87 |
| Collection, median | 62.04 |
| Model update, median | 1.18 |
| Three checkpoint publications, median | 0.051 |

Whole-process throughput is **7.95 decisions/second**. Collection accounts for
about 96% of elapsed time, whereas optimizer work is under 2%. Peak process RSS
is approximately 570–584 MB. Each replica has seven defeats and one quota cutoff,
with no failures or positive run reward. This measures the current policy's
workload, not successful learning or time to a competent agent.

One complete imitation repeat uses the existing 1,665 training decisions and 411
separate development decisions, the same combat-to-run transfer recipe, and 256
updates at batch size eight. It takes **421.00 seconds (7.02 minutes)** including
process startup. Data preparation takes **412.58 seconds**, broken down below
using exclusive timers so nested operations are counted once.

| Imitation preparation | Seconds |
| --- | ---: |
| Canonical loading and validation | 163.10 |
| Observation feature encoding | 197.01 |
| Vocabulary fitting, excluding canonical loading | 52.18 |
| Other preparation | 0.29 |

The actual 256 optimizer updates take **3.34 seconds**; four before/after corpus
evaluations take 3.96 seconds and checkpoint publication takes 0.034 seconds.
The packed training corpus occupies 1.082 GB; peak process RSS is 2.974 GB.
The current recipe decodes every training trajectory three times (manifest
checking, vocabulary fitting and encoding) and every development trajectory
twice. This repeat confirms the earlier pilot's data-preparation bottleneck.

The separate 128-decision profile matches the baseline's actions, likelihoods
and values. Of its 46.43 seconds of profiled collection, the public `from_dict`
path accounts for 36.01 cumulative seconds; `get_type_hints` is called 1,292,349
times and accounts for 18.69 cumulative seconds. These nested times overlap and
include profiler overhead. By comparison, model forward calls total 0.109
seconds and engine `apply` calls total 0.155 seconds in that profile. Repeated
public conversion/type resolution is the first optimization target suggested
by this measurement; the profile is not a throughput benchmark.

At this measured PPO workload, 10,000 decisions project to about 21 minutes,
100,000 to 3.50 hours, and one million to 34.96 hours. These are linear throughput
projections, not additional completed experiments. Longer campaigns accumulate
larger observations and can cost more per decision. The earlier complete
milestone-6 pilot took 23.90 minutes including demonstration collection and
evaluation; that figure is historical workflow timing, not a repeated benchmark.

Results and artifact bindings are retained in
[the benchmark evidence](evidence/training_time_benchmark_2026_09_29.json), with
raw reports and the one-shot script under
`runs/training-time-benchmark-20260929/`. To repeat the protocol, prepare a fresh
owner-only private directory containing a mode-0600 copy of the original
`runs/training-time-benchmark-20260929-private/seeds.json`, then run:

```bash
PYTHONPATH=. .venv/bin/python runs/training-time-benchmark-20260929/benchmark.py \
  --output-dir runs/training-time-repeat \
  --private-dir runs/training-time-repeat-private
```

Use fresh output and private directories; existing artifacts are not overwritten.
The script includes a separate 128-decision collection profile, excluded from
throughput statistics. No game/training implementation or accepted checkpoint
was changed, and no held-out test cases were used. The next performance task is
to reduce repeated public-observation conversion and validation, and reuse
prepared corpus features, while preserving boundary checks and exact action
mapping. No optimization is implemented by this benchmark.

The five benchmark workers completed in 662.96 seconds (11.05 minutes).
Post-run validation reloaded all 27 new canonical trajectories (1,664 actions)
in 20.17 seconds, verified identical public states/actions across the PPO
replicas, checked 42 private files' permissions, and confirmed unchanged source
and input identities with no partial artifacts. No gameplay suite or release
gate was needed for this measurement-only change.

### Training performance optimization (2026-09-29)

The first three measured passes reduced data-processing overhead while preserving
public observations, action mappings and numerical training results. The earlier
passes added bounded static schema-metadata caching, cheaper exact primitive
handling, and removal of redundant encoding validations. Their original
[source and timing evidence](evidence/training_optimization_2026_09_29.json) and
[second-pass evidence](evidence/training_optimization2_2026_09_29.json) remain
unchanged. The third pass reuses work within one observation or corpus preparation.

For standard combat and full-run PPO environments, a training-only encoder keeps
the freshly validated packed graph for the exact current decision object. Gym
padding and learned features share that graph; returned Gym arrays remain
independent copies. The retained pair is cleared before every encoding attempt
and when collection closes, including failures. Different decision objects cannot
reuse it. Custom environments, encoder subclasses and non-default capacities keep
the original independent encoding path. Standalone encoders still validate every
input; no arbitrary caller-supplied graph becomes a trusted feature input.

Full-run imitation opts into `corpus_paths(..., retain=True)`, which returns a
one-use handoff of the trajectories already validated against the manifest. The
loader reuses those snapshots for vocabulary fitting and feature preparation,
rechecks split, duplicate, task and reward constraints, and releases each decoded
episode as its examples are built. Retained snapshots refer to the bytes just
validated; later disk replacement cannot change them. A consumed handoff rejects
reuse. Ordinary path inputs still read and validate current files, once per
preparation. The default `corpus_paths()` result remains a list of paths. There
is no global or persistent disk cache.

The unchanged benchmark script, models, corpus, seeds and configuration were run
in fresh output directories on the same CPU with one PyTorch thread:

| Measurement | Original baseline | Second pass | Third pass |
| --- | ---: | ---: | ---: |
| Complete 512-decision PPO process, median of three | 64.43 s | 23.40 s | **19.24 s** |
| PPO decisions per second | 7.95 | 21.88 | **26.61** |
| PPO collection, median | 62.04 s | 21.06 s | 16.89 s |
| PPO model update, median | 1.18 s | 1.16 s | 1.16 s |
| Complete imitation process, one pass | 421.00 s | 124.35 s | **89.18 s** |
| Imitation data preparation | 412.58 s | 115.83 s | 80.47 s |
| Feature encoding within imitation preparation | 197.01 s | 41.97 s | 42.93 s |

The latest pass adds **21.6% PPO throughput**, with repeats spanning
19.21–19.26 seconds, and makes the imitation recipe **1.39× faster**. Across all
three passes, PPO is **3.35× faster** and imitation **4.72× faster** than the
original benchmark. Canonical trajectory loads fall from 37 to 13: once for
each of the 11 training and two validation files. Their loading/validation time
falls from 55.49 to 19.43 seconds. Vocabulary work takes 17.96 seconds and the
256 optimizer updates take 3.52 seconds. Feature extraction itself is unchanged.

In the separate 128-decision profile, graph packing drops from 260 to 131 calls
and full-run public parsing from 653 to 524 calls. Profiled timings include
instrumentation overhead and are excluded from throughput figures. Observation
processing and corpus preparation still dominate optimizer time.

Retention trades some memory for fewer parses. Peak imitation process RSS rose
from **3.002 to 3.155 GB** (5.1%); the packed training corpus remains 1.082 GB.
A separate fresh-process comparison of direct path loading with a frozen
vocabulary matched all labels, references and arrays for all 1,665 training
examples. Preparation took 53.96 seconds before and 54.31 seconds after, with peak
RSS rising from 2.239 to 2.359 GB. That path already loaded each file once when
using a frozen vocabulary; it has no measured speed benefit here. During
vocabulary fitting, all decoded trajectories are held together, so larger
corpora can require more memory than the prior streaming passes. These direct
loader checks are separate from the full training benchmark.

Validation passed **650 agent/package tests** in 290.93 seconds, the 14 new
focused regressions in 2.34 seconds, and compilation of `game` and `tests`.
The comparison against saved previous source matched 891 arrays, wire bytes and
reference mappings across all ten full-run contexts, a late-campaign state and
ten legacy examples in 3.76 seconds. Independent semantic review accepted the
change after checking custom-capacity fallback, identical rollout updates,
corpus equivalence, split/reuse rejection and file replacement behavior; its
independent probe took 0.983 seconds.

The final audit reloaded 27 canonical trajectories containing 1,664 actions.
Every public state/action and PPO training record, all 256 imitation numerical
update metrics and evaluations, and all 14 model weight sets match the previous
optimization exactly. Private permissions and incomplete-artifact checks passed.
Game rules, public schemas, objectives and model architecture are unchanged.
Inference bundles remain usable; exact training resumes retain the source-build
requirement. Historical checkpoints and evidence were preserved.

At this workload, 100,000 PPO decisions project to **1.04 hours** and one million
to **10.44 hours**, excluding extra evaluation. Longer campaigns can cost more per
decision. Three PPO replicas and one imitation pass provide timing evidence, with
uncontrolled OS file caches and background load. All PPO victory rewards remain
zero; these optimizations leave the measured playing behavior unchanged.

The [latest optimization evidence](evidence/training_optimization3_2026_09_29.json)
binds the source identities, inputs, validation and output artifacts. Raw results
are under `runs/training-optimization3-20260929/benchmark/`; the unchanged script
and fresh-directory procedure above reproduce the protocol. Benchmark execution
took 159.22 seconds (2.65 minutes), and the final artifact audit took 8.90 seconds.

### Parallel PPO collection (2026-09-29)

The `ppo` command supports `--workers 1` through `--workers 8` for both combat and
full-run tasks. The default remains one local collector, preserving the existing
serial sampling path. For example:

```bash
sts-agent-train ppo --checkpoint runs/run-imitation/final.sts-model \
  --config configs/training/full_run_ppo.json --output-dir runs/run-ppo-parallel \
  --workers 4 --decisions 2048 --time-limit 600
```

With multiple workers, the parent owns Adam and the update RNG. Spawned processes
each use one Torch thread and perform simulation, public encoding, inference and
recording locally. They persist between rounds and receive a copied snapshot of
the same behavior policy for each round. Completed public feature batches return
through pipes; transfer threads leave the parent responsive to cancellation and
deadlines. The parent merges batches by worker index and then performs the PPO
update. A worker failure discards the round and closes the entire pool, with no
retry or update from a successful subset. Completed recordings remain available;
interrupted recordings remain `.partial`.
On interruption, progress counts include only workers that returned a result;
other workers may have left recordings that are absent from the stopped report.

`rollout_steps` and `--decisions` remain **total** budgets. A 512-decision rollout
with four workers gives each worker 128 decisions, not 512. The last local episode
closes at that quota and bootstraps its actual final observation; GAE never crosses
a worker's episode boundary. Smaller per-worker horizons can reduce the chance
of observing a full-run victory, so choose a larger total rollout when longer
campaigns need to finish. Throughput alone does not establish learning quality.

The parent draws worker action seeds in stable index order from its private action
generator. Each worker reserves a disjoint range of episode indexes as large as
its decision quota. The next committed cursor skips the whole reserved range,
including unused indexes. Region/encounter selection uses a separate schedule:
`iteration * active_workers + worker_index`, advancing by `active_workers` for
each local episode. This avoids seed-range strides repeatedly selecting the same
region. Seeds and cursors remain private and never become policy inputs or public
progress fields. Results are independent of worker completion order when time
limits do not interrupt collection.

Worker count is an execution option rather than a new field in existing PPO JSON
configs or inference manifests. Existing inference bundles still load. Exact
resume requires the saved worker count, allocation schedule, source, runtime and
rollout boundaries. Worker RNGs and games are recreated each round, so idle
processes hold no additional resume state. Python callers should use
`with PPOLearner(..., workers=4) as learner:` or call `close()`; executable scripts
using spawn need the usual `if __name__ == '__main__':` entry-point guard.

The fixed-budget benchmark used the same initial model, mixed-region config and
private starting plan for three fresh invocations of each worker count, on the
same 18-logical-CPU arm64 host. Every invocation trained 1,024 decisions in two
512-decision rounds, including recording, optimization and checkpoints. Workers
were reused for round two. The table reports medians; complete invocation times
also include Python startup and pool cleanup.

| Workers | Complete 1,024-decision invocation | First collection, 512 decisions | Warm collection, 512 decisions | Invocation speedup |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 37.37 s | 16.69 s | 17.15 s | 1.00× |
| 2 | 21.45 s | 9.03 s | 8.81 s | 1.74× |
| 4 | 14.09 s | 5.51 s | 4.86 s | 2.65× |
| 8 | 10.40 s | 3.86 s | 2.73 s | 3.59× |

Four workers reached **72.67 decisions/s** and eight reached **98.48 decisions/s**,
including invocation overhead. Updates stayed around 1.13–1.17 seconds each.
Within each worker setting, all three replicas produced identical numerical
rollouts and final weights. Across settings, game samples and local cutoffs differ,
so the main table compares a fixed decision budget, not identical trajectories.
An additional comparison executed the four-worker first-round jobs sequentially:
it took **17.13 seconds** versus the parallel median of **5.51 seconds**. All 512
public states/actions, masks, likelihoods, values, rewards and GAE results matched.
That single reference timing confirms a collection speedup on identical game work.

Start with four workers when enabling parallelism; eight was fastest in this
measurement. More processes use additional memory, and total pool RSS was not
measured. The default remains one worker to preserve existing experiments.
The first serial rollout and updated weights also match the previous optimization
exactly. All measured full-run victory rewards remained zero, and more workers
caused more quota cutoffs; this is throughput evidence, not improved playing strength.

The [parallelization evidence](evidence/training_parallelization_2026_09_29.json)
binds source, inputs, timings and validation. Raw results and reproduction scripts
are in `runs/training-parallel-20260929/`. The 12 benchmark invocations took
248.91 seconds. An artifact audit validated 231 canonical trajectories containing
12,288 actions, restored all 48 published checkpoint pairs, and checked permissions
on 298 private files. It took 52.18 seconds while the regression suite ran.
No partial benchmark artifacts or reused training reset seeds were found.
The independent semantic review took 272 seconds and found no blocking issue.
Final validation passed **665 agent/package tests in 322.42 seconds**, with the
same three Gymnasium observation-space warnings as before, and compilation of
`game` and `tests`. Focused tests exercise real spawned workers, exact resume,
frozen probabilities, seed/scenario coverage, worker crashes, blocked pipe sends,
spawn interruption, forced cancellation/deadlines and installed CLI SIGTERM.
Game rules, public observations, reward objectives and model architecture are
unchanged. Inference compatibility is retained; historical evidence was preserved.

## Milestone 7: usable commands and final delivery checks

The installed `sts-agent-train`, `sts-agent-evaluate` and checkpoint playback
commands were added incrementally through milestones 1–6. This milestone verifies
their delivery from a built wheel in fresh environments, including configuration
errors, finite execution, exact resume, reports and worker propagation. The default
heuristic path and canonical recording semantics remain unchanged.

Two delivery fixes were needed. Checkpoint playback now reports the missing
`sts-agent[train]` extra as a structured failure instead of a Python traceback.
Malformed curriculum JSON now receives a parser error before any output is
created; partial nested PPO settings still use their existing defaults. Unexpected
import failures continue to propagate, so optional-dependency guidance cannot
hide unrelated defects.

Install `'.[train]'` for training and checkpoint commands, or `'.[dev,train]'`
to include the Python test suite. Core installation has no runtime dependencies;
ordinary heuristic playback and every command's help work without NumPy, Gymnasium
or Torch. The installed commands use the canonical `game` package.

| Workflow | Main report | Delivery checks |
| --- | --- | --- |
| `sts-agent-train collect` / `collect-run` | `demonstrations.json` / `run-demonstrations.json` | Separate training/validation corpora; finite episodes; declared assisted fixtures |
| `sts-agent-train imitate`, with optional `--full-run` | `imitation.json` | Initial/final bundles, combat actor transfer, exact resume with matching private state |
| `sts-agent-train ppo` | `ppo.json` | Complete-update checkpoints, total decision/time budgets, 1–8 collectors, saved worker count on resume |
| `sts-agent-train curriculum` | `curriculum.json` | Three distinct learners through five finite stages; stage collection remains serial |
| `sts-agent-evaluate` | `baseline.json`, `hybrid.json`, `full-run.json` or `benchmark.json` | Paired policies, frozen populations, development selection and locked held-out evaluation |
| `sts-agent-play --combat-checkpoint` / `--checkpoint` | Command summary and canonical trajectories | Correct task routing, two-worker playback and explicit task-mismatch errors |

Use a fresh output directory per invocation. Public inference bundles and reports
are separate from owner-only resume files and replay audits. Exact resume requires
matching implementation sources, runtime, corpus/objective and worker allocation.
These remain deliberate compatibility checks; this milestone adds no migration
of historical optimizer/RNG state.

The clean-install smoke used Python 3.11.15 on macOS arm64, Torch 2.13.0,
NumPy 2.4.6 and Gymnasium 1.0.0. Both fresh virtual environments disabled system
site packages, installed offline from exact cached dependency wheels and passed
`pip check`. Commands ran from a neutral directory with `PYTHONPATH` removed;
their imports came from the installed wheel. The core and training installations
took 1.61 and 9.38 seconds respectively. This is the tested platform and dependency
combination, not an executed cross-platform or Python 3.10 matrix.

All **48 installed-command smoke checks passed in 69.03 seconds**. Combat and
full-run imitation, plus two-worker PPO for both tasks, matched uninterrupted
training exactly after resume: model tensors, optimizer state, RNG and cursors.
Inference ZIP timestamps can differ even when these learning states match.
A separate installed two-worker SIGTERM check returned exit 130, removed its
process group and restored its last complete checkpoint; the check took 2.94 seconds.

The artifact audit validated **222 canonical trajectories with 539 actions**,
**190 combat sidecars**, all **77 inference/private checkpoint pairs**, and
permissions on **332 private files** in 6.02 seconds. It found no partial artifacts
in the completed smoke outputs and verified every packaged game source against
the checkout. The tiny decision limits, including a separate disposable frozen
benchmark, establish integration only and add no playing-strength evidence.

The two fixes passed 33 focused tests in 22.38 seconds and an independent semantic
review in 188 seconds. Final validation compiled `game` and `tests` and accounted
for all **8,447 collected tests**. The first broad invocation reported 5,063 passes
and one localhost-permission failure before its 20-minute command limit. The
remaining 3,383 tests passed in 361.98 seconds; the continuation starts at the
first unreported case, with the completed prefix retained. The synthetic socket
fixture passed separately in 0.01 seconds with loopback permission. It never
contacted a live bridge, and no source fix was needed. No code failures remain.

The [delivery evidence](evidence/training_delivery_2026_09_29.json) binds the
tested wheel, source identity, dependency versions, validation logs and a manifest
of 1,051 retained artifacts in `runs/training-milestone7-20260929/` and its separate
cancellation outputs. Temporary installation environments were removed after
validation. Initial investigation, implementation, packaging and review overlapped
over 475 seconds before the final gates; separate implementation time was not
measured. These headless checks required no native build or live game launch.

## Staged learning diagnostic (2026-09-29)

The follow-up comparison is complete. Its largest observed regression occurs
during PPO, with a separate non-combat selection failure already present before
PPO. This is a diagnosis of one retained checkpoint lineage on four fresh
development cases; it does not establish population playing strength.

The protocol froze five retained checkpoints, four validation cases (two genuine
Ironclad A0 starts in each first-act region), eight controller configurations and
the probe before execution. Each controller received the same campaign seed and
region within a case. Hybrids used the runner's authoritative combat ownership;
learned policies received only public decisions. Limits were 1,024 decisions and
90 seconds per episode, with a 30-minute total cap. No training, checkpoint
selection, held-out evaluation, objective change or native game access occurred.

All **32 episodes** completed their declared execution, recording **9,350
decisions** in **507.45 seconds**. There were 26 defeats, six decision-budget
cutoffs and no wins, failures, time cutoffs or omitted pairs. The heuristic's
mean last observed floor was 11.00. The table includes floor-zero cutoffs in its
means; these figures are descriptive progress measures, not victory estimates.

| Frozen actor | Mean floor: learned combat, heuristic elsewhere | Mean floor: learned at every decision | Full-policy cutoffs |
| --- | ---: | ---: | ---: |
| Original combat checkpoint | 11.25 | Not evaluated | — |
| Transferred actor, before imitation | 11.00 | 1.75 | 3/4 |
| Full-run imitation | 10.75 | 2.75 | 3/4 |
| Final mixed-region PPO | 1.25 | 1.50 | 0/4 |

All six cutoffs occurred on floor zero in a relic card selector. Their final
32 actions alternated between selecting and deselecting a card; confirmation was
legal after selection. The initial actor transfer and 256-update full-run imitation
therefore did not reliably complete this interaction under greedy playback.
Ending the loop is a distinct requirement from improving combat.

The fixed common-state panel used the first 64 combat-context and 16 other
decisions from each heuristic campaign: **320 public decisions** scored by all
five checkpoints. It includes the intermediate Overgrowth PPO checkpoint, which
was not a separate campaign controller. These groups describe public context
labels; hybrid routing also handles nested combat ownership. Teacher agreement
measures behavior on the teacher's states and is not a gameplay score.

| Stage | Teacher agreement on 256 combat states | End turn with energy and a legal card play, out of 193 opportunities |
| --- | ---: | ---: |
| Original combat | 122/256 | 0/193 |
| Transferred actor | 120/256 | 2/193 |
| Full-run imitation | 209/256 | 0/193 |
| Overgrowth PPO | 182/256 | 0/193 |
| Final mixed-region PPO | 60/256 | 22/193 |

Imitation and Overgrowth PPO chose the same action on 225/256 combat states;
imitation and final PPO agreed on only 60/256. On those same states, mean action
entropy rose from 0.8661 after imitation to 1.2206 after Overgrowth PPO and 1.5399
after mixed-region PPO. This locates the largest sampled behavior change between
the two saved PPO stages. It does not isolate changing regions as the cause:
region mixture and additional optimizer updates changed together. The end-turn
measure is a warning sign, not proof that every available card was useful.

The transfer itself copied all **29 shared/actor tensors**, the unknown embedding
and all **156 existing token embeddings** exactly. Expanding the vocabulary to
974 names added 818 randomly initialized embeddings, which can change inputs
even when shared weights are preserved. The transferred actor changed 13/256
combat choices and 16/320 overall choices relative to the source. A separately
identified shadow actor replaced only the new embeddings with the original
unknown embedding. It reproduced all 320 original choices and every probability
exactly. This isolates the vocabulary contribution on the fixed panel; it does
not measure its causal effect on campaign outcomes. The shadow was never trained,
published as a deployable checkpoint or used for campaign decisions.

The saved PPO audit covers all **2,048 training decisions in four batches**.
Every recorded reward, advantage, return, value and next value was exactly zero.
Both policy loss and value MSE were zero throughout the reported updates; total
loss matched the entropy term within 3.1e-10. The fresh PPO optimizers still made
**160 optimizer steps**, driven by entropy regularization with weight 0.01.
The agent received no sampled victory signal directing those changes. All four
updates reached the KL stopping threshold, with final approximate KL values
0.31425, 0.06393, 0.19049 and 0.03666 against a target of 0.03. This check runs
after each epoch and does not roll back that epoch. The full-run critic remained
zero on the probe; the combat critic estimates a different objective and its
values are not compared as calibrated run-victory probabilities.

The [diagnostic evidence](evidence/training_stage_diagnostic_2026_09_29.json)
binds the protocol, checkpoint hashes, paired episode results, public trajectories,
private audit digests, probe, scripts and PPO source reports. The canonical loader
validated all 32 new trajectories, and their replay audits verified pairing and
owner-only permissions. Source and model bytes remained unchanged. Analysis and
validation took 104.67 seconds; independent read-only reviews checked campaign
routing, the shadow control, metric denominators and the zero-signal attribution.
Raw artifacts are retained in `runs/training-stage-diagnostic-20260929/` with
separate private replay data. No production behavior changed in this experiment.

## Configurable full-run rewards

Full-run PPO now accepts `sts_full_run_reward_v2`. Set the finite weights in
`training.reward.weights` inside the existing PPO experiment configuration.
All supported components are measured even when their weights are zero. Unknown
names and malformed values reject before training. The historical v1 objective
and checkpoint identities remain unchanged and loadable for inference.

| Component | Measurement on one reconciled action | Example weight |
| --- | --- | ---: |
| `run_victory` | 1 at actual run victory | 1.0 |
| `run_defeat` | 1 at actual run defeat, including lethal events | -1.0 |
| `run_abandoned` | 1 at explicit abandonment, distinct from defeat | -1.0 |
| `combat_win` | 1 when a newly completed fight reports victory | 0.1 |
| `combat_loss` | 1 when a newly completed fight reports defeat | 0.0 |
| `win_hp_fraction` | HP / max HP after victory cleanup and automatic healing; 0 otherwise | 0.025 |
| `end_turn_action` | 1 on the accepted `end_turn` command | -0.001 |
| `potion_use_action` | 1 on accepted manual potion use, including outside combat | 0.0 |

These example weights are in
[`full_run_shaped_ppo.json`](../configs/training/full_run_shaped_ppo.json).
They are an editable starting configuration, not tuned performance results.
Omitted weights default to zero except `run_victory`, which defaults to 1.
Components add together: setting both `combat_loss` and `run_defeat` to -1
gives -2 for a fatal fight. The example assigns its terminal penalty through
`run_defeat` and leaves `combat_loss` at zero.

For example, winning a fight at 46/80 HP pays `0.1 + 0.025 × 46/80 = 0.114375`.
The campaign continues; reward collection does not pay for the same fight again.
Nested card/potion confirmations do not repeat the potion-use component, and
automatic revival does not count as manual potion use. Fights that finish during
room entry also report their confirmed result. Decision/time cutoffs are not
defeats; an executed combat win can still earn reward on the same step as a
nonterminal cutoff. Invalid, stale, uncertain and action-free cutoff attempts
produce no training reward measurement.

Start a new shaped experiment from a full-run imitation checkpoint with an
explicit objective reset and adoption of the preset's single-card policy:

```bash
sts-agent-train ppo \
  --checkpoint runs/full-run-milestone6-20260929/imitation/final.sts-model \
  --config configs/training/full_run_shaped_ppo.json \
  --reset-objective --reset-action-policy \
  --output-dir runs/full-run-shaped --decisions 512 --time-limit 300 --workers 2
```

`--reset-objective` requires different full-run objectives. It copies the actor
and frozen vocabulary exactly, initializes a fresh value head with zero output,
and starts fresh optimizer/RNG/counters. It records both objectives and the source
checkpoint in `ppo.json`. The critic now predicts the configured shaped return,
which is not a calibrated run-victory probability. The original checkpoint is
preserved. Direct combat-to-run transfer still goes through the existing full-run
imitation command.

The preset also enables the [shared policy-action layer](#shared-policy-actions-and-selection-order).
For subsequent training with the same objective and action policy, omit both reset flags.
Exact resume additionally supplies the matching `--resume-state`; changing
weights or resetting the objective during resume rejects. As before, historical
private optimizer states require their exact implementation/runtime to resume;
compatible inference weights can initialize a new experiment. Worker allocation
and total decision-budget semantics are unchanged.

`FullRunTrainingEnv` wraps the existing campaign environment for v2 PPO only.
It uses the adapter's allowlisted combat result and post-hook HUD measurements.
Structured policy observations and game rules are unchanged. Each shaped PPO
batch publishes `sts_ppo_rollout_v2` for the unrestricted action policy, or
`sts_ppo_rollout_v3` for the filtered policy, retaining the resolved objective, weighted
reward, individual components, and before/after public combat summaries. Its
episode rows bind those actions to canonical trajectory hashes. Components can
be rescored explicitly with `RewardSpec.shaped_full_run(new_weights).evaluate(...)`;
that does not alter the recorded objective or the original artifacts.

Canonical trajectories and `FullRunEnv` keep their original +1/0 run-victory
reward. Full-run demonstration value labels also retain their original objective;
old records are not retroactively given missing combat measurements. Evaluation
and playback accept v2 full-run checkpoints. Evaluation still compares actual
genuine-start run victories and records the training objective separately from
the evaluation objective. Higher shaped return alone is not evidence of stronger
campaign performance.

Validation for this change passed all 692 agent/package-layout tests in 327.05
seconds, Python compilation, and an independent semantic review of reward
boundaries, public measurements and objective transfer (145 seconds). An installed
two-worker PPO smoke trained on 128 accepted decisions in 3.16 seconds: six combat
wins produced a shaped return of 0.702319 and 103 nonzero advantages, with zero
full-run victories. Both episodes ended at decision cutoffs. Installed evaluation
and playback also accepted the shaped checkpoint. The 0.52-second artifact audit
verified exact actor transfer, all reward/action joins, canonical trajectories,
checkpoint identity and private-file permissions. Raw reports and validation
output are retained in `runs/full-run-rewards-20260929/`. This verifies training
integration, not improved playing strength; a larger training experiment has not
been run for these weights.

## Shared policy actions and selection order

The shared [`action_policy.py`](../game/agent/action_policy.py) layer restricts
policy choices over the complete public decision. It does not change native
legality, the canonical adapter, candidate order or game rules. The current
`commit_card_selection_v1` policy blocks undo in known deferred selectors:

- Combat manual selections, relic card selections, Meat Cleaver Cook and Sea Glass
  retain every unselected pick up to the maximum. Selected cards cannot be
  deselected; Sea Glass's selected `choose_relic_reward` actions count as undo.
- Confirmation stays a separate recorded and budgeted command, available whenever
  the minimum is satisfied. Optional zero-card confirmation remains available,
  and meeting the minimum does not force completion before the maximum.
- Every ordered final selection is reachable from a newly opened empty selector
  by choosing its members in that order and confirming. Picks are never sorted.
  Attached selections commit their inherited members too; native free-slot reuse
  still determines the order when an attachment already contains selection holes.
- Bounds, selected membership and the complete pick/undo/confirm action set must
  match a recognized selector. Immediate choices and unknown shapes stay unchanged.
  Cook cancellation and potion actions remain legal, so this prevents selection
  toggles rather than guaranteeing progress through every navigation action.

The Act 1 and shaped full-run presets enable this policy. It is versioned
separately: existing checkpoints keep their original behavior, and historical
recordings are not rewritten. All-legal and original singleton policy identities
retain their existing serialization. An explicit policy reset transfers weights
to a new experiment; it cannot be combined with exact optimizer resume.

The original `commit_single_card_v1` policy remains supported unchanged. It
prevents a mandatory single-card select/deselect loop:

1. The public selector must explicitly require exactly one card, with integer
   `minimum == maximum == 1` and manual confirmation.
2. Exactly one card must be selected. The only legal candidates must be that
   card's deselect action and the matching confirmation.
3. The last recorded public action must have selected that exact card in the
   same action family. A fresh attachment to a preselected engine state without
   that history keeps its undo action.
4. The policy mask then permits only confirmation. Selecting and confirming
   remain two separate, recorded and budgeted engine steps. A one-step budget
   can stop after selection; no hidden confirmation runs after the cutoff.

That original policy recognizes combat/rest `select_card`, `deselect_card`,
`confirm_selection`, and relic `choose_relic_card`, `deselect_relic_card`,
`confirm_relic_selection`. This is a structural rule over public fields, including
cases whose bounds become one after eligibility is capped. Empty selectors,
optional selections, multiple-card choices, immediate choices and unknown shapes
retain their full legal support. The filter neither sorts cards nor confirms an
optional selector as soon as its minimum is met.

The same function supplies the mask to imitation features, PPO sampling and
updates, worker models, evaluation and checkpoint playback. The canonical graph
and trajectories still expose every legal candidate. Filtered PPO rollout v3
(v4 for the Act 1 objective) records both `legal_mask` and `policy_mask`; replay verifies the policy version,
the chosen action and its sampling support. A forced confirmation has probability
one, log probability zero and entropy zero. Imitation rejects demonstrations with
excluded actions rather than silently dropping or relabelling them.

Unrestricted checkpoints and configurations use `all_legal_v1`, retaining their original
serialization and identities. New filtered checkpoints use inference bundle v3
and bind the action-policy version to corpus, experiment, behavior and resume
identities. Exact resume cannot change that policy. To enable it:

- For new imitation, add `--action-policy commit_card_selection_v1` to the existing
  `sts-agent-train imitate` command, including full-run imitation when applicable.
- For PPO, use experiment schema `sts_ppo_experiment_v2` with
  `training.action_policy` set to `commit_card_selection_v1`. The shaped full-run
  example configuration already does this.
- When the source checkpoint has a different action policy, add
  `--reset-action-policy`. This starts a new experiment with copied model weights
  and fresh optimizer, RNG and episode cursor; the source checkpoint is preserved.
  Add `--reset-objective` as well only when changing the full-run reward objective,
  which also resets the critic. Omit either flag when its setting is unchanged.
- Combat curriculum stages inherit their initial checkpoint's action policy.
  Inference loads it from the checkpoint; there is no separate playback override.

### Inventory of current headless card selectors

This inventory covers the current headless catalog and command families. It is a
source audit with focused engine tests, not a new live-game equivalence claim.
Counts below describe card definitions, not every possible eligibility, upgrade
or power-stack state. The core selection implementation caps bounds to eligible
cards and sometimes resolves the only required set without opening a choice.

There are **40 direct card-selector definitions**: eight immediate choices and
32 definitions using explicit toggle/confirm selection.

| Family | Definitions and selection bounds |
| --- | --- |
| Immediate hand choice (5) | Base Armaments; upgraded True Grit; Brand; Burning Pact; Scavenge. Each choice applies immediately. Upgraded Armaments and base True Grit do not ask for this choice. |
| Immediate pile choice (3) | Headbutt, Wish, Hologram. Each resolves one pick immediately. |
| Other explicit cards (2) | Neow's Fury: 0–2, upgraded 0–3, capped by hand space. Dual Wield: exactly one eligible attack/power. |
| Colorless explicit cards (7) | Discovery and Splash: 0–1; Purity: 0–3, upgraded 0–5; Secret Technique, Secret Weapon, Seeker Strike and Thinking Ahead: one. |
| Silent explicit cards (7) | Acrobatics, Dagger Throw, Survivor, Hand Trick and Nightmare: one; Hidden Daggers: two; Prepared: one, upgraded two. |
| Regent explicit cards (9) | Begone, Cosmic Indifference, Decisions Decisions, Glimmer, Photon Cut and Heirloom Hammer: one; Charge: two; Guards: 0–all eligible; Quasar: 0–1. Glimmer and Photon Cut put one card on the draw pile per selection. |
| Necrobinder explicit cards (7) | Cleanse, Graveblast, Sculpting Strike, Seance, Snap and Transfigure: one; Dredge: up to three required picks, capped by remaining hand space and eligibility. |

Other sources use the same core toggle/confirm mechanism:

| Source | Definitions and bounds |
| --- | --- |
| Potions (9) | Ashwater: optional exhaust; Gambler's Brew: optional discard/redraw; Droplet of Precognition, Liquid Memories and Touch of Insanity: one; Attack, Skill, Power and Colorless Potions: 0–1 generated offer. |
| Powers (6) | Entropy, Stratagem, Tools of the Trade, Foregone Conclusion and Tyranny: required picks based on stacks, capped by eligibility; Well-Laid Plans: 0–stacks retained cards. |
| Combat relics (3) | Toolbox: 0–1 generated offer; Gambling Chip: 0–all discard/redraw; Choices Paradox: one generated offer. Crossbow resolves automatically and is not a selector. |
| Monster | Knowledge Demon: one curse offer. |

The **20 persistent relic pickup selectors** are defined in
[`pickup.py`](../game/headless/relics/pickup.py) and
[`ancient_pickups.py`](../game/headless/relics/ancient_pickups.py).
Bounds are capped by eligibility.

| Operation | Relics and requested counts |
| --- | --- |
| Clone | Dolly's Mirror: one. |
| Transform | New Leaf: one; Astrolabe: three, then upgrade the replacements. |
| Remove | Biiig Hug: four; Empty Cage: two; Precarious Shears: two, then damage; Precise Scissors: one; Preserved Fog: three, then add Folly. |
| Upgrade | Pomander: one; Yummy Cookie: four. |
| Enchant | Beautiful Bracelet: three; Electric Shrymp: one; Gnarled Hammer: 0–3; Kifuda: 0–3; Pael's Growth: one; Punch Dagger: one; Royal Stamp: one; Tri-Boomerang: three. |
| Replace/store | Claws: 0–6 attribute-preserving Maul replacements; Pael's Tooth: store five cards. |

Other card-choice surfaces have distinct command or completion rules:

| Surface | Current behavior |
| --- | --- |
| Sea Glass | Choose 0–15 generated offers, then confirm. Both selection and deselection use `choose_relic_reward`; selected links distinguish them. Acquisition hooks execute in selected order. The current commitment policy excludes selected-offer toggles. |
| Meat Cleaver Cook | Select two cards at rest, then confirm, or cancel. Removing the same pair and applying the fixed max-HP gain commute in current code. The current policy blocks deselection and retains cancellation and potion actions. |
| Smith and shop removal | One immediate pick, with cancel where legal, including mandatory Lord's Parasol smithing. No selected-set confirmation loop. |
| Event deck choices | The shared Steps/Flow system and specialized Aroma of Chaos, Morphic Grove, Sapphire Seed, Wellspring and Whispering Hollow paths. Steps applies each pick immediately. Morphic Grove collects two picks before transforming them; their order can affect RNG results. |
| Card/removal rewards and event offers | Immediate choice/skip, or successive distinct choices where the event allows several. Acquisition order and hooks can matter; these are not all toggle selectors. |

The Steps/Flow deck-choice callers are Luminous Choir, Wood Carvings, Self Help
Book, Amalgamator, Doors of Light and Dark, Field of Man-Sized Holes, Grave of the
Forgotten, Spiraling Whirlpool, Spirit Grafter, Symbiote, Waterlogged Scriptorium,
Zen Weaver, Stone of All Time, Endless Conveyor and Trial. Their branches are in
[`act1_content.py`](../game/headless/events/act1_content.py),
[`roster.py`](../game/headless/events/roster.py),
[`minigames.py`](../game/headless/events/minigames.py) and
[`social.py`](../game/headless/events/social.py).

### Selection order is not universally interchangeable

The engine keeps selection order in
[`core/choices.py`](../game/headless/core/choices.py) and applies ordered effects
when confirming. Four regression tests in
[`test_selection_order.py`](../tests/agent/test_selection_order.py) show:

| Interaction | Same selected cards, different order |
| --- | --- |
| Neow's Fury | Strike then Defend versus Defend then Strike produces the corresponding hand order. |
| Astrolabe | With seed 2 and the same Strike, Injury and Secret Weapon selected, one order produces Sword Boomerang, Curse of the Bell and Panic Button; the reverse produces Splash, Curse of the Bell and Mangle. RNG is consumed per selected card. |
| Purity | Exhausting Drum of Battle then Strike versus the reverse, with Dark Embrace and a later Void draw, leaves **1 versus 2 energy**. Exhaust and draw hooks interleave. |
| Gambling Chip | Discarding Abrasive then Untouchable versus the reverse leaves **7 versus 6 block** through Sly autoplay. |

Simple deck removal, upgrading and enchanting the same selected identities
commute in the current pickup implementation. That does not generalize to ordered
draw/discard/exhaust effects, card acquisition or transformations. Claws can append
modified replacements in selected order. Pael's Tooth sorts by definition ID, but
equal-ID modified cards retain their relative selection order.

Order sensitivity does not make undo necessary for these deferred selectors.
Only confirmation applies their effects, so each final ordered subset has a
direct sequence of picks from an empty selector. The
[`commit-selection tests`](../tests/agent/test_commit_selection.py) exhaust the
native slot states for a three-option, zero-to-two-card Neow's Fury choice and
reach all ten ordered outcomes without undo. The four order-sensitive examples
above also run through the current policy. Attachment tests retain native slot
reuse without sorting inherited selections. This is headless evidence, not a
new live-game comparison.

Validation passed **723 agent/package-layout tests in 337.95 seconds**, including
31 new policy/selection-order cases, plus Python compilation. Tests cover real
selectors, separate select/confirm execution, cutoffs, policy-mask likelihoods,
serial and parallel PPO, imitation, exact resume, malformed versions and all
curriculum stages. Independent source/order review took 390 seconds; independent
implementation review, including the final corrections, took 403 seconds. Both
reviews closed without remaining blockers.

An installed two-worker PPO integration smoke completed 128 decisions in 3.73
seconds, followed by installed playback and evaluation. The 1.77-second artifact
audit checked all 128 recorded policy masks against canonical public decisions,
unchanged actor transfer, reward joins, checkpoint identity, eight further
trajectories and private-file permissions. This campaign smoke did not encounter
a filtered selector; the focused tests exercise those in both serial and parallel
collection. A read-only check of the three earlier imitation-loop observations
confirmed that identical actor weights now choose confirmation with probability
one where the original checkpoint chose deselection. These are immediate-decision
checks, not complete campaign reruns or evidence of improved win rate. Reports,
the audit script and validation log are retained in
`runs/policy-actions-20260929/`. No longer training experiment or native launch was
performed for this change.

## PPO signal guard and three-learner pilot

Every new PPO update now applies `skip_zero_signal_v1`. If all raw GAE advantages
are exactly zero, the learner replays the full rollout through the current model
and validates its original candidates, masks and chosen actions. It skips the
optimizer only if every current value prediction also exactly matches its return
target. The check counts residuals directly: a tiny nonzero error can have a
squared error that underflows to zero, and must still train. There is no threshold
that discards weak signals. Zero immediate rewards alone do not cause a skip;
bootstrapped value differences can still provide learning signal. Conversely,
an already perfectly predicted nonzero terminal reward can have no learning signal.

A skipped rollout performs no optimizer step, leaves all model tensors and Adam
state unchanged, and consumes no optimizer-shuffle RNG. It still advances the
completed-rollout count, processed-decision count and episode cursor so the next
collection uses fresh games. Cancellation or deadline expiry during validation
cannot commit that progress. This is a whole-rollout rule; updates containing
any learning signal continue to use the configured entropy regularization.

Each update records its status, skip reason, counts of nonzero advantages, return
targets and rewards, and the number of replayed value errors when that check is
needed. Reports separate `processed_decisions`, `trained_decisions`,
`skipped_decisions` and `skipped_updates`. Private PPO resume schema v3 binds the
update policy and skipped-iteration count. Its counter checks distinguish completed
rollouts from actual optimization iterations; old v1/v2 states retain their
original validation rules. Inference compatibility is unchanged, and exact resume
still requires matching sources and runtime.

The bounded development pilot uses the original full-run imitation actor, the
existing shaped reward preset and `commit_single_card_v1`. Its protocol was frozen
before campaign execution, including source, configuration, script and checkpoint
hashes plus a separate private seed registry:

- Sixteen genuine Ironclad A0 starts compare the original and filtered policies
  with identical model tensors and vocabulary; only the action-policy version
  differs. Eight starts use Overgrowth and eight use Underdocks.
- Three learners each receive 5,120 PPO decisions with two collectors, unchanged
  reward weights and hyperparameters, disjoint training episode ranges, and fresh
  optimizer/RNG state. The actor is retained and the shaped critic starts fresh.
  A 512-decision rollout is divided between the two workers, so a collected
  episode receives at most 256 decisions before its quota closes.
- Sixteen different starts, frozen at the same time, compare the filtered
  initializer with all three final checkpoints. Every final checkpoint is
  reported; there is no best-checkpoint selection or tuning on these cases.
- Campaign attempts have 4,096-action and 90-second limits. Cutoffs, defeats,
  abandonment and victory remain distinct, and every planned case stays in the
  denominator. Exact canonical replays measure confirmed combat outcomes using
  the adapter's allowlisted summary; replay seeds and engine state never enter
  the actor. Floor progress and shaped return are secondary measures.

The protocol and raw artifacts live in `runs/training-readiness-20260929/`, with
private data in its separate owner-only sibling directory. This is development
evidence in one imitation lineage, not held-out performance or native-game validation.

The paired filter comparison completed all 32 campaign attempts in 852.50 seconds,
including canonical replay and outcome analysis:

| Policy on the same 16 starts | Run wins | Selector-loop cutoffs | Mean last observed floor | Confirmed combat wins |
| --- | ---: | ---: | ---: | ---: |
| Original imitation | 0/16 | 5 | 7.69 | 49 |
| Identical actor with single-card commitment | 0/16 | 0 | 11.06 | 74 |

All five original cutoffs were floor-zero selection loops at the time limit. The
filter let those campaigns proceed; all filtered campaigns eventually ended in
defeat. The other eleven pairs had identical outcomes, floors and combat-win
counts. This establishes a progress benefit on the paired cases, without evidence
of increased run win rate.

All three shaped learners completed their 5,120-decision budget in ten batches.
The initial batches contained a few zero advantages; every later batch contained
512 nonzero advantages. No batch met the skip criterion, and no episode failed.

| Learner | Training seconds | Nonzero advantages / decisions | Confirmed combat wins during collection | Training defeats / quota cutoffs |
| --- | ---: | ---: | ---: | ---: |
| 1 | 107.58 | 5,114 / 5,120 | 210 | 42 / 19 |
| 2 | 105.00 | 5,109 / 5,120 | 204 | 38 / 20 |
| 3 | 105.98 | 5,114 / 5,120 | 213 | 38 / 20 |

Training took 318.57 seconds in total and produced no complete-run victories.
These collection results show that the shaped objective supplies learning signal;
they do not measure playing-strength improvement. Quota cutoffs bootstrap the
last ready observation and are recorded separately from defeats. The two-worker
256-decision episode horizon also limits exposure to later campaign decisions.

The separate final comparison completed all 64 planned campaign attempts in
844.87 seconds, including canonical replay and outcome analysis:

| Policy on the same 16 evaluation starts | Run wins | Time-limit cutoffs | Mean last observed floor | Confirmed combat wins |
| --- | ---: | ---: | ---: | ---: |
| Filtered initializer | 0/16 | 1 | 9.63 | 70 |
| Learner 1, final checkpoint | 0/16 | 0 | 10.31 | 93 |
| Learner 2, final checkpoint | 0/16 | 2 | 9.94 | 77 |
| Learner 3, final checkpoint | 0/16 | 0 | 10.69 | 86 |

Every non-cutoff campaign ended in defeat. The paired mean-floor differences
are +0.69, +0.31 and +1.06 respectively. These are descriptive progress gains;
all run-win differences remain zero with conservative paired 95% bounds of
approximately ±67.91 percentage points. The pilot establishes neither improved
run win rate nor equivalence. Do not compare these floor averages directly to
the earlier filter panel, which uses different seeds. No checkpoint was selected
or promoted from this development comparison.

The initializer's timeout was an optional, manually confirmed move-to-hand
selection with minimum zero and maximum two at floor 2. All three trained
policies completed that selection and later lost the campaign. Learner 2 instead
timed out on two other seeds by repeatedly opening and closing the same card
reward. Those reward-navigation loops were identified after observing the results
and are explicitly labeled as a post-hoc diagnostic, separate from the protocol's
select/deselect cutoff metric. Mandatory-single-card commitment does not cover
either optional/multiple-card selection or reward navigation.

The implementation passed **742 agent/package-layout tests in 352.95 seconds**,
including 18 new no-signal cases and legacy-resume coverage, plus Python
compilation. Focused checks also exercised tiny nonzero value errors, positive
but perfectly predicted terminal reward, warm Adam state, serial and parallel
collection, cancellation and exact resume. Independent reviews accepted the guard,
frozen protocol, analysis scripts and final interpretation. The [retained evidence](evidence/training_readiness_2026_09_29.json)
binds the protocol, all three learners, paired outcomes, validation and artifact
hashes; complete models, trajectories and scripts remain under ignored `runs/`.

A 67.32-second final artifact audit verified all 96 canonical campaign replays,
all 15,360 training decisions and their reward/action-mask joins, 177 unique
training episode reset seeds, and exact restore of all three final checkpoints.
All 310 private files had owner-only permissions and no partial artifacts remained.

## Act 1 training and configurable act rewards

The current curriculum objective is **Act 1 completion**, replacing full-campaign
victory as the near-term training and evaluation target. The policy controls the
whole first act: Neow, route choices, combat, rewards, shops, rests and events.
Both Overgrowth and Underdocks use genuine Ironclad A0 campaign starts.

The shared public boundary is `act_transition.completed_act == 1`. The engine
exposes it after the Act 1 boss has been defeated and its rewards have been
resolved or left. Training stops there, before `continue_act` enters Act 2.
This is task success (`terminated=True`, zero value bootstrap), including when
completion occurs on the last allowed action or at the time limit. A budget that
expires before an action remains a cutoff and earns no invented reward.
Canonical campaign trajectories retain their reached public decision and close
as `truncated/external_stop` with canonical reward zero. Reports separately
identify `act1_cleared`; an Act 1 success is never relabeled as an Architect victory.

Use the [Act 1 PPO preset](../configs/training/act1_ppo.json):

```bash
sts-agent-train ppo \
  --checkpoint runs/training-readiness-20260929/filtered-initializer.sts-model \
  --config configs/training/act1_ppo.json --output-dir runs/act1-ppo \
  --reset-objective --reset-action-policy --workers 2 --decisions 1024 --time-limit 120 \
  --seed 401 --start-index 700000
```

The preset uses reward schema `sts_full_run_reward_v3` with `goal: "act1"`.
The `full_run` mode/source identify the existing all-decision campaign pipeline;
the explicit goal sets its episode horizon. Goal and weights are both bound to
the objective identity in configuration, checkpoints and resume state. Changing
either requires `--reset-objective`: retain the actor/vocabulary, reset the critic
and optimizer, and start a new experiment. The historical filtered initializer
uses `commit_single_card_v1`; the current preset uses `commit_card_selection_v1`,
so this example also resets the action policy. To continue from an existing
Act 1 checkpoint with the same rewards, use only `--reset-action-policy` when
adopting the broader filter. Omit it once the checkpoint already uses that policy.

| Reward component | Preset weight |
| --- | ---: |
| `act_cleared` | +1.0 |
| `combat_win` | +0.1 |
| `win_hp_fraction` | +0.025 |
| `end_turn_action` | −0.001 |
| `run_defeat`, `run_abandoned` | −1.0 each |
| `run_victory`, `combat_loss`, `potion_use_action` | 0.0 |

Every weight is configurable. Act-clear success is measured independently of its
weight, so setting `act_cleared` to zero does not disable task termination or the
clear-rate metric. The preset collects 1,024 total decisions per rollout with a
512-decision episode cap. With two workers each gets at most 512 decisions;
remaining batch quota can still shorten a later episode. Time/decision cutoffs
remain separate from successes and defeats and retain their bootstrap values.

The new component also works in continuing full campaigns: use reward schema v3
with `goal: "full_run"` and the desired `act_cleared`/`run_victory` weights. Each
accepted transition into a newly completed act pays once. Reset/attachment,
`continue_act`, Architect entry and Architect victory do not repay it. A10's first
Glory boss does not pay an act bonus because the engine still requires its second
boss. Existing v1/v2 reward schemas retain their original weights and semantics;
they reject the new component until explicitly migrated to v3.

Compare a trained actor against a frozen initializer on identical Act 1 cases:

```bash
sts-agent-evaluate --act1 --checkpoint runs/act1-ppo/final.sts-model \
  --reference-checkpoint runs/training-readiness-20260929/filtered-initializer.sts-model \
  --output-dir runs/act1-evaluation --split validation --start-index 710000 \
  --campaign-cases 16 --max-decisions 1024 --time-limit 90 --workers 8
```

This evaluates heuristic, reference and learned policies on the same frozen
starts, alternating the two Act 1 regions. `act1-plan.json` is published before
the first action. `act1.json` reports `act1_clears`, `act1_clear_rate`, conservative
paired uncertainty, defeats, cutoffs, failures, unattempted cases and last observed
floor. `paired_vs_reference` is the direct improvement comparison. Every planned
case remains in the denominator. `--combat-checkpoint` can supply the existing
combat hybrid instead of a reference actor. The old `--full-run` evaluation keeps
its full-campaign victory metric. Choose fresh output directories and disjoint
episode ranges for follow-up runs; the example training budget is a bounded
integration run, not evidence that 1,024 decisions establish playing strength.

Evaluation accepts `--workers 1` through `--workers 8` for both `--act1` and
`--full-run`; the default is serial. Each persistent worker loads frozen
checkpoint copies once, verifies their digests against the published plan and
uses one Torch thread. Every case/policy game has its own engine, seed and files.
The same case seed is reused across its three policies regardless of scheduling.
Canonical recording validation and outcome analysis also run in the worker;
the parent retains the fixed plan order and computes the paired summaries.
Evaluation workers are independent of the PPO collector and analysis exporter
worker settings. Other evaluation modes reject parallel worker requests.

The parent stops assigning games after failure or interruption, retains completed
acknowledgements from sibling workers and never retries a game. Interrupted and
unattempted rows remain in the planned denominator. Workers receive a cooperative
stop, followed by bounded forced cleanup if needed; forced terminations are
reported, and failed cleanup cannot produce a successful batch. Public failure
categories contain no private seed or exception text. The report/plan's
`execution` field records the scheduling mode, worker count and worker thread
count; existing public trajectory and Act 1/full-run report schemas are retained.

Gameplay still obeys each episode's configured decision/time limits. The parent
also guards worker startup (30 seconds) and a stuck game/analysis job (twice its
gameplay time limit plus 30 seconds). A worker deadline is an operational failure,
not a game defeat. For reproducibility comparisons, allow enough gameplay time:
host contention can make wall-clock cutoffs differ between worker counts even
when seeded decisions otherwise agree. Per-policy summed game time is distinct
from the complete evaluation's elapsed `total_seconds`, especially in parallel.

Matched evaluation benchmark (2026-09-29): the frozen 50k actor, its initializer
and the heuristic each played the same 16 performance-benchmark starts with one
worker and then eight. Each batch completed 48 games / 7,066 decisions. Evaluation
including canonical outcome validation took **288.55 seconds serially** and
**65.86 seconds with eight workers**, a **4.38× speedup**. Whole installed-command
elapsed time was 289.52 and 66.63 seconds respectively. This is one matched local
measurement, with serial measured first; it is not a general scaling guarantee.
Every initial state, transition record, outcome and non-timing metric matched.
Both runs retained all planned cases with no failures or time/decision cutoffs.
The learner's one genuine-start Act 1 clear in each batch also exercised the
successful public stopping boundary. These starts were used to measure throughput;
the result is not a new policy-selection or playing-strength claim.

The final affected regression gate passed **105 tests in 80.13 seconds**, and the
changed modules compiled successfully. Independent semantic review found no
blockers and took approximately 270 seconds, including acknowledgement-draining,
abrupt-exit and cancellation-cleanup probes. Independent artifact comparison took
1.25 seconds and checked paired seeds, canonical file/footer digests, unchanged
source/models, 98 owner-only private files and absence of partial recordings.
The [retained benchmark evidence](evidence/evaluation_parallel_2026_09_29.json)
binds source identities, measured timings, parity checks and the generated
artifacts under `runs/evaluation-parallel-20260929/`.

PPO rollout schema v4 retains the goal, all measured components and the previous
public act marker alongside the combat reward context. The collector checks the
marker against its original observation and verifies the terminal success against
the actual public successor. Task reports distinguish Act 1 clears from full-run
wins; private Act 1 runner audits use `sts_private_replay_v2` to bind the goal.
The public observation and canonical trajectory schemas are unchanged.

For one-policy playback, add `--act1` to `sts-agent-play --checkpoint PATH`.
The runner stops at the same public boundary and its batch summary reports
`act1_clears`; parallel playback preserves that goal for each worker.

Validation on 2026-09-29: all 758 agent/package tests passed in 364.33 seconds,
and `compileall game tests` passed. The 16 new Act 1 cases also passed separately
in 14.90 seconds. They cover configurable bonuses, actual boss-reward exits,
single-payment semantics across three acts, A10's two-boss boundary, successful
termination with zero bootstrap, coincident budgets, serial/parallel PPO,
checkpoint restore and paired evaluation failure denominators. Independent
read-only boundary and implementation reviews took 203 and 294 seconds;
the reviewer found no blockers and passed a separate 19-assertion semantic probe.

Installed-command smoke artifacts are in `runs/act1-training-20260929/`:
two-worker PPO processed/trained 128 decisions in 3.21 seconds and exact resume
processed/trained 16 more in 1.48 seconds. A two-case, three-policy paired
evaluation completed in 1.71 seconds; two-worker playback completed in 0.98
seconds. Evaluation/playback were capped at four actions per episode. The
1.02-second artifact audit validated all 13 canonical trajectories, all 144 PPO
reward joins, unchanged transferred actor weights, the fresh critic, both final
checkpoint restores, identical paired starts, 20 owner-only private files and
absence of partial artifacts. These are integration checks: they recorded no
Act 1 clears and do not establish a playing-strength improvement.

## Act 1 pilot (2026-09-29)

The first bounded Act 1 learning pilot is complete. Its protocol fixed the
initializer, reward preset, source identities, private seed registry and budgets
before the first baseline action. Sixteen fresh validation starts (eight per
region) were shared by the heuristic, filtered initializer and all three final
learners. The three training ranges were disjoint from one another, these
validation cases and the prior generated-headless audits checked during setup.
No hyperparameters were tuned during the pilot and no checkpoint was selected
or promoted. Raw protocols, models, trajectories and analysis scripts are under
`runs/act1-pilot-20260929/`; replay seeds and optimizer state are in its separate
owner-only sibling directory.

Each learner started from the same filtered actor, retained its vocabulary and
used a fresh Act 1 critic and optimizer. The unchanged Act 1 preset supplied
10,240 decisions in ten 1,024-decision rollouts, with two collectors and a
512-decision episode cap. All 30,720 decisions were processed and trained; no
batch met the zero-signal skip condition and no episode failed.

| Learner | Training seconds | Episodes | Act 1 clears | Defeats | Quota cutoffs |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 218.38 | 99 | 1 | 78 | 20 |
| 2 | 215.38 | 105 | 0 | 85 | 20 |
| 3 | 218.56 | 99 | 0 | 79 | 20 |

Training took 652.32 seconds in total. The single genuine-start completion paid
the configured +1 bonus and ended with zero bootstrap. Only one of 303 collected
episodes supplied that success signal; these stochastic, quota-bounded training
outcomes are separate from final-policy validation.

Final greedy evaluation used a 1,024-action/90-second cap per attempt and retained
every planned case in the denominator. All 80 baseline/final attempts completed
with no execution failures or unattempted cases. The baseline panel took 388.11
seconds and the three-learner panel 530.51 seconds, including exact canonical
replay and outcome measurement.

| Policy on the same 16 starts | Act 1 clears | Defeats | Cutoffs | Mean last observed floor | Confirmed combat wins |
| --- | ---: | ---: | ---: | ---: | ---: |
| Filtered initializer | 0/16 | 15 | 1 | 9.875 | 69 |
| Learner 1 | 0/16 | 16 | 0 | 11.375 | 101 |
| Learner 2 | 0/16 | 15 | 1 | 8.6875 | 80 |
| Learner 3 | 0/16 | 16 | 0 | 11.625 | 97 |
| Heuristic reference | 1/16 | 15 | 0 | 14.6875 | 109 |

There is **no observed Act 1 clear-rate improvement**. Paired clear-rate
differences are zero for all three learners; their conservative uncertainty
intervals span zero and do not establish equivalence. Floor differences versus
the initializer are +1.5, -1.1875 and +1.75. These descriptive gains for learners
1 and 3 do not establish consistent improvement across learner seeds.

The initializer and learner 2 each hit the action cap on the same optional,
manually confirmed zero-to-two-card move-to-hand selection at floor 1. Learner 1
advanced to floor 16 on that start. The planned tail-action check identified the
selector loops; no reward-navigation loops occurred in this panel. Mandatory
single-card commitment therefore remains useful but does not resolve this
optional selector. Successful Act 1 endings remain scarce even with dense combat
rewards. The next useful training stage is targeted Act 1 late-act/boss practice
and successful demonstrations, including completion of optional selections,
using training cases and retaining separate genuine-start evaluation.

The 217.79-second artifact audit verified all 30,720 PPO decisions and their
reward/action-mask joins, all 80 canonical evaluation replays, identical starts
across the five policies, 303 unique training episode seeds, all three exact
checkpoint restores and 420 owner-only private files. No partial artifacts
remained. Production sources, tests and dependencies were unchanged during this
pilot; the preceding 758-test validation was reused after verifying matching
implementation and runtime. Artifact manifest preparation took 1.16 seconds.
The [retained evidence](evidence/act1_pilot_2026_09_29.json) binds the frozen
protocol, all learner results, paired outcomes, audit and artifact hashes.

## Single-learner 50k experiment (2026-09-29)

The requested follow-up trained **one learner for 50,000 decisions with eight
parallel collectors**. It used the same imitation-trained actor and vocabulary
as the previous pilot, a fresh Act 1 critic and optimizer, and the current
`commit_card_selection_v1` policy. Rewards, both Ironclad A0 regions and the
512-decision episode cap followed the Act 1 preset.

The experiment increased `rollout_steps` from 1,024 to 4,096 so that eight
workers retained an allowance of 512 decisions each. Keeping the old rollout
size would have reduced each worker's allowance to 128. The final partial
rollout contained 848 decisions, or 106 per worker. The existing 20,000-decision
invocation limit was respected through three chunks of 16,384, 16,384 and
17,232 decisions, with exact checkpoint/optimizer/RNG/cursor resume between
chunks. These are continuations of one learner, not three independent learners.

All 50,000 decisions were trained in 13 PPO rounds and 6,250 optimizer steps,
with no skipped updates or failed episodes. Training took **428.54 seconds
(7m 9s), or 116.67 decisions/second**:

| Training phase | Seconds |
| --- | ---: |
| Parallel experience collection | 298.96 |
| Model updates | 126.69 |
| Other overhead | 2.89 |

There were **2 Act 1 clears in 493 training episodes**, alongside 388 defeats
and 103 quota/episode cutoffs. These sampled training outcomes do not measure
the final greedy policy's clear rate. The previous pilot averaged about 47
decisions/second, but the larger rollout batch, updated selection mask and new
game seeds mean this follow-up is not a matched-workload speed benchmark.

The final checkpoint was compared against its own initialization and the
heuristic on 16 fresh paired validation starts, eight in each region. The
initializer uses the same current selection mask as the final learner. This
isolates their learned-weight comparison from the selection-filter change;
neither reference is selected using evaluation results. Evaluation took
263.88 seconds (4m 24s).

| Policy | Act 1 clears | Defeats | Cutoffs | Mean last observed floor |
| --- | ---: | ---: | ---: | ---: |
| Heuristic | 0/16 | 16 | 0 | 13.25 |
| Initializer with current selection mask | 0/16 | 16 | 0 | 11.00 |
| Final 50k learner | 0/16 | 16 | 0 | 10.875 |

There is **no observed improvement** in Act 1 clear rate or mean floor against
the initializer. The paired clear-rate difference is zero, with the existing
conservative 95% interval spanning approximately ±67.91 percentage points.
One learner and 16 development starts do not establish policy equivalence or
general performance. Every planned case remains in the denominator; no
intermediate checkpoint was selected or promoted.

The resolved configuration, protocol, chunk reports and evaluation are under
`runs/act1-50k-8workers-20260929/`. The final inference bundle is
`chunk-03/final.sts-model`; the matching owner-only continuation state is
`runs/act1-50k-8workers-20260929-private/chunk-03/final.resume.pt`.
Use the experiment's saved `config.json` and eight workers for exact resume.
The [retained evidence](evidence/act1_50k_8workers_2026_09_29.json) records the
configuration, timings, checkpoint identities, results and artifact checks.

Post-experiment verification restored all three chunk checkpoints, confirmed
493 unique training episode seeds, and validated all 50,000 training decisions
against their canonical public recordings, including action masks and recomputed
rewards. The export verified identical public starts for all 16 evaluation cases.
All 562 private files retained owner-only permissions and no partial artifacts
remained. The analysis heuristics flagged no selection-toggle or reward-navigation
loops in the evaluation episodes; this is a check of these recordings, not a
general guarantee about future behavior.

The separate viewer export is `runs/act1-50k-8workers-20260929-analysis/`, with
541 episodes and 56,844 decisions. Verification and export took 473.97 seconds
(7m 54s), including 472.88 seconds for the export; this time is separate from
training and evaluation. Its `chunk-01`, `chunk-02` and `chunk-03` training groups
are consecutive segments of the same learner. Load the first chunk's
`initial.sts-model` and each chunk's `final.sts-model` to compare the initializer,
16,384-, 32,768- and 50,000-decision checkpoints on a recorded public state.

## Act 1 training throughput follow-up (2026-09-29)

A matched benchmark repeats the current Act 1 workload: **one learner, eight
persistent collectors, and 8,192 decisions in two 4,096-decision rounds**. Each
worker gets 512 decisions per round. Three fresh processes per version use the
same frozen initializer, private seed plan, rewards and optimizer configuration
as each other. The initializer and resolved configuration come from the 50k
experiment. Recording, every-round checkpoints and worker cleanup are included;
evaluation and analysis export are separate. Diagnostic profiler runs are excluded
from these timing medians.

| Measurement | Before | Optimized |
| --- | ---: | ---: |
| Complete process, 8,192 decisions | 71.70 s | **60.28 s** |
| Parallel collection, both rounds | 49.34 s | **40.04 s** |
| PPO updates, both rounds | 20.23 s | **18.20 s** |
| Decisions/second, including process overhead | 114.25 | **135.89** |
| First collection round, including worker startup | 25.37 s | 20.55 s |
| Second collection round, reusing workers | 23.97 s | 19.22 s |

The complete workload uses **15.9% less time**, or **18.9% more decisions per
second**. At this rate 50k decisions would take approximately **6m 8s**, excluding
evaluation and export. That is an extrapolation, not another measured 50k learning
experiment. Game lengths and later policy behavior can change throughput. Baseline
process times were 70.24–72.75 seconds; optimized times were 59.16–60.51 seconds.
OS caches and background host load were not controlled.

Profiling identified repeated Python schema inspection during public observation
conversion and repeated vocabulary hashing during PPO batch preparation. The
public codec now prepares bounded reusable schema readers and serialization field
layouts. It still validates every input and every public semantic invariant;
only schema work is reused. Union member ordering, exact primitive/Literal types,
recursive graphs and per-parse generic substitutions are preserved. The immutable
vocabulary computes its unchanged digest once when constructed, including after
loading a checkpoint. Model architecture, policy masks, sampling, rewards and
optimizer mathematics are unchanged.

Collection remains the main cost, around two-thirds of the complete process.
This pass does not reduce the retained observation payload: the two 4,096-step
rollouts contain 1.264 GB and 1.238 GB of packed data. Median parent peak RSS was
4.11 GB before and 4.15 GB after; those measurements exclude collector processes
and are not total pool memory.

Validation passed **635 focused contract, full-game projection, PPO, worker,
checkpoint, recording, Gym and encoding/package checks**, plus compilation and
diff checks. All six timing repetitions matched every recorded public state,
action and outcome, masks, likelihoods, values, rewards, advantages, returns,
non-timing update metrics and final model weights. An additional canonical reload
validated 176 baseline/optimized trajectories containing 16,384 decisions; all
652 generated private files/directories retained owner-only permissions, with
no partial artifacts. Independent semantic review found no blockers and compared 1,438
valid/malformed cases with the original codec, matching acceptance, decoded
values and error details. Inference bundles keep their wire format; exact
optimizer/RNG resume still requires the matching source build.

The raw protocol, source snapshots, profiles and reports are under
`runs/training-throughput-20260929/`. The
[retained evidence](evidence/training_throughput_2026_09_29.json) binds the inputs,
source identities, timing repetitions and validation results. These are throughput
checks; no checkpoint is selected or promoted for playing strength.

### Further snapshot copy optimization

The next pass reuses the preceding accepted three-repetition baseline and runs
three more repetitions of the identical eight-worker, 8,192-decision workload.
The benchmark script, initializer, configuration, private seed-plan digest,
runtime and host match; the source manifests differ only in the new private
snapshot copier and its two consumers.

| Measurement | Previous optimized build | With faster snapshot copying |
| --- | ---: | ---: |
| Complete process, 8,192 decisions | 60.28 s | **58.98 s** |
| Parallel collection, both rounds | 40.04 s | **38.94 s** |
| PPO updates, both rounds | 18.20 s | 18.27 s |
| Decisions/second, including process overhead | 135.89 | **138.88** |

This is **2.2% less total time** and **2.8% less collection time** in the measured
medians. The optimized range was 57.85–59.22 seconds, slightly overlapping the
baseline's 59.16–60.51 seconds; this is a modest result on one machine with
uncontrolled background load, not a guaranteed speedup. The linear 50k estimate
is now approximately **6m 0s**, excluding evaluation/export; no new 50k learning
experiment was run.

Private run/combat snapshots now use a detached dataclass copier that reuses
field-name metadata and directly returns exact immutable scalars. Mutable data
is still freshly copied, and namedtuples, container subclasses and custom leaf
copying retain the existing behavior. Snapshot validation, RNG capture/restore,
stale-action guards and snapshot schemas remain unchanged. Because the change
lives in the engine package, its source/rules digest changes legitimately;
historical evidence retains its original digest, and exact optimizer/RNG resume
still requires the matching build.

Validation passed **541 engine, snapshot/restore, public projection, recording,
PPO/parallel and package checks**. Independent semantic review found no blockers
and matched 315 differential cases against the standard copier. All six timing
repetitions matched every public transition, learning input, non-timing update
metric and final model weight, excluding only run identities and source/timing
metadata. Canonical reload independently validated 176 trajectories / 16,384
decisions against their original source bindings. All 327 new private
files/directories retained owner-only permissions; no partial artifacts remained.

The separate diagnostic profile still identifies public-observation conversion
and serialization as the largest remaining collection costs. Collection occupies
about two-thirds of the process, and the large packed rollout payload is unchanged.
An exploratory update-only probe with four Torch threads took 7.23 seconds versus
9.07 seconds with one thread, but produced different weights. The default remains
one thread; thread tuning needs a separately identified reproducibility/learning
comparison, and that single probe is not an end-to-end speed claim.

Raw reports, profiles and frozen source snapshots are under
`runs/training-snapshot-optimization-20260929/`. The
[retained evidence](evidence/training_snapshot_optimization_2026_09_29.json)
binds this result to the previous baseline, inputs, source changes and checks.

### Validated-observation reuse (2026-09-30)

Projection, encoding and PPO recording now share one prepared public observation.
Preparation validates and reconstructs canonical immutable records, including
canonical field order for structurally equivalent caller records. The owner
retains its serialized form; consumers requesting wire data receive independent
dictionary copies. Reuse requires the exact prepared decision object; equal-but-different
decisions cannot borrow another owner's validation. Owners stay with the current
frame/encoding and are released with the existing reset, failure and cleanup
paths. Nonterminal cutoffs and Act 1 completion retain their actual final decision.

The standard full-run and combat PPO paths use this automatically, as does the
built-in full-run Gym encoder. Custom encoders keep their own hooks and validating
fallback. Standalone unprepared inputs and disk recordings are still validated
independently. The recorder shares its action, execution, sequence, reward and
completion checks across both paths. Engine guards, game rules, RNG, model
architecture, policy masks, rewards and optimizer mathematics are unchanged.

Three **fresh** baseline repetitions and three optimized repetitions use the same
one-learner, eight-worker, 8,192-decision workload described above, including
recordings, checkpoints and cleanup. The baseline already includes the previous
optimizations; today's fresh measurements avoid comparing host conditions across
days. Medians are:

| Measurement | Fresh baseline | Prepared observations |
| --- | ---: | ---: |
| Complete process, 8,192 decisions | 56.69 s | **52.14 s** |
| Parallel collection, both rounds | 36.76 s | **32.11 s** |
| PPO updates, both rounds | 17.98 s | 18.07 s |
| Decisions/second, including process overhead | 144.50 | **157.13** |

Collection uses **12.6% less time**, and the complete process uses **8.0% less
time**. Baseline runs took 55.65–57.05 seconds; optimized runs took 50.31–52.53
seconds. Background load and OS caches remain uncontrolled. The linear estimate
for 50k decisions is **5m 18s**, excluding evaluation/export; this is a throughput
experiment, not a new 50k learning result or evidence of stronger play.

A separate 4,096-decision profile reduced full-public parsing calls from 16,534
to 4,180: approximately four passes per decision become one. The baseline
diagnostic profile has the exact matching source/runtime from the preceding
experiment; instrumented timings are excluded from the fresh throughput medians.
Canonical graph construction, tensor packing and stale-state guards remain
substantial costs. Packed rollout sizes are unchanged.

All **714 final regression tests passed**, covering contracts, ownership and
mutation isolation, custom encoders, encoding failures, full campaigns, recording,
analysis, PPO workers/checkpoints and package integration. Independent semantic
review found no blockers. All six timed runs matched every public transition,
mask, reward, value, likelihood, advantage, return, non-timing update metric and
final model weight. Canonical reload validated 176 trajectories / 16,384 decisions
against their original bindings; all 606 private files/directories retained
owner-only permissions, with no partial artifacts. Wire schemas and the engine's
rules digest are unchanged; exact optimizer/RNG resume still requires the matching
source build.

Raw reports and frozen sources are under
`runs/training-observation-reuse-20260930/`; the
[retained evidence](evidence/training_observation_reuse_2026_09_30.json) records
inputs, source identities, timing repetitions, profiles, checks and measured
phase timings.

### Direct prepared-observation encoding (2026-09-30)

The encoder now traverses the prepared owner's canonical immutable public records
directly, avoiding an intermediate dictionary copy. Field indexes are computed
once per packing operation. Both paths use the same ordered traversal, reference
registration, candidate sorting, capacity checks and array allocation. Canonical
dataclass field order and visible tuple order are preserved. Exact owner checks
still gate reuse; ordinary inputs and custom encoders retain validation, and
recorders still receive independent wire copies. No training configuration change
is needed to use this in standard combat/full-run PPO or the built-in full-run Gym
encoder.

Three fresh baseline repetitions and three optimized repetitions use the same
frozen initializer, configuration and seed schedule, with one learner, eight
workers and 8,192 decisions in two 4,096-decision rounds. Recording, checkpointing
and cleanup are included. This baseline already contains validated-observation
reuse and all preceding optimizations. Medians are:

| Measurement | Fresh baseline | Direct record encoding |
| --- | ---: | ---: |
| Complete process, 8,192 decisions | 51.35 s | **48.97 s** |
| Parallel collection, both rounds | 31.36 s | **29.21 s** |
| PPO updates, both rounds | 17.99 s | 18.01 s |
| Decisions/second, including process overhead | 159.54 | **167.28** |

Collection uses **6.9% less time**, and the complete process uses **4.6% less
time**. Baseline runs took 50.25–51.66 seconds; optimized runs took 48.26–49.48
seconds. A separate alternating-order packing probe on 137 recorded decisions,
701,308 tree rows and nine decision types took 0.514 → 0.393 seconds at the median
(23.6% less packing time), with exact arrays and action/reference bindings. That
probe excludes public preparation, inference, recording and PPO. Background load
and OS caches are uncontrolled in these measurements. The linear estimate for
50k decisions is **4m 59s**, excluding evaluation/export; it is not a new 50k
learning result or evidence of stronger play.

A separate 4,096-decision diagnostic profile reduced wire-copy calls from 8,208
to 4,104, retaining the recorder's copies. Encoding's share of profiled collection
time fell from 20.8% to 15.6%; public-observation construction (32.6%) and
stale-state guards (24.8%) remain larger costs. These instrumented measurements
are excluded from the throughput medians.

All **617 final regression tests passed**, covering v1/v2 encoding, prepared-owner
isolation, custom hooks, exact capacity errors, full public command families,
all five characters, both Act 1 regions, A0/A10, controlled complete campaigns,
recording, analysis consumers and PPO workers/checkpoints. Independent semantic
review found no blockers, including 810 additional differential cases against
the frozen pre-change encoder. All six timed runs matched every public transition,
mask, reward, value, likelihood, advantage, return, non-timing update metric and
final model weight. Canonical reload validated 176 trajectories / 16,384 decisions
with their original source bindings; all 606 private files/directories retained
owner-only permissions, with no partial artifacts. Game rules, stale-state guards, RNG, rewards,
model architecture and optimizer mathematics are unchanged. Exact optimizer/RNG
resume still requires the matching source build.

Raw reports and frozen source snapshots are under
`runs/training-encoding-optimization-20260930/`; the
[retained evidence](evidence/training_encoding_optimization_2026_09_30.json)
binds the inputs, source identities, timing repetitions and validation.

## Implementation sequence and next experiment

1. Milestones 1 and 2 established combat episodes, measured baselines,
   configurable rewards and faithful training records, with results reviewed
   between the user-authorized milestones.
2. Milestone 3 delivered the first usable combat checkpoint and began bounded
   hybrid full-run evaluation with heuristic non-combat decisions.
3. Milestones 4 and 5 added combat PPO, curriculum and paired evaluation, with
   hybrid development evaluations at selected checkpoints.
4. Milestone 6 extended the validated pipeline to full-run learning. The first
   full-run pilot demonstrated integration without improved campaign performance.
5. Commands arrived as each stage became usable; milestone 7 completed their
   installation and delivery checks.

The delivered baseline is combat-first Ironclad A0, terminal-win reward, optional
objective weights, a candidate-scoring actor-critic, imitation warm-up and masked
PPO. Resolved configs, architecture settings, dependencies and measured results
are recorded above. Hardware and larger compute budgets remain experiment
settings; cloud jobs, native game launches, live corpus collection and
profile/save access are outside this implementation's scope.

The signal guard, paired filter comparison, shaped campaign pilot and first
Act 1 pilot are complete. Act 1 remains the current training target:

1. Increase useful success exposure with Act 1 late-act/boss continuation training
   and successful public demonstrations from training cases. Label assisted
   continuations explicitly and keep their results separate from genuine-start
   Act 1 clear rate; the first pilot produced only one clear in 303 training
   episodes and no clear-rate improvement in validation.
2. Include optional/multiple-card selections and reward-screen completion in
   targeted demonstrations, including states reached by the learned actors.
   Verify that greedy playback confirms selections or resolves/skips rewards
   and leaves the screen. Preserve ordered outcomes, native legality and public
   inputs. The current commitment filter preserves ordered outcomes while
   blocking selector undo; use it for new training and retain the historical
   initializer as a separately identified reference.
3. Repeat a bounded multi-seed comparison against the frozen initializer after
   that training change. Judge progress by Act 1 clear rate, with floors, combat
   outcomes and cutoff counts as secondary diagnostics. Expand to later acts only
   after repeatable Act 1 improvement; keep the initializer as the reference
   until paired evidence supports replacing it.

Configurable rewards now provide dense learning signal, and the guard prevents
updates when both advantages and value errors are absent. The remaining
completion failures and Act 1 learning goal motivate the next experiment.
Keep canonical run victory distinct from Act 1 task success, preserve checkpoint
lineage, and retain every planned cutoff and defeat in follow-up comparisons.

Repeatability is scoped to recorded software, hardware and deterministic settings;
[PyTorch documents limits across versions and platforms](https://docs.pytorch.org/docs/2.14/notes/randomness.html).
Do not promise bitwise equivalence across devices or unsupported resume points.
Implementation completion and improved gameplay are separate results, and both
must be reported honestly.
