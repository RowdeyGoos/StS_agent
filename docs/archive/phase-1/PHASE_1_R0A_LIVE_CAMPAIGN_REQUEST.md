# Phase 1 R0a Preliminary Menu Smoke Request

- **Status:** final exact scope; independently reviewed; not executed; awaiting
  exact user approval
- **Approval ID:** `R0A-PRELIMINARY-MENU-SMOKE-V1`
- **Milestone:** preliminary evidence before full `R0a`
- **Logical profile:** `project_test_profile`
- **Target:** Slay the Spire 2 `v0.107.1`, Steam default build `23811903`,
  macOS arm64
- **UI scope:** the already selected dedicated profile's main menu and Settings
  only
- **Direct profile/save/Cloud access by campaign tools, bridge, or operator:**
  none

Every tool and governing identity below is concrete. The request is approvable
only at its final document hash after the complete command set and that exact
document pass independent review.

## 1. Purpose, authority, and claim boundary

This request authorizes one narrow preliminary engineering smoke of the first
project-owned bridge. Its only positive claims can be:

1. the exact accepted overlay is discovered by the pinned game loader;
2. its authenticated loopback health, manifest, and public-screen happy paths
   return the frozen canonical responses;
3. the public reader agrees with the visibly open main-menu and Settings
   screens at three point observations;
4. a normal game exit releases the listener;
5. the exact campaign-owned overlay/configuration can be quarantined after
   process exit; and
6. a final no-bridge launch and clean-install projection succeed.

This is **not** full `R0a` acceptance and cannot close `L-BOOT`, `L-PASSIVE`,
complete `L-NET`, or complete `L-ERROR`. It does not establish profile/save or
Cloud passivity, rule/RNG equivalence, locked-mode behavior, hot unload,
negative live HTTP behavior, a complete observation contract, an action path,
or a functional full-run agent. It authorizes no run start/resume, gameplay
decision, profile visit/switch, save recovery, or later `R0b`/`R1` capability.

No campaign helper, bridge code, or operator action may enumerate, open,
compare, copy, parse, hash, restore, delete, or report profile, save, Steam
Cloud, run-state, or game-log content. The corrected `PF-HASH-BASELINE-V1`
invocation remains separate and unauthorized.

However, ordinary Steam and game behavior is outside that direct-access
prohibition. Each approved launch or exit may perform opaque reads, writes, or
synchronization involving profile, save, preference, telemetry, and Steam
Cloud state. Those effects are unmeasured and potentially mutating. Because no
recoverable profile baseline exists, they may be unrecoverable. Approval must
explicitly accept that risk; a successful smoke must not be described as
passive or recoverable.

## 2. Runtime-bound identities and fixed locations

The request deliberately stores no username, physical profile number, or home
path. At execution time the following symbols have exactly one meaning:

| Symbol | Exact binding |
| --- | --- |
| `<EffectiveUid>` | decimal `501`, which must equal `os.geteuid()` |
| `<UserProfile>` | `os.path.normpath(pwd.getpwuid(os.geteuid()).pw_dir)` |
| `<RepoRoot>` | the canonical repository root containing this exact approved document; every Python command below has this working directory |
| `<ApplicationSupport>` | `<UserProfile>/Library/Application Support` |
| `<InstallRoot>` | `<ApplicationSupport>/Steam/steamapps/common/Slay the Spire 2` |
| `<GameExecutable>` | `<InstallRoot>/SlayTheSpire2.app/Contents/MacOS/Slay the Spire 2` |
| `<OverlayRoot>` | `<InstallRoot>/SlayTheSpire2.app/Contents/MacOS/mods/Sts2AgentBridge` |
| `<OperatorRoot>` | `<UserProfile>/Library/Application Support/Sts2AgentBridge` |
| `<ConfigRoot>` | `<OperatorRoot>/r0a` |
| `<CampaignRoot>` | `<ApplicationSupport>/Sts2AgentBridgeCampaign-r0a-menu-smoke-v1` |
| `<ArtifactRoot>` | `/private/tmp/sts-r0a-final-output.5HNUil` |

The expected application bundle identifier is
`com.megacrit.SlayTheSpire2`. The only network endpoint is literal IPv4
`127.0.0.1:43117`; no hostname, wildcard interface, IPv6 address, port scan, or
override is authorized.

Each fixed campaign, game, config, repository, and artifact path must be
reached component-by-component without following a symbolic link. The sole OS
runtime exception is this exact two-hop chain, whose parent components must
all be non-links: root-owned, mode `0755`, link-count-one
`/Library/Developer/CommandLineTools/usr/bin/python3` has exact link text
`../../Library/Frameworks/Python3.framework/Versions/3.9/bin/python3`; the
resulting root-owned, mode `0755`, link-count-one `python3` has exact link text
`python3.9`; and that lands at the separately path/size/hash-pinned regular
runtime in Section 3. No other link, link metadata, intermediate component, or
target is accepted. A mismatch between supplied UID, effective UID, and the OS
account home fails closed before a user-bound target is accessed. No command
may retain a PID, process command line, username, home path, Steam identity, or
physical profile number in its output or result.

