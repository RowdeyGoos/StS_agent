# Multi-Agent Execution Model

- **Status:** operating guide
- **Scope:** coordinated development by several agents or contributors working
  in parallel on this repository

This document defines how to use concurrency without losing correctness,
architectural coherence, or the user's understanding of the work. It complements
[AGENTS.md](../AGENTS.md), which remains the source of repository workflow and
invariants, and
[LONG_TERM_ARCHITECTURE_ROADMAP.md](LONG_TERM_ARCHITECTURE_ROADMAP.md), which
defines the strategic destination and dependency order.

This is an operating model, not a requirement to keep several agents busy.
Concurrency is useful only when work can proceed behind stable boundaries.
Sequential work is preferable when a shared contract is still unsettled or when
several tasks would edit the same state transition.

## 1. Desired outcome

A successful multi-agent effort has four properties:

1. each workstream has a bounded objective and an accountable owner;
2. agents can make progress without silently invalidating one another's
   assumptions;
3. integration is supported by evidence, not by optimistic status reports;
4. the user receives a concise account of outcomes, decisions, risks, and next
   milestones rather than a transcript of internal coordination.

Parallelism should shorten the critical path. It must not create a second,
hidden critical path made of merge conflicts, incompatible schemas, duplicated
implementations, or repeated user clarification.

## 2. Operating principles

1. **Dependencies determine concurrency.** Start work only when its required
   contracts and inputs are available, or make the task explicitly exploratory
   and read-only.
2. **One owner per writable boundary.** A source file, schema, or shared contract
   has one active write owner at a time.
3. **Contracts precede consumers.** State, action, observation, trajectory,
   content, and checkpoint changes are reviewed before several lanes build on
   them.
4. **Rules remain authoritative.** Agents and representations consume legal
   actions and transitions; they do not recreate game legality independently.
5. **Evidence travels with the change.** Every handoff names the validation
   performed, the exact scope covered, and any unresolved limitation.
6. **Repository invariants survive delegation.** Canonical package paths,
   deterministic seeded behavior, structured observations, stable identity, and
   Python 3.10+ compatibility apply to every lane.
7. **User authority is not delegated.** Parallel agents do not broaden scope,
   approve destructive actions, choose the target game benchmark, or make
   external commitments on the user's behalf.
8. **The coordinator integrates; it does not merely collect answers.** Conflicts,
   duplicated proposals, and incompatible evidence are resolved before results
   are presented as complete.
9. **Small coherent batches beat broad speculative edits.** Prefer one vertical
   slice with an end-to-end test over many disconnected partial implementations.
10. **Concurrency is reversible.** Work should be easy to pause, isolate,
    review, or discard without damaging unrelated user changes.
11. **Do not impose an arbitrary worker cap.** Dispatch every dependency-ready
    task with exclusive writable ownership when review and integration capacity
    are available; shared contracts and semantic join points, not a default
    headcount, determine what must remain sequential.

## 3. Workstream lanes

The long-term program naturally separates into the lanes below. The same model
also applies to shorter combat-prototype work: use only the lanes that the
current milestone needs.

| Lane | Primary ownership | Typical outputs | Main prerequisites |
| --- | --- | --- | --- |
| Target and governance | benchmark charter, information boundary, versions, licenses, approval record | target charter, version policy, decision records | user direction |
| Live integration | game bridge, capability discovery, synchronization, recovery | protocol spike, captured traces, bridge tests | target build and allowed integration scope |
| Contracts | state, decision, action, transition, manifest, trajectory, snapshot, policy/value provider, planner, and strategy-router interfaces | versioned schemas and compatibility tests | target charter and bridge evidence |
| Rules and simulation | run/combat state, effects, events, RNG, legality, snapshots | deterministic engine slices and scenario builders | accepted contracts |
| Content and conformance | normalized definitions, mechanic fixtures, live/simulator comparisons | content manifests, golden traces, coverage matrix | bridge plus rules primitives |
| Observation and representation | public projection, information state, optional memory/belief, tokenization, candidate tensors | leakage tests, encoders, schema fingerprints | public-state and candidate contracts |
| Planning and agents | heuristic, policy/value-provider, router, and tactical/strategic planner implementations | swappable strategies, models, runtime controller | stable candidates, provider/planner contracts, snapshots, value semantics |
| Data and training | recorder, datasets, actors, learners, reanalysis, exact resume | versioned datasets and checkpoints | trajectory contracts and validated simulator |
| Evaluation | correctness gates, regret, paired benchmarks, statistics, certification | independent reports and sealed results | declared target, manifests, reproducible artifacts |
| Integration and documentation | merge train, release notes, architecture consistency, user reporting | integrated branch, updated decisions and docs | outputs from all active lanes |

