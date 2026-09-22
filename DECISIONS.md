# Current decisions

This is the compact architectural record. [AGENTS.md](AGENTS.md) owns session
workflow; [current status](docs/STATUS.md) owns implementation
and evidence. Detailed earlier rationale, including D1–D64, remains in the
[historical decision log](docs/archive/DECISIONS_2026_09_08.md).
Historical process prescriptions do not override the decisions below.

## D65. Use proportionate validation and direct capability experiments

Accepted 2026-09-08 at the user's request after reviewing development delays.

Start with a useful outcome and the smallest observable acceptance case. Resolve
native uncertainty early using a representative caller and controlled experiment.
Retain target identity, legal execution, effect checks and cleanup; do not make
a general proof of the test setup a prerequisite for trying the operation.

The off-screen investigation demonstrated why: geometry admission prevented
several tests from attempting card input. A direct card16 selection with exact
preview/completion checks succeeded. Its conclusion applies to that controlled
allocated-holder setup; it does not certify all selectors or deck sizes.
[V10 evidence](docs/archive/phase-1/research/PHASE_1_GENERIC_EVENT_RELEASE_V10_ACCEPTANCE.md).

One owner carries a change through its requested feedback loop. Use focused
regressions during corrections, one independent semantic review for risky changes,
and one final relevant integration/release gate. Additional review or reruns need
a changed input, failure or distinct unresolved risk. Reuse trusted dependency
evidence with matching source/test/toolchain/settings identities. Documentation
changes need document checks, not gameplay certification.

The [working guide](AGENTS.md) and [live guide](docs/LIVE_DEVELOPMENT.md) replace
the procedural defaults of earlier packet plans. They preserve privacy,
authorization, artifact authenticity and honest evidence labels. Measure available
phase timings for substantial work rather than treating test counts as progress.

## D66. Preserve releases without freezing every development iteration

Accepted and implemented 2026-09-08 at the user's request. Shared bridge code now
lives in `components/`, initially with distinct compositions in `apps/` and one
maintained checker. The 32 successor source trees are removed from the working
tree. Git commit `4f0c9ed912b533da17e431bc2ff59a63b06b2aae` retains their exact
sources; original manifests/policies remain in
[release history](bridge/Sts2AgentBridge/releases/history/README.md).

Keep development editable across corrections. Validate current dependencies and
affected behavior, then bind a stable release to its source, toolchain, binary and
results. Live clients verify the selected release manifest before credential
access, without executing a predecessor checker. Historical evidence is never
silently repinned. Public interfaces change version when semantics change.

The four initial consolidated production builds reproduced their accepted DLLs
byte-for-byte. D67 replaces those deployment compositions; their exact records
remain in Git at `1d63e74`. Consolidation itself did not broaden live acceptance.

## D67. Ship one bridge with exclusive capability modules

Implemented 2026-09-08 at the user's request. Combat, rewards, map/rest, items,
shop/standard rooms, card selection and generic events share one production DLL,
loopback listener, owner-frame queue, configuration, client and package pipeline.
The separate feature mods and their operational/checker copies are retired.
Existing route versions describe their contracts; they do not require separate
runtime deployments.

Create native feature sessions lazily. Preserve parent-owned child routes, block
unrelated actions while a session owns the game, and hand off only after native
completion and successful disposal. An uncertain mutation or cleanup failure
stops the shared host. Core action reconciliation also fences feature entry.

Generalized transformation uses the successful direct native input mechanism for
all eligible allocated holders, preserving exact identity, preview, deferred
input and effect checks. No card16-only mask or viewport certificate remains.
Offline handoff and native-input fixtures do not establish a live full-run claim.

Develop through focused component checks. One final release binds the combined
binary and package; package identity is derived once and shared by installation,
cleanup and clients. New features extend modules, not release directories.

## D68. Implement game logic independently of its consumers

Requested and implemented 2026-09-13. `game/headless/` owns content definitions,
mutable instances, combat rules and persistent run state. It imports only its own
modules and the standard library. Game definitions drive execution directly;
adding a card does not require another projection or encoder registration.

The initially retained `CombatEnv` and reduced-backend compatibility layers were
subsequently retired by D69. New rules stay in the game package, independently of
consumer integration.

Content catalogs are immutable and explicit, identity/RNG belongs to each run,
and pending game state contains values instead of callback closures. Private
continuation remains distinct from public information and release evidence.
Future mechanics may extend state and lifecycle operations; unrelated consumers
must not constrain that work. The [engine guide](docs/HEADLESS_ENGINE.md) records
the reference-repository analysis, actual migration and remaining limits.

