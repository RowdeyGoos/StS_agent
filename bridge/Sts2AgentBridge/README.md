# Live bridge

One production mod, **Sts2AgentBridgeUnified**, contains all supported live
capabilities. `apps/bridge/` owns its runtime, client, package and operational
tools. `components/` holds editable capability modules; `src/` retains the shared
public combat/reward/map/room adapters and codecs. The four former feature apps
and the separate original production project are retired.

Read [current status](../../docs/STATUS.md) for evidence and
[live development](../../docs/LIVE_DEVELOPMENT.md) for the working process.

## Runtime and capabilities

| Module | Existing interface |
| --- | --- |
| Core combat, rewards, map, rest/basic rooms | `/probe/v0/health`, `/probe/v0/manifest`, `/probe/v0/public/*` |
| Event combat continuation | `/probe/event-combat-v2/public/decision`; owned child `/probe/event-combat-v2/public/item-decision` and `item-action` |
| Combat discard/exhaust choice | `/probe/combat-choice-v1/public/decision` and `action` |
| Potion/relic collection | `/probe/item-v1/public/item-decision` and `item-action` |
| Shop and standard room flows | `/probe/room-flows-v1/public/decision` and `action` |
| Standalone card selection | `/card-selection-v1/parent`, `parent/action`, `child`, `child/action` |
| Generic events and their children | `/probe/generic-event-v7/public/decision` and `action` |

All routes use one authenticated loopback listener at `127.0.0.1:43117` and one
owner-frame queue. Native feature sessions are created only when their route is
requested. The current session owns its parent and child operations until the
native result reconciles and disposal succeeds; another capability receives
`capability_busy`. The standard event parent retains its item-child route.
Core actions likewise fence unrelated operations until their decision reconciles.

Clean completion releases the module and keeps the host available for the next
capability. An uncertain mutation, failed response delivery or failed cleanup
stops the host. There are no automatic mutation retries. Process-wide limits are
16,384 reads, 512 action reservations and 64 feature sessions, with the existing
stricter limits inside each module.

A core `stale_decision` rejection with `mutation_state: none` permits a fresh
observation: native dispatch did not occur. Once its response is fully sent, its
reservation is released; a fresh selection still revalidates native legality and
consumes the bounded attempt budget. Other rejections remain terminal.

The existing route/body versions remain meaningful protocol contracts. The
manifest reports bridge version `1.0.0` and Harmony support. Internal historical
namespace names do not denote separately installed mods.

Transformation now uses direct native input for every eligible allocated holder.
The test-only card16 restriction is removed; exact holder/model ownership,
native legality, preview membership, deferred input and effect checks remain.
Generic single/multi-upgrade selectors now also accept allocated holders beyond
the viewport, retaining native clickability and exact preview/effect checks.
This does not support cards without allocated holders or certify every selector.
The upgrade extension has a live Sapphire Seed single-upgrade result for
off-screen Defend slot 20 in a 23-card eligible domain; see the
[combined batch](../../docs/evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md).

## Development checks

Use Python 3.10+ and the existing environment. From the repository root:

```bash
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --suite sources
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --component events --suite python
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --component events --suite test \
  --dotnet /ABS/dotnet --game-data-dir /ABS/data_sts2_macos_arm64
```

Select `host`, `core`, `items`, `rooms`, `cards` or `events` for focused behavior
checks. `all` is the default. `sources` checks the complete explicit source graph;
`python` runs the affected Python fixtures; `test` adds affected C# behavior and
producer/client integration. `build` compiles only the one production DLL.
A narrow correction can run its individual existing fixture directly.

List exact check names without an SDK or build, then select only the relevant
checks during development. Repeat `--check` to select more than one:

```bash
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --component events --list-checks
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --component events \
  --check test:components/events/direct_input_tests/DirectTransformInput.Tests.csproj \
  --dotnet /ABS/dotnet --game-data-dir /ABS/data_sts2_macos_arm64
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --component events \
  --check events:host_native --event-group offers \
  --dotnet /ABS/dotnet --game-data-dir /ABS/data_sts2_macos_arm64
```

`--event-group` selects related integration cases; repeat it to combine groups.
The listing includes the available groups. Unknown check names fail before any
check executes. Selected checks build their required fixtures automatically and
record their selection in `result.json`; they do not produce a release manifest.
Selection is explicit, not automatic dependency-impact analysis: include the
affected host, native and shared-router checks for changes crossing those boundaries.

Event integration runs up to four isolated Python workers by default, each still
starting and disposing a fresh C# process for every scenario. Related baseline
and comparison cases remain together. The larger `reward_sets` group is scheduled
as four independent parts; selecting that group still runs all its cases.
When both are selected, the native event regression suite overlaps integration
after their fixtures have been built. This adds one C# test process alongside
the integration workers. Failures stop the peer suite and prevent release output;
logs remain separate for each check. Builds and other check groups stay sequential.
Use `--jobs 1` to disable both kinds of overlap for serial diagnosis, or
`--jobs N` (1–8) to bound integration concurrency. The full event matrix runs when
`--event-group` is omitted. Per-check timings can overlap, so their sum need not
equal the full gate's elapsed time.

