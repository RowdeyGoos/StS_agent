# Single-player Ironclad card pool — 2026-09-13

## Scope and content

All **85 single-player Ironclad definitions** from game **0.107.1** now execute at
base and upgraded level. The native pool has 87 entries; Demonic Shield and Tank
are omitted by the user's multiplayer exclusion. The independent
[constructor inventory](../../tests/headless/fixtures/ironclad_native_inventory.json)
records every native name, cost, kind, rarity, target and method token.

| Rarity | Definitions | Acquisition |
| --- | ---: | --- |
| Basic | 3 | Strike, Defend, Bash; starter deck, outside ordinary rewards |
| Common | 20 | Ordinary rewards, common shop slot, Ironclad transforms |
| Uncommon | 35 | Ordinary rewards, uncommon shop slot, Ironclad transforms |
| Rare | 25 | Ordinary/boss rewards, rare shop slot, Ironclad transforms |
| Ancient | 2 | Break and Corruption execute; excluded from ordinary acquisition |

The ordinary reward/transform pool is 80 cards. Native rarity weights and native
seed/draw-order reproduction are separate work; current sampling remains explicitly
project-authored. Generation filters the registered Ironclad ordinary pool, excludes
Feed and Not Yet, and uses an owned independent RNG. Basic and Ancient cards cannot
be randomly generated in combat. Primal Force's Giant Rock is implemented separately;
its event transformations use the supported colorless pool. Shockwave stays colorless.

## Rule ownership

- Immutable card values/effects and acquisition metadata live in `cards/`. Named
  operations compose damage expressions, powers, hand/discard choices and generation.
- `core/resolution.py` owns nested play frames and a plain task queue. Havoc,
  Cascade, Hellraiser, One-Two Punch and Stampede share it. A frame captures result
  pile/resources before effects; repeats execute play hooks individually and move
  the physical card once. Unplayable autoplay moves to its result pile without
  charging energy or running play hooks.
- `powers/ironclad.py` owns ordered player hooks, including ordinary/Ethereal
  exhaust, HP loss, block, vulnerability application, card play and turn phases.
  Positive powered block entries from other plays control Unmovable. Rupture's
  card-caused strength waits until the card's play completes. Lethal incoming
  damage does not trigger Flame Barrier retaliation.
- Transient card values, powers, counters, nested choices and generated IDs are
  owned serializable data. Feed explicitly carries maximum HP into the permanent
  run. Combat modifiers and temporary upgrades do not change the master deck.
- Combat snapshot **v8** and run snapshot **v18** bind the new state; older private
  schemas reject. Restore checks control suffixes, nested completion order, result
  piles and active-card ownership before installation. Search cloning includes the
  new RNG and preserves power listener order in its state key.

## Source basis