## D69. Retire the legacy simulator and research pipelines

Requested 2026-09-22, with no backward compatibility requirement. Keep the current
`game/headless` engine, direct gameplay CLI and production bridge. Remove old
simulation wrappers, reduced rules/contracts, policies, training, datasets,
benchmarks, search, configs and their commands/tests. The historical reward-gold
comparison tool is also retired because it executes the removed reduced rules;
bridge execution and the independent wire codec remain intact.

Preserve game-rule regressions through direct engine commands and JSON continuation.
Historical guides, evidence and original source identities remain archival;
do not repin their fingerprints. Full-game public observations and subsequent
policy/data consumers are new adapters over the engine (HF-44–47), without a
legacy checkpoint or fixture compatibility obligation.

## Core architecture

- **Game rules are independent of agent representations (D68–D69).** Preserve
  stable enemy slots, legal commands, explicit seeded RNG, serializable state and
  canonical subpackages. Future public adapters expose legal candidates while
  keeping private world/RNG state and hindsight outside policy inputs. Use the
  pinned game as the fidelity authority and complete-run victory as the objective.
- **Generic events follow shared interactions.** Reserve parent context before
  dispatch; obtain operation, counts, originals and tasks at owned native request
  and screen-creation boundaries. Event names identify ownership/tests, not a
  required new admission row for every standard event. Preserve original game
  execution; native asynchronous completion must be observed, not guessed.
- **Selection and completion are different.** Preserve exact original-card
  references, preview membership, deferred dispatch identity and selected-only
  effect reconciliation. Transformation journals account for partial removals,
  insertions and replacement substitutions. Item collection waits for the
  owned reward/parent tasks and verifies the relevant inventory transition.
- **Evidence stays attributable (D48, D53–D55).** Reduced headless progression
  is structural until named conformance cases establish fidelity. Public actor
  datasets separate held-out sources and privileged audit data; artifacts retain
  their accepted provenance. Tiny deterministic cloning results prove plumbing,
  not strategic quality or target-game parity.

Detailed native semantics are in the selected component contracts, reached through
[current status](docs/STATUS.md). The [target](docs/TARGET.md)
and [long-term architecture](docs/LONG_TERM_ARCHITECTURE_ROADMAP.md) retain the
full-game objective, information rules and eventual evaluation requirements.

## Historical training and analysis choices

The earlier algorithms, defaults and checkpoint formats belong to the retired
research pipelines. See the archived experiment guides for their original scope.
New full-game consumers follow HF-44–47 and have no legacy checkpoint requirement.

## D47. Separate Room Identity From Foreground And Completion Evidence

A room's continued existence does not make its controls foreground or actionable.
Revalidate before mutation and require the selected implementation's authoritative
completion witness. An inspection map cannot authorize actions behind it.
The original R0i event-completion limits remain properties of that artifact;
later accepted event successors have their own evidence.

## D49. Separate Reward Attempts, Receipt Acceptance And Reconciliation

An attempted exchange, an accepted bound receipt and an observed effect are
different facts. Preserve each count and cumulative completed-child evidence
through later parent actions or failures. Never invent success after a timeout
or retry an uncertain mutation merely to improve the report.

## D50. Centralize Bounded Host Transport Without Merging Phase Semantics

Reuse bounded credential/HTTP/parsing/cleanup machinery while keeping phase-specific
legality and reconciliation authoritative. Avoid copied implementations that
receive inconsistent fixes. New shared code must preserve uncertainty and resource
cleanup on failures.

## D52. Treat Elite As Host-Side Combat Without Expanding The Bridge

The host can route elites through the existing encounter-generic combat seam.
Implementation/fixture acceptance does not establish elite live coverage. Keep
explicit phase entry and existing run-budget accounting; do not infer permission
to resume a spent or uncertain action.

## D56. Keep Room-Stage Diagnostics Separate From Run Acceptance

Bounded host-stage diagnostics identify where an attempt stopped without retaining
raw responses, identifiers or secrets. They do not convert an accepted receipt,
partial progress or an unknown native cause into completed-run evidence. Preserve
the selected controller's validation, mutation budget and exceptional-exit cleanup.

## Maintaining this record

Add a short decision when architecture, training defaults or workflow materially
change. Keep operational progress and per-test history out of this file. Search
the historical log for earlier decision IDs instead of adding its chronology back.