### 3.1 Dependency spine

The default critical path is:

> target charter → live evidence → shared contracts → conformance-tested rules →
> complete run → strategic learning and search → sealed certification

Useful parallelism exists around that spine:

- bridge discovery, benchmark design, and current-repository audits can begin
  together after the target scope is known;
- contract consumers may build read-only prototypes against checked-in fixtures
  while the contract owner finalizes the interface;
- content definitions, conformance capture, representation experiments, and
  performance harnesses can proceed in parallel after the relevant contract is
  frozen for the milestone;
- training infrastructure can mature alongside rules work, but large-scale
  training is gated on supported-mechanic fidelity;
- evaluation starts early and remains independent, even though final
  certification comes last.

### 3.2 Dependency states

Every task dependency is labeled as one of:

- **hard:** work must not begin until the dependency is accepted;
- **fixture:** work may use a versioned fixture or mock, but cannot claim
  integration until the real dependency lands;
- **advisory:** a related task may alter details, but not the task's core
  contract;
- **none:** the task is genuinely independent.

Calling a hard dependency “advisory” to increase concurrency is an anti-pattern.

## 4. Roles within an execution cycle

Roles are assigned per task or milestone; they are not permanent ranks.

### 4.1 Coordinator

The coordinator:

- translates the user's objective into a dependency-aware execution graph;
- assigns task and file ownership;
- identifies shared contracts and names their owners;
- keeps a compact progress and decision ledger;
- resolves conflicting recommendations;
- sequences review and integration;
- consolidates approval questions for the user;
- provides milestone updates and the final self-contained handoff.

The coordinator should retain enough direct understanding to review interfaces
and evidence. Delegation is not a substitute for reading the relevant code and
documentation.

### 4.2 Lane owner

A lane owner is accountable for one coherent outcome. The owner may delegate
bounded subtasks but remains responsible for:

- keeping delegated work within the lane contract;
- reviewing returned changes and evidence;
- notifying dependents of contract changes;
- providing one integrated lane handoff rather than several incompatible
  fragments.

### 4.3 Contract owner

Every shared contract has exactly one active owner. The contract owner:

- publishes the current version or draft;
- decides local naming and representation details within accepted architecture;
- maintains compatibility and migration notes;
- reviews every change to that contract;
- communicates a freeze, revision, or withdrawal to all consumers.

Contract ownership applies to semantic boundaries, not only files. For example,
the structured observation contract can span state types, projection code,
fixtures, and schema documentation.

### 4.4 Implementer

An implementer owns a bounded change and its focused tests. The implementer must
not silently modify adjacent contracts to make the task easier.

### 4.5 Reviewer or verifier

For high-risk work, use an agent or contributor who did not author the change to
verify:

- semantics and edge cases;
- conformance with the accepted contract;
- validation quality;
- migration and compatibility impact;
- hidden-information and determinism boundaries where applicable.

The verifier may be read-only. Independent review is still valuable when no
separate branch or pull request exists.

## 5. Task design

Parallel tasks must be concrete, bounded, independently checkable, and useful
even if another lane finishes later.

### 5.1 Required task brief

Use this template for every delegated implementation or review:

