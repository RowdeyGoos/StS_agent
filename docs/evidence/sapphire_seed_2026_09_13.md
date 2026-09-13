# Sapphire Seed, Sown and Guilty correction — 2026-09-13

## Implemented rules

Sapphire Seed is the tenth supported generated Overgrowth event. **Eat** heals
9 HP, capped, before mandatory selection of one upgradable permanent card.
**Plant** grants Sown (amount 1) to one eligible permanent card. Empty selections
resolve without a card effect, one candidate resolves automatically, and multiple
candidates expose exact card commands without cancel. Plant preserves upgrades
and card identity; Eat preserves any existing enchantment.

Sown grants 1 energy on the card's first completed play each combat. It runs after
card effects and selectors, before after-card enemy hooks. Energy must still be
available to pay the original card cost. Reshuffling/replaying does not trigger
again. The permanent instance stays untriggered; fresh combats clone that state,
while combat snapshots and search clones retain the current trigger state.
Killing the final enemy consumes the trigger without granting energy; player
death during the card skips the enchantment hook.

Per-card enchantment state contains an explicit definition ID, positive integer
amount and boolean trigger flag. Sown is nonstackable. Status, curse, quest,
unplayable permanent cards and already enchanted cards are ineligible. Ethereal
alone is not disqualifying. Existing internal `block` cards (Defend/Shrug It Off)
are native skills and eligible. Upgrade preserves enchantment; transformation
creates a fresh unenchanted card; removal removes the owned card and its modifier.

**Guilty correction:** an earlier source interpretation incorrectly treated
keyword 4 as Ethereal. It means Unplayable; Guilty has only that keyword. Guilty
now discards and reshuffles normally until its existing five-combat expiry.
Clumsy explicitly has keywords 4 and 2 and remains unplayable/Ethereal. The
[original evidence](event_pack_2026_09_13.md) is annotated rather than rewriting
its historical validation results.

## Source basis

Pinned game **0.107.1**, Steam build **23811903**, macOS `sts2.dll`, SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The [build manifest](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)
identifies the target. Evidence is bounded static metadata/IL inspection plus
headless execution; no game/profile/save/history access or live claim.

| Native member / token | Verified behavior |
| --- | --- |
| SapphireSeed variables `100689551` | Heal 9 |
| Eat async `100709232` | Heal before FromDeckForUpgrade(count1), then upgrade if selected |
| Plant async `100709234` | Filter through CanEnchant, mandatory one-card choice, Enchant<Sown>(amount1) |
| Sown.OnPlay async `100709498` | Status0 grants amount energy then sets Status1; subsequent plays skip |
| EnchantmentModel `100682376/377` | Nonstackable; reject types4/5/6, permanent Unplayable keyword4 and existing enchantment |
| CardModel.OnPlayWrapper async `100706385` | Card.OnPlay at1522, enchantment.OnPlay at1674, AfterCardPlayed at2038; player-death check precedes enchantment |
| PlayerCmd.GainEnergy `100712429` | Combat-ending guard prevents terminal energy gain |
| CardModel.DeepCloneFields `100682185`; EnchantmentModel.DeepCloneFields `100682390` | Independent enchantment clone retains mutable trigger state; owner/callback references are cleared |
| CardFactory.CreateRandomCardForTransform `100695706/707`; CardCmd.Transform `100712181` | Fresh canonical replacement is created and swapped without enchantment transfer |
| Guilty keywords `100692033`; Clumsy keywords `100691232` | Guilty only[4]; Clumsy[4,2] |
| CardKeyword enum metadata | Exhaust1, Ethereal2, Innate3, Unplayable4, Retain5, Sly6, Eternal7 |

## Validation and packaging

- Final broad affected suite: **1,228 passed in 44.20 seconds**, covering headless,
  simulation, analysis, engine, headless backends, content, lazy imports/package
  layout and CLI. Compileall and diff checks passed.
- Focused Sapphire/event pack/event combat checks: **92 passed in 4.78 seconds**;
  the later strengthened upgraded-Plant case is included in the final broad run.
  Tests cover no-effect/automatic choices, heal ordering, exact selection,
  Sown timing through Armaments, repeated plays, fresh fights, terminal behavior,
  unaffordable cards, transform loss and malformed/restored modifier state.
- Independent review closed with no blocking findings: 89 tests, 26 exact event
  decision continuations, source rules and search-clone ownership/state keys.
- Installed wheel checks ran outside the checkout with `PYTHONPATH` unset and
  confirmed imports from `site-packages`. Eat produced 49 HP and an upgraded
  Strike; Plant produced Sown and its expected first-play energy refund. Every
  event action and first combat play matched an independently restored clone.
- Three installed generated routes with an explicit Sapphire-only event pool
  completed all 16 rooms using synthetic combat wins: seed0/left/Ceremonial Beast
  (78 checks), seed2/right/Vantom (74), seed4/left/The Kin (76). The latter two
  ended with one and two enchanted deck cards respectively. These are progression
  checks, not demonstrations of policy strength.
- The natural installed default ten-event generated seed2/right/rest Neow demo
  completed Vantom at **15/94 HP, 199 gold, 186 commands**, with exact restore
  throughout. This is one seeded restricted-pool result, not a general win rate.
- The natural installed authored seed2/left/rest route remains an Act1 win at
  **11/94 HP, 236 gold, 124 commands**, with exact restore throughout.

Wheel SHA-256:
`e62954153e648667feb63812e7ead3ea72b32aa19f90adaad47871b72d92d273`.
Combined compile/build took 0.42 seconds; disposable installation took 0.33 seconds.
Implementation and review overlapped; separate phase timings were not measured.

## Compatibility and remaining work

Private run schema is now `headless_run_state_v16`, combat schema v7, and event
profile `supported_events_all_unlocked_v5`. Card fingerprints bind the enchantment
catalog; missing/older private state rejects. No public projection or bridge
change is required.

Other enchantments, duplication/replay card effects, full reward and transform
pools, native RNG parity and remaining events are still open. The
[engine guide](../HEADLESS_ENGINE.md#sapphire-seed-and-sown) describes extension
points; [next assignments](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment)
retain Byrdonis Nest's egg/hatch lifecycle and Luminous Choir's dependencies.
