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
| [`run/state.py`](../game/headless/run/state.py), [`run/engine.py`](../game/headless/run/engine.py) | Persistent state and owned combat handoff |
| [`run/config.py`](../game/headless/run/config.py), [`run/actions.py`](../game/headless/run/actions.py), [`run/flow.py`](../game/headless/run/flow.py) | Declared character/difficulty/pools and direct run command legality/dispatch |
| [`run/deck.py`](../game/headless/run/deck.py), [`run/rewards.py`](../game/headless/run/rewards.py), [`run/rooms.py`](../game/headless/run/rooms.py) | Persistent mutations, reward resolution and room transitions |
| [`run/rest_site.py`](../game/headless/run/rest_site.py), [`run/inventory.py`](../game/headless/run/inventory.py), [`relics/`](../game/headless/relics/), [`potions/`](../game/headless/potions/) | Rest/smith decisions, owned item acquisition/removal, victory healing, permanent max-HP pickup effects and potion effects |
| [`treasure/catalog.py`](../game/headless/treasure/catalog.py), [`run/treasure.py`](../game/headless/run/treasure.py), [`run/treasure_validation.py`](../game/headless/run/treasure_validation.py) | Chest content, gold on opening, optional relic acquisition, pool depletion and private continuation |
| [`shops/catalog.py`](../game/headless/shops/catalog.py), [`run/shop.py`](../game/headless/run/shop.py), [`run/shop_validation.py`](../game/headless/run/shop_validation.py) | Authored stock, native base-price bands, purchases, permanent removal and private continuation validation |
| [`events/catalog.py`](../game/headless/events/catalog.py), [`events/jungle_maze.py`](../game/headless/events/jungle_maze.py), [`run/events.py`](../game/headless/run/events.py) | Native event definitions, content-owned choices/effects and owned event lifecycle |
| [`map/graph.py`](../game/headless/map/graph.py), [`events/safe.py`](../game/headless/events/safe.py) | Authored navigation with explicit encounter/event IDs and shared primitive effects |
| [`core/rng.py`](../game/headless/core/rng.py), [`core/snapshots.py`](../game/headless/core/snapshots.py), [`run/snapshots.py`](../game/headless/run/snapshots.py) | Owned RNG streams and private JSON continuation |
| `game/simulation/`, `game/backends/`, `game/contracts/`, actor/data/training packages | Compatibility, encoding, public-information policy and external consumption |

The enforced import rule is one-way: consumers may import `game.headless`; that
package may import only itself and the standard library. Existing symbols such as
`game.simulation.card.StrikeCard` remain importable, but re-export the canonical
game classes. There is one combat implementation, not two simulators to maintain.

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
All fifteen implemented Ironclad definitions have one upgrade. The original
eleven use the starter/hallway pools; Sword Boomerang joins the Act 1 route pool,
and three rares form the restricted boss pool. Earlier source checks: [starter-card evidence](evidence/strike_upgrade_2026_09_13.md) and
[reward-card/encounter evidence](evidence/slice_combat_content_2026_09_13.md).
Slimed costs one, draws one and exhausts; it cannot be upgraded.

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
`Deck.selection_rng`, forked without consuming deck/enemy RNG. This is deterministic
Python sampling, not the native run's `CombatCardSelection` seed sequence.

Uppercut costs 2, deals 13 damage, then applies 1 Weak and 1 Vulnerable;
its upgrade applies 2 of each without increasing damage. Shockwave costs 2,
applies 3 Weak then 3 Vulnerable to each living enemy in slot order, and exhausts;
its upgrade applies 5 of each. Both are in the eight-card restricted reward pool.
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

Game commands describe intent, not network authority. External adapters still own
public references, stale request bindings, information filtering and representation
limits. A new action family may eventually require adapter work, but that work is
not a prerequisite for implementing or testing its game rule.

Extend relics, potions, selectors and other families with verified behavior.
Keep their rules beside their content; add explicit lifecycle
operations in the core as needed. Do not put card-name switches, global mutable
registries, live-service dependencies or callback closures into saved game state.
Do not scaffold empty plugin frameworks or guess all future hooks now.

## Ordinary events

The Act 1 route visits Jungle Maze Adventure after its third combat, immediately
before treasure. `ChooseEventOption(event_instance_id, option_id)` chooses
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

`events/jungle_maze.py` owns the event rules; `run/events.py` owns lifecycle and
dispatch. The older primitive event fixture still uses `run/rooms.py`; native
content is not dispatched by its synthetic option dictionary. Native event pool
weights, eligibility/repeat tracking, multiplayer voting and the rest of the
Overgrowth event catalog remain open. See [source and validation evidence](evidence/first_event_2026_09_13.md).

## Treasure rooms

The `overgrowth-act1` route now visits `treasure` after the third combat, before
its first rest site. `OpenChest()` grants 42–52 gold once. The single relic can
then be taken using `ClaimTreasureRelic(treasure_id)` or declined with
`LeaveTreasure()`. Leaving a closed chest grants nothing. The example player
opens the chest and claims its relic; direct commands also permit skipping.

