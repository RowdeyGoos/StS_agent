# Continuous generated route traces — 2026-09-20

The pinned 0.107.1 native fixture now plays seed 0 from actual Neow offers through
16 Act 1 rooms, ending in **defeat against Vantom**. The 170 combat actions and all
recorded combat/reward/room boundaries match headless. Every Python action also
executes from a JSON-restored copy, checking identical snapshots and legal actions.
This is continuous native gameplay evidence through a loss, not a completed act
or a winning three-act campaign.

## Retained evidence and scope

- [Native route capture](native_generated_route_2026_09_20.json): pinned engine,
  assemblies, dependencies, fixture source hashes, build identity, timings,
  cleanup and complete selected path/actions/results.
- [First-combat regression capture](native_generated_start_route_regression_2026_09_20.json):
  the extended fixture's original `generated-start` mode still produces exactly
  the [previous accepted result](native_generated_start_verified_2026_09_20.json).
- [Replay](../../tests/headless/test_native_generated_route.py) verifies both
  executed source bindings and the action-by-action route. Historical matrix and
  earlier captures are preserved unchanged.

The route comprises 11 combats, three healing rests, an unopened chest and a
merchant exit without purchases. It claims native gold, selected cards and earned
relics, and skips potions. Relics at defeat are Burning Blood, Scroll Boxes,
Lantern and Ripple Basin; gold is 295. Final Rewards/Niche/Shuffle counters are
142/19/362. Comparisons include ordered hand and deck IDs/upgrades, player HP,
block and energy, living enemy IDs/HP/block, card reward offers and choices, relic
claims, inventory, gold and those three RNG counters. These fields do not expose
every native power, hidden pile or RNG stream.

The fixture uses real native card actions/executor and reward selection objects.
It invokes end-turn phases explicitly, uses mock localization/textures and
in-memory saves, asserts saving and uploads disabled, bounds actions/awaits and
runs cleanup in `finally`. Both retained executions had empty stderr and removed
their owned temporary user directories. No game project, profile or Cloud data
was loaded and no HP, kill or victory was injected.

## Corrected behavior

1. Chest offers pull from the shared relic bag only. A skipped offer remains in
   the player's bag; actual pickup removes both copies. Previously the unopened
   chest also depleted the player bag, changing the later elite reward from
   native Ripple Basin to Tiny Mailbox. Player reward/shop pulls retain their
   existing removal from both bags.
2. Inklet starts with Slippery 1. The first unblocked damage is capped at one and
   consumes the stack; subsequent hits apply normally.
3. Inklet's random follow-up branch orders Piercing Gaze before Whirlwind. The
   probabilities were equal before, but the reversed ordering changed exact
   seeded moves and later HP.

Private snapshot versions are now **combat v36 / run v55**. Both old versions
reject atomically; standalone combat snapshots must not reinterpret the corrected
Inklet RNG continuation. Independent source review confirmed the three behavior
changes and identified the standalone schema issue, which was corrected.

## Validation

The final native route build took 1.50 seconds and execution 1.81 seconds. The
legacy first-combat regression build took 1.59 seconds and execution 1.80 seconds.
The final affected integration batch passed **736 tests in 173.84 seconds** across
native RNG, chest bags, relic eligibility, Overgrowth encounters/routes, generated
start/route, rewards, endings and Act 2/3 progression. Six targeted chest, Slippery
and old-schema cases passed in 0.42 seconds during correction. After adding exact
room-entry comparisons, the two route/identity tests passed again in 12.47 seconds.
Compilation with the project Python environment, diff checks and all file links
in changed guides passed. An initial compile attempt used the system Python and
could not write its macOS cache directory; the project environment completed it.

The previous [repository-wide verification](headless_verification_2026_09_20.md)
remains the record for unrelated bridge/frozen-corpus failures; this batch does
not claim they are repaired. The full suite was not repeated. End-to-end
implementation and review elapsed times were not separately measured.

## Remaining limits and next implementation

