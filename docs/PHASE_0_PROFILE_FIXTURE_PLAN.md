# Phase 0 Dedicated Profile Fixture Plan

- **Status:** active design; the user confirmed the dedicated profile,
  clean-close/no-run boundary, and Cloud `Up to Date`/idle state, and the
  approved metadata-only D1 and D1B probes passed; no file content, hash, copy,
  golden, or Cloud behavior test has been performed; standalone D1C was
  deliberately skipped; the first approved consolidated fingerprint invocation
  stopped before target-content access because of a runner path-binding defect,
  and no corrected invocation is currently authorized
- **Target build:** Steam default/main build `23811903`, depot `2868842`
  manifest `8653035385353091849`, packaged release `v0.107.1`
- **Target scope:** the Ironclad single-player profile state defined by the
  [Phase 0 target charter](PHASE_0_TARGET_CHARTER.md)
- **Safety boundary:** this plan does not authorize locating, listing, reading,
  copying, editing, deleting, or publishing any personal save or profile
- **Current enabled-mod state:** unknown; installed Workshop content does not
  prove that any mod is enabled or loaded

This document designs the reproducible profile fixture required by Phase 0. The
new profile is known only from the user's report and is referred to publicly as
`project_test_profile`; its physical slot remains protected operational
information. This plan does not select a save format, install or enable a
bridge, or launch the game. Static build research and the separately approved
metadata probe now establish a unique shallow local boundary; see the
[sanitized discovery result](research/PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md).
The separately approved D1B probe established that the **current** shallow
projection contains exactly the core roles plus the two statically predicted
backup-sidecar roles; see its
[sanitized result](research/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md).
It did not read save content, prove continuity with the earlier redacted
entries, or establish recoverability. D1C was reviewed, deliberately
unselected/skipped, and never executed; its fail-closed profile-root and
empty-history predicate is incorporated into
[`PF-HASH-BASELINE-V1`](PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md). Its first
approved invocation
[stopped before target-content access](research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md)
because the runner used the wrong fixed profile-component construction. That
attempt provides no boundary or fingerprint evidence. The unchanged scope would
read only the four fixed-size allowlisted files for two fresh-open hash samples
after the embedded preflight passes, but a corrected invocation requires fresh
approval.

The fixture must support two related uses:

1. a clean, no-mod control for profile, save, and gameplay-passivity tests; and
2. an otherwise equivalent test variant with exactly one declared
   observation/control bridge enabled.

Both variants belong to one logical fixture family. They may need distinct
game-managed save namespaces; that behavior is unknown until observed on the
pinned build. Candidate bridges must never share mutable working state during a
comparison.

## 1. Recommendation in brief

Use a staged decision rather than choosing a construction method now:

1. Have the user create a new game-recognized profile or save namespace that is
   reserved for this project. Prefer a dedicated macOS user or another
   account-level isolation boundary if practical, but do not require one before
   discovering what the game actually supports.
2. With separate permission, inspect only the newly created fixture's file
   deltas and game-visible state. Do not enumerate or open unrelated save roots.
3. Determine whether normal, supported game flows can construct the required
   Ironclad unlock state in reasonable effort.
4. If they can, prefer a clean deterministic construction. If they cannot, ask
   for explicit permission to clone a specifically named unlocked source into
   the isolated target while keeping the source read-only.
5. Consider save import or setup tooling only after the profile format,
   official support, license/data boundary, and live-game equivalence are
   understood. Such tooling must be absent during scored runs.
6. Freeze a pristine local golden snapshot outside the repository. Restore a
   disposable working copy before every test or scored run, verify its identity,
   and quarantine the post-run mutation before the next reset.
7. Freeze base-control and bridge-enabled variants only after their normalized
   unlock state and rule-affecting settings match and the exact loaded-mod state
   is independently verified.

This keeps the safest path first while preserving a practical route if earning
every unlock through normal play is too slow. It does not authorize the copied-
profile or import alternatives.

## 2. Goals and non-goals

### 2.1 Goals

The fixture must:

- be isolated from the user's everyday profile and unrelated game data;
- bind to the exact captured game-build identity;
- expose the frozen, normal Ironclad unlock inventory required by the charter;
- record every setting that can affect rules, available content, automation,
  input interpretation, randomness, or bridge behavior;
- start each campaign attempt with no active or resumable run unless the test
  explicitly requires a save/resume boundary;
- permit deterministic verification and recoverable reset before every attempt;
- contain no gameplay-affecting mods and, for bridge tests, exactly one declared
  bridge in the verified ordered loaded-mod list;
- separate a read-only golden snapshot from candidate-specific working copies;
- survive a failed run, bridge crash, game crash, or interrupted save without
  risking the golden snapshot or any personal source;
- produce repository-safe manifests without raw saves, account identifiers,
  absolute user paths, credentials, or personal history;
- fail closed when the profile, unlocks, settings, save namespace, cloud-sync
  state, or loaded mods cannot be verified.

### 2.2 Non-goals

This plan does not:

- verify the save serialization/content schema; the approved D1 and D1B probes
  resolve only the dedicated shallow local directory and its current
  direct-child role/type projection;
- assume that the game supports multiple profiles, import/export, or a separate
  modded-save namespace;
- authorize inspecting an existing personal profile;
- authorize copying an unlocked personal profile;
- authorize editing save bytes, using a console, or changing unlock flags;
- authorize disabling cloud sync, installing a bridge, enabling a mod, or
  launching the game;
- distribute or commit save files, extracted game data, screenshots containing
  identifiers, or proprietary assets;
- make an A0 functionality, simulator-fidelity, or near-optimality claim;
- define the seed registries, inference budgets, or statistical thresholds owned
  by other Phase 0 work;
- treat a profile hash as proof that the correct profile was selected at runtime.

## 3. Fixture model and terminology

The fixture is a versioned family, not a single mutable save file.

