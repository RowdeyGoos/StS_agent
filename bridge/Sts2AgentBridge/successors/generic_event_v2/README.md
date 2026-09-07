# Generic event v2

Shared native discovery for standard event upgrade-one and deck removal with
one to eight selected cards, including variable selection limits. No event-name
or option-key registration supplies interaction rules. The game command and
owned screen-creation arguments supply operation, counts and original candidates.

The [contract](../../../../docs/PHASE_1_GENERIC_EVENT_V2_CONTRACT.md) preserves
two-stage admission: reserve exact context and the complete pre-action deck;
observe the owned request, creation and asynchronous completion; publish an
immutable admitted descriptor; create the actual frozen card session using its
exact opaque admission identity. Stops after dispatch retain attempts and
receipts and report unverified effects when completion is uncertain.

## Supported interactions

| Family | Selection | Commit | Domain |
| --- | --- | --- | --- |
| Upgrade | Exactly one | Native preview and confirm | 2..64 original deck cards |
| Remove | 1 <= min <= max <= 8 | Preview below max via button or automatically at max, then confirm | More than max, at most64 original deck cards |

Both are noncancelable. Optional zero, scrolling, repeated-key loops, generated
adds, transformation, multi-upgrade, item children, custom screens and event
combat remain unsupported in this component. Frozen predecessor capabilities
remain unchanged. This component does not claim every event or branch works.

Removal reads original-card references from the actual preview holders, including
when native preview clears grid highlights. It validates exact selected membership,
the request/selector result sets, successful awaited parent completion and exact
remaining-deck identity/order/keys/levels. It does not certify unrelated HP/gold
consequences. Reverse click order is supported without changing candidate order.

## Components

- `core/`: bounded parent and immutable native admission; source-links the frozen
  card session for selection and exact effect reconciliation.
- `native/`: shared command/creation discovery and native controls, with an
  exclusive observational Harmony lease. Original methods always run.
- `wire/`: correlated publications, receipts and exact child descriptors.
- `host/`: Python3.10+ controller with immutable injected decision provider,
  one deadline, bounded actions and no retry after uncertainty.
- `native_tests/`, `wire_tests/`, `integration_tests/`: inert hooks, negative
  protocol cases and production native-to-Python fixtures.

The new outer protocol is `generic_event_v2`; decision/action routes are
`/probe/generic-event-v2/public/decision` and
`/probe/generic-event-v2/public/action`. Child payloads remain `card_selection_v1`.
The Python entry point is `run_event(request, provider=...)`; `first_legal` is an
explicit fixture policy. Clients cannot create native interaction descriptors.

## Offline verification

The checker verifies all fifteen frozen predecessors and original bridge sources,
checks exact derivation diffs and isolated explicit project closures, executes
inert fixtures and compares two compile-only native builds. Supply SDK9.0.303,
the pinned target references and exact Harmony2.4.2 package in `dependency.json`.
It downloads nothing and never executes target assemblies.

```sh
python -B bridge/Sts2AgentBridge/successors/generic_event_v2/check.py \
  --dotnet /absolute/path/to/dotnet \
  --game-data-dir /absolute/path/to/pinned/game/data \
  --harmony-package /absolute/path/to/lib.harmony.2.4.2.nupkg \
  --scratch /private/tmp/generic-event-v2-new-check
```

Scratch must not already exist. Logs and `result.json` are disposable; exact
acceptance evidence belongs in the [ledger](../../../../docs/research/PHASE_1_GENERIC_EVENT_V2_ACCEPTANCE.md).
No third-party binary is committed. Harmony is MIT licensed; a future distribution
must retain its license.

No listener, package, installation or live release is provided. The real game's
EventSynchronizer route must preserve scoped asynchronous dispatch context;
inert fixtures and target compilation cannot prove this. Lost context stops
discovery rather than adopting an unowned request. Release composition and live
validation remain separate gates.
