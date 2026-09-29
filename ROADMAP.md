# Roadmap

Priorities updated 2026-09-29. This file owns priorities;
[current status](docs/STATUS.md) owns capability and evidence. Follow [AGENTS.md](AGENTS.md) for the development
process. Completed packets and old campaign instructions are historical references.

## Immediate priorities

The requested non-training completion pass is complete for the declared pinned
single-player scope. The shared contract, fixed action encoding, Gym environments,
public data tools and bounded execution are delivered. The named bridge paths
have representative live evidence, the shared-v2 saved continuation reaches a
settled native ending, and no known correctness failure remains open in the
requested paths. The current package passed its release gate, installation and
exact cleanup checks; source and evidence are committed.

The final coverage work included the native Kifuda empty-confirm correction and
successful one-card toggle retest, automatic Neow pickups, Sozu-blocked Holster,
empty removal retaining Eternal, standalone first Sacrifice, shop spending/kind
variants, an assisted elite handoff and natural Orobas entry. Agent-managed Steam
launch, normal shutdown and restart worked across the controlled batches.
[Current status](docs/STATUS.md) owns exact results and limits; the
[live ledger](docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#prevention-removal-policy-variants-and-handoffs)
retains the separate boss-helper map stop with all actions reconciled.

Milestone 7 remains accepted by the user for the assisted potion campaign: all
its gameplay was policy-controlled through the native ending, with one reload
for the Waterfall Giant correction. Its original continuation result is unchanged;
another fresh campaign is not an acceptance requirement. The later shared-v2
ending is an assisted saved continuation with its own corrections and reloads,
not a fresh uninterrupted v2 certification. See the
[accepted scope](docs/AGENT_ENVIRONMENT.md#7-complete-live-campaign-traversal).

Further work should start from a new concrete requirement:

1. **Maintain the accepted package.** Reuse unchanged engine/consumer evidence,
   including the September 26 package refresh and its 406 agent checks, until
   affected inputs or the pinned game build change. Preserve exact source,
   artifact, test and cleanup bindings.
2. **Resolve new native discrepancies when observed.** Identify the caller and
   observable outcome first, then add the smallest implementation and validation
   needed. Unsupported shapes with no identified gameplay caller retain explicit
   limits; they are not an unbounded implementation queue.
3. **Improve Act 1 completion.** The current training goal is Ironclad A0 Act 1
   clear rate across Overgrowth and Underdocks, using configurable act-clear and
   combat rewards. Full-campaign training is deferred until repeatable Act 1
   progress. Use the [Act 1 workflow](docs/AGENT_TRAINING.md#act-1-training-and-configurable-act-rewards)
   for the finite task horizon and paired initializer comparison. Stronger full-run learning,
   throughput targets, stronger policies, exhaustive branch/seed coverage and a
   fresh uninterrupted shared-v2 campaign are subsequent scopes. Representative
   bridge coverage does not establish strategic quality.
   The user-requested [training plan](docs/AGENT_TRAINING.md) starts with combat
   objectives and then full-run learning. Milestones 1–5 deliver combat episodes,
   measured baselines, configurable objectives, faithful training records, a
   public graph actor-critic, imitation warm-up, bounded masked PPO and resumable
   CPU checkpoints, a finite curriculum and frozen paired combat benchmarks.
   The first broader held-out comparison is inconclusive; selector completion
   remains a measured weakness. Hybrid campaign evaluation continues alongside
   combat training. Milestone 6 adds full-run demonstrations, explicit actor
   transfer with a fresh run critic, canonical victory PPO and paired genuine
   campaign evaluation. Milestone 7 completes the installed-command delivery,
   clean-package checks and broad Python integration. The completed
   [staged diagnostic](docs/AGENT_TRAINING.md#staged-learning-diagnostic-2026-09-29)
   finds entropy-only PPO drift and pre-existing non-combat selection loops in
   one checkpoint lineage. Requested configurable full-run rewards now provide
   combat and run components with explicit objective transfer and canonical
   win-rate evaluation. A shared, versioned policy layer now completes explicit
   mandatory single-card selections across training and playback; optional and
   multiple-card selections preserve native actions because order can matter.
   PPO now skips updates with no advantage or value-learning signal and records
   skipped work separately. Next, improve the remaining selector and reward-screen
   completion behavior and establish useful Act 1 completion targets before
   increasing training budgets.

[Current status](docs/STATUS.md#implementation-gaps-versus-remaining-live-tests)
owns remaining evidence limits, and the
[headless backlog](docs/HEADLESS_FULL_GAME_IMPLEMENTATION.md#hf-48--accept-complete-run-fidelity-and-close-coverage-gaps)
owns concrete engine discrepancies. Allocated off-screen transformation and
single-upgrade holders already have representative results; further tests should
address new behavior rather than repeat their geometry checks.

## Scope of further bridge implementation

[Current status](docs/STATUS.md#implementation-gaps-versus-remaining-live-tests)
owns implementation limits separately from the accepted representative coverage.
Rest selector cancellation, wider terminal reward screens and the named
full-producer pickup paths are implemented and have representative evidence.
Unsupported selector/pickup shapes without a concrete caller remain outside the
implementation queue. Multi-card Smith is not a native gameplay
requirement in the pinned assembly.

Use the [research map](docs/EVENT_INTERACTION_MAP.md) for source-backed callers;
its historical gap matrix is not a current task queue. Variable upgrades, enchantment
stacking/replacement and unallocated-holder mechanisms need a concrete caller/setup before implementation. Native cancellation
is confirmed for rest-site Smith/Cook, separately from optional-zero event selectors.
Plan shared capabilities from native dependencies, not event-name rules.

## Headless and learning direction

Prioritize faithful game logic in the [independent engine](docs/HEADLESS_ENGINE.md).
Implement and test cards, monsters, powers, items and run progression directly,
then integrate mature capabilities into actor/bridge consumers when useful.
Projection, encoding and training work must not gate ordinary gameplay features.
The old simulator/reduced backend and research pipelines are retired. Future
public observations and policy/data adapters must consume the current engine.

The [full-game backlog](docs/HEADLESS_FULL_GAME_IMPLEMENTATION.md) owns feature
scope and acceptance cases. Strike+ is now ordinary game content; the experimental
per-upgrade profile is retired. Headless and bridge work can proceed in parallel
with disjoint source ownership and shared pinned-game rule evidence.

Public datasets and operational agent execution now consume the full-run
observations/encoding in HF-46/47. CPU imitation, bounded PPO and checkpoint
playback now use that interface. Stronger policies and search remain
subsequent work.
The [agent environment plan](docs/AGENT_ENVIRONMENT.md) defines the shared-contract,
bridge-adapter and Gymnasium milestones and their observable acceptance cases.
Its [shared contract and both bounded producers](docs/AGENT_CONTRACT.md) are
implemented, with the same public-only chooser over the combat/selection/reward/map
slice. Milestone 3's controlled native slice, separate map dispatch and cleanup
are accepted. Milestone 4's [fixed public encoding and Gymnasium environment](docs/AGENT_ENCODING.md)
are implemented. Milestone 5 adds full headless decision/content coverage and
`FullRunEnv`, with explicit exclusions from the existing live profile. Milestone 6
adds [public trajectories, the installed agent command and bounded workers](docs/AGENT_EXECUTION.md).
Milestone 7's assisted live traversal is accepted with its documented bridge-fix
reload. Further native coverage and stronger policies preserve the current
profile's explicit gaps and evidence requirements.

## Long-term destination

Use the faithful full-run engine to develop stronger policy/value
models and optional tactical/strategic search over shared legal candidates.
Expand content and certify performance under the pinned target, public-information
boundary and declared compute budget. See the
[target](docs/TARGET.md) for current evaluation requirements and the
[archived architecture plan](docs/archive/LONG_TERM_ARCHITECTURE_ROADMAP_2026_09_22.md)
for historical design detail.

Update this file when priorities change, not after every test run. For substantial
features, use available phase timings to check whether the streamlined process
reduces time to usable behavior without increasing regressions.
