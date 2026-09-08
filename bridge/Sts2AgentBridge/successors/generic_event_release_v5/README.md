# Generic event release v5 — native reward hitbox compatibility

Installable composition of frozen generic_event_v3 and generic_event_lifecycle_v1: shared event upgrade-one,
removal1..8 and reward additions1..8, with authoritative request/creation rules
and no event-name admission catalog. The exact frozen parent/card/wire and Python
controller remain the source of gameplay semantics. Unsupported families stop.

This release corrects the measured reward hitbox exact-type mismatch by accepting
a live instance through its declared native NClickableControl contract, including
subclasses. Exact retained-reference checks still reject replacement, and all
other candidate,ownership,visibility and selection checks remain. The78 diagnostic
values and gameplay protocol remain unchanged; candidate_hitbox_type is reserved
historical vocabulary. The actual live subtype name was not captured.

The lifecycle correction treats removed option buttons as opaque receipts after
strict predispatch validation; all scoped callback and child ownership remains.
The new release connects those components to a protected operator config,
authenticated127.0.0.1:43117 transport and the Godot owner frame. Full child
lineage is preserved across the HTTP boundary. Parent completion/map handoff ends
the campaign; child completion returns control to the event parent. Uncertain
POSTs are never retried. Hook installation failure and unpatch failure retain
owner-frame cleanup until successful, after transport stops.

Production uses the game-owned0Harmony.dll, version2.4.2.0, with exact path,
file hash, MVID and assembly/load-context binding verified before hook creation.
No second Harmony copy is loaded or distributed. Frozen v3's earlier NuGet-based
fixture evidence is separate; this release's inert tests also exercise the actual
pinned game Harmony library against target stubs. Offline checks never execute
sts2.dll,GodotSharp.dll or the production bridge assembly.

See the [release contract](../../../../docs/PHASE_1_GENERIC_EVENT_RELEASE_V5_CONTRACT.md)
and [acceptance ledger](../../../../docs/research/PHASE_1_GENERIC_EVENT_RELEASE_V5_ACCEPTANCE.md)
for exact validation, dependency identities, package status and live disposition.
All22 predecessor source trees and the original bridge are preserved.

## Offline gate

```sh
python -B bridge/Sts2AgentBridge/successors/generic_event_release_v5/check.py \
  --dotnet /absolute/path/to/dotnet \
  --game-data-dir /absolute/path/to/pinned/game/data \
  --scratch /private/tmp/a-new-generic-release-gate
```

Use SDK9.0.303 and a nonexistent scratch directory. The checker verifies source
and project closure, exact production metadata/IL, inert lifecycle/native/socket/
Python fixtures, package and transactional-tool mutations, and byte-identical
production builds. It downloads and installs nothing.

The canonical package contains only Sts2AgentBridgeGenericEventV5.dll and its
manifest. Publishing/installation follow successful independent release gates.
Fixed artifact root:/private/tmp/sts-generic-event-v5-release; fixed campaign:
GENERIC-EVENT-V5-SMOKE-V1; protected operator leaf:generic_event_v5.
Existing campaign objects are preserved and block a conflicting installation.

## Live setup

Install only with the game stopped, port closed and exact base verified. Wait
for explicit launch instructions. First campaign: Profile3,single-player,Room
Full of Cheese at initial choices,Gorge untouched,no selector/console/map/popup.
The controller must own the initial parent action; an open selector cannot be
adopted. One client invocation only. Generic admission remains independent of
this representative event name.

Client: `client/run_live.py --expected-state-sha256 <current-state-sha256>`.
It validates source, package, installed state and protected files before one
credential transfer into the frozen host. Output contains only fixed summary
status/counts and last_response_diagnostic; it never prints raw observations, option/card keys or credentials.
After the campaign quit normally, verify stopped/closed, quarantine code first,
purge exactly owned objects and verify base. The repeated unmodded launch remains
waived. No profile/save filesystem or Steam Cloud changes are part of this work.
