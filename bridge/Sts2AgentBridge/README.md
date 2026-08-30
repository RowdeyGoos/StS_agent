# STS2 Agent Bridge (`R0i`)

This directory contains the first deliberately restricted, project-owned live
integration slice for the Slay the Spire 2 agent. `R0a` proved the loader and
public-screen path, `R0b` exposed one real combat decision, `R0c` added one
snapshot-bound card play, and `R0d` completes one bounded combat turn through
a replaceable host decision provider. `R0e` repeats that verified loop until
the current combat reaches an authoritative victory or defeat result. `R0f`
adds one bounded reward-screen decision: observe the offered cards and apply
Skip through the game's public reward APIs, then verify arrival at the map.
`R0g` exposes the currently travelable map nodes and applies one
snapshot-bound node selection through the game's public map API. `R0h`
composes the existing bounded controllers into one verified floor transition:
combat victory, reward skip, and one legal map selection. `R0i` expands that
same boundary into a batched run slice: granular gold/card reward handling,
bounded rest-site and standard-event choices, and up to three combat-floor
transitions under replaceable host decision providers.

The controlling contract is the accepted
[Phase 1 BR0 preflight freeze](../../docs/PHASE_1_BR0_PREFLIGHT.md). The broader
boundary and rationale are in the
[restricted bridge design](../../docs/PHASE_1_RESTRICTED_BRIDGE_DESIGN.md).

## Scope and non-goals

The production assembly is `Sts2AgentBridge.dll`, version `0.8.0`, with protocol
`live_probe_v0`. When enabled and compatible, it exposes eleven exact
authenticated routes on literal IPv4 loopback `127.0.0.1:43117`: seven reads
and four action POSTs. Its loader manifest declares
`affects_gameplay: true`.

The combat path can enqueue at most 48 advertised, snapshot-bound actions per
combat and 144 per bridge process. Each decision ID can be accepted only once.
The allowed combat actions are card play and end turn. The complete-combat host
controller also enforces a 12-round bound and stops on the first authoritative
victory or defeat result. The reward path can claim gold, open a card reward,
choose one offered card, skip a skippable card reward, and proceed; it is capped
at 17 actions per reward session, three sessions, and 51 actions per process.
Map travel is capped at three accepted destinations, while rest-site heal/
proceed and safe standard-event choices share a 12-action process cap. Custom,
nested, dangerous, and unsupported room interactions fail closed. Potions,
shops, full-map planning, search, models, and an in-process agent runtime remain
out of scope. The batched controller attempts at most three combat floors and
keeps combat, reward, map, and room provider seams separate. It does not read
profiles, saves, progress,
preferences, history, replay, seeds, or multiplayer identity. It does not use
Harmony, input dispatch, outbound networking, or arbitrary filesystem access.

Repository-local compilation, tests, surface verification, and install-free
packaging do **not** authorize any of the following:

- writing into the game installation or operator-configuration directory;
- launching the game or loading the bridge into it;
- accessing a profile, save, Steam Cloud state, or operator credential; or
- conducting a live probe or removal campaign.

Each such operation requires its own exact artifact-bound authorization
checkpoint. Earlier completed campaigns are evidence, not standing permission
for another installation or launch. Outside an active approval, use only
disposable work/output roots and the pinned game assemblies as read-only compile
references.

## Current verification status

The living cross-milestone disposition is maintained in
[`docs/PHASE_1_CURRENT_STATUS.md`](../../docs/PHASE_1_CURRENT_STATUS.md). In
summary, bounded live smokes have reached `R0i` and demonstrated menu/Settings,
combat, granular card/gold rewards, map selection, and one composed floor
transition. Rest-site and standard-event controllers and the full three-combat-
floor cap remain fixture-demonstrated rather than live-accepted. One batched
attempt stopped on a transient `decision_response_mismatch`; the narrower combat
path subsequently resumed, but the composed controller still needs a repeatable
multi-floor live pass.

## Prerequisites

- Python 3.10 or newer.
- The repository bridge root as a canonical absolute path, referred to below as
  `/ABS/BRIDGE_ROOT`.
- An executable from the isolated .NET SDK `9.0.303` for parity gates. The
  optional servicing build uses a separate `9.0.317` executable.
- The explicit absolute path to the pinned arm64 game data directory. It must
  contain these exact regular files:

  - `sts2.dll`, SHA-256
    `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`;
  - `GodotSharp.dll`, SHA-256
    `0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289`.

