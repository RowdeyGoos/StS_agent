# Phase 1 Integration and Fast-Backend Evidence Plan

- **Status:** active; the project-owned bridge is implemented through `R0i` and
  has passed bounded live observation/control smokes, while representative
  phase coverage, corpus work, reliability evidence, and the fast-backend
  decision remain open
- **Full Phase 1 campaign ID:** `TBD`
- **Target-charter ID/hash:** `TBD`
- **Preregistration freeze commit/time:** `TBD`
- **Decision owners/reviewers:** `TBD`

This document operationalizes Phase 1 of the
[`LONG_TERM_ARCHITECTURE_ROADMAP.md`](LONG_TERM_ARCHITECTURE_ROADMAP.md).
It is an evidence plan, not an implementation design. Its purpose is to decide,
with reproducible observations, which live-game bridge should establish semantic
ground truth and whether the fast backend should be Python, engine-hosted, or a
hybrid.

The living implementation and evidence disposition is maintained in
[`PHASE_1_CURRENT_STATUS.md`](PHASE_1_CURRENT_STATUS.md). Point-in-time status
statements in preserved freezes and campaign requests remain historical.

The first live-path engineering direction is fixed: a lean project-owned bridge
entered the gates before any third-party runtime and is now the selected live
path. Its staged boundary is defined in
[`PHASE_1_RESTRICTED_BRIDGE_DESIGN.md`](PHASE_1_RESTRICTED_BRIDGE_DESIGN.md).
The resulting artifact satisfies the repository compile, contract,
reproducibility, package, and forbidden-surface gates initially recorded in
[`research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md`](research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md).
Bounded live campaigns have since established loader viability, authenticated
public observation, snapshot-bound control, complete combat, reward handling,
map selection, and one composed floor transition. They have not established
full gameplay passivity, representative phase coverage, general transaction
recovery, complete-run control, or sustained reliability. The evidence plan
below remains open for those broader claims and for the fast-backend decision.

Phase 1 consumes the target charter produced by Phase 0 of the long-term
roadmap. The charter's exact build, branch, character, Ascension, unlock state,
information boundary, allowed mods, platform, and compute rules are normative.
No result is comparable until the charter ID and hash above are filled in.

## 1. Outcomes

Phase 1 must answer two separate decisions:

1. **Live truth path:** adopt, fork, clean-room reimplement, or reject each
   candidate bridge; select one path for observation, safe control, trajectory
   capture, and actual-game evaluation.
2. **Fast-backend path:** expand the project-owned Python simulator, use a
   locally engine-hosted backend, or use both with explicit responsibilities.

The spike succeeds only if it produces auditable evidence for both decisions.
Successfully completing one showcase run is not sufficient.

### 1.1 Goals

- Capture an exact, reproducible target-build identity.
- Test revision-pinned prior art under one common protocol.
- Observe and safely control every required full-run decision family.
- Determine legal-action completeness, event ordering, identity stability,
  restart/resume behavior, throughput, and patch coupling.
- Test action idempotency, stale-state handling, recovery, local security, and
  controller exclusivity.
- Prove that policy-ready data contains only charter-allowed public information.
- Measure whether enabling the bridge changes gameplay, RNG-observable outcomes,
  rewards, unlocks, or save behavior.
- Produce a versioned live trajectory/conformance corpus.
- Record licensing, provenance, and redistribution constraints before reuse.
- Freeze quantitative exit gates before comparative trials begin.

### 1.2 Non-goals

- Implementing the canonical Phase 2 backend protocol.
- Expanding the current simulator's content catalog.
- Training or selecting an RL agent.
- Proving full simulator parity or near-optimal play.
- Shipping a bridge, patched game assembly, extracted content bundle, or model.
- Supporting co-op, arbitrary mods, daily/custom modes, or every platform.
- Treating upstream coverage, fidelity, or throughput claims as evidence.
- Using hidden game state to make deployed decisions.

## 2. Safety and evidence rules

- Use a dedicated test profile and recoverable copies of saves. Do not run
  destructive tests against a primary profile.
- Test only locally owned installations and local loopback services. This plan
  does not authorize probing third-party systems.
- Keep the unmodified/base-rules control installation and bridge-enabled test
  installation/configuration distinguishable and fully recorded.
- Never commit or redistribute game assemblies, patched binaries, extracted
  proprietary content, saves, credentials, or player identifiers.
- Retain raw payloads and privileged traces in access-separated storage. The
  policy-ready corpus is generated separately and cannot link them at runtime.
- A manual correction, console command, hidden-state read, save edit, or test
  harness intervention is recorded; it cannot be silently counted as an
  autonomous success.
- Unknown, unmeasured, and unsupported are distinct result states. None means
  pass.
- Every upstream candidate is identified by the inspected revision. If it must
  be patched, the exact patch and derived license obligations become part of the
  candidate identity.

