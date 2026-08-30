# Phase 1 Restricted Live Bridge Design

- **Status:** `R0a` repository implementation and install-free package gates
  passed; no live overlay, operator configuration, game load, or probe campaign
  has been executed
- **Initial capability:** `live_probe_v0`, authenticated and read-only
- **Target build:** Steam default/main build `23811903`, depot `2868842`,
  packaged release `v0.107.1`
- **Build identity:**
  [`sts2-steam-main-build-23811903-macos-universal.json`](../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)
- **Parent evidence plan:**
  [`PHASE_1_INTEGRATION_SPIKE.md`](PHASE_1_INTEGRATION_SPIKE.md)

## 1. Decision

Build the first live path as a lean, project-owned bridge. Do not install or
load the unchanged STS2MCP binary, and do not make a narrowed STS2MCP fork the
runtime foundation.

The exact pinned STS2MCP source remains useful as:

- target-build type/member compatibility evidence;
- a catalog of decision phases and engine integration points to audit;
- an MIT-licensed source of individually reviewed adapter snippets when reuse
  is genuinely smaller and clearer than a project-owned implementation.

Any reused source must retain required attribution and pass the same boundary
review as new code. The project must not inherit the upstream REST/MCP API,
bootstrap, state dictionary, transport, settings patch, action dispatcher, or
profile surface.

Here, “project-owned” means that this repository owns and maintains the bridge
boundary and release decision. It is not a claim of exclusive authorship if an
audited MIT snippet is reused. Every reused file/snippet receives file-level
provenance, license notice, and a recorded source revision.

### Why a fork is not the smaller design

The unsafe coupling is concentrated in the candidate's central seams:

- initialization writes configuration, patches settings, and starts a broad
  unauthenticated server;
- observation, UI manipulation, actions, profiles, history, wiki, multiplayer,
  and deletion share one router and trust boundary;
- nominal reads can open merchant or treasure UI;
- state is built as a mutable, screen-shaped dictionary without an enforceable
  actor-public projection boundary;
- actions rediscover mutable lists by position and report queueing rather than a
  committed transition;
- there is no decision identity, idempotency contract, controller lease,
  reconciliation journal, or reliable teardown boundary.

Replacing those parts would replace most of the value of a fork. A small
project-owned bridge produces a narrower binary, clearer provenance, and a
contract shaped around this agent rather than an inherited debugging API.

## 2. Capability stages

The bridge grows by replacing a reviewed artifact with a newly reviewed
artifact. A remote request can never upgrade its capabilities.

| Stage | Purpose | Compiled surface | Required prior gate |
| --- | --- | --- | --- |
| `R0a` | First load/passivity probe | Health, manifest, visible screen classification | Compile/package gate plus recoverable dedicated fixture |
| `R0b` | Read-only decision capture | Public decision envelope, events, and authoritative legal candidates | `R0a` load, security, teardown, and passive-read acceptance |
| `R1` | Controlled exploratory action | One leased typed candidate-transaction surface and reconciliation | `R0b` phase/public-boundary acceptance plus separately approved writes/ledger |
| `R2` | Ground-truth corpus runs | Accepted observation/control phase adapters | Full fault, recovery, coverage, and fixture gates |

`R0a` is deliberately smaller than a useful gameplay API. Its purpose is to
prove mod loading, build guarding, local transport, authentication, game-thread
read dispatch, a minimal public projection, and process-exit cleanup without
exposing actions or profile data.

No stage here is the final Phase 2 canonical protocol. The initial wire
namespace is intentionally disposable.

## 3. Trust and information boundaries

### 3.1 Actor-public

Only information allowed by the target charter may reach a policy, value model,
or planner:

- state visible to a player at the current decision;
- visibly legal choices;
- static rules allowed by the benchmark;
- history legitimately observed through prior public decisions and events.

Public projection is a field-by-field allowlist. It is never a redaction pass
over a broad engine/debug snapshot. Two situations with identical public
semantics but different hidden seed, pile order, RNG, future layout, or internal
object identity must yield identical public payloads and hashes.

### 3.2 Operational