| Term | Meaning |
| --- | --- |
| Logical fixture | The normalized target unlocks, settings, mode availability, and clean-run preconditions independent of physical storage |
| Golden snapshot | A closed-game, verified, read-only local snapshot from which working copies are restored |
| Base-control variant | The logical fixture loaded with no mods enabled or loaded |
| Bridge variant | The equivalent logical fixture loaded with exactly one declared bridge and no other mods |
| Candidate working copy | A disposable copy used by one bridge candidate, test case, or scored attempt |
| Post-run mutation | The quarantined state after a test or run, retained only as long as the evidence policy requires |
| Public manifest | Repository-safe metadata, normalized state, and fingerprints with no personal paths or identifiers |
| Protected operations record | Local, access-controlled mapping of logical roles to actual paths, backup locations, and sensitive evidence |

The preferred family shape is:

```text
sts2-ironclad-profile-fixture-v1
├── logical-state-v1
├── base-control-golden-v1
├── bridge-<candidate-id>-golden-v1
└── disposable working copies per attempt
```

The tree is conceptual. Actual save layout and whether the game itself creates
distinct namespaces remain unknown. Raw snapshots stay outside Git.

### 3.1 Identity boundaries

Do not collapse these identities into one hash:

- game build;
- logical profile state;
- physical profile/save snapshot;
- base or bridge environment variant;
- bridge source, binary, and configuration;
- ordered runtime-loaded mod list;
- campaign working copy;
- post-run mutated state.

A bridge update, changed setting, changed unlock, different physical snapshot,
or different mod order creates a new identity even if the profile name shown in
the UI is unchanged.

## 4. Construction options

### 4.1 Option A: new clean dedicated profile

The user creates a new profile or game-recognized save namespace using only the
normal UI on the pinned build. Required unlocks are then earned or established
through supported game flows.

**Advantages**

- strongest separation from personal history and identifiers;
- clearest provenance;
- lowest risk of copying corrupted, stale, modded, or patch-migrated state;
- easiest to explain and audit.

**Limitations and unknowns**

- the exact multiple-profile support and creation flow are not yet verified;
- reaching the full intended Ironclad unlock state may require substantial play;
- automatic tutorials, first-time-user state, unlock popups, statistics, or
  timeline progression may create unwanted decision variants;
- a bridge may cause the game to use a different save namespace.

**Selection rule**

Prefer this method when the pinned build offers a supported, reasonably bounded
path to the required unlock inventory and repeated construction can be
documented. Do not assume that merely starting a new profile yields the desired
unlocked benchmark state.

### 4.2 Option B: permissioned clone of a specific unlocked profile

With explicit user authorization, copy a specifically identified unlocked
source into a newly isolated fixture target. The source remains read-only and
is never used directly for tests.

**Advantages**

- likely fastest path to the intended content breadth;
- uses state already accepted by the game;
- can unblock Phase 1 phase-coverage work without waiting for progression.

**Limitations and risks**

- the source may contain personal statistics, account identifiers, run history,
  achievements, seeds, mod history, or other private data;
- inherited tutorial, timeline, active-run, daily/custom, beta, or modded state
  may affect reachable decisions;
- cloud sync may propagate changes to the source or replace the clone;
- copying between profile slots or OS users may not be officially supported;
- provenance and redistribution are local-only unless separately reviewed.

**Selection rule**

Use only if clean construction is impractical, the user names and authorizes the
exact source and target, static and in-game verification can distinguish them,
and the source can remain mechanically read-only throughout capture. Any
unremovable personal content keeps raw files and their sensitive mapping out of
the repository.

### 4.3 Option C: deterministic import or setup tooling

A supported import, project-owned local setup tool, or carefully reviewed
transformation constructs the target state from a declarative unlock manifest.

**Advantages**

- potentially the most repeatable clean-profile-to-target procedure;
- may avoid copying personal history;
- can make patch migration and cross-host setup tractable.

**Limitations and risks**

- no supported import or fixture API has been verified;
- direct save editing may be format-fragile, unsafe, or inconsistent with game
  invariants;
- tooling may accidentally alter achievements, cloud data, progression, RNG,
  content availability, or campaign semantics;
- generated files may contain proprietary or private data and may not be
  redistributable;
- a tool that remains active during evaluation could become an undeclared
  gameplay modification.

**Selection rule**

Treat this as a separate evidence project, not the default. It becomes eligible
only after a source/provenance review and paired live validation show that it
produces the same normalized profile state and run-generator behavior as a
normally unlocked profile. The tool must be disabled and absent from the
runtime loaded-mod list during scored runs.

### 4.4 Isolation environment: complementary, not a fourth source

A dedicated macOS account, dedicated Steam account where licensing permits, or
another OS-level user-data boundary can strengthen any of Options A–C. It
reduces path confusion and cloud-sync exposure but does not itself create the
required unlock state. Account creation, Steam login, licensing, and cloud
settings are user actions and are not assumed by this plan.

### 4.5 Decision matrix

| Criterion | Clean profile | Permissioned clone | Setup/import tooling |
| --- | --- | --- | --- |
| Personal-data isolation | Best | Requires redaction and strict controls | Potentially best if generated cleanly |
| Initial effort | Unknown; potentially high | Usually lowest | High until format/API is understood |
| Reproducibility | High if construction is bounded | High locally; source-dependent | Potentially highest |
| Format fragility | Low | Medium | High unless officially supported |
| Unlock breadth | Must be earned/established | Inherits source | Declarative if proven |
| Patch migration | Repeat supported flow | Revalidate source migration | Revalidate tool and every invariant |
| Evidence burden | Construction and unlock audit | Privacy, provenance, clone, and unlock audit | Tool, invariants, legality, and equivalence audit |
| Current eligibility | Discovery candidate | Not authorized | Not demonstrated |

No method is accepted until the unknowns in Section 18 that affect it are
resolved and the user approves any required data access.

## 5. Privacy and threat model

### 5.1 Protected assets

- personal saves and profiles;
- account, platform, device, or cloud identifiers;
- run history, seeds, screenshots, and gameplay statistics;
- credentials, tokens, bridge secrets, and controller leases;
- raw fixture saves and backups;
- absolute paths that reveal user or account names;
- privileged game state captured for conformance;
- the immutable fixture golden and its integrity record.