The user is the sole UI operator. They perform every Steam/game launch,
main-menu/Settings transition, normal quit, and visible Cloud-status check on
the local display, pausing at each declared checkpoint while the project tools
run. This campaign authorizes no screenshot, OCR, screen recording,
accessibility-tree capture, remote-desktop capture, or computer-use tool. The
user reports only the fixed checkpoint enum requested by the operator; no
account/profile label or UI text is transcribed.

## 3. Exact accepted artifact and implementation inputs

| Input | Exact identity |
| --- | --- |
| Target manifest | `manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json`; SHA-256 `ea9046a6a66e2388be3fb1db4e287e0982ae1b3772bec28546a40ef48c23b470` |
| Clean base projection | `429` regular files; SHA-256 `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0` |
| Canonical DLL | `77,824` bytes; SHA-256 `ebb9423d61bdf942904995e99c3b8bc5f5753eb052b134edfce25d5e1148733f` |
| Loader manifest | `316` bytes; SHA-256 `622d5fbcb301ee8ba59223095e27a6558a2d4b94a63c9117f979dd2bb451ab53` |
| Canonical ZIP | `78,456` bytes; SHA-256 `eeaaec5f6313a6ae4cf2e843d8380b4a7a0421c82989f1147cfe71c54f2eba4a` |
| Enabled config template | `bridge/Sts2AgentBridge/contracts/live_probe_v0/config_enabled.json`; `129` bytes; SHA-256 `f8c6ff9592fa330cc9317cd63200c9ee5b0f8023c23efc328f04eea57d6dffea` |
| Surface policy | `bridge/Sts2AgentBridge/contracts/live_probe_v0/forbidden_surface.json`; SHA-256 `798c7b809de1db1765ec416dd73e9a6f1757b4b9115ea2323ef603b1966dd9a7` |
| Production source projection | `26` C# files; SHA-256 `c302b141e12b05b92138912459f1099a00c82438631fda1bd064490cede463be` |
| Release structure | SHA-256 `fbc4e34efcb090b36761b31f695013ee17ed283c9a2fe76b9c2f0444bcc15dca` |
| Command shell | `/bin/bash`: root-owned mode `0555` single-link regular file, `1,293,840` bytes, SHA-256 `fde343ee184953c1fa1185abddeaa8be61c6acbebae4eb54db5d6b55b09a5755`; exported `BASH_ENV`, `SHELLOPTS`, and `BASHOPTS` must all be absent |
| Python launcher/runtime | `/usr/bin/python3`: `118,928` bytes, link count `78`, SHA-256 `179301dcb41ea78accc3fa0048a7e6f6710d891945a751a34addd622020c1818`; running `sys.executable` must be `/Library/Developer/CommandLineTools/usr/bin/python3` and resolve to `/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3.9`: Python `3.9.6`, `102,352` bytes, link count `1`, SHA-256 `bdea59019a38eb6600cc9e71e984a97fedadc406448431281e7657030f54987e` |

The discarded Git-suffixed DLL with SHA-256 prefix `945c3fcc` is forbidden and
must never be installed. A rebuild is not a substitute for the accepted DLL,
manifest, or ZIP even if static semantics appear equal.

Immediately before any campaign mutation, `<ArtifactRoot>` must be a
non-symbolic-link directory owned by UID `501`, mode `0700`, with no granting
ACL. It must contain exactly these three single-link, non-symlink
regular files, each owned by UID `501`, mode `0644`, with the exact sizes and
hashes above:

```text
Sts2AgentBridge.dll
Sts2AgentBridge.json
Sts2AgentBridge-0.1.0.zip
```

No extra entry, wrong owner/mode/link count, granting ACL, changing inode,
changing byte stream, or package mismatch is accepted.

## 4. Frozen tools and governing documents

Every Python command except the standalone bootstrap input verifier depends on
the same frozen `tool_common.py`. The bootstrap imports only the standard
library and verifies `tool_common.py` before any later command executes. This
final request contains no placeholder identity.

