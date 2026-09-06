# Phase 1 event card-caller capture synthetic validation

- Date: 2026-09-06
- Status: passed; target not read
- Wrapper source manifest SHA-256: `af38247cca15d9d3e803d165f2a65a975970662374427ae14c5daedc009c084e`
- Unchanged scanner source manifest SHA-256: `d8c5a1026dfeabbe5458a8d95b6bf6ac7f72ff96d4db43fb6946cd669370365c`

The disposable test used the exact scanner bundle and inert two-event fixture.
It proved byte-complete create-only result persistence, result-hash and schema
validation, private directory/file modes, and output-directory non-reuse. It
did not open the game target.

```json
{"schema_version":1,"status":"passed","suite":"event_card_callers_capture","check_count":4}
```