- Separate, pre-created empty absolute work and output directories for each
  command that requests them.

The scripts perform no default game-install, operator-config, SDK, or output
search. Replace every `/ABS/...` placeholder below with a canonical absolute
path before running a command. Do not pass relative paths, paths containing
`..`, symlinked path components, or a reused non-empty work/output root.

## Repository-local gates

These commands compile against the two pinned assemblies but never launch the
game. Work roots hold isolated CLI state, restore state, build artifacts, and
logs; they must be fresh and empty.

### Test

The test gate requires the exact parity SDK `9.0.303`:

```bash
python3 "/ABS/BRIDGE_ROOT/tools/run_gate.py" test \
  --source-root "/ABS/BRIDGE_ROOT" \
  --dotnet "/ABS/DOTNET_9_0_303" \
  --game-data-dir "/ABS/PINNED_ARM64_DATA" \
  --work-root "/ABS/EMPTY_TEST_WORK_ROOT"
```

### Build

The parity build is the canonical production build:

```bash
python3 "/ABS/BRIDGE_ROOT/tools/run_gate.py" build \
  --source-root "/ABS/BRIDGE_ROOT" \
  --dotnet "/ABS/DOTNET_9_0_303" \
  --sdk-role parity \
  --game-data-dir "/ABS/PINNED_ARM64_DATA" \
  --work-root "/ABS/EMPTY_PARITY_WORK_ROOT" \
  --output-dir "/ABS/EMPTY_PARITY_OUTPUT_DIR"
```

The secondary servicing smoke build is non-canonical and must use SDK
`9.0.317` with different empty roots:

```bash
python3 "/ABS/BRIDGE_ROOT/tools/run_gate.py" build \
  --source-root "/ABS/BRIDGE_ROOT" \
  --dotnet "/ABS/DOTNET_9_0_317" \
  --sdk-role servicing \
  --game-data-dir "/ABS/PINNED_ARM64_DATA" \
  --work-root "/ABS/EMPTY_SERVICING_WORK_ROOT" \
  --output-dir "/ABS/EMPTY_SERVICING_OUTPUT_DIR"
```

The successful build output reports the SDK role/version and SHA-256 of
`Sts2AgentBridge.dll`.

### Forbidden-surface verification

Run the surface gate against the parity-built production DLL and the checked-in
[default-deny policy](contracts/live_probe_v0/forbidden_surface.json):

```bash
python3 "/ABS/BRIDGE_ROOT/tools/run_gate.py" surface \
  --source-root "/ABS/BRIDGE_ROOT" \
  --dotnet "/ABS/DOTNET_9_0_303" \
  --game-data-dir "/ABS/PINNED_ARM64_DATA" \
  --work-root "/ABS/EMPTY_SURFACE_WORK_ROOT" \
  --assembly "/ABS/PARITY_OUTPUT_DIR/Sts2AgentBridge.dll" \
  --policy "/ABS/BRIDGE_ROOT/contracts/live_probe_v0/forbidden_surface.json"
```

This gate checks the production assembly against the frozen source,
dependency, metadata, IL/member, route, and owning-callsite boundary. A passing
surface scan is still only static evidence; it is not evidence that the bridge
was loaded by the game.

`run_gate.py surface` also builds and runs the complete named negative-fixture
catalog. For a later review that needs to rerun only the already-built metadata
verifier against one DLL, use the narrow wrapper below. `VERIFIER_DLL` must be
the `Sts2AgentBridge.Verifier.dll` produced by the reviewed surface build:

```bash
python3 "/ABS/BRIDGE_ROOT/tools/verify_forbidden_surface.py" \
  --dotnet "/ABS/DOTNET_9_0_303" \
  --verifier "/ABS/VERIFIER_DLL" \
  --assembly "/ABS/PARITY_OUTPUT_DIR/Sts2AgentBridge.dll" \
  --policy "/ABS/BRIDGE_ROOT/contracts/live_probe_v0/forbidden_surface.json" \
  --source-root "/ABS/BRIDGE_ROOT"
```

## Canonical package

The canonical archive is `Sts2AgentBridge-0.8.0.zip`. It contains exactly two
stored regular files, in this order:

```text
Sts2AgentBridge/Sts2AgentBridge.dll
Sts2AgentBridge/Sts2AgentBridge.json
```

