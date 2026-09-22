# Complete A0 Overgrowth encounter roster — 2026-09-13

All 22 entries in the pinned native Overgrowth encounter census are implemented:
16 weak/normal encounters, three elites and three bosses, using 29 native monster
types including summons. This closes A0 Overgrowth combat-content coverage; it
does not close native map generation, full Ironclad content or native RNG parity.

## Source and scope

Static metadata and bounded IL inspection used the pinned v0.107.1 / Steam build
23811903 macOS assembly, SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The input was `/private/tmp/sts-current-release-final/references/sts2.dll`.
No game assembly was executed and no live game, profile, save or history was used.
Native metadata tokens below identify methods in that exact assembly. Extracted
scratch records are in `/private/tmp/sts-headless-overgrowth-native/`; they are
local working material, not a portable evidence dependency.

The census is `Overgrowth.GenerateAllEncounters` (100694198); boss discovery order
is 100694200. The maintained mapping is
[the encounter catalog](../../game/headless/encounters/catalog.py).
Higher ascensions remain rejected. Selection uses owned seeded Python RNG;
native bit-for-bit RNG and discovery-dependent eligibility are not claimed.

## Encounter coverage

IDs below are prefixed with `overgrowth_`. Small/medium describe slime sizes.

| Native encounter | Headless ID suffix | Composition |
| --- | --- | --- |
| NibbitsWeak | nibbit | One Nibbit |
| SlimesWeak | slimes | One small Leaf and Twig, with a random medium between them |
| FuzzyWurmCrawlerWeak | fuzzy | One Fuzzy Wurm Crawler |
| ShrinkerBeetleWeak | shrinker | One Shrinker Beetle |
| OvergrowthCrawlers | crawlers | Shrinker Beetle and Fuzzy Wurm Crawler |
| CubexConstructNormal | cubex | Cubex Construct |
| FlyconidNormal | flyconid | Random medium slime and Flyconid |
| FogmogNormal | fogmog | Fogmog; summons Eye with Teeth |
| InkletsNormal | inklets | Three Inklets; middle opens with Whirlwind |
| MawlerNormal | mawler | Mawler |
| NibbitsNormal | nibbits | Two Nibbits with distinct opening roles |
| RubyRaidersNormal | ruby_raiders | Three distinct choices from Axe, Assassin, Brute, Crossbow and Tracker |
| SlimesNormal | slimes_normal | Medium Twig, medium Leaf, then one small of each in random order |
| SlitheringStranglerNormal | strangler | Jaxfruit, random medium slime or two independently chosen small slimes, followed by Strangler |
| SnappingJaxfruitNormal | jaxfruit | Snapping Jaxfruit and Flyconid |
| VineShamblerNormal | vine_shambler | Vine Shambler |
| BygoneEffigyElite | bygone_effigy | Bygone Effigy |
| ByrdonisElite | byrdonis | Byrdonis |
| PhrogParasiteElite | phrog_parasite | Phrog Parasite; four Wrigglers on death |
| CeremonialBeastBoss | ceremonial_beast | Ceremonial Beast |
| TheKinBoss | the_kin | Dance-opening Follower, Slash-opening Follower and Kin Priest |
| VantomBoss | vantom | Vantom |

Encounter generation tokens: Bygone 100689909, Byrdonis 100689913, Ceremonial
100689922, Cubex 100689946, Flyconid 100690017, Fogmog 100690024, Fuzzy 100690038,
Inklets 100690069, Mawler 100690125, normal Nibbits 100690149, weak Nibbit
100690155, Crawlers 100690160, Phrog 100690188, Ruby 100690211, Shrinker
100690244, normal Slimes 100690259, weak Slimes 100690265, Strangler 100690270,
Jaxfruit 100690289, Kin 100690343, Vantom 100690398 and Vine 100690403.
Ruby's static count initialization (100690213) permits each raider once.

## Rules added and source-sensitive details

