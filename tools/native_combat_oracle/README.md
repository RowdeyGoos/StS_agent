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

## Combat card and potion generation

Pass `generation` as the third argument to emit the separate
[generation fixture](../../tests/fixtures/headless_native_combat_generation_vectors.json):

```sh
dotnet /tmp/sts-combat-oracle/bin/oracle/debug/oracle.dll /path/to/sts2.dll /path/to/dependencies generation > /tmp/native-combat-generation.json
```

This mode initializes only the synthetic player's empty deck and all-unlocked
state in addition to the construction context. It calls actual CardFactory
`GetDistinctForCombat`/`GetForCombat`, including actual CombatState card creation.
Two pool inventories retain native type, rarity, generation eligibility and energy
metadata. Sixty-six sequences cover 11 caller recipes at six seeds, including
run seed 2's actual combat-generation domain. Sixteen extra cases cover empty,
singleton and duplicate input pools and zero/oversized requests. Twelve potion
sequences call actual in-/out-of-combat factories three times each, including
run seed 2's potion-generation domain. Repeated calls can produce duplicates.

Recipes follow inspected pinned caller methods. These cases execute factories,
not whole card plays, choice screens, insertion hooks or a native combat turn.
No native rarity or upgrade rolls occur in the combat card factory. Caller
upgrades, free-cost flags and optional choices are covered by source inspection
and Python action/restoration regressions. Splash's unsupported foreign pools
and Entropy's transformation factory are outside this fixture. The original
two-argument mode and its construction/shuffle output remain unchanged.


## Native attack interactions

Pass `interactions` as the third argument to emit
[interaction vectors](../../tests/fixtures/headless_native_interaction_vectors.json).
The existing verified assembly loader dispatches to `interactions.cs`; the two
older modes and their outputs are unchanged.

This mode enables the assembly's TestMode and sets the synthetic local net ID to
zero in its disposable process. That ID is required: native AfterDeath returns
without visiting any listeners when LocalContext.NetId is absent. It constructs
fresh in-memory CombatState/Creature/Power objects and an explicit constructor-free
Player (no Player constructor, SaveManager or profile access). Its synthetic
PlayerCombatState supplies turn numbering for in-memory combat history. Player
hook collections are intentionally inactive and empty: these are attack-command
and enemy-power cases, not relic/card-play-wrapper cases.

Each of four seeds executes eight attack recipes: Slippery, full/partial block,
zero damage, changing random targets after death, and random/fixed/area attacks
through Phrog's Infested spawn. Actual AttackCommand.Execute calls actual damage,
death, native Wriggler construction and subsequent target selection. Initial HP
and block are explicit fixtures. Animations and attack FX are omitted; TestMode
suppresses presentation waits. Native hooks are not patched or bypassed.
Results retain per-hit physical target slots, HP/block/overkill, surviving HP and
powers, and target/Niche/AI counters and next-double suffixes.

The IRunState proxy delegates listener enumeration to the actual combat state;
its map-point-history entry is explicitly null. Unexpected context access throws.
No existing player history, save files or Cloud data are read. Each command has a
five-second task bound; invoke the tool in a disposable process. These records
do not execute Horn/Hellraiser, detached hook choices, full card plays, turns,
run boundaries or multiplayer. Horn's automatic ordering correction uses pinned
source plus labeled Python regressions. Paused death hooks now have owned FIFO
continuations and live-pile selection in Python; see the
[paused-hook evidence](../../docs/evidence/paused_death_hooks_2026_09_14.md).
Direct native queue mechanics now execute in the optional isolated Godot fixture
below; actual card/selector composition remains outside that probe.

## Combat transformations and foreign-card census

Pass `transforms` as the third argument to execute actual
`GetDefaultTransformationOptions` and `CreateRandomCardForTransform` in the same
explicit solo/all-unlocked context. The retained
[fixture](../../tests/fixtures/headless_native_transform_vectors.json) contains
ordered options and three replacements at each of five seeds for 174 originals,
including status/curse, basic, event, Ancient, token and quest inputs. Tests compare
the 172 currently implemented originals; native-only Soot and Frantic Escape
remain inventoried. This executes the
factory, not CardCmd.Transform, selectors or complete combat turns.

