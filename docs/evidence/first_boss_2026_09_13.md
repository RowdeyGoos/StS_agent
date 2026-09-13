# First Overgrowth boss and act completion, 2026-09-13

Vantom, Slippery, Wounds, Sword Boomerang, three rare cards and a boss reward/act-completion boundary
are implemented in the independent game package. The authored `overgrowth-act1`
route has five fights and two rest sites. It remains a restricted progression
example; it omits native Act 1 generation and most deck-building opportunities.

## Native source identity

Target v0.107.1, Steam build 23811903; assembly SHA-256:
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
[Build manifest](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
Implementation base: `dd22de1` on `codex/headless-integration`.

Used the bounded static metadata scanner from the
[starter-card source check](strike_upgrade_2026_09_13.md) under .NET 9.0.303.
Its hash/symlink/size/instruction guards were retained; output additionally reports
constant metadata fields to disambiguate native enums. No native models were
instantiated, no live game was launched and no player saves were accessed.
Selected roots covered the three Overgrowth boss encounter definitions, Vantom,
Ceremonial Beast, Slippery, Wound, the three implemented rare cards, reward/card
creation odds and relevant commands. Scratch JSON while retained:
`/private/tmp/sts-headless-boss-native/{bosses,rules,cards,extra,odds,boomerang}.json`.

Tokens and IL offsets below are decimal. A0 uses the non-modifier branch.

| Native member | Token | Verified rule / anchors |
| --- | --- | --- |
| Vantom minimum HP / Slippery amount | 100689000 / 100689001 | A0 173 HP at 6; Slippery 8 at 3. Maximum HP delegates to minimum. |
| Vantom attack values | 100689003–100689005 | Ink Blot 7 at 3; Inky Lance 6 at 3; Dismember 26 at 4. |
| Vantom state machine | 100689013 | Locals 1/2/3/4 are Ink Blot/Inky Lance/Dismember/Prepare. Follow-ups at 183–208 form that cycle; initial local 1 at 243–244. |
| Vantom room-add body | 100708863 | Applies Slippery using the difficulty-dependent amount at 127–145. |
| Ink Blot / Inky Lance bodies | 100708867 / 100708869 | Attacks execute at 95 / 106; Lance sets two hits at 48–49. |
| Dismember body | 100708865 | Attacks at 441–484, then adds three Wounds to pile 3 (Discard) at 695–705. |
| Prepare body | 100708871 | Applies self Strength 2 at 157–182. |
| VantomBoss | 100690390 / 100690398 | Boss room metadata and one mutable Vantom. |
| Slippery.ModifyHpLostAfterOsty | 100686143 | Only modifies its owner; leaves values below 1 unchanged, otherwise returns 1 (11–31). |
| Slippery.AfterDamageReceived body | 100707670 | Checks target identity at 18–29, requires UnblockedDamage ≥1 at 36–48, then decrements at 58–59. Fully blocked hits do not consume stacks. |
| Wound | 100693797–100693799 | Cost -1, status rarity/type; maximum upgrade level 0; Unplayable keyword 4. |
| Impervious | 100692195–100692200 / 100710219 | Cost 2, Rare 4; 30 block, upgraded by 10; Exhaust 1. GainBlock at 46. |
| Offering | 100692620–100692625 / 100710444 | Cost 0, Rare 4; lose 6 HP, gain 2 energy, draw 3; upgrade adds 2 draw. Exhaust. Ordered body calls damage at 68, energy at 186 and draw at 305. Damage ValueProp 14 combines Unblockable/Unpowered/Move. |
| PlayerCmd.GainEnergy body | 100712429 | Returns when combat is ending at 36–48. Lethal Offering therefore grants no energy; existing draw rules also stop. |
| Fiend Fire | 100691782–100691787 / 100709997 | Cost 2, Rare 4; damage 7, upgrade +3, Exhaust. Captures hand/count at 78–108, exhausts that list at 143–152, then uses captured count as hit count at 331–337 before executing attack at 397. |
| Sword Boomerang | 100693476–100693479 / 100710881 | Cost 1, Common 2, damage 3 and hit count 3; upgrade increases Repeat by 1. Uses TargetingRandomOpponents with duplicates enabled at 68–75. |
| AttackCommand random targets | 100697513 / 100712501 | Valid targets are rebuilt at 353–394 for each hit; random selection uses the player/PetOwner run CombatTargets stream at 1004–1056. |
| RewardsSet.GenerateRewardsFor | 100667241 | Boss block at 294–369 adds encounter gold, potion roll and three-card reward; no elite relic. |
| EncounterModel gold bounds | 100682412 / 100682413 | Boss minimum and maximum are both 100 (offset 39); reused from the elite source check. |
| CardCreationOptions.ForRoom | 100665993 | Room type 3 uses boss rarity odds type 3 at 95–96. |
| CardRarityOdds.GetBaseOdds | 100667527 | Boss branch at 97–156: Common/Uncommon 0, Rare 1.0. |

Enum metadata confirms Discard=3, Exhaust keyword=1, Unplayable=4, Rare=4 and
BossEncounter rarity odds=3. Bludgeon was inspected but excluded: it is Uncommon
in this pinned build, so it is not one of the three implemented boss offers.

## Implemented scope

Slippery modifies damage after block, then consumes one stack per positive
unblocked hit. It handles ordinary attacks and Fire Potion, and persists across
turns. Vantom-generated Wounds use the existing combat-owned card allocator.
Unplayable cards reject both direct player play and engine actions before energy
or pile mutation. They remain eligible for applicable hand-exhaust effects.

Rare cards have their own immutable definitions and reusable effects. Fiend Fire
exhausts the original remaining hand before any hit, resolves hits individually,
and stops on target death. The source card exhausts once after resolution.
Offering bypasses block and attack modifiers; death stops subsequent energy/draw.
No new exhaust-trigger family or general damage-order certification is claimed.

Boss rewards use exactly the three supported rares, with authored offer ordering
and the existing restricted potion sampler. This does not reproduce the full
native pool, upgrade chances, native RNG sequence or all drop modifiers. Earlier
routes retain their hallway and elite pools. The new Act 1 route adds Sword
Boomerang to its nonboss reward pool, for nine supported offers. A low-level custom configuration can
supply another explicit supported card pool; it is not a native generation claim.

Leaving a won boss reward, with claims or forfeits, records
`ActCompletion(1, "overgrowth_vantom")` and ends at `act_complete`. The player can
still claim/skip rewards before exiting. No map terminal can create that result.
Act 2 initialization, inter-act healing/rewards and full-run victory remain open.
Run snapshot v4 binds the new boss pool and completion record; earlier run formats
reject. Combat snapshot v4 adds a distinct owned target RNG stream. Analysis
clones and state keys preserve both target and hand-selection RNG. The card catalog fingerprint changes automatically. No public reduced
fixture was repinned or bridge/RL vocabulary expanded.

## Acceptance and limits

- New boss/card suite: **31 passed in 0.60 seconds**. Covers complete move cycles,
  generated identities, owned RNG aliases, blocked/zero/multiple Slippery hits,
  modifier interaction, Wound legality, rare upgrades/exhaust, lethal Offering,
  lethal Dismember, exact boss reward types and terminal claim/forfeit/restore.
- Final broad affected suite: **722 passed in 14.51 seconds** across headless,
  simulation, analysis, engine, headless backends, content, package/lazy imports
  and headless CLI. The final Sword Boomerang suite passed **12 tests in 0.46
  seconds**, including an additional RNG state-key regression. Compileall and diff whitespace checks passed.
- Independent review found no blockers. It passed 244 headless/CLI tests and
  verified 412 boss/rare-card decision continuations, a synthetic boss victory
  through act completion, and five malformed terminal records rejected atomically.
- Sword Boomerang review additionally verified 80 seeded target/continuation
  probes and 38 boss/analysis tests, including target reselection after death,
  duplicate targets, terminal RNG stopping, stream isolation and rejected explicit
  targets. No blocking findings.
- The normal seed-2 right/Rest route reaches Vantom and loses. Every command
  restores exactly, including Wounds and death. Broader simple/experimental policy
  probes also failed to produce a natural starter-route win. Therefore victory
  handoff is **controlled-fixture evidence**, not demonstrated full Act 1 success.
  No boss HP, player HP, starting inventory or production policy was altered to
  manufacture a winning route. Experimental policies/maps stayed in scratch.

The next useful gameplay addition is a first shop with purchases and permanent
card removal, followed by the remaining room/content/generation work. A naturally
winning starter-route replay remains an acceptance case to add as the route and
its deck-building opportunities expand.

Wheel SHA-256:
`614cce5615baadbb7ada848ca06bd2232ff516b1bb62e5cc1c601bef4361a6c1`.

Installed into the disposable no-RL environment and checked outside the source
tree with `PYTHONPATH` unset. Seed 2 right/Rest Act 1 route: 100 commands, five
combats completed, 186 gold, 14 persistent cards, defeated by Vantom with no act
completion; every command restored exactly. The original first slice still
completed in 38 commands at 66/80 HP with 127 gold. A separate installed
Sword Boomerang+ check dealt four hits to Vantom, removed four Slippery stacks,
and matched its restored continuation exactly.

Work began at 14:03:53 UTC. The first boss implementation, source inspection,
tests/review and unsuccessful natural-win probes occupied approximately the
first 18 minutes. The user then requested Sword Boomerang; source checks,
implementation, tests/review and final packaging followed over approximately
seven minutes. These activities overlapped; no separate implementation/review
stopwatch was kept. The final broad suite took 14.51 seconds; wheel build,
installation and installed checks each took under a second. No user wait was
required.