At the ordinary-trace checkpoint, the fixture still needed a winning continuation
through Acts 2/3 and the Architect. The boosted trajectory below now exercises
that progression with an explicit HP override; ordinary-HP victory remains open. The ordinary trace avoids unknown rooms, leaves
shops and skips potions. Its single unopened chest did not establish repeated
chest cleanup; the boosted trace below now exercises three opened/skipped chests.
These traces remain distinct from Python synthetic progression tests and the
native prepared-ending matrix.

Fresh native shared bags also refill an initially empty requested rarity in
canonical order without RNG. Current headless exhaustion behavior, owned-item
filtering and unique treasure-history validation do not implement that boundary.
Add native exhaustion/filter/fallback cases and update generation, duplicate
pickup and persistence together. Do not infer native disk-save reload parity
from Python JSON continuation: native deserialized bags use different refill
configuration. This is an explicit remaining fidelity task, not part of the
ownership correction proved by this trace.


## Boosted three-act campaign

The user explicitly requested a high-HP test to reach a three-act win. The
[retained native capture](native_boosted_campaign_2026_09_20.json) sets current and
maximum HP to **1,000,000 once before Neow**, then wins Vantom, Knowledge Demon,
Test Subject and the Architect ending using actual combat and reward actions.
Natural healing, damage and max-HP loss remain enabled. This is a boosted gameplay
integration test, not evidence of an ordinary winning policy.

The route has **48 records: 35 combats, six rests, three opened/skipped chests,
one shop exit, two act transitions/Ancient choices and one victory**. It replays
**917 combat actions** plus three explicit Disintegration selections. The default
native test selector's null answer is not accepted as a Knowledge Demon choice:
the fixture queues index 0 and requires that answer to be consumed. Pael offers
Pael's Horn/Claw/Legion and chooses Horn; Nonupeipe offers Delicate Frond/Glitter/
Blessed Antler and chooses Frond. The three chest skips run completed native
`PickRelicAction`s and subsequent room exit clears voting state.

[Shared route replay](../../tests/headless/native_route_replay.py) checks every
recorded combat, room entry/exit, reward and transition boundary, restoring JSON
before and after each Python action. New native combat IDs bind once to headless
creation slots; native encounter ordering and dead-illusion retention do not
change public headless target indices. It also compares current and maximum HP
at each combat step. Final retained winning state is **999,533/999,986 HP**, 990
gold and 31 deck cards; Rewards/Niche/Shuffle counters are **435/118/1853**. Native
ending is recorded, the serialized winning HP is positive, and subsequent creature
disposal produces zero HP; headless retains the winning state with no legal actions.

The longer trace exposed these source-confirmed corrections:

- Parafright acts before Obscura, so Wail buffs it after that turn's attack.
  Random multi-hit targeting enumerates the same native encounter positions,
  while headless target slots stay stable.
- Bronze Scales installs the existing Thorns power at combat entry. It retaliates
  before incoming damage instead of through a late relic callback. A Scroll killed
  by Thorns still lands its current hit, but its removed Paper Cuts cannot reduce
  max HP. Surviving Scrolls still apply Paper Cuts once per unblocked hit.
- Fabricator evaluates its next move at the next player-side setup, after later
  bots can die. Its serializable pending roll is bound to the completed action
  in the active enemy continuation, rejects inserted/dropped flags, and clears
  without RNG on terminal cleanup.

Independent source review confirmed the native ordering and Thorns lifecycle,
then identified the deferred-roll ownership/terminal cases. Focused tests cover
those cases including a real reactive-draw pause and JSON restoration. Private
schemas move to **combat v37 / run v56**; older snapshots reject atomically.