- **Task ID and title:** stable short identifier
- **Outcome:** one observable result, phrased as a completed state
- **Context:** why the result matters and which milestone it serves
- **Inputs:** accepted contracts, fixtures, branches, decisions, and source docs
- **In scope:** exact behavior or questions to handle
- **Out of scope:** adjacent work that must not be inferred
- **Owned files:** files or directories this task may edit
- **Read-only dependencies:** files the task may inspect but not edit
- **Contract version:** schema or interface version assumed
- **Acceptance evidence:** tests, traces, measurements, or review criteria
- **Required documentation:** README, DECISIONS, project context, roadmap, or none
- **Risk level:** low, medium, or high, with the reason
- **Blockers and approval gates:** known decisions that require escalation
- **Handoff format:** files changed, evidence, limitations, and dependent
  follow-ups

For a read-only task, replace owned files with “none” and explicitly prohibit
edits.

### 5.2 Good task boundaries

Good parallel tasks usually:

- own different files and different semantic responsibilities;
- consume an already accepted interface;
- produce a fixture, test harness, audit, or benchmark that another lane can use;
- have one clear completion condition;
- can be reviewed without reconstructing the entire program.

Examples:

- define snapshot round-trip property tests against an accepted state contract;
- audit a live bridge and return a capability matrix without adopting it;
- port one mechanic family after the effect ordering contract is frozen;
- build a tokenization prototype from immutable recorded decision fixtures;
- independently review public-observation leakage for one vertical slice.

### 5.3 Poor task boundaries

Do not delegate tasks such as:

- “improve the simulator”;
- “add several cards and fix any architecture needed”;
- “make the model near optimal”;
- “update all affected files” without naming the shared contract owner;
- two implementations of the same contract unless the task is an explicit,
  read-only design comparison.

## 6. Ownership and file boundaries

### 6.1 Exclusive write ownership

At the start of a cycle, record an ownership table:

| Path or semantic boundary | Owner | Mode | Contract/version | Dependents |
| --- | --- | --- | --- | --- |
| example path | task ID | write or read-only | version | task IDs |

Rules:

- one active writer per file;
- directory ownership does not permit editing a shared file owned by another
  task;
- read access is unrestricted unless data is protected, but reading does not
  grant mutation authority;
- a task that discovers it must edit an unowned file pauses that part of the
  work and requests ownership from the coordinator;
- ownership transfers are explicit and include a handoff of uncommitted changes,
  assumptions, and validation status.

### 6.2 Shared and high-contention files

Treat these as integration-owned unless a task brief explicitly assigns them:

- AGENTS.md;
- DECISIONS.md;
- ROADMAP.md;
- docs/PROJECT_CONTEXT.md;
- docs/LONG_TERM_ARCHITECTURE_ROADMAP.md;
- docs/PHASE_0_TARGET_CHARTER.md;
- docs/PHASE_1_INTEGRATION_SPIKE.md;
- docs/MULTI_AGENT_EXECUTION.md;
- game/__init__.py;
- package and dependency manifests;
- central registries, schema fingerprints, and public export lists;
- versioned state/action/trajectory contracts;
- shared CLI parsers and benchmark campaign definitions.

Feature lanes should return the required documentation or export delta in their
handoff. The integration owner applies the consolidated edit after the code and
decision are accepted.

### 6.3 Existing user changes

The worktree may already be dirty. Every agent must:

- inspect relevant status before editing;
- assume pre-existing changes belong to the user or another lane;
- avoid reformatting, reverting, staging, or committing unrelated changes;
- stop on an overlapping unexpected edit rather than overwriting it;
- use explicit paths when staging or reviewing.

Destructive recovery commands are never a conflict-resolution tool.

### 6.4 Generated artifacts

Generated files need an owner and a reproducible generator. Do not have one lane
edit generated output while another edits its source. Record whether generated
benchmarks, manifests, or fixtures are checked in, ephemeral, or protected
evaluation data.

## 7. Branches, worktrees, and shared workspaces

### 7.1 Default branch model

For code-producing lanes, prefer one isolated worktree and branch per coherent
task. Use the repository branch prefix codex/, followed by a short milestone and
task name.

An integration branch or designated integration worktree receives reviewed work
in dependency order. Dependent branches update from the accepted contract
revision before final validation.

### 7.2 When a shared worktree is acceptable

A shared worktree is acceptable when:

