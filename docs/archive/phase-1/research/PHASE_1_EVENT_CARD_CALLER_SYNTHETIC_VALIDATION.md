# Phase 1 event card-caller synthetic validation

- Date: 2026-09-06
- Status: passed; target not read
- Scanner source manifest SHA-256: `d8c5a1026dfeabbe5458a8d95b6bf6ac7f72ff96d4db43fb6946cd669370365c`

The disposable offline gate built only inert managed fixtures. It demonstrated
exact direct selector/effect matching, async state-machine attribution,
unrelated-call omission, deterministic output, hash-before-PE behavior, fixed
malformed-image failure, event/API configuration rejection including both target-mode byte pins, body/callsite
bounds and physical-path rejection. It did not open the pinned game assembly.

Command shape:

```text
/private/tmp/event-card-callers-b/run_fixtures.py --dotnet <SDK-9.0.303>
```

Expected and observed canonical result:

```json
{"schema_version":1,"status":"passed","suite":"event_card_callers","check_count":14}
```
