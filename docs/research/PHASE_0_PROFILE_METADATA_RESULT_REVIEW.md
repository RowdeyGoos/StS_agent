# Phase 0 Profile-Metadata Result and D1B Scope Review

- **Review date:** 2026-08-29
- **Result:** D1 result is repository-safe; at review time D1B was safe to
  present for a new exact approval
- **Review type:** independent result/contract/static-evidence/privacy review;
  no additional user-data access

Historical note: D1B was subsequently approved and executed within the exact
reviewed scope. Its outcome is recorded in the
[`sanitized D1B result`](PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md).
The original D1B request remains unchanged so its approved hash stays
reproducible.

## Reviewed artifacts

| Artifact | SHA-256 | Result |
| --- | --- | --- |
| [`PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md`](PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md) | `8d6e3ca05f9cbd661b4233fb1dee33698c79643cd252b36330a2fe1190c14e5e` | Sanitized D1 result and caveats are conservative and repository-safe |
| [`PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_REQUEST.md`](../PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_REQUEST.md) | `adf968fb0bec15800f3f25969d7be1f2040941a6580b8f18800934b708c7d69d` | Safe to present at review time; subsequently approved and executed within that scope |

The original D1 request remains unchanged at its approved SHA-256,
`ad568f8441567ab532d7fa5219c5e1d4759bfae52069c15c44ad17ac3f3e214f`.
Any substantive change to either artifact above invalidates this sign-off and
requires a focused review with a new hash.

## Independent review outcomes

### D1 result and privacy boundary

The reviewers checked the execution caveats, allowed durable fields, claim
strength, protected identifiers, path disclosure, Cloud wording, and gate
status. The accepted result:

- discloses the rejected out-of-protocol root-open attempt and the missing
  immediate process recheck without claiming either was stronger than it was;
- records only logical roles, object kinds, permitted sizes, categorical
  checks, and a redacted unexpected-entry count;
- contains no physical profile slot, account namespace, absolute resolved
  user-data path, unexpected basename, or raw output;
- does not claim content stability, complete clean state, recoverability,
  unlock readiness, Cloud persistence, passivity, or permission for later work;
- preserves the exact parent approval hash instead of rewriting the historical
  request.

### Static sidecar hypothesis

The reviewers checked the hypothesis against the exact pinned managed assembly
and API XML hashes in the build manifest. The evidence supports these limited
claims:

- the save-write path can create `.backup` recovery sidecars before replacing
  existing primary files;
- migration loading can use a backup fallback;
- the pinned game's `CloudSaveStore` filter excludes `.backup` files, without
  implying universal Steam or Auto-Cloud behavior;
- the predicted progress/preferences backup pair is compatible with the two
  entries counted by D1, but static evidence cannot establish their names or
  filesystem-object continuity.

### D1B contract and race boundary

The accepted request now makes the only passing current shallow projection
explicit:

- `progress.save` and `prefs.save` are regular files;
- `history` is a directory and remains unenumerated;
- both known active-run markers are absent;
- both predicted backup sidecars are regular files;
- no other direct child exists;
- two complete basename/kind/backup-size projections taken through the same
  held no-follow directory descriptor are identical.

Every other state stops with a sanitized reason. Raw names stay in process
memory, raw path-bearing errors are not retained, the probe result remains
protected until redaction review, and only a sanitized summary may enter the
repository. Nothing becomes actor-visible state.

## What this review does not authorize or prove

At review time, this record did not authorize:

- D1B execution or any other profile/user-data access;
- contents, hashes, timestamps, copying, backup creation, mutation, restore, or
  Cloud API access;
- other profiles, account-scoped files, `modded/`, or history enumeration;
- game launch, bridge implementation, packaging, installation, or load.

At review time, D1B still required all immediate preconditions, the protected
physical-profile binding, and explicit user approval of the exact reviewed
artifact. Those were subsequently supplied for D1B only. This historical
review and the completed D1B approval authorize no later scope.
