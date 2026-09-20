# Native initialization oracle

Read-only .NET 9 reference generator for pinned 0.107.1. The program checks the
assembly SHA-256 before loading it and resolves dependencies from an explicit
directory. It registers immutable act/encounter/event/relic model definitions;
it never initializes a game run, launches the game or reads a player profile/save.
A scoped constructor-free RunState and AscensionManager supply process-local
difficulty to native getters; both singleton fields are restored on disposal.

```sh
dotnet build tools/native_initialization_oracle/oracle.csproj --artifacts-path /tmp/sts-init-oracle
dotnet /tmp/sts-init-oracle/bin/oracle/debug/oracle.dll /path/to/sts2.dll /path/to/dependencies > /tmp/native-initialization.json
```

The declared inputs are solo, all unlocked, no modifiers, and the fixed
Overgrowth/Hive/Glory act sequence by default. Pass `underdocks` as the optional
third argument to use Underdocks/Hive/Glory instead:

```sh
dotnet /tmp/sts-init-oracle/bin/oracle/debug/oracle.dll /path/to/sts2.dll /path/to/dependencies underdocks > /tmp/underdocks-initialization.json
```

Pass `hive` to retain the Overgrowth/Hive/Glory startup and emit the Act 2
`StandardActMap`; pass `spoils` for the actual `SpoilsActMap` constructor. Spoils
receives an explicit read-only `IRunState` proxy with only the Hive model, a solo
player-count container and root-seeded `RunRngSet`; unexpected property access fails.
No player data is loaded. Both modes record the map’s own RNG counter and suffix.

This deliberately bypasses the game's profile-dependent lobby act picker.
Headless campaigns support Hive and Glory through the Architect ending.
Pass `glory` to retain the same startup inputs and emit the Act 3 standard map.
Its 13-seed geometry/RNG output is retained in
[`headless_native_glory_map_vectors.json`](../../tests/fixtures/headless_native_glory_map_vectors.json).

`RelicGrabBag.Populate`, `ActModel.GenerateRooms` and `StandardActMap` execute
actual assembly methods. The small shared-Ancient partition loop mirrors the
inspected `RunManager.GenerateRooms` prelude using actual native RNG calls.
The output records source pool metadata, all three generated room sets, final
UpFront counters/suffixes and complete selected maps/counters/suffixes for 13 seeds.
The checked-in Overgrowth and Underdocks fixtures preserve these values with one
compact record per seed. Hive/Spoils fixtures retain their map vectors separately;
all outputs record the verified DLL digest.

Production `generation/room_pools.py` contains immutable metadata extracted from
these native models. Future-act room sets consume startup randomness and are
retained as plain run data; they do not register unimplemented playable content.
Changing the pinned assembly requires a separately reviewed target and evidence.

Pass a fourth argument from `0` through `10` to set ascension. Higher levels emit
seeds `0`, `4`, `42`; A0 retains the original thirteen seeds. At A10 the mirrored
RunManager prelude draws a distinct second Glory boss after the final act's rooms,
and the Glory map includes its second boss point. The retained ascension map
fixture combines A1/A10 for Overgrowth, Underdocks, Hive, Glory and Spoils.
