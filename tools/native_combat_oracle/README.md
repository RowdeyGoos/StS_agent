# Native combat construction and shuffle oracle

Run from the repository root with .NET 9 and the pinned 0.107.1 assembly:

```sh
dotnet build tools/native_combat_oracle/oracle.csproj --artifacts-path /tmp/sts-combat-oracle
dotnet /tmp/sts-combat-oracle/bin/oracle/debug/oracle.dll /path/to/sts2.dll /path/to/dependencies > /tmp/native-combat.json
```

The program verifies the assembly SHA-256 before loading it and resolves dependencies
only from the supplied directory. It registers canonical content and supplies an
explicit in-memory A0 `IRunState` proxy. Unexpected context reads throw. A synthetic
Player/Creature supplies the single target; no RunManager, game launch, profile,
save, history or Cloud access occurs.

Actual native methods generate 184 encounter records: four seed strings, two
explicit total-floor inputs, all 22 Overgrowth encounters and Dense Vegetation.
For each record the oracle calls `GenerateMonstersWithSlots`, constructs/adds
creatures in native roster order, then calls `SetUpForCombat` and `RollMove`.
Records include roster, HP, first move, local monster seed, composition/HP/AI
counters and next-double suffixes. The local monster seed is recorded context,
not a claim that Python implements every monster-local RNG consumer.

Another 48 cases invoke actual `UnstableShuffle` and `StableShuffle` for three
uint32 RNG seeds and sizes 0/1/3/10/16/17/31/64. Mutable Strike, Defend, Bash, Anger
and Shrug It Off copies include upgrades; output indices identify physical copies,
including equal sort keys. This tests the native List.Sort tie permutation as well
as the Fisher–Yates result. It does not exhaust every permutation or force the
introsort heapsort fallback.

The retained [fixture](../../tests/fixtures/headless_native_combat_vectors.json)
is this output with compact JSON records; Python never generates expected values.
The oracle does not execute full combat turns, relic/power hooks or a native run.
The generated first-node floor offset is checked separately from pinned room-entry
IL, and Python continuation tests are labeled regression evidence.
