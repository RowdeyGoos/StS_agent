# Four-event headless pack — 2026-09-13

## Scope and behavior

Whispering Hollow, Wellspring, Slippery Bridge and Sunken Statue extend the default
restricted generated Ironclad A0 event pool from four to eight definitions. Both
branches of each event are implemented, including their required card/relic
behavior. Authored routes retain their explicit earlier pools. This is static
native-source inspection plus synthetic and installed headless evidence; no live
game, profile, save or history access was used.

| Event | Implemented branches |
| --- | --- |
| Whispering Hollow | Entry requires 44 gold. Pay an entry-time 26–44 gold price for two optional potions, or transform one card and then take 9 damage. |
| Wellspring | One optional potion, or mandatory one-card removal followed by one Guilty. An empty deck still receives Guilty. |
| Slippery Bridge | Entry requires floor >6 and a removable card. Remove the offered card, or pay escalating 3/4/5… damage and reroll. Initial offers prefer nonbasic cards; later candidates exclude the previous definition and skipped instances, with all-removable fallback. Lethal damage still consumes its reroll. |
| Sunken Statue | Receive Sword of Stone, or gain an entry-time 101–121 gold before taking 7 damage. |

Shared potion rewards support partial collection, full-inventory rejection,
discard to free space, and finishing with unclaimed rewards. Claimed then discarded
potions cannot be claimed again. Mandatory deck selections automatically resolve
zero/one candidates and retain exact original identities for multi-card decks.

Guilty is unplayable and Ethereal, with an owned master-deck lifetime of five
completed combats. Clumsy is unplayable and Ethereal without expiry. Curse
transformation uses the supported Guilty/Clumsy subpool, excludes the original
definition and resets the new card's lifetime. Sword of Stone counts elite
victories independently per owned instance; the fifth replaces it in place with
a fresh Sword of Jade, which grants 3 Strength at combat start. Duplicate sword
instances are allowed and each contributes its own effects.

## Native basis

Pinned assembly: Steam build **23811903**, game **0.107.1**, macOS `sts2.dll`,
SHA-256 `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Read through the existing bounded metadata/IL scanner; no assembly execution.
The existing [build manifest](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)
identifies the target. Metadata tokens below identify the exact methods, including
async state-machine bodies where the substantive effects execute.

| Type / methods | Tokens and observed rules |
| --- | --- |
| WhisperingHollow | `100689829`, `100709444`: gold eligibility; `100689830/831`: 35 + NextInt(-9,10); `100709445`: payment/two PotionRewards; `100709447`: transform before 9 damage |
| Wellspring | `100689823`: one Guilty; `100709440`: random unlocked shared/character potion offer; `100709438`: removal then curse; `100709436`: curse grant |
| Guilty / Clumsy | `100692030–033`, `100710118`: unplayable, Ethereal, five-combat master-deck expiry; `100691231–233`: Clumsy cost/keyword/no upgrades |
| SlipperyBridge | `100689572/574`, `100709250/251`: damage and entry predicate; `100689577/582/583`, `100709252/253`: candidate rules; `100709254/256`: hold/reroll and removal |
| SunkenStatue | `100689606–609`, `100709278`: gold scalar/range, choices and gold-before-damage |
| SwordOfStone / SwordOfJade | `100684681–683`, `100707064`: five elite wins then replacement; `100684674`, `100707062`: 3 Strength on combat entry |
| Relic ownership | Player.AddRelicInternal `100696092` permits duplicate instances; RelicCmd.Obtain `100712471` uses IsStackable for pool handling, not ownership rejection; Replace `100712475` removes and obtains at the original index |

## Validation

- Broad affected suite: **1,171 passed in 40.31 seconds**, covering headless,
  simulation, analysis, engine, headless backends, content, packaging/imports and
  the headless CLI. This preceded the final focused lifetime/restore correction.
- Final focused event/Aroma/Morphic regression: **114 passed in 5.79 seconds**,
  including forged fresh-curse counters, missing relic counters, stale actions,
  failed-action atomicity, full inventories, lethal branches, empty/single decks,
  repeated bridge fallback and five-combat/five-elite lifecycle transitions.
- Independent semantic review closed without remaining blockers. It checked
  native branch scalars/order, duplicate sword ownership and evolution, 97 event
  continuations, five-fight Guilty expiry and fresh-curse restore rejection.
  Review corrections now have committed regression tests.
- `compileall` for `game` and `tests` passed. Installed package checks ran outside
  the checkout with `PYTHONPATH` unset and confirmed `site-packages` imports.
- Installed eight-branch exercise passed **43 exact continuation checks**,
  including event acquisition through combat, Guilty expiry and Sword of Jade's
  next-combat Strength. Combat wins in this exercise were synthetic.
- Three installed generated routes completed all 16 rooms with synthetic combat
  wins: seed 0/left/Ceremonial Beast (79 continuation checks), seed 2/right/Vantom
  (74), seed 4/left/The Kin (75). These validate progression, not policy strength.
- Natural installed authored seed-2 left/rest demo still completes Vantom:
  11/94 HP, 236 gold, 124 commands, exact restore throughout.
- Natural installed generated seed-2 right/rest Neow demo now reaches 16 rooms
  and ends in defeat: 0/94 HP, 99 gold, 195 commands, five events resolved, exact
  restore throughout. The prior four-event pool's win remains historical evidence;
  expanding the pool changes seeded event assignments and the demo policy outcome.

Wheel: `sts_agent-0.1.0-py3-none-any.whl`, SHA-256
`9da66b94d905be46d004c996ea4e0307aba5e073a40c0e43f23f910c708b0755`.
Offline wheel build took 0.49 seconds and disposable installation 0.39 seconds.
The initial installed helper assumed every unconfigured combat creates a reward
phase; it stopped on an illegal LeaveRewards. Correcting that helper to leave
only when offered produced the successful eight-branch result; no gameplay fix
was required.

## Boundaries and continuation

Potion rewards uniformly sample the supported **Fire/Block** pool, not the full
native weighted/unlocked distribution. Curse transforms support **Guilty/Clumsy**,
not the full native curse pool. Eternal, curse prevention/replacement and other
item hooks remain open. All currently modeled permanent cards are removable;
Slippery Bridge with an empty deck is explicitly unsupported, including an
exhausted-pool fallback that would select it. Native RNG algorithm/stream parity
and multiplayer remain unverified.

Private run snapshots are now `headless_run_state_v14`; nested combat snapshots
are `headless_combat_state_v6`. Both bind the new lifetime/counter semantics and
reject older private formats. The event progression profile is
`supported_events_all_unlocked_v3`. No bridge/projection/encoding work is included.

The [engine guide](../HEADLESS_ENGINE.md) describes the implementation boundaries;
the [implementation queue](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment)
assigns the next event-combat and content dependencies.