| File | Required SHA-256 / result |
| --- | --- |
| `bridge/Sts2AgentBridge/tools/tool_common.py` | `57283b9aafe98579b91e1293948677fb498951fe38375841c71fa2db9597bd1e` |
| `bridge/Sts2AgentBridge/tools/verify_package.py` | `e21948fcbac48b4ad9df8ccfcc8c20d957c97fb3ec78b09eeb0572dd8b02a690` |
| `bridge/Sts2AgentBridge/tools/verify_clean_install.py` | `552ab2e2a051f563f9c474368860de2e7042de0e86c3a6a8a6ad34aac9148b00` |
| `bridge/Sts2AgentBridge/tools/verify_operator_config.py` | `f6d08adae0b13ce69a595ef2d3891655e9447fb63e04c1cd927f3232db25a46c` |
| `bridge/Sts2AgentBridge/tools/verify_operator_config_fixtures.py` | `d6c12933f11e5e1642ffcc8b2824316b2b9588fe094ada9655608cc96bb93c1d`; `31/31` passed with real ACL checks |
| `bridge/Sts2AgentBridge/tools/check_live_runtime.py` | `43ab6f1375486336dffd6343265ed7605c15ba4612f23cfc97086d03a9b91ccc` |
| `bridge/Sts2AgentBridge/tools/check_live_runtime_fixtures.py` | `64cab3009a98ee1c86441b20ee81bbce1daf35cd445f3b6e89816654f01c13ad`; `17/17` passed, including an OS-assigned loopback fixture |
| `bridge/Sts2AgentBridge/tools/verify_live_campaign_inputs.py` | `c5e541cc06de4bfc5933e0aacae3193462b8032e9f0bfedcb2d0ca4cfaf24c12` |
| `bridge/Sts2AgentBridge/tools/verify_live_campaign_inputs_fixtures.py` | `4751e9a5f9dab3146a9ad290b4f7a382dc39789426fa322c279873ed3b452274`; `19/19` passed |
| `bridge/Sts2AgentBridge/tools/manage_live_campaign.py` | `a7177b3a6440770754abd1a727d55a949da233813367f14011e382a32dddab92` |
| `bridge/Sts2AgentBridge/tools/manage_live_campaign_fixtures.py` | `c654e6e0bf55ceb08bb7c59ca0f1ede601000c779c8c562f0eed11806f18f008`; `34/34` passed |
| `bridge/Sts2AgentBridge/tools/probe_live.py` | `2ed5a41b606aced24b3d13d5445f054f01d0c1410a1f66ab1dcbcca026e889aa` |
| `bridge/Sts2AgentBridge/tools/probe_live_fixtures.py` | `5d1bcb1c420f08be19bccac327cc7459dc850442eeb547a06d1e040a9c33bb3f`; `12/12` passed |
| `docs/PHASE_1_BR0_PREFLIGHT.md` | `ae90bc33e08cf38b152dc110c4805b39ca329a5002cf66e9788519e0743b1ea3` |
| `docs/PHASE_1_RESTRICTED_BRIDGE_DESIGN.md` | `adeb4eb8de55812649bdc38a0519b59d7b265c970f2ef3befa6ecf17a128a38e` |
| `docs/research/PHASE_1_R0A_IMPLEMENTATION_EVIDENCE.md` | `e514c5f08c949062a61092d723e63f339c089dbaa8aa163b0de789205531e2a6` |

The manager and runtime guard are the only campaign tools that may mutate or
query operational state beyond read-only verification. Their final source and
fixtures require an independent exact-hash review before this request is
approved.

## 5. Fixed generated state and filesystem rules

Only `manage_live_campaign.py install` may generate live campaign material. It
creates one 32-byte credential directly into owned mutable memory, manually
encodes it as exactly 64 lowercase hexadecimal ASCII bytes without a newline,
and zeroes every owned credential-bearing buffer in `finally` paths. The
credential is never printed, hashed, passed in an argument, used in a filename,
or copied to a second persistent file. Transient in-process bridge, verifier,
client, request, and OS-buffer copies may exist; buffers owned by the project
tools are zeroed where the runtime permits.

The manager uses the fixed persistent private `<CampaignRoot>`, owned by UID
`501`, mode `0700`, and a canonical mode-`0600` state record containing no
path, username, profile, PID, credential, credential hash, or token-derived
value. It is deliberately outside `/private/tmp`, whose OS cleanup policy is
not a durable retained-state boundary. Its state machine is:

```text
absent
  -> preparing
  -> activating
  -> installed
  -> quarantining
  -> quarantined
  -> purging
  -> absent
```

The whole operator directory and overlay unit are staged privately and moved
with exclusive, same-filesystem, descriptor-relative renames. Activation moves
the whole operator directory first and code second. Quarantine moves code
first and the whole operator directory second. It never overwrites an active
unit or destination,
merges, repairs, follows a symlink, falls back to copying across filesystems,
scans a sibling tree, or recursively deletes an unbounded path. The only
replacement is the manager-owned canonical `state.next` to `state.json`
transition after exact state identity and ordering checks. It records and
rechecks device/inode identities. Each atomic update also requires the complete
predecessor state read at transition entry. Across invocations, `install`
returns the SHA-256 of the stable canonical installed state; `quarantine`
requires that exact externally retained value and returns the quarantined-state
SHA-256; and `purge` requires that second value. A canonical-looking replacement
therefore cannot be adopted merely by patching its self-recorded inode.

