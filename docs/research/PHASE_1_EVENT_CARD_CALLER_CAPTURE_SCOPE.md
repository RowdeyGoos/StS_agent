# Phase 1 event card-caller capture-only follow-up scope

- Date: 2026-09-06
- Status: proposed; synthetic capture gate passes, no follow-up target read performed
- Baseline: `920ec84`
- Predecessor result SHA-256: `6dff720300102d30dffa6b1f514e6c1b6741287680236077b2424164bbc2a760`

## Purpose

Persist the complete canonical stdout from one separately reviewed invocation
of the unchanged event card-caller scanner. The accepted first invocation
completed, but its command transport truncated the row array before it was
saved. Its surviving aggregate result was 68 events, 791 scanned bodies, 31
selector calls and 45 effect calls. No row from that run is accepted.

This follow-up changes capture only. It does not change the scanner, event set,
API allowlist, target, body set, limits, or interpretation in
`PHASE_1_EVENT_CARD_CALLER_SCOPE.md` SHA-256
`b2bd845547c23884b86bfb26f1a7228c66c87508da76ef781b706547b7012677`.
It remains a positive and intentionally incomplete direct/attribute-bound
`MoveNext` census. It cannot prove that an event without a row has no card
interaction.

## Exact pinned inputs

- scanner source manifest: `d8c5a1026dfeabbe5458a8d95b6bf6ac7f72ff96d4db43fb6946cd669370365c`;
- scanner DLL, 41,472 bytes: `f780c547ffdc6e5371543f8d22c2d3109eb55de4ff341792b43e7b21b800736d`;
- scanner deps: `08204570ec3bf235136ad1407a13f8805c80f2cf6a8904faec249469ddfa1428`;
- scanner runtime config: `9b93bb9ae8b1f2d369e6bfd31f183e2db18031236ff1171bb899522aea902297`;
- exact event config: `5cae9ace6df7bf2de5b4d479d279368fcd45225a2bfc9e53400a84c1b56952f7`;
- exact API config: `705c405e0a68c2dd37e3998218dc2d8bf1b5f475f8e9e8a840c08d570edd727f`;
- target `sts2.dll`: `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.

The wrapper verifies the 21-row source manifest and every listed source byte,
then the five managed scanner-bundle inputs above, before invoking the scanner.
The unchanged scanner independently verifies the event/API pins and target pin
before metadata decoding.

## Capture and validation

The output directory must be an absent direct child of `/private/tmp` named
`event-card-callers-capture-` plus 24 lowercase hexadecimal characters. The
wrapper creates it with mode `0700`. It captures at most 1,000,000 stdout bytes
and 4,096 stderr bytes for at most 60 seconds. Overflow, timeout, nonzero exit,
or any stderr fails closed.

Before printing any wrapper summary, it creates `result.json` and `stderr.bin`
with exclusive creation and mode `0600`, writes the exact captured bytes, and
syncs them. It then requires one newline-terminated JSON object with the exact
scanner schema, pinned target hash, aggregate counts 68/791/31/45, exactly 76
rows, exact row key order, nonnegative offsets, sorted row order, configured
event names, and exact configured `(kind, callee)` pairs. It finally creates a
summary containing only schema, pass status, suite name, result SHA-256 and row
count. Reusing an output directory fails before invocation.

The result retains only the metadata identities and offsets allowed by the
original scope. It contains no raw instructions, constants, resources,
localization, profile, save, history, Cloud, network, game execution, operator,
package or live-runtime data.

## Disposable wrapper and synthetic gate

The wrapper is in `/private/tmp/event-card-callers-capture-b`:

- `capture_runner.py`: `8b6899083257009e200bf3b35937ed28921d7de247f0f8545e85cff7bcee540c`;
- `run_capture_fixtures.py`: `7e142d8d39543d2282700d69827dda1ad967b84e6cd5ef0cbd940a1ac1740a7f`;
- two-input source manifest: `af38247cca15d9d3e803d165f2a65a975970662374427ae14c5daedc009c084e`.

The inert test invokes the exact pinned scanner in fixture mode, persists its
four rows, validates the stored result hash, aggregate schema and private file
modes, then proves a second use of the same output directory fails before
invocation. Its fixed
result is:

```json
{"schema_version":1,"status":"passed","suite":"event_card_callers_capture","check_count":4}
```

Independent review must accept this exact wrapper and scope before the root
coordinator gives an explicit go for one capture-only target invocation. Any
failure stops without another read or a looser rerun.
