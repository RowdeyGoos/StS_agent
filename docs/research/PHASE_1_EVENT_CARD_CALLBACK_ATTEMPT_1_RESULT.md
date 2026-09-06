# Phase 1 event card-callback attempt 1 result

- Date: 2026-09-06
- Status: stopped fail closed; no rows accepted; no retry under this scope
- Reviewed scope SHA-256: `df86ffaf26c8102a4c531a590e16d9dfbbbb90e0af1215b94161be7e34218dc7`
- Reviewed tool source manifest: `cd1bbd52730a5ce9ed5ec98ba98ab351508bf2e0087ffdd7dc51c951b2ab7762`
- Reviewed scanner DLL: 64,000 bytes,
  `3da08f6d993fb58ed1cd90d240f97d68cf15fdbad4f45b07ad6557b7a57d3ee9`
- Reviewed capture manifest:
  `ca4adf369f06048e1073968ae2e4b556ce3210f609e70980d819faba532e3857`

The single authorized invocation opened the pinned assembly for metadata-only
inspection and stopped with the fixed scanner error `ambiguous_metadata`.
There was no target execution, live operation, profile/save access, Cloud or
network access. The capture wrapper persisted its bounded streams before
validation:

- `/private/tmp/event-card-callbacks-capture-6aee91bd788b4f6ba8ff51c4/result.json`:
  0 bytes, mode `0600`, SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- `stderr.bin`: 68 bytes, mode `0600`, SHA-256
  `12def444279fc4eeb9d7b57d18d394d4bca3be0a7ca73e98c870e28633b52a44`;
- no summary was written.

No option key, callback, helper or completion row survived the failure. All
five proposed production rows remain disabled. Source review localized the
defect to an assembly-global dictionary keyed by a method identity that omits
generic arity and return type. A separate corrected scope must pass independent
review before any new target invocation.
