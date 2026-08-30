# Phase 0 Profile Baseline Fingerprint Request

- **Status:** awaiting explicit approval; not executed
- **Approval ID:** `PF-HASH-BASELINE-V1`
- **Logical target:** `project_test_profile`
- **Parent result:**
  [`PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md`](research/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md)
- **Embedded preflight:** the candidate-boundary predicate from the reviewed but
  unexecuted
  [`PF-D1C-RECOVERY-UNIT-METADATA-V1`](PHASE_0_PROFILE_RECOVERY_UNIT_METADATA_REQUEST.md)
- **Target build:** Steam default/main build `23811903`, packaged release
  `v0.107.1`
- **Access level:** fixed-boundary full-byte reads for cryptographic hashing;
  no parsing or copying
- **Expected filesystem writes:** none

This request replaces a standalone D1C execution with one consolidated
read-only fingerprint step. Two matching metadata snapshots run as the
mandatory preflight before any file is opened, followed by one snapshot after
each of two full-byte hash passes. This saves one approval round without
weakening the candidate-boundary check.

Approval of this exact request authorizes both the embedded metadata preflight
and the two fixed-boundary full-byte hash reads described below. It authorizes
neither parsing nor any operation listed in Section 5.

No earlier approval authorizes this request. In particular, D1, D1B, and the
reviewed D1C alternative do not authorize byte reads or hashing.

## 1. Goal and exact candidate unit

The request asks whether four allowlisted profile-local byte streams produce
the same role, exact size, and SHA-256 in two separate fresh-open samples:

```text
saves/
├── progress.save
├── prefs.save
├── progress.save.backup
├── prefs.save.backup
└── history/                     # required empty
```

The dedicated profile root must contain only `saves/`. Both known active-run
markers must be absent. Any other profile-root, `saves/`, or `history/` entry
in either preflight snapshot stops the request before hashing. A later boundary
failure stops the request and discards all transient fingerprint material.

This is a path-scoped content contract, not an object-continuity or atomic
snapshot contract. An identical-byte replacement is deliberately treated as
content-equivalent. The result cannot prove file-object continuity, writer
quiescence, hard-link isolation, cross-file atomicity or semantic coherence, or
that the sampled bytes still name the paths when the result is accepted.

## 2. Required user confirmations

Immediately before execution, the user must confirm:

1. the same physical dedicated profile is still the target and explicitly bind
   it in the approval;
2. Slay the Spire 2 is fully closed;
3. no single-player or multiplayer run has been started or resumed;
4. Steam shows Cloud `Up to Date` and idle;
5. Cloud settings remain unchanged;
6. the game will remain closed during the probe.

The physical profile number remains in the noncommitted approval/execution
context. The durable result records only `profile_mapping_confirmed=true`.

## 3. Exact proposed read scope

Approved root template if the user authorizes this request:

```text
<MACOS_HOME>/Library/Application Support/SlayTheSpire2/steam/
```

Before filesystem access, the probe must inspect the process table only to
answer whether the exact Slay the Spire 2 executable is running. It retains no
process identifier, command line, environment, or information about other
processes. A running game or unavailable process check stops the probe.

### 3.1 Resolve and hold the boundary

1. Open the known components from `<MACOS_HOME>` through `steam` one at a time
   using descriptor-relative no-follow directory operations.
2. List all immediate children of `steam` once, non-recursively; keep names in
   process memory only. Count immediate children that are numeric no-follow
   directories and continue only when resolution is `unique`.
3. Bind `<DEDICATED_PROFILE_DIR>` from the physical slot named in the same
   approval. Open and hold the profile, `saves`, and `history` directories with
   descriptor-relative no-follow operations.

### 3.2 Candidate-boundary snapshot

Each candidate-boundary snapshot runs end to end in this order through the held
descriptors and fresh enumeration cursors:

1. **Profile root:** require the only immediate basename to be `saves`; stop on
   the first other basename without classifying or retaining it. Confirm the
   allowlisted `saves` role is a no-follow directory.
2. **`saves/`:** require exactly the five roles in Section 1. Stop on the first
   outside basename without classifying or retaining it. Stop on either known
   active-run basename without classifying it. Confirm the four file roles are
   no-follow regular files and `history` is a no-follow directory.