The final native boosted execution took **2.78 seconds**, build **1.61 seconds**,
with zero stderr and successful owned-directory cleanup. Earlier attempts exposed
missing mock display text and are not accepted captures. Both ordinary modes
were freshly rerun: generated-start took 1.83 seconds (build 1.64), generated-route
1.89 seconds (build 1.65); their exact earlier results remain unchanged in the
[regression record](native_boosted_campaign_regressions_2026_09_20.json). Historical
captures are unchanged. The initial complete JSON replay passed in 83.90 seconds;
939 affected tests passed in 78.47 seconds. The final pass after snapshot hardening
passed 179 tests in 103.47 seconds, including the complete JSON replay, ordinary
mode regressions, native verification matrix and affected monster cases. Compilation,
diff checks and local file links in the changed guides also passed. Overall
implementation/review times were not separately measured.

This test avoids unknown rooms, skips potions and shop purchases, uses manual
native turn phases and mock persistence, and samples one Overgrowth path. It does
not verify every hidden power/pile/RNG field, live UI/vote scheduling, arbitrary
histories, an Underdocks trajectory or normal-HP winning play. Shared relic-bag
exhaustion/refill remains the separate limitation described above. The HP boost
is confined to the fixture and replay setup; ordinary game defaults are unchanged.

## Expanded Underdocks campaign and relic refill

The user clarified the acceptance scope on 2026-09-20: boosted native/Python
campaigns are valid simulator integration evidence, a normal-HP test-policy win
is not required, and multiplayer/alternate modes are excluded from the project.
This supersedes the earlier next-step wording above. Starting HP can change which
thresholds are reached; focused low-HP, death and revival cases remain alongside
these campaigns. Ordinary agent evaluation is still a separate objective.

The [expanded native trace](native_boosted_underdocks_2026_09_20.json) starts
Underdocks seed 1 with 1,000,000 current/max HP and uses actual earned resources.
Its **48 records** include **26 combats, 1,093 combat/potion actions, ten rests,
five shops, three chests, Sunken Treasury, two Ancient transitions and victory**.
It buys five cards, drinks seven potions and claims Bag of Preparation and Lantern
from chests. Phial Holster's Skill Potion remains unused. Pael grants Pael's Tears;
Tanx grants Throwing Axe. Lagavulin Matriarch, Knowledge Demon and Aeonglass are
beaten through actual native actions, followed by the Architect ending.

Every recorded run/combat boundary matches headless, including hand contents,
creature identities/HP/block, player current/max HP, energy/block, potion slots,
deck/inventory/gold and Rewards/Niche/Shuffle/Shops counters. Every Python action
also resumes from JSON. Final retained state is **999,161/999,955 HP**, **646 gold**,
25 deck cards and eight relics. Rewards/Niche/Shuffle/Shops counters finish at
**376/57/1636/140**. This is the second matching continuous three-act trajectory;
the previous Overgrowth trace remains intact.

This trace fixed two further source-confirmed rules:

- Phial Holster generates its starting potions through the native
  `CombatPotionGeneration` stream, rather than Rewards.
- Cubex's setup calls `GainBlock(13)` before `IsInProgress` becomes true. The native
  command returns without granting block; Artifact still applies. Headless now
  starts Cubex at zero block, matching the actual pinned lifecycle.

The fixture uses mock display resources and manual native turn phases. Chest
claims execute `PickRelicAction`, require a matching `RelicsAwarded` result, then
invoke the actual `RelicCmd.Obtain` used by the absent UI callback. This verifies
native voting/acquisition rules, not UI animation or scheduling. Native TestMode
suppresses three shop potion-price RNG draws. Coverage mode temporarily turns
TestMode off only around synchronous `MerchantPotionEntry.CalcCost`, restoring it
in `finally`. That method only computes prices and consumes Shops RNG. For this
trace, applying those draws after room entry is equivalent; this is not evidence
for arbitrary room-entry hooks which might themselves consume Shops RNG.

The final native run took **2.88 seconds**, build **1.64 seconds**, with empty
stderr and successful isolated-directory cleanup. The three existing modes were
freshly rerun with current sources and their exact previous results matched:
generated-start **1.82 seconds**, generated-route **1.97 seconds**, boosted-campaign
**2.86 seconds**, with builds **1.72/1.77/1.77 seconds**. The
[regression record](native_expanded_campaign_regressions_2026_09_20.json) binds those
executions to unchanged historical captures. Earlier diagnostic attempts exposed
mock-text gaps, a minion-targeting loop and Kaiser Crab's missing presentation
scene; none are accepted captures. This mode uses highest-HP targeting and a
bounded declared set of simple potion/card/event choices.

