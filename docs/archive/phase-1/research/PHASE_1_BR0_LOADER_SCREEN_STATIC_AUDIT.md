# Phase 1 BR0 Loader and Minimal Screen Static Audit

- **Result:** implementation-ready loader/package and passive screen accessor
  boundary for `R0a`
- **Evidence tier:** pinned managed-metadata and IL audit; no runtime claim
- **Target:** Slay the Spire 2 `v0.107.1`, Steam build `23811903`, macOS arm64
- **Target manifest:**
  [sts2-steam-main-build-23811903-macos-universal.json](../../../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)
- **Related compile evidence:**
  [PHASE_1_BR0_ACCESSOR_COMPILE_PROBE.md](PHASE_1_BR0_ACCESSOR_COMPILE_PROBE.md)

## 1. Exact artifact identities

| Artifact | SHA-256 |
| --- | --- |
| arm64 `sts2.dll` | `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18` |
| `sts2.xml` | `940ccc0cd6c2be3d75ae831a1b91a3375de571d94fdf896f45b26761148eccce` |
| arm64 `GodotSharp.dll` | `0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289` |

## 2. Loader and package boundary

Pinned `ModManager` metadata and IL establish:

- `ReadModsInDirRecursive` treats every lower-case `.json` file as a candidate
  manifest and recursively visits local mod directories;
- `ReadModManifest` assigns the JSON's containing directory as `Mod.path` and
  rejects a missing/empty manifest `id`;
- `TryLoadMod` loads `<Mod.path>/<id>.dll` when `has_dll` is true and the
  corresponding PCK only when `has_pck` is true;
- `CallModInitializer` reads `ModInitializerAttribute.initializerMethod`,
  requires a public static named method, and invokes it with no arguments; and
- if no attributed initializer type exists, the loader constructs Harmony and
  calls `PatchAll` automatically.

The frozen overlay is therefore exactly:

```text
Sts2AgentBridge/Sts2AgentBridge.json
Sts2AgentBridge/Sts2AgentBridge.dll
```

There is no production secondary project DLL. The manifest explicitly includes
the pinned fields `dependencies: []` and `min_game_version: "0.107.1"`, and the
package verifier must prove the attributed initializer exists to prevent the
loader's implicit Harmony fallback.

`HandleAssemblyResolveFailure` special-cases exactly the game-owned `sts2` and
`0Harmony` names. No observed branch resolves an arbitrary sibling project
assembly. This is why the project freezes a conservative one-production-DLL
package; it is not a claim that every possible CLR dependency-resolution path
has been disproved.

| Loader method | RVA | IL SHA-256 |
| --- | ---: | --- |
| `ReadModsInDirRecursive` | `0x290044` | `b2dde19e5ec29056b6cba0d13816c05115ae985b3d23be0e21ab12439c060735` |
| `ReadModManifest` | `0x290124` | `75d8303b8d8d0fb3c55467071013aac5e1fb8674a5589ceb589fe7b0b643b992` |
| `TryLoadMod` | `0x2904ec` | `c874301918859944f6ba3eecae826988f986ea5bccb8ee0901539ab3906dba94` |
| `CallModInitializer` | `0x2914ec` | `d6f5d7f356a5d51294efbf95029352cd8f4f46af0e52d65bd51ad9baf82b6683` |

## 3. Passive public-screen boundary

The exact public type chain is:

```text
NGame : Godot.Control
NMainMenu : Godot.Control
NMainMenuSubmenuStack : NSubmenuStack
NSubmenuStack : Godot.Control (abstract)
NSubmenu : Godot.Control (abstract)
NSettingsScreen : NSubmenu
```

The reader needs only:

```text
public static NGame NGame.Instance { get; }
public NSceneContainer NGame.RootSceneContainer { get; }
public NMainMenu NGame.MainMenu { get; }
public NMainMenuSubmenuStack NMainMenu.SubmenuStack { get; }
public NSubmenu NSubmenuStack.Peek()
public static bool GodotObject.IsInstanceValid(GodotObject)
public bool CanvasItem.IsVisibleInTree()
```

`NGame.MainMenu` reads `RootSceneContainer.CurrentScene`, performs an `isinst
NMainMenu`, and returns it. `NMainMenu.SubmenuStack` is a field getter.
`NSubmenuStack.Peek()` uses `Stack<NSubmenu>.TryPeek` and returns null when the
stack is empty. No scene-tree search or mutation occurs.

| Member | RVA | IL SHA-256 |
| --- | ---: | --- |
| `NGame.Instance` | `0x60e98` | `805d7442c7d78e7e0937de18ed10ef5fd4f8ef98b11eafda9656b51599294370` |
| `NGame.RootSceneContainer` | `0x60ea7` | `52be7ed9d33a0721cce7d52981016a044df4202e020be551dd8c709212d944da` |
| `NGame.MainMenu` | `0x60ec9` | `49740dda1a14410d33a2875cc78b7932b2ed9ee7b9f7d9b5f07a3b176b6e9b1c` |
| `NMainMenu.SubmenuStack` | `0x11f52f` | `d9bbe5893237825a1518f8b31698ce015631f9058ae96c79c35cf2ce67cbfe6b` |
| `NSubmenuStack.Peek` | `0x12c118` | `b5989b614c1b49982b122fc7d9babba00069d49f09ffd73caa9e513231ab452c` |

The frozen classification is:

1. missing/invalid `NGame.Instance` or root container: `waiting/unknown`;
2. root exists but main menu is missing, invalid, or non-visible:
   `unsupported/unknown`;
3. invalid/unavailable submenu stack: fail closed;
4. visible top `NSettingsScreen`: `ready/settings`;
5. null top plus visible main menu: `ready/main_menu`; and
6. any other top submenu or transition ambiguity: `unsupported/unknown`.

This removes `SceneTree.Root`, `Node.GetChildren`, node paths/names, and broad
scene inspection from the public reader. `Engine.GetMainLoop` is retained only
for the separate stored frame dispatcher.

## 4. Build guard and interpretation

The exact build-location exception is
`typeof(MegaCrit.Sts2.Core.Modding.ModInitializerAttribute).Assembly.Location`.
General reflection,
member/type enumeration, dynamic invocation, and dependency loading remain
forbidden.

Static inspection and compile success do not prove loader discovery, main-loop
readiness, visible-screen semantics, passivity, teardown, or runtime safety.
Those remain isolated live gates.
