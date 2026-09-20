# Headless ascension implementation and evidence

Date: 2026-09-20. Target: pinned StS2 0.107.1, solo Ironclad, all unlocked/all seen,
Overgrowth or Underdocks → Hive → Glory → Architect. A0 remains the default;
all cumulative A1–A10 rules now execute through the existing engine. See the
[rule table and API](../HEADLESS_ENGINE.md#ascension-levels).

## Native references executed

The pinned assembly SHA-256 is
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Both reference programs verify it before loading. They use explicit process-local
in-memory context, without game launch or profile/save/history/Cloud access.
Difficulty context is restored/cleared on exit; the getter output records cleanup.
No native combat turns or complete native campaign execute in these new captures.

- [`headless_native_ascension_vectors.json`](../../tests/fixtures/headless_native_ascension_vectors.json):
  11 levels, 102 native monster classes and 4,917 HP/move-property getter evaluations,
  plus elite target counts, removal prices, encounter gold bounds and rarity odds.
  The headless property table includes 403 entries (including repeated inherited
  Decimillipede bindings and unchanged properties). Sewer Clam's initial Plating
  uses an inspected `AddInitialPowers` constant rather than a getter.
- [`headless_native_ascension_maps.json`](../../tests/fixtures/headless_native_ascension_maps.json):
  30 cases: A1/A10 × Overgrowth/Underdocks/Hive/Glory/Spoils × seeds 0/4/42.
  Actual native generation supplies room queues, map geometry, types, edges,
  entrances and RNG counters/suffixes. The small initialization loop mirrors native
  RunManager ordering; A10 draws its distinct second boss after Glory's room/Ancient
  generation. Python compares every recorded value.

The map fixture combines independent native outputs, adding each invocation's mode
and ascension to its rows. JSON is compacted per row without changing values.

### Reproduction

Use .NET 9, the exact assembly and its dependency directory:

```sh
dotnet build tools/native_combat_oracle/oracle.csproj --artifacts-path /tmp/sts-asc-combat
dotnet /tmp/sts-asc-combat/bin/oracle/debug/oracle.dll /path/to/sts2.dll /path/to/dependencies ascensions > /tmp/ascension-values.json
dotnet build tools/native_initialization_oracle/oracle.csproj --artifacts-path /tmp/sts-asc-init
dotnet /tmp/sts-asc-init/bin/oracle/debug/oracle.dll /path/to/sts2.dll /path/to/dependencies glory 10 > /tmp/glory-a10.json
```

Repeat the last invocation with levels 1/10 and the five modes listed above to
reproduce the map fixture rows. These are scalar/generator references, distinct
from the existing queue-runtime campaign harness and its historical evidence.

| Input/output | SHA-256 |
| --- | --- |
| `tools/native_combat_oracle/oracle.cs` | `ff1f8252e18be841fcd8bf8ee40a113121a1f0820c50d5aaf2ee005b3c07dfb0` |
| `tools/native_combat_oracle/ascensions.cs` | `5ea4b2c936395d3d939a998d3f1722bcb0a63a9477dd2378cd5c2c4566b4d93a` |
| `tools/native_combat_oracle/oracle.csproj` | `cb765a6735ef72de272ff46b04ddd8dd9b9db323646cda3be0b521e62a967f38` |
| `tools/native_initialization_oracle/oracle.cs` | `2ce685195ffff1f4f25dda7d0f99b64f77b865e4b80439086d0c8881199e42b1` |
| `tools/native_initialization_oracle/oracle.csproj` | `c27c03352ad84ece5b40e02312e8342c53df40eb807257ff3492ab638c054be2` |
| `tests/fixtures/headless_native_ascension_vectors.json` | `6db530006c35839037b41c51d00b0678739ebd920462327f4d4d87ae1f81de04` |
| `tests/fixtures/headless_native_ascension_maps.json` | `a179e6c72815cfa4bde05120b4dc1fd3527d921d822be66f7076610b5b84f89c` |

## Python and independent review

[`test_ascensions.py`](../../tests/headless/test_ascensions.py) passes **256 cases
in 11.70 seconds**. It covers cumulative starts and level bounds, native getter/map
comparisons, scarcity upgrade rolls, chest rounding and unchanged draws, every
registered encounter at A8/A9, JSON continuation, instance isolation, Test Subject
revival HP, Axebot replacement Strength, and both A10 campaign endings. There are
87 registered encounter entries; event combats are isolated through CombatEngine,
while ordinary encounters use RunEngine. A10 progression tests use boosted HP and
synthetic victories to isolate routing; they do not demonstrate native combat parity.

An independent semantic review compared the run modifiers and monster bindings
against pinned source. It caught and verified corrections for Golden Compass's
single-boss replacement map, Magi Knight Prep, Flyconid Vulnerable Spores and
Axebot's per-life Strength multiplier. Independent startup/JSON probes passed at
all eleven levels; targeted monster execution and JSON probes also passed.

`--route first-slice --ascension 10 --verify-restore` completed the authored CLI
slice with 43 HP. Compilation passes.

The broad run completed with **8,002 passed, 16 failed and 63 setup errors in
1,085.40 seconds (18:05)**. Five failures were legacy assertions that A1/A10 must
reject; those now test the invalid upper bound 11. One existing demo-policy
failure also reproduced on the unchanged base: Abyssal Baths repeatedly selected
Linger until death. The demo now exits after its first immersion; game event
rules are unchanged. The final affected regression run passes **388 tests in
50.34 seconds**, including all 256 new ascension cases. All six existing native
A0 campaign replays passed in the broad run.

The ten remaining failures are outside headless gameplay: eight live-bridge
fixture mocks lack `shutdown`, one ephemeral-socket test is sandbox-blocked, and
one frozen bridge-identity assertion differs from current bridge sources. The
63 setup errors share that frozen identity gate. All ten failures and the shared
setup gate reproduce on unchanged base `0295231` (10 failures / 1 setup error in
1.21 seconds). No bridge code or historical identity pins were changed. The full
repository suite is therefore not green; the ascension and affected headless
regressions have no remaining failures.

Private schemas advance to **combat v41 / run v60**. Run/combat/monster difficulty
mismatches and older formats reject atomically. No public observation encoding or
combat projection was changed. Runtime difficulty has no global mutable owner.

## Remaining acceptance scope

The six existing native three-act victory captures remain A0 evidence. A boosted
native A10 three-act capture, including both Glory bosses and their intervening
resources/RNG, is the next useful acceptance case. No normal-HP test-policy victory
is required. Continue focused low-HP/death/revival cases because boosted HP changes
branch reachability. Native getter and generator parity does not establish every
higher-ascension interaction, inventory combination or seed. Multiplayer,
alternate modes and profile-dependent unlocks remain outside the project scope.
