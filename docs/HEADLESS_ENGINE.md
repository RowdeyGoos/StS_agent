# Headless game engine

This guide owns current gameplay scope, API usage and code ownership. The
[implementation backlog](HEADLESS_FULL_GAME_IMPLEMENTATION.md) owns remaining
assignments. Dated implementation notes and their original limits are preserved in
[the September 22 archive](archive/HEADLESS_ENGINE_2026_09_22.md).

## Current completion scope

The independent `game/headless` engine supports all five solo characters at
**A0–A10**, with all content unlocked, through **Overgrowth or Underdocks → Hive
→ Glory → Architect** on pinned game **0.107.1**. The
[game-build manifest](../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)
owns the exact target identity.

Cards, powers, monsters, relics, potions, rewards, generation, shops, rests, events
and Ancient choices execute through shared rules. The implemented solo roster
includes 58 regular events and eight Ancients. Multiplayer-only content,
alternate modes and progression-dependent unlock histories are excluded.

Implemented rules and selected native comparisons do not imply exhaustive native
equivalence. The CLI has a demonstration policy; it is not a trained agent or a
normal-HP victory guarantee. Full-game public observations and policy/data adapters
remain open in HF-44–47.

## Use and extend the game directly

Install and run the CLI using the [README](../README.md#playing-and-implementing-the-game).
For programmatic play, select a legal command and apply it through `RunEngine`:

```python
import json
from game.headless.run.ancient import PROFILE as NEOW_PROFILE
from game.headless.run.engine import RunEngine

run = RunEngine.campaign(
    character="defect", seed=2, ascension=10,
    first_act="underdocks", ancient_profile=NEOW_PROFILE,
)
actions = run.legal_actions()
run.apply(actions[0])

private_state = json.loads(json.dumps(run.snapshot()))
restored = RunEngine()
restored.restore(private_state)
assert restored.legal_actions() == run.legal_actions()
```

`legal_actions()` returns game-owned command values, including nested card/item
choices. Use `run.apply()` throughout a campaign so combat completion, rewards,
room continuation and persistent inventory changes remain owned by the run.
After a boss, apply an offered `ContinueAct()` command; after Glory, resolve the
Architect's offered ending choice to obtain full-game victory.

| Entry point | Intended use |
| --- | --- |
| `RunEngine.campaign(character=..., first_act=..., ascension=...)` | Generated campaign through Glory and the Architect; `last_act="hive"` stops after Act 2 |
| `RunEngine.act1(character=..., act=..., ascension=...)` | Generated single-act run |
| `RunEngine.ironclad_run(...)`, `ironclad_act1(...)` | Ironclad-specific factory conveniences |
| `RunEngine.ironclad_slice(route=..., seed=...)` | Restricted authored Ironclad scenarios for focused rule tests |
| `RunEngine(...)` | Explicit isolated/custom setup; no generated campaign or automatic starter relic |
| `CombatEngine(...)` | Isolated combat rules without run progression |

Generated factories default to native RNG. Pass `ancient_profile=NEOW_PROFILE`
(or CLI `--ancient neow`) to include the opening Neow choice; the default starts
without that choice. Later campaign Ancients use ordinary progression.
Authored routes and bare `RunEngine()` default to the fixture RNG profile.
`slice_complete` and a single-act endpoint are not full-game victory.

For an isolated encounter, use `RunEngine.start_combat(encounter_id=...)` with an
ID from the [encounter catalog](../game/headless/encounters/catalog.py), or supply
an explicit fixture factory. In manual isolated setups, call `finish_combat()`
after the owned combat finishes. Generated campaigns handle that handoff through
`run.apply()`.

## Playable characters

The [character catalog](../game/headless/characters.py) owns starting HP, decks,
relics, orb capacity and exclusive pools. Select `ironclad`, `silent`, `regent`,
`necrobinder` or `defect` in generated factories or with CLI `--character`.
Authored slices are Ironclad scenarios.

Rewards, shops, transformations, event rewards, Neow and character-dependent
Ancient gifts use the selected owner. Shared rules handle Stars/Forge, Osty,
orbs, powers and resumable choices. Ordinary acquisition excludes basic and
Ancient-only cards; Shockwave belongs to the colorless pool.

The [startup/content evidence](evidence/playable_characters_2026_09_20.md),
[native character campaigns](evidence/native_character_campaigns_2026_09_21.md)
and [focused interaction audit](evidence/native_character_interactions_2026_09_21.md)
describe distinct checks. The campaign evidence covers the four added characters
at A0 and A10 through native victories with boosted HP and Python JSON replay.
It is not limited to Python-only campaign wins, nor does it cover every deck/seed.

## Ascension levels

Ascension is an integer from 0 through 10, defaulting to 0. Rules are cumulative
and owned by the run/combat, never a global setting. The
[difficulty rules](../game/headless/core/ascension.py), monster values and move
modules are the implementation authority.

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

Summons inherit their owner's level; higher-level standalone encounters must use
factories that propagate construction inputs. Restore validates consistent
run/combat/monster levels. Historical profile identifiers containing `a0` do not
override the separately owned ascension setting.

See [ascension evidence](evidence/headless_ascensions_2026_09_20.md) and
[character campaign comparisons](evidence/native_character_campaigns_2026_09_21.md)
for getter/map checks and selected A10 double-boss trajectories.

## Ownership

Game rules import only `game.headless` and the standard library. Consumers import
the engine; adding content must not require a projection or encoder registration.

| Location under `game/headless/` | Responsibility |
| --- | --- |
| [`cards/`](../game/headless/cards/) | Immutable definitions, upgrade values, ordered effects and explicit catalogs; instances own mutable state |
| [`characters.py`](../game/headless/characters.py) | Character starts and exclusive acquisition pools |
| [`core/combat.py`](../game/headless/core/combat.py), [`core/actions.py`](../game/headless/core/actions.py) | Combat commands, legality, turn execution and stable enemy slots |
| [`core/`](../game/headless/core/) | Player/deck state, piles, owned identities, resolution tasks, pending selections and private snapshots |
| [`monsters/`](../game/headless/monsters/), [`encounters/`](../game/headless/encounters/) | Monster behavior and separate seeded encounter composition |
| [`powers/`](../game/headless/powers/) | Shared and character-specific power lifecycles |
| [`run/engine.py`](../game/headless/run/engine.py), [`run/flow.py`](../game/headless/run/flow.py), [`run/actions.py`](../game/headless/run/actions.py) | Persistent ownership, command dispatch and combat/room/act handoffs |
| [`run/`](../game/headless/run/) | Inventories, rewards, shop/rest/event continuations and run snapshots |
| [`events/`](../game/headless/events/), [`relics/`](../game/headless/relics/), [`potions/`](../game/headless/potions/) | Content-owned rules, shared hooks and pending choices |
| [`map/`](../game/headless/map/), [`generation/`](../game/headless/generation/), [`shops/`](../game/headless/shops/), [`treasure/`](../game/headless/treasure/) | Map/room generation, content pools, native probability rules and room definitions |

For a new card using existing operations, define its values/effects in one
`CardDefinition` and add it to the relevant catalog. Use instance IDs for commands;
display names do not determine behavior. Definitions may have multiple upgrade
levels. New mechanics belong in a content module or a shared rule module when
multiple callers need them. Pending work stores plain data, not callback closures.

The CLI is [`game/cli/headless_play.py`](../game/cli/headless_play.py).
The retained [`r0i_wire.py`](../game/backends/live/r0i_wire.py) is a bridge fixture
codec, not the planned full-game public observation contract. Legacy `CombatEnv`,
reduced backends, training/search pipelines and compatibility constructors were
[retired](archive/README.md#retired-simulator-pipelines).

## Native randomness and generation

Generated runs use the pinned MegaRandom algorithm (xoshiro256**, SplitMix64
initialization), native seed hashing and owned stream domains. See
[`native_rng.py`](../game/headless/core/native_rng.py) and
[`native_service.py`](../game/headless/core/native_service.py). Native factories
accept integer or text seeds: integer `2` is interpreted as text `"2"`, while
`"002"` is distinct. The CLI accepts integer seeds.

Aliased native callers share the same stream, including reward consumers.
Composition, creature HP and monster AI have their own native ownership rules;
event streams use model-ID salts. Random-orb generation retains the logical
`combat_orb_generation` key while using native salt `combat_orbs`. Restore
reestablishes stream aliases and counters. Policy RNG stays outside game state.

The explicit fixture profile is useful for authored scenarios and isolated tests;
it does not claim native seeded parity. New fidelity work should begin with a
specific caller or differing sequence, not an unbounded new seed matrix.

## Private continuation

Current schemas are **`headless_combat_state_v47`** and
**`headless_run_state_v68`**, defined in the
[combat serializer](../game/headless/core/snapshots.py) and
[run serializer](../game/headless/run/snapshots.py). Snapshots are JSON-compatible
private continuation records, not public observations or native on-disk saves.

They retain RNG state/aliases, stable identities, ordered piles, modifiers, owned
pending tasks/selections, character resources and run/room history. Restore binds
content fingerprints, validates ownership and rejects incompatible versions;
it does not infer missing state. Reuse the same rules/catalogs when restoring.
Mutable branch state is independent, while immutable definitions may be shared.
Do not serialize arbitrary callables or import a type named by a snapshot.

These records are not release-provenance certificates. Actor inputs must exclude
private RNG, hidden draw order and privileged continuation data. HF-44 owns the
future public view.

## Consolidated native verification

Use evidence for its declared profile, inputs and compared boundaries:

| Evidence | What it establishes |
| --- | --- |
| [Generated campaign comparisons](evidence/headless_generated_route_2026_09_20.md) | Selected Ironclad routes and regional bosses |
| [Ascension comparisons](evidence/headless_ascensions_2026_09_20.md) | Cumulative difficulty checks and selected A10 campaigns |
| [Character campaigns](evidence/native_character_campaigns_2026_09_21.md) | Eight additional-character A0/A10 native victories and JSON replay |
| [Event branch matrix](evidence/native_event_branches_2026_09_20.md) | 9,376 native branch-prefix cases across 65 families, with separate Architect coverage |
| [Item/status comparisons](evidence/native_item_status_2026_09_20.md), [focused monster behavior](evidence/native_focused_behavior_2026_09_20.md) | Declared relic, potion, power and monster interactions |
| [Character interaction audit](evidence/native_character_interactions_2026_09_21.md) | Focused character/item mechanisms, orb passive rules and RNG salt correction |

Boosted native campaigns are accepted simulator evidence. Their ordinary game
rules still run, but low-HP thresholds, death and revival need focused boundary
checks. A normal-HP victory by the demonstration policy is not a simulator gate.
Native TestMode captures are distinct from live desktop play and native disk-save
restoration. No finite campaign set proves every possible inventory or action order.
The [backlog](HEADLESS_FULL_GAME_IMPLEMENTATION.md) owns remaining fidelity and
consumer tasks; historical “remaining” labels are not a current task queue.

## Validation

Follow [AGENTS.md](../AGENTS.md#review-and-validation). Run affected test modules
first; broaden once stable when shared behavior or consumers changed. For example:

```bash
PYTHONPATH=. python -m pytest -q tests/headless/test_game_engine.py
PYTHONPATH=. python -m pytest -q tests/headless/test_native_character_interactions.py
```

Full campaigns and event matrices deliberately replay many commands and JSON
continuations. They are materially slower than focused rule tests. Use
`--durations=10` to identify slow cases; the
[test-overhead study](evidence/headless_test_overhead_2026_09_20.md) records prior
controlled measurements, not a permanent runtime promise.
Documentation-only changes need diff, link and factual checks, not gameplay tests.
Native capture work uses the existing [reference harness](../tools/native_combat_oracle/README.md)
and its isolation rules; do not recapture unchanged evidence just to refresh dates.

## Why this structure

The reference analysis adopted content modules, owned combat/run state and
external consumers. It did not copy the reference's global instance counter,
callback-bearing pending choices or large engine modules. Owned IDs, plain
continuations, explicit catalogs and smaller rule modules keep dependencies local.
The [original analysis](archive/HEADLESS_ENGINE_2026_09_22.md#why-this-structure)
preserves the pinned reference links and rationale.

Future mechanics can require changes. The architectural goal is to extend game
concepts without forcing changes into unrelated policy, transport or artifact code.
