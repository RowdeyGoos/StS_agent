# Phase 1 event card-callback synthetic validation

- Date: 2026-09-06
- Status: passed; target not read
- Tool source manifest: `a3a012d287f73f37ff1865417e0ff30363ea375b319b02906993670b8f6c6851`
- Capture source manifest: `cac346c367cea8409033d49aa5bc7267e9e161cf240a042fdb5b1bcf88069d59`

The exact tool built offline and inspected only an inert two-event assembly. It
validated source-to-state-machine, callsite and exact option-key/delegate
bindings, emitted the exact removal wrapper/generic state/callback chain plus
the selected, initial-options and callback bodies, redacted all other user
strings, accepted an unrelated generic-arity identity collision, rejected that
collision on an exact selected identity, and passed its other
selection/pin/boundary negatives.

```json
{"schema_version":1,"status":"passed","suite":"event_card_callbacks","check_count":13}
```

The separate capture fixture persisted that inert output before summary and
validated private ownership and create-only behavior.

```json
{"schema_version":1,"status":"passed","suite":"event_card_callbacks_capture","check_count":3}
```
