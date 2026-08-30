# Phase 1 R0a Implementation Evidence

- **Milestone:** `R0a` / `live_probe_v0`
- **Evidence date:** 2026-08-30
- **Target:** Slay the Spire 2 `v0.107.1`, Steam build `23811903`, macOS arm64
- **Repository disposition:** implementation, tests, static verification, and
  deterministic package gates passed
- **Live disposition:** not run; installation, operator configuration, game
  launch, live probing, and removal remain a later artifact-bound checkpoint
- **Controlling freeze:**
  [PHASE_1_BR0_PREFLIGHT.md](../PHASE_1_BR0_PREFLIGHT.md)
- **Parent boundary:**
  [PHASE_1_RESTRICTED_BRIDGE_DESIGN.md](../PHASE_1_RESTRICTED_BRIDGE_DESIGN.md)

## 1. Claim boundary

This report closes the repository-side implementation gate for the first
project-owned bridge. It establishes that one exact source tree produces one
deterministic, statically restricted, two-file package and that its package-free
tests pass against the pinned compile assemblies.

It does **not** establish that the game loader accepts the package, that the
bridge sees the correct live menu/settings state, that it is passive in a live
process, or that its teardown is clean in the game. Those claims require the
later reversible live campaign.

No bridge overlay was installed. No real operator configuration or credential
was created, read, or changed. The game was not launched. This work did not
access a profile, save, Steam Cloud content, or run state. It did not start or
resume a single-player or multiplayer run.

The corrected `PF-HASH-BASELINE-V1` profile runner remains **unauthorized**.
Its first approved invocation stopped before target-content access, and none of
the R0a work changes that approval boundary.

## 2. Pinned inputs

| Input | Frozen identity |
| --- | --- |
| Target manifest | `sts2-steam-main-build-23811903-macos-universal`; SHA-256 `ea9046a6a66e2388be3fb1db4e287e0982ae1b3772bec28546a40ef48c23b470` |
| `sts2.dll` compile reference | SHA-256 `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18` |
| `GodotSharp.dll` compile reference | SHA-256 `0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289` |
| Parity SDK executable | .NET SDK `9.0.303`; SHA-256 `14383abf1e2f714c42f61e7572cb9889e83cef771a68a739629e2e3bc8dc2e6f` |
| Servicing SDK executable | .NET SDK `9.0.317`; SHA-256 `c1773b3c8958c647995739a7031ac4167e95868a2c1bc01e7d0646fb3b8e9ee4` |
| SDK selection file | `global.json`; SHA-256 `eca284a49ac825a1a8c87c70969c68844fca6595bae84b1aedf0acbae50b9793` |

The game DLLs were read only as the two explicit compile/static-inspection
inputs. They were not copied into the release package.

## 3. Implemented architecture and capability boundary

The release is one production assembly, `Sts2AgentBridge.dll`, plus the loader
manifest `Sts2AgentBridge.json`. There is no project runtime dependency, PCK,
configuration, credential, game assembly, PDB, install script, or second DLL in
the package.

The startup path is deliberately narrow:

```text
ModEntry.Initialize
  -> BridgeBootstrap
     -> StrictConfigurationLoader (fixed macOS path, read-only)
     -> PinnedBuildGuard (loaded sts2.dll path, exact size and SHA-256)
     -> compatible: GodotFrameDispatcher + PinnedPublicScreenReader
        locked: no dispatcher or engine reader
     -> BridgeRuntime
        -> BoundedLoopbackServer
           -> ProbeRequestParser / authenticator / canonical encoder
```

The compatible artifact exposes exactly these authenticated routes on literal
IPv4 loopback `127.0.0.1:43117`:

```text
GET /probe/v0/health
GET /probe/v0/manifest
GET /probe/v0/public/screen
```

Known-incompatible locked mode exposes only health and manifest. An uncertain
build identity starts no listener. The public reader classifies only the pinned
main-menu/settings boundary. It does not serialize profile, save, run, seed,
unlock, multiplayer, node-path, UI-text, or arbitrary game state.

The release contains no action application, input dispatch, Harmony patch,
profile API, privileged capture, bridge filesystem write, outbound network
client, search, model, policy, or training code. Authentication uses an
externally created 64-character lowercase-hex credential; the bridge neither
creates nor repairs it.

