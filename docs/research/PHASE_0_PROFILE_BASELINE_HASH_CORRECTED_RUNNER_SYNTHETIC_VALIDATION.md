# Phase 0 Corrected Fingerprint-Runner Synthetic Validation

- **Validation date:** 2026-08-29
- **Result:** corrected mechanics passed disposable synthetic validation; no
  real-profile execution authorized
- **Bound request SHA-256:**
  `366e08638475e0e6b41926c6fc6422c8e28908f71038206d3484846f54a4da66`
- **Real user-data access:** none
- **Real process-table access:** none
- **Repository code changes:** none; the harness and fixtures were temporary

This validation checks the corrected runner mechanics after
[`attempt 1`](PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md) used the wrong
fixed profile-component construction. It is synthetic evidence only. It does
not inspect, fingerprint, or authorize access to the real dedicated profile.

## 1. Disposable fixture

The automatically cleaned temporary tree contained:

- one numeric synthetic account namespace;
- the valid `profile<slot>/saves/` boundary;
- a complete bare-number directory as a trap;
- the four exact-size allowlisted synthetic files;
- an empty `history/` directory.

The corrected constructor accepted only canonical ASCII numeric input and
produced exactly `profile` plus that input. Instrumented relative opens confirmed
that the valid component was opened and the bare-number trap was never opened.

## 2. Success-path checks

All 20 success assertions passed:

| Check | Result |
| --- | ---: |
| Complete candidate-boundary snapshots | 4 (`A1`, `A2`, `B`, `C`) |
| Injected endpoint process checks | 2 |
| Target-file opens | 8 in the exact pass-A/pass-B role order |
| Content-read calls | 8 |
| Authorized bytes requested | 210,004 |
| Bytes returned | 210,004 |
| Byte-ceiling violations | 0 |
| Extra EOF-probe reads | 0 |
| Bare-number trap opens | 0 |

The fixed output role order, exact canonical fingerprint object, RFC 8785/JCS
bytes for the restricted value types, domain separator, and aggregate SHA-256
construction were independently reproduced.

## 3. Fail-closed injections

Seven synthetic failure families were exercised:

1. noncanonical/raw-slot component construction before lookup;
2. symbolic-link target;
3. unexpected `saves/` entry;
4. nonempty `history/`;
5. pre-read size mismatch;
6. post-read size change;
7. pass-A/pass-B digest mismatch.

Every stopped result used the restricted stopped-result union and omitted all
per-file sizes, digests, role records, equality results, canonical bytes, and
aggregate fingerprints.

## 4. Bookkeeping defect found and corrected

Review of the first ephemeral harness run found that its synthetic state marker
advanced to `partial` only after a role completed. That would incorrectly label
a post-read size failure as `content_access_stage=none` even though a content
read had occurred.

The harness was corrected to set `pass_a_partial` or `pass_b_partial`
immediately **before** the first content-read call in that pass and to promote
to `*_complete` only after all four roles complete. Focused post-read-size and
read-error regressions then passed `2/2`, each returning `partial`, never
`none`.

The corrected real invocation must retain this exact marker ordering. The
attempt-1 runner already set the partial marker before each read; the only
real-profile defect diagnosed from attempt 1 was its fixed profile-component
construction.

## 5. Authorization boundary

This synthetic validation does not reuse or extend the consumed attempt-1
approval. It does not authorize:

- a real PF-HASH invocation;
- another profile, path search, or fallback component;
- parsing, copying, Cloud access/change, restore, launch, or bridge work.

One corrected real invocation still requires fresh explicit approval of the
unchanged request hash and all six immediate user confirmations.
