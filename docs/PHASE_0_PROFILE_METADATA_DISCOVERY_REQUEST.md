# Phase 0 Dedicated-Profile Metadata Discovery Request

- **Status:** awaiting explicit approval; not executed
- **Approval ID:** `PF-D1-DEDICATED-METADATA-V1`
- **Logical target:** `project_test_profile`
- **Target build:** Steam default/main build `23811903`, packaged release
  `v0.107.1`
- **Build evidence:**
  [`sts2-steam-main-build-23811903-macos-universal.json`](../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)
- **Access level:** narrowly bounded filesystem metadata only
- **Expected writes:** none

This document states the complete proposed scope for the first filesystem look
at the dedicated project profile. Its existence does not authorize the probe.
The user must approve this exact scope after confirming the preconditions in
Section 3.

No game user-data root, profile, save, Steam account directory, or Cloud file
was accessed while preparing this request. The physical profile number provided
by the user is protected operational information. This repository uses:

```text
<DEDICATED_PROFILE_NUMBER> := protected numeric slot
<DEDICATED_PROFILE_DIR>    := profile<DEDICATED_PROFILE_NUMBER>
```

At execution, `<DEDICATED_PROFILE_NUMBER>` must be bound only from the physical
slot explicitly named in the same user approval. That mapping exists only in
the noncommitted approval/execution context. If the approval omits the slot, the
operational mapping is unavailable, or the expected directory does not match
that mapping, stop. The durable result records only
`profile_mapping_confirmed=true` or a sanitized failure, never the number or
directory name.

## 1. Why this probe is needed

Before any bridge is installed or loaded, the project must establish that:

- the new profile has a distinct local boundary;
- that boundary can be selected without scanning personal profiles;
- no active single-player or multiplayer run file is present;
- later backup, restore, and load/close-delta proposals can name an exact target;
- account and absolute-path identifiers can remain outside Git and actor data.

This probe cannot prove that the profile is recoverable, unlocked, synchronized
to Steam Cloud, or safe for a bridge load. It only resolves a local metadata
boundary. File-content inspection, copying, backup, launch, and Cloud behavior
are separate future approvals.

## 2. Static path evidence

The exact pinned game package and assembly establish the following path model:

```text
user://steam/<ACCOUNT_NAMESPACE>/<DEDICATED_PROFILE_DIR>/saves/
```