## 4. Test-only seams and release separation

The package-free test project sets `BridgeTestSeam=true` only on its project
reference. That defines `STS2_AGENT_BRIDGE_TEST_SEAM` while compiling the test
variant and enables two isolated facilities:

- a pre-created `TcpListener` bound to an OS-assigned loopback port; and
- a synthetic trusted-anchor override for configuration filesystem tests.

Production builds do not set that property. In release, the server constructs
only `IPAddress.Loopback` with `LiveProbeLimits.ListenerPort`, and the
configuration anchor comes only from the OS user-profile API.

The final release metadata/string inspection contains none of
`_testListener`, `TestTrustedAnchorOverride`, or the test-seam symbol. More
importantly, the default-deny verifier passed the exact normalized release
structure below. A release that accidentally compiled either test seam would
change its fields, constructors, calls, and release-structure fingerprint and
would fail the surface gate.

## 5. Final release artifacts

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| `Sts2AgentBridge.dll` | `77,824` bytes | `ebb9423d61bdf942904995e99c3b8bc5f5753eb052b134edfce25d5e1148733f` |
| `Sts2AgentBridge.json` | `316` bytes | `622d5fbcb301ee8ba59223095e27a6558a2d4b94a63c9117f979dd2bb451ab53` |
| `Sts2AgentBridge-0.1.0.zip` | `78,456` bytes | `eeaaec5f6313a6ae4cf2e843d8380b4a7a0421c82989f1147cfe71c54f2eba4a` |

The independently reproduced output was staged at
`/private/tmp/sts-r0a-final-output.5HNUil/` on the evidence host. That location
is disposable; the hashes, not the temporary path, identify the accepted
artifacts.

The ZIP contains exactly these two stored regular-file entries, in this order:

```text
Sts2AgentBridge/Sts2AgentBridge.dll
Sts2AgentBridge/Sts2AgentBridge.json
```

The checked-in package-layout contract has SHA-256
`b1ad9d7201e49171aebc385e31b6d05ac6c6298a171706535a976da49421caf6`.

## 6. Executed gate results

### 6.1 Build and reproducibility

| Gate | Result |
| --- | --- |
| Direct parity build | SDK `9.0.303`; passed with zero warnings/errors; DLL `ebb9423d61bdf942904995e99c3b8bc5f5753eb052b134edfce25d5e1148733f` |
| Direct servicing build | SDK `9.0.317`; passed with zero warnings/errors; byte-identical DLL `ebb9423d61bdf942904995e99c3b8bc5f5753eb052b134edfce25d5e1148733f` |
| Two-root reproducibility | two independent copied source roots, restores, builds, and packages passed; DLL, manifest, and ZIP were byte-identical |
| Reproduced DLL | `ebb9423d61bdf942904995e99c3b8bc5f5753eb052b134edfce25d5e1148733f` in both roots and final output |
| Reproduced manifest | `622d5fbcb301ee8ba59223095e27a6558a2d4b94a63c9117f979dd2bb451ab53` in both roots and final output |
| Reproduced ZIP | `eeaaec5f6313a6ae4cf2e843d8380b4a7a0421c82989f1147cfe71c54f2eba4a` in both roots and final output |

The final independent reproduction used fresh roots
`/private/tmp/sts-r0a-final-repro-a.gZY2ZP` and
`/private/tmp/sts-r0a-final-repro-b.JmvfgM`. The isolated subprocesses emitted
a host `confstr` fallback warning for the Darwin temporary-directory lookup;
all authoritative exit codes were zero and the compared bytes were identical.

### 6.2 Package-free bridge tests

The parity test gate passed all nine suites:

```text
PASS contract
PASS configuration
PASS identity
PASS build_identity
PASS hosting
PASS threading
PASS public
PASS transport
PASS security
PASS all 9
```

The test assembly used for this final run had SHA-256
`83ecb4628fda372ec700857f5ac3ee40f10fa35e6ddb82905c5cde11a97135f9`.
It is test evidence only and is not a package input.

Notable executed coverage includes:

