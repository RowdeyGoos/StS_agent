# Phase 1 BR0 Exact Member Metadata Check

- **Result:** passed for the exact signatures recorded below
- **Evidence tier:** local managed-reflection inspection; no game launch, mod
  load, profile access, or runtime-behavior claim
- **Executed:** 2026-08-30
- **Purpose:** close the overload/type-closure inputs required by the final
  `BR0-PREFLIGHT` forbidden-surface freeze

## Exact inputs

| Artifact | SHA-256 |
| --- | --- |
| pinned arm64 `sts2.dll` | `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18` |
| pinned arm64 `GodotSharp.dll` | `0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289` |
| disposable inspection source | `b1d619ebd3fbb61084198168d334e1bb98f36075728e743f08de90fb3ad0684a` |
| disposable inspection project | `c7951c7c57e5c1fba83a55f8eaa6de6047ac909ed02a09786d6ebb621e1ca3e2` |

The inspection ran with the already acquired .NET SDK `9.0.303`. It loaded the
two exact managed assemblies into a disposable inspection process and queried
only named types and members. It performed no assembly/type enumeration, game
launch, mod load, listener creation, profile/save/Cloud access, or write into
the game installation. Temporary compiler outputs remained outside the game
and repository.

## Confirmed pinned members

The named game accessors have these signatures:

```text
MegaCrit.Sts2.Core.Modding.ModInitializerAttribute..ctor(System.String)
static MegaCrit.Sts2.Core.Nodes.NGame MegaCrit.Sts2.Core.Nodes.NGame.get_Instance()
MegaCrit.Sts2.Core.Nodes.NSceneContainer MegaCrit.Sts2.Core.Nodes.NGame.get_RootSceneContainer()
MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NMainMenu MegaCrit.Sts2.Core.Nodes.NGame.get_MainMenu()
MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NMainMenuSubmenuStack MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NMainMenu.get_SubmenuStack()
MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NSubmenu MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NSubmenuStack.Peek()
```

The named Godot members have these exact usable overloads:

```text
static System.Boolean Godot.GodotObject.IsInstanceValid(Godot.GodotObject)
System.Boolean Godot.CanvasItem.IsVisibleInTree()
static Godot.MainLoop Godot.Engine.GetMainLoop()
static Godot.Callable Godot.Callable.From(System.Action)
static readonly Godot.StringName Godot.SceneTree+SignalName.ProcessFrame
Godot.Error Godot.GodotObject.Connect(Godot.StringName,Godot.Callable,System.UInt32)
System.Void Godot.GodotObject.Disconnect(Godot.StringName,Godot.Callable)
static System.Void Godot.GD.Print(System.String)
static System.Void Godot.GD.PrintErr(System.String)
```

The inspection also confirmed adjacent overloads exist and therefore must not
be admitted accidentally: generic `Callable.From` variants and the
`Godot.GD.Print(System.Object[])` / `PrintErr(System.Object[])` variants. The
preflight policy selects only the non-generic `System.Action` callable and
single-string logging overloads.

## Interpretation

This check establishes named-member availability and exact overload/type
signatures for compilation and metadata-policy inputs. It does not establish
loader discovery, callback readiness, screen semantics, logging behavior,
passivity, teardown, or live compatibility. Those remain compile/package and
isolated live gates.