There are no directory entries, PDBs, PCKs, config files, credentials, game
assemblies, dependency DLLs, sources, install scripts, or removal scripts. The
archive has the frozen timestamp, mode, ordering, and metadata described by the
[package layout contract](contracts/live_probe_v0/package_layout.json).

Build the archive from a parity DLL and the checked-in canonical
[loader manifest](package/Sts2AgentBridge.json):

```bash
python3 "/ABS/BRIDGE_ROOT/tools/build_package.py" \
  --dll "/ABS/PARITY_OUTPUT_DIR/Sts2AgentBridge.dll" \
  --manifest "/ABS/BRIDGE_ROOT/package/Sts2AgentBridge.json" \
  --output "/ABS/DISPOSABLE_PACKAGE_OUTPUT/Sts2AgentBridge-0.8.0.zip"
```

Verify it with the lower-case 64-character hashes reported by the successful
build/package steps:

```bash
python3 "/ABS/BRIDGE_ROOT/tools/verify_package.py" \
  --package "/ABS/DISPOSABLE_PACKAGE_OUTPUT/Sts2AgentBridge-0.8.0.zip" \
  --expected-dll-sha256 3d44887ac8935a1cbe8920e610db4a7d1209556242f555fce524e22c5f77b748 \
  --expected-manifest-sha256 498e815fc742e85112e43823b3b2e291e60efe03353a22e263d316e6fb67b971
```

The hashes above bind the current canonical R0i package inputs.

The package-fixture gate proves that extra JSON, a secondary DLL, a copied game
assembly, traversal, a symbolic-link entry, compression, and an archive comment
are each rejected for their specific reason:

```bash
python3 "/ABS/BRIDGE_ROOT/tools/verify_package_fixtures.py" \
  --canonical-package "/ABS/DISPOSABLE_PACKAGE_OUTPUT/Sts2AgentBridge-0.8.0.zip" \
  --work-root "/ABS/EMPTY_PACKAGE_FIXTURE_WORK_ROOT"
```

### Reproducibility

This gate copies the bridge source into two distinct roots, independently
builds and packages both copies with SDK `9.0.303`, and requires byte-identical
DLL, manifest, and ZIP outputs:

```bash
python3 "/ABS/BRIDGE_ROOT/tools/verify_reproducible.py" \
  --source-root "/ABS/BRIDGE_ROOT" \
  --dotnet "/ABS/DOTNET_9_0_303" \
  --game-data-dir "/ABS/PINNED_ARM64_DATA" \
  --work-root-a "/ABS/EMPTY_REPRO_WORK_ROOT_A" \
  --work-root-b "/ABS/EMPTY_REPRO_WORK_ROOT_B" \
  --output-dir "/ABS/EMPTY_REPRO_OUTPUT_DIR"
```

The source root, pinned game-data directory, both work roots, and output root
must be mutually non-overlapping. On success the output directory contains the
verified DLL, manifest, and canonical ZIP.

The install-free `R0i` candidate currently binds these exact outputs:

- DLL: `3d44887ac8935a1cbe8920e610db4a7d1209556242f555fce524e22c5f77b748`;
- manifest: `498e815fc742e85112e43823b3b2e291e60efe03353a22e263d316e6fb67b971`;
- canonical ZIP: `dfc4a85877aa9488584ee116959657dc114ccc3f458ee0c44b0a6e725799b385`.

See the
[implementation evidence](../../docs/research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md)
for the full gate record and the discarded earlier candidate.

## Operational-boundary tools reserved for an approved checkpoint

The verifiers and runtime guard below are read-only. The `probe_live.py` client
only observes; `apply_one_live.py` preserves the earlier single-card smoke and
`apply_turn_live.py` preserves the bounded one-turn loop. `apply_combat_live.py`
performs the bounded complete-combat loop. `apply_reward_live.py` resolves the
supported reward choices, `apply_map_live.py` selects one legal map node,
`apply_room_live.py` handles the bounded room slice, and `apply_run_live.py`
composes up to three combat floors for `R0i`. The campaign
manager documented later is the only tool allowed to generate, activate,
quarantine, or purge project-owned live material. None of these tools launches
the game. Under repository-local authorization alone, do not point them at the
live Steam installation or real operator configuration and do not invoke the
manager against production paths.

