# Phase 0 Backup-Sidecar Metadata Confirmation Request

- **Status:** awaiting explicit approval; not executed
- **Approval ID:** `PF-D1B-BACKUP-SIDECARS-V1`
- **Logical target:** `project_test_profile`
- **Parent result:**
  [`PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md`](research/PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md)
- **Target build:** Steam default/main build `23811903`, packaged release
  `v0.107.1`
- **Access level:** fixed-allowlist shallow filesystem metadata only
- **Expected writes:** none

This request proposes one small follow-up to the completed D1 boundary probe.
It is not authorized merely because it is documented.

Two direct entries appeared in both permitted D1 snapshots, and their names
were deliberately not retained. Static inspection of the exact pinned game
predicts two normal local recovery-sidecar roles in this situation:

```text
progress.save.backup
prefs.save.backup
```

This probe asks only whether the **current** shallow direct-child projection is
the previously known core set plus exactly that fixed pair, with no active-run
marker or other entry. Because D1 and D1B occur at different times, a pass would
be compatible with the earlier redacted pair but would not prove filesystem-
object identity across the two probes. It does not read contents or establish
that either backup is valid.

## 1. Static evidence and hypothesis

This hypothesis comes from read-only static type/member and method-body
inspection of the pinned arm64 `sts2.dll` plus its API XML. Their exact SHA-256
values are recorded in the
[`game-build manifest`](../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json):
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`
and `940ccc0cd6c2be3d75ae831a1b91a3375de571d94fdf896f45b26761148eccce`,
respectively. No game code or profile data was executed to derive it.

In those pinned artifacts:

- the progress and preferences managers write `progress.save` and `prefs.save`;
- the byte-oriented save-write path reaches `CopyBackup` before replacing an
  existing primary;
- `CopyBackup` appends `.backup` when a prior primary exists;
- migration loading can fall back to `.backup`;
- the pinned game's `CloudSaveStore` file-selection filter excludes `.backup`
  files. This does not prove behavior of every Steam or Auto-Cloud mechanism.

Other sidecars are conditional:

- active-run backups require corresponding active-run rewrites;
- `.tmp` and `.backup.tmp` are staging/crash artifacts rather than expected
  steady-state children;
- corruption preservation can create `.corrupt`-derived files.

Therefore the observed count of two is compatible with the normal progress and
preferences backup pair, but static evidence cannot prove the observed names.

## 2. Required user confirmations

Immediately before execution, the user must confirm:

1. the same physical dedicated profile is still the target and explicitly bind
   it in the approval;
2. Slay the Spire 2 remains fully closed;
3. no single-player or multiplayer run has been started or resumed;
4. Steam still shows Cloud `Up to Date` and idle;
5. Cloud settings remain unchanged;
6. the game will remain closed during the probe.

The physical profile number remains in the noncommitted approval/execution
context. The durable result records only `profile_mapping_confirmed=true`.

## 3. Exact proposed read scope

The prior D1 approval authorizes nothing in this request. D1B newly proposes the
same root template and descriptor-relative no-follow traversal:

```text
<MACOS_HOME>/Library/Application Support/SlayTheSpire2/steam/
```

Before filesystem access, the probe may inspect the process table only to
answer whether the exact Slay the Spire 2 executable is running. It does not
retain command lines, environment variables, or information about other
processes; the durable result is only `game_process_running=true|false`. A
running game stops the probe.

Allowed operations:

1. Open the known components from `<MACOS_HOME>` through `steam` one at a time,
   rejecting symbolic links.
2. List all immediate children of `steam` once, non-recursively; retain their
   names in process memory only. Count the immediate children that are numeric
   no-follow directories and continue only when that resolution is `unique`.
3. Bind `<DEDICATED_PROFILE_DIR>` from the physical slot named in the same
   approval, then open its `saves` directory component by component with
   no-follow operations.
4. Keep the verified `saves` directory descriptor open. Through that same
   descriptor, create exactly two snapshots: one initial and one final repeat.
   Each snapshot lists all direct children non-recursively and performs a
   descriptor-relative no-follow type check on every child solely to reject
   symbolic links and validate the required kinds.
5. Retain raw basenames in process memory only and compare them against this
   complete allowlist:

   ```text
   progress.save
   prefs.save
   history
   current_run.save
   current_run_mp.save
   progress.save.backup
   prefs.save.backup
   ```

6. Define the only passing direct-child projection as:

   - `progress.save` and `prefs.save` are present regular files;
   - `history` is a present directory and is not enumerated;
   - `current_run.save` and `current_run_mp.save` are absent;
   - `progress.save.backup` and `prefs.save.backup` are present regular files;
   - no entry exists outside the complete allowlist.

7. For the two `.backup` roles, collect existence, no-follow type, and byte
   size. For core and run-marker roles, retain only the presence/absence and
   type facts needed to evaluate the passing projection; do not retain their
   sizes.
8. For any entry outside the complete allowlist, retain only a redacted count;
   do not print, log, hash, or persist its name.
9. Define each snapshot as the complete logical basename-set, no-follow kind,
   and backup-size projection above. Compare those two projections exactly. A
   difference stops the probe; a match does not prove content stability.

## 4. Allowed durable output

- approval ID and target-build identity;
- `game_process_running=true|false`;
- `account_namespace_resolution = absent | unique | ambiguous`;
- `profile_mapping_confirmed=true` or sanitized failure;
- containment and symbolic-link result;
- `shallow_metadata_repeat_match=true|false`;
- `required_core_role_set_match=true|false`;
- `known_run_marker_absent=true|false`;
- `expected_backup_sidecar_set_match=true|false`;
- `complete_allowlisted_projection_match=true|false`;
- logical existence/type/size for `progress_backup` and
  `preferences_backup`;
- redacted count of entries outside the complete allowlist;
- overall pass/stopped result and sanitized reason;
- confirmation that no contents, hashes, timestamps, Cloud APIs, other
  profiles, or writes were accessed.

Raw account/profile paths and pre-redaction names exist only in process memory
and are discarded at process exit. No raw enumeration output is retained.
Errors are converted to fixed sanitized reason codes before reporting; raw OS
error text containing a path or basename is neither logged nor persisted.

The durable probe result remains protected until a redaction review passes.
Only a further sanitized summary may be committed, and neither protected nor
sanitized fixture metadata becomes actor-visible state.

## 5. Explicit exclusions

This request does **not** include:

- contents or hashes of a primary, backup, or any other file;
- command lines, environments, or retained information about other processes;
- timestamps, ownership, permissions, ACLs, extended attributes, or inode IDs;
- enumeration inside `history/` or any other child directory;
- other profile slots or the `modded/` namespace;
- account-scoped `profile.save` or `settings.save`;
- Steam `userdata`, Cloud-file enumeration, or Remote Storage calls;
- copying, backup creation, restore testing, mutation, rename, deletion, or
  permission changes;
- game launch, bridge installation/load, profile switching, or run creation;
- fallback search outside the exact approved boundary.

## 6. Stop conditions

Stop with a sanitized result if:

- any required precondition is uncertain;
- Slay the Spire 2 is running;
- account resolution is absent or ambiguous;
- the physical profile mapping is missing or mismatched;
- any relevant component or shallow child is a symbolic link;
- the target leaves the approved descriptor-relative boundary;
- either shallow snapshot changes during the probe;
- an entry exists outside the complete allowlist;
- `progress.save` or `prefs.save` is absent or is not a regular file;
- `history` is absent or is not a directory;
- either known active-run marker is present;
- either predicted sidecar is absent or is not a regular file;
- safe redaction cannot be guaranteed.

Do not broaden the search or inspect content to explain a mismatch.

## 7. Result and next gate

A pass would establish that the current approved `saves/` direct-child
projection contains the statically predicted local recovery-sidecar pair and
no other entry. It would be compatible with—but would not prove temporal
identity with—the two entries counted by D1. It would still not establish:

- backup validity or equality with the primaries;
- a complete serialization/content schema;
- remote Cloud persistence or recovery behavior;
- a golden snapshot, reset procedure, or permission to copy;
- logical unlock state or clean campaign readiness.

Only after this current shallow metadata classification passes, or any mismatch
is explicitly resolved, may the project present a separate content/copy
proposal for a recoverable local golden. D1B would not cover account-scoped
files, history contents, modded state, or Cloud recovery. This approval cannot
be reused for any later step.