- Monster rules live in small content modules under
  [monsters](../../game/headless/monsters/). Fixed move cycles share `ScriptedEnemy`;
  random transitions and special phases retain explicit owned state. Existing
  Nibbit, slime, Fuzzy, Mawler, Byrdonis and Vantom rules remain in use.
- Bygone Effigy has 127 HP, opens with Sleep, gains 10 Strength on Wake and then
  repeats a base-13 Slash. Slow increases incoming attack damage by 10% per fully
  resolved player card and resets at the enemy turn. Move graph 100687296;
  Slow hooks 100686158, 100686159 and 100686161.
- Ceremonial Beast has 252 HP. Stamp applies Plow 150; its Plow attack deals 18
  and gains two Strength. Positive unblocked damage leaving it at or below 150 HP
  interrupts that phase, clears Strength and stuns it. It then cycles Beast Cry
  (Ringing), Stomp 15 and Crush 17 plus three Strength. Move graph 100687363;
  threshold hook 100707548. Restores reject inconsistent Plow/phase state.
- Phrog Parasite has 61–64 HP and alternates three Infection cards with four hits
  of four. Its death immediately adds four 17–21 HP Wrigglers before another hit
  or combat completion. The children are primary enemies with an initial stun
  and alternating opening roles. Move graphs 100688279 and 100689085; death hook
  100707454 and combat-ending guard 100685636. Owned parent/child slots prevent
  duplicate or missing death spawns during continuation.
- Fogmog has 74 HP and summons a six-HP Eye with Teeth. The Eye generates three
  Dazed cards, becomes untargetable on death, clears its debuffs and revives at its
  next turn. Its stable slot is retained. Killing Fogmog ends the encounter and
  cleans up the minion. Move graph 100687690 and Illusion death hook 100685610.
- The Kin uses two 58–59 HP Followers and a 190 HP Priest. Followers cycle Slash
  5, Boomerang 2×2 and Strength 2. The Priest cycles Frailty Orb 8/Frail,
  Weakness Orb 8/Weak, Beam 3×3 and Strength 2. Priest death ends combat even with
  Followers alive; follower-death reactions are cosmetic in this build. Move
  graphs 100687883 and 100687904; reaction 100687910.
- Flyconid's branch integers 3 and 2 are cooldowns, not selection weights.
  Eligible moves have equal weight. When all moves are excluded, the native
  zero-weight selector still consumes RNG and selects its first branch. Relevant
  methods: move graph 100687680, branch construction 100681564, weight 100681568,
  selection 100681567 and RNG 100667301/100667302. Tests cover that fallback.
- New shared powers include Artifact, Frail, Constrict, Tangled and Ringing.
  Frail affects powered card block, while Block Potion remains unaffected.
  Constrict and Shrink retain their applier's stable slot and clear on its death.
  Tangled increases Attack costs until turn end; Ringing limits plays to the
  first card of the turn. Hooks: Frail 100685466, Constrict 100707271/100707269,
  Tangled 100686326/100707753/100707755/100707757, Ringing 100686010/100707608.
- Dazed is unplayable and Ethereal; Infection is unplayable and deals three
  blockable, unpowered damage per copy at end of hand. Dazed 100691389/100691391;
  Infection 100692204/100692207/100710221. Lethal hand damage stops the turn.
- Shrink's 0.7 factor now combines with other attack multipliers before the final
  floor, correcting the old double-floor behavior. Native multiplier 100686104.
  The existing Shrink/Vulnerable regression expectation was updated accordingly.
- Each individual hit settles deaths, summons and primary-enemy completion before
  continuing damage or draw effects. Enemy-turn participants are captured before
  execution, matching native `ExecuteEnemyTurn` 100712561, offsets 175–197;
  enemies summoned during that turn cannot act immediately.

## Continuation and playable entry points

