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
same boundary with granular gold/card reward handling, a separate bounded
rest-site and standard-event controller, and a combat/reward/map/room runner
capped at three completed combats under replaceable host decision providers.
The runner reconciles a supported room preflight, bounded room interaction,
return to map, and—when the next destination is a monster or elite—one next-
combat continuation. Unsupported or inconsistent handoffs fail closed.
The Python runner now treats advertised `elite` destinations as combat through
the same clients. Independent actual-client fixtures cover default, prefix and
post-room continuation, defeat, uncertainty and cleanup; elite remains
unobserved live. The C# assembly and wire are unchanged. Exact acceptance is in
the [actor-ready ledger](../../docs/research/PHASE_1_ACTOR_READY_ACCEPTANCE.md).

The controlling contract is the accepted
[Phase 1 BR0 preflight freeze](../../docs/PHASE_1_BR0_PREFLIGHT.md). The broader
boundary and rationale are in the
[restricted bridge design](../../docs/PHASE_1_RESTRICTED_BRIDGE_DESIGN.md).

## Separate item release

The separately scoped [item bootstrap candidate](../../docs/PHASE_1_ITEM_V1_BOOTSTRAP_PLAN.md)
now compiles as one `Sts2AgentBridgeItemV1.dll` from four frozen successor trees.
Its secure operator loader passes 13 fixture groups and its first-frame
lifecycle passes 24, with two byte-identical source-snapshot builds. The
[item release](../../docs/PHASE_1_ITEM_V1_RELEASE_PLAN.md) now has an accepted
whole-assembly policy, canonical two-entry package and item-aware fixed client,
transactional installer and cleanup tools. Separate user-confirmed potion-only
and relic-only Loot rewards now each live-pass exactly one
attempted/accepted/reconciled collection, with complete cleanup. Parent room
completion and relic hook fidelity remain unpromoted. The existing 0.8.0
instructions below cannot install or activate it. Exact candidate hashes and reproduction
commands are in the [acceptance ledger](../../docs/research/PHASE_1_MISSING_ROOM_ACCEPTANCE.md).

For a live item test, prepare the separate **Loot!** reward list after combat
(an elite fight can supply a relic). Leave only untouched potion/relic rows;
collect gold and handle card rewards manually first. A potion needs an empty
slot. The chest **What’s Inside?** screen, Neow’s starting choices and shop
inventory are different surfaces and are not supported by this adapter.

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
keeps separate combat, reward, map, and safe-room provider seams. It does not
read profiles, saves, progress, preferences, history, replay, seeds, or
multiplayer identity. It does not use
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
combat, granular card/gold rewards, map selection, one direct safe event-to-map
transition, two consecutive composed combat/reward/map handoffs, and standalone
rest-site completion with inspection-map stale-action rejection. A later
campaign also live-demonstrated explicit fresh reward entry through reward
resolution, one reconciled map selection and terminal combat defeat, with
truthful partial-prefix accounting. Explicit map entry, the full
three-combat-floor cap and a reconciled batched room handoff remain unaccepted
live. The Python
preflight now polls validated
inactive `complete` responses within its existing deadline; only a validated
expected-kind `ready` response succeeds. Cross-kind residue is fixture-tested.

The earlier 2026-09-04 campaign reproduced multi-step event timeout and
demonstrated rest-site map selection, preflight, healing, and map opening, but
rest completion also timed out. Underlying room controls can persist while the
map is foreground; room observations then remained ready for the prior event
or waiting for rest. No behind-map action was attempted in that campaign. Do
not interpret map opening alone as completed room acceptance, reset replay
guards, or retry an ambiguous action. A scoped C# lifecycle/foreground-surface
repair is a separate
decision from the accepted Python preflight. Normal teardown, bridge removal,
clean base-game launch/quit, and final purge all passed. See the living status
page and its acceptance record for the exact evidence boundary.

