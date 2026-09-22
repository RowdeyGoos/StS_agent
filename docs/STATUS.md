# Bridge support and status

Reviewed 2026-09-19 against bridge source, pinned native game IL and retained evidence. Latest live
session: **2026-09-13**. This is the authoritative summary of bridge support;
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
bounded interactions, not a complete autonomous run. Shared event mechanisms discover
supported requests at runtime; there is no blanket event-name allowlist. Automatic
parent effects generally remain `unverified` even when a child effect and map return
are verified. Final Proceed does not erase earlier verified child results.

## Supported interactions

### Combat, map and rooms

| Interaction | Implemented scope | Live evidence and limits |
| --- | --- | --- |
| Combat → rewards → map | Bounded combat, gold/card/item rewards, card choice or Skip, actionable-map check | Both card policies demonstrated; no autonomous full-run acceptance |
| Combat card choices | Owned discard/exhaust selections, including optional zero confirmation | Neow’s Fury zero/two-card choices and resumed victory demonstrated; other fixed/exhaust callers offline only |
| Map and room handoffs | Public legal map actions and bounded event/combat-to-map verification | Representative map/next-room transitions demonstrated; composite `*-map` clients verify the map but do not select a node |
| Rest | Heal/Proceed and Smith (one card); Lift, Kindle, Dig, Cook, Clone and Hatch in source | Heal/Smith demonstrated. The six additional actions have offline fixtures/build coverage only; see the native action table and limits below |
| Shop purchases | Cards, potions, supported passive relics, Potion Belt +2 slots; 0–8 purchases, kind policy, gold reserve and callback-certified restock | Seven-card/one-potion visit and three restocked potion purchases with original-potion replacement demonstrated. Passive relics, capacity and other policy variants need live coverage |
| Shop removal | Exact selected original, price/effect reconciliation, then separate inventory close and Leave | Demonstrated through map return; removing a card does not itself leave the shop |
| Shop pickup selectors | Dolly’s Mirror, Gnarled Hammer, Kifuda, Punch Dagger and Royal Stamp; exact native clone/enchantment selection | Implemented and offline tested; live coverage open. Other pickup callbacks are not generally supported |

### Native rest-site actions

These are actual options in the pinned game, with their enabling callers checked
in native IL. Availability still depends on the current run. The bridge supports
ordinary Heal and Smith, plus the six additional single-player options in source.
The new rest flow has its own native effect and selector checks.

| Option | Native source / trigger | Native behavior | Bridge |
| --- | --- | --- | --- |
| Heal | Default rest option | Heal, then run rest hooks and any generated rewards | Ordinary Heal/Proceed demonstrated; relic-triggered follow-up rewards not covered by that result |
| Smith | Default rest option | Select and upgrade **one** card | Supported; native cancellation is not exposed by the bridge |
| Dig | Shovel | Obtain a relic directly, including its pickup callback | Implemented in source; exact new relic and callback completion. One owned deck/enchantment selector of up to three cards; other follow-up surfaces stop |
| Lift | Girya, fewer than three lifts | Increase its lift counter, granting Strength in later combats | Implemented in source; exact +1 and native task completion checked. Offline fixtures/build only; not released or live demonstrated |
| Cook | Meat Cleaver | Remove two cards, gain nine max HP; native selection can be canceled | Implemented in source; exact requested original pair and +9 max HP. Cancellation remains unsupported |
| Clone | Pael’s Growth | Copy the deck’s Clone-enchanted cards | Implemented in source; scoped native insertion results, including add-time upgrades |
| Kindle | Pumpkin Candle | Add five to its remaining combat counter | Implemented in source; exact +5 and native task completion checked. Offline fixtures/build only; not released or live demonstrated |
| Hatch | Byrdonis Egg card | Obtain Byrdpip and transform every egg into Byrd Swoop | Implemented in source; exact relic and all egg transformations |
| Mend | Generated only with multiple players | Target and heal another player | Outside the current single-player bridge scope |

