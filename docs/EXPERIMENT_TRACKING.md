# Local experiment tracking

MLflow provides experiment comparison and learning curves. The decision inspector
remains the tool for examining what happened in a particular game. Both read the
existing public reports; tracking does not replace canonical trajectories,
checkpoint bundles, private resume states or evaluation protocols.

## Start the dashboard

```bash
python3 -m pip install -e '.[train,tracking]'
sts-agent-track import runs --store runs/experiment-tracking \
  --experiment 'Historical experiments' --report runs/tracking-import.json
sts-agent-track serve --store runs/experiment-tracking --port 5050
```

Open <http://127.0.0.1:5050>. The server listens only on loopback. The SQLite
database, small lineage index and artifacts live under the selected store.
MLflow telemetry is disabled before import and server startup. Ambient
`MLFLOW_TRACKING_URI` settings cannot redirect these writes to a remote service.
The optional dependency is MLflow 3.16; TensorBoard is not required.

Use named experiments to separate active research from development/performance
runs. Within an experiment, filter `tags.sts.kind = 'ppo'` to see learners, or
`tags.sts.kind = 'evaluation'` to see evaluation panels. Select learners and use
MLflow's comparison view for their parameter differences and curves. Display
names, tags and the Markdown run description can hold experiment notes. Write
notes above or below the generated description block; subsequent imports preserve
that text and retain the inspector link when no replacement URL is supplied.

## Focused saved views

Report imports and live tracking automatically apply reusable views as the
corresponding metrics arrive. Empty experiments get no empty charts. Open an
experiment's **Runs** page and use **Views** at the top right. MLflow 3.16 can
open a saved view in table mode; select the chart icon to show its curated
charts. The table also retains only the selected metrics. Direct links below
include chart mode.

| View | Use it for |
| --- | --- |
| **01 · Combat performance** | Recorded fixed-case scores and separately labelled online rollout win rates. Greedy, sampled and evaluation populations stay separate. Campaign learners use the name **01 · Performance**. |
| **02 · Fight quality** | Available fixed-case HP measurements: Vantom player HP before healing, boss HP on losses, paired changes, or the canonical report's HP-on-win metric. Labels distinguish these meanings. Higher player HP and lower boss HP are better; conditional means alone do not establish improvement. |
| **03 · PPO diagnostics** | Entropy, approximate KL, clipping, critic error, policy loss and gradient norms. |
| **04 · Training speed** | Collection and update time, collection throughput and cumulative training wall time. |

The previously curated views remain available in **Vantom specialist**, **Vantom action previews**,
**Vantom potential shaping** and **Vantom continuation diagnosis**. **Combat
representation** and **Combat research 7h** have performance, PPO and speed views;
their original and fresh validation populations remain separate. Missing
measurements are not converted to zeros. The views keep each learner separate
and use no smoothing or cross-seed averaging. Continuation-diagnostic performance
curves use additional decisions; PPO diagnostic curves retain native learner
counters. Win rates are fractions, and parent win-rate differences in the
shaping/preview views are percentage points.

