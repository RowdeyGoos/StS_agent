# Phase 0 Backup-Sidecar Metadata Confirmation Result

- **Status:** passed after one fail-closed pre-filesystem attempt
- **Approval ID:** `PF-D1B-BACKUP-SIDECARS-V1`
- **Approved-scope SHA-256:**
  `adf968fb0bec15800f3f25969d7be1f2040941a6580b8f18800934b708c7d69d`
- **Logical target:** `project_test_profile`
- **Target build:** Steam default/main build `23811903`, packaged release
  `v0.107.1`
- **Access level:** fixed-allowlist shallow filesystem metadata only

The exact approved scope is preserved in
[`PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_REQUEST.md`](../PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_REQUEST.md).
Its pre-execution status remains unchanged so the reviewed and user-approved
hash stays reproducible.

No physical profile number, account namespace, absolute resolved path, raw
basename enumeration, process identifier, or raw command output is retained
here.

## 1. Execution attempts

The first sandboxed attempt stopped with sanitized reason
`PROCESS_CHECK_UNAVAILABLE` before any filesystem access. The exact same
approved probe was then rerun with the required process-table permission and
confirmed `game_process_running=false` before filesystem access.

The successful attempt did not broaden the approved filesystem or metadata
scope.

## 2. Sanitized result

| Check | Result |
| --- | --- |
| Game process | `game_process_running=false` |
| Account namespace resolution | `unique` |
| Dedicated-profile mapping | `profile_mapping_confirmed=true` |
| Descriptor-relative containment | `true` |
| Symbolic-link rejection | `true` |
| Shallow repeat | `shallow_metadata_repeat_match=true` |
| Required core roles | `required_core_role_set_match=true` |
| Known run markers | `known_run_marker_absent=true` |
| Predicted backup sidecars | `expected_backup_sidecar_set_match=true` |
| Complete allowlisted projection | `complete_allowlisted_projection_match=true` |
| Outside-allowlist entries | `0` |

Backup-sidecar metadata:

| Logical role | Existence | Kind | Size |
| --- | --- | --- | ---: |
| `progress_backup` | Present | Regular file | 52,214 bytes |
| `preferences_backup` | Present | Regular file | 287 bytes |

No file contents, hashes, timestamps, Cloud or Remote Storage APIs, other
profiles, or writes were accessed.

## 3. Interpretation

The D1B shallow direct-child classification passes. At the successful-probe
boundary, the approved `saves/` directory contained the required core roles
plus exactly the two statically predicted backup-sidecar roles, with no known
active-run marker or outside-allowlist entry. Both permitted metadata
projections matched.

This current projection is compatible with the two redacted entries counted
during D1, but it does not prove filesystem-object identity across the two
probes. The observed backup sizes equal the primary sizes recorded during D1;
size equality does not prove that either sidecar equals its primary, contains
valid data, or is recoverable. The repeat match does not prove file-content
stability or Cloud quiescence.

## 4. Limits and next gate

This result does **not** authorize or establish:

- content reading, hashing, copying, restore testing, or launch/close deltas;
- backup validity or primary/backup content equality;
- a golden snapshot or complete recoverable profile boundary;
- account-scoped file, history-content, or modded-namespace coverage;
- Cloud persistence, synchronization, conflict handling, or recovery;
- logical unlock state, rule-affecting settings, or clean campaign readiness;
- any full fixture validation-matrix pass;
- bridge implementation, packaging, installation, load, or game launch.

D1B unlocks only presentation of a separate exact proposal for the next
content/fingerprint/copy stage. The D1B approval cannot be reused for that work.
