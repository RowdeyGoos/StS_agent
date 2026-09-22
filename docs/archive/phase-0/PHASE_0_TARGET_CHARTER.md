# Phase 0 Target Charter

- **Status:** active Phase 0 charter; Phase 0 exit gate not yet satisfied
- **Program target:** a functional and eventually defensible near-optimal
  single-player Slay the Spire 2 agent
- **Initial character:** Ironclad
- **Initial functional difficulty:** Ascension 0 (`A0`)
- **Certification difficulty:** the highest standard single-player difficulty
  available to Ironclad in the pinned target build
- **Target build:** Steam default/main build `23811903`, depot `2868842`
  manifest `8653035385353091849`, packaged release `v0.107.1`; see the
  [sanitized build manifest](../../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)

This charter makes the first target concrete. It instantiates the scope and
evidence requirements from
[`LONG_TERM_ARCHITECTURE_ROADMAP.md`](../LONG_TERM_ARCHITECTURE_ROADMAP_2026_09_22.md), which
remains the authority for the project's long-term architecture and dependency
order. This file owns the initial benchmark definition and its unresolved Phase
0 decisions. It does not replace the short-term [`ROADMAP.md`](../../../ROADMAP.md).

The durable program commitment is recorded in [`DECISIONS.md`](../../../DECISIONS.md).
Parallel work follows
[`MULTI_AGENT_EXECUTION.md`](../../MULTI_AGENT_EXECUTION.md), with this charter's
Accepted, Provisional, and TBD statuses supplying the relevant approval gates.

The project has not yet earned a functional, strong, or near-optimal claim.
In particular, the immutable `combat_v0` baseline freeze and the numerical
near-optimal thresholds described below are pending Phase 0 deliverables.
Existing benchmark outputs are exploratory research artifacts, not a committed
baseline release or certification campaign.

## 1. Target statement

The initial program target is:

> Build an autonomous agent that can play standard single-player Ironclad runs
> on one exactly pinned Slay the Spire 2 main-branch build, using a reproducibly
> unlocked profile and no gameplay modifications other than the declared
> observation/control bridge. The first end-to-end milestone is reliable A0 run
> completion. The eventual certification target is the highest standard
> single-player difficulty available to Ironclad in that pinned build. The actor
> receives only player-available information and observable history, does not
> receive or decode the run seed, and optimizes complete-run win probability
> under a named inference budget.

“Near optimal” will mean only an operational claim under the frozen build,
profile, information rules, evaluation population, and compute budget. It will
not mean a proof of global optimality.

## 2. Scope

### 2.1 Included

- Standard single-player play.
- Ironclad only for the first functional and certification campaigns.
- A reproducibly constructed or restored unlocked profile whose exact unlock
  state is captured in the benchmark manifest.
- A0 for the first functional full-run milestone.
- The maximum standard single-player difficulty offered to Ironclad by the
  pinned build for the eventual near-optimal certification campaign. Its exact
  in-game name and level are recorded during dedicated profile/mode
  verification; they are not inferred from binary metadata alone.
- One main-branch game build, selected and pinned when the first authoritative
  binary/build capture is made.
- Base gameplay with exactly one declared observation/control bridge in the
  ordered mod list. The bridge may transport state and actions and may bypass
  non-semantic presentation delays only when that behavior is declared and
  validated not to change rules, choices, or RNG outcomes.
- Every decision family reachable in the declared Ironclad profile and target
  mode: combat, card and other rewards, map, shop, rest site, event, treasure,
  boss/act transition, nested selections, and terminal flow.
- Both policy-only and planner-enhanced inference, reported separately.
- Live-game evaluation and a conformance-tested fast backend for training and
  search.

### 2.2 Excluded from the initial target

- Other characters.
- Co-op.
- Daily, custom, challenge, beta-branch, or modded gameplay modes.
- Gameplay-affecting, content, balance, convenience, or information-revealing
  mods beyond the declared bridge.
- Cross-patch leaderboards or aggregation of results from different builds.
- Seed lookup tables, seed decoding, RNG-state recovery from the displayed seed,
  or any other seed-specific privileged planning.
- Save-scumming, restarting a run to alter outcomes, or manual intervention in
  a scored run.