The checker pins .NET SDK **9.0.303** and read-only `sts2.dll`, `GodotSharp.dll`
and `0Harmony.dll` identities. It uses no NuGet feeds and isolates outputs under
`/private/tmp/sts-bridge-*`. Native fixtures use inert game objects; target-game
assemblies are not executed. Test loopback listeners may need sandbox permission.

New features extend the shared modules and relevant tests. They do not create
another launcher, listener, operator tree, package, source copy or release gate.
Do not run gameplay checks for documentation-only changes.

## One release

Once behavior is stable, run:

```bash
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --suite release \
  --dotnet /ABS/dotnet --game-data-dir /ABS/data_sts2_macos_arm64
```

The release suite always runs all checks and all event integration groups;
`--check` and `--event-group` are rejected. Use focused checks while correcting a
feature, then one complete gate for its stable release candidate. Parallel
integration changes scheduling, not release coverage or native ownership checks.

This runs the integrated checks, verifies a reproducible production binary, checks
its compiled entry point/dependency surface, compares the results-screen hook and
fixture declaration against pinned game PE metadata, and exercises package mutations and
owned installation/cleanup. It derives `apps/bridge/package/identity.json` from
the candidate once; package and operational tools share that binding.

A successful gate writes `bridge-release.json`, `result.json` and the three
package files into its printed scratch directory. The release manifest binds
exact source/test inputs, toolchain, references, results and binary/package
identities. Retain its printed SHA-256 separately. Failure cannot emit an accepted
release manifest. Keep one [current release record](releases/current/README.md);
Git retains earlier records. Development corrections do not need manual freezing.

To place accepted artifacts in the fixed install-input directory:

```bash
.venv/bin/python -B bridge/Sts2AgentBridge/apps/bridge/package/publish.py \
  --release-manifest /ABS/bridge-release.json --release-sha256 <accepted-hash> \
  --dll /ABS/release-output/package/Sts2AgentBridgeUnified.dll
```

This verifies current release sources and package identity, then creates
`/private/tmp/sts-unified-bridge-release` exclusively. It never overwrites or
adopts an existing directory. It does not install or launch the game.

## Installation, client and cleanup

Within the user's requested live scope, the single operational entry point is:

```bash
.venv/bin/python -B bridge/Sts2AgentBridge/apps/bridge/operations/run.py \
  --release-manifest /ABS/bridge-release.json --release-sha256 <accepted-hash> \
  --mode install
```

It creates only the owned `Sts2AgentBridgeUnified` overlay and the fixed
`Library/Application Support/Sts2AgentBridge/unified/` configuration/credential.
Existing legacy overlays and campaign state are conflicts, not files to adopt or
delete. Native dependencies and the game build remain pinned. Configuration is
fixed; credentials are generated by the owned installer, not hand-entered.

After installation and the user's requested game setup, use one client:

```bash
.venv/bin/python -B bridge/Sts2AgentBridge/apps/bridge/client/run_live.py \
  --release-manifest /ABS/bridge-release.json --release-sha256 <accepted-hash> \
  --expected-state-sha256 <current-owned-state-hash> --capability events
```

Capabilities are `events`, `event-map`, `event-combat-map`, `combat`, `combat-map`, `combat-choice`,
`rewards`, `cards`, `items`, `shop`, `room-event` and `core`.
The feature modes run their bounded controller; `core` observes one `--route` or
submits an advertised action with `--decision` and `--action`. A core accepted
receipt reports acceptance, not completion; reconcile through the corresponding
decision route. Event choices use the replaceable first-legal host provider.
The client verifies release and owned installation before credential access.

Use `--capability combat` for bounded combat with nested discard/exhaust choices,
or `combat-choice` to resolve one such selector. `--choice-policy minimum` confirms
as soon as the native control permits it; the default `first-select` fills the
selection to its maximum. Parent combat and child selection have separate
attempted/accepted/reconciled counts, retained on failure. Supported native
surfaces, protocol semantics and limits are in [combat choices](../../docs/COMBAT_CHOICES.md).
Neow's Fury zero and two-card selection with combat resume passed in the
[September 9 live batch](../../docs/evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md).

Use `--capability combat-map` to finish one combat, resolve its gold/card rewards,
and verify an actionable map with the same client. Defeat stops before rewards.
The default `--reward-policy first-card` claims gold and chooses the first legal
card; `skip-card` uses the native card skip. `--capability rewards` starts directly
at a reward parent and ends after reward Proceed reconciles; it does not perform
an additional map-readiness check. Neither mode selects a map node. Unsupported
uncollected rewards stop the flow rather than being abandoned by Proceed.