- inventory equality and byte-for-byte comparison of all 32 checked-in JSON
  and complete HTTP golden vectors against production encoders;
- all 30 `limits.json` fields bound to production or derived constants,
  including the queue and shutdown consumers;
- strict configuration parsing, real disposable filesystem shapes, credential
  handling/zeroization, and fixed-time comparison IL;
- compatible and locked lifecycle, reverse cleanup, bounded queue behavior,
  cancellation, concurrent stop, listener collision, and real loopback
  accept/response/port-release behavior on an OS-assigned test port;
- the malformed/framing/authentication/Host/Origin/method/mode/route precedence
  matrix, deterministic malformed corpus, and at least 10,000 fuzz cases;
- exhaustive 216-case public projector truth-table coverage and repeated stable
  reads; and
- exception-injection sanitization for fake credential, path, request, and game
  type values.

### 6.3 Forbidden-surface gate

The production assembly passed the source, metadata, dependency, type/member,
IL callsite, constant, route, path-provenance, initializer, and normalized
release-structure verifier.

```json
{
  "status": "passed",
  "assembly_sha256": "ebb9423d61bdf942904995e99c3b8bc5f5753eb052b134edfce25d5e1148733f",
  "route_count": 3,
  "checked_method_bodies": 344,
  "configuration_structure_sha256": "1f1b8aa5cf12ab5762fb357ee5fb34a8f37b24610e4f0e24992c5ccb6618f2dc",
  "build_guard_structure_sha256": "7152a2cc4c4c4304e24dd449d7c53840ae7a76660e91f9fff0952f476cc5a00e",
  "transport_structure_sha256": "ab304c1fb866159067f49e756a0c1824d71dd51c6a351f71294a5193acd518d6",
  "source_projection_sha256": "c302b141e12b05b92138912459f1099a00c82438631fda1bd064490cede463be",
  "release_assembly_structure_sha256": "fbc4e34efcb090b36761b31f695013ee17ed283c9a2fe76b9c2f0444bcc15dca"
}
```

The complete surface campaign passed:

- the production assembly;
- one unmutated positive fixture assembly;
- 68 named compiled or source-mutation negative fixtures, each rejected for
  its expected code; and
- one forbidden-source negative fixture.

The gate reports `fixture_count: 70` for the positive/negative fixture controls
after the production pass. The verifier DLL had SHA-256
`4e2bcbc38344f54c5dc57701fa20a383189ddbb2c60eda56530e4fd83a181773`.
The surface-policy artifact has SHA-256
`798c7b809de1db1765ec416dd73e9a6f1757b4b9115ea2323ef603b1966dd9a7`;
the fixture catalog has SHA-256
`de3aa79bdcb7b0ec91b5988c8793728452516d729fe06bdc8ac51db4388651f1`.

### 6.4 Package gate

The canonical package verifier passed with exactly two entries and reproduced
the DLL, manifest, and ZIP hashes in Section 5. Seven deliberately malformed
ZIPs were each rejected for their named rule:

| Fixture | Required rejection |
| --- | --- |
| extra JSON | `package_extra_manifest` |
| secondary DLL | `package_secondary_dll` |
| copied game assembly | `package_game_assembly` |
| traversal member | `package_traversal_entry` |
| symbolic-link member | `package_symlink_entry` |
| compressed member | `compressed_entry` |
| archive comment | `archive_comment` |

Result: `fixture_count: 7`, all passed.

### 6.5 Configuration artifacts and external-preflight fixtures

| Artifact/check | Result |
| --- | --- |
| `limits.json` | SHA-256 `1654364bf1e032fe939d2f8f0f0849dd83b0f84ec7c4564f6d8fcca888ba4435`; all 30 fields bound to production/derived constants |
| enabled config | `129` exact bytes; SHA-256 `f8c6ff9592fa330cc9317cd63200c9ee5b0f8023c23efc328f04eea57d6dffea`; strict parser returns enabled |
| disabled config | `130` exact bytes; SHA-256 `132f4c49ee499a52b43d2f0d66edcba1bd78bd5b49777c270636246d85cd3b52`; strict parser returns disabled without reading a token |
| synthetic external verifier | `fixture_count: 31`; passed; `real_acl_check: true` on the disposable macOS fixture; verifier-owned credential buffers were demonstrated zeroed after success and shape failure |

