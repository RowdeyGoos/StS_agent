# Phase 1 BR0 Preflight Freeze

- **Status:** accepted implementation freeze; all focused independent review
  lanes passed and implementation may begin behind the frozen ownership table
- **Milestone:** `R0a` / `live_probe_v0`
- **Target:** Slay the Spire 2 `v0.107.1`, Steam build `23811903`, macOS arm64
- **Parent design:**
  [PHASE_1_RESTRICTED_BRIDGE_DESIGN.md](PHASE_1_RESTRICTED_BRIDGE_DESIGN.md)
- **Target manifest:**
  [sts2-steam-main-build-23811903-macos-universal.json](../../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)
- **Minimal accessor evidence:**
  [PHASE_1_BR0_ACCESSOR_COMPILE_PROBE.md](research/PHASE_1_BR0_ACCESSOR_COMPILE_PROBE.md)
- **Exact member metadata evidence:**
  [PHASE_1_BR0_EXACT_MEMBER_METADATA_CHECK.md](research/PHASE_1_BR0_EXACT_MEMBER_METADATA_CHECK.md)
- **Pinned loader/screen audit:**
  [PHASE_1_BR0_LOADER_SCREEN_STATIC_AUDIT.md](research/PHASE_1_BR0_LOADER_SCREEN_STATIC_AUDIT.md)
- **Static-audit scope deviation:**
  [PHASE_1_BR0_STATIC_AUDIT_SCOPE_DEVIATION.md](research/PHASE_1_BR0_STATIC_AUDIT_SCOPE_DEVIATION.md)
- **Independent freeze review:**
  [PHASE_1_BR0_PREFLIGHT_REVIEW.md](research/PHASE_1_BR0_PREFLIGHT_REVIEW.md)

## 1. Purpose and authority

This document resolves the `BR0-PREFLIGHT` decisions that must be fixed before
several agents implement the first project-owned bridge in parallel. It freezes
one deliberately tiny read-only vertical slice. It does not authorize or claim
installation, game launch, profile access, runtime compatibility, passivity, or
gameplay control.

The user has explicitly asked the project to implement the bridge and verify it
against the real game. Repository-local implementation, tests, install-free
packaging, and compile-only inspection may therefore proceed after the focused
review passes. The later write into the game or operator-configuration
directories, game launch, live probe, and removal campaign still require an
exact artifact-bound operational checkpoint because those paths and hashes do
not exist yet.

No upstream bridge source is copied. Prior audited projects are evidence about
the loader and game API only. The implementation is project-owned clean source.

## 2. Frozen identity and package shape

| Field | Frozen value |
| --- | --- |
| Mod ID / production assembly | `Sts2AgentBridge` / `Sts2AgentBridge.dll` |
| Loader manifest | sibling `Sts2AgentBridge.json` |
| Display name | `STS2 Agent Bridge` |
| Version | `0.1.0` (`0.1.0.0` assembly/file version) |
| Protocol | `live_probe_v0`; wire `schema_version` is integer `1` |
| Canonical archive | `Sts2AgentBridge-0.1.0.zip`, one two-file overlay directory |
| Fixed listener | literal `127.0.0.1:43117` |
| PCK | absent |
| Gameplay-affecting declaration | `false` |

The loader manifest is canonical UTF-8 JSON with a trailing LF:

```json
{
  "id": "Sts2AgentBridge",
  "name": "STS2 Agent Bridge",
  "author": "StS Agent Project",
  "description": "Restricted read-only local bridge for StS agent research",
  "version": "0.1.0",
  "has_pck": false,
  "has_dll": true,
  "dependencies": [],
  "affects_gameplay": false,
  "min_game_version": "0.107.1"
}
```

The checked-in manifest template is named `Sts2AgentBridge.json`; the generic
name `mod_manifest.json` is not used in the package. The canonical archive
contains exactly these two regular files, in this order, with no symlinks or
extra directory records:

```text
Sts2AgentBridge/Sts2AgentBridge.dll
Sts2AgentBridge/Sts2AgentBridge.json
```

No PDB, configuration, credential, game assembly, dependency from the game,
source file, secondary project assembly, install script, or removal script is
packaged. Release builds set `DebugType=None` and emit no compiler symbols. The
ZIP uses stored entries, timestamp `1980-01-01T00:00:00`, Unix mode `0644`, no
archive/member comment or extra field, no directory entry, and ASCII member
order, so two clean builds in different roots must be byte-identical.

The main assembly exposes one loader entry point:

```csharp
namespace Sts2AgentBridge.Adapters.Bootstrap;

[MegaCrit.Sts2.Core.Modding.ModInitializer("Initialize")]
public static class ModEntry
{
    public static void Initialize()
    {
        BridgeBootstrap.Initialize();
    }
}
```

The pinned loader scans lower-case `.json` files recursively, assigns the
manifest's containing directory as the mod path, and loads exactly
`<mod-path>/<id>.dll`. It treats every extra JSON as another manifest. The
package therefore contains one JSON and keeps the DLL beside it. The package
verifier also proves that the attributed public static initializer exists: on
this pinned loader, absence of an attributed initializer causes an automatic
Harmony `PatchAll` fallback even though the project itself does not reference
Harmony.

There is no Harmony reference or patch. `Sts2AgentBridge.dll` directly
references only `sts2`, `GodotSharp`, and the .NET framework. `Private=false`
applies to the two game references.

The single-DLL rule is a conservative frozen compatibility/package rule. On
the pinned build, `ModManager.TryLoadMod` explicitly loads only
`<manifest-directory>/<id>.dll`; its observed assembly-resolution fallback
special-cases exactly `sts2` and `0Harmony` and provides no evidence that an
arbitrary sibling project DLL would resolve. Production therefore compiles the
pure core source into the main assembly and has no project-assembly runtime
dependency.

## 3. Source layout and ownership

```text
bridge/Sts2AgentBridge/
  README.md
  global.json
  Sts2AgentBridge.sln
  Directory.Build.props
  contracts/live_probe_v0/
    limits.json
    forbidden_surface.json
    package_layout.json
    config_enabled.json
    config_disabled.json
    vectors/
  src/
    Sts2AgentBridge/
      Sts2AgentBridge.csproj
      Core/
        Configuration/
        Hosting/
        Identity/
        Protocol/
        Public/
        Transport/
      Adapters/
        Bootstrap/
        Diagnostics/
        Identity/
        Public/
        Threading/
  tests/
    Sts2AgentBridge.Tests/
      Sts2AgentBridge.Tests.csproj
      Program.cs
      Assertions.cs
      Contract/
      Configuration/
      BuildIdentity/
      Hosting/
      Identity/
      Public/
      Threading/
      Transport/
      Security/
      VerifierFixtures/
  tools/
    run_gate.py
    build_package.py
    verify_forbidden_surface.py
    verify_package.py
    verify_clean_install.py
    verify_operator_config.py
    verify_reproducible.py
    Sts2AgentBridge.Verifier/
      Sts2AgentBridge.Verifier.csproj
  package/
    Sts2AgentBridge.json
```