3. **`history/`:** create a fresh enumeration cursor and observe only whether
   one immediate child exists. Require empty. If a name appears, stop without
   retaining it, counting further entries, or accessing any child metadata or
   content.

Retain only aggregate predicate booleans from a snapshot. On early stop, omit
unevaluated fields rather than synthesizing `false`.

### 3.3 Two full-byte hash passes

Run this exact sequence while holding the same profile, `saves`, and `history`
directory descriptors throughout:

1. Candidate-boundary preflight snapshot A1.
2. Candidate-boundary preflight snapshot A2. Require A1 and A2 to satisfy the
   predicate and have identical aggregate projections. Do not open, size, or
   read any candidate file unless both snapshots pass.
3. Hash pass A over the four regular-file roles in this fixed order:

   1. `progress_primary` → `progress.save`
   2. `preferences_primary` → `prefs.save`
   3. `progress_backup` → `progress.save.backup`
   4. `preferences_backup` → `prefs.save.backup`

4. Candidate-boundary snapshot B.
5. Hash pass B over the same four roles in the same order, reopening every file
   through the held `saves` descriptor.
6. Candidate-boundary snapshot C.

For each role in each hash pass:

1. Open the fixed basename descriptor-relative with no-follow, read-only flags.
2. Verify from the opened descriptor that it is a regular file.
3. Record its byte size before reading and require this exact protected size
   vector from D1/D1B before any byte access for that role:

   | Logical role | Required size |
   | --- | ---: |
   | `progress_primary` | 52,214 bytes |
   | `preferences_primary` | 287 bytes |
   | `progress_backup` | 52,214 bytes |
   | `preferences_backup` | 287 bytes |

   A different, negative, unrepresentable, or otherwise invalid size stops the
   request before that file's first byte read.
4. Set `remaining` to the role's exact authorized size. Every read request must
   be no larger than `remaining`; feed each returned byte exactly once into
   SHA-256 and subtract it with checked arithmetic. Do not decode, parse,
   decompress, log, or retain the bytes. A read call may legally return a chunk
   smaller than its request. A syscall-level interrupted-call continuation
   remains part of this same open and pass; it must not reopen or restart the
   file. EOF while `remaining > 0`, a read error, a zero-byte non-EOF result, or
   any counter invariant failure stops the request.
5. Once `remaining == 0`, issue no further content read—not even an extra read
   to test EOF. Require the descriptor's post-read size to remain exactly the
   authorized size, then close it. This makes the authorized size a hard read
   ceiling even if a writer appends during the sample.

Each logical role has a hard cap of one complete read in pass A and one complete
read in pass B. There is no automatic retry, recovery read, or third hash pass.
Any failed or changing read stops the request.

Pass only when:

- snapshots A1, A2, B, and C all satisfy the same candidate-boundary
  predicate;
- all four aggregate predicate projections are identical;
- for every logical role, pass-A and pass-B size and SHA-256 are identical;
- no early-stop condition occurred.

This detects size/count or digest differences observable in the two samples. It
does not prove that no adversarial, identical-byte, size-preserving, or
perfectly reverted replacement occurred, that no writer was active, or that the
four role samples were one atomic/coherent save state.

After snapshot C, repeat the exact game-process-presence check. Pass only when
it again reports `game_process_running=false`; an unavailable final check stops
the request. Run this check before accepting results or constructing canonical
fingerprint bytes. The two endpoint checks and the user's closed-game promise
do not exclude an undetected transient launch. Cloud `Up to Date` and idle is a
user-reported precondition only; this probe does not establish Steam-client or
Cloud-writer quiescence.

## 4. Fingerprint format and protected output

Only after every pass condition and the final process-absence check succeeds,
create `sts2_profile_physical_fingerprint_v1` from this exact typed, path-free
JSON object:

```json
{
  "canonicalization": "RFC8785-JCS",
  "hash_algorithm": "sha256",
  "history_empty": true,
  "known_run_marker_absent": true,
  "profile_root_projection_match": true,
  "required_file_role_kind_match": true,
  "roles": [
    {
      "logical_role": "preferences_backup",
      "sha256": "<64-lowercase-hex>",
      "size_bytes": 287
    },
    {
      "logical_role": "preferences_primary",
      "sha256": "<64-lowercase-hex>",
      "size_bytes": 287
    },
    {
      "logical_role": "progress_backup",
      "sha256": "<64-lowercase-hex>",
      "size_bytes": 52214
    },
    {
      "logical_role": "progress_primary",
      "sha256": "<64-lowercase-hex>",
      "size_bytes": 52214
    }
  ],
  "saves_projection_match": true,
  "schema": "sts2_profile_physical_fingerprint_v1",
  "target_build_identity_payload_sha256": "a0f7f8f57621122e4c246372115783909f4bb97f4b4eb7e57340428143d4c4cf",
  "target_build_manifest_id": "sts2-steam-main-build-23811903-macos-universal"
}
```

The four `<64-lowercase-hex>` tokens are construction placeholders, not literal
record values; replace each with that role's accepted common digest. Every
listed key is required and no additional key is permitted. JSON strings,
booleans, arrays, objects, and integers have their ordinary JSON types; every
`size_bytes` value is a nonnegative integer; no `null` or floating-point value
is permitted. Each role contains the one common size and lowercase 64-hex
digest accepted only after its pass-A and pass-B results match. The `roles`
array has exactly the four displayed records in displayed order, which is ASCII
order by `logical_role`.

Canonicalize the complete object with RFC 8785 JSON Canonicalization Scheme
(JCS), identified here as `RFC8785-JCS`. The displayed indentation is
explanatory only; the canonical bytes have no BOM or trailing newline. Compute
the aggregate physical fingerprint as exactly:

```text
SHA-256(
  ASCII("sts2_profile_physical_fingerprint_v1")
  || one 0x00 byte
  || RFC8785-JCS(object above)
)
```

The domain prefix, separator byte, and canonical JSON bytes are all part of the
aggregate input. The object deliberately excludes the approval ID, account,
physical profile, host, capture time, paths, evidence location, duplicate
pass-A/pass-B values, and primary-versus-backup comparison results.

### 4.1 Protected result channel

The only durable execution sink is the current task's protected structured tool
result channel. The probe emits exactly one sanitized JSON result and writes no
filesystem record. It emits no raw stdout/stderr, enumeration, path, byte,
traceback, or unsanitized OS error. If that protected channel cannot be
guaranteed, stop before byte reads.

The result is a discriminated union with schema
`sts2_profile_baseline_hash_result_v1`. Every result requires exactly these
common keys:

- `schema="sts2_profile_baseline_hash_result_v1"`;
- `approval_id="PF-HASH-BASELINE-V1"`;
- the exact `target_build_manifest_id` and
  `target_build_identity_payload_sha256` from the fingerprint record;
- `status`, exactly `passed` or `stopped`;
- `content_access_stage`, exactly one of `none`, `pass_a_partial`,
  `pass_a_complete`, `pass_b_partial`, or `pass_b_complete`;
- `reason_code`, from the finite enum below;
- `excluded_operations_confirmed`, a JSON boolean that is `true` only when all
  Section 5 exclusions were honored.

`content_access_stage=none` means no target content-read call was issued. A
`*_partial` value means at least one content-read call was issued in that pass
but not every role in it completed. A `*_complete` value means every role in
that pass completed; it makes no claim that a later snapshot, process check,
comparison, or canonicalization passed.

The complete reason-code enum is:

```text
OK
PRECONDITION_UNCONFIRMED
PROCESS_CHECK_UNAVAILABLE
GAME_RUNNING
PROTECTED_CHANNEL_UNAVAILABLE
ACCOUNT_NAMESPACE_NOT_UNIQUE
PROFILE_MAPPING_MISMATCH
BOUNDARY_OPEN_FAILED
CONTAINMENT_FAILED
SYMLINK_OR_KIND_MISMATCH
PROFILE_ROOT_PROJECTION_MISMATCH
SAVES_PROJECTION_MISMATCH
RUN_MARKER_PRESENT
HISTORY_NOT_EMPTY
BOUNDARY_SNAPSHOTS_DIFFER
TARGET_OPEN_FAILED
TARGET_SIZE_MISMATCH
TARGET_READ_FAILED
TARGET_EARLY_EOF
TARGET_COUNTER_INVARIANT_FAILED
TARGET_POST_SIZE_MISMATCH
ROLE_SAMPLE_MISMATCH
FINAL_PROCESS_CHECK_UNAVAILABLE
GAME_STARTED_DURING_PROBE
CANONICALIZATION_FAILED
SAFE_REDACTION_FAILED
INTERNAL_INVARIANT_FAILED
```