The subsequently approved C# repair is integrated: foreground maps/travel
suppress room actions, immediate revalidation rejects stale dispatch, and only
accepted same-room literal rest `proceed` plus a travel-ready map proves
completion. A bounded numeric identity registry preserves replay identity
across missing surfaces and revisits. Event-to-map completion remains fail-closed.
The new artifact passed all repository gates. After an unlaunched locked-desktop
attempt was fully cleaned up, the resumed campaign live-accepted the rest-site
slice: an inspection map suppressed candidates and one original snapshot-bound
action was rejected as stale with no mutation reported; heal and literal Proceed
then completed through the bounded controller. Closing the completed map left
the room projection non-actionable. Event suppression and the wider identity-
registry cases remain fixture-only; multi-step event completion and a complete
batched room handoff were not demonstrated. Normal quit, exact removal, clean
base-game launch/quit with the bridge port closed, and final purge all passed.

The next-increment Python join now carries `(screen_kind, room_ordinal)` from
run preflight into the room client and checks every ready decision before POST.
The real-client wire transcript covers the positive handoff, room replacement,
transport failures and captured-output privacy checks without live I/O.
`verify_room_acceptance.py` provides a one-shot inspection-map stale-rejection
helper with an explicitly bounded/cooperative acknowledgement hook. Its room
summary validates complete producer output; its run count summary is deliberately
labelled `run_result_unvalidated`, not a certificate of full run history.

The maintained `apply_run_acceptance_live.py` entry point now validates both
complete bounded-run result forms in memory and emits only fixed aggregate
counts, entry/source milestones, termination and terminal-combat outcome. It
delegates the existing 14/16 arguments to `apply_run_live.py` in process. It
checks component fields, provider reconciliation, retained reward facts,
combat/reward health, destination sequencing, cap/handoff relationships and
action arithmetic. Malformed results return `run_acceptance_result_mismatch`;
known production failures pass through a finite allowlist, while unexpected
callback or cleanup failures return a fixed code. There is no capture flag.
Independent actual-client fixtures and whole-bridge review are accepted at
`847882f`. The first authorized
attempt stopped before installation when Steam inspection stalled beyond the
30-minute campaign limit. The base remained unchanged with zero overlay and
no game process or bridge listener. A bounded infrastructure retry opened Steam
but repeatedly failed screen capture (`-3811`), including after session reset.
Game-window capture subsequently worked after a manual launch, and Profile 3
was visibly confirmed. The helper was then invoked **once** from a fresh map
with first-legal/first-card/elite/safe providers and floor limit three. It
returned only `room_interaction_timeout` (exit 4), with **no accepted run
summary**. Exact phase/action counts and a successful map/elite/room chain are
not certified. No retry occurred. Normal quit, exact quarantine, clean unmodded
launch/quit, four-file purge and final unchanged-base/zero-overlay/process/
listener checks all passed. The campaign ended within 30 minutes; no campaign
is active. See the actor-ready ledger for its exact result and evidence limits.

A later capture-off `diagnose_run_room_live.py` campaign passed explicit fresh
map entry: three destinations, two completed floors and 54 actions. Its room
record was `not_entered` with zero room actions, so it did not test the unresolved
room timeout. The user selected a fresh untouched question-mark event as the
next direct target. Normal quit, quarantine/four-file purge and stopped/base
checks passed; the user explicitly waived the repeated unmodded launch/quit
check. Future repeated cleanup uses that revised procedure, recording the
omitted check as waived. Exact evidence is in the actor-ready ledger.

Its isolated synthetic gate is:

```bash
/ABS/PYTHON_3_10_PLUS -B -E -s -S /ABS/BRIDGE_ROOT/tools/apply_run_acceptance_live_fixtures.py
```

The separate offline room-timeout gate exercises the actual Python room
client through synthetic sockets and a deterministic clock. It covers the
shared deadline before and after accepted room actions, delayed completion,
replay/identity guards and fixed acceptance-wrapper failure propagation. A
`room_interaction_timeout` does not identify which action or waiting stage was
reached. The canonical waiting body contains no such reason, and D47 still
withholds event-to-map completion. These fixtures neither reconstruct a live
run nor change the production deadline or completion rules:

```bash
/ABS/PYTHON_3_10_PLUS -B -E -s -S /ABS/BRIDGE_ROOT/tools/apply_room_timeout_fixtures.py
```