There is one production project and one production assembly. Core namespaces
contain no Godot or game reference; their host lifecycle, router, canonical
encoders, configuration parser, authenticator, bounded transport, and projector
are tested with fakes. Exact pinned-loader and engine adapters remain thin and
isolated. The package-free executable test project may reference/copy the two
exact game compile assemblies only into a disposable test output when the CLR
needs them; package construction takes inputs from an explicit main-assembly
allowlist and cannot see that test output.

After this freeze passes, parallel writers own disjoint boundaries:

| Package | Exclusive source boundary |
| --- | --- |
| `BR0-CONTRACT` | `Core/Configuration`, `Core/Identity`, `Core/Protocol`; tests `Contract`, `Configuration`, `Identity`; contracts `limits.json`, `config_enabled.json`, `config_disabled.json`, and the entire `vectors/` subtree |
| `BR0-HOST` | `Core/Hosting`; adapters `Bootstrap`, `Diagnostics`, `Identity`, `Threading`; tests `BuildIdentity`, `Hosting`, `Threading` |
| `BR0-TRANSPORT` | `Core/Transport`; tests `Transport`, `Security` |
| `BR0-PUBLIC` | `Core/Public`, `Adapters/Public`; tests `Public` |
| `BR0-PACKAGE` | solution/project/build files; contracts `forbidden_surface.json` and `package_layout.json`; manifest; all verifier/package tools and fixtures; bridge README |
| integration owner | test `Program.cs`/`Assertions.cs`, `.gitignore`, project-level docs, and cross-lane integration |

No package may expand the route, data, or capability surface to satisfy its
own tests.

## 4. Exact wire contract

All successful response bodies are compact UTF-8 JSON with no BOM, indentation,
HTML-relaxed escaping, or trailing LF. Object key order below is canonical.
`schema_version` is the integer `1`. The response media type is
`application/json; charset=utf-8` and every connection closes after one
response.

The authenticated route set is exactly:

```text
GET /probe/v0/health
GET /probe/v0/manifest
GET /probe/v0/public/screen
```

The screen route is not registered in known-incompatible locked mode. There is
no query-string variant, trailing-slash alias, case-folding, percent-decoded
alias, redirect, or `OPTIONS` route.

### 4.1 Health

```json
{"schema_version":1,"lifecycle_state":"running","correlation_id":"00000000000000000000000000000000"}
```

The listener is reachable only while the lifecycle is `running`; build
compatibility is reported by the manifest rather than overloaded onto the
lifecycle field. The correlation identifier is a per-process 16-byte random
value encoded as exactly 32 lowercase hexadecimal characters. It contains no
machine, account, process, path, profile, or game identity.

### 4.2 Manifest

Compatible mode uses this exact shape and ordering:

```json
{"schema_version":1,"protocol":"live_probe_v0","bridge_id":"sts2_agent_bridge","bridge_version":"0.1.0","mode":"live_probe_v0","build_compatibility":"compatible","target_build_manifest_id":"sts2-steam-main-build-23811903-macos-universal","target_game_version":"v0.107.1","target_steam_build_id":"23811903","capabilities":{"observe_public_screen":true,"observe_decision":false,"apply":false,"profile_access":false,"privileged_state":false,"snapshot_restore":false,"bridge_filesystem_writes":false,"host_logging":"sanitized_existing_sink","harmony_patches":false,"outbound_network":false,"hot_unload":false}}
```

Known-incompatible mode changes only `build_compatibility` to
`incompatible_locked` and `observe_public_screen` to `false`. The observed hash
is retained only in protected operational evidence, not exposed over the wire.
The explicit wrong-pre-open-size case is known-incompatible without hashing;
for an exact-size candidate, failure to obtain one complete stable assembly
hash is uncertain identity and starts no listener at all.

### 4.3 Public screen

```json
{"schema_version":1,"status":"ready","screen_kind":"main_menu","actionable":false,"candidates":[]}
```

Allowed combinations are:

| `status` | `screen_kind` | Meaning |
| --- | --- | --- |
| `ready` | `main_menu` | a valid visible `NMainMenu` whose `SubmenuStack.Peek()` is null |
| `ready` | `settings` | a visible `NSettingsScreen`; this takes precedence over a visible menu behind it |
| `waiting` | `unknown` | a successfully executed game-thread read observes that `NGame` or its root container is not yet available |
| `unsupported` | `unknown` | a successful read finds an invalid/invisible menu or stack, a non-settings top submenu, transition ambiguity, or no valid visible allowlisted screen |

`actionable` is always `false`; `candidates` is always the empty array. No
profile name/number, save/run state, seed, unlock, node name/path, type name,
internal identifier, text label, or timing value is serialized.

### 4.4 Errors

Every error has this exact body shape and canonical key order:

```json
{"schema_version":1,"code":"invalid_request","retryable":false,"mutation_state":"none","correlation_id":"00000000000000000000000000000000"}
```

There is no free-form message. `mutation_state` is always `none`. Stable
mappings are:

| HTTP | Code | Condition |
| ---: | --- | --- |
| `400` | `invalid_request` | complete malformed request or disallowed header/query |
| `401` | `unauthenticated` | missing, duplicated, malformed, or incorrect credential |
| `403` | `forbidden` | valid auth with wrong Host or any `Origin` header |
| `404` | `unsupported_content` | unknown route or the absent locked-mode screen route |
| `405` | `read_only` | authenticated well-formed request using a method other than `GET` |
| `413` | `payload_too_large` | declared body/framing or a safely classified size limit exceeded |
| `429` | `rate_limited` | authenticated rate or game-thread queue capacity exceeded |
| `500` | `backend_fault` | serialization/response invariant failure; not retryable |
| `503` | `backend_fault` | dispatcher unavailable after startup, queue/result timeout, callback failure, or an unexpected thrown reader/projector exception; retryable |

No response contains exception text, stack, path, token, request payload,
reflection/game type, or user-provided echo. Authentication is checked before
Host, Origin, method, and route disclosure; syntax and framing/body rejection
remain pre-authentication transport checks. A per-request 16-byte random
correlation ID is encoded as 32 lowercase hex characters. CORS headers are
never emitted.

