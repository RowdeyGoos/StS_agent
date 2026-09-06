# Generic event v1

A functional successor that discovers standard event upgrade interactions from
shared game calls, without an event-type or option-key policy catalog. It composes
bounded ordinary option pages, one owned card child per option, native preview
confirmation, exact upgrade reconciliation and explicit Proceed/map handoff.

The [contract](../../../../docs/PHASE_1_GENERIC_EVENT_V1_CONTRACT.md) defines
two-stage admission. Before dispatch the parent reserves exact context and the
complete deck. Scoped observational hooks capture the actual upgrade request,
creation preferences, original-card domain, screen and asynchronous tasks. Only
then can the frozen card session expose legal actions. Event identity correlates
ownership; it supplies no operation or count rules. A stop after parent dispatch
retains attempted/accepted counts and reports unverified effects.

Current generic native family: exactly one noncancelable upgrade, complete domain
of2..64 original deck cards, native single-card preview confirmation, either
RequireManualConfirmation preference value. Multi-upgrade, optional/scrolling
selectors, add/remove/transform, item children, repeated-key loops, custom screens
and event combat are explicitly unsupported in this successor. Earlier component
capabilities remain available in their unchanged trees. This is not all-event or
all-branch coverage, a strategic policy, or a live-tested release.

## Composition

- `core/`: bounded event state machine and public immutable DTOs; source-links
  the actual frozen card session.
- `native/`: exact parent/UI binding, creation discovery and shared card adapter.
  Harmony observes only EventOption.Chosen, CardSelectCmd.FromDeckForUpgrade and
  NDeckUpgradeSelectScreen.ShowScreen. Originals always run; no private fields,
  game-file rewriting, argument/result replacement or transpilers are used.
- `wire/`: owner-thread decision/action pair with reserved publications and child
  lineage. Clients can select legal actions; they cannot construct native rules.
- `host/`: Python3.10+ controller with an injected immutable decision provider,
  exact receipts, bounded work and no retries after uncertainty.
- `native_tests/`, `wire_tests/`, `integration_tests/`: inert native hooks, protocol
  negatives and actual C#-to-Python composition.

The outer protocol is `generic_event_v1`, with
`/probe/generic-event-v1/public/decision` and
`/probe/generic-event-v1/public/action`. Requests use the published decision/action
and optional child ordinal/parent receipt. The child payload preserves
`card_selection_v1`. The parent receipt does not promise a child before discovery.

The Python entry point is `run_event(request, provider=...)`; `request` is an
injected transport returning an owned bytearray. `first_legal` is an explicitly
selected deterministic fixture policy. There is no listener or installation
entry point in this component.

## Offline verification

Supply SDK9.0.303, the pinned game data directory and the exact Harmony2.4.2 NuGet
package identified in `dependency.json`. The checker never downloads dependencies,
executes target assemblies or writes build outputs into accepted source trees.
It verifies all fourteen predecessor identities and original48, runs inert tests
in disposable snapshots and compares two compile-only native builds.

```sh
python -B bridge/Sts2AgentBridge/successors/generic_event_v1/check.py \
  --dotnet /absolute/path/to/dotnet \
  --game-data-dir /absolute/path/to/pinned/game/data \
  --harmony-package /absolute/path/to/lib.harmony.2.4.2.nupkg \
  --scratch /private/tmp/generic-event-new-check
```

Use an absent scratch directory. The check writes logs and `result.json` there.
The package is MIT licensed; no third-party binary is committed. Retain its
license if a future reviewed release distributes it. Exact acceptance evidence
and residuals belong in the [ledger](../../../../docs/research/PHASE_1_GENERIC_EVENT_V1_ACCEPTANCE.md).

Functional checks do not create a release verifier, bootstrap, listener, package,
installation or live campaign. The new instrumentation requires its own release
boundary before use in the running game. Ordinary native choices pass through
EventSynchronizer before Chosen; inert fixtures cannot establish that the real
game preserves the scoped asynchronous dispatch context along that route. If it
does not, discovery stops instead of adopting an unowned request. That lifecycle
needs validation in a separately prepared live release.