An earlier bounded Profile 3 campaign live-passed the separate
`verify_room_acceptance.py` helper and the new
context-bound rest heal/proceed/map completion. The next connected route was an
elite, so full ordinary-combat continuation and an eligible gold comparison
remain unobserved. No map destination was selected. Exact cleanup and another
clean base-game launch/quit passed. See the
[next-increment ledger](../../docs/research/PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md).

`compare_reward_gold_live.py` is a separate capture-off, one-claim gold
comparison consumer. It uses the canonical production-rule evaluator and
returns only fixed field verdicts, eligibility/correspondence, omissions and
reviewed code/spec identities. It cannot retain a named case or grant fidelity
admission. Unexpected reward-list changes, removed/reindexed selected rewards,
unstable post-state and uncertain correspondence remain unobserved; player
scalar differences are preserved as divergent findings, not normalized away.
Its 33 mocked checks include whole-CLI stdout/stderr capture, deliberate leak
mutations, receipt/transport failures, cancellation and cleanup. It has **not**
been exercised on an eligible live gold boundary.

The follow-up campaign at clean `300d230` exercised the adapter's
`unsupported_gold_amount` path live: zero claim POSTs, all five findings
unobserved, no admission. The ordinary reward controller subsequently stopped
at `reward_action_response_mismatch`, with no retry. This code covers both
receipt mismatch/rejection and HTTP/backend failure; neither the failed action
nor its mutation outcome was retained. The vanished modal does not prove
accepted Proceed. Full composed acceptance remains open. Final cleanup, clean
base-game launch/quit, zero installed overlay and closed listener passed; the
ledger also records recovery from premature quarantine before Quit confirmation.

Use a Python 3.10+ interpreter for this package-backed tool. Its isolated fixture
command requires no optional RL packages or editable installation:

```bash
/ABS/PYTHON_3_10_PLUS -B -E -s -S "/ABS/BRIDGE_ROOT/tools/compare_reward_gold_live_fixtures.py"
```

The corresponding live form is `compare_reward_gold_live.py --transient-check
--user-profile /ABS/OS_USER_PROFILE --effective-uid 501`, under coordinator
campaign authority with the same exact installed artifact checks. Do not invoke
it merely to inspect state: an eligible boundary permits one claim POST.
There is no capture/output-directory switch. The existing `game.analysis`
namespace can attempt optional imports in a normal interpreter; `-S` isolation
passes without those packages. This is not the stricter no-import-attempt
guarantee tested for `sts-headless --help`.

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
  --expected-dll-sha256 a586aa99b9deeeb04b22596340dcccd0c6894b59db27625dfa1a1a8c2508c285 \
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

- DLL: `a586aa99b9deeeb04b22596340dcccd0c6894b59db27625dfa1a1a8c2508c285`;
- manifest: `498e815fc742e85112e43823b3b2e291e60efe03353a22e263d316e6fb67b971`;
- canonical ZIP: `c97f3a0cd094523c769065fc921c3758569575c8dd5e754c5d2597ab7ee5a595`.

See the
[2026-09-04 acceptance record](../../docs/research/PHASE_1_2026_09_04_ACCEPTANCE.md)
for the reviewed lifecycle repair and its exact gates. Earlier candidates remain
in the historical implementation evidence and are not the current package.

## Operational-boundary tools reserved for an approved checkpoint

The verifiers and runtime guard below are read-only. The `probe_live.py` client
only observes; `apply_one_live.py` preserves the earlier single-card smoke and
`apply_turn_live.py` preserves the bounded one-turn loop. `apply_combat_live.py`
performs the bounded complete-combat loop. `apply_reward_live.py` resolves the
supported reward choices, `apply_map_live.py` selects one legal map node,
`apply_room_live.py` handles the separate bounded room slice, and
`apply_run_live.py` composes combat, reward, map, and supported-room handoffs
over up to three reconciled map selections for `R0i`. By default it begins at
combat. An explicit fresh-boundary entry may instead begin at a currently
visible reward or map decision; this is not recovery, phase detection, or
continuation after an uncertain request. The campaign
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
  --room-provider safe \
  --floor-limit 3