The controller runtime and evidence recorder, but not `DecisionStrategy`, may
use:

- build, bridge, protocol, configuration, and process identities;
- authentication, lease, request, retry, timeout, and correlation data;
- monotonic run-incarnation, decision, event, and commit sequences;
- public-state and candidate-set hashes;
- latency, health, capability, and recovery state.

The physical profile slot, account namespace, local path, and protected fixture
mapping are operational/private. They never appear in the public decision
schema, policy features, search input, or repository-safe trajectory.

### 3.3 Privileged

Privileged data includes raw seed/RNG state, hidden pile order, unrevealed
offers or map cells, future outcomes, private enemy state, raw saves, profile
history, platform identity, internal object addresses, and debug-only snapshots.

A later conformance collector must be a separate package identity such as
`Sts2AgentBridge.PrivilegedCapture`. It is not a flag or route in the public
bridge, is never co-loaded with the deployed actor, and exposes no actor-facing
service.

### 3.4 Unknown

An unclassified engine field, phase, overlay, or side effect is unavailable.
Unknown does not mean public. Unknown screens return a typed `unsupported`
status with no plausible fallback candidates.

## 4. Planned component boundary

The initial project shape is conceptual until implementation is separately
started:

```text
bridge/Sts2AgentBridge/
├── Bootstrap/
│   ├── ModEntry
│   └── BridgeHost
├── Configuration/
│   └── StrictConfigLoader
├── Identity/
│   ├── BuildGuard
│   └── RuntimeManifest
├── Transport/
│   ├── LoopbackServer
│   ├── ProbeRouter
│   ├── Authentication
│   └── RequestLimits
├── Threading/
│   └── GameThreadDispatcher
├── Protocol/
│   ├── ProbeV0Dtos
│   ├── CanonicalJson
│   └── ErrorCodes
├── Public/
│   └── PublicScreenProbe
└── Diagnostics/
    └── SafeLogger
```

Later read-only decision work may add:

```text
Public/
├── PassiveEngineReader
├── PublicObservationProjector
├── DecisionBoundaryTracker
└── CandidateRegistry
```

The `R0a` binary must contain no compiled `Control/` implementation. Later
control work is isolated behind:

```text
Control/
├── LeaseManager
├── TransactionCoordinator
├── OperationJournal
├── CommitObserver
├── Reconciler
└── Adapters/
```

Whether `R1` ships these as a replacement package or a separately composed
assembly remains an implementation review decision. The invariant is that the
read-only artifact contains no dormant mutation surface.

## 5. Internal data flow

Transport is an adapter around typed domain records, not the domain model.

```text
game thread
    │
    ▼
PassiveEngineReader
    │ raw capture (internal only)
    ▼
PublicProjector ──► DecisionBoundaryTracker ──► CandidateRegistry
    │                         │                         │
    └──────────── typed immutable DecisionEnvelope ────┘
                              │
                              ▼
                    local transport adapter
                              │
                              ▼
                      LiveGameBackend
                              │ normalized GameBackend contract
                              ▼
                         AgentRuntime
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
         heuristic       policy-only       planner/search
```

Search, model inference, prompt/LLM logic, Markdown formatting, simulator
branching, and training do not run inside the C# bridge. HTTP routes and status
codes do not leak into the typed decision model.

## 6. `live_probe_v0` wire surface

The first binary exposes exactly three authenticated read-only routes:

| Route | Purpose |
| --- | --- |
| `GET /probe/v0/health` | Listener/host lifecycle state and sanitized correlation identifier only |
| `GET /probe/v0/manifest` | Operational build, protocol, mode, and negative capability identity |
| `GET /probe/v0/public/screen` | Minimal classification of the currently visible screen |

Compatible-build mode exposes all three routes. Incompatible-build locked mode
exposes only authenticated health and manifest; the public screen route is
absent.

There are no `POST`, `PUT`, `PATCH`, `DELETE`, or `OPTIONS` routes. There is no
generic RPC, reflection, file, console, profile, history, wiki, compendium,
multiplayer, debug, or action route.

The screen response is limited to the equivalent of:

```text
schema_version
status: ready | waiting | unsupported
screen_kind: main_menu | settings | unknown
actionable: false
candidates: []
```

It does not expose profile name/slot, account identity, save path, seed,
unlocks, run history, scene/type names, or internal object identifiers. It does
not open, dismiss, select, focus, hover, or otherwise alter UI.

The manifest advertises absences explicitly:

```text
observe_public_screen = true
observe_decision = false
apply = false
profile_access = false
privileged_state = false
snapshot_restore = false
bridge_filesystem_writes = false
host_logging = sanitized_existing_sink
harmony_patches = false
outbound_network = false
hot_unload = false
```

## 7. Local security contract

`R0a` uses a minimal local attack surface:

- bind only the literal IPv4 loopback address `127.0.0.1` on one predeclared
  fixed port;
- fail closed on a port collision; never bind a wildcard or choose another
  port automatically;
- require a precreated high-entropy bearer credential on all three routes;
- never create, repair, print, return, or persist an additional credential
  copy;
- omit CORS headers and reject requests carrying a browser `Origin` header;
- enforce a strict route/method allowlist and reject request bodies;
- enforce hard header, response, concurrency, queue, and timeout limits;
- return stable bounded errors without exception text, stack traces, paths,
  reflection names, credentials, or raw payloads;
- make no outbound connections and start no child process;
- own no write-capable profile, save, or arbitrary-filesystem dependency.

`SafeLogger` emits bounded sanitized messages only through the game's existing
host logging facility; the bridge owns no log file or file sink. Base-game log
writes are measured against the base control and are not misreported as
bridge-owned save/profile access.

Authentication protects access; loopback binding is not treated as
authentication. The configuration is precreated outside profile/Cloud storage,
strictly parsed with unknown fields rejected, and fingerprinted in the protected
run manifest. Missing, malformed, or unprotected configuration leaves the
bridge disabled with no listener.

## 8. Build guard and compatibility behavior

An external preflight verifies the complete recorded base-install projection.
The bridge independently verifies the pinned game assembly identity before any
engine read is registered.

With valid configuration but an incompatible game build, startup takes a
separate locked branch: it skips game-thread callback and public-reader
registration, then may start only authenticated health/manifest diagnostic
routes. The public screen route is absent. Any other uncertain identity fails
closed.

The build manifest is operational evidence, not actor input. A successful
compile or assembly-hash match does not establish runtime behavior, public
semantics, or passivity.

## 9. Lifecycle and teardown

The host uses an idempotent lifecycle:

```text
created -> starting -> running -> stopping -> stopped
                    \-> faulted
```

Compatible-build startup order:

1. Strictly load and validate the precreated configuration.
2. Verify build identity without reading profile state.
3. Register one stored game-thread callback.
4. Start the bounded loopback listener.
5. Publish a sanitized runtime manifest.

The incompatible-build branch performs configuration and identity checks,
skips step 3 entirely, and starts only the locked diagnostic listener described
above.

If a step fails, already-created resources are unwound in reverse order.

Shutdown order:

1. Stop accepting requests.
2. Cancel and fail queued work.
3. Disconnect the exact stored game callback.
4. Close the listener and release its port.
5. Join the server worker within a fixed bound.
6. Clear credential material and enter `stopped` or a recorded fault state.

The host's explicit stop/unwind behavior is exercised with component tests.
The initial live package claims process-exit cleanup only; after a process has
exited, a live test cannot separately prove that an in-process callback was
disconnected. It instead proves normal process exit, port release, and a clean
base-control restart. The design does not claim hot unload until the loader
provides and testing proves a reliable unload boundary.

## 10. Read-only decision contract after `R0a`

`R0b` introduces an immutable typed decision envelope only after the minimal
probe passes. The envelope separates its policy payload from its operational
wrapper and contains:

- schema and public-semantics versions;
- status: `actionable`, `waiting`, `terminal`, `unsupported`, or
  `desynchronized`;
- phase and typed decision kind;
- normalized actor-public observation;
- ordered public events since the prior boundary;
- all and only currently legal typed candidates;
- public-state, candidate-set, and canonical-decision hashes;
- operational run-incarnation, decision, and public-event sequences.

