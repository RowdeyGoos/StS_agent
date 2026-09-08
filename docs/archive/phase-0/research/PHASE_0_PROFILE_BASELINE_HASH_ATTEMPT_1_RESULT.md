# Phase 0 Baseline-Fingerprint Attempt 1 Result

- **Status:** stopped fail-closed before any target-content read
- **Execution date:** 2026-08-29
- **Approval ID:** `PF-HASH-BASELINE-V1`
- **Approved-scope SHA-256:**
  `366e08638475e0e6b41926c6fc6422c8e28908f71038206d3484846f54a4da66`
- **Scope-review SHA-256:**
  `92ad4c9d1be9438d19e360d34b9d24e9f6d86a3ea454a31cc23f5a81d7391b3a`
- **Logical target:** `project_test_profile`
- **Target build:** Steam default/main build `23811903`, packaged release
  `v0.107.1`

The exact approved scope is preserved in
[`PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md`](../PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md).
Its pre-execution status remains unchanged so the reviewed and user-approved
hash stays reproducible.

No physical profile number, account namespace, absolute resolved path, raw
basename enumeration, process identifier, raw operating-system error, file
size, content digest, aggregate fingerprint, or raw command output is retained
here.

## 1. Sanitized protected result

| Field | Result |
| --- | --- |
| Result schema | `sts2_profile_baseline_hash_result_v1` |
| Status | `stopped` |
| Reason | `BOUNDARY_OPEN_FAILED` |
| Content-access stage | `none` |
| Initial game-process check | `game_process_running=false` |
| Account namespace resolution | `unique` |
| Excluded operations honored | `true` |
| Target-build manifest | `sts2-steam-main-build-23811903-macos-universal` |
| Target-build identity payload | `a0f7f8f57621122e4c246372115783909f4bb97f4b4eb7e57340428143d4c4cf` |

`content_access_stage=none` means no target content-read call was issued. It
does **not** mean that no filesystem metadata was accessed: the approved Steam
root was traversed and one numeric account namespace was resolved before the
stop.

The attempt stopped before:

- opening the actual dedicated-profile boundary;
- snapshot A1 or any later candidate-boundary snapshot;
- opening or sizing any target save file;
- reading, hashing, parsing, copying, or writing any target content;
- constructing a per-file or aggregate fingerprint;
- the final game-process check.

## 2. Cause and protocol deviation

The runner incorrectly used the protected numeric slot itself as the
account-relative directory component. The frozen static path contract defines
the component as `profile<DEDICATED_PROFILE_NUMBER>`. The attempted component
therefore could not open and the runner returned the sanitized boundary error.

This is an implementation defect, not evidence that the dedicated profile is
absent, damaged, or outside the previously confirmed mapping. The attempt was
fail-closed and honored the request's content, write, Cloud, other-profile,
fallback-search, launch, and bridge exclusions. It did not, however, implement
the approved positive path binding correctly and therefore supplies no
fingerprint or candidate-boundary evidence.

No fallback search, alternate profile-component attempt, or automatic rerun
occurred.

## 3. Corrective disposition

The reviewed request and its hash remain unchanged. Before any corrected
invocation, the runner must:

1. construct the protected profile component exactly as `profile` plus the
   canonical ASCII numeric slot bound in the same approval;
2. reject any other construction before a filesystem lookup;
3. preserve the descriptor-relative no-follow traversal, four boundary
   snapshots, fixed role/size vector, hard byte ceiling, result union, and all
   exclusions from the approved request.

This correction narrows the implementation to the already reviewed path
contract; it does not authorize a broader search or change the access scope.

The first approval was consumed by this stopped invocation. A corrected
invocation requires fresh explicit approval of the same request ID and SHA-256,
plus all six immediate user confirmations. It authorizes exactly one new
attempt and no further retry.