- all but one task are read-only;
- writers own disjoint files and do not run repository-wide rewrite tools;
- tasks are short and the coordinator can see every active write boundary;
- no task needs independent Git history or a conflicting dependency version.

In a shared worktree:

- never stage all changes indiscriminately;
- never commit another task's files;
- do not run global formatters unless every affected path is owned;
- re-check file contents immediately before applying a patch;
- notify the coordinator as soon as an unexpected change appears.

### 7.3 When isolation is required

Use separate worktrees when:

- two lanes touch nearby code or tests;
- a shared contract is being revised;
- dependency or generated-file changes differ;
- a task requires broad mechanical rewrites;
- a long experiment or migration should not block other work;
- independent review or rollback matters.

### 7.4 Commit discipline

Each task should produce reviewable commits that:

- contain only its owned scope;
- describe the behavior or contract changed;
- include tests with the implementation where practical;
- avoid drive-by cleanup;
- do not conceal generated or formatting churn.

Agents must not use hard resets, broad checkouts, or history rewriting to resolve
integration problems. Prefer a normal rebase or merge after inspecting the
conflict, and ask before any destructive recovery.

## 8. Shared-contract protocol

Shared contracts include state, identity, actions, legal candidates, effects,
events, observations, RNG, snapshots, trajectories, content manifests,
representations, checkpoints, and evaluator semantics.

### 8.1 Contract lifecycle

Use these states:

1. **proposed:** alternatives and unknowns are still open;
2. **accepted for slice:** stable enough for named consumers in one milestone;
3. **implemented:** reference implementation and fixtures exist;
4. **verified:** compatibility, round-trip, and integration evidence pass;
5. **superseded:** a new version exists with an explicit migration boundary.

Only read-only prototypes should depend on a proposed contract.

### 8.2 Contract change packet

Any shared-contract change must identify:

- old and new semantics;
- motivation and alternatives considered;
- affected producers and consumers;
- compatibility classification: compatible, adapter-required, retraining
  boundary, data migration, or intentionally breaking;
- schema/version/fingerprint change;
- fixtures and tests that demonstrate the new contract;
- rollout order;
- rollback or fail-closed behavior.

Meaningful architecture or training-default choices belong in DECISIONS.md once
accepted. Short-lived implementation discussion belongs in the execution
ledger, not in permanent decision history.

### 8.3 Freeze windows

For a vertical slice, freeze the minimum contract set needed by parallel
consumers. A freeze is scoped and time-bounded; it does not claim the interface
is final for the project.

If the contract must change during the window:

1. the contract owner marks the old revision withdrawn;
2. consumers stop integration work at a safe point;
3. the owner publishes the semantic delta and new fixtures;
4. dependents acknowledge whether they will migrate, finish behind an adapter,
   or be discarded;
5. integration resumes only after version alignment.

### 8.4 Contract tests

Prefer executable contract tests over prose alone. Depending on the boundary,
include:

- serialization and fingerprint fixtures;
- legal-action soundness/completeness cases;
- snapshot/restore continuation;
- deterministic replay;
- observation leakage checks;
- backend capability and error behavior;
- checkpoint preflight and explicit incompatibility rejection.

## 9. Cross-agent communication

Communication should be timely, structured, and proportional to impact.

### 9.1 Required messages

An active task sends:

- **acknowledgement:** scope, owned files, and assumptions understood;
- **contract notice:** any discovered ambiguity or required shared change before
  implementing it;
- **dependency publication:** a contract, fixture, commit, or artifact is ready
  for consumers;
- **risk notice:** evidence invalidates the current plan or reveals user-impacting
  scope;
- **handoff:** result, files, validation, limitations, and follow-ups;
- **blocker:** exact condition, checks attempted, and authority or input needed.

### 9.2 Message format

Use a compact structure:

- **Task:** ID
- **State:** active, ready for review, blocked, or done
- **Outcome/change:** one paragraph
- **Contract impact:** none or exact version/delta
- **Evidence:** commands, fixtures, or measurements
- **Needs:** decision, review, dependency, or none

### 9.3 Routing

