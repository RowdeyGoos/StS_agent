# Phase 0 Profile-Local Recovery-Unit Metadata Request

- **Status:** awaiting explicit approval; not executed
- **Approval ID:** `PF-D1C-RECOVERY-UNIT-METADATA-V1`
- **Logical target:** `project_test_profile`
- **Parent result:**
  [`PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md`](research/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md)
- **Target build:** Steam default/main build `23811903`, packaged release
  `v0.107.1`
- **Access level:** fixed-allowlist profile-local shallow metadata only
- **Expected writes:** none

This request proposes the smallest next boundary check after D1B. It is not
authorized merely because it is documented. The D1 or D1B approvals authorize
nothing here.

D1B established that the current direct children of `saves/` match the required
core roles plus the two predicted backup-sidecar roles. For privacy and approval
clarity, the project chooses one final metadata-only checkpoint before asking
for any byte read: determine whether `saves/` is the only direct child of the
dedicated profile root and whether `history/` is empty. A later byte-level
request could instead embed the same predicate as its mandatory preflight, but
it must not silently omit profile-local state.

A pass would define a **profile-local candidate recovery unit**, not a complete
recoverable profile or account:

```text
saves/
├── progress.save
├── prefs.save
├── progress.save.backup
├── prefs.save.backup
└── history/                     # required empty
```

The known single-player and multiplayer run-marker files must remain absent.

## 1. Required user confirmations

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

## 2. Exact proposed read scope

D1C newly proposes the previously reviewed root template:

```text
<MACOS_HOME>/Library/Application Support/SlayTheSpire2/steam/
```

Before filesystem access, the probe must inspect the process table only to
answer whether the exact Slay the Spire 2 executable is running. It retains no
process identifier, command line, environment, or information about other
processes. A running game stops the probe.

Allowed operations:

1. Open the known components from `<MACOS_HOME>` through `steam` one at a time
   using descriptor-relative no-follow directory operations.
2. List all immediate children of `steam` once, non-recursively; retain their
   names in process memory only. Count immediate children that are numeric
   no-follow directories and continue only when resolution is `unique`.
3. Bind `<DEDICATED_PROFILE_DIR>` from the physical slot named in the same
   approval and open it component by component with no-follow operations.
4. Open the fixed `saves` and `history` components with descriptor-relative
   no-follow directory operations, then keep the verified profile, `saves`, and
   `history` descriptors open for the entire probe.
5. Take **composite snapshot 1 end to end** in this exact order:

   1. Through the held profile descriptor, list immediate basenames. The only
      passing set is `saves`. Stop on the first other basename without
      classifying it; retain only
      `unexpected_profile_root_entry_present=true`. No-follow classify the
      allowlisted `saves` entry as a directory.
   2. Through the held `saves` descriptor, list direct basenames. Stop on the
      first basename outside the D1B allowlist without classifying it; retain
      only `unexpected_saves_entry_present=true`. If either known active-run
      basename appears, retain only `known_run_marker_absent=false` and stop
      without classifying it. No-follow classify the five expected roles. The
      only passing predicate is:

      - `progress.save` and `prefs.save` are regular files;
      - `progress.save.backup` and `prefs.save.backup` are regular files;
      - `history` is a directory;
      - `current_run.save` and `current_run_mp.save` are absent;
      - no other direct child exists.

      For the four regular-file roles, retain only
      `required_file_role_kind_match=true|false`; do not retain per-role facts,
      sizes, or file content.
   3. Create a fresh enumeration cursor from the held `history` descriptor and
      observe only whether one immediate child exists. The only passing
      predicate is `history_empty=true`. If any name appears, retain only
      `history_empty=false` and stop without retaining the name, counting
      further entries, or classifying/opening a child.

6. Only if snapshot 1 passes, take **composite snapshot 2 end to end** in the
   same profile root → `saves/` → `history/` order, using the same held directory
   descriptors and a newly created enumeration cursor at every level. Do not
   group the two profile-root reads, the two `saves/` reads, or the two history
   reads together.
7. Define each composite snapshot as:

   - the profile-root direct basename/kind projection;
   - the `saves/` direct basename/kind projection; and
   - the `history_empty=true` predicate.

