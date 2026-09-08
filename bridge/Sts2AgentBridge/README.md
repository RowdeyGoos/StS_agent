# Live bridge

One maintained source tree replaces the 32 successor snapshots. Shared code lives
in `components/`; `apps/` contains the latest distinct release compositions,
clients and operational tools. Historical source is in Git, with original source
manifests and release policies in [releases/history](releases/history/README.md).

Read [current status](../../docs/PHASE_1_CURRENT_STATUS.md) for demonstrated
capabilities and [live development](../../docs/LIVE_DEVELOPMENT.md) for workflow.

## Maintained targets

| Target | Implementation | Scope |
| --- | --- | --- |
| `events` | [components/events](components/events), [apps/events](apps/events/README.md) | General G7 interactions and latest V10 direct-card16 experiment |
| `rooms` | [components/rooms](components/rooms), [apps/rooms](apps/rooms/README.md) | Shop/map permission repair and bounded standard room flows |
| `cards` | [components/cards](components/cards), [apps/cards](apps/cards/README.md) | Standalone card selection with accepted completion repair |
| `items` | [components/items](components/items), [apps/items](apps/items/README.md) | Standalone potion/relic collection |

`components/item_wire`, `item_transport` and `item_bootstrap` provide shared
producer, transport, operator-file and bootstrap code. Keep one maintained copy
of a component. Existing C# namespaces, assembly names and wire versions remain
stable; directory consolidation does not create new protocol semantics.

The general G7 transformation adapter and V10 experiment deliberately have
different behavior. The experiment's project explicitly selects its card16-only
adapter in `apps/events/gameplay`; it does not replace general G7 with a restricted
test policy. Generalizing direct input remains the next behavior change.

## Development checks

Use Python 3.10+; the repository `.venv` is suitable. From the repository root:

```bash
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --target events --suite sources
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --target events --suite python
.venv/bin/python -B bridge/Sts2AgentBridge/check.py --target events --suite test \
  --dotnet /ABS/dotnet \
  --game-data-dir /ABS/data_sts2_macos_arm64
```

Choose `items`, `rooms`, `cards`, or `events`; use `all` only when the change
affects all compositions. `sources` checks explicit current project dependencies.
`python` runs the selected host, transport, client and operational fixtures.
`test` also compiles and exercises C# behavior and actual producer/client
integration. Development suites do not require freezing a source inventory or
updating a release policy before testing a change.

The checker uses .NET SDK **9.0.303**, no NuGet feeds, and pinned read-only
`sts2.dll`, `GodotSharp.dll` and `0Harmony.dll` references. Build inputs and outputs
are isolated under a new `/private/tmp/sts-bridge-*` directory. Native fixtures
use inert game stubs; the actual game assemblies are never executed. Socket
fixtures use temporary loopback endpoints and may require sandbox permission.

For a narrow correction, run the affected existing test script or project
directly. Do not rerun the aggregate because documentation changed.

## Release and live client

Use `--suite build` for only the selected production build. Use `--suite release`
once the change is stable; it adds the maintained source/policy closure, binary
surface and mutation checks, canonical package checks and clean-install fixtures.
The accepted surface and package bindings live beside each app. Update these
current bindings deliberately for a new binary; do not create another successor
directory or repin historical evidence.

A successful release gate writes `<target>-release.json` and its SHA-256 to the
disposable output directory. The manifest binds current transitive sources,
tests, toolchain/references, test results and binary identity. Keep its printed
hash separately. Failed or development-only gates do not publish a live-usable
release manifest.

The four migrated targets' [current release records](releases/current/README.md)
and validation summary are retained in the repository. Replace a target's current
record after a later release; Git preserves its earlier versions.

The maintained live client now takes the release identity in addition to the
owned campaign state:

```bash
.venv/bin/python -B bridge/Sts2AgentBridge/apps/events/client/run_live.py \
  --expected-state-sha256 <current-owned-campaign-state-hash> \
  --release-manifest /ABS/events-release.json \
  --release-sha256 <hash-printed-by-the-successful-release-gate>
```

This verifies the selected current source bundle before credential access. It
never loads historical checkers. Native identity, legality, single-attempt
dispatch, reconciliation, authenticated configuration and owned cleanup remain.
Use the selected app's package/operations tools within the requested live scope;
old campaign readiness and credentials are not reusable. A repository gate does
not install, launch or interact with the game.

## Original combat/reward/map bridge

The original `live_probe_v0` implementation remains in `src/`, with its tests,
`contracts/live_probe_v0`, package manifest and `tools/` entry points. It provides
the existing combat/reward/map/rest/bounded-run capabilities and is a distinct
protocol, not a copy of the generic event component. Its Python consumers in
`game/backends/live` and `tests/backends/live` keep their paths.

Use `tools/run_gate.py --help` for its existing offline gate and the
[BR0 contract](../../docs/PHASE_1_BR0_PREFLIGHT.md) when changing that interface.
Exact earlier commands and source are available in the
[original guide at the consolidation baseline](https://github.com/RowdeyGoos/StS_agent/blob/4f0c9ed912b533da17e431bc2ff59a63b06b2aae/bridge/Sts2AgentBridge/README.md).
