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
This does not support cards without allocated holders or certify every selector.

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

This runs the integrated checks, verifies a reproducible production binary, checks
its compiled entry point/dependency surface, and exercises package mutations and
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

Capabilities are `events`, `event-map`, `combat`, `combat-map`, `combat-choice`,
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
These additions await live testing.

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
These composed paths have offline shared-socket coverage and await live testing.

The shared client spaces exchanges by at least 60 ms, below the listener's
20-per-second authenticated allowance. Pacing consumes the existing exchange
budget; an expired wait or connection cannot send a request. Server rate limits
remain unchanged and rate-limited/uncertain requests are never retried.

Use `--capability event-map` for the next event-to-core handoff test. After a
resolved event it polls `/probe/v0/public/map-decision` within a five-second
window and 100-read cap, accepting only a validated actionable map. An in-flight
exchange can extend elapsed time by its existing two-second transport limit;
responses arriving after the polling deadline cannot pass. It selects no map node.
Only a `waiting` map response permits another read; errors, unsupported responses,
uncertainty or interruption stop the check. The result retains the full `event`
summary and a separate `map_handoff` status/read count even when that check fails.
A failed event never starts the map check. The existing `events` mode is unchanged.

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