The packaged Godot settings select the custom user-data directory name
`SlayTheSpire2`. On macOS, Godot maps a custom user directory to
`<MACOS_HOME>/Library/Application Support/<custom-name>`. See the official
[Godot data-path documentation](https://docs.godotengine.org/en/4.5/tutorials/io/data_paths.html).

Traceability within the pinned artifacts:

- the packaged PCK settings
  `application/config/use_custom_user_dir` and
  `application/config/custom_user_dir_name` establish the custom directory;
- `UserDataPathProvider.GetPlatformDirectoryName`,
  `UserDataPathProvider.GetProfileDir`, and
  `UserDataPathProvider.GetProfileScopedBasePath` establish the Steam account
  and `profile<number>` path construction;
- the pinned assembly/XML metadata for progress, preferences, run history, and
  current-run persistence establishes the logical roles below.

The strongest static hypothesis for the approved discovery root is therefore:

```text
<MACOS_HOME>/Library/Application Support/SlayTheSpire2/steam/
```

Static metadata from the pinned build also identifies these logical roles:

```text
<ACCOUNT_NAMESPACE>/
├── profile.save                         # account-scoped
├── settings.save                        # account-scoped, local-only
└── <DEDICATED_PROFILE_DIR>/
    └── saves/
        ├── progress.save
        ├── prefs.save
        ├── history/
        ├── current_run.save             # conditional
        └── current_run_mp.save          # conditional
```

When the game regards itself as modded, it may instead use
`modded/<DEDICATED_PROFILE_DIR>`. That namespace is deliberately excluded from
this first probe because its provenance and loaded-mod relationship are not yet
known.

Static evidence predicts locations; it does not verify that the local machine
matches them. That is why this proposal fails closed instead of broadening its
search when the expected marker is missing or ambiguous.

## 3. Preconditions the user must confirm

All of these must be true immediately before execution:

1. Slay the Spire 2 is fully closed.
2. The dedicated project profile was selected and the game was then closed
   normally.
3. No single-player or multiplayer run was started or resumed on that profile.
4. Steam shows Cloud synchronization as **Up to Date**, with no upload,
   download, conflict, or retry in progress.
5. Steam Cloud settings remain unchanged.
6. No game or bridge launch will occur during the probe.

If any item is uncertain, the probe pauses. The project will not launch the game
or change a Cloud setting to resolve it.

## 4. Exact proposed read scope

The probe uses read-only metadata operations. It never opens a save for content
reading.

Before filesystem access, it may inspect the process table only to answer
whether the exact Slay the Spire 2 executable is running. It does not retain
command lines, environment variables, or information about other processes;
the durable result is only `game_process_running=true|false`.

### D1a — resolve one private account namespace

Approved root:

```text
<MACOS_HOME>/Library/Application Support/SlayTheSpire2/steam/
```

Allowed operations:

1. Open the known path components from `<MACOS_HOME>` through `steam` one at a
   time with descriptor-relative, no-follow directory operations. Verify each
   component is a real directory; reject a symbolic link rather than resolving
   through it.
2. List only its immediate children, non-recursively.
3. Count numeric immediate-child directories while keeping every child name in
   process memory only. Never print, log, hash, or retain it.
4. Continue only if exactly one numeric immediate-child directory exists. If
   there are zero or multiple candidates, stop without inspecting beneath any
   of them.
5. For that single candidate only, descend through the account,
   `<DEDICATED_PROFILE_DIR>`, and `saves` components one at a time using the
   already opened parent descriptor and no-follow operations. Then perform a
   no-follow metadata check on the fixed terminal file:

   ```text
   <child>/<DEDICATED_PROFILE_DIR>/saves/progress.save
   ```

6. Do not use a terminal-only `lstat` as proof for the whole path: every
   ancestor must pass the descriptor-relative no-follow check before descent.
7. Continue only when the suffix resolves to a regular file. Refer to the
   private parent thereafter only as `<ACCOUNT_SCOPE>`.

This is not a recursive account scan. The newly created dedicated profile and
its statically known `progress.save` suffix are the selector.

### D1b — inspect only the dedicated save directory's shallow metadata

Approved target after D1a succeeds:

```text
<ACCOUNT_SCOPE>/<DEDICATED_PROFILE_DIR>/saves/
```

Allowed operations:

1. Reuse the already verified directory descriptors to ensure the profile and
   `saves` directories remain beneath the approved root. All child metadata and
   enumeration operations are descriptor-relative and no-follow.
2. List the direct children of `saves` once for the initial snapshot and once
   for the final repeat, without recursion. Two shallow listings are the hard
   maximum.
3. Collect only:

   - an allowlisted logical basename for `progress.save`, `prefs.save`,
     `history`, `current_run.save`, or `current_run_mp.save`;
   - a redacted counter, but not the name, for any unexpected entry;
   - existence;
   - regular-file, directory, or symbolic-link classification;
   - byte size for a regular file;
   - containment and symbolic-link rejection result.

4. Do not enumerate inside `history/` or any other child directory.
5. Repeat the allowed shallow metadata calculation at the end. If it changed
   during the probe, discard the result and stop because the writer/Cloud state
   is unresolved. If it matches, record only
   `shallow_metadata_repeat_match=true`. A match does not prove unchanged file
   contents, remote persistence, or Cloud quiescence.

The expected durable result is a small sanitized table such as
`progress_primary: regular file, <size>` and
`active_single_player_run: absent`. It must not contain a Steam identifier or
absolute resolved path.

## 5. Explicit exclusions

This approval request does **not** include:

- any other profile slot;
- `modded/` or any modded-profile namespace;
- account-scoped `profile.save` or `settings.save`;
- any directory below `history/`;
- logs, replays, screenshots, cache, crash reports, or console history;
- Steam's `userdata` tree, `remotecache.vdf`, login/account configuration, or
  Remote Storage API;
- Cloud-file enumeration or proof of remote persistence;
- file contents, partial byte reads, parsing, serialization, or decryption;
- content hashes, timestamps, ownership, ACLs, extended attributes, or inode
  identifiers;
- copying, backup, rename, permission change, mutation, deletion, quarantine,
  upload, or publication;
- game launch, bridge installation/load, profile switching, or run creation;
- fallback recursive search if the expected target is absent or ambiguous.

## 6. Stop conditions

Stop and report only a sanitized reason if:

- Slay the Spire 2 is running;
- Steam Cloud is not visibly quiescent before the probe;
- the approved root is absent or a symbolic link;
- zero or multiple numeric account namespaces exist beneath the approved root;
- a relevant path component is a symbolic link or leaves the approved root;
- `progress.save` is absent or not a regular file;
- unexpected concurrent metadata change occurs;
- safe redaction cannot be guaranteed.

The probe must not compensate by inspecting another profile, Steam directory,
or broader user-data location.

## 7. Retention and reporting

Ephemeral only:

- the Steam account namespace;
- the absolute resolved account/profile paths;
- raw directory-enumeration results before redaction.

These values exist only in process memory, are never written to a raw output or
log, and are discarded when the probe process exits.

Allowed durable result:

- approval ID and target build identity;
- root-template and logical-role names;
- `account_namespace_resolution = absent | unique | ambiguous`;
- `profile_mapping_confirmed=true` or a sanitized failure, without the number
  or directory name;
- allowlisted direct save basenames, redacted unexpected-entry counts, object
  kinds, and regular-file sizes;
- containment, symlink, `shallow_metadata_repeat_match`, active-run-marker, and
  overall pass/fail results;
- confirmation that no contents, hashes, other profiles, or Cloud APIs were
  accessed.

The durable result remains protected until reviewed. Only a further sanitized
summary may be committed. None of this metadata becomes actor-visible state.

## 8. Cloud interpretation

The current fact is only:

```text
cloud_setting: user_reported_enabled
```

It is not yet:

```text
dedicated_profile_remote_persistence: verified
cloud_sync_quiescence: experimentally_verified
cloud_conflict_behavior: known
```

Cloud enabled is not itself a failure. It makes the fixture's later
`PF-CLOUD-01` recovery and synchronization test mandatory. No Cloud setting will
be changed automatically.

## 9. Result and next gate

If this probe passes, the project may record that a unique local metadata
boundary exists for `project_test_profile`. It still may not read or copy any
save content.

The next proposal would separately state the exact content/copy scope needed to
create a recoverable local golden and to compare one normal launch/close cycle.
Only after that baseline is accepted, and after a separate bridge
installation/load approval, can the read-only live probe begin.
