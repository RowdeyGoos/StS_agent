# Combat card choices, 2026-09-13

Armaments and True Grit now exercise game-owned hand selection, temporary combat
upgrades and exhaustion. The restricted slice offers six reward-card families.
This evidence combines static native IL inspection with synthetic Python rule
cases and complete authored run loops; it is not live differential certification.

## Source

Target v0.107.1 / Steam build 23811903, with assembly SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
See the [build identity](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
Implementation starts from integration commit `7dc7a6f`.

Reused the bounded, hash-checked metadata scanner from the
[starter-card evidence](strike_upgrade_2026_09_13.md) under .NET 9.0.303.
No game types were executed. Selected roots under `MegaCrit.Sts2.Core`:
`Models.Cards.Armaments`, `Models.Cards.TrueGrit`, `Commands.CardSelectCmd`,
`CardSelection.CardSelectorPrefs`, including nested state-machine bodies.
Scratch output: `/private/tmp/sts-headless-combat-choices-native/il.json` while
available. Decimal metadata tokens and IL offsets below allow reinspection.

| Native method | Token | Verified behavior |
| --- | --- | --- |
| Armaments constructor / canonical vars | 100690825 / 100690827 | Cost 1; block 5 at offset 0. No card-specific upgrade override. |
| Armaments play body | 100709540 | GainBlock at 53 completes before the upgrade branch. IsUpgraded at 145; upgraded filters hand cards at 200 and upgrades each at 224. Base calls FromHandForUpgrade at 269, then upgrades its non-null result at 372. |
| Armaments upgrade filter | 100709539 | Calls CardModel.IsUpgradable at 1. |
| True Grit constructor / vars / upgrade | 100693642 / 100693644 / 100693647 | Cost 1; block 7 at 0; upgrade adds 2 at 11–17, yielding 9. |
| True Grit play body | 100710965 | GainBlock at 65; upgraded requests one hand card at 169–195, exhausts at 320. Base reads RunState.Rng.CombatCardSelection at 433–448, calls NextItem on hand cards at 460 and exhausts a non-null result at 481. |
| FromHandForUpgrade body | 100712316 | Stops if combat ends at 33–47. Filters hand at 129; count <= 1 returns FirstOrDefault at 140–161. Otherwise requests exactly one at 178–181. |
| FromHand body | 100712312 | Stops if combat ends at 33–51. Empty eligible list returns at 154–169. Without manual confirmation, count <= minimum automatically selects at 174–213. Otherwise requests the configured min/max. |
| CardSelectorPrefs constructors | 100697916 / 100697917 | Single-count overload assigns equal minimum/maximum. Initialization defaults Cancelable to false; RequireManualConfirmation is false for equal nonnegative counts, at 94–124. |

The default one-upgrade limit is recorded in the starter-card evidence. Native
content hooks and modifiers outside the supported rules remain unimplemented.
The headless engine uses Python random choice on a separately owned stream; this
verifies the random-versus-player-choice rule, not native RNG consumption or
run-wide seed parity. Its stream forks from the provided combat deck RNG state
before initial shuffle, without advancing that RNG. Empty hand selection does
not consume randomness in this model.

## State and acceptance

`ChooseCombatCard` selects an exact current hand instance. While pending, card
play, end turn and run potion commands reject without mutation. Zero or one
eligible card resolves automatically; larger sets require one choice, with no
cancel action. The source stays in an in-play pile until the effect suffix
finishes. Cost and block happen once before suspension. Both upgrades and
exhaustion affect combat instances only; the run's master deck remains separate.

Private combat snapshot v2 records the in-play pile, immutable pending effect
index/target slot and selection RNG. Restore builds a separate graph, validating
that an active, authored selection really requires multiple eligible hand cards.
No callbacks, module names or executable continuation objects are deserialized.
The existing private run v2 codec carries this nested record. Earlier combat v1
records reject. Public fixture schemas and the frozen legacy vocabulary stay
unchanged; legacy oracle/action encoders cannot use these choice cards.

The new tests cover both card levels, automatic empty/single selection, duplicate
names with distinct IDs, exhausted status cards, capped upgrades, upgraded Body
Slam's immediate zero cost, temporary-upgrade persistence through reshuffle and
reset at the next combat, seeded random exhaustion, malformed-state atomicity,
sequential choices and resuming an authored effect suffix. The existing real run
acquire → Smith → play acceptance now includes both new reward cards.

Independent semantic review found no blockers and checked 1,177 legal transitions
across 20 seeded runs, including 79 explicit choices, with identical restored
continuation. Its separate focused run passed 136 headless tests. Final affected validation passed **582 tests in 11.42 seconds** across headless,
simulation, analysis, engine, headless backends, content, package/lazy-import and
headless CLI tests. `compileall game tests`, diff whitespace and local links pass.

Built and installed the wheel into the disposable no-RL environment. With the
source checkout absent from `PYTHONPATH`, installed `sts-headless-play --seed 2
--verify-restore` completed both Smith and Rest paths in 38 commands, with final
HP 66/78, gold 127 and 12 cards. Explicit installed-engine checks restored and
resolved pending choices for both cards. The default demo policy did not choose
these cards in a bounded 20-seed check; the real acquisition/Smith acceptance
selects each new card deliberately, while the CLI supports the resulting choice
command. This is a demonstration policy limitation, not missing engine legality.

Final wheel SHA-256:
`d1b84814a27f16470d887852d074ff04711342a52a27d84264da276eb35a183d`.
The first final matrix preceded a small isolated-Player compatibility correction;
the affected matrix above was rerun after it, and the installed wheel contains
that correction. Review reported no blockers. Elapsed task time was about
14 minutes; native inspection and implementation occupied approximately the
first 10 minutes, followed by overlapping review, tests, documentation and
package checks. No user wait or live game launch was required.
