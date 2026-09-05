# Room Flows V1 acceptance

Date: 2026-09-05. Selected checkout: 23cf, branch
codex/phase1-actor-ready-integration; predecessor HEAD bfb0170.
The user asked for actual shop/event development with parallel implementation.
The [implementation plan](../PHASE_1_SHOP_EVENT_IMPLEMENTATION_PLAN.md)
and [functional contract](../PHASE_1_ROOM_FLOWS_V1_CONTRACT.md) bind this packet.

## Implemented scope and ownership

Shop and event writers owned their separate core/native/tests subtrees.
The coordinator implemented common interfaces, the frozen-item broker,
wire/host and actual cross-language fixtures. An independent reviewer read
each implementation and required corrections before acceptance. After the
event lane was frozen, its writer implemented only the coordinator-delegated
offline checker. The coordinator owns shared docs and final integration.

Shop handles one already-open inventory, zero/one affordable ordinary card,
explicit inventory close and separately reconciled room leave. It preserves
raw stock indices, passive rendered prices, exact deck/gold/entry reconciliation,
one-sided asynchronous prefixes, terminal state, subscriptions and reservations.
Cleared known slots are skipped before model/price reads; restock is unsupported.

Event publishes bounded exact label source and option facts, reserves stable
keys for the parent lifetime, requires structural continuation excluding text,
allows one controller-owned item child at the first supported transition,
revalidates the retained parent, and exits only through exact final Proceed.
Changed parent projection revokes old child eligibility. Item success is
independent of ordinary-option effects; only the final map handoff is a
reconciled parent exit. Rest upgrades remain outside scope.

## Review and fixture evidence

| Gate | Result |
| --- | --- |
| Common and real frozen-item broker | Accepted; 575 real-service assertions. |
| Shop core and pinned native adapter | Accepted; 13 pure fixture groups; native compile-only passed. |
| Event core and pinned native adapter | Accepted; 36 pure fixture groups; native compile-only passed. |
| Shared wire service/codec | Accepted; 16 concrete-session lifecycle and route-isolation assertions. |
| Strict Python host and actual C# bytes | Accepted; 192 cross-language checks. |
| Existing Python regression | 1154 passed in sandbox; one synthetic ephemeral bind denied by sandbox, then same focused test passed unchanged with authorized local-socket access. All1155 existing tests covered. |

Broker review corrected terminal monotonicity and callback interference.
Module review corrected text-only continuation, first-transition child
ownership, exact pending effect orderings, complete-state persistence, malformed
captures and cleanup reentry. Host review added exact lifetime-aware legal lists
and structural digest parity using raw eligible actions before reservation
filtering. Mutated canonical responses cannot hide legal options or turn a
text-only change into another action, before or after a real item child.

Integration cases exercise real C# ShopV1Session/EventV1Session, real
ItemWireV1Service/ItemV1Session and the frozen Python item controller, through
the real successor wire codec. They include purchase and no-purchase shops,
ordinary/Unicode events, one item child, uncertain dispatch, incorrect receipt
and prior-result identity, reserved-key ABA, omitted legal actions, empty text,
text-only continuation and a late child response under the shared deadline.
Native effects are synthetic fixture bindings; no live result follows.

## Aggregate source gate

The final checker passed from the new physical directory
/private/tmp/room-flows-v1-check-20260905b. The coordinator verified the returned
[result JSON](PHASE_1_ROOM_FLOWS_V1_OFFLINE_RESULT.json) against its SHA256.
An independent reviewer verified all 33 source paths/hashes against the
reviewed versions and accepted the aggregate. There were no post-manifest
source edits. The checker verified all five frozen predecessor inventories
and all 48 old bridge inputs, ran the exact 575/13/36/16/192 fixture summaries,
and compiled both native adapters without executing target or native code.

| Frozen identity | SHA256 |
| --- | --- |
| Functional contract |67c5221f0db9625c9b0c67539dc64899849bfc55780495fa2f8681f4b44f5416 |
| Source manifest, 33 inputs |91f5750b70a7b3c735f487a0e5d3d0315b6c6b32593b6fe452845745e506b213 |
| Source inventory |96c47beadd96acb1a886748fad5691efca754f83dc1f26064707804a8a178bae |
| Offline checker |c61218e8673860d864c34a49183eca036d8558fe7d44e1afe7b5b308244c298e |
| Result JSON |05fc1b908f89a5075e1b170228bc6ddfe88abf4db5e76c37f95d9da9b1acf921 |
| Shop native compile-only DLL |75d0f069e533d5187c0db93837345d492cd7fd400a982b68d12dd48f36e1f296 |
| Event native compile-only DLL |851b28c40b46870df2cb5c0748194815ae125e3e83fa50f86f951369db864c4c |

The only SDK stderr admitted by the checker is the already-observed exact
CSSM_ModuleLoad warning during restore/build; SDK version and every pure
fixture execution remain stderr-strict. Offline source and project closure
checks disallow added package/analyzer/exec targets and native runtime
dependencies in pure tests. Compileall for game/tests also passed using a
disposable pycache directory.

## Operational disposition and next gate

No game, endpoint, operator/config, profile/save, Cloud, remote Git or live corpus
operation occurred in this implementation packet. One existing regression used
only its synthetic ephemeral loopback test server. No campaign remains active.

This packet is functional code plus native compile and cross-language evidence.
It does not include a new listener, composite runtime/bootstrap, production
verifier/package or live installation. Integrate those once for both flows,
preserving all frozen predecessors, before requesting a precise user-prepared
shop inventory or fresh untouched event. Normal cleanup remains required;
the user-waived repeated unmodded launch check remains waived.