Waiting polls do not create new decisions. An overlay or automatic transition
does not inherit candidates from the last actionable state.

The client supplies `after_cursor` and may supply a previously returned
`through_cursor`. When `through_cursor` is omitted, the bridge snapshots the
current latest cursor as the response's upper watermark. The response declares
the earliest/latest retained cursors, selected upper watermark, ordered events,
and any pagination cursor. Retrying or continuing with the same
`through_cursor` returns the same immutable records/order through that watermark
even if newer events have arrived; newer events are excluded until a later
snapshot request. A read never advances server-side consumer state. The client
advances only by supplying a later `after_cursor` after receipt. A cursor before
the retained range, beyond the selected watermark, from another
run/incarnation, or otherwise unreconstructible returns
`history_gap`/`desynchronized` with no candidates and no silent continuation.
Restart/resume reconstruction is capability-declared per bridge version; until
it is proven, a process restart starts a new incarnation and requires explicit
runtime reconciliation.

Candidates are semantic operations, for example:

```text
play_card(card_instance_id, target_entity_id)
end_turn()
choose_map_node(map_node_id)
select_modal_item(item_id)
confirm_selection()
```

The client never submits a hand/shop/list index, arbitrary action string,
free-form target, profile number, or seed. Candidate creation and later
execution share one decision-local resolver table.

That table is cleared at every decision transition, terminal state,
desynchronization, and shutdown. It uses non-owning engine references or
re-resolving semantic keys with explicit validity checks; cached candidates may
not extend a Godot/game object's lifetime.

## 11. Identity and canonicalization rules

| Identity | Declared lifetime |
| --- | --- |
| `bridge_instance_id` | One game process/mod load |
| `attempt_id` | One evidence or scored attempt; assigned outside the actor |
| `run_id` | One logical run through terminal, including supported resume |
| `run_incarnation_id` | One process/resume incarnation of a run |
| `decision_id` / `decision_seq` | One public actionable boundary; operational guard identity/sequence |
| `candidate_id` | Exactly one decision; deterministic from canonical public decision and candidate semantics |
| `public_event_seq` | Monotonic over public events in one run |
| `commit_seq` | Monotonic over mutation attempts when control exists |
| `entity_instance_id` | Explicitly declared per entity kind/lifetime and allocated from public reveal history |
| `lease_id` | One controller lease |
| `idempotency_key` | One logical mutation across transport retries |
| `request_id` | One transport attempt |

Dead enemies keep their encounter identity. A card instance keeps its public
identity only across transitions that public history can uniquely track. When a
card enters a hidden/unordered zone, is shuffled, or becomes publicly
indistinguishable from duplicate copies, the public linkage ends; a later reveal
receives a newly bound public identity unless public evidence uniquely proves
continuity. Internal engine identity never repairs that public ambiguity.
Generated cards and summons receive new identities. Candidate IDs never outlive
their decision.

Canonical public hashes and operational identities are separate:

- `public_state_hash` hashes only the public-semantics version plus the
  canonical actor-public phase/kind, normalized observation, and declared
  observable-history fields;
- `candidate_semantics_hash` hashes the canonical semantic candidates sorted by
  their public semantic key, excluding candidate handles;
- `canonical_decision_hash` hashes the schema/public-semantics version,
  actionable status, phase/kind, `public_state_hash`, and
  `candidate_semantics_hash`;
- randomly allocated/cached bridge, run-incarnation, decision, request, lease,
  and guard identities are operational and excluded from all three canonical
  hashes;
- public entity IDs are allocated deterministically from public reveal
  event/order under the schema, and `candidate_id` is derived from the canonical
  public decision plus the candidate's semantic key; neither uses an engine
  address or hidden ordering.

The policy receives public entity semantics/identities and deterministic
candidate IDs only as defined by the public schema; random transaction handles
remain in the operational wrapper.
No ID, ordering key, or hash encodes seed, hidden order, RNG state, internal
addresses, hidden event counts, platform/profile identifiers, or localized
presentation text. Public-equivalence tests compare canonical actor payloads,
candidate semantics, and hashes after excluding the operational wrapper.

