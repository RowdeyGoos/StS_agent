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
and Python action/restoration regressions. Splash's foreign pools
and Entropy's transformation factory are outside this original fixture; later modes
below cover their factories. The original
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
below; its optional death-draw mode adds the explicit Horn draw callback described there.

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
project pack. The default `--mode queue` executes actual HookPlayerChoiceContext, GenericHookGameAction and
ActionQueueSet with synthetic choice tasks, a singleplayer-only network proxy and
manual native action driving. It asserts detachment, FIFO, repeated-choice blocking
and combat-end cancellation of waiting/gathering hooks. It records that canceled
coroutines remain suspended until the disposable process exits. This is not a
Horn/card-draw/UI/ActionExecutor-loop or complete native turn fixture.

Pass `--mode death-draw` with the same arguments for actual GremlinHorn.AfterDeath
→ CardPileCmd.Draw/Shuffle → StratagemPower → TheAbacus execution. Six cases use
seeds 0, 2 and 42 with one or three physical Defends initially in discard, empty
hand/draw, zero energy/block, Stratagem 1 and an unused Shuffle stream. The callback
is invoked explicitly with an enemy; no creature is killed by the fixture.
A controlled ICardSelector supplies native choice begin/end signals and selects
the first option. Native hook actions are driven manually. Assertions require
automatic singleton versus detached three-card behavior, exactly zero/one selector
calls, +1 energy/+6 block, one/two cards in hand and physical-card conservation.
The [retained result](../../docs/evidence/native_death_draw_2026_09_19.json)
includes paused/final piles, options and RNG suffixes. Python comparison and
paused JSON continuation live in `tests/headless/test_native_death_draw.py`.

This mode does not run the death dispatcher, enclosing attack, live selector UI,
ActionExecutor frame loop or enemy turn. It uses constructor-free fixture shells
where needed and explicit in-memory localization entries. Native shuffle's FTUE
check accesses SaveManager's **in-memory TestMode MockGodotFileIo**; real save
files and localization initialization are not used.

Pass `--mode attack-hooks` for actual PlayCardAction with Sword Boomerang against
a one-HP Phrog Parasite, Gremlin Horn, Stratagem 1 and Abacus. The shared fixture
runs twelve cases: seeds 0/2/42 × one/three discarded Defends × base/upgraded card.
It creates an actual NetReplayGameService and PlayerChoiceSynchronizer, installs
only explicit RunManager services, and delivers the native replay enqueue,
physical-card choice and resume events. Native PlayCardAction handles legality,
cost payment, OnPlayWrapper/OnPlay and discard; native Hook.AfterDeath creates
its own Horn context. There is no test selector or patched rule. Base deferred
cases choose the top card; upgraded cases choose the bottom card.

Assertions require a finished/discarded outer card, the expected detached hook
count, four surviving children, remaining-hit damage before resumption, Abacus
ordering, final resources/hand and card conservation. The
[retained record](../../docs/evidence/native_attack_hooks_2026_09_19.json) contains
native per-hit history, initial/paused/final piles and enemy data, and four RNG
counters/suffixes. `tests/headless/test_native_attack_hooks.py` compares the
headless play and paused JSON continuation. This is an explicit nonterminal
combat fixture with manually driven actions/replay events; it does not establish
live UI behavior, executor-loop scheduling, multiple-death cancellation or
whole-run parity. It retains the callback mode's in-memory save/localization scope.

Pass `--mode multiple-deaths` for 24 additional cases: seeds 0/2/42 × three/eight
Defends × base/upgraded Sword Boomerang × with/without Duplication. Strength 100
makes each hit lethal. Native powers and the card's real hit counts are used;
no card definition is altered. Later Horn draws shrink the first paused choice.
The replay answer uses the live draw pile, including a deliberate empty answer
when no cards remain (source-backed screen behavior, not actual UI execution).

Terminal cases assert native IsEnding after the fifth kill, then manually deliver
the queued hook and call actual ActionQueueSynchronizer.SetCombatState(NotInCombat)
from an established PlayPhase. This is the cancellation step used by
EndCombatInternal; its preceding room/reward/save lifecycle is **not** executed.
Assertions require canceled actions, suspended callback tasks, an empty queue,
unchanged resources/piles/RNG across cancellation and physical-card conservation.
The final lethal damage is absent from native history by design, so all-dead state
and five target rolls independently check the terminal boundary. The native attack
remains in Play; headless terminal disposal puts it in discard. The
[retained record](../../docs/evidence/native_multiple_deaths_2026_09_19.json) and
Python comparison preserve that difference explicitly. One Horn is paused in
these cases; they do not establish several simultaneously paused contexts.

