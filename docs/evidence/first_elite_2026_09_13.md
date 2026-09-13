# First Overgrowth elite and relic rewards, 2026-09-13

Byrdonis is the first supported elite on the authored Ironclad A0 Overgrowth
route. Its combat, Territorial power, elite reward handoff and three permanent
max-HP relic pickups use the independent gameplay package. This does not complete
Act 1 or reproduce native encounter/reward generation.

## Native source

Target: v0.107.1, Steam build 23811903. Assembly SHA-256:
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
[Build manifest](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
Implementation base: `f9cb36d` on `codex/headless-integration`.

Reused the bounded static metadata scanner described in the
[starter-card evidence](strike_upgrade_2026_09_13.md), under .NET 9.0.303, retaining
hash, symlink, size and instruction-count guards. No native game object was
instantiated and no live game was launched. Selected roots under
`MegaCrit.Sts2.Core` included Overgrowth, Byrdonis/ByrdonisElite, TerritorialPower,
EncounterModel, RewardsSet, GoldReward, RelicReward, Strawberry, Pear, Mango and
CreatureCmd, with their nested method bodies. Scratch outputs while retained:
`/private/tmp/sts-headless-elite-native/{content,rules,fruits}.json`.

Tokens and IL offsets below are decimal. Difficulty-dependent values use the
non-modifier branch, appropriate to A0.

| Native member | Token | Verified rule / anchors |
| --- | --- | --- |
| Overgrowth.GenerateAllEncounters | 100694198 | ByrdonisElite appears at 17 in the actual Overgrowth pool; BygoneEffigyElite and PhrogParasiteElite are the other elite entries. |
| Byrdonis HP | 100687304 / 100687305 | Minimum 81 and maximum 84, A0 constants at 3. |
| Byrdonis Peck damage/repeats / Swoop damage | 100687306–100687308 | Peck 3 at 3, repeat count 3 at 3; Swoop 17 at 4. |
| Byrdonis state machine | 100687312 | Local 1 is Peck, local 2 is Swoop. Swoop→Peck at 95–97; Peck→Swoop at 102–104. Initial state is **local 2, Swoop**, at 123–125. |
| Byrdonis.AfterAddedToRoom body | 100708122 | Applies Territorial 1 at 115–139 after the base room-add operation. |
| Peck / Swoop bodies | 100708124 / 100708126 | Peck reads damage/repeats at 17/32, applies hit count at 37 and executes at 90. Swoop reads damage at 17 and executes at 80. |
| ByrdonisElite room / composition | 100689911 / 100689913 | Room type 2 (elite); one mutable Byrdonis. |
| Territorial.AfterSideTurnEnd body | 100707783 | Checks whether the side participants contain the owner at 18–29; otherwise returns at 34–36. Applies self Strength equal to Territorial amount at 48–78. |
| EncounterModel gold minimum / maximum | 100682412 / 100682413 | Elite type 2 yields 35 / 45 at 34; hallway type 1 yields 10 / 20 at 29. |
| GoldReward.Populate | 100667148 | Uses NextInt(minimum, maximum+1) at 30–43: inclusive gold endpoints. |
| RewardsSet.GenerateRewardsFor | 100667241 | Elite block adds encounter gold at 212/223, potion roll at 249, room card creation options at 262, three-card reward at 267–270 and RelicReward at 282/287. Hallway block has no relic reward. |
| Strawberry variables / obtained body | 100684660 / 100707058 | Max-HP amount 7 at 0; calls GainMaxHp at 44. |
| Pear variables / obtained body | 100684248 / 100706917 | Max-HP amount 10 at 0; calls GainMaxHp at 44. |
| Mango variables / obtained body | 100683930 / 100706803 | Max-HP amount 14 at 0; calls GainMaxHp at 44. |
| CreatureCmd.GainMaxHp body | 100712377 | Rejects negative gain at 18–40, raises maximum HP at 47–79, then heals the same amount at 248–255. |

Territorial persists rather than decaying. The combat engine triggers it after
its owner's whole side, once per living owner. Byrdonis therefore opens Swoop 17,
then Peck 4×3, Swoop 19, Peck 6×3 before Weak/Vulnerable or other modifiers.
Restoring does not rerun room-add or relic-obtained effects. Fruit relic removal
has no inverse pickup effect; the maximum HP increase remains permanent.

## Authored rules and compatibility

The final branch after Rest/Smith now offers Mawler, paired Nibbits or Byrdonis.
Together with the earlier slimes/Fuzzy ordering this gives six four-combat paths.
The demo's `--path right` now chooses Byrdonis; direct commands can select any
legal branch. All paths still terminate at `slice_complete`.

Encounter definitions carry room kind, gold range and whether a relic is awarded.
The run owns the selected encounter ID during combat and passes it to rewards.
Both registered definition objects and their previously exported raw factories
retain the correct identity through the low-level combat-start API.

Elite rewards use the existing restricted eight-card and two-potion pools, plus
one uniform choice from unowned Strawberry/Pear/Mango. Native rarity weighting,
card upgrade chances, complete reward pools and RNG sequence parity remain open.
This evidence verifies scalar amounts and reward types, not native generation.
An exhausted declared relic pool rejects elite entry before RNG or route mutation;
this is an explicit unsupported-content boundary, not native exhaustion behavior.

`ClaimRelic()` can precede or follow other claims. Leaving forfeits unclaimed
rewards. Pickup adds maximum and current HP once; current HP remains capped at the
new maximum. Maximum-HP pickup during combat is explicitly unsupported. Run v3
snapshots include active/reward encounter IDs, the relic pool and claim state;
run v1/v2 reject. Combat v3 and public reduced-fixture schemas remain unchanged.
No bridge projection, encoder or training surface was extended.

## Validation

- Broad affected suite: **678 passed in 15.60 seconds**, covering headless,
  simulation, analysis, engine, headless backends, content, package/lazy-import
  and headless CLI tests. All six route paths, with both Rest and Smith, completed
  through ordinary actions and exact JSON continuation.
- After the final restore correction: **40 elite tests passed in 0.63 seconds**,
  including two new malformed active-pool cases. Compileall and diff checks passed.
- Independent semantic review verified Territorial timing, pickup permanence,
  factory compatibility and atomic restore. It found two concrete issues: raw
  factory identity inference and missing active-elite pool validation on restore.
  Both were fixed and independently rechecked; no findings remain. Its earlier
  route panel also verified 798 restored decisions.
- Additional cases cover HP endpoints, opening and full move cycles, no move RNG,
  Weak/Vulnerable per-hit rounding, dead owners, owned RNG aliases, duplicate
  claims, forfeits, excluded relics, exhausted-pool rollback, real defeat and
  malformed reward identity/ownership/gold/graph records.

Built wheel SHA-256:
`c053306d67791e5464084fb2ba5a42f7515e05e15e1025676ea99f57955ee7db`.
Installed into the disposable environment and ran outside the source tree with
`PYTHONPATH` unset:

- Overgrowth, seed 2, right/Rest: four combats, 75 commands, 60/90 HP, 186 gold,
  14 cards, Burning Blood + Pear, two potions used; restored every command.
- Default first slice, seed 2, Smith: two combats, 38 commands, 66/80 HP, 127 gold,
  12 cards, one upgraded card; restored every command.

Work began at 13:38:42 UTC. Source inspection and implementation occupied roughly
the first seven minutes; tests, review and documentation overlapped the following
seven. The broad suite itself took 15.60 seconds; wheel build/install and both
installed-command checks each took under a second. No user wait was required.