Raw operating-system errors map to this enum and are never emitted. `OK` is
valid only with `status=passed`; every other code is valid only with
`status=stopped`.

On `status=passed`, the result has `content_access_stage=pass_b_complete`,
`reason_code=OK` and `excluded_operations_confirmed=true`. It has exactly the
following complete shape and no other keys; digest tokens are construction
placeholders, and the displayed primary/backup equality values are examples:

```json
{
  "account_namespace_resolution": "unique",
  "approval_id": "PF-HASH-BASELINE-V1",
  "boundary_snapshots_match": true,
  "content_access_stage": "pass_b_complete",
  "descriptor_relative_containment": true,
  "domain_separated_aggregate_fingerprint_sha256": "<64-lowercase-hex>",
  "excluded_operations_confirmed": true,
  "final_game_process_running": false,
  "history_empty": true,
  "initial_game_process_running": false,
  "known_run_marker_absent": true,
  "preferences_primary_backup_digest_equal": false,
  "profile_mapping_confirmed": true,
  "profile_root_projection_match": true,
  "progress_primary_backup_digest_equal": false,
  "reason_code": "OK",
  "required_file_role_kind_match": true,
  "roles": [
    {
      "logical_role": "preferences_backup",
      "sha256": "<64-lowercase-hex>",
      "size_bytes": 287,
      "two_pass_match": true
    },
    {
      "logical_role": "preferences_primary",
      "sha256": "<64-lowercase-hex>",
      "size_bytes": 287,
      "two_pass_match": true
    },
    {
      "logical_role": "progress_backup",
      "sha256": "<64-lowercase-hex>",
      "size_bytes": 52214,
      "two_pass_match": true
    },
    {
      "logical_role": "progress_primary",
      "sha256": "<64-lowercase-hex>",
      "size_bytes": 52214,
      "two_pass_match": true
    }
  ],
  "saves_projection_match": true,
  "schema": "sts2_profile_baseline_hash_result_v1",
  "status": "passed",
  "symbolic_link_rejection": true,
  "target_build_identity_payload_sha256": "a0f7f8f57621122e4c246372115783909f4bb97f4b4eb7e57340428143d4c4cf",
  "target_build_manifest_id": "sts2-steam-main-build-23811903-macos-universal"
}
```

Replace each digest token with a JSON string and each displayed primary/backup
equality value with the actual JSON boolean. Primary/backup digest equality
does not affect pass status. The roles array is fixed in the displayed order.

On `status=stopped`, the only permitted additional key is `evaluated`, a JSON
object that may contain only the following keys, and only when that field was
fully evaluated:

```text
initial_game_process_running             boolean
final_game_process_running               boolean
account_namespace_resolution             "absent" | "ambiguous" | "unique"
profile_mapping_confirmed                 boolean
descriptor_relative_containment           boolean
symbolic_link_rejection                    boolean
profile_root_projection_match             boolean
saves_projection_match                    boolean
known_run_marker_absent                    boolean
required_file_role_kind_match              boolean
history_empty                              boolean
boundary_snapshots_match                   boolean
```

Omit `evaluated` when no listed field completed. No other top-level or
`evaluated` key is permitted. A stopped result can never contain a file size,
file digest, role record, primary/backup equality, canonical record, or
aggregate fingerprint.

On any early stop, boundary failure, open/read/counter error, size/hash mismatch,
canonicalization failure, or final process-check failure, stop immediately;
close every probe-opened target descriptor; and discard all transient file chunks,
digests, sizes, counters, hash contexts, and canonical-record bytes before
emitting. Do not continue to later roles, passes, snapshots, or canonicalization
merely to fill output, and never calculate or retain a partial aggregate.
Persist only fully evaluated non-content predicates, excluded-operation
booleans, and one fixed sanitized reason code; omit every unstarted, incomplete,
or content-derived role/pass/equality field.

