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

## Native randomness and generation

Generated `RunEngine.ironclad_act1()` runs default to `rng_profile="native"`.
`RunEngine()` and `ironclad_slice()` retain the original Python fixture generator;
`ironclad_act1(rng_profile="fixture")` explicitly selects that compatibility profile.
Native runs accept integer or text seeds programmatically: integer `2` is hashed
as text `"2"`, while `"002"` is a different seed. The CLI currently accepts integers.
Changing profiles changes seeded trajectories. Old private snapshots reject rather
than being silently reinterpreted: current schemas are **combat v24 / run v36**.

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
The native fixture uses synthetic choices and manually drives native actions;
whole Horn/card-selection composition remains unverified. Native
enemy-side work runs concurrently with the action queue; its exact scheduling,
multiplayer queues and the complete hook-order audit remain separate work.

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
Hive/Glory initialization does not enable their gameplay. The declared act sequence
is **Overgrowth → Hive → Glory**, solo, A0, all unlocked/all seen; the native lobby
act picker and profile-dependent first-run overrides are outside this profile.

Native event progression uses `native_act1_events_all_unlocked_v1`: all **31**
queued IDs are shuffled before eligibility, including nine later-act events and
one disabled event. Only the 21 supported Act-1-eligible events can normally enter
rooms. Their exclusions are explicit metadata, not inferred from missing handlers.
An exhausted queue that falls back to unsupported content fails without committing
an event or advancing its cursor. Fixture progression retains its original profile.

The native map uses second-entrance rejection draws, column-first stable sorting,
insertion-ordered pruning and deterministic centering/spreading/straightening.
Thirteen direct assembly reference seeds match complete room queues, startup RNG
counters/suffixes and every Act 1 map coordinate, edge, type and entrance.
See [native initialization evidence](evidence/native_initialization_2026_09_14.md).

Runtime acquisition checks execute all 161 relic predicates against the pinned
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
potions have executable rules even where their granting event is not implemented;
Foul's combat and ordinary merchant uses are supported, while Fake Merchant awaits
that event's implementation.

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

The pinned solo Ironclad/Overgrowth Act 1 acquisition inventory contains **161
relic definitions**: 118 shared, 8 Ironclad, 27 Neow, 7 event/evolution definitions
and Circlet. All **161 are supported by the default card catalog**. Kaleidoscope
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
Foreign-character pools remain unavailable in the default catalog.

See the [scope inventory](../tests/fixtures/headless_relic_scope.json),
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
Later-act event gameplay and unlock epochs remain open. Native initialization
uses pinned pool order; authored profiles retain their declared pool restrictions. Juzu Bracelet and Winged Boots now modify unknown/travel behavior; tutorial overrides and native RNG
parity remain unsupported. Generated runs opt in to
`RunConfig.relic_fallback="circlet"`, preventing exhausted relic rewards
from blocking a later elite; authored routes retain their existing rejection rule.
Each claimed reward records its exact item instance, including repeated Circlets.

Every path has 16 room visits before Act 1 completion if survived. This is a
full-length **restricted-content** route, not yet complete native Act 1 fidelity.
[Source anchors, checks and remaining work](evidence/map_pruning_unknowns_2026_09_13.md).

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
Spoils Map is carried as its native quest card; its Act 2 route/gold quest is outside
this Act 1 implementation. Later-act shared events and disabled events are excluded.
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
unlock filters, additional conditional eligibility, multiplayer voting and the rest of the
later-act event catalog remain open; the generated route now has owned
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
distribution. Curse transformations use all 18 native definitions and reject Eternal source cards. Native RNG parity remains open. Empty-deck Slippery Bridge fallback is explicitly unsupported.

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
There is no map shortcut to this outcome, no Act 2 launch or inter-act healing,
and no claim of full-game victory. The example player is deliberately simple;
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

Private run snapshots now use `headless_run_state_v36`, including configuration,
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
Nested combat records now use `headless_combat_state_v24`, including the in-play
played-power and offered-card piles, nested plain-data continuations, selection/target/generation/potion/HP RNG,
optional multi-card selections and independent colorless power timers,
ordered player powers, temporary card values, per-turn/combat counters, Feed maximum-HP
gains, Stars and paid/captured Star-X values, per-target hit history, generated-card
counts, owned Osty HP, Doom/Ethereal/draw history, pending reactive event receipts,
Scythe damage and Genetic Algorithm block growth, ordered local cost setters,
owned orb identities/slots/values and orb-generation RNG, side-end listener order,
instanced Orbit/Monologue counters, earned Royalties, power duration flags, player
card-play counts, exact power applier slots, monster phase/spawn counters and
per-card enchantment trigger state. Permanent card records retain enchantments
with an untriggered state.
Creature context references are rebound from owned state, never serialized.
Earlier combat
v1–v22 and run v1–v34 formats are rejected rather than assigning invented item
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
They include an unlisted card with three levels, changed cost/damage, two combats,
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
