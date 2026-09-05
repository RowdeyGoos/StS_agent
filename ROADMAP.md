# ROADMAP.md

This file tracks the most useful next steps for the project. It is not a strict commitment list; it is a guide for future work and for quickly understanding where the simulator is headed.

The goal is to keep the scope growing in a way that stays useful for RL research
without turning the codebase into a full game clone too early. The combat-
research priorities below coexist with the active full-game integration track;
the latter's authoritative progress summary is
[`docs/PHASE_1_CURRENT_STATUS.md`](docs/PHASE_1_CURRENT_STATUS.md).

## Current Position

The project currently has:

- a modular combat simulator
- deterministic seeded runs
- single-enemy and multi-enemy encounters
- starter deck cards plus `Slimed`, with an optional four-card Ironclad sequencing preset
- `vulnerable` and `shrink`
- structured observations and fixed-width RL encodings
- fixed legal-action feature encodings for policy architectures
- random, heuristic, Q-learning, DQN-family, and PPO baselines
- masked PPO with an action-conditioned policy head
- opt-in permutation-equivariant shared-enemy PPO policy scoring
- opt-in permutation-equivariant shared-enemy DQN-family Q scoring
- named starter and Ironclad sequencing deck selection across training and inspection tools
- an experimental fixed-capacity semantic card-record and learned-embedding kernel
- batched multi-environment PPO rollout collection with per-environment GAE
- opt-in process-parallel CPU PPO environment collection through shared memory
- opt-in PPO phase timing and CPU/memory/accelerator resource reports
- the `simple` encounter, canonical `overgrowth_easy`, and a versioned partial `overgrowth_hard_v1` pool with Mawler
- aggregate and per-encounter evaluation metrics, including damage taken
- deterministic fixed-seed policy benchmarks with table and JSON output
- saved trace analysis for common tactical mistakes
- a seeded brute-force oracle for small-encounter optimal-policy comparisons
- per-decision oracle regret traces for ranking trained-policy weak points
- sampled information-aware regret over hidden draw orders and future RNG
- automatic CUDA, Apple MPS, and CPU selection for neural training
- self-contained run directories with reusable configs, checkpoints, and metadata
- reusable PPO sweep configs with explicit Optuna search spaces
- process-parallel Optuna trials with resumable local journal storage
- responsibility-based `simulation`, `agents`, `training`, `analysis`, and `cli`
  packages with one canonical import and command surface

The full-game integration track additionally has:

- a project-owned authenticated live bridge at milestone `R0i`;
- bounded live reads at the main menu, Settings, combat, rewards, and map;
- snapshot-bound combat, reward, and map actions with reconciliation;
- replaceable external providers for combat, rewards, map travel, and supported
  rooms;
- a verified live complete-combat loop, one direct safe event-to-map action,
  and a composed live sequence spanning two combat/reward/map handoffs;
- live-accepted standalone rest-site healing and completion, foreground
  inspection-map action suppression, and stale snapshot rejection;
- live-accepted explicit fresh reward entry through reward/map composition to
  terminal combat defeat with truthful partial-prefix accounting;
- repository and disposable-fixture coverage for a combat/reward/map/room
  controller capped at three combat floors;
- implemented host-only elite continuation and an opt-in elite-first provider,
  with independent actual-client fixture and historical-control coverage;
- the accepted `headless_v0` contract, composed deterministic reduced-run
  backend, component-addressable evidence, snapshots/replay, and an independent
  66-test conformance gate;
- accepted public-only headless smoke choosers, cancellation-safe sequential/
  spawned rollout collection, and a synthetic live-wire versus headless
  common-subset comparator that preserves divergences;
- versioned headless experiment artifacts/CLI and maintained deterministic
  panel checks;
- a frozen public variable-candidate encoder with out-of-band IDs and explicit
  row masks, independently reviewed for reference/permutation invariance;
- a small masked candidate scorer with variable/empty view handling and pinned
  checkpoint payloads;
- a trusted public actor dataset with explicit accepted pins, separated panels
  and exact component evidence retained outside actor examples;
- an accepted deterministic CPU behavior-cloning smoke with trusted structural
  panels, masked loss, provenance-bound report/checkpoint and safe cancellation;
  and
- repeated normal teardown, bridge removal, and clean base-game relaunches.

This is not yet a complete autonomous run. Shops and potion decisions remain
unsupported, fully reconciled event handling still needs bounded live
acceptance. Earlier batched campaigns observed `decision_response_mismatch`,
`run_room_not_ready`, and multi-step `room_interaction_timeout`; the Python
readiness repair is integrated, while the historical response and event
observations remain unexplained or unreproduced. Earlier live tests isolated a
foreground-map/underlying-room mismatch and failed completion after both event
advancement and rest-site healing. The independently reviewed narrow C# repair
has now passed bounded
rest-site live acceptance: inspection-map suppression and stale rejection,
heal/Proceed completion, and non-actionability after closing the completed map.
Its broader replay-identity edge cases remain fixture-tested. Normal teardown,
clean base-game launch/quit, and final purge passed. Multi-step event completion
and a full batched room handoff remain unaccepted live.
The headless rollout/throughput consumer is accepted, with bounded local
measurements and no learned-policy or target-game-parity claim.