The 31 external-preflight cases cover canonical enabled/disabled trees,
identity binding, owner/mode/link-count, file/directory kind, symlink and
component containment, stable bounded read/change/short-read/failure, config
hash, credential shape and owned-buffer zeroing, and
clean/granting/unsupported ACL cases. They operate only below a disposable work
root and do not use the real operator path.

The external verifier and its synthetic harness have SHA-256 values
`f6d08adae0b13ce69a595ef2d3891655e9447fb63e04c1cd927f3232db25a46c`
and
`d6c12933f11e5e1642ffcc8b2824316b2b9588fe094ada9655608cc96bb93c1d`,
respectively.

### 6.6 Repository regression tests

The existing Python repository suite passed unchanged:

```text
235 passed
```

The bridge implementation did not change the combat prototype's observation,
action, simulator, training, or checkpoint semantics.

### 6.7 Operational-boundary tools and sanitized client

After the package freeze, the external clean-install verifier was run read-only
against the exact installed game root in base mode. It passed with
`base_file_count: 429`, base SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`,
and `overlay_count: 0`. This proves only that one pre-campaign base projection
matched; the same check remains mandatory immediately before and after live
work.

The separately packaged-free live client was then frozen for the later
artifact-bound campaign:

| Tool/check | Result |
| --- | --- |
| `tools/probe_live.py` | SHA-256 `2ed5a41b606aced24b3d13d5445f054f01d0c1410a1f66ab1dcbcca026e889aa`; fixed OS identity/path, literal loopback endpoint, three exact routes, bounded exchange, canonical response validation, sanitized output |
| `tools/probe_live_fixtures.py` | SHA-256 `5d1bcb1c420f08be19bccac327cc7459dc850442eeb547a06d1e040a9c33bb3f`; all `12` in-memory success/fail-closed cases passed |
| `tools/check_live_runtime.py` | SHA-256 `43ab6f1375486336dffd6343265ed7605c15ba4612f23cfc97086d03a9b91ccc`; fixed OS/executable identity indicators, fixed loopback point checks, absolute deadlines, and consecutive stopped/closed confirmation |
| `tools/check_live_runtime_fixtures.py` | SHA-256 `64cab3009a98ee1c86441b20ee81bbce1daf35cd445f3b6e89816654f01c13ad`; all `17` boundary/race/deadline/loopback cases passed |
| `tools/manage_live_campaign.py` | SHA-256 `a7177b3a6440770754abd1a727d55a949da233813367f14011e382a32dddab92`; persistent fixed-path install/quarantine/purge state machine, externally chained state hashes, full-predecessor atomic updates, exclusive descriptor-relative moves, inode-bound inventories, exact allowlisted deletion, and sanitized fixed output |
| `tools/manage_live_campaign_fixtures.py` | SHA-256 `c654e6e0bf55ceb08bb7c59ca0f1ede601000c779c8c562f0eed11806f18f008`; all `34` lifecycle, hard-interruption checkpoint, self-consistent state-replacement, in-transition replacement, foreign-object, ACL/mode/link, credential-zeroing, and output cases passed |
| standalone campaign-input bootstrap | isolated standard-library imports; own/request hash binding; exact repository, artifact, shell, and Python-runtime-chain byte/metadata checks; no path or manifest override |
| campaign-input bootstrap fixtures | all `19` stable-byte, path/link, runtime-chain, shell-environment, CLI, sanitized-output, and import-isolation cases passed; final bootstrap byte identity is intentionally bound by the later live request |
| shared `tools/tool_common.py` | SHA-256 `57283b9aafe98579b91e1293948677fb498951fe38375841c71fa2db9597bd1e`; operator interruption maps to a sanitized fixed error |
| Python compile | shared helper, package/clean/operator/bootstrap/manager/runtime/client tools, and their campaign fixtures passed the system Python `py_compile` gate |
| Golden-vector check | health `100`, compatible manifest `606`, main menu `98`, and settings `97` body bytes each matched the checked-in production vectors exactly |
| Request grammar check | all three fixed GET requests matched the production parser grammar and exact Host/Bearer/CRLF shape |

The client accepts no host, port, route, credential, or arbitrary-path
override. It was independently adversarially reviewed without a blocker. It
has not read the real credential or connected to the live endpoint; those are
still operational evidence.

The runtime guard similarly has not queried the real game process or fixed
production port. Its fixtures use mocked process boundaries and one
OS-assigned disposable loopback port. Exact executable evidence is an anchored
argument-list indicator rather than a native executable-vnode query; a
process-title/argument adversary and the unavoidable start-after-check gap
remain declared residuals. Base-port results are point samples, not continuous
monitoring.

The manager similarly has not touched its fixed production state, overlay, or
operator paths. Its persistent state root is outside the OS-cleaned temporary
namespace. Its fixtures execute complete created- and pre-existing-parent
lifecycles plus every published transition checkpoint in disposable trees.
Successful install and quarantine transitions export a non-secret canonical
state SHA-256 required by the next invocation, and every atomic update requires
the complete in-memory predecessor. A hard interruption after durable
publication intentionally leaves exact material in place without publishing a
new continuation hash and does not authorize automatic retry or repair; a
focused recovery procedure would be required for that retained state.

## 7. Normalized source and structure fingerprints

The verifier-enforced production projection contains exactly the 26 C# files
listed by the production project. The normalized release hashes are:

| Projection | SHA-256 |
| --- | --- |
| `StrictConfigurationLoader.cs` source bytes | `35b3dc0c8675379e624080a7d6a3e512556f4c1db3e7cc9c8bb6dcc21d6f15ba` |
| normalized configuration type structure | `1f1b8aa5cf12ab5762fb357ee5fb34a8f37b24610e4f0e24992c5ccb6618f2dc` |
| `PinnedBuildGuard.cs` source bytes | `181ac0c3f4449458817f027f1fc21cf69545206f22b8e1e7935f065eb7072497` |
| normalized build-guard type structure | `7152a2cc4c4c4304e24dd449d7c53840ae7a76660e91f9fff0952f476cc5a00e` |
| normalized transport type-family structure | `ab304c1fb866159067f49e756a0c1824d71dd51c6a351f71294a5193acd518d6` |
| normalized 26-file production source projection | `c302b141e12b05b92138912459f1099a00c82438631fda1bd064490cede463be` |
| normalized release assembly structure | `fbc4e34efcb090b36761b31f695013ee17ed283c9a2fe76b9c2f0444bcc15dca` |

For a broader repository-side inventory, 134 regular files below
`bridge/Sts2AgentBridge/` were projected after excluding directory components
`bin`, `obj`, and `__pycache__`, `.DS_Store`, and the exact bootstrap pair
`tools/verify_live_campaign_inputs.py` and
`tools/verify_live_campaign_inputs_fixtures.py`. Those two files are instead
bound directly by the final live request and by the bootstrap's own/fixture
hash checks, which avoids a circular evidence/bootstrap hash dependency. Each
inventory record is
`<lowercase SHA-256><two spaces>./<relative path><LF>`, sorted by raw path bytes.
The SHA-256 of that record stream is
`ebed3039f9b6b754c9db7f2489ca09c5048d1008bfa43004963fca2b9d82677b`.
This broad inventory is evidence bookkeeping; the 26-file production and
assembly fingerprints above are the enforced release boundary.

## 8. Discarded Git-provenance candidate and closure

An initial direct parity candidate at
`/private/tmp/sts-r0a-parity-out.lqF2kt/Sts2AgentBridge.dll` had SHA-256
`945c3fcc51c50bf228aca62ab1f9df41530bbbe4974fa917e0671c21ef71ed1f`.
It was rejected and was never packaged for acceptance, installed, or loaded.

Independent reproduction found that two copied source roots agreed with each
other but not with that candidate. Byte/string inspection isolated the cause:

- the Git-worktree build embedded assembly informational version
  `0.1.0+3d3b12e4803de72c30d0d10f71558d9f66420ec7`;
- the copied roots, which had no `.git` metadata, embedded the frozen `0.1.0`.

The .NET SDK had appended `SourceRevisionId` according to build context. That
violated the frozen exact `InformationalVersion=0.1.0` and made a repo-root
build differ from a copied-root build even though the C# inputs matched.

The closure was applied in four layers:

1. `Directory.Build.props` sets
   `IncludeSourceRevisionInInformationalVersion=false`;
2. the production project repeats the false setting beside the exact
   `InformationalVersion`;
3. the verifier-fixture project does the same; and
4. `run_gate.py` passes the property explicitly into isolated builds and tests
   assembly/file/informational-version mutations.

After that closure, direct parity `9.0.303`, direct servicing `9.0.317`, and
both independent copied-root parity builds all produced the exact final DLL
`ebb9423d61bdf942904995e99c3b8bc5f5753eb052b134edfce25d5e1148733f`.
Final inspection contains `0.1.0` and no appended 40-hex revision. The
`945c3fcc...` candidate must not be reused.

## 9. `PathMap` syntax adaptation

The preflight displayed the two logical mappings separated by a semicolon in
its human-readable property list. MSBuild/C# compiler `PathMap` uses a comma to
separate multiple mappings, so the executable property is:

```xml
<PathMap>$(MSBuildThisFileDirectory)=/_/bridge/,$(STS2GameDataDir)=/_/game/</PathMap>
```

This is a syntax adaptation, not a boundary change: the same bridge root and
game-data root are mapped to the same frozen virtual roots. The byte-identical
direct, servicing, and two-root results verify the intended effect.

## 10. Independent review and residual limitations

Independent contract/test review found no material repository-side BR0 blocker.
Independent runtime/source review found no P0/P1 issue and no static blocker to
a controlled live gate. The following limitations remain explicit.

### 10.1 Contract-test literal coverage

- The suite does not literally execute `N-1`, `N`, and `N+1` for every value in
  the complete limits table. It does so for all parser limits and executes the
  important connection, rate, and queue boundaries. Remaining timeout, body,
  and backlog values are exact constant-bound and behaviorally sampled.
- There is not one separate negative assembly for every possible adjacent BCL
  overload. Representative network, filesystem, Godot, and generic adjacent
  cases execute. The verifier's exact default-deny observed-member equality is
  the exhaustive control that rejects every unlisted overload.

These are differences from a literal reading of preflight Sections 10.6 and
10.17, not evidence of a currently admitted extra surface.

### 10.2 Build-guard short-read and TOCTOU coverage

Real adapter tests cover wrong size with zero content read, exact-size digest
mismatch, exact-size unreadable input, link rejection, and restoration of the
disposable pinned-assembly copy. Pure classification and structural checks bind
the complete-read and post-read facts. The actual OS adapter is not dynamically
fault-injected for every short-read or post-size-change interleaving.

More generally, the build guard cannot prove that every path metadata check and
later read refers to one immutable inode in the presence of a hostile same-UID
process. The controlled launch and pinned clean-install preflight mitigate this
for R0a; descriptor-relative no-follow opens and handle identity would be a
future hardening step.

### 10.3 Managed configuration filesystem race

The managed loader checks fixed-component containment, kind, link target,
mode, size, refresh stability, bounded reads, exact bytes, and credential shape.
The external preflight additionally checks effective ownership, link count,
ACLs, modes, and hashes. Managed `LinkTarget`/metadata checks followed by a
`FileStream` open are still not an atomic `O_NOFOLLOW`/`fstat` transaction. A
malicious same-UID or privileged process could race a same-length replacement.
That threat is accepted for this controlled local milestone, not claimed away.

### 10.4 Live screen and locked-bootstrap evidence

The public projector truth table and pinned member mappings are comprehensively
tested or structurally bound, but the real game has not loaded the bridge.
Correct classification of actual `NMainMenu` and `NSettingsScreen` instances is
therefore still unverified.

The locked core runtime and its two-route behavior execute in tests, and the
production bootstrap branch is source/assembly fingerprinted. The exact
production incompatible-build bootstrap path has not been exercised through an
injected or real game loader. That is a runtime-injection gap rather than an
unrestricted fallback: uncertain identity still has no listener path, and the
locked branch contains no public reader/dispatcher construction.

### 10.5 Listener/runtime-state P2

An unexpected post-start accept-loop fault ends acceptance fail-closed, but the
current listener does not publish that completion/fault back to
`BridgeRuntime`. The runtime may remain marked `Running` and retain
configuration/dispatcher resources until normal stop. There is no dedicated
runtime monitoring or recovery signal for this case.

Separately, the canonical health body is static. An already accepted connection
can observe a narrow startup/shutdown race in which the body says `running`
without a serving-readiness value coupled atomically to the lifecycle
transition. Normal startup/stop and port-release paths pass; barrier-controlled
unexpected-accept-fault and lifecycle-race injection are not present.

This is a nonblocking P2 for the short controlled live probe, not a claim that
the bridge is suitable for unattended persistent service. A future hardening
change should couple listener completion and serving readiness to runtime state
and add deterministic fault/race tests.

### 10.6 No live hot unload

`hot_unload` is intentionally `false`. R0a supports bounded normal stop during
the host lifecycle, but it does not claim that the loader can unload the DLL
from a running game. The operational campaign must close the game before
removing the overlay or operator artifacts.

## 11. Gate disposition

The exact source, DLL, manifest, and ZIP above pass the repository/build/package
gate and are suitable inputs to a separately reviewed, reversible live
checkpoint. They do not yet pass a live-load, live-screen, passivity, teardown,
or base-control gate.

Any later live request must bind the exact final hashes, recheck the clean base
projection and operator boundary immediately before launch, remain at public
menu/settings screens, close the game before removal, and preserve the separate
profile/Cloud authorization boundary.

## 12. Bounded live-smoke result — 2026-08-30

The existing R0a artifact completed its first end-to-end live smoke on the
pinned Steam build and dedicated test profile:

- the isolated two-file overlay and dedicated authenticated configuration were
  installed without replacing a base-game file;
- after the user enabled the newly installed mod in the game's own Mods
  settings and restarted, authenticated `health`, `manifest`, and
  `public/screen` requests all passed at both the main menu and Settings;
- the manifest reported `live_probe_v0` and compatible build identity, while
  the public screen reported `main_menu` and `settings` at the corresponding
  visible checkpoints;
- normal quit released the process and listener, after which the overlay and
  operator configuration were quarantined;
- a subsequent base-game launch reached the main menu with the bridge port
  closed; and
- final purge removed the four generated bridge/configuration files. The game
  was stopped and the installation again matched the 429-file clean-base
  projection with zero overlay files.

Two milestone blockers occurred and were fixed narrowly:

1. The operator verifier and live client treated macOS's standard
   `everyone deny delete` ACL as permission-granting. Their parsers now accept
   explicit deny-only entries while continuing to reject allow or unclassified
   ACL entries.
2. The first launch had no listener because the newly installed mod had not yet
   been accepted/enabled in the game's Mods settings. Enabling it and using the
   game's requested restart flow produced the successful live load.

This demonstrates loader entry, authenticated transport, build compatibility,
and real main-menu/Settings classification for R0a. It does not yet expose a
gameplay decision or authorize state-changing game control.

## 13. R0b read-only combat-decision result — 2026-08-30

The deliberately narrow R0b slice completed a bounded live smoke on Profile 3
and the same pinned game build:

- bridge version `0.2.0` exposed one authenticated, read-only first-turn combat
  snapshot without save/profile access or action application;
- the live response reported round 1, Ironclad at 80/80 HP with 3 energy, one
  43/43-HP Nibbit with a visible attack intent, five visible hand cards, and
  six legal actions;
- the separate deterministic client selected hand slot 0,
  `DEFEND_IRONCLAD`, from that legal-action set because an incoming attack was
  visible; no card, target, end-turn, or other game action was applied;
- the bridge was quarantined after a normal exit, and a clean-base relaunch
  reached the Profile 3 main menu with the listener closed; and
- final purge removed four generated bridge/configuration files. The game was
  stopped and the installation again matched the exact 429-file base
  projection with zero overlay files.

This demonstrates the first real observation-to-recommendation vertical slice.
The recommendation policy is intentionally only a smoke-test heuristic; it is
not evidence of strong gameplay quality.