Pass `--mode enemy-turn` for 36 cases: seeds 0/2/42 × one/three/eight Defends ×
first/last choice × with/without Tools of the Trade. Two prepared native Chompers
attack; the first has one HP, and the player has Thorns 1, Stratagem 1, Gremlin Horn
and Abacus. Actual `CombatManager.ExecuteEnemyTurn` runs through enemy cleanup,
side switch and next-player setup before replay delivers the pending answers.
The single-card case completes Horn automatically, granting block before the
current incoming hit. Other cases defer Abacus until the enemy attacks and new
hand draw finish. Tools' later discard choice stays behind Horn and sees the live
hand after Horn's selected/drawn cards enter it.

[Retained vectors](../../docs/evidence/native_enemy_turn_2026_09_19.json) include
per-hit damage, before/checkpoint/final physical piles, HP/block/energy/turn/side,
enemy slots/HP/next moves, each choice and four RNG counters/suffixes. Python
comparisons in `tests/headless/test_native_enemy_turn.py` restore every exposed
choice from JSON. Empty live Horn choices auto-complete in headless; native replay
explicitly returns an empty list. Separate source-backed terminal tests cover
cancellation without further draws.

This mode uses the native turn manager with prepared state, no encounter entry
hooks and checksums explicitly disabled. It does not launch a run, execute live
UI or the ActionExecutor frame loop, or run combat-end/reward/save processing.
The observed schedule allows enemy work to finish before any replay answer;
other live interleavings and multiple paused death contexts remain unverified.
Shared TestMode save and localization isolation is unchanged.

Pass `--mode autoplay` for 96 Mayhem cases: seeds 0/2/42 × one/three
Defends × one/three autoplay count × with/without a card initially in draw ×
with/without Stratagem × first/last answer. Abacus is present throughout. Actual
Mayhem's callback invokes native gather-before-play; the fixture records every
physical pile at the initial state, pause, each replay answer and completion.
Physical play IDs and five RNG counters/suffixes detect repeated-card plays or
extra shuffles. [Retained vectors](../../docs/evidence/native_autoplay_2026_09_20.json)
include automatic singleton choices and batches shortened by Stratagem taking the
last available card.

Pass `--mode autoplay-flak` for 12 cases: seeds 0/2/42 × with/without Dark Embrace ×
first/last answer. Mayhem gathers Flak Cannon, Slimed and Wound, with three Defends
in discard, Stratagem and Abacus. Flak exhausts the queued status cards; Dark
Embrace can pause before the second status exhaust. Native subsequently attempts
those queued references from their new piles. The
[record](../../docs/evidence/native_autoplay_flak_2026_09_20.json) includes final
enemy HP, exact play order, piles and RNG. Python comparisons in
`tests/headless/test_native_autoplay.py` restore each exposed choice, including
pending exhaust work. Mixed-card candidates compare membership: replay candidates
use raw draw order, not the UI's sort. Physical draw order is checked exactly.

Both modes execute prepared nonterminal callbacks, with owned hook contexts and
manually supplied native replay actions. They omit full player-turn setup, live
UI, the executor frame loop, encounter entry and room/reward/save processing.
They retain the existing in-memory TestMode save/localization isolation. The
native captures exercise Mayhem; shared Havoc/Chaos semantics and terminal
cancellation are not independently demonstrated by these captures. Run either mode
with the same command below plus its `--mode` argument and a fresh output directory.

Pass `--mode draw-cards` for 96 Pillage/Escape Plan cases: seeds 0/2/42 ×
base/upgraded × both cards × eight prepared setups. Setups cover mixed and
all-attack discard piles, singleton/empty piles, nine other cards already in hand,
Fiddle, No Draw and controlled draw-pile depletion during Stratagem. Base cases
answer first and upgraded cases last in raw draw-pile order. All have Stratagem 1
and Abacus. Actual `PlayCardAction` executes the attack/draw/block/result-pile rules.
The [record](../../docs/evidence/native_draw_cards_2026_09_20.json) includes before,
paused and completed physical piles/resources/HP, every replay answer, draw and
play history, five RNG counters/suffixes and explicit controlled moved-card IDs.