## 12. Future transaction and recovery contract

No transaction code or route exists in `R0a` or `R0b`. Before `R1`, the design
must support one exclusive controller and one typed candidate-application path,
not one endpoint per game action.

`R1` boots and restarts **disarmed**. Observer and controller credentials have
distinct scopes. A controller credential or lease can never arm writes. Arming
is an explicit local, out-of-band operator action bound to one approved fixture,
bridge/configuration identity, capability mode, and attempt; no network route
can perform or broaden it. Lease acquisition and renewal require an already
armed attempt.

The bridge automatically disarms on process restart, explicit revocation,
lease expiry, `timeout_unknown`, desynchronization, unresolved journal intent,
or bridge/backend fault. If later evidence supports a different in-flight
lease-expiry rule, that rule must be frozen before `R1`; expiry always rejects
new dispatch and never guesses the outcome of an operation already in flight.
Rearming after any automatic disarm is another explicit local operator action,
not an API retry.

Every apply request must carry:

- authenticated controller lease;
- client-generated idempotency key and transport request ID;
- expected bridge and run-incarnation identities;
- expected decision ID/sequence/hash and candidate-set hash;
- last observed public-event and commit sequences;
- exactly one advertised candidate ID.

On the game thread, the transaction coordinator must:

1. verify authentication, armed mode, lease, request identity, and the complete
   expected decision;
2. reserve the idempotency key and request digest before possible mutation;
3. resolve the candidate from the current immutable registry;
4. revalidate referenced objects and legality immediately before dispatch;
5. allow only one mutation in flight;
6. record an intent in the separately approved operation journal;
7. dispatch at most once;
8. observe an actual commit, rejection, or coherent postcondition rather than
   treating queue admission as success;
9. record and cache the typed result;
10. return that result for an identical retry and reject same-key/different-
    payload reuse.

The honest guarantee is at-most-once dispatch plus fail-closed reconciliation,
not unconditional exactly-once behavior across arbitrary process crashes.

Typed outcomes include:

```text
accepted
already_applied
rejected
stale
unsupported
timeout_unknown
reconciliation_required
```

Each states `mutation_state = none | not_committed | committed | unknown`.
After `timeout_unknown`, further writes are disarmed until read-only
reconciliation succeeds or the attempt is invalidated. A potentially committed
mutation is never retried automatically.

A bridge restart changes `bridge_instance_id`, invalidates leases, and remains
disarmed. Manual UI input is an external transition, not something an API lease
can prevent; it stales the decision and invalidates autonomous evidence.

Any operation journal introduces a bridge-owned write and therefore requires a
separate exact path, retention, recovery, and approval design outside profile
and Cloud storage.

## 13. Error model

Errors are typed and stable:

```text
invalid_request       unauthenticated       forbidden
read_only             unsupported_build     unsupported_phase
unsupported_content   not_actionable        stale_decision
candidate_expired     invalid_candidate     action_rejected
lease_required        lease_expired         lease_conflict
idempotency_conflict  timeout_unknown       desynchronized
history_gap           payload_too_large     rate_limited
backend_fault
```

An error includes retryability, mutation state, and a sanitized correlation ID.
It may include the current public decision reference when safe. It never
includes a stack trace, raw exception, engine type name, absolute path,
credential, profile/account identity, seed, or raw request payload.

## 14. Search neutrality and backend integration

The bridge does not know whether search is enabled.

```text
C# public bridge
    -> versioned wire decision
Python LiveGameBackend
    -> normalized GameBackend decision
AgentRuntime
    -> InformationState + candidates + budget
DecisionStrategy
    ├── HeuristicStrategy
    ├── PolicyOnlyStrategy -> PolicyProvider
    └── PlannerStrategy -> Planner + PolicyProvider + ValueProvider
```