- Send local implementation detail directly to the affected lane owner.
- Copy the coordinator on contract changes, schedule changes, blockers, and
  completed handoffs.
- Do not ask the user questions independently. Route approval needs through the
  coordinator so the user receives one consolidated, contextual question.
- Do not repeatedly poll another task when a dependency publication or bounded
  wait is sufficient.
- Do not broadcast routine progress that has no effect on another lane.

The final point governs internal cross-agent traffic. It does not permit the
coordinator to leave the user without a useful status update during sustained
active work.

### 9.4 Assumption discipline

Every assumption is one of:

- **verified:** supported by code, a fixture, or authoritative source;
- **contractual:** deliberately chosen and recorded;
- **working:** safe and reversible for local progress;
- **blocking:** materially changes the result and requires a decision.

Working assumptions are stated in the handoff. Blocking assumptions are not
silently converted into implementation choices.

## 10. Review and merge gates

No task is complete merely because its author finished editing.

### 10.1 Review gates

Apply gates in proportion to risk:

1. **Scope gate:** only owned and requested behavior changed.
2. **Semantic gate:** implementation matches the accepted rule or contract.
3. **Invariant gate:** determinism, explicit RNG, inspectable state, stable
   identity, and structured/encoded separation remain intact.
4. **Compatibility gate:** consumers, adapters, schemas, checkpoints, and
   migrations are identified.
5. **Validation gate:** focused tests pass and broader relevant regressions run.
6. **Conformance gate:** game-rule changes match authoritative traces for the
   supported slice.
7. **Information gate:** public inputs contain no hidden state or hindsight
   outcome.
8. **Performance gate:** hot paths meet a predeclared benchmark or include a
   measured regression justification.
9. **Documentation gate:** durable assumptions and supported commands are
   updated in their canonical documents.
10. **Integration gate:** the accepted aggregate, not only each branch in
    isolation, passes validation.

### 10.2 Risk levels

**Low risk**

- isolated documentation clarification;
- focused test addition;
- internal refactor with unchanged public behavior.

Author plus integration review may be sufficient.

**Medium risk**

- new content using existing primitives;
- localized training or analysis behavior;
- additive CLI or artifact field.

Require focused tests, consumer review, and relevant regression suites.

**High risk**

- state/action/observation semantics;
- RNG or event ordering;
- public-information boundary;
- serialization, snapshots, manifests, or checkpoint compatibility;
- live-game mutation/control;
- reward/objective or evaluation methodology;
- broad dependency, package, or repository restructuring.

Require an accepted decision/contract packet, independent review, targeted and
integration evidence, and any applicable user approval.

### 10.3 Merge order

Merge in dependency order:

1. accepted contract and fixtures;
2. reference producer or rules implementation;
3. consumers and adapters;
4. conformance and integration tests;
5. consolidated documentation and exports;
6. performance or training changes that rely on the integrated behavior.

If independent branches all modify tests for the same contract, the integration
owner consolidates them rather than accepting contradictory fixtures.

### 10.4 Final integration review

Before calling a milestone complete:

- inspect the aggregate diff;
- confirm no unrelated user changes were included;
- run the agreed integration test matrix;
- verify manifests and generated artifacts;
- review unresolved TODOs and skipped tests;
- confirm every task handoff is represented or deliberately rejected;
- update the progress ledger and durable decisions;
- prepare a self-contained user report.

## 11. Evidence and validation

### 11.1 Completion evidence

Every implementation handoff includes:

- exact files changed;
- behavior added or altered;
- commands run and their result;
- tests not run and why;
- compatibility or schema impact;
- known limitations;
- suggested dependent validation.

Never report “tests pass” when only a subset ran. Name the subset.

### 11.2 Repository baseline

Use the validation guidance in AGENTS.md. The normal regression commands are:

    python3 -m compileall game tests
    PYTHONPATH=. python3 -m pytest -q

Use the repository virtual environment when dependencies are unavailable from
the system interpreter. Run focused tests during implementation and the broader
suite at integration.

### 11.3 Change-specific evidence

Simulation and rules changes should include, as applicable:

- focused mechanic tests;
- same-seed and same-action deterministic continuation;
- card/pile/entity conservation;
- event-order assertions;
- snapshot/restore round trips;
- legal-action completeness and rejection tests;
- structured observation inspection;
- live differential fixtures.

Observation changes normally require review of:

- game/simulation/core.py;
- game/simulation/encoding.py;
- game/simulation/action_features.py;
- game/agents/baselines.py;
- simulation and agent tests;
- game/cli/demo.py.

Action changes normally require review of:

- game/simulation/actions.py;
- game/simulation/core.py;
- game/simulation/encoding.py;
- game/simulation/action_features.py;
- masks, agents, traces, oracle/search, and CLI consumers.

The owning task does not automatically gain write ownership of all these files;
the list defines the consumer review surface.

### 11.4 Conformance evidence

For mechanics intended to match STS2:

- identify the pinned game build;
- record the authoritative pre-state, legal candidates, action, ordered effects,
  and post-state;
- state which fields are public versus privileged;
- compare the simulator at decision boundaries;
- record acknowledged divergences explicitly;
- fail closed on unsupported mechanics.

Wiki or prose sources can guide discovery, but they do not replace observed
behavior from the pinned game for certification.

### 11.5 Performance evidence

Performance claims name:

- workload and content version;
- hardware and process configuration;
- warm-up and measurement method;
- transitions, candidates, snapshots, search nodes, or learner updates measured;
- correctness checks enabled;
- baseline and uncertainty or repeated-run variation.

A faster result with different semantics is not a performance improvement.

## 12. Decision authority and approval gates

### 12.1 Delegated authority

Within an accepted task brief, agents may decide:

- local implementation details;
- private helper structure;
- focused test organization;
- reversible diagnostics and read-only inspection;
- minor naming that does not alter a shared contract.

The coordinator may:

- sequence tasks and reviews;
- reassign file ownership;
- choose between equivalent, reversible implementation approaches;
- reject incomplete or unsupported handoffs;
- pause concurrency when dependencies become unstable.

### 12.2 Contract and architecture authority

Contract owners can propose and refine shared interfaces, but acceptance requires
the designated architecture/integration review. Changes to core assumptions are
recorded in DECISIONS.md.

The short-term ROADMAP.md changes only when near-term priorities materially
shift. The long-term roadmap changes only when the strategic architecture or
phase dependency order changes.

### 12.3 User approval required

Escalate a consolidated question before:

- materially changing the user's stated scope or success criterion;
- choosing the pinned game build, character, difficulty, information policy, or
  near-optimal threshold when not already authorized;
- performing destructive or difficult-to-recover operations;
- making external writes, messages, releases, or publications not already in
  scope;
- installing or adopting a dependency with meaningful license, security, or
  distribution consequences;
- enabling a live-game bridge to mutate game state beyond an approved local
  spike;
- intentionally abandoning compatibility or user data when the migration choice
  is not already decided;
- spending a materially larger compute, time, or monetary budget;
- selecting between alternatives that produce meaningfully different user
  outcomes.

Do not escalate routine, reversible implementation choices. Present the
evidence, options, recommendation, and consequence in one question.

## 13. Progress and decision tracking

### 13.1 Execution ledger

Maintain one ledger per milestone in the project's chosen issue, pull request,
campaign artifact, or temporary coordination document. Avoid turning
ROADMAP.md into a task board.

Each task record contains:

- task ID, title, owner, and lane;
- state: backlog, ready, active, review, blocked, done, or dropped;
- hard and fixture dependencies;
- owned paths;
- contract versions;
- latest evidence;
- blocker or review owner;
- resulting commits/artifacts;
- follow-up tasks.

Only one state is current. “Done” means accepted and integrated, not merely
implemented on a branch.

### 13.2 Decision ledger

Track temporary decisions with:

- decision ID;
- question;
- evidence;
- alternatives;
- decision and owner;
- date/version;
- affected tasks;
- revisit trigger.

Promote durable architecture and training-default choices to DECISIONS.md.
Discard routine implementation decisions after the milestone closes.

