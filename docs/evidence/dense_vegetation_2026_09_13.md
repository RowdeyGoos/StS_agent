# Dense Vegetation and owned event combat — 2026-09-13

## Implemented behavior

Dense Vegetation is the ninth definition in the restricted generated Ironclad A0
event pool. Both initial choices are implemented:

- **Trudge On:** lose 8 HP, then gain an entry-time 61–99 gold roll. The gold
  effect still occurs when the preceding damage is lethal.
- **Rest:** heal 30% maximum HP, truncated and capped, then expose a mandatory
  Fight choice. The heal cannot be repeated and the event cannot be left here.
- **Fight:** four Wrigglers start without the Phrog spawn stun. Stable slots 0/2
  start with Bite, 1/3 with Wriggle; they alternate thereafter. Victory produces
  ordinary hallway rewards, then returns to the map without resuming the event.
  Defeat terminates the run.

The encounter uses existing Wriggler rules, Infection, combat construction,
Burning Blood, potions and reward resolution. Event fights age Guilty but do not
count as elite victories for Sword of Stone. Authored routes retain their earlier
explicit event fork; the generated demo chooses Rest, then Fight.

`events/combat.py` contains plain requests and records; `run/event_combat.py`
owns the handoff. `RunState.event_combats` retains event/node identity, encounter,
combat number, outcome and reward exit separately from map encounter assignments.
An event fight increments the total combat count without consuming a hallway or
elite queue entry or adding a visited map node. Failed combat construction keeps
the healed event and RNG unchanged. Duplicate launch, missing owners and reused
event identities reject. Dense entry requires configured combat reward pools,
including directly initialized fixtures.

## Pinned native evidence

Target: game **0.107.1**, Steam build **23811903**, macOS `sts2.dll`.
SHA-256 `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The [build manifest](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)
identifies the assembly. Inspection used the retained bounded metadata/IL scanner;
no native execution or profile/save/history access was performed.

| Methods / tokens | Source conclusion |
| --- | --- |
| DenseVegetation `100689302/303` | 8 damage; gold NextInt(61,100); rest amount from HealRestSiteOption |
| DenseVegetation.IsAllowed `100689304` | Unconditional in single-player; multiplayer low-HP gate is outside this scope |
| TrudgeOn async `100709047` | Damage precedes gold, then event finishes |
| Rest async `100709045` | MimicRestSiteHeal, then a sole Fight option |
| Fight `100689308`; EventModel overload `100682527` | Empty extra rewards, resume=false; creates an ordinary combat child with parent identity |
| DenseVegetationEventEncounter `100689961–965` | Normal combat room; four named Wriggler slots; StartStunned=false |
| Wriggler `100689085`, `100689091–094` | Slot-dependent alternating Bite/Wriggle openings and cycle |
| HealRestSiteOption `100695939`; Creature `100696407/408` | Base heal is decimal 30% maximum HP; HP assignment caps and truncates positive fractions |
| RewardsSet.GenerateRewardsFor `100667241`; CombatRoom constructor `100666841` | Normal reward path, 10–20 gold, ordinary potion roll/card offer; gold proportion 1.0 |

The three other inspected candidates remain unimplemented. Byrdonis Nest requires
Byrdonis Egg's rest-site/hatch lifecycle; Sapphire Seed requires Sown enchantment;
Luminous Choir requires two-card removal plus Spore Mind and native relic-bag
acquisition. Their dependencies remain explicit in the implementation queue.

## Validation and packaging

- Final affected suite: **1,207 passed in 44.54 seconds**. Paths cover headless,
  simulation, analysis, engine, headless backends, content, lazy imports/package
  layout and the headless CLI. `compileall game tests` and diff checks passed.
- New event-combat suite: **29 tests**. Cases include capped/fractional/no-effect
  healing, lethal trudge, native Wriggler openings, victory and defeat, rewards
  collected/skipped, repeated events, next-room continuation, failed construction,
  corrupt ownership and generated encounter accounting.
- Independent semantic review closed with no blockers. It verified source
  ordering/rounding/reward semantics and the final 29 tests (1.91 seconds).
  Corrections reject missing reward configuration before entry or restore and
  prevent completed event records from reusing the next pending event's identity.
- Installed checks used `site-packages` from a disposable environment outside
  the checkout, with `PYTHONPATH` unset.
- A controlled authored fixture started with the native starter deck, 40/80 HP,
  Burning Blood and three Fire Potions. Normal legal actions completed Dense
  Rest/Fight/rewards and the next Nibbit combat in **36 commands**, ending at
  **56 HP and 28 gold**. Every command was checked against a JSON-restored clone.
  Inventory was configured for this scenario; no combat outcome was forced.
- Three installed generated routes with an explicit Dense-only event subpool
  completed all 16 rooms using synthetic combat wins: seed 0/left/Ceremonial Beast
  (78 continuation checks, no event fights), seed 2/right/Vantom (80 checks, two
  event fights), seed 4/left/The Kin (82 checks, two event fights). These establish
  progression and ownership, not policy strength.
- Natural installed authored seed-2 left/rest demo remains an Act 1 win at
  **11/94 HP, 236 gold, 124 commands**. Default generated seed-2 right/rest with
  Neow remains a defeat after reaching 16 rooms at **0/94 HP, 99 gold, 195 commands**.
  Both verified continuation throughout.

Wheel: `sts_agent-0.1.0-py3-none-any.whl`, SHA-256
`b5a5d9af440223e486adcf3407e2ce91dd4e2ad044a8160e8a45eee9e816fa60`.
The combined compile/build command took 0.48 seconds; disposable install took
0.34 seconds. Implementation and review overlapped; separate phase timings were
not measured. No game launch or bridge packaging was needed.

## Remaining limits

This is the native **non-resuming** event-combat flow. Resuming parents, event
special combat rewards, training expiry and other callers still need their own
rules and continuation checks. Reward card/potion pools remain restricted;
Python seeded RNG does not establish native algorithm or draw-order parity.

Private run snapshots are now `headless_run_state_v15`, with required event
combat history; older private run schemas reject. Combat remains v6. The default
event progression profile is `supported_events_all_unlocked_v4`. Public adapters,
projections and bridge code are unchanged.

See the [engine guide](../archive/HEADLESS_ENGINE_2026_09_22.md#dense-vegetation-and-event-combat) and
[next implementation assignments](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