Policy-only and planner-enhanced runs use the same bridge binary,
configuration, recorded public envelope, candidate set, and submission/recovery
path. They differ only in declared strategy/provider/budget and their selected
candidate/latency. Search branches through a simulator capability; it never
requests a privileged live snapshot. If live state advances while search runs,
ordinary expected-state validation returns `stale`.

`LiveGameBackend`/`AgentRuntime` orchestrate credential use, lease
acquisition/renewal, expected-state submission, retry decisions, and recovery
workflows. The bridge authoritatively enforces authentication scope, armed
state, lease ownership, idempotency reservations, dispatch serialization,
commit state, and disarming. None of those operational values are learned
features.

## 15. Compile-only gate for the project-owned probe

Before installation is proposed, `R0a` must satisfy all of these:

1. Compile unchanged project-owned source with .NET SDK `9.0.303`, matching the
   target's .NET `9.0.7` runtime, against the recorded arm64 game assemblies.
2. Treat warnings as errors and produce zero compiler/MSBuild warnings or
   errors.
3. Repeat with the current .NET 9 servicing SDK as a secondary smoke test.
4. Reference only the required `sts2` and `GodotSharp` assemblies directly; no
   Harmony dependency.
5. Prove the package contains only the three `GET` routes and no action,
   profile, privileged, Harmony, or write-capable module.
6. Run forbidden-symbol checks for profile/save APIs, `DebugOnlyGetState`, UI
   clicks/queues, generic client-supplied paths or enumeration, all writes,
   wildcard/CORS transport, and outbound networking. Filesystem reads are an
   exact path-contained allowlist limited to the predeclared configuration,
   credential source, and build-identity inputs.
7. Unit/contract-test strict configuration, authentication, Origin/method/body
   rejection, bounds, build mismatch, canonical serialization, and safe errors
   outside the game where possible.
8. Align manifest, assembly, file, and informational versions.
9. Build twice with deterministic/path-mapped settings; require identical
   packages or document and eliminate the non-semantic difference.
10. Record source tree, SDK/runtime, reference assembly, configuration template,
    output, and package hashes.
11. Verify no game assembly is copied into the package and the recorded
    `429`-file base-game projection remains unchanged.
12. Complete an independent source and package review.

A compile pass is compatibility evidence only. It cannot authorize installation
or imply load/passivity success.

## 16. First isolated load gate

The full `R0a` isolated load/acceptance gate needs a new, separately reviewable
approval after all prerequisites pass:

- the dedicated profile boundary and recoverable baseline are verified;
- Steam Cloud behavior has a safe test/rollback procedure;
- the game is closed and the exact base projection passes;
- the unique overlay, manifest, precreated configuration, token source, and
  removal procedure are hashed and shown;
- the user approves the exact install, launch, close, and removal scope.

One narrower preliminary menu smoke may run before the recoverable baseline and
Cloud rollback prerequisites only as a separately approved, explicit risk
exception. That request must:

- state that it cannot complete full `R0a`, `L-BOOT`, or `L-PASSIVE`;
- keep the already selected dedicated profile at visible main menu and Settings
  only, with no profile-screen visit, profile switch, run start, or run resume;
- prohibit direct profile/save/Cloud content access or comparison by campaign
  helpers, bridge code, and the operator while acknowledging that Steam and the
  game can perform opaque ordinary I/O and synchronization during approved
  launches and exits;
- obtain the user's explicit acceptance that any such unobserved effect is
  potentially mutating and unrecoverable without the deferred baseline;
- recheck user-visible Cloud `Up to Date`/idle between launches and stop on an
  uncertain or changed state; and
- bind one exact artifact, safe file manager, verifiers, client, process/port
  checks, time bounds, quarantine state machine, and normal-exit-only removal.

This exception exists only to establish whether the exact bridge can load and
return the two visible classifications. It does not weaken the prerequisites
for a later full passivity/acceptance campaign.

The bounded probe then:

1. records a no-mod base-control launch/close first;
2. adds only the non-colliding `R0a` overlay;
3. launches to the dedicated profile's main menu without starting/resuming a
   run;
4. verifies game-visible loaded-mod identity and authenticated bridge identity;
5. tests exact loopback binding, authentication, wrong-method, Origin, body,
   bounds, and port-collision behavior;