Any pre-authorization validation of these boundaries must use synthetic,
disposable fixtures containing no user, profile, Cloud, credential, or live
installation data. The operator-config verifier deliberately binds to the
effective macOS user's fixed home path, so its real command should not be run
as a temporary-directory rehearsal; use the package-free test harness for
synthetic coverage instead.

### Frozen campaign-input verifier

`verify_live_campaign_inputs.py` is the standalone bootstrap for a separately
approved campaign. It runs with isolated standard-library imports, accepts
only its expected own hash and approved-request hash, and then verifies the
frozen repository tools/documents, accepted artifact set, command shell, and
the exact Apple Python launcher/runtime chain. It accepts no path or manifest
override and emits only a fixed input-set identifier and aggregate count.

Before live approval, exercise only its disposable fixture suite:

```bash
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/verify_live_campaign_inputs_fixtures.py"
```

The fixture suite covers stable byte checks, path/link boundaries, the exact
two-hop Python runtime chain, shell startup-option rejection, CLI closure,
sanitized failures, and isolated-import behavior. The final bootstrap and
request hashes belong in the exact live-campaign request, not in this general
README.

### Durable campaign manager

`manage_live_campaign.py` is the only operational tool allowed to create,
activate, quarantine, or purge the preliminary campaign's generated material.
It has exactly three modes: `install`, `quarantine`, and `purge`. Installation
stages a protected operator unit and bridge unit below the fixed persistent
Application Support state root, records their filesystem identities in a
canonical durable state, then
moves operator configuration first and code second with exclusive
same-filesystem renames. Quarantine reverses exposure in the safer order—code
first, operator unit second. Purge is allowed only from the exact quarantined
state and removes only the recorded allowlisted descendants.

Hard interruption is intentionally fail-closed. A partially advanced state is
retained for separately reviewed recovery; the manager never guesses, repairs,
overwrites, resumes, or rolls back a published transition. Installation emits
a canonical state SHA-256 that quarantine must receive externally; quarantine
emits the hash that purge must receive. Every atomic update also requires the
complete predecessor, so a self-consistent replacement state is rejected both
between and during invocations. Its disposable
fixture suite covers both new and pre-existing `mods` parents, all published
fault checkpoints, inode/state replacement, foreign objects, ACL/mode/link
failures, exclusive moves, credential-buffer zeroing, and sanitized output:

```bash
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/manage_live_campaign_fixtures.py"
```

All 34 lifecycle, fault-retention, state-lineage, and fail-closed checks pass. Production mode
is reserved for the exact hash-bound live request; this README does not grant
permission to invoke it.

### Sanitized live client

`probe_live.py` is reserved for the separately approved live campaign. It
accepts no host, port, route, credential, or arbitrary-path override. It binds
the effective macOS identity to the supplied OS home, reads only the fixed
protected `r0a/credential.hex`, connects only to literal
`127.0.0.1:43117`, and validates health, compatible manifest, and one expected
public screen or combat decision byte-canonically. Its output contains no credential,
token-derived value, raw body, correlation ID, or absolute path.

After the exact campaign is approved and the operator boundary passes, invoke
it as:

```bash
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/probe_live.py" \
  --user-profile "/ABS/OS_USER_PROFILE" \
  --effective-uid 501 \
  --expected-screen main_menu
```

Use `--expected-screen settings` only while the visible Settings screen is
open, or `--expected-screen combat` for read-only combat observation. The
complete-combat client accepts the same named, replaceable decision-provider
seam as the one-turn client:

```bash
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/apply_combat_live.py" \
  --user-profile "/ABS/OS_USER_PROFILE" \
  --effective-uid 501 \
  --decision-provider heuristic
```

The batched controller exposes each provider explicitly:

```bash
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/apply_run_live.py" \
  --user-profile "/ABS/OS_USER_PROFILE" \
  --effective-uid 501 \
  --combat-provider heuristic \
  --reward-provider first-card \
  --map-provider coverage \
  --floor-limit 3
```

Replace `501` with the separately established effective UID. Before live
approval, run only its in-memory disposable fixture suite:

```bash
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/probe_live_fixtures.py"
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/apply_turn_live_fixtures.py"
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/apply_combat_live_fixtures.py"
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/apply_floor_live_fixtures.py"
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/apply_reward_live_fixtures.py"
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/apply_room_live_fixtures.py"
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/apply_run_live_fixtures.py"
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/decision_providers_fixtures.py"
```