If the campaign creates the `mods` parent, that entire exact parent is the
overlay unit and has mode `0700`. If a safe `mods` parent already exists, it is
preserved and only its newly created `Sts2AgentBridge` child is the overlay
unit, mode `0700`. Overlay files are mode `0644`. `<OperatorRoot>` and
`<ConfigRoot>` are mode `0700`; config and credential files are mode `0600`.
All created objects are owned by UID `501`, have the expected kind and link
count, and have no granting ACL.

Here, a pre-existing `mods` parent is safe only if no path component is a
symlink; the final object is a stable real directory owned by UID `501`; group
and other write bits are clear; it has no granting ACL; the exact
`Sts2AgentBridge` child is absent without sibling enumeration; and its device
permits the manager's exclusive same-filesystem move from the staged overlay.
Any mismatch stops before activation and the pre-existing parent is never
renamed, chmodded, merged, or removed.

Purge is permitted only in the durable `quarantined` state after all final
checks pass. It unlinks exact recorded/allowlisted descendants, credential
first and state last, and stops on any extra, changed identity, active target,
or unsafe object. Unlinking is deletion, not guaranteed secure erasure.

## 6. Exact command forms

All commands use working directory `<RepoRoot>`. The standalone bootstrap uses
`/usr/bin/python3 -I -B -S`; all later Python commands use
`/usr/bin/python3 -B -E -s -S`. These forms disable bytecode writes, ignore
`PYTHON*` variables, exclude the user site, and skip automatic `site`
initialization; isolated mode additionally removes the script/repository path
from bootstrap imports. The commands use the symbols from Section 2 and no
environment override. Placeholders are substituted only with their single
Section 2 binding, except for the two externally carried state hashes defined
below. No other option, retry flag, path, host, port, timeout, force,
overwrite, recovery, or recursive mode is authorized.

Every command block below defines the normative final argument vector. Each
executable, flag, fixed value, and placeholder binding is exactly one argument
even when its value contains spaces; line wrapping is only for display. The
available operator runner necessarily accepts a command string, so it may use
one non-login, non-interactive `/bin/bash` invocation per block solely for
lexical tokenization and quote removal. Paths and substituted values must be
literal single-quoted tokens, while fixed safe executable/flag tokens may be
unquoted. The resulting argument vector must equal the displayed vector
exactly. The bootstrap requires `BASH_ENV`, `SHELLOPTS`, and `BASHOPTS` to be
absent and binds the exact shell bytes and metadata in Section 3 before later
commands run. No expansion, environment-derived argument, control operator,
redirection, glob, command or variable substitution, pipeline, additional
command, or shell-side filesystem action is authorized.

The two displayed union tokens in Sections 6.5 and 6.6 are schemas, not
literal arguments or shell syntax. At each declared checkpoint, the sequence
selects exactly one listed member and substitutes that member as one final
argument: one of `require-stopped`, `require-running`,
`sample-base-port-closed`, or `wait-stopped` for `--mode`, and one of
`main_menu` or `settings` for `--expected-screen`.

`<InstalledStateSha256>` and `<QuarantinedStateSha256>` are the only dynamic
command values. Each is exactly the 64-character lowercase-hex
`state_sha256` emitted by the immediately preceding successful `install` or
`quarantine` manager result in this same campaign. The operator retains it
outside the campaign filesystem and substitutes it literally as one argument;
it is never recomputed from the current state file, accepted from another run,
or repaired after a missing/failed result. The manager CLI enforces the exact
displayed option order for all three modes.

### 6.0 Frozen byte checks

Invoke the frozen, no-path-output input verifier first, with its final own hash
from Section 4 and the exact SHA-256 quoted in the user's approval:

```text
/usr/bin/python3 -I -B -S bridge/Sts2AgentBridge/tools/verify_live_campaign_inputs.py
  --expected-self-sha256 <FINAL_INPUT_VERIFIER_SHA256>
  --expected-request-sha256 <FINAL_APPROVED_REQUEST_SHA256>
```

It verifies its own stable bytes, this exact request document, the concrete
repository/tool/document inputs in Sections 3 and 4, `/bin/bash`,
`/usr/bin/python3`, the exact two-hop Python runtime chain, and all three stable
artifact files against fixed internal labels and digests. It
accepts no path, root, record, or expected-input override and emits only a fixed
manifest ID and aggregate check count. It does not recompute the derived
production-source or release-structure projections; those remain identities
inherited from the hash-bound implementation evidence. The manager separately
proves artifact-root owner, mode, ACL, entry set, file identity, size, and
stable bytes before its first campaign write.

### 6.1 Package verification

