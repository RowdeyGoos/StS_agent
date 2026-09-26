# Roadmap

Priorities updated 2026-09-26. This file owns priorities;
[current status](docs/STATUS.md) owns capability and evidence. Follow [AGENTS.md](AGENTS.md) for the development
process. Completed packets and old campaign instructions are historical references.

## Immediate priorities

The current user-requested objective is to finish the non-training system for the
declared pinned single-player scope. Carry implementation, relevant native
validation, packaging and cleanup through completion before moving to training.
The shared contract, fixed action encoding, Gym environments, public data tools
and bounded execution are already delivered; the remaining work is below.

Milestone 7 is accepted by the user for the assisted potion campaign: all gameplay
was policy-controlled through the native ending, with one reload to install the
Waterfall Giant correction. Its original continuation result remains unchanged;
another fresh campaign is not an acceptance requirement. See the
[accepted scope](docs/AGENT_ENVIRONMENT.md#7-complete-live-campaign-traversal).

1. **Finish representative coverage of remaining pickup and selector variants.**
   Custom screens, Trial abandonment Cancel/Confirm, event combat/reward/map paths,
   Dummy victory with automatic upgrades, terminal potion policies and assisted
   Fake Merchant seven-relic collection now have live results. Remaining targets
   include capacity-first terminal/event rewards,
   other Neow compound branches,
   and Sphere tool/reward variants. Yummy Cookie's true four-card upgrade
   selector, all five supported shop card-selector families and Cauldron/Orrery
   rewards, plus Silver Crucible’s empty chest, now have representative live
   acceptance; conditional Trial paths retain their separate evidence limits.
   Choose a concrete native caller and observable outcome before extending a mechanism.
   [Current status](docs/STATUS.md) owns exact evidence and practical limits.
2. **Exercise remaining handoff variants in useful live runs.**
   Reuse the [multi-case results](docs/evidence/MULTICASE_BRIDGE_LIVE_2026_09_12.md),
   [combined batch](docs/evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md) and
   [unified smoke](docs/evidence/UNIFIED_BRIDGE_SMOKE_2026_09_08.md).
   Test held-out handoffs and elite variants, keeping run completion,
   branch coverage and strategic quality as separate claims. Use generalized
   transformation in useful play; do not repeat the card16 geometry experiment.
3. **Verify the complete shared v2 route.** Exercise the current public-only
   producer and chooser through native act transitions and the ending, with every
   action reconciled. Reuse authorized controlled assistance and keep its scope
   explicit. This verifies the newer shared interface; milestone 7's earlier
   traversal acceptance remains intact.
4. **Close concrete fidelity and delivery issues.** Use focused native comparisons
   for identified rule/public-information discrepancies or a specific uncovered
   mechanism. Retain accepted unchanged engine and consumer evidence, including
   the existing low-HP, death and revival comparisons. Finish with the current package's clean-install,
   command/Gym/data/continuation checks, source identity, documented limits and
   committed changes. Training-specific throughput targets follow actual training
   workloads later.

Completion means the named gameplay paths have the required representative
evidence, no known in-scope correctness failure is unresolved, the shared v2 route
reaches a settled ending, and the supported package can be installed and used
as documented. Fixes discovered during these checks remain part of this work.
Unsupported shapes with no identified gameplay caller retain explicit limits;
they are neither silently marked passed nor an unbounded implementation queue.
Training and trained-policy performance are subsequent work. The detailed open
coverage list stays in [current status](docs/STATUS.md#implementation-gaps-versus-remaining-live-tests),
and concrete engine discrepancies stay in the
[headless backlog](docs/HEADLESS_FULL_GAME_IMPLEMENTATION.md#hf-48--accept-complete-run-fidelity-and-close-coverage-gaps).

Allocated off-screen transformation and single-upgrade holders each have a
representative live result. Further tests should address new behavior, such as
multi-upgrade or unallocated cards, rather than repeating their geometry checks.

## Scope of further bridge implementation

[Current status](docs/STATUS.md#implementation-gaps-versus-remaining-live-tests)
owns the missing-feature list, separately from implemented capabilities awaiting
live coverage. Rest selector cancellation, wider terminal reward screens and the
named full-producer pickup paths are implemented; representative coverage remains
the immediate priority. Unsupported selector/pickup shapes without a concrete
caller stay outside that queue. Multi-card Smith is not a native gameplay
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
observations/encoding in HF-46/47. Stronger policies, training-library integration
and search remain subsequent work over that interface.
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