- Training or evaluating the deployed actor on hidden draw order, future random
  outcomes, hidden rewards, engine RNG state, or privileged debug fields.
- A claim that A0 functionality alone demonstrates strong or near-optimal play.
- A universal optimality proof, support for every future patch, or a calendar
  commitment.

## 3. Profile and run initialization

The target uses a reproducibly unlocked profile rather than an individual's
mutable everyday save. The construction, privacy, reset, recovery, and
validation procedure is designed in
[`PHASE_0_PROFILE_FIXTURE_PLAN.md`](PHASE_0_PROFILE_FIXTURE_PLAN.md). That design
does not complete this gate: the user created the dedicated project profile and
the approved metadata-only probe established a unique shallow local boundary,
and the separately approved D1B probe established that the current direct-child
projection matches the required core roles plus the predicted backup-sidecar
pair. No file content or hash was read, temporal identity with D1 is unproved,
and the construction method and exact unlock manifest remain open. See the
[`sanitized D1 result`](research/PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md)
and [`sanitized D1B result`](research/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md).
D1C was reviewed, deliberately unselected/skipped, and never executed; its
fail-closed predicate is incorporated into the exact frozen
[`PF-HASH-BASELINE-V1`](PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md) request. Its
first approved invocation
[stopped before target-content access](research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md)
because of a runner profile-component construction defect. That invocation
consumed its approval; no corrected rerun is currently authorized. Any eventual
content-only result would not prove recoverability, logical state, or Cloud
behavior.

Phase 0 must define one documented profile fixture with:

- the target build and platform;
- the exact profile/save files and cryptographic hashes, where retention and
  redistribution are permitted;
- a clean-profile-to-target procedure or a legally usable local restoration
  procedure;
- a normalized manifest of every gameplay unlock visible to the run generator;
- settings that can affect game rules, input, randomness, or available content;
- a verification command or checklist that fails if the loaded profile differs;
- a policy for profile mutations caused by completed runs and a reset procedure
  before each campaign.

The desired fixture exposes the normal unlocked single-player content intended
for Ironclad in the pinned build. The exact unlock inventory remains TBD until
the dedicated profile is captured; it may not be silently changed after a
campaign begins.

Each evaluation run starts from the frozen profile state and a registry-assigned
run seed. Runs are played once from start to natural victory, defeat, or a
predeclared infrastructure termination. Any restart, retry, or exclusion follows
the campaign's frozen failure policy and is recorded.

## 4. Information boundary and problem framing

### 4.1 Actor-visible information

The deployed policy, value model, memory, and planner may consume only:

- facts currently visible to a normal player through the supported game UI;
- rules and content knowledge that a player could know independently of the
  current run;
- publicly observable event and decision history from the current run;
- derived quantities computed solely from those public inputs;
- the authoritative legal action candidates for the current public decision.

The public-state projector is a security boundary. Privileged bridge fields may
exist for conformance or diagnosis, but they must use a separate schema and data
path and must be unavailable to the deployed actor. Certification requires both
automated leakage tests and an auditable record of the model inputs.

### 4.2 Seed policy

The run seed is recorded in protected run metadata so a trajectory can be
reproduced. It is not an actor input, even if the game UI can display it. The
actor may not receive the seed string, a hash or embedding derived from it, the
game's initial RNG states, or a seed-indexed retrieval result. Search begins
from the actor's public information state rather than the run's true hidden RNG
state.

Evaluation infrastructure may use the seed to start and pair runs. That use must
remain outside the actor process and model input contract.

### 4.3 Stochastic framing, history, and belief

The initial engineering model is a **mostly-observable stochastic sequential
decision process with limited hidden state**. Most strategically relevant facts
are public, but one current observation is not always sufficient: an
already-shuffled draw order can remain hidden, while publicly reconstructible
history and counters can matter. Future random choices or rewards that have not
yet been generated are chance transitions, not hidden current state.

The minimum actor therefore receives normalized public history sufficient to
reconstruct known facts. A recurrent or attention-based memory is permitted but
not mandatory. An explicit analytic, sampled, particle, or other belief model
is also optional and applies only to action-relevant persistent hidden state. It
is added only if controlled ablations on held-out information-sensitive states
show practically meaningful improvement after leakage checks. The project must
not add hidden simulator state merely because an explicit belief model is
difficult.