## Near-Term Priorities

These are the highest-value next steps.

### Full-Game Integration Priority

Keep the C# bridge and `live_probe_v0` wire frozen. The bounded Python host now
treats `elite` as combat using the existing clients, with independent fixture
coverage. The maintained capture-off acceptance validator and independent join
review and aggregate bridge suite are accepted. The first campaign attempt
stopped during read-only Steam inspection after that tool stalled beyond the
30-minute limit, before installation or launch. The bounded infrastructure
retry opened Steam but repeatedly failed screen capture (`-3811`), including
after automation-session reset. Game capture subsequently worked after manual
launch. The one authorized capture-off run from a fresh map returned
`room_interaction_timeout` with no accepted summary; no complete map/elite/room
chain is certified. Exact quarantine, clean unmodded launch/quit, four-file
purge and final base/runtime checks passed within the 30-minute limit.
Fresh-session Steam capture still fails with `-3811`. Focused repository and
actual-client fixture diagnosis shows that `room_interaction_timeout` can occur
before any room action or after accepted choices/Proceed; the shared deadline
and generic waiting body do not identify the stage. No production defect or
justified timeout increase was established. The timeout regression gate remains
accepted. A separate opt-in room-stage diagnostic is now implemented and
independently reviewed, with fixed bounded stage/count output, strict acceptance
parity and cleanup/privacy gates. It preserves every existing controller output,
C# and wire contract. A subsequent live diagnostic passed explicit fresh map
entry with three destinations and two completed floors, but never entered the
room client. The user selected a targeted question-mark event test and offered
to prepare a fresh event with its choices untouched. The direct-room adapter is now implemented and independently accepted with
1,112 tests passing. That exact state was tested once: one accepted event
receipt followed by explicit `room_state_unsupported`, without room completion.
The matching literal regression passes. Current event fields identify choices
and immediate lethal risk, but do not model costs/effects or supported follow-up
screens. Any consequence model or room-to-reward handoff is a separate scoped
contract decision; do not broaden potion/reward controls or replay the stopped
choice under the current frozen scope. Do not use another generic map route as evidence for the room issue.

The user selected parallel repository work on shops, item rewards and event
continuation. The [missing-room capability plan](docs/PHASE_1_MISSING_ROOM_CAPABILITIES_PLAN.md)
defines isolated proposals and shared-contract gates. Bounded static inspection
is reviewed, and the first isolated item-collection component is implemented:
ten synthetic core groups pass, its native adapter compiles against the pinned
game, and fresh builds reproduce. It stays outside the existing 0.8.0 bridge.
The isolated wire and programmatic host are also reviewed: 9 C# groups, 27 host
tests and 17 actual cross-language cases pass, with two matching source-snapshot
builds. The transport and owned-thread queue now also pass review, 11 C# groups,
16 Python tests and 15 actual synthetic socket cases. The secure operator and
first-frame bootstrap candidate now passes 13 operator groups, 24 lifecycle
groups, 24 checker boundary cases and two matching fresh builds. The
[release packet](docs/PHASE_1_ITEM_V1_RELEASE_PLAN.md) now has an independently
reviewed whole-assembly policy, exact reproduced package, fixed client and
transactional campaign tools. Separate live potion and relic collections now
each pass with exact receipt/reconciliation and complete cleanup. Broader room
behavior remains unproven. Next development is the named shop dispatch/back/FTUE
static gate and reviewed parent event/child lifecycle contract; chest collection
is also outside the current Loot-screen adapter.
Exact results are in the [missing-room acceptance ledger](docs/research/PHASE_1_MISSING_ROOM_ACCEPTANCE.md).

Supported user-initiated launch remains available; the restricted browser
Steam-URI route is not bypassed. Normal quit, exact quarantine/purge and final
stopped/closed/base checks remain required. At the user's direction, repeated
unmodded launch/quit checks are waived and must not be claimed as passed.
Preserve exact room caps, replay and uncertainty behavior. The historical timeout
and elite/composed-room evidence remain open; keep boss, shops, treasures,
relics and potions fail-closed. Discarded responses cannot establish the prior
root cause or justify replaying its uncertain action.

Keep models and search outside the bridge and postpone shop support until this
composition is reliable. This preserves easy comparison among heuristic,
policy-only, and future planner-enhanced providers.

