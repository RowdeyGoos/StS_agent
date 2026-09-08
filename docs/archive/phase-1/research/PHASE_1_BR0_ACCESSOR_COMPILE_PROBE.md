# Phase 1 BR0 Minimal Accessor Compile Probe

- **Result:** passed with zero compiler/MSBuild warnings and zero errors
- **Evidence tier:** compile-only; no game launch, mod load, or runtime claim
- **Executed:** 2026-08-29
- **Target:** Slay the Spire 2 `v0.107.1`, Steam build `23811903`, macOS arm64
- **Purpose:** resolve the `BR0-PREFLIGHT` loader-entry and minimal
  public-screen accessor signatures for `R0a`

## Scope

One disposable `net9.0` library was compiled with C# 12 and warnings as errors
against only the pinned arm64 `sts2.dll` and `GodotSharp.dll`. It exercised:

- `[ModInitializer("Initialize")]` on one public static entry class;
- `Engine.GetMainLoop()` cast to `SceneTree` for the dispatcher;
- one stored `Callable.From(...)` connected to and disconnected from
  `SceneTree.SignalName.ProcessFrame`;
- the direct passive reader chain `NGame.Instance`, `NGame.MainMenu`,
  `NMainMenu.SubmenuStack`, and `NSubmenuStack.Peek()`;
- `GodotObject.IsInstanceValid` and `CanvasItem.IsVisibleInTree`; and
- a direct type test for `NSettingsScreen`.

The probe did not reference Harmony, run the output, install a mod, launch the
game, access a profile/save/Cloud path, open a listener, or write into the game
installation. The only game-install content reads were the exact managed
compile inputs already identified by the pinned manifest and their normal
assembly-resolution closure.

## Exact inputs and outputs

| Artifact | SHA-256 |
| --- | --- |
| Probe project | `fc8b6b9db9b9832eb033ceb29bed58bdf258f737bc7931e182695859609e0836` |
| Probe source | `919459a20e75d1b3f7cfa948a313a47579cbb96d7ce90670848af4b62b82e100` |
| `sts2.dll` | `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18` |
| `GodotSharp.dll` | `0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289` |
| Probe DLL (`5,120` bytes) | `42b4c3b84f2282859ee09835c6c544e1511410468c197cf6d84176802b1c5121` |
| Probe PDB (`10,784` bytes) | `a9ad9349b3de6dff3b78598105c4f7442be958ff916d46f8702fabbe11f3d3d4` |
| Probe deps file (`409` bytes) | `fe9e7aa2a67bb1fc1cfbe6d18d1de0e0bd144c1d3bbd40288f13afec7ee31c5c` |

The compiler was the already acquired runtime-parity SDK `9.0.303` with host
runtime `9.0.7` and MSBuild `17.14.13`. Restore was local and completed in
`24 ms`. The compile produced:

```text
Build succeeded.
    0 Warning(s)
    0 Error(s)
```

The previously observed host diagnostic
`CSSM_ModuleLoad(): One or more parameters passed to a function were not valid.`
also appeared and is retained as a host-level diagnostic, not classified as an
MSBuild/compiler warning or a game-API failure.

## Interpretation

This resolves ordinary compile-time availability of the frozen accessors. It
does not prove that the initializer is discovered, that the main loop is ready
at initializer time, that the visible-node classification matches the rendered
UI, that callback teardown works live, or that the read is passive. Those are
the later isolated-load and paired-live gates.