```text
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/verify_package.py
  --package <ArtifactRoot>/Sts2AgentBridge-0.1.0.zip
  --expected-dll-sha256 ebb9423d61bdf942904995e99c3b8bc5f5753eb052b134edfce25d5e1148733f
  --expected-manifest-sha256 622d5fbcb301ee8ba59223095e27a6558a2d4b94a63c9117f979dd2bb451ab53
```

### 6.2 Base and overlay projection verification

```text
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/verify_clean_install.py
  --install-root <InstallRoot>
  --target-manifest <RepoRoot>/manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json
  --mode base
```

```text
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/verify_clean_install.py
  --install-root <InstallRoot>
  --target-manifest <RepoRoot>/manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json
  --mode overlay
  --package <ArtifactRoot>/Sts2AgentBridge-0.1.0.zip
```

### 6.3 Campaign manager

```text
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/manage_live_campaign.py
  --mode install
  --user-profile <UserProfile>
  --effective-uid 501
  --artifact-root <ArtifactRoot>
```

```text
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/manage_live_campaign.py
  --mode quarantine
  --user-profile <UserProfile>
  --effective-uid 501
  --expected-state-sha256 <InstalledStateSha256>
```

```text
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/manage_live_campaign.py
  --mode purge
  --user-profile <UserProfile>
  --effective-uid 501
  --expected-state-sha256 <QuarantinedStateSha256>
```

### 6.4 Operator configuration verification

```text
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/verify_operator_config.py
  --user-profile <UserProfile>
  --config-root <ConfigRoot>
  --expected-config-sha256 f8c6ff9592fa330cc9317cd63200c9ee5b0f8023c23efc328f04eea57d6dffea
  --effective-uid 501
```

### 6.5 Runtime/process/port guard

```text
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/check_live_runtime.py
  --mode require-stopped|require-running|sample-base-port-closed|wait-stopped
  --user-profile <UserProfile>
  --effective-uid 501
```

The campaign substitutes exactly one listed mode at each declared checkpoint.
`sample-base-port-closed` is a point sample only. No result may be worded as
continuous port monitoring.

The process indicator first matches an anchored exact executable `argv[0]` and
then treats a name-only match as ambiguous. Ambiguity fails positive running
checks and counts as running for stopped/teardown safety. Each process query is
capped at two seconds. `require-running` makes one exact-process observation.
`sample-base-port-closed` makes one exact-process observation and one loopback
connect attempt capped at 0.2 seconds. `require-stopped` makes an initial
process observation and then requires two consecutive port-refused followed by
process-stopped joint samples within a five-second absolute deadline.
`wait-stopped` polls process state for at most 30 absolute seconds and then
performs the same five-second joint confirmation. Only `ECONNREFUSED` counts as
a closed port. A restart, ambiguity, non-refused socket result, failed process
query, or deadline overrun fails closed. OS scheduling/subprocess termination
may delay command return slightly, but a sample completing after its deadline
cannot pass.

### 6.6 Authenticated live client

```text
/usr/bin/python3 -B -E -s -S bridge/Sts2AgentBridge/tools/probe_live.py
  --user-profile <UserProfile>
  --effective-uid 501
  --expected-screen main_menu|settings
```

The campaign substitutes only the visibly open declared screen. Each client
has a 10-second logical probe deadline and begins a connect only before that
deadline. A connect is capped at one second. After it succeeds, socket
operations use the lesser of one second, the remaining three-second
post-connect connection deadline, and the remaining logical probe deadline.
Scheduler, connect return, and final validation can make command return later
than ten wall-clock seconds, but no further route starts after the logical
deadline. Each execution makes exactly one authenticated `GET` for each of
`/probe/v0/health`, `/probe/v0/manifest`, and `/probe/v0/public/screen`. There
is no unauthenticated readiness poll and no client retry after a failure.

## 7. Immediate user confirmations and risk acceptance

The exact approval must bind, outside this repository document, the physical
slot that is the logical `project_test_profile` and confirm all of the
following immediately before execution:

1. that physical slot is still the dedicated project profile and is already
   selected in the game;
2. the game is fully closed;
3. no single-player or multiplayer run has been started or resumed there;
4. Steam visibly reports Cloud `Up to Date` and idle;
5. Steam Cloud settings are unchanged;
6. game branch, launch options, mod state, and relevant settings are unchanged;
7. no one will visit the profile screen, switch profiles, start/resume a run,
   or change a setting during the campaign;
8. the game will remain closed except for the three exact launches below; and
9. the user accepts that ordinary Steam/game I/O or Cloud synchronization is
   opaque, potentially mutating, unmeasured, and unrecoverable without the
   deferred baseline; and
10. the user will perform all UI/Cloud steps locally and report only fixed
    checkpoint enums, without screenshots or copied UI text.