The composite result retains `combat`, `rewards` and `map_handoff` summaries plus
its final `stage` and `code`. A failure never erases earlier reconciled actions or
combat chooser results. Reward gold/card totals count only verified transitions.
Reward bounds are 45 seconds, 512 reads, 17 accepted/25 attempted actions and eight
known no-mutation stale rejections. Existing combat and map bounds also apply.
Both reward policies have shared-socket coverage and completed live from combat
through verified reward effects to an actionable map in that batch.

The shared client spaces exchanges by at least 60 ms, below the listener's
20-per-second authenticated allowance. Pacing consumes the existing exchange
budget; an expired wait or connection cannot send a request. Server rate limits
remain unchanged and rate-limited/uncertain requests are never retried.

Use `--capability event-map` to verify an event-to-map handoff. After an event
resolved with destination `map_handoff` it polls `/probe/v0/public/map-decision` within a five-second
window and 100-read cap, accepting only a validated actionable map. An in-flight
exchange can extend elapsed time by its existing two-second transport limit;
responses arriving after the polling deadline cannot pass. It selects no map node.
Only a `waiting` map response permits another read; errors, unsupported responses,
uncertainty or interruption stop the check. The result retains the full `event`
summary and a separate `map_handoff` status/read count even when that check fails.
A failed event or `combat_handoff` destination never starts the map check.

The checkout also supports `--capability event-combat-map` for a non-resuming
fight started by an owned event choice with no event-supplied extra rewards. It
requires `combat_handoff`, then uses the existing combat/rewards/map controllers.
The result preserves `event` and `combat_flow`; the latter retains each downstream
stage. `--choice-policy` and `--reward-policy` have the same meaning as in
`combat-map`. The default event policy chooses the first legal option: for the
pending Dense Vegetation live case, prepare its Fight page after Rest. Returning
to an event after combat is also supported in the checkout when its exact resume
callback completes, including an owned potion/relic reward or ordered item set.
For `combat_resume_handoff`,
the host verifies the original callback and new event node, then runs one fresh
event session through Proceed/map. Training expiry is reported as `event_resumed`,
not victory. Item collection counts/results are retained in `combat.resume_items`.
Its result retains `combat`, `resumed_event` and `map_handoff` inside
`combat_flow`. Resume-time card rewards, nested pickup selectors and extra combat
rewards remain unsupported.

Use `--event-option BATTLEWORN_DUMMY.pages.INITIAL.options.SETTING_2` with
`--capability event-combat-map` for the pending Battleworn Dummy case.
Use `SETTING_1` instead for the potion-reward branch, with a free potion slot.
The host collects the owned reward, waits for callback completion and then runs
Proceed/map. This reusable option chooses the exact legal first parent option, then uses first-legal actions;
a missing/illegal requested option stops before input. It also works with `events`
and `event-map`. Automatic upgrade effects are not certified by callback completion.

This feature is not in the retained accepted release and has no live result yet.
Parent responses now identify protocol `generic_event_v9` over the existing v7
routes. The `events` mode stops at its reported `destination`; combat entry alone
is not a completed fight. See [event combat](../../docs/GENERIC_EVENTS.md#implemented-offline-non-resuming-event-combat)
and [resumption semantics](../../docs/GENERIC_EVENTS.md#implemented-offline-event-combat-resumption).

`/probe/v0/public/screen` recognizes only main menu/settings; its unsupported
result during a run is not a map diagnostic. Use the map decision route above.
The event summary's final `effects: unverified` describes its latest parent action
(usually Proceed); cumulative `completed_card_children`/`completed_item_children`
retain verified child completions. [Generic event semantics](../../docs/GENERIC_EVENTS.md)
explain the distinction.

Normal quit and stopped/closed-listener checks precede cleanup. Use the same
operational command with `--mode quarantine`, then `--mode purge`, each with
`--expected-state-sha256` from the preceding owned state. Preserve the release
source/package bindings until its installed campaign is closed. Cleanup verifies
exact ownership, state lineage and unchanged base files.

The unified bridge has a [representative live module smoke](../../docs/evidence/UNIFIED_BRIDGE_SMOKE_2026_09_08.md):
combat/rewards/map/shop, Smith/card selection, singleton potion collection and a
generic transformation event. Combat needed one UI-assisted chooser; console/UI
fixtures supplied later setups. The generic final effect summary and legacy
screen coverage retain documented limits. This is not an autonomous full-run result.
The earlier controlled V10 card16 result remains the specific off-screen evidence.

## Historical references

[Release history](releases/history/README.md) retains original identities; Git
retains the removed source trees and feature workflows. Commit `1d63e74` contains
the four interim consolidated app releases. Do not restore them as dependencies.

Original `contracts/live_probe_v0`, Python consumers and semantic fixtures keep
their paths. `tests/core_reference/` is a test-only assembly without a mod entry
point. The old `tools/run_gate.py` and R0a `verify_live_campaign_inputs.py` workflow
are retired. The latter binds documentation and inputs in its original checkout;
see the [documentation archive](../../docs/archive/README.md#original-bytes-and-paths).
Old operator/launch workflows are historical, while the actual core exchange/
manifest helper is compatibility-tested against the unified listener. Use the
entry points above for current work.