The separate [eight native relic-bag vectors](../../tests/fixtures/headless_relic_refill_vectors.json)
execute front/back refill, player exhaustion, nonempty caller filtering, empty
fallback, global eligibility purge and duplicate ownership. Existing eligibility
oracle outputs were rerun and remained unchanged. Production behavior now matches:

- Fresh shared bags refill only the requested physically empty rarity after
  global `IsAllowed` removal, in original pool order without RNG. Later fallback
  rarities and nonempty queues blocked only by caller filters do not refill.
- Player bags remain depleted. Ownership is not a global eligibility predicate;
  repeated offered/picked relics have independent IDs. Nonstackable pickup removes
  both bag copies; stackable pickup retains native bag semantics.
- Repeated chest history survives restoration. A persisted entry allocator
  boundary binds a claim to its newly acquired offered instance, rejects reopening
  an already claimed chest, and rejects pretending a preexisting copy was claimed.
- Source-backed duplicate effects cover independent Lizard Tails, Tungsten Rods,
  Pen Nibs, Vambraces, Unsettling Lamps, Strike Dummies, Miniature Cannons, Meat on
  the Bone, rest rewards, Gremlin Horns, Unceasing Tops and Lasting Candy. Candy
  upgrades remain attached to physical offer positions. Tiny Mailbox also now
  grants the native two potion rewards per instance. Aubergine gold sums per copy.

Private schemas are **combat v38 / run v57**. Fixture-profile uniqueness behavior
is retained where it was part of that declared fixture. Python JSON continues the
fresh native session semantics; native disk-loaded bags discard refill settings
and are not claimed equivalent. Independent semantic review covered bag rules,
duplicate consumers, chest forgery rejection, Phial RNG, Cubex and the fixture's
native award/price callbacks.

The new complete JSON trace and identity tests passed **2 tests in 96.61 seconds**.
Focused refill/duplicate cases passed **40 tests in 0.45 seconds**, then chest and
forgery coverage passed **55 tests in 7.88 seconds**. A broader affected run passed
**1,327 tests in 67.89 seconds** with one old Cubex expected-block assertion failing;
that assertion was corrected to the source/native-supported value. The final
regression run passed **127 tests in 99.62 seconds**, covering that correction,
the previous campaign traces, current fixture bindings and focused Phial/Cubex
cases. The already-passed expanded JSON replay was excluded from that repeat run.
Compilation, diff whitespace and changed-guide local-link checks passed. Overall
implementation/review elapsed times were not separately measured.

Remaining acceptance work is broader declared boosted boss/event/interaction
coverage, including native Kaiser Crab presentation support. These two paths do
not prove every seed, hidden power/pile/RNG field, arbitrary history or native
save-load behavior. The existing unrelated bridge/frozen-corpus full-suite
failures were not part of this change and the whole repository suite was not rerun.


## Kaiser Crab and third boosted campaign

The [retained native capture](native_boosted_kaiser_2026_09_20.json) follows
**Underdocks seed 0 → Hive → Glory → the Architect**, with the same single
1,000,000 starting/current-max-HP override. It records **48 boundaries, 35 combats
and 712 combat/potion actions**, including seven potion uses. Bosses are **Soul Fysh,
Kaiser Crab and Test Subject**. Tezcatara grants Yummy Cookie, with four explicitly
selected physical deck cards upgraded; Nonupeipe grants Delicate Frond. There are
six rests, one visited shop without purchases, and three opened/skipped chests.
The run ends at **999,385/1,000,000 HP**, 990 gold, 28 cards and eight relics.
Rewards/Niche/Shuffle/Shops counters are **435/67/1446/28**. Native victory and
post-victory disposal checks pass.

