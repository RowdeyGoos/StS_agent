# Phase 1 event card-callback attempt 2 result

- Date: 2026-09-06
- Status: stopped fail closed; no rows accepted; no retry under this scope
- Reviewed scope SHA-256:
  `faca6e77b28471e2a83fce08bd14b388ad3d4a1419cdc3bf3c47026bb55ef5a4`
- Reviewed tool source manifest:
  `a3a012d287f73f37ff1865417e0ff30363ea375b319b02906993670b8f6c6851`
- Reviewed scanner DLL: 64,000 bytes,
  `f1c728be934b5b2e462618634abfed18b613384df7eabd3d01570ce35ac63ac7`
- Reviewed capture manifest:
  `cac346c367cea8409033d49aa5bc7267e9e161cf240a042fdb5b1bcf88069d59`

The one newly authorized corrected invocation opened the pinned assembly for
metadata-only inspection and stopped with the fixed scanner error
`option_binding_mismatch`. There was no target execution, live operation,
profile/save access, Cloud or network access. The capture wrapper persisted its
bounded streams before validation:

- `/private/tmp/event-card-callbacks-capture-a5c9bfe32eb74388a0cff59d/result.json`:
  0 bytes, mode `0600`, SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- `stderr.bin`: 73 bytes, mode `0600`, SHA-256
  `889c089b3b4b881b0574acc002406b9b710c6c0aeb79502c604fc6b777f9de60`;
- no summary was written.

No option key, callback, helper or completion row survived. All five proposed
production rows remain disabled. Source review shows the scanner required every
`EventOption` constructor segment in every selected event's complete
`GenerateInitialOptions` body to have exactly one direct same-event callback
and one key-like string. This can reject an unrelated option before any
selected caller row is emitted. Any follow-up must have a separately reviewed
scope and may not infer support from an unresolved constructor.