8. Compare the two composite snapshots exactly through the same held
   descriptors. A difference stops the probe. A match does not prove file-byte
   stability or writer/Cloud quiescence.
9. Keep every raw account, profile-root, `saves/`, and `history/` basename only
    in process memory. For anything outside a passing allowlist, retain only the
    applicable presence boolean; never print, log, hash, count further entries,
    or persist its name.

## 3. Allowed durable output

- approval ID and target-build identity;
- `game_process_running=true|false`;
- `account_namespace_resolution = absent | unique | ambiguous`;
- `profile_mapping_confirmed=true` or sanitized failure;
- containment and symbolic-link result;
- `composite_shallow_repeat_match=true|false`;
- `profile_root_projection_match=true|false`;
- `saves_projection_match=true|false`;
- `required_file_role_kind_match=true|false`;
- `known_run_marker_absent=true|false`;
- `history_empty=true|false`;
- `unexpected_profile_root_entry_present=true|false` and
  `unexpected_saves_entry_present=true|false`;
- overall pass/stopped result and fixed sanitized reason code;
- confirmation that no contents, hashes, timestamps, Cloud APIs, other
  profiles, or writes were accessed.

On an early stop, persist only booleans actually evaluated before the stop.
Omit every unevaluated field; never synthesize `false` for a predicate the probe
did not reach.

Raw account/profile paths and pre-redaction names exist only in process memory
and are discarded at process exit. Raw OS error text containing a path or name
is converted to a fixed sanitized reason code before reporting.

The durable result remains protected until a redaction review passes. Only a
further sanitized summary may enter the repository, and no fixture metadata
becomes actor-visible state.

## 4. Explicit exclusions

This request does **not** include:

- contents, partial bytes, parsing, hashes, decoding, or decompression;
- timestamps, ownership, permissions, ACLs, extended attributes, or inode IDs;
- retention of any `history/` child basename, or classification, stat metadata,
  or contents of a child beyond the single ephemeral presence observation;
- account-scoped `profile.save`, `settings.save`, or any other account entry;
- any other profile slot or the `modded/` namespace;
- Steam `userdata`, Cloud-file enumeration, Remote Storage calls, or Cloud
  configuration changes;
- copying, destination creation, backup creation, restore testing, mutation,
  rename, deletion, quarantine, or permission changes;
- game launch, profile switching, run creation, bridge implementation,
  packaging, installation, or load;
- fallback search outside the exact approved boundary.

## 5. Stop conditions

Stop with a sanitized result if:

- any required precondition is uncertain;
- Slay the Spire 2 is running or the exact process check is unavailable;
- account resolution is absent or ambiguous;
- the protected profile mapping is missing or mismatched;
- any allowlisted component or shallow child is a symbolic link;
- the target leaves the descriptor-relative boundary;
- the profile root contains anything other than one real `saves` directory;
- the D1B allowlisted `saves/` basename/kind predicate no longer matches;
- `history/` contains any direct child;
- either composite snapshot changes;
- safe redaction cannot be guaranteed.

Do not inspect an unexpected entry, broaden the search, or access content to
explain a mismatch.

## 6. Result and next gate

A pass would establish only that the current profile-local candidate recovery
unit has the exact shallow shape above and that `history/` is empty at the probe
boundary. It would still not establish:

- primary/backup byte equality, validity, or recoverability;
- content stability or a complete serialization schema;
- account-level profile selection or settings recovery;
- coverage of account-scoped, modded, Steam, or Cloud state;
- logical unlock/settings state or clean campaign readiness;
- a golden snapshot, independent backup, restore path, or reset procedure.

An unexpected profile-root or history entry may be legitimate conditional
profile-local state; D1C would stop and require a revised boundary rather than
labeling the profile corrupted.

If D1C passes, the next byte-level proposal can bind to this reviewed candidate
boundary. It must still re-run the same fail-closed metadata predicate
immediately before byte access. If D1C is skipped, that predicate must instead
be embedded in the later request's preflight. Cloud containment and full-byte
hashing remain separate approval scopes. Hashing, copying, parsing, Cloud
changes, restore tests, and game launch are independent authorization units;
D1C cannot be reused for any of them.