If a confirmation becomes false or uncertain, the campaign stops. The approval
expires if the first launch has not begun within 15 minutes. Continuing then
requires the user's full exact Section 12 approval message again with the same
final request hash and physical profile slot; a partial or paraphrased renewal
is invalid.

Approval is single-use for the one ordered campaign in Section 8. Only the
three launches and repetitions explicitly listed there are authorized. After
any stop or failure, the sequence may not be resumed or restarted under the
same approval. Another attempt requires the full exact Section 12 approval
again and, when active/partial/quarantined state was retained, a separately
reviewed recovery transition first.

## 8. Exact campaign sequence and deadlines

For this request, a **normal exit** means all three of: the user reports a
successful local quit through the game's own UI; the user observed no crash,
hang, force-quit, or relaunch indication; and runtime `wait-stopped` passed.
Process/port absence by itself never establishes a normal exit.

### 8.1 Read-only preflight

With the game visibly closed:

1. run the exact Section 6.0 concrete-file byte checks and require every frozen
   digest; treat production-source and release-structure projections only as
   identities inherited from the hash-bound implementation evidence;
2. run package verification and require exactly two canonical entries with the
   accepted DLL, manifest, and package hashes;
3. run base projection verification and require `429`,
   `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`,
   and `overlay_count: 0`;
4. run runtime `require-stopped` and require its joint consecutive
   process-absent/port-refused evidence.

Any failure stops without mutation or launch.

For every launch below, any unexpected stable screen, modal, loader
warning/error, prompt, or overlay outside the declared main menu and Settings
screens is a UI-scope failure. Do not dismiss or interact with it except to use
a normal game-provided quit control if one is visibly available.

At each pause, the user reports exactly the requested fixed enum and no UI
text: `BASE_MAIN_MENU_READY`, `BASE_SETTINGS_READY`,
`BASE_MAIN_MENU_RETURNED`, `BASE_NORMAL_QUIT`, `BASE_CLOUD_IDLE`,
`BASE_CLOUD_NOT_IDLE`, `BRIDGE_MAIN_MENU_READY`, `BRIDGE_SETTINGS_READY`,
`BRIDGE_MAIN_MENU_RETURNED`, `BRIDGE_NORMAL_QUIT`, `BRIDGE_CLOUD_IDLE`,
`BRIDGE_CLOUD_NOT_IDLE`, `FINAL_MAIN_MENU_READY`, `FINAL_SETTINGS_READY`,
`FINAL_MAIN_MENU_RETURNED`, `FINAL_NORMAL_QUIT`, `FINAL_CLOUD_IDLE`, or
`FINAL_CLOUD_NOT_IDLE`. Any other problem is reported only as
`UI_SCOPE_FAILURE` or `NORMAL_QUIT_FAILED`; the campaign then applies Section 9
without requesting UI details.

### 8.2 Base-control launch before installation

1. Launch the unchanged game through the existing Steam UI. Do not change its
   branch, launch options, Cloud setting, mod state, or game setting.
2. Reach the already selected dedicated profile's main menu within 120 seconds.
   Stop if a profile screen appears, a run is entered/offered for automatic
   resume, or the state is uncertain. Report `BASE_MAIN_MENU_READY` before any
   tool sample.
3. At that reported stable visible main menu, run one runtime
   `sample-base-port-closed` point sample.
4. Open Settings without changing a setting within 30 seconds, report
   `BASE_SETTINGS_READY`, and run one `sample-base-port-closed` point sample.
5. Return to the stable main menu within 30 seconds, report
   `BASE_MAIN_MENU_RETURNED`, and run one final `sample-base-port-closed` point
   sample.
6. Quit through the normal game UI and report `BASE_NORMAL_QUIT`. Then run
   runtime `wait-stopped`; its process deadline is 30 wall-clock seconds and
   its subsequent joint port-release deadline is 5 wall-clock seconds. A
   restart/reappearance fails closed.
7. In Steam, wait at most 120 seconds for visible Cloud `Up to Date` and idle,
   checking no more than once per five seconds and at most 25 times. Report
   `BASE_CLOUD_IDLE` or `BASE_CLOUD_NOT_IDLE`; do not proceed to another launch
   after the latter.

No claim exceeds the three point-in-time port observations.

### 8.3 Reverification and exclusive installation

With the game stopped and Cloud visibly idle:

1. rerun package verification;
2. rerun the clean base projection;
3. run runtime `require-stopped`;
4. run manager `install` once; before its first write it must require
   `<CampaignRoot>`, `<OverlayRoot>`, and `<OperatorRoot>` absent using only
   no-follow metadata checks, and it must validate the exact artifact-root
   boundary; require its sanitized success result to contain canonical phase
   `installed` and retain its `state_sha256` as `<InstalledStateSha256>`;
5. run the overlay projection verifier and require the unchanged 429-file base
   projection plus exactly two matching overlay files;
