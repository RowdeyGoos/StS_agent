# Native initialization oracle

Read-only .NET 9 reference generator for pinned 0.107.1. The program checks the
assembly SHA-256 before loading it and resolves dependencies from an explicit
directory. It registers immutable act/encounter/event/relic model definitions;
it never starts RunManager, launches the game or reads a player profile/save.

```sh
dotnet build tools/native_initialization_oracle/oracle.csproj --artifacts-path /tmp/sts-init-oracle
dotnet /tmp/sts-init-oracle/bin/oracle/debug/oracle.dll /path/to/sts2.dll /path/to/dependencies > /tmp/native-initialization.json
```

The declared inputs are solo, all unlocked, no modifiers, and the fixed
Overgrowth/Hive/Glory act sequence. This deliberately bypasses the game's
profile-dependent lobby act picker. Runtime gameplay for Hive and Glory is not
part of the headless implementation.

`RelicGrabBag.Populate`, `ActModel.GenerateRooms` and `StandardActMap` execute
actual assembly methods. The small shared-Ancient partition loop mirrors the
inspected `RunManager.GenerateRooms` prelude using actual native RNG calls.
The output records source pool metadata, all three generated room sets, final
UpFront counters/suffixes and complete Act 1 maps/counters/suffixes for 13 seeds.
The checked-in fixture preserves these values with one compact record per seed.

Production `generation/room_pools.py` contains immutable metadata extracted from
these native models. Future-act room sets consume startup randomness and are
retained as plain run data; they do not register unimplemented playable content.
Changing the pinned assembly requires a separately reviewed target and evidence.