The six new options use `rest_v2` on the existing room-flow routes. They are
implemented and validated offline, **not released or live demonstrated**. A flow
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
| Remove | Positive selections up to eight with exact original preview/removal | Amalgamator fixed-two demonstrated; other counts/callers need evidence |
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
| Terminal reward potions | Stop-on-full, skip-full, skip-all, protected original-potion replacement | Skip-full, skip-all with full **and free** capacity, and replacement including distinct same-key potions demonstrated |
| Potion Belt capacity | Exact +2 empty slots, retained prior inventory, at most eight slots; terminal, event and resume paths | Implemented and offline tested; representative live capacity pickup remains open |
| Special/extra combat rewards | At most eight event extras, at most one special card; gold/card/potion/relic collection | Lantern Key special card and Punch Off potion/relic extras demonstrated. Complete terminal screen still limited to eight entries |
| Non-resuming event combat | Exact entry ownership → combat → rewards → map | Dense Vegetation, Lantern Key, Punch Off and initial Fake Merchant fight demonstrated |
| Resuming event combat | Exact original Resume callback/task → owned item reward if present → resumed event/Proceed/map | Dummy training expiry, Setting1 victory/potion and Setting2 victory demonstrated; consecutive matching combats also demonstrated. No recursive combat driver |
| Resume-time item rewards | One owned Offer with singleton or 2–8 potion/relic entries | Setting1 potion collect/skip/replacement demonstrated. Relic/set reward screens are fixture-only with no concrete resume caller identified; Setting3 obtains its relic directly. Resume-time cards/selectors unsupported |
| Fake Merchant inventory | Initially closed inventory → 0–6 supported relic purchases → close/Leave | Two-purchase visit demonstrated; zero/six purchase variants offline only; already-open entry unsupported |
| Fake Merchant fight/healing | Initial owned Foul Potion starts combat; terminal Fake Lee’s Waffle verifies capped 10% max-HP healing | Assisted seven-relic collection, HP33→41 at max80, Proceed/map/next room demonstrated. Setup removed ordinary rewards before the first core read; **original ten-entry screen is not supported by the eight-entry reader**. Fight after shopping unsupported |
| Crystal Sphere | Owned Uncover Future/Payment Plan entry, small/big tool, legal 11×11 fog reveals, earned rewards and exact native exit/overlay cleanup | Both entry paths demonstrated; Uncover Future gold/map verified. Other tool/reward variants offline only. Hidden items are not projected; already-open adoption and full-belt replacement unsupported |
| Trial abandonment | Owned popup Cancel or explicit Confirm, exact native abandonment task | Both demonstrated; Cancel continued to rewards/map/next room, Confirm produced `run_abandoned` and native Defeat/HP0 |
| Architect ending | Native vote/queued action/next-act/WinRun task chain, terminal `run_won` | **Known live failure:** initial bridge read returned `unsupported_state` at the prepared final Proceed; zero actions. Ending code is offline tested, but live terminal progression is not working/accepted |

<a id="current-exclusions"></a>

## Known failures and runtime limits

- **Architect admission:** native final-act setup reached the event, but the exact
  rejected admission predicate remains unknown. Diagnose it before another win
  attempt. Direct `event THE_ARCHITECT` is unavailable in the console catalog.
- **Cold-start reads:** intermittent owner-frame deadline failures remain unresolved.
  Fixed diagnostic codes/stage timings are available; later successful starts do
  not prove the cause is fixed. Reads retain the 500 ms frame-result deadline.
- **Terminal reward budget:** at most **eight entries per screen, three screens per
  game process, 17 accepted actions per screen/51 total**. A new client does not
  reset the process counter. Resume-item children use a separate path.
- **Global bounds:** 16,384 reads, 512 action reservations and 64 feature sessions;
  individual controllers have tighter limits. These are not full-run budgets.
- **Native ownership:** modules remain exclusive until reconciliation and successful
  disposal. Uncertain mutations or failed cleanup stop the host; no mutation retries.
  Only a known `stale_decision` with `mutation_state: none` permits bounded re-observation.
- **Selectors:** direct input requires allocated native holders. Optional zero
  confirmation is supported on specific contracts; it is not native cancellation.
- **Evidence boundary:** supported child effects do not certify all automatic parent
  rewards/costs. Setup-assisted tests do not establish natural eligibility, whole-event
  coverage, boss victory or autonomous play. Public-screen reads are not map probes.

## Implementation gaps versus remaining live tests

### Confirmed game interactions outside current support

- **Additional rest pickup follow-ups:** Dig supports one native deck/enchantment
  selector of up to three cards. Other popup/reward/multiple-selector surfaces are
  not supported. Mend belongs to multiplayer.
- **Native selector cancellation at rest:** Smith and Cook explicitly allow it.
  The bridge does not expose cancel; this is a real optional interaction, not
  required to complete the ordinary successful Smith path.