### 5.2 Threats and controls

| Threat | Required control |
| --- | --- |
| Wrong profile is inspected or overwritten | User names the target in the UI; discovery uses a newly created marker/delta; resolved paths must match an explicit allowlist before any read or write |
| Broad directory scan exposes unrelated saves | No recursive scan of a user-data root; enumerate only a user-approved dedicated target path or narrowly compare metadata created by the controlled new-profile action |
| Personal source is mutated while cloning | Mount or filesystem permissions read-only where practical; copy once into a staging target; all tests operate on a verified descendant of the target, never the source |
| Steam Cloud restores, uploads, or races local data | Determine cloud participation before capture; user controls any cloud-setting change; prove local/cloud behavior with a harmless dedicated fixture before freezing a golden |
| Game or bridge writes while a backup is taken | Capture only at a verified quiescent boundary: game and bridge stopped, no writer process, and the file set stable under the frozen check |
| Candidate bridge modifies another candidate's state | One candidate-specific working copy and environment identity; never reuse a mutated working copy across candidates |
| Installed mod is mistaken for an enabled mod | Record UI/config selection and runtime-loaded module evidence; require agreement; installed-only inventory is not sufficient |
| Modded save namespace silently diverges | Capture base and bridge physical identities separately and compare normalized unlock/settings state; unknown namespace behavior blocks the fixture gate |
| Raw save or identifier enters Git/logs | Repository allowlist contains only sanitized manifests and hashes; run privacy/denylist checks; keep raw files, mappings, and screenshots in protected storage |
| Hashes leak low-entropy identifiers | Hash file contents only for dedicated fixture files; do not publish hashes of personal-source names or identifiers; keep sensitive fingerprints in the protected record |
| Restore command targets too broadly | Resolve and display the exact dedicated target; reject symlinks, traversal, globs, unresolved variables, and roots; use staging plus atomic replacement or another recoverable method |
| Crash leaves an ambiguous partial save | Quarantine the entire working state before recovery; never merge uncertain files into the golden; restore a fresh working copy and verify every hash |
| Bridge exposes profile deletion or filesystem access | Inventory and disable such endpoints; policy runtime has no access; mutating control is loopback-only, authenticated, leased, and off by default |
| Screenshot/video captures names or IDs | Treat raw media as protected; review/redact before any repository inclusion or external sharing |

### 5.3 Data classes

| Class | Examples | Repository policy |
| --- | --- | --- |
| Public project metadata | Fixture schema, logical alias, build ID, normalized unlock IDs, normalized rule-setting values | May be committed after review |
| Protected fixture evidence | Raw dedicated save, exact local path, physical file map, screenshots, post-run diffs | Store outside Git with restricted access and retention policy |
| Personal source data | Everyday save, source profile history, account IDs, raw source hash/path | No access without explicit permission; never commit |
| Privileged conformance data | Hidden state or debug fields captured by an authorized bridge mode | Separate access and schema; never actor input |
| Secrets | Service tokens, bridge credentials, signing material | Secret storage only; never logs, manifests, or datasets |

The public manifest may refer to a protected evidence-bundle ID and content hash.
It must not contain enough path or account material to locate unrelated user
data.

## 6. Manifest and fingerprint design

### 6.1 Public fixture manifest

The repository-safe manifest should record these fields exactly after capture:

| Group | Required fields |
| --- | --- |
| Schema | manifest name/version; canonicalization ID/tool/version; hash algorithm |
| Fixture | project-defined fixture ID/version; status; creation method; capture time; reviewer |
| Build | game-build manifest ID and stable identity hash; clean base-install projection method/result; platform/architecture; release/build/depot IDs |
| Logical state | normalized unlock-manifest ID/hash; normalized setting-manifest ID/hash; clean-run precondition hash |
| Variants | base-control and candidate bridge variant IDs; parent logical-state hash; physical-snapshot fingerprint reference |
| Profile files | logical file roles, sizes, per-file SHA-256, aggregate snapshot hash where publication is privacy- and rights-safe |
| Mods | exact allowed overlay paths and aggregate hash; expected ordered loaded-mod list; each mod ID/version/source revision/binary/config hash; zero overlay entries for base control |
| Bridge | candidate ID, source revision, binary/package hash, configuration hash, capability mode, writes armed/disarmed |
| Environment | locale/language/timezone classifications; cloud-sync state/evidence; game settings schema/hash |
| Verification | verifier version/hash; checks run; result; evidence-bundle reference/hash |
| Lineage | parent golden, derivation procedure/version, reset procedure/version, superseded-by relation |
| Privacy | public/protected field policy version; raw-save committed=`false`; personal source accessed=`true/false`; redaction review |

Use logical roles such as `profile_primary`, `profile_metadata`, and
`settings_primary`; do not commit actual path components if they expose account
or user identifiers. The exact roles come from discovery rather than guesswork.

### 6.2 Protected operations record

The local protected record adds:

- exact resolved source, target, golden, working, quarantine, and backup paths;
- filesystem ownership/permissions and symlink checks;
- private profile/slot/account identifiers;
- raw source and destination file inventory where access was authorized;
- backup media/location, encryption and access policy, and retention deadline;
- cloud-sync configuration and observed synchronization events;
- operator actions, user confirmations, and approval scope;
- raw screenshots/logs and the redaction status of derived evidence;
- restore attempts, failures, quarantines, and recovery outcomes.

The protected record is not an actor input and is not copied into the policy-
ready trajectory store.

### 6.3 Hashing rules

- Use SHA-256 for every retained physical fixture file.
- Compute the aggregate physical snapshot hash from a versioned canonical record
  of logical role, byte size, and file hash, sorted by logical role. Do not use
  absolute paths or modification times in stable identity.
- Hash the normalized unlock and setting manifests independently using a named,
  versioned JSON canonicalization procedure.
