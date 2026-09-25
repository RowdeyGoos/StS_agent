# Bridge support and status

Updated 2026-09-25 for broader native v2 implementation and interactive rest live validation; other capability review remains
2026-09-19 against bridge source, pinned native game IL and retained evidence. Latest live
session: **2026-09-25**. This is the authoritative summary of bridge support;
[usage](../bridge/Sts2AgentBridge/README.md), [technical contracts](GENERIC_EVENTS.md),
[caller evidence](EVENT_COVERAGE.md) and [priorities](../ROADMAP.md) have separate roles.

Quick navigation: [supported interactions](#supported-interactions) ·
[known failures and limits](#known-failures-and-runtime-limits) ·
[missing features versus remaining tests](#implementation-gaps-versus-remaining-live-tests) ·
[release and evidence](#release-and-latest-evidence).

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
rest/card-reward/map path passed live; broader v2 acceptance remains open. Its [coverage and remaining gaps](AGENT_CONTRACT.md#native-full-run-v2-candidate)
now include hand/optional combat choices, general potion use/discard and owned
selectors, chest claims/empty chests, reward reroll/sacrifice, shop removal cancel,
automatic relic effects, Cauldron/Orrery rewards and shared event reward children.
An opt-in public live journal is implemented; no live corpus was collected for
this development. The [broader live batch](evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md)
demonstrated reroll, map potion use/discard, chest claiming, potion-owned hand and
optional offers, and the first Sacrifice. The corrected Whetstone-granting
Sacrifice passed its saved-run retest: **4/4/4 actions**, five reads and an actionable
map, with no pending action. Full-producer shop-removal preview cancellation also
passed: **5/5/5 actions**, unchanged gold/deck and map return. The ledger preserves the preceding failed artifact
and its **36/36/35** counts. Prior rest
cancellation and potion-reward evidence retains its separate package identity.

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
| Rest | Heal/Proceed and Smith (one card); Lift, Kindle, Dig, Cook, Clone and Hatch. Packaged `rest_v3` exposes selector cancellation and Heal-owned rewards | Ordinary Heal/Smith, Smith/Cook immediate and preview cancellation, Dream Catcher card collect/Skip, and Tiny Mailbox two-potion collection demonstrated. Successful effects of the six additional actions remain offline only |
| Shop purchases | Cards, potions, supported passive relics, Potion Belt +2 slots; 0–8 purchases, kind policy, gold reserve and callback-certified restock | Seven-card/one-potion visit and three restocked potion purchases with original-potion replacement demonstrated. Passive relics, capacity and other policy variants need live coverage |
| Shop removal | Exact selected original, price/effect reconciliation, preview cancellation, then separate inventory close and Leave | Removal and full-producer preview cancellation demonstrated through map return; cancellation retained exact deck and gold |
| Shop pickup selectors | Dolly’s Mirror, Gnarled Hammer, Kifuda, Punch Dagger and Royal Stamp; exact native clone/enchantment selection | Implemented and offline tested; live coverage open. Other pickup callbacks are not generally supported |

### Native rest-site actions

These are actual options in the pinned game, with their enabling callers checked
in native IL. Availability still depends on the current run. The bridge supports
ordinary Heal and Smith, plus the six additional single-player options in source.
The new rest flow has its own native effect and selector checks.

| Option | Native source / trigger | Native behavior | Bridge |
| --- | --- | --- | --- |
| Heal | Default rest option | Heal, then run rest hooks and any generated rewards | Ordinary Heal/Proceed, Dream Catcher card collect/Skip and Tiny Mailbox potion collection demonstrated |
| Smith | Default rest option | Select and upgrade **one** card | Ordinary upgrade and `rest_v3` cancellation before selection/from preview demonstrated; deselection remains offline only |
| Dig | Shovel | Obtain a relic directly, including its pickup callback | Implemented in source; exact new relic and callback completion. One owned deck/enchantment selector of up to three cards; other follow-up surfaces stop |
| Lift | Girya, fewer than three lifts | Increase its lift counter, granting Strength in later combats | Included in the current package; exact +1 and native task completion checked offline. No live demonstration |
| Cook | Meat Cleaver | Remove two cards, gain nine max HP; native selection can be canceled | Immediate and two-card preview cancellation demonstrated. Successful removal/+9 max HP remains offline only |
| Clone | Pael’s Growth | Copy the deck’s Clone-enchanted cards | Implemented in source; scoped native insertion results, including add-time upgrades |
| Kindle | Pumpkin Candle | Add five to its remaining combat counter | Included in the current package; exact +5 and native task completion checked offline. No live demonstration |
| Hatch | Byrdonis Egg card | Obtain Byrdpip and transform every egg into Byrd Swoop | Implemented in source; exact relic and all egg transformations |
| Mend | Generated only with multiple players | Target and heal another player | Outside the current single-player bridge scope |

The six new options use `rest_v2` on the existing room-flow routes. They are
implemented, validated offline and included in the current package. Their successful
effects remain **without live demonstration**; Cook cancellation passed live. A flow
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
| Deck changes around a selector | Append-only baseline before the first selector; removal followed by at most one separate appended grant | Grave/Confront and Amalgamator/CombineStrikes demonstrated; grant provenance unverified; arbitrary survivor changes/multiple grants unsupported |
| Upgrade | Fixed selection counts 1–8; eligible allocated off-screen holders | Sapphire Seed single upgrade at slot 20 of 23 demonstrated. **True multi-card upgrade selector remains untested live**; Dummy automatic upgrades are not selector evidence |
| Enchant | Single selection and fixed 2–8 selections with exact preview/effects | Sapphire Seed, Grave and Prickly Sponge fixed-two demonstrated; other counts/callers offline only; stacking/replacement and optional counts unsupported |
| Remove | Positive selections up to eight with exact original preview/removal; owned automatic removal without a selector | Amalgamator fixed-two and one-card Dark Door automatic completion/map demonstrated; other counts/callers need evidence |
| Transform | Fixed/positive variable counts up to eight; optional 0..8; fixed-one generic transform-prompt surface | Allocated off-screen input, Wood Carvings/Bird and Claws zero/three/six demonstrated; Torus and other callers need evidence |
| Add-card grid | Positive selection; optional 0..15 with explicit confirmation | Cheese two-of-eight and Sea Glass zero/three/fifteen demonstrated |
| Ordinary card-reward menus | One or 2–8 menus, 1–5 cards/menu, native choice/Skip and final dismissal | Brain Leech singleton and Colorful Philosophers choose/Skip/choose demonstrated; other counts/outcomes offline only |
| Direct offered card | Required `card_offer_v1`; optional v2 choice/Skip with zero/one observed appended grant | Lead Paperweight and Hefty Tablet choice/Skip demonstrated. Required-choice v1 is fixture-only capability with no identified native caller; not a pending gameplay test |
| Card bundle | 1–5 bundles of 1–8 cards, original preview and Confirm | Scroll Boxes three-card bundle demonstrated; other variants offline only |
| Results acknowledgment | Confirm 1–64 displayed results while preserving the post-show deck | Pandora’s Box nine-result screen demonstrated; preceding automatic transformations are not certified |
| Ancient dialogue/options | Native ancient layout, bounded dialogue and supported pickup children | Console-selected routes demonstrated. Natural entry/dialogue and normal Darv pool eligibility remain open |

### Item rewards, combat events and custom screens

| Interaction | Implemented scope | Live evidence and limits |
| --- | --- | --- |
| Event potion/relic rewards | Singleton or 2–8 ordered items; supported exact pickup effects | Singleton and Potion Courier three-potion collection demonstrated; other counts/relic sets offline only |
| Mixed event rewards | 2–8 card/potion/relic entries; use advertised order, native card Skip/final dismissal | Lost Coffer choose and Skip demonstrated; other orders/counts offline only |
| Full-inventory event/resume policies | `item_policy_v1`: skip-full, skip-all, protected original-potion replacement, stop-on-full; capacity-first collection | Courier full-belt skip/three replacements, Lost Coffer card plus potion skip/replacement, and Dummy resume skip/replacement demonstrated. Capacity-first paths need live coverage |
| Terminal Strawberry pickup | Exact native type/key/+7 max HP/+7 HP, ready schema 7 | Saved floor-8 native retest passed: five reward actions reconciled and reached the map; max HP 2,064→2,071 |
| Modified terminal gold | Bowler Hat final integer gain, ready schema 8 in source | Saved floor-15 retest passed: printed 20 gold yielded and reconciled 25 gold (492 → 517), then reached the map |
| Terminal reward potions | Stop-on-full, skip-full, skip-all, protected original-potion replacement | Skip-full, skip-all with full **and free** capacity, and replacement including distinct same-key potions demonstrated |
| Potion Belt capacity | Exact +2 empty slots, retained prior inventory, at most eight slots; terminal, event and resume paths | Floor-31 terminal pickup increased capacity from three to five slots, retaining both original potions. Event/resume pickup and full-belt capacity-first behavior remain unverified |
| Special/extra combat rewards | At most eight event extras, at most one special card; gold/card/potion/relic collection | Lantern Key special card and Punch Off potion/relic extras demonstrated. Terminal schemas 9–10 support up to 32 total entries; event extras retain their eight-entry bound |
| Non-resuming event combat | Exact entry ownership → combat → rewards → map | Dense Vegetation, Lantern Key, Punch Off and initial Fake Merchant fight demonstrated |
| Resuming event combat | Exact original Resume callback/task → owned item reward if present → resumed event/Proceed/map | Dummy training expiry, Setting1 victory/potion and Setting2 victory demonstrated; consecutive matching combats also demonstrated. No recursive combat driver |
| Resume-time item rewards | One owned Offer with singleton or 2–8 potion/relic entries | Setting1 potion collect/skip/replacement demonstrated. Relic/set reward screens are fixture-only with no concrete resume caller identified; Setting3 obtains its relic directly. Resume-time cards/selectors unsupported |
| Fake Merchant inventory | Initially closed inventory → 0–6 supported relic purchases → close/Leave | Two-purchase visit demonstrated; zero/six purchase variants offline only; already-open entry unsupported |
| Fake Merchant fight/healing | Initial owned Foul Potion starts combat; terminal Fake Lee’s Waffle verifies capped 10% max-HP healing; terminal schemas 9–10 support 32 entries; schema 10 adds exact Fake Mango +3 max HP/+3 HP | Original ten-entry rewards passed after native Continue: 12/12/12 actions, all rewards collected, HP10/80→21/83 and actionable map. Earlier assisted seven-relic collection and the failed 8/8/7 Mango attempt retain separate evidence. Fight after shopping unsupported |
| Crystal Sphere | Owned Uncover Future/Payment Plan entry, small/big tool, legal 11×11 fog reveals, earned rewards and exact native exit/overlay cleanup | Both entry paths demonstrated; Uncover Future gold/map verified. Other tool/reward variants offline only. Hidden items are not projected; already-open adoption and full-belt replacement unsupported |
| Trial abandonment | Owned popup Cancel or explicit Confirm, exact native abandonment task | Both demonstrated; Cancel continued to rewards/map/next room, Confirm produced `run_abandoned` and native Defeat/HP0 |
| Architect ending | Native vote/queued action/next-act/WinRun task chain, terminal `run_won`; exact owned victory event with its combat layout and retained map-travel flag | Empty final-boss reward Proceed and the Architect parent sequence reached `run_won`; native Victory observed in both controlled saved runs. The latest ending used three reconciled parent actions. Saved continuations report `continued_victory`, not full-campaign certification |

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
- **Selectors:** direct input requires allocated native holders. Optional zero
  confirmation is supported on specific contracts; it is not native cancellation.
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

Neow's Bones remains a concrete implementation gap. Its two mandatory relic
rewards can themselves open more rewards (Lost Coffer, Kaleidoscope, Small Capsule),
card offers/bundles (Lead Paperweight, Massive Scroll, Hefty Tablet, Scroll Boxes),
or deck selectors (New Leaf, Precise Scissors, Pomander). It then adds one curse
through a native insertion task; the preview is visual only. The full producer
continues to reject its actionable parent before input.

The next extension needs one retained event owner with nested reward/pickup/selector
continuations and exact ancestor screen/stack bindings. Each child must be certified
before the outer callback's later mutations; the last reward can close and insert
the curse before another host read. Reusing the existing controllers under their
actual pickup task comes before removing the guard. Ordinary shared rewards do
not establish this compound caller or arbitrary nested effects.

### Contract limits without a confirmed missing gameplay caller

These are **not an implementation queue or required live-test checklist**:

- Dig popup/reward/multiple-selector follow-ups: the normal Common/Uncommon/Rare
  draw has no identified pickup-screen caller beyond current support. The bounded
  helper remains for injected setups. [Pool audit](EVENT_INTERACTION_MAP.md#dig-pool-audit-september-24).
  Mend belongs to multiplayer.
- Selectorless transform/add/enchantment variants retain their own contract limits;
  the new automatic-removal path does not broaden them.
- Multi-card Smith: no native count-changing caller found; removed as a feature gap.
- Variable-count upgrades, enchantment stacking/replacement, and unallocated-card
  input: retained contract limits, without a concrete necessary caller/setup.
- Resume-time card/selector reward screens and multi-item/relic reward screens:
  no concrete Resume caller identified. Dummy Setting1 offers one potion, Setting2
  upgrades automatically, and Setting3 obtains a relic directly.
- Nested pickup selectors outside the identified Neow's Bones chain, multiple
  independent selector children per callback, and broader post-selector deck
  changes beyond current one-grant support still require a concrete caller.
- Required direct card offers: v1 exists in fixtures, but the inspected Lead
  Paperweight/Massive Scroll callers are optional v2; there is no required-v1
  gameplay case to schedule yet.

### Implemented, but still needing representative live evidence

- Full-producer empty-chest completion, automatic pickup effects, shop
  Cauldron/Orrery and shared event reward children, plus an ending test.
  Representative hand/optional offers, potion use/discard and potion-owned choices,
  chest claiming, reroll and Sacrifice passed live, including the corrected
  Whetstone-granting second Sacrifice. Shop-removal preview cancellation also
  passed, with unchanged deck/gold and map return.
- Expanded terminal schemas 9–10: the representative ten-entry screen passed live.
  The wider 32-entry bound and 65-action card-menu sequence remain fixture/socket
  evidence, without a separately identified ordinary 32-entry gameplay caller.
- Selectorless removal: one-card Dark Door passed live. Empty domains, retained
  Eternal cards, other callers and adversarial variants remain fixture evidence.
- Shop passive relic/Potion Belt purchases, all five pickup selectors, and remaining
  zero-buy/kind/gold-reserve variants.
- Capacity-first Potion Belt collection in terminal, event and resume reward flows.
  The demonstrated terminal pickup verifies +2 capacity and retained potions;
  full-inventory ordering and the event/resume variants remain separate tests.
- True multi-upgrade selection using Trial/MerchantInnocent (two) or Yummy Cookie
  (four); held-out enchant/removal/transform callers such as Torus; Trial’s
  conditional curse-plus-two-transform path.
- Natural ancient entry/dialogue.
- Broader reward orders/outcomes with a concrete offered screen, Sphere small-tool
  and earned card/potion/relic variants, and Fake Merchant zero/six-purchase variants.
- Held-out elite and room-handoff variants beyond the accepted campaign route.
  The demonstrated long traversal does not establish all-branch coverage or
  strategic quality. Another fresh run is not required for milestone 7 acceptance.

[Roadmap](../ROADMAP.md) owns the order of work. [Caller evidence](EVENT_COVERAGE.md)
links the exact demonstrated paths; the [research map](EVENT_INTERACTION_MAP.md)
supplies dated source candidates rather than a current implementation checklist.

## Release and latest evidence

The current [release manifest](../bridge/Sts2AgentBridge/releases/current/bridge.json)
is **`1f83ded88af136170f2c1191bf28371aa435c9ab1616c011357fa64140e6f7e6`**.
It binds 461 source/test inputs across 52 projects, source `887c1da`, feature
`cc9fa81`. The gate passed **85 groups in 313.965 seconds**, including 168 client
tests, 1,628 router checks, 13,984 native event checks and 656 rest checks.
Independent semantic review is clear. The Whetstone correction observes the
actual model upgrade instead of a potentially inlined command wrapper. The exact
saved-run Whetstone retest passed **4/4/4 actions**, five reads and map return.
Normal quit and owned cleanup completed by **14:34:33 UTC**: four generated files
removed, zero overlays, all 429 base files unchanged.
The same package passed shop-removal preview cancellation: **5/5/5 actions**,
seven reads, unchanged deck/gold and map return. Normal quit and exact cleanup
completed by **14:54:07 UTC**, with four generated files removed and all 429 base
files unchanged. The following Lost Coffer attempt stopped before any policy
action (**0/0/0**, 34 reads): shop-based setup retained map-travel state incompatible
with the ancient entry guard. That source-supported setup diagnosis is separate
from live reward acceptance, which remains open. Cleanup finished by **15:13:49 UTC**;
the same package was reinstalled and verified by **15:14:15 UTC**, with two exact
owned overlays and unchanged base files. Corrected event-room setup awaits manual
launch on the saved campaign.

The preceding package `32d721e8…`, source `6c04327`, completed 35 actions before
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