## 5. Objective and inference modes

### 5.1 Canonical objective

The canonical utility is the probability of winning the complete run under the
declared target rules. Victory and defeat must be defined from authoritative
terminal game states at build capture.

HP, gold, deck strength, relics, potions, act/floor reach, score, and combat
damage are diagnostics, auxiliary targets, or persistent consequences. They are
not interchangeable with run utility. Reward shaping may aid early training,
but final selection and certification use run wins and must demonstrate that
shaping has not silently replaced the objective.

### 5.2 Named inference modes

Every result identifies one of these modes:

1. **Policy-only.** A learned policy or declared deterministic heuristic scores
   the current legal candidates without online simulator lookahead. Recurrent
   state computed from public history is allowed.
2. **Planner-enhanced.** The same public-information actor may call the declared
   fast backend and policy/value models for bounded online search. Search may
   sample or maintain beliefs, but may not initialize from the live run's hidden
   world state or RNG state.

The modes have separate frozen budgets. Each budget must state per-decision and
whole-run wall time, search nodes and simulator calls, model size, memory,
hardware, batching, precomputation or retrieval, pause semantics, and timeout
behavior. The certification mode and both numerical budgets are TBD. The
expected strongest mode is planner-enhanced, but that expectation is
provisional until measured.

## 6. Milestones and success criteria

### 6.1 A0 functional milestone

The first full-run milestone is functional, not near-optimal. On the pinned
build and profile, the Ironclad controller must:

- start, play, and reach an authoritative terminal outcome on A0 without manual
  input for every scored run not terminated by a predeclared external outage;
- handle every decision type and nested/modal choice reachable in the supported
  A0 scope;
- choose only from the authoritative current legal candidate set;
- detect and safely report stale actions, rejections, timeouts, desynchronization,
  empty nonterminal candidate sets, and unsupported content;
- avoid silent no-ops, UI softlocks, undeclared restarts, and hidden human help;
- emit a replayable trajectory with complete state/action hashes, errors,
  latencies, manifests, and terminal result;
- reproduce supported simulator trajectories and pass the declared live/simulator
  conformance corpus;
- satisfy the preregistered A0 reliability threshold.

The number of A0 runs, acceptable infrastructure-failure rate, retry rules, and
other numerical reliability thresholds are pending Phase 0 statistics work.

### 6.2 Strong-agent milestone

Before near-optimal certification, a strong agent must:

- outperform the frozen deterministic heuristic and declared learned baselines
  on paired held-out runs by a preregistered practical margin;
- replicate the gain across multiple independent training seeds;
- retain performance across preregistered exogenous content/seed strata;
- show worthwhile paired improvement from search over policy-only inference at
  its additional compute cost;
- pass fidelity, leakage, replay, and reliability gates.

Exact margins and sample sizes are TBD pending independent pilot data and a
prospective precision/power analysis.

### 6.3 Highest-difficulty near-optimal certification

Certification is attempted only after first-character parity and functionality
at the highest standard difficulty in the pinned build. Under a frozen named
mode and budget, the agent must:

- satisfy a preregistered paired non-inferiority or equivalence test against the
  strongest trusted reference agent, with the full confidence interval inside
  the declared practical margin;
- achieve small information-aware regret on preregistered tractable decision
  families with exact, bounded, or independently high-confidence references;
- avoid catastrophic performance in every preregistered supported subgroup,
  subject to declared minimum sample sizes;
- show no material improvement under a stronger post-hoc search budget ladder
  on sampled states, with an independent reference method or model family where
  feasible;
- meet the frozen automation-failure, invalid-action, timeout, intervention,
  latency, and compute limits;
- pass all build, simulator-conformance, replay, artifact-integrity, and
  public-information leakage gates.

Failure to reject a difference is not equivalence. “No improvement found” is
evidence only relative to the declared audit, not an upper bound. The numerical
regret, non-inferiority/equivalence, subgroup, reliability, and search-audit
thresholds are **TBD Phase 0 deliverables and are not currently satisfied**.

## 7. Evaluation design

### 7.1 Seed and state registries