The depletion setup deliberately calls actual native `CardPileCmd.Add` to move all
but one draw card into discard while the card action awaits its choice, then
selects the remaining card. This is controlled interference to isolate resumption;
it does not demonstrate a live legal-action/executor sequence causing those moves.
Python comparisons in `tests/headless/test_native_draw_cards.py` restore the paused
state before those moves and final state afterward. They do not claim support for
saving a transient externally modified active selector. Normal choices restore
without interference. Candidate membership and exact draw-pile order are checked;
UI sorting is not executed.

This mode shares the prepared nonterminal combat, manual replay and in-memory
save/localization scope above. A minimal Chomper name string permits native action
logging without loading localization settings. It does not execute encounter
entry, complete turns, the live UI/executor frame loop or room/reward/save cleanup.
Use the command below with `--mode draw-cards` and a fresh output directory.

Pass `--mode remaining-draw` for 180 cases: seeds 0/2/42 × Scrape/Toasty
Mittens/Foregone Conclusion × two variants × ten prepared setups. Variants are
Scrape base/upgraded, Mittens turn one/two and Foregone amount two/three. Setups
include mixed zero/nonzero/X/unplayable cards, singleton/empty piles, hand capacity,
Fiddle, No Draw, controlled depletion, an Innate-first pile, capacity reached before
refill and a two-card automatic all-selection. Variant false answers in raw pile
order; true reverses that order. All have Stratagem 1 and Abacus.

Scrape runs through actual `PlayCardAction`; the other subjects run their actual
`BeforeHandDraw` callback in an owned native hook context. This tests callbacks
without running an entire hand-draw/turn sequence. Depletion uses the same explicit
native pile moves and limited snapshot scope as `draw-cards`. Automatic Foregone
selection is verified in native physical pile order; explicit choice UI sorting
is not exercised. Native effects and definitions are not patched.

The [retained record](../../docs/evidence/native_remaining_draw_2026_09_20.json)
contains recipe definitions, initial/paused/choice/final piles, resources, enemy HP,
Strength, Foregone amount, actual draw/play history and five RNG counters/suffixes.
`tests/headless/test_native_remaining_draw.py` checks these values and JSON
restoration. Its extra Mittens/Dark Embrace test is source-backed, not part of the
native capture. This mode preserves the shared in-memory save/localization scope
and omits encounter entry, live UI/executor frames and room/reward/save processing.
Use `--mode remaining-draw` with the command below and a fresh output directory.

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
15-second bound (queue probe: five seconds; death-draw continuation waits: three
seconds each; attack mode: five-second play and three-second hook execution
waits); a failed process is not retried.
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

## Defect card inventory

Pass `defect` as the third argument to reproduce
[`headless_native_defect_vectors.json`](../../tests/fixtures/headless_native_defect_vectors.json).
This read-only mode enumerates the pinned all-unlocked solo pool plus Fuel,
constructs mutable native cards and invokes their actual upgrade methods. Its 87
rows include costs, targeting, generation eligibility, keywords and dynamic values
at both levels. Biased Cognition and Quadcast are inventoried Ancient exclusions.
It executes metadata/upgrade methods, not native card plays, orb phases or turns.

## Foreign acquisition and transformation factories

Pass `foreign` as the third argument. This reproduces
`tests/fixtures/headless_native_foreign_vectors.json`: 30 Kaleidoscope cases at
five seeds with six reward-hook configurations, ten base/upgraded Splash cases,
and 16 foreign ordinary/basic transformation pools with three sampled RNG seeds.
It retains offers, modifiers, native pool order, counters and next-value suffixes.

The in-memory all-unlocked A0 run context calls actual native StableShuffle,
CreateForReward, GetDistinctForCombat, reward hooks and transformation factories.
Acquisition orchestration follows inspected source; this does not call complete
Kaleidoscope.AfterObtained or Splash.OnPlay, execute a UI or demonstrate native
turn/run parity. It uses TestMode and does not read a profile or save.
See [evidence](../../docs/evidence/foreign_acquisition_2026_09_19.md).

## Hive Act 2 construction

Pass `hive` as the third argument to emit the
[Hive fixture](../../tests/fixtures/headless_native_hive_vectors.json):

```sh
dotnet /tmp/sts-combat-oracle/bin/oracle/debug/oracle.dll /path/to/sts2.dll /path/to/dependencies hive > /tmp/native-hive.json
```

