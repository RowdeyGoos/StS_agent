# Phase 1 event card-callback diagnostic synthetic validation

- Date: 2026-09-06
- Status: passed; target not read
- Tool source manifest:
  `3a64ea4f4ede20e35035adf9b40f55f8978a18bef8a41eb929ad73db3298d5d5`
- Capture source manifest:
  `d2b1ce75ab3da77443c58776a4afaf0e05fb75dfadeb554000574dbb2a826dca`

The scanner built offline and inspected only inert fixture assemblies. It
preserved selected, initial-options, callback and removal-helper bodies while
separately reporting two unambiguous selected bindings, one unresolved
closure/extra-string constructor and its lexical key candidates. It did not
promote the unresolved option to a binding. The exact-method ambiguity,
callsite, target pin, redaction, deterministic-output and physical-file
controls remain active. A separate fixture delegated all option construction
and proved zero direct constructor rows still preserve every bounded body
family.

```json
{"schema_version":1,"status":"passed","suite":"event_card_callbacks","check_count":15}
```

The capture wrapper persisted the inert result before validation and retained
private modes and output-directory non-reuse.

```json
{"schema_version":1,"status":"passed","suite":"event_card_callbacks_capture","check_count":3}
```