### 13.3 Progress truth

Report three separate quantities when useful:

- implementation complete;
- review/validation complete;
- integrated and accepted.

Collapsing these into one percentage hides the actual critical path.

## 14. User-facing milestone updates

The user should not need to follow agent names, internal messages, branch churn,
or routine test retries. Updates lead with the project outcome.

Send an update when:

- coordinated work begins, stating the intended outcome and parallel lanes;
- a meaningful milestone or vertical slice completes;
- evidence changes the plan;
- a user decision is needed;
- risk, scope, or expected outcome materially changes;
- a long-running task reaches a useful checkpoint.

During a long interactive work period, send a compact progress update at the
platform's required cadence even when no milestone has completed. For work that
runs outside one interactive turn, report at each bounded checkpoint and do not
let routine activity obscure a blocker. Blockers and material plan changes are
reported immediately.

Use this compact format:

- **Milestone:** what is now true
- **Evidence:** the most relevant tests, traces, or measurements
- **Decisions:** accepted choices or “none”
- **Risks:** unresolved material risks or “none newly identified”
- **Next:** the next dependency on the critical path
- **Need from you:** one concise approval/question, or “nothing”

Prefer one integrated update over one update per lane. The final response remains
self-contained even if earlier progress messages are collapsed.

## 15. Conflicts and blocked work

### 15.1 File conflict

When an agent finds unexpected overlapping edits:

1. stop editing the affected file;
2. preserve current work without reverting either version;
3. identify the active owner and source of both changes;
4. compare semantic intent, not only text conflicts;
5. let the owner or integration lead choose the combined result;
6. rerun all validation affected by the merge.

Do not resolve a conflict by taking “ours” or “theirs” wholesale unless review
shows the discarded side is genuinely unrelated or superseded.

### 15.2 Contract conflict

When two lanes assume different semantics:

1. pause dependent integration;
2. write the smallest concrete counterexample showing the conflict;
3. ask the contract owner to decide or version the alternatives;
4. update fixtures and the contract change packet;
5. migrate consumers deliberately;
6. invalidate evidence collected under the rejected semantics where necessary.

### 15.3 Evidence conflict

If tests, live traces, and documentation disagree, follow the truth hierarchy in
the long-term roadmap. For game behavior, the pinned build and normalized
authoritative trace outrank the simulator, learned features, and prose.

### 15.4 Blocker report

A blocker report contains:

- exact blocking condition;
- why safe in-scope work cannot continue;
- checks and alternatives attempted;
- tasks and milestones affected;
- smallest decision, permission, or external change that would unblock it;
- work that remains valid.

“This is difficult” is not a blocker. Missing authority, incompatible contracts,
unavailable required state, and repeated external failure can be.

### 15.5 Abandoned or failed task

If a task is interrupted or dropped:

- mark its branch/files and validation state;
- do not present partial code as integrated;
- retain useful read-only findings and fixtures;
- return ownership explicitly;
- either create a smaller recovery task or remove the work through a reviewed,
  recoverable operation.

## 16. Anti-patterns

Avoid:

- spawning many tasks before mapping hard dependencies;
- assigning two writers to the same contract or high-contention file;
- asking every agent to update DECISIONS.md or public exports independently;
- allowing consumers to code against different unstated schema drafts;
- broad “clean up anything nearby” mandates;
- repository-wide formatting from a narrowly owned task;
- hiding contract changes inside a feature implementation;
- duplicating game semantics in rules, metadata, previews, heuristics, and model
  features;
- declaring a lane complete because its own unit tests pass while integration or
  conformance is pending;
- training at scale before the supported simulator slice passes fidelity gates;
- treating bounded or hindsight search as an information-valid optimal teacher;
- exposing private engine state to make an agent input conveniently Markov;
- using policy RNG through the game RNG;
- preserving legacy checkpoints by distorting a better long-term contract;
- merging generated artifacts without recording their generator and manifest;
- using destructive Git commands to escape conflicts;
- staging or committing unrelated user or agent changes;
- sending the user raw internal chatter or asking the user to coordinate agents;
- remaining silent when evidence invalidates the plan;
- reporting implementation, review, and integration as the same status;
- adding concurrency after the critical path has become contract-bound.