Native execution took **2.65 seconds**, after a **1.68-second build**, with empty
stderr and successful removal of the owned temporary user directory. Four tests,
including the full action-by-action replay with JSON restoration, passed in
**66.66 seconds**. The [fresh regression captures](native_kaiser_campaign_regressions_2026_09_20.json)
show exact unchanged results for generated-start, generated-route, boosted-campaign
and boosted-coverage. They retain each execution's compiled identity, timing and
cleanup; historical captures were not repinned. The affected Python regression
suite passed **595 tests in 286.29 seconds**, covering Underdocks, Hive, Ancient
relics, both preceding boosted JSON traces, ordinary generated traces and retained
verification bindings. The new complete Kaiser replay was not repeated in that
suite. The final five focused checks, including missing/unpinned extension
rejection before build or launch, also passed in **0.16 seconds**.

This adds only the presentation required for the native callbacks:

- The runner loads the pinned Spine framework through an authored fixture manifest.
  Real native `NKaiserCrabBossBackground` methods use an authored skeleton with
  empty named animations and an empty atlas. No game assets, PCK, autoload or game
  extension manifest are loaded; gameplay methods are not patched or replaced.
- Off-tree game/audio/shake nodes never execute `NGame._EnterTree` or `_Ready`.
  Both native arm death callbacks complete before the fixture clears the temporary
  singleton, ahead of progress/epoch notifications. The trace asserts two attached
  arms, two deaths, node cleanup and removal of listeners.
- Soul Nexus's actual synchronous death callback requires a non-null combat-room
  lookup. A pair of fixture listeners creates and releases an empty native visual
  room around that callback. The native lookup returns no creature visual. The
  trace asserts this callback ran once. This is a specific callback fixture, not
  general UI emulation.
- Native screen-shake setup/hits consume presentation-only `Rng.Chaotic`. The
  comparison concerns the recorded seeded gameplay streams, not that visual RNG.
  All persistence remains in-memory mock storage with uploads disabled.

The trace exposed a production bug before Kaiser: Soul Fysh's randomly inserted
Beckon used the native top-first index directly in Python's bottom-first draw pile.
It now converts the position while consuming the same single Shuffle draw. The
fixture RNG profile retains its prior ordering. A focused regression checks the
physical insertion and one-draw consumption. Private continuation schemas are
**combat v39 / run v58**; the preceding versions reject atomically.

An earlier diagnostic run let native TestCardSelector choose no cards for Yummy
Cookie. That is not accepted campaign evidence. The final fixture supplies four
eligible physical cards and asserts that the selector consumes them; Python
replays each selection and confirmation. Initial presentation and build failures
are diagnostic only. Independent semantic review covered the native callback
ordering, off-tree lifetime, user-data boundary, Beckon indexing/RNG and Cookie
selection legality. The reviewer independently reran the five focused identity,
insertion, schema and extension-rejection checks: **5 passed in 0.15 seconds**.
Compilation, whitespace and changed-guide local-link checks passed. The whole
repository suite was not rerun.

These three boosted campaigns cover seven distinct bosses. Remaining campaign
coverage includes Ceremonial Beast, the Kin, Waterfall Giant, The Insatiable, the
Queen and additional event
branches. They do not prove every seed, hidden power/pile/RNG field, arbitrary
history, real rendering/audio, native disk-save continuation or a winning policy.
Normal-HP policy victory remains unnecessary; low-HP/death/revival checks remain
relevant. Multiplayer and alternate modes remain excluded. Overall implementation
and review elapsed times were not separately measured.


## All regional bosses

Three additional captures complete the regional boss census for solo A0 Ironclad
on pinned build 0.107.1. All begin at 1,000,000 current/max HP with the actual
starter deck and native generated route, then play legal actions through the
Architect's recorded victory and cleanup.