Useful starting points are the
[Vantom learning curve](http://127.0.0.1:5050/#/experiments/8/runs?viewStateShareKey=17910198782163edgmyyy&compareRunsMode=CHART),
[Vantom fight quality](http://127.0.0.1:5050/#/experiments/8/runs?viewStateShareKey=sts-fight-quality-v1&compareRunsMode=CHART),
[reward-shaping comparison](http://127.0.0.1:5050/#/experiments/10/runs?viewStateShareKey=sts-combat-performance-v1&compareRunsMode=CHART)
and [continuation comparison](http://127.0.0.1:5050/#/experiments/11/runs?viewStateShareKey=sts-combat-performance-v1&compareRunsMode=CHART).

**Performance benchmarks** has six separate views: collectors above 16,
collectors from 8 to 16, greedy evaluation, full evaluation, PPO update replay,
and complete PPO training. Each filters to its own benchmark and workload.
Evaluation charts show medians of three repetitions; collector bars show the
individual runs, and update-replay curves use repetition number as their step.
Start with [collector scaling above 16](http://127.0.0.1:5050/#/experiments/4/runs?viewStateShareKey=sts-collectors-above16-v1&compareRunsMode=CHART).

These layouts are saved in the existing MLflow experiment metadata and survive
server restarts. They select existing metrics without changing recordings,
rewards, scores, checkpoints or training. Native charts keep their exact metric
names, with plain-language section labels. Detailed metrics remain available
from the ordinary view and run details. New experiments need their own saved
views, generated from the versioned definitions in
[`game/agent/tracking/views.py`](../game/agent/tracking/views.py).

New PPO reports get performance, diagnostics and speed views as their metrics
arrive; fixed-case HP scores add fight quality. Further imports expand untouched
templates when new metrics appear. Canonical evaluation curves retain their
population ID in both the metric name and chart label. Historical `combat/*`,
`diagnostic/*`, `eval/*` and `research/*` aggregate names have explicit mappings;
unknown metrics stay available in run details without being guessed into a view.
Templates use the native metric step, unsmoothed lines with visible points and
no cross-run averaging. Existing hand-curated views keep their original layouts.

To apply templates to an existing experiment, or after an experiment driver
writes metrics directly through the MLflow client, run:

```bash
sts-agent-track views --store runs/experiment-tracking --experiment 'Combat research'
```

This only writes saved-layout metadata, never run metrics, parameters or model
artifacts. Untouched generated views can be refreshed; edited, renamed, deleted
or independently created matching views take precedence. Repeated refreshes
are idempotent, and interrupted writes can be retried with the same command.
If an interrupted first save leaves no visible view, refresh preserves that
absence: it cannot distinguish a failed save from a subsequent user deletion.
Automatic layout failures warn without failing the canonical report import.
Refreshes occur when a reporting session first imports a report or sees new
metric keys, rather than on every update with the same metric names.

Benchmark templates use the recorded `sts.benchmark`, `sts.kind` and `panel`
values to keep workloads separate; they are not tied to experiment IDs or dates.
New custom metrics or a new naming convention require a template mapping. This
is local StS tracking integration, not a server-wide MLflow plugin: experiments
and metrics created directly in MLflow require the command above. The original
one-off creation recipe and verification remain under `runs/mlflow-views-20261003/`.

## Compare checkpoints in Models

The experiment's **Models** view focuses on each learner's initial checkpoint,
latest completed endpoint, evaluated checkpoints and explicitly retained candidates.
Resumed chunks belong to one learner: a former chunk endpoint leaves the catalog
when training advances unless it was evaluated or retained. Ordinary PPO recovery
saves still happen after every complete update, and every update still contributes
to the learning curves. Unevaluated intermediate saves are not published to Models.
Each entry shows its training counter, architecture/configuration parameters and
source training run. The model artifacts contain a verified `checkpoint.sts-model`,
its manifest and source binding. The source run also lists these model outputs.

Use **Columns** to choose the relevant dataset and
`evaluation/<split>/<mode>/<population>/win_rate` metric (or `act1_clear_rate`)
to compare checkpoints on the same cases. The installed
Models UI does not expose tag filtering. For API queries,
`MlflowClient.search_logged_models` accepts filters on the `sts.evaluated` or
`sts.validation` tags (value `true`) to restrict results to evaluated checkpoints.
Metrics carry MLflow dataset identities as well as distinct population names;
different panels and action-selection modes remain separate. Dataset metadata
retains the complete population hash; MLflow's shorter digest field uses its
first 32 hexadecimal characters. Models receive aggregate scores and outcome
counts so the comparison table stays manageable. Encounter, room, threat and HP
breakdowns remain available on the linked evaluation runs and in their reports.

Repeated imports reuse the same entry for the same learner, bundle hash and
counter. Different bundle bytes, learner forks and experiment groups remain
distinct. Scores describe the exact checkpoint bytes: when multiple learners
reuse the same bundle, their catalog entries share its recorded scores and are
marked as shared. The evaluation no longer claims one exclusive learner/model.
New learner-curve overlays require a unique learner/counter match; existing
measurements are retained and are not assertions of exclusive ownership.
Checkpoints without imported training provenance remain visible in evaluation
runs, but are not fabricated as catalog entries.

Reimport existing reports with their original `--experiment` to populate Models
without changing training curves or rerunning games. Import training reports
before evaluations (the importer does this automatically for a combined input).
Live tracking maintains the same selection automatically. Evaluating a previously
unlisted checkpoint publishes it using its imported training provenance. Promotion
requires the saved source report: checkpoints from an active invocation become
eligible once its terminal report is published and imported. A model becomes
`READY` after its verified public bundle is copied; this does not certify gameplay
or select it as the best checkpoint. Failed publication leaves a recoverable
pending entry. These are StS bundles, usable through the existing StS loaders;
this integration does not add MLflow serving wrappers or registry promotions.

To clean up a catalog imported before this selection rule, or explicitly retain
an intermediate candidate, use:

```bash
sts-agent-track catalog --store runs/experiment-tracking --experiment 'Combat research'
sts-agent-track catalog --store runs/experiment-tracking --experiment 'Combat research' \
  --keep-checkpoint runs/my-training/update-00012.sts-model
```

Use `--release-checkpoint PATH` to remove explicit retention; evaluated checkpoints
and current learner endpoints remain visible. Selection is local to the named
experiment and applies to entries for the exact bundle bytes. Existing recovery
files, private resume files, reports, run curves, model IDs and catalog artifacts
are preserved. Historical reimports do not repopulate intermediate entries.

MLflow 3.16 has no logged-model restore API or UI tag filter. Curation uses a
bounded local SQLite lifecycle change with a revision-bound marker to hide old
entries and restore the same IDs when needed. Manual deletions take precedence.
Do not run `mlflow gc` as ordinary cleanup on this store: it treats hidden entries
as deleted and can permanently remove their catalog artifacts. Canonical files
outside the tracking store are unaffected; storage retention is a separate policy.

## Record new training and evaluation

Add these options to `sts-agent-train ppo`, `imitate`, `curriculum`, or
`sts-agent-evaluate`:

```bash
--tracking-dir runs/experiment-tracking \
--tracking-experiment 'Combat research' \
--tracking-name 'Architecture experiment A'
```

`--tracking-name` names a newly created learner. Exact continuations retain the
original name. Add `--inspector-url http://127.0.0.1:51002/` when the appropriate
inspector dataset is being served. The run description contains a clickable link.
Inspector ports are session-specific; reimport the relevant reports with a new
`--inspector-url` to update the link. Source report paths remain in the artifacts
and tags when that server is no longer running.

For Python experiment drivers, scope the existing trainer/evaluator calls:

```python
from game.agent.tracking import TrackingConfig, tracking_session

with tracking_session(TrackingConfig(
        'runs/experiment-tracking', experiment='Combat research')):
    path, report = run_ppo(...)  # Existing trainer arguments and safeguards apply.
```

The shared `report_progress(path, report)` boundary is independent of model
architecture. New trainers can add a report normalizer in `tracking/records.py`
and use that boundary. The parent process logs snapshots, with a five-second
minimum interval while running and an unconditional final flush. Each snapshot
retains all intervening update metrics. Spawned rollout workers do not initialize
MLflow. Without an explicit tracking session there are no dashboard writes or
MLflow imports.

Invalid tracking configuration fails before training starts. Later dashboard
errors produce a warning and retain the canonical training result. Recover with
`sts-agent-track import PATH --store ... --experiment ...`; never rerun games just
to repair logging. A failed write reserves its learner assignment and terminal
source hash, preventing a sibling resume from claiming the same curve on retry.

## What the curves mean

| View | Recorded values and axis |
| --- | --- |
| `train/*` | Online rollout outcomes, rewards, HP and potion use; includes quota cutoffs. Axis: cumulative processed decisions. These are not fixed-case validation scores. |
| `ppo/*` | Policy/value losses, entropy, approximate KL, clip fraction, gradient norms, optimizer steps and packed input sizes. |
| `imitation/*` | Update losses plus before/after train and validation imitation measurements. Axis: optimizer updates. |
| `evaluation/<split>/<mode>/<population>/*` | Fixed-population checkpoint measurements on the owning learner's decision/update axis, with encounter/room/start/threat breakdowns. |
| Evaluation child runs | One policy/population measurement, always at local step zero. `sts.checkpoint_step` records the learner counter when known. |
| `system/*` | Collection/update timing, throughput, process memory and cumulative segment wall time. Memory remains parent-process-only where that is all the source recorded. |
| `by_seconds/*` | PPO training curves whose step axis is measured training seconds. |
| `segment/*` | Per-invocation totals, including accepted versus trained/skipped decisions and failures. |

Counters use processed decisions, so an intentionally skipped PPO update still
advances the decision axis. `segment/trained_decisions` and skipped counts expose
the distinction. Per-update elapsed time sums measured collection/update time
and previous segment wall time. Checkpoint/cleanup overhead within the current
segment is only included in `system/cumulative_wall_seconds` at segment end.
MLflow's creation and metric timestamps are ingestion times for historical
imports, not reconstructed historical start times; use the explicit seconds
curves and wall-time metrics for cost comparisons.

Parameters contain architecture, features, objective/rewards, PPO/imitation
configuration, worker settings, dataset identities and recorded implementation
and runtime identity. Full resolved configuration, original reports, public
checkpoint manifests and checkpoint paths/hashes are attached as artifacts.
The last available public bundle of each completed segment is copied into run
artifacts. The Models catalog also retains the recorded public checkpoint bundles;
canonical files remain in their original directories.

Raw learner/game seeds, optimizer RNG state, private replay snapshots and private
audit directories are not imported. Separate learners retain separate run IDs;
exact-resume state digests bind PPO continuations without exposing RNG contents.

## Continuations, comparisons and historical imports

PPO segments join only when an explicit resume has a matching exact state digest,
counter, configuration, runtime and source identity at an unclaimed closed tail.
This joins repackaged exact-resume bundles, including the fresh combat 250k → 500k
continuation. Resuming an earlier checkpoint or concurrently resuming a tail
creates a separate branch. Loading weights into a fresh optimizer creates a new
learner. Explicit imitation resumes from newly recorded reports use their named,
successfully restored parent bundle; older imitation reports lack that binding
and remain separate.

Import parents and continuations together: the importer orders them by counters.
A child imported alone before its parent is explicitly marked unresolved and is
not later silently reassigned. Use a fresh named experiment and import the full
chain together if that history needs regrouping. Reimporting unchanged reports
does not duplicate metric points. Changed terminal reports are rejected,
including after interrupted tracking writes. Evaluation imports can be repeated
after training imports to resolve previously unknown checkpoint ownership.

Evaluation population identities include the objective, split, case/state set,
repeats, action-selection mode, recorded limits/rewards and source. Hybrid
evaluations retain their fixed outside-combat controller identity. Different
populations get different curves; opening fights, continuations, tiny training
panels, greedy decisions and sampled decisions are not pooled. The inspector
link supplements these aggregate measurements.

Wins require successfully terminated episodes. Failures, cutoffs and unattempted
cases remain in planned denominators. Incomplete legacy baseline reports omit
some case identities: their overall planned count is preserved, unavailable
subgroup rates are omitted, and those report populations remain separate.
Repeated fights from one source campaign are not independent evidence; the
original reports retain their grouped uncertainty calculations. No new confidence
interval is inferred from individual games or a single learner seed.

The importer recognizes PPO/imitation, combat-corpus/frozen-combat, Act 1/full-run,
baseline/hybrid, legacy readiness and the frozen plateau diagnostic reports. It reports unsupported
summary wrappers separately and never follows their arbitrary file references.
The import inventory lists every imported, skipped and failed source. Historical
reports are labelled `reported_metadata`: importing them does not replay games,
certify old engine behavior or promote superseded evidence to current evidence.

Imports only traverse explicit public roots, rejecting symlinks/private trees.
Checkpoint bytes are checked against report hashes; only manifest JSON is read,
never pickled tensors or private resume state. Existing evaluation reports can be
imported without opening test snapshots or running new test cases. Current engine
and exact-resume source checks remain unchanged: this tracking code changes the
current implementation hash, and historical source identities are preserved.

For the tools being integrated, see [MLflow tracking](https://mlflow.org/docs/latest/ml/tracking/)
and the existing [decision analysis guide](AGENT_TRAINING.md#decision-analysis-tools).