## 17. Example: one mechanic vertical slice

Suppose the milestone is to add a mechanic family that introduces a nested card
selection during combat.

An effective execution graph is:

1. **Contract owner:** specify the pending-decision and incremental
   select/deselect/confirm candidate contract, with fixtures.
2. **Live integration lane:** capture public traces for the mechanic on the
   pinned build; capture privileged traces only when explicitly authorized for
   conformance and keep them on the separate diagnostic path.
3. **Rules lane:** implement suspension, selection legality, resume ordering, and
   snapshots against the accepted fixture.
4. **Content lane:** define one representative card using those primitives and
   build the differential test.
5. **Observation lane:** project the pending choice and tensorize its candidates
   without hidden fields.
6. **Agent lane:** add a candidate-scoring smoke test; no new global action head.
7. **Evaluation lane:** verify legal-action completeness, replay, leakage, and
   same-seed continuation.
8. **Integration owner:** merge in dependency order, run the aggregate suite,
   update durable decisions, and report the milestone.

The contract and trace tasks can run together during discovery, but rules,
representation, and policy integration do not begin against incompatible
guesses. This is less superficially concurrent than assigning the card to every
lane immediately, and substantially faster to integrate.

## 18. Checklists

### 18.1 Coordinator kickoff

- [ ] Read the repository documents in the order specified by AGENTS.md.
- [ ] State the user-visible outcome and explicit non-goals.
- [ ] Map hard, fixture, advisory, and absent dependencies.
- [ ] Name shared contracts and their owners.
- [ ] Assign non-overlapping write boundaries.
- [ ] Choose shared worktree or isolated worktrees deliberately.
- [ ] Define evidence and review gates per task.
- [ ] Record approval gates and avoid duplicate user questions.
- [ ] Start only tasks that can make valid progress.

### 18.2 Task handoff

- [ ] Outcome is complete within the brief.
- [ ] Changed files are all owned and listed.
- [ ] Contract assumptions and deltas are explicit.
- [ ] Focused validation ran.
- [ ] Broader validation status is truthful.
- [ ] Compatibility, determinism, information, and performance effects are noted.
- [ ] Limitations and follow-ups are named.
- [ ] No unrelated changes are staged or included.

### 18.3 Integration

- [ ] Contracts and producers merged before consumers.
- [ ] Aggregate diff reviewed.
- [ ] Conflicts resolved semantically.
- [ ] Relevant regression and conformance suites pass.
- [ ] Generated artifacts and manifests are reproducible.
- [ ] Shared exports and canonical docs are updated once.
- [ ] Durable decisions are recorded.
- [ ] Ledger marks accepted work done and incomplete work accurately.
- [ ] User update leads with outcome, evidence, risk, and next dependency.

## 19. Relationship to repository documents

- [README.md](../README.md) remains the user-facing setup and command guide.
- [AGENTS.md](../AGENTS.md) remains the coding-session guide and repository
  invariant list.
- [DECISIONS.md](../DECISIONS.md) records accepted durable architecture and
  training decisions.
- [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) describes the current technical state.
- [ROADMAP.md](../ROADMAP.md) tracks near-term priorities.
- [LONG_TERM_ARCHITECTURE_ROADMAP.md](LONG_TERM_ARCHITECTURE_ROADMAP.md) defines
  the destination and program dependency order.
- [PHASE_0_TARGET_CHARTER.md](PHASE_0_TARGET_CHARTER.md) owns accepted target
  choices and unresolved program approval gates.
- [PHASE_1_INTEGRATION_SPIKE.md](PHASE_1_INTEGRATION_SPIKE.md) owns the active
  live/fast-backend evidence campaign and its prerequisites.
- This document defines how several agents execute one accepted milestone
  without fragmenting those sources of truth.

When these documents appear to disagree, first determine whether the conflict is
about current state, short-term priority, long-term direction, or execution
process. Update the document that owns that kind of truth rather than duplicating
the correction everywhere.