Pinned Steam build **23811903**, macOS `sts2.dll`, SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
See the [build manifest](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
Evidence is static metadata/IL inspection and headless execution, not live-game
verification. No profile, save or history data was read.

| Native member/token | Rule checked |
| --- | --- |
| IroncladCardPool.GenerateAllCards `100693955` | 87 native definitions; inventory excludes two multiplayer entries |
| CardModel play wrapper `100706385` | Per-repeat play/enchantment/after-play hooks, single final movement |
| GetResultPileTypeForCardPlay `100682237` | Power result precedes force-exhaust; destination resolved before effects |
| AutoPlay `100712167`, MoveToResultPileWithoutPlaying `100712177` | Unplayable movement; X value captures available energy without payment |
| SetupPlayerTurn `100712569` | Innate draw expands to count, capped at ten |
| FreeAttack.BeforeCardPlayed `100707374` | Consume a stack per attack play, including repeats |
| Hook.AfterTurnEnd `100711489`, IterateHookListeners `100712603` | Player power insertion order controls side-end hooks |
| NoDraw `100707500`, DarkEmbrace `100707313` / `100707315` | Draw prevention, ordinary exhaust draws and deferred Ethereal draws |
| Unmovable `100686456`, predicate `100707809` | Powered positive block history excluding the current CardPlay |
| Juggling `100685671` / `100707468`, Stomp `100693376` / `100693377` | Earlier attacks, third-attack clones, turn cost reductions |
| Aggression `100707204`, Stampede `100707695`, Hellraiser `100707426` | Discard retrieval/upgrades, post-turn random attacks, early-draw Strike autoplay |
| CardFactory `100695703` / `100695704` | Sampling with replacement, fresh cards and generation exclusions |
| Clone `100682244` | Independent mutable values and enchantments, fresh card identities |
| Feed `100709985` | Fatal eligibility before attack, actual kill outcome afterward |
| CreatureCmd.Damage `100712357` | Skip AfterDamageReceived for a killed/dead target |
| Howl `100710189`, Pact's End `100692659` | Exhaust-pile autoplay and current exhaust-count condition |
| Cinder `100709721`, Dominate `100709893`, Not Yet `100710436` | Random hand exhaust; total target Vulnerable strength; heal only |
| Drum of Battle `100709908`, Juggernaut `100707465`, Vicious `100707812` | Own-card exhaust energy, unpowered random damage, successful Vulnerable draw |

The older external C# reference was only a navigation aid. Several native values
have changed, including Break, Cinder, Conflagration, Dominate, Drum of Battle,
Fight Me, Forgotten Ritual, Juggernaut, Not Yet, Spite, Stoke and Tremble; current
implementation follows the pinned assembly rather than those older definitions.

## Validation

The new `test_ironclad_complete.py` covers all 170 base/upgrade executions, private
JSON continuation across turns, full-pool acquisition, nested choices, replay,
powers, resource costs, generation/cloning, permanent HP and malformed restore.
Existing route-policy victory fixtures explicitly retain their historical small
reward pools; separate tests cover acquisition from all 80 current reward cards.
Those historical victories are not claims about the expanded-pool demo policy.

Independent semantic review checked native hook ordering, generation and clone
ownership, fatal damage, X autoplay and adversarial restore. All reported concrete
issues were corrected and rechecked. Review is bounded to those implemented rules,
not full native differential certification or all possible item combinations.

- Broad affected suite: **1,478 passed in 107.45s**, covering direct headless,
  simulation, analysis/search, engine, headless backends, content, CLI and package
  imports. Compileall, diff and local documentation link checks passed.
- Final focused card/choice/legacy compatibility cases: **268 passed in 4.98s**, rerun after the final scoped-target compatibility fix.
  The new card file contains 214 cases, including the 170 base/upgrade matrix.
- The wheel was installed into a disposable environment. Checks ran outside the
  checkout with `PYTHONPATH` unset and verified `site-packages` imports. All **170**
  card/upgrade executions and their JSON continuations passed.
- Installed natural seed2/rest demos restored at each command: authored Act1/left
  **defeat**, 0/94 HP, 136 gold, 133 commands; generated/right **defeat**, 0/80 HP,
  109 gold, 95 commands. The simple policy is not a measure of rules completeness.
- Installed generated progression with **synthetic lethal boundaries**, separately
  from policy play: seed0/left/Ceremonial Beast, seed2/right/Vantom and seed4/left/
  The Kin each completed all **16 rooms**, with 78/72/78 checked transitions.
  These verify route/reward/content continuation, not natural victories.

Wheel SHA-256:
`2011039dde302129a795dee9983be99311afb3dbe79991c91b2a383f1e364b13`.
Build took 0.38s and installation 0.32s. Implementation and independent review
were interleaved; separate phase durations were not measured.

## Remaining boundaries

The full Ironclad card pool is implemented; a complete native Act 1 still needs
remaining relic/potion/colorless/event content, native reward/merchant distributions,
RNG parity and differential validation. Other ascensions remain explicitly rejected.
Infinite-HP debug-enemy safeguards in native Hellraiser are outside the implemented
finite-HP monster model. Public projections and the legacy fixed training/oracle
vocabulary remain restricted; this change adds game rules rather than claiming
those consumers can encode every new mechanic.