Private combat snapshots are **v5**, and private run snapshots are **v9**. Older
private versions reject explicitly; public fixture protocols are unchanged.
New state includes the turn's card count, source-owned powers, random-move
cooldowns, phase state and summon ownership. Pending decisions remain plain data.
Combat context references are rebound on restore and clone, never serialized as
another player. Legacy search cloning/state keys were adjusted for those owned
references; no combat projection, observation encoder or training feature was added.

`RunEngine.ironclad_slice(route="overgrowth-act1", boss=..., elite=..., hallway=...)`
and `sts-headless-play --boss ... --elite ... --hallway ...` allow the catalog's
encounters in existing authored route positions. Hallway changes the left
branch's fourth fight; elite changes the right branch's fourth fight; boss changes
the final fight. Room kinds are validated. All 22 encounters can also be selected
directly through `CombatEngine` and `ENCOUNTERS`.

## Validation

- Focused encounter/lifecycle and search regressions: **97 passed in 1.27 s**.
  The new encounter file contains 90 tests, including every encounter's turn
  continuation, victory/reward handoff and defeat, composition variants, damage
  packets, death/revival ordering and malformed snapshots.
- Final affected integration command:

  ```sh
  PYTHONPATH=. python -m pytest -q tests/headless tests/simulation tests/analysis tests/engine tests/backends/headless tests/content tests/test_lazy_public_api.py tests/test_package_layout.py tests/cli/test_headless.py
  ```

  **975 passed in 21.86 s**, using the existing Python 3.11 environment.
  `python -m compileall -q game tests` and `git diff --check` passed.
- Independent semantic review closed with no remaining blockers. It also checked
  40 special encounters across 1,438 exact continuation decisions. Findings about
  context cloning, death cleanup, premature completion and malformed summon or
  revival phases were corrected and covered before the final checks.
- Built `sts_agent-0.1.0-py3-none-any.whl` with no dependencies, build isolation or
  index access, then force-reinstalled it in the disposable installed environment.
  Wheel SHA-256: `4462480a4302882e7699a5ff93ae79c1ea2fa183531cff3521cc41b054513479`.
  Build took 0.55 s; installation took 0.35 s.
- Outside the checkout with `PYTHONPATH` unset, all **22 installed encounters**
  completed 12 synthetic endurance turns each: **264 exact JSON-restored turns**.
  Import origin was the installed environment's `site-packages/game/__init__.py`.
  This fixture uses 10,000 HP and no cards; victory fixtures likewise force damage.
  Neither is evidence of policy strength or natural run wins.

Installed CLI runs used seed 2 and `--verify-restore` at every command:

| Authored route/configuration | Outcome | Final HP | Gold | Commands |
| --- | --- | --- | --- | --- |
| First slice, smith | Slice complete | 66/80 | 127 | 38 |
| Act 1, left, rest, defaults | Act complete: Vantom | 11/94 | 236 | 124 |
| Act 1, right, rest, defaults | Act complete: Vantom | 12/104 | 332 | 118 |
| Act 1, right, rest, Phrog / Ceremonial Beast | Defeat | 0/104 | 232 | 127 |
| Act 1, left, rest, Fogmog / The Kin | Defeat | 0/94 | 136 | 115 |
| Act 1, right, rest, Bygone Effigy / Vantom | Defeat | 0/104 | 232 | 111 |

All six installed runs terminated without continuation mismatches. These are
deterministic example-policy results, not win-rate estimates. Source inspection,
implementation and independent review did not have separately recorded start/end
timers; no phase durations are inferred. Installed checks were complete by
15:58:55 UTC on 2026-09-13.

## Remaining Act 1 work

The next bounded assignment is native map topology and run-owned encounter
progression (HF-29/30), including weak/normal pools, exclusions, boss selection and
discovery settings. Current authored routes remain five-fight fixtures.
Complete Ironclad cards, relics, potions, rewards, shops and event branches still
need their respective coverage tasks. Native RNG parity and higher ascensions are
separate milestones. See the current
[implementation assignments](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment)
and [engine guide](../HEADLESS_ENGINE.md) for the maintained task boundaries.