Before any model-selection experiment for a campaign, create disjoint,
content-addressed registries for:

| Split | Permitted use |
| --- | --- |
| Training | Actor collection, replay, curricula, search teaching, and fitting |
| Tuning-validation | Hyperparameter, architecture, curriculum, and checkpoint selection |
| Public regression | Stable release comparison and regression detection; not a repeatedly optimized hidden test substitute |
| Sealed certification | One model-selection-free final campaign; identities withheld from actor and learner until execution |

Simulator snapshots used as tactical or strategic evaluation cases follow the
same separation. A state, seed, or derived trajectory may not migrate from a
later split into an earlier one. Near-duplicate states and continuations must be
deduplicated across splits by semantic hashes or provenance, not only by file
name.

The seed sampling population, registry generator, split sizes, stratification,
and access controls are TBD and must be frozen before certification. Seed values
remain infrastructure metadata and never become actor features.

### 7.2 Comparisons and experimental units

- Compare agents on common root run seeds where possible. Because their actions
  can cause different subsequent random requests, pairing denotes a common
  starting seed, not identical realized randomness.
- Use deterministic evaluation policies/search when appropriate, or freeze and
  record independent policy/search sampling seeds and replicate them according
  to the statistics plan.
- Cross multiple independent model-training seeds with game seeds. Treat model
  seed, game seed, and any policy/search replicate as explicit experimental
  factors; do not count all rows from one checkpoint as independent evidence.
- Use a crossed random-effects analysis, two-way cluster bootstrap, or another
  preregistered method valid for the actual sampling design.
- Use paired effect estimates and confidence intervals. Certification uses a
  predeclared non-inferiority or equivalence margin, not null-hypothesis
  non-significance.
- Predeclare confidence level, prospective precision/power target, stopping
  rule, multiplicity handling, minimum subgroup sample sizes, and treatment of
  incomplete runs.
- Treat route, deck archetype, and other policy-selected outcomes as descriptive
  diagnostics, not unbiased comparative subgroups. Certification subgroups are
  based on exogenous pre-run seed/content features or fixed scenario
  interventions.

### 7.3 Failures and exclusions

The campaign statistics plan must distinguish policy failures, bridge failures,
host/service outages, and simulator mismatches before the first scored run.
Policy-caused illegal actions, timeouts, softlocks, or unrecovered errors count
against the agent and normally count as losses. Infrastructure exclusions or
reruns are allowed only under a narrow frozen rule independent of agent identity.
All attempts, exclusions, retries, crashes, manual interventions, and reasons
remain in the published raw rows.

Discovery of an unacknowledged gameplay-affecting simulator divergence or
information leak invalidates the affected performance claim. The campaign may
resume only under a new versioned campaign identity and, where exposure could
have influenced selection, a new sealed set.

### 7.4 Required reports

Report policy-only and planner-enhanced modes separately, including:

- wins, losses, completion, and paired deltas with confidence intervals;
- results across independent training seeds;
- preregistered exogenous strata and worst supported strata;
- invalid/rejected/no-op actions, retries, timeouts, interventions, and crashes;
- calibration and information-aware regret where valid references exist;
- per-decision and whole-run latency, nodes, simulator calls, memory, and
  hardware;
- simulator/live mismatch counts and known unsupported content;
- complete raw evaluation rows and exclusion annotations.

## 8. Build, bridge, and artifact pinning

### 8.1 First authoritative build capture

The binary/build identity was captured on 2026-08-29 after selecting Steam's
default `public` channel:

- Steam build `23811903`;
- depot `2868842`, manifest `8653035385353091849`;
- packaged release `v0.107.1`, commit `59260271`;
- universal macOS bundle with arm64 and x86-64 assemblies;
- individual executable, content archive, assembly, runtime, API sidecar, and
  mod-support dependency hashes;
- an aggregate SHA-256 identity over all 429 regular installation files.