Stop the affected work package immediately if a test risks save corruption,
binds a mutating interface beyond loopback, exposes secrets/privileged fields to
the policy client, or requires redistribution not yet approved.

## 3. Captured target build and remaining host prerequisites

After the user selected Steam's default branch, the following target build was
captured on the available host on 2026-08-29:

| Item | Captured observation |
| --- | --- |
| Host | macOS 26.5.2, arm64 |
| Game install | Slay the Spire 2 is installed |
| Steam branch metadata | `BetaKey = public`, Steam's default public channel |
| Steam build ID | `23811903` |
| Depot | `2868842`, manifest `8653035385353091849` |
| `release_info.json` | version/branch `v0.107.1`; commit `59260271`; date `2026-06-18T15:43:56-07:00`; `main_assembly_hash = -1718063421` |
| Bundle | Universal macOS arm64/x86-64; strict deep code-signature verification passed |
| Cryptographic capture | Individual semantic/runtime file hashes plus aggregate SHA-256 over 429 regular installation files |
| System .NET SDK | `dotnet` is not currently installed; the game bundles .NET 9.0.7, so this does not prevent the installed game from running |

The former `public-beta` mismatch is resolved. The authoritative sanitized
record is
[`sts2-steam-main-build-23811903-macos-universal.json`](../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
Its installation-tree hash is the clean base-install projection. A bridge
variant must hash its exact non-colliding overlay separately and reproduce that
base projection after excluding only the allowlisted overlay; the raw combined
tree is not expected to retain the clean hash. The manifest otherwise resolves
only the binary/build identity. The dedicated profile, unlocks, rule-affecting
settings, enabled-mod order, bridge, retention procedure, and candidate-campaign
freeze remain open.

## 4. Preregistration and exact build capture

### 4.1 Freeze before comparative execution

Before running candidate comparisons, fill and freeze:

- campaign and target-charter IDs/hashes;
- target main-branch display version, Steam build/depot manifest, game commit,
  executable/assembly/resource fingerprints, and capture time;
- target OS/architecture and whether portability is required or merely observed;
- character, Ascension, unlock/profile state, run modifiers, and seed policy;
- permitted public information, including seed visibility and observable history;
- allowed mod list: normally only the candidate observation/control bridge;
- scenario/run seed registry and which panel is exploratory versus held out;
- metric definitions, sample counts, thresholds, and tie-breaking rules in
  Section 14;
- candidate revisions and any locally applied patches;
- evidence-root path, retention/redaction policy, and reviewer sign-off.

Changes after the freeze create a new campaign ID. Failed exploratory work may
inform a new campaign but cannot silently change the active gates.

### 4.2 Build manifest procedure

This read-only binary/build identity capture completes one Phase 0 prerequisite.
It does not capture a profile and does not use a bridge to capture game state or
transitions. Comparative Phase 1 candidate campaigns begin only after the
remaining charter freeze. Static audits, compile-only compatibility probes,
reversible fixture discovery, and separately approved isolated read-only loads
may overlap as exploratory evidence. Bounded mutating probes additionally need
an accepted disposable golden fixture and the relevant safety gates, but may be
used to set thresholds; none of these exploratory tiers count as comparative or
certification evidence.

Capture a machine-readable build manifest containing:

1. Steam app ID, selected branch, build ID, every relevant depot manifest, and
   Steam app-manifest snapshot/hash.
2. `release_info.json` fields and file hash.
3. Cryptographic hashes, sizes, and relative paths for the main assembly,
   executable, mod loader, XML documentation, and other files later shown to
   affect semantics. Hashing occurs only after the target branch is selected.
4. Ordered enabled-mod list, mod IDs/versions, manifests, and binary hashes.
5. OS, architecture, game/runtime/Godot/.NET versions, locale, game settings,
   fast-mode/animation settings, and relevant environment configuration.
6. Dedicated profile/unlock-state fingerprint and recoverable-save-copy identity,
   without publishing personal data.
7. Capture timestamp, operator, clean/dirty evidence workspace state, and the
   tool/version used to produce the manifest.

Store only hashes and lawful project-authored metadata in the repository.
Whether and how an old build may be retained or reconstructed is a Phase 1 legal
and operations question, not an assumption.

## 5. Candidate register

The initial candidates come from the roadmap's revision-pinned prior-art matrix,
inspected on 2026-08-27. Upstream movement does not change these identities.
The completed static evidence and the resulting execution shortlist are tracked
in [`PHASE_1_STATIC_AUDIT_SYNTHESIS.md`](PHASE_1_STATIC_AUDIT_SYNTHESIS.md), with
detailed revision-pinned dossiers under [`docs/research/`](research/). The exact
STS2MCP source has also passed the
[`compile-only gate`](research/PHASE_1_STS2MCP_COMPILE_PROBE.md) against the
pinned arm64 assemblies. Static eligibility and compile compatibility do not
satisfy any live or behavioral knockout gate below.

The first profile-filesystem proposal is separately frozen in
[`PHASE_0_PROFILE_METADATA_DISCOVERY_REQUEST.md`](PHASE_0_PROFILE_METADATA_DISCOVERY_REQUEST.md).
It was approved and its shallow local-boundary probe passed with disclosed
execution caveats; see the
[`sanitized result`](research/PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md).
The separately approved
[`PF-D1B-BACKUP-SIDECARS-V1`](PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_REQUEST.md)
probe then established that the current shallow projection matches the fixed
core/backup-sidecar allowlist; see its
[`sanitized result`](research/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md).
It cannot prove filesystem-object continuity from D1, content equality,
recoverability, or Cloud behavior, and it authorizes no later content/copy step.
D1C was reviewed, deliberately unselected/skipped, and never executed; its
fail-closed profile-root/empty-history predicate is incorporated into the
exact frozen
[`PF-HASH-BASELINE-V1`](PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md) request. Its
first approved invocation
[stopped before target-content access](research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md)
because of a runner component-binding defect and supplies no fingerprint
evidence. A corrected invocation requires fresh approval. The request
authorizes neither copying nor parsing, Cloud, restore, launch, or bridge work.

| ID | Candidate/revision | Candidate role | Initial reuse status |
| --- | --- | --- | --- |
| `LIVE-PROJECT` | Project-owned `live_probe_v0` | First restricted read-only live path | Source/package and independent repository gates passed; exact live load, security, passivity, and teardown rows remain open |
| `LIVE-MCP` | [STS2MCP `55e0648`](https://github.com/Gennadiyev/STS2MCP/tree/55e064850a68f3b4cde7e5fd525bf9b2dec4e885) | Compatibility donor and coverage reference | MIT; unchanged source passes exact arm64 type/member compilation including .NET `9.0.7` parity, while its README still reports runtime testing on `v0.103.2`; its bootstrap/transport/state/action surface is not accepted for loading |
| `LIVE-AGPL` | [STS2-Agent `9f99876`](https://github.com/CharTyr/STS2-Agent/tree/9f99876d8dd11416aec13273956902d58a231ccb) | Live bridge/agent | AGPL-3.0-only; adoption/isolation decision required before modification or distribution |
| `LIVE-NETCAN` | [slay-the-spire2-agent `3ac97a1`](https://github.com/netcan/slay-the-spire2-agent/tree/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60) | Live C#/Python bridge prototype | No explicit repository software license found; reference-only absent permission |
| `PY-PRIOR` | [sts2-rl-agent `1b7e7ce`](https://github.com/zhiyue/sts2-rl-agent/tree/1b7e7ce35e608722650763938c153ea8bc370333) | Reported Python full-run simulator and bridge | No explicit repository software license found; reference-only absent permission |
| `ENGINE-CLI` | [sts2-cli `d11aa88`](https://github.com/wuhao21/sts2-cli/tree/d11aa883b582dd68bd39b331f3370746b30d447e) | Reported engine-hosted headless JSON CLI | MIT covers project-authored source, not copied/patched proprietary game assemblies |
| `STS1-PRECEDENT` | [CommunicationMod `5e417eb`](https://github.com/ForgottenArbiter/CommunicationMod/tree/5e417eb189530986b9047a3c9426889fb261d146) | Protocol and synchronization design precedent | MIT; design evidence only, not an STS2 executable candidate |
| `PROJECT-PY` | Current repository at campaign freeze commit | Project-owned Python combat simulator | Expansion candidate; currently combat-only and not presumed faithful to full STS2 |

Official mod-loader and Workshop tooling establish feasibility, but are not an
agent-control candidate. A newly discovered candidate may enter only through a
preregistration amendment or a new campaign.

## 6. Question register

Every answer must cite a test ID and artifact, not only source inspection.

### 6.1 Live bridge questions

- Does it load on the exact target build and platform without gameplay-affecting
  companion mods?
- Can it start, observe, act through, save, resume, and terminate a complete
  supported run?
- Does every actionable state expose all and only legal choices, including nested
  and incremental selections?
- Are run, decision, entity, card-instance, target, candidate, and event IDs
  stable for their declared lifetime?
- Can it distinguish actionable, automatically advancing, waiting, terminal,
  unsupported, and desynchronized states?
- Are automatic effects and events ordered, attributable, and observable at a
  sufficient fidelity for differential tests?
- Does action submission support expected-state validation, idempotent retry,
  controller exclusivity, and a knowable commit result?
- Can client and game restart/resume without duplicate actions or lost public
  history?
- What are reset time, decision-transition latency, sustainable run rate, and
  isolated multi-instance limits?
- Which fields are public, privileged, inferred, omitted, unstable, or
  version-coupled?
- Does enabling the bridge change any rules, RNG-observable outcomes, rewards,
  unlocks, save behavior, or timing-sensitive semantics?
- What breaks on a deliberately non-target smoke build, and does it fail closed?

### 6.2 Engine-hosted backend questions

- Does it execute locally owned target-build game rules or a divergent
  reimplementation, and what patches/stubs alter behavior?
- Can it traverse every required phase and nested selection with the same public
  semantics as the live game?
- Are initial state, RNG streams, event ordering, and continuation deterministic
  under exact replay?
- Can it reset cheaply, snapshot/restore arbitrary decision boundaries, branch,
  enumerate or sample chance, and run multiple isolated instances?
- Does headless execution skip UI-only gates in a way that changes rules or
  unlock/save semantics?
- What throughput, memory, startup, snapshot-size, and restore-latency envelope
  is achieved on declared hardware?
- Can the project lawfully depend on it using a user-owned installation without
  distributing proprietary or patched assemblies?
- How tightly is it coupled to one game build, platform, and private API surface?

### 6.3 Project-owned Python backend questions

- Can its current deterministic combat contract be adapted to the future typed
  backend protocol without preserving the fixed action/observation limitations?
- Are snapshots, semantic keys, explicit chance operations, and event ordering
  feasible without invasive duplication of rules?
- Which representative mechanics already agree with the live target and which
  are unsupported or divergent?
- What measured throughput remains after representative full-fidelity state,
  event, and snapshot requirements are added in a minimal spike?
- What is the estimated parity workload by mechanic family and complete-run
  phase, based on live differential evidence rather than content counts?
- Would a Python backend remain the most inspectable/searchable truth model, or
  should it specialize in search while an engine-hosted backend supplies corpus
  generation and validation?

`PY-PRIOR` may inform this question register, but its code cannot be copied or
treated as reusable unless permission/license status changes.

## 7. Common execution protocol

Each executable candidate advances through the same stages:

1. **Static audit:** revision, dependencies, build assumptions, license,
   endpoints/protocol, claimed phases, tests, privileged fields, and security.
2. **Build/load smoke:** clean target install, bridge/backend only, health and
   manifest capture, default-write posture, clean shutdown.
3. **Decision-contract probes:** observe/legal/apply behavior on controlled,
   reversible states; IDs, ordering, hashes, and error taxonomy.
4. **Phase corpus:** every row in Section 8, using natural runs plus declared
   targeted fixtures/save points where lawful.
5. **Transaction, fault, security, boundary, and passivity tests:** Sections
   9–11.
6. **Complete-run trials:** preregistered consecutive seeded runs without manual
   correction, followed by restart/resume trials.
7. **Performance and isolation:** cold/warm latency, sustained operation, resets,
   snapshots where supported, and instance scaling.
8. **Non-target build smoke:** only after target evidence is preserved; measure
   failure mode and patch coupling, never mix results into target metrics.

Every test case uses this record:

| Field | Requirement |
| --- | --- |
| Test ID/version | Stable ID and immutable procedure version |
| Hypothesis | One falsifiable claim |
| Preconditions | Build/candidate/profile/scenario hashes and required state |
| Procedure | Ordered operator and automated actions, including fault timing |
| Expected result | Preregistered observable pass/fail condition |
| Measurements | Named fields from Section 12 with units |
| Artifacts | Manifest, trace, logs, screenshots/video where useful, and hashes |
| Result | Pass/fail/partial/unsupported/invalid, deviation, operator, reviewer |

Exploratory discoveries become new versioned cases. They do not retroactively
change an executed case.

## 8. Required phase and overlay corpus

A complete natural run proves continuity. Targeted cases provide breadth and
rare edge coverage. Each required row needs at least one successful trace and
one relevant rejection/edge trace unless marked otherwise before freeze.

| Group | Required decisions and edges |
| --- | --- |
| Lifecycle | Launch, mod consent, dedicated profile, main menu, continue/new run, character, Ascension, explicit/random seed as chartered, unlock/timeline assumptions |
| Starting flow | Starting option/bonus, skip where legal, tutorial/FTUE popup, acknowledgement-only continuation |
| Map | Legal connected-node selection, invalid/unreachable node rejection, map reopen/overlay interruption |
| Combat basics | Play self/no-target/single-target/all-target cards, insufficient-cost rejection, end turn, victory and death |
| Combat state | Multiple enemies with stable identity through death/summon/escape; generated/upgraded/enhanced cards; powers/statuses; retained/exhausted cards; hand/pile limits |
| Potions | Use with each target shape, discard, full slots, unusable potion, consume-at-combat-end edge |
| Nested combat choices | Card/pile selection, multi-select, ordering, confirm/cancel, repeated target where applicable, automatic effects around the modal |
| Rewards | Gold, card choose/skip/reroll where available, potion with full slots, relic, nested reward, leaving/confirming |
| Shop | Buy card/relic/potion, insufficient gold, full potion slots, remove/transform/other supported service, leave, stale inventory action |
| Rest site | Every reachable action for the target slice, upgrade/selection submodal, unavailable-action rejection, leave/confirm behavior |
| Event | Branch choice, disabled condition, nested selection/reward/combat, leave, state carried into later floors |
| Treasure | Open/claim/leave semantics, relic choice or fight where applicable, overlay interruption |
| Boss/act boundary | Boss reward, boss relic/choice, act transition, map replacement, persistent state conservation |
| Save/resume | Save/quit at map, combat-safe boundary, reward/modal boundary where supported; client restart; game restart; resume and no duplicate commit |
| Terminal | Defeat, victory/true-ending status as scoped, game-over dismissal, run-summary/unlock popup, return to menu |
| Non-agent overlays | Pause/settings, card inspection, pile viewer, map drawing or comparable overlay, focus loss, tutorial, error/version popup; wait or reject without accidental action |

For each row, record whether the state is a genuine policy decision, an automatic
transition, an acknowledgement, or an unsupported UI state. UI polling must not
inflate the agent decision count.

## 9. Action transaction and recovery tests

Minimum cases:

| ID | Fault or race | Required evidence |
| --- | --- | --- |
| `TX-01` | Duplicate identical request before response | At most one game mutation; duplicate returns the original typed outcome |
| `TX-02` | Response lost after commit, then retry | `already_applied` or equivalent knowable result; no duplicate purchase/play/choice |
| `TX-03` | Request delayed until decision advances | Stale rejection against expected decision/hash; new state returned or observable |
| `TX-04` | Candidate reused outside lifetime | Clean rejection; no partial cost/payment or mutation |
| `TX-05` | Invalid target/parameter/malformed payload | Typed rejection, bounded error, bridge remains healthy |
| `TX-06` | Two controller clients race | One valid lease/controller; deterministic rejection or revocation semantics |
| `TX-07` | Client dies before/after submission | Lease expiry/recovery is observable; committed action is not guessed or repeated |
| `TX-08` | Bridge disconnect/restart | Public state and last committed sequence reconcile or fail closed |
| `TX-09` | Game process restart/save resume | Correct run/decision identity transition and no stale request acceptance |
| `TX-10` | Overlay/automatic transition appears during action | No action applied to the wrong screen; recovery reaches a coherent boundary |
| `TX-11` | Timeout with unknown commit status | Explicit `timeout_unknown`-class state followed by read-only reconciliation |
| `TX-12` | Unsupported content/phase | Explicit failure without plausible fabricated state or action |

Record retries, reconciliation reads, recovery time, final state hash, mutation
count, and whether human intervention was required. Unknown commit status that
cannot be reconciled is a critical defect.

## 10. Security and passivity tests

### 10.1 Local security

- Verify bind addresses for IPv4 and IPv6; mutating services must be loopback-only
  by default.
- Verify writes are disabled until explicitly armed and authenticated according
  to the frozen policy.
- Reject missing/invalid credentials, expired/revoked controller leases,
  oversized/malformed requests, and unsupported methods without game mutation.
- Confirm concurrent observers cannot become controllers implicitly.
- Confirm logs, errors, URLs, and artifacts do not reveal credentials, personal
  profile data, privileged state, or raw saves.
- Inventory debug/console/profile-deletion endpoints. They must be absent from
  the policy surface and disabled during performance/certification-style runs.
- Record dependencies, listening processes/ports, filesystem writes, child
  processes, and outbound network behavior.

A bridge that cannot meet the security target may still be useful as design
evidence, but cannot be adopted unchanged.

### 10.2 Gameplay passivity

Use paired, scripted action sequences on the same target build and declared run
seeds with (a) no bridge and (b) only the bridge enabled. Compare:

- public decision states and legal choices;
- ordered public events and observable RNG outcomes;
- card draws, enemy intents/actions, rewards, maps/events, and persistent state;
- damage, HP, gold, deck/relic/potion changes, and terminal result;
- unlock/profile/save effects and save hashes where meaningful;
- timing-sensitive rule outcomes under normal and declared fast settings.

Differences caused solely by the game's documented modded-save namespace are
recorded separately; they do not excuse semantic divergence. Minimize every
unexpected delta to the shortest reproducing trace. A bridge is “passive” only
relative to the tested build, configuration, and corpus.

## 11. Public/privileged information boundary

Produce a field-level inventory for every raw state, event, identifier, candidate,
and timing field:

| Classification | Meaning |
| --- | --- |
| Public-current | Visible at the decision boundary |
| Public-history | Previously observed and legitimately rememberable/derivable |
| Rules/content | Static mechanics allowed by the charter |
| Privileged | Hidden pile order, exact RNG/seed-derived state, unrevealed choices/rewards, private AI state, future events, debug internals |
| Operational | Build/health/timing data needed by the controller but not a policy feature |
| Unknown | Blocked from the policy surface until reviewed |

For every public claim, record its UI/rules basis. Test that:

- the public endpoint/schema contains no privileged or unknown fields;
- canonical public decision hashes and candidate IDs do not encode privileged
  values indirectly;
- candidate ordering, opaque IDs, error messages, response timing, and presence/
  absence do not leak hidden alternatives;
- seed and run identifiers follow the target charter;
- the policy process cannot call privileged endpoints or read privileged files;
- policy-ready trajectories are generated from public records, not by redacting
  an object still accessible at runtime;
- a deliberately privileged conformance recorder is separately enabled,
  stored, named, and access-controlled.

The required runtime component in this phase is a public-state tracker and
consistency reconciler. Persistent particle beliefs, hidden-RNG inference, and
learned recurrence are not prerequisites for bridge selection.

## 12. Trajectory corpus and measurement schema

### 12.1 Corpus layout

Each candidate/run produces a self-contained evidence bundle:

```text
campaign/<campaign-id>/<candidate-id>/<attempt-id>/
  manifest.json
  events.jsonl
  states.public.jsonl
  actions.jsonl
  decisions.jsonl
  errors.jsonl
  summary.json
  files.sha256
  privileged/          # separate access/retention policy; never policy input
  attachments/         # screenshots/video/minimized repros when required
```

The final repository need not store large/raw bundles; it stores validated
schemas, hashes, summaries, and lawful fixtures. The evidence index records the
external artifact location and retention policy.

### 12.2 Required run manifest fields

- campaign, charter, test-procedure, candidate revision/patch, and adapter IDs;
- exact game/build/depot/file fingerprints and ordered mods;
- host/runtime/hardware, settings, locale, profile/unlock fingerprint;
- run seed policy and public/withheld status;
- start/end wall-clock UTC and monotonic duration;
- corpus schema/logger versions and redaction mode;
- file list, sizes, hashes, missing/truncated status;
- operator, automation version, deviations, and reviewer.

### 12.3 Required per-decision/action fields

- run/attempt ID, monotonic event and decision sequences, phase/kind;
- public state hash, candidate IDs and candidate-set hash;
- controller lease/session, idempotency ID, expected decision/hash, request ID;
- selected action and typed parameters;
- received/validated/committed/next-actionable monotonic timestamps;
- outcome: accepted, rejected, stale, already applied, timeout unknown, no-op,
  unsupported, or terminal;
- post-state/transition hash, retries, reconciliation reads, recovery result;
- policy/manual/scripted source and any intervention;
- separately linked privileged record hash only when the test authorizes it.

### 12.4 Derived measurements

Report distributions and raw denominators, not only averages:

- phase/action coverage and legal-action soundness/completeness defect counts;
- autonomous run completion and consecutive-success count;
- invalid mutations, unknown commits, stale actions, duplicate mutations,
  desynchronizations, softlocks, crashes, timeouts, interventions, and recovery
  success/time;
- observe latency, validation/commit latency, commit-to-next-decision latency,
  end-to-end transition latency (`p50/p95/p99/max`);
- cold/warm startup, run reset, save/resume, snapshot and restore latency;
- decisions/second, simulator steps/second, combats/hour, runs/day, CPU, peak RSS,
  artifact bytes/decision, and isolated-instance scaling;
- deterministic replay matches and first-divergence location;
- passivity paired-trace matches/divergences;
- public-field audit findings and privileged-leak count;
- setup/maintenance effort, patch-specific changes, and unresolved questions.

Use one failure taxonomy across candidates. Exclusions and invalid attempts remain
in the raw index with reasons.

## 13. Licensing and redistribution review

Before executing modified or redistributed candidate code, record:

- exact revision and full license text/SPDX for every project component;
- license compatibility with this repository and intended distribution model;
- transitive dependencies and copied, generated, decompiled, or extracted
  provenance;
- whether evaluation requires loading, copying, patching, or deriving from game
  assemblies/content;
- what stays local to a user-owned installation and what, if anything, may be
  committed or shipped;
- obligations for notices, source availability, modifications, network use, and
  combined/derivative works, reviewed by a qualified person rather than assumed;
- rights and retention policy for extracted metadata, traces, screenshots/video,
  saves, human demonstrations, and trained artifacts;
- whether the chosen approach is adoption, fork, separate-process dependency,
  protocol interoperability, clean-room reimplementation, or reference only.

Specific cautions:

- `LIVE-NETCAN` and `PY-PRIOR` remain reference-only absent an explicit license
  or permission.
- `LIVE-AGPL` needs a conscious AGPL adoption/isolation decision.
- `ENGINE-CLI`'s MIT license does not license `sts2.dll`, patched derivatives, or
  game content. Prefer a lawful local setup from a user-owned installation; do
  not distribute the resulting assemblies without approval.
- Public GitHub visibility and “research/educational” wording are not software
  reuse licenses.

Legal uncertainty is reported as a decision constraint, not hidden in a
technical score.

## 14. Preregistered exit gates

All `TBD-FREEZE` values must be replaced and signed before comparative complete-
run trials. A candidate must pass every applicable knockout gate; weighted
scores cannot compensate for a critical failure.

### 14.1 Live truth path knockout gates

| Gate | Frozen threshold | Result |
| --- | --- | --- |
| Exact build | Manifest and cryptographic identity complete; target branch matches charter | **PASS (binary/build identity)** — [build `23811903` manifest](../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json) |
| Required phase coverage | `___%` required rows and `___%` required edge cases, with named allowed exceptions | `TBD-FREEZE` |
| Consecutive autonomous runs | `N = ___` on preregistered seeds; zero manual correction | `TBD-FREEZE` |
| Invalid/duplicate mutation | `0` | `TBD-FREEZE` |
| Unknown commit | `0` unreconciled cases across `___` injected faults | `TBD-FREEZE` |
| Desynchronization | At most `___`; `___%` recovered within `___ ms`; no silent continuation | `TBD-FREEZE` |
| Restart/resume | `___/___` client and game restart cases reconstruct correctly | `TBD-FREEZE` |
| Legal actions | `0` known soundness defects and at most `___` completeness defects across frozen corpus | `TBD-FREEZE` |
| Public boundary | `0` privileged/unknown fields or indirect leaks on policy surface | `TBD-FREEZE` |
| Passivity | `0` unexplained semantic/RNG-observable divergences across `N = ___` paired traces | `TBD-FREEZE` |
| Security | All critical Section 10.1 cases pass; exception policy `___` | `TBD-FREEZE` |
| Latency | Commit-to-next-actionable `p95 <= ___ ms`, `p99 <= ___ ms` under declared settings | `TBD-FREEZE` |
| Artifacts | `___%` valid bundles; no missing required event/action/state records | `TBD-FREEZE` |
| Legal feasibility | Approved adoption/fork/dependency/distribution boundary | `TBD-FREEZE` |

### 14.2 Fast-backend feasibility gates

| Gate | Frozen threshold | Result |
| --- | --- | --- |
| Required phase capability | Supported set `___`; unsupported set explicitly fail-closed | `TBD-FREEZE` |
| Differential fidelity | `0` unexplained divergences across frozen representative corpus of `___` traces | `TBD-FREEZE` |
| Deterministic replay | `___/___` exact continuations match through terminal state | `TBD-FREEZE` |
| Snapshot/restore | `___/___` arbitrary supported boundaries round-trip; `p95 <= ___ ms`; size `<= ___` | `TBD-FREEZE` |
| Throughput | `>= ___` decisions/s and `>= ___` combats/s per declared hardware unit | `TBD-FREEZE` |
| Scaling | `___` isolated instances with efficiency `>= ___%` and no cross-instance state | `TBD-FREEZE` |
| Search affordances | Required branch/chance/key capabilities `___` demonstrated | `TBD-FREEZE` |
| Patch effort | Target-to-smoke-build migration effort/changed surface `<= ___` or explicitly accepted | `TBD-FREEZE` |
| Legal feasibility | Local use and intended project distribution approved | `TBD-FREEZE` |

If the selected project bridge fails, the correct live-path outcome is to
revise/rebuild it from named failures, run a separately approved eligible
comparator when that would discriminate the design, or defer with a named
missing experiment. The correct fast-backend outcome may likewise be deferred.
Neither lane relaxes thresholds post hoc.

## 15. Parallel work packages

| Package | Work | Dependencies | Output |
| --- | --- | --- | --- |
| `WP0 Charter/build` | Binary/build identity captured; capture dedicated profile and freeze remaining charter/gates | None; remaining work blocks campaign evidence | Charter reference, preregistration, profile record, accepted build manifest |
| `WP1 Static/legal` | Revision-pinned capability, dependency, security, provenance, and license audit | Candidate register | Candidate dossiers and eligibility decisions |
| `WP2 Live bridge` | Build the restricted project-owned stages, then run load, decision, phase, latency, and patch-coupling probes | WP0; WP1 eligibility; restricted bridge design | Per-stage project bridge evidence bundles; optional candidate comparators only after separate approval |
| `WP3 Corpus` | Scenario registry, complete-run and targeted phase traces, validator/index | WP0; begins with first viable live bridge | Ground-truth trajectory corpus |
| `WP4 Fault/security/boundary` | Transaction injection, recovery, loopback/auth, passivity, field audit | Viable live candidate from WP2 | Fault matrix, security/passivity/information reports |
| `WP5 Engine hosted` | Engine-backend setup, fidelity, snapshot, throughput, isolation, legal boundary | WP0; WP1 eligibility | Engine-hosted feasibility report |
| `WP6 Python` | Current-backend contract fit, representative differential probes, parity-work estimate | WP0 and initial WP3 fixtures | Python expansion feasibility report |
| `WP7 Synthesis` | Validate artifacts, apply gates, score eligible choices, sensitivity review | WP1–WP6 | Decision records and Phase 2 inputs |

WP1, setup preparation for WP2/WP5, schema validation for WP3, and non-mutating
analysis for WP6 may run in parallel. No work package may bypass WP0's target
identity or WP1's reuse restrictions.

## 16. Decision matrix

Score live truth paths and fast backends separately. Do not select one candidate
merely because it spans both roles.

### 16.1 Scoring

Freeze weights before full trials. For each criterion record score, confidence,
evidence IDs, and unresolved risks.

- Score `0`: contradicted/critical failure.
- Score `1`: major gap or fragile manual workaround.
- Score `2`: partial support with bounded remediation.
- Score `3`: passes frozen requirement.
- Score `4`: materially exceeds requirement with reproduced evidence.
- Confidence `A`: repeated target-build measurement.
- Confidence `B`: single target-build measurement or strong focused evidence.
- Confidence `C`: static inspection/upstream test only.
- Confidence `D`: upstream claim or unknown.

Unknowns receive no assumed capability. Weight sensitivity is reported; a choice
that flips under small reasonable weight changes needs another experiment or an
explicit strategic decision.

### 16.2 Live path criteria

| Criterion | Weight | Knockout? |
| --- | ---: | --- |
| Target-build/platform compatibility | `TBD-FREEZE` | Yes |
| Phase/legal-action completeness | `TBD-FREEZE` | Yes |
| Transaction safety and recovery | `TBD-FREEZE` | Yes |
| Public/privileged separation | `TBD-FREEZE` | Yes |
| Gameplay passivity | `TBD-FREEZE` | Yes |
| Security posture | `TBD-FREEZE` | Yes |
| Event/identity/conformance fidelity | `TBD-FREEZE` | Yes |
| Latency, operational stability, restart | `TBD-FREEZE` | Threshold-dependent |
| Patch maintainability and code quality | `TBD-FREEZE` | No |
| License/distribution fit | `TBD-FREEZE` | Yes |
| Estimated adopt/fork/build effort | `TBD-FREEZE` | No |

Allowed decisions per candidate: `adopt pinned dependency`, `fork`, `clean-room
protocol reimplement`, `reference only`, or `reject`. The selected path includes
the exact revision, remediation list, ownership, and patch policy.

### 16.3 Fast-backend criteria

| Criterion | Weight | Knockout? |
| --- | ---: | --- |
| Target-build semantic fidelity | `TBD-FREEZE` | Yes |
| Determinism/snapshot/branching | `TBD-FREEZE` | Yes for strongest-search role |
| Full-run phase support | `TBD-FREEZE` | Role-dependent |
| Throughput and multi-instance scaling | `TBD-FREEZE` | Threshold-dependent |
| Search/chance/transposition affordances | `TBD-FREEZE` | Role-dependent |
| Inspectability, testability, and debugging | `TBD-FREEZE` | No |
| Patch migration burden | `TBD-FREEZE` | No |
| License/local-install/distribution fit | `TBD-FREEZE` | Yes |
| Estimated parity and maintenance effort | `TBD-FREEZE` | No |

Allowed decisions: `Python`, `engine-hosted local`, `hybrid`, or `defer`. A hybrid
decision must name which backend owns training, search, corpus generation,
conformance, and certification; “use both” alone is not a decision.

## 17. Final outputs

Phase 1 closes with these reviewable artifacts:

1. Frozen target-charter reference and exact build/profile/mod manifest.
2. Candidate dossiers with revision, capability, security, provenance, license,
   and allowed reuse mode.
3. Versioned test/scenario registry and deviation log.
4. Validated public trajectory corpus index plus separately controlled privileged
   conformance index.
5. Phase/overlay coverage report and minimized divergence fixtures.
6. Action transaction, fault recovery, security, public-boundary, and gameplay-
   passivity reports.
7. Live latency/reliability/throughput report with raw denominators.
8. Engine-hosted and project-owned Python feasibility reports.
9. Completed knockout gates and weighted matrices with confidence and sensitivity.
10. Two decision records: live bridge adopt/fork/build and fast-backend
    Python/engine/hybrid.
11. Phase 2 input package: accepted capability gaps, remediation backlog,
    proposed canonical contract constraints, corpus/schema versions, revised
    effort estimates, and named blockers.

The review records failed candidates and negative results. Phase 2 begins only
when the target build is reproducible, one live truth path passes its knockout
gates, and the fast-backend choice has an evidence-backed role definition. If
those conditions are not met, Phase 1 remains open with a bounded next experiment.
