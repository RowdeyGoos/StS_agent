# Byrdonis Nest, Hatch and colorless cards — 2026-09-13

## Implemented rules

Byrdonis Nest is the eleventh supported generated Overgrowth event. **Eat** gains
7 maximum and current HP. **Take** adds Byrdonis Egg, an unplayable quest card with
no upgrade and no Ethereal/Eternal keyword. It discards normally and can be removed
or transformed. Normal event selection excludes players with an egg or event-pet
relic; the native exhausted-pool fallback can still repeat the event.

An egg offers **Hatch** at a rest site, alongside Rest and any available Smith.
Hatch consumes the site's action, grants a fresh owned Byrdpip relic and transforms
all permanent eggs into fresh base Byrd Swoops at their original deck positions.
Unrelated cards retain their exact state. Repeated hatches grant separate relic
instances. Rest/Smith can be chosen instead, retaining eggs for later sites.

Byrd Swoop is a zero-cost attack dealing 14/18 damage without Exhaust. Its damage
uses the player's Strength/Weak and target modifiers. The native pet acts as its
visual attacker; its own idle move loop has no gameplay effect. We retain the
relic's gameplay ownership without a cosmetic creature/skin. In-combat acquisition
of this relic is explicitly unsupported; the implemented rest-site path is outside
combat. Future pet-affecting content must implement its concrete creature rules.

Egg and Swoop random transformations use colorless cards. The restricted supported
pool is **Finesse** (0 cost, 4/7 block, draw 1) and **Flash of Steel** (0 cost, 5/8
damage, draw 1), also excluding the source when transforming either colorless card.
Aroma, Morphic Grove and Whispering Hollow share the pool rules. These cards are
not added to the Ironclad combat reward pool. Full native colorless pools and RNG
parity remain open.

## Source basis

Pinned game **0.107.1**, Steam build **23811903**, macOS `sts2.dll`, SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The [build manifest](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json)
identifies the target. Evidence is static metadata/IL inspection and headless
execution, not a live-game demonstration or profile/save/history inspection.

| Native member / token | Verified behavior |
| --- | --- |
| ByrdonisNest initial options `100689259`, vars `100689261` | Eat / Take; maximum HP 7 |
| Eat async `100709002`, Take async `100709004` | Gain maximum HP; create egg in permanent deck |
| IsAllowed `100689260` / lambda `100709001`; HasEventPet `100696056` | Exclude owned pet relic or permanent egg |
| ByrdonisEgg constructor `100691119`, max upgrade `100691120`, keywords `100691121` | Cost -1, quest type, no upgrades, only Unplayable keyword 4 |
| CardModel.IsRemovable `100682146`, IsTransformable `100682147` | Eternal keyword 7 is the exclusion; egg/swoop remain eligible |
| Egg.TryModifyRestSiteOptions `100691122`; Hatch.OnSelect async `100711680` | Add Hatch; obtain Byrdpip and consume rest action |
| Byrdpip.AddsPet `100683253`; AfterObtained async `100706552` | Pet relic; transform every egg into Byrd Swoop |
| CardCmd.TransformTo `100712183` | Fresh canonical base instance, same deck position |
| ByrdSwoop vars `100691124`, upgrade `100691126`, play async `100709683` | Damage 14 +4 upgraded; player-owned attack with visual pet animation |
| DamageCmd.FromCard `100697508`, WithAttackerAnim `100697515` | Owner remains actual attacker; pet is visual attacker only |
| Byrdpip monster move loop `100687322`; GetPossibleTargets `100697490` / predicate `100712585` | Idle self-loop; player-target attacks exclude nonplayer pet |
| CardFactory.GetDefaultTransformationOptions `100695705` | Quest and special/event rarity sources use ColorlessCardPool |
| Finesse vars `100691801`, upgrade `100691802`, play async `100710003` | Block 4 +3; draw 1 after block |
| FlashOfSteel vars `100691829`, upgrade `100691831`, play async `100710029` | Damage 5 +3; draw 1 after attack |

## Validation and packaging

- Focused Nest/event pack/Sapphire/event combat suite: **127 passed in 5.28s**.
  The 35 new tests cover all branches, multiple eggs, alternative rest actions,
  modifiers, actual card draw, unplayable discard, removal, all three transform
  events, pet eligibility/fallback, custom catalogs and atomic malformed restore.
- Broad affected suite: **1,263 passed in 46.68s**, covering headless, simulation,
  analysis, engine, headless backends, content, package layout/lazy imports and CLI.
  Compileall and diff checks passed.
- Independent semantic review closed with no remaining blockers. It verified the
  native rules, 35 focused tests in 0.20s, 12 JSON colorless continuations and probes
  for stale hatch ownership and custom-catalog pickup. Review corrections normalized
  item fingerprints for JSON, threaded the owned catalog through relic claims,
  and bound the new hatch relic to its prior inventory.
- Installed wheel checks ran outside the checkout with `PYTHONPATH` unset and
  confirmed `site-packages` imports. Eat produced 47/87 HP from 40/80; Take then
  Hatch produced Byrdpip/Swoop and a 14-damage first play. Each action matched an
  independently restored JSON clone.
- Three installed generated routes with an explicit Nest-only event pool completed
  all 16 rooms using **synthetic combat wins**: seed0/left/Ceremonial Beast (78
  checks, no hatches), seed2/right/Vantom (72 checks, one hatch turning two eggs
  into Swoops), seed4/left/The Kin (74 checks, two hatches/two Swoops). These check
  progression and fallback, not policy strength.
- The natural installed default eleven-event seed2/right/rest Neow demo reached
  the boss and **lost**, at 0/94 HP, 132 gold and 172 commands. It owned Byrdpip;
  all 16 room entries and every decision restored exactly. The added event changes
  this seeded demo's content and outcome; no win-rate claim is made.
- The natural installed authored seed2/left/rest demo still completed Act 1 at
  **11/94 HP, 236 gold, 124 commands**, with exact restore throughout.

Wheel SHA-256:
`e18ba1c56ae1f1ab4e4c255392dd6aad5ad26cc1ca25f739d95b6b2478cb181f`.
Compile/build took 0.44s; disposable installation took 0.31s. Implementation and
review overlapped, so separate phase durations were not measured.

Private run schema is `headless_run_state_v17`, event profile
`supported_events_all_unlocked_v6`, and combat schema remains v7 with a new content
fingerprint. Older private snapshots reject; no bridge/projection changes are
required. See the [engine guide](../archive/HEADLESS_ENGINE_2026_09_22.md#byrdonis-nest-and-hatch) and
[remaining implementation queue](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