The tiny deterministic behavior-cloning smoke over the public encoder, trusted
actor dataset and masked candidate scorer is reviewed and integrated. It
preserves cancellation-safe publication, explicit skips and separate
hindsight/audit records. Its accepted structural metrics and reproducible
checkpoint/report round trip prove training plumbing only;
structural reward/map/room rules remain synthetic until named live differential
cases pass. No retained live corpus is authorized.

The active dependency graph, ownership, acceptance and handoff packets for both
tracks are in
[`docs/PHASE_1_ACTOR_READY_EXECUTION_PLAN.md`](docs/PHASE_1_ACTOR_READY_EXECUTION_PLAN.md).

The completed predecessor increment is preserved in
[`docs/PHASE_1_NEXT_INCREMENT_PLAN.md`](docs/PHASE_1_NEXT_INCREMENT_PLAN.md).
It prioritizes pre-action room-context binding and actual-client composition
fixtures, headless experiment artifacts/CLI and maintained generated tests,
and a separate narrow gold-claim conformance path. Event investigation is
nonblocking for rest composition. Pre-action context binding,
actual-client composition fixtures, experiment artifacts/CLI, named evidence,
the production gold evaluator, offline corpus codec and maintained generated
tests and the capture-off gold adapter are integrated. A bounded
campaign passed context-bound rest completion and inspection-map stale rejection;
the full chain remains unobserved because the route led to an elite. Cleanup
and a clean base-game launch/quit passed. Event-step identity stays fail-closed.
See the [execution ledger](docs/research/PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md)
for exact commits, reviews, residuals and evidence levels.

### 1. Better Evaluation Reporting

Completed foundation:

- evaluation results break down by encounter composition
- aggregate and per-encounter rows report win rate, reward, final HP, steps, and damage taken
- compare mode and `sts-benchmark` use explicit shared held-out seeds across policies

Next:

- use the brute-force oracle on tractable fixed seeds to report policy optimality gaps
- compare hindsight and information-aware regret so hidden future knowledge is not mislabeled as an agent weakness

Why:

- the env now contains more than one matchup
- aggregate win rate alone is no longer enough to understand policy quality

### 2. More Encounter Diversity

Completed foundation:

- corrected easy Slimes to one Leaf Slime (S), one random medium slime, and one Twig Slime (S)
- added Mawler with per-hit intents and the partial `overgrowth_hard_v1` pool
- added fixed two-Nibbit and Shrinker Beetle plus Fuzzy Wurm Crawler matchups

Next:

- add a few more enemy types or encounter pools before adding full progression
- keep them small and explicit
- prefer encounter diversity over a huge card pool at first

Why:

- prevents overfitting to a tiny enemy set
- improves the value of the environment as a benchmark

### 3. More Status Effects

- add `weak`
- add `frail`
- consider poison or simple damage-over-time later

Why:

- statuses create delayed value and more interesting planning
- the codebase already has a basic status foundation

### 4. More Cards With Sequencing Decisions

Completed foundation:

- added Pommel Strike and Shrug It Off for draw decisions
- added Iron Wave for mixed block/attack sequencing
- added Body Slam for block-dependent damage
- kept the canonical starter deck as the default and exposed an optional research preset

Completed deck-selection foundation:

- added a named, pickle-safe deck registry to `CombatEnvFactory`, initially with
  `starter` and `ironclad_sequencing`, while keeping `starter` as the default
- added a `--deck` option to training and the matching configuration/sweep fields;
  expose the same selection in watch, benchmark, and other evaluation tools so
  checkpoints can be tested with the deck they were trained on
- persisted the resolved deck name in checkpoint metadata, traces, benchmark
  reports, and experiment summaries

Next for deck training distributions:

- add a later `--deck-set` option for named, versioned training distributions
  that can sample a different supported deck for each episode
- make deck sampling deterministic through the environment seed/RNG and support
  explicit uniform or configured weighted distributions
- report evaluation both per fixed deck and over the sampled deck distribution,
  using matched seed grids so deck robustness is not hidden in one aggregate
- require every deck in a sampled set to share a compatible observation/action
  schema, and fail before training when dimensions or supported cards differ
- establish a uniform mixed-deck baseline before considering curricula that
  gradually change deck probabilities during training

Good next card types:

- multi-hit attacks
- cards that care about statuses

Completed representation foundation before expanding to a broad card catalog:

- added opt-in `card_records_v1` semantic records for cost, damage,
  block, draw, targeting, statuses, exhaust, and dynamic-damage rules
- combined those semantics with a small learned embedding keyed by the existing
  append-only card ID so cards with unique behavior remain distinguishable
- represented pile contents as exact `(card ID, count)` records processed by a
  shared card encoder and fixed-width pooling layer, rather than one
  permanent column per supported card and pile
- preserved exact card names and counts in structured observations for debugging;
  the compact representation is only the RL encoding layer

Next for card representation:

