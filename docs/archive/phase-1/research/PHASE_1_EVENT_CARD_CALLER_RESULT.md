# Phase 1 event card-caller census result

- Date: 2026-09-06
- Status: aggregate execution facts accepted; callsite rows not accepted
- Reviewed scope SHA-256: `b2bd845547c23884b86bfb26f1a7228c66c87508da76ef781b706547b7012677`
- Scanner source manifest SHA-256: `d8c5a1026dfeabbe5458a8d95b6bf6ac7f72ff96d4db43fb6946cd669370365c`
- Scanner program SHA-256: `beb1a92c9d65523673a1cfb556d79609d839741ec2a30e318edca49dfc6a55fb`
- Target SHA-256: `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`

The one reviewed metadata-only target invocation exited successfully. The
following aggregate fields survived intact:

```json
{"event_count":68,"body_count":791,"selector_call_count":31,"effect_call_count":45}
```

No scanner failure or limit fired. The target was not loaded or executed.

The scanner emitted its canonical result as one long stdout line. The command
transport truncated a middle portion before the result was persisted. The row
array therefore has no accepted byte identity and must not be reconstructed
from the displayed fragments. This run cannot select or authorize any exact
production registry row and cannot support event-level or caller-level
completeness claims. A separately reviewed capture-only scope is required to
persist exact rows.

No second target read was performed under this scope.

## Capture-only follow-up

An initial capture command exited 127 before Python started because the
checkout-local interpreter path did not exist. It created no output directory
and did not open the scanner or target. The coordinator then supplied the
existing repository Python 3.11 interpreter and explicitly authorized the
accepted capture-only packet SHA-256
`05325cefd2ccaebb43cb59f96b9c443eed4c0c8490fa6a4ece5dfe0db193d8b3`.

That capture completed successfully and persisted the canonical result before
printing its summary:

- result path: `/private/tmp/event-card-callers-capture-7f813682e42542f992c82401/result.json`;
- result: 38,094 bytes, mode `0600`, SHA-256 `c6340b67d61bd01f447bd4bad320e3ef26abf323a04b1db51f4a0050dc245f6e`;
- stderr: zero bytes, mode `0600`, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- summary: 174 bytes, mode `0600`, SHA-256 `944d5cfb0d27babdcad38da1c111356ad661876ec2ac170796810778dd1202a3`;
- containing directory: mode `0700`.

The persisted result has the exact accepted schema and aggregate counts, 76
sorted allowlisted rows, 33 event types with positive rows, and 52 attributed
source/body methods with positive rows. These remain positive direct or
attribute-bound state-machine facts. Display-class lambdas, arbitrary callees
and inherited bodies remain outside the census, so the result does not support
negative event-level or caller-level claims.