6. run the operator verifier as the final filesystem gate and require the
   exact enabled config and a valid credential shape; and
7. run runtime `require-stopped` again immediately before launch.

The manager does not repair or automatically retry a partial state. Any
non-passing install result, missing success output/state hash, or phase other
than canonical `installed` stops immediately: run no overlay/operator verifier
and do not launch. The game remains closed, the exact recorded state is
retained, and only a separately approved transition for that state may run.
This includes interruption after both units move, after the final durable state
update, or before the success hash reaches the operator.

### 8.4 Bridge-enabled launch and three authenticated observations

1. Launch through the same Steam UI and reach the already selected dedicated
   profile's main menu within 120 seconds, without entering a profile or run;
   report `BRIDGE_MAIN_MENU_READY`.
2. After that report, run runtime `require-running`, then run the live client
   once with `expected-screen main_menu`.
3. Open Settings without changing a setting within 30 seconds, report
   `BRIDGE_SETTINGS_READY`, run runtime `require-running`, then run the client
   once with `expected-screen settings`.
4. Return to the main menu within 30 seconds, report
   `BRIDGE_MAIN_MENU_RETURNED`, run runtime `require-running`, then run the
   client once with `expected-screen main_menu`.
5. Quit through the normal UI, report `BRIDGE_NORMAL_QUIT`, and run
   `wait-stopped` under the same 30-second process and 5-second joint-release
   wall-clock bounds.
6. Wait at most 120 seconds for visible Cloud `Up to Date` and idle under the
   same 5-second/25-observation rule, then report `BRIDGE_CLOUD_IDLE` or
   `BRIDGE_CLOUD_NOT_IDLE`.

Each client must validate canonical health with running lifecycle, the exact
eleven-field compatible manifest capability object, the three fixed route
exchanges, and `ready` with the visibly expected screen. Its sanitized success
output contains exactly `schema_version`, `status`, `protocol`, `mode`,
`build_compatibility`, `screen_kind` (the expected screen), and
`routes_checked: 3`; it does not echo lifecycle or capability fields. The
client emits no raw body/header, correlation ID, credential, token-derived
value, absolute path, engine type, UI text, or profile identity.

### 8.5 Post-exit verification and quarantine

Only after the bridge-enabled launch exits normally:

1. rerun the overlay projection verifier;
2. rerun the operator verifier as the active-identity gate;
3. run runtime `require-stopped` immediately before teardown;
4. run manager `quarantine` once with `<InstalledStateSha256>`, which moves
   overlay first and the whole operator directory second into the fixed private
   campaign root; require its canonical `quarantined` success and retain its
   `state_sha256` as `<QuarantinedStateSha256>`; and
5. run base projection verification and runtime `require-stopped`.

If Cloud is not visibly idle after a normal exit, quarantine is still allowed
after these stopped/identity checks, but no further launch or purge is allowed.
The private quarantine is retained and reported.

### 8.6 Final base-control launch and purge

Only when quarantine succeeded and Cloud is visibly idle:

1. launch unchanged base game through Steam;
2. reach main menu within 120 seconds, report `FINAL_MAIN_MENU_READY`, and
   sample the bridge port closed;
3. open Settings within 30 seconds, report `FINAL_SETTINGS_READY`, and sample
   it closed;
4. return to main menu within 30 seconds, report `FINAL_MAIN_MENU_RETURNED`,
   and sample it closed;
5. quit normally and report `FINAL_NORMAL_QUIT`; require bounded
   `wait-stopped`, then report `FINAL_CLOUD_IDLE` or `FINAL_CLOUD_NOT_IDLE`
   after the visible 120-second Cloud check; on `FINAL_CLOUD_NOT_IDLE`, stop,
   retain quarantine, and do not run steps 6-8;
6. rerun base projection verification and runtime `require-stopped`;
7. run manager `purge` once with `<QuarantinedStateSha256>`; and
8. rerun base projection verification and runtime `require-stopped` one final
   time.

Purge removes only exact generated campaign material. The accepted reproducible
artifact root remains. A successful purge reports the fixed `absent` state and
cannot imply secure erasure.

## 9. Fail-closed handling and retained-state rules

- Before installation, any failure stops without mutation.
- After installation but before launch, quarantine is allowed only if the
  runtime guard proves the game jointly stopped and the manager recognizes its
  exact recorded state/inodes using the retained `<InstalledStateSha256>`.
- After a client/UI/check failure, attempt only a normal UI quit if the game is
  responsive. Once normal exit is proven, perform the post-exit verification
  and quarantine, then always stop and retain the quarantine. That failed smoke
  invocation never proceeds to a final launch or purge.
- If the game hangs, the normal quit fails, a process indicator remains or
  reappears, or port/process evidence is uncertain, do not force-kill, move,
  revoke, quarantine, purge, or delete anything. Leave the exact active state,
  keep the game closed if possible, and request user intervention.