```

The opt-in `elite` map provider ranks elite, rest site, monster and ancient,
then other advertised choices with the existing deterministic tie-break.
Existing `first`, `combat` and `coverage` providers retain their behavior.
Normal/prefix selection of the final allowed destination returns before its
combat. A supported room's post-room selection still runs its one continuation
combat when that selection consumes the final slot, then returns before reward.

Omission of `--entry-phase` and explicit `--entry-phase combat` have the same
combat-entry behavior and exact `r0i_bounded_run` success JSON. To start only
when the named fresh phase is already visible, append exactly one of:

```text
--entry-phase reward
--entry-phase map
```

The selected phase's existing client performs the first validation directly;
the runner does not scan another phase, auto-detect, fall back, retry, or adopt
an earlier action. Reward entry runs reward, waits for map readiness, and then
runs map. Map entry runs map directly. Waiting, cached/complete, unsupported,
malformed, mismatched, uncertain, or unreconciled entry state stops fail-closed.

Reward/map success uses milestone `r0i_bounded_run_entry`. Its `entry_prefix`
is logical floor 1 and records exactly the destination, ordered observed and
unavailable phases, nullable combat/reward/map component records, and the
existing three readiness counters. Direct entry attempts are zero; only the
reward-to-map readiness wait records attempts. `floors` contains only complete
combat/reward/map triples and begins at logical floor 2. Consequently
`completed_floor_count` excludes the prefix, while `processed_floor_count`
counts every accepted-and-reconciled map selection, including the prefix and a
post-room selection. That count never exceeds `floor_limit`, whose maximum
remains three. Unavailable phases remain `null`; the host summary does not
infer their outcome, continuity, action, or state.

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
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/apply_run_wire_fixtures.py"
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/apply_run_entry_wire_fixtures.py"
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/verify_room_acceptance_fixtures.py"
/usr/bin/python3 -B -E -s -S "/ABS/BRIDGE_ROOT/tools/decision_providers_fixtures.py"
```

The fixture suites cover read-only probing, both decision-provider choices,
one complete turn, bounded victory and defeat, the waiting interval during
enemy actions, false-terminal rejection, and fail-closed
rejection without reading the real operator path or opening a real network
connection.

### Capture-off reward diagnostics

`diagnose_reward_live.py` is an explicitly selected diagnostic form of the
existing bounded reward controller. It **can apply reward actions**; do not run
it merely to inspect state or retry an uncertain action. Use it only inside a
coordinator-controlled campaign after the exact artifact and live boundary
checks pass:

```bash
/ABS/PYTHON_3_10_PLUS -B -E -s -S "/ABS/BRIDGE_ROOT/tools/diagnose_reward_live.py" \
  --user-profile "/ABS/OS_USER_PROFILE" \
  --effective-uid 501 \
  --decision-provider first-card
```

It uses the ordinary reward controller's providers, deadlines, 17-action cap,
exact receipt acceptance and post-state reconciliation. It adds no retries or
network reads. The default reward CLI and its success/error contract remain
unchanged.

The diagnostic emits one compact schema-version-1 record for success, handled
failures and keyboard interruption, preserving `ToolFailure` exit codes.
Output contains only fixed
status/code, action category, failure stage and classification, three counters,
and an optional receipt projection. Unlisted source failure codes become the
fixed code `failure`; exception text is never emitted. The counter invariant is
`0 <= reconciled <= accepted <= attempted <= 17`:

- `attempted`: action exchanges entered, not proof of delivery or application;
- `accepted`: receipts passing the original exact acceptance and binding check;
- `reconciled`: actions whose subsequent state passed reconciliation.

The receipt projection has only validated status/reason/mutation enums and
nullable decision/action binding-match booleans. These are receipt facts, not
proof of the actual mutation outcome of an unbound or uncertain request.
Classifications distinguish canonical 429, retryable 503 and nonretryable 500,
malformed envelopes, transport failures, rejected/malformed receipts and
reconciliation failures. No raw bodies, body hashes, control IDs, credentials,
player scalars or full reward results are emitted, and no capture/output path
is accepted. The previous campaign's discarded response remains unclassified.