- integrate `card_records_v1` with policy inputs, rollout/replay storage, and
  checkpoint preflight without changing the structured observation
- implement the documented checkpoint contract: representation version, schema
  fingerprint, registry prefix, maximum trained card ID, capacities, and
  embedding dimensions
- keep existing models labeled `legacy_flat` and require retraining for the
  future card-record policy path rather than silently adapting weights

Why:

- increases decision depth without requiring a much larger engine rewrite
- named deck selection makes non-default-deck experiments reproducible through
  the supported CLI instead of one-off Python environment factories
- multi-deck sampling can reduce overfitting to one deck composition and test
  whether policies learn transferable card and sequencing concepts
- the current encoding adds 14 observation values and one action-identity
  feature for every supported card, which becomes sparse and repeatedly breaks
  checkpoint dimensions as the catalog grows
- semantic features allow policies to transfer knowledge between mechanically
  similar cards while embeddings retain card-specific information

### 5. Trace-Guided Policy Improvement

- compare analyzer findings across heuristic, DQN-family, and PPO agents
- use those findings to guide reward tweaks, imitation data, or curriculum choices
- consider simple behavior-cloning pretraining from the heuristic baseline

Why:

- the repo now has trace analysis and an action-conditioned PPO path
- the next leverage point is reducing recurring tactical mistakes, not just adding more algorithms

## Medium-Term Direction

These are good next layers once the near-term items are in a solid place.

### Broader Action-Conditioned Policies

Completed foundation:

- added `shared_enemy` as an opt-in architecture for DQN, Double DQN, and Dueling
  Double DQN
- reused the PPO design: one encoder for every stable enemy slot,
  permutation-invariant pooling for encounter context, and the selected enemy
  embedding for targeted action scores
- removed `target_slot_fraction` from the learned action inputs in this mode so
  swapping equivalent enemy slots produces equivalent Q-values
- gave Dueling Double DQN a compatible invariant value stream and target-aware
  advantage stream
- extended training and sweep CLI choices, checkpoint metadata/loading, benchmark
  compatibility checks, and configuration examples
- added enemy-slot permutation-equivariance, training-smoke, and checkpoint
  round-trip tests for every supported DQN-family variant

Next:

- compare `shared_enemy` against `action_feature` on identical fixed-seed
  multi-enemy benchmarks before changing any default

Why:

- the existing DQN `action_feature` architecture shares an action scorer but
  still encodes enemy slots as one flat ordered state, allowing arbitrary
  slot-specific preferences
- shared enemy encoding should improve transfer between encounter layouts and
  prevent target decisions from depending on incidental slot order

### Better Observation Features

- consider richer deck-order uncertainty summaries
- possibly add compact history features if needed
- only do this when there is a clear learning bottleneck

Why:

- representation quality has already proven to matter a lot in this project

### Better Experiment Tooling

Completed foundation:

- versioned fixed-seed benchmark reports
- deterministic comparison tables and JSON output
- a resumable full-system campaign with parallel equal-transition training,
  isolated equal-time finalist runs, cross-deck testing, historical checkpoint
  inventory, card-record microbenchmarks, and deterministic robust rankings

Next:

- optional plotting utilities
- run the balanced campaign regularly as encounter/card coverage grows and use
  its paired results to decide whether shared-enemy or card-record policies
  should become defaults

Why:

- makes the project more useful as a research sandbox

## Later In The Combat Simulator, But Not Yet

These items refer to the Python research simulator. Some now have deliberately
narrow live-bridge contracts, but they should still wait in the simulator until
the combat core and the Phase 1 backend decision are more mature.

- relics
- potions
- multiple combat acts or map progression
- events or shops
- a large generic event-hook system
- full Slay the Spire parity

Why not yet:

- they add a lot of surface area quickly
- they can dilute the project’s value as a clean RL testbed if added too early

## Guidance For Choosing The Next Task

If unsure what to implement next, prefer work that does one of these:

1. improves benchmark quality
2. improves learning signal or observability
3. adds strategic depth without exploding engine complexity
4. keeps the simulator easy to reason about

Avoid work that mostly adds content volume without improving the research usefulness of the environment.

## How To Update This File

Update `ROADMAP.md` when:

- a near-term priority is completed
- priorities noticeably change
- a previously “later” item becomes immediate

When making a major architectural choice while doing that work, also update [DECISIONS.md](DECISIONS.md).

## Current room-control increment

Shop and event functional implementations now have reviewed cores/native
adapters and actual cross-language fixtures, including one frozen item child.
The single combined runtime/bootstrap/package now passes independent full
release acceptance. The next gate is bounded live shop/event testing with a
user-prepared exact screen. See the
[release ledger](docs/research/PHASE_1_ROOM_RELEASE_V1_ACCEPTANCE.md).
Rest-site card upgrades remain unsupported; no upgrade scope was added.