Raw file chunks and hash/canonicalization buffers exist only in process memory
and are discarded at process exit. All accepted per-file and aggregate hashes
remain protected in the current task until independent privacy review. The
project creates no additional protected copy. Tool-channel retention follows
the host application's policy; if that boundary is unacceptable or unavailable,
stop before byte reads.

After review, a repository-safe summary may bind a fixture-candidate version to
the aggregate fingerprint only if the privacy review permits it. Per-file
digests remain protected by default. A later fingerprint supersedes rather than
silently overwrites the candidate version and records its lineage. No hash is
committed or published merely because this request passes. Raw account or
profile paths, physical slot, basenames outside the fixed allowlist, raw bytes,
and raw path-bearing errors are never retained.

Only a separately reviewed sanitized summary may enter the repository. Neither
hashes nor fixture metadata become actor-visible state.

## 5. Explicit exclusions

This request does **not** include:

- semantic parsing, decoding, decompression, deserialization, field extraction,
  or content display;
- retention, logging, or publication of raw file bytes;
- timestamps, ownership, permissions, ACLs, extended attributes, or inode IDs;
- hard-link or file-object isolation checks; no-follow rejects symbolic links
  but does not prove that an allowlisted regular file has no hard link outside
  the candidate boundary;
- retention or metadata/content access for any unexpected or `history/` child;
- account-scoped `profile.save`, `settings.save`, or another account entry;
- another profile slot, `modded/`, Steam `userdata`, or Remote Storage calls;
- Cloud-file enumeration, Cloud configuration changes, uploads, downloads, or
  conflict handling;
- file or directory creation, copying, backup, restore, mutation, rename,
  deletion, quarantine, permission changes, or destination access;
- game launch, profile switching, run creation, bridge implementation,
  packaging, installation, or load;
- fallback search outside the exact approved boundary.

## 6. Stop conditions

Stop with a sanitized reason and do not broaden scope if:

- any required precondition is uncertain;
- the game is running or the process check is unavailable;
- account resolution is absent or ambiguous;
- the protected profile mapping is missing or mismatched;
- an allowlisted component or role is a symbolic link or wrong kind;
- the target leaves the descriptor-relative boundary;
- an unexpected profile-root or `saves/` basename appears;
- a known active-run marker or any `history/` child appears;
- any candidate-boundary snapshot fails or differs;
- a file cannot be opened safely, changes size during a read, returns a read
  error or EOF before its exact authorized byte count, violates a counter
  invariant, or differs from its exact authorized size before or after reading;
- either role hash or size differs between pass A and pass B;
- canonicalization cannot be reproduced exactly;
- the final game-process check is unavailable or reports the game running;
- safe redaction or protected retention cannot be guaranteed.

Do not inspect an unexpected entry, retry or restart any failed or changing role
under this approval, access another profile/account namespace, or parse content
to explain a mismatch.

## 7. Result and next gate

A pass would establish only that the four allowlisted byte streams yielded the
same role, exact size, and SHA-256 in two separate fresh-open samples bound to
the named build-manifest/identity context and endpoint closed-game checks. This
profile probe does not revalidate the installed game build. It would not
establish:

- semantic validity, unlock/settings state, or clean campaign readiness;
- file-object continuity, path currency at result completion, hard-link
  isolation, writer quiescence, or an atomic/coherent four-file snapshot;
- primary/backup equivalence beyond byte hashes, or that the game can recover
  from either backup;
- account-level or modded-namespace completeness;
- Steam Cloud persistence, quiescence, conflict behavior, or recovery;
- a copied golden, independent backup, restore procedure, or working copy;
- permission for parsing, copying, Cloud changes, restore testing, game launch,
  or bridge work.

After a pass, raw local copying, semantic parsing of an offline copy, Cloud
containment, restore testing, and game launch remain distinct immutable
requests with distinct approval IDs. They may be previewed together in one
status update, but each decision and execution remains independently
selectable. This approval cannot be reused for any of them.
