# Generic event v4 — multi-upgrade and cumulative child evidence

This functional successor extends shared native upgrade discovery to fixed
selection counts1..8. It preserves variable-count removal1..8, reward additions1..8
and ordinary event continuation with explicit Proceed/map handoff. Event names
are ownership and test data, never an admission allowlist. Unsupported families
stop explicitly after accounting for any already-dispatched parent action.

For multi-upgrade, each native candidate dispatch reserves one exact callback
ticket. The matching deferred selector callback consumes it and scopes native
RunState.CloneCard observations. The preview binds exact original→clone pairs
and actual preview holders; it never infers originals from CloneOf, card names or
visual similarity. Confirm is exposed only for a complete unchanged preview.
The frozen card session verifies every selected original gains exactly one
upgrade while preserving the remaining ordered deck.

The outer protocol is `generic_event_v4`; the frozen `card_selection_v1` child
payload and session remain unchanged. `completed_card_children` counts fully
validated child resolutions and persists through Proceed or later failures.
The existing `effects` field still describes the latest parent action. These
fields distinguish verified card completion from uncertified later event effects.

Scope is deliberately explicit: upgrade counts are fixed (`min=max`), domain
must exceed maximum and be at most64, cancellation is unsupported, and the entire
selector must be visible. Transformation, optional/scrolling selectors, generic
item children and custom/combat interactions require further shared adapters.
Single-upgrade retains its separate native preview. The v5 reward hitbox repair
and lifecycle correction are included; all 23 predecessor trees stay frozen.

Read the [contract](../../../../docs/PHASE_1_GENERIC_EVENT_V4_CONTRACT.md) and
[acceptance ledger](../../../../docs/research/PHASE_1_GENERIC_EVENT_V4_ACCEPTANCE.md)
for the current implementation, review and validation status.

## Offline validation

```sh
python -B bridge/Sts2AgentBridge/successors/generic_event_v4/check.py \
  --dotnet /absolute/path/to/dotnet \
  --game-data-dir /absolute/path/to/pinned/game/data \
  --scratch /private/tmp/a-new-generic-v4-gate
```

Use SDK9.0.303 and a fresh scratch directory. The checker verifies every frozen
predecessor, exact derivation and compile closure, native/core/wire/Python fixture
composition and two byte-identical native builds. It downloads nothing and never
executes the game, Godot or production adapter assemblies. Only the exact pinned
game-owned Harmony executes with inert target stubs. Build outputs remain in the
disposable snapshot, outside the source trees.

This is a functional component, not an installable release: it contains no
operator config, listener, campaign tools or package. Release composition and
live validation are separate gates. Do not use a closed campaign's state or
credentials to test a new component.
