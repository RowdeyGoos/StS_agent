# Phase 0 Baseline-Fingerprint Scope Review

- **Review date:** 2026-08-29
- **Result:** safe to present for one new exact approval; not authorized or
  executed
- **Review type:** independent authorization, byte-bound, race/claim,
  canonicalization, result-schema, and privacy review; no user-data access

## Reviewed artifact

| Artifact | SHA-256 | Result |
| --- | --- | --- |
| [`PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md`](../PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md) | `366e08638475e0e6b41926c6fc6422c8e28908f71038206d3484846f54a4da66` | Bounded, fail-closed, implementable, privacy-preserving, and safe to present for explicit approval |

Any substantive change invalidates these sign-offs and requires a focused
review with a new hash.

## Selection and authorization state

D1C was reviewed, deliberately unselected/skipped, and never executed; its
fail-closed predicate is incorporated into PF-HASH. The preserved D1C request
and review remain immutable historical alternatives:

- D1C request SHA-256:
  `d7f865d9d2c9c3811962da40b2a84d1d676d785aa3a2ec7584d0999695fb88a7`;
- D1C review SHA-256:
  `740114ee22e75bc9b59245c78e4b13263b1e285f12ded2bab67373158a3e93bf`.

This review does not authorize PF-HASH execution. D1, D1B, D1C review, and the
general project mandate cannot be reused as byte-read consent. Each PF-HASH
invocation requires the request's immediate confirmations and one explicit
approval binding the exact reviewed request, physical dedicated profile, and
closed-game conditions. It does not authorize unattended or automatic reruns.

## Independent review outcomes

Three independent review lanes signed off on the exact artifact:

1. **Profile-boundary and privacy review:** verified the D1/D1B size evidence,
   no-follow fixed-role scope, hard byte ceiling, zero-retry rule, protected
   retention, and stopped-result exclusions.
2. **Bridge-contract and race review:** verified the honest path-scoped content
   contract, A1/A2/B/C sequencing, fresh-open samples, append-race bound, final
   process bracket, fixed result union, finite reason codes, and narrow claims.
3. **Accelerated gate-composition review:** verified that embedding two complete
   matching D1C snapshots before the first candidate-file open preserves the
   skipped gate's fail-closed promise and that all later operations remain
   separately approval-gated.

The accepted request:

- requires two matching complete boundary snapshots before a candidate regular
  file is opened, sized, or read;
- holds the same profile, `saves`, and `history` directory descriptors and uses
  descriptor-relative no-follow traversal with fresh enumeration cursors;
- reads only four allowlisted roles at the exact previously observed sizes;
- caps every read request to the remaining authorized count, issues no extra
  EOF-probe read, and permits at most 210,004 target-content bytes across both
  passes;
- permits one fresh-open read per role per pass, with no retry, recovery read,
  or third pass;
- takes another complete boundary snapshot after each pass and brackets the
  operation with two exact game-process checks;
- accepts a role only when both exact-size SHA-256 samples match;
- creates the aggregate only after every pass condition and the final process
  check succeeds, using RFC 8785 JCS and the frozen domain separator;
- emits one fixed versioned protected result shape and discards every
  content-derived field on a stopped attempt;
- binds the target build by both manifest ID and stable identity-payload hash;
- reads without parsing, copying, decoding, displaying, or writing any save
  content.

## Claim boundary

A pass would show only that the four allowlisted paths yielded matching exact
sizes and SHA-256 values in two fresh-open samples. It would not prove:

- file-object continuity, hard-link isolation, path currency at result
  completion, or absence of an identical-byte replacement;
- writer or Steam Cloud quiescence;
- an atomic or semantically coherent four-file save snapshot;
- semantic validity, unlock/settings state, completeness, or recoverability;
- account-scoped or modded-namespace coverage;
- primary/backup equality as a pass condition;
- that the installed game build was revalidated by this profile probe.

## What this review does not authorize

This record does not authorize:

- PF-HASH execution, another profile attempt, or any user-data access;
- parsing, decoding, content display, copying, backup, restore, or mutation;
- Cloud or Remote Storage access, configuration changes, or conflict handling;
- game launch, profile switching, run creation, or controlled delta capture;
- bridge implementation, packaging, installation, load, or control;
- publication or repository retention of per-file or aggregate fingerprints.

Copying, optional parsing of an offline copy, Cloud containment, restore,
launch, and bridge work require distinct immutable requests and distinct
approval IDs.
