# Bridge support and status

Updated 2026-09-27 for shared-producer shop, rest, treasure, event and ending
coverage; other capability review remains
2026-09-19 against bridge source, pinned native game IL and retained evidence. Latest live
session: **2026-09-27**. This is the authoritative summary of bridge support;
[usage](../bridge/Sts2AgentBridge/README.md), [technical contracts](GENERIC_EVENTS.md),
[caller evidence](EVENT_COVERAGE.md) and [priorities](../ROADMAP.md) have separate roles.

Quick navigation: [supported interactions](#supported-interactions) ·
[known failures and limits](#known-failures-and-runtime-limits) ·
[missing features versus remaining tests](#implementation-gaps-versus-remaining-live-tests) ·
[release and evidence](#release-and-latest-evidence).

The [Trial Merchant/Innocent case](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#trial-curse-and-two-upgrades-passed)
passed **5/5/5**, with fifteen controller reads and nothing pending. Shame was
observed before the fixed-two selector; two original Strikes gained one upgrade,
with all other cards and inventory unchanged through map return. Both named
Trial selector branches now have live evidence. Cleanup passed by **16:55:30 UTC**,
with zero overlays and all 429 base files unchanged.

The [Punch Off full-belt Potion Belt case](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#punch-off-capacity-first-potion-belt-passed)
passed **17 attempted / 16 accepted / 16 reconciled**, with one non-mutating stale
rejection, 234 controller reads and nothing pending. Belt added two empty slots
before either potion claim; the three originals were preserved and two distinct
Fire Potions filled the new slots. Gold, Whirlwind and map return completed.
This adds terminal reward evidence to the earlier Repy event **6/6/6** pass.
Cleanup passed by **16:44:24 UTC**, with zero overlays and all 429 base files unchanged.

The [New Leaf / empty-belt Phial Holster case](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#neow-new-leaf-and-empty-belt-phial-holster-passed)
passed **6/6/6**, with 53 controller reads and nothing pending. The selected
Strike became Body Slam, Holster added Attack and Weak potions, and Writhe and
map return completed. Other originals, HP and gold were unchanged. Cleanup passed
by **15:31:24 UTC**, with zero overlays and all 429 base files unchanged.

The corrected [full-belt Phial Holster case](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#neow-precarious-shears-and-full-belt-phial-holster-passed)
also passed **7/7/7**: two exact Strike removals, fourth slot/Explosive Ampoule,
preserved original potions, Injury and map return. The preceding **6/5/4** failure
remains unreconciled under its original artifact; fresh passes do not adopt it.

The [Neow offer/upgrade case](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#neow-lead-paperweight-and-pomander-passed)
passed **7/7/7**, following bundle/removal at **8/8/8**. These results retain manifest
`14772d59…`, as does the stopped Holster attempt and its **14:32:26 UTC** cleanup.
Seeded Custom-mode cases used no modifiers and console setup before attachment.
The prior empty-grid **5/5/3** failure and Hefty Tablet/Kaleidoscope **9/9/9** result
retain their own original release.

## How to read support

**Implemented** means the adapter/controller exists within the stated bounds.
**Live demonstrated** means a representative native interaction passed, often with
console/UI-assisted setup; it does not certify every caller, branch or full run.
**Offline only** means fixtures/integration checks passed without that live case.
A **known live failure** is neither missing code nor accepted working behavior.

There is one production bridge, `bridge/Sts2AgentBridge/apps/bridge/`. It supports
bounded interactions and a live-demonstrated campaign traversal controller.
The user accepted milestone 7's assisted campaign with one recorded bridge-fix
reload; normal-HP policy strength remains unmeasured. Shared event mechanisms discover
supported requests at runtime; there is no blanket event-name allowlist. Automatic
parent effects generally remain `unverified` even when a child effect and map return
are verified. Final Proceed does not erase earlier verified child results.

The new native `agent_v2` / `full_run_v2` candidate connects rich observations and
nested decisions to the same public-only chooser as headless. Its first controlled
rest/card-reward/map path and an assisted saved continuation through the Architect
and native Victory passed live; broader v2 acceptance remains open. Its [coverage and remaining gaps](AGENT_CONTRACT.md#native-full-run-v2-candidate)
now include hand/optional combat choices, general potion use/discard and owned
selectors, chest claims/empty chests, reward reroll/sacrifice, shop removal cancel,
automatic relic effects, Cauldron/Orrery rewards and shared event reward children.
An opt-in public live journal is implemented; no live corpus was collected for
this development. The [broader live batch](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md)
demonstrated reroll, map potion use/discard, chest claiming, potion-owned hand and
optional offers, and the first Sacrifice. The corrected Whetstone-granting
Sacrifice passed its saved-run retest: **4/4/4 actions**, five reads and an actionable
map, with no pending action. Full-producer shop-removal preview cancellation also
passed: **5/5/5 actions**, unchanged gold/deck and map return. Neow’s Bones then
passed its Large Capsule/Lost Coffer chain, nested Sacrifice and final curse:
**7/7/7 actions**, 53 controller reads and map return with no pending action.
The corrected full-producer Red Mask purchase also passed: **3/3/3 actions**, four
controller reads, exact payment/pickup and map return. Kifuda then passed its
three-card pickup selector: **7/7/7 actions**, 25 controller reads, exact Adroit 3
effects and map return. A further batch demonstrated Dolly’s Mirror, Potion Belt
with both added slots filled, and Cook with deselection/reselection: **45/45/45**
including the legal intervening map travel. Lift, Kindle, Clone, Hatch and Dig
then passed in one Miniature Tent visit, followed by Smith deselection/reselection
at the next connected rest site: **24/24/24** including travel. Yummy Cookie's
four-card upgrade selector then passed **7/7/7**, with exact upgrades, retained
unselected cards/inventory and map return. Punch Dagger's corrected single-card
preview then passed **7/7/7**, including deselection/reselection, exact Momentum 5
on the original Bludgeon+ and map return. Its earlier **2/2/0** failure remains
bound to the preceding package; the successful retest does not reconcile that attempt.
Gnarled Hammer then passed **7/7/7** with three Sharp 3 originals; legal travel
and an exact-inventory zero-purchase shop exit brought that batch to **25/25/25**.
Royal Stamp then passed **7/7/7**, including deselection/reselection and exact
Royally Approved, Innate and Retain on the original Defend+. All five supported
shop card-selector families now have a representative successful live case.
Orrery's five card rewards and automatic return to the shop then passed through
map return at **13/13/13**; later legal travel reached another merchant at **28/28/28**.
Cauldron's corrected full-belt replacement test also passed **13/13/13**, collecting
all five potions while protecting newly collected items. Its earlier **3/3/2**
helper/deadline stop remains a separately recorded failed attempt.
The ledger preserves the
earlier Whetstone failure at **36/36/35** and shop failure at **1/0/0** under their
original artifacts. Prior rest cancellation and potion-reward evidence retains
its separate package identity.

## Supported interactions

### Combat, map and rooms

| Interaction | Implemented scope | Live evidence and limits |
| --- | --- | --- |
| Combat → rewards → map | Bounded combat, gold/card/item rewards, card choice or Skip, actionable-map check | Both card policies demonstrated; assisted campaign traversal accepted under the scope below |
| Shared agent contract/policy | `agent_v1` public projection and the same public-only chooser as headless; owned combat/selection/reward/map dispatch | Controlled Neow's Fury two-card selection, combat, gold/reward leave and separate map transition demonstrated with one shared callback. Live card-offer selection and wider content remain unverified; see the [native producer contract](AGENT_CONTRACT.md#native-producer) |
| Campaign traversal | Prepared Ironclad A0 entry, persistent process budgets, versioned native act/ending transitions, rest/shop/treasure/event/combat orchestration | Milestone 7 accepted by the user: upfront-assisted potion campaign, all gameplay by policy, one Waterfall Giant correction/reload, then all three bosses and the ending. Original continuation flags and earlier failures remain recorded; shared v1 coverage is unchanged |
| Combat potion use | `combat_potions_v1`: 15 ordinary types, exact native inventory/target/task binding; campaign collects and uses eligible potions | Four uses of Fire, Strength and Vulnerable potions reconciled in the fresh assisted run under v5. The other 12 types remain offline only; the v6 continuation commanded no potions |
| Visible infinite enemy HP | Combat schema 2 represents the native infinity display with null numeric HP; campaign v6 conserves potions and ends turns when all enemies are infinite | Saved Waterfall Giant retest passed: 25/25/25 combat actions, native victory, rewards and Act 2 entry. The same controller continued through both remaining bosses and the native ending |
| Combat card choices | Owned discard/exhaust selections, including optional zero confirmation; v2 adds visible Draw grids; v3 adds mandatory one-card offers | Neow’s Fury zero/two-card choices and resumed victory demonstrated. Repeated Séance Draw selections and enclosing victories passed through Act 3. Three Knowledge Demon offers reconciled, followed by its boss victory and the ending. Other fixed/exhaust callers remain offline only |
| Map and room handoffs | Public legal map actions and bounded event/combat-to-map verification | Representative map/next-room transitions demonstrated; composite `*-map` clients verify the map but do not select a node |
| Rest | Heal/Proceed and Smith (one card); Lift, Kindle, Dig, Cook, Clone and Hatch. Packaged `rest_v3` exposes selector cancellation and Heal-owned rewards | Every supported single-player option has a representative successful live case. Smith/Cook cancellation and deselection/reselection, Dream Catcher card collect/Skip, Tiny Mailbox two-potion collection and remaining Miniature Tent options demonstrated. Exact per-option limits remain below |
| Shop purchases | Cards, potions, supported passive relics, Potion Belt +2 slots; 0–8 purchases, kind policy, gold reserve and callback-certified restock | Seven-card/one-potion visit and three restocked potion purchases with original-potion replacement demonstrated. Full-producer passive, selector and Belt pickups passed through map return; Belt expanded a full inventory from three to five slots and both added slots were filled. Zero-purchase Close/Leave passed 2/2/2 with exact inventory preservation. Remaining pickup and policy variants need live coverage |
| Shop removal | Exact selected original, price/effect reconciliation, preview cancellation, then separate inventory close and Leave | Removal and full-producer preview cancellation demonstrated through map return; cancellation retained exact deck and gold |
| Shop-owned rewards | Cauldron's five potions and Orrery's five card menus under the purchase owner | Both passed 13/13/13 through purchase, all five rewards, automatic shop return and Close/Leave. Orrery added five exact cards while preserving the original deck, HP and potions. Cauldron replaced five original potions, protected newly collected items including a distinct same-key potion, and preserved the deck/HP. Earlier helper stops and Cauldron's unresolved 3/3/2 attempt remain in the ledger |
| Shop pickup selectors | Dolly’s Mirror, Gnarled Hammer, Kifuda, Punch Dagger and Royal Stamp; exact native clone/enchantment selection | All five have representative live success: Kifuda’s three Adroit 3 originals; Mirror’s exact Bludgeon clone; Punch Dagger’s Momentum 5 on Bludgeon+; Hammer’s Sharp 3 on two Bludgeon+ originals and Headbutt+; Royal Stamp’s Royally Approved/Innate/Retain on Defend+. Punch Dagger and Stamp included deselection/reselection. All paid exactly and returned to the map, retaining other cards/HP/potions. Zero/fewer-card or toggle variants not separately demonstrated remain offline only. Other pickup callbacks are not generally supported |

### Native rest-site actions

These are actual options in the pinned game, with their enabling callers checked
in native IL. Availability still depends on the current run. The bridge supports
ordinary Heal and Smith, plus the six additional single-player options in source.
The new rest flow has its own native effect and selector checks.

| Option | Native source / trigger | Native behavior | Bridge |
| --- | --- | --- | --- |
| Heal | Default rest option | Heal, then run rest hooks and any generated rewards | Ordinary Heal/Proceed, Dream Catcher card collect/Skip and Tiny Mailbox potion collection demonstrated |
| Smith | Default rest option | Select and upgrade **one** card | Ordinary upgrade and `rest_v3` cancellation before selection/from preview demonstrated. Full-producer deselect/reselect of the same Bludgeon, exact +1 upgrade and map return passed at 6/6/6 |
| Dig | Shovel | Obtain a relic directly, including its pickup callback | Bag of Preparation pickup, exact relic append and unchanged HP/gold/deck/potions passed live. One owned deck/enchantment selector of up to three cards is implemented; other follow-up surfaces stop |
| Lift | Girya, fewer than three lifts | Increase its lift counter, granting Strength in later combats | Counter 0 → 1 and unchanged unrelated inventory passed through the full producer |
| Cook | Meat Cleaver | Remove two cards, gain nine max HP; native selection can be canceled | Immediate and two-card preview cancellation demonstrated. Successful Decay/Defend+ removal, deselection/reselection, HP 88/88 → 97/97 and map return passed through the full producer at 7/7/7 |
| Clone | Pael’s Growth | Copy the deck’s Clone-enchanted cards | One exact upgrade-0 Clone-enchanted Bludgeon copy passed live, preserving originals and other inventory. Scoped native insertions include add-time upgrades; those variants remain offline only |
| Kindle | Pumpkin Candle | Add five to its remaining combat counter | Counter 5 → 10 and unchanged unrelated inventory passed through the full producer |
| Hatch | Byrdonis Egg card | Obtain Byrdpip and transform every egg into Byrd Swoop | One egg transformed to Byrd Swoop, exact Byrdpip append and preserved survivors passed live. Multiple-egg coverage remains offline only |
| Mend | Generated only with multiple players | Target and heal another player | Outside the current single-player bridge scope |

The six new options use `rest_v2` on the existing room-flow routes. They are
implemented, validated offline and included in the current package. All six have
representative successful live results; Cook cancellation also passed. The
[five-option batch](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#remaining-rest-options-and-smith-toggle-passed-2026-09-26)
verified Miniature Tent retaining choices between completed options. A flow
starts with at most 64 deck cards, executes one option, waits for the native effect
and rest continuation, verifies hook removal, then returns at the rest site without
pressing Proceed. Remaining Miniature Tent choices stay available for the next
interaction. Cook precommits two original deck slots; the client defaults to the
first two removable cards and accepts an explicit pair. Dig's one-selector pickup
policy selects the first eligible originals up to the native maximum (at most
three); arbitrary popup/reward/multiple-selector follow-ups remain unsupported.

Validation covers real Harmony with inert native surfaces, Python/C# integration,
shared-client loopback tests, and the affected shared card-input fixtures. These
checks do not establish live animation or relic coverage.

The packaged `rest_v3` route uses that same exclusive room module and shared
card/reward drivers. Each selection and reward is a separate callback decision;
the parent settles only after native completion and return to the same rest room.
Smith/Cook cancellation verifies the unchanged deck/inventory and restored option
controls. Heal owns the exact reward set and card menu: taking the last reward can
close it automatically, while card Skip returns to the reward parent for separate
dismissal. Unopened card offers are hidden. Full-belt replacement and arbitrary
additional reward kinds remain outside this route. Representative cancellation and
reward collection/Skip cases passed live; this is not the native `full_run_v2` producer.
[Usage and contract](../bridge/Sts2AgentBridge/README.md#rest-options)

Full-profile `rest_v4` now allows 128 starting-deck cards and selector originals,
matching the shared run inventory. Clone's predictable result must fit that bound
before any option is published or clicked; overflow stops explicitly without
hiding native actions. Legacy v2/v3 keep their 64-card entry bound. Completed
rest/shop receipts are returned before reading the successor surface. These
corrections passed a saved-run rest cycle: the shared policy reached 86 cards
through Clone, then returned to the map at **14/14/14**, with nothing pending.
The 128-card selector endpoint remains fixture evidence.

**Smith correction:** its constructor sets `SmithCount = 1`. An assembly-wide
IL scan found no call to `set_SmithCount` and no other write to its backing field
outside the constructor/property setter. The bridge’s `SmithCount != 1` guard
is a defensive limit, **not evidence that multi-card Smith exists in gameplay**.
Multi-card event upgrades are real: Trial/MerchantInnocent selects two and
Yummy Cookie selects four. [Audit scope and source anchors](EVENT_INTERACTION_MAP.md#native-capability-audit-september-19)
record the distinction.

### Event choices and card surfaces

These are generic-event capabilities; their wider bounds do not automatically
extend standalone rest/shop contracts.

| Interaction | Implemented scope | Live evidence and limits |
| --- | --- | --- |
| Ordinary and repeated option pages | Owned choices, completed callbacks, fresh native controls and bounded revisits | Abyssal Baths two Lingers/exit demonstrated; other long chains need caller coverage |
| Deck changes around a selector | Append-only baseline before the first selector; removal followed by at most one separate appended grant | Grave/Confront, Amalgamator/CombineStrikes and both Trial/Innocent selector branches demonstrated; grant provenance unverified; arbitrary survivor changes/multiple grants unsupported |
| Upgrade | Fixed selection counts 1–8; eligible allocated off-screen holders | Sapphire Seed single upgrade at slot 20 of 23 demonstrated. Full-producer Trial/MerchantInnocent fixed-two passed 5/5/5 after Shame addition, and Yummy Cookie fixed-four passed 7/7/7, with exact upgrades and map return. Other counts/callers retain separate limits; Dummy automatic upgrades are not selector evidence |
| Enchant | Single selection and fixed 2–8 selections with exact preview/effects | Sapphire Seed, Grave and Prickly Sponge fixed-two demonstrated; other counts/callers offline only; stacking/replacement and optional counts unsupported |
| Remove | Positive selections up to eight with exact original preview/removal; owned automatic removal without a selector | Amalgamator fixed-two and one-card Dark Door automatic completion/map demonstrated; other counts/callers need evidence |
| Transform | Fixed/positive variable counts up to eight; optional 0..8; fixed-one generic transform-prompt surface | Allocated off-screen input, Wood Carvings/Bird and Claws zero/three/six demonstrated. Trial/NondescriptInnocent passed 5/5/5 after observed Doubt addition: two exact originals transformed, survivors/inventory preserved and map returned. Torus and other callers need evidence |
| Add-card grid | Positive selection; optional 0..15 with explicit confirmation | Cheese two-of-eight and Sea Glass zero/three/fifteen demonstrated |
| Ordinary card-reward menus | One or 2–8 menus, 1–5 cards/menu, native choice/Skip and final dismissal | Brain Leech singleton and Colorful Philosophers choose/Skip/choose demonstrated; other counts/outcomes offline only |
| Direct offered card | Required `card_offer_v1`; optional v2 choice/Skip with zero/one observed appended grant | Lead Paperweight and Hefty Tablet choice/Skip demonstrated. Required-choice v1 is fixture-only capability with no identified native caller; not a pending gameplay test |
| Card bundle | 1–5 bundles of 1–8 cards, original preview and Confirm | Scroll Boxes three-card bundle demonstrated; other variants offline only |
| Results acknowledgment | Confirm 1–64 displayed results while preserving the post-show deck | Pandora’s Box nine-result screen demonstrated; preceding automatic transformations are not certified |
| Ancient dialogue/options | Native ancient layout, bounded dialogue and supported pickup children | Console-selected routes and natural Nonupeipe entry in the shared Act-3 continuation demonstrated; other natural routes and normal Darv pool eligibility retain separate limits |

### Item rewards, combat events and custom screens

| Interaction | Implemented scope | Live evidence and limits |
| --- | --- | --- |
| Event potion/relic rewards | Singleton or 2–8 ordered items; supported exact pickup effects | Singleton and Potion Courier three-potion collection demonstrated; other counts/relic sets offline only |
| Mixed event rewards | 2–8 card/potion/relic entries; use advertised order, native card Skip/final dismissal | Lost Coffer choose and Skip demonstrated; other orders/counts offline only |
| Full-producer event rewards | `full_rewards_v1` shared rewards; `full_rewards_v2` retains Neow’s Bones nested pickups, visible choices and final curse under one event owner | Lost Coffer potion replacement, card choice and event/map return passed 6/6/6. Neow’s Bones with Large Capsule, Lost Coffer, nested Sacrifice and the final curse passed 7/7/7 through map return; other compound branches, callers and alternatives retain separate evidence limits |
| Full-inventory event/resume policies | `item_policy_v1`: skip-full, skip-all, protected original-potion replacement, stop-on-full; capacity-first collection | Courier full-belt skip/three replacements, Lost Coffer card plus potion skip/replacement, and Dummy resume skip/replacement demonstrated. Full-producer Repy collected Belt before potions, retained all three originals, filled both added slots and reached the map at 6/6/6. Resume capacity remains fixture-only |
| Terminal Strawberry pickup | Exact native type/key/+7 max HP/+7 HP, ready schema 7 | Saved floor-8 native retest passed: five reward actions reconciled and reached the map; max HP 2,064→2,071 |
| Modified terminal gold | Bowler Hat final integer gain, ready schema 8 in source | Saved floor-15 retest passed: printed 20 gold yielded and reconciled 25 gold (492 → 517), then reached the map |
| Terminal reward potions | Stop-on-full, skip-full, skip-all, protected original-potion replacement | Skip-full, skip-all with full **and free** capacity, and replacement including distinct same-key potions demonstrated |
| Potion Belt capacity | Exact +2 empty slots, retained prior inventory, at most eight slots; terminal, event and resume paths | Full-belt terminal ordering passed through Punch Off at 17/16/16, including one non-mutating stale rejection; event ordering passed through Repy at 6/6/6. Both retained three originals, verified two new empty slots before potion claims, filled both slots and returned to the map. Resume capacity handling is fixture-only with no identified native reward-set caller |
| Special/extra combat rewards | At most eight event extras, at most one special card; gold/card/potion/relic collection | Lantern Key special card and Punch Off potion/relic extras demonstrated. Terminal schemas 9–10 support up to 32 total entries; event extras retain their eight-entry bound |
| Non-resuming event combat | Exact entry ownership → combat → rewards → map | Dense Vegetation, Lantern Key, Punch Off and initial Fake Merchant fight demonstrated |
| Resuming event combat | Exact original Resume callback/task → owned item reward if present → resumed event/Proceed/map | Dummy training expiry, Setting1 victory/potion and Setting2 victory demonstrated; consecutive matching combats also demonstrated. No recursive combat driver |
| Resume-time item rewards | One owned Offer with singleton or 2–8 potion/relic entries | Setting1 potion collect/skip/replacement demonstrated. Relic/set reward screens are fixture-only with no concrete resume caller identified; Setting3 obtains its relic directly. Resume-time cards/selectors unsupported |
| Fake Merchant inventory | Initially closed inventory → 0–6 supported relic purchases → close/Leave | Two-purchase visit demonstrated; zero/six purchase variants offline only; already-open entry unsupported |
| Fake Merchant fight/healing | Initial owned Foul Potion starts combat; terminal Fake Lee’s Waffle verifies capped 10% max-HP healing; terminal schemas 9–10 support 32 entries; schema 10 adds exact Fake Mango +3 max HP/+3 HP | Original ten-entry rewards passed after native Continue: 12/12/12 actions, all rewards collected, HP10/80→21/83 and actionable map. Earlier assisted seven-relic collection and the failed 8/8/7 Mango attempt retain separate evidence. Fight after shopping unsupported |
| Crystal Sphere | Owned Uncover Future/Payment Plan entry, small/big tool, legal 11×11 fog reveals, earned rewards and exact native exit/overlay cleanup | Both entry paths demonstrated. Shared v2 Payment Plan passed 17/17/17 with big→small→big switching, all six exact fog/count changes, earned gold/two potions/card and map return. Earned relics and other outcomes remain separate. Hidden items are not projected; already-open adoption and full-belt replacement unsupported |
| Trial abandonment | Owned popup Cancel or explicit Confirm, exact native abandonment task | Both demonstrated; Cancel continued to rewards/map/next room, Confirm produced `run_abandoned` and native Defeat/HP0 |
| Architect ending | Native vote/queued action/next-act/WinRun task chain, terminal `run_won`; exact owned victory event with its combat layout and retained map-travel flag | Legacy controlled saved runs reached `run_won` and native Victory. The shared-v2 chooser also completed final combat, rewards and Architect at 12/12/12 new actions, returning `victory/none` with native Victory observed. These are assisted saved continuations, not fresh full-campaign certification |

<a id="current-exclusions"></a>

## Known failures and runtime limits

- **Owner-frame reads:** an earlier floor-33 read timed out before claim at 501 ms.
  The accepted release permits one internal GET replacement after atomic
  cancellation, with at most eight replacements per process. The saved continuation
  then completed 7,477 reads through victory without a read failure. Successful
  responses do not expose a retry count, so this does not prove recovery occurred
  or explain intermittent cold-start failures. The 500 ms per-submission deadline
  remains; POSTs and claimed callbacks cannot be retried.
- **Campaign budgets in source:** terminal schemas 1–8 allow eight entries and
  17 accepted actions; schemas 9–10 allow 32 entries and 65 accepted actions,
  across at most 64 screens. Transport allows 131,072
  reads and 8,192 action reservations; the 64 feature-session cap is unchanged.
  A new client resets none of these process counters. Ordinary controllers retain
  tighter local bounds; see [campaign limits](../bridge/Sts2AgentBridge/README.md#campaign-traversal).
  These budgets are included in the current accepted assisted campaign release.
- **Native ownership:** modules remain exclusive until reconciliation and successful
  disposal. Uncertain mutations or failed cleanup stop the host; no mutation retries.
  Only a known `stale_decision` with `mutation_state: none` permits bounded re-observation.
- **Corrected shop pickup hook:** inherited passive relic callbacks now use their
  declared method for hook ownership, installation and cleanup. The Red Mask retest
  passed **3/3/3** with exact payment/pickup and map return. The
  [original 1/0/0 live stop](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#red-mask-shop-purchase-stopped-before-acceptance)
  retains its uncertain result and separate artifact; no mutation was retried.
- **Ordinary reward and Sacrifice callback hooks:** the shared-v2 route stopped
  at Small Capsule's Stone Cracker claim with **2/1/0** and pending work. Derived
  passive-relic fixtures reproduced inherited-method hook failures in both
  observers. The correction uses each selected callback's declaring method for
  ownership, patching and cleanup; focused checks, independent review and the
  final release gate passed. The corrected package recovered Neow's reward and
  event/map return during the later route; non-compound Sacrifice remains a
  separate live limit. The
  [failed attempt](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#shared-v2-route-stopped-at-small-capsule-2026-09-26)
  retains its original package and unresolved counts after clean removal.
- **Large-deck shared selectors:** the later route stopped at Cook with a 33-card
  deck and **51/51/50** counts. The shared selector incorrectly waited for every
  native holder to be allocated. The released correction preserves all public
  choices and performs bounded native scrolling/rebinding only for the requested
  original. Partial-grid and slow-frame regressions and all 85 release checks
  pass. The saved-run retest passed **7/7/7** on a publicly verified **32-card**
  deck: public deck positions 0/31, deselection/reselection, exact Blood Wall+/Stomp
  removal, +9 HP/max HP and map return. No exact live allocation count was sampled.
  Full-producer single upgrade/enchant event selectors use released `card_grid_v1`
  with up to 128 public originals. Symbiote's 105-card retest passed at **4/4/4**
  with settled map return; exact eligible count and holder allocation were not
  sampled. Other generic selectors retain their allocated-holder boundary.
  [Retest](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#large-deck-cook-retest-passed-2026-09-27) and
  [original failure](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#shared-v2-neow-recovery-and-large-deck-cook-stop-2026-09-26).
  Optional zero confirmation is contract-specific and is not native cancellation.
- **Large-deck rest handoff:** after the successful Cook retest, the unchanged
  shared policy reached Act 2 floor 79 and stopped with an 86-card deck and
  **236/234/233**, one pending action. Only Proceed was visible. A regression
  reproduced the conflicting 64-card entry/128-card effect limits; the
  coordinator also withheld a verified receipt until the successor read.
  Both corrections are implemented with pre-input capacity guards and focused
  tests. The original final action was not logged, so Clone is a
  source-consistent explanation, not an observed final action. Normal quit and
  exact cleanup passed. The corrected saved-run rest cycle then passed
  **14/14/14**, including 24 verified Clone additions, an 86-card rest and map
  return. This does not reconcile the original failed attempt.
  [Result and diagnosis](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#shared-v2-act-2-rest-handoff-stop-2026-09-27).
- **Extended saved-campaign navigation:** the subsequent shop passed through map
  return, then the route stopped while entering floor 81 at **27/27/26**, one
  pending action. Source inspection identified the legacy 80-floor cap in full
  navigation and loss of an already verified map receipt when the next read
  failed. The released correction separates full-profile progress from execution
  budgets and preserves certified receipts in terminal failures. Original live
  counts remain unchanged. The corrected continuation admitted floor-81 combat,
  cleared the fight/rewards, and retained the next map completion at **10/10/10**
  when rest entry stopped explicitly at Clone's 128-card capacity guard. Nothing
  remained pending. A later shared-v2 continuation reached the native ending,
  as recorded under [latest evidence](#release-and-latest-evidence).
  [Result](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#large-rest-recovery-and-floor-81-stop-2026-09-27).
- **Single-card shop enchant preview:** Punch Dagger stopped after purchase and
  selection at **2/2/0**, before confirmation. The pinned preview queues old scene
  children for deletion until frame end; a matching fixture reproduced the
  immediate child-count rejection. The correction waits only during the owned
  input, before accepting any preview bindings, then keeps exact card/effect
  validation. The corrected live retest passed **7/7/7**, including preview
  deselection/reselection and exact effect/map reconciliation. The
  [failed attempt](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#punch-dagger-single-preview-failure-2026-09-26)
  retains its original artifact and unresolved counts despite successful cleanup.
- **Evidence boundary:** supported child effects do not certify all automatic parent
  rewards/costs or whole-event coverage. Controlled victories do not establish
  normal-HP win rate or exhaustive native coverage. Public-screen reads are not map probes.

## Implementation gaps versus remaining live tests

### Confirmed rest gaps implemented and demonstrated

Native Smith/Cook cancellation and rest-triggered Dream Catcher/Tiny Mailbox
rewards now have interactive adapters and ownership/effect checks. Representative
cancellation, reward collection and card Skip passed live on 2026-09-25.
These changes have separate live evidence from the newer full-producer extensions.

### Broader native v2 implementation

The candidate implements the named hand-selector, potion, treasure, reward,
shop and recording gaps in the [full-producer contract](AGENT_CONTRACT.md#native-full-run-v2-candidate).
The original versioned controllers retain their semantics. New native owners
verify exact tasks, inventory effects and nested receipts before handoff; failed
or unresolved cleanup still stops the host.

Neow's Bones now has a production-connected `full_rewards_v2` compound owner.
Its two mandatory relics retain their actual pickup tasks and nested screens through
reward sets, card offers, bundles, remove/upgrade/transform choices and the final
curse addition. The shared policy sees only the current visible choice. Completed
children retain ordered receipts while their enclosing pickup remains pending;
retiring screens cannot reclaim a later sibling's input.

The pinned Neow pool is covered by these effect families: ordinary passive pickups;
Small Capsule/Lost Coffer/Kaleidoscope reward sets; Lead Paperweight/Massive Scroll/
Hefty Tablet/Scroll Boxes offers; Precise Scissors/Precarious Shears/Pomander/New Leaf
selectors; and the remaining scalar, upgrade, card-add, transform and potion
pickups, including Large Capsule, Leafy Poultice and Phial Holster. Actual command
results and callbacks certify effects, including prevented card/potion grants and
native Egg upgrades. Unknown callbacks or unrelated inventory changes still stop.

This compound support is **released with representative live acceptance**:
Neow’s Bones generated Large Capsule and Lost Coffer, nested Sacrifice granted
Regal Pillow, and the final Decay curse settled before event/map return. All seven
actions reconciled. Hefty Tablet/Kaleidoscope also completed at 9/9/9; the
bundle/removal correction passed its controlled live retest at 8/8/8. Lead
Paperweight/Pomander then passed the offer/upgrade chain at 7/7/7. The
[live ledger](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#neows-bones-compound-rewards-passed)
binds this controlled path to its tested artifact. The final focused owner/alternative regressions passed
four groups in 49.605 s. Public projection and parent/wire checks also passed.
Independent semantic review found no remaining blocker after nested Sacrifice
was connected to the existing pickup chain; every visible alternative is retained.
The final release validation passed as recorded below. Fixture and live evidence
remain distinct; this case does not establish every Neow outcome or localization.

The compound owner admits at most five reward sets, eight rows per set, 40 child
inputs, 2,048 reads and five minutes within the existing 52-total-action event
budget. Only Neow's Bones selects this owner; other full-producer events keep
`full_rewards_v1`. Nested Sacrifice retains the exact Pael’s Wing callback and
certifies its actual automatic relic pickup or unchanged no-grant inventory before
completion. Arbitrary nested relics and unrelated selector chains remain
unsupported; this does not broaden standalone shop/rest contracts.
[Shared contract](AGENT_CONTRACT.md#native-full-run-v2-candidate).

### Contract limits without a confirmed missing gameplay caller

These are **not an implementation queue or required live-test checklist**:

- Dig popup/reward/multiple-selector follow-ups: the normal Common/Uncommon/Rare
  draw has no identified pickup-screen caller beyond current support. The bounded
  helper remains for injected setups. [Pool audit](EVENT_INTERACTION_MAP.md#dig-pool-audit-september-24).
  Mend belongs to multiplayer.
- Selectorless transform/add/enchantment variants retain their own contract limits;
  the new automatic-removal path does not broaden them.
- Multi-card Smith: no native count-changing caller found; removed as a feature gap.
- Variable-count upgrades, enchantment stacking/replacement, and generic-event
  unallocated-card input: retained contract limits, without a concrete necessary
  caller/setup. The shared Cook large-deck failure is a separate confirmed defect
  with a released correction and a successful 32-card saved-run retest.
- Resume-time card/selector reward screens and multi-item/relic reward screens:
  no concrete Resume caller identified. Dummy Setting1 offers one potion, Setting2
  upgrades automatically, and Setting3 obtains a relic directly. Resume-time
  capacity-first Potion Belt ordering therefore also remains fixture-only,
  rather than a scheduled gameplay acceptance case.
- Nested pickup selectors outside the identified Neow's Bones chain, multiple
  independent selector children per callback, and broader post-selector deck
  changes beyond current one-grant support still require a concrete caller.
- Required direct card offers: v1 exists in fixtures, but the inspected Lead
  Paperweight/Massive Scroll callers are optional v2; there is no required-v1
  gameplay case to schedule yet.

### Implemented, but still needing representative live evidence

- Other full-producer Neow’s Bones compound branches and potion-procurement
  outcomes; remaining automatic
  pickup effects and additional shared event reward callers.
  New Leaf's selected transformation followed by empty-belt Phial Holster's two
  potions, final curse and map return passed at 6/6/6 with unchanged survivors.
  Shears' two-card removal followed by full-belt Phial Holster, final curse and
  map return now passed at 7/7/7 with exact original-potion preservation.
  Representative hand/optional offers, potion use/discard and potion-owned choices,
  chest claiming, reroll and Sacrifice passed live, including the corrected
  Whetstone-granting second Sacrifice. Shop-removal preview cancellation also
  passed, with unchanged deck/gold and map return. Lost Coffer's full-producer
  rewards passed potion replacement, card choice and event/map return at 6/6/6.
  Neow’s Bones with Large Capsule, Lost Coffer, nested Sacrifice and final Decay
  passed at 7/7/7 through map return. Orrery's five card additions, automatic shop
  return and map exit passed at 13/13/13. Cauldron's five-potion replacement,
  automatic return and map exit also passed at 13/13/13. Silver Crucible’s first
  empty chest passed Open/Proceed at 2/2/2 with exact inventory preservation.
- Expanded terminal schemas 9–10: the representative ten-entry screen passed live.
  The wider 32-entry bound and 65-action card-menu sequence remain fixture/socket
  evidence, without a separately identified ordinary 32-entry gameplay caller.
- Selectorless removal: one-card Dark Door passed live. Empty domains, retained
  Eternal cards, other callers and adversarial variants remain fixture evidence.
- Kifuda/Gnarled Hammer zero/fewer-card and deselection variants, and remaining
  kind/gold-reserve variants. All five supported shop card selectors now have
  representative live acceptance. Zero-purchase
  Close/Leave passed with exact inventory preservation. The inherited passive Red Mask purchase
  passed through the full producer; other pickup effects remain separate cases.
- Other capacity-reward callers retain separate limits. Representative full-belt
  Potion Belt ordering now passed in terminal rewards through Punch Off at
  17/16/16 and event rewards through Repy at 6/6/6. Both preserved the three
  original potions and filled both added slots. Console-created Repy had no
  Lantern Key; quest removal and natural entry remain separate evidence limits.
  Resume capacity has no identified native caller.
- Held-out enchant/removal/transform callers such as Wood Carvings/Torus retain
  separate evidence limits. Its fixed-one basic-card choice and exact Toric
  Toughness replacement are prepared as the next case. Yummy Cookie's fixed-four
  upgrades and both Trial/Innocent curse-plus-two selectors now have representative
  live acceptance; each Trial branch passed 5/5/5. Recreating Trial repeats a
  campaign's branch; the saved TEST531 campaign produced Merchant as predicted.
- Other natural ancient entry/dialogue routes beyond the demonstrated Nonupeipe continuation.
- Broader reward orders/outcomes with a concrete offered screen, Sphere earned
  relics, and Fake Merchant zero/six-purchase variants. Sphere small/big tools,
  six exact reveals and earned gold/card/potions passed through the shared producer
  at 17/17/17; other outcomes retain separate limits.
- Held-out elite and room-handoff variants beyond the accepted campaign route.
- A fresh uninterrupted shared-v2 campaign. The assisted saved continuation now
  demonstrates the ending, with earlier stops, corrections and reloads retained
  in its evidence.
  The demonstrated long traversal does not establish all-branch coverage or
  strategic quality. Another fresh run is not required for milestone 7 acceptance.

[Roadmap](../ROADMAP.md) owns the order of work. [Caller evidence](EVENT_COVERAGE.md)
links the exact demonstrated paths; the [research map](EVENT_INTERACTION_MAP.md)
supplies dated source candidates rather than a current implementation checklist.

## Release and latest evidence

The current [release manifest](../bridge/Sts2AgentBridge/releases/current/bridge.json)
is **`69bfd021968f2ea8e3879fe09901cdaf53f3cfa90fbae5f8bc69fe16f3f2e639`**, source
`0fb2972`. Reward claims now propagate capacity validated by the exact full effect
owner, including Phial Holster and nested relic grants. Stored capacity advances
only after successful settlement; pending callbacks and unexpected inventory
changes retain their waiting/failure behavior. Focused checks passed **3,487 reward
checks and 216 alternative checks** in 61.067 seconds. Independent review found no
blocker. The final gate passed **85 groups in 379.888 seconds**, including production
build/package reproducibility and operational checks. Installation and metadata
verification passed by **15:07:20 UTC**. The fresh full-belt Holster retest passed
**7/7/7**, 61 controller reads plus one verification read. The same artifact's
New Leaf/empty-belt Holster case then passed **6/6/6**, 53 controller reads plus
one verification read. Both completed the final curse and actionable map.
Repy's full-belt capacity-first event rewards then passed **6/6/6**, 42 controller
reads plus one verification read, with exact originals retained and both added
slots filled before map return.
Punch Off's full-belt terminal variant passed **17/16/16**, 234 controller reads
plus one verification read, one non-mutating stale rejection and nothing pending.
Both added slots contained the exact offered Fire Potions, and the original deck
was preserved with Whirlwind appended.
Trial/MerchantInnocent then passed **5/5/5**, 34 preflight reads, fifteen controller
reads and one verification read. Shame and two exact Strike upgrades settled
through map return without changing other inventory.
Latest exact owned cleanup and base verification passed by **16:55:30 UTC**:
zero overlays and all 429 base files unchanged.

The prior manifest **`14772d59c22d9d630bc71780c3871fedd95331e9c6797267a5fe0acd5ab0582a`**,
source `988f2b5`, carried the scoped compound-grid preview correction. Its release
gate passed 85 groups in 386.222 seconds. Bundle/removal passed **8/8/8**, 56 reads;
offer/upgrade passed **7/7/7**, 60 reads. Holster then stopped at **6/5/4**, one
pending action; exact cleanup passed at **14:32:26 UTC**. The stopped action stays
unreconciled in that artifact's historical record.

The preceding manifest
**`325f2611735c00376775a0d6f4c2c4c1aa1657a93477e056cf777a318321bf20`**. Source `2e9e66d` changes only the full client and
its two regression files among 489 bound inputs across 52 projects. Full mode
now stops after four consecutive confirmed no-mutation stale rejections; only
validated acceptance resets that streak. Cumulative reporting, the legacy cap,
uncertain-dispatch stops and time/read/action limits remain intact. Independent
review cleared the correction; the final gate passed **85 groups in
399.505 seconds**, including 173 client tests, 1,719 router checks and
17,151 native event checks.

The native DLL and package exactly match the preceding accepted release. Fresh
installed/runtime, authenticated health and compatibility checks passed before
resuming the same settled combat, without restarting or reinstalling the game.
The preceding release passed the 105-card Symbiote Corrupted chooser and map
return at **4/4/4**, then completed further combats, treasure, rest and Tinker
Time before the floor-99 `stale_limit` stop at **116/112/112**, nothing pending.
Three subsequent read-only decisions had identical tokens and public graphs.
The corrected client then completed final combat, rewards and the Architect,
returning **`victory/none`** with **12/12/12 new actions**, 262 reads, zero stale
rejections and nothing pending. Native Victory was observed; cumulative native
counts were **124/124/124**. This demonstrates the shared-v2 ending for the
assisted saved continuation. The corrected segment did not encounter stale
rejections, so separated-stale recovery is still fixture evidence. Normal quit,
owned-file cleanup and base verification passed by **12:56:22 UTC**: zero overlays
and all **429** base files unchanged.
[Latest result](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#symbiote-passed-and-settled-combat-stale-stop-2026-09-27).

The older package's Symbiote Approach stopped at **84/81/80**, one pending action.
That failed attempt and its **11:11:57 UTC** exact cleanup retain their original
artifact in the ledger; the successful retest does not reconcile it.

An earlier package passed the saved-run rest cycle at **14/14/14**, with Clone
expanding the deck to 86 and a verified map return. Its next shop completed,
then floor-81 navigation stopped at **27/27/26**, one pending action. Normal quit
and exact cleanup passed by **10:31:01 UTC**; original counts and artifact identity
remain in the [ledger](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#large-rest-recovery-and-floor-81-stop-2026-09-27).

The preceding `fed09e93…` package passed the saved Cook retest at **7/7/7** on
2026-09-27. Its unchanged-policy continuation crossed Act 1 into Act 2, then
stopped at an 86-card rest site at **236/234/233**, one pending action. Normal
quit and exact cleanup passed by **09:49:02 UTC**: zero overlays and all 429 base
files unchanged. The final action was not retained; the source-consistent Clone
explanation is not direct live evidence. That result remains bound to its
original artifact in Git `1f74e08` and the live ledger; cleanup does not reconcile it.

The [preceding route](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#shared-v2-neow-recovery-and-large-deck-cook-stop-2026-09-26)
under manifest `e8cfb4c7` recovered Neow's reward and event/map return, then
completed four fights and Slippery Bridge before Cook's 33-card selector stopped
at **51/51/50** with pending work. Normal Quit and cleanup passed by
**17:39:16 UTC**, leaving zero overlays and all 429 base files unchanged. No act
transition or ending was reached. Cleanup does not reconcile Cook or the earlier
uncertain reward attempt. The previous release record and package inputs remain
under `/private/tmp/sts-bridge-0ceoerz0`, as well as the dated Git record.

The latest accepted [Sphere tool/reward test](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#sphere-small-and-big-tools-passed-2026-09-26)
passed **17/17/17**, 64 public reads, zero stale rejections and no pending action.
Both tool switches and all six fog/divination changes matched the next public
board. Three gold entries, two potions and a card were collected before map
return; original deck and potions stayed exact. The user freed three potion slots
before attachment. Normal Save and Quit, game Quit and cleanup passed by
**16:11:01 UTC**, leaving zero overlays and all 429 base files unchanged.
That test reused the preceding package (`289fabed`) and its accepted gate.
The [shared-v2 route attempt](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#shared-v2-route-stopped-at-small-capsule-2026-09-26)
then stopped at Neow's Small Capsule/Stone Cracker reward with
`uncertain_dispatch`, **2/1/0** and pending work. Upfront assistance was verified
at HP 2072/2072 with four Break and two Flash of Steel cards in the 29-card deck.
No action was retried. Normal Quit and exact cleanup passed by **16:44:26 UTC**,
leaving zero overlays and all 429 base files unchanged. The inherited callback
defect was reproduced in ordinary rewards and Sacrifice; its declaring-method
correction passed the final release gate and recovered Neow in the subsequent
route recorded above. Neither attempt reached an act transition or ending.

The preceding [Trial two-transform test](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#trial-curse-and-two-transforms-passed-2026-09-26)
passed **5/5/5**, with fifteen controller reads and no pending action. Doubt was
observed before the selector; two Bludgeon+ originals became Headbutt and
True Grit+, with every other card and inventory item preserved through map return.
Normal Save and Quit, game Quit and cleanup passed by **14:53:12 UTC**, leaving
zero overlays and all 429 base files unchanged. The preceding
[0/0/0 setup rejection](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#trial-direct-shop-setup-rejected-2026-09-26)
retains its original evidence; normal connected rest entry corrected the setup
without changing any production guard.

The subsequent [Trial/Sphere preparation](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#trial-seed-limit-and-sphere-setup-stop-2026-09-26)
stopped before bridge attachment: Trial repeated its campaign-seeded branch,
and one native potion-discard attempt did not visibly establish free capacity.
No public gameplay reads or bridge actions ran. Normal game Quit and cleanup
passed by **15:11:52 UTC**, with zero overlays and all 429 base files unchanged.
Its later successful Sphere test is recorded above; the earlier setup stop
remains distinct. Resume-time capacity-first reward ordering was removed from
the live-test queue: the existing caller audit identifies no native reward set for it.

The preceding [Silver Crucible empty-chest test](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#silver-crucible-empty-chest-passed-2026-09-26)
passed **2/2/2** through Open/Proceed, with eighteen controller reads and no
pending action. The map was actionable and the full inventory stayed exact.
Normal Save and Quit, game Quit and cleanup passed by **2026-09-26 13:31:05 UTC**,
leaving zero overlays and all 429 base files unchanged.

The preceding [Cauldron retest](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#cauldron-five-potion-replacement-passed-2026-09-26)
passed **13 attempted / 13 accepted / 13 reconciled**, fourteen controller reads,
zero stale rejections and no pending action. All five originals were replaced
with the five exact reward potions; newly collected items were protected. Gold
changed 665 → 454, while all 23 cards and HP 88/88 stayed unchanged through map
return. Normal Save and Quit, game Quit and exact cleanup passed by **2026-09-26
13:18:15 UTC**, leaving zero overlays and all 429 base files unchanged.

The preceding [Cauldron attempt](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#cauldron-helper-stop-and-expired-purchase-2026-09-26)
stopped at **3 attempted / 3 accepted / 2 reconciled**, with the purchase pending.
The helper missed the discard/claim alternation needed for a full belt. Its later
read failed after the existing 60-second purchase deadline elapsed during
continuation preparation. The helper is corrected; no production safeguard changed.
Normal game Quit and exact cleanup passed by **2026-09-26 13:10:43 UTC**, leaving
zero overlays and unchanged base files. Cleanup and the separate successful
retest do not reconcile that purchase.

The preceding [Orrery batch](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#orrery-five-card-rewards-and-merchant-travel-passed-2026-09-26)
passed **13/13/13** through purchase, all five card choices and shop/map return.
Gold changed 826 → 649 and the deck grew 17 → 22, preserving every original card,
HP and potions. The helper stopped after the game's automatic reward dismissal;
all eleven actions were settled, and Close/Leave completed separately. Legal
travel then reached another merchant at **28/28/28**, with one known non-mutating
stale rejection handled from a fresh decision. No production correction was needed.
Normal Save and Quit, game Quit and exact cleanup passed by **2026-09-26 13:00:51 UTC**,
leaving zero overlays and all 429 base files unchanged.

The preceding [Royal Stamp test](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#royal-stamp-preview-toggle-passed-2026-09-26)
passed **7 attempted / 7 accepted / 7 reconciled**, 19 controller reads, no stale
rejection or pending action. The same Defend+ was selected, deselected and
reselected, then received exactly Royally Approved with Innate and Retain.
Gold changed 826 → 614; the other sixteen cards, HP 88/88 and potions were
preserved through map return. Normal Save and Quit, game Quit and exact cleanup
passed by **2026-09-26 12:42:36 UTC**, with zero overlays and unchanged base files.
The unchanged accepted release was reused.

The preceding [Gnarled Hammer and zero-purchase batch](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#gnarled-hammer-and-zero-purchase-shop-passed-2026-09-26)
passed **25 attempted / 25 accepted / 25 reconciled**, with no pending action.
Hammer applied Sharp 3 to three exact originals for 204 gold (**7/7/7**); legal
combat/event travel reached another merchant (**16/16/16**); Close/Leave without
purchases preserved the exact inventory and returned to the map (**2/2/2**).
Normal Save and Quit, game Quit and exact cleanup passed by
**2026-09-26 12:34:12 UTC**: four generated files removed, zero overlays and all
429 base files unchanged. No production change or new release gate was needed.

The same package's corrected [Punch Dagger retest](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#punch-dagger-corrected-preview-passed-2026-09-26)
passed **7 attempted / 7 accepted / 7 reconciled**, 19 controller reads, no stale
rejection or pending action, and an actionable map. It bought the relic for 188,
selected/deselected/reselected the same Bludgeon+, then confirmed exactly one
Momentum 5 enchantment. Gold changed 1017 → 829; the other fifteen cards,
HP 88/88 and five occupied potion slots stayed unchanged. Normal Save and Quit,
game Quit and exact cleanup passed by **2026-09-26 12:20:28 UTC**: four generated
files removed, zero overlays and all 429 base files unchanged.
The preceding package's [failed attempt](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#punch-dagger-single-preview-failure-2026-09-26)
retains its original **2/2/0** result, artifact and cleanup evidence. Royal Stamp's
separate successful test above also exercises the corrected shared preview.

The preceding manifest's [Yummy Cookie test](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#yummy-cookie-four-card-upgrade-passed-2026-09-26)
passed **7 attempted / 7 accepted / 7 reconciled**, 31 controller reads, no stale
rejection or pending action, and an actionable map. Bludgeon, Headbutt, Body Slam
and Fiend Fire each upgraded 0 → 1; the other twelve cards, HP 88/88, gold 17,
existing relics and all five potion slots stayed unchanged. Exactly one Cookie
was appended. Normal Save and Quit, game Quit and exact cleanup passed by
**2026-09-26 11:02:11 UTC**: installation absent, four generated files removed,
zero overlays and all 429 base files unchanged. Controlled Tezcatara entry does
not establish natural Ancient entry, other counts or persistence across reload.

The preceding rest batch passed **24 attempted / 24 accepted / 24 reconciled**, with
no pending action. Lift 0 → 1, Kindle 5 → 10, an exact Clone-enchanted Bludgeon copy,
one egg → Byrd Swoop/Byrdpip, and Dig’s Bag of Preparation pickup all settled in
one Miniature Tent visit (6 actions, 80 controller reads, including Leave).
Legal combat/rest travel added 12 actions and 93 reads; Smith then deselected and
reselected the same Bludgeon before exactly one upgrade and map return (6 actions,
38 reads). HP stayed 88/88 and unrelated inventory checks passed. The
[live ledger](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#remaining-rest-options-and-smith-toggle-passed-2026-09-26)
records the setup, per-case effects and separate public reads. Normal Save and Quit,
game Quit and exact cleanup passed by **2026-09-26 10:27:28 UTC**: installation
absent, four generated files removed, zero overlays and all 429 base files unchanged.
The earlier [Mirror/Belt/Cook batch](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#mirror-potion-belt-and-cook-batch-passed-2026-09-26)
remains separately recorded at **45/45/45**, including legal travel.
The same release's
[Kifuda result](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#kifuda-three-card-shop-pickup-passed-2026-09-26)
remains separately recorded at **7/7/7**, 25 controller reads and map return.
Cauldron/Orrery were untested in that earlier batch; their later acceptance is recorded above. The
[Red Mask result](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#red-mask-corrected-shop-purchase-passed)
remains separately recorded at **3/3/3**, four controller reads and map return.

The preceding manifest `18169693…`, source `7bd3e09`, passed Neow’s Bones:
**7 attempted / 7 accepted / 7 reconciled**, 53 controller reads, no stale rejection
or pending action, and map return. Its later Red Mask purchase stopped with
`uncertain_dispatch` at **1 attempted / 0 accepted / 0 reconciled**, one controller
read and a pending action. The policy did not retry it. The inherited-method
regression reproduced a hook failure before purchase input; live UI still showed
466 gold and Red Mask in stock. Normal save/quit and exact cleanup finished by
**21:13:24 UTC**: four generated files removed, zero overlays and all 429 base files
unchanged. These results remain bound to their original artifact in Git `c599a9f`
and the [live ledger](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md).

The preceding manifest `2d9a2560…`, source `b55c51d`, passed Lost Coffer:
**6 attempted / 6 accepted / 6 reconciled**, 42 reads, no stale rejection or pending
action. Potion replacement, card choice and event/map return completed; HP/gold
stayed 88/88 and 466, with the deck growing seven to eight. A subsequent debug shop
switch produced no new agent action and timed out after 900 reads while the full
session still tracked the map. This is setup-only evidence, not shop acceptance.
Normal quit and exact cleanup finished by **16:58:22 UTC**: four generated files
removed, zero overlays and all 429 base files unchanged. This evidence retains its
original package identity in Git `43241c9` and the
[live ledger](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md).

The preceding manifest `bc0767b1…`, source `d9eda0d`, passed Neow projection and
accepted Lost Coffer. Native Loot displayed Flex Potion and Add a card, then
`read_native_failed` stopped at **1 attempted / 1 accepted / 0 reconciled**,
35 reads and a pending parent action. No reward action ran or uncertain mutation
was retried. Normal quit and exact cleanup finished by **16:26:04 UTC**, with four
generated files removed, zero overlays and all 429 base files unchanged. The result
retains its original release identity in Git `ca440d3` and the
[live ledger](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md). Its unreconciled action
remains separate from the corrected release's successful retest.

Under the earlier manifest `1f83ded8…`, source `887c1da`, Whetstone Sacrifice
passed **4/4/4 actions**, five reads and map return. Shop-removal preview
cancellation also passed **5/5/5**, seven reads, unchanged deck/gold and map return.
Both later Lost Coffer setups stopped before policy input: **0/0/0**, 34 reads and
`read_native_failed`. The second used an event room, so the earlier shop-travel
explanation was insufficient; those coarse diagnostics left the cause unknown. Normal quit and exact
cleanup finished by **15:23:45 UTC**: four generated files removed, zero overlays
and all 429 base files unchanged. These results remain bound to their original
artifact in Git `7e23b4e` and the live ledger; the diagnostic change does not turn
them into acceptance.

The earlier package `32d721e8…`, source `6c04327`, completed 35 actions before
Whetstone's second-Sacrifice reconciliation failed on action 36. The
[live ledger](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md) retains each result
under that artifact. No mutation was retried. Normal quit and cleanup finished
by **14:09:44 UTC**: four generated files removed, all 429 base files unchanged,
zero overlays. Its record is preserved in Git `887c1da`; this result is not
repinned to the corrected package.

The previous manifest `812c148b…`, source `53e2255`, passed the controlled
Profile 3 v2 rest/card-reward/map test: **4/4/4 actions**, 27 reads, no stale
rejection or pending action. Its original record remains in Git `8a75686`. The
shared policy healed HP **45/83 → 69/83**, increased the deck **6 → 7**, and stopped
at the actionable map with `truncated/external_stop`. Normal quit and exact owned
cleanup completed by **11:02:21 UTC**: four generated files removed, all 429 base
files unchanged and zero overlays. That evidence retains its original package identity.

The preceding diagnostic package stopped at the saved rest site with
`read_context_failed` before any policy action (0/0/0, one read). A regression
reproduced the cause: the shared reader cleared a response buffer while its JSON
document still borrowed that memory. That correction gives the document
its own storage before clearing the source. The diagnostic run ended with normal
quit and complete owned cleanup: four files removed, all 429 base files unchanged,
zero overlays by 10:09:24 UTC, recorded in Git `53e2255`.
**Broader native v2 live coverage and campaign acceptance remain outstanding.** The
[release record](../bridge/Sts2AgentBridge/releases/current/README.md) retains exact
source/package, review, validation and installation identities.

The previous rest manifest was `1926afc8…`, source `ff3cb5f` (feature `24f620d`),
recorded in Git `4f8b633`. Its controlled Profile 3 checks passed on **2026-09-25**:
Smith/Cook immediate and preview cancellation, Heal-owned card/two-potion
collection, and separate card Skip/parent dismissal. All **20/20/20 actions**
reconciled across 102 reads. Normal quit and owned cleanup completed by
**07:11:34 UTC**: process/listener stopped, four generated files removed, zero
overlays and all 429 base files unchanged. Those original results are retained
with their original package; they are not evidence of v2 shared-policy behavior.

The prior automatic-removal release was
**`308e9683a74a3d60ef2071e3dd6f97583e2ace1adb2494778a9aaee73e89105e`**,
with 416 exact source/test inputs across 51 projects, committed in `b7ee84b`.
The release gate passed **83 groups in 304.387 seconds**, including 12,799 native
checks. The wrapper-only removal correction passed 320 focused checks and
independent semantic review. The one-card Dark Door retest passed live with
**2/2/2 parent actions**, no child selector, and an actionable map with two legal
destinations. Owned cleanup completed by **20:58:54 UTC**: game/listener stopped,
four generated files removed, zero overlays, and all 429 base files unchanged.
The merchant acceptance retains the preceding package identity.

An earlier candidate read Profile 3's original ten-entry Fake Merchant screen
after an assisted fight (11/11/11 combat actions). Rewards stopped at **8 attempted /
8 accepted / 7 reconciled** when Fake Mango applied its unrecognized +3 max HP/+3 HP.
No pickup was retried. Exact cleanup completed by **19:56:46 UTC on 2026-09-24**.
The earlier Dark Door failure retains its separate identity and unknown predicate.

The older `00280cad…` candidate passed the **original ten-entry Fake Merchant
rewards** after native Continue restored the whole list: **12/12/12** reward actions, 300
gold, Regen Potion, all seven fake relics and Headbutt, then the actionable map.
HP changed from 10/80 to 21/83, including Waffle and Fake Mango's exact effects.
This attempt attached at rewards; it did not replay the fight.

That preceding package's one-Bash Dark Door retest stopped at **1/1/0** with
`pending_selectorless_request`. The game removed Bash and displayed Proceed;
the bridge did not claim completion or retry. A source correction now handles an
exact outer removal request without requiring a second observation of its generic
implementation; its one-card live retest now passes as recorded above. The original
rejected predicate was not emitted. Both attempts were cleaned up by **20:31:55 UTC**: process and
listener stopped, four generated files removed, zero overlays, all 429 base files
unchanged.

The pinned target remains **v0.107.1 / Steam 23811903 / macOS arm64**.
The milestone 7 package completed an assisted campaign continuation with **643
attempted / accepted / reconciled actions**, 82 stages and the native ending.
The user accepted milestone 7 with the documented bridge-fix reload; a fresh
repeat is not required. The original `continued_victory` result and
`full_campaign_verified: false` marker remain unchanged. Its four earlier potion
uses, assistance, original release identities and complete cleanup are preserved
in the [M7 record](evidence/AGENT_CAMPAIGN_M7_2026_09_24.md).
That campaign used the smoke policy, not the full shared policy.

See the [current release record](../bridge/Sts2AgentBridge/releases/current/README.md)
and [validation](../bridge/Sts2AgentBridge/releases/current/validation.json).

The accepted M3 live session, under the previous M3 release, completed the controlled shared-policy combat, Neow's Fury
two-card selection, gold/reward leave and separate map transition: **16 attempted,
accepted and reconciled actions**, with no pending action or stale rejection.
It used the same headless/live callback with a gold-then-leave reward override.
A fresh native act map resolved the preceding setup-sensitive stall with the same
package; the original rejected map predicate remains unknown. Normal quit, exact
stopped-process/closed-listener checks and owned quarantine/purge completed:
**installation absent at 2026-09-23 19:14:56 UTC**, zero overlay files and all 429
base game files unchanged. The first M7 package was subsequently installed and
cleaned up after its controlled attempt; the [M7 record](evidence/AGENT_CAMPAIGN_M7_2026_09_24.md)
retains that distinct release, result and cleanup identity. The earlier M3 result
is not live evidence for the new candidate.

| Evidence record | What it establishes |
| --- | --- |
| [September 24 campaign integration](evidence/AGENT_CAMPAIGN_M7_2026_09_24.md) | Controlled resumed campaign victory, act transitions/ending, selectors and rewards, four live potion uses, Waterfall Giant stop/correction, assistance and cleanup |
| [September 23 agent integration](evidence/AGENT_BRIDGE_M3_2026_09_23.md) | Shared-contract adapter, paired/inert fixtures, accepted package and controlled live slice/map/cleanup; earlier failed attempts retained |
| [September 12–13 multi-case ledger](evidence/MULTICASE_BRIDGE_LIVE_2026_09_12.md) | Earlier shop/potion/combat/resume/Trial/Merchant/Dummy results and original Architect failure; exact releases, assistance, counts and cleanup |
| [Crystal Sphere ledger](evidence/CRYSTAL_SPHERE_LIVE_2026_09_12.md) | Uncover Future reveal/gold/map and corrected overlay cleanup |
| [September 9–10 combined ledger](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md) | Representative selector/reward/ancient/combat-choice paths |
| [September 8 unified smoke](evidence/UNIFIED_BRIDGE_SMOKE_2026_09_08.md) | Earlier core/rest/shop/item/event smoke with its original assistance and limits |

Earlier failures remain in those dated records; a later pass does not rewrite their
artifact identity or counts. Keep future chronology there and update the relevant
support row here.

## Headless game engine

The independent [game engine](HEADLESS_ENGINE.md) supports all five solo characters
at A0–A10 through Overgrowth or Underdocks, Hive, Glory and the Architect. Selected
native campaigns cover Ironclad and all four added characters, including boosted
A0/A10 victories with Python JSON continuation replay. See the
[character comparisons and limits](HEADLESS_ENGINE.md#playable-characters).
This simulator evidence is separate from live-bridge acceptance above.

The legacy simulator, reduced backend and actor/training pipelines were retired
on 2026-09-22; their evidence remains [archival](archive/README.md#retired-simulator-pipelines).
Full-game public observations and policy/data adapters are HF-44–47 in the
[current backlog](HEADLESS_FULL_GAME_IMPLEMENTATION.md). The headless
[`full_run_v2` profile](AGENT_CONTRACT.md#full-run-v2-profile), public-only chooser
and [`FullRunEnv`](AGENT_ENCODING.md#full-run-profile-and-environment) now cover
the current engine's command/decision families. Normal-HP campaign tests and
controlled ending fixtures are separate from policy strength and native fidelity.
This does not widen the live `agent_v1` profile or change its accepted package;
[public trajectories, data loaders, the installed agent CLI and bounded workers](AGENT_EXECUTION.md)
now deliver headless operational execution. Autonomous live campaigns remain
outside that delivery.
