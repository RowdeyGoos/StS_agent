# Phase 1 Static Candidate-Audit Synthesis

- **Status:** Static audit, STS2MCP compile-only evidence, and the restricted
  project-owned bridge design are complete; the dedicated shallow metadata
  boundary and current direct-child projection passed D1 and D1B, but no bridge
  has passed a load, behavioral, or fidelity gate
- **Target build:** Slay the Spire 2 `v0.107.1`, Steam build `23811903`, macOS
  universal depot `2868842`
- **Build manifest:**
  [`sts2-steam-main-build-23811903-macos-universal.json`](../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)
- **Parent evidence plan:**
  [`PHASE_1_INTEGRATION_SPIKE.md`](PHASE_1_INTEGRATION_SPIKE.md)

## Current handoff

In plain terms, the working profile is a **throwaway project test profile**. It
is not the user's normal save and it is not yet the final unlocked benchmark
fixture.

| Work package | State | Dependency | Need from the user |
| --- | --- | --- | --- |
| Exact game-build capture | Complete | None | Nothing |
| Revision-pinned static candidate audit | Complete | Exact source pins | Nothing |
| Project test-profile creation | User-confirmed complete | Game UI | Nothing |
| STS2MCP compile-only probe | Complete; exact source passed twice with zero MSBuild/compiler warnings or errors | Exact MIT source, current .NET 9 SDK, runtime-parity .NET 9 SDK, and pinned game assemblies | Nothing |
| Restricted live-bridge design | Complete; lean project-owned `live_probe_v0` selected | Compile result plus [independent hash-bound reviews](research/PHASE_1_BOUNDARY_REVIEW_RECORD.md) | Nothing; no bridge source, package, installation, or load was produced |
| Narrow profile metadata discovery | D1 and D1B passed with disclosed execution details | Separately approved hash-bound scopes | Nothing; see the [D1](research/PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md) and [D1B](research/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md) sanitized results |
| Stable profile-local content fingerprint | Blocked pending corrected-invocation approval | Exact PF-HASH request embeds two matching D1C boundary snapshots before two fixed-size fresh-open byte samples | Attempt 1 stopped before target-content access because of a runner binding defect; no byte read/hash occurred and no rerun is authorized |
| Complete boundary/recoverable baseline | Blocked | Resolve account-scoped and modded-namespace coverage, then use distinct approvals for copy, optional offline parsing, Cloud containment, restore, and launch checks | No copy, parse, restore, launch, or Cloud API/change is authorized |
| `BR0-PREFLIGHT` contract/accessor/package freeze | Ready after this document review | Restricted bridge design | Nothing; this design-only freeze creates no mod source or package and must finish before implementation fans out |
| Isolated bridge load | Blocked | Restricted bridge surface, disposable profile, and load-probe protocol | Separate later installation/launch approval |
| Comparable candidate campaign | Blocked | Frozen fixture, charter IDs, thresholds, retention, and evidence schemas | Nothing yet |

The compile-only and restricted-design lanes are complete. The user confirmed
the clean-close/no-run and Cloud-idle boundary, and the approved metadata-only
probe established one unique local dedicated-profile namespace without
retaining its identity. The separately approved
[D1B probe](research/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md)
established that the current projection matches the fixed core/backup-sidecar
allowlist. It cannot prove object continuity from D1, content equality, backup
validity, recoverability, or Cloud behavior. No choice between clean unlock
progression, an authorized clone, or setup tooling is needed yet.
D1C was reviewed, deliberately unselected/skipped, and never executed; its
fail-closed profile-root/empty-history predicate is incorporated into the
exact frozen [PF-HASH request](PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md). This
composition removes one approval round while still requiring two matching
complete boundary snapshots before any candidate file is opened, sized, or
read. Its first approved invocation
[stopped pre-content](research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md)
because the runner attempted the wrong fixed profile component. No automatic
retry occurred or is authorized.

## 1. Purpose and limits

This document turns the revision-pinned static audits and first compile-only
result into an execution shortlist. It does not select a production bridge or
fast backend. Source inspection can establish reported scope, implementation
shape, license posture, obvious safety gaps, and the next discriminating tests.
Compilation can add exact type/member signature evidence. Neither establishes
runtime loading, gameplay passivity, semantic fidelity, reliability, throughput,
or complete public-information coverage.

The detailed evidence records are split by role:

- [`PHASE_1_LIVE_BRIDGE_DOSSIERS.md`](research/PHASE_1_LIVE_BRIDGE_DOSSIERS.md)
  covers live-game bridge candidates and the Slay the Spire 1 protocol precedent.
