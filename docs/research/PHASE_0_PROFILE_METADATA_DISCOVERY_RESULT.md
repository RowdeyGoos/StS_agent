# Phase 0 Dedicated-Profile Metadata Discovery Result

- **Status:** passed with disclosed execution caveats
- **Approval ID:** `PF-D1-DEDICATED-METADATA-V1`
- **Approved-scope SHA-256:**
  `ad568f8441567ab532d7fa5219c5e1d4759bfae52069c15c44ad17ac3f3e214f`
- **Logical target:** `project_test_profile`
- **Target build:** Steam default/main build `23811903`, packaged release
  `v0.107.1`
- **Executed:** 2026-08-29
- **Access level:** shallow filesystem metadata only

The exact approved scope is preserved in
[`PHASE_0_PROFILE_METADATA_DISCOVERY_REQUEST.md`](../PHASE_0_PROFILE_METADATA_DISCOVERY_REQUEST.md).
That request's pre-execution status text is intentionally left unchanged so its
reviewed and user-approved hash remains reproducible.

No physical profile number, account namespace, absolute resolved path,
unexpected basename, or raw command output is retained here.

## 1. Sanitized result

| Check | Result |
| --- | --- |
| Account namespace resolution | `unique` |
| Dedicated-profile mapping | `profile_mapping_confirmed=true` |
| Path containment | Descriptor-relative, component-by-component no-follow traversal passed |
| Symbolic-link rejection | Passed for the approved path and shallow children |
| Shallow repeat | `shallow_metadata_repeat_match=true` |
| Unexpected direct entries | `2`; names were not retained and roles remain unknown |
| File contents read | `false` |
| Content hashes computed | `false` |
| Timestamps collected | `false` |
| Cloud or Remote Storage API accessed | `false` |
| Other profiles or modded namespace accessed | `false` |
| Files copied or written | `false` |

Known logical roles:

| Logical role | Existence | Kind | Size |
| --- | --- | --- | ---: |
| `progress_primary` | Present | Regular file | 52,214 bytes |
| `preferences_primary` | Present | Regular file | 287 bytes |
| `history_directory` | Present | Directory; contents not listed | Not collected |
| `active_single_player_run` | Absent at the statically known filename | Expected regular file | — |
| `active_multiplayer_run` | Absent at the statically known filename | Expected regular file | — |

The missing known run-marker files establish only
`known_run_marker_absent=true`. They do not prove complete logical clean state,
especially while two direct entries remain unclassified and no save content was
parsed.

## 2. Execution caveats

### 2.1 Aborted root-open preflight

The first attempt verified that the game process was absent and then
unnecessarily attempted to open filesystem root `/`. The sandbox rejected that
operation with `EPERM` before any target directory was listed or any user-data
metadata was captured.

The approved procedure begins at the approved macOS home boundary, not `/`.
A descriptor-relative no-follow diagnostic from that boundary through the
Steam platform directory then passed. The successful probe used that corrected
starting point.

This is a non-data-bearing protocol deviation. The rejected attempt did not
result in broader access, expose an identifier, or mutate anything.

### 2.2 Process recheck limitation

Game-process absence was machine-confirmed immediately before the initial
attempt. A repeated process-table query immediately before the successful
metadata pass was blocked by the sandbox. The successful pass therefore relied
on the earlier machine result plus the user's explicit confirmation that the
game was closed and would remain closed.

Do not describe this as an immediate machine re-verification at the successful
pass boundary.

## 3. Interpretation

The D1 local metadata-boundary gate passes:

- one account namespace was resolved without retaining its name;
- the user-approved dedicated profile mapping matched the statically predicted
  vanilla boundary;
- the known `saves` directory was contained and free of followed symbolic
  links;
- the two permitted shallow snapshots agreed;
- no statically known active-run marker was present.

The result does **not** establish:

- a complete profile/save schema;
- the roles or safety of the two unexpected direct entries;
- unchanged file contents or a quiescent writer;
- an unlocked benchmark profile or normalized logical state;
- a recoverable snapshot, golden, reset, or rollback procedure;
- per-file Steam Cloud persistence, remote equality, conflict behavior, or
  recovery;
- base-versus-bridge isolation or passivity;
- permission to read, hash, copy, back up, modify, or delete any file;
- permission to install/load a bridge or launch the game.

Accordingly, this result does not pass `PF-ISO-01`, `PF-ISO-02`,
`PF-LOGIC-02`, `PF-HASH-01`, or `PF-CLOUD-01` from the fixture plan.

## 4. Next gate

Follow-up static build research found that the pinned save writer can create
two local recovery sidecars when it rewrites the corresponding persistent
primary files:

- `progress.save.backup`;
- `prefs.save.backup`.

The migration loader can fall back to those sidecars, and the pinned game's
`CloudSaveStore` file-selection filter excludes `.backup` files. This does not
prove every Steam or Auto-Cloud mechanism. Their predicted count is exactly
compatible with the two redacted entries, but it does not prove the earlier
entries had those names or roles.

The minimal next proposal is therefore
[`PF-D1B-BACKUP-SIDECARS-V1`](../PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_REQUEST.md):
test whether the current shallow direct-child projection contains exactly that
fixed sidecar pair in addition to the required core roles, with no run marker or
other entry. It requires a new explicit approval and does not read contents.

Only after the approved shallow `saves/` direct-child classification passes, or
any mismatch is explicitly resolved, may the project propose a separate
content/copy scope for a recoverable local golden and one controlled base-game
launch/close delta. D1B would not establish a complete recoverable profile
boundary. The current approval cannot be reused for that work.