| Capture | Bosses | Combats / actions | Final HP / max HP | Native build / execution |
| --- | --- | --- | --- | --- |
| [Overgrowth 1](native_boosted_overgrowth_1_2026_09_20.json) | Ceremonial Beast, The Insatiable, Queen | 26 / 618 | 998657 / 999991 | 1.60s / 2.61s |
| [Overgrowth 3](native_boosted_overgrowth_3_2026_09_20.json) | The Kin, The Insatiable, Queen | 28 / 700 | 998076 / 999972 | 1.61s / 2.96s |
| [Underdocks 4](native_boosted_underdocks_4_2026_09_20.json) | Waterfall Giant, Knowledge Demon, Aeonglass | 27 / 600 | 999345 / 1000012 | 1.64s / 2.38s |

Together with the preceding three captures, this covers **all 12 regional
bosses**. The added routes exercise Sunken Statue's sword, Trash Heap's dive,
Colossal Flower's first extraction, Amalgamator's two-Strike combination and
Slippery Bridge's first removal. They include 30 smith upgrades, 14 potion uses,
12 shop purchases and five chest claims. Sea Glass explicitly selects zero cards;
Yummy Cookie and Amalgamator explicitly select physical cards. The Insatiable is
beaten using Frantic Escape and earned upgrades; earlier diagnostic policies died
to Sandpit despite boosted HP, and those attempts are not victory evidence.

The retained native traces exposed and now regress:

- Neow and later Ancient EventRooms consume one room-set event position.
- Trash Heap and Doll Room fixed-pool relic choices use the event RNG.
- Gas Bombs occupy native positions before Living Fog while Python keeps stable
  target indices; random-target selection follows native position order.
- Summons during AfterDeath exclude the still-present dying parent's maximum HP
  from the unique-HP candidate set, without excluding previously removed corpses.
- Stone Cracker upgrades in every combat, with native top-first StableShuffle;
  Whetstone and War Paint use native card sorting before Niche shuffle.
- Pending combat rewards record their generation-time Amethyst Aubergine owners.
  Main/extra reward claims and Pael's Wing pickups preserve the generated gold,
  including pre-existing duplicate owners; malformed source IDs reject atomically.

Independent source review also identified Ceremonial Beast skipping its mandatory
stun when Thorns crosses the threshold during Plow, retaining temporary Strength
wrappers at that transition, and Waterfall Giant retaining ordinary powers after
revival. Focused JSON regressions cover these corrections; those exact edge cases
are source-reviewed tests rather than separate native runtime vectors.

The fixture supplies mock event text, scoped off-tree screen shake for
Amalgamator, explicit legal selectors, and strongly retained mock textures. It
executes actual native rules; no game PCK/assets/autoload, profile, persistent
save or upload access is used. Each capture has empty stderr and verifies removal
of the temporary custom user directory and presentation cleanup. Input cards are
recorded before play so post-victory War Hammer upgrades cannot rewrite the
recorded input. Headless gold bundles compare to the sum of native gold rows.

[Five fresh baseline executions](native_boss_campaign_regressions_2026_09_20.json)
match all retained generated-start, generated-route, boosted-campaign,
boosted-coverage and boosted-kaiser results exactly. Historical capture identities
remain unchanged. Current private continuation formats are **combat v40 / run
v59**; previous formats reject atomically.

The affected monster, Ancient, event, relic and prior native-campaign regression
selection passed **1,567 tests in 443.35s**. Independent semantic review covered
native timing/RNG changes and the reward continuation boundary; its final six
Aubergine cases passed in 0.29s. After the final generation-time gold fix,
**387 reward, event-combat, Ancient and new campaign tests passed in 209.19s**,
including all three complete native/headless replays with JSON continuation at
every action. These selections overlap; their counts are not a unique total.
`compileall`, diff checks and added local documentation links pass. Overall implementation,
review and user-wait times were not separately measured. Remaining acceptance is
broader ordinary-event branches and inventory interactions, plus hidden native
power/pile/RNG comparisons where useful. These six paths do not establish every
seed or branch, rendering/audio, native disk-save continuation or a winning policy.
Normal-HP victory remains unnecessary; low-HP/death/revival tests remain in scope.
Multiplayer and alternate modes remain excluded.
