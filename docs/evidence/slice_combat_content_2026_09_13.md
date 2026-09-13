# First-slice combat content source checks, 2026-09-13

The current seven Ironclad cards now have their base and single-upgrade versions.
Slimed draws one card and exhausts. The two-combat slice's solo Nibbit and four
slime variants have source-checked A0 values, move cycles and branch constraints.
This is static native-source evidence plus Python execution/continuation tests,
not live differential certification or native seed parity.

## Source and method

- Target: v0.107.1, Steam build 23811903; [binary identity](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
- Assembly SHA-256: `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
- Reference: `/private/tmp/sts-current-release-final/references/sts2.dll`.
- Implementation base: `e227b23` on `codex/headless-integration`.

Reused the bounded metadata scanner described in the
[starter-card source check](strike_upgrade_2026_09_13.md), with the same hash,
symlink, file-size, type-count and method-size guards. The scanner ran under
.NET 9.0.303; it did not load or execute native game types. Scratch selected IL
is in `/private/tmp/sts-headless-combat-content-native/{il,helpers,lifecycle}.json`
while temporary storage exists. Existing draw and creature-command output from
the [hand-limit](hand_limit_2026_09_13.md) and
[first-slice](first_vertical_slice_2026_09_13.md) checks supplied shared anchors.

Exact selected roots under `MegaCrit.Sts2.Core` were the five new card families
in `Models.Cards`, `Models.Monsters.Nibbit`, `LeafSlimeS`, `LeafSlimeM`,
`TwigSlimeS`, `TwigSlimeM`, `Models.Encounters.SlimesWeak`, `NibbitsWeak`,
`MonsterMoves.MonsterMoveStateMachine.RandomBranchState`, `MoveState`,
`Helpers.AscensionHelper`, `Models.MonsterModel`, `Models.PowerModel`,
`Models.Powers.StrengthPower`, `VulnerablePower`, `Commands.PowerCmd`,
`Combat.CombatManager`, `Entities.Cards.CardEnergyCost`, and
`Localization.DynamicVars.CalculatedVar`, `CalculatedDamageVar`, including
nested state-machine bodies. Tokens and offsets below are decimal.

## Cards

| Definition / methods | Tokens | Verified result and relevant offsets |
| --- | --- | --- |
| Pommel Strike constructor / vars / upgrade | 100692756 / 100692758 / 100692760 | Cost 1; damage 9 at 8 and draw 1 at 24. Upgrade adds one to each at 11–16 and 32–37: 10 damage, draw 2. |
| Pommel Strike play body | 100710505 | Attack executes at 113; draw begins at 233 after the awaited attack. |
| Shrug It Off constructor / vars / upgrade | 100693170 / 100693172 / 100693174 | Cost 1; block 8 at 8, draw 1 at 23; upgrade adds 3 block at 11–17, preserving draw count. |
| Shrug It Off play body | 100710723 | Gain block at 53, then draw at 173. |
| Iron Wave constructor / vars / upgrade | 100692241 / 100692243 / 100692245 | Cost 1, damage/block 5 at 8/23; upgrade adds 2 to each at 11–17 and 33–39. |
| Iron Wave play body | 100710240 | Gain block at 74 before attack execution at 226. |
| Body Slam constructor / vars / upgrade | 100690998 / 100690999 / 100691002 | Cost 1; calculated damage with base 0, extra 1 and a block multiplier. Upgrade passes -1 to `CardEnergyCost.UpgradeBy` at 6–7, producing cost 0. |
| Body Slam multiplier / play | 100709626 / 100709627 | Multiplier reads owner's current block at 11; play passes calculated damage to the attack builder at 52. |
| `CalculatedVar.Calculate` | 100694832 | Combines base plus extra × multiplier at 95–100. Attack modifiers remain separate. |
| `StrengthPower.ModifyDamageAdditive` | 100686253 | Adds owner's Strength only for powered attacks (16–36). |
| `VulnerablePower.ModifyDamageMultiplicative` | 100686501 | Requires the affected target and powered attack; unsupported relic/power multiplier hooks remain outside these cases. |
| Slimed constructor / upgrade limit / vars / keywords / play | 100693204–100693208; play body 100710740 | Cost 1, no upgrade (limit 0), one-card draw, Exhaust; play calls Draw at 88. |

The four reward cards inherit the default one-upgrade limit recorded in the
starter evidence. Their costs remain one except Body Slam+. The existing
Strike/Defend/Bash source records remain authoritative for those values.

## Encounters

`AscensionHelper.GetValueIfAscension` (100695208, 13–16) returns its final argument
when the modifier is absent. The A0 values below use that branch.

| Enemy | Native tokens | A0 rules |
| --- | --- | --- |
| Solo Nibbit | HP/damage/block/Strength 100688132–100688137; state machine 100688144 | HP 42–46. Butt 12 → Hesitant Slice 6 then block 5 → Hiss grants self Strength 2 → repeat. |
| Nibbit move bodies | 100708492 / 100708496 / 100708494 | Attack; attack at 88 before block at 199; self Strength application at 160 respectively. |
| `NibbitsWeak.GenerateMonsters` | 100690155 | One Nibbit, `IsAlone=true` at 17–18. The conditional state machine opens with Butt for this role. Paired roles are separate work. |
| Small Leaf | 100687984–100687986; state machine 100687988 | HP 11–15, Tackle 3, Goop adds one Slimed. Equal initial choice; neither move can immediately repeat. |
| Medium Leaf | 100687976–100687978; state machine 100687980 | HP 32–35. Opens with Sticky Shot (two Slimed), alternates with Clump Shot 8. |
| Small Twig | 100688963–100688965; state machine 100688967 | HP 7–11, repeatedly Tackle 4. |
| Medium Twig | 100688954–100688957; state machine 100688959 | HP 26–28. Opens with Sticky Shot (one Slimed). Attack damage 11; at most two consecutive attacks, no consecutive Sticky Shots. The legacy Python label `Chomp` corresponds to native state `POKEY_POUNCE_MOVE`. |

Generated-card bodies are small Leaf 100708429, medium Leaf 100708427 and medium
Twig 100708840. Their `AddToCombatAndPreview<Slimed>` calls use pile type 3 and
counts 1/2/1. `CardPile.Get` (100696517) maps switch case 3 to DiscardPile at 98.
These are generated combat cards; they never enter the persistent master deck.

Two overloads had previously been conflated: medium Twig calls
`RandomBranchState.AddBranch(state, int)` with 2 (100688959, 114–115), which
specifies a consecutive-repeat limit, not weight 2. The Sticky Shot call uses
`MoveRepeatType` value 2 (122–123), which forbids an immediate repeat.
`AddBranch` 100681565–100681566 supplies default weight 1 to both;
100681558 stores the integer as `maxTimes`. `GetStateWeight` 100681568 enforces
the consecutive-history restriction. Thus the choice after the first attack
is 50/50, followed by forced Sticky Shot after a second attack.

`RandomBranchState.GetNextState` (100681567) calls `NextFloat` at 39 even if only
one branch has nonzero weight. Python Leaf/Twig random branches now likewise
consume one roll for each transition. This verifies the branch rule, not native
RNG domains or bitwise results.

`SlimesWeak.GenerateMonsters` (100690265) selects two distinct small types at
24/45, appends the first at 64, a random medium at 97, and the other small at
115. Its static pools (100690267) contain Leaf/Twig small and Leaf/Twig medium.
The corrected stable slots are **small / medium / small**.

## Combat ending, ownership and compatibility

`CombatManager.get_IsEnding` (100697584) detects the lack of remaining enemies
and pending loss; `get_IsOverOrEnding` (100697585) also covers stopped combat.
The retained `CardPileCmd.Draw` body checks that condition at 29–34 and before
each draw at 410–415. `CreatureCmd.<GainBlock>d__18.MoveNext` (100712375) returns
without block at 33–53 when combat is ending. `PowerCmd.<Apply>d__2.MoveNext`
(100712455) checks combat ending at 45–55 and power eligibility at 85–98.

Draws therefore stop after a last-enemy lethal attack, while a nonfinal lethal
Pommel Strike still draws. The player owns an alias to its combat's enemy slots
for liveness; reset, private restore and search cloning rebind it explicitly.
No resolver callback or external projection is stored in game state. Lethal
enemy attacks stop follow-up effects and further move sampling.

The new medium Twig repeat counter is owned and serialized with the monster.
Restore checks its valid range and correspondence to the current move before
installing state. Added upgrades and corrected Slimed change the automatic
card-catalog fingerprint, so older private default-catalog snapshots reject.

Slime layout and RNG-consumption corrections intentionally change Python seeded
slime traces. Two current compatibility regression expectations were updated to
the corrected shared rules. Accepted reduced simple/Nibbit fixtures, historical
manifests and evidence hashes were not repinned. The fixed legacy card vocabulary
remains unchanged; Slimed metadata now reports its real draw effect automatically.

## Validation and remaining scope

[Card cases](../../tests/headless/test_slice_cards.py) cover all four base/upgrade
pairs, effect order, Body Slam's zero cost and modifiers, Slimed's draw/exhaust,
terminal effects and actual acquisition → smith → second-combat use for every
reward card. [Encounter cases](../../tests/headless/test_slice_encounters.py)
cover HP ranges, full move cycles, random branch boundaries and forced choices,
stable composition, exact generated cards, every-boundary JSON continuation,
invalid repeat-state rejection and isolated search-clone ownership.

The independent semantic reviewer identified an invalid-counter restore case;
the content-owned validation and adversarial tests fixed it. No blockers remained.
The reviewer independently ran 36 existing direct tests and compared 182 combat
transitions with restored copies, including search-clone alias checks.

Final affected integration passed **554 tests in 10.88 seconds**, including the
42 new card/encounter cases, existing direct gameplay, simulation, analysis,
legacy engine/backends/content, package/lazy imports and the headless CLI.
`compileall game tests` and local Markdown-link checks passed. An offline wheel
installed into the disposable dependency-free Python environment completed both
seed-2 rest/smith examples with JSON verification: each took 38 commands, used
one potion and finished both combats. Their final HP was 78/66 respectively.

This covers the current card definitions and solo Nibbit/slime rules with the
slice's supported interactions. Full native RNG, broader hooks/modifiers,
paired Nibbit roles and other enemies remain open. Native Vulnerable ticks at
the enemy-side boundary with `SkipNextDurationTick` (100707829 / 100712465);
Bash-applied enemy duration is covered here, but general player/source timing
still needs HF-12. No new statuses were required by these selected encounters.
The [backlog](../HEADLESS_FULL_GAME_IMPLEMENTATION.md) records those remaining
tasks. No native launch or broad live conformance claim accompanies these tests.