- If the game crashes or exits unexpectedly, do not classify it as normal exit
  and do not automatically quarantine or purge under this request. Retain the
  exact state and request a focused recovery authorization.
- If manager state is partial, malformed, noncanonical, replaced, contains an
  unknown inode, lacks its externally retained predecessor hash, disagrees with
  that hash, or a rename result is ambiguous, stop. Do not reverse a successful
  move, adopt another object, regenerate a credential, repair, recompute the
  expected hash from disk, or invoke purge.
- If quarantine succeeds but the final base control, Cloud observation, base
  projection, or purge prerequisite fails, retain the private quarantine and
  report it. Do not retry or broaden access.

There is no hot-unload procedure. Removal is filesystem teardown only after
process exit. The runtime checks remain point observations with an unavoidable
start-after-check race; the user's promise to keep the game closed is still
required during every install/quarantine/purge operation.

## 10. Sanitized result

The durable result may record only:

- approval ID and final request-document SHA-256;
- hashes of the governing documents, tools, accepted artifact, template, and
  target manifest;
- the non-secret canonical installed- and quarantined-state SHA-256 values
  returned by successful manager transitions;
- aggregate pass/fail codes and bounded timings for preflight, the two base
  control sets of three point samples each, installation, three authenticated
  observations, normal exits, Cloud-visible checkpoints, quarantine, purge,
  and final projection;
- safe SDK/game/bridge/protocol versions and fixed state enums; and
- deviations, limitations, and whether generated material is active,
  quarantined, purged, or uncertain.

It must not record a credential, credential hash, token-derived value, raw
correlation ID, raw HTTP request/response, PID, command line, username, absolute
path, Steam/account identity, physical profile number, UI text, profile/save
metadata, Cloud content, or host log content. The campaign does not inspect the
game's existing logging sink; the statically reviewed bridge may write only its
declared sanitized lifecycle entries there.

## 11. Explicit residual limitations

Even a complete pass leaves these open:

- full `R0a`, `L-BOOT`, `L-PASSIVE`, full `L-NET`, and full `L-ERROR`;
- profile/save/Cloud mutation, recoverability, and baseline comparison;
- known-incompatible locked mode and build-change behavior in a real process;
- wrong-token, Origin, method, body, oversize, malformed, collision, overload,
  and unexpected-listener-fault live cases;
- the accepted tiny race in which static health can still say `running` around
  an unexpected post-start listener shutdown; each health result is only a
  point observation;
- screen kinds beyond main menu and Settings;
- continuous port/process monitoring and elimination of point-check races;
- native executable-vnode identity and listener-owner attestation; the runtime
  guard uses anchored argument-list/name indicators and fixed-port behavior;
- hot unload and forced-crash recovery;
- atomicity against malicious same-UID filesystem races or a rewritten
  verifier in managed configuration-loader, pinned build-guard, and
  campaign-helper filesystem operations;
- read-only decision capture, legal candidates, actions, transactions, restart
  reconciliation, complete-run control, fast-backend choice, and near-optimal
  play.

## 12. Exact approval form

Approval is valid only after independent review and must quote the final
document SHA-256 while binding the physical dedicated profile outside this
file. The final user message must use this exact form with
`<PHYSICAL_SLOT>` and `<FINAL_DOCUMENT_SHA256>` replaced:

```text
I approve R0A-PRELIMINARY-MENU-SMOKE-V1, SHA-256
<FINAL_DOCUMENT_SHA256>, for physical <PHYSICAL_SLOT>, which is still the
dedicated project test profile and is already selected. The game is fully
closed; no single-player or multiplayer run has been started or resumed; Steam
Cloud is visibly Up to Date and idle; Cloud settings, launch options, game
branch, mod state, and relevant settings are unchanged; and the game will
remain closed except for the three exact launches in the request. No profile
screen will be visited, no profile will be switched, no run will be started or
resumed, and no setting will be changed. I accept that ordinary Steam/game I/O
and Cloud synchronization during those launches and exits are opaque,
potentially mutating, unmeasured, and unrecoverable without the deferred
baseline. I will perform every UI and visible Cloud step locally and report
only the requested fixed checkpoint enums; I authorize no screenshot, OCR,
screen recording, accessibility capture, or computer-use capture. I approve
only the exact artifact-bound installation, authenticated
loopback happy-path probes, stopped prelaunch cleanup or normal-exit-only
postlaunch quarantine, final base control, and exact generated-material purge
described in the request. I understand that a pass is preliminary and cannot
complete R0a, L-BOOT, L-PASSIVE, or any profile/save/Cloud passivity claim.
```

Any material edit, tool edit, dependency edit, artifact change, stale immediate
confirmation, or paraphrased broader authority invalidates approval and
requires a new final hash.
