# Phase 1 STS2MCP Compile-Only Probe

- **Result:** Passed two unchanged-source compiles with zero MSBuild/compiler
  warnings and zero errors, including an SDK/runtime-parity confirmation
- **Evidence tier:** Compile-only exploratory probe; no runtime or behavioral
  claim
- **Executed:** 2026-08-29
- **Candidate:**
  [`STS2MCP@55e064850a68f3b4cde7e5fd525bf9b2dec4e885`](https://github.com/Gennadiyev/STS2MCP/commit/55e064850a68f3b4cde7e5fd525bf9b2dec4e885)
- **Target:** Slay the Spire 2 `v0.107.1`, Steam build `23811903`, macOS arm64
- **Target manifest:**
  [`sts2-steam-main-build-23811903-macos-universal.json`](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)
- **Parent synthesis:**
  [`PHASE_1_STATIC_AUDIT_SYNTHESIS.md`](../PHASE_1_STATIC_AUDIT_SYNTHESIS.md)

## 1. Outcome

The exact upstream Git tree compiled unchanged twice against the arm64 managed
assemblies in the pinned game installation. The primary confirmation used the
historical SDK paired with the game's bundled .NET runtime patch:

```text
STS2_MCP -> <PROBE_ROOT>/out/STS2_MCP.dll

Build succeeded.
    0 Warning(s)
    0 Error(s)
```

The initial build used the current .NET 9 servicing SDK, `9.0.317`, with
framework references at `9.0.19`. Independent review identified that the game
bundles runtime `9.0.7`, so the probe was repeated with SDK `9.0.303`, which
Microsoft's release metadata pairs with runtime `9.0.7`. Both builds passed.

This establishes a narrow but useful fact: the C# compiler and MSBuild assembly
resolver accepted the candidate's referenced types and members against the
exact target assemblies at exact BCL patch parity. It improves the candidate
from a source-only version claim to an exact-build signature-compatibility
result.

It does **not** establish that the mod loads, that Harmony patches apply safely,
that actions or observations are correct, that nominal reads are passive, that
the HTTP service is secure, or that the candidate satisfies the project's
public-information and transaction contracts. No installation or load is
authorized by this result.

## 2. Authorization and isolation boundary

The approved scope allowed:

- downloading the exact pinned MIT-licensed source into disposable storage;
- acquiring two project-scoped .NET 9 SDKs in disposable storage;
- reading the direct and transitively resolved pinned game assemblies during
  compilation;
- writing build intermediates, caches, logs, and outputs only below temporary
  probe directories; and
- recording hashes and diagnostics in this repository.

The probe did not:

- copy a DLL or manifest into the game installation;
- install or enable a mod;
- launch the game or execute the compiled assembly;
- list, read, copy, or modify a profile or save;
- run the optional Python MCP adapter; or
- modify PATH, install a system SDK, or vendor third-party source or binaries
  into this repository.

For each build, the source was copied once more inside a temporary probe root.
MSBuild's normal `obj/` writes therefore affected only those disposable copies,
not the identity-checked extraction.

## 3. Exact source identity

| Field | Recorded value |
| --- | --- |
| Upstream commit | `55e064850a68f3b4cde7e5fd525bf9b2dec4e885` |
| Upstream Git tree | `51b5bfafa025de720c1f38ba5bf631176a194a98` |
| Download archive size | `825447` bytes |
| Download archive SHA-256 | `e377a26839dade398e58c13eade1e4030ac7388c7726a1c3a672dc5b283a2c09` |
| `STS2_MCP.csproj` SHA-256 | `363cb85c2649aca193ede69c28ca487ac587a53f40e1f1af3f00f2ae75e5270b` |
| `STS2_MCP.sln` SHA-256 | `2b4d8829e35de3768ffbc072321a840e657f11af85b87ab3ff3ba91a5791d981` |
| `build.ps1` SHA-256 | `f1f8218ad916ff29d868b4b27fc020414ae68a66929f9388b5453f2350f55e27` |
| `mod_manifest.json` SHA-256 | `f64ee11ebfa9f3cc9dfa89d99fa6125c594e3de4a46ac5e1776327f7a80aa3c9` |

The codeload archive contained one commit-named top-level directory and no
absolute or parent-traversal entries. To avoid trusting that name, the extracted
files and executable modes were added to a fresh SHA-1 Git index. `git
write-tree` reproduced `51b5bfafa025de720c1f38ba5bf631176a194a98`, the tree
reported by GitHub for the pinned commit.

The commit specifically updates three `v0.107.1`-sensitive areas: the removed
combat-manager play-phase property, the `ICombatState` target-resolution type,
and per-player merchant inventory access. The pinned README still says it was
tested on `v0.103.2`; the compile result resolves signature compatibility on our
exact assembly, not that documentation conflict's runtime side.

## 4. Build graph

`STS2_MCP.csproj` is the only .NET project. It is an SDK-style `net9.0` library
using C# 12 with nullable analysis enabled. The normal SDK compile glob includes
the eleven root C# files.

It declares exactly three direct external file references, all marked
`Private=false`:

| Input | SHA-256 in the pinned arm64 game data directory |
| --- | --- |
| `sts2.dll` | `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18` |
| `GodotSharp.dll` | `0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289` |
| `0Harmony.dll` | `ef1898322c9f5c86dc1b0758b272a9c440823b4a41ca9a0b82a3aa6b3d206387` |

MSBuild's `ResolveAssemblyReference` cache shows that resolving the dependency
closure also read five transitive assemblies from the same pinned directory:

| Transitive resolution input | SHA-256 |
| --- | --- |
| `Sentry.dll` | `77132b2e6e1fcbf3a568a53df6e7803e020ec7e4bdd74aa665107ee413cdfa21` |
| `Steamworks.NET.dll` | `1dac8e6e05d89dc1445cebc6e02744c64cdf063adf42f6d1bb22da287ee7d665` |
| `System.IO.Hashing.dll` | `fbe8c2fcb4adc01da5c3c8ed0d727903b8fda1e6b84da3c447c9794615f30664` |
| `SmartFormat.dll` | `6220cde1dafffde5c51a4e23db4bb16e8ec620ef52bac51c0ad5f48c4769f168` |
| `SmartFormat.ZString.dll` | `723e9ffdb9cec9565d9bbbdb27b4d19a9b0ba4ff006e1ab8b94022ae5c426450` |

These are resolution inputs, not undeclared project references or copied
outputs. Recording them prevents the three direct `HintPath` entries from being
mistaken for the entire file-read closure.

There are no package or project references, custom imports or targets, build
commands, analyzers, source generators, resources, package lock, `global.json`,
`Directory.Build.*`, NuGet configuration, runtime identifier, or self-contained
publish setting. The SDK patch version is consequently an unpinned build input
and is recorded below.

The optional Python MCP adapter is not part of this graph and was not installed
or run. The upstream `build.ps1` was also not used: its assembly-presence check
is Windows-specific even though the project file has a correct macOS path
branch. Source inspection found no project-defined install or game-write step.

## 5. Toolchain identity

The probe used official macOS arm64 .NET SDK archives listed in Microsoft's
[.NET 9 download page](https://dotnet.microsoft.com/en-us/download/dotnet/9.0)
and [machine-readable release
metadata](https://dotnetcli.blob.core.windows.net/dotnet/release-metadata/9.0/releases.json).
The exact artifacts were
[`9.0.303`](https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.303/dotnet-sdk-9.0.303-osx-arm64.tar.gz)
and
[`9.0.317`](https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.317/dotnet-sdk-9.0.317-osx-arm64.tar.gz).

| Field | Runtime-parity confirmation | Current-servicing initial build |
| --- | --- | --- |
| SDK | `9.0.303`, commit `5d97611193` | `9.0.317`, commit `26570c2743` |
| MSBuild | `17.14.13+65391c53b` | `17.14.51+25f168cee` |
| Host/runtime | `9.0.7`, commit `3c298d9f00` | `9.0.19`, commit `8381bdb01f` |
| Runtime identifier | `osx-arm64` | `osx-arm64` |
| SDK archive size | `210286441` bytes | `210494986` bytes |
| SDK archive SHA-256 | `20aa6e28fe8a284851cc33ba330d64f0255361e76e4e47ac248342c8c341e747` | `74d0fdf6782c829ddcb7a93e75e81b86febcb57f8305693d0321ee6dc4d319b6` |
| Published and verified SHA-512 | `410999907d6092c52155afc59c3bcac149811851db7318f6fe215e37b377ac1b316cbb595bb21cb526791f396da4cd439e4b2db76d45a825b57cc2f4729a2e2e` | `f707a1c73e84c6d009baab2a274270bd11bbb58cd8244cf59594fe1662f50225d1665878d3af4e4b9649b6feccd95b693cf9cf28e127742b7a4e6287caa3eb2a` |

Microsoft's [SDK `9.0.303` release
note](https://github.com/dotnet/core/blob/main/release-notes/9.0/9.0.7/9.0.303.md)
explicitly pairs that SDK with runtime `9.0.7`. It is retained here only as a
historical parity toolchain for the pinned game; `9.0.317` was the current .NET 9
servicing SDK when this probe ran.

Both extracted launchers were native arm64 Mach-O binaries. No workloads were
installed. `DOTNET_CLI_HOME`, `NUGET_PACKAGES`, first-run state, and telemetry
settings were all redirected or disabled within disposable storage. The initial
build's MSBuild and C#/VB compiler servers reported successful explicit
shutdown; the parity build used `--disable-build-servers`.

## 6. Invocation and diagnostics

The following is the path-sanitized equivalent of the stricter runtime-parity
command that produced the primary recorded outputs:

```bash
env \
  DOTNET_CLI_HOME="<SDK_TEMP>/cli-home" \
  NUGET_PACKAGES="<SDK_TEMP>/nuget-packages" \
  DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
  DOTNET_CLI_TELEMETRY_OPTOUT=1 \
  DOTNET_NOLOGO=1 \
  DOTNET_GENERATE_ASPNET_CERTIFICATE=false \
  "<SDK_TEMP>/sdk/dotnet" build \
  "<PROBE_ROOT>/build-src/STS2_MCP.csproj" \
  --configuration Release \
  --output "<PROBE_ROOT>/out" \
  --disable-build-servers \
  --nologo \
  --verbosity:minimal \
  -p:STS2GameDir="<STEAM_GAME_INSTALL>" \
  -p:STS2GameDataDir="<STEAM_GAME_DATA_ARM64>" \
  -p:ImportDirectoryBuildProps=false \
  -p:ImportDirectoryBuildTargets=false \
  -p:RestoreIgnoreFailedSources=true
```

`<STEAM_GAME_DATA_ARM64>` was the app bundle's
`Contents/Resources/data_sts2_macos_arm64` directory. Both restores completed
locally in under 30 ms; the graph contained no external packages. The initial
build took 21.68 seconds and the parity confirmation took 1.81 seconds.

Both invocations emitted this macOS diagnostic during startup or restore:

```text
CSSM_ModuleLoad(): One or more parameters passed to a function were not valid.
```

This was not classified as an MSBuild/compiler warning and did not prevent
restore or compilation. The parity invocation set
`DOTNET_GENERATE_ASPNET_CERTIFICATE=false` and created no ASP.NET certificate
sentinel, yet the line persisted. Its source and any external effect were not
established, so it remains a retained host-level diagnostic rather than being
silently discarded, attributed to certificate generation, or interpreted as a
game API failure.

## 7. Output identity

Primary runtime-parity outputs:

| Output | Size | SHA-256 |
| --- | ---: | --- |
| `STS2_MCP.dll` | `236544` bytes | `f755a55da563323bd273b806a4109ddfad91f971d8949ae26271621976b4a034` |
| `STS2_MCP.pdb` | `72580` bytes | `b3b6f75add6fd10ba45fd96c51cb260c22932a60acac361d968c4a45829ce9ad` |
| `STS2_MCP.deps.json` | `394` bytes | `632b1ea66d0633ca068645f6bf60e2ba4d8c8c0b887ee7db73ecce7ccf9607d3` |
| Build log | — | `75f3120d8634ac1b255a9976adca526761a8674b41bf3bf7ebee85d1fdd56dc7` |

Initial current-servicing outputs:

| Output | Size | SHA-256 |
| --- | ---: | --- |
| `STS2_MCP.dll` | `236544` bytes | `c0a8147cf934199bfa89d895b2484ca4b09100c263d4d68be00708e30bba2fde` |
| `STS2_MCP.pdb` | `72564` bytes | `60c1d03226bd87a8adaf514fc258bbff6d7c7651e19b8b679f115100e23eb3a5` |
| `STS2_MCP.deps.json` | `394` bytes | `632b1ea66d0633ca068645f6bf60e2ba4d8c8c0b887ee7db73ecce7ccf9607d3` |
| Build log | — | `c9a4c6cb01f28ae92b589db3b7a28110ae39bd3ecc84728a64d5ece54444fc38` |

The dependency file names only the `STS2_MCP` project for
`.NETCoreApp,Version=v9.0`. None of the eight resolved game-owned assemblies was
copied. `mod_manifest.json` is not a build output and was not copied into the
output or game.

The project does not set assembly version properties, so the compiled assembly
metadata defaults to `1.0.0.0` while the manifest and runtime constant say
`0.4.0`. That packaging mismatch is a later loader/operations check, not a
compile failure. The DLL and PDB also embed absolute temporary paths. Their
hashes identify these exact probe outputs but are not cross-directory
reproducibility oracles; the two builds also used different compiler patches and
temporary roots.

The transient source, SDKs, logs, and binaries remain outside the repository and
are not durable project artifacts. The hashes above are the durable identity
record for these exploratory outputs.

## 8. Game-installation integrity

Immediately before the first build and after each build, every regular file
below the Steam game installation root was hashed into the manifest's canonical
sorted record. All three record files were byte-identical:

| Check | Before first build | Final after both builds |
| --- | ---: | ---: |
| Regular-file count | `429` | `429` |
| Installation-tree SHA-256 | `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0` | `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0` |

That value also matches the immutable clean base-install projection in the
target manifest. The compile probe therefore did not add, remove, or change a
regular file in the game installation. The candidate's expected `mods`
directory was absent throughout.

## 9. Interpretation and next gate

The result is sufficient to retain STS2MCP as target-build compatibility and
coverage evidence. The later bridge-boundary decision selected a lean
project-maintained bridge as the first live path, so this result is not a reason
to load or fork the upstream service. The static audit's blockers remain:

- profile mutation, history/path, multiplayer-identity, seed, and other
  privileged fields share the agent-facing service;
- state-changing routes have no expected-state check, idempotency key, result
  cache, controller lease, or ambiguous-commit recovery;
- HTTP mutation is unauthenticated and wildcard CORS is enabled;
- some nominal reads can open merchant or treasure UI;
- load can create configuration and apply a settings-UI Harmony patch; and
- explicit listener disposal, unpatching, or a mod-unload hook was not found.

Compilation also cannot validate reflection-only member names, private-field
access, string-named Harmony targets, Godot node paths, loader discovery, or
runtime sequencing. Those remain load- and behavior-probe questions even when
ordinary C# member references compile.

The restricted surface is now designed in
[`PHASE_1_RESTRICTED_BRIDGE_DESIGN.md`](../PHASE_1_RESTRICTED_BRIDGE_DESIGN.md).
The next technical lane is its design-only `BR0-PREFLIGHT` freeze, followed by a
new compile-only gate if implementation is started. The approved shallow
profile-metadata scope has since passed with disclosed execution caveats; see
the
[`sanitized result`](PHASE_0_PROFILE_METADATA_DISCOVERY_RESULT.md).
Recoverability, Cloud behavior, any content/copy access, bridge installation,
and game launch remain separate later authorization and evidence tiers.