The fixture also records all eight relevant pool inventories, including 344 solo
foreign definitions (320 ordinary), native type/rarity/cost, generation eligibility,
maximum upgrade and keywords. The census is evidence of scope, not an assertion
that foreign cards have executable headless rules. Native replacement IDs, RNG
counters and suffixes are never synthesized by Python.

## Native paused-hook queue runtime

`queue_runtime/run.py` uses the pinned macOS arm64 game engine with a fresh custom
project pack. It executes actual HookPlayerChoiceContext, GenericHookGameAction and
ActionQueueSet with synthetic choice tasks, a singleplayer-only network proxy and
manual native action driving. It asserts detachment, FIFO, repeated-choice blocking
and combat-end cancellation of waiting/gathering hooks. It records that canceled
coroutines remain suspended until the disposable process exits. This is not a
Horn/card-draw/UI/ActionExecutor-loop or complete native turn fixture.

Use Python 3.10+, .NET 9 and extracted NuGet packages **Godot.NET.Sdk 4.5.1** and
**Godot.SourceGenerators 4.5.1** (package roots containing `Sdk/` and `analyzers/`
respectively). The runner does not download dependencies. Example:

```sh
python3 tools/native_combat_oracle/queue_runtime/run.py \
  --engine '/path/to/SlayTheSpire2.app/Contents/MacOS/Slay the Spire 2' \
  --native-data /path/to/SlayTheSpire2.app/Contents/Resources/data_sts2_macos_arm64 \
  --godot-sdk /tmp/godot-sdk-4.5.1 \
  --godot-generators /tmp/godot-generators-4.5.1 \
  --dotnet /path/to/dotnet \
  --output /tmp/new-native-queue-output
```

The output directory must not exist. Engine, game assembly and GodotSharp hashes
are checked before staging. The runner copies the engine and symlinks native
runtime dependencies, builds the fixture and composes its self-contained runtime
metadata from the native runtime inventory. It does not modify native inputs.
Only four whitelisted project resources enter the custom ZIP. No native game PCK,
autoload or extension manifest is loaded. `_custom_features="dotnet"` enables
exported managed hosting. The native assembly must load in the fixture's component
assembly context, so both use the same initialized GodotSharp instance.

Godot requires a user directory even for this fixture: the runner creates a unique
empty `StsNativeQueueOracle-<uuid>` under macOS Application Support, then removes
only that directory with `rmdir`. Unexpected files cause cleanup to fail visibly.
No real profile/save/history/Cloud directory is read. The runtime process has a
15-second bound (native probe: five seconds); a failed process is not retried.
Output retains build/runtime logs, exact fixture/dependency hashes, native result,
timing and cleanup confirmation in `evidence.json`. See the retained
[queue record](../../docs/evidence/native_hook_queue_2026_09_14.json).


### Silent card values

Pass `silent` as the third argument to the same pinned-assembly oracle to emit
`tests/fixtures/headless_native_silent_values.json`. It enumerates all unlocked solo
Silent entries plus Shiv, makes mutable cards, applies each upgrade and reads
resolved local costs, keywords and dynamic variables. Ancient entries remain in
the census even though the staged ordinary-family implementation excludes them.
The mode does not start a game, access profiles or demonstrate native card execution.

## Regent card inventory

Pass `regent` as the third argument to reproduce
[`headless_native_regent_values.json`](../../tests/fixtures/headless_native_regent_values.json).
This read-only mode instantiates the pinned all-unlocked solo Regent pool and four
generated dependencies, then invokes actual upgrade methods. Its 90 rows retain
energy/Star costs, both X flags, kind, rarity, target, generation eligibility,
keywords and dynamic base/upgrade values. The two Ancient rows are inventoried but
excluded from the ordinary-family implementation. It executes metadata/upgrade
methods, not complete card plays or native turn scheduling.

## Necrobinder card inventory

Pass `necrobinder` as the third argument to reproduce
[`headless_native_necrobinder_vectors.json`](../../tests/fixtures/headless_native_necrobinder_vectors.json).
This read-only mode enumerates the pinned all-unlocked solo pool, Soul and Sweeping
Gaze, then invokes actual upgrade methods. Its 88 rows include costs, X flags,
kind, rarity, targeting, generation eligibility, keywords and dynamic values for
both levels. Forbidden Grimoire and Protector remain inventoried Ancient exclusions.
It executes metadata and upgrades, not native card plays or turn scheduling.
