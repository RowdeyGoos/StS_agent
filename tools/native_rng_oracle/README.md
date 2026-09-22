# Pinned native RNG oracle

This read-only .NET 9 program executes `Rng` and `StringHelper` from the pinned
0.107.1 assembly. It verifies the assembly SHA-256 before loading it. Supply the
assembly and a directory containing its dependencies (including GodotSharp); no
game initialization, gameplay mutation or player-profile access is performed.

Build into disposable output, then capture the JSON:

```sh
dotnet build tools/native_rng_oracle/oracle.csproj --artifacts-path /tmp/sts-rng-oracle
dotnet /tmp/sts-rng-oracle/bin/oracle/debug/oracle.dll /path/to/sts2.dll /path/to/dependencies > /tmp/native-vectors.json
```

`tests/fixtures/headless_native_rng_vectors.json` retains the results. Hash,
integer, float, double, shuffle and Gaussian vectors execute actual assembly
methods. The Neow rows combine the actual RNG with a source-derived composition
algorithm; they **do not execute the full native Neow model**. They explicitly
exclude multiplayer Massive Scroll and unavailable foreign-card Kaleidoscope.

Changing the target assembly requires a new reviewed identity and new evidence,
not simply replacing the checksum. The oracle is a development tool; gameplay
has no .NET or installed-game dependency.