6. repeatedly reads health, manifest, and visible screen while verifying no UI
   or allowed fixture metadata changes;
7. closes normally and proves process exit and port release; callback
   stop/unwind remains a component-test claim;
8. removes or disables the declared overlay by the approved reversible method;
9. proves a clean base-control restart;
10. compares only the separately authorized dedicated-profile metadata.

This tests loading and the minimal boundary. It does not establish gameplay
coverage, full passivity, action correctness, save/resume, simulator fidelity,
or candidate ranking.

## 17. Acceptance matrix

| ID | Required result |
| --- | --- |
| `C-BUILD` | Exact pinned build and parity SDK compile with recorded provenance and zero warnings/errors |
| `C-SURFACE` | `R0a` binary/package contains no mutation, profile, privileged, Harmony, or undeclared route surface |
| `C-REPRO` | Two clean canonical packages are identical |
| `L-BUILD` | Exact build enables the probe; incompatible build remains locked and performs no engine read |
| `L-BOOT` | Configuration remains byte-identical; relative to base control there is no bridge-initiated profile/save API or filesystem access, undeclared write, child process, or outbound connection; declared host-log delta is sanitized |
| `L-NET` | Only the declared loopback listener exists; authentication, Origin, bounds, methods, and collision tests pass |
| `L-SCREEN` | Repeated screen reads match visible UI and perform no UI action |
| `L-ERROR` | Malformed, oversized, and unsupported requests are bounded, sanitized, and nonmutating |
| `L-STOP` | Component tests prove explicit stop and reverse startup-failure unwind, including callback/listener cleanup |
| `L-TEARDOWN` | Live normal process exit releases the port and a clean base-control restart succeeds; no stronger hot-unload claim is made |
| `L-PASSIVE` | Paired base/probe traces show zero unexplained semantic, save-metadata, UI, or RNG-observable divergence within the tested scope |
| `D-PUBLIC` | After excluding the operational wrapper, equal public histories serialize identical actor payloads, entity/candidate semantics and ordering, status/errors, response shape/size, and canonical hashes despite hidden-state differences; response timing is unavailable to the actor and tested for hidden-dependent leakage |
| `D-STATUS` | Actionable, waiting, terminal, unsupported, overlay, and desynchronized states are distinct |
| `D-ID` | Entity/decision/candidate identities remain stable for their declared public lifetime and card linkage is dropped/rebound across hidden or indistinguishable zones |
| `D-LEGAL` | Candidates equal independently audited visible legal choices |
| `D-GAP` | The same `after_cursor`/`through_cursor` window idempotently replays immutable ordered events without server-side advancement; retention/pagination watermarks are explicit; missing/restarted history returns `history_gap`/desynchronized and cannot silently continue |
| `D-UNSUPPORTED` | Unknown phase/content/overlay fails closed with no inherited or plausible fallback candidates |
| `A-ARM` | Boot/restart is disarmed; network/lease operations cannot arm; local attempt-bound arming and every automatic-disarm trigger pass |
| `A-LEASE` | At most one valid controller reaches dispatch |
| `A-LEASE-LIFE` | Renewal, expiry, revocation, and expiry during an in-flight operation follow the frozen rule without a second dispatch |
| `A-STALE` | Old or changed decisions reject before mutation |
| `A-DUP` | Concurrent duplicate/lost-response retry produces one dispatch and the cached result |
| `A-KEY` | Reusing one idempotency key with a different payload rejects before mutation |
| `A-ATOMIC` | Invalid target, cost, or candidate produces no partial payment or side effect |
| `A-TIMEOUT` | Unknown commit disarms writes and reconciles read-only or invalidates the attempt |
| `A-EXTERNAL` | Manual/automatic transitions cannot apply an action to the wrong decision |
| `A-RESTART` | Client, bridge, and game-process restart cases invalidate/reconstruct identities, leases, journal, and result cache without duplicate action |
| `A-ERROR` | Every R1 rejection/fault is typed, sanitized, bounded, and reports honest mutation state |
| `N-STRATEGY` | Policy and planner use byte-identical public decision/candidate evidence and the same bridge artifact |

