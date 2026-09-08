# Generic event v6 — singleton item children

This functional successor adds direct singleton potion and relic reward children
to the generic event controller. Admission follows the event's owned shared
RewardsSet request and ordinary screen creation, without event-name registration.
Native evidence and complete aggregate acceptance are recorded in the
[acceptance ledger](../../../../docs/research/PHASE_1_GENERIC_EVENT_V6_ACCEPTANCE.md).

Item children use the actual frozen `item_v1` session and `item_probe_v1` codec/parser.
Potion collection proves one exact inventory insertion into an empty slot; relic
collection proves the exact reward-local claimed model and successful selection.
The wrapper retains local collection evidence while waiting for the owned
collection, reward-offer and event callback tasks and screen closure. It freshly
revalidates the effect during that wait, within one total 256-read budget.

The outer protocol is `generic_event_v6`, using
`/probe/generic-event-v6/public/decision` and
`/probe/generic-event-v6/public/action`. Explicit card/item descriptors select the
frozen `card_selection_v1`, `card_transform_v1` or `item_v1` child payload. Item
replay checks include outer parent/child lineage, allowing identical later offers.
`completed_card_children` and `completed_item_children` retain cumulative verified
completion; `effects` continues to describe the latest parent action.

Existing upgrade, removal, reward-card and transformation behavior is preserved.
One potion/relic offer must be the entire authoritative reward set, on an owned
nonterminal screen. Full potion belts, multiple rewards, linked rewards, custom
selectors, optional/scrolling selection and event combat remain unsupported.

Read the [contract](../../../../docs/PHASE_1_GENERIC_EVENT_V6_CONTRACT.md) for
exact semantics and acceptance gates. All25 predecessor successors and the
original bridge remain frozen.

## Offline validation

```sh
python -B bridge/Sts2AgentBridge/successors/generic_event_v6/check.py \
  --dotnet /absolute/path/to/dotnet \
  --game-data-dir /absolute/path/to/pinned/game/data \
  --scratch /private/tmp/a-new-generic-v6-gate
```

Use SDK9.0.303 and a fresh scratch directory. The checker validates predecessor
identities, derivations, explicit source links, core/native/wire/Python tests and
actual native-to-host integration. Two production builds must match byte for byte.
Build outputs stay in disposable snapshots. No game, Godot or production native
assembly executes; pinned game-owned Harmony executes only against inert stubs.

This component has no listener, package, operator configuration or campaign tooling.
Release composition and live validation remain separate work.
