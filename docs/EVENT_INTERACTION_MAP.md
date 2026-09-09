# Event interaction research map

Updated 2026-09-09. This is the static event-to-interaction research overview for
Slay the Spire 2 v0.107.1 / Steam build 23811903. [Coverage](EVENT_COVERAGE.md)
owns implemented and live evidence; [roadmap](../ROADMAP.md) owns priorities.
The [research record and reproducible scanner](evidence/event_interactions_2026_09_09/README.md)
retain the pinned source identity, scope and validation. The
[structured inventory](evidence/event_interactions_2026_09_09/inventory.json)
contains all 68 types, 105 branch groups, pool references, source method tokens
and positive IL callsite offsets, plus immediate relic interactions.

Implementation update, later on September 9: [repeated ordinary pages](GENERIC_EVENTS.md#implemented-repeated-ordinary-option-pages)
now use completed callbacks and fresh native controls, with offline coverage.
The inventory and gap matrix below retain the original research comparison at
`4d3516f`; their source hashes and gap annotations are not repinned to later code.
Use [coverage](EVENT_COVERAGE.md) for current implementation/live evidence.

## What the research changes

- **Rewards need more than “multiple items.”** Ordinary events offer card rewards
  inside `RewardsSet`, including three card-reward entries in Colorful Philosophers.
  Those are different from the already implemented Cheese add-card grid.
- **Existing selectors do not cover every composition.** Grave of the Forgotten
  and Trial add a curse before requesting a selector. Amalgamator and several
  removal events add cards after selection. The current parent binds the earlier
  deck and requires the complete option task to finish before accepting the child
  effect. These are concrete compatibility gaps, even with supported card counts.
- **Repeated options needed a progress model at the research baseline.** Abyssal Baths reuses option IDs;
  Endless Conveyor can revisit a dish; Slippery Bridge eventually uses a `LOOP`
  suffix. The baseline structural stamp ignores changed text and rejects revisits.
  Numbered chains such as Colossal Flower or Tablet of Truth are separate
  validation cases, not automatic evidence that a new adapter is necessary.
- **Ancients expose additional shared selectors through relic pickup effects.**
  Claws requests zero-to-six transformations; Sea Glass uses optional card grids
  in successive passes; Scroll Boxes chooses a bundle. The current exact-layout
  check rejects `NAncientEventLayout` before any of those choices can run.
- **Named custom cases are now identified.** Crystal Sphere needs a cell-reveal
  minigame, Fake Merchant a custom merchant surface, Wood Carvings a generic deck
  selector followed by a fixed-result transformation, and Trial an abandon popup.
  The Architect ends in run/act progression rather than an ordinary map return.
- **Five event types request combat.** Battleworn Dummy explicitly resumes the
  event afterward; Dense Vegetation, Fake Merchant, Punch Off and The Lantern Key
  request combat without event resumption. “Fight” in Round Tea Party is ordinary
  option-driven damage, not combat.

## Scope and interpretation

The 68 concrete types match the earlier pinned census. Static pool references
account for **57 ordinary events** and **seven ancients**. Sunken Statue appears
in two ordinary act pools and is counted once. The other four types are Darv
(an ancient without a reference in the inspected act pools), The Architect
(a special terminal encounter event), and two deprecated placeholders.
Pool membership does not establish current-run eligibility: `IsAllowed`, unlocks,
act discovery order, character, multiplayer and modifiers can filter or change it.
No player progress was read and no encounter-frequency estimate is made.

The scan includes every declared method of those event types and their nested
state machines/lambdas, the shared event/card/reward machinery, act/shared pool
getters, named custom surfaces, and 135 explicitly referenced relic types.
Immediate relic pickup selectors are distinguished from effects that only trigger
later during combat. It is **not** a whole-game transitive proof through all random
relic outcomes, modifiers and global hooks. Such outcomes retain a conditional
coverage limit, including on otherwise ordinary direct-relic branches.

A branch group combines equivalent options or a bounded chain; 105 is not a count
of every possible generated option, random outcome or game-state branch. Method
names below identify native source paths. Locked options and ordinary Proceed are
implicit unless they have distinct behavior. Automatic HP/gold/card/relic effects
are executed by the game after choosing an option and do not by themselves need
another input adapter. Their generic parent effect summary remains `unverified`.

**“Candidate” below means no specific missing interaction was found in that
branch group. It is not a claim of runtime support or full-branch acceptance.**
Existing cardinality, allocated-holder, ownership and effect checks still apply.
Representative live results remain limited to Dense Vegetation, Cheese, Potion
Courier, Aroma and Sapphire Seed paths recorded in the coverage page. No new live
acceptance is claimed by this research.

## Interaction families and concrete blockers

Counts are distinct event types with an identified dependency, overlap across
rows, include named ancient pickup paths, and do not measure encounter frequency
or how many entire events a single change will complete.

| Required feature | Event types | Representative acceptance question |
| --- | ---: | --- |
| Event card rewards (`event_card_rewards`) | 6 | BrainLeech/Rip: collect or skip the native card reward and resume the event. |
| Multiple reward entries (`multiple_rewards`) | 10 | PotionCourier/GrabPotions: resolve three FoulPotion entries, including inventory-full behavior. |
| Deck changes around a child (`composite_deck`) | 7 | GraveOfTheForgotten/Confront: bind the selector after Decay; Amalgamator: reconcile removal plus merged-card grant. |
| Repeated-page progress (`repeat_progress`) | 3 | AbyssalBaths: complete two Linger actions with reused IDs, then exit; preserve bounded exactly-once ownership. |
| Ancient event layout (`ancient_layout`) | 8 | Neow: observe legal native option buttons, handle any required dialogue, choose a simple relic and reach map. |
| Combat event layout (`combat_layout`) | 3 | PunchOff/Nab: admit the combat-layout event even when choosing the noncombat branch. |
| Event combat handoff (`event_combat`) | 5 | DenseVegetation/Rest for combat exit; BattlewornDummy for actual return-to-event handling. |
| Multi-card enchantment (`multi_enchant`) | 3 | WaterloggedScriptorium/PricklySponge: exact two-card Steady selection and effect. |
| Zero/optional selection (`optional_select`) | 2 | Tanx/Claws: select zero or a positive subset; zero completion is not cancellation. |
| Sequential child ownership (`sequential_children`) | 1 | Orobas/SeaGlass: finish one optional grid, then handle the next while the same parent task is pending. |
| Generic deck → transform (`generic_deck_transform`) | 1 | WoodCarvings/Bird: select an eligible original on the generic deck grid and verify its fixed-result transform. |
| Choose-card surface (`choose_card`) | 1 | Neow/LeadPaperweight: choose through the native ChooseACard screen and add the exact card. |
| Bundle surface (`choose_bundle`) | 1 | Neow/ScrollBoxes: select one bundle and reconcile all its cards. |
| Card-results acknowledgment (`card_results`) | 1 | Darv/PandorasBox: acknowledge the automatic transformation results; Darv pool eligibility is unresolved. |
| Crystal Sphere minigame (`crystal_sphere`) | 1 | Reveal a legal cell using only public/revealed state; resolve earned rewards and exit. |
| Fake Merchant surface (`fake_merchant`) | 1 | Open inventory and make one legal interaction through the custom event owner. |
| Special card reward (`special_card_rewards`) | 1 | TheLanternKey combat: collect the specified SpecialCardReward through the right reward surface. |
| Abandon confirmation (`abandon_confirmation`) | 1 | Trial/DoubleDown: recognize the native popup and support cancellation; accepting is terminal. |
| Terminal event outcome (`terminal_event`) | 1 | TheArchitect: advance native dialogue and reconcile terminal progression without demanding map return. |

These are proposed acceptance questions for feature planning, not instructions to
run destructive branches or use privileged information. Native preconditions and
shared ownership remain necessary. The existing bridge has one production
composition; new families should extend its router, adapters and host.

A cross-cutting domain case also needs explicit handling: native
`FromDeckForRemoval` forwards to `FromDeckGeneric`, whose no-manual-confirmation
path returns all eligible cards when their count is at most `MinSelect`, without
creating a selector screen. The current parent rejects completed requests without
screens. For example, DoorsOfLightAndDark/Dark with only one eligible card is a
static candidate for testing **automatic selectorless completion**. This depends
on the domain, so it is not counted as another disjoint event family above. Empty
or dead-player paths also return without screens and must remain distinct from
successful automatic selection. No such live setup was run in this research.

## All-event map

“Shared” is `ModelDb.AllSharedEvents`; named acts refer to their `AllEvents` or
`AllAncients` getters. Gap identifiers are defined above. A listed gap can affect
only one branch of an event; other branches can remain candidates.

| Event type | Static pool | Branches and required interactions | Identified gaps |
| --- | --- | --- | --- |
| `AbyssalBaths` | Underdocks | **Abstain / ExitBaths** → options. Heal or finish.<br>**Immerse → Linger repeatedly** → options, repeated options. Repeated LINGER / EXIT_BATHS IDs; visible amounts or body text can change without structural stamp changing. | `repeat_progress` |
| `Amalgamator` | Hive | **CombineStrikes / CombineDefends** → options, removal selector, automatic deck effects. Select exactly two matching starter cards; remove them and add a merged card before the option finishes. | `composite_deck` |
| `AromaOfChaos` | Overgrowth | **LetGo** → options, transform selector. Fixed-one random transformation; representative live acceptance.<br>**MaintainControl** → options, upgrade selector. Fixed-one upgrade; native caller fixtures. | Candidate; caller validation remains |
| `BattlewornDummy` | Glory | **Setting1 / Setting2 / Setting3 → StartCombat → Resume** → options, event combat, item reward, automatic deck effects. All settings enter combat with shouldResume=true. Resume branches finish and can offer a potion, auto-upgrade cards or grant a relic. | `event_combat` |
| `BrainLeech` | Shared | **ShareKnowledge** → options, add-card grid. Choose one generated card; explicitly Cancelable=false.<br>**Rip** → options, card reward. Damage followed by CardReward through OfferCustom. | `event_card_rewards` |
| `Bugslayer` | Hive | **Extermination / Squash** → options, automatic deck effects. AddAndPreview grants the chosen fixed card; no card-selection request. | Candidate; caller validation remains |
| `ByrdonisNest` | Overgrowth | **Eat / Take** → options, automatic deck effects. Max HP or fixed card grant/preview. | Candidate; caller validation remains |
| `ColorfulPhilosophers` | Hive | **Generated color options → OfferRewards** → options, card reward, reward set. Three CardReward objects in one custom reward set. | `event_card_rewards`, `multiple_rewards` |
| `ColossalFlower` | Hive | **ExtractCurrentPrize / ExtractInstead / PollinousCore** → options. Gold or direct relic grant.<br>**ReachDeeper stages** → options, repeated options. Numbered stage keys lead to distinct ordinary option pages; validate the bounded chain before changing loop support. | Candidate; caller validation remains |
| `CrystalSphere` | Shared | **UncoverFuture / PaymentPlan** → options, minigame. Pay gold or add Debt, then play the cell-reveal minigame on NCrystalSphereScreen; earned results are separate from hidden board content. | `crystal_sphere` |
| `Darv` | Special / not in inspected pools | **Generated relic options / inherited Done** → ancient layout/options, transform selector, removal selector, reward set, card-results screen. Astrolabe transform-three; EmptyCage remove-two; CallingBell reward set after curse; PandorasBox result screen; remaining relic options apply automatic/passive effects. | `ancient_layout`, `card_results`, `multiple_rewards` |
| `DenseVegetation` | Overgrowth | **TrudgeOn** → options. Damage/gold then finish; representative continuation live evidence.<br>**Rest → Fight** → options, event combat. Rest followed by combat; shouldResume=false. | `event_combat` |
| `DeprecatedAncientEvent` | Deprecated | **GenerateInitialOptions** → placeholder. Deprecated ancient concrete type; excluded from active ancient planning. | `placeholder` |
| `DeprecatedEvent` | Deprecated | **GenerateInitialOptions** → placeholder. Deprecated concrete type; excluded from ordinary pool planning. | `placeholder` |
| `DollRoom` | Shared | **ChooseRandom / TakeSomeTime / Examine → ChooseDollAndShowDescription** → options. Random or displayed doll choices are ordinary EventOptions; direct relic grant and finish. | Candidate; caller validation remains |
| `DoorsOfLightAndDark` | Underdocks | **Light** → options, automatic deck effects. Automatically upgrades selected-by-game cards; no upgrade selector.<br>**Dark** → options, removal selector. Fixed-one removal. | Candidate; caller validation remains |
| `DrowningBeacon` | Underdocks | **BottleOption** → options, item reward. Singleton potion custom reward.<br>**ClimbOption** → options. Max-HP loss and direct relic grant. | Candidate; caller validation remains |
| `EndlessConveyor` | Underdocks | **ObserveChef / Leave** → options, automatic deck effects. Automatic upgrades or finish.<br>**GrabSomethingOffTheBelt repeatedly** → options, repeated options. Dish callback then new dish/Leave; recurring dish keys can collide with previously seen structures.<br>**JellyLiver / SuspiciousCondiment / other dishes** → transform selector, item reward, automatic deck effects. Fixed-one transform, singleton potion, or automatic card/HP/gold/upgrade effects; each dish returns to the belt page. | `repeat_progress` |
| `FakeMerchant` | Shared | **Merchant inventory / leave** → custom shop. NFakeMerchant owns merchant inventory and a custom Proceed button; no ordinary option list.<br>**FoulPotionThrown** → custom shop, event combat, reward set. Triggers combat with up to the explicitly constructed relic rewards; shouldResume=false. | `event_combat`, `fake_merchant`, `multiple_rewards` |
| `FieldOfManSizedHoles` | Hive | **EnterYourHole** → options, enchant selector. Fixed-one PerfectFit; player overload forwards to the supported list overload.<br>**Resist** → options, removal selector, automatic deck effects. Canonical fixed-two removal followed by Normality curse additions. | `composite_deck` |
| `GraveOfTheForgotten` | Glory | **Accept** → options. Direct ForgottenSoul grant.<br>**Confront** → options, enchant selector, automatic deck effects. Adds Decay before fixed-one SoulsPower selection; current pre-dispatch deck check rejects that changed deck. | `composite_deck` |
| `HungryForMushrooms` | Glory | **BigMushroom / FragrantMushroom** → options, automatic deck effects. Direct relic choices; FragrantMushroom AfterObtained performs automatic upgrades, not a selector. | Candidate; caller validation remains |
| `InfestedAutomaton` | Hive | **Study / TouchCore** → options, automatic deck effects. Generate/add/preview cards automatically. | Candidate; caller validation remains |
| `JungleMazeAdventure` | Overgrowth | **SoloQuest (DontNeedHelp) / JoinForces (SafetyInNumbers)** → options. Ordinary choices with HP/gold effects and synchronized presentation; multiplayer timing remains untested. | Candidate; caller validation remains |
| `LostWisp` | Hive | **Claim / Search** → options, automatic deck effects. Curses and direct relic, or gold; no selector request. | Candidate; caller validation remains |
| `LuminousChoir` | Overgrowth | **OfferTribute** → options. Gold payment and direct relic.<br>**ReachIntoTheFlesh** → options, removal selector, automatic deck effects. Fixed-two removal followed by SporeMind curse. | `composite_deck` |
| `MorphicGrove` | Overgrowth | **Loner** → options. Max-HP effect.<br>**Group** → options, transform selector. Gold loss followed by fixed-two random transformation. Gold does not alter the deck baseline. | Candidate; caller validation remains |
| `Neow` | Overgrowth ancient, Underdocks ancient | **Generated relic options / inherited Done** → ancient layout/options, removal selector, upgrade selector, transform selector, choose-card screen, bundle screen, reward set, card reward. Relic options include fixed removal/upgrade/transform, ChooseACard rewards, ScrollBoxes bundles and custom reward sets; see relic appendix. Modifier options are also generated conditionally. | `ancient_layout`, `choose_bundle`, `choose_card`, `event_card_rewards`, `multiple_rewards` |
| `Nonupeipe` | Glory ancient | **Generated relic options / inherited Done** → ancient layout/options, enchant selector. BeautifulBracelet requests Swift on three cards; remaining fixed relic options apply automatic/passive effects. | `ancient_layout`, `multi_enchant` |
| `Orobas` | Hive ancient | **Generated relic options / inherited Done** → ancient layout/options, enchant selector, card reward, reward set, add-card grid, optional selection. ElectricShrymp enchant-one; GlassEye five-card-reward set; SeaGlass optional generated-card selection across rarity passes; remaining options automatic/passive. | `ancient_layout`, `event_card_rewards`, `multiple_rewards`, `optional_select`, `sequential_children` |
| `Pael` | Hive ancient | **Generated relic options / inherited Done** → ancient layout/options, enchant selector, removal selector. PaelsGrowth enchant-one; PaelsTooth remove-five; remaining fixed relic options automatic/passive. | `ancient_layout` |
| `PotionCourier` | Shared | **Ransack** → options, item reward. Singleton potion; representative live acceptance.<br>**GrabPotions** → options, item reward, reward set. Canonical three FoulPotion rewards in one OfferCustom. | `multiple_rewards` |
| `PunchOff` | Underdocks | **Nab** → options, item reward, automatic deck effects. Injury then singleton relic reward; Combat layout blocks entry before this branch.<br>**TakeThem → Fight** → options, event combat, reward set. Combat layout; relic and potion extra rewards; shouldResume=false. | `combat_layout`, `event_combat`, `multiple_rewards` |
| `RanwidTheElder` | Shared | **GivePotion / GiveGold / GiveRelic** → options. The offered potion/relic identity is already encoded in an option; discard/pay/remove then obtain a relic. No inventory-selection overlay is requested. | Candidate; caller validation remains |
| `Reflections` | Glory | **TouchAMirror / Shatter** → options, automatic deck effects. Automatic downgrade/upgrade or card copies and BadLuck; no deck selector. | Candidate; caller validation remains |
| `RelicTrader` | Shared | **Top / Middle / Bottom / Done** → options. One indexed trade removes and grants a relic then Done; this is not a repeating trade loop. | Candidate; caller validation remains |
| `RoomFullOfCheese` | Shared | **Gorge** → options, add-card grid. Choose exactly two of eight offered cards; live acceptance.<br>**Search** → options. Damage and direct ChosenCheese grant; live path had zero item children. | Candidate; caller validation remains |
| `RoundTeaParty` | Glory | **EnjoyTea** → options. Direct relic and heal.<br>**PickFight → ContinueFight** → options. Ordinary follow-up, damage and relic; despite its name, this branch never requests combat. | Candidate; caller validation remains |
| `SapphireSeed` | Overgrowth | **Eat** → options, upgrade selector. Heal and fixed-one upgrade; live including allocated off-screen target.<br>**Plant** → options, enchant selector. Fixed-one Sown; live acceptance. | Candidate; caller validation remains |
| `SelfHelpBook` | Shared | **ReadTheBack / ReadPassage / ReadEntireBook / SkipBook** → options, enchant selector. SelectAndEnchant requests one filtered card: Sharp, Nimble or Swift; no available cards gives an ordinary skip option. | Candidate; caller validation remains |
| `SlipperyBridge` | Shared | **Overcome** → options, automatic deck effects. Automatically removes the currently offered card; not a removal selector.<br>**HoldOn repeatedly** → options, repeated options. Numbered keys eventually become LOOP at count >=7; the next structurally identical page can stall despite new card/text. | `repeat_progress` |
| `SpiralingWhirlpool` | Underdocks | **ObserveTheSpiral** → options, enchant selector. Fixed-one filtered Spiral enchantment.<br>**Drink** → options. Heal and finish. | Candidate; caller validation remains |
| `SpiritGrafter` | Hive | **LetItIn** → options, automatic deck effects. Heal and automatic card grant.<br>**Rejection** → options, upgrade selector. Fixed-one upgrade then damage. | Candidate; caller validation remains |
| `StoneOfAllTime` | Shared | **Lift** → options. Discard already-chosen potion and gain max HP; no potion-selector child.<br>**Push** → options, enchant selector. Damage then fixed-one Vigorous; amount is read from public event dynamic variables. | Candidate; caller validation remains |
| `SunkenStatue` | Overgrowth, Underdocks | **GrabSword / DiveIntoWater** → options. Direct SwordOfStone, or gold and damage. | Candidate; caller validation remains |
| `SunkenTreasury` | Underdocks | **FirstChest / SecondChest** → options, automatic deck effects. Gold, optionally Greed; no chest or reward-selection screen. | Candidate; caller validation remains |
| `Symbiote` | Shared | **Approach** → options, enchant selector. Fixed-one Corrupted.<br>**KillWithFire** → options, transform selector. Equal min/max from Cards dynamic variable (canonical value one), not evidence of optional/variable selection. | Candidate; caller validation remains |
| `TabletOfTruth` | Overgrowth | **Smash / GiveUp** → options. Heal or finish.<br>**Decipher repeatedly** → options, repeated options, automatic deck effects. Numbered ordinary pages; LoseMaxHpAndUpgrade performs automatic upgrades. No variable-count upgrade selector. | Candidate; caller validation remains |
| `Tanx` | Glory ancient | **Generated relic options / inherited Done** → ancient layout/options, transform selector, optional selection, enchant selector. Claws transforms zero to six cards to a specified result; TriBoomerang enchants three; remaining options automatic/passive. | `ancient_layout`, `multi_enchant`, `optional_select` |
| `TeaMaster` | Shared | **BoneTea / EmberTea / TeaOfDiscourtesy** → options. Pay if required, obtain fixed relic and finish. | Candidate; caller validation remains |
| `Tezcatara` | Hive ancient | **Generated relic options / inherited Done** → ancient layout/options, removal selector, upgrade selector, reward set. BiiigHug remove-four; YummyCookie upgrade-four; ToyBox custom relic reward set; remaining options automatic/passive. | `ancient_layout`, `multiple_rewards` |
| `TheArchitect` | Special / not in inspected pools | **AdvanceDialogue → WinRun** → combat layout, dialogue, terminal outcome. Combat layout; dialogue options lead to WinRun/act-change readiness rather than an event-to-map exit. Not in the ordinary event pools. | `combat_layout`, `terminal_event` |
| `TheFutureOfPotions` | Shared | **Generated potion options → Trade / Done** → options, card reward. Discard indexed potion, offer rarity-specific card reward with an AfterGenerated upgrade callback, then Done. | `event_card_rewards` |
| `TheLanternKey` | Hive | **ReturnTheKey** → options. Gold and finish; Combat layout blocks initial parent admission.<br>**KeepTheKey → Fight** → options, event combat, special card reward. Combat layout; SpecialCardReward extra; shouldResume=false. | `combat_layout`, `event_combat`, `special_card_rewards` |
| `TheLegendsWereTrue` | Shared | **NabTheMap** → options, automatic deck effects. Automatic card grant.<br>**SlowlyFindAnExit** → options, item reward. Damage then singleton potion reward. | Candidate; caller validation remains |
| `ThisOrThat` | Shared | **Plain / Ornate** → options, automatic deck effects. Damage/gold or direct relic plus Clumsy. | Candidate; caller validation remains |
| `TinkerTime` | Glory | **ChooseCardType → Attack / Skill / Power → RiderChosen** → options, automatic deck effects. Ordinary option pages construct the card, select a rider through options, then add/preview it. No card-selection overlay. | Candidate; caller validation remains |
| `TrashHeap` | Underdocks | **DiveIn / Grab** → options, automatic deck effects. Damage/direct relic or gold/automatic card grant. | Candidate; caller validation remains |
| `Trial` | Glory | **Accept → MerchantGuilty / NobleGuilty / NobleInnocent** → options, automatic deck effects. Ordinary verdict page, automatic curse/relic/heal/gold effects.<br>**MerchantInnocent / NondescriptInnocent** → options, upgrade selector, transform selector, automatic deck effects. Curse before fixed-two upgrade or fixed-two transform; incompatible pre-dispatch deck baseline.<br>**NondescriptGuilty** → options, card reward, automatic deck effects. Doubt then CardReward custom screen.<br>**Reject → Accept / DoubleDown** → options, confirmation popup, terminal outcome. DoubleDown creates NAbandonRunConfirmPopup; model as explicit confirmation/cancel and terminal outcome, not ordinary Proceed. | `abandon_confirmation`, `composite_deck`, `event_card_rewards` |
| `UnrestSite` | Overgrowth | **Rest / Kill** → options, automatic deck effects. Heal/curses or max-HP loss/direct relic. | Candidate; caller validation remains |
| `Vakuu` | Glory ancient | **Generated relic options / inherited Done** → ancient layout/options, removal selector, automatic deck effects. PreservedFog removes three then adds Folly; remaining fixed relic options automatic/passive. Combat-time relic choices are outside event resolution. | `ancient_layout`, `composite_deck` |
| `WarHistorianRepy` | Shared | **Initial/Second UnlockCage** → options, automatic deck effects. Consumes quest keys automatically, grants HistoryCourse; can expose the other ordinary choice.<br>**Initial/Second UnlockChest** → options, reward set, automatic deck effects. Consumes quest keys then two potions plus two relics in a custom reward set; possible follow-up cage choice. | `multiple_rewards` |
| `WaterloggedScriptorium` | Underdocks | **BloodyInk** → options. Max-HP effect.<br>**TentacleQuill** → options, enchant selector. Pay gold, fixed-one Steady.<br>**PricklySponge** → options, enchant selector. Pay gold, fixed-two Steady (Cards canonical value two). | `multi_enchant` |
| `WelcomeToWongos` | Shared | **BuyBargainBin / BuyFeaturedItem / BuyMysteryBox / Leave** → options, automatic deck effects. Ordinary purchase options and direct relic grants; Leave automatically downgrades a card. No shop surface or repeated purchase loop. | Candidate; caller validation remains |
| `Wellspring` | Overgrowth | **Bottle** → options, item reward. Singleton potion.<br>**Bathe** → options, removal selector, automatic deck effects. Fixed-one removal then conditional Guilty additions. Pure-removal outcome is only a subset. | `composite_deck` |
| `WhisperingHollow` | Overgrowth | **Hug** → options, transform selector. Fixed-one random transform then damage.<br>**Gold** → options, reward set. Gold payment then two potion rewards. | `multiple_rewards` |
| `WoodCarvings` | Overgrowth | **Snake** → options, enchant selector. Fixed-one Slither.<br>**Bird / Torus** → options, generic deck selector → transform. FromDeckGeneric uses NDeckCardSelectScreen and then TransformTo<Peck/ToricToughness>; current transformation request/screen hook pair does not cover it. | `generic_deck_transform` |
| `ZenWeaver` | Hive | **BreathingTechniques** → options, automatic deck effects. Pay and add fixed cards.<br>**EmotionalAwareness / ArachnidAcupuncture** → options, removal selector. Fixed-one / fixed-two removal, followed by gold payment. | Candidate; caller validation remains |

## Ancient relic pickup paths

Every row also depends on ancient layout admission. The inventory retains the
named relic references for each ancient, including options not shown in a
particular run. The source chain is `AncientEventModel.RelicOption` →
`RelicCmd.Obtain` → virtual `RelicModel.AfterObtained` → the concrete callback.
This is why scanning only event-local selector calls missed these requirements.
The table highlights 27 pickup paths that request an interaction or result screen;
other inspected relics perform automatic/passive pickup work. Random relic rewards
can bring additional pickup callbacks and are not exhaustively enumerated here.

| Relic | Ancient reference | Immediate interaction and limit |
| --- | --- | --- |
| `Astrolabe` | Darv | Fixed-three transform; creates upgraded replacements. Needs exact custom transformation preview/effect coverage. |
| `BeautifulBracelet` | Nonupeipe | Fixed-three Swift; multi-enchantment gap. |
| `BiiigHug` | Tezcatara | Fixed-four removal. |
| `CallingBell` | Darv | Curse then three relic rewards; obtaining one reward may invoke another pickup interaction. |
| `Claws` | Tanx | Zero through six selected originals, transformed to the specified Claw result; Cancelable=false. Zero completion is distinct from cancellation. |
| `ElectricShrymp` | Orobas | Fixed-one; amount supplied from its dynamic variable. |
| `EmptyCage` | Darv | Fixed-two removal. |
| `GlassEye` | Orobas | Five CardReward objects in a single custom reward set. |
| `HeftyTablet` | Neow | Choose a card on NChooseACardSelectionScreen, then add multiple copies; not the existing add-grid child. |
| `Kaleidoscope` | Neow | Builds multiple CardReward entries from generated cross-pool choices. |
| `LeadPaperweight` | Neow | ChooseACard screen, then add the chosen card. |
| `LostCoffer` | Neow | Card reward and potion together. |
| `MassiveScroll` | Neow | ChooseACard screen, then add the chosen card. |
| `NewLeaf` | Neow | Fixed-one random transformation. |
| `PaelsGrowth` | Pael | Fixed-one Clone enchantment. |
| `PaelsTooth` | Pael | Fixed-five filtered removal, with relic bookkeeping for the chosen cards. |
| `PandorasBox` | Darv | Automatic transformations followed by NSimpleCardsViewScreen; requires closing/acknowledging the result surface. |
| `Pomander` | Neow | Fixed-one upgrade. |
| `PrecariousShears` | Neow | Damage then fixed-two removal; HP changes do not change the deck baseline. |
| `PreciseScissors` | Neow | Fixed-one removal. |
| `PreservedFog` | Vakuu | Fixed-three removal then Folly; composite deck-effect boundary. |
| `ScrollBoxes` | Neow | NChooseABundleSelectionScreen, then add each card in the chosen bundle. |
| `SeaGlass` | Orobas | Multiple rarity passes; each offers min=0, max=offer count. Sequential children within one AfterObtained task; a pass may select zero or the entire offered domain. |
| `SmallCapsule` | Neow | One relic reward; its randomly obtained relic may have a further pickup interaction. |
| `ToyBox` | Tezcatara | Several randomly pulled wax relic rewards; pickup effects can introduce nested work. |
| `TriBoomerang` | Tanx | Fixed-three Instinct; multi-enchantment gap. |
| `YummyCookie` | Tezcatara | Fixed-four upgrade, not variable-count upgrading. |

## Planning implications

The research supports a discussion around these coherent increments:

1. **Make ordinary parent/child composition reliable.** Cover repeated option
   progress and deck changes around selectors. Each has a small representative
   caller and both affect paths that superficially look supported today.
2. **Expand the shared event reward flow.** Card rewards and multiple reward
   entries have direct ordinary-event callers. Reuse core reward machinery where
   its ownership/lifecycle semantics match; include return-to-event and nested
   pickup behavior explicitly rather than assuming a singleton-item extension is
   sufficient.
3. **Add the narrow selector gaps.** Two-card enchantment and Wood Carvings'
   generic deck transformation have concrete ordinary-event callers. Fixed-count
   removal/upgrade/transform paths that already fit need held-out native/live
   validation, not another implementation.
4. **Handle the other event layouts and combat lifecycle.** Ancient layout and
   combat layout are different admissions. Then cover non-resuming combat,
   resuming combat, and ancient pickup children: optional selection, bundles,
   ChooseACard and sequential children. These dependencies affect any proposed
   feature ordering.
5. **Give custom and terminal surfaces explicit adapters.** Crystal Sphere,
   Fake Merchant, the abandonment popup, card-results acknowledgment and The
   Architect have different legal inputs and completion states.

This is an evidence-based grouping for the next planning discussion, not a fixed
release schedule or a coverage-percentage promise. Priorities can favor common
pool membership, small acceptance cases, or full-run blockers; the static census
alone does not establish frequency or effort.

## Earlier assumptions to retire or narrow

- No event-local selector in this scan constructs unequal min/max bounds.
  `Symbiote.KillWithFire` reads a dynamic value but passes it as **equal** bounds.
  Concrete optional selectors were found through Claws and Sea Glass instead.
- No inspected event or immediate named pickup path established **variable-count
  upgrades** or a true native **cancelable** deck selector. Keep those capabilities
  deferred until a real caller is found; `Cancelable=false` with min=0 is not cancel.
- The 17 inspected referenced enchantment types inherit non-stackable behavior;
  the base native eligibility rule rejects an existing incompatible enchantment.
  Stacking/replacement is not an evidenced next feature for these callers.
- “Take a card,” “upgrade cards,” “chest,” “fight” and “shop” in event descriptions
  do not reliably identify the native input family. Sunken Treasury uses automatic
  gold/curse effects, Round Tea Party uses option-driven damage, and Welcome to
  Wongo's uses ordinary options. Wood Carvings is a transform effect on a different
  selector screen. Use the request/screen chain rather than names.
- This scan does not establish an unallocated-holder caller. Retain the known
  limitation, but select a real setup before designing scrolling/rebinding.

The next implementation should name its branch, required native surface,
observable effect and completion destination from this map. Existing live and
fixture evidence should be reused where its actual dependencies still match.
