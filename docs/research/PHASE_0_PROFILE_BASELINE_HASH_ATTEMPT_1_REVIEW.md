# Phase 0 Baseline-Fingerprint Attempt 1 Review

- **Review date:** 2026-08-29
- **Result:** sanitized stopped result accepted; corrected rerun requires fresh
  explicit approval
- **Review type:** independent execution-stage, schema, static-path, privacy,
  claim-boundary, and authorization review; no additional profile access

## Reviewed artifacts

| Artifact | SHA-256 | Result |
| --- | --- | --- |
| [`PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md`](../PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md) | `366e08638475e0e6b41926c6fc6422c8e28908f71038206d3484846f54a4da66` | Exact frozen scope remains unchanged |
| [`PHASE_0_PROFILE_BASELINE_HASH_SCOPE_REVIEW.md`](PHASE_0_PROFILE_BASELINE_HASH_SCOPE_REVIEW.md) | `92ad4c9d1be9438d19e360d34b9d24e9f6d86a3ea454a31cc23f5a81d7391b3a` | Original scope sign-off remains valid |
| [`PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md`](PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md) | `5e7d3afe8efe2478f168afd7ec811202377cdde4a20bf5d21f6d3a0cec65a229` | Accurate, privacy-preserving disclosure of the fail-closed stopped invocation |
| [`PHASE_0_PROFILE_BASELINE_HASH_CORRECTED_RUNNER_SYNTHETIC_VALIDATION.md`](PHASE_0_PROFILE_BASELINE_HASH_CORRECTED_RUNNER_SYNTHETIC_VALIDATION.md) | `0819e4e1adad1e1d9ce5e7aace423ff8ea019e590b9745dc6dfaf0b0d2bebb58` | Corrected binding, full success mechanics, byte ceiling, canonicalization, and seven fail-closed families validated without real-profile access |

Any substantive change to the result invalidates its result-review sign-off and
requires a new hash-bound review. The frozen request and scope-review files must
not be edited to make the execution history look successful.

## Independent review outcomes

Three independent lanes agree:

1. **Execution and schema:** the protected result had every required common
   identity field, `status=stopped`, `content_access_stage=none`,
   `reason_code=BOUNDARY_OPEN_FAILED`, the two permitted evaluated fields, and
   no content-derived field.
2. **Pinned-build path mapping:** static IL and XML evidence confirm that the UI
   supplies a one-based profile ID unchanged and
   `UserDataPathProvider.GetProfileDir` constructs `profile` plus that integer.
   A bare numeric component is not the pinned-build vanilla mapping.
3. **Authorization:** the stopped call consumed its one-invocation approval.
   The unchanged request may be presented again only for one fresh corrected
   invocation with all six immediate confirmations; no automatic or unattended
   retry is authorized.

The result correctly distinguishes **no target-content read** from **no
filesystem access**. The approved Steam root and account-namespace metadata were
accessed before the stop, so the latter claim would be false.

## Failure classification

The failure occurred at Section 3.1 step 3, while opening the fixed
dedicated-profile component. It was before:

- the actual dedicated-profile boundary;
- snapshot A1;
- any target-file open or size check;
- any content read, hash, canonical record, or aggregate fingerprint.

The runner bound the protected numeric slot directly rather than constructing
the reviewed `profile<number>` component. This is a project implementation
defect, not evidence that the profile is absent, damaged, or inconsistent with
D1/D1B.

`excluded_operations_confirmed=true` remains accurate for the request's Section
5 exclusions: there was no other-profile access, fallback search, content read,
parse, copy, write, Cloud access/change, launch, or bridge operation. It is not
evidence that the positive path semantics were implemented correctly.

## Required correction before reapproval

Before presenting a corrected invocation, the runner must:

- construct exactly `profile` plus the canonical ASCII numeric slot;
- reject any other construction before filesystem lookup;
- retain the pre-read `partial` marker ordering validated by the
  [disposable synthetic suite](PHASE_0_PROFILE_BASELINE_HASH_CORRECTED_RUNNER_SYNTHETIC_VALIDATION.md);
- preserve every reviewed no-follow, snapshot, byte-cap, output, cleanup, and
  exclusion rule unchanged.

The narrow correction does not require a new scope hash if it changes only the
implementation to match the existing contract. Any broader enumeration,
fallback search, alternate component attempt, output change, or access semantic
would require a revised request and new independent review.

## What this review does not authorize

This record does not authorize:

- a corrected PF-HASH invocation or another profile attempt;
- parsing, copying, Cloud activity, restore, launch, or bridge work;
- repository retention or publication of a future per-file or aggregate
  fingerprint;
- treating attempt 1 as candidate-boundary or fingerprint evidence.