- **Oversized terminal reward screens:** Fake Merchant produced a ten-entry screen;
  the bridge projects at most eight. Assisted seven-relic collection does not solve it.
- **Selectorless automatic selection:** `FromDeckGeneric` can return all eligible
  cards without opening a screen when no manual confirmation is requested and
  count is at most the minimum. Doors of Light and Dark/Dark with one eligible
  removable card is a source-backed case; runtime compatibility remains unaccepted.
- **Longer/full-run orchestration:** actual runs exceed the current bounded client
  flows/process budgets; no complete autonomous run or strategic live policy is accepted.

Architect is an existing implementation with a **known live admission failure**,
not an absent terminal feature. Rest-triggered rewards (Dream Catcher card reward,
Tiny Mailbox’s two potion rewards) are also real; their continuation needs a compatibility
check before assigning a new adapter or claiming ordinary Heal covers them.

### Contract limits without a confirmed missing gameplay caller

These are **not an implementation queue or required live-test checklist**:

- Multi-card Smith: no native count-changing caller found; removed as a feature gap.
- Variable-count upgrades, enchantment stacking/replacement, and unallocated-card
  input: retained contract limits, without a concrete necessary caller/setup.
- Resume-time card/selector reward screens and multi-item/relic reward screens:
  no concrete Resume caller identified. Dummy Setting1 offers one potion, Setting2
  upgrades automatically, and Setting3 obtains a relic directly.
- Nested pickup selectors inside event/terminal rewards, multiple independent
  selector children per callback, and broader post-selector deck changes beyond
  current one-grant support: require an actual caller before new implementation.
- Required direct card offers: v1 exists in fixtures, but the inspected Lead
  Paperweight/Massive Scroll callers are optional v2; there is no required-v1
  gameplay case to schedule yet.

### Implemented, but still needing representative live evidence

- Shop passive relic/Potion Belt purchases, all five pickup selectors, and remaining
  zero-buy/kind/gold-reserve variants.
- Capacity-first Potion Belt collection in terminal, event and resume reward flows.
- True multi-upgrade selection using Trial/MerchantInnocent (two) or Yummy Cookie
  (four); held-out enchant/removal/transform callers such as Torus; Trial’s
  conditional curse-plus-two-transform path.
- Natural ancient entry/dialogue.
- Broader reward orders/outcomes with a concrete offered screen, Sphere small-tool
  and earned card/potion/relic variants, and Fake Merchant zero/six-purchase variants.
- Elite continuation and longer multi-room composition. Passing these does not by
  itself establish all-branch coverage or strategic quality.

[Roadmap](../ROADMAP.md) owns the order of work. [Caller evidence](EVENT_COVERAGE.md)
links the exact demonstrated paths; the [research map](EVENT_INTERACTION_MAP.md)
supplies dated source candidates rather than a current implementation checklist.

## Release and latest evidence

The accepted [release manifest](../bridge/Sts2AgentBridge/releases/current/bridge.json)
is **`cb2d91104d8cab404a0000f004e0d0dcef9b5850cff2e8273425e27c043a20b0`**.
It retains its original build provenance from the working checkout based on
`7334873`; implementation was subsequently committed in `cd3dc76`. Documentation
cleanup does not change that manifest or repin historical evidence.

The pinned target is **v0.107.1 / Steam 23811903 / macOS arm64**. This is the tested
build, not a claim about the currently installed game. The accepted gate passed
**71 groups in 262.450 seconds**, including reproducible build, package and owned
installation/cleanup checks; focused native/client/integration checks and independent
semantic review preceded it. See the [release record](../bridge/Sts2AgentBridge/releases/current/README.md)
and [validation](../bridge/Sts2AgentBridge/releases/current/validation.json).

The last recorded live session passed Dummy victory/resumption/map and visually
confirmed two automatic upgrades, then stopped at Architect admission with zero
Architect actions. Normal quit, stopped-process/closed-listener verification and
owned quarantine/purge completed: **installation absent at that September 13 cleanup**.
This documentation review did not recheck the running machine or launch the game.

| Evidence record | What it establishes |
| --- | --- |
| [September 12–13 multi-case ledger](evidence/MULTICASE_BRIDGE_LIVE_2026_09_12.md) | Current shop/potion/combat/resume/Trial/Merchant/Dummy results and unresolved Architect failure; exact releases, assistance, counts and cleanup |
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
[current backlog](HEADLESS_FULL_GAME_IMPLEMENTATION.md).