Every complete response uses an exact `HTTP/1.1` status line, then these
headers in this order: `Content-Type: application/json; charset=utf-8`, exact
`Content-Length`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`,
and `Connection: close`. A `401` additionally inserts
`WWW-Authenticate: Bearer` before `Connection`; a `405` inserts `Allow: GET`;
and a `429` inserts `Retry-After: 1`. `Date`, `Server`, compression, transfer
encoding, and all CORS fields are absent.

### 4.5 Canonical vector set

The checked-in `contracts/live_probe_v0/vectors/` directory must reproduce the
following ASCII bodies byte for byte. `CID` vectors use 32 ASCII zeroes. Tests
replace that field only: health uses the one process correlation ID; an error
uses a freshly generated request correlation ID. No other byte is variable.

| Vector | Body bytes | Canonical body |
| --- | ---: | --- |
| `health_running` | `100` | `{"schema_version":1,"lifecycle_state":"running","correlation_id":"00000000000000000000000000000000"}` |
| `manifest_compatible` | `606` | `{"schema_version":1,"protocol":"live_probe_v0","bridge_id":"sts2_agent_bridge","bridge_version":"0.1.0","mode":"live_probe_v0","build_compatibility":"compatible","target_build_manifest_id":"sts2-steam-main-build-23811903-macos-universal","target_game_version":"v0.107.1","target_steam_build_id":"23811903","capabilities":{"observe_public_screen":true,"observe_decision":false,"apply":false,"profile_access":false,"privileged_state":false,"snapshot_restore":false,"bridge_filesystem_writes":false,"host_logging":"sanitized_existing_sink","harmony_patches":false,"outbound_network":false,"hot_unload":false}}` |
| `manifest_locked` | `616` | `{"schema_version":1,"protocol":"live_probe_v0","bridge_id":"sts2_agent_bridge","bridge_version":"0.1.0","mode":"live_probe_v0","build_compatibility":"incompatible_locked","target_build_manifest_id":"sts2-steam-main-build-23811903-macos-universal","target_game_version":"v0.107.1","target_steam_build_id":"23811903","capabilities":{"observe_public_screen":false,"observe_decision":false,"apply":false,"profile_access":false,"privileged_state":false,"snapshot_restore":false,"bridge_filesystem_writes":false,"host_logging":"sanitized_existing_sink","harmony_patches":false,"outbound_network":false,"hot_unload":false}}` |
| `screen_main_menu` | `98` | `{"schema_version":1,"status":"ready","screen_kind":"main_menu","actionable":false,"candidates":[]}` |
| `screen_settings` | `97` | `{"schema_version":1,"status":"ready","screen_kind":"settings","actionable":false,"candidates":[]}` |
| `screen_waiting` | `98` | `{"schema_version":1,"status":"waiting","screen_kind":"unknown","actionable":false,"candidates":[]}` |
| `screen_unsupported` | `102` | `{"schema_version":1,"status":"unsupported","screen_kind":"unknown","actionable":false,"candidates":[]}` |
| `error_400` | `139` | `{"schema_version":1,"code":"invalid_request","retryable":false,"mutation_state":"none","correlation_id":"00000000000000000000000000000000"}` |
| `error_401` | `139` | `{"schema_version":1,"code":"unauthenticated","retryable":false,"mutation_state":"none","correlation_id":"00000000000000000000000000000000"}` |
| `error_403` | `133` | `{"schema_version":1,"code":"forbidden","retryable":false,"mutation_state":"none","correlation_id":"00000000000000000000000000000000"}` |
| `error_404` | `143` | `{"schema_version":1,"code":"unsupported_content","retryable":false,"mutation_state":"none","correlation_id":"00000000000000000000000000000000"}` |
| `error_405` | `133` | `{"schema_version":1,"code":"read_only","retryable":false,"mutation_state":"none","correlation_id":"00000000000000000000000000000000"}` |
| `error_413` | `141` | `{"schema_version":1,"code":"payload_too_large","retryable":false,"mutation_state":"none","correlation_id":"00000000000000000000000000000000"}` |
| `error_429` | `135` | `{"schema_version":1,"code":"rate_limited","retryable":true,"mutation_state":"none","correlation_id":"00000000000000000000000000000000"}` |
| `error_500` | `137` | `{"schema_version":1,"code":"backend_fault","retryable":false,"mutation_state":"none","correlation_id":"00000000000000000000000000000000"}` |
| `error_503` | `136` | `{"schema_version":1,"code":"backend_fault","retryable":true,"mutation_state":"none","correlation_id":"00000000000000000000000000000000"}` |

Status lines are exactly `HTTP/1.1 200 OK`, `400 Bad Request`, `401
Unauthorized`, `403 Forbidden`, `404 Not Found`, `405 Method Not Allowed`, `413
Payload Too Large`, `429 Too Many Requests`, `500 Internal Server Error`, and
`503 Service Unavailable`. Each `.http` vector is the selected status line plus
`CRLF`, the ordered headers frozen above (including its conditional header), a
blank `CRLF`, and its canonical body with no final newline. `Content-Length` is
the listed decimal body length. Golden tests compare the complete response,
not just parsed JSON.

## 5. Transport and resource limits

The transport is a project-owned, one-request-per-connection HTTP/1.1 subset on
a `TcpListener`, not a general web framework. It never creates a client socket.

| Resource | Frozen limit |
| --- | ---: |
| Listener address / requested OS backlog | `127.0.0.1:43117` / `8` |
| Simultaneously serviced connections | `4` |
| Pre-auth connection bucket | `32/s`, burst `16` |
| Authenticated request bucket | `20/s`, burst `10` |
| Request line | `128` bytes |
| Complete request head, including request line and final CRLFCRLF | `4096` bytes |
| Header count | `8` |
| Header name / value | `32` / `512` bytes |
| Request target | `64` ASCII bytes |
| Error body | `512` bytes |
| Response body | `4096` bytes |
| Header read / response write | `1000 ms` / `1000 ms` |
| Total accepted-connection lifetime | `2000 ms` |
| Outstanding screen reads / work per frame | `2` / `2` |
| Game-thread queue wait / result wait | `250 ms` / `500 ms` |
| Worker shutdown join | `2000 ms` |

Only ASCII request syntax is accepted. The only accepted request headers are
one `Host`, one `Authorization`, and optional single `Accept` and
`Connection: close` fields. `Host` must be exactly `127.0.0.1:43117`.
`Authorization` must be exactly `Bearer ` plus the 64-character token.
`Content-Length` (including zero), `Transfer-Encoding`, `Expect`, `Trailer`,
`TE`, `Upgrade`, every `Origin` value, and every other header are rejected; the
transport does not read a body. Duplicate headers are rejected.
Keep-alive, pipelining, upgrade, absolute-form targets, fragments, and proxy
requests are unsupported and the socket is closed after the response.

Header names are compared ASCII case-insensitively and duplicate detection is
case-insensitive. Methods, request targets, route bytes, Host value, bearer
scheme/value, and other header values are ordinal and case-sensitive. `Accept`
may be absent or exactly `*/*` or `application/json`; every other value is a
complete malformed request. `Connection` may be absent or exactly `close`.

Both rate limiters are process-global monotonic token buckets, initially full,
continuously refilled, and clamped to their burst capacity. The pre-auth bucket
has capacity `16`, refills `32` tokens/second, and charges one token immediately
after TCP acceptance before allocating a worker. The authenticated bucket has
capacity `10`, refills `20` tokens/second, and charges after successful
credential comparison but before Host, Origin, method, mode, or route checks.
They use injected monotonic timestamp ticks in tests; elapsed time is clamped
nonnegative and refill is computed under one lock as
`min(capacity, tokens + elapsed_ticks / frequency * rate)` in `double`; a
request succeeds only when the result is at least `1.0`, then subtracts exactly
`1.0` and records the current tick. There is one credential, so no
per-credential bucket exists.

Syntax and declared body/framing failures are classified before
authentication. For every otherwise well-formed request, invalid authentication
returns `401` even when Host, Origin, method, or route is also wrong. A complete
bounded head declaring any body/framing returns `413`. Head overflow before a
terminator, incomplete-head timeout, pre-auth bucket exhaustion, and
application-handler exhaustion close silently because a safe authenticated
request was not established. The `2000 ms` total connection lifetime is an
outer deadline that overrides every sub-deadline.

The server owns one accept thread and at most four bounded worker tasks. Hard
overflow, incomplete requests, pre-auth rate/connection exhaustion, or cases in
which a complete safe request cannot be established close silently. The
requested OS backlog is a kernel hint, not an exact SYN-queue claim; the four
application handlers and two screen-read slots are exact caps. Startup fails
closed on a port collision and never chooses another interface or port.

The `4096`-byte maximum runs from the first request-line byte through the final
`CRLFCRLF`; the `128`-byte line and per-header limits are subsets of that same
total. The parser uses a fixed `4097`-byte byte buffer solely to detect one-byte
overflow and span-based ASCII parsing,
not `StreamReader`, `ReadLine`, `string.Split`, `Uri`, or a general HTTP parser.
It rejects bytes already buffered after the header terminator and zeroes the
entire request buffer after use. A delayed client can send invalid unframed
bytes after dispatch; those bytes cannot enter a handler or another request
because the protocol closes the connection. The bridge therefore claims a
strict framed dialect, not general HTTP/1.1 compliance or proof that the peer
never transmitted delayed invalid bytes.

## 6. Configuration and credential contract

On the only supported live target, macOS, the bridge calls only
`Environment.GetFolderPath(Environment.SpecialFolder.UserProfile,
Environment.SpecialFolderOption.DoNotVerify)` and appends fixed
`Library/Application Support` components. It never falls back to `HOME`, another
environment variable, the current directory, a search, or a command-line
value. The bridge reads exactly:

```text
<UserProfile>/Library/Application Support/Sts2AgentBridge/r0a/config.json
<UserProfile>/Library/Application Support/Sts2AgentBridge/r0a/credential.hex
```

`UserProfile` is resolved through the OS API and only these fixed components are
appended. This directory is outside the game's `SlayTheSpire2/steam`
profile/Cloud tree.
Neither path is supplied over the wire, read from the mod directory, searched,
enumerated, repaired, or created by the bridge. Unsupported operating systems
or an empty/non-absolute user-profile anchor disable it. Starting at that
trusted anchor, each appended component (`Library`, `Application Support`,
`Sts2AgentBridge`, `r0a`, and both files) is checked in order for exact
containment, absence of a managed `LinkTarget`, and expected
directory/regular-file kind; any ambiguity disables the bridge with no
listener. For each component, `LinkTarget` is read and required to be null
before `Exists`, `Attributes`, `Length`, `GetUnixFileMode`, `Refresh`, or a
`FileStream` open is attempted for that component. The trusted user-profile
anchor itself is resolved by the OS identity API and is not reopened.

The configuration must be byte-for-byte one of two canonical compact UTF-8
files with no BOM or trailing newline. Enabled is `129` bytes with SHA-256
`f8c6ff9592fa330cc9317cd63200c9ee5b0f8023c23efc328f04eea57d6dffea`:

```json
{"schema_version":"live_probe_v0_config_v1","enabled":true,"bind_address":"127.0.0.1","port":43117,"token_file":"credential.hex"}
```

Disabled is the same ordered object with `enabled:false`, is `130` bytes, and
has SHA-256
`132f4c49ee499a52b43d2f0d66edcba1bd78bd5b49777c270636246d85cd3b52`.
The loader still parses strict JSON and independently verifies types, all fields,
no duplicates/unknowns, and every frozen literal; byte equality is an
additional protection. Disabled starts no token read, identity read, engine
callback, or listener. Any other size, byte, syntax, field, or value is invalid
and starts nothing; the hard read cap remains `512` bytes plus one overflow
detection byte.

The token file is exactly 64 lowercase hexadecimal ASCII characters followed
immediately by EOF, representing 32 externally generated random bytes. The
bridge reads at most 65 bytes to prove the bound, never creates or repairs
the token, never includes it in a response/log/manifest, compares presented
credentials in fixed time, and zeroes its owned byte buffer on stop/failure.

The `Sts2AgentBridge` and `r0a` directories must each have Unix mode `0700`;
both files must be regular, non-symlink files with mode `0600`. Group/other
permissions, executable bits, or a platform on which those managed checks
cannot be performed is fail-closed. The bridge independently checks path
derivation/containment, component kinds, managed link targets, required modes,
bounded sizes, strict config semantics, and credential shape. It does not
independently prove effective-user ownership, single-link identity, absence of
granting ACLs, or race-free opened-object identity.

The mandatory external live-run preflight verifies effective-user ownership,
single-link files, absence of granting ACL entries, exact modes, component
containment/kinds/link targets, and exact canonical config SHA-256 immediately
before launch. The config hash, never the token or any token-derived value, is
bound into protected operational evidence. That preflight creates/hashes the
operator artifacts only within its later exact approval; the bridge performs
no filesystem write.

Managed `LinkTarget`/mode checks followed by a read-only `FileStream` open are
not an atomic `O_NOFOLLOW`/`fstat` transaction. This milestone explicitly does
not claim protection from a malicious same-user or privileged process racing
those checks. The protected-directory modes prevent another ordinary OS user
from replacing entries; the external live preflight verifies owner, link
count, containment, modes, and hashes immediately before launch. Adding native
descriptor interop would enlarge the first bridge and is deferred unless the
threat boundary later includes hostile same-UID processes.

## 7. Build identity and engine accessors

The build guard classifies, and at the exact size hashes, the loaded game
assembly location obtained from
`typeof(MegaCrit.Sts2.Core.Modding.ModInitializerAttribute).Assembly.Location`.
It requires file name
`sts2.dll`, macOS on an arm64 process, regular-file size `9,363,456`, exact SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`,
and target manifest ID
`sts2-steam-main-build-23811903-macos-universal` embedded in project-owned
constants. It does not accept a path, hash, or manifest identity from the
client or configuration. The universal bundle's x86-64 assembly is not an
accepted fallback for this first artifact.

A readable regular assembly with a different complete SHA-256 is a known
mismatch and may start authenticated health/manifest in locked mode. A regular
non-symlink `sts2.dll` whose pre-open size differs from `9,363,456` is also a
known mismatch and enters locked mode without a content read. At the exact
path, the guard first constructs `FileInfo`, requires `LinkTarget` to be null,
and only then queries `Exists`, `Attributes`, or `Length`; a pre-existing link
is uncertain identity and starts no listener. At the exact size, the guard
opens the file once with `FileMode.Open`, `FileAccess.Read`, and
`FileShare.Read`; reads at most exactly `9,363,456` bytes into the incremental
SHA-256; requires a complete read; and compares both the open handle length and
path post-read size with the original exact size before comparing the digest.
Digest mismatch is known-incompatible locked mode. Short read, read/hash error,
post-read size change, wrong basename, non-regular kind, symlink, rename/path
ambiguity, wrong OS/architecture, or any uncertain location starts no listener.
No EOF-probe byte is read past the exact cap. The external compile/package
preflight still verifies the complete `429`-file clean base projection.

The compatible public reader's exact owning callsite is
`Sts2AgentBridge.Adapters.Public.PinnedPublicScreenReader.Read()`. Only that
method may reference these pinned game/Godot members and overloads:

```text
static System.Boolean Godot.GodotObject.IsInstanceValid(Godot.GodotObject)
System.Boolean Godot.CanvasItem.IsVisibleInTree()
static MegaCrit.Sts2.Core.Nodes.NGame MegaCrit.Sts2.Core.Nodes.NGame.get_Instance()
MegaCrit.Sts2.Core.Nodes.NSceneContainer MegaCrit.Sts2.Core.Nodes.NGame.get_RootSceneContainer()
MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NMainMenu MegaCrit.Sts2.Core.Nodes.NGame.get_MainMenu()
MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NMainMenuSubmenuStack MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NMainMenu.get_SubmenuStack()
MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NSubmenu MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NSubmenuStack.Peek()
```

That method may additionally use
`MegaCrit.Sts2.Core.Nodes.Screens.Settings.NSettingsScreen` only as an `isinst`
type test. It may use `NMainMenu` only as the getter result and receiver of the
listed visibility/property calls; no constructor, other property, or other
method on either type is admitted.

Static IL establishes that `NGame.MainMenu` returns
`RootSceneContainer.CurrentScene as NMainMenu` and that `NSubmenuStack.Peek()`
uses `Stack<NSubmenu>.TryPeek`, returning null for an empty stack. The reader
does no tree traversal, node enumeration, scene-path lookup, reflection, or
fallback search. A valid visible settings screen at the top of the submenu
stack takes precedence. Only a null top plus a valid visible menu is
`main_menu`; every other top submenu or transition ambiguity is
`unsupported/unknown`. Missing/invalid `NGame` or root container is waiting;
invalid/invisible menu, stack, or top-submenu references handled by the
explicit validity checks are unsupported. An unexpected thrown
reader/infrastructure exception is a retryable `503 backend_fault` and is never
disguised as content.

The dispatcher has exactly two game/Godot-owning callsites. Its
`Sts2AgentBridge.Adapters.Threading.GodotFrameDispatcher..ctor(System.Action)`
may use:

```text
static Godot.MainLoop Godot.Engine.GetMainLoop()
static Godot.Callable Godot.Callable.From(System.Action)
static readonly Godot.StringName Godot.SceneTree+SignalName.ProcessFrame
Godot.Error Godot.GodotObject.Connect(Godot.StringName,Godot.Callable,System.UInt32)
```

The `Connect` flags argument is the literal `0u`. Its
`Sts2AgentBridge.Adapters.Threading.GodotFrameDispatcher.Dispose()` may use only:

```text
static readonly Godot.StringName Godot.SceneTree+SignalName.ProcessFrame
System.Void Godot.GodotObject.Disconnect(Godot.StringName,Godot.Callable)
```

The adapter stores exactly one private `Godot.SceneTree` and one private
`Godot.Callable`, connects that callable to `ProcessFrame`, drains at most two
already-bounded work items per frame, and disconnects the same field values
during explicit component teardown. The known-incompatible path never obtains
the main loop, registers a callback, or constructs the public reader.

## 8. Lifecycle and logging

The core host preserves the parent design's lifecycle and reverse unwind:

```text
created -> starting -> running -> stopping -> stopped
                    \-> faulted
```

Compatible startup is configuration, correlation ID, exact build identity,
stored game callback, then listener. Locked startup performs no main-loop
access, callback registration, public-reader construction, or screen read;
sanitized host logging remains permitted.
Every failed step disposes prior resources in reverse order. Stop first rejects
new work, cancels/fails queued work, disconnects the exact callback, closes the
listener, joins within the bound, and clears the credential buffer.

The mod entry point catches all exceptions and emits only enumerated messages
through `GD.Print`/`GD.PrintErr`: disabled, invalid configuration, uncertain
build identity, known-incompatible locked mode, running, startup failed, and
stopped. It may include the random correlation ID and stable error code, never
an exception message/type, path, hash mismatch value, request detail, token, or
game-derived value. The bridge has no log file or other write sink.

Live `R0a` claims only process-exit cleanup. Explicit disconnect/unwind remains
a component-test claim until a loader-supported live unload exists.

## 9. Forbidden surface policy

Source, metadata-reference, IL/member-reference, and package scans must jointly
reject:

- `HarmonyLib`, `0Harmony`, patch attributes, or dynamic detours;
- `MegaCrit.Sts2.Core.Saves`, profile, progress, preferences, history, replay,
  seed, multiplayer identity, or `DebugOnlyGetState` APIs;
- reflection/dynamic invocation, assembly/type/member enumeration, and
  client-supplied paths, except the exact build-guard sequence
  `typeof(MegaCrit.Sts2.Core.Modding.ModInitializerAttribute).Assembly.Location`;
- button press/click/focus/input/action dispatch, deferred calls, signal
  emission, or scene mutation;
- file/directory create, write, append, copy, move, replace, delete, permission
  change, enumeration, watcher, or arbitrary open;
- process creation, shelling out, environment mutation, native library loading,
  P/Invoke, unsafe code, or dynamic code generation;
- `HttpClient`, `WebRequest`, every `TcpClient` use, UDP, DNS lookup, or any
  socket-connect operation;
- wildcard/IPv6/non-loopback bind, CORS response headers, credential output, or
  a fourth route;
- game-owned DLLs, `Sts2AgentBridge.Core.dll`, unexpected dependencies,
  symlinks, traversal names, or extra files in the package.

The only production filesystem opens are bounded read-only opens in the fixed
configuration/token loader and exact loaded-assembly identity verifier. The
only production network object constructed by bridge code is the literal IPv4
loopback `TcpListener`; each server-side `Socket` is returned by its accept
method rather than constructed. The only game node operations are the Section
7 allowlist. Verifier code and tests may create isolated temporary fixtures but
are never packaged into or loaded by the mod.

The machine-readable policy default-denies `System.Net` and every subnamespace,
including `System.Net.Sockets`, `System.Net.WebSockets`, and
`System.Net.Quic`. It may admit exactly the following production network
members and overloads:

```text
System.Net.IPAddress.Loopback
System.Net.Sockets.TcpListener..ctor(System.Net.IPAddress,System.Int32)
System.Net.Sockets.TcpListener.Start(System.Int32)
System.Net.Sockets.TcpListener.AcceptSocketAsync(System.Threading.CancellationToken)
System.Net.Sockets.TcpListener.Stop()
System.Net.Sockets.Socket.ReceiveAsync(System.Memory<System.Byte>,System.Net.Sockets.SocketFlags,System.Threading.CancellationToken)
System.Net.Sockets.Socket.SendAsync(System.ReadOnlyMemory<System.Byte>,System.Net.Sockets.SocketFlags,System.Threading.CancellationToken)
System.Net.Sockets.Socket.Shutdown(System.Net.Sockets.SocketShutdown)
System.Net.Sockets.Socket.Dispose()
```

`ReceiveAsync` and `SendAsync` must use `SocketFlags.None`. `Shutdown` may use
only `SocketShutdown.Both`. Production never constructs a `NetworkStream` or
`TcpClient`; the verifier rejects both types entirely and rejects every
`Socket.Connect*`, `SendTo*`, `ReceiveFrom*`, DNS, remote-endpoint, or alternate
accept/receive/send overload.

The only outer methods allowed to own those network calls are the exact
`Sts2AgentBridge.Core.Transport.BoundedLoopbackServer` methods
`AcceptLoopAsync(System.Threading.CancellationToken)`,
`HandleAcceptedSocketAsync(System.Net.Sockets.Socket,System.Threading.CancellationToken)`,
`ReceiveBoundedHeadAsync(System.Net.Sockets.Socket,System.Threading.CancellationToken)`,
and
`SendAllAsync(System.Net.Sockets.Socket,System.ReadOnlyMemory<System.Byte>,System.Threading.CancellationToken)`.
For an async method, the metadata verifier follows its
`System.Runtime.CompilerServices.AsyncStateMachineAttribute` to exactly one
compiler-generated nested state-machine type and treats only that type's
`MoveNext()` as the attributed outer method's callsite. It verifies the nested
type is compiler generated, is the exact attribute target, and is referenced by
no other owning method. Lambdas, local functions, manually authored nested
types, un-attributed state machines, and a wildcard for nested types are never
accepted callsites.

The policy separately default-denies `System.IO` and every subnamespace,
including `System.IO.Pipes`, `System.IO.MemoryMappedFiles`, and
`System.IO.Compression`. Its filesystem/path portion may admit exactly the
following members and overloads:

```text
System.IO.Path.IsPathFullyQualified(System.String)
System.IO.Path.GetFullPath(System.String)
System.IO.Path.Combine(System.String,System.String)
System.IO.Path.GetFileName(System.String)
System.IO.Path.DirectorySeparatorChar
System.IO.DirectoryInfo..ctor(System.String)
System.IO.DirectoryInfo.Exists.get
System.IO.FileInfo..ctor(System.String)
System.IO.FileInfo.Exists.get
System.IO.FileInfo.Length.get
System.IO.FileSystemInfo.Attributes.get
System.IO.FileSystemInfo.LinkTarget.get
System.IO.FileSystemInfo.Refresh()
System.IO.File.GetUnixFileMode(System.String)
System.IO.FileStream..ctor(System.String,System.IO.FileMode,System.IO.FileAccess,System.IO.FileShare)
System.IO.FileStream.Length.get
System.IO.FileStream.Read(System.Span<System.Byte>)
System.IO.Stream.Dispose()
```

Every `FileStream` constructor must use `FileMode.Open`, `FileAccess.Read`, and
`FileShare.Read`.
`Sts2AgentBridge.Core.Configuration.StrictConfigurationLoader` may use the
path, directory, file, Unix-mode, bounded-read, and disposal entries only for
the two fixed Section 6 leaves and their fixed ancestors.
`Sts2AgentBridge.Adapters.Identity.PinnedBuildGuard` may use the path, file,
bounded-read, refresh, and disposal entries only for the exact
`Assembly.Location` result in Section 7; it may not call `GetUnixFileMode` or
construct `DirectoryInfo`. No other production type or method may reference an
`System.IO` member. Compiler-emitted `System.IDisposable.Dispose()` calls are
accepted only when their receiver is the allowlisted `FileStream`; they are
normalized to the `System.IO.Stream.Dispose()` entry by the verifier. Within
both allowed classes, the verifier also requires that control flow reaches a
successful `LinkTarget == null` branch for a given `FileSystemInfo` local before
any allowlisted existence, attributes, length, mode, refresh, or open operation
uses its path; known-bad fixtures contain pre-existing links to prove the order
is enforced.

The only admitted `System.Environment` member is
`System.Environment.GetFolderPath(System.Environment+SpecialFolder,System.Environment+SpecialFolderOption)`
inside
`Sts2AgentBridge.Core.Configuration.StrictConfigurationLoader`, with the
literal enum values `UserProfile` and `DoNotVerify`. Every other
`System.Environment` member,
including `CurrentDirectory`, `GetEnvironmentVariable`, command-line access,
and expansion APIs, is denied. The `System.Net` and `System.IO` namespace-family
denials admit TypeRefs only when they are the declaring, parameter, return,
field, or enum types required by one exact member above; this is signature
closure, not a namespace or type wildcard.

The metadata verifier default-denies every `sts2` and `GodotSharp` `TypeRef`,
`MemberRef`, `MethodSpec`, field reference, and custom attribute. The complete
admitted type closure is exactly:

```text
MegaCrit.Sts2.Core.Modding.ModInitializerAttribute
MegaCrit.Sts2.Core.Nodes.NGame
MegaCrit.Sts2.Core.Nodes.NSceneContainer
MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NMainMenu
MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NMainMenuSubmenuStack
MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NSubmenuStack
MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NSubmenu
MegaCrit.Sts2.Core.Nodes.Screens.Settings.NSettingsScreen
Godot.GodotObject
Godot.CanvasItem
Godot.Engine
Godot.MainLoop
Godot.SceneTree
Godot.SceneTree+SignalName
Godot.Callable
Godot.StringName
Godot.Error
Godot.GD
```

Those TypeRefs may occur only as the declaring/parameter/return/field/local/type
test closure of the exact operations and owning locations below; listing a type
does not admit any other member on it. The complete game/Godot member policy is
the seven reader members and the five dispatcher members/field in Section 7,
plus exactly:

```text
MegaCrit.Sts2.Core.Modding.ModInitializerAttribute..ctor(System.String)
static System.Void Godot.GD.Print(System.String)
static System.Void Godot.GD.PrintErr(System.String)
```

The initializer attribute may appear exactly once, on public static type
`Sts2AgentBridge.Adapters.Bootstrap.ModEntry`, with constructor argument
`"Initialize"`; that type must expose exactly one public static
`System.Void Initialize()` initializer with no parameters. `Godot.GD.Print` may
be called only by
`Sts2AgentBridge.Adapters.Diagnostics.GodotBridgeLogger.Info(System.String)` and
`Godot.GD.PrintErr` only by
`Sts2AgentBridge.Adapters.Diagnostics.GodotBridgeLogger.Error(System.String)`.
The `System.Object[]` logger overloads and every generic `Callable.From`
overload are denied.

The sole reflection exception, owned only by
`Sts2AgentBridge.Adapters.Identity.PinnedBuildGuard.Evaluate()`, is the exact IL
sequence and members:

```text
ldtoken MegaCrit.Sts2.Core.Modding.ModInitializerAttribute
static System.Type System.Type.GetTypeFromHandle(System.RuntimeTypeHandle)
System.Reflection.Assembly System.Type.get_Assembly()
System.String System.Reflection.Assembly.get_Location()
```

No other `System.Type`, `System.Reflection`, runtime-handle, assembly-loading,
or metadata-enumeration operation is admitted. The bootstrap attribute and
this `ldtoken` are the only two uses of `ModInitializerAttribute`; no other game
or Godot TypeRef is permitted outside the exact reader, dispatcher, and logger
owners/field signatures above.

The verifier also applies the exhaustive callsite-scoped BCL lists above:
filesystem/path members may appear only in
`Sts2AgentBridge.Core.Configuration.StrictConfigurationLoader` and
`Sts2AgentBridge.Adapters.Identity.PinnedBuildGuard`; inbound
listener/accepted-socket members only in the four exact
`Sts2AgentBridge.Core.Transport.BoundedLoopbackServer` methods or attributed
compiler state machines defined above; and
`System.Security.Cryptography.CryptographicOperations.FixedTimeEquals(System.ReadOnlySpan<System.Byte>,System.ReadOnlySpan<System.Byte>)`
only in
`Sts2AgentBridge.Core.Identity.FixedTimeAuthenticator.Matches(System.ReadOnlySpan<System.Byte>)`.
Any member not listed is rejected rather than inferred from a namespace or
wildcard.

Any unresolved assembly/member/method body is a verifier failure. Source text,
assembly references, type/member references, custom attributes, IL calls,
route-table runtime enumeration, user strings, and ZIP members are all checked;
a string grep alone cannot pass the gate. The executable test harness requires
compatible and locked `Router.RegisteredRoutes` to equal the frozen sets, while
the metadata scan permits only their three exact route literals. Known-bad
fixtures must prove rejection of Harmony/implicit-initializer, profile/save,
write, outbound connect, fourth-route, unsafe/reflection, secondary-DLL, extra
JSON, traversal/symlink, and copied-game-assembly cases.

## 10. Tests and canonical vectors

The no-package console test runner must cover at least:

1. byte-exact health, compatible/locked manifest, all screen combinations, and
   every error vector;
2. strict configuration fields, duplicates, types, UTF-8, size, containment,
   symlink, mode, missing/disabled, token shape, and secret clearing;
3. exact/failing/changing build hashes and proof that uncertain identity starts
   neither engine nor listener;
4. compatible and locked lifecycle order, every startup failure point,
   idempotent concurrent stop, callback/listener disposal, queue cancellation,
   and join bounds;
5. wrong/missing/duplicate auth, fixed-time authenticator behavior at the API
   seam and IL assertion of `CryptographicOperations.FixedTimeEquals`; the full
   malformed/framing/auth/Host/Origin/method/mode/route precedence matrix;
   lowercase/mixed-case security headers; duplicate security headers; and proof
   that every rejection calls neither a route handler nor the game callback;
6. fragmented headers, CR/LF edge cases, absolute targets, pipeline/keep-alive
   attempts, early disconnect, partial response, exact `N-1`/`N`/`N+1` cases
   for every numeric bound, and at least `10,000` deterministic fuzz inputs of
   lengths `0..4097` plus a frozen malformed corpus;
7. public projection precedence, null/hidden/disposed menu and submenu states,
   engine exceptions, repeated stable reads, and proof that output never
   contains fixture-only node names/paths/text;
8. locked mode's exact two-route set and zero engine-reader/dispatcher calls;
9. source/IL/package forbidden-surface checks and exact three-route extraction;
10. two clean builds from different absolute roots producing byte-identical
    canonical ZIPs, with no game assembly copied and unchanged base projection;
11. build-guard wrong size (zero content reads), exact cap, short read,
    digest mismatch, post-size change, wrong kind/link/name/OS/architecture, and
    proof of locked versus no-listener classification;
12. synthetic config owner/mode/ACL/link-count/symlink/component-containment
    cases divided between bridge-managed and external-preflight checks;
13. exception injection containing a fake credential, absolute path, raw
    request, and game type, proving none reaches any response or host log;
14. CORS-header absence on every success and every typed error, exact complete
    `.http` golden vectors, and no raw runtime-generated response; and
15. known-bad source, IL, initializer, dependency, route, and ZIP fixtures that
    prove every important forbidden category is detected;
16. one known-good verifier fixture for every individually permitted
    network/filesystem/environment/game/Godot/reflection member and owning
    callsite, including the attributed compiler async state machines; and
17. known-bad verifier fixtures for each adjacent overload and unlisted
    game/Godot member; wrong listener address, port `43118`, backlog `7`, socket
    flags, shutdown mode, Connect flags, or `FileMode`/`FileAccess`/`FileShare`
    constant; an allowed member moved to a wrong class, lambda, local function,
    manual nested type, forged/unattributed async state machine, or extra field;
    `Environment.CurrentDirectory` and `GetEnvironmentVariable`; and one use
    each of `NetworkStream`, `TcpClient`, WebSockets, QUIC, pipes,
    memory-mapped files, and compression. Each fixture must fail for its named
    rule, so a different generic rejection cannot create a false pass. Separate
    path-provenance fixtures must put an otherwise allowed `FileInfo` or
    `FileStream` use inside the correctly named configuration class but target
    a third hard-coded leaf, and put an otherwise allowed build-guard file use
    on a path not derived from the exact `Assembly.Location` sequence; both
    must fail specifically for path provenance.

Network tests bind only an OS-assigned loopback test port through an injected
test endpoint; production construction refuses any endpoint except the frozen
literal. Tests do not touch the game, Steam, profile, Cloud, or operator config
paths.

## 11. Build and acceptance commands

### 11.1 Deterministic project freeze

`global.json` contains SDK version `9.0.303`, `rollForward: "latestPatch"`, and
`allowPrerelease: false`. The isolated parity toolchain therefore selects
exactly `9.0.303`; the isolated secondary toolchain selects the separately
recorded `9.0.317` in the same feature band. Only parity output is canonical.

The production project freezes:

```text
TargetFramework=net9.0
OutputType=Library
AssemblyName=Sts2AgentBridge
RootNamespace=Sts2AgentBridge
LangVersion=12.0
Nullable=enable
ImplicitUsings=disable
TreatWarningsAsErrors=true
WarningLevel=9999
AllowUnsafeBlocks=false
Deterministic=true
ContinuousIntegrationBuild=true
DebugType=None
DebugSymbols=false
AssemblyVersion=0.1.0.0
FileVersion=0.1.0.0
Version=0.1.0
InformationalVersion=0.1.0
PathMap=<bridge-root>=/_/bridge/;<game-data-root>=/_/game/
```

It has exactly two direct file references, `sts2.dll` and `GodotSharp.dll`,
both `Private=false`, supplied only through an explicit absolute
`STS2GameDataDir`. Missing/non-absolute input fails before reference resolution.
There are no package references, analyzers, generators, custom external imports,
runtime identifiers, self-contained publishing, or post-build/install targets.
The test and verifier projects are executable `net9.0` projects and are never
package inputs.

### 11.2 External verifier interfaces

All bridge tools require absolute arguments, perform no default install/config
search, make no network request, and write only below an explicit absolute
work/output root. On success they emit one canonical compact JSON line. Shared
exit codes are `0` pass, `2` invalid invocation, `3` unsafe path/boundary,
`4` verification mismatch, and `5` internal tool failure.

The clean-install verifier interface is:

```text
python3 tools/verify_clean_install.py \
  --install-root <ABS_INSTALL_ROOT> \
  --target-manifest <ABS_TARGET_MANIFEST> \
  --mode base|overlay \
  [--package <ABS_CANONICAL_ZIP>]
```

It requires a real absolute non-symlink installation root and never follows a
symlink during `lstat`/directory traversal. The target-manifest file must have
SHA-256 `ea9046a6a66e2388be3fb1db4e287e0982ae1b3772bec28546a40ef48c23b470`
and manifest ID `sts2-steam-main-build-23811903-macos-universal`. It hashes every regular file into
`<lowercase_sha256><two spaces><POSIX install-relative path><LF>`, sorted by raw
UTF-8 path bytes, and requires the base projection count `429` and SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Base mode permits no overlay. Overlay mode requires the canonical ZIP and
excludes exactly these non-replacing files before reproducing the base record:

```text
SlayTheSpire2.app/Contents/MacOS/mods/Sts2AgentBridge/Sts2AgentBridge.dll
SlayTheSpire2.app/Contents/MacOS/mods/Sts2AgentBridge/Sts2AgentBridge.json
```

Both overlay files must be regular/non-symlink, byte-identical to the two ZIP
members, and the `mods/Sts2AgentBridge` subtree must contain nothing else. Any
other regular-file delta changes the base count/hash and fails. The output
contains only schema, pass/fail code, mode, base count/hash, and overlay count;
it never prints the installation path.

The separate operator-config verifier interface is:

```text
python3 tools/verify_operator_config.py \
  --user-profile <ABS_OS_USER_PROFILE> --config-root <ABS_FIXED_R0A_ROOT> \
  --expected-config-sha256 <64_LOWER_HEX> \
  --effective-uid <DECIMAL_UID>
```

It requires `config-root` to equal the frozen components below `user-profile`
and, before any path access, requires `effective-uid == os.geteuid()` and
`user-profile == pwd.getpwuid(os.geteuid()).pw_dir` using exact normalized
absolute paths. An identity/root mismatch exits with unsafe-boundary code `3`.
It then performs the external owner, single-link, ACL, modes,
component-kind/link, containment, config-hash, strict config, and
credential-shape checks frozen in Section 6. It never emits or hashes the
credential and never repairs anything.

### 11.3 Exact gate CLI contracts

The implementation must provide these invocation forms unchanged:

```text
python3 tools/run_gate.py test \
  --source-root <ABS_BRIDGE_ROOT> --dotnet <ABS_DOTNET_9_0_303> \
  --game-data-dir <ABS_PINNED_ARM64_DATA> --work-root <ABS_EMPTY_WORK_ROOT>

python3 tools/run_gate.py build \
  --source-root <ABS_BRIDGE_ROOT> --dotnet <ABS_DOTNET> \
  --sdk-role parity|servicing --game-data-dir <ABS_PINNED_ARM64_DATA> \
  --work-root <ABS_EMPTY_WORK_ROOT> --output-dir <ABS_OUTPUT_DIR>

python3 tools/run_gate.py surface \
  --source-root <ABS_BRIDGE_ROOT> --dotnet <ABS_DOTNET_9_0_303> \
  --game-data-dir <ABS_PINNED_ARM64_DATA> --work-root <ABS_EMPTY_WORK_ROOT> \
  --assembly <ABS_BRIDGE_DLL> --policy <ABS_FORBIDDEN_POLICY>

python3 tools/build_package.py \
  --dll <ABS_BRIDGE_DLL> --manifest <ABS_MANIFEST> --output <ABS_ZIP>

python3 tools/verify_package.py \
  --package <ABS_ZIP> --expected-dll-sha256 <64_LOWER_HEX> \
  --expected-manifest-sha256 <64_LOWER_HEX>

python3 tools/verify_reproducible.py \
  --source-root <ABS_BRIDGE_ROOT> --dotnet <ABS_DOTNET_9_0_303> \
  --game-data-dir <ABS_PINNED_ARM64_DATA> \
  --work-root-a <ABS_EMPTY_ROOT_A> --work-root-b <ABS_EMPTY_ROOT_B> \
  --output-dir <ABS_OUTPUT_DIR>
```

`run_gate.py` validates `dotnet --version` as exactly `9.0.303` for parity and
`9.0.317` for servicing, fixes CLI home/NuGet/intermediate/output directories
below `work-root`, disables first-run/telemetry/certificate/build servers,
sets `DirectoryBuildPropsPath` to the exact bridge-owned props file, disables
ambient `Directory.Build.targets`, restores locally with failed sources ignored,
and passes the deterministic properties above. `test` executes the
package-free console harness and its minimum fuzz corpus. `surface` runs the
project-owned metadata verifier and known-bad fixtures. `verify_reproducible.py`
copies the same source into two distinct empty absolute roots, invokes parity
build/package in each, and requires byte-identical DLL, manifest, and ZIP.

Build scripts take explicit `STS2GameDataDir`, output, and temporary-cache
arguments; they have no default game-install search. The primary build uses the
already acquired SDK `9.0.303`/runtime `9.0.7`; `9.0.317` is the secondary
servicing smoke test. Both run with imports restricted, telemetry/first-run
disabled, build servers disabled, warnings as errors, deterministic/path-mapped
settings, and no external package source requirement.

Acceptance order is:

1. core tests and fuzz corpus;
2. exact game-API compile against pinned `sts2.dll` and `GodotSharp.dll`;
3. forbidden-source and metadata/IL surface verification;
4. parity and servicing SDK release builds with zero warnings/errors;
5. two clean different-root parity builds and canonical packages;
6. package member/dependency/version/route verification;
7. exact package, source-tree, toolchain, reference, template, and verifier
   hashes;
8. independent source/package review;
9. confirm the game installation still matches the recorded clean `429`-file
   projection.

The compile gate writes only to repository build-ignored paths or disposable
storage. Passing it does not authorize install or imply that the loader,
screen classifier, passivity, or teardown works in the game.

## 12. Explicit non-goals

`R0a` has no decision envelope, candidates, actions, controller, arming, lease,
journal, profile/save access, run observation, simulator, search, model, or
agent runtime. It does not start/resume a run and cannot play the game. Its
purpose is to prove the minimal safe loader, transport, identity, thread, and
public-screen path before `R0b` expands observation.

## 13. Review record

The complete contract body passed three independent focused reviews at exact
SHA-256
`e452ef2716b09a70d78106840ff2a028ab79a7c8570fd2390101f32bac6240a9`,
supported by exact-member evidence SHA-256
`1862a5fb6700d5a14992679c417541dab921f3c631d8a50afe94e3d2548a258b`:

- contract/test/ownership review: **PASS**; all canonical vectors, parent-design
  Section 20 decisions, writer boundaries, and positive/negative verifier
  fixtures are freeze-complete;
- security/fail-closed review: **PASS**; parser/auth ordering, resource bounds,
  configuration, build guard, exact namespace/member/callsite/path provenance,
  symlink ordering, and async-state-machine rules have no remaining blocker;
- pinned loader/game API review: **PASS**; entrypoint, type closure, public
  reader, dispatcher, logger, build guard, and locked mode match the exact
  pinned evidence.

Earlier blocked revisions are retained as review history in the linked
independent report; each reported ambiguity was corrected and re-reviewed. The
final administrative file hash and exact implementation-start disposition are
also recorded there, avoiding a self-referential checksum in this document.
The user explicitly requested implementation and real verification, so the
repository-local `R0a` packages may now fan out exactly as Section 3 assigns.
Installation, operator-configuration writes, game launch, live probing, and
removal remain behind the later exact artifact-bound operational checkpoint in
Section 1.
