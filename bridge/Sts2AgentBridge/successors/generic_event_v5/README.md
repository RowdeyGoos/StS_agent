# Generic event v5 — native card transformations

This functional successor adds fixed-count transformations of1..8 cards to the
shared generic event handler. It observes the actual native selection, preview,
command, substitution hook and deck insertion. Event names remain ownership and
test data; production admission uses the shared interaction contract.

Transformations use the new `card_transform_v1` child state machine. The game may
remove every original in a batch before appending replacements, pausing after
each insertion. A bounded immutable journal proves those removals and actual
original-to-final mappings. Reconciliation checks the surviving original deck
followed by the observed append sequence, and waits for exact successful command
results, the original selection request, selector closure and the parent callback.
An initial preview or generated card is not proof of the final replacement because
native hooks may substitute it. No extra RNG call or lazy input enumeration occurs.

The outer protocol is `generic_event_v5`. The service and host use
`/probe/generic-event-v5/public/decision` and
`/probe/generic-event-v5/public/action`. Transform payloads carry
`card_transform_v1`; upgrades, removals and additions retain the actual frozen
`card_selection_v1` engine, codec and parser. Explicit operation/version binding
prevents mixing the two effect contracts. `completed_card_children` remains
cumulative, while `effects` describes the latest parent action.

Transform admission requires fixed `min=max`1..8, an explicit preview and Confirm,
a complete visible candidate domain larger than the maximum and at most64, and
no cancellation. The complete baseline deck is bounded at512 cards. Sequential
native command batches may cover disjoint subsets of the selected originals;
unknown mutations, invalid results, stale controls and reused replacement references
stop the child without completion credit. Partial progress never authorizes retry.
Existing fixed upgrade, variable removal and reward-addition modes are retained.
Optional, scrolling, variable transform minima, custom/item/combat interactions
remain outside this increment.

Read the [accepted contract](../../../../docs/PHASE_1_GENERIC_EVENT_V5_CONTRACT.md)
and [acceptance ledger](../../../../docs/research/PHASE_1_GENERIC_EVENT_V5_ACCEPTANCE.md)
for exact semantics, validation status and evidence limits. All24 predecessor
successors and the original bridge remain frozen.

## Offline validation

```sh
python -B bridge/Sts2AgentBridge/successors/generic_event_v5/check.py \
  --dotnet /absolute/path/to/dotnet \
  --game-data-dir /absolute/path/to/pinned/game/data \
  --scratch /private/tmp/a-new-generic-v5-gate
```

Use SDK9.0.303 and a fresh scratch directory. The checker verifies frozen
predecessor identities, derivations, explicit compile closure, transform/core/
native/wire/Python tests and complete native-to-host integration. Two native builds
must be byte-identical. Outputs stay in disposable snapshots, outside source trees.
It downloads nothing and never executes game, Godot or production native assemblies.
Only the exact pinned game-owned Harmony executes against inert target stubs.

This component contains no listener, package, operator config or campaign tooling.
Release composition and live validation remain separate gates; offline completion
does not establish live transformation support.