- Hash the stable `identity` payload separately from capture time, host-private
  paths, evidence locations, and operator notes, following the pattern used by
  the existing
  [game-build manifest](../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
- Record missing, optional, ignored, and unknown files explicitly. A missing file
  must not disappear silently from the aggregate.
- Treat symlinks and aliases as invalid until a specific safe policy is defined.
- Do not infer equality of logical state from identical file hashes alone; also
  verify state through the game UI or an independently audited public bridge.

If publishing a dedicated fixture file hash still risks linking private data,
keep it in the protected registry and commit only the protected evidence-bundle
hash plus the normalized public-state hashes. This satisfies auditability
without publishing a fingerprint of a personal source.

## 7. Normalize the profile state

### 7.1 Unlock manifest

The final manifest must enumerate every unlock that can change the Ironclad run
generator or reachable decision graph. Candidate categories include:

- available characters and the selected Ironclad identity;
- available standard Ascension levels and the exact maximum label/level present
  in the pinned build;
- character card unlocks;
- shared/global card unlocks, if any;
- relic, potion, event, room, encounter, boss, act, or other content unlocks;
- starting bonuses or choice pools affected by progression;
- tutorial, first-time-user, timeline, ending, or acknowledgement state that can
  insert decisions or overlays;
- any unlock or progression flag exposed to map, reward, shop, event, or combat
  generation;
- active challenge, daily, custom, beta, co-op, or run modifiers, all expected
  absent for the initial target;
- supported content that remains locked, with an explicit reason.

These are candidate categories, not claims about the actual save schema. During
capture, map each verified field to a stable game/content ID, value, evidence
source, and confidence. A display string alone is insufficient when a stable ID
can be obtained lawfully. Unknown categories remain `unknown` and block the exit
gate; they are not interpreted as locked or irrelevant.

### 7.2 Settings manifest

Classify every discovered setting as:

- **rules/content affecting** — part of fixture identity and required exact;
- **automation/input affecting** — part of environment identity and required
  exact;
- **presentation/timing affecting** — recorded because it can affect bridge
  readiness or latency, even if rules-neutral;
- **privacy/accessibility affecting** — recorded only when operationally
  necessary and with sensitive values redacted;
- **verified irrelevant** — recorded with evidence and may be excluded from the
  stable logical-state hash;
- **unknown** — blocks campaign readiness until classified.

At minimum, inspect the game mode, difficulty, character availability, tutorial
and popup behavior, language/locale, input mode, animation/fast settings, and
any mod-loader or developer setting. This list is a discovery checklist, not an
assertion that all named settings exist.

### 7.3 Clean-run preconditions

The logical fixture must verify:

- no active, continued, suspended, or partially initialized run;
- no pending reward, unlock, tutorial, consent, error, or migration popup unless
  explicitly included in a test case;
- standard single-player mode is available;
- Ironclad is available;
- A0 and the later target standard difficulty are selectable as chartered;
- no daily, custom, challenge, beta, co-op, or gameplay modifier is active;
- profile migration has completed and will not run after the golden is frozen;
- the next new-run flow is deterministic up to the externally assigned seed and
  ordinary game chance;
- no seed value or seed-derived field is exposed to the actor.

The profile can record historical victories or statistics if unavoidable, but
they must be proven not to change reachable choices or actor inputs. Otherwise
the fixture needs a different construction.

## 8. Permissioned discovery and capture protocol

No step below is authorized merely because it appears in this plan.

### Stage D0 — Preflight and user boundary

1. Record the accepted build-manifest identity and verify it still matches.
2. Ask the user to close the game and identify whether Steam Cloud is enabled.
3. Ask the user to create and select a newly named project-only profile or the
   closest game-supported equivalent through the normal UI.
4. Ask the user to close the game cleanly without starting a run.
5. Obtain permission for a narrow read-only inspection of only the new target's
   filesystem changes. State the exact proposed roots before access.
6. Record that no personal source profile access is authorized.

Current checkpoint: the build identity is recorded; the user confirmed the
dedicated profile, normal close without starting/resuming a run, Cloud enabled,
and Cloud `Up to Date`/idle. The exact D1 metadata scope was approved and passed
with the execution caveats recorded in
[`PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md`](research/PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md).
This establishes a unique local metadata boundary only. It does not establish
complete logical clean state, remote Cloud persistence, or recoverability.

### Stage D1 — Narrow file-delta discovery

The first D1 pass is narrower than the general protocol below: it may resolve
one private account namespace by the fixed dedicated-profile marker and list
only shallow metadata inside that profile's `saves` directory. It excludes file
contents, hashes, timestamps, other profiles, the modded namespace,
account-scoped files, Steam data, Cloud APIs, and all writes. See the exact
approval scope linked above. Any broader byte inspection or controlled delta is
a later request.

This first pass is complete. It confirmed one account namespace, the protected
profile mapping, no-follow containment, known progress/preferences/history
roles, and absence of the statically known active-run markers. At that D1
boundary, two direct entries were left unclassified because their names were
not retained. See the sanitized result linked above.

Static analysis predicts that the pair counted by D1 is compatible with the
normal `progress.save.backup` and `prefs.save.backup` recovery sidecars. The
separately approved fixed-allowlist D1B probe subsequently confirmed that the
current projection contains exactly those roles alongside the required core
roles, with no active-run marker or other entry. Its
[sanitized result](research/PHASE_0_PROFILE_BACKUP_SIDECAR_METADATA_RESULT.md)
does not prove filesystem-object continuity from D1, content equality, backup
validity, or recoverability.

The following numbered procedure is that **later D1 expansion**. It is not part
of either `PF-D1-DEDICATED-METADATA-V1` or the approved metadata-only D1B scope,
and remains unauthorized unless another exact scope is presented and approved.

1. Capture metadata for the approved target area before and after one harmless
   user action on the dedicated profile.
2. Identify candidate files by controlled delta, not by recursively reading all
   saves.
3. Resolve real paths, reject links/traversal, and prove every candidate is under
   the approved target boundary.
4. Inspect only the minimum bytes necessary to identify format and role, after
   the user approves content inspection.
5. Separate profile state, settings, logs, cache, cloud metadata, screenshots,
   and unrelated files.
6. Document every unread or unresolved file as unknown.

If the game does not expose a dedicated boundary that can be distinguished from
personal data, stop and propose OS-account isolation before further inspection.

### Stage D2 — Runtime/state discovery

With separate launch authorization:

1. verify the selected profile in the UI;
2. capture the game-visible unlock and mode state without enabling a bridge;
3. record settings and all first-time overlays;
4. verify the runtime-loaded mod list using game-visible evidence;
5. close cleanly and compare the approved dedicated file set;
6. determine whether merely loading/closing mutates the profile;
7. determine whether cloud sync participates and whether it changes files.

Do not start a scored run. Any test run is explicitly exploratory and the
working copy is discarded afterward.

### Stage D3 — Select and construct

Apply the decision rules in Section 4. If Option B or C is proposed, present one
consolidated approval request containing the evidence, exact source and target,
read/write scope, backup, privacy implications, and rollback. Do not infer
consent from the user's general approval of the agent project.

### Stage D4 — Freeze and verify

1. finish any one-time migration/tutorial/consent state intentionally;
2. close the game and establish the quiescent-save check;
3. capture the physical inventory and protected operations record;
4. generate normalized unlock, settings, and clean-run manifests;
5. create the local golden and make accidental mutation difficult;
6. restore and verify disposable working copies repeatedly;
7. run the recovery and cloud-sync cases in Section 14;
8. create base-control and bridge variants only after bridge adoption is
   separately approved;
9. review and commit only the sanitized public manifest.

## 9. Enabled-mod and bridge lifecycle

### 9.1 Installed is not enabled

An installed Workshop package or local mod proves only availability on disk. A
variant's loaded-mod identity requires agreement between:

1. the game UI or authoritative mod-loader configuration showing selected and
   ordered mods;
2. runtime evidence showing which mod assemblies were actually loaded; and
3. the expected package/source revision, binary hashes, and configuration
   hashes in the public manifest.

If any source disagrees, status is `unknown` and the run cannot begin.

The base-control variant requires an empty runtime-loaded mod list. The bridge
variant requires exactly one declared bridge. Framework libraries bundled with
the game are runtime dependencies, not automatically enabled mods; record them
under the build identity rather than misclassifying them.

### 9.2 Bridge lifecycle states

Use explicit lifecycle states:

| State | Profile and bridge rule |
| --- | --- |
| `absent` | Bridge not installed in an active mod location; base-control capture |
| `installed_disabled` | Package present but not selected or loaded; never equated with base-control until runtime evidence is empty |
| `loaded_read_only` | Exact bridge loaded from a separately hashed overlay; mutation endpoints disabled; generated config precreated and hashed; load-time patches absent or declared and passivity-tested; profile observation and namespace discovery only |
| `loaded_armed` | Exact bridge loaded; approved loopback controller has a lease; writes enabled only for the named local test |
| `disarmed` | Mutating control revoked; read-only reconciliation and clean shutdown |
| `removed_or_inactive` | Candidate no longer active; its working copy is quarantined and cannot be reused by another candidate |

Every transition records operator, time, old/new configuration hashes, runtime-
loaded evidence, and profile snapshot identity. `loaded_armed` requires the
separate Phase 1 security and mutation approval; this profile plan does not
grant it.

### 9.3 Variant derivation

- Derive each candidate's working copy from the same accepted logical fixture,
  not from another candidate's post-run state.
- If enabling a bridge creates or migrates to a modded namespace, treat the new
  physical state as a derived bridge golden only after normalized unlocks and
  settings match the base-control fixture.
- Record migration deltas and prove that disabling the bridge does not cause the
  wrong namespace to be loaded.
- Never let bridge debug, console, unlock, profile-delete, or save-edit features
  appear on the deployed policy surface.
- Enabling or disabling one candidate invalidates the loaded-mod verification
  for all later attempts until recaptured.

Official material confirms that Slay the Spire 2 has integrated mod support and
official Workshop upload tooling, but it does not by itself establish local
enabled-mod state, load order, save-namespace behavior, or bridge passivity. See
the [v0.107.1 announcement](https://steamcommunity.com/games/2868840/announcements/detail/710026912607505281)
and Mega Crit's [official mod uploader](https://github.com/megacrit/sts2-mod-uploader).

## 10. Golden, working-copy, and reset procedure

### 10.1 Golden creation

Create the golden only after:

- the game and every bridge/helper process are stopped;
- the approved file inventory is stable under a frozen quiescence check;
- cloud-sync state is known and controlled;
- the normalized unlock/settings/clean-run checks pass;
- no active run exists;
- every file hash and the aggregate identity are recorded;
- a second recoverable backup has been verified independently;
- source/target path containment and ownership checks pass.

The golden is never launched directly. Make it read-only or otherwise protected
against routine mutation. Protection is defense in depth, not a substitute for
correct target selection.

### 10.2 Reset before an attempt

1. Confirm the exact target build and environment variant.
2. Confirm that the game, bridge, and cloud writer are quiescent according to
   the accepted procedure.
3. Move the previous working copy to an attempt-specific quarantine; do not
   overwrite it in place.
4. Restore the golden into a fresh staging target.
5. Verify resolved path containment, file inventory, per-file hashes, aggregate
   snapshot hash, permissions, and normalized logical-state hash.
6. Atomically activate the staging target, or use another reviewed recoverable
   activation primitive if the filesystem/game layout does not support it.
7. Launch only after the active target identity is re-read and matches.
8. Verify the selected profile, clean-run preconditions, settings, loaded mods,
   and bridge lifecycle state at runtime.
9. Assign the externally managed attempt and seed-registry IDs. Do not make the
   run seed an actor input.

A hash mismatch, extra file, missing file, unresolved cloud event, unexpected
popup, unexpected mod, or active run is a hard stop.

### 10.3 Post-attempt mutation handling

1. Stop the controller and disarm the bridge.
2. Close the game cleanly when possible; otherwise mark crash termination.
3. Wait for the frozen quiescence condition, then snapshot the entire working
   inventory and mutation diff.
4. Bind the post-run snapshot to attempt ID, terminal/failure status, trajectory,
   build, bridge, and starting-golden hashes.
5. Quarantine it under the evidence retention policy.
6. Never promote a post-run state to a golden without a new fixture review and
   version.
7. Restore a new working copy for the next attempt.

This prevents victories, defeats, statistics, unlock popups, or bridge side
effects from accumulating across a campaign.

### 10.4 Backup and recovery

Maintain at least:

- the protected local golden;
- one independently verified recoverable backup on a separate storage failure
  domain where practical; and
- the disposable active working copy.

The retention plan must state encryption, access, expiry, and whether backup
software or cloud services can read the raw save. Recovery is:

1. stop all possible writers;
2. preserve and hash the ambiguous/corrupted target before touching it;
3. verify the golden and independent backup against their recorded hashes;
4. restore only to a fresh dedicated target;
5. verify physical and normalized logical identity;
6. perform a read-only game load and clean close;
7. reverify hashes and expected load/close deltas;
8. mark the failed attempt as infrastructure evidence rather than erasing it.

Never restore over a personal source. If neither golden copy verifies, stop; do
not reconstruct from fragments or silently fall back to the user's profile.

## 11. Clean campaign initialization

Before every Phase 1 trial or later scored campaign, an automated gate plus a
short independent UI check must confirm:

1. exact immutable game-build identity: base control matches the raw clean tree,
   or a bridge variant matches the clean base-install projection after excluding
   only its separately hashed, non-colliding overlay; no unexpected file exists;
2. accepted fixture family, logical-state, physical-golden, and working-copy
   identities;
3. expected standard single-player mode, Ironclad, and difficulty availability;
4. exact normalized unlock manifest;
5. exact rule-, automation-, input-, locale-, and presentation-setting manifests;
6. no current, continued, suspended, seeded, daily, custom, challenge, co-op,
   or otherwise modified run;
7. no pending migration, tutorial, consent, unlock, reward, or error modal outside
   the frozen scenario;
8. cloud-sync state matches the fixture contract and no unresolved sync is in
   progress;
9. base-control has zero loaded mods, or bridge variant has exactly the declared
   bridge in the correct order;
10. bridge source/binary/config hashes match and lifecycle state is the expected
    `loaded_read_only` or separately approved `loaded_armed` state;
11. privileged/debug endpoints are disabled for actor runs and the public-state
    process cannot read protected profile records;
12. controller lease, attempt ID, and evidence recorder are fresh;
13. seed is assigned by evaluation infrastructure and withheld from actor input;
14. the pre-run evidence bundle is complete and hashed.

The run begins only after the new-run decision is observed through the accepted
public contract. UI polling, profile selection, and popup dismissal are lifecycle
events, not policy decisions unless the frozen benchmark explicitly says so.

## 12. Permission and user-action boundaries

| Future action | Required authority | Current status |
| --- | --- | --- |
| Read repository docs and sanitized build metadata | Current project task | Complete for this design |
| Locate/list the exact dedicated metadata root under `PF-D1-DEDICATED-METADATA-V1` | Explicit approval after stating the exact proposed scope | Complete; unique namespace resolved without retaining its identity |
| Locate/list any other game, profile, account, modded, Steam, or Cloud root | New explicit approval | Not authorized |
| Create/select a dedicated in-game profile | User action or explicit UI-control authorization | User-confirmed and shallow mapping-confirmed |
| Report current Steam Cloud setting | User report | Enabled and `Up to Date`/idle at the approval boundary; remote persistence and behavior not verified |
| Inspect dedicated-profile file metadata | Explicit narrow read-only approval | Complete only for the separately approved D1 and D1B shallow scopes |
| Compare the current shallow direct-child projection with the fixed backup-sidecar allowlist under `PF-D1B-BACKUP-SIDECARS-V1` | New explicit approval of the exact hash-bound request | Complete; current projection passed, without content or recoverability claims |
| Standalone profile-root/empty-history check under `PF-D1C-RECOVERY-UNIT-METADATA-V1` | New explicit approval of its preserved exact request | Reviewed alternative deliberately unselected/skipped; never executed |
| Run the embedded boundary preflight and two fixed-size byte-hash samples under `PF-HASH-BASELINE-V1` | New explicit approval of the exact independently reviewed request for each invocation | Attempt 1 stopped pre-content because of a runner binding defect; corrected invocation not authorized |
| Read contents of dedicated-profile files outside `PF-HASH-BASELINE-V1` | Separate exact approval after metadata discovery | Not authorized |
| Read/list/copy an existing personal profile | Explicit opt-in naming exact source and purpose | Not authorized |
| Change or disable Steam Cloud behavior | User decision and preferably user action | Not authorized |
| Copy source into isolated fixture target | Explicit source/target/backup/rollback approval | Not authorized |
| Edit or generate save content | Separate technical, legal, and equivalence approval | Not authorized |
| Install a bridge/dependency | Separate license/security/setup approval after audit | Not authorized |
| Enable/disable a mod or arm bridge writes | Separate exact-candidate local-spike approval | Not authorized |
| Reset/delete a disposable working copy | Accepted exact-path reset procedure and scoped authorization | Not authorized |
| Commit raw saves, paths, IDs, or protected media | Separate data-rights/privacy approval; normally forbidden | Not authorized |
| Publish or upload any fixture/evidence | Separate external-write and data-rights approval | Not authorized |

When approval is needed, present one consolidated request with the reason, exact
target, data classes, read/write operations, backup, expected mutation, rollback,
and what will be recorded. General permission to develop the agent is not
permission to inspect personal saves.

## 13. Evidence bundle

Each fixture capture or validation attempt should produce a protected bundle:

```text
profile-fixtures/<fixture-family>/<capture-or-attempt-id>/
  public-manifest.candidate.json
  protected-operations-record.json
  file-inventory.private.json
  unlock-manifest.json
  settings-manifest.json
  loaded-mod-evidence.json
  validation-results.json
  mutation-diff.private.json
  approvals.private.json
  attachments.private/
  files.sha256
```

Only the reviewed public manifest and schema/checklist may be copied into the
repository. The protected bundle location is represented by an opaque evidence
ID and integrity hash. The project must define retention and secure deletion
before raw profile material is collected.

## 14. Validation matrix

All results use `pass`, `fail`, `blocked`, or `unknown`. `unknown` never counts
as `pass`.

| ID | Test | Pass condition |
| --- | --- | --- |
| `PF-BUILD-01` | Build binding | Base control matches the clean installation-tree hash, or a bridge variant's allowlisted overlay is separately hashed and the remaining base projection matches; no overlay path replaces a base file |
| `PF-ISO-01` | Source/target separation | Dedicated target resolves outside every protected personal source; no shared writable file or symlink |
| `PF-ISO-02` | Narrow access | Access log contains only approved target roles; no unrelated profile was listed or opened |
| `PF-PRIV-01` | Repository privacy | No raw save, personal/account identifier, absolute user path, credential, or protected media appears in repository artifacts |
| `PF-HASH-01` | Physical identity | Repeated closed-game capture produces the expected per-file and aggregate hashes, accounting for explicitly volatile files |
| `PF-LOGIC-01` | Unlock completeness | Every run-generator-relevant unlock category is enumerated and matches the frozen manifest; no unknown category remains |
| `PF-LOGIC-02` | Clean state | No active run or unexpected modal/migration state exists |
| `PF-SET-01` | Settings | Every relevant setting has an accepted classification and value; no unknown relevant setting remains |
| `PF-MODE-01` | Target availability | Standard single-player Ironclad A0 and the captured maximum standard target difficulty are selectable |
| `PF-MODS-01` | Base control | Configuration/UI and runtime evidence both report no loaded mods |
| `PF-MODS-02` | Bridge exactness | Configuration/UI and runtime evidence both report exactly the declared bridge, revision/binary/config, and order |
| `PF-MODS-03` | Installed-versus-enabled | An installed-but-disabled control proves it is absent from runtime-loaded evidence |
| `PF-NS-01` | Save namespace | Base and bridge namespace behavior is observed, recorded, and normalized-state equivalence is proven or explicitly fails |
| `PF-BRIDGE-01` | Read-only default | Loading the bridge in read-only mode causes no unauthorized profile mutation and exposes no mutating actor capability |
| `PF-BRIDGE-02` | Lifecycle | Arm, disarm, restart, and removal transitions match the recorded configuration and runtime state without cross-candidate contamination |
| `PF-RESET-01` | Repeatable restore | At least three consecutive golden-to-working restores produce the same accepted starting identities, unless another count is frozen before execution |
| `PF-MUT-01` | Mutation containment | A harmless exploratory run changes only the candidate working copy; source and golden remain byte-identical |
| `PF-RECOVER-01` | Interrupted-save recovery | A controlled failure leaves ambiguous state quarantined and a fresh verified working copy can be restored without touching source/golden |
| `PF-CLOUD-01` | Cloud behavior | Upload/download/race behavior is known and cannot replace or propagate the active fixture unexpectedly |
| `PF-LOAD-01` | Load/close stability | Expected load/close mutations are classified; unexplained file or logical-state changes are zero |
| `PF-CAMPAIGN-01` | Pre-run gate | The full Section 11 checklist fails closed under deliberately changed build, profile, setting, mod, and active-run cases |
| `PF-RECOVERY-02` | Independent backup | A fresh target restored from the independent backup verifies physically and logically |
| `PF-REVIEW-01` | Independent review | Reviewer can reconstruct identities and procedures from sanitized plus protected records without relying on operator memory |

The three-restore recommendation is an engineering smoke threshold, not a
statistical performance threshold. Freeze it or its replacement before capture;
do not change it after observing failures.

## 15. Failure policy

- Unexpected personal data access stops the procedure and triggers a privacy
  review before any artifact is retained.
- A path ambiguity, symlink, unexpected writer, or cloud-sync race stops all
  mutations.
- A hash mismatch quarantines the working copy; it is never repaired in place.
- An unexpected unlock, setting, loaded mod, modal, or active run blocks the
  campaign start.
- An unexplained base/bridge normalized-state difference blocks passivity and
  candidate comparison.
- A candidate-specific mutation never becomes another candidate's starting
  state.
- A corrupted or missing golden cannot be replaced from a personal profile
  without a new explicit authorization and fixture version.
- Any manual repair, console action, save edit, or hidden-state inspection is
  recorded and invalidates that attempt as autonomous campaign evidence.

## 16. Phase 0 fixture exit gate

The profile-fixture deliverable is complete only when an independent reviewer
can verify all of the following:

- one accepted construction method and exact procedure are versioned;
- every personal-data access was separately authorized and the source, if any,
  remained read-only;
- the accepted build identity matches;
- the exact Ironclad unlock inventory and maximum standard difficulty are
  captured from the pinned build;
- every relevant setting is classified and frozen;
- the base-control runtime-loaded mod list is empty;
- each eligible bridge variant loads exactly one declared bridge and no other
  mod, with source/binary/config hashes;
- base and bridge variants have the same normalized logical state, or any
  unavoidable namespace difference is understood and accepted;
- pristine golden and independent backup identities verify;
- reset, mutation-containment, recovery, cloud, and load/close tests pass;
- clean campaign initialization fails closed on deliberate mismatches;
- raw saves, sensitive mappings, and personal evidence remain outside Git under
  a declared retention policy;
- the sanitized public manifest, protected evidence reference, verifier, and
  review sign-off are complete.

Until then, the Phase 0 charter's profile fixture and unlock manifest remain
open, and Phase 1 bridge executions are exploratory rather than comparable
campaign evidence.

## 17. Recommended staged path

### Stage 1 — Safe discovery

Completed under the hash-bound D1 approval:

- the user reported that a project-only profile exists and Steam Cloud is
  enabled;
- the user confirmed clean close, no started/resumed run, and Cloud
  `Up to Date`/idle;
- the exact narrow metadata inspection in
  `PHASE_0_PROFILE_METADATA_DISCOVERY_REQUEST.md` was approved and completed
  without contents or controlled deltas.

Completed under the separate hash-bound D1B approval:

- the current direct-child projection matched the required core roles and
  predicted backup-sidecar pair;
- both known active-run markers were absent, no outside-allowlist entry existed,
  and both permitted metadata projections matched;
- no content, hash, copy, Cloud API, other-profile, or write access occurred.

Remaining discovery work:

- obtain fresh one-invocation approval, if the user chooses, for a corrected
  execution of the unchanged `PF-HASH-BASELINE-V1` request. Its first two
  matching boundary snapshots embed D1C's fail-closed predicate before any byte
  access;
- only if still needed, present and obtain a new exact approval before any
  controlled launch/action delta or byte read used to identify
  save/settings/cloud boundaries;
- document multiple-profile and modded-namespace behavior as observed facts.

**Decision:** whether a dedicated boundary exists. If not, propose OS-account
isolation and stop.

**Current result:** a unique shallow local boundary exists and its current
direct-child role/type projection matches the fixed D1B allowlist. D1C was
reviewed, deliberately unselected/skipped, and never executed; its fail-closed
predicate is incorporated into PF-HASH. The first invocation stopped before the
actual profile boundary or target-content access because of an implementation
binding defect and supplies no fingerprint evidence. Stage 1 remains open for a
freshly approved corrected fixed-boundary fingerprint and for any later
save/settings, account-scoped, history, modded-namespace, copy, parse, restore,
or Cloud work; the current results do not prove fixture-wide isolation or
recoverability.

### Stage 2 — Unlock-source decision

- enumerate the clean profile's game-visible unlock state;
- estimate the supported normal path to the target state;
- determine whether a lawful, supported import exists;
- if clean construction is impractical, present the permissioned-clone option
  with privacy and rollback details.

**Decision:** choose A, B, or a separately reviewed C. No source access occurs
before this decision and approval.

### Stage 3 — Freeze the logical fixture

- construct the selected target;
- clear active-run and one-time overlay state through accepted procedures;
- capture normalized unlocks, settings, difficulty, and clean-run conditions;
- create and verify the golden plus independent backup;
- pass reset, mutation, recovery, and cloud tests.

**Decision:** accept `sts2-ironclad-profile-fixture-v1` or record the exact
blocked requirement.

### Stage 4 — Derive bridge variants

- only after one candidate bridge is statically eligible and installation is
  approved, create a candidate-specific working copy;
- load read-only first;
- verify exact runtime-loaded mod state and namespace behavior;
- compare normalized logical state against base control;
- freeze a bridge variant only if the profile and passivity prerequisites pass.

**Decision:** candidate is eligible for the Phase 1 executable spike, needs
remediation, or is rejected. Bridge writes remain a separate approval.

### Stage 5 — Campaign operation

- reset from golden before every attempt;
- run the complete preflight gate;
- quarantine every post-run mutation;
- continuously verify that the personal source and goldens do not change;
- rotate the fixture version when build, unlocks, settings, namespace, or bridge
  identity changes.

## 18. Open questions to resolve during discovery

These are intentionally `unknown`, not assumptions:

1. Does the pinned macOS build support multiple named profiles or an equivalent
   first-class isolated save namespace?
2. Which exact files and directories form profile state, settings, cache, logs,
   and Steam Cloud metadata?
3. Which files are stable at a clean close, and which contain timestamps or
   other expected volatility?
4. Does enabling any mod use a separate save namespace, copy/migrate profile
   state, or share the base state?
5. How does Steam Cloud identify, upload, download, conflict-resolve, or recreate
   these files?
6. Is there an official local profile import/export, reset, or backup flow?
7. What exact unlock categories affect Ironclad run generation on `v0.107.1`?
8. What is the exact maximum standard single-player Ironclad difficulty name and
   level exposed by this build?
9. Which tutorial, timeline, acknowledgement, or migration flags can introduce
   extra decisions?
10. Does starting, abandoning, winning, or losing a run mutate unlock pools,
    statistics, history, achievements, or other generator inputs?
11. Which settings affect rules, RNG consumption, UI readiness, input, or
    bridge timing?
12. How can runtime-loaded mod identity and order be observed independently of
    installed files?
13. Which profile operations and files are touched by each candidate bridge?
14. Can a golden be made read-only without causing the game to fail or silently
    switch to another location?
15. What retention period and encrypted storage are available for protected raw
    fixture evidence?

## 19. Authorities and related plans

- The [Phase 0 target charter](PHASE_0_TARGET_CHARTER.md) owns the profile policy,
  target scope, information boundary, and Phase 0 exit gate.
- The [dedicated-profile metadata discovery request](PHASE_0_PROFILE_METADATA_DISCOVERY_REQUEST.md)
  owns the exact first read scope, exclusions, retention, and stop conditions;
  it is not authorization by itself.
- The [Phase 1 integration plan](PHASE_1_INTEGRATION_SPIKE.md) owns bridge
  candidate execution, passivity, security, recovery, and comparison evidence.
- The [sanitized game-build manifest](../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)
  owns the current binary/build identity and explicitly does not identify a
  profile or enabled mods.
- Mega Crit's [v0.107.1 announcement](https://steamcommunity.com/games/2868840/announcements/detail/710026912607505281)
  is the primary release reference for the pinned version's integrated mod and
  Workshop support.
- Mega Crit's [official mod uploader](https://github.com/megacrit/sts2-mod-uploader)
  is primary evidence for official Workshop packaging/upload tooling. It does
  not document profile storage, enabled-mod state, load order, or save namespace
  behavior, so this plan leaves those fields unknown until measured.