The existing pinned assembly guard and synthetic A0 context are reused with
`CurrentActIndex = 1`. All 20 native Hive encounters run at four seed strings and
two total-floor values (160 rows). Actual `GenerateMonstersWithSlots`, creature
construction, `SetUpForCombat` and `RollMove` supply composition, raw HP, initial
move and composition/Niche/MonsterAi counters plus next-double suffixes.
`AfterAddedToRoom` is not invoked: Decimillipede HP deduplication and initial
power application are not native evidence from this fixture. Full combat turns,
summoning, choices and rewards are likewise outside this oracle. Those mechanics
have source-grounded Python regressions, not native trajectory parity.

## Glory Act 3 construction

Pass `glory` as the third argument to reproduce
[`headless_native_glory_vectors.json`](../../tests/fixtures/headless_native_glory_vectors.json).
The same guarded assembly and in-memory solo A0 context use `CurrentActIndex = 2`.
All 18 Glory encounters run at four seed strings and two total-floor values
(144 rows). Actual native construction and `RollMove` provide composition, raw HP,
initial moves and composition/Niche/MonsterAi counters plus next-double suffixes.
As with Hive, `AfterAddedToRoom`, turn execution, summons, choices and rewards are
excluded. This mode does not launch gameplay or access profiles/saves.

## Duplicate reward option oracle

Pass `reward-edges` as the third argument to reproduce
[`headless_native_reward_edge_vectors.json`](../../tests/fixtures/headless_native_reward_edge_vectors.json).
The mode executes the actual base-odds `CardFactory.CreateForReward`, then actual
encounter option hooks for Lasting Candy, Silver Crucible and Wing Charm. Its 135
explicit contexts span five seeds, three acts and duplicate/unseen/no-power pools.
Physical card values and both Rewards/Niche stream counters and suffixes are kept.
The fixture supplies Candy with two completed combats and marks options as card
rewards. It does not model a run, a reward screen or changing-odds orchestration;
the native changing-odds logger requires an initialized Godot host. No profile or
save access occurs. Source-backed Python tests separately exercise ordinary
changing-odds generation and run continuation.


### Combined shared interactions (`--mode interactions` / `--mode enemy-interactions`)

These modes reuse the same pinned, isolated queue runtime and its replay choice
support. `interactions.cs` runs 84 cases (three seeds, two variants): Scrape with
Hellraiser and optional Reflex/Tactician; direct Drum of Battle exhaustion with
Dark Embrace/Feel No Pain and optional Duplication, Burst, Throwing Axe or Charon's
Ashes; and Draw with Pagestorm plus Iteration, Automation, or Confused/Speedster/
Corrosive Wave, Chains of Binding, or Slither-enchanted Kingly cards. Six cases
explicitly remove Corrosive Wave with the native command while its captured
listener waits; this is controlled lifetime interference, not live-frame evidence.
Variants change upgrade/answer direction and power application
order. An explicitly authored 500-HP Chomper or Queen prevents incidental combat ending.
Cards, draw/discard/play history, Bound/Poison state, power counters, costs, resources and six RNG
counters/suffixes are captured at the initial state, pause, each answer and finish
(as applicable; history/RNG are final records).

`enemy_interactions.cs` runs 24 cases through native `CombatManager.StartTurn`,
including enemy block clearing, moves and next-player setup. Thorns kills the
first Chomper; Horn either draws a Hellraiser Strike against the initially blocked
second Chomper, or pauses a Fiddle-allowed enemy-side draw at Stratagem. The latter
continues after the Fiddle-enhanced next hand. Tools of the Trade optionally adds
another pending choice. Enemy HP/block/moves, per-hit damage, piles, resources and
four RNG streams are compared. Checksums are disabled; replay answers arrive
after enemy work. No live executor frame schedule or full run is demonstrated.

Evidence: [card/power cases](../../docs/evidence/native_interactions_2026_09_20.json)
and [enemy-turn cases](../../docs/evidence/native_enemy_interactions_2026_09_20.json).
Consumers assert exact piles, draw identities, play/discard counts, resources,
status/cost state and RNG. Consumers: `test_native_hook_interactions.py` and
`test_native_enemy_interactions.py`. All exposed boundaries round-trip JSON;
additional headless tests reject malformed/older continuations atomically.
