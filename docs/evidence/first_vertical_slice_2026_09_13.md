# First persistent gameplay slice, 2026-09-13

M1 now runs Ironclad A0 through two encounters, both reward bundles, and a choice
of rest or smith between them. Seed 2 on the smith path exercises a starter-card
upgrade, Burning Blood and a potion acquired in the first rewards and used in
the second fight. Every decision can be restored through JSON and continued.
The ending is `slice_complete`, distinct from actual game victory.

## Source identity and method

- Target: v0.107.1, Steam build 23811903; [binary identity](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
- Assembly SHA-256: `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
- Reference: `/private/tmp/sts-current-release-final/references/sts2.dll`.
- Implementation base: `7d93423` on `codex/headless-integration`.

Reused the bounded metadata scanner from the
[starter-card source check](strike_upgrade_2026_09_13.md), retaining its hash,
symlink, file-size, type-count and method-size guards. The .NET 9.0.303 runtime
executed the scanner, not game code. No game launch or player-profile access was
needed. Scratch selectors and output are under
`/private/tmp/sts-headless-vertical-native/` while that temporary storage exists.
The anchors below identify reproducible methods independently of those files.

Exact selectors under `MegaCrit.Sts2.Core` were `Models.Characters.Ironclad`,
`Models.Relics.BurningBlood`, `Models.Potions.FirePotion`,
`Models.Potions.BlockPotion`, `Models.CharacterModel`, `Models.EncounterModel`,
`Models.PotionModel`, `Entities.Players.Player`, `Entities.Creatures.Creature`,
`Commands.CreatureCmd`, `Entities.RestSite.HealRestSiteOption`,
`Entities.RestSite.SmithRestSiteOption`, `Entities.RestSite.RestSiteOption`,
`Rewards.GoldReward`, `Rewards.CardReward`, `Rewards.PotionReward`,
`Rewards.RewardsSet`, `Odds.PotionRewardOdds`, `Odds.AbstractOdds` and
`ValueProps.ValuePropExtensions`, including nested state-machine types.

## Native anchors

Tokens and IL offsets below are decimal and refer only to that assembly.

| Method | Token | Finding |
| --- | --- | --- |
| `Ironclad.get_StartingHp`, `get_StartingGold` | 100690629, 100690630 | Offset 0 returns 80 HP and 99 gold respectively. |
| `Ironclad.get_StartingDeck` | 100690634 | Strike calls at 9/17/25/33/41, Defend at 49/57/65/73, Bash at 82: five/four/one. |
| `Ironclad.get_StartingRelics` | 100690635 | Offset 0 requests Burning Blood. |
| `CharacterModel.get_StartingPotions`, `get_MaxEnergy` | 100682298, 100682289 | Empty starting potion array; maximum energy returns 3 at offset 0. |
| `Player.CreateForNewRun` | 100696084 | Constant 3 at 26 supplies potion-slot count to the constructor at 44; inventory population at 51. |
| `BurningBlood.get_CanonicalVars` | 100683242 | Heal value 6 at offset 0. |
| `BurningBlood.<AfterCombatVictory>d__4.MoveNext` | 100706544 | Owner death check at 18–28; living owner receives the heal through `CreatureCmd.Heal` at 74. |
| `FirePotion.get_Usage`, `get_TargetType`, `get_CanonicalVars` | 100686766, 100686767, 100686768 | Combat usage, enemy target, 20 damage at offset 0 with value-prop flag 4 at 7. |
| `BlockPotion.get_Usage`, `get_TargetType`, `get_CanonicalVars` | 100686650, 100686651, 100686652 | Combat usage, player target, 12 block at offset 0 with value-prop flag 4 at 7. |
| `BlockPotion.<OnUse>d__10.MoveNext` | 100707867 | Target validation at 23; `CreatureCmd.GainBlock` at 47 using the block variable. |
| `ValuePropExtensions.IsPoweredAttack`, `IsPoweredCardOrMonsterMoveBlock` | 100663702, 100663703 | Powered checks require flag 8 and exclude flag 4 (25–37). Potion effects therefore bypass the implemented attack modifiers. |
| `HealRestSiteOption.GetBaseHealAmount` | 100695939 | Maximum HP multiplied by decimal 0.3, constructed at 11–16, multiply at 21. |
| `Creature.HealInternal`, `SetCurrentHpInternal` | 100696407, 100696408 | Adds healing then applies maximum HP cap (`Math.Min` at 13) and decimal-to-int truncation at 18. Positive 30% healing rounds down. |
| `RestSiteOption.get_IsEnabled` | 100695975 | Returns true at 0; Heal uses this default, including at full HP. |
| `SmithRestSiteOption.get_IsEnabled`, constructor | 100695990, 100695991 | Requires positive upgradable-card count; default SmithCount is 1. |
| `SmithRestSiteOption.<OnSelect>d__14.MoveNext` | 100711697 | Cancelable and manual-confirmation flags set true at 44–53; upgrade selection at 68; empty selection does not complete smithing; card upgrade at 218. |
| `EncounterModel.get_MinGoldReward`, `get_MaxGoldReward` | 100682412, 100682413 | Ordinary combat branches return 10 and 20 at 29 before ascension modifiers. Only A0 is supported here. |
| `GoldReward.Populate` | 100667148 | Passes max + 1 to `NextInt` at 43, making the maximum inclusive. |
| `RewardsSet.GenerateRewardsFor` | 100667241 | Normal-combat branch constructs gold at 150, rolls potion at 169, creates a three-card reward at 187–190. |
| `RewardsSet.RollForPotionAndAddTo` | 100667242 | Uses the player's potion odds at 6/27; creates a potion reward on success at 37. |
| `PotionRewardOdds` constructor, `Roll` | 100667538, 100667540 | Starts at float 0.4; normal-combat success subtracts 0.1 at 87–93, miss adds 0.1 at 107–113. Elite and forced-drop paths are outside this slice. |
| `AbstractOdds.set_CurrentValue` | 100667513 | Direct backing-field assignment; no clamping hook. |
| `RewardsSet` constructor, `WithSkippingDisallowed` | 100667234, 100667238 | Ordinary rewards leave the disallow-skipping flag false; the explicit modifier sets it true at 1–2. |

Starter upgrade and ordinary hand-cap evidence are retained in their existing
[upgrade](strike_upgrade_2026_09_13.md) and [draw](hand_limit_2026_09_13.md) records.

## Delivered behavior and evidence boundary

The [engine guide](../HEADLESS_ENGINE.md) owns the gameplay API and supported
rules. [Direct acceptance cases](../../tests/headless/test_vertical_slice.py)
cover both full routes, exact persistent deck identities, item consumption,
once-only capped victory healing, defeat, independent reward claiming/skipping,
full inventory/discard/claim, stable enemy targets, smith cancellation, invalid
operation atomicity, RNG odds persistence and malformed snapshot rejection.
Complete route tests serialize/restore before every command and compare the
resulting state. Synthetic exact-lethal and damage-modifier setups are labeled
in the tests; they are not recorded native game interactions.

An independent semantic review found no blockers, independently ran 50 direct
tests at its review point, and checked 1,559 randomized legal transitions across
30 seeds against JSON-restored continuation. This is engine consistency evidence,
not native end-to-end conformance.

Final affected integration passed **503 tests in 10.71 seconds** across direct
headless rules, simulation, analysis, legacy engine/backends, lazy imports,
package layout and the existing headless CLI. `compileall game tests` also passed.
An offline wheel was built and installed into a disposable Python environment;
the installed `sts-headless-play --seed 2 --verify-restore` completed both smith
and rest paths (40 and 39 commands respectively), each using one potion and
finishing with 12 cards and 127 gold. No RL dependency was installed there.

The authored map is Nibbit → rest → Overgrowth slimes → slice end. Reward cards
are restricted to three distinct offers from Pommel Strike, Shrug It Off, Iron
Wave and Body Slam. Potion content is restricted to Fire and Block Potions.
Only Strike, Defend and Bash have implemented upgrade levels. Existing monster
and nonstarter card rules are reused partial implementations, not newly certified
complete models. The native scalar checks above do not certify every timing hook
or interaction around them.

Generation uses explicit named Python streams and integer percentage odds. This
is deterministic project-authored sampling, not native seed, floating-point,
rarity, pool, shared-domain or draw-order parity. Full maps/acts, bosses, Ancients,
other items, reward-card upgrades, generalized nested choices, higher ascensions
and complete game victory remain open in the
[feature backlog](../HEADLESS_FULL_GAME_IMPLEMENTATION.md). No projection, encoder,
bridge protocol or training integration was required for M1.