- [`PHASE_1_FAST_BACKEND_DOSSIERS.md`](research/PHASE_1_FAST_BACKEND_DOSSIERS.md)
  covers engine-hosted and Python simulation paths.
- [`PHASE_1_STS2MCP_COMPILE_PROBE.md`](research/PHASE_1_STS2MCP_COMPILE_PROBE.md)
  records exact source, toolchains, resolved assemblies, outputs, diagnostics,
  and game-install integrity for the compile-only result.
- [`PHASE_0_PROFILE_FIXTURE_PLAN.md`](PHASE_0_PROFILE_FIXTURE_PLAN.md) defines
  how live tests can be isolated from personal profile data.
- [`PHASE_0_PROFILE_METADATA_DISCOVERY_REQUEST.md`](PHASE_0_PROFILE_METADATA_DISCOVERY_REQUEST.md)
  preserves the exact hash-bound metadata-only scope that was approved.
- [`PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md`](research/PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md)
  records its sanitized pass, execution caveats, and remaining unknowns.
- [`PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_REQUEST.md`](PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_REQUEST.md)
  preserves the separate approved fixed-allowlist D1B scope.
- [`PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md`](research/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md)
  records the sanitized current-projection pass and strict limits.
- [`PHASE_0_PROFILE_BACKUP_SIDECAR_RESULT_REVIEW.md`](research/PHASE_0_PROFILE_BACKUP_SIDECAR_RESULT_REVIEW.md)
  binds the independent D1B execution-result sign-offs to exact hashes.
- [`PHASE_0_PROFILE_RECOVERY_UNIT_METADATA_REQUEST.md`](PHASE_0_PROFILE_RECOVERY_UNIT_METADATA_REQUEST.md)
  preserves the reviewed D1C metadata-only alternative that was deliberately
  skipped and never executed.
- [`PHASE_0_PROFILE_RECOVERY_UNIT_SCOPE_REVIEW.md`](research/PHASE_0_PROFILE_RECOVERY_UNIT_SCOPE_REVIEW.md)
  binds the independent review of that preserved alternative to its exact hash.
- [`PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md`](PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md)
  defines the frozen fixed-size, two-sample content-fingerprint scope and its
  embedded fail-closed preflight; no corrected invocation is currently
  approved.
- [`PHASE_0_PROFILE_BASELINE_HASH_SCOPE_REVIEW.md`](research/PHASE_0_PROFILE_BASELINE_HASH_SCOPE_REVIEW.md)
  binds the independent authorization, race/claim, canonicalization, and
  privacy reviews of PF-HASH to its exact hash.
- [`PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md`](research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md)
  records the sanitized pre-content stop, implementation deviation, and fresh
  approval boundary for a corrected invocation.
- [`PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_REVIEW.md`](research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_REVIEW.md)
  binds independent execution-stage, static-path, privacy, and authorization
  sign-offs to the exact stopped-result hash.
- [`PHASE_0_PROFILE_BASELINE_HASH_CORRECTED_RUNNER_SYNTHETIC_VALIDATION.md`](research/PHASE_0_PROFILE_BASELINE_HASH_CORRECTED_RUNNER_SYNTHETIC_VALIDATION.md)
  validates the corrected component binding, complete success mechanics, hard
  byte ceiling, output markers, and seven fail-closed families without real
  profile or process-table access.
- [`PHASE_0_PROFILE_METADATA_RESULT_REVIEW.md`](research/PHASE_0_PROFILE_METADATA_RESULT_REVIEW.md)
  preserves the historical pre-execution D1 result and D1B scope review.
- [`PHASE_1_RESTRICTED_BRIDGE_DESIGN.md`](PHASE_1_RESTRICTED_BRIDGE_DESIGN.md)
  records the selected project-owned bridge boundary, staged capabilities, and
  acceptance gates.
- [`PHASE_1_BOUNDARY_REVIEW_RECORD.md`](research/PHASE_1_BOUNDARY_REVIEW_RECORD.md)
  binds the independent bridge/profile-scope sign-offs to exact document
  hashes.

The labels in this synthesis mean:

- **source-verified:** directly observed in the pinned source revision;
- **upstream-reported:** stated by the project but not reproduced here;
- **unknown:** requires a target-build experiment or an explicit rights review;
- **ineligible for code reuse:** public visibility does not supply a software
  license, or the intended use needs a separate license decision.

## 2. Static outcome