The relic is drawn on room entry from unowned Strawberry/Pear/Mango. A drawn
relic leaves the restricted treasure pool even if the chest or relic is skipped.
The exhausted pool offers Circlet, which has no pickup effect and permits multiple
separately owned instances. Ordinary relic definitions still reject duplicates.
Gold uses the owned `treasure.gold` stream on opening; the relic uses
`treasure.relic` on entry. Neither inspection nor restore rerolls or grants rewards.

This is authored uniform sampling and a treasure-specific depleted pool. Native
rarity weights, shared/player bags across reward sources, tutorial overrides,
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
All currently implemented cards are removable; native Eternal cards will need
eligibility support when introduced. `LeaveShop()` returns to the map. While
selecting a removal, only removal/cancel commands are legal.

Stock is explicitly authored: one common card (Sword Boomerang, Pommel Strike or
Shrug It Off), one uncommon (Uppercut or Shockwave), one rare (Impervious, Offering
or Fiend Fire), one unowned Strawberry/Pear/Mango, and Fire and Block Potions.
An exhausted fruit pool omits that slot. One card is on sale at half its rounded
price. Native base prices are 50/75/150 for these card rarities, 175/225/275 for
the three fruits and 50 for either potion. Cards and potions vary by ±5%; relics
by ±15%. Sampling uses owned `shop.stock` and `shop.prices` streams, with discrete
basis-point variation; this is not native pool composition, rarity weighting,
float precision or RNG parity. Shops with discounts, restock relics, colorless
cards and pickup selectors remain open. See [source and validation evidence](evidence/first_shop_2026_09_13.md).

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

Hallway rewards contain 10–20 gold; Byrdonis rewards contain 35–45 gold and one
relic. Both have three distinct offers sampled from Pommel Strike,
Shrug It Off, Iron Wave, Body Slam, Armaments, True Grit, Uppercut and Shockwave, and a possible Fire or Block Potion.
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
relic-pool exhaustion rule. Native rarity weighting, upgraded card offers and
full elite reward pools remain open. See the
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
still demonstrates a boss defeat. With `--path left --rest-choice rest`, the
installed seed-2 demo now wins this authored Act 1 at 11/94 HP in 124 commands,
including event, treasure and shop decisions with exact restore. See the
[event acceptance](evidence/first_event_2026_09_13.md). This five-fight route omits
most of a native Act 1 map and its deck-building opportunities. See the
[boss source and acceptance evidence](evidence/first_boss_2026_09_13.md).

At a rest site, `Rest` heals floor(30% of maximum HP), capped at maximum HP.
`Smith` opens a plain-data, cancelable selection of implemented upgrades.
`ChooseUpgrade(instance_id)` commits one exact card; `ChooseUpgrade(None)` returns
to the rest options without spending the action. Only one rest/smith action can
be completed. All fifteen current Ironclad cards can be upgraded once. Pommel
Strike+ deals 10 and draws 2; Shrug It Off+ gives 11 block and draws 1; Iron Wave+
gives 7 block then deals 7; Body Slam+ costs zero and still scales with current
block. Unsupported cards and further upgrade levels remain excluded explicitly.
Fire Potion deals 20 damage through enemy block without attack modifiers; Block
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
draw-prevention/after-draw hooks, other card-zone mechanics, remaining items,
complex selections, full merchant pools/modifiers, procedural maps,
all content and complete target-game progression remain in the
[implementation backlog](HEADLESS_FULL_GAME_IMPLEMENTATION.md). `RunEngine`
orchestrates the restricted slice, not a complete native run. Other ascensions
reject explicitly. Generic `RunEngine()` retains the isolated primitive setup
without automatic starter items; its older `run/rooms.py` rest/event amounts
remain caller-supplied synthetic values. Combat copies the persistent deck;
permanent combat-produced deck changes need their own explicit rules.

Ordinary draws stop at the native ten-card hand limit, checked before each draw
and any needed reshuffle. Overflow stays in its current piles; a full-hand draw
consumes no shuffle RNG. The same rule applies through the legacy `CombatEnv`;
its encoder size does not configure game capacity. See the
[draw source check](evidence/hand_limit_2026_09_13.md) for scope and remaining hooks.

Private run snapshots now use `headless_run_state_v7`, including configuration,
items, card/item/shop/treasure/event allocators, depleted treasure offers, chest decisions,
persistent removal count, owned shop offers and selection,
shop/treasure/event catalog fingerprints, event node IDs and pending event data, potion odds, active/reward encounter IDs, relic claim state, boss reward pools, an explicit
act-completion record and every pending decision.
Nested combat records now use `headless_combat_state_v4`, including the in-play
pile, pending continuation, selection/target RNG and power duration flags. Earlier combat
v1/v2/v3 and run v1/v2/v3/v4/v5/v6 formats are rejected rather than assigning invented item
or progression defaults. Public reduced fixture schemas are unchanged. The fixed legacy action vocabulary
and brute-force oracle do not support combat choices, Weak or the new card families.
The legacy status encoder retains its two-name vocabulary; new powers are exposed
as active status entries by direct game inspection.
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