The committed, sanitized record is
[`sts2-steam-main-build-23811903-macos-universal.json`](../../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
It stores hashes and project-authored metadata only, not binaries, assets, raw
Steam manifests, account identifiers, absolute user paths, or saves.

The 429-file aggregate is the clean base-install projection. A bridge-enabled
variant separately hashes its exact non-colliding overlay and must reproduce the
clean aggregate after excluding only those allowed overlay files; its raw
whole-tree hash is expected to differ. See the build-manifest integrity policy.

This resolves the exact binary/build decision. The following capture work
remains open:

- content, rules, state, action, observation, and protocol manifests;
- exact profile fixture and unlock-manifest hashes;
- exact bridge source revision, binary hash, configuration, permissions, and
  ordered mod list;
- rule-affecting settings and the exact in-game certification difficulty label;
- a legally reviewed old-build retention or reconstruction procedure.

The allowed mod list contains only the declared bridge. Development-only
privileged endpoints must be physically or configurationally disabled for
scored runs and their state recorded in the campaign manifest. If the game
patches, results remain attached to the old build; migration creates a new
benchmark identity rather than extending the old sample.

The game-build manifest identifies only the installed binary/build artifacts;
it does not identify a profile, enabled mods, or a bridge. The sanitized D1 and
D1B results establish only the dedicated profile's shallow local boundary and
current direct-child role/type projection. They are not a profile-content,
logical-state, mod, or recovery identity.
The Phase 1 integration campaign captures live decisions and transitions only
after the remaining identity prerequisites and information boundary are frozen.
The Phase 1 plan may be drafted and statically audited in parallel, but its
comparative execution cannot substitute for those Phase 0 deliverables.

### 8.2 Research artifact identity

Every dataset, trajectory, checkpoint, evaluation row, and report must bind to:

- game, profile, content, bridge, simulator/rules, and schema fingerprints;
- repository revision and dirty-state record;
- model architecture, checkpoint, optimizer/training configuration, and dataset
  hashes where applicable;
- seed-registry and evaluator versions;
- information boundary and policy/search mode;
- inference and training resource declarations;
- machine/runtime metadata and timestamps.

Trajectories retain normalized public states, legal candidates, chosen actions,
accepted/rejected outcomes, event ordering, state hashes, decision/search
metadata, errors, and terminal result. Privileged diagnostic data, if captured,
is stored separately and cannot be read by actor-ready data loaders.

### 8.3 Pending `combat_v0` baseline freeze

Phase 0 must create an immutable `combat_v0` baseline package containing the
current interface semantics, supported content, representative configs, tests,
seed policy, raw benchmark rows, environment metadata, and code/artifact hashes.
The package should preserve useful current DQN, PPO, heuristic, search, and
regret results as historical baselines without implying full-run ability.

This freeze has **not** happened yet. Current benchmark files, screenshots, and
working-tree outputs are not automatically part of the committed baseline. They
must be deliberately selected, regenerated where necessary, fingerprinted, and
reviewed before the baseline can be called immutable or reproducible.

## 9. Decision register

Statuses have precise meanings:

- **Accepted:** binding for this initial target unless this charter is revised.
- **Provisional:** preferred direction, but an evidence gate may replace it
  before campaign freeze.
- **TBD:** unresolved; the named Phase 0 or capture deliverable must decide it.

| Decision | Status | Current charter value or resolution rule |
| --- | --- | --- |
| Primary mode | Accepted | Standard single-player |
| First character | Accepted | Ironclad |
| Profile policy | Accepted | Dedicated, reproducibly unlocked, hashed fixture; exact unlock manifest captured before use |
| First full-run milestone | Accepted | Functional autonomous A0 completion; not a strength claim |
| Eventual certification difficulty | Accepted | Maximum standard Ironclad difficulty present in the pinned target build |
| Game branch | Accepted | Public main branch |
| Exact game build | Accepted | Steam default/main build `23811903`; depot `2868842` manifest `8653035385353091849`; packaged release `v0.107.1`; sanitized capture manifest linked in Section 8.1 |
| Allowed mods | Accepted | Exactly the declared observation/control bridge; no gameplay/content mods |
| Information boundary | Accepted | Player-available public state and observable history only |
| Run seed | Accepted | Recorded outside the actor; raw or derived seed data and decoding unavailable to policy/value/search |
| Canonical objective | Accepted | Complete-run win probability |
| Problem framing | Accepted | Mostly-observable stochastic sequential decision process with limited hidden state |
| Memory/recurrence | Provisional | Add only if held-out ablations show useful information-state benefit without leakage |
| Explicit particle/belief model | Provisional | Optional and evidence-gated; never initialized from true hidden world state |
| Inference modes | Accepted | Policy-only and planner-enhanced, benchmarked separately |
| Certification mode | TBD | Name one frozen mode and budget before campaign preregistration |
| Policy-only/search budgets | TBD | Resolve per-decision and whole-run compute contract |
| Bridge implementation | Accepted direction | Build the staged project-maintained bridge in `PHASE_1_RESTRICTED_BRIDGE_DESIGN.md`; runtime viability and production acceptance still require compile, load, passivity, phase, transaction, and recovery evidence |
| Fast backend | TBD | Python, engine-hosted, or hybrid based on measured fidelity, snapshots, throughput, and legal constraints |
| Evaluation split protocol | Accepted | Disjoint training, tuning-validation, public-regression, and sealed-certification registries |
| Split identities and sizes | TBD | Freeze after sampling-frame and power/precision design |
| Strong reference agents | TBD | Select and version before certification preregistration |
| Numerical functional thresholds | TBD | Reliability and coverage analysis deliverable |
| Numerical strong/near-optimal thresholds | TBD | Freeze practical margins, regret, subgroup, audit, reliability, sample-size, and prospective power/precision rules before Phase 0 exit |
| `combat_v0` baseline | TBD | Pending deliberate immutable baseline package; current artifacts are not a committed release |

## 10. Phase 0 deliverables

Phase 0 is complete only when the repository or associated immutable artifact
registry contains:

1. This charter reviewed with every accepted choice explicit and every remaining
   TBD assigned an owner and resolution milestone.
2. The exact main-build capture record and legally usable retention or
   reconstruction procedure.
3. The reproducible Ironclad profile fixture, unlock manifest, reset procedure,
   and hashes.
4. The bridge/mod declaration, public-information schema, privileged-data
   separation design, seed firewall, and leakage threat model.
5. The policy-only and planner-enhanced compute-budget templates, with the
   certification mode and final budgets resolved before its campaign.
6. A versioned seed/state registry design covering training, tuning-validation,
   public regression, and sealed certification.
7. A preregisterable statistics plan specifying the sampling population,
   independent training runs, experimental units, comparisons, confidence
   method, prospective power/precision, stopping, exclusions, failures,
   multiplicity, and subgroup rules.
8. Numerical A0 functional, strong, and near-optimal thresholds, practical
   margins, prospective power/precision analysis, and sample sizes, all frozen
   before Phase 0 exit. A later change creates a new versioned charter/campaign;
   it may use only the preregistered non-sealed pilot or blinded recalculation
   rule and never sealed outcomes.
9. The deliberately selected and fingerprinted immutable `combat_v0` baseline
   package. Existing artifacts do not satisfy this deliverable by default.
10. The semantic version/fingerprint scheme for build, profile, content, rules,
    backend, bridge, public state, actions, trajectories, datasets, models,
    checkpoints, seed registries, and evaluators.
11. A prior-art, bridge, license, data-rights, security, and artifact-distribution
    assessment.
12. A campaign checklist that prevents a performance run from starting when
    manifests, information boundaries, seed access, budgets, or evaluator
    versions do not match.

## 11. Phase 0 exit gate

The Phase 0 exit gate passes only when an independent reviewer can answer, from
immutable records and without inspecting implementation assumptions:

- exactly which game binary, branch, profile, unlock state, bridge, mods, and
  rules define the target;
- what the actor may observe and how seed/privileged-data access is prevented;
- what counts as a win, loss, automation failure, exclusion, retry, and manual
  intervention;
- which policy-only and planner-enhanced resource budgets are being compared;
- which data and seed split may be used for each research activity;
- which statistics, margins, sample sizes, subgroups, and reference agents will
  support each claim;
- how every run, model, dataset, and report is reconstructed and audited;
- what exactly belongs to the frozen `combat_v0` baseline.

No strong or near-optimal campaign may begin while its exact build, profile,
information contract, certification mode, resource budget, reference agents,
numerical thresholds, seed registries, or failure rules remain TBD. Phase 0
completion establishes a measurable target; it does not itself establish A0
functionality or any performance claim.