The static evidence supports a staged, reversible investigation rather than an
immediate architecture choice:

1. Establish a disposable, reproducible game profile before any bridge is
   enabled.
2. Build a lean project-owned read-only probe as the first live path. Use the
   strongest eligible third-party candidate only as revision-pinned
   compatibility evidence and a source of individually audited, attributed
   adapter snippets.
3. Treat the live game as the only semantic authority and capture ground-truth
   traces before expanding a simulator.
4. Evaluate the engine-hosted and project-owned Python paths separately. A live
   bridge and a fast backend solve different problems and need not come from the
   same project.
5. Preserve the current Python combat simulator as `combat_v0`, a search and
   conformance laboratory, and a possible future backend adapter. Do not turn
   its current fixed observation/action API into the full-game contract.

No third-party candidate was cloned into the project, installed, built, or
executed during the original static audit; source was inspected through pinned
public pages. The separately authorized compile-only probe later downloaded and
built the exact STS2MCP pin only in disposable storage. It did not install or
execute the output, modify the game, or access any profile or save.

## 3. Candidate shortlist

### 3.1 Live truth path

| Candidate | Static disposition | Why it remains useful | Why it cannot be used unchanged |
| --- | --- | --- | --- |
| Project-owned `live_probe_v0` | **Selected first live-path design; not implemented** | Small authenticated read-only surface, allowlisted public projection, exact build guard, explicit lifecycle, and no dormant mutation/profile code | Must still compile, package, load, and pass security/passivity/teardown gates on the target |
| [`STS2MCP@55e0648`](https://github.com/Gennadiyev/STS2MCP/tree/55e064850a68f3b4cde7e5fd525bf9b2dec4e885) | **Compile gate passed; retain as compatibility donor/reference, not the runtime foundation** | MIT, broad decision coverage, explicit `v0.107.1` changes, and two unchanged-source compiles against exact arm64 assemblies including .NET `9.0.7` parity | Runtime loading/macOS behavior unproved; central bootstrap/transport/state/action seams violate the restricted boundary and would require replacement |
| [`netcan/slay-the-spire2-agent@3ac97a1`](https://github.com/netcan/slay-the-spire2-agent/tree/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60) | **Transaction-design reference; optional second probe only after permission** | Session/state/decision/action identities and read-only default are useful design evidence | No software license, much older Windows evidence, incomplete phases, possible ordered-draw leak, and timeout retries can enqueue duplicate mutations |
| [`CharTyr/STS2-Agent@9f99876`](https://github.com/CharTyr/STS2-Agent/tree/9f99876d8dd11416aec13273956902d58a231ccb) | **Coverage comparator/reference** | Broad recent action/state surface and relevant `v0.107.1` history | Raw seed and unrevealed Crystal Sphere information reach its agent view; no idempotent commit/reconciliation envelope or lease; `AGPL-3.0-only` requires a deliberate adoption/isolation decision |
| [`CommunicationMod@5e417eb`](https://github.com/ForgottenArbiter/CommunicationMod/tree/5e417eb189530986b9047a3c9426889fb261d146) | **STS1 precedent only** | Stable decision snapshots, advertised legal commands, and one child-controller channel | Wrong game; raw seed and ordered draw pile; no transactional recovery or idempotency |

The STS2MCP pin has conflicting upstream version text: its commit says it fixes
`v0.107.1` integration, while its README still says tested on `v0.103.2`. The
compile-only probe now establishes exact-build signature compatibility with zero
MSBuild/compiler warnings or errors. It does not resolve runtime behavior. No
loaded bridge should expose the unchanged candidate's raw actor/profile surface.

### 3.2 Fast backend

| Candidate | Static disposition | Main evidence gap |
| --- | --- | --- |
| Current project at `3d3b12e` | **Keep as `combat_v0`, search laboratory, and future adapter seed** | Combat-only; no canonical events or versioned serialized snapshot/full-run protocol |
| [`sts2-cli@d11aa88`](https://github.com/wuhao21/sts2-cli/tree/d11aa883b582dd68bd39b331f3370746b30d447e) | **Optional local engine/corpus probe after rights and artifact-boundary approval** | Older build, behavior-changing patches/stubs and recovery mutation, incomplete decision surfaces, no arbitrary snapshot/branch API, and no qualified throughput evidence |
| [`sts2-rl-agent@1b7e7ce`](https://github.com/zhiyue/sts2-rl-agent/tree/1b7e7ce35e608722650763938c153ea8bc370333) | **Reference only** | No software license, decompiled-source provenance boundary, unproved parity, no snapshot API, and a lossy fixed `151`-observation/`157`-action Gym surface |

The engine-hosted candidate is not currently a search candidate. Its potential
value is local execution of game-derived rules for corpus and conformance work.
The project-owned Python path is the only current route with functional
covered-state branching, but its cost is not yet qualified and it must earn
every supported mechanic against live evidence.
A hybrid remains plausible; “hybrid” will be meaningful only when training,
search, corpus generation, conformance, and certification ownership are named.

STS2MCP compile compatibility now has direct tier-1 evidence. All runtime
capability confidence remains `D` (upstream claim or unknown) until target-build
execution. Static implementation and license findings are at most `C`; no
weighted candidate score is assigned before the weights and knockout thresholds
are frozen.

## 4. Current project fit

The project-owned Python code has several properties worth carrying forward:

- randomness is explicit and seedable;
- mutable combat state can be cloned while preserving RNG state and shared-RNG
  identity;
- structured observations are separate from learned encodings;
- legal actions are generated by the environment and masked for policies;
- stable enemy slots avoid accidental target-identity shifts;
- exact bounded combat search records proof status instead of calling a
  resource-limited result optimal;
- information-aware root analysis already distinguishes future chance from
  current hidden-state hypotheses;
- tests cover deterministic encounters, actions, encodings, search, training,
  and trace analysis.

Those strengths are foundations, not evidence of full-game readiness. The
current implementation is combat-only and supports a deliberately small set of
cards, enemies, and statuses. It has no map, route, reward, shop, event, rest,
treasure, potion, relic, deck-evolution, profile, save/resume, act-transition,
or complete-run state machine. Its policy surface is a fixed-width vector and a
global hand-slot/target-slot action grid. Its trajectory is one record per
player step rather than an ordered event stream.

The optimized combat clone is useful for same-process search, but it is not yet
a versioned serialized snapshot/restore contract. The search state contains
hidden pile order and future RNG state, so the exact oracle is a hindsight
diagnostic and cannot be exposed to the deployed actor. There are no canonical
run, decision, entity, candidate-lifetime, expected-state, or idempotency IDs.

Consequently, the safe reuse boundary is:

| Keep and adapt | Freeze or replace at the full-game boundary |
| --- | --- |
| Seeded RNG discipline and explicit chance tests | One global fixed action grid |
| Structured debug state separated from encodings | Fixed catalog one-hot observation |
| Legal-action generation and target stability lessons | Combat-shaped reward as run utility |
| Clone/state-key/search diagnostics | Private clone function as a snapshot protocol |
| Test and benchmark discipline | Step-level records as the complete event model |
| Combat mechanics that pass live differential tests | Simulator internals as actor-visible information |

The production-facing backend protocol should therefore be introduced beside
`CombatEnv`, with an adapter for `combat_v0`, instead of rewriting every current
caller around an unproven full-game schema.

## 5. Safety constraints for the first live probe

Before any live bridge is run, the probe must satisfy all of these constraints:

- use only the dedicated fixture profile and a recoverable baseline;
- verify the clean base-install projection and the exact non-colliding bridge,
  manifest, and generated-config overlay separately; do not expect the raw
  whole-install tree hash to remain unchanged while a bridge is present;
- expose only loopback transport and verify the actual bound interfaces;
- authenticate or otherwise provide operating-system-enforced controller
  exclusivity;
- remove or hard-disable profile deletion, arbitrary file access, debug/console,
  and unrelated multiplayer/profile endpoints from the test surface;
- split public policy state from privileged conformance state;
- impose request/body and response bounds plus timeouts;
- precreate and hash generated configuration, remove or explicitly declare and
  passivity-test every load-time patch, and prove listener/patch teardown or
  clean process-exit isolation;
- attach a unique request ID and expected decision/state identity to mutations;
- cache or reconcile duplicate requests so a timeout cannot silently double-act;
- fail closed on an unknown build, unknown decision kind, unknown field, or
  ambiguous commit result;
- record the exact source revision, build inputs, binary hash, configuration,
  mod order, and profile-fixture identity.

A candidate can be useful prior art even when it cannot meet these constraints
unchanged. The selected outcome for the first probe is the lean project-owned
bridge in [`PHASE_1_RESTRICTED_BRIDGE_DESIGN.md`](PHASE_1_RESTRICTED_BRIDGE_DESIGN.md),
not a waiver of the constraints or an inherited upstream server.

## 6. Recommended experiment order

Profile discovery and restricted bridge design are now separate parallel lanes;
the unchanged-source compile tier is complete. The dependency is strict at Gate
D: no candidate may be loaded until the disposable fixture and restricted
bridge surface are ready.

Keep four evidence tiers distinct:

1. **Compile-only exploratory probe:** exact source and toolchain; no profile,
   mod installation, or game launch.
2. **Isolated read-only load probe:** throwaway project profile, mutation routes
   disabled, no access to a personal source, and no candidate ranking claim.
3. **Bounded mutating exploratory probe:** verified golden/working-copy reset,
   security and controller gates, named tests, and quarantined post-test state;
   results may design thresholds but are not comparative campaign evidence.
4. **Comparable candidate campaign:** full fixture, charter IDs, thresholds,
   retention, failure policy, and evidence schemas frozen before results.

### Gate A — fixture authorization

The user created the project-only profile through the normal game UI and
confirmed normal close without starting/resuming a run, Steam Cloud enabled,
and Cloud `Up to Date`/idle. The separately approved D1 and D1B metadata scopes
passed; see their [D1](research/PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md)
and [D1B](research/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md) sanitized
results.

This closes only shallow local-boundary and current direct-child classification.
No contents or hashes were read, temporal identity with D1 is unproved, and no
copy/golden, Cloud behavior, or logical-state claim follows. Do not enumerate
unrelated profile roots or access a personal source.

D1C was reviewed, deliberately unselected/skipped, and never executed. The next
exact fixture request remains `PF-HASH-BASELINE-V1`, which incorporates D1C's
fail-closed predicate as two matching pre-read boundary snapshots and then
allows exactly two fixed-size fresh-open hash samples of the four allowlisted
files. Attempt 1 stopped before the actual profile boundary and before target
content because of a runner component-construction defect. A corrected
invocation requires fresh explicit approval and all immediate confirmations. It
does not authorize parsing, copying, Cloud access or changes, restore, launch,
installation, or bridge work.

### Gate B — toolchain and source preparation (complete for STS2MCP)

The exact upstream Git tree, current servicing SDK, historical runtime-parity
SDK, and all resolved game-assembly inputs are recorded in the compile report.
Building a bridge against the locally owned game assembly remains separate from
installing it; the latter still needs an explicit, reviewable scope.

### Gate C — compile-only compatibility probe (passed for unchanged STS2MCP)

The unchanged pin compiled twice against the pinned `v0.107.1` arm64
installation, including SDK/runtime `9.0.303/9.0.7` parity, with zero
MSBuild/compiler warnings or errors. See the
[`STS2MCP compile-only probe`](research/PHASE_1_STS2MCP_COMPILE_PROBE.md).
The project-owned `live_probe_v0` must repeat this gate under the stricter
requirements in the restricted bridge design. A compile pass does not establish
load or behavioral compatibility.

### Gate D — isolated load and read-only probe

After a separate future approval, install only the declared project-owned
`R0a` overlay without replacing any base file. Precreate and hash configuration
so loading creates no untracked bridge file. The artifact contains no Harmony
patch or mutation/profile route. Verify health, manifest, visible-screen read,
exact bound interface, authentication, listener/port release, clean
process-exit isolation, and a clean base-control restart without submitting
gameplay or profile mutations. A failure must leave the base game and fixture
recoverable.

### Gate E — transaction and phase probes

Run the preregistered decision, duplicate/stale action, timeout, restart,
security, passivity, and public-boundary matrices. Only after those gates pass
should the bridge generate a full-run ground-truth corpus.

### Gate F — fast-backend probes

Use the live corpus to test deterministic replay, snapshot/restore, branching,
chance control, throughput, and patch burden for each eligible fast-backend
role. Run the engine-hosted and project-owned Python experiments against the
same normalized fixtures and do not infer fidelity from content counts.

## 7. What this increment does not decide

The following Phase 0 and Phase 1 choices remain open:

- which profile-fixture construction path the user authorizes;
- exact `live_probe_v0` DTO limits, configuration/token path, and inspected
  visible-screen accessors before implementation;
- whether an engine-hosted backend is acceptable for local use under the
  intended distribution model;
- whether Python, engine-hosted execution, or a hybrid owns training, search,
  corpus generation, and certification;
- the numerical latency, coverage, reliability, throughput, snapshot, and
  campaign thresholds;
- the final canonical protocol schemas and `combat_v0` freeze identity.

Keeping these open is deliberate. The compile gate narrows signature risk only;
selection requires target-build runtime and behavioral evidence.