The fixture suites cover read-only probing, both decision-provider choices,
one complete turn, bounded victory and defeat, the waiting interval during
enemy actions, false-terminal rejection, and fail-closed
rejection without reading the real operator path or opening a real network
connection.

### Runtime process/port guard

`check_live_runtime.py` binds the supplied UID/home to the fixed game
executable and literal `127.0.0.1:43117`. It exposes only
`require-running`, `sample-base-port-closed`, `require-stopped`, and
`wait-stopped`. Running checks require an anchored executable argument-list
indicator; a name-only match is ambiguous and fails closed. Stopped checks use
absolute deadlines and two consecutive port-refused/process-absent joint
samples. These remain point observations, not atomic or continuous monitoring.

The separately approved campaign invokes one fixed mode as:

```bash
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/check_live_runtime.py" \
  --mode require-stopped \
  --user-profile "/ABS/OS_USER_PROFILE" \
  --effective-uid 501
```

Before live approval, exercise only the disposable fixture suite:

```bash
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/check_live_runtime_fixtures.py"
```

The guard and fixture SHA-256 values are respectively
`43ab6f1375486336dffd6343265ed7605c15ba4612f23cfc97086d03a9b91ccc`
and `64cab3009a98ee1c86441b20ee81bbce1daf35cd445f3b6e89816654f01c13ad`.
All 17 process, identity, deadline, restart-race, CLI, and disposable-loopback
fixtures pass. Exact process evidence is not a native executable-vnode query,
and a process can still start immediately after a passing check.

### Clean-install projection

The target is the pinned
[game-build manifest](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
Base mode accepts no package:

```bash
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/verify_clean_install.py" \
  --install-root "/ABS/AUTHORIZED_INSTALL_PROJECTION_ROOT" \
  --target-manifest "/ABS/REPO_ROOT/manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json" \
  --mode base
```

Overlay mode additionally requires the exact canonical ZIP:

```bash
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/verify_clean_install.py" \
  --install-root "/ABS/AUTHORIZED_INSTALL_PROJECTION_ROOT" \
  --target-manifest "/ABS/REPO_ROOT/manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json" \
  --mode overlay \
  --package "/ABS/AUTHORIZED_ARTIFACT_ROOT/Sts2AgentBridge-0.8.0.zip"
```

The verifier rejects symlinks and special files, hashes every regular file in
the supplied root, and requires the frozen clean projection of 429 files. In
overlay mode it excludes only the exact bridge DLL/manifest pair after proving
that they match the ZIP and that their subtree contains nothing else. Its
successful output never prints the installation path.

### Operator configuration

The verifier requires the exact fixed root
`<user-profile>/Library/Application Support/Sts2AgentBridge/r0a`, the actual
effective macOS user identity, and one of the two frozen config hashes:

- enabled: `f8c6ff9592fa330cc9317cd63200c9ee5b0f8023c23efc328f04eea57d6dffea`;
- disabled: `132f4c49ee499a52b43d2f0d66edcba1bd78bd5b49777c270636246d85cd3b52`.

After separate authorization, its exact invocation is:

```bash
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/verify_operator_config.py" \
  --user-profile "/ABS/OS_USER_PROFILE" \
  --config-root "/ABS/OS_USER_PROFILE/Library/Application Support/Sts2AgentBridge/r0a" \
  --expected-config-sha256 f8c6ff9592fa330cc9317cd63200c9ee5b0f8023c23efc328f04eea57d6dffea \
  --effective-uid 501
```

Replace `501` with the separately established decimal effective UID and select
the hash matching the authorized enabled/disabled config. The verifier checks
identity before config-path access, then checks containment, ownership, modes,
ACLs, link counts, exact config bytes, and credential shape. It never emits or
hashes the credential and never repairs a failed condition.

## Tool results and exit codes

A successful tool emits one compact JSON line. Treat the process exit code as
authoritative:

| Code | Meaning |
| ---: | --- |
| `0` | Verification passed |
| `2` | Invalid invocation |
| `3` | Unsafe path or boundary |
| `4` | Verification mismatch |
| `5` | Internal tool failure |

A nonzero result is fail-closed. Do not reinterpret it as a partial pass, and
do not widen a path, disable a check, repair live state, or substitute an
unreviewed artifact to make the command pass.