The host-side probe and room clients now share one private bounded
send/receive/cleanup implementation while retaining their existing `_exchange`
entry points, route-specific request builders, exact errors, deadlines, caps and
no-retry behavior. This removes the duplicated receive loop and carries the
probe's exceptional-exit mutable-response wiping to room calls. The independent
`bounded_transport_fixtures.py` gate exercises both actual entry points through
29 synthetic request, bound, timeout, cancellation and close-precedence cases.
It is bridge-fixture evidence only; no DLL, package or wire contract changed.

Run the isolated, wholly synthetic CLI/transport acceptance suite without a
game, operator configuration or socket connection:

```bash
/ABS/PYTHON_3_10_PLUS -B -E -s -S "/ABS/BRIDGE_ROOT/tools/reward_action_diagnostics_fixtures.py"
```

The diagnostic schema is not a wire, headless-state, training or replay schema.
See [D49](../../DECISIONS.md#d49-separate-reward-attempts-receipt-acceptance-and-reconciliation)
and the [acceptance ledger](../../docs/research/PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md)
for evidence and exact reviewed source identities. Its fixtures are not live
demonstration.

### Capture-off run/room diagnostics

`diagnose_run_room_live.py` executes the existing bounded run once and emits a
separate fixed room-stage diagnostic. It applies the same game actions as the
run controller and uses its exact 14/16 arguments. Within an authorized campaign,
a visibly fresh map entry uses:

```bash
/ABS/PYTHON_3_10_PLUS -B -E -s -S "/ABS/BRIDGE_ROOT/tools/diagnose_run_room_live.py" \
  --user-profile "/ABS/OS_USER_PROFILE" --effective-uid 501 \
  --combat-provider first-legal --reward-provider first-card \
  --map-provider elite --room-provider safe --floor-limit 3 --entry-phase map
```

The top-level record contains exactly `schema_version`, `status`, `milestone`,
`code`, `room` and `run_acceptance`. The room record contains the final host
stage, last successfully validated observation status and ready room kind,
exchange-attempt and accepted-receipt counts, last fixed action categories, and
confirmed-completion boolean. Counts are bounded by the existing 12-action cap.
Entering an exchange does not prove delivery or application; acceptance requires
the original exact receipt validator, and completion requires the original
same-room checks. The last ready kind survives waiting and may change on a
later validated wrong-kind body before the existing mismatch rejection.

For example, a timeout at `room_waiting` with zero attempts differs from waiting
after an accepted `rest_heal`, `rest_proceed` or `event_choice`. A timeout at
`manifest_read` may mean setup consumed the shared deadline before any room
read. A failure at `action_exchange` may have an unaccepted attempt. These are
host-stage facts; they do not identify the C# reason behind canonical waiting.

Success includes the unchanged strictly validated run acceptance aggregate only
when its room action count agrees with the diagnostic. Failure always has
`run_acceptance=null`. Unknown exceptions use existing `internal_failure`;
cancellation uses `interrupted`. Unsafe diagnostic state or result cleanup
supersedes either outcome with `internal_failure` and both records null.
Nested output is discarded through a non-retaining sink. No raw responses,
identifiers, arbitrary text, timing, poll count, action history or capture path
are retained. Existing CLI outputs, wire, package, deadlines, providers, request
order, replay rules and completion semantics remain unchanged.

Run the synthetic gates without game or operator access:

```bash
/ABS/PYTHON_3_10_PLUS -B -E -s -S "/ABS/BRIDGE_ROOT/tools/room_stage_diagnostics_fixtures.py"
/ABS/PYTHON_3_10_PLUS -B -E -s -S "/ABS/BRIDGE_ROOT/tools/diagnose_run_room_wire_fixtures.py"
```

The unit gate has six grouped checks. The independent 25-case gate exercises
literal actual-client requests, failure stages, receipt accounting, cancellation,
cleanup, exact acceptance parity with and without a room, and deliberate request,
count, category and output-suppression mutations. Evidence is `bridge_fixture`;
no new live room completion or historical timeout root cause is claimed. See
[D56](../../DECISIONS.md#d56-keep-room-stage-diagnostics-separate-from-run-acceptance),
the [frozen diagnostic plan](../../docs/PHASE_1_ROOM_STAGE_DIAGNOSTIC_PLAN.md),
and the [actor-ready ledger](../../docs/research/PHASE_1_ACTOR_READY_ACCEPTANCE.md).

### Direct untouched-room diagnostics

`diagnose_room_live.py` enters the existing room controller directly, with no
map, combat or reward continuation. Its intended targeted setup is Profile 3,
Ironclad, Ascension 0, inside a fresh event reached through a question-mark node,
with choices visible and no choice selected. The user may navigate to this exact
state after campaign staging; that navigation is outside controller evidence.
Verify that the question-mark node actually became an event before invoking:

```bash
/ABS/PYTHON_3_10_PLUS -B -E -s -S "/ABS/BRIDGE_ROOT/tools/diagnose_room_live.py" \
  --user-profile "/ABS/OS_USER_PROFILE" --effective-uid 501 \
  --decision-provider safe
```

This applies room choices once under the existing 30-second deadline and
12-action cap. It emits exactly `schema_version`, `status`, `milestone`, `code`
and `room`, with milestone `r0i_room_diagnostic`. The room record is identical
to the run diagnostic's fixed stage/count record. Success requires the existing
full room-result verifier plus matching complete/count/kind facts; its internal
acceptance summary is discarded. No route/poll count, partial result or new
capture path is emitted. Default room and run commands remain unchanged.

A user-prepared fresh event has now exercised this command live: one entered
`event_choice` exchange and accepted receipt, followed by
`room_state_unsupported` at `room_validation`; completion stayed false. A visible
loot overlay was consistent with the generic nested-overlay guard, but the
aggregate does not identify that cause. No collect/skip or retry followed.
The direct fixture now has 11 grouped categories, including that authored
accepted-event/unsupported boundary.

Event observation reads option-button indices, public text keys and flags. It
does not expose full option descriptions or structured costs/effects. The
`safe` event selector chooses the first eligible non-lethal option and does not
predict or guarantee that its resulting surface is supported.

The direct wrapper preserves the room parser's exact `invalid_decision_provider`
/exit-2 pair locally; all other failures follow the frozen run-diagnostic helper.
Unknown errors, cancellation, unsafe-state/cleanup precedence and non-retaining
output suppression retain the same strict behavior. Stop when the controller
returns; do not manually continue or retry an uncertain action.

The synthetic direct gate exercises the actual CLI/room client with literal
transport fixtures, including accepted-event waiting, zero-action waiting,
receipt failures, strict completion, default parity, argument rejection,
cancellation, hostile exceptions, cleanup precedence and an output-sink mutation:

```bash
/ABS/PYTHON_3_10_PLUS -B -E -s -S "/ABS/BRIDGE_ROOT/tools/diagnose_room_live_fixtures.py"
```

See the [direct-room contract](../../docs/PHASE_1_DIRECT_ROOM_DIAGNOSTIC_PLAN.md)
and [actor-ready ledger](../../docs/research/PHASE_1_ACTOR_READY_ACCEPTANCE.md)
for exact acceptance and any later live result. The user's current cleanup
instruction keeps normal quit, exact quarantine/purge and stopped/closed/base
verification, while waiving repeated unmodded launch/quit checks. Record the
waiver explicitly; do not claim that omitted check passed.

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


The corrective [shop map permission release](successors/shop_map_permission_v1/README.md)
is independently accepted offline. It replaces exactly three pre-leave shop
permission checks while preserving leave/event behavior and all eight earlier
successors. Its [acceptance ledger](../../docs/research/PHASE_1_SHOP_MAP_PERMISSION_V1_ACCEPTANCE.md)
owns exact source/package identities and the accepted single-card shop live
test:3 actions attempted/accepted/reconciled, followed by complete cleanup.

The same accepted package subsequently passed a fresh event-selected test on
Dense Vegetation: ordinary choice→follow-up→Proceed→map, 2 parent accepts and 1
correlated final handoff. Event item rewards and longer choice chains remain
unobserved live. See the [event ledger](../../docs/research/PHASE_1_EVENT_CONTINUATION_LIVE_ACCEPTANCE.md)
for exact counters and completed cleanup; no campaign remains active.
