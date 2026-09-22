# Weak, Uppercut and Shockwave, 2026-09-13

This batch implements Weak and its first two Ironclad callers, plus the shared
Weak/Vulnerable duration rule. Evidence is static inspection of the pinned game
assembly and Python execution tests. It does not certify native seed parity,
unsupported power/relic interactions or live differential behavior.

## Source identity and anchors

Target v0.107.1, Steam build 23811903; assembly SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
[Build manifest](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
Implementation base: `c8f028c` on `codex/headless-integration`.

Used the bounded, hash-checked metadata scanner described in the
[starter-card evidence](strike_upgrade_2026_09_13.md), under .NET 9.0.303.
No native game types were executed. Selected roots under `MegaCrit.Sts2.Core`:
`Models.Powers.WeakPower`, `VulnerablePower`, `Models.Cards.Uppercut`, `Shockwave`,
`Commands.CreatureCmd`, and `Hooks.Hook`, including nested bodies. Shared
`PowerCmd` and `Creature` anchors come from retained earlier source inspections.
Scratch output is `/private/tmp/sts-headless-weak-native/{il,helpers}.json` while
available. Tokens/offsets below are decimal.

| Native method | Token | Verified rule / offsets |
| --- | --- | --- |
| Weak canonical vars / modifier | 100686511 / 100686512 | Decimal .75 from 75/scale2 at 5–11. Modifier requires this owner as attacker and a powered attack at 3–22. Unsupported Paper Krane/Debilitate modifications are outside this batch. |
| Vulnerable canonical vars / modifier | 100686500 / 100686501 | Decimal 1.5 from 15/scale1 at 5–11; requires this owner as target and a powered attack at 2–21. |
| Weak / Vulnerable side-end bodies | 100707831 / 100707829 | Both compare side to enemy value2 at 18–24, then call TickDownDuration at 29. |
| PowerCmd.Apply body | 100712455 | Existing instance stacks via ModifyAmount at 151–277 and skips new-instance setup. New player-side debuff (side1/type2) sets SkipNextDurationTick at 1053–1088. |
| PowerCmd.TickDownDuration body | 100712465 | Reads skip flag at 16, clears it and returns at 21–35; otherwise decrements at 43. |
| Hook.ModifyDamageInternal | 100695207 | Adds additive modifiers at 59–69; multiplies decimal modifiers at 170–180. No intermediate integer rounding between Weak and Vulnerable. |
| Creature.LoseHpInternal | 100696404 | Caps the decimal amount with Math.Min at 48, converts to integer at 53, then clamps HP at 69. Positive fractional damage truncates down. |
| Uppercut constructor / vars / upgrade | 100693705 / 100693706 / 100693709 | Cost2; damage13 at 8, Power1 at 29. Upgrade adds one to Power at 16–21; damage remains13. |
| Uppercut play body | 100710992 | Attack Execute at 161, then Weak at 320, then Vulnerable at 452. |
| Shockwave constructor / vars / keywords / upgrade | 100693159–100693161 / 100693164 | Cost2, all-enemy target3, Power3 at 5, Exhaust keyword1. Upgrade adds2 at 16–22 for Power5. |
| Shockwave play body | 100710719 | Enumerates HittableEnemies at 198–208, applying Weak at 288 then Vulnerable at 415 to each enemy before advancing. |

## Implementation and boundaries

Uppercut deals 13 and applies 1 Weak/1 Vulnerable; Uppercut+ applies 2 of each.
Shockwave applies 3 of each to all living enemy slots, then exhausts; Shockwave+
applies 5. Both cost2 and are available in the eight-card restricted reward pool.
Persistent Smith upgrades and temporary Armaments upgrades use their definitions.
Debuff application skips dead targets and stops when combat ends.

Weak's stack count represents duration, not increasing damage reduction. Damage
combines Strength, Weak and Vulnerable before final rounding, separately for
each hit. Enemy intent inspection retains its rounded damage preview, while
execution uses its private authored amount to avoid applying Vulnerable to an
already rounded Weak amount. Example: base5 × .75 × 1.5 becomes5, not4. Non-attack
damage ignores these attack modifiers. The older Shrink approximation remains
explicitly outside this verification and retains its existing rounding step.

The combat owner ticks both sides' duration powers once after the whole enemy
side. New player debuffs skip the first tick; stacking does not restart that
flag. Final removal clears duration state. Player Vulnerable no longer expires
at player end turn before enemies attack; the old regression asserted that
incorrect approximation and now asserts the source-checked result.

Private combat schema v3 persists skip flags and rejects earlier v1/v2 records.
The existing run v2 format embeds this versioned combat record. Invalid duration
flags reject before installing state. Search clones copy flags independently and
state keys include them: equal stacks with different future expiration must not
merge. Public reduced fixture artifacts were not repinned. Legacy status encoder
width remains fixed; Weak/new cards require the direct game API. Legacy incoming
damage projection based only on rounded intent fields is not certified for Weak
combined with Vulnerable; broader consumer integration is separate work.

## Acceptance

Focused tests cover both card levels, attack-before-debuff ordering, per-enemy
Weak-before-Vulnerable ordering, dead slots, source exhaustion, stacking,
expiration, new-instance skip behavior, once-per-side ticking, combined modifier
rounding, multi-hit and non-attack damage, malformed restore, and search branch
isolation/key distinction. Real reward → Smith → next-combat play tests now
include both cards and compare JSON-restored continuation at every decision.

Independent review found and verified correction of a missing duration flag in
the legacy search key. No blockers remain. Its separate checks passed 166
headless tests and 311 mixed debuff/choice transitions with identical restored
continuation.

Final affected suite: **609 passed in 11.99 seconds**, covering headless,
simulation, analysis, engine, headless backends, content, package/lazy-import and
headless CLI tests. Compileall, diff whitespace and local documentation links
passed. Earlier focused validation took 1.17 seconds for 59 tests.

Built wheel SHA-256:
`d373b2d9b2a60dc724572799473f0416d511372a5dcb978120dd70f5648e9bf5`.
Installed into the disposable no-RL environment and ran outside the source tree
with `PYTHONPATH` unset. Both seed2 Smith/Rest CLI paths completed with restore
verification in 38 commands, final HP66/78, gold127 and 12 cards. Explicit
installed-engine checks exercised both upgraded cards and identical restored
continuation through the following enemy turn.

Elapsed work was approximately ten minutes: source inspection and implementation
occupied the first four minutes, with review, focused validation and test
expansion overlapping the next three; documentation, final checks and package
preparation followed. No user wait or live game launch was required.

## Correction: Shockwave is colorless

The user's correction was verified against the same pinned DLL:
`ColorlessCardPool.GenerateAllCards` token `100693916` includes Shockwave;
`IroncladCardPool.GenerateAllCards` token `100693955` excludes it. The earlier
combat effects remain correct, but the initial pool placement was wrong.

Shockwave now lives with Finesse and Flash of Steel in `cards/colorless.py`.
It is removed from default Ironclad combat rewards, Ironclad transformations
and the authored uncommon shop slot. That slot now contains only Uppercut;
proper colorless merchant slots remain unimplemented. Shockwave joins the
restricted colorless transformation pool, and transforming Shockwave yields
another supported colorless card. All three existing transformation events
use this rule. Explicit custom fixture decks can still contain Shockwave.

Changed event/shop fingerprints reject preceding run snapshots; unchanged
card rules preserve direct combat compatibility. No public encoding changed.

Correction validation: **197 focused tests passed in 5.11s**, then the broad
headless/consumer suite passed **1,266 tests in 45.50s**. Compileall and diff checks
passed. The installed wheel, exercised outside the checkout with `PYTHONPATH`
unset, excluded Shockwave from default rewards and replayed its transformations
through Aroma, Morphic Grove and Whispering Hollow with exact JSON continuation.
Installed seed2/rest demos now yield generated/right/Neow defeat (0/80 HP, 184 gold,
91 commands), authored/left victory (15/94 HP, 236 gold, 123 commands), and
authored/right victory (20/104 HP, 332 gold, 121 commands). These seeded outcomes
change with the corrected pools and do not measure general policy strength.

Correction wheel SHA-256:
`70f743c275223e9083b3bafafe3b2961a3136b5b74efed646f8caaa2fa2cfc48`.
Compile/build took 0.40s and disposable installation 0.32s.