Only the `C-*` and `L-*` rows relevant to `R0a` are executable in the first
milestone. Later rows are requirements, not claims of current support.

## 18. Parallel implementation packages

One integration owner must first complete the design-only `BR0-PREFLIGHT`
freeze. It resolves every “Before `R0a` implementation” item in Section 20 and
freezes DTO vectors, numeric limits, exact read paths, static accessors, package
shape, forbidden-surface policy, and acceptance commands. It creates no mod
source or package.

Only after `BR0-PREFLIGHT` is accepted and implementation is explicitly started
may the bounded implementation packages fan out in parallel behind those frozen
interfaces:

| Package | Exclusive ownership | Output |
| --- | --- | --- |
| `BR0-PREFLIGHT` | One integration/design owner | Frozen implementation input package and review hash; blocks every row below |
| `BR0-CONTRACT` | Probe DTOs, canonicalization, errors, configuration schema | Pure library plus contract vectors |
| `BR0-HOST` | Bootstrap, build guard, lifecycle, game-thread dispatcher | Host library with fake-engine seams |
| `BR0-TRANSPORT` | Loopback listener, router, authentication, request bounds | Transport adapter tested against frozen DTOs |
| `BR0-PUBLIC` | Allowlisted visible-screen classifier only | Pure projector plus fixtures; no transport/profile/action references |
| `BR0-PACKAGE` | Build files, versioning, deterministic packaging, hash manifest | Install-free package candidate |
| `BR0-REVIEW` | Forbidden-surface, threat-model, provenance, and package audit | Independent gate report |

All seven packages are now implemented and reviewed for the repository/build
boundary. Exact artifacts, gate results, discarded-candidate history, and
residuals are recorded in
[`research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md`](research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md).
This closes the compile/package prerequisites only; the `L-*` live rows remain
open until a separately approved operational campaign runs.

One integration owner combines reviewed outputs. No agent edits the same file
without an explicit handoff. Contract vectors, forbidden-symbol policy, and
package acceptance tests are frozen before parallel implementation begins.
Every design, source, and package review records the exact artifact SHA-256;
substantive edits invalidate the earlier sign-off and require focused recheck.

`R0b`, `R1`, simulator, model, and search work are separate packages. They do
not expand `R0a` to keep workers busy.

## 19. Current boundary and non-goals

- no live bridge installation, operator-configuration write, or game launch has
  occurred yet;
- no upstream bridge binary load;
- no profile/save read, copy, switch, deletion, or mutation;
- no game launch or run start;
- no action route, gameplay mutation, controller lease, or journal;
- no full observation, legal-candidate enumeration, or phase coverage claim;
- no Harmony patch or UI/settings manipulation;
- no privileged/debug endpoint in the public package;
- no simulator, search, policy, model, trainer, or MCP/LLM facade in the mod;
- no multiplayer;
- no claim that `/probe/v0` is the final canonical API;
- no production, strong-play, or near-optimality claim.

## 20. Resolved and remaining decisions

The former pre-implementation decisions for DTO bytes, numeric limits,
protected configuration paths, visible-screen accessors, package shape, and
external verifiers were resolved by
[`PHASE_1_BR0_PREFLIGHT.md`](PHASE_1_BR0_PREFLIGHT.md) and exercised by the
implementation evidence above. They are no longer open design choices for
`R0a`.

Before either a preliminary smoke or a full `R0a` live campaign, the exact
artifact-bound overlay, operator-configuration, launch, probe, teardown, and
rollback scope still needs explicit approval. A preliminary smoke establishes
only the point observations it actually exercises. Full `R0a`, profile/save
passivity, and Cloud rollback remain separate evidence gates.

Before `R1`:

- freeze the Phase 2 candidate/decision semantics required for the covered
  phases;
- decide control-package composition and the exact protected journal path;
- define commit evidence per action family and restart reconciliation;
- approve all write, retention, and reset behavior;
- pass the public/privileged differential suite.

These are explicit gates, not invitations to inherit an upstream default.
