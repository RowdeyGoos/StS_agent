# Headless game engine

Implement game rules in `game/headless/`. It runs without public projections,
Gymnasium, encoders, training, bridge clients or artifact manifests. The older
combat research API consumes the same combat rules; the accepted reduced public
run backend remains a compatibility fixture. New gameplay does not go through
that fixture's protocol gates.

## Why this structure

The reference examined was
[`zhiyue/sts2-rl-agent/sts2_env` at `1b7e7ce`](https://github.com/zhiyue/sts2-rl-agent/tree/1b7e7ce35e608722650763938c153ea8bc370333/sts2_env).
Its useful separation is content by game concept, combat/run ownership, and
external Gym/bridge consumers. In particular,
[`cards/ironclad_basic.py`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/sts2_env/cards/ironclad_basic.py)
keeps card effects with their factories, while
[`gym_env/combat_env.py`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/sts2_env/gym_env/combat_env.py)
wraps the combat state with action/observation encoding and reward computation.
This is the dependency direction adopted here; no external implementation was copied.

The reference is not a debt-free template. Its
[`cards/base.py`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/sts2_env/cards/base.py)
contains a global instance counter;
[`core/selection.py`](https://github.com/zhiyue/sts2-rl-agent/blob/1b7e7ce35e608722650763938c153ea8bc370333/sts2_env/core/selection.py)
stores resolver callbacks in pending choices. Its combat engine is 3,875 lines
and run manager 2,108 lines at that revision. We use owned IDs, plain pending data,
explicit content catalogs and smaller rule modules. This analysis concerns
maintainability, not verification of that repository's gameplay fidelity.

Our previous coupling was concrete: combat legality consulted encoder capacity;
card execution and metadata were duplicated; reduced room/reward/map rules built
public protocol decisions; and one upgrade added profile handling across several
adapters. The refactor removes these dependencies from the gameplay path.

## Ownership

| Location | Implement here |
| --- | --- |
| [`cards/base.py`](../game/headless/cards/base.py), [`cards/ironclad.py`](../game/headless/cards/ironclad.py), [`cards/effects.py`](../game/headless/cards/effects.py) | Immutable definitions, resolved upgrade values, mutable instances, ordered card effects |
| [`cards/catalog.py`](../game/headless/cards/catalog.py) | Explicit immutable content lookup; extend a catalog once, never register a card in each consumer |
| [`core/combat.py`](../game/headless/core/combat.py), [`core/actions.py`](../game/headless/core/actions.py) | Turn execution, legality and game commands using card instance IDs and stable enemy slots |
| [`core/player.py`](../game/headless/core/player.py), [`core/deck.py`](../game/headless/core/deck.py) | Combat player state, card zones and owned generated-card identities |
| [`monsters/`](../game/headless/monsters/), [`encounters/`](../game/headless/encounters/) | Monster behavior and separate seeded encounter composition |
| [`powers/status.py`](../game/headless/powers/status.py) | Implemented status rules and damage modifiers |
| [`run/ancient.py`](../game/headless/run/ancient.py), [`events/progression.py`](../game/headless/events/progression.py) | Seeded Neow offers and owned unique-event queue progression |
| [`run/state.py`](../game/headless/run/state.py), [`run/engine.py`](../game/headless/run/engine.py) | Persistent state and owned combat handoff |
| [`run/config.py`](../game/headless/run/config.py), [`run/actions.py`](../game/headless/run/actions.py), [`run/flow.py`](../game/headless/run/flow.py) | Declared character/difficulty/pools and direct run command legality/dispatch |
| [`run/deck.py`](../game/headless/run/deck.py), [`run/rewards.py`](../game/headless/run/rewards.py), [`run/rooms.py`](../game/headless/run/rooms.py) | Persistent mutations, reward resolution and room transitions |
| [`run/rest_site.py`](../game/headless/run/rest_site.py), [`run/inventory.py`](../game/headless/run/inventory.py), [`relics/`](../game/headless/relics/), [`potions/`](../game/headless/potions/) | Rest/smith decisions, owned item acquisition/removal, victory healing, permanent max-HP pickup effects and potion effects |
| [`treasure/catalog.py`](../game/headless/treasure/catalog.py), [`run/treasure.py`](../game/headless/run/treasure.py), [`run/treasure_validation.py`](../game/headless/run/treasure_validation.py) | Chest content, gold on opening, optional relic acquisition, pool depletion and private continuation |
| [`shops/catalog.py`](../game/headless/shops/catalog.py), [`run/shop.py`](../game/headless/run/shop.py), [`run/shop_validation.py`](../game/headless/run/shop_validation.py) | Stock, purchases, permanent removal and private continuation validation |
| [`events/catalog.py`](../game/headless/events/catalog.py), [`events/jungle_maze.py`](../game/headless/events/jungle_maze.py), [`run/events.py`](../game/headless/run/events.py) | Native event definitions, content-owned choices/effects and owned event lifecycle |
| [`map/graph.py`](../game/headless/map/graph.py), [`events/safe.py`](../game/headless/events/safe.py) | Authored navigation with explicit encounter/event IDs and shared primitive effects |
| [`core/rng.py`](../game/headless/core/rng.py), [`core/snapshots.py`](../game/headless/core/snapshots.py), [`run/snapshots.py`](../game/headless/run/snapshots.py) | Owned RNG streams and private JSON continuation |
| [`generation/`](../game/headless/generation/), [`core/native_rng.py`](../game/headless/core/native_rng.py), [`core/native_service.py`](../game/headless/core/native_service.py) | Native RNG, stream ownership, probability rules, relic bags and merchant generation |
| `game/simulation/`, `game/backends/`, `game/contracts/`, actor/data/training packages | Compatibility, encoding, public-information policy and external consumption |

The enforced import rule is one-way: consumers may import `game.headless`; that
package may import only itself and the standard library. Existing symbols such as
`game.simulation.card.StrikeCard` remain importable, but re-export the canonical
game classes. There is one combat implementation, not two simulators to maintain.

## Current completion scope

The supported campaign is solo Ironclad A0–A10 on pinned build 0.107.1, with all content
unlocked, through either Act 1 region, Hive, Glory and the Architect ending.
The [next assignments](HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment)
track current completion work. Older batch descriptions below retain their original
validation limits; their mentions of missing later acts, cards or generation do
not override the implemented campaign and catalogs described above.

The grouped native combat/choice/turn, reward and ending fixtures have been rerun
together; see [consolidated verification](#consolidated-native-verification).
Boosted Overgrowth and Underdocks three-act trajectories match native execution; broader
seed/path comparison remains acceptance work. A normal-HP test-policy victory is
not required. Boosted runs use ordinary rules; focused low-HP/death/revival cases
remain necessary because starting HP changes which branches a route encounters.
Passing Python progression with synthetic combat wins does not establish that
fidelity. Other playable character starts, progression-dependent unlocks,
multiplayer and alternate modes are outside the project scope.

## Ascension levels

`RunEngine.ironclad_run(seed=4, ascension=10)` and
`sts-headless-play --route overgrowth-glory --ascension 10 --verify-restore`
select any integer level from 0 through 10. The default remains 0; rules are
cumulative and match the pinned 0.107.1 level definitions.

| Level | Added rule |
| --- | --- |
| 1 — Swarming Elites | Map generation targets eight elites instead of five, including pruning and Spoils Map. |
| 2 — Weary Traveler | Ancients heal 80% of missing HP, rounded down; Neow starts Ironclad at 64/80 HP. |
| 3 — Poverty | Encounter gold bounds are reduced to 75% before sampling; chest gold is reduced after sampling. Fake Merchant retains its fixed 300 gold. |
| 4 — Tight Belt | Start with two potion slots. Relic capacity changes still apply. |
| 5 — Ascender's Bane | Add the Eternal, unplayable, Ethereal curse to the starting deck. |
| 6 — Inflation | Merchant removal starts at 100 gold and increases by 50 per removal, before relic discounts. |
| 7 — Scarcity | Reduced rare-card odds and rarity-offset growth; non-rare upgrade odds grow by 12.5 percentage points per act instead of 25. |
| 8 — Tough Enemies | Native per-monster HP, defensive powers and phase thresholds. |
| 9 — Deadly Enemies | Native per-move damage, hit counts, buffs, generated statuses and other offensive effects. |
| 10 — Double Boss | Draw a different second Glory boss from UpFront at startup and require both boss fights before the Architect ending. No Ancient heal between them. |

Golden Compass retains the native exception: its replacement Glory map has one
boss, although startup still selects and records the second boss. Both ordinary
Glory boss fights retain native final-boss reward suppression; normal relic effects
and combat-start healing continue to apply.

Difficulty belongs to `RunConfig` and each `CombatEngine`/monster, never a global
setting. Immutable `monsters/ascension_values.py` and `ascension_moves.py` bind native
properties to existing rules; phase-dependent effects remain in their monster
modules. Summons inherit their parent's level. Standalone higher-level combats
use an `encounter_factory` accepting construction inputs; zero-argument enemy
factories must not silently create A0 monsters in a higher-level combat.
Private JSON rejects mismatched run/combat/monster levels and older schemas.
Historical map-profile names containing `a0` remain stable identifiers; the owned
ascension config selects difficulty separately.

[Ascension evidence](evidence/headless_ascensions_2026_09_20.md) contains all eleven
native getter levels and 30 native map/initialization comparisons. Python tests
exercise every registered encounter at A8/A9, modifiers, summons/revivals and A10
progression/JSON restoration. Two boosted native A10 campaigns now win from
Overgrowth and Underdocks through both Glory bosses and the Architect: 52 combats
and 1,504 combat actions. Replays compare all four card piles and enchantments,
resources, rewards and all 15 run/player RNG counters, with JSON continuation at
every action. Six earlier native victories remain separate A0 coverage. This is
bounded trajectory evidence, not exhaustive seed/inventory coverage.

Those comparisons corrected Pendulum's persistent three-turn counter and native
end-of-hand status/curse movement through Play and Discard before ordinary hand
flush. Pendulum counts a turn admitted to the ordinary turn-start listener pass,
even if an earlier listener wins combat; it does not count a pass skipped because
the preceding hand draw already won. Suspended callbacks and end-of-hand wrappers
have owned, validated continuations. Older private schemas reject atomically.

## Duplicate card reward choices

Lasting Candy first tries powers absent from the original three offers, then
falls back to the complete eligible power pool. The appended card keeps its own
upgrade roll and late reward modifiers, even when its definition repeats. A pool
without powers produces no extra offer. This applies to ordinary combat rewards,
Prayer Wheel/White Star/Hunt card rewards and Driftwood rerolls.

Main `card_modifiers` and relic/Hunt card reward `modifiers` are now ordered lists
aligned with `offers`. `ChooseRewardCard(definition_id, offer_index)` and
`ChooseExtraReward(reward_index, definition_id, offer_index)` select an exact
position in the active reward. The index is required for repeated definitions;
unique definitions retain the existing index-free command. Declining remains
`definition_id=None`. Acquisition copies only the chosen offer’s modifiers.
Event and relic-pickup reward selectors retain their existing representations.

Name-keyed reward modifiers from older private run formats are rejected rather
than interpreted as physical offers. Restore validates modifier count, card
values and the Lasting Candy duplicate source; ambiguous or mismatched selections
fail before acquisition or RNG changes. Rerolling replaces the complete offer list.

[Native reward vectors](../tests/fixtures/headless_native_reward_edge_vectors.json)
cover 135 cases: five seeds, three act upgrade contexts, duplicate/unseen/no-power
pools, and plain Candy/Silver Crucible/Wing Charm hooks. They execute the actual
base-odds card factory followed by actual encounter reward hooks in isolated native
contexts, comparing physical offers, upgrades, enchantments and Rewards/Niche
counters and suffixes. Changing-odds orchestration is excluded: its logger requires
a Godot host. This fixture does not execute a complete native reward screen or run.

Validation: **5,445 headless/backend/CLI/package tests passed in 485.94 seconds**.
The new position/eligibility/native-vector tests passed 157 cases in 0.67 seconds;
14 native duplicate pairs have different upgrades or enchantments. The installed
wheel passed 429 affected tests in 38.13 seconds, and its CLI restored all 38
commands of the authored first slice. All 235 packaged headless/demo source files
matched the validated checkout. The native oracle built with zero warnings/errors
in 1.02 seconds. Compilation, documentation links and diff checks passed.
Independent semantic review found no blockers in choice identity, modifier
ownership, reward alternatives, snapshot rejection or Slippery Bridge filtering.

## Native randomness and generation

Generated `RunEngine.ironclad_act1()` runs default to `rng_profile="native"`.
`RunEngine()` and `ironclad_slice()` retain the original Python fixture generator;
`ironclad_act1(rng_profile="fixture")` explicitly selects that compatibility profile.
Native runs accept integer or text seeds programmatically: integer `2` is hashed
as text `"2"`, while `"002"` is a different seed. The CLI currently accepts integers.
Changing profiles changes seeded trajectories. Old private snapshots reject rather
than being silently reinterpreted: current schemas are **combat v42 / run v61**.

The pinned 0.107.1 assembly uses **MegaRandom (xoshiro256\*\*, SplitMix64 initialization)**,
not `System.Random`. `core/native_rng.py` implements its UTF-16 seed hash, integer,
binary32 float and double draws, boolean draws, Fisher–Yates shuffle and bounded
Gaussian integer draws. Private snapshots retain all four state words, seed and
counters. Every Gaussian attempt consumes two counted double draws.

`core/native_service.py` owns streams and aliases callers that share native state.
Gold, card rarity/picks/upgrades, potion drops and relic rarity share player
`rewards`; shop picks/prices use `shops`. Neow and ordinary events use the native
model-ID seed salt; entering an event resets its local stream. Solo player slot
zero is supported. Combat uses eight run-owned domains for shuffle, selection,
targeting, card/potion generation, energy costs, monster AI and Niche creature HP. Restore validates
both snapshot views and reestablishes their ownership aliases. Policy RNG remains
outside the game state.

`encounters/randomness.py` separates encounter composition from creature HP and
AI. Composition is seeded by root seed + total floor + native encounter ID hash;
HP uses the shared run Niche stream and avoids existing living enemies' max-HP
values when possible. Fixed-HP monsters still consume a draw. Monsters retain
only their owned AI stream; Phrog/Fogmog summons use the same HP rule. Generated
map floors include the completed Ancient root even when Neow's optional choice
was skipped. Synthetic direct encounters use their explicitly represented floor.

Native initial shuffles use the incoming deck order; discard refills first sort
by native card ID and upgrade level. `core/native_shuffle.py` preserves .NET's
unstable equal-key permutation before Fisher–Yates, so distinct copies retain the
correct identity. Piles retain the engine's existing stack orientation, with native
index-zero draw order translated at the boundary. Catastrophe uses the same native
stable candidate shuffle. Fixture RNG trajectories keep their prior behavior.

[Combat RNG evidence](evidence/combat_rng_2026_09_14.md) covers all 22 encounter
openings, Dense Vegetation and initial/refill permutations through 64 cards.
This is actual native method execution in explicit contexts, not a full native
combat or run. The complete relic/power hook-order audit remains open.

`core/piles.py` composes shared shuffle and generated-entry hooks. Bottled Potential
merges discard, native top-first draw and hand-at-bottom before StableShuffle.
Stratagem resolves before The Abacus, then the triggering draw resumes. Choices
sort by rarity/model ID with stable copy ties; automatic all-card selection keeps
pile order. Abacus grants unpowered block. Opening Innate placement reverses the
Innate group through repeated moves to top, and its draw-count minimum applies
after opening draw modifiers, capped at ten. Opening shuffle does not fire Abacus.
Fresh offered Stomps receive their finished-attack discount only on entering a
combat pile; ordinary moves and clones do not apply that entry discount again.
[Shuffle-hook evidence](evidence/shuffle_hooks_2026_09_14.md) distinguishes pinned
source inspection, actual native shuffle vectors and Python command/restore tests;
it does not claim execution of full native shuffle commands or turns.

[Native attack interaction evidence](evidence/combat_interactions_2026_09_14.md)
now executes actual AttackCommand/CreatureCmd damage and Infested death callbacks
for 32 cases. Per-hit targets, blocked/HP damage, surviving identities, spawned HP
and target/HP/AI RNG suffixes match Python. Slippery remains a post-block HP cap;
the pinned build consumes its stack only on positive unblocked damage.
Automatic Gremlin Horn death draws now run before Infested spawns, so a Hellraiser
Strike cannot attack children that do not exist yet. Unplayable no-target autoplay
moves the card to its result pile without a play or target roll.

`core/hook_scheduler.py` now detaches a Gremlin Horn callback at its first choice.
Infested and the enclosing player action finish before queued hooks resume FIFO.
Each hook owns plain tasks and a play context; nested Seeker Strikes keep their
own card attribution, and repeated choices stay on the active hook. Stratagem
builds its visible options from the then-current draw pile: empty completes;
a previously deferred singleton still requires input. Seeker Strike filters the live draw pile by its original three-card sample. Combat ending cancels waiting hooks.

[Paused-hook evidence](evidence/paused_death_hooks_2026_09_14.md) covers native
source inspection, Python action/restore regressions and direct native FIFO,
repeated-choice and combat-end cancellation checks in an isolated Godot runtime.
The queue mode uses synthetic choices and manually drives native actions.
The separate `death-draw` mode now executes an explicit native Gremlin Horn
AfterDeath callback through actual Draw/Shuffle, Stratagem and Abacus, using a
controlled selector that supplies native choice begin/end signals and an answer.
[Six retained native cases](evidence/native_death_draw_2026_09_19.json) cover
three seeds with automatic singleton and deferred three-card choices. Headless
comparisons match paused/final physical pile order, energy/block, options and
Shuffle counter/next-double suffix, including JSON restoration while paused.
No production rule change was needed. This probe does not execute the death
dispatcher, enclosing attack, live card UI or ActionExecutor frame loop.
The separate `attack-hooks` mode now closes the enclosing play/death-dispatch gap
for Sword Boomerang against a one-HP Phrog with Horn, Stratagem 1 and Abacus.
[Twelve native cases](evidence/native_attack_hooks_2026_09_19.json) execute actual
PlayCardAction (legality, cost, wrapper, OnPlay and discard), damage/death dispatch,
Infested spawning and deferred choice resumption. They cover base/upgraded cards,
three seeds and automatic singleton/deferred three-card draws. The real native
replay-choice path receives an in-memory physical-card answer; there is no test
selector or rule patch. Python matches each hit, surviving slot/HP/power data,
paused/final piles and resources, and Shuffle/CombatTargets/Niche/MonsterAi
counters and next-value suffixes, including JSON continuation at the choice.
The existing game rules matched without changes.

The `multiple-deaths` mode adds [24 native cases](evidence/native_multiple_deaths_2026_09_19.json)
with Strength 100, three/eight discarded Defends and optional Duplication. Later
Horn callbacks draw while the first is paused, leaving a singleton, empty or
larger live draw pile. This exposed and fixed a repeated-refill bug: a draw that
already shuffled now resumes through `draw_after_shuffle`, so consuming its last
card during the pause does not shuffle the discarded attack again or grant a
second Abacus block. JSON continuation preserves this phase; combat v30 / run v46
reject older ambiguous continuations. Malformed amounts, flags and task shapes
are rejected atomically.

Duplicated attacks kill Phrog and all four children. Native terminal guards deny
the final kill's energy/draw; the fixture then invokes the actual synchronizer's
NotInCombat cancellation step and verifies canceled hooks leave piles, resources
and RNG untouched. The full EndCombatInternal room/reward/save lifecycle is not
executed. Native retains the finished attack in Play because result-pile moves
are blocked while ending; headless disposes it into discard. Tests keep that
terminal representation difference explicit. Native history also omits the final
lethal hit; all five headless hits, the terminal state and target RNG count are
checked separately. The empty replay answer is source-backed UI behavior, not a
live screen demonstration.

The `enemy-turn` mode now verifies [36 native cases](evidence/native_enemy_turn_2026_09_19.json)
through actual `CombatManager.ExecuteEnemyTurn`, enemy-side cleanup and the next
player's setup. Thorns kills the first of two attacking Chompers, opening Horn →
Stratagem while the second enemy still has work. Enemy attacks and the next hand
draw finish before the fixture supplies replay answers. The headless scheduler
now defers death choices across that independent work: Abacus cannot incorrectly
block later enemy attacks, and the choice uses the remaining live draw pile.
An automatic singleton draw still completes its hooks immediately, so its Abacus
block protects the current incoming hit.

Three seeds, one/three/eight discarded Defends, first/last answers and optional
Tools of the Trade cover both one and two paused contexts. The later Tools discard
waits behind Horn and refreshes the live hand after Horn resumes. Headless keeps
that setup continuation in its own plain context, including play/event ownership;
JSON restoration preserves both choice boundaries. Per-hit damage, stable enemy
slots/HP/next moves, physical piles, energy/block/HP and four RNG counters/suffixes
match. Empty live replay choices auto-settle on headless activation. Blocking
enemy choices, such as Knowledge Demon’s curse, remain active until their move
finishes; source-backed regressions restore that boundary with Horn and optional
Tools waiting. Source-backed terminal regressions additionally check cancellation
when a later enemy kills the player or dies to Thorns. Combat v31 / run v47 reject the previous scheduling
semantics; malformed context ownership and missing choice powers fail atomically.

Replay events and hook actions are manually driven after enemy work. This proves
that native enemy work and next-player setup can complete while a death hook is
paused; it does not prove every live executor-frame/UI interleaving. The fixture
uses explicit prepared combat state, disables native checksums and omits encounter
entry hooks. It executes neither the full EndCombatInternal room/reward/save
lifecycle nor a live run. Several simultaneously paused **death** contexts,
reactive enemy-side-start choices, multiplayer queues and the broader hook-order
audit remain separate work. The shared fixture retains in-memory TestMode save
and localization isolation.

The `autoplay` mode verifies [96 native Mayhem cases](evidence/native_autoplay_2026_09_20.json)
through the actual power callback and `CardPileCmd.AutoPlayFromDrawPile`.
Native gathers the entire available batch into Play before playing any card. The
headless implementation now does the same: a card discarded by an earlier play
cannot be reshuffled into the same batch. Each gathering step awaits its shuffle
once; if Stratagem takes the last card, resumption stops that batch without another
refill. Owned batch IDs, future card references and collection/play phases remain
plain snapshot data. Actual plays acquire their targets and play frames only when
their turn arrives, and move their physical card to the bottom of Play.

A further [12 native Flak Cannon cases](evidence/native_autoplay_flak_2026_09_20.json)
cover Flak exhausting already gathered Slimed/Wound cards, with optional Dark
Embrace pausing inside that exhaust work. Native still attempts those future cards
from their new piles. Headless preserves those references and requires owned
receipts for pending exhaust tasks, distinguishing legitimate movement from a
forged snapshot task. Tests compare physical piles, resources, damage, physical
play order, choice membership and five RNG counters/suffixes, and restore every
exposed choice through JSON. Nested Havoc/Armaments and terminal cancellation have
additional source-backed regression coverage. Combat v32 / run v48 reject the old
alternating gather/play semantics and missing batch ownership.

These modes manually deliver replay answers to prepared native combat callbacks;
they do not run the full player-turn setup, live UI or executor frame loop. Flak's
mixed-card candidates are compared as membership, with exact physical draw order
checked separately; UI sorting is not claimed. The cases share the fixture's
in-memory save/localization isolation. Havoc and Chaos use the corrected shared
batch path, but these native captures exercise Mayhem specifically. Broader dependent autoplay and whole-run parity remain open; the remaining
card-specific shuffle cases are described below.

The `draw-cards` mode verifies [96 native Pillage/Escape Plan cases](evidence/native_draw_cards_2026_09_20.json)
using actual `PlayCardAction` execution. Three seeds and both upgrades cover mixed
attack/skill piles, all-attack piles, singleton/empty piles, a hand filled by
Stratagem, Fiddle, No Draw and an emptied draw pile on resumption. Pillage repeats
only after an actual attack draw. Escape Plan grants its upgraded/base block only
after an actual skill draw; Stratagem's selected card is an Add and grants neither
draw history nor Escape Plan block. Escape Plan now obeys Fiddle during the player
side, before shuffling or consuming RNG.

Both cards now retain an explicit post-shuffle phase. Resumption checks the live
draw pile and hand capacity without issuing another shuffle. The emptied-pile
cases use controlled interference: while the card's Stratagem choice is paused,
the fixture invokes native `CardPileCmd.Add` to move all but one draw card into
discard, then answers with the remaining card. This establishes native continuation
behavior, not a live executor schedule that produces that interference. Tests
restore the original paused choice, apply the same moves to both copies and compare
the completed result; the transient externally modified selector is not presented
as a supported snapshot boundary.

Exact physical piles, draw history/order, damage, resources, actual card completion
and five RNG counters/suffixes match. Normal choice boundaries and completion
restore from JSON; malformed Escape Plan ownership/arguments and old schemas
reject atomically. Private versions are combat v33 / run v49. As with the other
queue modes, prepared combat state and manual replay omit UI sorting, encounter
entry, live executor frames and room/reward/save processing. Scrape and before-hand-draw callbacks are covered separately below.

The `remaining-draw` mode adds [180 native cases](evidence/native_remaining_draw_2026_09_20.json)
for Scrape and the actual `BeforeHandDraw` callbacks of Toasty Mittens and Foregone
Conclusion. Three seeds and two variants cover ten setups: mixed costs (including
zero, X and unplayable), singleton/empty piles, full hands, Fiddle, No Draw,
controlled depletion, Innate selection, capacity reached before another refill,
and automatic selection of every card. Variants exercise both Scrape upgrades,
Mittens on turns one/two and Foregone amounts two/three.

Scrape now checks draw permission once for its draw operation, honors hand capacity
before shuffling, and resumes a completed shuffle without refilling again. Its
captured actual draws determine the later cost-based discard; Stratagem additions
are excluded. Mittens similarly resumes once, skips Innate cards on turn one when
a non-Innate card exists, and grants Strength even when no card remains to exhaust.
Foregone removes its power when its selection is empty and preserves native
physical draw order when automatically taking all remaining cards. Explicit
selections retain their existing candidate sorting.

Snapshots preserve each new phase and the existing Defect event receipts. Ancient
continuation validation now reads reconstructed saved rules, fixing rejection of
legitimate paused Mittens saves. Source-backed coverage also restores Dark Embrace
pausing inside Mittens' exhaust: Strength arrives only after that draw completes.
Malformed ownership/arguments, missing Scrape receipts and older private formats
reject atomically; current formats are combat v42 / run v61.

The native comparisons check exact piles, draw order, damage, block/energy/Strength,
Foregone removal and five RNG counters/suffixes at prepared callbacks and choices.
Depletion uses explicit native pile moves during a paused Stratagem choice, with
the same controlled-interference and snapshot limits as `draw-cards`. These are
not complete player turns or live executor/UI runs.

The combined [card/power interaction vectors](evidence/native_interactions_2026_09_20.json)
and [enemy-turn interaction vectors](evidence/native_enemy_interactions_2026_09_20.json)
add **108 native cases**, grouped by shared mechanisms rather than individual card batches:

| Mechanism | Native coverage and resulting behavior |
| --- | --- |
| Captured discard and Sly | Scrape retains drawn card references after Hellraiser moves them. All captured eligible cards count as discards, including cards already in discard. Reflex/Tactician autoplay after the complete discard batch, with nested draws and choices. |
| Ordered draw powers | Ordinary Draw, Pillage, Escape Plan and Scrape use the same late-listener dispatcher after Hellraiser. Pagestorm, Iteration, Automation, Confused, Speedster, Corrosive Wave and Queen's Chains of Binding run in application order. Iteration checks draw history when its listener actually runs. Void loses energy after those powers. |
| Card/enchantment order | Kingly Kick and Kingly Punch run their card-owned draw hooks before Slither changes the drawn card's cost. |
| Captured power lifetime | Corrosive Wave listeners survive expiry during a paused death draw. Their last amount freezes on removal, and later reapplication is a separate instance. |
| Cost RNG | Confused consumes its native random roll for X-cost cards too. Compared counters and subsequent values cover combat energy costs as well as shuffle, targets, selection, Niche and AI. |
| Exhaust and replay modifiers | Drum of Battle waits for Dark Embrace, Feel No Pain and relic exhaust hooks before gaining energy. Its native play-count calculation consumes Duplication, Burst or Throwing Axe even though exhausting the card is not a card play. |
| Enemy initialization | All starting enemies clear block before the first move. A Thorns kill followed by Horn → Hellraiser therefore damages a later enemy against its cleared block. |
| Accepted draw continuation | Draw permission is checked once per command. A Horn draw paused during the enemy turn resumes after next-turn setup even when Fiddle is now active. Optional Tools of the Trade adds a second choice context. |

Every exposed decision restores from JSON and continues to matching piles,
resources, enemy state and RNG. Drum exhaust and captured draw-power work have
emitted-event receipts;
invalid owners, task shapes, missing receipts and previous combat/run schemas
reject atomically. These private formats are **combat v42 / run v61**.

The 84 card/power cases execute native card actions or draw/exhaust commands against
an authored 500-HP target (Chomper or Queen); 24 enemy cases execute native
`CombatManager.StartTurn`
through enemy moves and next-player setup. Replay answers are supplied after enemy
work, without a live executor/UI frame loop. Six power-lifetime cases explicitly
remove Corrosive Wave through the native command during a paused choice; four
additional headless regressions reproduce natural end-turn expiry and
reapplication. The record does not claim all card
combinations or whole-run parity. The combat-ending record below extends cleanup
evidence; full room/act transitions and seed/path completion remain open. Unsupported
foreign-character relics such as Tingsha and Tough Bandages were not added by this audit.

The [death/side-start record](evidence/native_death_start_2026_09_20.json) adds
**144 native cases**: three seeds, decks of two/three/eight cards, first/last replay
answers, optional Tools of the Trade, and four prepared scenarios. Six Chompers
with Thorns/Hellraiser/Horn produce two waiting death contexts plus interrupted
player setup. Their later live choices shrink to singleton or empty; the
singleton remains a decision, while the empty choice settles automatically in
headless. Poison kills a Chomper or Phrog before enemy moves; Accelerant cases
also complete three poison ticks against a surviving enemy while Horn waits.

All cases match the existing engine without a game-rule change: piles/resources,
enemy HP/block/Poison/intents, damage history, move counts, four RNG streams and
JSON continuation agree. Native Phrog children retain their `Spawned` move through
this turn: although the native move roster is sampled after side-start hooks,
`Creature.TakeTurn` skips monsters marked `SpawnedThisTurn`. Advancing those
children immediately would have introduced a timing error.

These cases use actual native `CombatManager.StartTurn` through the next player
setup, authored 500-HP player/survivor states and manually driven replay answers.
They do not exercise the live selector/frame loop or full combat-end/room/reward
lifecycle. Extra tests check malformed queued contexts and explicit synthetic
terminal disposal of all waiting work; they are not native end-combat evidence.
That verification-only batch left combat v35 / run v51 unchanged; the subsequent
combat-ending batch below advances the run format.

The [combat-ending record](evidence/native_end_boundary_2026_09_20.json) adds
**180 native cases** through actual `CheckWinCondition`: full `EndCombatInternal`
on victory, `ProcessPendingLoss` on defeat, and `RewardsCmd.GenerateForRoomEnd`
after victory. Three seeds, four HP thresholds and five relic inventories cover
plain victories, lethal Sword Boomerang with a waiting Horn, and explicit native
`CreatureCmd.Kill` defeats. The encounter shell is an ordinary room with authored
Phrog/Infested combat, Strength/Duplication and already-exhausted persistent cards;
it is not a native generated encounter or seed/path run.

The comparisons fixed persistent end-hook ordering. Defeat no longer advances
Guilty, Pumpkin Candle or Toy Box. Victory expires run cards, applies Improvement,
then runs captured relic end callbacks in inventory order before fresh early and
ordinary victory passes. Chosen Cheese now precedes Meat on the Bone; Fishing Rod
uses shared Niche RNG. Toy Box does not suppress an already-captured end callback,
but melted relics are excluded from the later victory pass, including healing and
Sword of Stone evolution. At 40/80 HP, Cheese followed by Meat/Burning Blood now
finishes at 47/81, rather than incorrectly receiving Meat's extra 12 healing.

The native fixture asserts finished-room and won/ended events, power/block/pile
cleanup, canceled queued Horn actions and no runnable combat work. It manually
enqueues replay hooks before the win check; native retains canceled references in
its hook registry. It compares persistent HP/deck/relic state, generated gold,
potion/card offers, changing rarity/potion odds and Rewards/Niche counters and
suffixes. JSON tests resume before lethal resolution, at the finished-combat
handoff and at rewards; additional headless commands claim rewards and leave the
room. Explicit `MockGodotFileIo` stores mock progress in memory. Replay suppresses
run-file saving; no real profile/save/history/Cloud or live reward UI is accessed.
Native reward selection, room exit/event resumption, boss/act handoff and complete
seed/path runs remain outside these vectors. Combat v35 is unchanged; run **v52**
rejects continuations from the previous end-hook/RNG semantics.

The [reward/handoff record](evidence/native_reward_handoff_2026_09_20.json) adds
**48 native cases** using real test-run objects and in-memory persistence. It
registers generated rewards through `RewardsSet.Offer`, claims them through
`RewardsSetSynchronizer`, supplies replay card choices, skips unclaimed rewards,
and exits the root combat room into `MapRoom`. First/last card selection, leaving
all rewards and cancel/reopen are covered across three seeds. Native cancellation
keeps the selector retryable; headless `ChooseRewardCard(None)` is an explicit
forfeit, not that UI cancellation.

Authored simultaneous relic rewards cover all three Eggs, Wing Charm, Silver
Crucible, Silken Tress, Fresnel Lens and fresh Lasting Candy. Acquisition now
refreshes unresolved factory-generated room/extra/event-batch and relic card
offers before pickup effects. Pael’s Wing acquisitions refresh the remaining
Orrery/Lost Coffer/Glass Eye/Dream Catcher offers while preserving nested pickup
priority. It applies only the acquired relic, preserves indexed duplicates
and existing modifiers, and does not consume Crucible/Tress uses: native's pickup
listener calls a different callback from normal reward generation. Fresh Candy
adds nothing. Explicit manual rewards such as Kaleidoscope remain unsubscribed.
Python comparisons include inventory, offers, Rewards/Niche suffixes, rollback,
and JSON continuation before/after pickup and claims.

Actual `ProceedFromTerminalRewardsScreen` resumes a prepared Battleworn Dummy
parent event for Setting 2 victories/timeouts. Random deck upgrades now occur
immediately on resume, without an extra result-page decision; the same timing
applies to its potion/relic outcomes in headless regression tests. Native
`EnterNextAct` from prepared finished bosses verifies Act 1→2 and Act 2→3 room
handoffs and unchanged HP. Headless generated-path tests compare those boundaries;
these are not paired full native paths or native map comparisons.

The fixture bypasses live UI/vote/executor scheduling, authors the completed
rooms and simultaneous relic grants, and does not verify final Architect/victory
handoff or complete seed/path runs. The ending is covered by the later grouped
verification below; complete native paths remain open.
Combat stays v35; **run v53** rejects older offer-refresh/event-timing semantics.

## Consolidated native verification

The [2026-09-20 verification report](evidence/headless_verification_2026_09_20.md)
records the repository sweep, final affected checks and fresh native execution of
all **16 fixture modes** (955 data rows plus the queue lifecycle probe). The
[aggregate](evidence/native_verification_final_2026_09_20.json) retains current
source/toolchain identities, result hashes, timings and cleanup results. Original
captures remain unchanged; result equality is checked against the named captures.

The [ending fixture](evidence/native_campaign_ending_2026_09_20.json) executes
actual final-boss reward generation, Architect entry and `WinRun` for three seeds
and four inventories. Final baseline rewards are suppressed while Wongo still
generates its three exact relics. Architect entry applies Maw Bank without another
floor or heal. Native initialization consumes one Niche draw for its fixed-HP
presentation creature and one owned event draw for fresh-history dialogue. Both
are now preserved. Winning HP is compared before native disposal sets it to zero;
terminal snapshots preserve the winning state and reject further actions.

The [generated-start trace](evidence/native_generated_start_verified_2026_09_20.json)
covers seed 0 from actual Neow offers and Scroll Boxes pickup through a generated
Nibbit combat and all 15 play/end-turn actions, without synthetic combat wins.
Neow offers, the Rewards counter, hand order, energy, block, enemy HP and final
player HP match with Python JSON continuation at every action. This exposed and
fixed Scroll Boxes drawing all commons first: native draws **common, common,
uncommon for each bundle**, excluding cards already used by either bundle.

The reward-handoff rerun exposed missing mock localization during Dummy event
initialization. Its [fresh capture](evidence/native_reward_handoff_verified_2026_09_20.json)
preserves the earlier 48 results, now with all three initial options checked and
no native stderr. The runner rejects stderr instead of accepting asynchronous
initialization errors behind a successful process exit.

These fixtures use in-memory saves with persistent saving and uploads disabled,
mock display text/textures, and bounded execution. The generated-start harness
uses the real card executor and manually invokes native end-turn phases; the
ending fixture starts from authored finished bosses. Neither establishes a full
native campaign, live UI/vote scheduling, arbitrary histories or all Dummy outcomes.
Combat remains v35; **run v54** rejects pre-fix ending RNG and Scroll Boxes semantics.

The subsequent [continuous Act 1 trace](evidence/native_generated_route_2026_09_20.json)
extends seed 0 through 16 rooms and 170 combat actions, ending in **defeat against
Vantom**. All recorded hand/HP/block/energy, living-enemy, reward offer and claim,
deck/relic/gold and Rewards/Niche/Shuffle counter boundaries match headless; each
Python action also runs after JSON restoration. It includes 11 combats, three
rests, one unopened chest and one shop exit. See the
[scope and validation](evidence/headless_generated_route_2026_09_20.md).

This exposed three discrepancies: chest offers must consume only the shared relic
bag until pickup; Inklet starts with Slippery 1; its equal-weight random branch
orders Piercing Gaze before Whirlwind. That batch’s **combat v36 / run v55** reject
snapshots using the previous continuation semantics. The first-combat fixture was
rerun separately and retained its exact earlier result.

The ordinary trace still ends in defeat. A separate user-requested
[boosted-HP campaign](evidence/native_boosted_campaign_2026_09_20.json) starts with
**1,000,000 current/max HP** and completes Overgrowth, Hive, Glory and the Architect:
35 real combats, 917 combat actions and 48 room/transition/ending records. Headless
replays every action with JSON continuation, comparing current/max HP, hands,
creature identities and damage, reward claims, inventory and the recorded RNG
counters. Three mandatory Knowledge Demon choices explicitly select Disintegration;
all three chests open and skip via completed native actions. Victory is checked
before native disposal. This proves that specific boosted trajectory, not a
normal-HP winning strategy, live UI scheduling or exhaustive native parity.

The boosted replay exposed and corrected Parafright/Obscura action order,
random-hit target enumeration after summons, Bronze Scales using Thorns before
incoming damage, Paper Cuts after its owner dies, and Fabricator's delayed
next-move decision after later bots finish. Current **combat v42 / run v61** reject
older continuation semantics. Fabricator's pending roll is owned by the active
enemy continuation and survives pauses without a second RNG draw.

See [scope and validation](evidence/headless_generated_route_2026_09_20.md#boosted-three-act-campaign).
The [expanded Underdocks trace](evidence/native_boosted_underdocks_2026_09_20.json)
adds 26 combats, 1,093 combat/potion actions, five card purchases, two chest claims
and Sunken Treasury before the Architect. It checks shop RNG as well as prior
boundaries and restores each Python decision. Phial Holster now generates starting
potions with the native combat-potion stream; Cubex starts with zero block because
its native setup block command runs before combat becomes active. Artifact applies.

Fresh native shared bags refill only the requested empty rarity, in canonical
order without RNG. Ownership is not a global filter; repeated instances have
separate identities, counters and effects. An entry allocator boundary binds
chest claims to newly acquired relics and rejects reopening or claiming an old copy.
Private schemas are combat v42 / run v61. Native disk-save loading drops the
refill configuration; Python JSON preserves the fresh session being continued.
See [refill and campaign evidence](evidence/headless_generated_route_2026_09_20.md#expanded-underdocks-campaign-and-relic-refill).
The [Kaiser campaign](evidence/native_boosted_kaiser_2026_09_20.json) adds Underdocks
seed 0 through Soul Fysh, Kaiser Crab and Test Subject: 35 combats, 712 actions,
four explicit Yummy Cookie upgrades and the Architect victory. Actual native Kaiser
callbacks use an isolated, pinned Spine library with authored empty animations;
Soul Nexus's actual death callback gets a temporary empty visual-room lookup.
No real game scene is launched. Headless matches every recorded boundary with JSON
continuation. This corrected Soul Fysh's native random Beckon insertion to account
for Python's reversed draw-pile storage, without changing RNG consumption.
See [Kaiser evidence and limits](evidence/headless_generated_route_2026_09_20.md#kaiser-crab-and-third-boosted-campaign).

The [remaining boss coverage](evidence/headless_generated_route_2026_09_20.md#all-regional-bosses)
adds Overgrowth seeds 1 and 3 and Underdocks seed 4: 81 combats and 1,918 actions,
ending in three native victories. Together the six retained boosted campaigns
cover **all 12 regional bosses**, with JSON continuation at each headless action.
The new routes exercise Sunken Statue, Trash Heap, Colossal Flower, Amalgamator
(two explicit Strikes), Slippery Bridge, smithing, Sea Glass's explicit empty
selection, shops, potions and additional earned relics.

Trace-driven corrections cover Ancient event-queue advancement, event-owned
fixed-pool relic RNG, Gas Bomb slot order, dying-parent HP exclusion for summons,
and Stone Cracker/Whetstone/War Paint native upgrade selection. Source-reviewed
edge regressions preserve Ceremonial Beast's reactive stun and temporary Strength
cleanup and Waterfall Giant's post-death power removal. Combat rewards preserve
the Amethyst Aubergine owners that generated their gold, so later pickups from
main/extra rewards or Pael's Wing cannot retroactively change the amount. Private
schemas are combat v42 / run v61; old continuations reject. Boss coverage does not establish every seed,
event branch, inventory combination or hidden native state field.

Further event and inventory coverage remains in the
[implementation queue](HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).

`generation/combat.py` shares the supported combat card pool and selection rules.
The native ordinary pools contain 78 eligible Ironclad and 50 eligible colorless
cards. Skill filters include legacy `block` cards such as Shrug It Off. Discovery,
card potions, Jack of All Trades, Infernal Blade and each Orobic Acid type use a
full eligible-pool shuffle before taking distinct cards. Stoke, Jackpot and Calamity
instead draw with replacement. Neither factory rolls rarity or upgrades; caller
rules apply explicit upgrades and discounts to fresh owned instances. Queued
generation carries an explicit distinct/replacement flag through restoration.

[Generation evidence](evidence/combat_generation_2026_09_14.md) contains 66 actual
native card-factory sequences, 16 empty/singleton/duplicate/count boundary cases
and 12 repeated potion-factory sequences. Alchemize consumes its in-combat potion
roll even when inventory is full; Entropic Brew calls the out-of-combat factory
once per free slot, allowing duplicate potions across those calls. Those existing
potion rules are now additionally checked against direct factory execution.

`generation/` contains the probability rules independently of rooms and content:

- Card rarity uses native normal/elite/boss/shop weights, float32 pity offset,
  per-caller offset modes and rarity fallback order. Native pool declaration order
  is explicit in `core/content_order.py`. Upgrade checks consume their native draw
  even when Act 1's base upgrade chance is zero; uniform/no-upgrade callers preserve
  their distinct consumption rules.
- Potion drops use float32 adaptive odds, the elite bonus and forced-drop updates;
  the native chance is not clamped. Potion rarity and ordered pools match the pinned
  factory, with distinct initial multi-potion offers.
- Relics use shared/player grab bags shuffled through `up_front`, native rarity
  weights, front/back pulls, cross-source depletion and Circlet fallback. Named
  acquisition also removes the relic from both bags. Runtime `IsAllowed` removes
  disallowed relics from every player rarity bag before a draw; caller filters
  skip candidates without depleting them. Filters consume no extra RNG.
- Native merchants have **13 slots**: two attacks, two skills, one power, two
  colorless cards, three relics and three potions. Stock, float32 prices, the sale's
  second price roll and Courier refill consumption use the pinned rules. A Courier
  potion refill can duplicate another stocked potion. Native merchant exclusions
  are Amethyst Aubergine, Bowler Hat, Lucky Fysh, Old Coin and The Courier.
- Dingy Rug extends marked card rewards, including Orrery/Lost Coffer, while
  preserving rarity/type filters. Direct grants, custom pools and explicit
  no-pool-modification callers keep their pools. Lasting Candy's extra power uses
  Source.Other/base rarity odds, a card pick and an upgrade check; White Star uses
  boss rarity rolls, and both additional encounter reward hooks compose.
- Potion batches apply blacklist/combat exclusions before rarity selection and
  remove each selected potion from the batch. Combat excludes Fairy, Fruit Juice
  and Regen; Entropic Brew deliberately retains its out-of-combat factory.

`generation/initialization.py` now reproduces the pinned startup sequence after
relic bags: shared-Ancient allocation, then each act's event shuffle, weak/normal/
elite encounter draws, boss and Ancient selection. All three room sets are retained
as plain `state.initialization` data, because their startup draws share `up_front`.
Generated campaigns reuse the saved Hive and Glory room sets on entry to those acts. The declared act sequence
is **Overgrowth or Underdocks → Hive → Glory**, selected explicitly, solo, A0–A10,
all unlocked/all seen; the native lobby
act picker and profile-dependent first-run overrides are outside this profile.

Native event progression uses `native_act1_events_all_unlocked_v1`: all **31**
Overgrowth or **28** Underdocks queued IDs are shuffled before eligibility,
including nine later-act events and one disabled event. The 21 Overgrowth or 18
Underdocks normally Act-1-eligible events can enter rooms. Their exclusions are explicit metadata, not inferred from missing handlers.
The full solo roster now also handles a later-act candidate selected by the native
exhausted-queue fallback; normal Act 1 eligibility remains unchanged. Fixture progression retains its original profile.

The native map uses second-entrance rejection draws, column-first stable sorting,
insertion-ordered pruning and deterministic centering/spreading/straightening.
Thirteen direct assembly reference seeds for each Act 1 location match complete room queues, startup RNG
counters/suffixes and every Act 1 map coordinate, edge, type and entrance.
See [native initialization evidence](evidence/native_initialization_2026_09_14.md).

Runtime acquisition checks execute the original 161 relic predicates against the pinned
assembly, eight bag sequences, six Dingy Rug contexts and eight potion batches.
The six relevant native pools and 18 epoch gates are inventoried under declared
inputs, without reading a user profile. Runtime uses `UnlockState.all` semantics
(9,999 prior runs); the first-ever Ironclad Lasting Candy exclusion and floor-41
cutoff are boundary-tested pure predicates, not new first-run/later-act modes.
See [acquisition evidence](evidence/runtime_eligibility_2026_09_14.md).

**This does not establish whole-run same-seed parity.** Remaining work concerns
remaining shuffle callers, generated-card insertion hooks and full interaction ordering,
broader acquired-card interactions and a complete native run comparison. The generator foundation and these initialization checks
cover declared inputs, not profile-dependent lobby selection or other acts' gameplay.
See [probability evidence](evidence/native_rng_2026_09_14.md) and
[HF-05](HEADLESS_FULL_GAME_IMPLEMENTATION.md#hf-05--match-target-rng-algorithms-domains-and-consumption).

### Foreign acquisition under Ironclad

The default catalog includes all 320 ordinary solo cards from Silent, Regent,
Necrobinder and Defect, plus their implemented starters and generated cards.
Normal rewards and shops remain in the Ironclad pool. This supports acquisition
under Ironclad, not playable foreign-character runs.

Kaleidoscope models the all-characters-unlocked context. Each of two groups shuffles
four native pools with Niche, takes three, and creates one reward per family using
Source.Other base rarity odds without pity changes. Singleton reward hooks run
before both groups' final reward hooks. Wing Charm, Silver Crucible, Silken Tress
and eggs retain their native ordering, modifiers and counters. Both groups can be
skipped independently. Partial custom catalogs cannot unlock the relic.

Splash draws three distinct eligible attacks in native character/pool order;
Splash+ upgrades them. Its optional choice makes the selected card's local Energy
cost zero until play or turn end and Star cost zero until turn end. Energy-X and
Star-X still consume their available resources. Choices and modifiers survive JSON
restoration. Ordinary/basic foreign cards transform within their own family,
including through Entropy, Aroma of Chaos, Morphic Grove, Whispering Hollow and
New Leaf.

Native factory vectors cover 30 Kaleidoscope cases, ten Splash cases and 16
transformation pools with sampled replacements. They execute native factories
inside source-reproduced acquisition orchestration, not native whole-card plays
or full runs. See [acquisition evidence](evidence/foreign_acquisition_2026_09_19.md).

### Silent content

`game.headless.cards.catalog.SILENT_CARDS` extends `IRONCLAD_CARDS` with all
**80 ordinary solo Silent cards**, their upgrades, four starter cards and Shiv.
It supports acquired Silent cards in the existing Ironclad run/combat owner;
it does not add a playable Silent character.
Suppress and Wraith Form are Ancient entries outside this ordinary-family batch.

Shared rules cover explicit discard/Sly ordering, Poison/Accelerant/Outbreak,
Shiv generation and enchantment/targeting powers, play/draw/discard histories,
turn-scoped costs and keywords, ordered Nightmare templates, optional retention,
and The Hunt's earned post-combat rewards. Choices and delayed effects are owned
plain data. The existing legacy encoder vocabulary remains unchanged.

```python
from game.headless.cards.catalog import SILENT_CARDS
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine

run = RunEngine(seed=2, rng_profile="native", cards=SILENT_CARDS,
                config=RunConfig(),
                card_ids=["blade_dance", "deadly_poison", "prepared", "tactician"])
run.start_combat(encounter_id="overgrowth_cubex")
```

Pinned native base/upgrade metadata is reproducible with the existing oracle's
`silent` mode. Interaction tests are source-backed Python regressions; they do
not establish native full-turn or whole-run parity. Acquisition factory coverage is described above.
See [Silent evidence](evidence/silent_cards_2026_09_15.md).

### Regent content

`game.headless.cards.catalog.REGENT_CARDS` extends `SILENT_CARDS` with all
**80 ordinary solo Regent cards**, both levels, four starters and Sovereign Blade,
Minion Strike, Minion Dive Bomb and Minion Sacrifice. It supports acquired Regent
cards under the existing Ironclad owner. Meteor Shower and The Sealed Throne are
Ancient entries outside this ordinary-family batch.

Stars live in `player.rules.stars`; `player.star_cost(card)` supplies current
payment and participates in legality. Stars persist across turns, reset with combat,
and autoplay captures Star-X without paying it. Forge updates owned blades,
including exhausted ones, and creates one when none remain outside Exhaust.
Sword Sage adds whole-card replays; Seeking Edge changes targeting; Parry gains
powered block per replay. Minion transformations replace exact owned instances.

Shared turn phases preserve power application order across families. Delayed
choices, card generation, temporary Strength, replay/resource capture and Royalties'
separate optional gold reward use existing command and continuation mechanisms.
The `regent` native-oracle mode reproduces 90 base/upgrade metadata rows, including
the two inventoried Ancient exclusions. [Regent evidence](evidence/regent_cards_2026_09_15.md)
distinguishes direct metadata execution from source-backed Python interaction tests.

```python
from game.headless.cards.catalog import REGENT_CARDS
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine

run = RunEngine(seed=2, rng_profile="native", cards=REGENT_CARDS,
                config=RunConfig(),
                card_ids=["venerate", "solar_strike", "spoils_of_battle", "cloak_of_stars"])
run.start_combat(encounter_id="overgrowth_cubex")
```

### Necrobinder content

`game.headless.cards.catalog.NECROBINDER_CARDS` extends `REGENT_CARDS` with all
**80 ordinary solo Necrobinder cards**, both levels, four starters, Soul and
Sweeping Gaze. These cards work under the existing Ironclad owner; this does not
add a playable Necrobinder character. Forbidden Grimoire and Protector are Ancient
entries outside this ordinary-family batch.

Osty is owned combat data, including HP and maximum HP after death. Summon creates
or revives him; incoming attacks consume player block, then Osty's HP, then spill
into player HP. Pet attacks use their own dealer modifiers. Doom checks the afflicted
side at turn end; End of Days requests the check immediately. Souls, delayed summons,
Ethereal choices, power ordering and multi-hit pet attacks use the existing explicit
continuations. The Scythe records permanent damage on the physical card and synchronizes
matching run-deck copies after each action, including combat-ending attacks.

Freshly generated and transformed cards both enter generated-card history; transformations
do not trigger Arsenal or Pillar of Creation. Both count toward Supermassive
while retaining their separate generation-hook behavior.

```python
from game.headless.cards.catalog import NECROBINDER_CARDS
from game.headless.run.engine import RunEngine

run = RunEngine(seed=2, rng_profile="native", cards=NECROBINDER_CARDS,
                card_ids=["bodyguard", "unleash", "scourge", "soul_storm"])
run.start_combat(encounter_id="overgrowth_cubex")
```

The oracle's `necrobinder` mode reproduces 88 native base/upgrade metadata rows,
including the two excluded Ancient entries. Card interactions are source-backed
Python regressions, not demonstrated native full-turn parity.
See [Necrobinder evidence](evidence/necrobinder_cards_2026_09_19.md).

### Defect content

`game.headless.cards.catalog.DEFECT_CARDS` extends `NECROBINDER_CARDS` with all
**80 ordinary solo Defect cards**, both levels, four starters and Fuel (85 definitions).
Together the cumulative catalogs implement the 320 ordinary foreign cards for
acquisition under Ironclad. This does not add playable foreign characters.
Biased Cognition and Quadcast are Ancient exclusions. `DEFAULT_CARDS` now uses
this complete cumulative catalog; `IRONCLAD_CARDS` remains an explicit restricted catalog.

Orbs are owned physical instances with ordered slots, a ten-slot cap and a separate
native orb-generation RNG stream. Ironclad begins with no slots; his first channel
opens one. Full queues evoke the front orb before inserting the new orb. Lightning,
Frost, Dark, Plasma and Glass implement their distinct Focus, passive and evoke
rules; Plasma naturally triggers at side start and the other orbs at side end.
Confirmed owner death clears active orbs and slots after revival effects run.

Shared commands handle Focus expiration, temporary slots, captured orb phases,
Echo Form/Signal Boost replays, Feral returns, generated Status listeners, Scrape's
own drawn-card history and ordered power callbacks. Rocket Punch uses an absolute
local cost setter lasting until play, so global cost increases still apply.
Doom and Hailstorm retain their application order across the side-end boundary.
Genetic Algorithm grows the physical card's permanent block and synchronizes its
matching run-deck ID, including when combat ends during resolution. Pending orb
and card reactions use source-owned task receipts rather than saved callbacks.

```python
from game.headless.cards.catalog import DEFECT_CARDS
from game.headless.run.engine import RunEngine

run = RunEngine(seed=2, rng_profile="native", cards=DEFECT_CARDS,
                card_ids=["zap", "dualcast", "glacier", "genetic_algorithm"])
run.start_combat(encounter_id="overgrowth_cubex")
```

The oracle's `defect` mode reproduces 87 native base/upgrade metadata rows,
including the two Ancient exclusions. Interaction tests execute the Python rules
checked against pinned native source; they do not establish native full-turn parity.
See [Defect evidence](evidence/defect_cards_2026_09_19.md).

## Use and extend the game directly

The complete first vertical slice is available through direct game commands:

```python
from game.headless.run.actions import ChooseNode
from game.headless.run.engine import RunEngine

run = RunEngine.ironclad_slice(seed=2, ascension=0)
run.apply(ChooseNode("fight_1"))
actions = run.legal_actions()  # PlayCard, EndTurn, and any owned usable potion
# Choose and apply one of these commands; continue through rewards/rest/map.
snapshot = run.snapshot()
restored = RunEngine()
restored.restore(snapshot)  # Also accepts json.loads(json.dumps(snapshot)).
assert restored.legal_actions() == actions
```

Run the complete deterministic example from the [README](../README.md#implementing-the-game).
Seed 2 exercises a potion acquired after the first fight and used in the second.
The example player is a CLI consumer, separate from the rules. The following
lower-level API remains useful for isolated rule tests:

```python
from game.headless.core.actions import PlayCard
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.run.engine import RunEngine

run = RunEngine(seed=43, card_ids=("strike", "strike", "defend"))
card_id = run.state.deck[0].instance_id
assert run.preview_upgrade(card_id).base_damage == 9
run.upgrade_card(card_id)
combat = run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=9))
combat.apply(PlayCard(card_id, target_slot=0))
assert combat.winner == "player"
run.finish_combat()
assert run.state.deck[0].upgraded
snapshot = run.snapshot()  # JSON-compatible private game state
```

For a card implemented with existing operations, add one `CardDefinition` with
its ordered effects and verified level values, then include it in the relevant
content catalog. New effects belong in that content family or shared game rules
when multiple cards need them. Display names do not dispatch behavior. A test can
inject a `CardCatalog` containing an entirely new card without touching any adapter.
Upgrade levels are per definition; they are not globally limited to a boolean.
All **85 single-player Ironclad definitions** from pinned game 0.107.1 have their
base and upgraded execution. Demonic Shield and Tank are excluded as multiplayer-only.
The full **80-card common/uncommon/rare pool** is available to ordinary rewards,
shops and Ironclad transformations. Boss rewards sample the rare subset. Strike,
Defend and Bash are basic; Break and Corruption are Ancient cards, implemented but
excluded from ordinary acquisition. Shockwave remains colorless. Primal Force's
Giant Rock is also implemented. See the [inventory and rule evidence](evidence/ironclad_complete_2026_09_13.md).
Generated native-profile runs use the rarity rules above; authored fixture profiles retain their original sampling.
Slimed costs one, draws one and exhausts; it cannot be upgraded.


### Colorless cards

All **53 single-player colorless definitions** in pinned 0.107.1 execute at base
and upgraded level. The native pool contains 64; Beacon of Hope, Believe in You,
Coordinate, Gang Up, Huddle Up, Intercept, Knockdown, Lift, Mimic, Rally and Tag Team
are excluded under the single-player scope. The explicit definitions are in
[`cards/colorless.py`](../game/headless/cards/colorless.py); see the
[native inventory and validation evidence](evidence/colorless_complete_2026_09_13.md).

Colorless cards have separate uncommon/rare merchant slots and a full transformation
pool; they do not enter ordinary Ironclad combat rewards. General choices expose
`ChooseCombatCard(instance_id)` to select/deselect and `ConfirmCombatSelection()`
to finish. Purity permits selecting zero cards; Discovery and Splash permit skipping.
Mandatory selections require their count before confirmation. Offered cards,
selected IDs and queued work are owned plain state. Existing single-card Ironclad
selectors still finish immediately on their `ChooseCombatCard` action.

Shared rules cover Retain and Retain Hand, shuffle-time Stratagem choices,
Automation draw counters, post-draw Mayhem autoplay, Entropy transformations,
independent Panache/Bomb/Boulder instances, temporary Dexterity/Vigor/block effects,
returning Bolas/Hatchet instances, and Hidden Gem's combat-local replay count.
Hidden Gem also multiplies Drum of Battle's exhaust energy. Play hooks preserve
power insertion order across content families. Original cards and generated clones
have independent state; combat changes do not alter the permanent deck.

Hand of Greed transfers fatal gold and Alchemize transfers successfully procured
potions through the run's owned inventory. Alchemize has a separate saved RNG stream
and still generates when slots are full. Generated runs now use all ordinary
Ironclad-accessible potions, filtering Fairy, Fruit Juice and Regen from Alchemize.
Authored slice fixtures retain their explicit Fire/Block pool. Discovery and
Calamity use the Ironclad generation catalog with their distinct native factory modes. Splash uses the native ordered foreign attack pools in the default catalog;
explicit restricted catalogs retain a single-character fallback. Entropy now uses
the native ordered combat transformation pools: 78 eligible Ironclad definitions,
50 colorless, all 18 curses and all ten combat-generatable statuses, excluding the
original definition. Ancient/event/token/quest cards transform into colorless
cards; registered foreign cards retain their own family. Replacements get fresh
IDs and base values, preserve pile position, clear old modifiers and run generated
entry hooks such as Stomp. Selection and RNG continuation match direct native
factory vectors. See [transformation evidence](evidence/combat_transforms_2026_09_15.md).

The six added statuses are Beckon (play to avoid six unblockable end-turn damage),
Burn (two blockable end-turn damage), Debris (pay one to exhaust), base Wither
(three blockable end-turn damage), Toxic (five blockable end-turn damage; pay one
to exhaust) and Void (lose one energy when drawn; ethereal). Automation's normal
draw hook precedes Void; generated entry does not count as drawing. Soot and
Frantic Escape cannot be generated in combat and await their later-act callers;
Wither's encounter-driven fake upgrades are also outside this Act 1 batch.
Private snapshots are combat **v19** / run **v31**. Other-character catalogs and
whole-command/native-run interaction fidelity remain separate work.

Armaments gives 5 block, then upgrades one eligible hand card for this combat;
Armaments+ upgrades all eligible hand cards. True Grit gives 7 block and exhausts
a random remaining hand card; True Grit+ gives 9 block and lets the player choose.
Empty selections do nothing and a single eligible card resolves automatically.
With multiple eligible cards, `ChooseCombatCard(instance_id)` is the only legal
command until the choice resolves. These selections require exactly one card;
there is no cancel command. See the [source checks](evidence/combat_card_choices_2026_09_13.md).

The resolving card stays in `Deck.in_play`, outside the selectable hand and
reshuffleable discard pile. `Player.pending_play` stores only its effect index
and target slot; the immutable catalog supplies eligibility and resolution rules.
Selecting resumes the ordered effect suffix, then discards/exhausts the source
once. Later effects can request another choice through the same mechanism.
Temporary upgrades keep their instance IDs and last through combat reshuffles;
the persistent master deck is unaffected. Random hand selection uses an owned
`Deck.selection_rng` (run-owned `combat_card_selection` in native-profile runs). This is deterministic
Python sampling, not the native run's `CombatCardSelection` seed sequence.

Uppercut costs 2, deals 13 damage, then applies 1 Weak and 1 Vulnerable;
its upgrade applies 2 of each without increasing damage. Shockwave is colorless and costs 2,
applies 3 Weak then 3 Vulnerable to each living enemy in slot order, and exhausts;
its upgrade applies 5 of each. Uppercut is in the full default Ironclad
reward pool; Shockwave is in the full single-player colorless transformation pool and merchant stock.
Weak multiplies attack damage by 0.75 regardless of stack count. Strength is
added first and Weak/Vulnerable fractions are combined before rounding down.
Enemy intents retain an authored damage amount privately so execution does not
multiply an already rounded preview a second time. Non-attack damage is unaffected.

Weak and Vulnerable tick once after the complete enemy side, for player and
enemies alike. A new player debuff skips its first tick; adding stacks to an
existing power preserves its current skip flag. Removing the final stack clears
that flag. Snapshot continuation and search cloning retain this owned duration
state. This corrects the old player-Vulnerable owner-turn approximation; the
reduced Shrink rule and unsupported power/relic modifiers remain separate work.
See the [native source and acceptance evidence](evidence/weak_and_area_debuffs_2026_09_13.md).

The shared resolver is `core/resolution.py`. It executes an explicit queue of
plain tasks and owned play frames, including nested Havoc/Cascade/Hellraiser
plays and One-Two Punch repeats. A frame captures its result pile and paid/X
resources before effects. Each repeated play runs its own hooks; the physical
card moves once. Headbutt selects from discard; Burning Pact and Brand reuse
hand selection. Choices during Stampede resume the pending enemy phase once.
`core/rule_snapshots.py` validates continuation structure and ownership before
installing restored state. No callback or global counter is saved.

`powers/ironclad.py` owns acquisition-ordered hooks for exhaust, HP loss, block,
play and turn boundaries. For example, Dark Embrace draws after ordinary exhaust
and defers Ethereal draws to its end-turn hook; No Draw expiry respects listener
order. Unmovable counts powered block entries from other plays. Corruption changes
skill costs and their captured result pile. Rage/Feel No Pain block and Juggernaut/
Inferno damage remain unpowered. Flame Barrier stops an attacker's remaining hits
if retaliation kills it, and never retaliates after player death.

`Card.combat_state` owns cost reductions and damage growth for Stomp, Rampage,
Thrash and generated cards. These values and temporary upgrades never mutate the
master deck. Anger/Juggling clones have fresh owned IDs and independent modifiers;
Stoke/Infernal Blade generation uses a separate saved RNG stream and excludes
Feed/Not Yet and basic/Ancient cards. Feed's fatal maximum-HP gain is carried back
to the run explicitly. Howl from Beyond plays from exhaust at turn end and then
returns to discard. Powers occupy a separate played-power pile.

Game commands describe intent, not network authority. External adapters still own
public references, stale request bindings, information filtering and representation
limits. A new action family may eventually require adapter work, but that work is
not a prerequisite for implementing or testing its game rule.

Extend relics, potions, selectors and other families with verified behavior.
Keep their rules beside their content; add explicit lifecycle
operations in the core as needed. Do not put card-name switches, global mutable
registries, live-service dependencies or callback closures into saved game state.
Do not scaffold empty plugin frameworks or guess all future hooks now.

## Potions

All **51 potion definitions in the solo Ironclad scope** execute against the pinned
0.107.1 / Steam build 23811903 rules: 45 shared, Blood Potion, Ashwater and Soldier's
Stew, plus Foul Potion, Glowwater Potion and Potion-Shaped Rock. Other characters'
12 exclusive potions and Deprecated Potion are outside this scope. Event/token
potions have executable rules and their granting solo events are implemented;
Foul's combat and ordinary merchant uses are supported, while Fake Merchant awaits
its event choice and inventory legality.

`potions/base.py` owns immutable content, `combat.py` applies ordered effects,
`powers.py` owns delayed/resource hooks, and `selections.py` defines card choices.
`use.py` consumes run-owned instances before effects. Pending use records contain
only IDs, targets and effect cursors; nested autoplay/draw/exhaust work completes
before Reptile Trinket and the final Unceasing Top check. Private snapshots are
combat v24 and run v36. Legacy RL encoders retain their frozen vocabulary.

- Damage/status/block/stat/energy potions share combat rules, including Artifact,
  damage caps, Dexterity and temporary Strength/Dexterity expiration.
- Attack/Skill/Power/Colorless offers can be skipped and grant a card free for the
  turn. Ashwater, Gambler's Brew, Liquid Memories, Droplet and Touch of Insanity
  select owned cards. Touch excludes X-cost and locally free cards.
- Distilled Chaos resumes nested card choices. Bottled Potential shuffles hand,
  draw and discard together. Snecko Oil uses its own saved cost RNG; its absolute
  local override replaces earlier discounts and expires on play or turn end.
- Gigantification triples one complete attack command, including every hit.
  Duplicator repeats the next card; Soldier's Stew adds replay to existing Strikes.
  Clarity/Radiance last three future turns; Regen, Ritual, Thorns, Buffer and Demise
  use their native resource/turn boundaries.
- Blood Potion, Fruit Juice and Entropic Brew can also be used outside combat.
  Event potion changes are recorded between resource boundaries, so repeated
  event decisions and automatic revival remain resumable. Fairy is automatic,
  consumes the first available Fairy, revives for at least 1 HP (30% max HP), and
  takes priority over Lizard Tail.

Generated runs, their merchant stock, and the potion-granting events use the full
ordinary pool. Reward, relic, merchant and Alchemize generators share the rarity
rule: 65% common, 25% uncommon, 10% rare, then a uniform definition in that rarity.
Native multi-potion factory calls choose without replacement. Alchemize excludes
Fairy, Fruit Juice and Regen; Entropic Brew deliberately uses the out-of-combat
factory even during combat, can generate those three, and fills the slot it freed.
Potion merchant base prices are 50/75/100 by rarity, with existing price variation,
discounts and Courier restocking. Authored slice fixtures and explicitly supplied
small pools retain their declared restricted sampling and stock layout. Native
seed/RNG parity, unlock progression and other-character potion mechanics remain
separate work.

See the [finite inventory](../tests/fixtures/headless_potion_scope.json),
[regressions](../tests/headless/test_potions_complete.py) and
[source/validation evidence](evidence/potions_2026_09_14.md).

## Relics

The default catalog contains **259 relic definitions**, including all **99 solo
Ancient relics** from pinned build 0.107.1. This extends the original 161-definition
Act 1 inventory with 70 Ancients and Black Blood, the Ironclad starter evolution
granted by Touch of Orobas, plus 27 event relics. Massive Scroll remains excluded as multiplayer-only.
Kaleidoscope
requires all four complete ordinary foreign families before offering two sets of
three cards from distinct families. Multiplayer-only relics
and other characters' exclusive relics are outside this scope.

Generated `RunEngine.ironclad_act1()` runs now use all ordinary eligible relics
for rewards/treasure and the full supported merchant relic pool. Amethyst Aubergine, Bowler Hat, Lucky Fysh, Old Coin and The Courier are excluded
from merchant generation. Authored routes retain their
explicit smaller `RunConfig` pools. Native-profile runs now apply rarity weights and
shared grab-bag depletion across sources. Profile-dependent unlock histories and whole-run seed parity remain separate work.

Relic rules live in small modules under `relics/`: `turns.py`, `plays.py` and
`damage.py` own combat hooks; `run_rules.py` owns shared resource/card mutations;
`pickup.py` and `neow.py` own acquisition; `rewards.py` and `pools.py` own offers.
Persistent counters and extra data belong to each run-owned relic instance.
Combat uses isolated copies and synchronizes counters back to the run; transient
trigger memory resets on combat entry. None of this adds projections or encoders.

Pickup choices use `ChooseRelicCard`, `ConfirmRelicSelection` and
`ChooseRelicReward`. Their plain queue can pause over the granting shop, chest,
reward or rest site. Nested Neow's Bones/Large Capsule rewards finish before their
following effects; no room entry is legal until acquisition finishes. Failed
acquisition rolls back resources, IDs, RNG and queued work. `obtain_relic(id)` is
the between-room API for direct scenarios; ordinary play obtains relics through
its room actions.

Combat hooks include opening resources, turn/card/exhaust counters, damage and
block modifiers, first-use/replay effects, reactive draws and potion interactions.
A reactive draw can interrupt between enemy hits, survive JSON restore, and kill
the attacker before it acts again. Run hooks include card upgrades/enchantments,
gold/healing/max HP, potion capacity, Membership/Courier prices and restocking,
Lift/Dig/extra rest actions, bonus rewards, Silver Crucible's first empty treasure,
Juzu's unknown-room combat exclusion and Winged Boots' three non-edge travels.

Relic-dependent content includes Sharp, Adroit, Momentum, Royally Approved, Swift,
Nimble and Glam enchantments, Eternal Greed, Injury, Neow's Fury and Potion-Shaped
Rock. Generated runs use the complete ordinary potion pool;
Neow's Bones generates from all ten native modifier-eligible curses after its
relic selections finish. All 18 curse-pool definitions are available for curse
transformations, including playable Spore Mind/Enthralled and Eternal results.
All four ordinary foreign-character card families are available in the default catalog.

Ancient acquisitions, combat hooks, persistent state and map changes live in
`ancient_pickups.py`, `ancient_combat.py`, `ancient_state.py` and `ancient_map.py`.
They use the same owned IDs, RNG streams, pickup queue and combat scheduler as
other content. Their dependent content includes Maul, Relax, Luminesce, Wish,
Brightest Flame, Whistle, Apparition, Apotheosis and Soot, all five Archaic Tooth
starter replacements, and Goopy, Tezcatara's Ember, Instinct, Imbued and Clone.
Goopy growth returns to its exact master-deck card; combat-only upgrades stay local.

`UseRestRelic("cook" | "clone" | "kindle")` exposes Meat Cleaver, Pael's Growth
and Pumpkin Candle. Cooking uses `ChooseCookCard` and `ConfirmCook`, with a
cancelable two-card choice. Sea Glass uses toggled `ChooseRelicReward(index)`
selections followed by `ConfirmRelicSelection`; `obtain_relic("sea_glass",
card_pool="silent")` can explicitly choose any of the five supported families.
Pael's Tooth stores removed card records and returns one upgraded card after each
combat. Toy Box retains wax relic identities after melting but disables their hooks.

`RerollCardReward(index=-1)` and `SacrificeCardReward(index=-1)` expose Driftwood
and Pael's Wing on actual card rewards, including nested acquisition/event rewards;
nonnegative indexes select additional combat rewards. Skipping does not sacrifice.
Rerolls preserve the source's pool/rarity/upgrade rules and roll back on failure.
Hefty Tablet, Lead Paperweight and Sea Glass are selection screens, so they do
not expose these alternatives. The pinned Kaleidoscope has an empty native reroll
pool: its reroll rejects atomically with an explicit error; sacrifice works.

Lord's Parasol automatically purchases each initial merchant slot once, pauses for
pickup choices, resumes with Courier restocking, then offers mandatory free removal
when eligible. Golden Compass replaces a generated Act 1 map with the fixed golden
path when acquired before map travel; its unknown nodes resolve to events. Fur Coat
marks up to seven fights using its independent seeded stream and also affects
summoned enemies. Whispering Earring spends resources on up to 13 automatic plays
and resolves its own card selections; Imbued plays first. These relics can be
acquired through `obtain_relic` scenarios. Neow keeps its native 27-relic offer pool;
this change does not add later-act Ancient encounter selection or later-act runs.

See the [Ancient census](../tests/fixtures/headless_ancient_scope.json) and
[Ancient behavior/continuation tests](../tests/headless/test_all_ancients.py).
The census is decompiled-source evidence, not a native runtime oracle. Tests cover
all 70 new acquisitions and combat continuations, resource/selection interactions,
RNG consumption, malformed snapshots and atomic failure. Independent semantic
review reproduced the key RNG and persistence cases. Whole-run same-seed parity
and exhaustive combinations remain unproven.

See the [original scope inventory](../tests/fixtures/headless_relic_scope.json),
[combat tests](../tests/headless/test_relic_combat.py),
[run tests](../tests/headless/test_relic_run.py) and
[source/validation record](evidence/relics_2026_09_13.md). Current private combat/run
snapshots persist this state and reject older schemas; public fixture schemas
are unchanged. This is static-source and synthetic execution evidence, not live
or exhaustive interaction conformance.

## Generated full-length Overgrowth route

```python
from game.headless.run.engine import RunEngine
run = RunEngine.ironclad_act1(seed=2, discovery="all_seen")
actions = run.legal_actions()  # Choices among generated first-row entrances.
```

```bash
sts-headless-play --route overgrowth-generated --seed 2 --path left --rest-choice rest --verify-restore
```

The default `overgrowth_a0_pruned_restricted_v2` profile generates seven paths
through 15 map rows, then a boss on row 16. Row 1 contains ordinary fights,
row 9 treasure and row 15 rest sites. The pinned base placement restrictions
apply before native duplicate-segment pruning and room-count repair. Equivalent
room sequences between the same branch/merge points can be removed; shared
branches retain their connections. Pruning may leave a single first-row entrance.
Native-profile runs apply centering, spreading and path straightening before
publishing coordinates and stable node IDs. Authored fixture profiles retain their original layout.

Unknown map markers remain `kind="unknown"` with no preselected event identity.
On entry, owned native base odds select combat, treasure, shop or event exactly
once: initially 10%, 2%, 3% and the remainder. Unselected enabled types gain their
base odds; the selected type resets. A shop outcome is excluded after a shop or
when every next map marker is a shop, without redistributing its probability or
increasing its blocked odds. Unknown combats consume the normal encounter queue.
`state.unknown_rooms` owns resolved outcomes and odds; `run/unknown_rooms.py` exposes
`room_node(state, graph, node_id)` for the effective visited room. Reading the map
never draws or exposes an unvisited outcome. Failed room construction rolls back
navigation, odds, outcome identity, event queue and RNG together.

The earlier base-map fixture remains selectable through
`RunEngine.ironclad_act1(map_profile="overgrowth_a0_base_restricted_v1")`; it keeps
its unpruned topology and explicit supported-event substitutions.

Run-owned encounter queues contain 15 hallway entries (three weak, then twelve
normal) and 15 elite entries, drawn from refillable bags with consecutive identity/
tag exclusions and the native exhausted-candidate fallback. Boss selection occurs
once at initialization. Successful combat entry records the selected encounter
against its node; other rooms do not advance either combat queue. Reads, rejected
choices and failed construction do not consume encounter entries. Queues,
assignments, topology and RNG persist through JSON continuation.

This profile explicitly assumes all encounters have been seen and skips native
first-run overrides. By default it retains the post-Ancient fixture start; the
optional Neow start below generates the supported native offer families. The native event profile queues all 31 IDs before eligibility using shared UpFront
initialization; the fixture `supported_events_all_unlocked_v7` profile shuffles
`RunConfig.event_pool` once. The
generated pool contains Jungle Maze Adventure, Aroma of Chaos, Morphic Grove and
Tablet of Truth, Whispering Hollow, Wellspring, Slippery Bridge, Sunken Statue, Dense Vegetation, Sapphire Seed and Byrdonis Nest, plus the ten definitions listed under [remaining Act 1 events](#remaining-act-1-events).
Morphic Grove requires at least 100 gold and two transformable cards; Whispering
Hollow requires 44 gold; Slippery Bridge requires floor greater than six and a
removable card. Byrdonis Nest excludes an owned event pet or Byrdonis Egg. The
remaining entry predicates include Choir gold/relic availability, Unrest missing HP, Wood Carvings removable Basics, Tea Master gold, Future of Potions inventory and Legends HP/deck requirements. On event entry,
the queue skips previously visited or ineligible definitions; after a full
exhausted pass it permits the current candidate even if visited or ineligible,
matching the native fallback. `state.event_progression` owns queue order, cursor,
node assignments and plain entry conditions (resources, deck eligibility and inventory counts).
Restore replays selection against those conditions and visited room outcomes. Reads and failed room construction never advance the queue.
Later-act events are available through the explicit event catalog below; eligible Hive and Glory events enter generated campaigns. Profile-dependent unlock epochs remain open. Native initialization
uses pinned pool order; authored profiles retain their declared pool restrictions. Juzu Bracelet and Winged Boots now modify unknown/travel behavior; tutorial overrides and native RNG
parity remain unsupported. Generated runs opt in to
`RunConfig.relic_fallback="circlet"`, preventing exhausted relic rewards
from blocking a later elite; authored routes retain their existing rejection rule.
Each claimed reward records its exact item instance, including repeated Circlets.

Every path has 16 room visits before Act 1 completion if survived. This is a
full-length **restricted-content** route, not yet complete native Act 1 fidelity.
[Source anchors, checks and remaining work](evidence/map_pruning_unknowns_2026_09_13.md).

## All solo events across acts

The pinned 0.107.1 census now has **66 implemented solo events**: **58 regular
events and eight Ancients**. `events/catalog.py` contains 65 definitions; Neow
retains its established `run/ancient.py` entry path. The two deprecated placeholder
models are excluded. [The checked-in census](../tests/fixtures/headless_solo_event_scope.json)
records the source build and DLL hash.

This adds 44 definitions, 17 event cards, six enchantments, 27 relics and six
encounter configurations. The default catalog now contains 547 cards and 259
relics. Event-only content stays out of ordinary reward and merchant pools.

| Content module | Implemented interactions |
| --- | --- |
| `events/roster.py` | Amalgamator, Bugslayer, Doors of Light and Dark, Drowning Beacon, Field of Man-Sized Holes, Grave of the Forgotten, Hungry for Mushrooms, Infested Automaton, Lost Wisp, Potion Courier, Reflections, Spiraling Whirlpool, Spirit Grafter, Sunken Treasury, Symbiote, Waterlogged Scriptorium, Zen Weaver, Stone of All Time |
| `events/social.py` | Abyssal Baths, Colossal Flower, Doll Room, Round Tea Party, Trial, Colorful Philosophers, Ranwid the Elder, Relic Trader, Welcome to Wongo's |
| `events/minigames.py` | Crystal Sphere's hidden grid, tools, reveal order and custom rewards; Endless Conveyor's weighted dishes and repeated purchases |
| `events/special.py` | Tinker Time's configured Mad Science card, Trash Heap's legacy cards/relics, War Historian Repy's key choices, Architect's terminal victory |
| `events/fights.py` | Three Battleworn Dummy settings, Punch-Off, Lantern Key/Mysterious Knight and Fake Merchant |
| `events/ancients.py` | Darv, Nonupeipe, Orobas, Pael, Tanx, Tezcatara and Vakuu offer generation and ordinary nested relic acquisition |

Use the existing event commands in authored scenarios:

```python
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run import events
from game.headless.run.actions import ChooseEventOption

run = RunEngine(seed=7, config=RunConfig(), gold=200, rng_profile="native")
run.state.act_index = 1  # Zero-based; owned scenario input, before event entry.
events.begin(run.state, "crystal_sphere", cards=run.cards)
run.apply(ChooseEventOption(run.state.pending["event_instance_id"], "payment_plan"))
# Choose from run.legal_actions(); snapshot()/restore() also work inside the grid.
```

`FlowEvent` extends the existing step interpreter with named pages. Saved pages
contain offered values, selections and operation receipts, never callbacks. Card
and relic acquisition uses the existing run rules. Repeated purchases and page
transitions update the owned continuation atomically. Pending reward batches are
fully generated before claims, and support ordinary reward modifiers, Driftwood
rerolls, Pael's Wing sacrifices and nested relic selectors.

Dummy expiry is recorded separately from a kill and returns to its result page.
Other event fights put custom loot alongside ordinary combat rewards, then leave
the event. A completed continuation cannot resume again in another fight. Fake
Merchant stores six prices rolled on the Shops stream; its event inventory does
not receive MerchantRoom discounts or Courier restocks. Crystal Sphere stores its
private board in the run snapshot; only hidden cell centers are legal dig targets.
The snapshot is privileged simulator state, not a public observation contract.

Mad Science retains its type/rider across cloning, combat and restore. History
Course replays a temporary duplicate that disappears after use. Bing Bong copies
new deck acquisitions with their modifiers and skips effects explicitly cloning a
card. Dream Catcher integrates with real rest-site rewards. The knight's Plating
expires by turn. New enchantments implement Perfect Fit, Soul's Power, Spiral,
Corrupted, Steady and Vigorous through shared card/turn rules.

`state.act_index`, `state.wongo_points` and `state.freed_repy` are explicit owned
scenario/progression values; no game profile is read or written. At act index 2,
Lantern Key forces the next unknown point to Repy. Ancient entry heals fully at A0,
and Darv binds Dusty Tome's offered card before the choice. Non-rare event card
upgrade rolls scale with act index; no-roll factories retain their native flags.

Validation is source-backed and synthetic: branch completion under both RNG
profiles, JSON continuation between decisions, card/relic combat tests, minigame
legality, reward ownership and adversarial replay/rollback cases. See
[branch tests](../tests/headless/test_all_solo_events.py) and
[event content tests](../tests/headless/test_extended_event_content.py). This is not
an assertion of live end-to-end parity for every event or a complete Act 2/3
campaign. See the current completion scope for implemented A0–A10 campaigns and
retained native route comparisons. Profile-dependent unlocks remain separate scope.

## Neow starting choice

```python
from game.headless.run.ancient import PROFILE as NEOW_PROFILE
from game.headless.run.actions import ChooseAncientRelic
from game.headless.run.engine import RunEngine

run = RunEngine.ironclad_act1(seed=2, ancient_profile=NEOW_PROFILE)
run.apply(next(a for a in run.legal_actions() if isinstance(a, ChooseAncientRelic)))
# Resolve any offered relic card selections before choosing a map entrance.
```

```bash
sts-headless-play --route overgrowth-generated --ancient neow --seed 2 --rest-choice rest --verify-restore
```

`neow_solo_all_unlocked_v2` generates two positive offers and one curse offer.
It filters eligibility before choosing the curse, applies paired exclusions,
then randomizes Lava Rock/Small Capsule, Oyster/Humidifier and Talisman/Pomander
before shuffling the positive pool. Large Capsule excludes its conflicting pair.
The default catalog supports all 27 solo Neow relics, including Kaleidoscope. Massive Scroll is multiplayer-only.
The default assumes all content is unlocked; native RNG parity is not claimed.

Selection and nested card/relic rewards use the existing owned pickup queue.
Map entry remains blocked until acquisition finishes. Restore binds offered
choices to the seed, content availability, selected relic and pickup history.
The historical `neow_pickups_restricted_v1` fixture retains its two fixed offers.
`ancient_profile=None` remains the explicit post-Ancient factory default;
`--ancient neow` selects the randomized profile. No player save/profile is read.
See [source, tests and limits](evidence/events_neow_2026_09_14.md).

## Generated Underdocks Act 1

```python
from game.headless.run.engine import RunEngine
from game.headless.run.ancient import PROFILE as NEOW

run = RunEngine.ironclad_act1(seed=2, act="underdocks", ancient_profile=NEOW)
```

```bash
sts-headless-play --route underdocks-generated --ancient neow --seed 2 --verify-restore
```

This route connects Neow, all 20 Underdocks encounters, ten local events, shared
events, shops, treasure, rest sites and boss rewards through Act 1 completion.
Omit `ancient_profile` / `--ancient` for the existing post-Ancient test start.
`act="overgrowth"` remains the programmatic default. Explicit act selection assumes
solo Ironclad, all content unlocked and encounters seen; it does not read unlock
profiles or reproduce the profile-dependent lobby picker. The default is A0; pass
`ascension=1` through `10` to apply the cumulative rules described above.

[`map/act1.py`](../game/headless/map/act1.py) shares the pinned map generator between
both Act 1 locations. Underdocks uses `underdocks_a0_pruned_restricted_v1`: 15 rows
plus the boss, the same fixed rest/treasure rows, native pruning, positioning and
unknown-room rules as Overgrowth. `underdocks_a0_base_restricted_v1` is the optional
unpruned test layout. The old Overgrowth import delegates to the shared generator;
its seed trajectories and profile identifiers are preserved.

[`generation/room_pools.py`](../game/headless/generation/room_pools.py) declares the
ordered pools. Three weak fights precede twelve normal entries; elites have their
own 15-entry queue. Refillable bags reject consecutive matching identities/tags,
including the Slug and Seapunk families across the weak-to-normal boundary. Boss
sampling uses Matriarch, Soul Fysh, Giant order, distinct from native discovery
order. The selected act's event shuffle and encounters consume the same UpFront
stream before Hive/Glory initialization. Campaigns reuse both Hive’s and Glory’s saved room sets.

The ten local events are Abyssal Baths, Drowning Beacon, Endless Conveyor, Punch Off,
Spiraling Whirlpool, Sunken Statue, Sunken Treasury, Doors of Light and Dark, Trash
Heap and Waterlogged Scriptorium. Native initialization shuffles them with all 18
shared events before applying eligibility. Eight shared events are normally eligible
in Act 1; the other ten remain in the queue for native ordering/fallback semantics.
Entry predicates retain resource, floor and enchantment requirements. Reads and
failed entries do not advance queues; successful event fights retain their separate
history and do not consume ordinary hallway entries.

`RunConfig.act`, `EncounterProgression.act`, map profile and seed-bound initialization
must agree. Private run schema v44 saves these declarations and rejects mixed-act
queues, maps, bosses or event pools atomically. Golden Compass map replacement and
Fur Coat marks keep the declared act and its encounter ownership.

The read-only [initialization oracle](../tools/native_initialization_oracle/README.md)
ran actual `RelicGrabBag.Populate`, `ActModel.GenerateRooms` and `StandardActMap`
methods from pinned build 0.107.1. The new
[13-seed fixture](../tests/fixtures/headless_underdocks_initialization_vectors.json)
matches ordered model metadata, all three room sets, complete maps and RNG counters/
suffixes. Existing Overgrowth vectors remain unchanged. This is native generation
evidence, not a claim of whole-run gameplay parity.

[`test_underdocks_run.py`](../tests/headless/test_underdocks_run.py) also covers native
and test RNG profiles, Neow acquisition, entry predicates, full generated routes
through boss rewards with every decision restored, and corrupted continuation
rejection. Combat victories in the full-route lifecycle tests are synthetic; the
ordinary CLI demo can lose and does not establish policy strength.

Validation on 2026-09-19: 4,814 broad headless/simulation/backend/encoder/CLI tests
passed in 295.18 seconds. The fresh wheel passed 89 route/native-reference tests
in 25.72 seconds; 213 installed headless modules and the CLI matched source bytes.
The installed Neow-to-Underdocks demo ended in defeat after 117 commands with
restore verification enabled. Independent semantic review, compilation and local
documentation link/diff checks passed. Native oracle build took 1.25 seconds and
reference execution 0.80 seconds; neither accessed profiles or launched gameplay.

## Generated campaign through Hive

`RunEngine.ironclad_run(seed=2, first_act="overgrowth", last_act="hive")` generates a solo A0
campaign through **Overgrowth or Underdocks → Hive**. Pass the existing Neow
`ancient_profile` to include Act 1’s opening. The CLI exposes `--route overgrowth-hive`
and `--route underdocks-hive`, with `--ancient neow` and `--verify-restore` supported.
`ironclad_act1` retains its one-act endpoint.

After the first boss’s rewards are left, `ContinueAct()` is the sole legal action.
It archives the completed map, path and room queues, reuses Hive’s startup-selected
encounters/events/Ancient, and resets current navigation and unknown-room odds.
Deck, HP, gold, inventory, item/card IDs, reward probabilities, relic bags and
persistent RNG streams carry forward. Construction is atomic: failure preserves
the previous completed act. Healing occurs when the player enters Hive’s explicit
row-zero Ancient, before its offers; Maw Bank pays afterward. Continuing itself
grants no heal or room reward.

Hive uses 14 ordinary rows, treasure on row 8, rest on row 14 and boss on row 15.
The `hive_a0_pruned_v1` profile uses the native `act_2_map` domain, point counts,
pruning and positioning. Its queues hold two weak fights followed by twelve normal
entries, fifteen elite entries and one boss. The full local/shared event pool uses
Hive eligibility and skips events already visited in Act 1. Total floor and combat
numbers continue across acts, including event fights. Winged Boots history spans
both maps. Golden Compass and Fur Coat retain their acquisition act and map;
Hive Ancient pickups can modify Hive’s map without deleting its Ancient entrance.

Spoils Map carried into Hive replaces the standard map with the native hourglass
profile `hive_a0_spoils_v1`, using its own fresh `spoils_map` RNG. Its plain quest
record binds original card IDs to the first treasure on the final map. Golden
Compass can replace this layout and retarget the quest; replacement provenance
preserves the quest’s save binding. Opening the marked chest grants normal chest
gold, then 600 gold per current Spoils Map copy and removes those copies. Removing
all original marker owners disables the quest. Leaving the chest unopened or
Silver Crucible suppressing its contents retains the cards; Ectoplasm suppresses
gold normally. Relic pickup remains a separate choice.

[`run/campaign.py`](../game/headless/run/campaign.py) owns the transition and compact
completed-act records. Shared map rules live in
[`map/standard.py`](../game/headless/map/standard.py); the existing Act 1 import is
a compatibility entry point. Private run **v44** requires campaign/history fields
and validates each act’s queues, map, event/unknown decisions, global combat count,
free travel and map relic ownership. Older run snapshots are rejected explicitly;
combat schema is **v35**. Hive boss reward exit records `ActCompletion(act=2, …)`
and stops at `ACT_COMPLETE` when `last_act="hive"`. The default campaign now
continues through Glory and the Architect as described below.

The read-only [native oracle](../tools/native_initialization_oracle/README.md)
executed actual pinned 0.107.1 `StandardActMap` and `SpoilsActMap` constructors.
[Hive vectors](../tests/fixtures/headless_native_hive_map_vectors.json) and
[Spoils vectors](../tests/fixtures/headless_native_spoils_map_vectors.json) each match
complete geometry, starts, RNG counters and suffixes for 13 seeds.
[`test_act2_run.py`](../tests/headless/test_act2_run.py) covers both starting regions
and both RNG profiles through Hive boss rewards, restoring every decision, plus
malformed history, failed transitions, Ancient timing and Spoils chest interactions.
Full-route victories are synthetic lifecycle tests; these results do not establish
live whole-run parity or demo-policy strength.

Broader validation covered all 5,124 collected cases. The initial run passed
4,084 before three failures in an outdated floor-count test double (321.39 seconds).
After updating that fixture to the cumulative room-count interface, all 1,046
affected/remaining cases passed in 69.19 seconds. Final map regressions include
the subsequent Golden Compass/Spoils ownership correction.

Validation on 2026-09-19: the final installed wheel passed 473 campaign, standard/
Spoils map, Underdocks, native initialization and Ancient regressions in 145.76
seconds. All 227 installed headless/CLI Python files matched source bytes.
The installed Underdocks→Hive Neow demo verified 117 decisions and ended in Act 1
defeat. Independent semantic review, compilation and documentation link/diff
checks passed. The Spoils oracle built in 1.11 seconds and executed in 0.52 seconds;
these read-only references did not launch gameplay or access player data.

## Generated campaign through Glory

`RunEngine.ironclad_run(seed=2, first_act="overgrowth")` now defaults to the complete
supported solo Ironclad A0 sequence **Overgrowth or Underdocks → Hive → Glory →
The Architect**. Neow remains an explicit `ancient_profile` option, matching the
existing startup API. `ContinueAct()` after Hive’s boss reuses Glory’s native
startup-selected Ancient and room queues without rerolling UpFront. Earlier act
maps, paths, queues and Spoils Map quest provenance stay in `completed_acts`.
The existing two-act API is available with `last_act="hive"`.

Glory uses the shared map generator with 13 ordinary rows, treasure on row 7,
rest on row 13 and boss on row 14. Its rest count is a uniform integer, 5 or 6;
its unknown count is the native standard Gaussian count minus one. Pruning,
repair and coordinate layout use the actual grid height. The `act3.map` alias
owns native `act_3_map`; generating Glory does not consume either earlier map RNG.
The `glory_a0_pruned_v1` profile is distinct from both earlier regions.

The row-zero Ancient is Nonupeipe, Tanx or Vakuu, or shared Darv when startup
allocated him to Glory. Entering that room runs its existing healing and choice
logic. The local/shared event queue uses Glory eligibility and skips previously
visited events across both earlier acts. A carried Lantern Key forces an unknown
room into War Historian Repy while still consuming its event-queue selection.
Golden Compass and Fur Coat bind their acquisition act and owning map; archived
Hive Spoils layouts retain their quest record after current Glory quest state resets.

The final boss has **no normal gold, card or potion rewards**, no pity/offer RNG
rolls, and no appended Hunt/Royalties combat rewards. The native reward-modifier
pass still runs: an eligible Wongo’s Mystery Ticket adds its three relic rewards.
The empty baseline retains the existing `LeaveRewards()` transition, followed by
`ACT_COMPLETE` and `ContinueAct()` into the Architect.

[`run/epilogue.py`](../game/headless/run/epilogue.py) owns that post-map event through
an exact `epilogue_event_id` and retained Glory `ActCompletion`. It invokes the
existing Architect event’s single `proceed` option; profile-dependent dialogue
and presentation are omitted. Entry adds no map node, TotalFloor or Ancient heal,
but still invokes room-entry hooks such as Maw Bank. Only choosing `proceed`
records `VICTORY`. Native post-victory presentation death is not a simulated defeat.
No Lantern Key or other optional event is required to finish the run.

Private **run v44** saves the epilogue identity and archived Spoils quest records;
combat uses **v35**. Restore requires the completed campaign/boss, matching
Ancient identities in both current and historical maps, and an owned Architect
event or completed victory. It rejects incomplete victory claims, mixed-act
history, final-boss ordinary rewards, and missing archived quest owners. Failed
map or Architect construction leaves the current state and RNG untouched.

[Native Glory map vectors](../tests/fixtures/headless_native_glory_map_vectors.json)
match all nodes, edges, starts, counters and RNG suffixes for 13 seeds using the
actual pinned 0.107.1 `StandardActMap` constructor. The
[read-only oracle](../tools/native_initialization_oracle/README.md) built in 1.20
seconds (seven existing nullable-context warnings) and executed in 0.42 seconds.
It did not launch gameplay or read profiles/saves. Final rewards and ending order
are source-backed; the native oracle does not execute complete campaigns.

[`test_act3_run.py`](../tests/headless/test_act3_run.py) covers both starting regions
and both RNG profiles through all three bosses and the Architect, restoring each
decision, plus native map vectors, queue/history corruption, final reward rules,
failed transitions, Lantern Key, map relics and archived Spoils ownership. Route
victories use synthetic combat outcomes to isolate run integration from policy
strength. They do not establish live whole-run parity or a winning demo policy.

Validation: the broad headless/simulation/consumer/package selection completed in
487.62 seconds with 5,415 passes and one test-fixture failure: Lava Rock’s
first-boss test selected the catalog’s first boss, now an Act 3 boss. Restricting
that fixture to Act 1 required no game-logic change; the affected relic and final
Glory campaign suites then passed **341 tests in 73.35 seconds**. The final
installed wheel passed **359 Act 2/Glory tests in 142.16 seconds**; all 246 packaged
headless/CLI Python files matched their source bytes. Neow-start routes covering
all three Glory bosses also passed (three tests, 2.91 seconds).

The installed CLI’s `underdocks-glory --ancient neow --seed 2 --verify-restore`
run restored 117 decisions before its demo policy lost in Act 1; this checks
packaging and continuation, not a three-act policy victory. Compilation, document
links and diff checks passed. Independent semantic review covered RNG ownership,
campaign persistence, final rewards and the Architect, with no remaining blockers.

## Complete Glory Act 3 encounter roster at A0

All 18 entries in pinned 0.107.1 `Glory.GenerateAllEncounters` are registered in
[`encounters/glory.py`](../game/headless/encounters/glory.py). Direct combats and
authored encounter overrides retain Act 3 context. Final bosses have no ordinary
reward bundle; Wongo’s ticket may still add relic rewards. Leaving records
`ActCompletion(act=3, …)`. Direct/authored encounters stop there; a generated full
campaign continues into the [Architect ending](#generated-campaign-through-glory).

| Kind | Encounter IDs (each prefixed `glory_`) |
| --- | --- |
| Hallway / weak (12) | `axebots`, `construct_menagerie`, `devoted_sculptor`, `fabricator`, `frog_knight`, `globe_head`, `owl_magistrate`, `scrolls_of_biting`, `scrolls_of_biting_weak`, `slimed_berserker`, `the_lost_and_forgotten`, `turret_operator` |
| Elite (3) | `knights`, `mecha_knight`, `soul_nexus` |
| Boss (3) | `aeonglass`, `queen`, `test_subject` |

The roster adds 25 monster types including summons; Construct Menagerie reuses
Punch Construct and Cubex Construct. Rules live in four small content modules:
[`glory_normal.py`](../game/headless/monsters/glory_normal.py),
[`glory_summons.py`](../game/headless/monsters/glory_summons.py),
[`glory_elites.py`](../game/headless/monsters/glory_elites.py) and
[`glory_bosses.py`](../game/headless/monsters/glory_bosses.py).

- Hallways implement Ritual's first-turn delay, Plating decay, Frog Knight's
  one-time charge, Soar damage reduction, Galvanized powers, Paper Cuts maximum-HP
  loss, Slimed generation, stolen Strength/Dexterity recovery, and Rampart's
  exclusion of extra player turns.
- Axebot Stock creates two successive replacements with fresh HP RNG and clean
  powers. Ordered death work follows player death listeners, so Gremlin Horn
  autoplay cannot target a replacement before it exists. Fabricator uses native
  summon choices, capacity, position order and per-command RNG. Target indices
  stay stable while execution follows bot positions. New bots wait until the next
  enemy turn to attack but receive the current side-end effects.
- Knights implement bounded random move repeats, Hex/Ethereal and Dampen.
  Dampen saves each original card's upgrade loss and restores it when its last
  source dies; copies do not inherit that recovery entitlement. Mecha Knight and
  Soul Nexus include their status generation, Artifact and attack/debuff cycles.
- Aeonglass escalates existing and newly generated Withers, Strength, and its
  six-card counter. Queen tracks drawn Bound applications and the first Bound
  play, including autoplay and card replays. End autoplay happens before Bound
  cleanup. Torch Head Amalgam's death changes Queen's relevant phase.
- Test Subject retains three genuine death/revival forms (100/200/300 HP), removes
  ordinary powers at death, and applies Painful Stabs after the complete attack
  command. Post-attack work survives attacker death and reactive draw choices.
  The final form alternates Intangible, including unpowered damage and The Boot.

[`core/afflictions.py`](../game/headless/core/afflictions.py) enforces one affliction
per card across Smog, Tainted, Galvanized, Hexed and Bound. Glory-specific lifecycle
hooks are in [`powers/glory.py`](../game/headless/powers/glory.py). The initial Glory
implementation (**combat v29 / run v43**) added plain card-effect/history fields and the resumable post-attack
boundary. Restore rejects unowned effects, impossible boss phases, forged upgrade
history, duplicate death work and inconsistent replacement slots. Older private
snapshots are rejected explicitly; public bridge contracts are unchanged.

The read-only [combat oracle](../tools/native_combat_oracle/README.md#glory-act-3-construction)
retains [144 native construction vectors](../tests/fixtures/headless_native_glory_vectors.json):
18 encounters × four seeds × two floor inputs. These match composition, HP,
initial moves and exact composition/Niche/MonsterAi counters and next-value suffixes.
The oracle executes native construction and initial move selection, **not**
`AfterAddedToRoom`, native turns, choices or rewards. Combat mechanics are checked
against inspected source and synthetic Python regressions in
[`test_glory.py`](../tests/headless/test_glory.py), including JSON continuation in
both RNG profiles, all encounter reward exits and malformed-state rejection.
These are not native trajectory or live full-game parity claims.

Validation on 2026-09-19: the broad Python integration run passed 5,330 cases in
420.33 seconds; its single failure was the old monster-catalog census (83, now
108), corrected and rechecked below. The final affected Glory/Hive/Underdocks,
reactive-death and native-interaction regressions passed 639 cases in 72.45 seconds.
Independent semantic review passed, including focused correction rechecks.

The installed wheel passed 278 encounter/CLI/native-interaction cases in 19.78
seconds. One CLI fixture required its repository-relative config in the isolated
test directory; that case then passed in 0.11 seconds. An additional installed
legacy action-mask check passed in 0.05 seconds. All 245 installed headless/CLI
Python files match source bytes. The installed authored CLI with Glory overrides
verified restoration across 96 decisions and ended in defeat; this is packaging
and continuation evidence, not a boss-victory claim. The native oracle built in
1.20 seconds and ran in 0.087 seconds. Compilation and documentation link/diff
checks passed.

Final census/Glory recheck: **352 passed in 19.52 seconds**, including all 238
Glory cases and the corrected global monster census.

## Complete Hive Act 2 encounter roster at A0

All 20 entries in pinned 0.107.1 `Hive.GenerateAllEncounters` are registered in
[`encounters/hive.py`](../game/headless/encounters/hive.py). They support direct
combats and authored encounter overrides, with Act 2 reward context and boss
completion. The generated campaign below connects these encounters to Act 1, Hive’s Ancient and its native map.

```python
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig

run = RunEngine(seed=7, config=RunConfig())
run.start_combat(encounter_id="hive_knowledge_demon")
# Use legal_actions()/apply(); Knowledge Demon choices are ordinary combat actions.
```

| Kind | Encounter IDs (prefix `hive_`) |
| --- | --- |
| Hallways, including weak variants | `bowlbugs`, `bowlbugs_weak`, `chompers`, `exoskeletons`, `exoskeletons_weak`, `hunter_killer`, `louse_progenitor`, `mytes`, `ovicopter`, `slumbering_beetle`, `spiny_toad`, `the_obscura`, `thieving_hopper`, `tunneler` |
| Elites | `decimillipede`, `entomancer`, `infested_prism` |
| Bosses | `kaiser_crab`, `knowledge_demon`, `the_insatiable` |

The rules include Hard to Kill's damage cap before Block, Rock's fully blocked
attack stun, Tunneler's preserved Block and interrupt, Slumber/Plating wake timing,
Louse Progenitor's once-per-card Curl Up, Tender's temporary stat loss, Personal
Hive's Dazed insertion, and Vital Spark/Tainted skill afflictions. Decimillipede
segments revive and only the final segment qualifies for Fatal effects.

Ovicopter allocates stable egg identities, hatches them in place, and executes
native egg-slot order without changing targeting indices. The Obscura's
Parafright retains its slot through death and revival. Interrupted enemy attacks
save their captured move and stop remaining hits if the actor dies, including
reactive draw/selection pauses.

Knowledge Demon offers three rounds of Disintegration versus Mind Rot, Sloth or
Waste Away through owned, serializable card previews. The Insatiable inserts
Frantic Escape into draw/discard, increases each copy's combat cost when played,
and forces death when Sandpit expires. Kaiser Crab tracks facing, opposing-arm
damage amplification and the surviving arm's Rage.

Thieving Hopper selects an original draw/discard card using native rarity
priority and generation RNG. Its exact permanent card is held outside the run
deck during combat. Killing Hopper offers that same card as an optional reward;
skipping it or allowing escape loses it. Ordinary gold rewards remain available
on escape. Flutter reduces powered attack damage and interrupts the planned move
after five damaging hits. Generated combat cards cannot be stolen.

The initial Hive implementation added original-card ownership in **combat v28 / run v42**, a sequestered combat
pile, permanent stolen-card ownership, Tainted flags, optional frozen enemy turn
order and Hive continuations. Restore rejects missing power counters, forged
monster choices, unowned stolen cards and misplaced turn-boundary tasks. Earlier
private schemas are rejected rather than migrated.

The read-only [native construction oracle](../tools/native_combat_oracle/README.md#hive-act-2-construction)
retains 160 actual native cases: all 20 encounters × four seeds × two floor inputs.
Python matches composition, raw construction HP, first move, RNG counters and next
values. Native `AfterAddedToRoom` hooks are outside that oracle: adjusted
Decimillipede HP, summon/revival, powers, choices, rewards and JSON continuation
are covered by source inspection and synthetic regressions in
[`test_hive.py`](../tests/headless/test_hive.py). This is bounded construction
parity, not a native full-combat or full-Act-2 demonstration. Ascension scaling and
multiplayer behavior remain outside the solo A0 implementation.

Validation: the broad headless/simulation/backend/agent/CLI regression run passed
5,059 tests in 332.75 seconds. The final installed wheel passed all 246 Hive tests
in 32.22 seconds, including the final revival/order corrections, and its 222
headless Python files matched the source bytes. Independent semantic review
checked those corrections and snapshot rejection cases. An installed authored-route
CLI run with Hive overrides verified restoration over 83 commands and ended in
defeat; it is packaging evidence, not an Act 2 victory demonstration.

## Complete Underdocks encounter roster at A0

All 20 entries in native `Underdocks.GenerateAllEncounters` are registered in
[`encounters/underdocks.py`](../game/headless/encounters/underdocks.py): 14 hallway/easy
encounters, three elites and three bosses. They use 22 monster types including
summons; Punch Construct is shared with existing content. The independent
[census fixture](../tests/fixtures/headless_underdocks_scope.json) pins build
0.107.1 / Steam 23811903 and the assembly SHA-256. Behavior was checked against
that decompiled source. Regression evidence is synthetic, not live gameplay parity.

All IDs below have the `underdocks_` prefix:

| Kind | IDs without prefix |
| --- | --- |
| Hallway/easy | `corpse_slugs`, `corpse_slugs_weak`, `cultists`, `fossil_stalker`, `gremlin_merc`, `haunted_ship`, `living_fog`, `punch_construct`, `seapunk`, `seapunk_weak`, `sewer_clam`, `sludge_spinner`, `toadpoles`, `two_tailed_rats` |
| Elite | `phantasmal_gardeners`, `skulking_colony`, `terror_eel` |
| Boss | `lagavulin_matriarch`, `soul_fysh`, `waterfall_giant` |

Construct these directly or substitute them into the existing authored route:

```python
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine

run = RunEngine(seed=7, config=RunConfig(), rng_profile="native")
run.start_combat(encounter_id="underdocks_living_fog")

route = RunEngine.ironclad_slice(
    route="overgrowth-act1",
    hallway="underdocks_gremlin_merc",
    elite="underdocks_phantasmal_gardeners",
    boss="underdocks_waterfall_giant",
)
```

Encounter composition has its own floor/native-ID seed. Native runs reuse the
existing monster-AI and Niche HP streams; observations and restores consume no
randomness. Fixed group slots and authored opening roles match the source.
Summons append stable combat slots, retain separate native rat positions, and
wait until the next enemy turn to act.

Rules implemented in the content modules include:

- Corpse Slugs gain Strength and lose their next turn when an ally dies. Cultists
  start Ritual without an immediate Strength tick. Fossil Stalker gains Strength
  once per hit that deals unblocked damage, including damage absorbed by Osty
  and lethal damage followed by revival; its moves repeat at most twice.
- Sewer Clam and Matriarch retain Plating turn timing. Toadpole removes its
  temporary Thorns before Spike Spit; retaliation precedes the incoming hit,
  including lethal hits, and direct pet retaliation consumes shared Block.
- Rat reinforcements preserve weighted AI, cooldowns, the three-call shared limit
  and vacant native positions. Living Fog creates Minion Gas Bombs and Smog:
  after a Skill, further Skills are unplayable until turn cleanup. New Skills
  entering during that first Skill already carry Smog; automatic plays use the
  same restriction. Artifact blocks Smog and Matriarch's individual stat debuffs.
- Gardeners gain Block only after a complete card attack, once per opposing turn,
  based on that attack's first damage result for each receiver. This handles
  multihits, random targets, nested plays, custom attacks and extra turns.
  Skulking Colony caps accumulated unblocked damage at 20 per side turn.
  Terror Eel's threshold interrupts with a stun before Terror and its 99 Vulnerable.
- Matriarch sleeps for three turns or wakes when damaged. Soul Fysh creates Beckon
  in the correct piles and cycles Intangible. Waterfall Giant retains steam after
  lethal damage, performs About to Blow once, then explodes and dies. Reactive
  damage and paused draw choices cannot skip these forced transitions.
- Gremlin Merc steals up to 20 gold after each move. Death summons Sneaky and Fat
  Gremlins; killing Fat offers the stolen gold separately. A fleeing Fat leaves
  zero ordinary gold if carrying loot, otherwise half. The recovered fixed gold
  amount consumes its native reward-population RNG draw before relic-added offers.

Monster powers remain owned content state; pending work contains IDs and plain
values. Snapshot validation binds death work and attack completions to their
owners and preserves interrupted enemy moves independently of the next intent.
The private schema change records Smog, these continuations and stolen-loot
reward outcomes; older snapshots reject instead of guessing missing values.

[`test_underdocks.py`](../tests/headless/test_underdocks.py) covers the census,
12-turn trajectories and reward handoffs for every encounter under both RNG
profiles, defeat, rule interactions and invalid continuation rejection.

Validation on 2026-09-19: the broad headless/simulation/backend/encoder/CLI checks
passed 4,749 tests in 275.07 seconds. After the final multihit correction, the
installed wheel passed all 105 Underdocks tests in 20.30 seconds; all 212 installed
headless modules matched source bytes. The authored CLI smoke ended in defeat
after 114 commands with restore verification enabled. Independent semantic review,
compilation, documentation links and diff checks passed.

These encounters are also available in the [generated Underdocks route](#generated-underdocks-act-1).
Multiplayer remains outside this roster; A1–A10 modifiers are now implemented as
described in [ascension levels](#ascension-levels). Boss reward
exit records Act 1 completion through the existing lifecycle, not full-game victory.

## Complete Overgrowth encounter roster at A0

All 22 encounters in pinned `Overgrowth.GenerateAllEncounters` are registered in
`encounters/catalog.py`. The native-ID mapping is an explicit census: 16 normal/
easy encounters, three elites and three bosses, with 29 monster types including
summons. Every encounter can be constructed directly, restored during combat and
handed through the existing rewards/act-completion lifecycle. Run-owned A0 encounter queues and base procedural topology are now available
through the generated route below. Discovery overrides remain open.
See the [roster, native anchors and validation](evidence/overgrowth_roster_2026_09_13.md).

The additional content includes Cubex Construct, Flyconid, Fogmog/Eye With Teeth,
Inklets, five Ruby Raiders, Slithering Strangler, Snapping Jaxfruit, Vine Shambler,
Bygone Effigy, Phrog Parasite/Wrigglers, Ceremonial Beast and Kin followers/priest.
Mixed groups preserve native member order and authored opening roles. Ruby Raiders
select three distinct variants; normal slimes have four members. Flyconid retains
its native move cooldowns, including the source's first-branch fallback when all
weights are zero. Generated runs use native primitives and run-owned combat streams;
complete entity initialization and move-selection call-order parity remain open.

Rules added for these encounters:

- Frail multiplies powered card block by 0.75; potion block is unchanged. Artifact
  prevents and consumes one debuff application. Shrink, Weak, Vulnerable and Slow
  damage multipliers combine before the final floor.
- Constrict deals blockable non-attack damage at player-side end and clears on
  its recorded applier's death. Shrink also retains its actual applier slot.
- Tangled increases attack-card costs for the next player turn. Ringing allows
  only the first card started that turn, including skills; both expire at
  player-side end. Slow counts completed cards and resets on the enemy turn.
- Ceremonial Beast applies Plow 150, then attacks/gains Strength. Positive HP
  damage crossing that threshold removes Plow/Strength and interrupts with a
  stun, followed by Beast Cry, Stomp and Crush.
- Phrog's death runs automatic Gremlin Horn draws before appending four owned
  Wriggler slots. Unfinished Infested work prevents premature victory. Their
  initial stun and alternating slot roles survive restore. A paused Horn choice
  lets Infested and the enclosing player action finish before it resumes.
- Eye With Teeth remains in its slot while dead, clears debuffs, cannot be hit
  during revival and spends its next turn restoring HP. Secondary minions do
  not keep a fight alive after the last primary enemy dies. Summons do not join
  an enemy turn already in progress.
- Dazed exhausts from hand at turn end; Infection deals three blockable damage
  per copy remaining in hand. Generated cards stay in combat, outside the master
  deck, and dead-player/ended-combat rules stop subsequent effects.

Use `RunEngine.ironclad_slice(route="overgrowth-act1", boss=..., elite=...,
hallway=...)` or the matching installed CLI flags to substitute any registered
encounter of that room kind. Defaults preserve the earlier route. The route still
has five fights; a complete native Act 1 requires map/progression and remaining
content work, not another enemy backend.

## Remaining Act 1 events

The default generated catalog contains all 13 Overgrowth events and eight shared
events normally eligible in Act 1 (21 total), under the all-unlocked solo scope.
The ten additions are:

| Event | Implemented decisions |
| --- | --- |
| Luminous Choir | Remove two cards and gain Spore Mind, or buy a random relic for the captured price |
| Unrest Site | Heal the missing HP captured at entry and gain Poor Sleep, or trade maximum HP for a relic |
| Wood Carvings | Transform a Basic into Peck/Toric Toughness, or enchant a card with Slither |
| Brain Leech | Choose a character card, or take damage for an optional colorless reward |
| Room Full of Cheese | Choose two of eight Common cards, or take damage for Chosen Cheese |
| Self Help Book | Apply Sharp, Nimble or Swift to two eligible cards |
| Tea Master | Buy Bone Tea/Ember Tea or take Discourtesy |
| The Future of Potions | Trade a captured potion for an upgraded card reward matching its rarity and assigned type |
| The Legends Were True | Take Spoils Map or lose HP for an ordinary potion |
| This or That | Trade HP for gold, or gain a random relic followed by Clumsy |

Content lives in `events/act1_content.py`. `events/steps.py` executes small plain
operations and pauses through existing card, potion and relic choices. Receipts,
selection ownership and resource checkpoints reject inconsistent restores;
checkpoints are consistency checks, not authentication against coordinated edits.
Future of Potions freezes manual potion use/discard until its event finishes.
Lethal damage preserves unconditional native resource/relic effects while blocking
new card choices. Fairy revival continues the same branch.

Supporting rules include Peck's hits, Toric Toughness's captured block for two
future block-clear hooks (including Barricade), Slither's combat-long 0–3 cost
reroll after early draw autoplay, and the complete curse catalog. End-turn curse
work preserves post-autoplay Regret capture, ethereal-first ordering and remaining
effects across reactive draws. Neow's Bones uses the separate ten-card modifier pool.
Spoils Map is carried as its native quest card; generated campaigns implement its Hive map and 600-gold chest quest. Act 1 queues retain their later-act and disabled-event eligibility exclusions.
Native-profile card reward probabilities are implemented; unlock epochs and complete
run initialization/call-order parity remain separate work.

## Ordinary events

The Act 1 route offers Jungle Maze Adventure on the left and Aroma of Chaos on
the right after its third combat, immediately before treasure. `ChooseEventOption(event_instance_id, option_id)` chooses
`solo_quest` or `join_forces`. Solo Quest deals 18 damage, then grants the larger
gold amount; Join Forces grants the smaller amount without damage. There is no
initial leave choice. After resolution, `LeaveEvent(event_instance_id)` returns
to the map. Lethal Solo remains selectable and ends in defeat; the native ordered
sequence still grants its gold after damage, but no further action is available.
The demo chooses Join Forces.

Native payouts start at 150/50 with independent float variation from -15 to +15,
then truncate when acquired. The headless model samples integer payouts 135–164
and 35–64 once on entry using `event.jungle_maze`; exact native float/RNG parity
is not claimed. Each event owns its ID, stage, variables and selected outcome.
Inspection and restore consume no draws, and stale/repeated choices cannot award
again. Map event IDs and the event catalog are included in private snapshots.

Aroma offers `let_go` (transform one card) and `maintain_control` (upgrade one).
`ChooseEventCard(event_instance_id, card_instance_id)` resolves the mandatory
selection. There is no cancel; zero eligible cards finish without mutation, and
one resolves automatically. Multiple candidates expose only their exact card
commands until selection finishes. Upgrades preserve identity; transformation
uses `run/deck.py` to replace the original at the same index with a fresh owned
ID and base upgrade level, excluding its original definition. Candidate validation
precedes an owned RNG draw; failed transforms preserve deck, allocator and RNG.

The Ironclad transformation pool contains all 80 common/uncommon/rare cards.
Aroma, Morphic Grove and Whispering Hollow also accept basic and Ancient Ironclad
sources, implemented colorless/event cards and all 18 curses. Eternal cards cannot be selected as transformation sources; a transformation can produce an Eternal curse.
Giant Rock transforms through the supported colorless pool.
Curse transformations use their own 18-card pool, exclude the original
definition and reset the replacement lifetime. Missing catalog content or
unsupported sources reject entry atomically. Native generation probabilities remain open. The demo chooses Maintain Control, prioritizing Bash. Selector candidates
and resolved results are plain saved data checked against the permanent deck.
See [Aroma source and validation evidence](evidence/aroma_of_chaos_2026_09_13.md).

`events/jungle_maze.py` and `events/aroma_of_chaos.py` own event rules;
`run/events.py` owns lifecycle and
dispatch. The older primitive event fixture still uses `run/rooms.py`; native
content is not dispatched by its synthetic option dictionary. Native event pool
profile unlock filters and multiplayer voting remain open; the full solo event
catalog and its resource/act eligibility are implemented above; the generated route now has owned
unique-event progression and exhausted-pool repetition. See [source and validation evidence](evidence/first_event_2026_09_13.md).

## Tablet of Truth and Morphic Grove

The default generated Overgrowth route now includes both events. Authored routes
and the older base-map fixture keep their earlier explicit event pool. Both use
`ChooseEventOption(event_instance_id, option_id)` and `LeaveEvent`.

**Tablet of Truth:** `smash` heals 20 HP and finishes. `decipher_1` through
`decipher_4` cost 3, 6, 12 and 24 maximum HP respectively, each upgrading one random
upgradable deck card. Current HP is capped at the new maximum. After each step,
`give_up` retains the costs and upgrades and finishes. `decipher_5` pays current
maximum HP minus one, leaving 1 maximum HP, and upgrades every remaining upgradable
card. A cost at least equal to maximum HP leaves maximum HP at 1 and kills the
player without an upgrade. An empty/fully upgraded deck still pays the cost but
uses no upgrade RNG. Each repeated page and automatic result restores exactly.

**Morphic Grove:** `loner` grants 5 maximum/current HP. `group` spends all current
gold, then requires two original deck cards. With more than two candidates,
`ChooseEventCard` nominates one at a time; the first nomination changes no card and
reveals no transformation. Both replacements resolve together after the second
nomination, using the same restricted Ironclad pool as Aroma. They retain deck
positions and receive fresh unupgraded identities. There is no cancel or duplicate
nomination. If at most two cards exist, all are selected automatically, including
the zero-card case reachable through native exhausted-pool fallback. A failure
while preparing either replacement preserves the paid selection, deck and RNG.

The event modules own their content rules. Shared pool validation lives in
`events/transformation.py`; eligibility entry conditions live in
`events/eligibility.py`. Pending decisions and results contain plain data, without
callbacks. The demo chooses Smash and Loner. Foreign-character pools and native generation probabilities remain open.
See [pinned source and validation](evidence/overgrowth_events_2026_09_13.md).

## Whispering Hollow, Wellspring, Slippery Bridge and Sunken Statue

These four definitions form part of the 21-event default generated pool. Each
owns plain pending data, exact commands and JSON continuation; authored fixtures
retain their explicit pools. Shared `events/potion_rewards.py` and
`events/deck_choice.py` handle acquisition and mandatory single-card selections.

- **Whispering Hollow:** `gold` pays an entry-time price of 26–44 gold for two
  optional potion rewards. `hug` transforms one chosen card, then deals 9 damage,
  including lethal damage. Zero/one candidates resolve automatically.
- **Wellspring:** `bottle` offers one optional potion. `bathe` removes one chosen
  card and adds Guilty, including when the original deck is empty. Guilty is
  unplayable and is discarded normally at turn end; its master-deck instance disappears after five completed
  combats. Clumsy is unplayable/Ethereal and has no expiry.
- **Slippery Bridge:** `overcome_N` removes the currently offered card;
  `hold_on_N` pays 3, then 4, then 5 damage and so on to reroll. The first offer
  prefers nonbasic cards. Later offers exclude the previous definition and all
  skipped instances, falling back to all removable cards when needed. Repeated
  pages retain distinct command identities. A lethal hold still records its reroll.
- **Sunken Statue:** `dive_into_water` grants 101–121 entry-time gold before dealing
  7 damage. `grab_sword` grants Sword of Stone. Each owned sword tracks elite wins
  independently and becomes a new Sword of Jade after five. Each Jade grants
  3 Strength at combat start; repeated event rewards can yield duplicate swords.

Potion bundles expose `claim_potion_N` and `finish_rewards`. Full inventory removes
claim actions until `DiscardPotion` frees a slot; finishing skips unclaimed items.
Discarding a claimed potion never makes its reward claimable again. The supported
reward pool now contains all 48 ordinary Ironclad potions, with native rarity
distribution. Curse transformations use all 18 native definitions and reject Eternal source cards. Native RNG parity remains open. Slippery Bridge requires at least one removable card in native play; no empty-deck fallback is required. Candidate selection uses the card’s Basic rarity and Eternal keyword, including foreign starters.

`run/lifecycle.py` handles master-deck expiry and elite relic evolution after
combat; combat copies do not age the persistent cards. The demo chooses Gold,
Bottle, Overcome and Dive. See [source and validation](evidence/event_pack_2026_09_13.md).

## Dense Vegetation and event combat

Dense Vegetation has two initial choices. `trudge_on` loses 8 HP, then grants an
entry-time 61–99 gold roll, including after lethal damage. `rest` heals 30% maximum
HP, truncated and capped, using the shared rest calculation. Rest exposes only
`fight`; it cannot be repeated or followed by leaving the event.

Fight launches four Wrigglers without the Phrog spawn stun. Slots 0/2 open with
Bite and 1/3 with Wriggle; all alternate thereafter. Victory uses the ordinary
hallway reward bundle (10–20 gold, three supported card offers and the ordinary
potion roll), then returns to the map. The event does not resume. Defeat is
terminal. Burning Blood, persistent curse ageing and potion use follow the same
combat lifecycle; this is not an elite victory for Sword of Stone.

`events/combat.py` defines plain requests/history records, and
`run/event_combat.py` owns the transfer. Both map and event fights use the same
combat construction and reward modules. `RunState.event_combats` tracks these
extra fights separately from normal encounter assignments, so event fights do
not consume the hallway/elite queues or add map visits. Its records bind the
original event identity, node, encounter, combat number, outcome and reward exit.
Construction failure preserves the healed event and RNG; duplicate launch,
missing owner/configuration and invalid history reject. Dense Vegetation requires
`RunConfig` even in a directly initialized fixture, so both branches are usable.

The default generated pool includes this event; authored routes retain their
existing event fork. The demo chooses Rest, then Fight. Resuming events, extra
special rewards and temporary training rules remain separate follow-ups; this
module currently supports the native non-resuming flow only. Native RNG and
full reward-pool fidelity remain open. See [source and validation](evidence/dense_vegetation_2026_09_13.md).

## Sapphire Seed and Sown

`eat` heals 9 HP, capped, before a mandatory one-card upgrade. `plant` permanently
adds Sown to one eligible card. Both resolve zero/one candidates automatically;
multiple candidates use exact `ChooseEventCard` commands with no cancel. Upgraded
cards are valid Plant targets and keep their upgrades and identity. The demo
chooses Plant.

`enchantments/base.py` owns explicit definitions and plain per-card instances:
definition ID, positive amount and a combat trigger flag. `Card.enchantment`
survives upgrades, permanent deck snapshots and combat copies. Sown grants 1
energy after the first completed play each combat, after any card selector and
before after-card enemy hooks. It does not reduce the cost needed to play the
card. Replaying it after a reshuffle gives no further energy. The permanent
instance remains untriggered; each fresh combat copies it independently. Combat
snapshot/search clones preserve the current trigger state.

Native eligibility excludes status/curse/quest cards, unplayable permanent cards
and any already enchanted card; Sown cannot stack. The existing internal `block`
category is a native skill and remains eligible. Ethereal alone does not prevent
enchantment. Transforming an enchanted card produces a fresh unenchanted card;
removal removes its enchantment along with that owned card.

When a card kills the final enemy, Sown records its trigger but gives no energy.
If the player dies during the card, the enchantment hook is skipped. Pending and
resolved event snapshots validate the original deck and exact upgrade/enchantment
result. Earlier private schemas reject rather than inventing missing state.
Other enchantments, card duplication effects and native RNG parity remain open.

The source check also corrected Guilty: keyword 4 is Unplayable, not Ethereal.
Guilty now discards/reshuffles normally until its five-combat expiry; Clumsy retains
both Unplayable and Ethereal. See [source and validation](evidence/sapphire_seed_2026_09_13.md).

## Byrdonis Nest and Hatch

`eat` gains 7 maximum and current HP; `take` adds an unplayable Byrdonis Egg to
the permanent deck. The egg is not Ethereal or Eternal: it discards normally,
cannot upgrade or receive Sown, and can be removed or transformed. Owning an egg
or a relic with `adds_pet` excludes Nest during ordinary event selection. The
native exhausted-pool fallback can still repeat it.

An egg enables `Hatch` alongside normal rest/smith options. Hatching consumes that
rest site's action, grants an owned Byrdpip relic and replaces **every** permanent
egg in place with a fresh base Byrd Swoop. Other cards retain identity, upgrades
and enchantments. Repeated acquisition keeps independently owned Byrdpip relics.
Choosing Rest or Smith instead preserves the egg for a later site; canceling
Smith restores Hatch availability. The demo prefers Take and Hatch.

Byrd Swoop is a zero-cost attack dealing 14 damage, or 18 upgraded. It uses player
Strength/Weak and target modifiers and does not exhaust. Native Byrdpip's actor
provides the attack animation; its idle move loop has no combat effect and enemy
player targeting excludes it. The headless engine retains relic/gameplay state
without a cosmetic actor or skin. In-combat Byrdpip acquisition remains unsupported;
the implemented hatch acquires it outside combat.

Egg, Byrd Swoop and colorless cards transform into the full 53-card single-player
colorless pool, excluding the original definition. Finesse costs zero, gains 4/7
block and draws one; Flash of Steel costs zero, deals 5/8 damage and draws one.
These cards remain separate from Ironclad combat rewards. Native sampling parity
remains open.
All three existing transformation events share these family rules.

Event content stays in `cards/event_cards.py` and `events/byrdonis_nest.py`;
colorless definitions live in `cards/colorless.py`. Owned hatch
state lives in `run/hatching.py`. The relic pickup uses shared deterministic deck
replacement and the owning engine's card catalog. Pending snapshots bind original
cards and prior relic IDs to the fresh grant; missing content and malformed results
reject without partial mutation. The Nest batch introduced run v17/event profile v6. Current combat/run formats
are described below; event profile v7 is current.
See [source and validation](evidence/byrdonis_nest_2026_09_13.md).

## Treasure rooms

The `overgrowth-act1` route now visits `treasure` after the third combat, before
its first rest site. `OpenChest()` grants 42–52 gold once. The single relic can
then be taken using `ClaimTreasureRelic(treasure_id)` or declined with
`LeaveTreasure()`. Leaving a closed chest grants nothing. The example player
opens the chest and claims its relic; direct commands also permit skipping.

The relic is drawn on room entry from the declared reward relic pool (Strawberry/Pear/Mango on the authored route). A drawn
relic leaves the restricted treasure pool even if the chest or relic is skipped.
The exhausted pool offers Circlet, which has no pickup effect and permits multiple
separately owned instances. Ordinary relic definitions still reject duplicates.
Gold uses the owned `treasure.gold` stream on opening; the relic uses
`treasure.relic` on entry. Neither inspection nor restore rerolls or grants rewards.

This authored route retains uniform sampling and a treasure-specific depleted pool.
Native-profile generated runs use rarity weights and shared/player bags across sources. Tutorial overrides,
multiplayer allocation, treasure-suppression modifiers and extra reward hooks
remain open. A native suppressed empty chest is distinct from ordinary pool
exhaustion, which uses Circlet. See [source and validation evidence](evidence/first_treasure_2026_09_13.md).

## Shops

The `overgrowth-act1` route offers `merchant` or `boss_camp` after its fourth
fight. `--path left` visits the merchant and then continues to the camp;
`--path right` bypasses it. The demo buys one affordable card, removes a starter
if affordable, then leaves. Direct commands can buy any sequence of legal stock.

`BuyShopItem(offer_id)` grants the item through shared acquisition rules, charges
its displayed price once and marks that exact offer sold. `BeginShopRemoval()`
opens a master-deck choice; `ChooseShopRemoval(instance_id)` permanently removes
that instance. `ChooseShopRemoval(None)` cancels for free. Removal costs 75 gold
plus 25 per previous successful shop removal and is available once per shop.
Eternal cards are excluded from removal choices. `LeaveShop()` returns to the map. While
selecting a removal, only removal/cancel commands are legal.

For this authored fixture route, stock is explicitly authored: one common, uncommon and rare card from the full
80-card Ironclad ordinary pool; one uncommon and rare from the full 53-card solo
colorless pool; one unowned Strawberry/Pear/Mango; and Fire and Block Potions.
An exhausted fruit pool omits that slot. One character card is on sale at half its
rounded price; colorless cards cannot be the sale slot. Native base prices are
50/75/150 for character cards, 86/172 for uncommon/rare colorless cards (the native
1.15 multiplier, rounded before variation), 175/225/275 for fruits and 50 per potion. Cards and potions vary by ±5%; relics
by ±15%. Sampling uses owned `shop.stock` and `shop.prices` streams, with discrete
basis-point variation; this is not native pool composition, rarity weighting,
float precision or RNG parity. Generated native-profile merchants use the 13-slot
composition and exact arithmetic described above. Membership Card discounts, The Courier restocking and relic pickup selectors now use the shared relic rules. See [source and validation evidence](evidence/first_shop_2026_09_13.md).

## Compatibility and limits

`CombatEnv` keeps legacy observations, discrete masks, reward shaping and trajectory
recording around `CombatEngine`. Its fixed vocabulary remains intentionally small.
The previous `strike_upgrade_v1` constructor option was an unreleased experiment
at commit `7ca5f77` and has been removed. Strike+ now runs directly in the game
engine; old profiles are not silently reinterpreted. The existing `headless_v0`
contract and accepted base backend fingerprints are unchanged.

The old `game/engine` map/reward/room decision machinery and
`ReducedRunBackend` continue serving their fixed synthetic protocol fixtures.
They are not the implementation destination for new game content. Replacing that
consumer with a generic adapter over `RunEngine` is deferred integration work,
not an invitation to maintain two evolving rule sets.

The first slice starts Ironclad with 80 HP, 99 gold, the ten-card starter deck,
Burning Blood and three empty potion slots. Its authored route is Nibbit →
rest site → Overgrowth slimes → `slice_complete`. Each victory returns combat HP,
applies Burning Blood's capped 6 HP heal once, then generates a hallway reward
bundle. Ordinary loss ends the run without victory healing or rewards.

`RunEngine.ironclad_slice(route="overgrowth", seed=2)` uses the same game engine
and inventories on a longer authored graph. The CLI equivalent is
`sts-headless-play --route overgrowth --path right --seed 2 --rest-choice rest --verify-restore`.
The route contains four combats and runs as follows:

1. Solo Nibbit.
2. Choose slimes or Fuzzy Wurm; then fight the other as the third combat.
3. Rest or Smith.
4. Choose solo Mawler, paired Nibbits or the Byrdonis elite, collect rewards and
   reach `slice_complete`.

The two forks give six paths. Direct `ChooseNode` commands select
any legal path; `--path left|right` makes the demo consistently choose the first
or last branch. The graph and visited history already survive run snapshots,
while the active encounter ID preserves its reward kind. Sibling/visited nodes cannot be
entered, and death stops progression without healing or rewards. The default
`first-slice` route remains the smaller two-combat example. Neither authored
route implements native map generation or complete encounter pools. The separate
`overgrowth-act1` route adds a boss as described below.

Fuzzy Wurm has 55–57 A0 HP and cycles attack 4 → gain 7 Strength → attack 4,
then repeats; Strength accumulates. Paired Nibbits retain front/back slots:
front starts with Hesitant Slice, back with Hiss. Both then follow the existing
Slice → Hiss → Butt cycle, without changing role after the other dies. Mawler
has 72 HP, opens with Claw 4×2, and samples equally among legal Rip and Tear 14,
Roar 3 Vulnerable and Claw successors. Attacks cannot repeat immediately; Roar
can happen once. Its branch rolls consume Python RNG even with one legal move.
Native branch order is retained, but native RNG sequence parity remains open.
See the [source and route acceptance](evidence/overgrowth_routes_2026_09_13.md).

Byrdonis has 81–84 A0 HP, opens with Swoop 17, then alternates Peck 3×3 and
Swoop. Its Territorial 1 adds one Strength after each completed enemy-side turn,
so the first Peck deals 4×3 before other modifiers. The power uses an owner-side
lifecycle rule; it does not trigger at the end of the opposing side or once per
other enemy. Dead owners do not trigger.

Hallway rewards contain 10–20 gold; all three elite encounters reward 35–45 gold and one
relic. Both have three distinct offers sampled from Pommel Strike,
Shrug It Off, Iron Wave, Body Slam, Armaments, True Grit and Uppercut, and a possible Fire or Block Potion.
Potion drop chance starts at 40%, changing by ten percentage points down after a
drop or up after a miss. The integer odds and named Python streams are
project-authored sampling; they do not reproduce native RNG or full pool/rarity
generation. Rewards can be claimed independently or forfeited by leaving.
A full potion inventory requires discarding an owned potion before claiming
another; slots never shift and discarded IDs are never reused.

The restricted elite relic pool is Strawberry (+7 max HP), Pear (+10) and Mango
(+14), sampled uniformly from unowned entries. `ClaimRelic()` applies the maximum
HP increase and heals the same amount once; restoring does not apply it again.
Removing the relic does not reverse the permanent gain. Pickup is currently
supported outside combat only. A depleted pool rejects elite entry before moving
the map cursor or consuming RNG. This explicit content limit is not a native
relic-pool exhaustion rule. Generated native-profile runs use the full configured pools,
native rarity weighting and upgrade checks. See the
[first elite source and acceptance evidence](evidence/first_elite_2026_09_13.md).

`RunEngine.ironclad_slice(route="overgrowth-act1")` extends the four-combat
Overgrowth route with another Rest/Smith site and Vantom as the fifth combat.
It retains native starter inventory and extends the eight-card hallway pool with
Sword Boomerang for this route. Earlier routes retain their original pools.
Vantom has 173 A0 HP and Slippery 8, and cycles Ink Blot 7 → Inky Lance 6×2 →
Dismember 26 plus three Wounds in discard → Prepare (+2 Strength). Slippery caps
each unblocked hit at 1 HP and consumes one stack. Fully blocked/zero hits consume
none; stacks survive turn boundaries. Attacks and Fire Potion both respect it.
Sword Boomerang costs 1 and deals 3 damage to a random living enemy three times,
or four when upgraded. Each hit chooses again, can repeat a target, and consumes
a Slippery stack independently. It stops rolling targets when combat ends. Its
owned `Deck.target_rng` is independent of shuffle and hand-selection streams;
Python sampling is deterministic but does not reproduce native seed sequences.
The target stream survives JSON restore and isolated analysis cloning.
Wound cannot be played or upgraded, but can be selected/exhausted by other cards.
Generated Wounds have combat-owned IDs and never enter the persistent master deck.

Boss rewards contain 100 gold, a possible potion and three rare offers from
Impervious, Offering and Fiend Fire, with no elite relic. The pool is deliberately
restricted; full native reward generation remains open. Impervious costs 2 and
gives 30/40 block. Offering costs 0, loses 6 HP through block, gains 2 energy,
and draws 3/5 cards. Fiend Fire costs 2, exhausts the other cards in hand, then
hits its selected enemy for 7/10 per captured card. All three exhaust themselves.
Fiend Fire resolves each hit separately, including Slippery consumption, and
stops attacking a dead target. Lethal Offering ends combat before energy or draw.

Leaving boss rewards, including forfeiting them, records
`ActCompletion(act=1, boss_encounter_id="overgrowth_vantom")` and ends this supported
run in `act_complete`. Winning the fight alone leaves the reward decision active.
This authored route ends at Act 1. Generated campaigns continue through Hive, Glory and the Architect; only that ending records full-game victory. The example player is deliberately simple;
`--route overgrowth-act1 --seed 2 --path right --rest-choice rest --verify-restore`
won with the earlier restricted card pool after Aroma upgraded Bash. The historical left/rest seed-2 route also won,
including Jungle Maze, treasure and shop decisions. Those policy outcomes are
not carried forward to the full 80-card reward pool. The original Maze/elite
route remains a tested defeat case. See the
[Aroma acceptance](evidence/aroma_of_chaos_2026_09_13.md). This five-fight route omits
most of a native Act 1 map and its deck-building opportunities. See the
[boss source and acceptance evidence](evidence/first_boss_2026_09_13.md).

At a rest site, `Rest` heals floor(30% of maximum HP), capped at maximum HP.
`Smith` opens a plain-data, cancelable selection of implemented upgrades.
`ChooseUpgrade(instance_id)` commits one exact card; `ChooseUpgrade(None)` returns
to the rest options without spending the action. Only one rest/smith action can
be completed. All 85 single-player Ironclad cards can be upgraded once. Pommel
Strike+ deals 10 and draws 2; Shrug It Off+ gives 11 block and draws 1; Iron Wave+
gives 7 block then deals 7; Body Slam+ costs zero and still scales with current
block. Unsupported cards and further upgrade levels remain excluded explicitly.
Fire Potion deals 20 damage, respecting enemy block and ignoring attack modifiers; Block
Potion gives 12 block. Both are combat-only and cost no energy. Their use consumes
the exact owned instance before checking combat completion. See the
[native rule evidence and scope](evidence/first_vertical_slice_2026_09_13.md).

The slime encounter uses native small/medium/small slot ordering, with one small
Leaf, one small Twig and either medium variant. Medium Twig starts with Sticky
Shot, then attacks; after one attack the next move is equally likely to attack
or use Sticky Shot, and after two attacks Sticky Shot is forced. Small Leaf
starts with an equal choice and then alternates. Both random-branch models
consume a Python roll on each transition, including forced choices. These
corrections change old seeded slime trajectories; native RNG parity is still open.

Card draws and later block/status effects stop when combat is ending. A lethal
Pommel Strike does not draw when it kills the last enemy, but still draws if
another enemy remains. The player references the owning combat's enemy slots
for this rule; reset, JSON restore and search cloning explicitly rebind that
alias. Enemy moves stop on player death before later effects or another roll.

This is a partial game model. Native RNG parity, full status/hook ordering,
other-character draw/pile hooks and card-zone mechanics, remaining items,
complex selections, full merchant pools/modifiers, native event eligibility and map modifiers,
all content and complete target-game progression remain in the
[implementation backlog](HEADLESS_FULL_GAME_IMPLEMENTATION.md). `RunEngine`
orchestrates the restricted slice, not a complete native run. Other ascensions
reject explicitly. Generic `RunEngine()` retains the isolated primitive setup
without automatic starter items; its older `run/rooms.py` rest/event amounts
remain caller-supplied synthetic values. Combat copies the persistent deck;
The Scythe synchronizes permanent damage growth by owned card ID into the run deck;
other permanent combat-produced deck changes need their own explicit rules.

Ordinary draws stop at the native ten-card hand limit, checked before each draw
and any needed reshuffle. Overflow stays in its current piles; a full-hand draw
consumes no shuffle RNG. The same rule applies through the legacy `CombatEnv`;
its encoder size does not configure game capacity. See the
[draw source check](evidence/hand_limit_2026_09_13.md) for scope and remaining hooks.

Private run snapshots now use `headless_run_state_v59`, including campaign configuration,
completed-act maps and paths, historical encounter/event/unknown-room queues,
map replacement provenance and owned Spoils Map quest targets,
native stream state, seed-bound initialization for all three room sets,
rarity/potion odds, shared/player relic bags,
items, card/item/shop/treasure/event allocators, depleted treasure offers, chest decisions,
persistent removal count, owned shop offers and selection, generated map metadata,
encounter/event queues and assignments with event entry conditions, optional Ancient start/selection history,
unknown-room odds/outcomes and exact claimed reward item IDs,
shop/treasure/event catalog fingerprints, event node IDs and pending event data, potion odds, active/reward encounter IDs, relic claim state, boss reward pools, an explicit
act-completion record and every pending decision. Card combat lifetimes and
independent relic evolution counters are explicit owned data. Event combat history
binds each fight to its event/node identity, combat number, outcome and reward exit.
Nested combat records now use `headless_combat_state_v40`, including the in-play
played-power and offered-card piles, nested plain-data continuations, selection/target/generation/potion/HP RNG,
optional multi-card selections and independent colorless power timers,
ordered player powers, temporary card values, per-turn/combat counters, Feed maximum-HP
gains, Stars and paid/captured Star-X values, per-target hit history, generated-card
counts, owned Osty HP, Doom/Ethereal/draw history, pending reactive event receipts,
Scythe damage and Genetic Algorithm block growth, ordered local cost setters,
owned orb identities/slots/values and orb-generation RNG, side-end listener order,
instanced Orbit/Monologue counters, earned Royalties, power duration flags, player
card-play counts, exact power applier slots, monster phase/spawn counters and
per-card enchantment trigger state, Ancient hook memory, generic monster stun and
owned autoplay batches, future card references and automatic-play continuations. Run records additionally retain stored Ancient
cards, wax state, map marks, reward rerolls and rest/shop continuations.
Permanent card records retain enchantments
with an untriggered state.
Creature context references are rebound from owned state, never serialized.
Earlier combat
v1–v24 and run v1–v36 formats are rejected rather than assigning invented item
or progression defaults. Public reduced fixture schemas are unchanged. The fixed legacy action vocabulary
and brute-force oracle do not support combat choices, Weak or the new card families.
The legacy status encoder retains its two-name vocabulary; Ironclad power stacks are inspected through `player.rules.powers`, and enemy
debuffs through `enemy.statuses`.
Snapshots bind card values/effect composition and item values automatically,
and restore RNG aliases and exact piles. Use the same game-rule implementation
when restoring: these are development continuation records, not release provenance
certificates. Unknown monster state types reject until their content family has a
serializer. Do not pickle arbitrary callables or import types named by a snapshot.
Policy consumers must never receive these private records.

The corrected Slimed definition and added upgrade levels change the automatic
card-catalog fingerprint, so older private default-catalog snapshots reject.
No historical release evidence or accepted fixture fingerprint was repinned.

No architecture guarantees that future mechanics require zero change. The stable
boundary is that game concepts can grow without driving changes in unrelated
policy, transport or artifact code.

## Validation

Run `PYTHONPATH=. python -m pytest -q tests/headless` for direct gameplay cases.
During local changes, run the affected test modules first; add `--durations=15` to
see slow cases. Run the broad suite after shared changes are stable. A profiler
can isolate repeated work without running the whole suite under instrumentation:

```bash
PYTHONPATH=. python -m cProfile -o /tmp/headless-tests.prof -m pytest -q \
  'tests/headless/test_foreign_acquisition.py::test_splash_matches_native_pool_offers_upgrades_and_rng[0False]' \
  'tests/headless/test_foreign_acquisition.py::test_every_native_offered_option_can_be_acquired_played_and_restored[0-plain]'
python -m pstats /tmp/headless-tests.prof
```

On 2026-09-19, those two cases called `CardCatalog.snapshot_fingerprint()` 90 times;
repeated catalog serialization took 4.14 of 4.82 profiled seconds (86%). Catalogs
now reuse their fingerprint only when all definition values are recursively frozen.
Mutable custom effects bypass caching, and changes to enchantment definitions
invalidate it. Cache state is owned by the catalog and excluded from its equality;
fingerprint bytes, snapshot formats and restore checks are unchanged.

The same 123 acquisition tests improved from **31.62 to 4.49 seconds (7.0×)** on
the same Python 3.11 environment, without changing tests or adding workers.
Profiled fingerprint time fell from 4.14 to 0.054 seconds, including the first
computation. All five cumulative catalog fingerprints and representative native
run/pending-Splash snapshots matched their pre-change bytes. Regression cases
cover cache reuse, changed values/effects, nested mutable effects, enchantment
changes and invalid custom effects. Remaining profile cost includes item/shop
metadata serialization; these measurements do not attribute every full-suite
second to catalog fingerprints.

The broad headless run passed **3,810 tests in 157.97 seconds (2m38s)**,
compared with the preceding 3,759-test run's 895.58 seconds (14m55s). That is
about 5.7× faster despite the additional tests; the identical 123-test comparison
above is the controlled before/after measurement. The slowest remaining individual
cases were full-route/CLI restoration tests at 1.4–2.3 seconds. Cache-specific
regressions live in
[`test_catalog_fingerprint.py`](../tests/headless/test_catalog_fingerprint.py).
Compatibility checks passed 360 tests in 79.36 seconds; a fresh wheel installation
passed 129 fingerprint/acquisition tests in 4.78 seconds and the 38-command authored
route with restoration verification. All 183 installed headless modules matched
source bytes. `compileall game tests` and diff checks passed.

The gameplay tests include an unlisted card with three levels, changed cost/damage, two combats,
JSON continuation, RNG aliasing, invalid-operation atomicity, branch isolation,
rewards, rooms, map navigation and an import-boundary check.
[`test_vertical_slice.py`](../tests/headless/test_vertical_slice.py) covers both
complete routes with JSON restore before each command, item legality, exact
persistent identities, canceled smithing, defeat and malformed snapshots.
[`test_slice_cards.py`](../tests/headless/test_slice_cards.py) and
[`test_slice_encounters.py`](../tests/headless/test_slice_encounters.py) cover the
completed reward upgrades, generated Slimed, move cycles, branch restrictions,
terminal effects and clone ownership. Existing simulation,
search and headless adapter tests cover compatibility. Broaden checks when a shared
rule or consumer actually changes; bridge builds and historical frozen-evidence
repinning are not part of ordinary card implementation.
