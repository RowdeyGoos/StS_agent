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
| [`run/rest_site.py`](../game/headless/run/rest_site.py), [`run/inventory.py`](../game/headless/run/inventory.py), [`relics/`](../game/headless/relics/), [`potions/`](../game/headless/potions/) | Rest/smith decisions, owned item acquisition/removal, victory healing and potion effects |
| [`map/graph.py`](../game/headless/map/graph.py), [`events/safe.py`](../game/headless/events/safe.py) | Authored map navigation and the existing primitive event effects |
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
All seven playable Ironclad definitions in the current pool have one implemented
upgrade: [starter-card evidence](evidence/strike_upgrade_2026_09_13.md) and
[reward-card/encounter evidence](evidence/slice_combat_content_2026_09_13.md).
Slimed costs one, draws one and exhausts; it cannot be upgraded.

Game commands describe intent, not network authority. External adapters still own
public references, stale request bindings, information filtering and representation
limits. A new action family may eventually require adapter work, but that work is
not a prerequisite for implementing or testing its game rule.

Extend relics, potions, selectors and other families with verified behavior.
Keep their rules beside their content; add explicit lifecycle
operations in the core as needed. Do not put card-name switches, global mutable
registries, live-service dependencies or callback closures into saved game state.
Do not scaffold empty plugin frameworks or guess all future hooks now.

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

Rewards contain 10–20 gold, three distinct offers sampled from Pommel Strike,
Shrug It Off, Iron Wave and Body Slam, and a possible Fire or Block Potion.
Potion drop chance starts at 40%, changing by ten percentage points down after a
drop or up after a miss. The integer odds and named Python streams are
project-authored sampling; they do not reproduce native RNG or full pool/rarity
generation. Rewards can be claimed independently or forfeited by leaving.
A full potion inventory requires discarding an owned potion before claiming
another; slots never shift and discarded IDs are never reused.

At a rest site, `Rest` heals floor(30% of maximum HP), capped at maximum HP.
`Smith` opens a plain-data, cancelable selection of implemented upgrades.
`ChooseUpgrade(instance_id)` commits one exact card; `ChooseUpgrade(None)` returns
to the rest options without spending the action. Only one rest/smith action can
be completed. All seven current Ironclad cards can be upgraded once. Pommel
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
complex selections, shops, procedural maps,
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

Private run snapshots now use `headless_run_state_v2`, including configuration,
items, allocator, potion odds, encounter references and every pending decision.
The earlier private v1 format is rejected rather than assigning invented item
or progression defaults. Public reduced fixture schemas are unchanged.
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
